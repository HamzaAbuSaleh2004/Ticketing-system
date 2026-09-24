import type { TicketStatus } from "../api/types";
import { STATUS_LABEL } from "./tickets";

export type StatusOption = { value: TicketStatus; label: string; disabledReason: string | null };

const HINT: Partial<Record<TicketStatus, string>> = {
  pending: "Waiting on customer",
  resolved: "Customer can reopen by replying",
  closed: "Locked; replies start a follow-up",
};

/** The status control offers only the moves the API says are legal
 * (`allowed_transitions`), plus the one guard it enforces: `open` needs an
 * assignee. */
export function statusOptions(
  current: TicketStatus,
  allowed: TicketStatus[],
  assigneeId: number | null,
): StatusOption[] {
  return allowed.map((value) => ({
    value,
    label: STATUS_LABEL[value],
    disabledReason: current === "triaged" && value === "open" && assigneeId === null ? "Assign someone first" : null,
  }));
}

export const statusHint = (s: TicketStatus) => HINT[s] ?? null;
