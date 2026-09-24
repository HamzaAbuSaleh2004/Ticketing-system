// Validates demo-data/tickets.json against the seed data and the domain rules
// in backend/app/domain/{lifecycle,sla}.py and services/sweeps.py.
// Usage: node check-tickets.mjs [path]
import { readFileSync } from 'node:fs';

const path = process.argv[2] ?? 'demo-data/tickets.json';
const data = JSON.parse(readFileSync(path, 'utf8')); // throws if it doesn't parse
const T = data.tickets;

// Mirrors backend/app/seed.py
const USERS = {
  'user1@ticketing.demo': 'end_user', 'user2@ticketing.demo': 'end_user',
  'agent1@ticketing.demo': 'tier1', 'agent2@ticketing.demo': 'tier1', 'agent3@ticketing.demo': 'senior',
};
const SLA = { urgent: [15, 240], high: [60, 480], normal: [240, 1440], low: [480, 4320] };
const CATEGORIES = ['account-login', 'billing', 'technical-issue', 'data-privacy', 'other'];
const STATUSES = ['new', 'triaged', 'open', 'in_progress', 'pending', 'resolved', 'closed'];
const RUNNING = ['new', 'triaged', 'open', 'in_progress'];
const COOLOFF_MIN = 72 * 60;
const FIELDS = new Set(['ref', 'parent_ref', 'subject', 'description', 'requester_email', 'assignee_email',
  'status', 'priority', 'category', 'escalated', 'created_minutes_ago', 'pending_minutes',
  'resolved_minutes_ago', 'closed_minutes_ago', 'ai_summary', 'ai_triage', 'comments']);

const failures = [];
const check = (ok, msg) => { if (!ok) failures.push(msg); };
const isAgent = (e) => USERS[e] === 'tier1' || USERS[e] === 'senior';

// SLA state at seed time (minutes are "ago", so larger = older). Mirrors
// sweeps.ticket_at_risk: response clock until first response, resolution
// clock always; at risk = < 25% of the window left and not paused.
function slaState(t) {
  if (t.status === 'resolved' || t.status === 'closed') return { state: 'none', left: null };
  if (t.status === 'pending') return { state: 'paused', left: null };
  const [respWin, resWin] = SLA[t.priority];
  const pausedDone = t.pending_minutes ?? 0;
  const resLeft = resWin + pausedDone - t.created_minutes_ago;
  const firstResp = firstResponse(t);
  const clocks = [{ left: resLeft, win: resWin }];
  if (firstResp === null) clocks.push({ left: respWin - t.created_minutes_ago, win: respWin });
  const worst = clocks.reduce((a, b) => (a.left / a.win < b.left / b.win ? a : b));
  if (worst.left < 0) return { state: 'breached', left: worst.left };
  if (worst.left < 0.25 * worst.win) return { state: 'at risk', left: worst.left };
  return { state: 'on track', left: worst.left };
}
function firstResponse(t) {
  const c = t.comments.filter((c) => isAgent(c.author_email) && !c.is_internal_note)
    .sort((a, b) => b.minutes_ago - a.minutes_ago)[0];
  return c ? c.minutes_ago : null;
}

const refs = new Map(T.map((t) => [t.ref, t]));
check(refs.size === T.length, 'refs are unique');
check(T.length >= 20 && T.length <= 30, `about 25 tickets (got ${T.length})`);

