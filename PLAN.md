# Ticketing Portal — Iteration 1 Execution Plan

> Source of truth for requirements: [ticketing-portal-brief.md](ticketing-portal-brief.md).
> This plan turns the brief into ordered phases for an executing agent (Sonnet).
> Execute **one phase per session/turn**, run that phase's verification, tick its checkbox here, then stop.
> Do not skip ahead, and do not add anything the brief lists as a non-goal.

---

## 0. Decisions locked (do not re-litigate)

| Area | Decision | Why |
|---|---|---|
| Backend | **Python 3.12 + FastAPI**, SQLAlchemy 2.x (async, `asyncpg`), Alembic, Pydantic v2 | Pydantic schemas double as Gemini structured-output schemas; Python keeps the ADK iteration-3 path open |
| DB | **Postgres 16 with pgvector** (image `pgvector/pgvector:pg16`) | `embedding` column is a real `vector(768)`; Cloud SQL for Postgres supports pgvector, so iteration 2 is a lift-and-shift |
| Queue | **Redis 7 Streams** behind an `EventBus` interface; separate `worker` container (same image, different command) | Direct stand-in for Pub/Sub: swap the implementation, not the call sites |
| AI | Gemini **REST via `httpx`** (no SDK), behind an `AIProvider` interface with `GeminiProvider` + `FakeProvider` | Brief says REST; the fake keeps the stack runnable offline and makes tests deterministic |
| Models | env-configured: `GEMINI_TRIAGE_MODEL=gemini-3.6-flash`, `GEMINI_ANSWER_MODEL=gemini-3.6-flash`, `GEMINI_EMBED_MODEL=gemini-embedding-001`, `EMBED_DIM=768` | Verified against ai.google.dev/gemini-api/docs/models on 2026-09-24. Never hardcode model IDs outside `config.py` |
| Auth | JWT (HS256, `PyJWT`), passwords with `bcrypt`, Bearer header; roles `end_user`, `agent`, `admin` | Brief |
| Frontend | **React 18 + Vite 8 + TypeScript 7**, **MUI 9** fully re-themed from M3 tokens, TanStack Query 5, **React Router 7** | Material Web is in maintenance mode, so use MUI themed to M3. No Tailwind, no shadcn. Versions were approved 2026-09-24 after the Phase 1 CVE bump. Use React Router 7's own APIs (`createBrowserRouter`, loaders are optional); don't write v6-era patterns. Check the MUI 9 docs for theme/`CssVarsProvider` APIs rather than recalling v5/v6 ones |
| Dynamic color | `@material/material-color-utilities` generates the whole scheme from **one seed** at runtime (light + dark) → CSS custom properties → MUI theme | Brief: tonal roles from a seed, not a hex palette |
| Tests | Backend `pytest` + `httpx.AsyncClient` against a test DB; frontend `vitest` + Testing Library for the lifecycle/SLA UI logic; one Playwright smoke run at the end | |
| Package mgmt | Backend `uv` (pyproject + lockfile); frontend `npm` | |

### Design direction (stated up front, as the brief requires)

- **Seed color: `#1E6A5E` "Spruce"**, a deep blue-green. It's calm and clinical without being Google blue. It generates warm-leaning neutrals, a teal primary, and a dusty-rose tertiary that we use for "attention" accents. Error red stays clearly distinct from the primary.
- **Display typeface: Google Sans Flex** (OFL, on Google Fonts since Dec 2025). Used for headlines/titles. Use its `ROND` (rounded terminals) axis at a moderate value on the end-user portal and 0 on the agent console, so one family carries two personalities.
- **Body typeface: Roboto Flex.** Used for body, labels and tables. Its `opsz` axis lets the dense agent tables read cleanly at 13px.
- **Utility (data only): Google Sans Code**, only for ticket IDs (`TCK-01042`), timestamps and SLA countdowns.
- **Tone:** *calm, spacious and reassuring for the end-user portal; dense, scannable and efficient for the agent console.*
- Verify the exact Google Fonts family names and axis tags on fonts.google.com before wiring them up. Self-host them via `@fontsource-variable/*` if packages exist; otherwise use the Google Fonts CSS2 API with `display=swap`.

