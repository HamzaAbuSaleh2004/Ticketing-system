import type { TicketStatus } from "../api/types";

export type SlaState = "on_track" | "at_risk" | "breached" | "paused" | "none";

export type SlaInput = {
  status: TicketStatus;
  created_at: string;
  sla_response_due: string | null;
  sla_resolution_due: string | null;
  sla_paused_at: string | null;
  sla_paused_total_seconds: number;
  first_responded_at: string | null;
};

export type SlaView = {
  state: SlaState;
  clock: "response" | "resolution" | null;
  /** Time left (negative once breached); frozen at the pause point while paused. */
  remainingMs: number;
  /** Share of the window still left, 0..1, for the ring. */
  fraction: number;
  countdown: string;
  stateLabel: string | null;
  description: string;
};

const AT_RISK_FRACTION = 0.25; // Mirrors backend domain/sla.is_at_risk.
const MIN = 60_000;
const HOUR = 60 * MIN;
const DAY = 24 * HOUR;

export function formatDuration(ms: number): string {
  const abs = Math.abs(ms);
  if (abs >= DAY) return `${Math.floor(abs / DAY)}d ${Math.floor((abs % DAY) / HOUR)}h`;
  if (abs >= HOUR) return `${Math.floor(abs / HOUR)}h ${String(Math.floor((abs % HOUR) / MIN)).padStart(2, "0")}m`;
  if (abs >= MIN) return `${Math.floor(abs / MIN)}m`;
  return "<1m";
}

const STATE_LABEL: Record<SlaState, string | null> = {
  on_track: null,
  at_risk: "At risk",
  breached: "Breached",
  paused: "Paused",
  none: null,
};

/** Which SLA clock matters now and how it's doing. The response clock runs
 * until the first public agent reply and never pauses; after that the
 * resolution clock runs, paused while pending (PLAN.md §3). */
export function slaView(t: SlaInput, now: number): SlaView {
  const none: SlaView = { state: "none", clock: null, remainingMs: 0, fraction: 0, countdown: "", stateLabel: null, description: "No SLA running" };
  if (t.status === "resolved" || t.status === "closed") return none;

  const created = Date.parse(t.created_at);
  let clock: "response" | "resolution";
  let due: number;
  let windowMs: number;
  let paused = false;

  if (t.first_responded_at === null && t.sla_response_due) {
    clock = "response";
    due = Date.parse(t.sla_response_due);
    windowMs = due - created;
  } else if (t.sla_resolution_due) {
    clock = "resolution";
    due = Date.parse(t.sla_resolution_due);
    windowMs = due - created - t.sla_paused_total_seconds * 1000;
    paused = t.sla_paused_at !== null;
  } else {
    return none;
  }

  const reference = paused ? Date.parse(t.sla_paused_at as string) : now;
  const remainingMs = due - reference;
  const fraction = windowMs > 0 ? Math.min(Math.max(remainingMs / windowMs, 0), 1) : 0;
  const state: SlaState = paused
    ? "paused"
    : remainingMs < 0
      ? "breached"
      : fraction < AT_RISK_FRACTION
        ? "at_risk"
        : "on_track";

  const countdown = remainingMs < 0 ? `${formatDuration(remainingMs)} over` : formatDuration(remainingMs);
  const what = clock === "response" ? "First reply" : "Resolution";
  const description =
    state === "paused"
      ? `${what} clock paused while waiting on the customer, ${formatDuration(remainingMs)} left`
      : state === "breached"
        ? `${what} overdue by ${formatDuration(remainingMs)}`
        : `${what} due in ${countdown}${state === "at_risk" ? ", at risk" : ""}`;

  return { state, clock, remainingMs, fraction, countdown, stateLabel: STATE_LABEL[state], description };
}
