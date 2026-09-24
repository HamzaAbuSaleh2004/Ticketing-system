import { Alert, Box, Button, MenuItem, Snackbar, Stack, Switch, Tab, Table, TableBody, TableCell, TableHead, TableRow, Tabs, TextField, Tooltip, Typography } from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { api, errorMessage } from "../../api/client";
import type { Category, Role, Team, TicketPriority, User } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { PRIORITY_SHORT, absoluteTime, relativeTime } from "../../lib/tickets";
import { sys } from "../../theme/scheme";

type SlaPolicy = { id: number; name: string; priority: TicketPriority; response_minutes: number; resolution_minutes: number };
type AdminAudit = { id: number; entity_type: string; entity_id: number; subject: string | null; actor_name: string | null; action: string; diff_json: { before?: Record<string, unknown>; after?: Record<string, unknown> } | null; created_at: string };

const TABS = ["users", "categories", "sla", "changes"] as const;
type TabKey = (typeof TABS)[number];
const ROLE_LABEL: Record<Role, string> = { end_user: "End user", agent: "Agent", admin: "Admin" };
const TEAM_LABEL: Record<Team, string> = { tier1: "Tier 1", senior: "Senior" };

const cellSx = { py: 0.75 } as const;

/** Loading and failure look different from "empty". */
function QueryState({ query, children }: { query: { isLoading: boolean; isError: boolean; data: unknown; refetch: () => unknown }; children: React.ReactNode }) {
  if (query.isLoading) {
    return (
      <Typography variant="bodyMedium" aria-busy="true" sx={{ color: sys("onSurfaceVariant"), py: 2 }}>
        Loading…
      </Typography>
    );
  }
  if (query.isError && !query.data) {
    return (
      <Box role="alert" sx={{ py: 2 }}>
        <Typography variant="bodyMedium" sx={{ mb: 1 }}>
          This didn't load.
        </Typography>
        <Button variant="outlined" size="small" onClick={() => query.refetch()}>
          Try again
        </Button>
      </Box>
    );
  }
  return <>{children}</>;
}

function useSave(onDone: (msg: string) => void, keys: string[][]) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ path, method, body }: { path: string; method: string; body: unknown; msg: string }) => api(path, { method, body }),
    onSuccess: (_, v) => {
      // Only what an admin change can affect, plus the change log.
      for (const queryKey of [...keys, ["admin", "audit"]]) qc.invalidateQueries({ queryKey });
      onDone(v.msg);
    },
    onError: (e) => onDone(errorMessage(e, "That change didn't save.")),
  });
}

