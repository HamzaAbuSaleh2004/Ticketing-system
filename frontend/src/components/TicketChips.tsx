import { Box } from "@mui/material";
import type { TicketPriority, TicketStatus } from "../api/types";
import { PRIORITY_SHORT, STATUS_LABEL } from "../lib/tickets";
import { sys, type ColorRole } from "../theme/scheme";
import { typescale } from "../theme/tokens";

type Tone = { bg: ColorRole | null; fg: ColorRole; outline?: boolean };

function Pill({ tone, children }: { tone: Tone; children: string }) {
  return (
    <Box
      component="span"
      sx={{
        display: "inline-flex",
        alignItems: "center",
        height: 24,
        px: 1.25,
        whiteSpace: "nowrap",
        borderRadius: "var(--md-sys-shape-corner-full)",
        bgcolor: tone.bg ? sys(tone.bg) : "transparent",
        color: sys(tone.fg),
        border: tone.outline ? `1px solid ${sys("outlineVariant")}` : "none",
        ...typescale("label-medium"),
      }}
    >
      {children}
    </Box>
  );
}

const STATUS_TONE: Record<TicketStatus, Tone> = {
  new: { bg: "surfaceContainerHighest", fg: "onSurface" },
  triaged: { bg: "surfaceContainerHighest", fg: "onSurfaceVariant" },
  open: { bg: "secondaryContainer", fg: "onSecondaryContainer" },
  in_progress: { bg: "secondaryContainer", fg: "onSecondaryContainer" },
  pending: { bg: null, fg: "onSurfaceVariant", outline: true },
  resolved: { bg: null, fg: "primary", outline: true },
  closed: { bg: null, fg: "onSurfaceVariant", outline: true },
};

export function StatusChip({ status }: { status: TicketStatus }) {
  return <Pill tone={STATUS_TONE[status]}>{STATUS_LABEL[status]}</Pill>;
}

const PRIORITY_TONE: Record<TicketPriority, Tone> = {
  urgent: { bg: "errorContainer", fg: "onErrorContainer" },
  high: { bg: "tertiaryContainer", fg: "onTertiaryContainer" },
  normal: { bg: null, fg: "onSurface", outline: true },
  low: { bg: null, fg: "onSurfaceVariant", outline: true },
};

export function PriorityChip({ priority }: { priority: TicketPriority }) {
  return <Pill tone={PRIORITY_TONE[priority]}>{PRIORITY_SHORT[priority]}</Pill>;
}
