import ArrowBackOutlined from "@mui/icons-material/ArrowBackOutlined";
import AttachFileOutlined from "@mui/icons-material/AttachFileOutlined";
import { Alert, Box, Button, CircularProgress, Link, Skeleton, Snackbar, Stack, TextField, Typography } from "@mui/material";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link as RouterLink, useLocation, useNavigate, useParams } from "react-router-dom";
import { errorMessage } from "../../api/client";
import { useCategoryName, useReply, useTicket } from "../../api/hooks";
import type { Comment, TicketDetailPublic } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { downloadAttachment } from "../../lib/download";
import { PRIORITY_LABEL, absoluteTime, relativeTime, replyMode, ticketRef } from "../../lib/tickets";
import { sys } from "../../theme/scheme";
import { typescale } from "../../theme/tokens";
import { CustomerStatusChip } from "./CustomerStatusChip";

const TRIAGE_POLL_MS = 3000;
const TRIAGE_POLL_FOR_MS = 30_000;

function InfoChip({ children }: { children: string }) {
  return (
    <Box
      component="span"
      sx={{
        display: "inline-flex",
        alignItems: "center",
        height: 28,
        px: 1.5,
        borderRadius: "var(--md-sys-shape-corner-full)",
        border: `1px solid ${sys("outlineVariant")}`,
        color: sys("onSurfaceVariant"),
        ...typescale("label-large"),
      }}
    >
      {children}
    </Box>
  );
}

function Message({ author, at, body, fromSupport }: { author: string; at: string; body: string; fromSupport: boolean }) {
  return (
    <Box
      component="li"
      sx={{
        p: { xs: 2, sm: 2.5 },
        borderRadius: "var(--md-sys-shape-corner-large)",
        bgcolor: fromSupport ? sys("surfaceContainerLow") : "transparent",
        border: fromSupport ? "none" : `1px solid ${sys("outlineVariant")}`,
      }}
    >
      <Stack direction="row" sx={{ alignItems: "baseline", justifyContent: "space-between", gap: 2, mb: 0.75 }}>
        <Typography variant="titleSmall" component="span">
          {author}
        </Typography>
        <Typography variant="bodySmall" component="time" dateTime={at} title={absoluteTime(at)} sx={{ color: sys("onSurfaceVariant"), flexShrink: 0 }}>
          {relativeTime(at)}
        </Typography>
      </Stack>
      <Typography variant="bodyLarge" sx={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
        {body}
      </Typography>
    </Box>
  );
}

function authorLabel(c: Comment, myId: number | undefined) {
  if (c.author_id === myId) return "You";
  return c.author_role === "end_user" ? c.author_name : `${c.author_name.split(" ")[0]} from Support`;
}

function TriageNotice({ ticket, pollingStopped }: { ticket: TicketDetailPublic; pollingStopped: boolean }) {
  if (ticket.status !== "new") return null;
  return (
    <Box
      role="status"
      sx={{ display: "flex", gap: 2, alignItems: "center", p: 2, mb: 3, borderRadius: "var(--md-sys-shape-corner-large)", bgcolor: sys("surfaceContainerLow") }}
    >
      {pollingStopped ? null : <CircularProgress size={20} aria-hidden sx={{ color: sys("primary") }} />}
      <Typography variant="bodyMedium">
        {pollingStopped
          ? "We're still reviewing this. It's safe to leave; we'll reply here."
          : "We're reviewing this and routing it to the right team."}
      </Typography>
    </Box>
  );
}

function ReplyBox({ ticket }: { ticket: TicketDetailPublic }) {
  const navigate = useNavigate();
  const reply = useReply(ticket.id);
  const [body, setBody] = useState("");
  const [emptyTried, setEmptyTried] = useState(false);
  const mode = replyMode(ticket.status, ticket.resolved_at, ticket.reopen_until);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!body.trim()) {
      setEmptyTried(true);
      return;
    }
    setEmptyTried(false);
    reply.mutate(
      { body: body.trim() },
      {
        // Failures render from reply.isError; mutate() doesn't reject.
        onSuccess: (result) => {
          setBody("");
          if (result.follow_up_ticket_id) {
            navigate(`/requests/${result.follow_up_ticket_id}`, { state: { followUpOf: ticket.id } });
          }
        },
      },
    );
  }

  return (
    <Box
      component="form"
      onSubmit={onSubmit}
      aria-label="Reply"
      sx={{ mt: 4, p: { xs: 2, sm: 3 }, borderRadius: "var(--md-sys-shape-corner-extra-large)", bgcolor: sys("surfaceContainerLow") }}
    >
      {mode.hint ? (
        <Typography variant="bodyMedium" sx={{ mb: 2, color: ticket.status === "pending" ? sys("tertiary") : sys("onSurfaceVariant") }}>
          {mode.hint}
        </Typography>
      ) : null}
      {reply.isError ? (
        <Alert severity="error" variant="filled" sx={{ mb: 2, bgcolor: sys("errorContainer"), color: sys("onErrorContainer") }}>
          {errorMessage(reply.error, "Your reply didn't send. Try again.")}
        </Alert>
      ) : null}
      <TextField
        label="Your reply"
        value={body}
        onChange={(e) => setBody(e.target.value)}
        multiline
        minRows={3}
        fullWidth
        error={emptyTried && !body.trim()}
        helperText={emptyTried && !body.trim() ? "Write a reply first" : undefined}
        sx={{ "& .MuiOutlinedInput-root": { bgcolor: sys("surface") } }}
      />
      <Button type="submit" variant="contained" sx={{ mt: 2 }} disabled={reply.isPending}>
        {reply.isPending ? "Sending…" : mode.action}
      </Button>
    </Box>
  );
}

