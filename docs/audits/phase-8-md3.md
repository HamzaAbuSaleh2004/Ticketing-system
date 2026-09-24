# MD3 Compliance Audit Report: Phase 8 (agent console)

- **Target:** the agent console at `http://localhost:5173/agent` and `/agent/tickets/:id`: nav rail, queue toolbar and filter chips, the dense queue table, the three-pane ticket workspace (queue pane, thread + composer, properties/AI/history side panel), and the SLA indicator. Source: `frontend/src/portals/agent/*`, `frontend/src/components/{SlaIndicator,TicketChips}.tsx`, `frontend/src/theme/*`.
- **Method:** source review, plus computed styles, screenshots and automated checks against the running Compose stack.
- **Date:** 2026-09-24
- **Overall score: 84/100.** Every category is ≥ 7, so the gate passes.

## Scores by category

| Category | Score | Status |
|---|---|---|
| Color tokens | 9/10 | pass |
| Typography | 8/10 | pass |
| Shape | 9/10 | pass |
| Elevation | 9/10 | pass |
| Components | 8/10 | pass |
| Layout | 8/10 | pass |
| Navigation | 8/10 | pass |
| Motion | 7/10 | pass |
| Accessibility | 8/10 | pass |
| Theming | 10/10 | pass |

## Evidence

- **Color tokens.**
  - No hex, `rgb()` or `rgba()` outside `src/theme/`.
  - Roles are paired throughout:
    - chips on `secondaryContainer`, `errorContainer` (urgent) and `tertiaryContainer` (high), each with its `on-` role
    - selected rows on `surfaceContainerHighest` with a `primary` bar
    - the SLA ring in `primary` / `tertiary` / `error` / `outline`
  - Internal notes use `color-mix()` of `tertiary` over `surfaceContainerLowest`, with `onSurface` text and a `tertiary` bar and label. That's token-derived, and axe-verified for contrast.
- **Typography.** The console is Roboto Flex at compact density: `body-medium` 14px body, `label-medium` column headers in sentence case, `title-large` page and ticket titles. IDs, countdowns and times use tabular figures (`.tabular`). Google Sans Flex appears only in display/headline roles, which the console barely uses, with ROND 0 set through the compact theme.
- **Shape.** Every radius is a shape token:
  - `small` (8) for the panes, messages, composer and draft box, per the plan's "table and panes use small (8px) corners"
  - `full` for chips, buttons, the search field and toggle groups
  - `large` for the rail indicator container
- **Elevation.** No drop shadows. The workspace is layered tonally:
  - `surfaceContainer` rail
  - `surface` queue pane
  - `surfaceContainerHigh` thread pane with `surfaceContainerLowest` messages
  - `surfaceContainerLow` side panel
  - `surfaceContainerHighest` selected row

  The only `boxShadow` uses in `src/` are `inset` 1–3px selection and emphasis bars, not elevation.
- **Components.**
  - M3 navigation rail, with a bottom navigation bar under 600px.
  - Filter chips with menus: an outlined chip by default; a `secondaryContainer` chip with a check when set.
  - Dense data table with a sticky header.
  - Segmented Reply / Internal note toggle.
  - Outlined select fields, with `renderValue` so they show the value only.
  - The new theme-level `tonal` Button variant ("Use draft"; also now used for "New request" in the end-user portal, which fixes the Phase 7 recommendation).
  - Accordion for history, snackbar for errors, linear progress for background refresh.
- **Layout.**
  - The queue is full-bleed. The workspace uses window size classes: three panes at ≥ 1200 (300 / flexible / 360), two at 840–1199 (thread + side, with a "Queue" back action), and one column below 840.
  - Panes scroll independently at full height. The table keeps a `minWidth` and scrolls horizontally rather than crushing columns.
  - Screenshots: `queue-1280`, `queue-1600`, `ticket-pending-1280`, `ticket-pending-1600`, and dark `queue-dark-1600`, `ticket-dark-1600`.
- **Navigation.** The rail shows Queue and Dashboard, plus Admin for admins, with `aria-current` on the active item. Filter state lives in the URL (`?status=…&priority=…&assignee=…&category=…&q=…&page=…`) and carries into the workspace links, so the queue pane and back action keep the same view. `j`/`k` move the selection and `Enter` opens it, in both the table and the queue pane, with a visible hint in the footer. Real links sit under every subject.
- **Motion.** State-layer and background transitions use `--md-sys-motion-duration-short4` / `-easing-standard`. There's no decorative motion; the only continuous change is the SLA countdown, which ticks every 15s through one shared timer. `prefers-reduced-motion` is honoured globally. This scores 7 because nothing here uses emphasized transitions yet. For example, the pane change on opening a ticket is an instant route swap.
- **Accessibility.**
  - `@axe-core/playwright` (WCAG 2.0–2.2 A+AA) → **0 violations** on the queue and on the ticket workspace (with the internal-note composer open), in light and dark (`e2e/phase8-a11y.spec.ts`).
  - Every state carries text as well as colour: SLA "At risk", "Breached" and "Paused" plus a dashed ring for paused; "Internal note" with a lock icon plus a bar; "Escalated" in text; a check plus a label on set filter chips.
  - The SLA indicator has `role="img"` with a sentence label ("First reply due in 12m, at risk") and a tooltip.
  - Touch targets: chips, buttons and icon buttons get 48dp hit areas via `::after`.
- **Theming.** The same runtime `SchemeContent` scheme drives both portals. Density comes from the theme (compact console, comfortable portal), so one set of components carries both personalities. Light and dark were both captured and scanned.

## Warnings (non-blocking)

- **Accessibility (8):** queue rows are 36px, as the plan requires for density. That's below 48dp, but each row also contains a full-width subject link, and keyboard `j`/`k`/`Enter` covers pointer-free use. The table is `minWidth: 980`, so it scrolls horizontally under ~1060px windows.
- **Components (8):** status, assignee, priority and category are MUI outlined selects rather than M3 exposed dropdown menus. They're visually close but not token-identical (label notch).
- **Colour note:** `tertiaryContainer` from this seed is a dark violet in light mode. That's fine for small chips (high priority), but it was too heavy for large note blocks, so notes use the tint described above.

## Density contrast with the end-user portal (the brief's anti-slop requirement)

| | End-user portal (Phase 7) | Agent console (Phase 8) |
|---|---|---|
| Body size | 16px `body-large` | 14px `body-medium` |
| Row height | ~72px list rows | 36px table rows |
| Width | 880px left-aligned column | full-bleed, 3 panes |
| Corners | 28–32px containers, pill buttons | 8px panes and messages, pill buttons and chips |
| Surfaces | mostly flat `surface`, one saturated `primary-container` moment | layered `surfaceContainer*` ladder |
| Display type | Google Sans Flex ROND 60 | ROND 0, mostly Roboto Flex |
| Signature | the grounded KB answer panel | the SLA ring and countdown on every row |

## Recommended fixes (priority order)

1. An emphasized shared-axis transition between the queue and the workspace would raise Motion; it's deferred as polish.
2. Consider M3 exposed dropdown menus for the side-panel fields.
