# Demo tickets

`tickets.json` holds 25 support tickets for `SEED_DEMO=true` (PLAN.md Phase 10). The seeder loads this content instead of inventing tickets.

**Times are relative.** Every `*_minutes_ago` is minutes before the moment the seeder runs. There are no absolute dates in the file.

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
      "status": "in_progress",             // open | in_progress | pending | resolved | closed
      "priority": "normal",                // low | normal | high | urgent (current, i.e. after any escalation)
      "category": "account-login",         // a seed.py category slug; null only on a brand-new, untriaged ticket
      "escalated": true,                   // optional, default false
      "created_minutes_ago": 1200,
      "resolved_minutes_ago": 1500,        // present iff status is resolved or closed
      "closed_minutes_ago": 4680,          // present iff status is closed
      "ai_summary": "…",                   // one-liner shown in the queue; absent on an untriaged ticket
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
2. Set `first_responded_at` to the time of the earliest comment that is **public** and written by an **agent**. Leave it null if there's none.
3. Write `ai_summary`, `ai_triage` and `escalated` straight to the matching columns.
   - If a triaged ticket has no `ai_triage`, the seeder may run `FakeProvider` triage, or leave the field null.
   - Escalated tickets already have the bumped priority and the senior assignee (agent3).
4. Insert tickets oldest first, and resolve `parent_ref` to the parent's new id.
5. Write one `ticket.created` audit row per ticket with `actor_id = NULL`, so the audit trail isn't empty. Don't publish `ticket.created` events: the worker would re-triage the tickets.

## What the data covers

`node check-tickets.mjs` checks all of these; its output is below.

- **Every status:** open 11, in_progress 6, pending 3, resolved 3, closed 2.
- **Every priority:** urgent 3, high 5, normal 12, low 5.
- **All five categories:** billing 6, technical-issue 5, data-privacy 4, account-login 4, other 3.
  - 3 `open` tickets have `category: null` and `priority: "normal"`: brand-new and untriaged, exactly what `POST /tickets` produces before an agent triages it.
- **2 escalated tickets**, both assigned to agent3 (the senior):
  - t11 (urgent, previously the auto-escalation case)
  - t14 (high, a manual escalation for a possible data exposure)
- **1 follow-up:** t25 was created after its closed parent t24, by the same requester.
- **Consistent assignees:** an untriaged (`category: null`) ticket has no assignee; every other ticket past `open` has one. Internal notes are always written by agents.

## Check output

```
$ node check-tickets.mjs
demo-data/tickets.json: 25 tickets parsed
status    closed=2 resolved=3 pending=3 open=11 in_progress=6
priority  high=5 normal=12 low=5 urgent=3
category  billing=6 technical-issue=5 other=3 data-privacy=4 account-login=4 null (untriaged)=3
escalated t11 (urgent, in_progress, agent3@ticketing.demo), t14 (high, in_progress, agent3@ticketing.demo)
follow-up t25 -> parent t24
PASS: all checks
```

The check script is kept in the design-drafts folder outside the repo, and a copy is in this folder as `check-tickets.mjs`. Run it from this folder with `node check-tickets.mjs tickets.json`.
