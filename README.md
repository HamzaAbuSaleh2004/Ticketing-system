# Ticketing Portal

A two-portal customer support system. Customers search a Gemini-grounded knowledge base and send requests; agents work a shared queue with SLAs, AI triage, internal notes and an analytics dashboard; admins manage users, categories and SLA targets. It runs entirely on your machine with Docker Compose.

Requirements are in [ticketing-portal-brief.md](ticketing-portal-brief.md). The build plan, with per-phase evidence, is in [PLAN.md](PLAN.md).

## Start it

```
docker compose up --build
```

That's the whole setup: no `.env`, no manual steps. The `api` container runs the migrations, seeds the database (users, SLA policies, categories, 5 help articles and ~25 demo tickets), and starts the API. The `worker` container starts AI triage and the SLA sweeps.

| | |
|---|---|
| App | http://localhost:5173 |
| API | http://localhost:8000 (`GET /health`, interactive docs at `/docs`) |

To start over from an empty database: `docker compose down -v && docker compose up --build`.

## Sign in

Every seeded account uses the password `ChangeMe123!`. It's for local demos only.

| Email | Role | Lands on |
|---|---|---|
| `user1@ticketing.demo` (Uma User) | end user | the customer portal, `/` |
| `user2@ticketing.demo` (Leo Client) | end user | `/` |
| `agent1@ticketing.demo` (Tara Tier1) | agent, tier 1 | the agent console, `/agent` |
| `agent2@ticketing.demo` (Tom Tier1) | agent, tier 1 | `/agent` |
| `agent3@ticketing.demo` (Sasha Senior) | agent, senior (escalation queue) | `/agent` |
| `admin@ticketing.demo` (Ada Admin) | admin | `/admin` (also has the console) |

The demo seed also adds three customers: `priya.shah@`, `marco.rossi@` and `ines.duarte@ticketing.demo`. You can register new customer accounts at `/register`.

## AI: the fake provider or Gemini

Out of the box the stack uses a **deterministic fake AI provider**, so it works offline and tests are reproducible:

- **Triage** picks a category and priority from keywords and writes a draft reply.
- **KB search** embeds text with stemmed-word feature hashing, and answers by quoting the best-matching article, cited.

To use **real Gemini**:

1. `cp .env.example .env` and set `GEMINI_API_KEY=...`. `AI_PROVIDER` defaults to `auto`, which means Gemini whenever a key is set.
2. `docker compose up -d --force-recreate api worker`. On start, the seed re-embeds the help articles with Gemini, because their stored embedding model no longer matches.
3. Check it end to end: `docker compose exec api python scripts/smoke_gemini.py`. It triages a sample ticket and runs three KB questions, and it fails loudly if any call fell back to the fake.

Model IDs are set only in `backend/app/config.py` (`GEMINI_TRIAGE_MODEL`, `GEMINI_ANSWER_MODEL`, `GEMINI_EMBED_MODEL`, `EMBED_DIM`), and each can be overridden from `.env`. The integration uses Gemini's REST API directly through `httpx`, with no SDK.

- **When Gemini fails** (timeouts, 5xx, invalid output), triage and answers fall back to the fake and log a warning. The ticket still flows, and the agent sees "keyword fallback" in the AI panel. Query embeddings never fall back, because mixing vector spaces would corrupt search; KB search returns "unavailable" instead.
- Set `AI_PROVIDER=fake` to force the fake even when a key is present.

## What's in it

**Customer portal**
- **Help search**: the answer panel quotes help articles with numbered, linked citations, or says plainly when there's no answer and offers a request.
- **"Your requests"**: shows what's happening in plain language ("Waiting on you").
- **New request**: with an optional attachment. Triage lands a few seconds later, and the page shows the applied category and priority.
- **Reply box**: says what a reply will do. It reopens a resolved request within 72 hours; replying to a closed one starts a linked follow-up.

