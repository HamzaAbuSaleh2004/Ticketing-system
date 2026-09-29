import ChevronLeft from "@mui/icons-material/ChevronLeft";
import ChevronRight from "@mui/icons-material/ChevronRight";
import { Box, Button, IconButton, LinearProgress, Stack, Typography } from "@mui/material";
import { useCallback, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQueue } from "../../api/hooks";
import { sys } from "../../theme/scheme";
import { apiQuery, PAGE_SIZE, readFilters, writeFilters, type QueueFilters } from "./queueParams";
import { QueueTable } from "./QueueTable";
import { QueueToolbar } from "./QueueToolbar";
import { useListKeys } from "./useListKeys";

export function QueuePage() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const filters = useMemo(() => readFilters(params), [params]);
  const queue = useQueue(apiQuery(filters));
  const rows = queue.data?.items ?? [];
  // By id, not index: the 20s refresh re-sorts by deadline, and the
  // highlight must stay on the ticket the agent chose.
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const found = rows.findIndex((r) => r.id === selectedId);
  const selected = found >= 0 ? found : 0;
  const setSelected = useCallback((i: number) => setSelectedId(rows[i]?.id ?? null), [rows]);

  const update = (next: Partial<QueueFilters>) => {
    setParams(writeFilters({ ...filters, ...next }));
    setSelectedId(null);
  };
  const linkFor = useCallback((id: number) => `/agent/tickets/${id}${params.size ? `?${params}` : ""}`, [params]);
  const open = useCallback((i: number) => rows[i] && navigate(linkFor(rows[i].id)), [rows, navigate, linkFor]);
  useListKeys(rows.length, selected, setSelected, open);

  const total = queue.data?.total;
  const pages = total ? Math.ceil(total / PAGE_SIZE) : 1;

  return (
    <Box sx={{ minHeight: "100dvh", display: "flex", flexDirection: "column" }}>
      <QueueToolbar filters={filters} total={total} onChange={update} />
      <Box sx={{ height: 4 }}>{queue.isFetching && !queue.isLoading ? <LinearProgress aria-label="Refreshing queue" /> : null}</Box>

      {queue.isError && !queue.data ? (
        <Box role="alert" sx={{ p: 3 }}>
          <Typography variant="bodyLarge" sx={{ mb: 2 }}>
            The queue didn't load.
          </Typography>
          <Button onClick={() => queue.refetch()}>
            Try again
          </Button>
        </Box>
      ) : !queue.isLoading && rows.length === 0 ? (
        <Box sx={{ p: 3 }}>
          <Typography variant="titleMedium">No tickets match these filters</Typography>
          <Typography variant="bodyMedium" sx={{ mt: 0.5, color: sys("onSurfaceVariant") }}>
            Clear a filter to widen the view.
          </Typography>
        </Box>
      ) : (
        <QueueTable rows={rows} selected={selected} linkFor={linkFor} onOpen={open} />
      )}

      <Stack
        direction="row"
        sx={{ mt: "auto", px: { xs: 2, md: 3 }, py: 1, alignItems: "center", justifyContent: "space-between", gap: 2, borderTop: `1px solid ${sys("outlineVariant")}` }}
      >
        <Typography variant="bodySmall" sx={{ color: sys("onSurfaceVariant") }}>
          <Box component="kbd" sx={{ fontFamily: "inherit", fontWeight: 600 }}>j</Box> and{" "}
          <Box component="kbd" sx={{ fontFamily: "inherit", fontWeight: 600 }}>k</Box> to move,{" "}
          <Box component="kbd" sx={{ fontFamily: "inherit", fontWeight: 600 }}>Enter</Box> to open
        </Typography>
        <Stack direction="row" sx={{ alignItems: "center", gap: 0.5 }}>
          <Typography variant="bodySmall" className="tabular" sx={{ color: sys("onSurfaceVariant") }}>
            Page {filters.page} of {pages}
          </Typography>
          <IconButton aria-label="Previous page" disabled={filters.page <= 1} onClick={() => update({ page: filters.page - 1 })}>
            <ChevronLeft />
          </IconButton>
          <IconButton aria-label="Next page" disabled={filters.page >= pages} onClick={() => update({ page: filters.page + 1 })}>
            <ChevronRight />
          </IconButton>
        </Stack>
      </Stack>
    </Box>
  );
}
