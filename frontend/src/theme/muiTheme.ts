import { createTheme, type Shadows, type Theme, type TypographyStyle } from "@mui/material/styles";
import type { ColorScheme } from "./scheme";
import { BODY_FONT, SHAPE, TYPESCALE, type TypeRoleName } from "./tokens";

export type Density = "comfortable" | "compact";

type M3Variant =
  | "displayLarge"
  | "displayMedium"
  | "displaySmall"
  | "headlineLarge"
  | "headlineMedium"
  | "headlineSmall"
  | "titleLarge"
  | "titleMedium"
  | "titleSmall"
  | "bodyLarge"
  | "bodyMedium"
  | "bodySmall"
  | "labelLarge"
  | "labelMedium"
  | "labelSmall";

declare module "@mui/material/styles" {
  interface TypographyVariants extends Record<M3Variant, TypographyStyle> {}
  interface TypographyVariantsOptions extends Partial<Record<M3Variant, TypographyStyle>> {}
  interface Palette {
    m3: ColorScheme;
    density: Density;
  }
  interface PaletteOptions {
    m3: ColorScheme;
    density: Density;
  }
}

declare module "@mui/material/Button" {
  interface ButtonPropsVariantOverrides {
    tonal: true;
  }
}

declare module "@mui/material/Typography" {
  interface TypographyPropsVariantOverrides extends Record<M3Variant, true> {}
}

export const toCamel = (role: string) => role.replace(/-([a-z])/g, (_, c: string) => c.toUpperCase()) as M3Variant;

function variant(role: TypeRoleName, rond: number): TypographyStyle {
  const p = `--md-sys-typescale-${role}`;
  const isDisplay = TYPESCALE[role].font === "display";
  return {
    fontFamily: `var(${p}-font)`,
    fontSize: `var(${p}-size)`,
    lineHeight: `var(${p}-line-height)`,
    fontWeight: `var(${p}-weight)` as TypographyStyle["fontWeight"],
    letterSpacing: `var(${p}-tracking)`,
    // ROND per portal: rounded (60) for the calm end-user portal, 0 for the
    // agent console. It's in the theme (not a CSS var on a wrapper) so
    // Menus/Dialogs portalled to <body> still get their portal's value.
    ...(isDisplay ? { fontVariationSettings: `'ROND' ${rond}` } : {}),
  };
}

export const ROND = { comfortable: 60, compact: 0 } as const;

function m3VariantsFor(density: Density) {
  return Object.fromEntries(
    (Object.keys(TYPESCALE) as TypeRoleName[]).map((role) => [toCamel(role), variant(role, ROND[density])]),
  ) as Record<M3Variant, TypographyStyle>;
}

const variantMapping: Record<M3Variant, string> = {
  displayLarge: "h1",
  displayMedium: "h1",
  displaySmall: "h1",
  headlineLarge: "h1",
  headlineMedium: "h2",
  headlineSmall: "h2",
  titleLarge: "h2",
  titleMedium: "h3",
  titleSmall: "h3",
  bodyLarge: "p",
  bodyMedium: "p",
  bodySmall: "p",
  labelLarge: "span",
  labelMedium: "span",
  labelSmall: "span",
};