for (const t of T) {
  const id = t.ref;
  for (const k of Object.keys(t)) check(FIELDS.has(k), `${id}: unknown field "${k}" (no due dates / absolute times)`);
  check(STATUSES.includes(t.status), `${id}: status`);
  check(t.priority in SLA, `${id}: priority`);
  check(USERS[t.requester_email] === 'end_user', `${id}: requester is user1/user2`);
  check(Number.isInteger(t.created_minutes_ago) && t.created_minutes_ago > 0, `${id}: created_minutes_ago`);
  check(t.subject.length <= 255 && t.subject.trim() && t.description.trim(), `${id}: subject/description`);
  check(!/lorem|ipsum|todo|tbd|placeholder|xxx/i.test(JSON.stringify(t)), `${id}: placeholder text`);

  // New tickets look like POST /tickets output: no category yet, default priority.
  if (t.status === 'new') {
    check(t.category === null && t.priority === 'normal', `${id}: new ticket is untriaged (category null, priority normal)`);
    check(!t.ai_summary && !t.ai_triage, `${id}: new ticket has no AI output yet`);
  } else {
    check(CATEGORIES.includes(t.category), `${id}: category slug`);
    check(!!t.ai_summary, `${id}: triaged+ ticket has ai_summary`);
  }

  // Assignee consistency: triaged/new have none, open+ have one, escalated → agent3.
  if (t.status === 'new' || t.status === 'triaged') check(t.assignee_email === null, `${id}: ${t.status} has no assignee`);
  else check(isAgent(t.assignee_email), `${id}: ${t.status} has an agent assignee`);
  if (t.escalated) check(t.assignee_email === 'agent3@ticketing.demo', `${id}: escalated → agent3 (senior)`);

  // Lifecycle timestamps.
  const hasRes = t.resolved_minutes_ago !== undefined, hasClosed = t.closed_minutes_ago !== undefined;
  check(hasRes === ['resolved', 'closed'].includes(t.status), `${id}: resolved_minutes_ago iff resolved/closed`);
  check(hasClosed === (t.status === 'closed'), `${id}: closed_minutes_ago iff closed`);
  if (hasRes) check(t.resolved_minutes_ago < t.created_minutes_ago, `${id}: resolved after created`);
  if (hasClosed) check(t.closed_minutes_ago <= t.resolved_minutes_ago, `${id}: closed after resolved`);
  if (t.status === 'resolved') check(t.resolved_minutes_ago < COOLOFF_MIN, `${id}: resolved < 72h ago (else the auto-close sweep closes it)`);

  // Pending.
  if (t.pending_minutes !== undefined) {
    check(t.pending_minutes > 0 && t.pending_minutes < t.created_minutes_ago, `${id}: pending_minutes within ticket lifetime`);
    check(['in_progress', 'pending', 'resolved', 'closed'].includes(t.status), `${id}: pending history only on tickets past open`);
  }
  if (t.status === 'pending') {
    check(t.pending_minutes !== undefined, `${id}: pending ticket has pending_minutes (current pause)`);
    const last = [...t.comments].sort((a, b) => a.minutes_ago - b.minutes_ago)[0];
    check(last && isAgent(last.author_email) && !last.is_internal_note && last.minutes_ago >= t.pending_minutes,
      `${id}: pending ticket's latest comment is the agent's public question, posted before the pause`);
  }

  // Comments.
  for (const c of t.comments) {
    check(c.minutes_ago < t.created_minutes_ago && c.minutes_ago >= 0, `${id}: comment after creation`);
    check(c.author_email === t.requester_email || isAgent(c.author_email), `${id}: comment author is requester or agent`);
    if (c.is_internal_note) check(isAgent(c.author_email), `${id}: internal notes are agent-only`);
    if (hasClosed) check(c.minutes_ago >= t.closed_minutes_ago, `${id}: no comments after close`);
    // A customer public reply after resolution would reopen the ticket (or make a follow-up).
    if (hasRes && c.author_email === t.requester_email) check(c.minutes_ago > t.resolved_minutes_ago, `${id}: no customer reply after resolution`);
    // A customer reply during the current pause would have resumed it.
    if (t.status === 'pending' && c.author_email === t.requester_email) check(c.minutes_ago > t.pending_minutes, `${id}: no customer reply during current pause`);
    check(typeof c.body === 'string' && c.body.trim(), `${id}: comment body`);
  }

  // Response SLA met by the first public agent reply, for tickets past triage.
  const fr = firstResponse(t);
  if (!['new', 'triaged'].includes(t.status)) {
    check(fr !== null, `${id}: open+ ticket has a public agent reply (sets first_responded_at)`);
    if (fr !== null) check(t.created_minutes_ago - fr <= SLA[t.priority][0], `${id}: first response within ${SLA[t.priority][0]}m response SLA`);
  }

  // Worker sweep stability: nothing it would auto-escalate the moment it runs.
  const s = slaState(t);
  t._sla = s;
  if (RUNNING.includes(t.status) && ['urgent', 'high'].includes(t.priority) && !t.escalated)
    check(!['at risk', 'breached'].includes(s.state), `${id}: urgent/high at-risk ticket would be auto-escalated by the sweep`);

  if (t.ai_triage) {
    const a = t.ai_triage;
    check(CATEGORIES.includes(a.category) && a.priority in SLA && a.one_line_summary && a.suggested_response_draft,
      `${id}: ai_triage shape`);
    check(Array.isArray(a.accepted_fields) && a.accepted_fields.every((f) => ['category', 'priority', 'one_line_summary', 'suggested_response_draft'].includes(f)),
      `${id}: ai_triage.accepted_fields`);
  }

  if (t.parent_ref) {
    const p = refs.get(t.parent_ref);
    check(p && p.status === 'closed', `${id}: parent ${t.parent_ref} exists and is closed`);
    if (p) check(t.created_minutes_ago < p.closed_minutes_ago, `${id}: follow-up created after parent closed`);
    check(t.requester_email === p?.requester_email, `${id}: follow-up has the parent's requester`);
  }
}

