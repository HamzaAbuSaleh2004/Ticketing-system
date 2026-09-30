import LockOutlined from "@mui/icons-material/LockOutlined";
import { Alert, Box, Button, Stack, TextField, ToggleButton, ToggleButtonGroup, Typography } from "@mui/material";
import { useState, type FormEvent, type KeyboardEvent } from "react";
import { errorMessage } from "../../api/client";
import { useReply } from "../../api/hooks";
import type { Comment, TicketDetail } from "../../api/types";
import { AttachmentList } from "../../components/AttachmentList";
import { SectionCaption } from "../../components/SectionCaption";
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

  function send() {
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

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    send();
  }

  // Enter sends, Shift+Enter inserts a newline - the standard convention.
  // isComposing excludes the Enter that confirms an IME composition (CJK
  // input); isPending stops a held/repeated Enter from sending twice before
  // the first request resolves and clears the draft.
  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      if (!reply.isPending) send();
    }
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
              : ticket.requester_name
                ? `Visible to ${ticket.requester_name}.`
                : "No customer linked yet: they won't see this until one is."}
        </Typography>
      </Stack>
      {reply.isError ? (
        <Alert severity="error" variant="filled" sx={{ mb: 1, bgcolor: sys("errorContainer"), color: sys("onErrorContainer") }}>
          {errorMessage(reply.error, "That didn't send. Try again.")}
        </Alert>
      ) : null}
      <Stack direction="row" sx={{ gap: 1, alignItems: "flex-end" }}>
        <TextField
          value={draft.body}
          onChange={(e) => onDraftChange({ ...draft, body: e.target.value })}
          onKeyDown={onKeyDown}
          placeholder={internal ? "Add context for the team" : "Write a reply"}
          multiline
          minRows={3}
          maxRows={24}
          fullWidth
          slotProps={{ htmlInput: { "aria-label": internal ? "Internal note" : "Reply" } }}
          error={emptyTried && !draft.body.trim()}
          helperText={emptyTried && !draft.body.trim() ? "Write something first" : "Enter to send, Shift+Enter for a new line"}
          sx={{ "& .MuiOutlinedInput-root": { bgcolor: sys("surface") } }}
        />
        <Button type="submit" variant="contained" disabled={reply.isPending} sx={{ flexShrink: 0 }}>
          {reply.isPending ? "Sending…" : internal ? "Add internal note" : "Send reply"}
        </Button>
      </Stack>
    </Box>
  );
}

export function AgentThread({ ticket, onError }: { ticket: TicketDetail; onError?: () => void }) {
  return (
    <Box sx={{ display: "grid", gap: 1 }}>
      <SectionCaption>Conversation</SectionCaption>
      <Box component="ol" aria-label="Conversation" sx={{ listStyle: "none", p: 0, m: 0, display: "grid", gap: 1 }}>
        {ticket.comments.length === 0 ? (
          <Typography component="li" variant="bodyMedium" sx={{ color: sys("onSurfaceVariant"), listStyle: "none" }}>
            No replies yet.
          </Typography>
        ) : (
          ticket.comments.map((c) => (
            <Message key={c.id} author={c.author_name} role={roleLabel(c)} at={c.created_at} body={c.body} internal={c.is_internal_note} />
          ))
        )}
        {ticket.attachments.length ? (
          <Box component="li" sx={{ pt: 0.5 }}>
            <AttachmentList attachments={ticket.attachments} onError={onError} />
          </Box>
        ) : null}
      </Box>
    </Box>
  );
}
