import TrendingUpOutlined from "@mui/icons-material/TrendingUpOutlined";
import { Box, Button, Chip, Divider, ListItemText, MenuItem, Stack, TextField, Typography } from "@mui/material";
import { useAuth } from "../../auth/AuthContext";
import {
  useAddCollaborator,
  useCategories,
  useCategoryName,
  useOrganizations,
  useRemoveCollaborator,
  useStaff,
} from "../../api/hooks";
import type { TicketDetail, TicketPatch, TicketPriority } from "../../api/types";
import { SlaIndicator } from "../../components/SlaIndicator";
import { statusHint, statusOptions } from "../../lib/lifecycle";
import { PRIORITY_LABEL, STATUS_LABEL, absoluteTime } from "../../lib/tickets";
import { sys } from "../../theme/scheme";
import { ActionItemsSection } from "./ActionItemsSection";
import { AuditTrail } from "./AuditTrail";

const PRIORITIES: TicketPriority[] = ["urgent", "high", "normal", "low"];

function Due({ label, at, done }: { label: string; at: string | null; done: string | null }) {
  if (!at && !done) return null;
  return (
    <Stack direction="row" sx={{ justifyContent: "space-between", gap: 1 }}>
      <Typography variant="bodySmall" sx={{ color: sys("onSurfaceVariant") }}>
        {label}
      </Typography>
      <Typography variant="bodySmall" className="tabular">
        {done ?? (at ? absoluteTime(at) : "")}
      </Typography>
    </Stack>
  );
}

