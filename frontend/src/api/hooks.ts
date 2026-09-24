import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type {
  Attachment,
  TicketDetail,
  TicketPatch,
  TicketQueue,
  User,
  Category,
  CommentCreateResult,
  KbArticle,
  KbSearchResult,
  TicketDetailPublic,
  TicketList,
} from "./types";

export const keys = {
  tickets: ["tickets"] as const,
  ticket: (id: number) => ["tickets", id] as const,
  kb: (q: string) => ["kb", q] as const,
  article: (slug: string) => ["kb-article", slug] as const,
  categories: ["categories"] as const,
};

export function useCategories() {
  return useQuery({
    queryKey: keys.categories,
    queryFn: () => api<Category[]>("/categories"),
    staleTime: 5 * 60_000,
  });
}

export function useCategoryName() {
  const { data } = useCategories();
  return (slug: string | null) => (slug ? (data?.find((c) => c.slug === slug)?.name ?? slug) : null);
}

export const MIN_QUERY = 2;

export function useKbSearch(q: string) {
  return useQuery({
    queryKey: keys.kb(q),
    queryFn: ({ signal }) => api<KbSearchResult>(`/kb/search?q=${encodeURIComponent(q)}`, { signal }),
    enabled: q.trim().length >= MIN_QUERY,
    staleTime: 5 * 60_000,
    retry: false,
  });
}

export function useArticle(slug: string) {
  return useQuery({ queryKey: keys.article(slug), queryFn: () => api<KbArticle>(`/kb/articles/${encodeURIComponent(slug)}`) });
}

export function useMyTickets() {
  return useQuery({
    queryKey: keys.tickets,
    queryFn: () => api<TicketList>("/tickets?sort=-updated_at&page_size=50"),
    placeholderData: keepPreviousData,
  });
}

export function useTicket<T = TicketDetailPublic>(
  id: number,
  refetchInterval?: number | false | ((data: T | undefined) => number | false),
) {
  return useQuery({
    queryKey: keys.ticket(id),
    queryFn: () => api<T>(`/tickets/${id}`),
    refetchInterval:
      typeof refetchInterval === "function" ? (query) => refetchInterval(query.state.data) : refetchInterval,
  });
}

export function useCreateTicket() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ subject, description, file }: { subject: string; description: string; file?: File | null }) => {
      const ticket = await api<TicketDetailPublic>("/tickets", { method: "POST", body: { subject, description } });
      let attachmentError: unknown = null;
      if (file) {
        try {
          await uploadAttachment(ticket.id, file);
        } catch (err) {
          attachmentError = err;
        }
      }
      return { ticket, attachmentError };
    },
    onSuccess: ({ ticket }) => {
      qc.setQueryData(keys.ticket(ticket.id), ticket);
      qc.invalidateQueries({ queryKey: keys.tickets, exact: true });
    },
  });
}

export function useReply(ticketId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { body: string; is_internal_note?: boolean }) =>
      api<CommentCreateResult>(`/tickets/${ticketId}/comments`, { method: "POST", body }),
    onSuccess: () => {
      // The reply isn't returned with the ticket, so refetch it, the
      // customer list and every agent queue (first reply switches the SLA clock).
      qc.invalidateQueries({ queryKey: keys.tickets });
    },
  });
}

export function useQueue(query: string) {
  return useQuery({
    queryKey: ["tickets", "queue", query],
    queryFn: () => api<TicketQueue>(`/tickets?${query}`),
    placeholderData: keepPreviousData,
    // The queue is shared; keep it current without a manual refresh.
    refetchInterval: 20_000,
  });
}

export function useStaff() {
  return useQuery({ queryKey: ["staff"], queryFn: () => api<User[]>("/users/staff"), staleTime: 5 * 60_000 });
}

export function useAgentTicket(id: number) {
  return useTicket<TicketDetail>(id, 20_000);
}

/** Store the fresh detail and refresh lists, without refetching the detail we just wrote. */
function writeTicket(qc: ReturnType<typeof useQueryClient>, id: number, ticket: TicketDetail) {
  qc.setQueryData(keys.ticket(id), ticket);
  qc.invalidateQueries({ queryKey: keys.tickets, predicate: (q) => q.queryKey[1] !== id });
}

export function usePatchTicket(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: TicketPatch) => api<TicketDetail>(`/tickets/${id}`, { method: "PATCH", body: patch }),
    onSuccess: (ticket) => writeTicket(qc, id, ticket),
  });
}

export function useRerunTriage(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<TicketDetail>(`/tickets/${id}/ai-triage`, { method: "POST" }),
    onSuccess: (ticket) => writeTicket(qc, id, ticket),
  });
}

export function uploadAttachment(ticketId: number, file: File) {
  const form = new FormData();
  form.append("file", file);
  return api<Attachment>(`/tickets/${ticketId}/attachments`, { method: "POST", form });
}
