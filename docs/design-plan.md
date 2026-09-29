# Design plan: Ticketing Portal (iteration 1)

Written before any component code, following `frontend-design`'s two passes: plan first, then review it against the brief and revise. Precedence is **brief > `material-3` > `frontend-design`**. §0 of [PLAN.md](../PLAN.md) locks the seed, the typefaces and the stack. This document turns them into a buildable system.

## 1. Stated up front (brief: "before generating any screen, state…")

- **Seed colour:** `#00A4D8` (LiverX Bright Cyan Blue, `docs/brand/liverx-brand-guideline.pdf`), expanded at runtime by `@material/material-color-utilities` `SchemeContent` into every M3 role, light and dark, at contrast levels 0 / 0.5 / 1.0. **(Phase 15; was `#1E6A5E` "Spruce" — see §8.7.)**
- **Display and body typeface:** IBM Plex Sans (`'IBM Plex Sans'`, self-hosted via `@fontsource/ibm-plex-sans` weights 400/500/700, OFL), with **Tajawal** after it in the stack for Arabic text. One family carries every role — there's no separate display face. **(Phase 15; was Google Sans Flex + Roboto Flex.)**
- **Tone:** calm, spacious and reassuring for the end-user portal; dense, scannable and efficient for the agent console.

The IBM Plex Sans and Tajawal packages were checked in their shipped weight manifests on 2026-09-29, including family names, available static weights and `font-display: swap`.

## 2. Colour: what the seed actually generates

Measured from `SchemeContent(Hct(#00A4D8), isDark, 0)`, not assumed:

| Role | Light | Dark | Used for |
|---|---|---|---|
| primary | `#006688` | `#75D1FF` | Filled buttons, focus, the KB answer's source chips |
| primary-container | `#00A4D8` (the seed itself) | `#00A4D8` | The KB answer panel ground in the end-user portal; selected nav item |
| secondary-container | `#BDE5FD` | `#234B5F` | Tonal buttons, filter chips (selected), status chips |
| tertiary / container | `#7D469D` / `#BC81DC` | `#E6B4FF` / `#BC81DC` | "Attention": internal notes, SLA at risk |
| error / container | `#BA1A1A` / `#FFDAD6` | `#FFB4AB` / `#93000A` | SLA breached, destructive actions |
| surface → container-highest | `#F5FAFE` → `#DEE3E7` | `#0F1417` → `#303539` | Tonal elevation ladder (no shadows) |
| outline-variant | `#BDC8D0` | `#3E484F` | Dividers and table rules |

Hex values appear only in the generated theme at runtime. Components reference `var(--md-sys-color-*)` or the MUI palette mapped from the same scheme object. The measured light `primary` (`#006688`) sits 0.85° from the brand's Teal Blue `#007BA2` on the hue wheel — well inside the scheme reading as LiverX.

## 3. Type scale (M3 roles → faces)

| Role | Face | Size / line (px) | Weight | Notes |
|---|---|---|---|---|
| display-L/M/S | IBM Plex Sans | 57/64, 45/52, 36/44 | 400 | Only on auth screens and the dashboard's stat figures |
| headline-L/M/S | IBM Plex Sans | 32/40, 28/36, 24/32 | 400 | Page titles in the end-user portal |
| title-L/M/S | IBM Plex Sans | 22/28, 16/24 (500), 14/20 (500) | 400/500 | Pane titles, ticket subjects |
| body-L/M/S | IBM Plex Sans | 16/24, 14/20, 12/16 | 400 | Body text |
| label-L/M/S | IBM Plex Sans | 14/20, 12/16, 11/16 | 500 | Buttons, chips, column headers (sentence case) |

