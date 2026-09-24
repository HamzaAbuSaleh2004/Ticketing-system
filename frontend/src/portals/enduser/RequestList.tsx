import { Box, Button, ButtonBase, Skeleton, Typography } from "@mui/material";
import { Link as RouterLink } from "react-router-dom";
import type { TicketListItem } from "../../api/types";
import { CUSTOMER_STATUS, absoluteTime, relativeTime, ticketRef } from "../../lib/tickets";
import { sys } from "../../theme/scheme";
import { CustomerStatusChip } from "./CustomerStatusChip";

/** "Your requests" as a divided list (not cards): subject + human status
 * line, the status, and when it last changed, each in its own column. */
type Props = { items: TicketListItem[] | undefined; isLoading: boolean; isError: boolean; onRetry: () => void };

export function RequestList({ items, isLoading, isError, onRetry }: Props) {
  if (isError && !items) {
    return (
      <Box role="alert" sx={{ py: 4 }}>
        <Typography variant="bodyLarge" sx={{ color: sys("onSurfaceVariant"), mb: 2 }}>
          Your requests didn't load. Check your connection and try again.
        </Typography>
        <Button variant="outlined" onClick={onRetry}>
          Try again
        </Button>
      </Box>
    );
  }

  if (isLoading) {
    return (
      <Box aria-busy="true" aria-label="Loading your requests">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} variant="rounded" height={72} sx={{ my: 1, bgcolor: sys("surfaceContainerHigh"), borderRadius: "var(--md-sys-shape-corner-large)" }} />
        ))}
      </Box>
    );
  }

  if (!items?.length) {
    return (
      <Box sx={{ py: 4 }}>
        <Typography variant="bodyLarge" sx={{ color: sys("onSurfaceVariant") }}>
          You haven't sent us anything yet. Search above first, or send a request and we'll take it from there.
        </Typography>
      </Box>
    );
  }

  return (
    <Box component="ul" sx={{ listStyle: "none", p: 0, m: 0 }}>
      {items.map((t) => (
        <Box component="li" key={t.id} sx={{ borderBottom: `1px solid ${sys("outlineVariant")}` }}>
          <ButtonBase
            component={RouterLink}
            to={`/requests/${t.id}`}
            sx={{
              textAlign: "left",
              display: "grid",
              gridTemplateColumns: { xs: "1fr auto", sm: "1fr auto 112px" },
              gridTemplateAreas: { xs: '"subject time" "status status"', sm: '"subject status time"' },
              alignItems: "center",
              columnGap: 2,
              rowGap: 1,
              py: 2,
              px: 1.5,
              mx: -1.5,
              width: "calc(100% + 24px)",
              borderRadius: "var(--md-sys-shape-corner-large)",
              transition: "background-color var(--md-sys-motion-duration-short4) var(--md-sys-motion-easing-standard)",
              "&:hover": { bgcolor: sys("surfaceContainerLow") },
              "&:focus-visible": { outline: `2px solid ${sys("primary")}`, outlineOffset: -2 },
            }}
          >
            <Box sx={{ gridArea: "subject", minWidth: 0 }}>
              <Typography variant="titleMedium" component="span" sx={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {t.subject}
              </Typography>
              <Typography variant="bodyMedium" component="span" sx={{ display: "block", color: sys("onSurfaceVariant") }}>
                {CUSTOMER_STATUS[t.status].line}
              </Typography>
            </Box>
            <Box sx={{ gridArea: "status", justifySelf: { xs: "start", sm: "end" } }}>
              <CustomerStatusChip status={t.status} />
            </Box>
            <Box sx={{ gridArea: "time", textAlign: "right" }}>
              <Typography
                variant="labelLarge"
                component="time"
                dateTime={t.updated_at}
                title={absoluteTime(t.updated_at)}
                sx={{ display: "block", color: sys("onSurface") }}
              >
                {relativeTime(t.updated_at)}
              </Typography>
              <Typography variant="labelMedium" component="span" className="tabular" sx={{ display: "block", color: sys("onSurfaceVariant") }}>
                {ticketRef(t.id)}
              </Typography>
            </Box>
          </ButtonBase>
        </Box>
      ))}
    </Box>
  );
}
