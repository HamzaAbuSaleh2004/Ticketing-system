import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type {
  Attachment,
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
      qc.invalidateQueries({ queryKey: keys.ticket(ticketId) });
      qc.invalidateQueries({ queryKey: keys.tickets, exact: true });
    },
  });
}

export function uploadAttachment(ticketId: number, file: File) {
  const form = new FormData();
  form.append("file", file);
  return api<Attachment>(`/tickets/${ticketId}/attachments`, { method: "POST", form });
}