// Coverage claims.
const set = (f) => new Set(T.map(f));
for (const s of STATUSES) check(set((t) => t.status).has(s), `covers status ${s}`);
for (const p of Object.keys(SLA)) check(set((t) => t.priority).has(p), `covers priority ${p}`);
for (const c of CATEGORIES) check(set((t) => t.category).has(c), `covers category ${c}`);
for (const s of ['on track', 'at risk', 'breached', 'paused', 'none']) check(set((t) => t._sla.state).has(s), `covers SLA state ${s}`);
const esc = T.filter((t) => t.escalated);
check(esc.length === 2, `exactly 2 escalated (got ${esc.length})`);
const followUps = T.filter((t) => t.parent_ref);
check(followUps.length >= 1, 'at least one follow-up of a closed ticket');

// Report.
const count = (f) => Object.entries(T.reduce((m, t) => ((m[f(t)] = (m[f(t)] ?? 0) + 1), m), {}))
  .map(([k, v]) => `${k}=${v}`).join(' ');
const fmt = (m) => (m === null ? '' : `${m < 0 ? '-' : ''}${Math.floor(Math.abs(m) / 60)}h ${Math.abs(m) % 60}m`);
console.log(`${path}: ${T.length} tickets parsed`);
console.log('status   ', count((t) => t.status));
console.log('priority ', count((t) => t.priority));
console.log('category ', count((t) => t.category ?? 'null (new, untriaged)'));
console.log('SLA      ', count((t) => t._sla.state));
console.log('escalated', esc.map((t) => `${t.ref} (${t.priority}, ${t.status}, ${t.assignee_email})`).join(', '));
console.log('follow-up', followUps.map((t) => `${t.ref} -> parent ${t.parent_ref}`).join(', '));
console.log('\nref  status       priority  sla       left     assignee');
for (const t of [...T].sort((a, b) => b.created_minutes_ago - a.created_minutes_ago))
  console.log(`${t.ref.padEnd(4)} ${t.status.padEnd(12)} ${t.priority.padEnd(9)} ${t._sla.state.padEnd(9)} ${fmt(t._sla.left).padEnd(8)} ${t.assignee_email ?? '-'}`);

if (failures.length) {
  console.log(`\nFAIL: ${failures.length} check(s)`);
  for (const f of failures) console.log('  - ' + f);
  process.exit(1);
}
console.log('\nPASS: all checks');
