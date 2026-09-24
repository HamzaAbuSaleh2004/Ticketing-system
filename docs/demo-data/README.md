# Demo tickets

`tickets.json` holds 25 support tickets for `SEED_DEMO=true` (PLAN.md Phase 10). The seeder loads this content instead of inventing tickets.

**Times are relative.** Every `*_minutes_ago` is minutes before the moment the seeder runs. There are no absolute dates and no SLA due dates in the file. The seeder computes those with `app/domain/sla.py`.

## Format

```jsonc
{
  "version": 1,
  "tickets": [
    {
      "ref": "t13",                        // stable key within this file (not the DB id)
      "parent_ref": "t24",                 // optional: follow-up of a closed ticket → tickets.parent_ticket_id
      "subject": "…",
      "description": "…",
      "requester_email": "user2@ticketing.demo",   // user1 or user2 from seed.py
      "assignee_email": "agent2@ticketing.demo",   // agent1–3, or null
      "status": "in_progress",             // new | triaged | open | in_progress | pending | resolved | closed
      "priority": "normal",                // low | normal | high | urgent (current, i.e. after any escalation)
      "category": "account-login",         // a seed.py category slug; null only on `new` tickets
      "escalated": true,                   // optional, default false
      "created_minutes_ago": 1200,
      "pending_minutes": 150,              // optional, see "Pending" below
      "resolved_minutes_ago": 1500,        // present iff status is resolved or closed
      "closed_minutes_ago": 4680,          // present iff status is closed
      "ai_summary": "…",                   // one-liner shown in the queue; absent on `new`
      "ai_triage": {                       // optional; the raw suggestion for tickets.ai_triage
        "category": "…", "priority": "…", "one_line_summary": "…",
        "suggested_response_draft": "…", "accepted_fields": ["priority"]
      },
      "comments": [
        { "author_email": "…", "body": "…", "is_internal_note": false, "minutes_ago": 1030 }
      ]
    }
  ]
}
```

## How the seeder should map it

Take `now = clock.now()` once, then for each ticket:

1. Set `created_at = now - created_minutes_ago`, and the same for `resolved_at`, `closed_at` and each comment's `created_at`.
2. Set `sla_response_due` and `sla_resolution_due` from `compute_due_dates(created_at, …)` using the `sla_policies` row for `priority`.
3. `pending_minutes` means different things depending on status:
   - **If `status == "pending"`:** the ticket is paused right now. Set `sla_paused_at = now - pending_minutes` and `sla_paused_total_seconds = 0`. Every pending ticket's latest comment is the agent's question that started the pause.
   - **Otherwise:** it's pause time already completed, from an earlier pending spell. Set `sla_paused_total_seconds = pending_minutes * 60` and push `sla_resolution_due` out by the same amount. That's the result `leave_pending` would have produced.
4. Set `first_responded_at` to the time of the earliest comment that is **public** and written by an **agent**. Leave it null if there's none. Every ticket past `triaged` has one, and each one lands within its priority's response window.
5. Write `ai_summary`, `ai_triage` and `escalated` straight to the matching columns.
   - If a triaged or later ticket has no `ai_triage`, the seeder may run `FakeProvider` triage, or leave the field null.
   - Escalated tickets already have the bumped priority and the senior assignee (agent3), so the SLA sweep's no-duplicate guard (`escalated = true`) leaves them alone.
6. Insert tickets oldest first, and resolve `parent_ref` to the parent's new id.
7. Write one `ticket.created` audit row per ticket with `actor_id = NULL`, so the audit trail isn't empty. Don't publish `ticket.created` events: the worker would re-triage the tickets.

## What the data covers

`node check-tickets.mjs` checks all of these; its output is below.

- **Every status:** new 3, triaged 3, open 5, in_progress 6, pending 3, resolved 3, closed 2.
- **Every priority:** urgent 3, high 5, normal 12, low 5.
- **All five categories:** billing 6, technical-issue 5, data-privacy 4, account-login 4, other 3.
  - The 3 `new` tickets have `category: null` and `priority: "normal"`. That's exactly what `POST /tickets` produces before triage runs.
- **2 escalated tickets**, both assigned to agent3 (the senior):
  - t11 (urgent, auto-escalation case, breached)
  - t14 (high, a manual escalation for a possible data exposure)
- **1 follow-up:** t25 was created after its closed parent t24, by the same requester.
- **Every SLA state at seed time:**
  - on track: 12
  - at risk: 3 (t04 on the response clock; t13 and t08 on the resolution clock)
  - breached: 2 (t11, t12)
  - paused: 3
  - none (resolved/closed): 5
- **Stable under the worker:**
  - No urgent/high ticket that isn't already escalated is at risk. Otherwise the 60s SLA sweep would escalate it straight after seeding.
  - Every resolved ticket was resolved less than 72h ago, so the auto-close sweep doesn't close it.
  - No customer replies after resolution, since those would reopen the ticket.
  - No customer replies during a current pause, since those would resume it.
- **Consistent assignees:** `new` and `triaged` tickets have no assignee; `open` and later tickets have one. Internal notes are always written by agents.

**The states drift after seeding.** The file is relative to seed time, so the clocks keep running. An on-track `normal` ticket becomes at risk hours later, and a `high` one can reach the sweep within about an hour. That's realistic, but a demo recorded long after seeding shows different SLA states. Re-seed, or reset the demo tickets, before a demo.

## Check output

```
$ node check-tickets.mjs
demo-data/tickets.json: 25 tickets parsed
status    closed=2 resolved=3 pending=3 open=5 in_progress=6 triaged=3 new=3
priority  high=5 normal=12 low=5 urgent=3
category  billing=6 technical-issue=5 other=3 data-privacy=4 account-login=4 null (new, untriaged)=3
SLA       none=5 paused=3 at risk=3 breached=2 on track=12
escalated t11 (urgent, in_progress, agent3@ticketing.demo), t14 (high, in_progress, agent3@ticketing.demo)
follow-up t25 -> parent t24
PASS: all checks
```

The check script is kept in the design-drafts folder outside the repo, and a copy is in this folder as `check-tickets.mjs`. Run it from this folder with `node check-tickets.mjs tickets.json`.
