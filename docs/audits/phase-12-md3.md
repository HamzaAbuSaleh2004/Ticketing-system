# MD3 Compliance Audit Report: Phase 12 (organisation, requester, action items)

- **Target:** the agent queue's new Organisation/Opened by/Waiting on columns and Organisation filter chip; the ticket workspace header (organisation + "Opened by") and side panel's Organisation select + "What's needed" section; the customer request page's organisation line and "What's needed" block; the dashboard's third chart ("Open tickets by organisation"); the admin Organisations tab and the Users tab's Organisation column. Source: `frontend/src/portals/agent/{QueueTable,QueueToolbar,TicketSidePanel,ActionItemsSection,AgentTicketPage}.tsx`, `frontend/src/portals/agent/dashboard/{DashboardPage,charts}.tsx`, `frontend/src/portals/enduser/{RequestPage,WhatsNeeded,RequestList}.tsx`, `frontend/src/portals/admin/AdminPage.tsx`, `frontend/src/components/TicketChips.tsx`.
- **Method:** source review (token usage, shape, structure) plus the screenshots in `docs/screenshots/phase-12/` (queue and workspace at 1280/1600, customer request at 360/1280, admin organisations at 1280) and the axe WCAG 2.2 AA scans built into `e2e/phase12-organizations.spec.ts` (queue, workspace, customer request, admin organisations - 0 violations on all four, plus the full pre-existing Playwright suite re-run clean).
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
| Navigation | 8/10 | pass |
| Motion | 8/10 | pass |
| Accessibility | 9/10 | pass |
| Theming | 9/10 | pass |

## Evidence

- **Color tokens.** `grep`ing every new/changed file for raw hex or `rgba(` finds none outside `theme/`. The new `OrganizationKindChip` reuses `Pill`'s existing outlined-neutral tone (`onSurfaceVariant` on transparent, `outlineVariant` border) rather than inventing a new colour for a third chip kind. Done action items use `onSurfaceVariant` (de-emphasis, not colour-only: paired with strikethrough text and "Done, <time>"). The dashboard's third chart reuses the exact `primary`-on-both-surfaces mark colour validated in Phase 9; no new colour was introduced for it.
- **Typography.** Organisation names and "Opened by" use `bodyMedium`/`bodySmall` consistent with the existing header block; the "What's needed" heading is `titleSmall` (agent, matching the side panel's other section headings) and `titleMedium` (customer, matching the KB/reply-box panel headings on that portal). No new typeface, weight, or ad hoc `fontSize` introduced. Ticket IDs remain the only tabular-figure use; item counts in "Waiting on" and the dashboard bar labels are short enough that not forcing tabular figures there doesn't misalign anything.
- **Shape.** Every new radius is a `--md-sys-shape-corner-*` token: `extra-large` for the customer's "What's needed" panel (matching the reply box's own panel radius on that page), `full` for the new organisation-kind chip (via the shared `Pill`), `small` for the reused dashboard `ChartCard`. No magic-number `borderRadius` anywhere in the diff.
- **Elevation.** No new shadows. The agent's "What's needed" section sits directly in the side panel's flat `surfaceContainerLow`, and the customer's sits on its own `surfaceContainerLow` panel identical in treatment to the existing reply box - consistent with the portal's no-shadow, tonal-surface language.
- **Components.**
  - The Organisation select in the side panel reuses the exact `TextField select` + `renderValue` + grouped `MenuItem`/`ListItemText` pattern already used for Assignee and Category, rather than introducing a new picker pattern.
  - The Organisation filter chip is the existing `FilterChip` component, unchanged, just given a fifth set of options - proving that component already generalised past the four filters it shipped with in Phase 8.
  - "What's needed" uses a plain `Checkbox` + text + remove `IconButton`, the simplest correct M3 mapping for a checklist row; there's no bespoke checkbox-lookalike control.
  - The admin Organisations tab mirrors Categories' add-row + table pattern, adding a per-row *editable* name field with its own Save button (Categories doesn't support rename yet) - a deliberate, minimal deviation the brief asked for, not a new pattern invented for its own sake.
- **Layout.** The queue table's two new columns push its `minWidth` from 1028px to 1318px; below that the table already scrolled horizontally (Phase 12's own instruction), so this doesn't regress narrower windows, it just moves the scroll threshold. The workspace's Organisation select and "What's needed" section sit in the existing single-column side panel, so no new breakpoint logic was needed. The customer's "What's needed" block reads as one more full-width panel in the existing single-column, comfortable-density request page.
- **Navigation.** The Organisation filter round-trips through the URL exactly like the other four filter chips (`?organization=<id>|none`), so a filtered queue view is shareable and survives a reload, matching Phase 8's own rule. The admin Organisations tab lives at `?tab=organizations`, consistent with the other four tabs.
- **Motion.** No new animation was added anywhere in this phase - action items appear and disappear instantly on mutation success, which is correct: these are frequent, low-ceremony edits (ticking a box, adding a line), not the portal's one signature moment. Scored 8 rather than higher only because the existing dashboard refetch-dimming (7 in Phase 9's audit) still applies to the third chart, and continues to be the only motion instance moved by this phase.
- **Accessibility.**
  - axe WCAG 2.2 AA: **0 violations** across all four newly-scanned screens (queue with the organisation column, the workspace with What's needed open, the customer request page with What's needed, and the admin Organisations tab), per `e2e/phase12-organizations.spec.ts`.
  - Two identically-worded "Add an item" fields (one per side) were caught before commit and given distinct accessible names (`Add an item from the customer` / `Add an item from LiverX`) on both the text field and its Add button, rather than leaving two same-named controls on one screen.
  - The admin Organisations tab's per-row Save button is likewise given a per-row accessible name (`Save name for {org}`) rather than N identical "Save" buttons, since a table with many organisations would otherwise be unusable by name for assistive tech / voice control.
  - "Waiting on" in the queue is text ("Customer 2", "LiverX 1", "Nothing pending"), never colour alone, per the brief's own rule for that column.
  - The read-only "From LiverX" checkboxes on the customer's side use the native `disabled` state (not just visual dimming with a live/interactive control left clickable), so assistive tech correctly reports them as non-interactive.
- **Theming.** Nothing in this phase reads `prefers-color-scheme` directly or hardcodes a light/dark pair; every surface came from the existing `--md-sys-color-*` set. Not re-verified by a fresh dark-mode screenshot this phase (none of the Phase 12 Verify captures were requested in dark mode), but nothing in the diff is capable of being theme-unaware given the token-only styling above.

## Warnings (non-blocking)

- **Theming (9, not 10):** no dark-mode screenshot was captured specifically for the new organisation/action-item UI this phase (Phase 12's Verify list only calls for light-mode captures at the stated sizes). Nothing in the source suggests a dark-mode issue, but it's unverified by a screenshot the way Phases 6-11's dark captures were.
- **Motion (8):** unchanged from Phase 9's assessment of the dashboard; the new third chart doesn't add anything beyond the existing refetch-dimming.
