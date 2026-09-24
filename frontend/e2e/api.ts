import { expect, request, type APIRequestContext } from "@playwright/test";
import { SEED_PASSWORD } from "./helpers";

const API = process.env.E2E_API_URL ?? "http://localhost:8000";

export type ApiUser = {
  ctx: APIRequestContext;
  id: number;
  headers: Record<string, string>;
  get: (path: string) => Promise<any>;
  post: (path: string, data?: object) => Promise<any>;
  patch: (path: string, data: object) => Promise<any>;
};

export async function apiAs(email: string, password = SEED_PASSWORD): Promise<ApiUser> {
  const ctx = await request.newContext({ baseURL: API });
  const login = await ctx.post("/auth/login", { data: { email, password } });
  expect(login.ok(), `login ${email}`).toBeTruthy();
  const { access_token, user } = await login.json();
  const headers = { Authorization: `Bearer ${access_token}` };
  const json = async (r: Awaited<ReturnType<APIRequestContext["get"]>>) => {
    expect(r.ok(), `${r.url()} → ${r.status()} ${await r.text()}`).toBeTruthy();
    return r.json();
  };
  return {
    ctx,
    id: user.id,
    headers,
    get: async (path) => json(await ctx.get(path, { headers })),
    post: async (path, data) => json(await ctx.post(path, { data, headers })),
    patch: async (path, data) => json(await ctx.patch(path, { data, headers })),
  };
}

export async function waitForTriage(as: ApiUser, id: number): Promise<any> {
  for (let i = 0; i < 40; i++) {
    const t = await as.get(`/tickets/${id}`);
    if (t.status !== "new") return t;
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`ticket ${id} was never triaged`);
}
