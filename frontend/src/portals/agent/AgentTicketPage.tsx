import ArrowBackOutlined from "@mui/icons-material/ArrowBackOutlined";
import { Box, Button, Link, Skeleton, Snackbar, Stack, Typography, useMediaQuery } from "@mui/material";
import { useCallback, useMemo, useState } from "react";
import { Link as RouterLink, useParams, useSearchParams } from "react-router-dom";
import { errorMessage } from "../../api/client";
import { useAgentTicket, usePatchTicket } from "../../api/hooks";
import type { TicketPatch } from "../../api/types";
import { SectionCaption } from "../../components/SectionCaption";
import { OrganizationKindChip, PriorityChip, StatusChip } from "../../components/TicketChips";
import { absoluteTime, ticketRef } from "../../lib/tickets";
import { sys } from "../../theme/scheme";
import { Composer, AgentThread } from "./AgentThread";
import { ClaimCustomer } from "./ClaimCustomer";
import { TicketSidePanel } from "./TicketSidePanel";

const pane = { borderRadius: "var(--md-sys-shape-corner-small)", overflowY: "auto", minHeight: 0 } as const;

export function AgentTicketPage() {
  const id = Number(useParams().id);
  const [params] = useSearchParams();
  const search = params.size ? `?${params}` : "";
  const twoPane = useMediaQuery("(min-width:840px)", { noSsr: true });

  const { data: ticket, isLoading } = useAgentTicket(id);
  const patch = usePatchTicket(id);
  const [draft, setDraft] = useState({ body: "", internal: false });
  const [toast, setToast] = useState<string | null>(null);

  const onPatch = useCallback(
    (p: TicketPatch) => patch.mutate(p, { onError: (e) => setToast(errorMessage(e, "That change didn't save.")) }),
    [patch],
  );
  const onError = useCallback((fallback: string) => (e: unknown) => setToast(errorMessage(e, fallback)), []);
  const columns = useMemo(() => (twoPane ? "minmax(0,1fr) 360px" : "1fr"), [twoPane]);

  if (isLoading) {
    return (
      <Box sx={{ p: 3 }}>
        <Skeleton width={320} height={36} />
        <Skeleton variant="rounded" height={240} sx={{ mt: 2 }} />
      </Box>
    );
  }
  // Only when there's nothing to show: a failed background refetch keeps the
  // cached ticket on screen (and the agent's draft with it).
  if (!ticket) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography variant="titleLarge">That ticket doesn't exist</Typography>
        <Button component={RouterLink} to={`/agent${search}`} sx={{ mt: 2 }}>
          Back to the queue
        </Button>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        display: "grid",
        gridTemplateColumns: columns,
        gap: 1,
        p: 1,
        height: twoPane ? "100dvh" : "auto",
        bgcolor: sys("surface"),
      }}
    >
      <Box component="section" aria-label="Ticket" sx={{ ...pane, bgcolor: sys("surfaceContainerHigh"), p: 2, display: "flex", flexDirection: "column", gap: 1.5 }}>
        <Stack direction="row" sx={{ alignItems: "center", gap: 1 }}>
          <Button component={RouterLink} to={`/agent${search}`} size="small" startIcon={<ArrowBackOutlined />} sx={{ ml: -1 }}>
            Queue
          </Button>
          <Typography variant="labelLarge" className="tabular" sx={{ color: sys("onSurfaceVariant") }}>
            {ticketRef(ticket.id)}
          </Typography>
          <StatusChip status={ticket.status} />
          <PriorityChip priority={ticket.priority} />
          {ticket.escalated ? (
            <Typography variant="labelMedium" sx={{ color: sys("error") }}>
              Escalated
            </Typography>
          ) : null}
        </Stack>
        <Box>
          <Typography variant="titleLarge" component="h1" sx={{ overflowWrap: "anywhere" }}>
            {ticket.subject}
          </Typography>
          {ticket.organization_name ? (
            <Stack direction="row" sx={{ alignItems: "center", gap: 0.75, mt: 0.25 }}>
              <Typography variant="bodyMedium" sx={{ fontWeight: 500 }}>
                {ticket.organization_name}
              </Typography>
              {ticket.organization_kind ? <OrganizationKindChip kind={ticket.organization_kind} /> : null}
            </Stack>
          ) : null}
          {ticket.requester_name ? (
            <Typography variant="bodySmall" sx={{ color: sys("onSurfaceVariant") }}>
              Opened by {ticket.requester_name}, {ticket.requester_email}. Opened {absoluteTime(ticket.created_at)}
              {ticket.parent_ticket_id ? (
                <>
                  {". Follow-up to "}
                  <Link component={RouterLink} to={`/agent/tickets/${ticket.parent_ticket_id}${search}`} className="tabular">
                    {ticketRef(ticket.parent_ticket_id)}
                  </Link>
                </>
              ) : null}
            </Typography>
          ) : (
            <Box sx={{ mt: 0.5 }}>
              <ClaimCustomer ticketId={ticket.id} onError={setToast} />
            </Box>
          )}
        </Box>
        <Box
          component="section"
          aria-label="Description"
          sx={{ p: 1.5, borderRadius: "var(--md-sys-shape-corner-small)", border: `1px solid ${sys("outlineVariant")}` }}
        >
          <Box sx={{ mb: 0.5 }}>
            <SectionCaption>Description</SectionCaption>
          </Box>
          <Typography variant="bodyMedium" sx={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
            {ticket.description}
          </Typography>
        </Box>
        <AgentThread ticket={ticket} onError={() => setToast("That attachment couldn't be opened.")} />
        <Box sx={{ mt: "auto", pt: 1 }}>
          <Composer ticket={ticket} draft={draft} onDraftChange={setDraft} />
        </Box>
      </Box>

      <Box component="aside" aria-label="Ticket properties" sx={{ ...pane, bgcolor: sys("surfaceContainerLow"), p: 2 }}>
        <TicketSidePanel ticket={ticket} onPatch={onPatch} patching={patch.isPending} onError={onError} />
      </Box>

      <Snackbar open={toast !== null} autoHideDuration={5000} onClose={() => setToast(null)} message={toast} />
    </Box>
  );
}
