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
- **No monospace face.** Ticket IDs (`TCK-01042`), timestamps and SLA countdowns use Roboto Flex with `font-variant-numeric: tabular-nums`, so the digits don't jitter as they tick. (Revised 2026-09-24: `frontend-design` lists "a monospace face for small data labels" as a template tell. Dropping it also keeps us to the brief's two typefaces.)
- **Tone:** *calm, spacious and reassuring for the end-user portal; dense, scannable and efficient for the agent console.*
- Verify the exact Google Fonts family names and axis tags on fonts.google.com before wiring them up. Self-host them via `@fontsource-variable/*` if packages exist; otherwise use the Google Fonts CSS2 API with `display=swap`.

**Per-portal contrast (the brief's anti-slop requirement):**

| | End-user portal | Agent console |
|---|---|---|
| Density | Comfortable: 16px body, 24–32px gaps, max width ~880px single column | Compact: 13–14px body, 36px table rows, full-bleed |
| Surfaces | `surface` + `surfaceContainerLow`, mostly flat | Layered: `surfaceContainer` rail, `surfaceContainerHigh` detail pane, `surfaceContainerHighest` for the selected row |
| Layout | Top app bar + one column: KB search on top, then "Your requests" as a **list** (not cards) | Nav rail + 3-pane: filter/queue list · ticket thread · properties/AI side panel |
| Shape | Large (16–28px) corners, pill buttons | Pill buttons/chips stay; table and panes use small (8px) corners |
| Signature element | **The KB answer panel**: a grounded answer with numbered source chips that link to the articles | **SLA ring/countdown** on every queue row, in tabular Roboto Flex. Pauses visibly (hatched/"paused" label) while `pending` |

**Banned:**
- Drop shadows for elevation (use tonal surfaces), purple gradients, a centered hero with an illustration, a card grid of everything, Inter/system-ui, default MUI blue.
- From `frontend-design`'s list of template tells:
  - ALL-CAPS labels. MUI uppercases buttons, tabs and `overline` by default, so set `textTransform: 'none'` in the theme.
  - Tracked-out eyebrow labels above headings.
  - Meta strings joined with middle dots (`Uma · Billing · 2h ago`). Use separate cells or columns instead.
  - `WORD — fragment` labels.
  - A `→` appended to links or buttons.
  - Accenting a single word in a headline.
  - Numbered markers on things that aren't sequences. The KB source chips [1] [2] are fine, because they map to citations.
  - Fade-and-slide-up entrances on every section.

### Design skills (the executor must load both before any UI phase, 6–9)

Both are in the project at [.claude/skills/](.claude/skills/). They were installed with `npx skills` into `~/.agents/skills`, which Claude Code doesn't read, so they were copied into the project.

- **`material-3`** is the design system: tokens, components, layout, navigation. Its rules **take precedence** on component structure and token usage.
  - Colour: `--md-sys-color-*` tokens only, with correct tonal pairing (`on-X` on `X`). Hex values appear only in the generated theme file.
  - Shape: `--md-sys-shape-corner-*` tokens, never raw `border-radius`.
  - Type: `--md-sys-typescale-*` roles.
  - Dividers: `outline-variant`, not `outline`.
  - Motion: M3 easing/duration tokens. Spring physics aren't available on web.
  - Layout: window size classes (compact < 600, medium 600–839, expanded 840–1199, large 1200–1599, extra-large 1600+). On large windows, constrain end-user content to 840–1040px.
  - Touch targets: 48px.
- **`frontend-design`** is the creative direction within those constraints. Use it for the two-pass process (plan → review against the brief and revise → build → screenshot → critique), "spend boldness in one place" (the signature elements above), and its UX-writing rules.
- **Precedence:** brief > `material-3` > `frontend-design`.
  - The seed and fonts above replace `frontend-design`'s "4–6 hex values" step, because the brief mandates M3 dynamic color.
  - Roboto Flex is correct for M3, per `material-3`. The generic "avoid Roboto" advice doesn't apply here.
- `beautiful-web-ui` is superseded by these two and doesn't need loading.
- **Audit gate:** at the end of Phases 7, 8 and 9, run the `material-3` skill's **audit** procedure on that phase's screens. Every category must score ≥ 7/10, and the report is saved to `docs/audits/phase-N-md3.md`. A category below 7 gets fixed before the phase's boxes are ticked.

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
- [x] **Phase 3 follow-ups (do first, each with a test).**
  - **Passwords over 72 bytes cause a 500 (reproduced).** bcrypt 5 raises `ValueError` from both `hashpw` and `checkpw` for passwords longer than 72 bytes.
    - `RegisterRequest.password`: add a validator that rejects more than 72 **UTF-8 bytes** with a 422 and a clear message. A character count isn't enough, because multi-byte characters take several bytes each.
    - Login: return a plain 401 for a password over 72 bytes, without calling bcrypt.
  - **Email case:** lowercase and strip emails before storing and looking them up, in both register and login. Otherwise `Uma@x.com` and `uma@x.com` become two accounts.
  - **Username enumeration by timing:** when login finds no user, still run `verify_password` against a fixed dummy hash, so a missing account takes as long as a wrong password.
  - **Duplicate-email race:** catch `IntegrityError` on the register commit and return 409 instead of 500.
  - **Default JWT secret:** at startup, refuse to run if `ENV=prod` and `JWT_SECRET` is still the default or shorter than 32 bytes. Local and test behaviour doesn't change.
- [x] Implement `domain/lifecycle.py` and `domain/sla.py` with **unit tests first** (every transition, illegal transitions, pause/resume math across multiple pending cycles, cooling-off reopen vs closed → follow-up).
- [x] `POST /tickets`, `GET /tickets` (filters: status, priority, assignee (incl. `me` and `unassigned`), category, `q` text; sort; pagination), `GET /tickets/:id` (with thread and audit trail for agents), `PATCH /tickets/:id` (status/assignee/priority/category/escalate).
- [x] `POST /tickets/:id/comments` `{body, is_internal_note}`: only agents/admins may send internal notes. Customer public reply side effects: `pending`→`in_progress`, `resolved` within the window→`in_progress`, `closed`→follow-up ticket. Agent public reply sets `first_responded_at`.
- [x] Attachments: `multipart` upload to a Docker volume at `/data/attachments`; store metadata. Keep it minimal (size limit, content-type allowlist).
- [x] Publish `ticket.created` to the EventBus on create.
- **Verify:** pytest integration test walks one ticket `new→triaged→open→in_progress→pending→in_progress→resolved→(customer reply)→in_progress→resolved→closed`, then a customer reply creates a linked follow-up. Also test that an end user gets 404 on another user's ticket and never receives internal notes in `GET /tickets/:id`. It asserts the SLA due date shifted by exactly the pending duration (frozen clock) and one audit row per change.

  **Evidence (2026-09-24):**
  - Phase 3 follow-ups, each with its own test in `backend/tests/test_auth.py`/`test_config.py`:
    - `MAX_PASSWORD_BYTES = 72` validator on `RegisterRequest.password` (`backend/app/schemas/auth.py`) rejects >72 UTF-8 bytes with 422 (`test_register_password_over_72_bytes_is_422`, and a UTF-8-multibyte case `test_register_password_over_72_utf8_bytes_is_422` using `"€" * 25` — 25 codepoints, 75 bytes). Login checks `password_exceeds_limit()` (`backend/app/auth/security.py`) before touching bcrypt and returns a plain 401 (`test_login_password_over_72_bytes_is_401_not_500`).
    - Both `RegisterRequest.email` and `LoginRequest.email` strip+lowercase via a `field_validator`; `test_register_and_login_email_case_insensitive` and `test_register_duplicate_email_different_case_conflicts` cover it.
    - `verify_password_timing_safe()` always calls `bcrypt.checkpw` against a fixed dummy hash when no user is found, instead of short-circuiting — login's `if user is None or not password_ok` now evaluates `password_ok` unconditionally.
    - Register no longer pre-checks for an existing email; it inserts and catches `IntegrityError` on commit → 409 (`backend/app/routers/auth.py`), closing the check-then-insert race instead of just wrapping it. `test_register_duplicate_email_conflicts` (existing) still covers the sequential case.
    - `Settings.check_prod_safe()` (`backend/app/config.py`), called from `main.py` at import time, raises `RuntimeError` when `ENV=prod` and `JWT_SECRET` is the default or under 32 bytes; local/test are unaffected. 4 tests in `test_config.py`.
  - `backend/app/domain/lifecycle.py`: `ALLOWED_TRANSITIONS` table, `validate_transition` (raises `IllegalTransitionError` with the allowed set; guards `triaged→open` on a missing `assignee_id`), `can_escalate`/`escalate_priority` (capped at `urgent`), `customer_reply_outcome` (`reopen`/`follow_up`/`none` — a `resolved` ticket past the cooling-off window is treated like `closed`, since nothing auto-closes it yet). `backend/app/domain/sla.py`: `compute_due_dates`, `recompute_due_on_priority_change` (freezes the response due date once responded, freezes the resolution due date while paused), `enter_pending`/`leave_pending` (pure pause-duration math), `mark_first_response`, `is_at_risk`. `backend/app/domain/clock.py` adds a single `now()` indirection so integration tests can freeze time by monkeypatching it, instead of every call site importing `datetime.now`. `backend/app/domain/audit.py`: `write_audit()`.
  - **51 unit tests, no DB, no sleep:** `backend/tests/test_domain_lifecycle.py` (39 — every legal/illegal transition pair, the assignee guard, escalation priority capping, all 4 `customer_reply_outcome` branches) and `backend/tests/test_domain_sla.py` (12 — due-date computation, priority-change recompute under both freeze conditions, single- and multi-cycle pause/resume accumulation, at-risk thresholds including already-breached).
  - `backend/app/routers/tickets.py`: `POST /tickets` (creator becomes requester, default `priority=normal`, SLA due dates computed from the matching `sla_policies` row, one `ticket.created` audit row, publishes to the event bus), `GET /tickets` (role-scoped — end users always filtered to `requester_id=user.id` in the query; `status`/`priority`/`category`/`q` (ILIKE on subject+description)/`assignee` (`me`/`unassigned`/a user id) filters; `sort` against a small allowlisted column map; `page`/`page_size` pagination with a `total` count), `GET /tickets/:id` (404, not 403, for an end user's own-scoping miss; comments filtered to non-internal for end users **in the query**; audit trail only attached for agents/admins; response includes `allowed_transitions` from `domain/lifecycle.allowed_next_statuses` so the Phase 8 status control can rely on the API instead of duplicating the transition table), `PATCH /tickets/:id` (reads `model_dump(exclude_unset=True)` so an omitted field is left alone but `assignee_id: null` unassigns; handles `status` via `validate_transition` + SLA pause/resume/resolved/closed timestamps, `priority` via `recompute_due_on_priority_change`, `category` validated against the `categories` table, `assignee_id` validated to be an existing agent/admin, and `escalate` — bumps priority, sets `escalated`, reassigns to the least-loaded `senior`-team agent via one grouped query, blocked with 409 on a `resolved`/`closed` ticket; exactly one `audit_log` row per PATCH with a `{before, after}` diff of only the fields that actually changed).
  - `POST /tickets/:id/comments`: internal notes rejected with 403 for non-agents; a requester's public reply runs `customer_reply_outcome` — `reopen` applies the pause/resume or resolved-clear math and adds one `ticket.reopened_by_reply` audit row; `follow_up` creates a new `Ticket` (`parent_ticket_id` set, own SLA due dates, own `ticket.created`-audited row, publishes its own `ticket.created` event) and returns `{follow_up_ticket_id}` with **no** comment on the original, which stays untouched; an agent's first public reply sets `first_responded_at`.
  - `POST /tickets/:id/attachments`: `ALLOWED_ATTACHMENT_CONTENT_TYPES` (`image/png`, `image/jpeg`, `image/gif`, `application/pdf`, `text/plain`) → 415 otherwise; reads up to `ATTACHMENT_MAX_BYTES + 1` and rejects over the limit with 413; stores under `/data/attachments/<ticket_id>/<uuid>_<sanitized filename>` (`Path(...).name` strips any directory components from the client filename to block path traversal); metadata row includes an optional `comment_id` validated to belong to the ticket.
  - `backend/app/events/bus.py`: `EventBus` protocol + `RedisStreamBus` (`XADD`, string-coerced fields) per PLAN.md §5's Pub/Sub seam; `create_ticket` and the follow-up-ticket path both publish `ticket.created`. Verified against the real `redis` container: `docker compose exec redis redis-cli XLEN ticket.created` / `XRANGE` show one entry per created ticket (including follow-ups) with the right `ticket_id`.
  - **Integration tests** (`backend/tests/test_tickets.py`, 5; `backend/tests/test_attachments.py`, 4 — 9 new integration tests, 81 total in the suite): `test_full_lifecycle_walk_sla_pause_and_follow_up` walks `new→triaged→(rejected open w/o assignee, 409 with `allowed:["open"]`)→(assign)→open→in_progress→pending→(clock frozen +2h via monkeypatching `app.domain.clock.now`)→in_progress→resolved→(customer reply, reopens)→in_progress→resolved→closed→(customer reply, follow-up)`, asserting after every status PATCH that the ticket's `audit_log` row count increased by exactly 1 (and by 0 on the rejected transition), that `sla_resolution_due` shifted by exactly the 2-hour pause duration and `sla_paused_total_seconds == 7200`, and that the closed ticket's audit trail is unchanged after the follow-up reply. `test_end_user_gets_404_on_another_users_ticket`, `test_end_user_never_receives_internal_notes` (asserts the end user's `comments` list is empty and `audit_log` is `None`, while the agent's view has both), `test_escalate_bumps_priority_and_reassigns_to_least_loaded_senior`, `test_cannot_escalate_a_closed_ticket`. Attachment tests cover an allowed upload, a rejected content type, an oversized file, and cross-user 404 scoping.
  - `docker compose exec api pytest -q` → **81 passed**. `ruff check app tests` → "All checks passed!".
  - Fresh-state end-to-end check: `docker compose down -v && docker compose up -d --build` → `api` logs show both migrations applying, `seed: complete`, uvicorn startup; `curl localhost:8000/health` → `{"status":"ok","db":true,"redis":true}`; `curl localhost:5173/` → 200; `pytest`/`ruff` re-run clean against the fresh stack. Manual curl walk against the real dev stack as seeded users (`user1@ticketing.demo` / `agent1@ticketing.demo`): create a ticket → `GET /tickets?status=new` lists it → `PATCH {"status":"triaged"}` → response's `allowed_transitions` correctly narrows to `["open"]`.

### Phase 5 — Gemini: auto-triage + KB smart search
- [x] **Phase 4 follow-ups (do first, each with a test).**
  - **SLA bug: a priority change erases earlier pause credit.** `recompute_due_on_priority_change` rebuilds the resolution due date as `created_at + resolution_minutes`, which drops `sla_paused_total_seconds`. It also leaves the old due date in place when the ticket is currently paused, so escalating a `pending` ticket never tightens its deadline.
    - Fix: always compute `created_at + resolution_minutes + paused_total_seconds`, even while paused. `leave_pending` then adds the current pause when the ticket resumes.
    - Test: pending for 2h → resume → escalate → the due date still includes the 2h. And: escalate while pending → resume after 1h → due date = new window + all pause time.
  - **Internal-note attachments leak to end users.** `_build_ticket_detail` filters internal-note comments for end users, but not attachments whose `comment_id` points to an internal note. Filter them in the query.
  - **Hide agent-only fields from end users.** Don't send `ai_triage` (it contains `suggested_response_draft`), `sla_paused_total_seconds` or `allowed_transitions` to end users. Use a separate `TicketDetailPublic` response model rather than nulling fields.
  - **Attachment download:** add `GET /attachments/{id}` with the same role scoping (the ticket must be visible to the user, and end users are blocked from internal-note attachments). Serve it with `Content-Disposition: attachment`. Phases 7 and 8 need this.
  - **Auto-close sweep:** in the worker's periodic loop (alongside the SLA-risk sweep), move `resolved` tickets whose cooling-off window has expired to `closed`. Set `closed_at` and write an audit row with `actor_id = NULL`. This makes the lifecycle match the brief, not just "behave like closed".
  - **Worker concurrency:** the SLA-risk and auto-close sweeps must lock the rows they change (`SELECT ... FOR UPDATE SKIP LOCKED`), so a sweep can't overwrite an agent's `PATCH` that's running at the same moment.

**Triage (do first, since it has the most leverage):**
- [x] `ai/gemini.py`: `generateContent` with `generationConfig.responseMimeType="application/json"` and a `responseSchema` derived from the Pydantic `TriageSuggestion` model: `{category (enum of active categories), priority (enum), one_line_summary, suggested_response_draft}`. Timeout 20s, 2 retries with backoff, validate with Pydantic, and fall back to `FakeProvider` on failure (log it; the ticket still flows).
- [x] **Verify the current REST request shape** (field names, `x-goog-api-key` header, endpoint path) against ai.google.dev docs before coding. Don't write it from memory.
- [x] Worker consumes `ticket.created` → calls triage → writes `ai_triage`, applies category + priority automatically, recomputes SLA, sets status `triaged`, and audit-logs with `actor_id = NULL` (system). `POST /tickets/:id/ai-triage` runs the same function synchronously (agent "re-run triage" button + internal use).
- [x] The worker also runs a 60s periodic loop: the **SLA-risk auto-escalation sweep** from §3 plus the auto-close sweep above. Put each sweep in its own function taking an injected `now`, so tests call it directly.
- [x] The agent can accept/override each field: `PATCH` records which fields were overridden in `ai_triage.accepted_fields`.

**KB search:**
- [x] `embedContent` with `outputDimensionality=768` and the appropriate task types (document vs query; verify the enum names in the docs). Normalise vectors before storing if the docs say reduced-dimension outputs aren't normalised.
- [x] `GET /kb/search?q=` → embed query → pgvector cosine top-4 → if best similarity < threshold (configurable), return `{answer: null, sources: []}` so the UI offers "Submit a request". Otherwise call Gemini with a strictly grounded prompt (answer only from the provided articles, cite as [1],[2], say you don't know otherwise) and structured output `{answer, cited_article_ids}`. Return `{answer, sources:[{id, title, slug, snippet}]}`. Drop any cited ID that wasn't in the retrieved set.
- [x] `GET /kb/articles/:slug` for the source link target.
- **Verify:** pytest with `FakeProvider` (deterministic). Then, **only if `GEMINI_API_KEY` is set**, a live smoke script `backend/scripts/smoke_gemini.py` that triages one ticket and runs one KB query against each of 3 seeded articles, printing results. Report honestly if no key is available.

  **Evidence (2026-09-24):**
  - **Live Gemini smoke test: NOT RUN.** No `.env` / `GEMINI_API_KEY` exists on this machine. `backend/scripts/smoke_gemini.py` is written and was executed: it printed `GEMINI_API_KEY is not set (or AI_PROVIDER=fake): nothing to smoke-test.` and exited 2. The Gemini REST request shapes are pinned by `httpx.MockTransport` tests only, so they are unproven against the live API until someone runs `docker compose exec api python scripts/smoke_gemini.py` with a key. The script disables the fake fallback for the grounded answer, so a silent fallback can't make it pass.
  - REST shapes verified on ai.google.dev (2026-09-24) before coding and recorded in the `backend/app/ai/gemini.py` docstring: `POST v1beta/models/{m}:generateContent` with header `x-goog-api-key`, `systemInstruction` + `contents` + `generationConfig.{responseMimeType, responseSchema}` (OpenAPI subset, uppercase types), reply at `candidates[0].content.parts[].text`; `POST v1beta/models/{m}:batchEmbedContents` with `requests[].{model: "models/<id>", content, embedContentConfig: {taskType, outputDimensionality}}` (the API reference marks the top-level `taskType`/`outputDimensionality` as deprecated), reply `embeddings[].values`; task types `RETRIEVAL_DOCUMENT`/`RETRIEVAL_QUERY`; the embeddings guide says `gemini-embedding-001` vectors below 3072 dims must be normalised by the caller, so they are L2-normalised. Note: the structured-output guide now leads with a newer Interactions API, but the reference still lists `generateContent` as supported and not deprecated, so §0's choice stands.
  - Phase 4 follow-ups, each with a test:
    - SLA fix: `recompute_due_on_priority_change` now takes `paused_total_seconds` and always returns `created_at + resolution_minutes + paused_total_seconds`, even while paused. `test_priority_change_after_a_pause_keeps_the_pause_credit` and `test_priority_change_while_pending_tightens_due_and_resume_adds_the_pause` cover it.
    - Internal-note attachments are filtered for end users in the query (outer join to `ticket_comments`).
    - `TicketDetailPublic` vs `TicketDetail`: the agent model's extra fields have no defaults, so a public payload can't validate as it. Tests assert `audit_log`/`ai_triage`/`sla_paused_total_seconds`/`allowed_transitions` are absent keys for end users.
    - `GET /attachments/{id}` is role-scoped (404 for another user's ticket or an internal-note attachment), served as `Content-Disposition: attachment` with `nosniff`, and the stored path is checked to be under `ATTACHMENTS_DIR`. Upload filenames are now stored with directory components stripped. Covered by `test_download_is_scoped_and_internal_note_attachments_never_reach_end_users`.
    - Auto-close sweep and SLA-risk sweep live in `backend/app/services/sweeps.py`, take `now`, and use `FOR UPDATE SKIP LOCKED`. PATCH, comments and triage also lock the ticket row (`services/tickets.lock_ticket`), which is what makes SKIP LOCKED meaningful. `test_sweep_skips_a_row_locked_by_a_concurrent_patch` holds a lock from a second session and shows the sweep skips the row, then escalates it once the lock is released.
  - Triage: the worker is a Redis Streams consumer group on `ticket.created`. It calls `services/triage.triage_ticket`, which applies category + priority only while the ticket is still `new` (and never a field an agent changed during the model call), recomputes SLA, sets `triaged`, stores `ai_triage = {suggestion, model, generated_at, accepted_fields}` and `ai_summary`, and writes an audit row with `actor_id = NULL`. The model call happens outside any transaction or lock. `POST /tickets/:id/ai-triage` runs it with `force=True`, for agents only (403 for end users). PATCH `ai_accept: [...]` plus direct category/priority edits record `accepted`/`overridden` in `ai_triage.accepted_fields`, which is audited.
  - `GeminiProvider` (`backend/app/ai/gemini.py`): a 20s timeout with 2 retries and exponential backoff on 408/429/5xx/timeouts for triage; 8s with 1 retry for the interactive KB calls. Pydantic validation, and category checked against the allowed enum. Triage and answer fall back to the fake with a warning; embeddings never fall back, since mixing vector spaces would corrupt search. `AI_PROVIDER` defaults to `auto`: Gemini only when `GEMINI_API_KEY` is set. Model IDs are read only from `config.py`.
  - KB: `GET /kb/search` embeds the query (`RETRIEVAL_QUERY`) and takes the pgvector cosine top 4, restricted to vectors whose `embedding_model` matches the current provider. Below the threshold it returns `{answer: null, sources: []}`. Otherwise it produces a grounded answer that cites by article id, and `domain/grounding.ground_citations` drops non-retrieved ids and renumbers markers to `[1]..[n]` in source order. `GET /kb/articles/{slug}`. FakeProvider embeddings were improved (stopwords, light stemming, sublinear TF → `fake-hash-v2`), because the old ones let "what is the weather in paris" (0.143) outscore "forgot my password" (0.06). Measured afterwards: relevant queries ≥ 0.079 with the correct top hit, irrelevant ≤ 0.025, so `KB_SIMILARITY_THRESHOLD_FAKE = 0.06`.
  - `docker compose exec api pytest -q` → **130 passed** (was 81). New suites: `test_ai_pure.py`, `test_gemini_provider.py` (request shape, retry, no retry on 4xx, fallback on invalid/blocked/non-JSON output and timeouts, embed normalisation, interactive budget), `test_triage.py`, `test_sweeps.py`, `test_kb.py` (4 seeded articles each return a grounded answer + source link; an irrelevant query returns null), and attachment download scoping. `ruff check app tests scripts` → "All checks passed!". Tests now publish to Redis DB 15, not the dev stack's DB 0, so a test run can no longer feed test-DB ticket ids to the dev worker.
  - Live on the dev stack (fake provider): as `user2`, `POST /tickets` "Locked out after password reset … Urgent" → the worker log shows `triaged ticket 3 with fake`. The agent view shows `status=triaged`, `category=account-login`, `priority=urgent`, `sla_response_due = created_at + 15m`, `sla_resolution_due = created_at + 4h`, `accepted_fields={"category":"auto","priority":"auto"}`, and audit `[ticket.created, ticket.ai_triaged]`. The end-user view of the same ticket had none of the agent-only keys. `GET /kb/search` returned grounded answers with the correct source for "I forgot my password", "why is my invoice prorated", "the site is slow and shows an error screen", "how do you protect my personal data" and "reset link never arrived"; "what is the weather in paris" → `answer: null`.
  - Found and fixed while verifying: redis-py 8 defaults `socket_timeout=5`, so a 5000ms `XREADGROUP` block crashed the worker on every idle read. It now blocks for 2s, survives Redis errors, and has `restart: unless-stopped`.
  - Code review (`code-review` at high) raised 10 findings, all fixed: unacked entries from dead consumers are now reclaimed with periodic `XAUTOCLAIM` (`test_worker_reclaims_entries_left_pending_by_a_dead_consumer`); triage no longer overwrites agent edits made mid-call (`test_worker_triage_never_overwrites_a_field_the_agent_changed_mid_call`); re-run keeps decisions whose suggestion didn't change; a non-JSON 2xx is a `GeminiError`; citations are by article id, so small ids can't be misread as positions; grouped markers `[12, 7]` are handled; empty category lists don't crash; long summaries are truncated rather than rejected; KB calls use a shorter interactive budget; `.env.example` now documents `auto`.

### Phase 6 — Frontend foundation: theme, shell, auth
**If `docs/design-plan.md` and `docs/mockups/` already exist,** they were produced in a parallel session for the user to review. Read them and the mockup's `m3-tokens.css`, and build from them. Don't rewrite them: append any revision to the plan's "Changes during build" section, with the reason. Only if they're missing, do the following. Load `material-3` and `frontend-design` first. Follow `frontend-design`'s two passes: write the design plan (seed, fonts, tone, per-portal table and banned list from §0, plus a one-sentence layout concept and ASCII wireframe for each portal) to `docs/design-plan.md`. Then review it against the brief, and record what you changed and why. Build only after that.
- [x] `theme/`: `material-color-utilities` → `SchemeContent` from `#1E6A5E` for light and dark, following `material-3`'s [theming-and-dynamic-color.md](.claude/skills/material-3/references/theming-and-dynamic-color.md). `SchemeContent` keeps the primary close to the chosen seed, where `SchemeTonalSpot` would desaturate it. Verify the class name and constructor in the installed package. Contrast level 0 by default, with the medium/high levels (0.5 / 1.0) exposed as a setting. Then emit every M3 colour role as a CSS variable (`--md-sys-color-*`), plus the shape scale (`--md-sys-shape-corner-*`), the type scale (`--md-sys-typescale-*`, with Google Sans Flex for display/headline and Roboto Flex for title/body/label), and the motion easing/duration tokens, all from `material-3`'s references. Then MUI `createTheme` maps palette, `shape`, typography roles (display/headline/title/body/label) and component overrides (Buttons = pill, no shadows anywhere: `shadows` all `none`, elevation via `surfaceContainer*`). Add a `density` context: `comfortable` (end user) vs `compact` (agent).
- [x] Theme toggle (system/light/dark). Fonts are loaded with `swap`.
- [x] Login/register screens (end-user styled), token store, `RoleGate`, role-based redirect after login (`end_user`→`/`, `agent`→`/agent`, `admin`→`/admin`).
- [x] A dev-only `/_tokens` route showing every color role and type role. It's used for the screenshot critique.
- **Verify:** `npm run build` + `npm run typecheck` clean. Screenshot `/_tokens` and the login page (Playwright) in light and dark, then critique against §0.

  **Evidence (2026-09-24):**
  - `material-3` and `frontend-design` were loaded first. [docs/design-plan.md](docs/design-plan.md) was written before any component code. It covers the seed, fonts and tone, the measured scheme table, the type scale, the per-portal table, the banned list, and a layout concept plus ASCII wireframe for each portal. Its §8 records six changes from reviewing it against the brief.
  - **§0 correction (description only, decision unchanged):** measured `SchemeContent(#1E6A5E)` output has a **dusky-violet tertiary** (`#4D3F71` light / `#CFBEF8` dark) and **cool, green-tinted neutrals**, not the "dusty-rose tertiary / warm neutrals" §0 describes. The seed and scheme are kept, because swapping in a hand-picked rose would break the brief's rule of tonal roles from a single seed. The violet is used as flat tonal fills only, never gradients.
  - Fonts verified from the installed packages' `metadata.json`: `'Google Sans Flex Variable'` (`@fontsource-variable/google-sans-flex/rond.css`: wght 1–1000, ROND 0–100, OFL-1.1) and `'Roboto Flex Variable'` (`@fontsource-variable/roboto-flex/opsz.css`: wght 100–1000, opsz 8–144, OFL-1.1), both `font-display: swap`. ROND is 60 in the end-user density scope and 0 in the agent scope. It's set in the MUI theme so portalled menus and dialogs inherit it.
  - `SchemeContent` class and constructor verified in `@material/material-color-utilities@0.4.0` (`(sourceColorHct, isDark, contrastLevel, specVersion?, platform?)`). The package ships extensionless internal ESM imports, which Node rejects, so vitest inlines it (`test.server.deps.inline`). Vite dev and build resolve it fine.
  - `frontend/src/theme/`: `scheme.ts` (seed → all 37 roles → `--md-sys-color-*`), `tokens.ts` (shape, typescale and motion vars), `muiTheme.ts` (palette from the same role map, 15 M3 typography variants mapped onto the MUI ones, pill buttons and chips, `shadows` all `none`, `textTransform: none`, tonal surfaces for Paper/Card/Menu/Dialog, compact vs comfortable density), `ThemeController.tsx` (system/light/dark + contrast 0/0.5/1, persisted with try/catch around `localStorage`, `DensityScope`).
  - Auth: `auth/session.ts` (token store, follows other tabs via the `storage` event), `AuthContext.tsx`, `RoleGate.tsx`, `LoginPage`/`RegisterPage` on `AuthLayout` (left-aligned headline beside the form, stacked at 360px). Role redirect: `end_user`→`/`, `agent`→`/agent`, `admin`→`/admin`. Shells: `EndUserShell` (top app bar, 880px column) and `AgentShell` (nav rail on medium and up, bottom navigation bar under 600px; Admin item only for admins). Dev-only `/_tokens`.
  - `npm run typecheck` → clean. `npm run build` → built, with only the >500 kB chunk advisory. `npx vitest run` → **8 passed** (`src/theme/scheme.test.ts`: primary hue stays within 8° of the seed in light and dark; a var for every role; WCAG AA ≥ 4.5 for 7 text pairings at all 3 contrast levels in both modes; higher contrast widens the gap; faces are Google Sans Flex + Roboto Flex with no mono/Inter/system-ui; no shadows or uppercase; density changes the body size).
  - Playwright (`frontend/e2e/phase6-foundation.spec.ts`, against the Compose stack) → **6 passed**: `/_tokens` + login screenshots in light and dark (asserts `--md-sys-color-primary` is the generated `#005147` / `#8dd4c5`); the computed heading font is Google Sans Flex and the button is Roboto Flex with `text-transform:none`, `box-shadow:none`, `border-radius:9999px`; RoleGate + redirects for all three roles; wrong-password error copy; register → `/`. Screenshots are in `docs/screenshots/phase-6/` (`tokens-{light,dark}`, `login-{light,dark}-{1280,360}`, `admin-shell-rail-1280`, `admin-shell-bottom-bar-360`).
  - Screenshot critique against §0:
    - Tonal surfaces carry depth with no shadows. Pill buttons and chips. Display roles read as Google Sans Flex, body as Roboto Flex, and IDs/timestamps use tabular figures. Dark mode is generated, not inverted.
    - The rail's selected item uses a secondary-container pill with a label in both states.
    - **Fixed:** the disabled grey "Sign in" made the page look inert on load. The primary action is now always enabled and the form validates on submit with field-level messages.
    - **Noted:** the generated `onSecondaryContainer` (`#506963` on `#CCE9E1`, ≈4.5:1) passes AA but looks light. It's kept as generated, and medium/high contrast is available in the Appearance menu.
  - **Found and fixed:** Vite and uvicorn `--reload` in Docker never saw bind-mount edits on Windows, so the dev server kept serving stale modules. Compose now sets `VITE_USE_POLLING=true` (the Vite config polls when set) and `WATCHFILES_FORCE_POLLING=true`.
  - Code review (`code-review` at high) found 10 issues, all fixed:
    - NavLink forced `aria-current` by prefix, marking Queue as current on the dashboard → plain `Link`.
    - `/auth/me` could merge into a different user's session → token-guarded.
    - A stale token's 401 could sign out a newer session → token-guarded.
    - No cross-tab session sync → `storage` listener.
    - Rail flashed on phones before the media query settled → `noSsr`.
    - ROND was lost in portalled menus and dialogs → moved into the theme.
    - Playwright output wasn't gitignored → ignored.
    - `/admin` remounted the agent shell → nested under one layout.
    - Emails weren't trimmed → trimmed on sign-in and register.
    - `toCamel` was duplicated → shared.

### Phase 7 — End-user portal (calm, spacious)
- [x] Home: a prominent KB search field (M3 search bar). The **signature grounded-answer panel** shows the answer text with inline [n] markers mapped to numbered source chips that link to the article page, with loading skeleton and empty/no-answer states. Below it is "Your requests" as a list with status chip, relative updated time and a human status line ("Waiting on you" for `pending`).
- [x] New request: subject, description, optional attachment. On submit, go to the ticket view with an optimistic "We're reviewing this" state, which updates (poll every 3s up to 30s, or refetch on focus) when triage lands and applies the category/priority.
- [x] Ticket view: the public thread only, a reply box, and state-aware copy (resolved → "Reply within 72h to reopen"; closed → "Replying starts a new request").
- **Verify:** Playwright: register → search KB (answer + source link visible) → submit ticket → the category/priority chip appears. Screenshot at 360px and 1280px, then critique.

  **Evidence (2026-09-24):**
  - Screens (`frontend/src/portals/enduser/`):
    - `HomePage`: an M3 search bar with `role="search"`, a 56dp pill and the query kept in `?q=`. The signature `KbAnswerPanel` on `primary-container` has inline `[n]` markers linked to `/help/:slug`, numbered source chips, a skeleton while loading, and no-answer and 503 states that each offer "Send a request". "Your requests" is a divided list, not cards, with subject + human status line, status chip and relative time + `TCK-` ref in separate columns.
    - `NewRequestPage`: subject, details, and an optional attachment with a client-side type/10 MB check. The query is prefilled from the KB panel.
    - `RequestPage`: public thread only; staff are shown as "Tara from Support". Attachment download goes through the authed client. The reply box copy depends on state: pending → "We're waiting on your reply to continue."; resolved → "Reply within 72h to reopen this request.", with the window from the API's new `reopen_until`, so it follows `RESOLVED_COOLOFF_HOURS`; closed → "Replying starts a new request.", which navigates to the linked follow-up.
    - `ArticlePage`: the source-link target.
  - Optimistic "We're reviewing this" state: `RequestPage` polls every 3s while `status == "new"`, for up to 30s per ticket (the page is keyed by id), then falls back to refetch-on-focus. Category and priority chips appear, with `aria-live`, when the worker's triage lands.
  - Backend additions this phase:
    - `GET /categories`, which lists all categories for display names.
    - `CommentOut.author_name`/`author_role`, where customers get staff first names only and the author is loaded explicitly (`selectinload`, `lazy="raise"`).
    - `TicketDetailPublic.reopen_until`.
    - Tests: `test_thread_carries_author_names_and_categories_are_listed` and `test_customers_see_staff_first_names_and_reopen_window`. `pytest` → **132 passed**, and ruff is clean.
  - `npm run typecheck` is clean and `npm run build` succeeds. `vitest` → **14 passed**; `src/lib/enduser.test.ts` covers `replyMode` for resolved within/after the server window (including a 24h configuration), closed, pending and active, plus customer status copy, `parseAnswer` marker splitting and out-of-range drop, `ticketRef` and `relativeTime`.
  - Playwright → **10 passed** in total. `e2e/phase7-enduser.spec.ts`:
    - **register → KB search** "I forgot my password and the reset email never came" → the answer region is visible, with the "Source 1: Resetting your password" marker and a source chip whose `href="/help/resetting-your-password"`. Clicking the chip opens the article. An irrelevant query shows "No help article answers this yet".
    - **submit** "Charged twice this month" with a `.txt` attachment → the page shows **"Billing"** and **"High priority"** chips once the real worker triage lands, plus the attachment. The request is listed on home.
    - A second test drives an agent through the API (assign → open → in_progress → reply → pending) and checks "Waiting on you" plus the pending copy. It then replies (→ In progress), resolves (→ "Reply within 72h to reopen this request." / "Reopen with reply"), closes (→ closed copy), and replies again, which lands on a follow-up with a "Follow-up to TCK-…" link and a toast.
  - Screenshots in `docs/screenshots/phase-7/`: `home-empty-1280`, `home-answer-{1280,360}`, `home-answer-dark-1280`, `home-no-answer-1280`, `article-1280`, `new-request-1280`, `request-triaged-1280`, `request-pending-{1280,360}`, `request-pending-dark-360`, `request-resolved-1280`, `home-with-requests-{1280,360}`.
  - Screenshot critique, all fixed:
    - The 1280 answer panel had been captured mid-reveal. The screenshot helper now waits two frames and then for finite animations to finish.
    - The "Request sent" toast repeated on reload, because router state persists. The state is now cleared after it's read.
    - "Send reply" was disabled until you typed, the same inert look as on login. It's now enabled with on-submit validation.
    - The dark-mode capture had caught a theme transition. Confirmed as a capture timing issue, not a colour bug.
    - The search input was only 32px tall inside the 56px bar. It now fills the bar.
  - **`material-3` audit: [docs/audits/phase-7-md3.md](docs/audits/phase-7-md3.md), 85/100, every category ≥ 8** (lowest: Typography, Shape, Components, Layout, Navigation and Motion at 8). Evidence includes `@axe-core/playwright` WCAG 2.2 AA → **0 violations** across 10 scans (5 screens × light/dark; `e2e/phase7-a11y.spec.ts`), after fixing the one contrast failure it found (the panel footer at an 85% colour mix). Also: no hex/rgba outside `theme/`, every radius a shape token, no shadows, and 48dp hit areas.
  - Code review (`code-review` at high) found 10 issues, all fixed:
    - `RequestPage` kept toast and poll state across ticket ids → remounted per id.
    - The screenshot wait would hang on infinite animations → filtered to finite ones.
    - Unhandled `mutateAsync` rejections → switched to `mutate` + `onSuccess`.
    - A tickets-query error showed the empty state → error state with a retry.
    - The hardcoded 72h window → `reopen_until` from the server.
    - Download bypassed the client's 401 handling and revoked the URL too early → `apiBlob` + delayed revoke.
    - The always-joined comment author and full staff names sent to customers → explicit load + first names.
    - A 40px hit area on small buttons → `-8px` inset.
    - The unencoded article slug and the duplicated query threshold → encoded + `MIN_QUERY`.

### Phase 8 — Agent console (dense, data-forward)
- [x] Nav rail (Queue, Dashboard; Admin if admin). Queue = filter chips (status, priority, assignee incl. "Mine"/"Unassigned", category) + a dense table with ID (tabular figures), subject + AI one-liner, requester, priority, status, **SLA indicator**, assignee, updated. The URL holds the filter state. Keyboard: `j/k` to move, `Enter` to open.
- [x] Ticket detail (right pane or route): the thread with internal notes visually distinct (tertiary-container tint + "Internal" label, not color alone). The composer has a Reply / Internal note toggle. Side panel: status control that **only offers legal next transitions** (from the API), assignee picker, priority, category, Escalate button, and an **AI triage panel** with the suggestions, per-field Accept/Override, a "Use draft" button that inserts `suggested_response_draft` into the composer, and "Re-run triage". Audit trail in a collapsible section.
- [x] `SlaIndicator`: countdown in tabular Roboto Flex with ring progress. States: on track / at risk (tertiary) / breached (error) / **paused** (outlined + "Paused" text), and none when resolved/closed. All states carry text, not just color.
- **Verify:** Playwright: an agent opens the seeded ticket, walks it through the full lifecycle via the UI, and adds an internal note. The end-user session doesn't see the note. Screenshot the queue at 1280 and 1600 and critique the density against the end-user portal.

  **Evidence (2026-09-24):**
  - Backend for the console:
    - Agent-only `TicketQueueItem` rows (requester/assignee names, `sla_paused_at`, `first_responded_at`, `sla_paused_total_seconds`). End users still get the public `TicketListItem`.
    - A repeatable `status` filter and a `sla_due` sort: the first-reply clock while unanswered, then resolution; paused tickets sort by where the deadline would be if resumed now.
    - `requester_name`/`requester_email`/`assignee_name` on the agent detail, `actor_name` on audit rows, and `GET /users/staff` (agents/admins only).
    - Tests: `test_agent_queue_rows_carry_names_and_clock_inputs_end_users_dont` and `test_sla_due_sort_puts_long_paused_tickets_after_running_urgent_ones`. `pytest` → **134 passed**, and ruff is clean.
  - Console (`frontend/src/portals/agent/`):
    - `QueuePage` + `QueueToolbar`: Status/Priority/Assignee (Anyone, Mine, Unassigned, each agent)/Category filter chips with menus, plus search. All filter state lives in the URL.
    - `QueueTable`: 36px rows with ID in tabular figures, subject plus the AI one-liner when it differs from the subject, requester, priority, status, **SLA indicator**, assignee, and a compact updated time. `j`/`k`/`Enter` move and open, and the selection is kept by ticket id across the 20s refresh.
    - `AgentTicketPage`: 3 panes at ≥ 1200, 2 at 840–1199, 1 below. The thread shows internal notes as a tertiary tint with a bar and a lock-icon "Internal note" label. The Reply / Internal note composer says who will see the message.
    - `TicketSidePanel`: the status select offers only `allowed_transitions`, with "open" guarded until someone is assigned; assignee plus "Take it"; priority; category; Escalate.
    - `AiTriagePanel`: per-field Accept with Applied/Accepted/Overridden/"Changed since" state, "Use draft" into the composer (never discards typed text or makes a note public), and Re-run.
    - `AuditTrail`: a collapsible history with actor names, and "System" for null actors.
  - `SlaIndicator` (`components/SlaIndicator.tsx`, logic in `lib/sla.ts`): a ring plus a tabular countdown. States are on track (primary), at risk <25% (tertiary + "At risk"), breached (error + "Breached", "12m over"), paused (dashed outline ring + "Paused", with the countdown frozen at the pause point), and none when resolved or closed. It has `role="img"` with a sentence label, and one shared 15s ticker drives every countdown.
  - `vitest` → **22 passed**. `src/lib/agent.test.ts` covers the response → resolution clock switch, the at-risk and breached thresholds, pause-credit in the window, frozen while paused (never "breached"), none when resolved or closed, duration formatting, and `statusOptions` (only the API's legal moves; the triaged→open guard).
  - Playwright `e2e/phase8-agent.spec.ts` → **3 passed**:
    - A realistic queue is seeded through the API: 6 tickets from a second customer across urgent/high/normal/low, one pending and one assigned.
    - **The agent walks a ticket through the whole lifecycle in the UI:**
      - It opens from the queue, after checking that the filter chip writes `?priority=high` to the URL and that `j`/`k` select.
      - It accepts the AI category (the panel shows "Accepted") and uses the draft (the composer is filled).
      - "Move to open" is disabled until the agent clicks "Take it". Then: open → in progress → sends the drafted public reply.
      - It adds an internal note, which renders with the "Internal note" label.
      - Pending → the side panel shows "Paused". Then in progress → resolved (SLA "None") → closed.
      - History shows "System ran AI triage".
    - **The customer never sees the note:** the API's `GET /tickets/:id` as `user1` has no internal comment, and a separate customer browser context shows the agent's public reply and "Closed" but not the note text.
    - Dark-mode captures.
  - Screenshots in `docs/screenshots/phase-8/`: `queue-1280`, `queue-1600`, `ticket-pending-1280`, `ticket-pending-1600`, `queue-dark-1600`, `ticket-dark-1600`.
  - Screenshot critique, all fixed:
    - Internal notes on the generated `tertiaryContainer` were a heavy dark-violet block, so they're now a tint + bar + label.
    - Selects showed the menu's two-line text inside the field, so they now use `renderValue`.
    - The "Updated" column truncated ("7 minutes …"), so it now shows a compact "7m" with the full time in the title.
    - The AI panel still said "Applied" after escalation changed the priority, so it now says "Changed since".
  - Density against the end-user portal: 14px body vs 16px, 36px rows vs ~72px, full-bleed 3 panes vs an 880px column, 8px panes vs 28–32px containers, a layered surface ladder vs flat surfaces with one saturated moment, ROND 0 vs 60. Table in the audit.
  - **Found and fixed:**
    - A crash on leaving the queue ("destroy is not a function"). An expression-bodied `useEffect(() => el.scrollIntoView())` returned a Promise, because current Chromium returns one from `scrollIntoView`, and React treated it as the cleanup. All effects are now block-bodied.
    - The M3 48dp touch target added to `IconButton`.
  - **`material-3` audit: [docs/audits/phase-8-md3.md](docs/audits/phase-8-md3.md), 84/100, every category ≥ 7** (Motion 7, Components, Layout, Navigation, Typography and Accessibility 8). axe WCAG 2.2 AA → **0 violations** on the queue and the workspace (with the note composer open), in light and dark (`e2e/phase8-a11y.spec.ts`). Also: no hex/rgba outside `theme/`, every radius a token, and `boxShadow` used only for inset selection bars.
  - Code review (`code-review` at high) found 10 issues, all fixed:
    - A transient refetch error replaced the loaded ticket or queue with an error screen.
    - The shared clock was stale after idling.
    - Paused tickets sorted as most overdue.
    - Queues weren't refreshed after a reply.
    - The "Paused so far" row never rendered.
    - The keyboard selection was tracked by index.
    - `j`/`k` on a focused control switched tickets and lost the draft.
    - "Use draft" overwrote the text and flipped a note to public.
    - A redundant detail refetch after each PATCH.
    - Duplicated category-name and ticket-ref helpers.

### Phase 9 — Analytics dashboard + Admin
- [x] `GET /analytics/summary?from&to`: ticket volume per day, median/avg first-response time, median/avg resolution time (excluding paused time), backlog by status, SLA breach count. SQL aggregates, not Python loops.
- [x] Dashboard: 4 stat tiles plus 2 charts (volume over time; backlog by status). **Load the `dataviz` skill** before building charts. Chart colors come from the M3 scheme roles.
- [x] Admin (minimal): users table with role/team edit, a category list (add/deactivate), and an SLA policy editor (edit minutes per priority; applies to new tickets only, which is stated in the UI). All changes are audit-logged.
- **Verify:** pytest for the analytics math on a fixed dataset; screenshot the dashboard and critique.

  **Evidence (2026-09-24):**
  - `GET /analytics/summary?from&to` (`backend/app/routers/analytics.py`, agents and admins only): every figure is a SQL aggregate.
    - Per-day volume uses `generate_series` over dates with UTC-explicit bounds, so buckets don't depend on the DB session `TimeZone`.
    - First response and resolution use `percentile_cont(0.5)` and `avg`; resolution subtracts `sla_paused_total_seconds`.
    - Backlog is the current active statuses, zero-filled.
    - SLA breaches are counted with `count(*) FILTER`. A paused ticket counts only if it paused after its due date.
    - Defaults to the last 30 UTC days (from the injectable clock); a 366-day cap; 422 if from > to.
  - Admin endpoints (`backend/app/routers/admin.py`, every write goes through `write_audit`):
    - `GET/PATCH /users`: role/team edits; team is cleared for non-agents; no self role change; can't demote someone still holding open tickets; an explicit null is ignored.
    - `POST/PATCH /categories`: slugged, 409 on duplicates, names validated after trimming, the slug stays fixed on rename.
    - `GET/PATCH /sla-policies/{priority}`: 1 min to 90 days, first reply ≤ resolution.
    - `GET /admin/audit`: a change feed with actor and subject names.
  - `pytest` → **138 passed**. `tests/test_analytics_admin.py` checks against a hand-computed dataset with a frozen clock:
    - volume `[2, 1, 2]`
    - first response median 900s / average 1425s over 4 tickets
    - resolution median/average 48600s over 2 tickets, with a 1h pause excluded
    - backlog `{new 1, triaged 0, open 1, in_progress 1, pending 1}`
    - breaches `{total 3, response 2, resolution 3}`, including a paused-before-due ticket correctly not counted
    - the default 30-day window, 422 and 403

    It also covers the admin rules, audit rows with before/after, and that new tickets pick up an edited policy while existing ones keep their dates. ruff is clean.
  - `dataviz` loaded before any chart code. Dashboard (`frontend/src/portals/agent/dashboard/`):
    - A 7/30/90-day segmented range (`?days=`) in one row above everything.
    - Four stat tiles: tickets created, median first response, median resolution (paused time excluded), SLA breaches split into first-reply and resolution.
    - A daily column chart and a backlog bar chart. Both are single-series in `primary`, with ≤ 24px bars, 4px rounded data ends, a hairline grid, a value-first tooltip on hover and arrow keys, a crosshair, and a "Show as table" twin. The previous render is held (dimmed) while refetching.
    - Validator: `primary` passes mark contrast on both chart surfaces in both modes. The seed tone was rejected for dark mode (2.9:1).
  - Admin (`frontend/src/portals/admin/AdminPage.tsx`, URL tabs):
    - Users: role and team selects; own role locked.
    - Categories: add, plus an active switch.
    - SLA policies: minute fields with hour hints and per-row Save, under the stated rule "Changes apply to tickets created after you save. Existing tickets keep their due dates unless their priority changes."
    - Change log: rows such as who, "User Tom Tier1", "Team Tier 1 to Senior" in separate cells.
    - Loading and error states on every tab.
  - `vitest` → **24 passed**, adding `niceTicks` (clean whole steps) and `describeChange`. Playwright `e2e/phase9-dashboard-admin.spec.ts` → **2 passed**:
    - tiles match the API's figures; hover and arrow-key tooltips; the table view has 30 rows plus a header; the range switch updates the URL
    - an admin team change, an SLA edit, and a category add plus deactivate all appear in the change log
    - the spec restores the seeded SLA values afterwards
  - Full Playwright suite → **17 passed**.
  - Screenshots in `docs/screenshots/phase-9/`: `dashboard-{1600,1280}`, `dashboard-hover-1600`, `dashboard-dark-1280`, `dashboard-dark-390`, `admin-{users,sla,categories,changes}-1280`.
  - Critique fixes:
    - The top y-tick label was clipped, so the plot has top padding.
    - "<1m" hid real sub-minute response times, so the dashboard shows seconds.
    - The SLA table mixed "Urgent" with "High priority", so it uses one short label map.
    - Snackbars covered the rail's account button, so they're centred.
    - "When" wrapped in the change log, so it's wider and doesn't wrap.
  - **`material-3` audit: [docs/audits/phase-9-md3.md](docs/audits/phase-9-md3.md), 84/100, every category ≥ 7** (Motion 7, Components, Layout, Navigation and Accessibility 8), plus the dataviz checklist. axe WCAG 2.2 AA → **0 violations** on the dashboard (light and dark, table open) and admin Users/SLA, after fixing a non-focusable scrollable table region it found.
  - Code review (`code-review` at high) found 9 issues, all fixed:
    - An explicit null role caused a 500.
    - Whitespace-only category names were accepted.
    - The change log didn't say what changed.
    - Demoting an agent orphaned their tickets.
    - Every admin save invalidated the whole query cache.
    - The analytics cache was keyed by preset rather than dates, so it went stale across UTC midnight.
    - Volume buckets depended on the session time zone.
    - Admin tabs had no loading/error states.
    - The priority label map was duplicated.

### Phase 10 — Hardening & acceptance
- [ ] README: one-command start, seeded credentials, how to add `GEMINI_API_KEY`, the fake vs gemini provider, and the stated seed/type/tone.
- [ ] Seed ~25 demo tickets across all statuses/priorities (behind `SEED_DEMO=true`, default on locally) so the queue and dashboard aren't empty. If `docs/demo-data/tickets.json` exists, load that content rather than writing new tickets. Timestamps in it are relative offsets, so resolve them against `now` at seed time, and set the SLA fields through `domain/sla.py`, not by hand.
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