export function RequestPage() {
  const id = Number(useParams().id);
  const { user } = useAuth();
  const location = useLocation();
  const navState = (location.state ?? {}) as { justCreated?: boolean; attachmentFailed?: boolean; followUpOf?: number };
  const categoryName = useCategoryName();

  // Poll every 3s for up to 30s while triage hasn't landed yet; after that,
  // refetch-on-focus (the query default) keeps it fresh.
  const startedAt = useRef(Date.now());
  const [pollingStopped, setPollingStopped] = useState(false);
  const { data: ticket, isLoading, error } = useTicket(id, (t) =>
    t?.status === "new" && !pollingStopped ? TRIAGE_POLL_MS : false,
  );
  const stillNew = ticket?.status === "new";

  useEffect(() => {
    if (!stillNew || pollingStopped) return;
    const remaining = TRIAGE_POLL_FOR_MS - (Date.now() - startedAt.current);
    const timer = window.setTimeout(() => setPollingStopped(true), Math.max(remaining, 0));
    return () => window.clearTimeout(timer);
  }, [stillNew, pollingStopped]);

  // Router state survives reloads; clear it once read so the toast shows once.
  const navigate = useNavigate();
  useEffect(() => {
    if (location.state) navigate(location.pathname, { replace: true, state: null });
  }, [location.state, location.pathname, navigate]);

  const [toast, setToast] = useState<string | null>(
    navState.followUpOf
      ? `Started a new request, linked to ${ticketRef(navState.followUpOf)}`
      : navState.attachmentFailed
        ? "Request sent, but the attachment didn't upload. Add it in a reply."
        : navState.justCreated
          ? "Request sent"
          : null,
  );

  if (isLoading) {
    return (
      <Box sx={{ pt: 6 }} aria-busy="true">
        <Skeleton width="60%" height={48} />
        <Skeleton width="30%" />
        <Skeleton variant="rounded" height={120} sx={{ mt: 3, borderRadius: "var(--md-sys-shape-corner-large)" }} />
      </Box>
    );
  }
  if (error || !ticket) {
    return (
      <Box sx={{ pt: 6 }}>
        <Typography variant="headlineMedium" component="h1">
          We can't find that request
        </Typography>
        <Typography variant="bodyLarge" sx={{ my: 2, color: sys("onSurfaceVariant") }}>
          It may belong to another account, or the link is wrong.
        </Typography>
        <Button component={RouterLink} to="/" variant="contained">
          Go to your requests
        </Button>
      </Box>
    );
  }

  const category = categoryName(ticket.category);
  const triaged = ticket.status !== "new";

  return (
    <Box sx={{ pt: { xs: 2, sm: 4 } }}>
      <Button component={RouterLink} to="/" startIcon={<ArrowBackOutlined />} sx={{ ml: -1.5, mb: 2 }}>
        Your requests
      </Button>

      <Typography variant="labelLarge" component="p" className="tabular" sx={{ color: sys("onSurfaceVariant") }}>
        {ticketRef(ticket.id)}
      </Typography>
      <Typography variant="headlineMedium" component="h1" sx={{ mt: 0.5, overflowWrap: "anywhere" }}>
        {ticket.subject}
      </Typography>

      <Stack direction="row" aria-live="polite" sx={{ flexWrap: "wrap", gap: 1, mt: 2, mb: 3 }}>
        <CustomerStatusChip status={ticket.status} />
        {triaged && category ? <InfoChip>{category}</InfoChip> : null}
        {triaged ? <InfoChip>{PRIORITY_LABEL[ticket.priority]}</InfoChip> : null}
      </Stack>

      {ticket.parent_ticket_id ? (
        <Typography variant="bodyMedium" sx={{ mb: 2, color: sys("onSurfaceVariant") }}>
          Follow-up to{" "}
          <Link component={RouterLink} to={`/requests/${ticket.parent_ticket_id}`} className="tabular">
            {ticketRef(ticket.parent_ticket_id)}
          </Link>
        </Typography>
      ) : null}

      <TriageNotice ticket={ticket} pollingStopped={pollingStopped} />

      <Box component="ol" aria-label="Conversation" sx={{ listStyle: "none", p: 0, m: 0, display: "grid", gap: 1.5 }}>
        <Message author="You" at={ticket.created_at} body={ticket.description} fromSupport={false} />
        {ticket.comments.map((c) => (
          <Message key={c.id} author={authorLabel(c, user?.id)} at={c.created_at} body={c.body} fromSupport={c.author_role !== "end_user"} />
        ))}
      </Box>

      {ticket.attachments.length ? (
        <Box sx={{ mt: 3 }}>
          <Typography variant="titleSmall" component="h2" sx={{ mb: 1 }}>
            Attachments
          </Typography>
          <Stack direction="row" sx={{ flexWrap: "wrap", gap: 1 }}>
            {ticket.attachments.map((a) => (
              <Button
                key={a.id}
                variant="outlined"
                startIcon={<AttachFileOutlined />}
                onClick={() => downloadAttachment(a.id, a.filename).catch(() => setToast("That file couldn't be downloaded."))}
              >
                {a.filename}
              </Button>
            ))}
          </Stack>
        </Box>
      ) : null}

      <ReplyBox ticket={ticket} />

      <Snackbar open={toast !== null} autoHideDuration={5000} onClose={() => setToast(null)} message={toast} />
    </Box>
  );
}
