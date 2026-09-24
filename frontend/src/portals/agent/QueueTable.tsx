import { Box, Link, Table, TableBody, TableCell, TableHead, TableRow, Typography } from "@mui/material";
import { useEffect, useRef } from "react";
import { Link as RouterLink } from "react-router-dom";
import type { TicketQueueItem } from "../../api/types";
import { PriorityChip, StatusChip } from "../../components/TicketChips";
import { SlaIndicator } from "../../components/SlaIndicator";
import { absoluteTime, compactAgo, relativeTime, ticketRef } from "../../lib/tickets";
import { sys } from "../../theme/scheme";

const COLUMNS: { key: string; label: string; width?: number; align?: "right" }[] = [
  { key: "id", label: "ID", width: 96 },
  { key: "subject", label: "Subject" },
  { key: "requester", label: "Requester", width: 150 },
  { key: "priority", label: "Priority", width: 92 },
  { key: "status", label: "Status", width: 112 },
  // Wide enough for "22h 04m over" + "Breached" without truncation.
  { key: "sla", label: "SLA", width: 196 },
  { key: "assignee", label: "Assignee", width: 140 },
  { key: "updated", label: "Updated", width: 80, align: "right" },
];

const cell = { py: 0, px: 1.5, height: 36, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" } as const;

/** Dense, full-bleed queue: 36px rows, tabular IDs, an SLA ring per row.
 * j/k move the selection, Enter opens it (handled by the page). */
export function QueueTable({
  rows,
  selected,
  linkFor,
  onOpen,
}: {
  rows: TicketQueueItem[];
  selected: number;
  linkFor: (id: number) => string;
  onOpen: (index: number) => void;
}) {
  const selectedRow = useRef<HTMLTableRowElement>(null);
  // Block body: scrollIntoView returns a Promise in current Chromium, which
  // React would otherwise treat as the effect's cleanup function.
  useEffect(() => {
    selectedRow.current?.scrollIntoView({ block: "nearest" });
  }, [selected]);

  return (
    <Box sx={{ overflowX: "auto" }}>
      <Table size="small" stickyHeader aria-label="Tickets" sx={{ tableLayout: "fixed", minWidth: 1028 }}>
        <TableHead>
          <TableRow>
            {COLUMNS.map((c) => (
              <TableCell
                key={c.key}
                align={c.align}
                sx={{ ...cell, width: c.width, bgcolor: sys("surface"), color: sys("onSurfaceVariant"), typography: "labelMedium" }}
              >
                {c.label}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((t, i) => {
            const isSelected = i === selected;
            const summary = t.ai_summary && t.ai_summary !== t.subject ? t.ai_summary : null;
            return (
              <TableRow
                key={t.id}
                ref={isSelected ? selectedRow : undefined}
                aria-selected={isSelected}
                onClick={(e) => {
                  // The subject link navigates by itself; don't double-handle it.
                  if (!(e.target as HTMLElement).closest("a")) onOpen(i);
                }}
                sx={{
                  cursor: "pointer",
                  bgcolor: isSelected ? sys("surfaceContainerHighest") : "transparent",
                  "&:hover": { bgcolor: isSelected ? sys("surfaceContainerHighest") : sys("surfaceContainerLow") },
                  "& td": { borderColor: sys("outlineVariant") },
                  // A left bar so the selection isn't carried by the tint alone.
                  "& td:first-of-type": { boxShadow: isSelected ? `inset 3px 0 0 ${sys("primary")}` : "none" },
                }}
              >
                <TableCell sx={cell}>
                  <Typography variant="bodyMedium" component="span" className="tabular" sx={{ color: sys("onSurfaceVariant") }}>
                    {ticketRef(t.id)}
                  </Typography>
                </TableCell>
                <TableCell sx={cell}>
                  <Link
                    component={RouterLink}
                    to={linkFor(t.id)}
                    underline="none"
                    sx={{ color: sys("onSurface"), fontWeight: 500, "&:hover": { textDecoration: "underline" } }}
                  >
                    {t.subject}
                  </Link>
                  {summary ? (
                    <Typography variant="bodyMedium" component="span" sx={{ color: sys("onSurfaceVariant"), ml: 1 }}>
                      {summary}
                    </Typography>
                  ) : null}
                  {t.escalated ? (
                    <Typography variant="labelMedium" component="span" sx={{ color: sys("error"), ml: 1 }}>
                      Escalated
                    </Typography>
                  ) : null}
                </TableCell>
                <TableCell sx={cell}>{t.requester_name}</TableCell>
                <TableCell sx={cell}>
                  <PriorityChip priority={t.priority} />
                </TableCell>
                <TableCell sx={cell}>
                  <StatusChip status={t.status} />
                </TableCell>
                <TableCell sx={cell}>
                  <SlaIndicator ticket={t} />
                </TableCell>
                <TableCell sx={{ ...cell, color: t.assignee_name ? sys("onSurface") : sys("onSurfaceVariant") }}>
                  {t.assignee_name ?? "Unassigned"}
                </TableCell>
                <TableCell sx={cell} align="right">
                  <Typography variant="bodyMedium" component="time" dateTime={t.updated_at} title={`${relativeTime(t.updated_at)}, ${absoluteTime(t.updated_at)}`} className="tabular">
                    {compactAgo(t.updated_at)}
                  </Typography>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </Box>
  );
}
