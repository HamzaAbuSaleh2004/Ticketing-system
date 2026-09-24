# Ticketing Portal — executor instructions

- Requirements: [ticketing-portal-brief.md](ticketing-portal-brief.md). Plan and progress: [PLAN.md](PLAN.md).
- Work **one PLAN.md phase at a time**. Finish its Verify step with real command output, tick its boxes in PLAN.md, report, then stop and wait for the user.
- §0 decisions in PLAN.md are locked: FastAPI + Postgres/pgvector + Redis Streams + React/Vite/TS + MUI themed to M3. Seed `#1E6A5E`, Google Sans Flex (display) / Roboto Flex (body) / Google Sans Code (data only). Don't change them without asking.
- Before any UI work, load the `beautiful-web-ui` skill. Before any chart, load `dataviz`. Before calling anything done, take screenshots and critique them.
- Never hardcode Gemini model IDs outside `backend/app/config.py`. Verify Gemini REST request shapes against ai.google.dev docs rather than writing them from memory.
- The stack must run with no `.env` (`AI_PROVIDER=fake`). Real Gemini is used only when `GEMINI_API_KEY` is set.
- Non-goals from the brief are out of scope, even if they'd be quick.
- Platform: Windows 11, Docker Desktop (Compose v5), Node 24, Python 3.11 on host (containers use Python 3.12). No git repo yet; run `git init` in Phase 1.
