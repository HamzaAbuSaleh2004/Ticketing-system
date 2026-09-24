// Evidence for the material-3 audit: static grep checks, token-pair contrast,
// and live DOM checks (touch targets, focus, computed fonts) in Chromium.
import { readFileSync } from 'node:fs';
import { chromium } from 'playwright';
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';

const dir = 'docs/mockups';
const css = readFileSync(`${dir}/mockup.css`, 'utf8');
const html = readFileSync(`${dir}/index.html`, 'utf8');
const tokens = readFileSync(`${dir}/m3-tokens.css`, 'utf8');
const stripComments = (t) => t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/<!--[\s\S]*?-->/g, '').replace(/^\s*\/\/.*$/gm, '');
const both = stripComments(css + html);

console.log('== Static checks (mockup.css + index.html) ==');
const count = (re) => (both.match(re) ?? []).length;
console.log('hex colours outside m3-tokens.css :', count(/#[0-9a-fA-F]{3,8}\b(?![-\w])/g) - count(/href="#[0-9a-fA-F]{3,8}"/g));
console.log('rgb()/hsl() literals              :', count(/\b(rgb|hsl)a?\(/g));
console.log('raw border-radius (not a token)   :', count(/border-(?:[a-z-]+-)?radius:\s*(?![\s]|var\(--md-sys-shape|inherit)/g));
console.log('box-shadow declarations           :', count(/box-shadow\s*:/g));
console.log('text-transform: uppercase         :', count(/uppercase/g));
console.log('gradients                         :', count(/gradient\(/g));
console.log('font-family not via tokens        :', (css.match(/font-family:\s*[^;]+/g) ?? []).filter((f) => !f.includes('var(--md-ref')).join(' | '));
console.log('middle dots in UI text            :', count(/·/g));
console.log('" → " arrows in UI text           :', count(/→/g));

// Parse token hex values per mode.
function block(sel) {
  const i = tokens.indexOf(sel); const s = tokens.indexOf('{', i); let d = 0, e = s;
  for (; e < tokens.length; e++) { if (tokens[e] === '{') d++; if (tokens[e] === '}' && --d === 0) break; }
  return Object.fromEntries([...tokens.slice(s, e).matchAll(/--md-sys-color-([\w-]+):\s*(#[0-9a-f]{6})/g)].map((m) => [m[1], m[2]]));
}
const light = block(':root {'), dark = block(':root[data-theme="dark"] {');
const lum = (hex) => { const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)); return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]; };
const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };

// Pairs the mockup actually uses (fg on bg), with the WCAG threshold that applies.
const PAIRS = [
  ['on-surface', 'surface', 4.5, 'body text'],
  ['on-surface-variant', 'surface', 4.5, 'secondary text, column headers'],
  ['on-surface-variant', 'surface-container-low', 4.5, 'thread meta, request lines'],
  ['on-surface-variant', 'surface-container-high', 4.5, 'side panel labels'],
  ['on-surface-variant', 'surface-container-highest', 4.5, 'AI panel labels, selected row ID'],
  ['on-secondary-container', 'secondary-container', 4.5, 'answer panel text'],
  ['on-primary', 'primary', 4.5, 'filled buttons, citation markers'],
  ['on-primary-container', 'primary-container', 4.5, 'New request FAB'],
  ['primary', 'surface-container-lowest', 4.5, 'source chip numbers (bg primary) / text buttons'],
  ['primary', 'surface-container-high', 4.5, 'text buttons in side panel'],
  ['primary', 'surface-container-highest', 4.5, 'AI Accept/Override buttons'],
  ['tertiary', 'surface', 4.5, 'At risk label (queue)'],
  ['tertiary', 'surface-container-highest', 4.5, 'At risk label (selected row)'],
  ['error', 'surface', 4.5, 'Breached label'],
  ['error', 'surface-container-highest', 4.5, 'Breached label (selected row)'],
  ['on-error', 'error', 4.5, 'rail badge'],
  ['on-secondary-container', 'secondary-container', 4.5, 'selected chips / nav indicator'],
  ['on-tertiary', 'tertiary', 4.5, 'senior avatar'],
  ['outline', 'surface', 3, 'button/field outlines (non-text 3:1)'],
  ['primary', 'surface', 3, 'SLA ring arc on track (non-text)'],
  ['tertiary', 'surface', 3, 'SLA ring arc at risk (non-text)'],
  ['error', 'surface', 3, 'SLA ring breached (non-text)'],
  ['primary', 'surface-container-highest', 3, 'selected-row start bar (non-text)'],
  ['tertiary', 'surface-container-low', 3, 'internal-note start border (non-text)'],
  ['secondary', 'surface', 3, 'focus ring (non-text)'],
];
const ATTN = { light: ['on-tertiary-fixed', 'tertiary-fixed'], dark: ['on-tertiary-container', 'tertiary-container'] };
let fails = 0;
console.log('\n== Contrast of used role pairs (WCAG 2.x) ==');
for (const [mode, t] of [['light', light], ['dark', dark]]) {
  const rows = [...PAIRS.map(([fg, bg, min, use]) => [fg, bg, min, use]),
    [ATTN[mode][0], ATTN[mode][1], 4.5, 'attention alias (internal note, Waiting on you)']];
  for (const [fg, bg, min, use] of rows) {
    const r = ratio(t[fg], t[bg]); const ok = r >= min; if (!ok) fails++;
    console.log(`${mode.padEnd(5)} ${ok ? 'ok  ' : 'FAIL'} ${r.toFixed(2).padStart(5)}:1 (min ${min})  ${fg} on ${bg}  [${use}]`);
  }
  const sel = ratio(t['surface-container-highest'], t['surface']);
  console.log(`${mode.padEnd(5)} info ${sel.toFixed(2).padStart(5)}:1          surface-container-highest vs surface (why the selected row also gets a primary bar)`);
}
console.log(`contrast failures: ${fails}`);

// Live checks.
const exe = process.env.CHROME ?? 'C:/Users/hamza/AppData/Local/ms-playwright/chromium-1228/chrome-win64/chrome.exe';
const browser = await chromium.launch({ executablePath: exe });
const base = pathToFileURL(resolve(`${dir}/index.html`)).href + '?bare';
console.log('\n== Live DOM checks ==');
for (const [hash, w] of [['#home', 360], ['#home', 1280], ['#ticket', 360], ['#agent', 1280], ['#agent', 360]]) {
  const page = await browser.newPage({ viewport: { width: w, height: 900 } });
  await page.goto(base + hash);
  await page.evaluate(() => document.fonts.ready);
  const r = await page.evaluate(() => {
    const vis = (el) => { const b = el.getBoundingClientRect(); return b.width > 0 && b.height > 0 && getComputedStyle(el).visibility !== 'hidden'; };
    const screen = document.querySelector('.screen.is-active');
    const ctrls = [...screen.querySelectorAll('button, a[href], input, textarea, [tabindex="0"]')].filter(vis);
    // Effective target = own box, expanded by ::after hit area if present.
    const small = ctrls.filter((el) => {
      const b = el.getBoundingClientRect(); const a = getComputedStyle(el, '::after');
      const extra = a.content !== 'none' && a.position === 'absolute' ? { h: -2 * parseFloat(a.top || 0), w: -2 * parseFloat(a.left || 0) } : { h: 0, w: 0 };
      return Math.min(b.height + (extra.h || 0), b.width + (extra.w || 0)) < 48 - 0.5;
    }).map((el) => `${el.tagName.toLowerCase()}.${[...el.classList].join('.') || '-'}(${Math.round(el.getBoundingClientRect().height)}px)`);
    const unnamed = ctrls.filter((el) => !(el.getAttribute('aria-label') || el.textContent.trim() || el.labels?.length || el.getAttribute('placeholder'))).length;
    const fonts = new Set([...screen.querySelectorAll('h1, h2, p, td, span, button')].filter(vis).map((e) => getComputedStyle(e).fontFamily.split(',')[0].replace(/"/g, '').trim()));
    const loaded = ['Google Sans Flex', 'Roboto Flex', 'Material Symbols Rounded'].map((f) => `${f}=${document.fonts.check(`16px "${f}"`)}`);
    const shadows = [...screen.querySelectorAll('*')].filter((e) => getComputedStyle(e).boxShadow !== 'none').length;
    const upper = [...screen.querySelectorAll('*')].filter((e) => getComputedStyle(e).textTransform === 'uppercase').length;
    return { controls: ctrls.length, small: [...new Set(small)], unnamed, fonts: [...fonts], loaded, shadows, upper };
  });
  console.log(`${hash} @${w}: ${r.controls} controls, ${r.unnamed} without an accessible name, box-shadow elements ${r.shadows}, uppercase ${r.upper}`);
  console.log(`   fonts in use: ${r.fonts.join(', ')} | loaded: ${r.loaded.join(' ')}`);
  console.log(`   targets < 48px: ${r.small.length ? r.small.join(', ') : 'none'}`);
  await page.close();
}
// Keyboard: first Tab stops show a focus ring?
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
await page.goto(base + '#agent');
await page.keyboard.press('Tab');
const ring = await page.evaluate(() => { const e = document.activeElement; const s = getComputedStyle(e); return `${e.tagName.toLowerCase()} outline=${s.outlineStyle} ${s.outlineWidth}`; });
await page.click('#q-body tr[data-id="TCK-01040"]');
await page.keyboard.press('j');
const afterJ = await page.evaluate(() => document.querySelector('#q-body tr[aria-selected="true"]').dataset.id);
console.log(`\nkeyboard: first Tab focus -> ${ring}; j from TCK-01040 selects ${afterJ}`);
await page.emulateMedia({ reducedMotion: 'reduce' });
const dur = await page.evaluate(() => getComputedStyle(document.querySelector('.sl'), '::before').transitionDuration);
console.log(`reduced motion: state-layer transition-duration = ${dur}`);
await browser.close();
