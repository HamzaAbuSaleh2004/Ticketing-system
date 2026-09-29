import { expect, test, type Page } from "@playwright/test";
import { apiAs, triage } from "./api";
import { shot, signIn } from "./helpers";

// [subject, description, category, priority] as an agent would triage them.
const QUEUE_TICKETS = [
  ["Can't log in after changing my password", "I reset my password and now I cannot log in at all. Urgent, demo in an hour.", "account-login", "urgent"],
  ["Invoice shows the wrong company name", "Our March invoice lists our old company name. Can you reissue it?", "billing", "normal"],
  ["Dashboard is really slow", "The analytics page takes a minute to load and sometimes shows an error.", "technical-issue", "high"],
  ["How do I export my data?", "Question: how can I export all of my ticket history?", "data-privacy", "low"],
  ["Charged twice for the annual plan", "I was charged twice on my card for the annual subscription.", "billing", "high"],
  ["Delete my personal data", "Please delete all personal data you hold about me (GDPR request).", "data-privacy", "normal"],
];

async function chooseField(page: Page, name: string, option: RegExp) {
  await page.getByRole("combobox", { name }).click();
  await page.getByRole("option", { name: option }).click();
}

async function chooseStatus(page: Page, label: RegExp) {
  await page.getByRole("combobox", { name: "Status" }).click();
  await page.getByRole("option", { name: label }).click();
}

test.describe.configure({ mode: "serial" });

test("seed a realistic queue", async () => {
  const customer = await apiAs("user2@ticketing.demo");
  const agent = await apiAs("agent2@ticketing.demo");
  const ids: number[] = [];
  for (const [subject, description, category, priority] of QUEUE_TICKETS) {
    const { id } = await customer.post("/tickets", { subject, description });
    await triage(agent, id, { category, priority });
    ids.push(id);
  }
  // A spread of states so the queue shows every SLA indicator state.
  await agent.patch(`/tickets/${ids[1]}`, { assignee_id: agent.id });
  await agent.patch(`/tickets/${ids[1]}`, { status: "open" });
  await agent.patch(`/tickets/${ids[1]}`, { status: "in_progress" });
  await agent.post(`/tickets/${ids[1]}/comments`, { body: "Looking into the invoice now." });
  await agent.patch(`/tickets/${ids[1]}`, { status: "pending" });
  await agent.patch(`/tickets/${ids[2]}`, { assignee_id: agent.id });
});

