import type { User } from "../api/types";

export type Session = { token: string; user: User };

const KEY = "ticketing.session";
type Listener = (s: Session | null) => void;
const listeners = new Set<Listener>();

function read(): Session | null {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

let current: Session | null = read();

// Another tab signed in or out: follow it, so this tab never keeps acting
// with a token that was replaced.
if (typeof window !== "undefined") {
  window.addEventListener("storage", (e) => {
    if (e.key !== KEY && e.key !== null) return;
    current = read();
    listeners.forEach((l) => l(current));
  });
}

function write(next: Session | null) {
  current = next;
  try {
    if (next) localStorage.setItem(KEY, JSON.stringify(next));
    else localStorage.removeItem(KEY);
  } catch {
    // Storage unavailable: the session lasts for this tab only.
  }
  listeners.forEach((l) => l(next));
}

/** The token store. The server enforces every role check; this only decides
 * which screens to show. */
export const session = {
  get: () => current,
  set: (s: Session) => write(s),
  clear: () => write(null),
  subscribe(listener: Listener) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
};
