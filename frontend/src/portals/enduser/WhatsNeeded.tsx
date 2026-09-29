import { Box, Checkbox, Snackbar, Stack, Typography } from "@mui/material";
import { useState } from "react";
import { errorMessage } from "../../api/client";
import { usePatchActionItem } from "../../api/hooks";
import type { ActionItem, TicketDetailPublic } from "../../api/types";
import { absoluteTime } from "../../lib/tickets";
import { sys } from "../../theme/scheme";

function Row({ item, editable, onToggle }: { item: ActionItem; editable: boolean; onToggle?: (done: boolean) => void }) {
  return (
    <Stack direction="row" sx={{ alignItems: "flex-start", gap: 0.5 }}>
      <Checkbox
        checked={item.done}
        disabled={!editable}
        onChange={(e) => onToggle?.(e.target.checked)}
        sx={{ p: 0.5, mt: 0.25 }}
        slotProps={{ input: { "aria-label": item.description } }}
      />
      <Box sx={{ pt: 1 }}>
        <Typography
          variant="bodyLarge"
          sx={{ textDecoration: item.done ? "line-through" : "none", color: item.done ? sys("onSurfaceVariant") : sys("onSurface") }}
        >
          {item.description}
        </Typography>
        {item.done ? (
          <Typography variant="bodySmall" sx={{ color: sys("onSurfaceVariant"), display: "block" }}>
            Done{item.done_at ? `, ${absoluteTime(item.done_at)}` : ""}
          </Typography>
        ) : null}
      </Box>
    </Stack>
  );
}

/** The customer's view of a ticket's two checklists: they can tick their own
 * side, and see LiverX's side (read-only). */
export function WhatsNeeded({ ticket }: { ticket: TicketDetailPublic }) {
  const patch = usePatchActionItem(ticket.id);
  const fromYou = ticket.action_items.filter((i) => i.side === "customer");
  const fromLiverx = ticket.action_items.filter((i) => i.side === "liverx");
  const locked = ticket.status === "closed";
  const [toast, setToast] = useState<string | null>(null);

  return (
    <Box
      component="section"
      aria-label="What's needed"
      sx={{ mt: 3, p: { xs: 2, sm: 3 }, borderRadius: "var(--md-sys-shape-corner-extra-large)", bgcolor: sys("surfaceContainerLow") }}
    >
      <Typography variant="titleMedium" component="h2" sx={{ mb: 2 }}>
        What's needed
      </Typography>
      <Stack spacing={3}>
        <Box>
          <Typography variant="labelLarge" component="h3" sx={{ color: sys("onSurfaceVariant"), display: "block", mb: 1 }}>
            From you
          </Typography>
          {fromYou.length ? (
            <Stack spacing={1}>
              {fromYou.map((item) => (
                <Row
                  key={item.id}
                  item={item}
                  editable={!locked}
                  onToggle={(done) =>
                    patch.mutate(
                      { id: item.id, done },
                      { onError: (e) => setToast(errorMessage(e, "That change didn't save.")) },
                    )
                  }
                />
              ))}
            </Stack>
          ) : (
            <Typography variant="bodyMedium" sx={{ color: sys("onSurfaceVariant") }}>
              Nothing needed from you right now.
            </Typography>
          )}
        </Box>
        <Box>
          <Typography variant="labelLarge" component="h3" sx={{ color: sys("onSurfaceVariant"), display: "block", mb: 1 }}>
            From LiverX
          </Typography>
          {fromLiverx.length ? (
            <Stack spacing={1}>
              {fromLiverx.map((item) => (
                <Row key={item.id} item={item} editable={false} />
              ))}
            </Stack>
          ) : (
            <Typography variant="bodyMedium" sx={{ color: sys("onSurfaceVariant") }}>
              Nothing pending from LiverX right now.
            </Typography>
          )}
        </Box>
      </Stack>
      <Snackbar open={toast !== null} autoHideDuration={5000} onClose={() => setToast(null)} message={toast} />
    </Box>
  );
}
