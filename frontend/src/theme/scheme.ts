import { Hct, SchemeContent, argbFromHex, hexFromArgb } from "@material/material-color-utilities";

/** The single seed the whole scheme is generated from (the LiverX brand's
 * Bright Cyan Blue, docs/brand/liverx-brand-guideline.pdf). */
export const SEED = "#00A4D8";

export type Contrast = 0 | 0.5 | 1;

const ROLES = [
  "primary",
  "onPrimary",
  "primaryContainer",
  "onPrimaryContainer",
  "inversePrimary",
  "secondary",
  "onSecondary",
  "secondaryContainer",
  "onSecondaryContainer",
  "tertiary",
  "onTertiary",
  "tertiaryContainer",
  "onTertiaryContainer",
  "error",
  "onError",
  "errorContainer",
  "onErrorContainer",
  "background",
  "onBackground",
  "surface",
  "onSurface",
  "surfaceVariant",
  "onSurfaceVariant",
  "surfaceDim",
  "surfaceBright",
  "surfaceContainerLowest",
  "surfaceContainerLow",
  "surfaceContainer",
  "surfaceContainerHigh",
  "surfaceContainerHighest",
  "inverseSurface",
  "inverseOnSurface",
  "outline",
  "outlineVariant",
  "shadow",
  "scrim",
  "surfaceTint",
] as const;

export type ColorRole = (typeof ROLES)[number];
export type ColorScheme = Record<ColorRole, string>;

export function generateScheme(isDark: boolean, contrast: Contrast = 0, seed = SEED): ColorScheme {
  // SchemeContent keeps the primary close to the seed; SchemeTonalSpot would desaturate it.
  const scheme = new SchemeContent(Hct.fromInt(argbFromHex(seed)), isDark, contrast);
  return Object.fromEntries(ROLES.map((role) => [role, hexFromArgb(scheme[role])])) as ColorScheme;
}

const kebab = (role: string) => role.replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`);

/** `--md-sys-color-*` custom properties for every role. */
export function schemeCssVars(scheme: ColorScheme): Record<string, string> {
  return Object.fromEntries(
    (Object.keys(scheme) as ColorRole[]).map((role) => [`--md-sys-color-${kebab(role)}`, scheme[role]]),
  );
}

/** `var(--md-sys-color-*)` reference for use in sx / styles. */
export const sys = (role: ColorRole) => `var(--md-sys-color-${kebab(role)})`;

export const COLOR_ROLES = ROLES;
