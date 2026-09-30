import { Box, Tooltip, Typography } from "@mui/material";
import { slaView, type SlaInput, type SlaState } from "../lib/sla";
import { useNow } from "../lib/useNow";
import { sys, type ColorRole } from "../theme/scheme";

const RING: Record<Exclude<SlaState, "none">, ColorRole> = {
  on_track: "primary",
  at_risk: "tertiary",
  breached: "error",
  paused: "outline",
};

/** The agent console's signature: a ring + tabular countdown on every row.
 * Every state carries text ("At risk", "Breached", "Paused"), not colour alone. */
export function SlaIndicator({ ticket, size = "row" }: { ticket: SlaInput; size?: "row" | "large" }) {
  const now = useNow();
  const v = slaView(ticket, now);
  if (v.state === "none") {
    return (
      <Typography variant="bodySmall" sx={{ color: sys("onSurfaceVariant") }} aria-label="No SLA running">
        None
      </Typography>
    );
  }

  const px = size === "large" ? 40 : 20;
  const stroke = size === "large" ? 4 : 3;
  const r = (px - stroke) / 2;
  const circumference = 2 * Math.PI * r;
  const color = sys(RING[v.state]);
  const paused = v.state === "paused";

  return (
    <Tooltip title={v.description}>
      <Box
        role="img"
        aria-label={v.description}
        sx={{ display: "inline-flex", alignItems: "center", gap: size === "large" ? 1.5 : 1, whiteSpace: "nowrap" }}
      >
        <Box component="svg" width={px} height={px} viewBox={`0 0 ${px} ${px}`} aria-hidden sx={{ flexShrink: 0, transform: "rotate(-90deg)" }}>
          <circle
            cx={px / 2}
            cy={px / 2}
            r={r}
            fill="none"
            stroke={paused ? color : sys("surfaceContainerHighest")}
            strokeWidth={stroke}
            // Paused: a dashed outline ring instead of progress.
            strokeDasharray={paused ? `${circumference / 12} ${circumference / 24}` : undefined}
          />
          {paused ? null : (
            <circle
              cx={px / 2}
              cy={px / 2}
              r={r}
              fill="none"
              stroke={color}
              strokeWidth={stroke}
              strokeLinecap="round"
              strokeDasharray={`${circumference * Math.max(v.fraction, v.state === "breached" ? 1 : 0.02)} ${circumference}`}
            />
          )}
        </Box>
        <Box sx={{ display: "flex", flexDirection: size === "large" ? "column" : "row", alignItems: size === "large" ? "flex-start" : "baseline", gap: size === "large" ? 0 : 0.75 }}>
          <Typography
            component="span"
            variant={size === "large" ? "titleMedium" : "bodyMedium"}
            className="tabular"
            sx={{ color: v.state === "breached" ? sys("error") : sys("onSurface"), fontWeight: v.state === "on_track" ? 400 : 500 }}
          >
            {v.countdown}
          </Typography>
          {v.stateLabel ? (
            <Typography
              component="span"
              variant="labelMedium"
              sx={{ color: v.state === "paused" ? sys("onSurfaceVariant") : sys(RING[v.state]) }}
            >
              {v.stateLabel}
            </Typography>
          ) : null}
        </Box>
      </Box>
    </Tooltip>
  );
}
