export type Role = "end_user" | "agent" | "admin";
export type Team = "tier1" | "senior";

export type User = {
  id: number;
  email: string;
  name: string;
  role: Role;
  team: Team | null;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

export type TicketStatus = "new" | "triaged" | "open" | "in_progress" | "pending" | "resolved" | "closed";
export type TicketPriority = "low" | "normal" | "high" | "urgent";

export type Category = { id: number; name: string; slug: string; active: boolean };

export type TicketListItem = {
  id: number;
  subject: string;
  status: TicketStatus;
  priority: TicketPriority;
  category: string | null;
  requester_id: number;
  assignee_id: number | null;
  escalated: boolean;
  ai_summary: string | null;
  sla_response_due: string | null;
  sla_resolution_due: string | null;
  created_at: string;
  updated_at: string;
};

export type TicketList = { items: TicketListItem[]; total: number; page: number; page_size: number };

export type Comment = {
  id: number;
  ticket_id: number;
  author_id: number;
  author_name: string;
  author_role: Role;
  body: string;
  is_internal_note: boolean;
  created_at: string;
};

export type Attachment = {
  id: number;
  comment_id: number | null;
  filename: string;
  content_type: string;
  created_at: string;
};

export type TicketDetailPublic = TicketListItem & {
  description: string;
  sla_paused_at: string | null;
  first_responded_at: string | null;
  parent_ticket_id: number | null;
  resolved_at: string | null;
  closed_at: string | null;
  reopen_until: string | null;
  comments: Comment[];
  attachments: Attachment[];
};

export type CommentCreateResult = { comment: Comment | null; follow_up_ticket_id: number | null };

export type KbSource = { id: number; title: string; slug: string; snippet: string };
export type KbSearchResult = { answer: string | null; sources: KbSource[] };
export type KbArticle = { id: number; title: string; slug: string; body: string; tags: string[]; updated_at: string };
