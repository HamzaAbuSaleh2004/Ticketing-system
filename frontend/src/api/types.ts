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

/** The password step's answer: a code (or first-time setup) comes next. */
export type MfaChallenge = { mfa_token: string; mfa: "enroll" | "verify" };
export type MfaSetup = { secret: string; otpauth_uri: string; qr_svg_data_uri: string };
export type MfaEnabled = TokenResponse & { recovery_codes: string[] };

export type TicketStatus = "open" | "in_progress" | "pending" | "resolved" | "closed";
export type TicketPriority = "low" | "normal" | "high" | "urgent";

export type Category = { id: number; name: string; slug: string; active: boolean };

export type OrganizationKind = "company" | "government";
export type Organization = { id: number; name: string; kind: OrganizationKind; active: boolean };

export type ActionItemSide = "customer" | "liverx";
export type ActionItem = {
  id: number;
  side: ActionItemSide;
  description: string;
  done: boolean;
  created_by: number;
  created_at: string;
  done_at: string | null;
  done_by: number | null;
  done_by_name: string | null;
};

export type TicketListItem = {
  id: number;
  subject: string;
  status: TicketStatus;
  priority: TicketPriority;
  category: string | null;
  // null: "unclaimed" (staff-created for a customer with no account yet).
  requester_id: number | null;
  assignee_id: number | null;
  escalated: boolean;
  created_at: string;
  updated_at: string;
  organization_id: number | null;
  organization_name: string | null;
  organization_kind: OrganizationKind | null;
  open_customer_items: number;
  open_liverx_items: number;
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
  first_responded_at: string | null;
  parent_ticket_id: number | null;
  resolved_at: string | null;
  closed_at: string | null;
  reopen_until: string | null;
  comments: Comment[];
  attachments: Attachment[];
  action_items: ActionItem[];
};

export type Collaborator = { user_id: number; name: string };

export type TicketQueueItem = TicketListItem & {
  requester_name: string | null;
  assignee_name: string | null;
  first_responded_at: string | null;
  collaborators: Collaborator[];
};

export type TicketQueue = { items: TicketQueueItem[]; total: number; page: number; page_size: number };

export type AuditEntry = {
  id: number;
  actor_id: number | null;
  actor_name: string | null;
  action: string;
  diff_json: { before?: Record<string, unknown>; after?: Record<string, unknown>; [k: string]: unknown } | null;
  created_at: string;
};

export type TicketDetail = TicketDetailPublic & {
  requester_name: string | null;
  requester_email: string | null;
  assignee_name: string | null;
  collaborators: Collaborator[];
  audit_log: AuditEntry[];
  allowed_transitions: TicketStatus[];
};

export type TicketPatch = Partial<{
  status: TicketStatus;
  assignee_id: number | null;
  priority: TicketPriority;
  category: string | null;
  organization_id: number | null;
  requester_id: number;
  escalate: boolean;
}>;

export type CustomerSearchResult = {
  id: number;
  name: string;
  email: string;
  organization_id: number | null;
  organization_name: string | null;
};

export type CommentCreateResult = { comment: Comment | null; follow_up_ticket_id: number | null };

export type KbResult = { id: number; title: string; slug: string; snippet: string };
export type KbSearch = { results: KbResult[] };
export type KbArticle = { id: number; title: string; slug: string; body: string; tags: string[]; updated_at: string };
