/** M3 shape, type scale and motion tokens as CSS custom properties
 * (values from the material-3 skill's typography-and-shape reference). */

// One face for every role (the LiverX brand guideline): IBM Plex Sans, with
// Tajawal after it so Arabic text in tickets and names renders in the
// brand's Arabic face. The UI itself stays English/LTR (out of scope).
export const FONT = "'IBM Plex Sans', 'Tajawal', sans-serif";

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

type TypeRole = { size: number; line: number; weight: number; tracking: number };

export const TYPESCALE = {
  "display-large": { size: 57, line: 64, weight: 400, tracking: -0.25 },
  "display-medium": { size: 45, line: 52, weight: 400, tracking: 0 },
  "display-small": { size: 36, line: 44, weight: 400, tracking: 0 },
  "headline-large": { size: 32, line: 40, weight: 400, tracking: 0 },
  "headline-medium": { size: 28, line: 36, weight: 400, tracking: 0 },
  "headline-small": { size: 24, line: 32, weight: 400, tracking: 0 },
  "title-large": { size: 22, line: 28, weight: 400, tracking: 0 },
  "title-medium": { size: 16, line: 24, weight: 500, tracking: 0.15 },
  "title-small": { size: 14, line: 20, weight: 500, tracking: 0.1 },
  "body-large": { size: 16, line: 24, weight: 400, tracking: 0.5 },
  "body-medium": { size: 14, line: 20, weight: 400, tracking: 0.25 },
  "body-small": { size: 12, line: 16, weight: 400, tracking: 0.4 },
  "label-large": { size: 14, line: 20, weight: 500, tracking: 0.1 },
  "label-medium": { size: 12, line: 16, weight: 500, tracking: 0.5 },
  "label-small": { size: 11, line: 16, weight: 500, tracking: 0.5 },
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
    vars[`${prefix}-font`] = FONT;
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
