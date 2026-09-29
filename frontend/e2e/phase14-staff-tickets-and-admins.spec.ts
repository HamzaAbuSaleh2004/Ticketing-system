import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { apiAs } from "./api";
import { shot, signIn, signInPassword, enrollTwoStep } from "./helpers";

async function axe(page: Page, label: string) {
  const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  const summary = r.violations.map((v) => `${v.id}: ${v.nodes.length} e.g. ${v.nodes[0]?.target.join(" ")}`);
  console.log(`[axe] ${label}: ${r.violations.length} violation(s) ${summary.join("; ")}`);
  expect(summary, label).toEqual([]);
}

test("agent creates an unclaimed ticket for an organisation, then links it to a customer who just registered", async ({
  page,
  browser,
}) => {
  const admin = await apiAs("admin@ticketing.demo");
  const stamp = Date.now() % 100000;
  const orgName = `Harborline Logistics ${stamp}`;
  await admin.post("/organizations", { name: orgName, kind: "company" });

  await page.setViewportSize({ width: 1280, height: 900 });
  await signIn(page, "agent1@ticketing.demo");
  await page.getByRole("link", { name: "New ticket" }).click();
  await expect(page).toHaveURL(/\/agent\/tickets\/new/);

  await page.getByRole("button", { name: "No account yet" }).click();
  await page.getByRole("combobox", { name: "Organisation" }).click();
  await page.getByRole("option", { name: orgName }).click();
  const subject = `Phone call from ${orgName} (${stamp})`;
  await page.getByLabel("Subject").fill(subject);
  await page.getByLabel("Details").fill("They called about a delayed shipment; no account yet.");
  await shot(page, "phase-14", "new-ticket-unclaimed-1280");
  await axe(page, "new ticket form");
  await page.getByRole("button", { name: "Create ticket" }).click();
  await expect(page).toHaveURL(/\/agent\/tickets\/\d+$/);

  const ticketSection = page.getByRole("region", { name: "Ticket" });
  await expect(page.getByText("No customer linked yet.")).toBeVisible();
  await expect(ticketSection.getByText(orgName, { exact: true })).toBeVisible();

  // A brand-new customer registers, unrelated to this ticket so far.
  const customerCtx = await browser.newContext();
  const customerPage = await customerCtx.newPage();
  const email = `harborline-contact-${stamp}@example.com`;
  await customerPage.goto("/register");
  await customerPage.getByLabel("Name").fill("Harborline Contact");
  await customerPage.getByLabel("Email").fill(email);
  await customerPage.getByLabel("Password").fill("Password123!");
  await customerPage.getByRole("button", { name: "Create account" }).click();
  await enrollTwoStep(customerPage);
  await expect(customerPage).toHaveURL(/\/$/);
  await expect(customerPage.getByText("You haven't sent us anything yet")).toBeVisible();

  // The agent links the ticket to that new customer.
  await page.getByRole("combobox", { name: "Link a customer" }).fill("Harborline Contact");
  await page.getByRole("option", { name: new RegExp(email) }).click();
  await shot(page, "phase-14", "workspace-claim-1280");
  await page.getByRole("button", { name: "Link" }).click();
  await expect(page.getByText(`Opened by Harborline Contact, ${email}`)).toBeVisible();

  // The customer now sees it.
  await customerPage.reload();
  await expect(customerPage.getByText(subject)).toBeVisible();
  await customerCtx.close();
});

test("admin creates a new admin account, who signs in and can demote the first one", async ({ page }) => {
  const stamp = Date.now() % 100000;
  const email = `manager-${stamp}@liverx.me`;
  const name = `Manager ${stamp}`;

  await page.setViewportSize({ width: 1280, height: 900 });
  await signIn(page, "admin@ticketing.demo");
  await page.goto("/admin?tab=users");
  await page.getByRole("button", { name: "Add admin or agent" }).click();
  const dialog = page.getByRole("dialog", { name: "Add admin or agent" });
  await expect(dialog).toBeVisible();
  await dialog.getByLabel(/^Name/).fill(name);
  await dialog.getByLabel(/^Email/).fill(email);
  await dialog.getByRole("combobox", { name: "Role" }).click();
  await page.getByRole("option", { name: "Admin" }).click();
  await dialog.getByLabel(/^Password/).fill("Password123!");
  await dialog.getByLabel("Confirm password").fill("Password123!");
  await shot(page, "phase-14", "admin-add-staff-dialog-1280");
  await axe(page, "add staff dialog");
  await dialog.getByRole("button", { name: "Add" }).click();
  await expect(page.getByText(`${name} added as admin`)).toBeVisible();
  const row = page.getByRole("row", { name: new RegExp(name) });
  await expect(row).toContainText(email);

  // The new admin signs in for the first time and enrols their own 2FA.
  await page.getByRole("button", { name: /Account/ }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await signInPassword(page, email, "Password123!");
  await enrollTwoStep(page);
  await expect(page).toHaveURL(/\/admin$/);
  await page.goto("/admin?tab=users");
  await expect(page.getByRole("row", { name: new RegExp(name) })).toContainText("On");

  // The new admin can demote the one who created them (then restore it, so
  // later specs relying on admin@ticketing.demo staying an admin still pass).
  await page.getByRole("combobox", { name: "Role for Ada Admin" }).click();
  await page.getByRole("option", { name: "Agent" }).click();
  await expect(page.getByText("Ada Admin is now agent")).toBeVisible();
  await expect(page.getByRole("row", { name: /Ada Admin/ })).toContainText("Agent");

  await page.getByRole("combobox", { name: "Role for Ada Admin" }).click();
  await page.getByRole("option", { name: "Admin" }).click();
  await expect(page.getByText("Ada Admin is now admin")).toBeVisible();
  await expect(page.getByRole("row", { name: /Ada Admin/ })).toContainText("Admin");
});
