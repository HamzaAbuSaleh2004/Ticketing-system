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

test("dashboard: tiles, charts with hover + keyboard + table view, range filter", async ({ page }) => {
  const summary = await (await apiAs("agent1@ticketing.demo")).get("/analytics/summary");
  await page.setViewportSize({ width: 1600, height: 1000 });
  await signIn(page, "agent1@ticketing.demo");
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Dashboard" }).click();
  await expect(page).toHaveURL(/\/agent\/dashboard/);

  const created = page.getByRole("region", { name: "Tickets created", exact: true });
  await expect(created).toContainText(summary.created.toLocaleString());
  await expect(page.getByRole("region", { name: "SLA breaches" })).toContainText(`${summary.sla_breaches.response} first-reply`);
  await expect(page.getByRole("region", { name: "Backlog by status" })).toContainText("In progress");
  await shot(page, "phase-9", "dashboard-1600");

  // Hover shows a per-day tooltip (value first).
  const chart = page.getByRole("img", { name: /Column chart, 30 days/ });
  const box = (await chart.boundingBox())!;
  await page.mouse.move(box.x + box.width - 12, box.y + box.height / 2);
  await expect(page.getByRole("status").filter({ hasText: /\d+ tickets?/ }).first()).toBeVisible();
  await shot(page, "phase-9", "dashboard-hover-1600");

  // Keyboard reads the same values; a table view is always available.
  await chart.focus();
  await page.keyboard.press("ArrowLeft");
  await expect(page.getByRole("status").filter({ hasText: /\d+ tickets?/ }).first()).toBeVisible();
  await page.getByRole("button", { name: "Show as table" }).first().click();
  await expect(page.getByRole("table", { name: "Tickets created per day" }).getByRole("row")).toHaveCount(31);

  await page.getByRole("button", { name: "Last 7 days" }).click();
  await expect(page).toHaveURL(/days=7/);
  await expect(page.getByRole("img", { name: /Column chart, 7 days/ })).toBeVisible();

  await page.setViewportSize({ width: 1280, height: 900 });
  await page.getByRole("button", { name: "Last 30 days" }).click();
  await shot(page, "phase-9", "dashboard-1280");
  await axe(page, "dashboard light");
  await page.emulateMedia({ colorScheme: "dark" });
  await shot(page, "phase-9", "dashboard-dark-1280");
  await axe(page, "dashboard dark");
  await page.setViewportSize({ width: 390, height: 844 });
  await shot(page, "phase-9", "dashboard-dark-390");
});

test("admin: SLA policy, categories and team edits are saved and logged", async ({ page }) => {
  const admin = await apiAs("admin@ticketing.demo");
  const current = (await admin.get("/sla-policies")).find((p: { priority: string }) => p.priority === "low");
  const newReply = current.response_minutes === 400 ? 420 : 400;
  const categoryName = `Returns ${Date.now() % 100000}`;
  try {

  await page.setViewportSize({ width: 1280, height: 900 });
  await signIn(page, "admin@ticketing.demo");
  await expect(page).toHaveURL(/\/admin$/);
  await expect(page.getByRole("table", { name: "Users" })).toContainText("Sasha Senior");
  await shot(page, "phase-9", "admin-users-1280");
  await axe(page, "admin users");

  // A team change.
  await page.getByRole("combobox", { name: "Team for Tom Tier1" }).click();
  await page.getByRole("option", { name: "Senior" }).click();
  await expect(page.getByText("Tom Tier1 moved to Senior")).toBeVisible();
  await page.getByRole("combobox", { name: "Team for Tom Tier1" }).click();
  await page.getByRole("option", { name: "Tier 1" }).click();
  await expect(page.getByText("Tom Tier1 moved to Tier 1")).toBeVisible();

  // SLA policies: the rule is stated; edit + save.
  await page.getByRole("tab", { name: "SLA policies" }).click();
  await expect(page.getByText("Changes apply to tickets created after you save.")).toBeVisible();
  const lowReply = page.getByRole("spinbutton", { name: "First reply within (minutes) for Low" });
  await lowReply.fill(String(newReply));
  await page.getByRole("row", { name: /^Low/ }).getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Low targets saved")).toBeVisible();
  await shot(page, "phase-9", "admin-sla-1280");
  await axe(page, "admin sla");

  // Categories: add, then deactivate.
  await page.getByRole("tab", { name: "Categories" }).click();
  await page.getByLabel("New category").fill(categoryName);
  await page.getByRole("button", { name: "Add category" }).click();
  await expect(page.getByRole("table", { name: "Categories" })).toContainText(categoryName);
  await page.getByRole("switch", { name: `${categoryName} active` }).click();
  await expect(page.getByText(`${categoryName} deactivated`)).toBeVisible();
  await shot(page, "phase-9", "admin-categories-1280");

  // All of it is in the change log.
  await page.getByRole("tab", { name: "Change log" }).click();
  const log = page.getByRole("table", { name: "Change log" });
  await expect(log).toContainText("SLA policy Low");
  await expect(log).toContainText(`First reply (min) ${current.response_minutes} to ${newReply}`);
  await expect(log).toContainText(`Category ${categoryName}`);
  await expect(log).toContainText("Active yes to no");
  await expect(log).toContainText("User Tom Tier1");
  await expect(log).toContainText("Team Tier 1 to Senior");
  await shot(page, "phase-9", "admin-changes-1280");

  // Two-step verification reset, on a throwaway account (the demo accounts stay enrolled).
  const stamp = Date.now() % 1_000_000;
  const who = `Lou Lostphone ${stamp}`;
  const email = `lost-phone-${stamp}@example.com`;
  const reg = await (await admin.ctx.post("/auth/register", { data: { email, password: "Password123!", name: who } })).json();
  const setup = await (await admin.ctx.post("/auth/2fa/setup", { data: { mfa_token: reg.mfa_token } })).json();
  const enabled = await admin.ctx.post("/auth/2fa/enable", { data: { mfa_token: reg.mfa_token, code: await nextCode(email, setup.secret) } });
  expect(enabled.ok()).toBeTruthy();
  // Made through the API after the table loaded, so load it again.
  await page.goto("/admin?tab=users");
  const row = page.getByRole("row", { name: new RegExp(who) });
  await expect(row).toContainText("On");
  await row.getByRole("button", { name: `Reset two-step verification for ${who}` }).click();
  const dialog = page.getByRole("dialog", { name: `Reset two-step verification for ${who}?` });
  await shot(page, "phase-11", "admin-reset-2fa-1280");
  await dialog.getByRole("button", { name: "Reset" }).click();
  await expect(page.getByText(`Two-step verification reset for ${who}`)).toBeVisible();
  await expect(row).toContainText("Not set up yet");
  const relogin = await (await admin.ctx.post("/auth/login", { data: { email, password: "Password123!" } })).json();
  expect(relogin.mfa).toBe("enroll");
  await page.getByRole("tab", { name: "Change log" }).click();
  await expect(log).toContainText("Two-step verification reset");

  } finally {
    // Leave the dev data at the seeded targets (low: 8h / 72h).
    await admin.patch("/sla-policies/low", { response_minutes: 480, resolution_minutes: 72 * 60 });
  }
});
