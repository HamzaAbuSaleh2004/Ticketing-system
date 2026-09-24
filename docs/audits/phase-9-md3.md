# MD3 Compliance Audit Report: Phase 9 (analytics dashboard + admin)

- **Target:** `/agent/dashboard` (range filter, 4 stat tiles, two charts with table views) and `/admin` (Users, Categories, SLA policies and Change log tabs). Source: `frontend/src/portals/agent/dashboard/*`, `frontend/src/portals/admin/AdminPage.tsx`.
- **Method:** source review, plus screenshots, computed checks and automated checks against the running Compose stack. The `dataviz` skill was loaded before any chart code; its checks are recorded below.
- **Date:** 2026-09-24
- **Overall score: 84/100.** Every category is ≥ 7, so the gate passes.

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

## Evidence

- **Color tokens.**
  - No hex or `rgb()` in the dashboard or admin source.
  - Chart marks use `var(--md-sys-color-primary)`. Gridlines and the baseline use `outline-variant` as solid 1px hairlines. The crosshair uses `outline`. Axis text uses `on-surface-variant` and values use `on-surface`, so text wears text tokens, never the series colour.
  - Tooltips use `inverse-surface`/`inverse-on-surface`. The SLA note uses `secondary-container`/`on-secondary-container`.
  - **dataviz validator** (`scripts/validate_palette.js`), run on the chart colour against both chart surfaces in both modes:
    - `#005147` on `#f7faf8` and `#f2f4f2`: contrast PASS (≥ 3:1)
    - `#8dd4c5` on `#101413` and `#191c1b`: contrast PASS
    - The lightness-band and chroma checks report out of band. They're defined for multi-hue categorical identity, which these single-series charts don't use: one series, one hue, no legend.
    - The seed `#1E6A5E` itself was rejected for dark mode (2.9:1), which is why the chart uses the `primary` role in each mode.
- **Typography.** The stat-tile values follow dataviz: the console's sans (Roboto Flex, weight 600) at display-small size with proportional figures, not the display face and not tabular. Axis ticks and table numbers use tabular figures. Labels are sentence case with no trailing colons.
- **Shape.** Every radius is a token: `small` tiles and cards (console density), `extra-small` tooltips, `full` segmented buttons. Chart columns and bars follow the dataviz mark spec: ≤ 24px, a 4px rounded data end, square at the baseline.
- **Elevation.** No shadows. Tiles and cards sit on `surface-container-low` over `surface`. The tooltip is the only raised element, and it's tonal (`inverse-surface`).
- **Components.**
  - M3 segmented buttons for the date range (one filter row, above everything it scopes).
  - Primary tabs for admin sections.
  - Outlined selects and number fields, a switch for active/inactive categories, and a text button for the table toggle.
  - The `tonal` button for Save, a snackbar for confirmations, and a dense data table.
- **Layout.** The KPI row is an `auto-fit` grid (4 across at ≥ 1280, one column at 390). Charts are 2:1 at ≥ 1200 and stacked below that. Admin content is capped at 640–760px per section. Captures: `dashboard-1600`, `dashboard-hover-1600`, `dashboard-1280`, `dashboard-dark-1280`, `dashboard-dark-390`, `admin-{users,sla,categories,changes}-1280`.
- **Navigation.** The dashboard range (`?days=`) and the admin tab (`?tab=`) live in the URL. The rail shows the active destination, and Admin appears only for admins (it's also enforced server-side with 403s).
- **Motion.** The only transition is refetch dimming (the previous render holds at 60% opacity), using the `short4`/`standard` tokens, per dataviz's "refetch keeps the frame". There are no entrance animations. It scores 7 for the same reason as Phase 8: there are no emphasized transitions.
- **Accessibility.**
  - axe WCAG 2.2 AA → **0 violations** on the dashboard (light and dark, with the table view open) and on admin Users and SLA (`e2e/phase9-dashboard-admin.spec.ts`). One violation was found and fixed: the scrollable table view wasn't keyboard-focusable, so it's now `tabIndex=0` with a labelled region.
  - The column chart is focusable, with an `aria-label` explaining arrow-key reading. Arrow keys move a value-first tooltip, the same as hover. Every chart has a "Show as table" twin, so tooltips enhance and never gate. The bar chart's `aria-label` lists every value, and values are also printed at the bar tips.
  - Hit targets: the whole row for backlog bars, and the whole column slot (plus crosshair) for daily columns.

## dataviz checklist

| Check | Result |
|---|---|
| Form picked first | KPI tiles for single headline numbers; a column chart for change over time; horizontal bars for magnitude by an ordered status list |
| Color by job | single series → one colour (`primary`); no categorical palette needed |
| Validator | run in both modes; contrast passes; the band/chroma checks are categorical-only (see above) |
| Mark specs | ≤ 24px bars, 4px rounded data end, 2px gap between columns, solid hairline grid, no border strokes around marks |
| Hover layer | crosshair + tooltip on columns; hovered bar lifts (others dim to 55%) |
| Legend | none, correctly: each chart has one series, and the title names it |
| Labels | selective: values at the tips of the 5 backlog bars; daily columns get their values from the axis, tooltip and table |
| Table view | both charts |
| Dark mode | the role's dark tone, validated against the dark surface |
| One filter row above | yes; all tiles and charts use the same range |
| Rendered and looked at | yes. Fixed: the top y-tick label was clipped (top padding added), and "<1m" hid real sub-minute response times (now seconds) |

## Warnings (non-blocking)

- **Motion (7):** no emphasized transitions.
- **Components (8):** MUI outlined select and number fields stand in for M3 exposed dropdowns and number steppers.
- The volume chart in the dev stack's captures has one tall column, because every dev ticket was created today. Phase 10's demo seed spreads tickets over 30 days.
