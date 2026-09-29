import type { TicketPriority, TicketStatus } from "../api/types";

export const ticketRef = (id: number) => `TCK-${String(id).padStart(5, "0")}`;

export const STATUS_LABEL: Record<TicketStatus, string> = {
  new: "New",
  triaged: "Triaged",
  open: "Open",
  in_progress: "In progress",
  pending: "Pending",
  resolved: "Resolved",
  closed: "Closed",
};

export const PRIORITY_LABEL: Record<TicketPriority, string> = {
  low: "Low priority",
  normal: "Normal priority",
  high: "High priority",
  urgent: "Urgent",
};

export const PRIORITY_SHORT: Record<TicketPriority, string> = { urgent: "Urgent", high: "High", normal: "Normal", low: "Low" };

/** The end-user portal speaks in what's happening, not in workflow states. */
export const CUSTOMER_STATUS: Record<TicketStatus, { label: string; line: string }> = {
  new: { label: "Received", line: "We're reviewing this" },
  triaged: { label: "Received", line: "Queued for the right team" },
  open: { label: "In progress", line: "An agent has picked this up" },
  in_progress: { label: "In progress", line: "An agent is working on it" },
  pending: { label: "Waiting on you", line: "We need a reply from you to continue" },
  resolved: { label: "Resolved", line: "Reply if it isn't fixed" },
  closed: { label: "Closed", line: "Replying starts a new request" },
};

export type ReplyMode = { hint: string | null; action: string; startsNew: boolean };

/** What a customer's reply will do, so the reply box can say so up front.
 * Mirrors backend domain/lifecycle.customer_reply_outcome; the window comes
 * from the API (`reopen_until`), so it follows RESOLVED_COOLOFF_HOURS. */
export function replyMode(
  status: TicketStatus,
  resolvedAt: string | null,
  reopenUntil: string | null,
  now: Date = new Date(),
): ReplyMode {
  if (status === "closed") {
    return { hint: "This request is closed. Replying starts a new request.", action: "Start a new request", startsNew: true };
  }
  if (status === "resolved") {
    const within = reopenUntil !== null && now.getTime() <= new Date(reopenUntil).getTime();
    const hours =
      resolvedAt && reopenUntil ? Math.round((new Date(reopenUntil).getTime() - new Date(resolvedAt).getTime()) / 3_600_000) : null;
    return within
      ? { hint: `Reply within ${hours}h to reopen this request.`, action: "Reopen with reply", startsNew: false }
      : { hint: "The reopen window has passed, so replying starts a new request.", action: "Start a new request", startsNew: true };
  }
  if (status === "pending") {
    return { hint: "We're waiting on your reply to continue.", action: "Send reply", startsNew: false };
  }
  return { hint: null, action: "Send reply", startsNew: false };
}

const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 365 * 86_400],
  ["month", 30 * 86_400],
  ["week", 7 * 86_400],
  ["day", 86_400],
  ["hour", 3600],
  ["minute", 60],
];

export function relativeTime(iso: string, now: Date = new Date()): string {
  const seconds = (new Date(iso).getTime() - now.getTime()) / 1000;
  for (const [unit, size] of UNITS) {
    if (Math.abs(seconds) >= size) return rtf.format(Math.round(seconds / size), unit);
  }
  return "just now";
}

/** "3m", "5h", "2d": for dense columns already headed "Updated". */
export function compactAgo(iso: string, now: Date = new Date()): string {
  const s = Math.max(0, (now.getTime() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "now";
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86_400) return `${Math.floor(s / 3600)}h`;
  if (s < 30 * 86_400) return `${Math.floor(s / 86_400)}d`;
  return new Date(iso).toLocaleDateString("en", { month: "short", day: "numeric" });
}

export const absoluteTime = (iso: string) =>
  new Date(iso).toLocaleString("en", { dateStyle: "medium", timeStyle: "short" });

/** "Customer 2", "LiverX 1", "Customer 1, LiverX 2", or null when nothing's
 * open on either side — as text, not colour alone, per the brief's queue rule. */
export function waitingOnText(openCustomerItems: number, openLiverxItems: number): string | null {
  const parts: string[] = [];
  if (openCustomerItems > 0) parts.push(`Customer ${openCustomerItems}`);
  if (openLiverxItems > 0) parts.push(`LiverX ${openLiverxItems}`);
  return parts.length ? parts.join(", ") : null;
}