- One face, every role: IBM Plex Sans replaces the former display/body split (Google Sans Flex's variable `ROND` axis, used to give the two portals distinct personalities, is gone with it — the end-user vs. agent contrast is now carried entirely by density, size and surfaces, which already differed).
- IBM Plex Sans ships as static weights (400/500/700), not a variable font, so there's no optical-sizing axis; `font-variant-numeric: tabular-nums` still gives tables and IDs tabular figures.
- `textTransform: 'none'` everywhere. Tracking comes from the M3 tokens and is never widened for labels.

## 4. Shape, elevation, motion, density

- **Shape:** `--md-sys-shape-corner-*` (none 0, xs 4, s 8, m 12, l 16, l-increased 20, xl 28, xl-increased 32, full 9999). Buttons and chips use `full` in both portals. End-user surfaces use `extra-large` (28). Agent panes and the table use `small` (8).
- **Elevation:** MUI `shadows` are all `none`. Depth comes only from the `surface-container-*` ladder.
- **Motion:** M3 easing/duration tokens as CSS vars. The only non-user-triggered motion is the KB answer panel's reveal when an answer arrives, and the SLA ring's countdown. `prefers-reduced-motion` turns both into instant changes.
- **Density:** a React context. `comfortable` (end user): 16px body, 24–32px gaps, 56px inputs. `compact` (agent): 13–14px body, 36px table rows, 40px inputs. Touch targets stay ≥ 48px on interactive controls in both. In compact mode the visual box is smaller, but the hit area is padded out to 48px where it isn't inside a dense table row.

## 5. Layout concepts

**End-user portal.** One calm column: a question comes first, and the portal answers it before you ever file a request.

```
┌──────────────────────────────────────────────────────────────┐
│ Support                                  [theme] [Uma ▾]     │  top app bar (surface)
├──────────────────────────────────────────────────────────────┤
│        How can we help?                                      │  headline-L, left aligned
│        ┌──────────────────────────────────────────────┐      │
│        │ 🔍  Describe your problem                     │      │  M3 search bar (full shape)
│        └──────────────────────────────────────────────┘      │
│        ┌──────────────────────────────────────────────┐      │  KB ANSWER PANEL (signature)
│        │ Go to the sign-in page and select Forgot      │      │  primary-container ground,
│        │ password [1]. The link lasts 30 minutes [1].  │      │  xl-increased corners
│        │ (1) Resetting your password  (2) …            │      │  numbered source chips → article
│        │ Didn't help?  [Submit a request]              │      │
│        └──────────────────────────────────────────────┘      │
│        Your requests                     [New request]       │  title-L + tonal button
│        ─────────────────────────────────────────────────     │
│        Can't log in                   Waiting on you   2h    │  list rows, not cards
│        Charged twice                  We're on it     1d     │
└──────────────────────────────────────────────────────────────┘
         ↑ max-width 880px, left-aligned inside a centred column
```

**Agent console.** A working surface: queue, conversation and decisions side by side, with nothing to scroll past.

```
┌────┬───────────────────────────┬──────────────────────────┬──────────────┐
│ ▣  │ Queue    [status][prio]…  │ TCK-00042  Charged twice │ Status  ▾    │
│ Q  │──────────────────────────│──────────────────────────│ Assignee ▾   │
│ D  │ 00042 Charged twice  ◔2h │ Uma: I was charged twice │ Priority ▾   │
│ A  │ 00041 Locked out     ◕9m │ ▌Internal  Checked Stripe│ [Escalate]   │
│    │ 00040 Export data  Paused│ Agent: Refund issued     │ AI triage    │
│    │ …   (36px rows)          │ [Reply | Internal note]  │ Billing ✓ ✎  │
│    │                          │ ┌──────────────────────┐ │ High    ✓ ✎  │
│    │                          │ └──────────────────────┘ │ [Use draft]  │
└────┴───────────────────────────┴──────────────────────────┴──────────────┘
 rail   surface-container         surface-container-high     container-low
 80px   (selected row: -highest)  full-bleed, 8px pane corners
```

**Auth screens** follow the end-user portal's style, since everyone signs in there. A left-aligned headline, a single form on `surface-container-low` with `extra-large` corners, and the product name. No hero illustration and no centred marketing block.

Alignment: text is left-aligned everywhere. Numbers in tables and tiles are right-aligned with tabular figures.

## 6. Signature elements (spend boldness here, keep the rest quiet)

- **End user: the KB answer panel.** It's the one saturated surface in the portal: `primary-container` (the seed colour) with `on-primary-container` text. Inline `[n]` markers are small `primary`-tinted pills that match numbered source chips, and each chip links to the article.
- **Agent: the SLA ring.** A 20px ring plus a tabular countdown on every queue row. States:
  - on track: primary ring
  - at risk: tertiary ring, labelled "At risk"
  - breached: error ring, labelled "Breached"
  - paused: dashed outline ring, labelled "Paused"
  - none when resolved or closed

  Every state carries text, not just colour.

## 7. Banned (from §0 plus `frontend-design`)

- Drop shadows for elevation, purple gradients, a centred hero with an illustration, a card grid of everything, Inter/system-ui, default MUI blue.
- ALL-CAPS labels; tracked-out eyebrows above headings; meta strings joined with middle dots; `WORD — fragment` labels; `→` on links and buttons; accenting one word of a headline; numbered markers on non-sequences (the KB citation chips are a real mapping, so they're allowed); fade-and-slide-up on every section.

## 8. Review against the brief (second pass), and what changed

1. **Colour description corrected.** §0 describes the Spruce scheme as having "warm-leaning neutrals… and a dusty-rose tertiary". Measuring `SchemeContent` shows **cool, green-tinted neutrals** and a **dusky violet tertiary** (`#4D3F71` light, `#CFBEF8` dark). The locked decision (seed + `SchemeContent`) is unchanged; only the prose was wrong. Consequence: the "attention" accent (internal notes, SLA at risk) is violet. It stays clearly distinct from error red and from the teal primary, and it's a flat tonal fill, never a gradient, so the purple-gradient ban doesn't apply. Swapping the tertiary for a hand-picked rose would break "tonal roles from a seed, not a hex palette", so I didn't.
2. **The KB panel was going to be an outlined card.** On review that reads as the generic SaaS card kit, and it would look like every other surface on the page. Changed to the single saturated `primary-container` surface, which makes it the memorable element and reserves the seed colour for it.
3. **"Your requests" nearly became cards with status badges.** That's the brief's banned card grid. It stays a divided list: subject, a human status line, and relative time in separate columns, with no middle-dot meta string.
4. **The auth screens were drafted as a centred card on a tinted page.** That's the generic default login. Changed to a left-aligned headline beside the form (stacked on compact widths), so it shares the end-user portal's calm, left-aligned column.
5. **Agent density check.** A first draft used the same 16px body and 56px inputs as the end user. That fails the brief's requirement for deliberately different density. Compact density is now a context the agent shell sets, not per-component props.
6. **Monospace for ticket IDs** was already removed in §0. Kept out: IDs like `TCK-00042` use tabular figures.
7. **(Phase 15) The LiverX brand guideline replaces the placeholder Spruce scheme and Google Sans Flex/Roboto Flex pairing**, per the scope-change note at the top of PLAN.md. Seed: `#00A4D8` (measured light `primary` `#006688`, 0.85° from the brand's `#007BA2`). Typeface: IBM Plex Sans throughout (with Tajawal for Arabic), replacing the two-face display/body split — the ROND-axis personality difference between portals is gone; density, size and surface already carried that contrast, so nothing was added to replace it. Every `Button` also became one filled-primary style (the user's rule), so `tonal`/`outlined`/`text` no longer appear as distinct button looks — the KB panel and SLA ring signature elements are unaffected, since neither is a button.

## 9. Build notes

- `src/theme/scheme.ts`: seed + mode + contrast → role map, emitted as `--md-sys-color-*`. `tokens.ts`: shape, typescale and motion vars. `muiTheme.ts`: MUI `createTheme` from the same role map (palette, shape, typography variants, component overrides, `shadows: none`).
- `ThemeController` context: mode `system | light | dark` and contrast `0 | 0.5 | 1`, persisted to `localStorage` and wrapped in try/catch.
- `/_tokens` (dev only) renders every colour role pair and type role. It's used for the screenshot critique.
