import { Box, Button, Stack, ToggleButton, ToggleButtonGroup, Typography } from "@mui/material";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { api } from "../../../api/client";
import type { TicketStatus } from "../../../api/types";
import { formatDuration } from "../../../lib/sla";
import { STATUS_LABEL } from "../../../lib/tickets";
import { sys } from "../../../theme/scheme";
import { typescale } from "../../../theme/tokens";
import { BarChart, ColumnChart } from "./charts";

type Summary = {
  from_date: string;
  to_date: string;
  created: number;
  volume: { date: string; count: number }[];
  first_response: { median_seconds: number | null; avg_seconds: number | null; count: number };
  resolution: { median_seconds: number | null; avg_seconds: number | null; count: number };
  backlog: { status: TicketStatus; count: number }[];
  sla_breaches: { total: number; response: number; resolution: number };
};

const RANGES = [7, 30, 90] as const;

const day = (iso: string) => new Date(`${iso}T00:00:00Z`).toLocaleDateString("en", { month: "short", day: "numeric", timeZone: "UTC" });
// Seconds matter here (a 40s first reply is a real result), unlike on SLA countdowns.
const duration = (s: number | null) =>
  s === null ? "None yet" : s < 60 ? `${Math.round(s)}s` : formatDuration(s * 1000);

function StatTile({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <Box component="section" aria-label={label} sx={{ p: 2, borderRadius: "var(--md-sys-shape-corner-small)", bgcolor: sys("surfaceContainerLow") }}>
      <Typography variant="labelLarge" component="h2" sx={{ color: sys("onSurfaceVariant") }}>
        {label}
      </Typography>
      {/* Same sans as the rest of the console, proportional figures (dataviz). */}
      <Box sx={{ ...typescale("display-small"), fontFamily: "var(--md-sys-typescale-body-large-font)", fontWeight: 600, mt: 0.5, color: sys("onSurface") }}>
        {value}
      </Box>
      <Typography variant="bodySmall" sx={{ color: sys("onSurfaceVariant") }}>
        {detail}
      </Typography>
    </Box>
  );
}

function ChartCard({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <Box component="section" aria-label={title} sx={{ p: 2, borderRadius: "var(--md-sys-shape-corner-small)", bgcolor: sys("surfaceContainerLow"), minWidth: 0 }}>
      <Typography variant="titleMedium" component="h2">
        {title}
      </Typography>
      <Typography variant="bodySmall" sx={{ color: sys("onSurfaceVariant"), mb: 2, display: "block" }}>
        {subtitle}
      </Typography>
      {children}
    </Box>
  );
}

export function DashboardPage() {
  const [params, setParams] = useSearchParams();
  const days = RANGES.find((r) => String(r) === params.get("days")) ?? 30;
  const to = new Date();
  const from = new Date(to.getTime() - (days - 1) * 86_400_000);
  const iso = (d: Date) => d.toISOString().slice(0, 10);
  const query = useQuery({
    // The window moves at UTC midnight, so key by the dates, not just the preset.
    queryKey: ["analytics", iso(from), iso(to)],
    queryFn: () => api<Summary>(`/analytics/summary?from=${iso(from)}&to=${iso(to)}`),
    placeholderData: keepPreviousData,
  });
  const s = query.data;

  return (
    <Box sx={{ p: { xs: 2, md: 3 } }}>
      <Typography variant="titleLarge" component="h1" sx={{ mb: 1.5 }}>
        Dashboard
      </Typography>

      {/* One filter row, above everything it scopes. */}
      <Stack direction="row" sx={{ alignItems: "center", gap: 2, mb: 2, flexWrap: "wrap" }}>
        <ToggleButtonGroup
          exclusive
          size="small"
          value={days}
          onChange={(_, v) => v && setParams({ days: String(v) })}
          aria-label="Date range"
        >
          {RANGES.map((r) => (
            <ToggleButton key={r} value={r} sx={{ px: 2 }}>
              Last {r} days
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
        {s ? (
          <Typography variant="bodySmall" className="tabular" sx={{ color: sys("onSurfaceVariant") }}>
            {day(s.from_date)} to {day(s.to_date)}, UTC
          </Typography>
        ) : null}
      </Stack>

      {query.isError && !s ? (
        <Box role="alert">
          <Typography variant="bodyLarge" sx={{ mb: 2 }}>
            The dashboard didn't load.
          </Typography>
          <Button variant="outlined" onClick={() => query.refetch()}>
            Try again
          </Button>
        </Box>
      ) : !s ? (
        <Typography variant="bodyMedium" sx={{ color: sys("onSurfaceVariant") }} aria-busy="true">
          Loading…
        </Typography>
      ) : (
        // Refetch keeps the frame: the previous render stays, dimmed.
        <Box sx={{ opacity: query.isPlaceholderData ? 0.6 : 1, transition: "opacity var(--md-sys-motion-duration-short4) var(--md-sys-motion-easing-standard)" }}>
          <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 1, mb: 1 }}>
            <StatTile label="Tickets created" value={s.created.toLocaleString()} detail={`In the last ${days} days`} />
            <StatTile
              label="Median first response"
              value={duration(s.first_response.median_seconds)}
              detail={s.first_response.count ? `Average ${duration(s.first_response.avg_seconds)} across ${s.first_response.count} tickets` : "No replies in this range"}
            />
            <StatTile
              label="Median resolution"
              value={duration(s.resolution.median_seconds)}
              detail={s.resolution.count ? `Average ${duration(s.resolution.avg_seconds)}, paused time excluded` : "Nothing resolved in this range"}
            />
            <StatTile
              label="SLA breaches"
              value={s.sla_breaches.total.toLocaleString()}
              detail={`${s.sla_breaches.response} first-reply, ${s.sla_breaches.resolution} resolution`}
            />
          </Box>

          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", lg: "minmax(0,2fr) minmax(0,1fr)" }, gap: 1 }}>
            <ChartCard title="Tickets created per day" subtitle="By the day the request arrived, UTC">
              <ColumnChart
                points={s.volume.map((v) => ({ key: v.date, label: day(v.date), value: v.count }))}
                valueLabel={(v) => (v === 1 ? "1 ticket" : `${v} tickets`)}
              />
            </ChartCard>
            <ChartCard title="Backlog by status" subtitle="Open work right now, whenever it arrived">
              <BarChart
                caption="Backlog by status"
                points={s.backlog.map((b) => ({ key: b.status, label: STATUS_LABEL[b.status], value: b.count }))}
              />
            </ChartCard>
          </Box>
        </Box>
      )}
    </Box>
  );
}
