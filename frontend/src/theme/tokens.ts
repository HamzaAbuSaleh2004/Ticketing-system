/** M3 shape, type scale and motion tokens as CSS custom properties
 * (values from the material-3 skill's typography-and-shape reference). */

export const DISPLAY_FONT = "'Google Sans Flex Variable', 'Roboto Flex Variable', sans-serif";
export const BODY_FONT = "'Roboto Flex Variable', sans-serif";

export const SHAPE = {
  none: "0px",
  "extra-small": "4px",
  small: "8px",
  medium: "12px",
  large: "16px",
  "large-increased": "20px",
  "extra-large": "28px",
  "extra-large-increased": "32px",
  "extra-extra-large": "48px",
  full: "9999px",
} as const;

export type ShapeToken = keyof typeof SHAPE;
export const shape = (token: ShapeToken) => `var(--md-sys-shape-corner-${token})`;

type TypeRole = { font: "display" | "body"; size: number; line: number; weight: number; tracking: number };

export const TYPESCALE = {
  "display-large": { font: "display", size: 57, line: 64, weight: 400, tracking: -0.25 },
  "display-medium": { font: "display", size: 45, line: 52, weight: 400, tracking: 0 },
  "display-small": { font: "display", size: 36, line: 44, weight: 400, tracking: 0 },
  "headline-large": { font: "display", size: 32, line: 40, weight: 400, tracking: 0 },
  "headline-medium": { font: "display", size: 28, line: 36, weight: 400, tracking: 0 },
  "headline-small": { font: "display", size: 24, line: 32, weight: 400, tracking: 0 },
  "title-large": { font: "body", size: 22, line: 28, weight: 400, tracking: 0 },
  "title-medium": { font: "body", size: 16, line: 24, weight: 500, tracking: 0.15 },
  "title-small": { font: "body", size: 14, line: 20, weight: 500, tracking: 0.1 },
  "body-large": { font: "body", size: 16, line: 24, weight: 400, tracking: 0.5 },
  "body-medium": { font: "body", size: 14, line: 20, weight: 400, tracking: 0.25 },
  "body-small": { font: "body", size: 12, line: 16, weight: 400, tracking: 0.4 },
  "label-large": { font: "body", size: 14, line: 20, weight: 500, tracking: 0.1 },
  "label-medium": { font: "body", size: 12, line: 16, weight: 500, tracking: 0.5 },
  "label-small": { font: "body", size: 11, line: 16, weight: 500, tracking: 0.5 },
} as const satisfies Record<string, TypeRole>;

export type TypeRoleName = keyof typeof TYPESCALE;

export const MOTION = {
  "easing-emphasized": "cubic-bezier(0.2, 0, 0, 1)",
  "easing-emphasized-decelerate": "cubic-bezier(0.05, 0.7, 0.1, 1)",
  "easing-emphasized-accelerate": "cubic-bezier(0.3, 0, 0.8, 0.15)",
  "easing-standard": "cubic-bezier(0.2, 0, 0, 1)",
  "easing-standard-decelerate": "cubic-bezier(0, 0, 0, 1)",
  "easing-standard-accelerate": "cubic-bezier(0.3, 0, 1, 1)",
  "duration-short2": "100ms",
  "duration-short4": "200ms",
  "duration-medium2": "300ms",
  "duration-medium4": "400ms",
  "duration-long2": "500ms",
} as const;

export const motion = (token: keyof typeof MOTION) => `var(--md-sys-motion-${token})`;

const px = (n: number) => `${n / 16}rem`;

export function staticCssVars(): Record<string, string> {
  const vars: Record<string, string> = {};
  for (const [token, value] of Object.entries(SHAPE)) vars[`--md-sys-shape-corner-${token}`] = value;
  for (const [role, t] of Object.entries(TYPESCALE) as [TypeRoleName, TypeRole][]) {
    const prefix = `--md-sys-typescale-${role}`;
    vars[`${prefix}-font`] = t.font === "display" ? DISPLAY_FONT : BODY_FONT;
    vars[`${prefix}-size`] = px(t.size);
    vars[`${prefix}-line-height`] = px(t.line);
    vars[`${prefix}-weight`] = String(t.weight);
    vars[`${prefix}-tracking`] = `${t.tracking / t.size}em`;
  }
  for (const [token, value] of Object.entries(MOTION)) vars[`--md-sys-motion-${token}`] = value;
  return vars;
}

/** A full type role as a style object, for sx / styled. */
export function typescale(role: TypeRoleName) {
  const p = `--md-sys-typescale-${role}`;
  return {
    fontFamily: `var(${p}-font)`,
    fontSize: `var(${p}-size)`,
    lineHeight: `var(${p}-line-height)`,
    fontWeight: `var(${p}-weight)`,
    letterSpacing: `var(${p}-tracking)`,
  } as const;
}
