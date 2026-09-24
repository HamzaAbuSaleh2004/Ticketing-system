import { expect, request, test, type Page } from "@playwright/test";
import { SEED_PASSWORD, shot } from "./helpers";

const API = process.env.E2E_API_URL ?? "http://localhost:8000";

async function agentApi() {
  const ctx = await request.newContext({ baseURL: API });
  const login = await ctx.post("/auth/login", { data: { email: "agent1@ticketing.demo", password: SEED_PASSWORD } });
  const { access_token, user } = await login.json();
  const headers = { Authorization: `Bearer ${access_token}` };
  return {
    patch: (id: number, data: object) => ctx.patch(`/tickets/${id}`, { data, headers }),
    reply: (id: number, body: string) => ctx.post(`/tickets/${id}/comments`, { data: { body }, headers }),
    agentId: user.id as number,
  };
}

async function register(page: Page) {
  const email = `uma-${Date.now()}@example.com`;
  await page.goto("/register");
  await page.getByLabel("Name").fill("Uma Example");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("Password123!");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/$/);
}

test("register → KB answer with source link → submit → triage chips appear", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await register(page);
  await expect(page.getByText("You haven't sent us anything yet.")).toBeVisible();
  await shot(page, "phase-7", "home-empty-1280");

  // KB search: grounded answer + numbered source chip linking to the article.
  await page.getByRole("searchbox", { name: "Search help articles" }).fill("I forgot my password and the reset email never came");
  await page.keyboard.press("Enter");
  const panel = page.getByRole("region", { name: "Answer from our help articles" });
  await expect(panel).toBeVisible();
  await expect(panel.getByRole("link", { name: "Source 1: Resetting your password" })).toBeVisible();
  const sourceChip = panel.getByRole("list", { name: "Sources" }).getByRole("link", { name: /Resetting your password/ });
  await expect(sourceChip).toHaveAttribute("href", "/help/resetting-your-password");
  await shot(page, "phase-7", "home-answer-1280");
  await page.setViewportSize({ width: 360, height: 800 });
  await shot(page, "phase-7", "home-answer-360");
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.emulateMedia({ colorScheme: "dark" });
  await shot(page, "phase-7", "home-answer-dark-1280");
  await page.emulateMedia({ colorScheme: "light" });

  await sourceChip.click();
  await expect(page.getByRole("heading", { name: "Resetting your password" })).toBeVisible();
  await shot(page, "phase-7", "article-1280");
  await page.goBack();

  // No-answer state.
  await page.getByRole("searchbox", { name: "Search help articles" }).fill("what is the weather in paris");
  await page.keyboard.press("Enter");
  await expect(page.getByText("No help article answers this yet")).toBeVisible();
  await shot(page, "phase-7", "home-no-answer-1280");

  // Submit a request.
  await page.getByRole("link", { name: "New request" }).click();
  await page.getByLabel("Subject").fill("Charged twice this month");
  await page.getByLabel("Details").fill("My card was charged twice for the March invoice. Please refund one of the charges.");
  await page.locator('input[type="file"]').setInputFiles({ name: "receipt.txt", mimeType: "text/plain", buffer: Buffer.from("txn 123") });
  await expect(page.getByText("receipt.txt")).toBeVisible();
  await shot(page, "phase-7", "new-request-1280");
  await page.getByRole("button", { name: "Send request" }).click();

  await expect(page).toHaveURL(/\/requests\/\d+$/);
  await expect(page.getByRole("heading", { name: "Charged twice this month" })).toBeVisible();
  // Triage lands via the worker; the page polls and shows the applied category/priority.
  await expect(page.getByText("Billing", { exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("High priority")).toBeVisible();
  await expect(page.getByRole("button", { name: "receipt.txt" })).toBeVisible();
  await shot(page, "phase-7", "request-triaged-1280");

  // Back on home, it's listed.
  await page.getByRole("link", { name: "Your requests" }).click();
  await expect(page.getByRole("link", { name: /Charged twice this month/ })).toBeVisible();
  await page.getByRole("searchbox", { name: "Search help articles" }).fill("");
  await page.goto("/");
  await shot(page, "phase-7", "home-with-requests-1280");
  await page.setViewportSize({ width: 360, height: 800 });
  await shot(page, "phase-7", "home-with-requests-360");
});

test("state-aware reply copy: pending, resolved, closed → follow-up", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await register(page);
  await page.goto("/requests/new");
  await page.getByLabel("Subject").fill("Locked out of my account");
  await page.getByLabel("Details").fill("I can't log in since this morning.");
  await page.getByRole("button", { name: "Send request" }).click();
  await expect(page).toHaveURL(/\/requests\/\d+$/);
  const id = Number(page.url().split("/").pop());
  await expect(page.getByText("Account & login", { exact: true })).toBeVisible({ timeout: 30_000 });

  const agent = await agentApi();
  for (const patch of [{ assignee_id: agent.agentId }, { status: "open" }, { status: "in_progress" }]) {
    expect((await agent.patch(id, patch)).ok()).toBeTruthy();
  }
  await agent.reply(id, "Thanks, Uma. Could you tell me which browser you're using?");
  expect((await agent.patch(id, { status: "pending" })).ok()).toBeTruthy();

  await page.reload();
  await expect(page.getByText("Waiting on you", { exact: true })).toBeVisible();
  await expect(page.getByText("We're waiting on your reply to continue.")).toBeVisible();
  await expect(page.getByText("Tara from Support")).toBeVisible();
  await shot(page, "phase-7", "request-pending-1280");
  await page.setViewportSize({ width: 360, height: 800 });
  await shot(page, "phase-7", "request-pending-360");
  await page.emulateMedia({ colorScheme: "dark" });
  await shot(page, "phase-7", "request-pending-dark-360");
  await page.emulateMedia({ colorScheme: "light" });
  await page.setViewportSize({ width: 1280, height: 900 });

  // Customer replies → back to in progress.
  await page.getByLabel("Your reply").fill("Firefox, latest version.");
  await page.getByRole("button", { name: "Send reply" }).click();
  await expect(page.getByText("Firefox, latest version.")).toBeVisible();
  await expect(page.getByText("In progress", { exact: true })).toBeVisible();

  expect((await agent.patch(id, { status: "resolved" })).ok()).toBeTruthy();
  await page.reload();
  await expect(page.getByText("Reply within 72h to reopen this request.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Reopen with reply" })).toBeVisible();
  await shot(page, "phase-7", "request-resolved-1280");

  expect((await agent.patch(id, { status: "closed" })).ok()).toBeTruthy();
  await page.reload();
  await expect(page.getByText("This request is closed. Replying starts a new request.")).toBeVisible();
  await page.getByLabel("Your reply").fill("It happened again today.");
  await page.getByRole("button", { name: "Start a new request" }).click();
  await expect(page).not.toHaveURL(new RegExp(`/requests/${id}$`));
  await expect(page.getByText(/Follow-up to/)).toBeVisible();
  const ref = `TCK-${String(id).padStart(5, "0")}`;
  await expect(page.getByRole("link", { name: ref })).toHaveAttribute("href", `/requests/${id}`);
  await expect(page.getByText(`Started a new request, linked to ${ref}`)).toBeVisible();
});
