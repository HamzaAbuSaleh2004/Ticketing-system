# Ticketing Portal

A two-portal customer support system. Customers search the help articles and send requests; agents triage and work a shared queue with SLAs, internal notes and an analytics dashboard; admins manage users, categories and SLA targets. It runs entirely on your machine with Docker Compose.

Requirements are in [ticketing-portal-brief.md](ticketing-portal-brief.md). The build plan, with per-phase evidence, is in [PLAN.md](PLAN.md).

## Start it

```
docker compose up --build
```

That's the whole setup: no `.env`, no manual steps. The `api` container runs the migrations, seeds the database (users, SLA policies, categories, 5 help articles and ~25 demo tickets), and starts the API. The `worker` container runs the SLA sweeps.

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

## Two-step verification

Every account, customer or LiverX staff, signs in with a password **and** a 6-digit code from an authenticator app (Google Authenticator, Microsoft Authenticator, 1Password…). The first sign-in shows a QR code to set it up, then 10 single-use recovery codes. An admin can reset someone's two-step verification from Admin → Users; they set it up again at their next sign-in, and their old sessions end.

The local demo accounts above already have it set up on a shared, published key: add `LIVERXDEMOTOTPSECRETFORLOCALONLY` to your authenticator app (as a time-based key) to sign in as any of them. Demo accounts are never created when `ENV=prod`.

## What's in it

**Customer portal**
- **Help search**: the answer panel quotes help articles with numbered, linked citations, or says plainly when there's no answer and offers a request.
- **"Your requests"**: shows what's happening in plain language ("Waiting on you").
- **New request**: with an optional attachment. The page says the team will review it; once an agent triages it, it shows the category and priority.
- **Reply box**: says what a reply will do. It reopens a resolved request within 72 hours; replying to a closed one starts a linked follow-up.

**Agent console**
- **Queue**: a dense queue filtered through the URL. `j`/`k` move and `Enter` opens. Every row has an SLA ring and countdown (on track, at risk, breached or paused).
- **Workspace**: three panes (queue, thread, properties). The thread has a Reply / Internal note composer; notes are never sent to customers, which is enforced in the API queries.
- **Properties**: a status control that offers only legal lifecycle moves, assignment, priority, category and Escalate. Escalating bumps priority and reassigns to the least-loaded senior agent.
- **Manual triage**: agents set category and priority, then move `new → triaged`. The side panel also holds the full history.
- **Dashboard**: volume, median first-response and resolution times (paused time excluded), backlog by status, and SLA breaches.

**Admin**
- Users (role and team), categories, SLA policy targets, and a change log. Every change is audit-logged.

**Background worker**
- Every 60s: auto-escalation of urgent/high tickets whose SLA is at risk, and auto-close of resolved tickets after the 72-hour reopen window.

**Lifecycle:** `new → triaged → open → in_progress ⇄ pending → resolved → closed`. The resolution SLA pauses while a ticket is pending.

## Design direction

Stated before any screen was built, as the brief asks. The full plan is in [docs/design-plan.md](docs/design-plan.md).

- **Seed colour:** `#00A4D8` (LiverX Bright Cyan Blue). At runtime, `@material/material-color-utilities` `SchemeContent` expands it into every Material 3 colour role for light and dark, at three contrast levels (Appearance menu). Components use only the `--md-sys-color-*` roles; there's no hand-picked palette.
- **Typefaces:** **IBM Plex Sans** for every role (display, headlines, body, labels and data), with **Tajawal** after it in the stack for Arabic text. Figures are tabular for IDs and countdowns. There's no monospace face.
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

- **Backend tests** create and migrate a separate `ticketing_test` database on the same Postgres, truncate between tests, so they never disturb the dev stack's data.
- **Playwright specs** create their own data and restore anything shared that they change.

## When you change dependencies

- **Backend** (`backend/pyproject.toml` / `uv.lock`): `docker compose up -d --build api worker`. The venv lives at `/opt/venv` inside the image, so a rebuild always picks up the lockfile.
- **Frontend** (`frontend/package.json`): `node_modules` is an anonymous volume that Compose carries between recreates, so use `docker compose up -d --build --renew-anon-volumes frontend`.

File watching in the containers uses polling (`VITE_USE_POLLING`, `WATCHFILES_FORCE_POLLING`), because Docker Desktop bind mounts don't deliver file-change events.

## Creating the first admin

`create_admin` creates a real admin account (or promotes an existing one), outside the seeded demo accounts. Local:

```
docker compose exec api python -m app.create_admin --email habusaleh@liverx.me --name "Hamza Abu Saleh"
```

It prompts for the password twice (hidden input) and applies the same validator as `/auth/register`. It never sets up two-step verification — the account enrols an authenticator at its first sign-in, the same as every other account. It's idempotent: running it again for the same email either says it's already an admin, or promotes it if it wasn't one yet. It refuses an email outside `STAFF_EMAIL_DOMAINS` (below), and works with `ENV=prod`.

On Cloud Run, this runs as a one-off job against the deployed database instead (Phase 16).

## Production hardening

- **Staff email domains.** `STAFF_EMAIL_DOMAINS` (default `liverx.me`, comma-separated) gates who can be promoted to `agent`/`admin`, via `PATCH /users/{id}` or `create_admin`. Locally (`ENV=local`), `@ticketing.demo` is also allowed, for the seeded demo staff — never in `test` or `prod`.
- **Registration switch.** `ALLOW_REGISTRATION` (default `true`). Set it to `false` to close public sign-up; `POST /auth/register` then returns 403, and the frontend hides "Create account" (`GET /auth/config` is the public source of truth both check).
- **Sign-in throttling.** 10 failed `POST /auth/login` attempts for one email, or from one client IP, in a 15-minute window returns 429 for the rest of that window. Attempts are stored in `login_attempts` (not in memory, since Cloud Run runs several instances) and pruned after a day by the worker's sweep. `TRUST_PROXY=true` reads the real client IP from the first hop of `X-Forwarded-For` (set this only behind something that sets that header itself, like Cloud Run — otherwise a client could claim any IP).
- **CORS.** `CORS_ORIGINS` (comma-separated, default `http://localhost:5173`). Empty in prod, where the SPA is served same-origin.
- **Security headers.** Every response carries `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`, `X-Frame-Options: DENY` and a `Content-Security-Policy` (self, plus `data:` for the QR code image and the self-hosted variable fonts, plus `'unsafe-inline'` styles for MUI/emotion's runtime style injection). Verified against the real `frontend/dist` build served locally with these exact headers, not just assumed.
- `ENV=prod` refuses to start with a default/short `JWT_SECRET`, or with `SEED_DEMO` explicitly on.

## Moving to Google Cloud (iteration 2)

These are seams only; nothing is deployed in this iteration.

| Here | GCP | Change |
|---|---|---|
| Postgres container | Cloud SQL for PostgreSQL | `DATABASE_URL` |
| Local attachment volume | Cloud Storage | the attachment storage module |
| uvicorn containers | Cloud Run | the Dockerfiles are 12-factor |
