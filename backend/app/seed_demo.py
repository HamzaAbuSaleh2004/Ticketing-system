"""Demo tickets for SEED_DEMO (PLAN.md Phase 10), loaded from
docs/demo-data/tickets.json (mounted at DEMO_DATA_PATH) and mapped exactly
as docs/demo-data/README.md specifies. Runs only when there are no tickets
at all, so it never touches real data and re-running is a no-op.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import clock
from app.domain.audit import write_audit
from app.domain.sla import compute_due_dates
from app.models import (
    AuditLog,
    SlaPolicy,
    Ticket,
    TicketActionItem,
    TicketComment,
    User,
)
from app.models.enums import ActionItemSide, TicketPriority, TicketStatus, UserRole

logger = logging.getLogger(__name__)

_AGENT_ROLES = (UserRole.agent, UserRole.admin)

# Phase 12 addition: a few "what's needed" items on active tickets, so the
# queue and workspace aren't empty of them. Not part of tickets.json (which
# predates action items and has its own fixed-content contract) - these are
# generic enough to make sense regardless of which tickets they land on.
_CUSTOMER_ACTION_ITEMS = [
    "Reply with a screenshot of the error",
    "Confirm the account email on the invoice",
    "Share the order or reference number",
]
_LIVERX_ACTION_ITEMS = [
    "Check the account's recent login history",
    "Confirm the refund with billing",
    "Follow up once the fix ships",
]


def load_demo_file(path: str) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("version") != 1:
        raise ValueError(f"Unsupported demo data version {data.get('version')!r}")
    return data["tickets"]


async def seed_demo_tickets(session: AsyncSession, path: str) -> int:
    if await session.scalar(select(func.count()).select_from(Ticket)):
        return 0
    if not Path(path).is_file():
        logger.info("seed: no demo data at %s; skipping demo tickets", path)
        return 0

    tickets = load_demo_file(path)
    emails = {t["requester_email"] for t in tickets}
    emails |= {t["assignee_email"] for t in tickets if t.get("assignee_email")}
    emails |= {c["author_email"] for t in tickets for c in t.get("comments", [])}
    users = {u.email: u for u in await session.scalars(select(User).where(User.email.in_(emails)))}
    missing = emails - users.keys()
    if missing:
        raise ValueError(f"Demo data references unknown users: {sorted(missing)}")
    policies = {p.priority: p for p in await session.scalars(select(SlaPolicy))}

    # One "now" for every relative offset in the file (README step 1).
    now = clock.now()

    def ago(minutes: float) -> datetime:
        return now - timedelta(minutes=minutes)

    ids_by_ref: dict[str, int] = {}
    inserted: list[Ticket] = []

    # Oldest first, so a follow-up's parent already has an id (step 6).
    for t in sorted(tickets, key=lambda t: t["created_minutes_ago"], reverse=True):
        created = ago(t["created_minutes_ago"])
        priority = TicketPriority(t["priority"])
        status = TicketStatus(t["status"])
        policy = policies[priority]
        # Step 2: due dates through domain/sla.py, not by hand.
        response_due, resolution_due = compute_due_dates(
            created, response_minutes=policy.response_minutes, resolution_minutes=policy.resolution_minutes
        )

        ticket = Ticket(
            subject=t["subject"],
            description=t["description"],
            status=status,
            priority=priority,
            category=t.get("category"),
            requester_id=users[t["requester_email"]].id,
            assignee_id=users[t["assignee_email"]].id if t.get("assignee_email") else None,
            # Inherited from the requester, exactly like a live POST /tickets.
            organization_id=users[t["requester_email"]].organization_id,
            created_at=created,
            sla_response_due=response_due,
            sla_resolution_due=resolution_due,
            escalated=bool(t.get("escalated")),
            parent_ticket_id=ids_by_ref[t["parent_ref"]] if t.get("parent_ref") else None,
            resolved_at=ago(t["resolved_minutes_ago"]) if "resolved_minutes_ago" in t else None,
            closed_at=ago(t["closed_minutes_ago"]) if "closed_minutes_ago" in t else None,
        )

        # Step 3: pending_minutes is the current pause for pending tickets, and
        # completed pause time (what leave_pending would have produced) otherwise.
        if "pending_minutes" in t:
            if status is TicketStatus.pending:
                ticket.sla_paused_at = ago(t["pending_minutes"])
                ticket.sla_paused_total_seconds = 0
            else:
                ticket.sla_paused_total_seconds = t["pending_minutes"] * 60
                ticket.sla_resolution_due = resolution_due + timedelta(minutes=t["pending_minutes"])

        comments = sorted(t.get("comments", []), key=lambda c: c["minutes_ago"], reverse=True)
        # Step 4: the earliest public comment written by an agent.
        public_agent = [
            c for c in comments if not c["is_internal_note"] and users[c["author_email"]].role in _AGENT_ROLES
        ]
        ticket.first_responded_at = ago(public_agent[0]["minutes_ago"]) if public_agent else None

        events = [created, ticket.resolved_at, ticket.closed_at, ticket.sla_paused_at]
        events += [ago(c["minutes_ago"]) for c in comments]
        ticket.updated_at = max(e for e in events if e is not None)

        session.add(ticket)
        await session.flush()
        ids_by_ref[t["ref"]] = ticket.id
        inserted.append(ticket)

        for c in comments:
            session.add(
                TicketComment(
                    ticket_id=ticket.id,
                    author_id=users[c["author_email"]].id,
                    body=c["body"],
                    is_internal_note=c["is_internal_note"],
                    created_at=ago(c["minutes_ago"]),
                )
            )
        # Step 7: one ticket.created audit row per ticket, as the system, dated
        # at the ticket's own creation (not seed time).
        await write_audit(
            session,
            entity_type="ticket",
            entity_id=ticket.id,
            actor_id=None,
            action="ticket.created",
            diff={"after": {"status": status.value, "priority": priority.value}, "source": "demo-seed"},
        )
        await session.flush()
        await session.execute(
            update(AuditLog)
            .where(AuditLog.entity_type == "ticket", AuditLog.entity_id == ticket.id)
            .values(created_at=created)
        )

    # A few "what's needed" items on active, assigned tickets - enough that
    # the queue and workspace show some, without touching tickets.json.
    active = [
        t for t in inserted
        if t.status in (TicketStatus.open, TicketStatus.in_progress, TicketStatus.pending) and t.assignee_id
    ]
    for i, ticket in enumerate(active[:3]):
        customer_done = i == 0
        session.add(
            TicketActionItem(
                ticket_id=ticket.id,
                side=ActionItemSide.customer,
                description=_CUSTOMER_ACTION_ITEMS[i % len(_CUSTOMER_ACTION_ITEMS)],
                created_by=ticket.assignee_id,
                done=customer_done,
                done_at=ticket.updated_at if customer_done else None,
                done_by=ticket.requester_id if customer_done else None,
            )
        )
        session.add(
            TicketActionItem(
                ticket_id=ticket.id,
                side=ActionItemSide.liverx,
                description=_LIVERX_ACTION_ITEMS[i % len(_LIVERX_ACTION_ITEMS)],
                created_by=ticket.assignee_id,
            )
        )

    await session.commit()
    return len(tickets)
