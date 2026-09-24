import AttachFileOutlined from "@mui/icons-material/AttachFileOutlined";
import LockOutlined from "@mui/icons-material/LockOutlined";
import { Alert, Box, Button, Stack, TextField, ToggleButton, ToggleButtonGroup, Typography } from "@mui/material";
import { useState, type FormEvent } from "react";
import { errorMessage } from "../../api/client";
import { useReply } from "../../api/hooks";
import type { Comment, TicketDetail } from "../../api/types";
import { downloadAttachment } from "../../lib/download";
import { absoluteTime, relativeTime } from "../../lib/tickets";
import { sys } from "../../theme/scheme";

// "Tertiary-container tint" (PLAN.md): SchemeContent's tertiary-container is
// a dark, saturated violet, so internal notes use a light wash of tertiary
// over the message surface, plus a bar and an "Internal note" label.
export const internalTint = `color-mix(in srgb, ${sys("tertiary")} 12%, ${sys("surfaceContainerLowest")})`;

function Message({ author, role, at, body, internal }: { author: string; role: string; at: string; body: string; internal: boolean }) {
  return (
    <Box
      component="li"
      sx={{
        p: 1.5,
        borderRadius: "var(--md-sys-shape-corner-small)",
        bgcolor: internal ? internalTint : sys("surfaceContainerLowest"),
        color: sys("onSurface"),
        boxShadow: internal ? `inset 3px 0 0 ${sys("tertiary")}` : "none",
      }}
    >
      <Stack direction="row" sx={{ alignItems: "center", gap: 1, mb: 0.5 }}>
        {internal ? (
          <Box component="span" sx={{ display: "inline-flex", alignItems: "center", gap: 0.5, typography: "labelMedium", fontWeight: 700, color: sys("tertiary") }}>
            <LockOutlined sx={{ fontSize: 14 }} aria-hidden />
            Internal note
          </Box>
        ) : null}
        <Typography variant="titleSmall" component="span">
          {author}
        </Typography>
        <Typography variant="labelMedium" component="span" sx={{ color: sys("onSurfaceVariant") }}>
          {role}
        </Typography>
        <Box sx={{ flex: 1 }} />
        <Typography variant="bodySmall" component="time" dateTime={at} title={absoluteTime(at)} className="tabular" sx={{ color: sys("onSurfaceVariant") }}>
          {relativeTime(at)}
        </Typography>
      </Stack>
      <Typography variant="bodyMedium" sx={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
        {body}
      </Typography>
    </Box>
  );
}

const roleLabel = (c: Comment) => (c.author_role === "end_user" ? "Customer" : c.author_role === "admin" ? "Admin" : "Agent");

export function Composer({
  ticket,
  draft,
  onDraftChange,
}: {
  ticket: TicketDetail;
  draft: { body: string; internal: boolean };
  onDraftChange: (d: { body: string; internal: boolean }) => void;
}) {
  const reply = useReply(ticket.id);
  const [emptyTried, setEmptyTried] = useState(false);
  const internal = draft.internal;
  const locked = ticket.status === "closed" && !internal;

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!draft.body.trim()) {
      setEmptyTried(true);
      return;
    }
    setEmptyTried(false);
    reply.mutate(
      { body: draft.body.trim(), is_internal_note: internal },
      { onSuccess: () => onDraftChange({ body: "", internal }) },
    );
  }

  return (
    <Box
      component="form"
      onSubmit={onSubmit}
      aria-label="Composer"
      sx={{
        p: 1.5,
        borderRadius: "var(--md-sys-shape-corner-small)",
        bgcolor: internal ? internalTint : sys("surfaceContainerLowest"),
        color: sys("onSurface"),
        boxShadow: internal ? `inset 0 0 0 1px ${sys("tertiary")}` : "none",
        transition: "background-color var(--md-sys-motion-duration-short4) var(--md-sys-motion-easing-standard)",
      }}
    >
      <Stack direction="row" sx={{ alignItems: "center", gap: 1.5, mb: 1, flexWrap: "wrap" }}>
        <ToggleButtonGroup
          exclusive
          size="small"
          value={internal ? "note" : "reply"}
          onChange={(_, v) => v && onDraftChange({ ...draft, internal: v === "note" })}
          aria-label="Message type"
        >
          <ToggleButton value="reply" sx={{ px: 2 }}>
            Reply
          </ToggleButton>
          <ToggleButton value="note" sx={{ px: 2, gap: 0.5 }}>
            <LockOutlined sx={{ fontSize: 16 }} aria-hidden />
            Internal note
          </ToggleButton>
        </ToggleButtonGroup>
        <Typography variant="bodySmall" sx={{ color: internal ? sys("tertiary") : sys("onSurfaceVariant") }}>
          {internal
            ? "Only agents see internal notes."
            : locked
              ? "Closed: the customer's next reply starts a follow-up."
              : `Visible to ${ticket.requester_name}.`}
        </Typography>
      </Stack>
      {reply.isError ? (
        <Alert severity="error" variant="filled" sx={{ mb: 1, bgcolor: sys("errorContainer"), color: sys("onErrorContainer") }}>
          {errorMessage(reply.error, "That didn't send. Try again.")}
        </Alert>
      ) : null}
      <TextField
        value={draft.body}
        onChange={(e) => onDraftChange({ ...draft, body: e.target.value })}
        placeholder={internal ? "Add context for the team" : "Write a reply"}
        multiline
        minRows={3}
        maxRows={12}
        fullWidth
        slotProps={{ htmlInput: { "aria-label": internal ? "Internal note" : "Reply" } }}
        error={emptyTried && !draft.body.trim()}
        helperText={emptyTried && !draft.body.trim() ? "Write something first" : undefined}
        sx={{ "& .MuiOutlinedInput-root": { bgcolor: sys("surface") } }}
      />
      <Stack direction="row" sx={{ justifyContent: "flex-end", mt: 1 }}>
        <Button type="submit" variant="contained" disabled={reply.isPending}>
          {reply.isPending ? "Sending…" : internal ? "Add internal note" : "Send reply"}
        </Button>
      </Stack>
    </Box>
  );
}

export function AgentThread({ ticket }: { ticket: TicketDetail }) {
  return (
    <Box component="ol" aria-label="Conversation" sx={{ listStyle: "none", p: 0, m: 0, display: "grid", gap: 1 }}>
      <Message author={ticket.requester_name} role="Customer" at={ticket.created_at} body={ticket.description} internal={false} />
      {ticket.comments.map((c) => (
        <Message key={c.id} author={c.author_name} role={roleLabel(c)} at={c.created_at} body={c.body} internal={c.is_internal_note} />
      ))}
      {ticket.attachments.length ? (
        <Box component="li" sx={{ display: "flex", flexWrap: "wrap", gap: 1, pt: 0.5 }}>
          {ticket.attachments.map((a) => (
            <Button
              key={a.id}
              size="small"
              variant="outlined"
              startIcon={<AttachFileOutlined />}
              onClick={() => downloadAttachment(a.id, a.filename).catch(() => undefined)}
            >
              {a.filename}
            </Button>
          ))}
        </Box>
      ) : null}
    </Box>
  );
}