test("agent walks a ticket through the full lifecycle in the UI, internal note stays internal", async ({ page, browser }) => {
  const customer = await apiAs("user1@ticketing.demo");
  const subject = `Refund for a double charge (${Date.now() % 100000})`;
  const created = await customer.post("/tickets", {
    subject,
    description: "My card was charged twice for the March invoice. Please refund one of them.",
  });
  const id: number = created.id;
  const ref = `TCK-${String(id).padStart(5, "0")}`;

  await page.setViewportSize({ width: 1600, height: 1000 });
  await signIn(page, "agent1@ticketing.demo");
  await expect(page).toHaveURL(/\/agent$/);
  const table = page.getByRole("table", { name: "Tickets" });
  await expect(table.getByRole("link", { name: subject })).toBeVisible();
  await shot(page, "phase-8", "queue-1600");
  await page.setViewportSize({ width: 1280, height: 900 });
  await shot(page, "phase-8", "queue-1280");

  // Filters live in the URL.
  await page.getByRole("button", { name: /^Priority:/ }).click();
  await page.getByRole("menuitemradio", { name: "Normal" }).click();
  await expect(page).toHaveURL(/priority=normal/);
  await expect(table.getByRole("link", { name: subject })).toBeVisible();
  await page.goto("/agent");

  // Keyboard: j/k move the selection, Enter opens it.
  await page.locator("body").click({ position: { x: 5, y: 5 } });
  await page.keyboard.press("j");
  await expect(table.locator('tr[aria-selected="true"]')).toHaveCount(1);
  await page.keyboard.press("k");
  await table.getByRole("link", { name: subject }).click();
  await expect(page).toHaveURL(new RegExp(`/agent/tickets/${id}$`));
  await expect(page.getByRole("heading", { name: subject })).toBeVisible();
  await expect(page.getByText(ref).first()).toBeVisible();

  const aside = page.getByRole("complementary", { name: "Ticket properties" });
  // Manual triage: category and priority, then mark it triaged.
  await expect(page.getByRole("combobox", { name: "Status" })).toHaveText(/New/);
  await chooseField(page, "Category", /^Billing$/);
  await expect(page.getByRole("combobox", { name: "Category" })).toHaveText(/Billing/);
  await chooseField(page, "Priority", /High priority/);
  await expect(page.getByRole("combobox", { name: "Priority" })).toHaveText(/High priority/);
  await chooseStatus(page, /Move to triaged/);
  await expect(page.getByRole("combobox", { name: "Status" })).toHaveText(/Triaged/);

  // Open needs an assignee: the option is guarded until someone takes it.
  await page.getByRole("combobox", { name: "Status" }).click();
  await expect(page.getByRole("option", { name: /Move to open/ })).toHaveAttribute("aria-disabled", "true");
  await page.keyboard.press("Escape");
  await aside.getByRole("button", { name: "Take it" }).click();
  await expect(page.getByRole("combobox", { name: "Assignee" })).toHaveText(/Tara Tier1/);

  await chooseStatus(page, /Move to open/);
  await expect(page.getByRole("combobox", { name: "Status" })).toHaveText(/Open/);
  await chooseStatus(page, /Move to in progress/);

  // A public reply, then an internal note.
  await page.getByRole("textbox", { name: "Reply" }).fill("Thanks for getting in touch about your bill. I'm refunding the duplicate charge now.");
  await page.getByRole("button", { name: "Send reply" }).click();
  await expect(page.getByRole("list", { name: "Conversation" }).getByText(/Thanks for getting in touch about your bill/)).toBeVisible();
  await page.getByRole("button", { name: "Internal note" }).click();
  await page.getByRole("textbox", { name: "Internal note" }).fill("Stripe shows two captures; refund the second one.");
  await page.getByRole("button", { name: "Add internal note" }).click();
  const note = page.getByRole("list", { name: "Conversation" }).getByRole("listitem").filter({ hasText: "Stripe shows two captures" });
  await expect(note).toContainText("Internal note");

  await chooseStatus(page, /Move to pending/);
  await expect(aside.getByText("Paused", { exact: true })).toBeVisible();
  await shot(page, "phase-8", "ticket-pending-1280");
  await page.setViewportSize({ width: 1600, height: 1000 });
  await shot(page, "phase-8", "ticket-pending-1600");

  await chooseStatus(page, /Move to in progress/);
  await chooseStatus(page, /Move to resolved/);
  await expect(aside.getByText("No SLA running").or(aside.getByText("None"))).toBeVisible();
  await chooseStatus(page, /Move to closed/);
  await expect(page.getByRole("combobox", { name: "Status" })).toHaveText(/Closed/);

  // History has one entry per change, including the manual triage.
  await aside.getByRole("button", { name: /History/ }).click();
  await expect(aside.getByText("Category Billing")).toBeVisible();
  await expect(aside.getByText("Status Triaged")).toBeVisible();

  // The customer never sees the internal note (API and UI).
  const asCustomer = await customer.get(`/tickets/${id}`);
  expect(asCustomer.comments.map((c: { body: string }) => c.body)).not.toContain("Stripe shows two captures; refund the second one.");
  expect(asCustomer.comments.some((c: { is_internal_note: boolean }) => c.is_internal_note)).toBe(false);
  const customerCtx = await browser.newContext();
  const customerPage = await customerCtx.newPage();
  await signIn(customerPage, "user1@ticketing.demo");
  await expect(customerPage).toHaveURL(/\/$/);
  await customerPage.goto(`/requests/${id}`);
  await expect(customerPage.getByText(/Thanks for getting in touch about your bill/)).toBeVisible();
  await expect(customerPage.getByText("Stripe shows two captures")).toHaveCount(0);
  await expect(customerPage.getByText("Closed", { exact: true })).toBeVisible();
  await customerCtx.close();
});

test("dark mode and density comparison captures", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.setViewportSize({ width: 1600, height: 1000 });
  await signIn(page, "agent1@ticketing.demo");
  await expect(page.getByRole("table", { name: "Tickets" })).toBeVisible();
  await shot(page, "phase-8", "queue-dark-1600");
  await page.getByRole("table", { name: "Tickets" }).getByRole("link").first().click();
  await expect(page.getByRole("complementary", { name: "Ticket properties" })).toBeVisible();
  await shot(page, "phase-8", "ticket-dark-1600");
});
