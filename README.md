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

No `.env` is required — the stack defaults to `AI_PROVIDER=fake` (deterministic, offline
AI). Copy `.env.example` to `.env` and set `GEMINI_API_KEY` to use real Gemini instead.

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

## Seeded accounts

Created by `backend/app/seed.py` (idempotent — safe to re-run). All accounts share the
password below; change it before this ever leaves a local dev environment.

| Email | Role | Team | Password |
|---|---|---|---|
| admin@ticketing.local | admin | — | `ChangeMe123!` |
| agent1@ticketing.local | agent | tier1 | `ChangeMe123!` |
| agent2@ticketing.local | agent | tier1 | `ChangeMe123!` |
| agent3@ticketing.local | agent | senior | `ChangeMe123!` |
| user1@ticketing.local | end_user | — | `ChangeMe123!` |
| user2@ticketing.local | end_user | — | `ChangeMe123!` |
