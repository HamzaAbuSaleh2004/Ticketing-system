# MD3 Compliance Audit Report: Phase 7 (end-user portal)

- **Target:** end-user screens at `http://localhost:5173`: home (search, KB answer panel, no-answer state, "Your requests"), new request, request view (new / triaged / pending / resolved / closed), help article, and the sign-in/register screens they share a style with. Source: `frontend/src/portals/enduser/*`, `frontend/src/theme/*`.
- **Method:** source review, plus computed styles, screenshots and automated checks against the running Compose stack.
- **Date:** 2026-09-24
- **Overall score: 85/100.** Every category is ≥ 7, so the gate passes.

## Scores by category

| Category | Score | Status |
|---|---|---|
| Color tokens | 9/10 | pass |
| Typography | 8/10 | pass |
| Shape | 8/10 | pass |
| Elevation | 9/10 | pass |
| Components | 8/10 | pass |
| Layout | 8/10 | pass |
| Navigation | 8/10 | pass |
| Motion | 8/10 | pass |
| Accessibility | 9/10 | pass |
| Theming | 10/10 | pass |

## Evidence

- **Color tokens.**
  - `grep -rnE "#[0-9a-fA-F]{3,8}"` over `src/` finds no hex outside `src/theme/` and tests, and there are no `rgb()`/`rgba()` literals.
  - Every surface and text colour is a `var(--md-sys-color-*)` via `sys()`, in tonal pairs:
    - `primaryContainer`/`onPrimaryContainer` for the answer panel
    - `tertiaryContainer`/`onTertiaryContainer` for "Waiting on you"
    - `secondaryContainer`/`onSecondaryContainer` for the tonal "New request"
    - `surfaceContainer*`/`onSurface(Variant)` elsewhere
    - dividers use `outlineVariant`, and field outlines use `outline`
  - State layers and the answer panel's chip borders use `color-mix()` of the paired `on-` role, which is still token-derived.
- **Typography.**
  - Headlines use the display/headline roles: `headlineLarge` "How can we help?", `headlineMedium` for the ticket subject. They're Google Sans Flex with `'ROND' 60`, verified via computed `font-family`.
  - Body, labels and titles are Roboto Flex. The ticket ref (`TCK-00042`) and times use tabular figures. There are no uppercase labels anywhere; buttons and chips have `text-transform: none`.
- **Shape.** All 24 `borderRadius` uses in `src/` are `var(--md-sys-shape-corner-*)`, with no magic numbers:
  - pill (`full`) for buttons, chips and the search bar
  - `extra-large` (28) for the reply box, no-answer panel and auth form
  - `extra-large-increased` (32) for the signature answer panel
  - `large` (16) for messages and list-row hover
- **Elevation.** `theme.shadows` is all `none`, asserted in `scheme.test.ts` and on the computed button `box-shadow`. Depth is tonal: `surface` page, `surfaceContainerLow` for panels, messages and the reply box, `surfaceContainerHigh` for the search bar.
- **Components.**
  - M3 search bar: full shape, 56dp, leading icon and trailing clear action, `role="search"` with `<input type="search">`.
  - Filled, tonal, outlined and text buttons. Assist-style info chips and a status chip.
  - A list, not cards, for "Your requests".
  - An inverse-surface snackbar, and outlined text fields with a `small` shape.
- **Layout.** A single column, left-aligned and capped at 880px (within M3's 840–1040 guidance for large windows). The 360px captures (`home-answer-360`, `home-with-requests-360`, `request-pending-360`, `request-pending-dark-360`) have no horizontal overflow. The list row reflows from 3 columns to subject/time plus a status row under 600px.
- **Navigation.** A top app bar with the wordmark linking home, plus account and appearance actions. Every sub-page has a labelled back action ("Your requests", "Back"), and URLs are real routes (`/?q=`, `/requests/:id`, `/help/:slug`), so browser back and deep links work. The search query lives in the URL.
- **Motion.** Only the answer panel's arrival animates, using `--md-sys-motion-duration-medium4` and `-easing-emphasized-decelerate`. There's no per-section entrance. State-layer transitions use the `short4`/`standard` tokens. `prefers-reduced-motion` disables animations globally in `CssBaseline` and on the panel.
- **Accessibility.**
  - `@axe-core/playwright` (WCAG 2.0/2.1/2.2 A+AA) → **0 violations** on 10 scans: home, answer, new request, article and request, each in light and dark (`e2e/phase7-a11y.spec.ts`). One colour-contrast failure (the panel footer at an 85% colour mix) was found and fixed during the audit.
  - Touch targets: buttons and source chips are 40dp visually with a 48dp hit area via `::after`. The search input fills the 56dp bar. Icon buttons are 48×48.
  - Triage progress and chip changes are announced (`role="status"`, `aria-live="polite"`). The KB answer is a labelled `region`, sources are an ordered list, and each inline marker has a label like "Source 1: Resetting your password".
- **Theming.** The seed `#1E6A5E` generates the scheme at runtime through `SchemeContent`. There's system/light/dark plus standard/medium/high contrast, persisted and switchable from the Appearance menu. The dark captures are generated, not inverted.

## Warnings (non-blocking)

- **Shape (8):** chips use `full` corners per PLAN.md §0 ("pill buttons/chips stay"), where the M3 default for chips is `small` (8dp). This is a deliberate, documented deviation.
- **Typography (8):** the answer text is set at 18px on ≥ 600px (`body-large` size overridden) for the signature panel. That's a size tweak outside the type scale, so I'm taking a point off.
- **Components (8):** the tonal button is `Button` + `sx` with `secondaryContainer` rather than a dedicated variant. It behaves correctly but is repeated per use. Worth adding a `tonal` variant to the theme in Phase 8 when the console needs more of them.
- **Accessibility / colour note:** the generated `onSecondaryContainer` on `secondaryContainer` is ≈4.5:1. It passes AA (axe confirms), but it's the weakest pair. It's left as generated; users can switch to medium/high contrast.
- **Inline citation markers** are 20dp. That's allowed under WCAG 2.5.8's inline-target exception, and each one duplicates a 48dp-target source chip.

## Recommended fixes (priority order)

1. Add a `tonal` Button variant to the MUI theme and use it in both portals (Phase 8).
2. Consider an M3 `title-large` role for the answer text instead of the 18px override.
