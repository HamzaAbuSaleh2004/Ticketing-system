import { session } from "../auth/session";

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: unknown,
  ) {
    super(typeof detail === "string" ? detail : `Request failed (${status})`);
  }
}

type Options = { method?: string; body?: unknown; form?: FormData; signal?: AbortSignal };

export async function api<T>(path: string, options: Options = {}): Promise<T> {
  const resp = await request(path, options);
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

/** Same auth + error handling as api(), for binary responses (downloads). */
export async function apiBlob(path: string): Promise<Blob> {
  return (await request(path, {})).blob();
}

async function request(path: string, { method = "GET", body, form, signal }: Options): Promise<Response> {
  const headers: Record<string, string> = {};
  const token = session.get()?.token;
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const resp = await fetch(`/api${path}`, {
    method,
    headers,
    body: form ?? (body !== undefined ? JSON.stringify(body) : undefined),
    signal,
  });

  if (resp.status === 401 && token && session.get()?.token === token) {
    // Expired or revoked token: drop the session so RoleGate sends the user
    // to sign in. A 401 for an older token (another user signed in since) is ignored.
    session.clear();
  }
  if (!resp.ok) {
    let detail: unknown = null;
    try {
      detail = (await resp.json()).detail;
    } catch {
      detail = resp.statusText;
    }
    throw new ApiError(resp.status, detail);
  }
  return resp;
}

/** A human message for an API error's `detail` (string, or FastAPI's 422 list). */
export function errorMessage(error: unknown, fallback = "Something went wrong. Try again."): string {
  if (!(error instanceof ApiError)) return fallback;
  const { detail } = error;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg).replace(/^Value error, /, "");
  if (detail && typeof detail === "object" && "error" in detail) return String((detail as { error: string }).error);
  return fallback;
}
