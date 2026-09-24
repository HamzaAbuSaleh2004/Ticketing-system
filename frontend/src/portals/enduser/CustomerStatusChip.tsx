import { Box } from "@mui/material";
import type { TicketStatus } from "../../api/types";
import { CUSTOMER_STATUS } from "../../lib/tickets";
import { sys, type ColorRole } from "../../theme/scheme";
import { typescale } from "../../theme/tokens";

const TONE: Record<TicketStatus, { bg: ColorRole | null; fg: ColorRole; outline?: boolean }> = {
  new: { bg: "surfaceContainerHighest", fg: "onSurfaceVariant" },
  triaged: { bg: "surfaceContainerHighest", fg: "onSurfaceVariant" },
  open: { bg: "secondaryContainer", fg: "onSecondaryContainer" },
  in_progress: { bg: "secondaryContainer", fg: "onSecondaryContainer" },
  // The one status that asks something of the customer gets the attention tone.
  pending: { bg: "tertiaryContainer", fg: "onTertiaryContainer" },
  resolved: { bg: null, fg: "primary", outline: true },
  closed: { bg: null, fg: "onSurfaceVariant", outline: true },
};

export function CustomerStatusChip({ status }: { status: TicketStatus }) {
  const tone = TONE[status];
  return (
    <Box
      component="span"
      sx={{
        display: "inline-flex",
        alignItems: "center",
        height: 28,
        px: 1.5,
        whiteSpace: "nowrap",
        borderRadius: "var(--md-sys-shape-corner-full)",
        bgcolor: tone.bg ? sys(tone.bg) : "transparent",
        color: sys(tone.fg),
        border: tone.outline ? `1px solid ${sys("outline")}` : "none",
        ...typescale("label-large"),
      }}
    >
      {CUSTOMER_STATUS[status].label}
    </Box>
  );
}
