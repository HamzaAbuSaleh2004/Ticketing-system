# MD3 Compliance Audit Report: Phase 15 (LiverX branding and one button colour)

- **Target:** the whole app's theme layer (`frontend/src/theme/*`), the wordmark/icon (`frontend/src/components/Logo.tsx`, `frontend/src/assets/brand/*`, `frontend/public/*`), and every `Button` call site across both portals and the admin console. This is a global re-theme (seed colour, typeface, one button style), so it's audited against representative screens from every portal rather than one feature area.
- **Method:** source review, plus screenshots and automated checks against the running Compose stack (fresh `docker compose down -v && up -d --build`, so every screenshot below reflects a clean seed, not hours of accumulated e2e fixture data). `material-3` and `frontend-design` were loaded before any of this phase's UI edits, per CLAUDE.md.
- **Date:** 2026-09-29
- **Overall score: 87/100.** Every category is ≥ 7, so the gate passes.

## Scores by category

| Category | Score | Status |
|---|---|---|
| Color tokens | 9/10 | pass |
| Typography | 9/10 | pass |
| Shape | 9/10 | pass |
| Elevation | 8/10 | pass |
| Components | 9/10 | pass |
| Layout | 8/10 | pass |
| Navigation | 8/10 | pass |
| Motion | 8/10 | pass |
| Accessibility | 9/10 | pass |
| Theming | 10/10 | pass |

## Evidence

- **Color tokens.**
  - Seed changed from the placeholder Spruce (`#1E6A5E`) to the LiverX brand's Bright Cyan Blue `#00A4D8` (`frontend/src/theme/scheme.ts`), still expanded at runtime by `SchemeContent`, still no hand-picked hex palette anywhere in component code.
  - Measured: light `primary` = `#006688`, dark `primary` = `#75D1FF`. The light primary sits **0.85° from the brand's Teal Blue `#007BA2`** on the hue wheel (checked with `Hct.fromInt`, well inside "reads as LiverX").
  - `scheme.test.ts`'s WCAG AA suite (primary/on-primary, both containers, surface/on-surface, surface-container-highest/on-surface-variant) passes at all three contrast levels (0 / 0.5 / 1) against the new seed — same assertions as before Phase 15, now proven against the brand colour instead of Spruce.
  - The two brand-specific hex literals in the codebase (`#ffffff` in `Logo.tsx`'s dark-mode chip, `#00a4d8` in `site.webmanifest`'s `theme_color`) are both outside the themed component tree by necessity: the manifest has no access to CSS custom properties, and the logo chip deliberately needs the *light* theme's `surface-container-lowest` (which is `#ffffff` by M3 definition in light mode, confirmed via `generateScheme(false)`) regardless of which mode is currently active — using the live `sys()` var there would return the *dark* value while dark mode is on, defeating the point.
- **Typography.** IBM Plex Sans (400/500/700) replaces Google Sans Flex + Roboto Flex for every role — display through label — with Tajawal after it in the stack for Arabic text (`frontend/src/theme/tokens.ts`). The former two-face `font: "display" | "body"` tag on `TYPESCALE` was removed as part of this change (code review: it was vestigial once both faces became the same value). `e2e/phase6-foundation.spec.ts`'s font test confirms `getComputedStyle` on both a heading and a button resolves to `"IBM Plex Sans"`, and the vitest suite confirms no monospace/system-ui/Inter fallback crept in.
- **Shape.** Unchanged from Phase 9–14: every radius is a token (`small` agent panes, `extra-large` end-user cards, `full` buttons/chips). Not touched by this phase.
- **Elevation.** Unchanged (no shadows, tonal surfaces only). Scores 8, same residual gap as before: the SLA ring and a couple of chips are the only components carrying any depth cue, which is intentional per the design plan.
- **Components.**
  - **One button colour, applied.** `MuiButton`'s `defaultProps.variant` is now `"contained"`, and `tonal`/`outlined`/`text` are mapped in `variants` to the identical filled-primary/`onPrimary` style, so nothing slips through even if a call site still asks for one of them. A grep audit (`grep -rn 'variant="tonal"\|variant="outlined"\|variant="text"' src --include=*.tsx`) confirms zero remaining matches on any `<Button>` in the app; the only `variant="outlined"`/`"text"` left in the codebase are on `Chip` and `Skeleton`, which the plan explicitly exempts ("icon buttons, chips, links, tabs, segmented buttons and menu items are not buttons").
  - Per-button colour overrides were removed too — e.g. the ticket workspace's "Escalate" button no longer hardcodes `sys("error")`/`sys("outline")`; it's the same filled-primary button as everything else, exactly as the rule requires.
  - A new vitest (`scheme.test.ts`, "every Button variant renders the same filled-primary colour pair") renders the theme's `MuiButton.variants` and asserts all four map to one identical `{backgroundColor, color}` pair, matching `theme.palette.primary`.
  - **One reviewed consequence, checked against the locked decision, not changed:** in the admin "Add admin or agent" and "Reset two-step verification" dialogs, `Cancel` and the confirming action now render identically (both filled primary). PLAN.md's own Phase 15 text anticipates exactly this ("Cancel and Reset in the admin 2FA dialog look the same; order and wording make the difference") — it's the accepted cost of the rule, not a bug, so it wasn't reverted.
