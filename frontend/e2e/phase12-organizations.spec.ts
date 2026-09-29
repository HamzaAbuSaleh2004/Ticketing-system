import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { apiAs } from "./api";
import { shot, signIn } from "./helpers";
import { nextCode } from "./totp";

async function axe(page: Page, label: string) {
  const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  const summary = r.violations.map((v) => `${v.id}: ${v.nodes.length} e.g. ${v.nodes[0]?.target.join(" ")}`);
  console.log(`[axe] ${label}: ${r.violations.length} violation(s) ${summary.join("; ")}`);
  expect(summary, label).toEqual([]);
}

test("a ticket carries its organisation and requester, and the two action-item lists work end to end", async ({ page, browser }) => {
  const admin = await apiAs("admin@ticketing.demo");
  const orgName = `Northwind Robotics ${Date.now() % 100000}`;
  const org = await admin.post("/organizations", { name: orgName, kind: "company" });

  const stamp = Date.now() % 1_000_000;
  const email = `org-e2e-${stamp}@example.com`;
  const name = `Orin Customer ${stamp}`;
  const reg = await (await admin.ctx.post("/auth/register", { data: { email, password: "Password123!", name } })).json();
  const setup = await (await admin.ctx.post("/auth/2fa/setup", { data: { mfa_token: reg.mfa_token } })).json();
  const enabled = await admin.ctx.post("/auth/2fa/enable", { data: { mfa_token: reg.mfa_token, code: await nextCode(email, setup.secret) } });
  expect(enabled.ok()).toBeTruthy();
  const { user } = await enabled.json();
  await admin.patch(`/users/${user.id}`, { organization_id: org.id });

  const customerCtx = await browser.newContext();
  const customerPage = await customerCtx.newPage();
  await signIn(customerPage, email, "Password123!", setup.secret);

  const subject = `The delivery portal won't load (${stamp})`;
  await customerPage.getByRole("link", { name: "New request" }).click();
  await customerPage.getByLabel("Subject").fill(subject);
  await customerPage.getByLabel("Details").fill("Our warehouse team can't load the delivery tracking portal since this morning.");
  await customerPage.getByRole("button", { name: "Send request" }).click();
  await expect(customerPage).toHaveURL(/\/requests\/\d+/);
  const id = Number(customerPage.url().match(/\/requests\/(\d+)/)![1]);

  // The ticket inherited the customer's organisation on create.
  const created = await admin.get(`/tickets/${id}`);
  expect(created.organization_name).toBe(orgName);

  await page.setViewportSize({ width: 1600, height: 1000 });
  await signIn(page, "agent1@ticketing.demo");
  await page.getByRole("button", { name: /^Organisation:/ }).click();
  await page.getByRole("menuitemradio", { name: orgName }).click();
  const table = page.getByRole("table", { name: "Tickets" });
  await expect(table.getByRole("link", { name: subject })).toBeVisible();
  await expect(table.getByRole("row", { name: subject })).toContainText(orgName);
  await expect(table.getByRole("row", { name: subject })).toContainText(name);
  await shot(page, "phase-12", "queue-1600");
  await page.setViewportSize({ width: 1280, height: 900 });
  await shot(page, "phase-12", "queue-1280");
  await axe(page, "queue with organisation column");

  await table.getByRole("link", { name: subject }).click();
  const ticketSection = page.getByRole("region", { name: "Ticket" });
  await expect(ticketSection.getByRole("heading", { name: subject })).toBeVisible();
  await expect(ticketSection.getByText(orgName)).toBeVisible();
  await expect(ticketSection.getByText("Company", { exact: true })).toBeVisible();
  await expect(ticketSection.getByText(`Opened by ${name}`)).toBeVisible();

  const aside = page.getByRole("complementary", { name: "Ticket properties" });
  await aside.getByRole("textbox", { name: "Add an item from the customer" }).fill("Confirm the affected warehouse's address");
  await aside.getByRole("button", { name: "Add an item from the customer" }).click();
  await expect(aside.getByText("Confirm the affected warehouse's address")).toBeVisible();
  await aside.getByRole("textbox", { name: "Add an item from LiverX" }).fill("Check the portal's error logs for this account");
  await aside.getByRole("button", { name: "Add an item from LiverX" }).click();
  await expect(aside.getByText("Check the portal's error logs for this account")).toBeVisible();
  await shot(page, "phase-12", "workspace-1280");
  await page.setViewportSize({ width: 1600, height: 1000 });
  await shot(page, "phase-12", "workspace-1600");
  await axe(page, "workspace with what's needed");

  // The queue row now shows what's waited on.
  await page.goto("/agent");
  await expect(table.getByRole("row", { name: subject })).toContainText("Customer 1");
  await expect(table.getByRole("row", { name: subject })).toContainText("LiverX 1");

  // The customer sees both lists, and can only tick their own.
  await customerPage.goto(`/requests/${id}`);
  const whatsNeeded = customerPage.getByRole("region", { name: "What's needed" });
  await expect(whatsNeeded).toContainText("Confirm the affected warehouse's address");
  await expect(whatsNeeded).toContainText("Check the portal's error logs for this account");
  await customerPage.setViewportSize({ width: 1280, height: 900 });
  await shot(customerPage, "phase-12", "request-1280");
  await customerPage.setViewportSize({ width: 360, height: 800 });
  await shot(customerPage, "phase-12", "request-360");
  await axe(customerPage, "customer request with what's needed");

  const yourItem = whatsNeeded.getByRole("checkbox", { name: "Confirm the affected warehouse's address" });
  await expect(whatsNeeded.getByRole("checkbox", { name: "Check the portal's error logs for this account" })).toBeDisabled();
  await yourItem.click();
  await expect(yourItem).toBeChecked({ timeout: 10_000 });
  await expect(whatsNeeded).toContainText("Done");

  // The agent sees it ticked, by whom and when.
  await page.goto(`/agent/tickets/${id}`);
  await expect(aside.getByText(`${name}, `)).toBeVisible();
  await customerCtx.close();
});