**Per-portal contrast (the brief's anti-slop requirement):**

| | End-user portal | Agent console |
|---|---|---|
| Density | Comfortable: 16px body, 24–32px gaps, max width ~880px single column | Compact: 13–14px body, 36px table rows, full-bleed |
| Surfaces | `surface` + `surfaceContainerLow`, mostly flat | Layered: `surfaceContainer` rail, `surfaceContainerHigh` detail pane, `surfaceContainerHighest` for the selected row |
| Layout | Top app bar + one column: KB search on top, then "Your requests" as a **list** (not cards) | Nav rail + 3-pane: filter/queue list · ticket thread · properties/AI side panel |
| Shape | Large (16–28px) corners, pill buttons | Pill buttons/chips stay; table and panes use small (8px) corners |
| Signature element | **The KB answer panel**: a grounded answer with numbered source chips that link to the articles | **SLA ring/countdown** on every queue row, in Google Sans Code. Pauses visibly (hatched/"paused" label) while `pending` |

**Banned:** drop shadows for elevation (use tonal surfaces), purple gradients, centered hero with illustration, card grid of everything, Inter/system-ui, default MUI blue.

The executor **must load the `beautiful-web-ui` skill** before any UI phase (6–9). It follows the skill's plan → critique → build → screenshot → critique loop. The seed and fonts above replace the skill's "pick 4–6 hex values" step, because the brief mandates M3 dynamic color.

---

## 1. Target repository layout

```
Ticketing-system/
├── docker-compose.yml
├── .env.example                # GEMINI_API_KEY=, AI_PROVIDER=gemini|fake, JWT_SECRET=...
├── CLAUDE.md                   # executor instructions (already written)
├── PLAN.md                     # this file
├── ticketing-portal-brief.md
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml / uv.lock
│   ├── alembic.ini, alembic/versions/
│   ├── app/
│   │   ├── main.py             # FastAPI app, routers, CORS
│   │   ├── config.py           # pydantic-settings; ALL env + model IDs live here
│   │   ├── db.py               # async engine/session
│   │   ├── models/             # SQLAlchemy models (one file per table group)
│   │   ├── schemas/            # Pydantic request/response + AI schemas
│   │   ├── auth/               # jwt, password hashing, deps: current_user, require_role
│   │   ├── domain/
│   │   │   ├── lifecycle.py    # state machine: allowed transitions, guards (pure functions)
│   │   │   ├── sla.py          # due-date calc, pause/resume math (pure functions)
│   │   │   └── audit.py        # write_audit(session, entity, actor, action, diff)
│   │   ├── ai/
│   │   │   ├── provider.py     # AIProvider protocol
│   │   │   ├── gemini.py       # REST calls: generateContent (JSON schema), embedContent
│   │   │   └── fake.py         # deterministic keyword-based triage + hash embeddings
│   │   ├── events/             # EventBus protocol + RedisStreamBus
│   │   ├── routers/            # auth, tickets, comments, kb, analytics, admin
│   │   ├── worker.py           # consumes ticket.created → triage; periodic SLA-risk sweep
│   │   └── seed.py             # idempotent seed: users, SLA policies, categories, 5 KB articles
│   └── tests/
└── frontend/
    ├── Dockerfile
    ├── package.json, vite.config.ts   # dev proxy /api → api:8000
    └── src/
        ├── theme/              # seed → scheme → CSS vars → MUI theme; typography; shape; density
        ├── api/                # typed client + TanStack Query hooks
        ├── auth/               # login/register, token store, RoleGate
        ├── portals/
        │   ├── enduser/        # Home (KB search + my tickets), NewTicket, TicketView
        │   ├── agent/          # Queue (3-pane), TicketDetail, Dashboard
        │   └── admin/          # Users, Categories, SLA policies
        └── components/         # SlaIndicator, StatusChip, PriorityChip, Thread, AiTriagePanel...
```

---

## 2. Schema additions beyond the brief (minimal, needed to satisfy it)

The brief's data model can't express some of its own acceptance criteria. Add **only** these:

- `tickets.sla_paused_at timestamptz null` and `tickets.sla_paused_total_seconds int default 0`: needed so the resolution clock pauses while `pending`.
- `tickets.first_responded_at timestamptz null`: needed for first-response-time analytics and the response SLA.
- `tickets.parent_ticket_id fk null`: the "linked follow-up ticket" for replies on closed tickets.
- `tickets.escalated bool default false`, `tickets.ai_triage jsonb null` (raw suggestion + `accepted_fields`), `tickets.ai_summary text null`.
- `categories` table (id, name, active). The brief's admin page has a "category list", and `tickets.category` references it by name/slug.
- `users.name text`, and `users.team` values include `tier1`, `senior` (the escalation queue).
- `knowledge_base_articles.embedding vector(768)`, `tags text[]`, `slug text unique`.
- Config: `RESOLVED_COOLOFF_HOURS` (default 72).

Document each addition in the Alembic migration docstring.

---

## 3. Core domain rules (implement as pure, unit-tested functions first)

**Lifecycle** (`domain/lifecycle.py`). Allowed transitions:

```
new         → triaged                       (system, after AI triage; or agent manually)
triaged     → open                          (requires assignee_id)
open        → in_progress
in_progress → pending | resolved
pending     → in_progress                   (agent, or automatically on a public customer reply)
resolved    → in_progress                   (customer public reply within cooling-off window → auto)
resolved    → closed                        (agent, or automatically after the cooling-off window)
closed      → (none; read-only)
```
- Any other transition → HTTP 409 with `{allowed: [...]}`.
- A customer reply on `closed` → create a new ticket with `parent_ticket_id`, status `new`, and the reply as its description. The old ticket is untouched and the response returns the new ticket ID.
- **Escalation** is an action, not a status. It's a `PATCH` with `{escalate: true}` that bumps priority one level (cap `urgent`), sets `escalated=true`, and reassigns to the least-loaded `senior`-team agent. Allowed from any status except `resolved`/`closed`. Audit-logged.
- Every `PATCH` writes one `audit_log` row with a before/after `diff_json` of the changed fields.

**SLA** (`domain/sla.py`):
- On create: look up `sla_policies` by priority → `sla_response_due = created_at + response_minutes`, `sla_resolution_due = created_at + resolution_minutes`.
- If triage changes the priority, recompute both from `created_at` (unless already paused/responded).
- Enter `pending`: set `sla_paused_at = now`. Leave `pending`: `delta = now - sla_paused_at`, push `sla_resolution_due += delta`, add to `sla_paused_total_seconds`, clear `sla_paused_at`. The response SLA does **not** pause.
- First public agent reply sets `first_responded_at` (if null).
- "At risk" = less than 25% of the window remaining and not paused. The worker sweeps every 60s and auto-escalates `urgent`/`high` tickets that are at risk (flag + audit; no duplicate escalation).
- Tests must use an injectable clock (`now()` parameter). No `sleep`.

---

## 4. Phases

Each phase ends with **Verify**: commands the executor must actually run, with the output observed, before ticking the box.

### Phase 1 — Scaffold & Compose skeleton
- [x] Create the layout above; `docker-compose.yml` with `db` (pgvector pg16, healthcheck), `redis` (healthcheck), `api` (depends_on healthy db/redis; runs `alembic upgrade head && python -m app.seed && uvicorn`), `worker`, `frontend` (Vite dev server on 5173, proxy `/api` → `api:8000`).
- [x] `env_file: .env` with `required: false` so `docker compose up` works with no `.env` (defaults to `AI_PROVIDER=fake`). `.env.example` documents `GEMINI_API_KEY`.
- [x] `GET /health` returns db + redis status.
- **Verify:** `docker compose up -d --build` → `curl localhost:8000/health` is OK → `localhost:5173` renders a placeholder. Then `docker compose down -v && docker compose up -d` also works (no manual steps).

  **Evidence (2026-09-24):**
  - `docker compose up -d --build` → all 5 services (`db`, `redis`, `api`, `worker`, `frontend`) built and started; `db`/`redis` reported `(healthy)`.
  - `curl localhost:8000/health` → `{"status":"ok","db":true,"redis":true}`.
  - `curl localhost:5173/` → 200, served the placeholder `<div id="root">` page with the Vite/React dev client injected.
  - `docker compose down -v` (removed containers + `db_data`/`backend_venv`/`attachments_data` volumes) → `docker compose up -d` (no `--build`, no manual steps) → re-checked health (`{"status":"ok","db":true,"redis":true}`) and frontend (200) again; `alembic upgrade head` and `python -m app.seed` ran cleanly with no migrations/seed data yet (both are no-ops until Phase 2).
  - Frontend deps were bumped to current majors during scaffolding (MUI 6→9, React Router 6→7, Vite 6→8, Vitest 2→5, TypeScript 5→7) after `npm audit` flagged a critical/high CVE pair in the initial pin set; `npm audit` now reports 0 vulnerabilities and `npm run build`/`tsc -b` pass.
  - `git init` run; two commits made (scaffold, then a fix removing an accidentally-tracked `tsconfig.tsbuildinfo`).

### Phase 2 — Data model, migrations, seed
- [x] **Phase 1 follow-up (do first).** Fix the dependency volumes, which will go stale:
  - `backend_venv` is a named volume, and `/app/node_modules` is an anonymous one that Compose carries over when it recreates a container. Docker only fills a volume from the image when the volume is empty, so after this phase adds or changes dependencies, `--build` alone would leave the old packages in place.
  - Fix for the venv: set `UV_PROJECT_ENVIRONMENT=/opt/venv` in the backend Dockerfile, put `/opt/venv/bin` on `PATH`, and drop the `backend_venv` mount.
  - Fix for node_modules: keep the anonymous mount, but document `docker compose up -d --build --renew-anon-volumes` for dependency changes in the README.
  - Also in the backend Dockerfile: `COPY pyproject.toml uv.lock ./` and run `uv sync --frozen` so the lockfile is actually honoured.
  - Verify by adding a dependency this phase needs (e.g. `pgvector` for SQLAlchemy), rebuilding, and importing it inside both `api` and `worker`.
- [x] SQLAlchemy models for all brief tables plus the §2 additions; first Alembic migration; `CREATE EXTENSION vector`.
- [x] Idempotent `seed.py`: 1 admin, 3 agents (2 `tier1`, 1 `senior`), 2 end users (print credentials in the README); 4 SLA policies (urgent 15m/4h, high 1h/8h, normal 4h/24h, low 8h/72h); categories (Account & login, Billing, Technical issue, Data & privacy, Other); **5 KB articles** with realistic bodies (≥3 required by acceptance). Embeddings are generated at seed time via the provider and skipped if already present.
- **Verify:** `docker compose exec db psql ... -c '\dt'` shows every table; re-running seed doesn't create duplicates.

  **Evidence (2026-09-24):**
  - Dockerfile: `UV_PROJECT_ENVIRONMENT=/opt/venv` + `PATH` now includes `/opt/venv/bin`; `COPY pyproject.toml uv.lock ./` then `uv sync --frozen --no-install-project`, then `uv sync --frozen` after the full `COPY . .`. `backend_venv` volume mount removed from `api`/`worker` in `docker-compose.yml` and dropped from the top-level `volumes:` block.
  - Added `pgvector>=0.3` to `backend/pyproject.toml` (resolved to `pgvector==0.5.0`), regenerated `uv.lock` with `uv lock` on the host. `docker compose build api worker` succeeded and installed it with no stale-venv issues (nothing to invalidate — `/opt/venv` isn't a volume).
  - Verified the import in both containers: `docker compose run --rm api python -c "from app import models; import pgvector; print(...)"` → `api: models + pgvector import OK`; same command against `worker` → `worker: models + pgvector import OK`. `app/worker.py` and `app/main.py` now import `app.models` for real (not just as a smoke check — it registers the models on `Base.metadata` in every process, and doubles as proof the pgvector import path works in both containers).
  - README's "When you change dependencies" section documents `docker compose up -d --build --renew-anon-volumes frontend` for frontend dependency changes, and explains why a plain `--build` is now sufficient for the backend.
  - Models: `backend/app/models/{enums,user,category,sla_policy,ticket,comment,attachment,kb_article,audit_log}.py`, one file per table group as PLAN.md §1 specifies, covering every brief table plus every §2 addition (`tickets.sla_paused_at`/`sla_paused_total_seconds`/`first_responded_at`/`parent_ticket_id`/`escalated`/`ai_triage`/`ai_summary`, `categories`, `users.name`/`users.team`, `knowledge_base_articles.embedding`/`tags`/`slug`).
  - First migration `backend/alembic/versions/d1faf9909ccb_initial_schema.py`, generated via `alembic revision --autogenerate` against the running `db` service and hand-edited to add `CREATE EXTENSION IF NOT EXISTS vector` (autogenerate doesn't know about extensions) and the missing `import pgvector.sqlalchemy` (autogenerate renders the `VECTOR` type but not its import). Docstring documents every §2 addition per PLAN.md's instruction. `alembic upgrade head` applied cleanly; a follow-up `alembic check` reported "No new upgrade operations detected" (no model/migration drift).
  - `docker compose exec db psql -U ticketing -d ticketing -c '\dt'` → all 9 tables present (`users`, `tickets`, `ticket_comments`, `attachments`, `sla_policies`, `knowledge_base_articles`, `audit_log`, `categories`, plus `alembic_version`). `\dx` shows the `vector` extension installed.
  - Minimal scaffolding needed by seed.py, ahead of their full Phase 3/5 build-out: `app/auth/security.py` (`hash_password`/`verify_password` via bcrypt) and `app/ai/{provider.py,fake.py,__init__.py}` (`AIProvider` protocol with just `embed()`; `FakeProvider` generates deterministic, normalized hash-based vectors — real triage/`GeminiProvider` land in Phase 5).
  - `docker compose run --rm api python -m app.seed` → `seed: complete`. Row counts: 6 users (2 tier1 agents, 1 senior agent, 1 admin, 2 end users), 4 SLA policies, 5 categories, 5 KB articles all with a non-null `embedding`. Re-ran the same command a second time: counts unchanged (6/4/5/5) — idempotent, no duplicates.
  - Fresh-state end-to-end check: `docker compose down -v && docker compose up -d --build` (empty `db_data`) → `api` logs show `alembic upgrade head` running the migration, then `seed: complete`, then uvicorn startup; `curl localhost:8000/health` → `{"status":"ok","db":true,"redis":true}`; `\dt` and row counts matched the above with zero manual steps. `curl localhost:5173/` still 200.
  - `ruff check app` inside the container: 0 findings beyond the pre-existing, repo-wide `EXE002` (shebang-missing) noise that predates this phase on every backend file (a Windows file-mode artifact, not a Phase 2 regression); the two real findings (unsorted imports, an unnecessary `encode("utf-8")`) were fixed.

### Phase 3 — Auth & roles
- [x] **Phase 2 follow-ups (do first).**
  - **KB embeddings must track which model made them.** Add `knowledge_base_articles.embedding_model text null` in a new migration. `seed.py` re-embeds any article whose `embedding_model` differs from the current provider's model ID (e.g. `fake-hash-v1` vs `gemini-embedding-001`), not just articles with no embedding. Otherwise, once a `GEMINI_API_KEY` is added, Gemini query vectors get compared against the fake vectors already stored, and search returns noise.
  - **Embed `title + "\n\n" + body`**, not the body alone.
  - **Make `FakeProvider.embed` roughly semantic.** Replace the SHA-per-text vector with feature hashing: lowercase, tokenise, hash each word and bigram into one of `EMBED_DIM` buckets with a ±1 sign, then L2-normalise. With the current version, similarity between unrelated texts is random, so fake-mode KB search (and the Phase 5 tests) can't return the right article. Add a unit test showing "forgot my password" ranks `resetting-your-password` first.
  - **Indexes:** add a composite index on `audit_log(entity_type, entity_id)` and indexes on `tickets.status` and `tickets.priority`.
  - **Silence the Windows-only `EXE002` ruff noise:** run `git config core.fileMode false` and add `EXE002` to `[tool.ruff.lint] ignore` in `pyproject.toml`, so `ruff check` comes back fully clean.
  - **System actor convention:** `audit_log.actor_id = NULL` means the system (AI triage, SLA sweep). Don't create a system user. The UI shows "System" for null actors.
- [x] `POST /auth/register` (always `end_user`), `POST /auth/login` → `{access_token, user}`; `GET /auth/me`.
- [x] Dependencies `current_user` and `require_role(*roles)`. End users can only see their own tickets and never see internal notes (enforced in the query, not the UI).
- **Verify:** pytest covers login success/failure, role denial (403) on a small agent-only probe route, expired or tampered tokens (401), and the Phase 2 follow-ups (fake-embedding ranking test; re-running the seed after changing the embedding model ID re-embeds all 5 articles). The "end user gets 404 on another user's ticket" test moves to Phase 4, because ticket routes don't exist yet.

  **Evidence (2026-09-24):**
  - Phase 2 follow-ups: `backend/alembic/versions/479c142aad4c_kb_embedding_model_and_query_indexes.py` (generated via `alembic revision --autogenerate`, docstring documents each change) adds `knowledge_base_articles.embedding_model`, `ix_audit_log_entity_type_entity_id`, `ix_tickets_status`, `ix_tickets_priority`. `alembic check` → "No new upgrade operations detected" after applying.
  - `AIProvider.EMBEDDING_MODEL_ID` (`backend/app/ai/provider.py`) added as a `ClassVar`; `FakeProvider.EMBEDDING_MODEL_ID = "fake-hash-v1"`. `FakeProvider.embed` (`backend/app/ai/fake.py`) rewritten as word+bigram feature hashing into signed `EMBED_DIM` buckets, L2-normalised, replacing the old per-text SHA hash.
  - `seed.py`'s `seed_kb_articles` now embeds `title + "\n\n" + body` and re-embeds (updating both `embedding` and `embedding_model`) whenever `existing.embedding_model != provider.EMBEDDING_MODEL_ID`, not just on a null embedding.
  - `git config core.fileMode false` run; `[tool.ruff.lint] ignore` in `backend/pyproject.toml` now has `EXE002` and (found during this phase) `B008` — FastAPI's idiomatic `Depends(...)` default-argument pattern, which every router in this app uses. `docker compose exec api ruff check app tests` → "All checks passed!".
  - System actor convention needed no code change: `audit_log.actor_id` was already nullable with no system user in `seed.py`.
  - Auth: `backend/app/auth/tokens.py` (PyJWT encode/decode, `TokenError`), `backend/app/auth/dependencies.py` (`current_user` via `HTTPBearer`, `require_role(*roles)`), `backend/app/schemas/auth.py`, `backend/app/routers/auth.py` (`POST /auth/register`, `POST /auth/login`, `GET /auth/me`, and `GET /auth/_probe/agent-only` — the small agent-only probe route this phase's Verify step calls for, standing in until Phase 4 adds real agent-only ticket routes). Wired into `backend/app/main.py`.
  - Test infra added (none existed before this phase): `backend/tests/conftest.py` runs against a real `ticketing_test` Postgres database (created automatically, migrated with `alembic upgrade head`), not mocks/SQLite, with tables truncated after every test. Required `asyncio_default_fixture_loop_scope = "session"` / `asyncio_default_test_loop_scope = "session"` in `pyproject.toml` — a single global async engine (`app.db`) can't hand out asyncpg connections across per-test event loops.
  - `docker compose exec api pytest -q` → **12 passed**: `tests/test_auth.py` (register → `/auth/me`, duplicate-email 409, login success/wrong-password/unknown-email, probe 403 for `end_user` / 200 for `agent`, missing/tampered/expired token → 401), `tests/test_ai_fake.py` (fake-embedding ranking: "forgot my password" ranks `resetting-your-password` first among all 5 seeded articles), `tests/test_seed.py` (re-seeding with an unchanged model ID is a no-op — 0 `embed()` calls, byte-identical vectors; bumping `EMBEDDING_MODEL_ID` re-embeds — 5 `embed()` calls, all 5 articles' `embedding_model` updated).
  - **Found and fixed during this phase:** the seeded `@ticketing.local` accounts (`admin`, `agent1-3`, `user1-2`) failed `pydantic.EmailStr` validation on login — `email-validator` (needed for `EmailStr`, added as a new dependency this phase) rejects `.local` as an IANA special-use TLD. Renamed the seed domain to `@ticketing.demo` in `backend/app/seed.py` and `README.md`.
  - Fresh-state end-to-end check: `docker compose down -v && docker compose up -d --build` → `api` logs show both migrations (`d1faf9909ccb`, `479c142aad4c`) applying in order, then `seed: complete`, then uvicorn startup; `curl localhost:8000/health` → `{"status":"ok","db":true,"redis":true}`. Manual smoke via curl: register → `/auth/me` (200); login as seeded `agent1@ticketing.demo` → probe (200); login as seeded `user1@ticketing.demo` → probe (403); wrong password → login (401); no token → `/auth/me` (401). `docker compose exec api pytest -q` and `ruff check app tests` re-run clean on this fresh stack too.
  - README gained a "Running the backend tests" section documenting `docker compose exec api pytest`.

### Phase 4 — Tickets, comments, lifecycle, SLA, audit (no AI yet)
- [ ] **Phase 3 follow-ups (do first, each with a test).**
  - **Passwords over 72 bytes cause a 500 (reproduced).** bcrypt 5 raises `ValueError` from both `hashpw` and `checkpw` for passwords longer than 72 bytes.
    - `RegisterRequest.password`: add a validator that rejects more than 72 **UTF-8 bytes** with a 422 and a clear message. A character count isn't enough, because multi-byte characters take several bytes each.
    - Login: return a plain 401 for a password over 72 bytes, without calling bcrypt.
  - **Email case:** lowercase and strip emails before storing and looking them up, in both register and login. Otherwise `Uma@x.com` and `uma@x.com` become two accounts.
  - **Username enumeration by timing:** when login finds no user, still run `verify_password` against a fixed dummy hash, so a missing account takes as long as a wrong password.
  - **Duplicate-email race:** catch `IntegrityError` on the register commit and return 409 instead of 500.
  - **Default JWT secret:** at startup, refuse to run if `ENV=prod` and `JWT_SECRET` is still the default or shorter than 32 bytes. Local and test behaviour doesn't change.
- [ ] Implement `domain/lifecycle.py` and `domain/sla.py` with **unit tests first** (every transition, illegal transitions, pause/resume math across multiple pending cycles, cooling-off reopen vs closed → follow-up).
- [ ] `POST /tickets`, `GET /tickets` (filters: status, priority, assignee (incl. `me` and `unassigned`), category, `q` text; sort; pagination), `GET /tickets/:id` (with thread and audit trail for agents), `PATCH /tickets/:id` (status/assignee/priority/category/escalate).
- [ ] `POST /tickets/:id/comments` `{body, is_internal_note}`: only agents/admins may send internal notes. Customer public reply side effects: `pending`→`in_progress`, `resolved` within the window→`in_progress`, `closed`→follow-up ticket. Agent public reply sets `first_responded_at`.
- [ ] Attachments: `multipart` upload to a Docker volume at `/data/attachments`; store metadata. Keep it minimal (size limit, content-type allowlist).
- [ ] Publish `ticket.created` to the EventBus on create.
- **Verify:** pytest integration test walks one ticket `new→triaged→open→in_progress→pending→in_progress→resolved→(customer reply)→in_progress→resolved→closed`, then a customer reply creates a linked follow-up. Also test that an end user gets 404 on another user's ticket and never receives internal notes in `GET /tickets/:id`. It asserts the SLA due date shifted by exactly the pending duration (frozen clock) and one audit row per change.

### Phase 5 — Gemini: auto-triage + KB smart search
**Triage (do first, since it has the most leverage):**
- [ ] `ai/gemini.py`: `generateContent` with `generationConfig.responseMimeType="application/json"` and a `responseSchema` derived from the Pydantic `TriageSuggestion` model: `{category (enum of active categories), priority (enum), one_line_summary, suggested_response_draft}`. Timeout 20s, 2 retries with backoff, validate with Pydantic, and fall back to `FakeProvider` on failure (log it; the ticket still flows).
- [ ] **Verify the current REST request shape** (field names, `x-goog-api-key` header, endpoint path) against ai.google.dev docs before coding. Don't write it from memory.
- [ ] Worker consumes `ticket.created` → calls triage → writes `ai_triage`, applies category + priority automatically, recomputes SLA, sets status `triaged`, and audit-logs with `actor_id = NULL` (system). `POST /tickets/:id/ai-triage` runs the same function synchronously (agent "re-run triage" button + internal use).
- [ ] The agent can accept/override each field: `PATCH` records which fields were overridden in `ai_triage.accepted_fields`.

**KB search:**
- [ ] `embedContent` with `outputDimensionality=768` and the appropriate task types (document vs query; verify the enum names in the docs). Normalise vectors before storing if the docs say reduced-dimension outputs aren't normalised.
- [ ] `GET /kb/search?q=` → embed query → pgvector cosine top-4 → if best similarity < threshold (configurable), return `{answer: null, sources: []}` so the UI offers "Submit a request". Otherwise call Gemini with a strictly grounded prompt (answer only from the provided articles, cite as [1],[2], say you don't know otherwise) and structured output `{answer, cited_article_ids}`. Return `{answer, sources:[{id, title, slug, snippet}]}`. Drop any cited ID that wasn't in the retrieved set.
- [ ] `GET /kb/articles/:slug` for the source link target.
- **Verify:** pytest with `FakeProvider` (deterministic). Then, **only if `GEMINI_API_KEY` is set**, a live smoke script `backend/scripts/smoke_gemini.py` that triages one ticket and runs one KB query against each of 3 seeded articles, printing results. Report honestly if no key is available.

### Phase 6 — Frontend foundation: theme, shell, auth
Load `beautiful-web-ui` first. Write the design plan (seed, fonts, tone, per-portal table from §0) as a comment block at the top of `src/theme/index.ts`, critique it once, then build.
- [ ] `theme/`: `material-color-utilities` → `SchemeTonalSpot` (verify the class name in the package) from `#1E6A5E` for light and dark → emit every M3 role as a CSS variable (`--md-sys-color-*`) → MUI `createTheme` maps palette, `shape`, typography roles (display/headline/title/body/label) and component overrides (Buttons = pill, no shadows anywhere: `shadows` all `none`, elevation via `surfaceContainer*`). Add a `density` context: `comfortable` (end user) vs `compact` (agent).
- [ ] Theme toggle (system/light/dark). Fonts are loaded with `swap`.
- [ ] Login/register screens (end-user styled), token store, `RoleGate`, role-based redirect after login (`end_user`→`/`, `agent`→`/agent`, `admin`→`/admin`).
- [ ] A dev-only `/_tokens` route showing every color role and type role. It's used for the screenshot critique.
- **Verify:** `npm run build` + `npm run typecheck` clean. Screenshot `/_tokens` and the login page (Playwright) in light and dark, then critique against §0.

### Phase 7 — End-user portal (calm, spacious)
- [ ] Home: a prominent KB search field (M3 search bar). The **signature grounded-answer panel** shows the answer text with inline [n] markers mapped to numbered source chips that link to the article page, with loading skeleton and empty/no-answer states. Below it is "Your requests" as a list with status chip, relative updated time and a human status line ("Waiting on you" for `pending`).
- [ ] New request: subject, description, optional attachment. On submit, go to the ticket view with an optimistic "We're reviewing this" state, which updates (poll every 3s up to 30s, or refetch on focus) when triage lands and applies the category/priority.
- [ ] Ticket view: the public thread only, a reply box, and state-aware copy (resolved → "Reply within 72h to reopen"; closed → "Replying starts a new request").
- **Verify:** Playwright: register → search KB (answer + source link visible) → submit ticket → the category/priority chip appears. Screenshot at 360px and 1280px, then critique.

### Phase 8 — Agent console (dense, data-forward)
- [ ] Nav rail (Queue, Dashboard; Admin if admin). Queue = filter chips (status, priority, assignee incl. "Mine"/"Unassigned", category) + a dense table with ID (mono), subject + AI one-liner, requester, priority, status, **SLA indicator**, assignee, updated. The URL holds the filter state. Keyboard: `j/k` to move, `Enter` to open.
- [ ] Ticket detail (right pane or route): the thread with internal notes visually distinct (tertiary-container tint + "Internal" label, not color alone). The composer has a Reply / Internal note toggle. Side panel: status control that **only offers legal next transitions** (from the API), assignee picker, priority, category, Escalate button, and an **AI triage panel** with the suggestions, per-field Accept/Override, a "Use draft" button that inserts `suggested_response_draft` into the composer, and "Re-run triage". Audit trail in a collapsible section.
- [ ] `SlaIndicator`: countdown in Google Sans Code with ring progress. States: on track / at risk (tertiary) / breached (error) / **paused** (outlined + "Paused" text), and none when resolved/closed. All states carry text, not just color.
- **Verify:** Playwright: an agent opens the seeded ticket, walks it through the full lifecycle via the UI, and adds an internal note. The end-user session doesn't see the note. Screenshot the queue at 1280 and 1600 and critique the density against the end-user portal.

### Phase 9 — Analytics dashboard + Admin
- [ ] `GET /analytics/summary?from&to`: ticket volume per day, median/avg first-response time, median/avg resolution time (excluding paused time), backlog by status, SLA breach count. SQL aggregates, not Python loops.
- [ ] Dashboard: 4 stat tiles plus 2 charts (volume over time; backlog by status). **Load the `dataviz` skill** before building charts. Chart colors come from the M3 scheme roles.
- [ ] Admin (minimal): users table with role/team edit, a category list (add/deactivate), and an SLA policy editor (edit minutes per priority; applies to new tickets only, which is stated in the UI). All changes are audit-logged.
- **Verify:** pytest for the analytics math on a fixed dataset; screenshot the dashboard and critique.

### Phase 10 — Hardening & acceptance
- [ ] README: one-command start, seeded credentials, how to add `GEMINI_API_KEY`, the fake vs gemini provider, and the stated seed/type/tone.
- [ ] Seed ~25 demo tickets across all statuses/priorities (behind `SEED_DEMO=true`, default on locally) so the queue and dashboard aren't empty.
- [ ] Fresh-clone test: `docker compose down -v && docker compose up --build` with no `.env` and no manual steps.
- [ ] Walk the brief's **acceptance checklist** item by item, with evidence (command output / screenshot path) for each. Record the results in the table at the bottom of this file. Anything unverified is marked as such, not ticked.
- [ ] Run the `code-review` skill at `high` on the full codebase and fix confirmed findings. Run `security-review` (auth scoping, internal-note leakage, upload handling).

---

## 5. Iteration-2 seams (build the seams now, don't build the features)

| Local now | GCP later | Seam |
|---|---|---|
| Postgres container + pgvector | Cloud SQL (pgvector) | `DATABASE_URL` only |
| Redis Streams `EventBus` | Pub/Sub | `events/` implementation swap |
| Gemini API key over REST | Vertex AI Gemini | `AIProvider` implementation swap + auth |
| Local volume attachments | Cloud Storage | `Storage` protocol (`save/open`); keep it to one small module |
| uvicorn containers | Cloud Run (api, worker, frontend static) | Dockerfiles already 12-factor; frontend has a prod build stage |

Out of scope (do **not** build): email/social intake, sentiment, in-thread draft generation beyond the triage draft, ADK multi-agent triage, an automation rules engine, and GCP deployment.

---

## 6. Acceptance evidence (fill in during Phase 10)

| Brief criterion | Status | Evidence |
|---|---|---|
| `docker compose up` brings up the full stack, no manual steps | ☐ | |
| End user submits, sees it listed, Gemini category/priority auto-applied | ☐ | |
| Agent sees it in the queue, walks the full lifecycle, adds an internal note | ☐ | |
| SLA due timestamps set on create, pause while `pending` | ☐ | |
| KB search returns a grounded answer + source link for ≥3 seeded articles | ☐ | |
| Both portals visibly M3; seed/typography stated and consistent | ☐ | |
