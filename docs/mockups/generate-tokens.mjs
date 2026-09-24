// Generates m3-tokens.css: every M3 colour role from ONE seed (SchemeContent,
// light + dark), plus shape, typescale, state-layer and motion tokens.
//
//   npm install @material/material-color-utilities
//   node generate-tokens.mjs [seed=#1E6A5E] [contrast=0] > m3-tokens.css
//
// Verified against @material/material-color-utilities 0.4.0:
//   new SchemeContent(sourceColorHct: Hct, isDark: boolean, contrastLevel: number,
//                     specVersion?: '2021' | '2025', platform?)
// Default spec version is 2021, which is what we want (the 2025 spec's extra
// *Dim roles are skipped below).

import { registerHooks } from 'node:module';

// 0.4.0 ships extensionless relative imports (e.g. '../dynamiccolor/dynamic_scheme'
// in scheme/*.js). Bundlers (Vite) resolve it; Node's strict ESM
// resolver doesn't, so retry bare relative specifiers with '.js'.
registerHooks({
  resolve(specifier, context, next) {
    try {
      return next(specifier, context);
    } catch (err) {
      if (err.code === 'ERR_MODULE_NOT_FOUND' && specifier.startsWith('.') && !specifier.endsWith('.js')) {
        return next(specifier + '.js', context);
      }
      throw err;
    }
  },
});

const { argbFromHex, hexFromArgb, Hct, SchemeContent } = await import('@material/material-color-utilities');

const SEED = process.argv[2] ?? '#1E6A5E';
const CONTRAST = Number(process.argv[3] ?? 0);

// Scheme getter name → CSS role name. Every standard M3 role, 2021 spec.
const ROLES = [
  'primary', 'onPrimary', 'primaryContainer', 'onPrimaryContainer',
  'secondary', 'onSecondary', 'secondaryContainer', 'onSecondaryContainer',
  'tertiary', 'onTertiary', 'tertiaryContainer', 'onTertiaryContainer',
  'error', 'onError', 'errorContainer', 'onErrorContainer',
  'primaryFixed', 'primaryFixedDim', 'onPrimaryFixed', 'onPrimaryFixedVariant',
  'secondaryFixed', 'secondaryFixedDim', 'onSecondaryFixed', 'onSecondaryFixedVariant',
  'tertiaryFixed', 'tertiaryFixedDim', 'onTertiaryFixed', 'onTertiaryFixedVariant',
  'background', 'onBackground',
  'surface', 'onSurface', 'surfaceVariant', 'onSurfaceVariant',
  'surfaceDim', 'surfaceBright',
  'surfaceContainerLowest', 'surfaceContainerLow', 'surfaceContainer',
  'surfaceContainerHigh', 'surfaceContainerHighest',
  'inverseSurface', 'inverseOnSurface', 'inversePrimary',
  'outline', 'outlineVariant', 'shadow', 'scrim', 'surfaceTint',
];

const kebab = (s) => s.replace(/[A-Z]/g, (c) => '-' + c.toLowerCase());

function colorBlock(isDark, indent) {
  const scheme = new SchemeContent(Hct.fromInt(argbFromHex(SEED)), isDark, CONTRAST);
  return ROLES.map((r) => {
    const v = scheme[r];
    if (typeof v !== 'number') throw new Error(`SchemeContent has no role "${r}"`);
    return `${indent}--md-sys-color-${kebab(r)}: ${hexFromArgb(v)};`;
  }).join('\n');
}

// M3 baseline type scale (material-3 references/typography-and-shape.md).
// Display/Headline use the brand face, Title/Body/Label the plain face.
const TYPE = [
  ['display-large', 'brand', 400, 57, 64, -0.25],
  ['display-medium', 'brand', 400, 45, 52, 0],
  ['display-small', 'brand', 400, 36, 44, 0],
  ['headline-large', 'brand', 400, 32, 40, 0],
  ['headline-medium', 'brand', 400, 28, 36, 0],
  ['headline-small', 'brand', 400, 24, 32, 0],
  ['title-large', 'plain', 400, 22, 28, 0],
  ['title-medium', 'plain', 500, 16, 24, 0.15],
  ['title-small', 'plain', 500, 14, 20, 0.1],
  ['body-large', 'plain', 400, 16, 24, 0.5],
  ['body-medium', 'plain', 400, 14, 20, 0.25],
  ['body-small', 'plain', 400, 12, 16, 0.4],
  ['label-large', 'plain', 500, 14, 20, 0.1],
  ['label-medium', 'plain', 500, 12, 16, 0.5],
  ['label-small', 'plain', 500, 11, 16, 0.5],
];
const rem = (px) => `${+(px / 16).toFixed(5)}rem`;