test("admin adds, renames, re-kinds and deactivates an organisation, and assigns it to an end user", async ({ page }) => {
  const admin = await apiAs("admin@ticketing.demo");
  const stamp = Date.now() % 100000;
  const orgName = `Coastal Utilities ${stamp}`;
  const renamed = `Coastal Utilities Board ${stamp}`;

  // A throwaway customer, rather than a seeded demo account, so this test
  // doesn't need to remember and restore someone else's original organisation.
  const email = `admin-org-e2e-${stamp}@example.com`;
  const who = `Uma Throwaway ${stamp}`;
  const reg = await (await admin.ctx.post("/auth/register", { data: { email, password: "Password123!", name: who } })).json();
  await admin.ctx.post("/auth/2fa/setup", { data: { mfa_token: reg.mfa_token } });

  await page.setViewportSize({ width: 1280, height: 900 });
  await signIn(page, "admin@ticketing.demo");
  await page.getByRole("tab", { name: "Organisations" }).click();
  await page.getByLabel("New organisation").fill(orgName);
  await page.getByRole("button", { name: "Add organisation" }).click();
  const nameField = page.getByRole("textbox", { name: `Name for ${orgName}` });
  await expect(nameField).toHaveValue(orgName);
  await shot(page, "phase-12", "admin-organizations-1280");
  await axe(page, "admin organisations");

  await page.getByRole("combobox", { name: `Kind for ${orgName}` }).click();
  await page.getByRole("option", { name: "Government" }).click();
  await expect(page.getByText(`${orgName} is now a government`)).toBeVisible();

  await nameField.fill(renamed);
  await page.getByRole("button", { name: `Save name for ${orgName}` }).click();
  await expect(page.getByText(`Renamed to ${renamed}`)).toBeVisible();
  const renamedField = page.getByRole("textbox", { name: `Name for ${renamed}` });
  await expect(renamedField).toHaveValue(renamed);

  await page.getByRole("switch", { name: `${renamed} active` }).click();
  await expect(page.getByText(`${renamed} deactivated`)).toBeVisible();

  // The Users tab offers it (inactive orgs stay selectable for whoever
  // already has them, but a fresh assignment needs an active one) - so
  // reactivate before assigning a user to it.
  await page.getByRole("switch", { name: `${renamed} active` }).click();
  await expect(page.getByText(`${renamed} activated`)).toBeVisible();

  await page.goto("/admin?tab=users");
  const userRow = page.getByRole("row", { name: new RegExp(who) });
  await userRow.getByRole("combobox", { name: `Organisation for ${who}` }).click();
  await page.getByRole("option", { name: renamed }).click();
  await expect(page.getByText(`${who} set to ${renamed}`)).toBeVisible();
  await expect(userRow.getByRole("combobox", { name: `Organisation for ${who}` })).toHaveText(renamed);

  await page.getByRole("tab", { name: "Change log" }).click();
  const log = page.getByRole("table", { name: "Change log" });
  await expect(log).toContainText(`Organisation ${renamed}`);
  await expect(log).toContainText("Kind Company to Government");
  await expect(log).toContainText(`Name ${orgName} to ${renamed}`);
  await expect(log).toContainText("Active yes to no");
});
