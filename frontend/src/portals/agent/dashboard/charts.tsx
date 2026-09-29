import { Box, Button, Table, TableBody, TableCell, TableHead, TableRow } from "@mui/material";
import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { sys } from "../../../theme/scheme";
import { typescale } from "../../../theme/tokens";

// dataviz mark specs: bars <= 24px, 4px rounded data-end square at the
// baseline, 2px surface gap between neighbours, hairline solid grid.
const MAX_BAR = 24;
const GAP = 2;
const RADIUS = 4;

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    if (!ref.current) return;
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);
  return [ref, width] as const;
}

/** Clean ticks for counts: 0, then a whole 1/2/5 × 10^n step. */
export function niceTicks(max: number, target = 4): number[] {
  if (max <= 0) return [0, 1];
  const raw = max / target;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = Math.max(1, [1, 2, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? 10 * mag);
  const top = Math.ceil(max / step) * step;
  return Array.from({ length: Math.round(top / step) + 1 }, (_, i) => i * step);
}

/** A bar path with a rounded data-end and a square base. */
function columnPath(x: number, y: number, w: number, h: number) {
  const r = Math.min(RADIUS, w / 2, h);
  return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
}
function barPath(x: number, y: number, w: number, h: number) {
  const r = Math.min(RADIUS, h / 2, w);
  return `M${x},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h - r}Q${x + w},${y + h} ${x + w - r},${y + h}H${x}Z`;
}

function Tooltip({ x, y, value, label, width }: { x: number; y: number; value: string; label: string; width: number }) {
  const left = Math.min(Math.max(x, 60), width - 60);
  return (
    <Box
      role="status"
      sx={{
        position: "absolute",
        left,
        top: y,
        transform: "translate(-50%, calc(-100% - 8px))",
        pointerEvents: "none",
        px: 1.25,
        py: 0.75,
        borderRadius: "var(--md-sys-shape-corner-extra-small)",
        bgcolor: sys("inverseSurface"),
        color: sys("inverseOnSurface"),
        whiteSpace: "nowrap",
        zIndex: 1,
      }}
    >
      {/* Value leads, label follows. */}
      <Box sx={{ ...typescale("title-small") }}>{value}</Box>
      <Box sx={{ ...typescale("body-small"), opacity: 0.85 }}>{label}</Box>
    </Box>
  );
}

function TableToggle({ shown, onToggle, children }: { shown: boolean; onToggle: () => void; children: ReactNode }) {
  return (
    <>
      <Button size="small" onClick={onToggle} sx={{ mt: 1, ml: -1 }} aria-expanded={shown}>
        {shown ? "Hide table" : "Show as table"}
      </Button>
      {shown ? children : null}
    </>
  );
}

export type Point = { key: string; label: string; value: number };

export function ColumnChart({ points, valueLabel, height = 220 }: { points: Point[]; valueLabel: (v: number) => string; height?: number }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [active, setActive] = useState<number | null>(null);
  const [table, setTable] = useState(false);
  const axisW = 36;
  const axisH = 24;
  // Room above the top gridline so its tick label isn't clipped.
  const padTop = 10;
  const plotW = Math.max(width - axisW, 0);
  const plotH = height - axisH - padTop;
  const ticks = niceTicks(Math.max(...points.map((p) => p.value), 0));
  const top = ticks[ticks.length - 1];
  const slot = points.length ? plotW / points.length : 0;
  const barW = Math.max(Math.min(MAX_BAR, slot - GAP), 1);
  const labelEvery = Math.max(1, Math.ceil(points.length / Math.max(1, Math.floor(plotW / 64))));
  const y = (v: number) => padTop + plotH - (v / top) * plotH;

  function onKey(e: KeyboardEvent) {
    if (!points.length) return;
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault();
      const d = e.key === "ArrowRight" ? 1 : -1;
      setActive((i) => Math.min(Math.max((i ?? (d > 0 ? -1 : points.length)) + d, 0), points.length - 1));
    }
  }

  const a = active !== null ? points[active] : null;

  return (
    <Box>
      <Box
        ref={ref}
        tabIndex={0}
        role="img"
        aria-label={`Column chart, ${points.length} days. Use the arrow keys to read each day, or show it as a table.`}
        onKeyDown={onKey}
        onBlur={() => setActive(null)}
        onPointerLeave={() => setActive(null)}
        onPointerMove={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const i = Math.floor((e.clientX - rect.left - axisW) / slot);
          setActive(i >= 0 && i < points.length ? i : null);
        }}
        sx={{ position: "relative", height, "&:focus-visible": { outline: `2px solid ${sys("primary")}`, outlineOffset: 4, borderRadius: "var(--md-sys-shape-corner-extra-small)" } }}
      >
        {width > 0 ? (
          <svg width={width} height={height} aria-hidden>
            {ticks.map((t) => (
              <g key={t}>
                <line x1={axisW} x2={width} y1={y(t)} y2={y(t)} stroke={sys("outlineVariant")} strokeWidth={1} />
                <text x={axisW - 8} y={y(t)} dy="0.32em" textAnchor="end" fill={sys("onSurfaceVariant")} style={{ ...typescale("label-small"), fontVariantNumeric: "tabular-nums" }}>
                  {t.toLocaleString()}
                </text>
              </g>
            ))}
            {points.map((p, i) => {
              const x = axisW + i * slot + (slot - barW) / 2;
              const h = padTop + plotH - y(p.value);
              return (
                <g key={p.key}>
                  {h > 0 ? (
                    <path
                      d={columnPath(x, y(p.value), barW, h)}
                      fill={sys("primary")}
                      opacity={active === null || active === i ? 1 : 0.55}
                    />
                  ) : null}
                  {i % labelEvery === 0 ? (
                    <text x={x + barW / 2} y={height - 6} textAnchor="middle" fill={sys("onSurfaceVariant")} style={{ ...typescale("label-small"), fontVariantNumeric: "tabular-nums" }}>
                      {p.label}
                    </text>
                  ) : null}
                </g>
              );
            })}
            {a !== null && active !== null ? (
              <line
                x1={axisW + active * slot + slot / 2}
                x2={axisW + active * slot + slot / 2}
                y1={padTop}
                y2={padTop + plotH}
                stroke={sys("outline")}
                strokeWidth={1}
              />
            ) : null}
          </svg>
        ) : null}
        {a && active !== null ? (
          <Tooltip x={axisW + active * slot + slot / 2} y={y(a.value)} value={valueLabel(a.value)} label={a.label} width={width} />
        ) : null}
      </Box>
      <TableToggle shown={table} onToggle={() => setTable((t) => !t)}>
        {/* Scrollable, so it must be keyboard-reachable (WCAG 2.1.1). */}
        <Box
          tabIndex={0}
          role="region"
          aria-label="Tickets created per day, table"
          sx={{ maxHeight: 260, overflowY: "auto", "&:focus-visible": { outline: `2px solid ${sys("primary")}` } }}
        >
          <Table size="small" aria-label="Tickets created per day">
            <TableHead>
              <TableRow>
                <TableCell>Day</TableCell>
                <TableCell align="right">Created</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {points.map((p) => (
                <TableRow key={p.key}>
                  <TableCell>{p.label}</TableCell>
                  <TableCell align="right" className="tabular">
                    {p.value}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
      </TableToggle>
    </Box>
  );
}

export function BarChart({
  points,
  caption,
  labelHeader = "Status",
  labelWidth = 96,
}: {
  points: Point[];
  caption: string;
  labelHeader?: string;
  labelWidth?: number;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [active, setActive] = useState<number | null>(null);
  const [table, setTable] = useState(false);
  const labelW = labelWidth;
  const valueW = 40;
  const rowH = 36;
  const max = Math.max(...points.map((p) => p.value), 1);
  const plotW = Math.max(width - labelW - valueW, 0);

  return (
    <Box>
      <Box ref={ref} role="img" aria-label={`${caption}: ${points.map((p) => `${p.label} ${p.value}`).join(", ")}`} sx={{ position: "relative" }}>
        {width > 0 ? (
          <svg width={width} height={points.length * rowH} aria-hidden>
            <line x1={labelW} x2={labelW} y1={0} y2={points.length * rowH} stroke={sys("outlineVariant")} strokeWidth={1} />
            {points.map((p, i) => {
              const w = (p.value / max) * plotW;
              const y = i * rowH + (rowH - MAX_BAR) / 2;
              return (
                <g
                  key={p.key}
                  onPointerEnter={() => setActive(i)}
                  onPointerLeave={() => setActive(null)}
                >
                  {/* Hit target: the whole row, not just the painted bar. */}
                  <rect x={0} y={i * rowH} width={width} height={rowH} fill="transparent" />
                  <text x={labelW - 12} y={i * rowH + rowH / 2} dy="0.32em" textAnchor="end" fill={sys("onSurfaceVariant")} style={typescale("label-large")}>
                    {p.label}
                  </text>
                  {w > 0 ? (
                    <path d={barPath(labelW, y, w, MAX_BAR)} fill={sys("primary")} opacity={active === null || active === i ? 1 : 0.55} />
                  ) : null}
                  <text x={labelW + w + 8} y={i * rowH + rowH / 2} dy="0.32em" fill={sys("onSurface")} style={{ ...typescale("label-large"), fontVariantNumeric: "tabular-nums" }}>
                    {p.value}
                  </text>
                </g>
              );
            })}
          </svg>
        ) : null}
      </Box>
      <TableToggle shown={table} onToggle={() => setTable((t) => !t)}>
        <Table size="small" aria-label={caption}>
          <TableHead>
            <TableRow>
              <TableCell>{labelHeader}</TableCell>
              <TableCell align="right">Tickets</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {points.map((p) => (
              <TableRow key={p.key}>
                <TableCell>{p.label}</TableCell>
                <TableCell align="right" className="tabular">
                  {p.value}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableToggle>
    </Box>
  );
}
