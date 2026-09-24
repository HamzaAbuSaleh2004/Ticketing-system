# Ticketing Portal — Iteration 1 Build Brief

## Context
Two-portal customer support ticketing system (end-user + agent/management), built to feel Google-designed (Material 3), running fully local for this iteration, with a clean migration path to Google Cloud Console (Cloud Run, Cloud SQL, Pub/Sub, Vertex AI/Gemini) for iteration 2. Gemini is used for smart search and ticket triage.

**Non-goals for this iteration:** no GCP deployment, no multi-channel intake (email/social), no omnichannel, no advanced automation rules engine — get one clean end-to-end flow working locally first.

## Tech stack (all local, all Docker Compose)
- Frontend: React + TypeScript, Material Design 3 components (Material Web / MUI themed to M3 tokens — do not use default Tailwind/shadcn look)
- Backend: Node.js (Express) or Python (FastAPI) — pick one and stay consistent
- Database: PostgreSQL
- Cache/queue stand-in: Redis
- Auth: JWT-based, roles = `end_user`, `agent`, `admin`
- AI: Gemini API called directly via REST (no cloud infra needed yet)
- Everything wired together with `docker-compose.yml` — one command (`docker compose up`) brings up db + api + frontend + redis

## Data model (Postgres)
- `users`: id, email, password_hash, role, team, created_at
- `tickets`: id, subject, description, status, priority, category, requester_id, assignee_id, sla_response_due, sla_resolution_due, created_at, updated_at, resolved_at, closed_at
- `ticket_comments`: id, ticket_id, author_id, body, is_internal_note (bool), created_at
- `attachments`: id, ticket_id, comment_id (nullable), file_path, filename, content_type
- `sla_policies`: id, name, priority, response_minutes, resolution_minutes
- `knowledge_base_articles`: id, title, body, tags, embedding (for later semantic search)
- `audit_log`: id, entity_type, entity_id, actor_id, action, diff_json, created_at

## Ticket lifecycle (state machine — implement exactly this)
`new` → `triaged` (Gemini suggests category/priority/assignee, agent can override) → `open` (assigned) → `in_progress` ⇄ `pending` (waiting on customer reply; **SLA resolution timer pauses while pending**) → `resolved` (customer can still reply within a cooling-off window, which reopens to `in_progress`) → `closed` (locked, read-only; a reply to a closed ticket creates a new linked follow-up ticket, it does not reopen the old one).

Escalation is not a separate status — it's a priority bump + reassignment to a senior/manager queue that can happen from any active status when SLA is at risk or severity is high.

## API surface (minimum for iteration 1)
- `POST /auth/login`, `POST /auth/register`
- `POST /tickets` (create), `GET /tickets` (list, filterable by status/priority/assignee/category), `GET /tickets/:id`, `PATCH /tickets/:id` (status/assignee/priority changes — write to audit_log)
- `POST /tickets/:id/comments` (public reply or internal note)
- `GET /kb/search?q=` — Gemini-grounded knowledge base search
- `POST /tickets/:id/ai-triage` — internal endpoint the backend calls on ticket creation to get Gemini's suggested category/priority/summary
- `GET /analytics/summary` — volume, first-response time, resolution time, backlog by status (agent portal dashboard)

## Gemini integration (iteration 1 scope — keep it to these two)
1. **Auto-triage on ticket creation**: send subject + description to Gemini, get back `{category, priority, one_line_summary, suggested_response_draft}` as structured JSON. Agent can accept or override every field. This is the single highest-leverage AI feature — do this first.
2. **KB smart search**: embed KB articles (Gemini embeddings), do semantic search against the query, return grounded answers with source article links for the end-user portal's search box.

Do not build sentiment analysis, draft-response-in-thread, or the ADK multi-agent triage system in this iteration — those are documented as iteration-2/3 stretch goals, not blockers for a working first version.

## Two portals, one app
Single React app, role-gated views:
- **End-user view**: submit ticket, list/track own tickets, reply, KB search box
- **Agent view**: shared queue with filters, ticket detail (thread + internal notes), assign/status controls, basic analytics dashboard
- **Admin**: user/role management, category list, SLA policy editor (can be a minimal settings page for now)

## Design direction — read before writing any UI code
This must read as deliberately Google-designed, not as generic AI-generated UI. Two things have to be true at once:
1. **Authentically Material 3**: dynamic color from a single seed color expanded into tonal roles (not a hardcoded hex palette), Google Sans / Google Sans Text or Roboto Flex for type (not Inter, not system-ui), M3's elevation-via-tonal-surface (not drop shadows), M3 shape scale (fully rounded corners by default).
2. **Not generic-AI-slop despite using a known design system**: pick one specific seed color and a specific type pairing before writing any component and state that choice up front — don't let the model default to Google-blue-on-white. Vary elevation and information density deliberately between the two portals (the agent queue is dense/data-forward; the end-user portal is calmer/more spacious). No purple gradients, no centered-hero-with-illustration template, no generic card-grid-of-everything layout.

Before generating any screen, state: the seed color, the two typefaces (display + body), and one sentence on tone (e.g. "calm and reassuring for the end-user portal, dense and efficient for the agent console").

## Acceptance criteria for "done" on iteration 1
- [ ] `docker compose up` brings up the full stack with no manual steps
- [ ] End-user can submit a ticket, see it appear in their list, and get a Gemini-suggested category/priority applied automatically
- [ ] Agent can see the ticket in the queue, reassign/change status through the full lifecycle above, and add an internal note
- [ ] SLA due timestamps are set on ticket creation and correctly pause while status = `pending`
- [ ] KB search box returns a Gemini-grounded answer with a source link for at least 3 seeded KB articles
- [ ] Both portals are visibly Material 3, with the seed color/typography choice stated and consistent across screens
