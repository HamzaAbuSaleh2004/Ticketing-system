import CloseOutlined from "@mui/icons-material/CloseOutlined";
import { Box, Button, Checkbox, IconButton, Snackbar, Stack, TextField, Typography } from "@mui/material";
import { useState } from "react";
import { errorMessage } from "../../api/client";
import { useCreateActionItem, useDeleteActionItem, usePatchActionItem } from "../../api/hooks";
import type { ActionItem, ActionItemSide, TicketDetail } from "../../api/types";
import { absoluteTime } from "../../lib/tickets";
import { sys } from "../../theme/scheme";

const SIDE_LABEL: Record<ActionItemSide, string> = { customer: "From the customer", liverx: "From LiverX" };
const ADD_LABEL: Record<ActionItemSide, string> = {
  customer: "Add an item from the customer",
  liverx: "Add an item from LiverX",
};

function Item({ item, locked, onToggle, onRemove }: { item: ActionItem; locked: boolean; onToggle: (done: boolean) => void; onRemove: () => void }) {
  return (
    <Stack direction="row" sx={{ alignItems: "flex-start", gap: 0.25 }}>
      <Checkbox
        size="small"
        checked={item.done}
        disabled={locked}
        onChange={(e) => onToggle(e.target.checked)}
        sx={{ p: 0.5, mt: 0.25 }}
        slotProps={{ input: { "aria-label": item.description } }}
      />
      <Box sx={{ flex: 1, minWidth: 0, pt: 0.5 }}>
        <Typography
          variant="bodyMedium"
          sx={{ textDecoration: item.done ? "line-through" : "none", color: item.done ? sys("onSurfaceVariant") : sys("onSurface") }}
        >
          {item.description}
        </Typography>
        {item.done && item.done_by_name ? (
          <Typography variant="bodySmall" sx={{ color: sys("onSurfaceVariant"), display: "block" }}>
            {item.done_by_name}, {item.done_at ? absoluteTime(item.done_at) : ""}
          </Typography>
        ) : null}
      </Box>
      {!locked ? (
        <IconButton size="small" onClick={onRemove} aria-label={`Remove "${item.description}"`} sx={{ mt: 0.25 }}>
          <CloseOutlined fontSize="small" />
        </IconButton>
      ) : null}
    </Stack>
  );
}

/** The agent workspace's "What's needed": two checklists, editable on both
 * sides by an agent, read-only once the ticket is closed. */
export function ActionItemsSection({ ticket }: { ticket: TicketDetail }) {
  const create = useCreateActionItem(ticket.id);
  const patch = usePatchActionItem(ticket.id);
  const remove = useDeleteActionItem(ticket.id);
  const locked = ticket.status === "closed";
  const [drafts, setDrafts] = useState<Record<ActionItemSide, string>>({ customer: "", liverx: "" });
  const [toast, setToast] = useState<string | null>(null);
  const onError = (fallback: string) => (e: unknown) => setToast(errorMessage(e, fallback));

  function add(side: ActionItemSide) {
    const description = drafts[side].trim();
    if (!description) return;
    create.mutate(
      { side, description },
      { onSuccess: () => setDrafts((d) => ({ ...d, [side]: "" })), onError: onError("That item didn't save.") },
    );
  }

  return (
    <Stack spacing={2}>
      <Typography variant="titleSmall" component="h2">
        What's needed
      </Typography>
      {(["customer", "liverx"] as const).map((side) => {
        const items = ticket.action_items.filter((i) => i.side === side);
        return (
          <Box key={side}>
            <Typography variant="labelLarge" component="h3" sx={{ color: sys("onSurfaceVariant"), display: "block", mb: 0.5 }}>
              {SIDE_LABEL[side]}
            </Typography>
            {items.length ? (
              <Stack spacing={0.25}>
                {items.map((item) => (
                  <Item
                    key={item.id}
                    item={item}
                    locked={locked || patch.isPending || remove.isPending}
                    onToggle={(done) => patch.mutate({ id: item.id, done }, { onError: onError("That change didn't save.") })}
                    onRemove={() => remove.mutate(item.id, { onError: onError("That item couldn't be removed.") })}
                  />
                ))}
              </Stack>
            ) : (
              <Typography variant="bodySmall" sx={{ color: sys("onSurfaceVariant") }}>
                Nothing yet.
              </Typography>
            )}
            {!locked ? (
              <Stack direction="row" sx={{ gap: 0.5, mt: 0.75 }}>
                <TextField
                  size="small"
                  fullWidth
                  placeholder="Add an item"
                  value={drafts[side]}
                  onChange={(e) => setDrafts((d) => ({ ...d, [side]: e.target.value }))}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      add(side);
                    }
                  }}
                  slotProps={{ htmlInput: { maxLength: 500, "aria-label": ADD_LABEL[side] } }}
                />
                <Button size="small" onClick={() => add(side)} disabled={create.isPending || !drafts[side].trim()} aria-label={ADD_LABEL[side]}>
                  Add
                </Button>
              </Stack>
            ) : null}
          </Box>
        );
      })}
      <Snackbar open={toast !== null} autoHideDuration={5000} onClose={() => setToast(null)} message={toast} />
    </Stack>
  );
}
