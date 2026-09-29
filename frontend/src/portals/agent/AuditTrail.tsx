import ExpandMore from "@mui/icons-material/ExpandMore";
import { Accordion, AccordionDetails, AccordionSummary, Box, Typography } from "@mui/material";
import type { AuditEntry, User } from "../../api/types";
import { PRIORITY_LABEL, STATUS_LABEL, absoluteTime, relativeTime, ticketRef } from "../../lib/tickets";
import { sys } from "../../theme/scheme";

// Read after the actor's name: "Tara Tier1 updated", "System closed it after the reopen window".
const ACTION: Record<string, string> = {
  "ticket.created": "created the ticket",
  "ticket.created_from_reply": "created this from a reply to a closed ticket",
  "ticket.updated": "updated",
  "ticket.reopened_by_reply": "reopened it by replying",
  "ticket.auto_escalated": "escalated it because the SLA was at risk",
  "ticket.auto_closed": "closed it after the reopen window",
};

type Namer = { staff: User[] | undefined; category: (slug: string | null) => string | null };

function describe(key: string, value: unknown, names: Namer): string | null {
  switch (key) {
    case "status":
      return `Status ${STATUS_LABEL[value as keyof typeof STATUS_LABEL] ?? value}`;
    case "priority":
      return `Priority ${PRIORITY_LABEL[value as keyof typeof PRIORITY_LABEL] ?? value}`;
    case "category":
      return value ? `Category ${names.category(value as string)}` : "Category cleared";
    case "assignee_id":
      return value ? `Assigned to ${names.staff?.find((u) => u.id === value)?.name ?? `user ${value}`}` : "Unassigned";
    case "escalated":
      return value ? "Escalated" : null;
    case "parent_ticket_id":
      return `Follow-up to ${ticketRef(Number(value))}`;
    default:
      return null;
  }
}

export function AuditTrail({ entries, names }: { entries: AuditEntry[]; names: Namer }) {
  return (
    <Accordion
      disableGutters
      square
      sx={{ bgcolor: "transparent", "&::before": { display: "none" } }}
      slotProps={{ transition: { unmountOnExit: true } }}
    >
      <AccordionSummary expandIcon={<ExpandMore />} sx={{ px: 0, minHeight: 48 }}>
        <Typography variant="titleSmall" component="h2">
          History
        </Typography>
        <Typography variant="bodySmall" className="tabular" sx={{ ml: 1, color: sys("onSurfaceVariant"), alignSelf: "center" }}>
          {entries.length} {entries.length === 1 ? "change" : "changes"}
        </Typography>
      </AccordionSummary>
      <AccordionDetails sx={{ px: 0, pt: 0 }}>
        <Box component="ol" sx={{ listStyle: "none", p: 0, m: 0, display: "grid", gap: 1.5 }}>
          {[...entries].reverse().map((e) => {
            const after = (e.diff_json?.after ?? {}) as Record<string, unknown>;
            const details = Object.entries(after)
              .map(([k, v]) => describe(k, v, names))
              .filter(Boolean);
            return (
              <Box component="li" key={e.id} sx={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 0.25, columnGap: 1 }}>
                <Typography variant="bodyMedium">
                  <Box component="span" sx={{ fontWeight: 500 }}>
                    {e.actor_name ?? "System"}
                  </Box>{" "}
                  {ACTION[e.action] ?? e.action}
                </Typography>
                <Typography variant="bodySmall" component="time" dateTime={e.created_at} title={absoluteTime(e.created_at)} sx={{ color: sys("onSurfaceVariant") }}>
                  {relativeTime(e.created_at)}
                </Typography>
                {details.length ? (
                  <Typography variant="bodySmall" sx={{ gridColumn: "1 / -1", color: sys("onSurfaceVariant") }}>
                    {details.join(", ")}
                  </Typography>
                ) : null}
              </Box>
            );
          })}
        </Box>
      </AccordionDetails>
    </Accordion>
  );
}
