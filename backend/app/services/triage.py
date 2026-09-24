"""AI triage of a ticket. Shared by the worker (on `ticket.created`) and
`POST /tickets/:id/ai-triage` (the agent's "Re-run triage").

`tickets.ai_triage` shape:
    {"suggestion": TriageSuggestion, "model": str, "generated_at": iso8601,
     "accepted_fields": {field: "auto" | "accepted" | "overridden"}}
"auto" = applied by the system on first triage; the agent's decisions
replace it (see record_ai_field_decisions).
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.provider import AIProvider
from app.domain import clock
from app.domain.audit import write_audit
from app.models import Category, Ticket
from app.models.enums import TicketPriority, TicketStatus
from app.schemas.ai import CategoryOption
from app.services.tickets import lock_ticket, set_priority

logger = logging.getLogger(__name__)


async def triage_ticket(
    session: AsyncSession,
    ticket_id: int,
    provider: AIProvider,
    *,
    actor_id: int | None = None,
    force: bool = False,
) -> Ticket | None:
    """Without `force` (the worker), a ticket that already has a triage is
    left alone, so a redelivered event is a no-op. Category/priority are
    applied and the status moves to `triaged` only while the ticket is still
    `new`, and never over a field an agent changed while the model call was
    in flight. On a later re-run the fresh suggestion is stored for the agent
    to accept or override; earlier decisions are kept for every field whose
    suggested value didn't change."""
    ticket = await session.get(Ticket, ticket_id)
    if ticket is None or (ticket.ai_triage is not None and not force):
        return ticket

    categories = [
        CategoryOption(slug=c.slug, name=c.name)
        for c in (await session.scalars(select(Category).where(Category.active.is_(True)).order_by(Category.id)))
    ]
    subject, description = ticket.subject, ticket.description
    snapshot = {"category": ticket.category, "priority": ticket.priority}
    # End the read transaction before the (up to ~1 min with retries) model
    # call, so no connection or lock is held while waiting on Gemini.
    await session.commit()

    result = await provider.triage(subject=subject, description=description, categories=categories)
    suggestion = result.suggestion

    ticket = await lock_ticket(session, ticket_id)
    if ticket is None or (ticket.ai_triage is not None and not force):
        await session.commit()  # releases the lock; rollback would expire `ticket`
        return ticket

    now = clock.now()
    before: dict = {"ai_summary": ticket.ai_summary}
    after: dict = {"ai_summary": suggestion.one_line_summary}
    new_suggestion = suggestion.model_dump(mode="json")
    accepted_fields = _carried_over_decisions(ticket.ai_triage, new_suggestion)

    if ticket.status is TicketStatus.new:
        category_untouched = ticket.category == snapshot["category"]
        priority_untouched = ticket.priority == snapshot["priority"]
        if category_untouched and suggestion.category in {c.slug for c in categories}:
            if suggestion.category != ticket.category:
                before["category"], after["category"] = ticket.category, suggestion.category
                ticket.category = suggestion.category
            accepted_fields["category"] = "auto"
        if priority_untouched:
            if suggestion.priority != ticket.priority:
                before["priority"], after["priority"] = ticket.priority.value, suggestion.priority.value
                await set_priority(session, ticket, TicketPriority(suggestion.priority))
            accepted_fields["priority"] = "auto"
        before["status"], after["status"] = ticket.status.value, TicketStatus.triaged.value
        ticket.status = TicketStatus.triaged

    ticket.ai_summary = suggestion.one_line_summary
    ticket.ai_triage = {
        "suggestion": new_suggestion,
        "model": result.model,
        "generated_at": now.isoformat(),
        "accepted_fields": accepted_fields,
    }

    await write_audit(
        session,
        entity_type="ticket",
        entity_id=ticket.id,
        actor_id=actor_id,
        action="ticket.ai_triaged",
        diff={"before": before, "after": after, "model": result.model},
    )
    await session.commit()
    await session.refresh(ticket)
    logger.info("triaged ticket %s with %s", ticket.id, result.model)
    return ticket


def _carried_over_decisions(previous: dict | None, new_suggestion: dict) -> dict[str, str]:
    if previous is None:
        return {}
    old_suggestion = previous.get("suggestion") or {}
    return {
        field: decision
        for field, decision in (previous.get("accepted_fields") or {}).items()
        if old_suggestion.get(field) == new_suggestion.get(field)
    }


def record_ai_field_decisions(ticket: Ticket, decisions: dict[str, str]) -> tuple[dict, dict] | None:
    """Merges {field: "accepted" | "overridden"} into ai_triage.accepted_fields.
    Returns the (before, after) accepted_fields for the audit diff, or None
    if nothing changed or the ticket has no triage."""
    if ticket.ai_triage is None or not decisions:
        return None
    current = dict(ticket.ai_triage.get("accepted_fields") or {})
    merged = {**current, **decisions}
    if merged == current:
        return None
    # A new dict (not in-place mutation), so SQLAlchemy sees the JSONB change.
    ticket.ai_triage = {**ticket.ai_triage, "accepted_fields": merged}
    return current, merged