export function TicketSidePanel({
  ticket,
  onPatch,
  patching,
  onError,
}: {
  ticket: TicketDetail;
  onPatch: (p: TicketPatch) => void;
  patching: boolean;
  onError: (fallback: string) => (e: unknown) => void;
}) {
  const { user } = useAuth();
  const staff = useStaff();
  const categories = useCategories();
  const categoryName = useCategoryName();
  const organizations = useOrganizations();
  const addCollaborator = useAddCollaborator(ticket.id);
  const removeCollaborator = useRemoveCollaborator(ticket.id);
  const options = statusOptions(ticket.status, ticket.allowed_transitions, ticket.assignee_id);
  const locked = ticket.status === "closed";
  const canEscalate = !["resolved", "closed"].includes(ticket.status);
  const activeCategories = (categories.data ?? []).filter((c) => c.active || c.slug === ticket.category);
  const collaboratorIds = new Set(ticket.collaborators.map((c) => c.user_id));
  const addableStaff = (staff.data ?? []).filter(
    (u) => u.id !== ticket.assignee_id && !collaboratorIds.has(u.id),
  );

  return (
    <Stack spacing={2}>
      <Box>
        <SlaIndicator ticket={ticket} size="large" />
        <Stack spacing={0.25} sx={{ mt: 1.5 }}>
          <Due label="First reply due" at={ticket.sla_response_due} done={ticket.first_responded_at ? `Replied ${absoluteTime(ticket.first_responded_at)}` : null} />
          <Due label="Resolve by" at={ticket.sla_resolution_due} done={null} />
          {ticket.sla_paused_total_seconds > 0 ? (
            <Due label="Paused so far" at={null} done={`${Math.round(ticket.sla_paused_total_seconds / 60)} min`} />
          ) : null}
        </Stack>
      </Box>

      <Divider />

      <Stack spacing={1.5}>
        <TextField
          select
          label="Status"
          size="small"
          value={ticket.status}
          disabled={patching || options.length === 0}
          onChange={(e) => onPatch({ status: e.target.value as TicketDetail["status"] })}
          slotProps={{ select: { renderValue: (v) => STATUS_LABEL[v as TicketDetail["status"]] } }}
          helperText={
            options.length === 0
              ? "Closed tickets are read-only."
              : options.some((o) => o.disabledReason)
                ? "Assign someone before opening it."
                : undefined
          }
        >
          <MenuItem value={ticket.status} disabled>
            <ListItemText primary={STATUS_LABEL[ticket.status]} secondary="Current" />
          </MenuItem>
          {options.map((o) => (
            <MenuItem key={o.value} value={o.value} disabled={o.disabledReason !== null}>
              <ListItemText primary={`Move to ${o.label.toLowerCase()}`} secondary={o.disabledReason ?? statusHint(o.value)} />
            </MenuItem>
          ))}
        </TextField>

        <Stack direction="row" sx={{ gap: 1, alignItems: "flex-start" }}>
          <TextField
            select
            label="Assignee"
            size="small"
            fullWidth
            value={ticket.assignee_id ?? ""}
            disabled={patching || locked}
            onChange={(e) => onPatch({ assignee_id: e.target.value === "" ? null : Number(e.target.value) })}
            slotProps={{
              select: {
                displayEmpty: true,
                renderValue: (v) =>
                  v === "" ? "Unassigned" : ((staff.data ?? []).find((u) => u.id === v)?.name ?? ticket.assignee_name ?? ""),
              },
              inputLabel: { shrink: true },
            }}
          >
            <MenuItem value="">Unassigned</MenuItem>
            {(staff.data ?? []).map((u) => (
              <MenuItem key={u.id} value={u.id}>
                <ListItemText primary={u.name} secondary={u.team === "senior" ? "Senior" : u.role === "admin" ? "Admin" : "Tier 1"} />
              </MenuItem>
            ))}
          </TextField>
          {user && ticket.assignee_id !== user.id && !locked ? (
            <Button size="small" onClick={() => onPatch({ assignee_id: user.id })} disabled={patching} sx={{ flexShrink: 0, mt: 0.5 }}>
              Take it
            </Button>
          ) : null}
        </Stack>

        <Stack spacing={0.75}>
          {ticket.collaborators.length ? (
            <Stack direction="row" sx={{ gap: 0.5, flexWrap: "wrap" }}>
              {ticket.collaborators.map((c) => (
                <Chip
                  key={c.user_id}
                  size="small"
                  label={c.name}
                  disabled={locked || removeCollaborator.isPending}
                  onDelete={
                    !locked
                      ? () => removeCollaborator.mutate(c.user_id, { onError: onError("That collaborator couldn't be removed.") })
                      : undefined
                  }
                />
              ))}
            </Stack>
          ) : null}
          {!locked && addableStaff.length ? (
            <TextField
              select
              size="small"
              fullWidth
              value=""
              disabled={addCollaborator.isPending}
              onChange={(e) =>
                addCollaborator.mutate(Number(e.target.value), { onError: onError("That collaborator didn't save.") })
              }
              slotProps={{
                select: { displayEmpty: true, renderValue: () => "+ Add collaborator", "aria-label": "Add collaborator" },
              }}
            >
              {addableStaff.map((u) => (
                <MenuItem key={u.id} value={u.id}>
                  {u.name}
                </MenuItem>
              ))}
            </TextField>
          ) : null}
        </Stack>

        <Stack direction="row" sx={{ gap: 1 }}>
          <TextField
            select
            label="Priority"
            size="small"
            fullWidth
            value={ticket.priority}
            disabled={patching || locked}
            onChange={(e) => onPatch({ priority: e.target.value as TicketPriority })}
          >
            {PRIORITIES.map((p) => (
              <MenuItem key={p} value={p}>
                {PRIORITY_LABEL[p]}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            select
            label="Category"
            size="small"
            fullWidth
            value={ticket.category ?? ""}
            disabled={patching || locked}
            onChange={(e) => onPatch({ category: e.target.value === "" ? null : e.target.value })}
          >
            <MenuItem value="">None</MenuItem>
            {activeCategories.map((c) => (
              <MenuItem key={c.slug} value={c.slug}>
                {c.name}
              </MenuItem>
            ))}
          </TextField>
        </Stack>

        <TextField
          select
          label="Organisation"
          size="small"
          fullWidth
          value={ticket.organization_id ?? ""}
          disabled={patching || locked}
          onChange={(e) => onPatch({ organization_id: e.target.value === "" ? null : Number(e.target.value) })}
          slotProps={{
            select: {
              displayEmpty: true,
              renderValue: (v) =>
                v === ""
                  ? "None"
                  : ((organizations.data ?? []).find((o) => o.id === v)?.name ?? ticket.organization_name ?? ""),
            },
            inputLabel: { shrink: true },
          }}
        >
          <MenuItem value="">None</MenuItem>
          {(organizations.data ?? [])
            .filter((o) => o.active || o.id === ticket.organization_id)
            .map((o) => (
              <MenuItem key={o.id} value={o.id}>
                <ListItemText primary={o.name} secondary={o.kind === "government" ? "Government" : "Company"} />
              </MenuItem>
            ))}
        </TextField>

        <Box>
          <Button
            size="small"
            startIcon={<TrendingUpOutlined />}
            disabled={patching || !canEscalate}
            onClick={() => onPatch({ escalate: true })}
          >
            Escalate
          </Button>
          <Typography variant="bodySmall" sx={{ display: "block", mt: 0.5, color: sys("onSurfaceVariant") }}>
            {ticket.escalated
              ? "Escalated. Escalating again bumps priority once more."
              : canEscalate
                ? "Raises priority one level and reassigns to the senior team."
                : "Resolved and closed tickets can't be escalated."}
          </Typography>
        </Box>
      </Stack>

      <Divider />

      <ActionItemsSection ticket={ticket} />

      <Divider />

      <AuditTrail entries={ticket.audit_log} names={{ staff: staff.data, category: categoryName }} />
    </Stack>
  );
}
