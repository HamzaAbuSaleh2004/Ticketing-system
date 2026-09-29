# LiverX Help Desk — executor instructions

- Requirements: [ticketing-portal-brief.md](ticketing-portal-brief.md), as amended by the scope-change note at the top of [PLAN.md](PLAN.md). Where they conflict, the note wins. Plan and progress: PLAN.md.
- Work through PLAN.md phases **in order, without stopping between them**. Before each phase, re-read it and `git log -3`, because the plan can be edited in parallel. For each phase:
  1. Do the phase's follow-ups first.
  2. Build it.
  3. Run its Verify step and look at the real output.
  4. Run the `code-review` skill at `high` on that phase's diff and fix confirmed findings.
  5. Tick its boxes in PLAN.md with evidence.
  6. Commit as `Phase N: <title>` (stage the files you changed, not a blind `git add -A`), then post a 3–5 line progress note and continue.
- **Stop and ask only when you're blocked:**
  - a Verify step fails and you can't fix it;
  - a §0 decision looks wrong;
  - you need something only the user has: the GCP project, billing, region or `gcloud auth login` (Phase 16), or consent for anything billable or outward-facing.

  Never tick a box or claim a pass you didn't observe.
- Locked stack: FastAPI + Postgres + React/Vite/TS + MUI themed to M3, with mandatory TOTP 2FA for every account.
  - No AI features, no Redis, no pgvector.
  - Type: Google Sans Flex (display) and Roboto Flex (body) until Phase 14 switches to the LiverX brand fonts: IBM Plex Sans, with Tajawal for Arabic. Tabular figures for data, no monospace.
  - The seed colour is `#1E6A5E` until Phase 14 replaces it with LiverX cyan `#00A4D8` (the brand guideline is in `docs/brand/`).
  - Every `Button` uses the same filled primary colour (the user's rule, Phase 14).
  - Don't change any of these without asking.
- Before any UI work, load **both** `material-3` and `frontend-design` (in [.claude/skills/](.claude/skills/)). Precedence: brief (as amended) > `material-3` > `frontend-design`. Before any chart, load `dataviz`. Before calling anything done, take screenshots and critique them, and pass the `material-3` audit (≥ 7/10 per category) as described in PLAN.md §0.
- Before any Google Cloud work, load the `google-cloud-platform` skill. Verify `gcloud` flags and Google client-library APIs against the docs or `--help`, not memory. Never put secrets in the repo, scripts or logs. Show the user a cost estimate before creating anything billable.
- The local stack must keep running with no `.env`: `docker compose up --build`, then the app is at http://localhost:5173.
- Out of scope, even if quick: AI features, email/social intake, an automation rules engine.
- Platform: Windows 11, Docker Desktop (Compose v5), Node 24, Python 3.11 on host (containers use Python 3.12). Most source files are CRLF. Git repo on `master`. Commits come after each verified phase.
