import { Hct, argbFromHex } from "@material/material-color-utilities";
import { describe, expect, it } from "vitest";
import { COLOR_ROLES, generateScheme, schemeCssVars, SEED } from "./scheme";
import { staticCssVars } from "./tokens";
import { buildMuiTheme } from "./muiTheme";

const luminance = (hex: string) => {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const contrastRatio = (a: string, b: string) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

describe("scheme from the Spruce seed", () => {
  it("keeps the primary on the seed's hue (SchemeContent, not TonalSpot)", () => {
    const seedHue = Hct.fromInt(argbFromHex(SEED)).hue;
    for (const dark of [false, true]) {
      const primaryHue = Hct.fromInt(argbFromHex(generateScheme(dark).primary)).hue;
      expect(Math.abs(primaryHue - seedHue)).toBeLessThan(8);
    }
  });

  it("emits a --md-sys-color var for every role, light and dark", () => {
    const vars = schemeCssVars(generateScheme(false));
    expect(Object.keys(vars)).toHaveLength(COLOR_ROLES.length);
    expect(vars["--md-sys-color-surface-container-highest"]).toMatch(/^#[0-9a-f]{6}$/);
    expect(generateScheme(true).surface).not.toEqual(generateScheme(false).surface);
  });

  it.each([0, 0.5, 1] as const)("text pairs meet WCAG AA at contrast %s", (level) => {
    for (const dark of [false, true]) {
      const s = generateScheme(dark, level);
      for (const [bg, fg] of [
        ["primary", "onPrimary"],
        ["primaryContainer", "onPrimaryContainer"],
        ["secondaryContainer", "onSecondaryContainer"],
        ["tertiaryContainer", "onTertiaryContainer"],
        ["errorContainer", "onErrorContainer"],
        ["surface", "onSurface"],
        ["surfaceContainerHighest", "onSurfaceVariant"],
      ] as const) {
        expect(contrastRatio(s[bg], s[fg])).toBeGreaterThanOrEqual(4.5);
      }
    }
  });

  it("higher contrast levels widen the gap", () => {
    const standard = generateScheme(false, 0);
    const high = generateScheme(false, 1);
    expect(contrastRatio(high.surface, high.onSurfaceVariant)).toBeGreaterThan(
      contrastRatio(standard.surface, standard.onSurfaceVariant),
    );
  });
});

describe("tokens and MUI theme", () => {
  it("emits shape, typescale and motion vars with the two faces", () => {
    const vars = staticCssVars();
    expect(vars["--md-sys-shape-corner-full"]).toBe("9999px");
    expect(vars["--md-sys-typescale-display-large-font"]).toContain("Google Sans Flex");
    expect(vars["--md-sys-typescale-body-large-font"]).toContain("Roboto Flex");
    expect(vars["--md-sys-typescale-body-large-font"]).not.toMatch(/mono|Inter|system-ui/i);
    expect(vars["--md-sys-motion-easing-emphasized"]).toBe("cubic-bezier(0.2, 0, 0, 1)");
  });

  it("has no shadows, no uppercase buttons, and density-specific body size", () => {
    const scheme = generateScheme(false);
    const comfortable = buildMuiTheme(scheme, false, "comfortable");
    const compact = buildMuiTheme(scheme, false, "compact");
    expect(new Set(comfortable.shadows)).toEqual(new Set(["none"]));
    expect(comfortable.typography.button.textTransform).toBe("none");
    expect(comfortable.palette.primary.main).toBe(scheme.primary);
    expect(comfortable.typography.body1.fontSize).toContain("body-large");
    expect(compact.typography.body1.fontSize).toContain("body-medium");
  });
});
