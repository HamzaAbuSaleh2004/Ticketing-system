# Ticketing Portal — executor instructions

- Requirements: [ticketing-portal-brief.md](ticketing-portal-brief.md). Plan and progress: [PLAN.md](PLAN.md).
- Work through PLAN.md phases **in order, without stopping between them**. For each phase:
  1. Do the phase's follow-ups first.
  2. Build it.
  3. Run its Verify step and look at the real output.
  4. Run the `code-review` skill at `high` on that phase's diff and fix confirmed findings. This replaces the review between phases that the planner used to do.
  5. Tick its boxes in PLAN.md with evidence.
  6. Commit as `Phase N: <title>`, then post a 3–5 line progress note and continue.
- **Stop and ask only when you're blocked:** a Verify step fails and you can't fix it, a §0 decision looks wrong, or you need something only the user has, such as a `GEMINI_API_KEY`. Never tick a box or claim a pass you didn't observe.
- §0 decisions in PLAN.md are locked: FastAPI + Postgres + React/Vite/TS + MUI themed to M3. (2026-09-29, user's scope change: no AI, no pgvector, no Redis; mandatory TOTP 2FA. See PLAN.md Phase 11. The Gemini rules below no longer apply.) Seed `#1E6A5E`, Google Sans Flex (display) / Roboto Flex (body, and data with tabular figures), no monospace. Don't change them without asking.
- Before any UI work, load **both** `material-3` and `frontend-design` (in [.claude/skills/](.claude/skills/)). Precedence: brief > `material-3` > `frontend-design`. Before any chart, load `dataviz`. Before calling anything done, take screenshots and critique them, and pass the `material-3` audit (≥ 7/10 per category) as described in PLAN.md §0.
- Never hardcode Gemini model IDs outside `backend/app/config.py`. Verify Gemini REST request shapes against ai.google.dev docs rather than writing them from memory.
- The stack must run with no `.env` (`AI_PROVIDER=fake`). Real Gemini is used only when `GEMINI_API_KEY` is set.
- Non-goals from the brief are out of scope, even if they'd be quick.
- Platform: Windows 11, Docker Desktop (Compose v5), Node 24, Python 3.11 on host (containers use Python 3.12). Git repo on `master`. Commits come after each verified phase.
