# Ticketing Portal

Two-portal customer support ticketing system (end-user + agent/admin), built Material 3,
running fully local via Docker Compose. See [ticketing-portal-brief.md](ticketing-portal-brief.md)
for requirements and [PLAN.md](PLAN.md) for the execution plan and progress.

> This README is filled in incrementally as phases land (see PLAN.md Phase 10 for the
> final pass: one-command start, `GEMINI_API_KEY` setup, fake vs. Gemini provider, and the
> stated design direction).

## Running it

```
docker compose up -d --build
```

No `.env` is required: with no `GEMINI_API_KEY` the stack uses a deterministic, offline
fake AI provider. Copy `.env.example` to `.env` and set `GEMINI_API_KEY` to use real Gemini
instead (`AI_PROVIDER=auto` is the default), then restart so the KB is re-embedded. Check it
end to end with `docker compose exec api python scripts/smoke_gemini.py`.

- API: http://localhost:8000 (health: `GET /health`)
- Frontend: http://localhost:5173

### When you change dependencies

- **Backend** (`backend/pyproject.toml` / `uv.lock`): just rebuild — `docker compose up -d --build api worker`.
  The venv lives at `/opt/venv` inside the image (not a mounted volume), so a rebuild always
  picks up the new lockfile.
- **Frontend** (`frontend/package.json`): `node_modules` is an anonymous volume Compose
  normally carries over between recreates, so a plain `--build` isn't enough. Use:

  ```
  docker compose up -d --build --renew-anon-volumes frontend
  ```

## Running the backend tests

```
docker compose exec api pytest
```

Tests run against a real Postgres database (`ticketing_test`, created automatically on the
same `db` service — not mocked or SQLite), migrated with `alembic upgrade head`. Tables are
truncated after every test for isolation, so re-running is always safe.

## Seeded accounts

Created by `backend/app/seed.py` (idempotent — safe to re-run). All accounts share the
password below; change it before this ever leaves a local dev environment.

| Email | Role | Team | Password |
|---|---|---|---|
| admin@ticketing.demo | admin | — | `ChangeMe123!` |
| agent1@ticketing.demo | agent | tier1 | `ChangeMe123!` |
| agent2@ticketing.demo | agent | tier1 | `ChangeMe123!` |
| agent3@ticketing.demo | agent | senior | `ChangeMe123!` |
| user1@ticketing.demo | end_user | — | `ChangeMe123!` |
| user2@ticketing.demo | end_user | — | `ChangeMe123!` |