function typeBlock() {
  const out = [];
  for (const [name, face, w, size, lh, track] of TYPE) {
    const font = `var(--md-ref-typeface-${face})`;
    const p = `--md-sys-typescale-${name}`;
    out.push(
      `  ${p}-font: ${font};`,
      `  ${p}-weight: ${w};`,
      `  ${p}-size: ${rem(size)};`,
      `  ${p}-line-height: ${rem(lh)};`,
      `  ${p}-tracking: ${rem(track)};`,
      // Shorthand for `font:`; letter-spacing still needs the -tracking token.
      `  ${p}: ${w} ${rem(size)} / ${rem(lh)} ${font};`,
      // Emphasized variant (Expressive): same metrics, heavier weight.
      `  --md-sys-typescale-emphasized-${name}-weight: ${w === 400 ? 500 : 700};`,
      `  --md-sys-typescale-emphasized-${name}: ${w === 400 ? 500 : 700} ${rem(size)} / ${rem(lh)} ${font};`,
    );
  }
  return out.join('\n');
}

const SHAPE = {
  none: '0px', 'extra-small': '4px', small: '8px', medium: '12px', large: '16px',
  'large-increased': '20px', 'extra-large': '28px', 'extra-large-increased': '32px',
  'extra-extra-large': '48px', full: '9999px',
};

const EASING = {
  emphasized: 'cubic-bezier(0.2, 0, 0, 1)',
  'emphasized-decelerate': 'cubic-bezier(0.05, 0.7, 0.1, 1)',
  'emphasized-accelerate': 'cubic-bezier(0.3, 0, 0.8, 0.15)',
  standard: 'cubic-bezier(0.2, 0, 0, 1)',
  'standard-decelerate': 'cubic-bezier(0, 0, 0, 1)',
  'standard-accelerate': 'cubic-bezier(0.3, 0, 1, 1)',
};
const DURATION = {};
['short', 'medium', 'long'].forEach((k, i) =>
  [1, 2, 3, 4].forEach((n) => (DURATION[`${k}${n}`] = `${i * 200 + n * 50}ms`)));
[1, 2, 3, 4].forEach((n) => (DURATION[`extra-long${n}`] = `${600 + n * 100}ms`));

const lines = (prefix, obj) =>
  Object.entries(obj).map(([k, v]) => `  --md-sys-${prefix}-${k}: ${v};`).join('\n');

const css = `/* GENERATED by generate-tokens.mjs, do not edit by hand.
 * Seed ${SEED.toUpperCase()}, SchemeContent, contrast ${CONTRAST}, @material/material-color-utilities 0.4.0
 * The only file in the mockup that contains hex colour values.
 * Theme switching: light by default; dark via prefers-color-scheme unless
 * <html data-theme="light">; forced dark via <html data-theme="dark">. */

:root {
  color-scheme: light dark;

  /* Reference typefaces (Google Fonts, verified axis tags) */
  --md-ref-typeface-brand: 'Google Sans Flex', 'Roboto Flex', sans-serif;
  --md-ref-typeface-plain: 'Roboto Flex', sans-serif;

  /* Colour: light */
${colorBlock(false, '  ')}

  /* Typescale */
${typeBlock()}

  /* Shape */
${lines('shape-corner', SHAPE)}

  /* State layers (opacity of on-X over X) */
  --md-sys-state-hover-state-layer-opacity: 0.08;
  --md-sys-state-focus-state-layer-opacity: 0.1;
  --md-sys-state-pressed-state-layer-opacity: 0.1;
  --md-sys-state-dragged-state-layer-opacity: 0.16;

  /* Motion */
${lines('motion-easing', EASING)}
${lines('motion-duration', DURATION)}
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
${colorBlock(true, '    ')}
  }
}

:root[data-theme="dark"] {
${colorBlock(true, '  ')}
}
`;

process.stdout.write(css);
