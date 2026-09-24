import type { TicketPriority, TicketStatus } from "../../api/types";

export const ACTIVE_STATUSES: TicketStatus[] = ["new", "triaged", "open", "in_progress", "pending"];
export const PAGE_SIZE = 50;

export type StatusFilter = "active" | "all" | TicketStatus;

export type QueueFilters = {
  status: StatusFilter;
  priority: TicketPriority | null;
  assignee: string | null; // "me" | "unassigned" | user id
  category: string | null;
  q: string;
  page: number;
};

/** The URL holds the queue's filter state (PLAN.md Phase 8), so views are
 * shareable and survive a reload. */
export function readFilters(params: URLSearchParams): QueueFilters {
  return {
    status: (params.get("status") as StatusFilter | null) ?? "active",
    priority: (params.get("priority") as TicketPriority | null) ?? null,
    assignee: params.get("assignee"),
    category: params.get("category"),
    q: params.get("q") ?? "",
    page: Math.max(1, Number(params.get("page") ?? 1) || 1),
  };
}

export function writeFilters(f: QueueFilters): URLSearchParams {
  const p = new URLSearchParams();
  if (f.status !== "active") p.set("status", f.status);
  if (f.priority) p.set("priority", f.priority);
  if (f.assignee) p.set("assignee", f.assignee);
  if (f.category) p.set("category", f.category);
  if (f.q) p.set("q", f.q);
  if (f.page > 1) p.set("page", String(f.page));
  return p;
}

export function apiQuery(f: QueueFilters): string {
  const p = new URLSearchParams();
  const statuses = f.status === "active" ? ACTIVE_STATUSES : f.status === "all" ? [] : [f.status];
  statuses.forEach((s) => p.append("status", s));
  if (f.priority) p.set("priority", f.priority);
  if (f.assignee) p.set("assignee", f.assignee);
  if (f.category) p.set("category", f.category);
  if (f.q) p.set("q", f.q);
  // Active work sorts by the next deadline; history by most recent change.
  p.set("sort", f.status === "resolved" || f.status === "closed" || f.status === "all" ? "-updated_at" : "sla_due");
  p.set("page", String(f.page));
  p.set("page_size", String(PAGE_SIZE));
  return p.toString();
}
