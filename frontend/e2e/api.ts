import { expect, request, type APIRequestContext } from "@playwright/test";
import { SEED_PASSWORD } from "./helpers";
import { withCode } from "./totp";

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
  const { mfa_token } = await login.json();
  let verified: { access_token: string; user: { id: number } } | undefined;
  await withCode(email, async (code) => {
    const verify = await ctx.post("/auth/2fa/verify", { data: { mfa_token, code } });
    expect([200, 401], `2fa ${email} → ${verify.status()} ${await verify.text()}`).toContain(verify.status());
    if (verify.ok()) verified = await verify.json();
    return verify.ok();
  });
  const { access_token, user } = verified!;
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

/** Triage is manual: an agent sets category and priority. The ticket stays
 * `open` (there's no separate "triaged" status) until someone takes it. */
export async function triage(agent: ApiUser, id: number, fields: { category: string; priority: string }): Promise<any> {
  return agent.patch(`/tickets/${id}`, { ...fields });
}
