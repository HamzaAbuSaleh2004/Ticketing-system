import AddOutlined from "@mui/icons-material/AddOutlined";
import SearchOutlined from "@mui/icons-material/SearchOutlined";
import { Box, Button, InputAdornment, Stack, TextField, Typography } from "@mui/material";
import { useEffect, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import { useCategories, useOrganizations, useStaff } from "../../api/hooks";
import type { TicketPriority, TicketStatus } from "../../api/types";
import { STATUS_LABEL } from "../../lib/tickets";
import { sys } from "../../theme/scheme";
import { FilterChip } from "./FilterChip";
import type { QueueFilters, StatusFilter } from "./queueParams";

const STATUSES: TicketStatus[] = ["open", "in_progress", "pending", "resolved", "closed"];
const PRIORITIES: TicketPriority[] = ["urgent", "high", "normal", "low"];

export function QueueToolbar({
  filters,
  total,
  onChange,
}: {
  filters: QueueFilters;
  total: number | undefined;
  onChange: (next: Partial<QueueFilters>) => void;
}) {
  const staff = useStaff();
  const categories = useCategories();
  const organizations = useOrganizations();
  const [q, setQ] = useState(filters.q);
  useEffect(() => {
    setQ(filters.q);
  }, [filters.q]);

  return (
    <Box sx={{ px: { xs: 2, md: 3 }, pt: 2, pb: 1.5 }}>
      <Stack direction="row" sx={{ alignItems: "center", gap: 2, flexWrap: "wrap", mb: 1.5 }}>
        <Typography variant="titleLarge" component="h1">
          Queue
        </Typography>
        <Typography variant="bodyMedium" className="tabular" sx={{ color: sys("onSurfaceVariant") }} aria-live="polite">
          {total === undefined ? "" : total === 1 ? "1 ticket" : `${total} tickets`}
        </Typography>
        <Box sx={{ flex: 1 }} />
        <Box
          component="form"
          role="search"
          onSubmit={(e) => {
            e.preventDefault();
            onChange({ q: q.trim(), page: 1 });
          }}
          sx={{ width: { xs: "100%", sm: 320 } }}
        >
          <TextField
            type="search"
            size="small"
            fullWidth
            placeholder="Search subject or description"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            slotProps={{
              htmlInput: { "aria-label": "Search tickets" },
              input: {
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchOutlined fontSize="small" />
                  </InputAdornment>
                ),
                sx: { borderRadius: "var(--md-sys-shape-corner-full)", bgcolor: sys("surfaceContainerHigh") },
              },
            }}
          />
        </Box>
        <Button component={RouterLink} to="/agent/tickets/new" startIcon={<AddOutlined />}>
          New ticket
        </Button>
      </Stack>
      <Stack direction="row" sx={{ gap: 1, flexWrap: "wrap" }} role="group" aria-label="Filters">
        <FilterChip
          label="Status"
          value={filters.status}
          defaultValue="active"
          options={[
            { value: "active", label: "Active" },
            ...STATUSES.map((s) => ({ value: s, label: STATUS_LABEL[s] })),
            { value: "all", label: "All statuses" },
          ]}
          onChange={(v) => onChange({ status: (v ?? "active") as StatusFilter, page: 1 })}
        />
        <FilterChip
          label="Priority"
          value={filters.priority}
          options={[{ value: null, label: "Any priority" }, ...PRIORITIES.map((p) => ({ value: p, label: p[0].toUpperCase() + p.slice(1) }))]}
          onChange={(v) => onChange({ priority: v as TicketPriority | null, page: 1 })}
        />
        <FilterChip
          label="Assignee"
          value={filters.assignee}
          options={[
            { value: null, label: "Anyone" },
            { value: "me", label: "Mine" },
            { value: "unassigned", label: "Unassigned" },
            ...(staff.data ?? []).map((u) => ({ value: String(u.id), label: u.name })),
          ]}
          onChange={(v) => onChange({ assignee: v, page: 1 })}
        />
        <FilterChip
          label="Category"
          value={filters.category}
          options={[{ value: null, label: "Any category" }, ...(categories.data ?? []).map((c) => ({ value: c.slug, label: c.name }))]}
          onChange={(v) => onChange({ category: v, page: 1 })}
        />
        <FilterChip
          label="Organisation"
          value={filters.organization}
          options={[
            { value: null, label: "Any organisation" },
            { value: "none", label: "No organisation" },
            ...(organizations.data ?? []).map((o) => ({ value: String(o.id), label: o.name })),
          ]}
          onChange={(v) => onChange({ organization: v, page: 1 })}
        />
      </Stack>
    </Box>
  );
}