- **Layout.** Not touched by this phase. Unaffected because the font-size scale (`TYPESCALE`) kept the same px/line-height values — only the face changed.
- **Navigation.** The X icon now marks the top of the agent nav rail (`AgentShell.tsx`), and the wordmark replaces the "Support" text link in both the end-user top app bar and the auth layout header. Both are real `<img alt="LiverX">` elements, not decorative background images, so they're in the accessibility tree.
- **Motion.** The ROND-axis "personality" difference between the two portals (Google Sans Flex's variable rounding, 60 vs 0) is gone with the old typeface — per the plan, density/size/surface already carried that contrast, so nothing was added to replace it. Scores 8: one real behavioural fix landed here too — a CSS `transition: background-color/color` (present on interactive elements site-wide, e.g. any `Button`) can still be interpolating when a test flips `colorScheme` via `emulateMedia` and immediately samples computed styles; `e2e/helpers.ts` now exports a reusable `settled()` wait (extracted from `shot()`) and the two-step setup screen's axe check uses it before scanning, so a mid-transition frame can't be mistaken for the rested state.
- **Accessibility.**
  - axe (WCAG 2.2 A/AA/2.1 AA/2.2 AA) → **0 violations** across every screen in the suite, light and dark: login/tokens, two-step setup, end-user home/search/article/request, agent queue/ticket/dashboard, admin users/SLA, the new-ticket form and the add-staff dialog (23/23 Playwright specs, full suite, fresh seed).
  - The dark-mode logo/icon chip exists specifically for a contrast reason: the wordmark's black blade (`#1a1a1a`) is close to invisible against the measured dark `surface` (`#0f1417`), so both `LiverXWordmark` and `LiverXIcon` put the colour mark on a fixed light card in dark mode instead — checked by eye in a live dark-mode screenshot, not assumed.
  - Contrast of the fully-filled buttons was reverified — the `MuiButton` "every variant, one colour" vitest above also confirms the background is exactly `theme.palette.primary.main` and the text is exactly `.contrastText`, so it inherits the same AA-checked pair as everywhere else, not a fourth untested combination.
- **Theming.** Every brand value change happened in exactly the two places the design plan promises: the seed (`theme/scheme.ts`) and the logo files (`assets/brand/`); no component reaches for a raw hex. `docs/design-plan.md` §1/§2/§3 and `README.md`'s design-direction section were both updated in the same diff, so the docs and the running app agree.

## Verification

- Backend: unaffected by this phase (no `backend/` files changed); 171 tests still pass, `ruff` clean.
- Frontend: `npm run typecheck`, `npm run build` clean; `npx vitest run` 27/27 (one new: the Button-variant colour-pair test).
- Playwright: full suite, 23/23, against a freshly rebuilt stack (`docker compose down -v && up -d --build`) — 0 axe violations anywhere. Two flakes surfaced and were root-caused rather than retried away:
  1. A pagination-order false negative in `phase8-agent.spec.ts` (a new normal-priority ticket sorted past page 1 of an SLA-ordered queue after ~4 hours of accumulated e2e fixture data across earlier phases) — fixed by rebuilding the stack fresh, not a code change.
  2. The mid-transition axe false positive described under Motion above — fixed with `settled()`.
- Screenshots: every existing per-phase screenshot (`docs/screenshots/phase-{6,7,8,9,10,11,12,14}/*`) was recaptured against the new brand by the same full-suite run, so they show the shipped LiverX look, not the Spruce/Google-Sans-Flex era — spot-checked (login light/dark, dashboard light/dark, admin users, end-user home) directly, not just assumed from green tests.

## Warnings (non-blocking)

- **Elevation (8) / Layout (8) / Navigation (8):** unchanged carry-overs from Phase 9–14's own scores in these categories; this phase didn't touch them.
- **Components (9), not 10:** the Cancel/Reset dialog look-alike above is a known, accepted cost of the one-button-colour rule, not a residual defect — the plan explicitly prices it in.
