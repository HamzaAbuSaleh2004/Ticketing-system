# MD3 compliance audit report

- **Target:** `docs/mockups/index.html` (with `m3-tokens.css` and `mockup.css`). Three screens: end-user home, end-user resolved request, agent console.
- **Date:** 2026-09-24
- **Method:** the `material-3` skill's audit procedure.
  - **Static:** read the source and grep it. The checks were run with `node audit-checks.mjs` in the drafts folder; the script is included next to this report.
  - **Live:** Chromium 149 via Playwright, at 360, 1024, 1280 and 1600px, in light and dark. Screenshots are in [screenshots/](screenshots/).
- **Overall score: 84/100**

## Scores by category

| Category | Score | Status |
|---|---|---|
| Color tokens | 9/10 | pass |
| Typography | 9/10 | pass |
| Shape | 9/10 | pass |
| Elevation | 9/10 | pass |
| Components | 8/10 | pass |
| Layout | 8/10 | pass |
| Navigation | 8/10 | pass |
| Motion | 7/10 | pass |
| Accessibility | 8/10 | pass |
| Theming | 9/10 | pass |

Every category is at 7 or above.

## Evidence (measured output, not estimates)

```
== Static checks (mockup.css + index.html, comments stripped) ==
hex colours outside m3-tokens.css : 0
rgb()/hsl() literals              : 0
raw border-radius (not a token)   : 0
box-shadow declarations           : 0
text-transform: uppercase         : 0
gradients                         : 0
font-family not via tokens        : font-family: 'Material Symbols Rounded'   (icon font only)
middle dots in UI text            : 0
" → " arrows in UI text           : 0
```

- **Contrast:** I checked 26 role pairs the mockup uses, in both modes: 52 checks, including the attention alias. Text pairs need 4.5:1 and non-text pairs 3:1. **0 failures.**
  - The tightest pairs are on-secondary-container on secondary-container (4.60 light, 4.54 dark), on-primary-container on the seed FAB (4.54), and the dark attention alias (4.56).
  - `surface-container-highest` against `surface` is only 1.23:1 in light, which is why the selected queue row also carries a 3px `primary` start bar (7.16:1).
- **Live DOM:**
  - 0 controls without an accessible name, on all 5 screen and width combinations.
  - 0 elements with a computed `box-shadow`, and 0 with computed `uppercase`.
  - Fonts in use: Google Sans Flex (end user only), Roboto Flex and Material Symbols Rounded. All report `document.fonts.check` = true where they're used.
  - The first Tab stop gets a 3px solid focus outline.
  - `j` moves the queue selection from TCK-01040 to TCK-01034.
  - With `prefers-reduced-motion: reduce`, the state-layer transition is 1ms.
- **Overflow:** there's no horizontal page scroll in any of the 16 screenshots, and no console errors.

## Critical issues (0–3)

None.

## Warnings (4–6)

None. The items below are the reasons categories scored 7–9 rather than 10.

## Passing, with notes

- **Color tokens (9).**
  - Every color is a `--md-sys-color-*` role, generated from one seed by `SchemeContent`, and hex appears only in `m3-tokens.css`.
  - Tonal pairs are respected (`on-X` on `X`). There's one component-level alias, `--attention-container`, which resolves to legal pairs: `tertiary-fixed` in light, `tertiary-container` in dark.
  - −1: the table-row hover uses `color-mix()` of `on-surface` into `surface`, driven by the state-layer opacity token. It's correct, but it's a computed color rather than a pure role.
- **Typography (9).**
  - All text uses `--md-sys-typescale-*`: Google Sans Flex for display/headline (ROND 60 on the end-user portal) and Roboto Flex for title/body/label. The agent console uses no display or headline roles.
  - IDs, countdowns and times use tabular figures, with no monospace.
  - −1: compact end-user breakpoints reassign the title role (display-small becomes headline-medium) through the `font` shorthand, so they need to repeat `font-variation-settings` for ROND. It's easy to miss in the React build.