function UsersTab({ notify }: { notify: (m: string) => void }) {
  const { user: me } = useAuth();
  const users = useQuery({ queryKey: ["admin", "users"], queryFn: () => api<User[]>("/users") });
  const save = useSave(notify, [["admin", "users"], ["staff"]]);
  const patch = (u: User, body: Partial<User>, msg: string) => save.mutate({ path: `/users/${u.id}`, method: "PATCH", body, msg });

  return (
    <QueryState query={users}>
    <Table size="small" aria-label="Users">
      <TableHead>
        <TableRow>
          <TableCell>Name</TableCell>
          <TableCell>Email</TableCell>
          <TableCell sx={{ width: 180 }}>Role</TableCell>
          <TableCell sx={{ width: 160 }}>Team</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {(users.data ?? []).map((u) => {
          const self = u.id === me?.id;
          return (
            <TableRow key={u.id}>
              <TableCell sx={cellSx}>{u.name}</TableCell>
              <TableCell sx={{ ...cellSx, color: sys("onSurfaceVariant") }}>{u.email}</TableCell>
              <TableCell sx={cellSx}>
                <Tooltip title={self ? "You can't change your own role" : ""}>
                  <span>
                    <TextField
                      select
                      size="small"
                      fullWidth
                      value={u.role}
                      disabled={self || save.isPending}
                      slotProps={{ htmlInput: { "aria-label": `Role for ${u.name}` } }}
                      onChange={(e) => patch(u, { role: e.target.value as Role }, `${u.name} is now ${ROLE_LABEL[e.target.value as Role].toLowerCase()}`)}
                    >
                      {(Object.keys(ROLE_LABEL) as Role[]).map((r) => (
                        <MenuItem key={r} value={r}>
                          {ROLE_LABEL[r]}
                        </MenuItem>
                      ))}
                    </TextField>
                  </span>
                </Tooltip>
              </TableCell>
              <TableCell sx={cellSx}>
                {u.role === "agent" ? (
                  <TextField
                    select
                    size="small"
                    fullWidth
                    value={u.team ?? "tier1"}
                    disabled={save.isPending}
                    slotProps={{ htmlInput: { "aria-label": `Team for ${u.name}` } }}
                    onChange={(e) => patch(u, { team: e.target.value as Team }, `${u.name} moved to ${TEAM_LABEL[e.target.value as Team]}`)}
                  >
                    {(Object.keys(TEAM_LABEL) as Team[]).map((t) => (
                      <MenuItem key={t} value={t}>
                        {TEAM_LABEL[t]}
                      </MenuItem>
                    ))}
                  </TextField>
                ) : (
                  <Typography variant="bodySmall" sx={{ color: sys("onSurfaceVariant") }}>
                    Agents only
                  </Typography>
                )}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
    </QueryState>
  );
}

function CategoriesTab({ notify }: { notify: (m: string) => void }) {
  const categories = useQuery({ queryKey: ["categories"], queryFn: () => api<Category[]>("/categories") });
  const save = useSave(notify, [["categories"]]);
  const [name, setName] = useState("");

  function add(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    save.mutate({ path: "/categories", method: "POST", body: { name: name.trim() }, msg: `Added ${name.trim()}` }, { onSuccess: () => setName("") });
  }

  return (
    <Box sx={{ maxWidth: 640 }}>
      <Box component="form" onSubmit={add} sx={{ display: "flex", gap: 1, alignItems: "flex-start", mb: 2 }}>
        <TextField size="small" label="New category" value={name} onChange={(e) => setName(e.target.value)} sx={{ flex: 1 }} slotProps={{ htmlInput: { maxLength: 100 } }} />
        <Button type="submit" variant="contained" disabled={save.isPending || !name.trim()}>
          Add category
        </Button>
      </Box>
      <Typography variant="bodySmall" sx={{ color: sys("onSurfaceVariant"), display: "block", mb: 1 }}>
        Inactive categories stay on existing tickets but aren't offered for new triage.
      </Typography>
      <QueryState query={categories}>
      <Table size="small" aria-label="Categories">
        <TableHead>
          <TableRow>
            <TableCell>Name</TableCell>
            <TableCell>Slug</TableCell>
            <TableCell align="right">Active</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {(categories.data ?? []).map((c) => (
            <TableRow key={c.id}>
              <TableCell sx={{ ...cellSx, color: c.active ? sys("onSurface") : sys("onSurfaceVariant") }}>{c.name}</TableCell>
              <TableCell sx={{ ...cellSx, color: sys("onSurfaceVariant") }}>{c.slug}</TableCell>
              <TableCell sx={cellSx} align="right">
                <Switch
                  checked={c.active}
                  disabled={save.isPending}
                  slotProps={{ input: { "aria-label": `${c.name} active` } }}
                  onChange={(e) =>
                    save.mutate({ path: `/categories/${c.id}`, method: "PATCH", body: { active: e.target.checked }, msg: `${c.name} ${e.target.checked ? "activated" : "deactivated"}` })
                  }
                />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      </QueryState>
    </Box>
  );
}

function SlaRow({ policy, notify }: { policy: SlaPolicy; notify: (m: string) => void }) {
  const save = useSave(notify, [["sla-policies"]]);
  const [response, setResponse] = useState(String(policy.response_minutes));
  const [resolution, setResolution] = useState(String(policy.resolution_minutes));
  useEffect(() => {
    setResponse(String(policy.response_minutes));
    setResolution(String(policy.resolution_minutes));
  }, [policy.response_minutes, policy.resolution_minutes]);
  const r = Number(response);
  const s = Number(resolution);
  const valid = Number.isInteger(r) && Number.isInteger(s) && r >= 1 && s >= 1 && r <= s;
  const dirty = r !== policy.response_minutes || s !== policy.resolution_minutes;
  const hours = (m: number) => (m >= 60 ? `${+(m / 60).toFixed(1)} h` : `${m} min`);

  return (
    <TableRow>
      <TableCell sx={cellSx}>{PRIORITY_SHORT[policy.priority]}</TableCell>
      {[
        [response, setResponse, "First reply within", r],
        [resolution, setResolution, "Resolve within", s],
      ].map(([value, set, label, n]) => (
        <TableCell key={label as string} sx={cellSx}>
          <TextField
            size="small"
            type="number"
            value={value as string}
            onChange={(e) => (set as (v: string) => void)(e.target.value)}
            slotProps={{ htmlInput: { min: 1, "aria-label": `${label} (minutes) for ${PRIORITY_SHORT[policy.priority]}` } }}
            helperText={Number(n) >= 1 ? hours(Number(n)) : "At least 1 minute"}
            error={!(Number(n) >= 1)}
            sx={{ width: 140 }}
          />
        </TableCell>
      ))}
      <TableCell sx={cellSx} align="right">
        <Button
          variant="tonal"
          size="small"
          disabled={!dirty || !valid || save.isPending}
          onClick={() =>
            save.mutate({
              path: `/sla-policies/${policy.priority}`,
              method: "PATCH",
              body: { response_minutes: r, resolution_minutes: s },
              msg: `${PRIORITY_SHORT[policy.priority]} targets saved`,
            })
          }
        >
          Save
        </Button>
        {!valid && r > s ? (
          <Typography variant="bodySmall" sx={{ display: "block", color: sys("error") }}>
            First reply can't exceed resolution
          </Typography>
        ) : null}
      </TableCell>
    </TableRow>
  );
}

function SlaTab({ notify }: { notify: (m: string) => void }) {
  const policies = useQuery({ queryKey: ["sla-policies"], queryFn: () => api<SlaPolicy[]>("/sla-policies") });
  return (
    <Box sx={{ maxWidth: 760 }}>
      <Alert severity="info" icon={false} sx={{ mb: 2, bgcolor: sys("secondaryContainer"), color: sys("onSecondaryContainer") }}>
        Changes apply to tickets created after you save. Existing tickets keep their due dates unless their priority changes.
      </Alert>
      <QueryState query={policies}>
      <Table size="small" aria-label="SLA policies">
        <TableHead>
          <TableRow>
            <TableCell>Priority</TableCell>
            <TableCell>First reply within (minutes)</TableCell>
            <TableCell>Resolve within (minutes)</TableCell>
            <TableCell />
          </TableRow>
        </TableHead>
        <TableBody>
          {(policies.data ?? []).map((p) => (
            <SlaRow key={p.id} policy={p} notify={notify} />
          ))}
        </TableBody>
      </Table>
      </QueryState>
    </Box>
  );
}

const ENTITY_LABEL: Record<string, string> = { user: "User", category: "Category", sla_policy: "SLA policy" };

const FIELD_LABEL: Record<string, string> = {
  role: "Role",
  team: "Team",
  name: "Name",
  active: "Active",
  slug: "Slug",
  response_minutes: "First reply (min)",
  resolution_minutes: "Resolve (min)",
};

function show(value: unknown): string {
  if (value === null || value === undefined) return "none";
  if (typeof value === "boolean") return value ? "yes" : "no";
  const s = String(value);
  return ROLE_LABEL[s as Role] ?? TEAM_LABEL[s as Team] ?? s;
}

/** "Role Agent to End user, Team Tier 1 to none". */
export function describeChange(a: Pick<AdminAudit, "diff_json">): string {
  const before = a.diff_json?.before ?? {};
  const after = a.diff_json?.after ?? {};
  return Object.entries(after)
    .map(([k, v]) => `${FIELD_LABEL[k] ?? k} ${k in before ? `${show(before[k])} to ${show(v)}` : show(v)}`)
    .join(", ");
}

function subjectOf(a: AdminAudit): string {
  const name = a.entity_type === "sla_policy" && a.subject ? PRIORITY_SHORT[a.subject as TicketPriority] : a.subject;
  return `${ENTITY_LABEL[a.entity_type] ?? a.entity_type}${name ? ` ${name}` : ""}`;
}

function ChangesTab() {
  const audit = useQuery({ queryKey: ["admin", "audit"], queryFn: () => api<AdminAudit[]>("/admin/audit") });
  if (audit.data?.length === 0) {
    return <Typography variant="bodyMedium" sx={{ color: sys("onSurfaceVariant") }}>No settings have changed yet.</Typography>;
  }
  return (
    <QueryState query={audit}>
    <Table size="small" aria-label="Change log">
      <TableHead>
        <TableRow>
          <TableCell sx={{ width: 150 }}>When</TableCell>
          <TableCell sx={{ width: 160 }}>Who</TableCell>
          <TableCell sx={{ width: 200 }}>What</TableCell>
          <TableCell>Change</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {(audit.data ?? []).map((a) => (
          <TableRow key={a.id}>
            <TableCell sx={{ ...cellSx, whiteSpace: "nowrap" }} title={absoluteTime(a.created_at)}>
              {relativeTime(a.created_at)}
            </TableCell>
            <TableCell sx={cellSx}>{a.actor_name ?? "System"}</TableCell>
            <TableCell sx={cellSx}>{subjectOf(a)}</TableCell>
            <TableCell sx={{ ...cellSx, color: sys("onSurfaceVariant") }}>{describeChange(a)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
    </QueryState>
  );
}

export function AdminPage() {
  const [params, setParams] = useSearchParams();
  const tab: TabKey = (TABS as readonly string[]).includes(params.get("tab") ?? "") ? (params.get("tab") as TabKey) : "users";
  const [toast, setToast] = useState<string | null>(null);

  return (
    <Box sx={{ p: { xs: 2, md: 3 } }}>
      <Typography variant="titleLarge" component="h1">
        Admin
      </Typography>
      <Typography variant="bodyMedium" sx={{ color: sys("onSurfaceVariant"), mb: 1 }}>
        Every change here is recorded in the change log.
      </Typography>
      <Tabs value={tab} onChange={(_, v) => setParams({ tab: v })} sx={{ mb: 2, borderBottom: `1px solid ${sys("outlineVariant")}` }}>
        <Tab value="users" label="Users" />
        <Tab value="categories" label="Categories" />
        <Tab value="sla" label="SLA policies" />
        <Tab value="changes" label="Change log" />
      </Tabs>
      <Stack>
        {tab === "users" ? <UsersTab notify={setToast} /> : null}
        {tab === "categories" ? <CategoriesTab notify={setToast} /> : null}
        {tab === "sla" ? <SlaTab notify={setToast} /> : null}
        {tab === "changes" ? <ChangesTab /> : null}
      </Stack>
      <Snackbar open={toast !== null} autoHideDuration={4000} onClose={() => setToast(null)} message={toast} />
    </Box>
  );
}
