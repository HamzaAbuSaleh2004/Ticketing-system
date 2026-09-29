# MD3 Compliance Audit Report: Phase 11 (mandatory TOTP 2FA, AI removal)

- **Target:** the two-step sign-in flow (`Set up two-step verification`, `Enter your code`, `Save your recovery codes`), the end-user KB search results panel (replacing the AI grounded-answer panel), the "Request received" state, and the admin "Reset two-step verification" dialog. Source: `frontend/src/auth/TwoStep.tsx`, `frontend/src/portals/enduser/KbResults.tsx`, `frontend/src/portals/enduser/RequestPage.tsx`, `frontend/src/portals/admin/AdminPage.tsx`.
- **Method:** source review (token usage, shape, structure) plus the screenshots in `docs/screenshots/phase-11/` (light/dark, 1280/360) and the axe WCAG 2.2 AA results already recorded for this phase (0 violations, including the verify and setup screens, per `e2e/phase11-*` specs referenced in PLAN.md's Phase 11 evidence).
- **Date:** 2026-09-29
- **Overall score: 85/100.** Every category is ≥ 7, so the gate passes.

## Scores by category

| Category | Score | Status |
|---|---|---|
| Color tokens | 9/10 | pass |
| Typography | 9/10 | pass |
| Shape | 9/10 | pass |
| Elevation | 9/10 | pass |
| Components | 8/10 | pass |
| Layout | 8/10 | pass |
| Navigation | 7/10 | pass |
| Motion | 8/10 | pass |
| Accessibility | 9/10 | pass |
| Theming | 9/10 | pass |

## Evidence

- **Color tokens.** `grep`ing `TwoStep.tsx`, `KbResults.tsx` and the admin dialog for raw hex/`rgba(` finds none outside `theme/`. The QR panel, code field and recovery-code grid sit on `surfaceContainerHighest`; the KB results panel is the phase's one saturated moment, on `primaryContainer`/`onPrimaryContainer`, with dividers and hover states mixed from `onPrimaryContainer` at low opacities (`color-mix`) rather than a second hardcoded colour. The wrong-code alert uses `errorContainer`/`onErrorContainer`, correctly paired.
- **Typography.** Titles (`titleSmall`/`titleMedium`) for the enrolment steps and result headings, `bodyMedium`/`bodyLarge` for copy, all via the `typescale()` helper — no ad hoc `fontSize`. The setup key and recovery codes use `fontVariantNumeric: tabular-nums`, matching the brief's rule for data that mustn't jitter; the 6-digit code field also forces `tabular-nums` with letter-spacing for scannability.
- **Shape.** Every radius is a `--md-sys-shape-corner-*` token: `large` for the QR box and recovery-code grid, `extra-large`/`extra-large-increased` for the results/empty-state panels (a deliberately bigger radius than the Phase 7 answer panel had, appropriate since this panel is now plain list content, not a hero), `large` again for each result row's hover target. No magic-number `borderRadius`.
- **Elevation.** No box-shadows in any of the three files. The admin dialog is MUI's `Dialog`, and the theme's global `shadows: []→none` (Phase 6) means its Paper has none either; separation comes from the scrim plus the dialog surface being `surface`/`surfaceContainer`-toned against the dimmed backdrop, visible in `admin-reset-2fa-1280.png`.
- **Components.**
  - Enrolment/verify reuse the established `AuthLayout` (left title+intro, right tonal panel) unchanged from Phases 6–7, which is the right call — this is still an auth-adjacent flow, not a new surface needing new patterns.
  - `CodeField` is one outlined `TextField` shared between the 6-digit and recovery-code cases (`inputMode: numeric` vs a plain text field), avoiding a second bespoke input.
  - The KB panel replaces cards with a divided list (`component="li"` + `borderTop`), matching the brief's explicit "list not cards" rule for the end-user portal, and reuses the Phase 7 "Send a request" CTA pattern.
  - The admin dialog is a standard MUI `Dialog`/`DialogActions` with a plain-text Cancel and a contained Reset — correct for this phase; Phase 14 is where the brief mandates collapsing all buttons to one filled style, so scoring this down now would be premature.
- **Layout.** `AuthLayout` reflows to a single centred column at 360 (`setup-360.png`, `setup-dark-360.png`) with the QR box unchanged in size (196×196, still comfortably tappable) and the ordered list stacking cleanly. The KB panel's divider list and CTA row wrap correctly at 360 (`home-results-360.png`). Docked at 7/10 rather than higher only because the recovery-code grid stays 2 columns at 360 rather than collapsing to 1 — codes stay legible (`5wpwj-pvatg` doesn't wrap) so it's not a fail, but a single column would give more breathing room at the narrowest width.
- **Navigation.** No new nav surface this phase — the two-step flow is pre-navigation (outside any shell) and the admin dialog sits inside the existing rail/Admin tab structure. Scored 7 (steady, not improved) because the enrolment flow still has no visible step indicator beyond the `<ol>` markers; a user who errors out and returns via "Sign in again" loses any sense of "step 1 of 2" beyond re-reading the numbered list. Non-blocking: the flow is only two screens and the copy already orients the user.
- **Motion.** The KB results panel keeps Phase 7's `reveal` keyframe (opacity+scale) on arrival, gated by `prefers-reduced-motion`, using M3 duration/easing tokens (`--md-sys-motion-duration-medium4`, `emphasized-decelerate`). The two-step screens intentionally have no entrance animation, which is correct per the banned list (no fade-and-slide-up on every section) — this is settings/security flow, not a moment to spend the portal's one signature animation on.
- **Accessibility.**
  - Per PLAN.md's Phase 11 evidence, axe WCAG 2.2 AA found 0 violations across the Playwright suite, "including the verify and setup screens."
  - The QR image has `alt="QR code for setting up two-step verification"`; the manual key has `aria-label="Setup key"` and `userSelect: all` so it can be selected in one action instead of hunting for word boundaries.
  - The recovery-code list is a labelled `<ul aria-label="Recovery codes">`, read as a set rather than 10 disconnected list items.
  - The KB "no results"/error panels are `role="status"`, and the loading skeleton is `aria-busy` + `aria-label="Searching help articles"`, so a screen-reader user gets the same three states a sighted user does.
  - Wrong-code and expired-token errors render through the shared `Alert` (`errorContainer`/`onErrorContainer`, ≥ 4.5:1 per the Phase 6 contrast test suite), and the expired case offers a real "Sign in again" action rather than a dead end.
- **Theming.** Every screen renders correctly in both light and dark (`setup-dark-360.png`, `home-results-dark-1280.png`) purely from the existing `--md-sys-color-*` swap; no component in this phase reads `prefers-color-scheme` or hardcodes a light/dark pair itself.

## Warnings (non-blocking)

- **Layout (8):** the recovery-code grid could collapse to one column below ~400px for more breathing room; two columns is still legible today.
- **Navigation (7):** the enrolment flow has no step-N-of-2 indicator beyond the `<ol>` numbering; fine at two screens, worth revisiting if enrolment ever grows a step.
- The dark-mode "How can we help?" heading shows faint colour fringing at letter edges in `home-results-dark-1280.png`; this reads as a PNG/subpixel-rendering capture artifact (the light and 360 dark captures don't show it), not a token or contrast defect — worth a re-capture if it recurs in a future audit, not a fix to `theme/`.
