import AutoAwesomeOutlined from "@mui/icons-material/AutoAwesomeOutlined";
import Check from "@mui/icons-material/Check";
import { Box, Button, Stack, Tooltip, Typography } from "@mui/material";
import type { FieldDecision, TicketDetail, TicketPatch, TriageField } from "../../api/types";
import { PRIORITY_LABEL, relativeTime } from "../../lib/tickets";
import { sys } from "../../theme/scheme";

const DECISION_LABEL: Record<FieldDecision | "changed", string> = {
  auto: "Applied",
  accepted: "Accepted",
  overridden: "Overridden",
  changed: "Changed since",
};

function Row({
  label,
  value,
  field,
  decision,
  matchesCurrent,
  onAccept,
  busy,
}: {
  label: string;
  value: string;
  field: TriageField;
  decision: FieldDecision | undefined;
  matchesCurrent: boolean;
  onAccept: (f: TriageField) => void;
  busy: boolean;
}) {
  // An applied/accepted suggestion that no longer matches the field (e.g.
  // escalation bumped the priority) mustn't still claim to be in effect.
  const shown = decision && decision !== "overridden" && !matchesCurrent ? "changed" : decision;
  const accepted = shown === "accepted";
  return (
    <Box sx={{ display: "grid", gridTemplateColumns: "72px minmax(0,1fr) auto", alignItems: "center", gap: 1, minHeight: 40 }}>
      <Typography variant="labelMedium" sx={{ color: sys("onSurfaceVariant") }}>
        {label}
      </Typography>
      <Typography variant="bodyMedium" sx={{ overflowWrap: "anywhere" }}>
        {value}
      </Typography>
      <Stack direction="row" sx={{ alignItems: "center", gap: 0.5, justifyContent: "flex-end" }}>
        {shown ? (
          <Typography
            variant="labelMedium"
            sx={{ display: "inline-flex", alignItems: "center", gap: 0.25, color: accepted ? sys("primary") : sys("onSurfaceVariant") }}
          >
            {accepted ? <Check sx={{ fontSize: 16 }} aria-hidden /> : null}
            {DECISION_LABEL[shown]}
          </Typography>
        ) : null}
        {!accepted ? (
          <Tooltip title={matchesCurrent ? "Confirm the suggestion" : "Apply the suggestion (or change the field above to override it)"}>
            <span>
              <Button size="small" variant="text" disabled={busy} onClick={() => onAccept(field)} aria-label={`Accept suggested ${label.toLowerCase()}`}>
                Accept
              </Button>
            </span>
          </Tooltip>
        ) : null}
      </Stack>
    </Box>
  );
}

export function AiTriagePanel({
  ticket,
  categoryName,
  onPatch,
  onUseDraft,
  onRerun,
  busy,
  rerunning,
}: {
  ticket: TicketDetail;
  categoryName: (slug: string | null) => string | null;
  onPatch: (p: TicketPatch) => void;
  onUseDraft: (draft: string) => void;
  onRerun: () => void;
  busy: boolean;
  rerunning: boolean;
}) {
  const t = ticket.ai_triage;
  const header = (
    <Stack direction="row" sx={{ alignItems: "center", gap: 1, mb: 1 }}>
      <AutoAwesomeOutlined sx={{ fontSize: 18, color: sys("primary") }} aria-hidden />
      <Typography variant="titleSmall" component="h2" sx={{ flex: 1 }}>
        AI triage
      </Typography>
      <Button size="small" onClick={onRerun} disabled={rerunning}>
        {rerunning ? "Running…" : t ? "Re-run" : "Run triage"}
      </Button>
    </Stack>
  );

  if (!t) {
    return (
      <Box>
        {header}
        <Typography variant="bodyMedium" sx={{ color: sys("onSurfaceVariant") }}>
          {ticket.status === "new" ? "Triage is on its way." : "No suggestion yet."}
        </Typography>
      </Box>
    );
  }

  const s = t.suggestion;
  const d = t.accepted_fields;
  const accept = (field: TriageField) => onPatch({ ai_accept: [field] });

  return (
    <Box>
      {header}
      <Typography variant="bodySmall" sx={{ color: sys("onSurfaceVariant"), display: "block", mb: 1 }}>
        {t.model === "fake-fallback"
          ? "Gemini was unavailable, so this came from the keyword fallback."
          : `Suggested ${relativeTime(t.generated_at)} by ${t.model}`}
      </Typography>
      <Row label="Category" field="category" value={categoryName(s.category) ?? s.category} decision={d.category} matchesCurrent={ticket.category === s.category} onAccept={accept} busy={busy} />
      <Row label="Priority" field="priority" value={PRIORITY_LABEL[s.priority]} decision={d.priority} matchesCurrent={ticket.priority === s.priority} onAccept={accept} busy={busy} />
      <Row label="Summary" field="one_line_summary" value={s.one_line_summary} decision={d.one_line_summary} matchesCurrent={ticket.ai_summary === s.one_line_summary} onAccept={accept} busy={busy} />

      <Box sx={{ mt: 1.5, p: 1.5, borderRadius: "var(--md-sys-shape-corner-small)", bgcolor: sys("surfaceContainerLowest") }}>
        <Stack direction="row" sx={{ alignItems: "center", mb: 0.5 }}>
          <Typography variant="labelMedium" sx={{ color: sys("onSurfaceVariant"), flex: 1 }}>
            Draft reply
          </Typography>
          {d.suggested_response_draft === "accepted" ? (
            <Typography variant="labelMedium" sx={{ color: sys("primary"), display: "inline-flex", alignItems: "center", gap: 0.25 }}>
              <Check sx={{ fontSize: 16 }} aria-hidden />
              Used
            </Typography>
          ) : null}
        </Stack>
        <Typography variant="bodyMedium" sx={{ display: "-webkit-box", WebkitLineClamp: 4, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
          {s.suggested_response_draft}
        </Typography>
        <Button
          variant="tonal"
          size="small"
          sx={{ mt: 1 }}
          onClick={() => {
            onUseDraft(s.suggested_response_draft);
            if (d.suggested_response_draft !== "accepted") onPatch({ ai_accept: ["suggested_response_draft"] });
          }}
        >
          Use draft
        </Button>
      </Box>
    </Box>
  );
}