export function buildMuiTheme(scheme: ColorScheme, isDark: boolean, density: Density): Theme {
  const c = scheme;
  const compact = density === "compact";
  const m3Variants = m3VariantsFor(density);
  const body = compact ? m3Variants.bodyMedium : m3Variants.bodyLarge;

  return createTheme({
    palette: {
      mode: isDark ? "dark" : "light",
      primary: { main: c.primary, contrastText: c.onPrimary, light: c.primaryContainer, dark: c.primary },
      secondary: { main: c.secondary, contrastText: c.onSecondary },
      error: { main: c.error, contrastText: c.onError },
      warning: { main: c.tertiary, contrastText: c.onTertiary },
      info: { main: c.secondary, contrastText: c.onSecondary },
      success: { main: c.primary, contrastText: c.onPrimary },
      background: { default: c.surface, paper: c.surfaceContainerLow },
      text: { primary: c.onSurface, secondary: c.onSurfaceVariant },
      divider: c.outlineVariant,
      m3: scheme,
      density,
    },
    shape: { borderRadius: parseInt(SHAPE.small, 10) },
    // M3 communicates elevation with tonal surfaces, never shadows.
    shadows: Array(25).fill("none") as Shadows,
    typography: {
      fontFamily: BODY_FONT,
      ...m3Variants,
      h1: m3Variants.headlineLarge,
      h2: m3Variants.headlineMedium,
      h3: m3Variants.headlineSmall,
      h4: m3Variants.titleLarge,
      h5: m3Variants.titleMedium,
      h6: m3Variants.titleSmall,
      subtitle1: m3Variants.titleMedium,
      subtitle2: m3Variants.titleSmall,
      body1: body,
      body2: m3Variants.bodyMedium,
      caption: m3Variants.bodySmall,
      overline: { ...m3Variants.labelSmall, textTransform: "none" },
      button: { ...m3Variants.labelLarge, textTransform: "none" },
    },
    components: {
      MuiCssBaseline: {
        styleOverrides: {
          body: { backgroundColor: c.surface, color: c.onSurface, fontOpticalSizing: "auto" },
          ".tabular": { fontVariantNumeric: "tabular-nums" },
          "@media (prefers-reduced-motion: reduce)": {
            "*, *::before, *::after": {
              animationDuration: "0.01ms !important",
              transitionDuration: "0.01ms !important",
            },
          },
        },
      },
      MuiTypography: { defaultProps: { variantMapping } },
      MuiButtonBase: { defaultProps: { disableRipple: false } },
      MuiButton: {
        defaultProps: { disableElevation: true },
        variants: [
          {
            // M3 filled tonal button: secondary-container, for secondary actions.
            props: { variant: "tonal" },
            style: {
              backgroundColor: c.secondaryContainer,
              color: c.onSecondaryContainer,
              "&:hover": { backgroundColor: `color-mix(in srgb, ${c.onSecondaryContainer} 8%, ${c.secondaryContainer})` },
              "&.Mui-disabled": { backgroundColor: `color-mix(in srgb, ${c.onSurface} 12%, transparent)` },
            },
          },
        ],
        styleOverrides: {
          root: {
            borderRadius: "var(--md-sys-shape-corner-full)",
            textTransform: "none",
            minHeight: compact ? 36 : 40,
            paddingInline: 24,
            // M3: 40dp visual height, 48dp touch target. The invisible
            // ::after pads the hit area out to 48 without changing layout
            // (ButtonBase is already position: relative). Layouts keep
            // >= 8px between stacked buttons so padded areas don't overlap.
            "&::after": { content: '""', position: "absolute", inset: compact ? "-6px 0" : "-4px 0" },
          },
          outlined: { borderColor: c.outline },
          sizeSmall: { minHeight: 32, paddingInline: 16, "&::after": { inset: "-8px 0" } },
        },
      },
      MuiIconButton: {
        styleOverrides: {
          root: {
            borderRadius: "var(--md-sys-shape-corner-full)",
            // 48dp touch target however small the visual button is.
            "&::after": { content: '""', position: "absolute", width: 48, height: 48, left: "50%", top: "50%", transform: "translate(-50%, -50%)" },
          },
        },
      },
      MuiToggleButton: {
        styleOverrides: {
          root: {
            textTransform: "none",
            borderColor: c.outline,
            color: c.onSurface,
            "&.Mui-selected": { backgroundColor: c.secondaryContainer, color: c.onSecondaryContainer },
            "&.Mui-selected:hover": { backgroundColor: c.secondaryContainer },
          },
        },
      },
      MuiToggleButtonGroup: {
        styleOverrides: {
          root: { borderRadius: "var(--md-sys-shape-corner-full)" },
          firstButton: { borderRadius: "var(--md-sys-shape-corner-full) 0 0 var(--md-sys-shape-corner-full)" },
          lastButton: { borderRadius: "0 var(--md-sys-shape-corner-full) var(--md-sys-shape-corner-full) 0" },
        },
      },
      MuiChip: {
        styleOverrides: {
          root: { borderRadius: "var(--md-sys-shape-corner-full)", ...m3Variants.labelLarge },
          outlined: { borderColor: c.outline },
        },
      },
      MuiPaper: {
        defaultProps: { elevation: 0 },
        styleOverrides: { root: { backgroundImage: "none" } },
      },
      MuiCard: {
        styleOverrides: {
          root: { borderRadius: "var(--md-sys-shape-corner-medium)", backgroundColor: c.surfaceContainerLow },
        },
      },
      MuiAppBar: {
        defaultProps: { elevation: 0, color: "transparent" },
        styleOverrides: { root: { backgroundColor: c.surface, color: c.onSurface } },
      },
      MuiDialog: {
        styleOverrides: {
          paper: { borderRadius: "var(--md-sys-shape-corner-extra-large)", backgroundColor: c.surfaceContainerHigh },
        },
      },
      MuiPopover: {
        styleOverrides: {
          paper: { borderRadius: "var(--md-sys-shape-corner-small)", backgroundColor: c.surfaceContainer },
        },
      },
      MuiMenu: {
        styleOverrides: {
          paper: { borderRadius: "var(--md-sys-shape-corner-small)", backgroundColor: c.surfaceContainer },
        },
      },
      MuiTooltip: {
        styleOverrides: {
          tooltip: {
            borderRadius: "var(--md-sys-shape-corner-extra-small)",
            backgroundColor: c.inverseSurface,
            color: c.inverseOnSurface,
            ...m3Variants.bodySmall,
          },
        },
      },
      MuiOutlinedInput: {
        styleOverrides: {
          root: {
            borderRadius: "var(--md-sys-shape-corner-small)",
            "& .MuiOutlinedInput-notchedOutline": { borderColor: c.outline },
            "&:hover .MuiOutlinedInput-notchedOutline": { borderColor: c.onSurface },
          },
        },
      },
      MuiTextField: { defaultProps: { size: compact ? "small" : "medium" } },
      MuiDivider: { styleOverrides: { root: { borderColor: c.outlineVariant } } },
      MuiTableCell: { styleOverrides: { root: { borderColor: c.outlineVariant } } },
      MuiTab: { styleOverrides: { root: { textTransform: "none", ...m3Variants.titleSmall } } },
      MuiLink: { defaultProps: { underline: "hover" } },
      MuiSnackbarContent: {
        styleOverrides: {
          root: {
            borderRadius: "var(--md-sys-shape-corner-extra-small)",
            backgroundColor: c.inverseSurface,
            color: c.inverseOnSurface,
          },
        },
      },
      MuiAlert: {
        styleOverrides: { root: { borderRadius: "var(--md-sys-shape-corner-medium)" } },
      },
    },
  });
}