- **Shape (9).**
  - Every radius is `--md-sys-shape-corner-*`: 0 raw values.
  - Buttons, chips, the search bar and citations use `full`. The answer panel uses `extra-large`, the requests list `large`, the AI groups `medium`, agent panes `small`, and selects `extra-small`.
  - −1: chips are pill-shaped by PLAN.md §0's decision, which deviates from M3's `small` chip default.
- **Elevation (9).**
  - The only depth cue is tonal: the rail and shell on `surface-container`, the queue on `surface`, the thread on `-low`, the side panel on `-high`, and the selected row and AI group on `-highest`. There are zero shadows.
  - −1: nothing lifts on hover beyond the state layer, which is fine for a mockup, but the build should raise the FAB one tonal level on hover.
- **Components (8).**
  - These are spec-aligned HTML/CSS versions of: search bar, segmented button, filter and assist chips, extended FAB, filled/tonal/outlined/text buttons, icon buttons, list, navigation rail and bar, and badge.
  - −2:
    - Selects and filter chips are visual only (no menu).
    - The status control uses tonal buttons for the legal next transitions, not an M3 menu. That's intentional (one click, and only legal moves are shown), but the build should keep it a real `role="group"` with the current status announced.
- **Layout (8).**
  - Window size classes:
    - compact (under 600px): one pane, and the list becomes two-line rows
    - medium/expanded (600–1199px): list and detail, with the side panel under the thread
    - large (1200px+): three panes, with a list-only mode when the ticket is closed
  - The end-user column is capped at 880px on large windows.
  - −2:
    - 36px queue rows are below the 48dp touch target. That's a deliberate desktop density; rows are 70px+ at compact.
    - At 1024px the SLA cell ellipsizes "Breached".
- **Navigation (8).**
  - Rail at 840px+ and navigation bar below it; the active destination uses a `secondary-container` indicator pill with a filled icon. There's a back affordance on compact detail and a leading back button in the end-user ticket view.
  - −2: the rail has no FAB or menu (by choice: there's no "create" action for agents), and predictive back isn't applicable on the web.
- **Motion (7).**
  - Uses `--md-sys-motion-easing-*` / `duration-*` tokens.
  - There's one orchestrated moment (the answer resolves from a skeleton with `medium4` and `emphasized-decelerate`) and no load-time entrance animations. State layers use `short2`, and reduced motion is honored.
  - −3: there are no spring physics (not available on web, per the skill), there's no container transform on opening a ticket, and the reduced-motion rule is a blunt global override.
- **Accessibility (8).**
  - All contrast checks pass, every control has an accessible name, and the focus ring is visible.
  - Every SLA state has text and an `aria-label` sentence. Internal notes are marked by tint, a lock icon and the label "Internal note".
  - The queue uses `role="grid"` with `aria-selected`, and j/k/Enter work.
  - −2:
    - Inline citation markers are 20px targets. That's allowed as inline targets under WCAG 2.5.8, and the same links exist as 48px source chips.
    - The grid lacks full arrow-key cell navigation.
- **Theming (9).**
  - The scheme is generated from the seed for light and dark. There's a system/light/dark control (segmented on wide end-user screens, a cycling icon button elsewhere), applied before first paint and persisted.
  - −1: the medium/high contrast levels (0.5 / 1.0) aren't exposed in the mockup. `generate-tokens.mjs` accepts a contrast argument, and the Phase 6 build should expose it as a setting.

## Recommended fixes for the build (priority order)

1. Expose contrast levels 0 / 0.5 / 1.0 as a setting. It's one `SchemeContent` argument.
2. Make the status control, the filter chips and the selects real MUI menus with `aria-expanded`, keeping only legal next transitions from the API's `allowed_transitions`.
3. Give the queue grid full arrow-key navigation, or use `role="listbox"` if cell-level navigation isn't needed.
4. At 840–1199px, shorten the SLA state word, or show it only as the aria-label plus a colored time, so "Breached" doesn't truncate.
5. Add a container-transform (or a shared-axis fade) when a ticket opens on compact.