**Agent console**
- **Queue**: a dense queue filtered through the URL. `j`/`k` move and `Enter` opens. Every row has an SLA ring and countdown (on track, at risk, breached or paused).
- **Workspace**: three panes (queue, thread, properties). The thread has a Reply / Internal note composer; notes are never sent to customers, which is enforced in the API queries.
- **Properties**: a status control that offers only legal lifecycle moves, assignment, priority, category and Escalate. Escalating bumps priority and reassigns to the least-loaded senior agent.
- **AI triage panel**: per-field Accept and Override, "Use draft" and Re-run. The side panel also holds the full history.
- **Dashboard**: volume, median first-response and resolution times (paused time excluded), backlog by status, and SLA breaches.

**Admin**
- Users (role and team), categories, SLA policy targets, and a change log. Every change is audit-logged.

**Background worker**
- AI triage for every new ticket, from the `ticket.created` Redis Stream. Entries a failed or dead worker left pending are reclaimed and retried.
- Every 60s: auto-escalation of urgent/high tickets whose SLA is at risk, and auto-close of resolved tickets after the 72-hour reopen window.

**Lifecycle:** `new → triaged → open → in_progress ⇄ pending → resolved → closed`. The resolution SLA pauses while a ticket is pending.

## Design direction

Stated before any screen was built, as the brief asks. The full plan is in [docs/design-plan.md](docs/design-plan.md).

- **Seed colour:** `#1E6A5E` ("Spruce", a deep blue-green). At runtime, `@material/material-color-utilities` `SchemeContent` expands it into every Material 3 colour role for light and dark, at three contrast levels (Appearance menu). Components use only the `--md-sys-color-*` roles; there's no hand-picked palette.
- **Typefaces:** **Google Sans Flex** for display and headlines (with its `ROND` axis rounded in the customer portal and square in the console), and **Roboto Flex** for body, labels and data. Figures are tabular for IDs and countdowns. There's no monospace face.
- **Tone:** calm, spacious and reassuring for the customer portal; dense, scannable and efficient for the agent console.
- **Signature elements:** the grounded KB answer panel (customer) and the SLA ring on every queue row (agent).
- **Elevation:** tonal surfaces only, with no drop shadows.
- **Audits:** each UI phase passed a Material 3 compliance audit ([docs/audits/](docs/audits/)), and screenshots are in [docs/screenshots/](docs/screenshots/).

## Tests

```
docker compose exec api pytest              # backend: real Postgres (ticketing_test), not mocks
docker compose exec api ruff check app tests
cd frontend && npm ci && npx vitest run    # frontend unit tests (SLA, lifecycle, copy, charts)
cd frontend && npx playwright install chromium && npx playwright test   # end-to-end, against the running stack
```

- **Backend tests** create and migrate a separate `ticketing_test` database on the same Postgres, truncate between tests, and use Redis DB 15, so they never disturb the dev stack's data or worker.
- **Playwright specs** create their own data and restore anything shared that they change.

## When you change dependencies

- **Backend** (`backend/pyproject.toml` / `uv.lock`): `docker compose up -d --build api worker`. The venv lives at `/opt/venv` inside the image, so a rebuild always picks up the lockfile.
- **Frontend** (`frontend/package.json`): `node_modules` is an anonymous volume that Compose carries between recreates, so use `docker compose up -d --build --renew-anon-volumes frontend`.

File watching in the containers uses polling (`VITE_USE_POLLING`, `WATCHFILES_FORCE_POLLING`), because Docker Desktop bind mounts don't deliver file-change events.

## Moving to Google Cloud (iteration 2)

These are seams only; nothing is deployed in this iteration.

| Here | GCP | Change |
|---|---|---|
| Postgres + pgvector container | Cloud SQL (pgvector) | `DATABASE_URL` |
| Redis Streams `EventBus` | Pub/Sub | a new `events/` implementation |
| Gemini API key over REST | Vertex AI Gemini | a new `AIProvider` implementation and auth |
| Local attachment volume | Cloud Storage | the attachment storage module |
| uvicorn containers | Cloud Run | the Dockerfiles are 12-factor |
