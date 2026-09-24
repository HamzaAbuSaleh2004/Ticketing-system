import { expect, test } from "@playwright/test";
import { shot, signIn } from "./helpers";

// Acceptance captures against the demo-seeded stack (docker compose down -v && up --build).
test("acceptance captures with demo data", async ({ page, browser }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await signIn(page, "agent1@ticketing.demo");
  const table = page.getByRole("table", { name: "Tickets" });
  await expect(table.getByRole("link", { name: "Charged for 14 seats but we only have 6 people" })).toBeVisible();
  // Every SLA state is on screen with its text label.
  await expect(table.getByText("Paused").first()).toBeVisible();
  await shot(page, "phase-10", "queue-demo-1600");

  // t11: escalated, breached, with internal notes.
  await table.getByRole("link", { name: "Charged for 14 seats but we only have 6 people" }).click();
  await expect(page.getByText("Internal note").first()).toBeVisible();
  await shot(page, "phase-10", "ticket-demo-1600");

  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Dashboard" }).click();
  await expect(page.getByRole("region", { name: "Tickets created", exact: true })).toBeVisible();
  await shot(page, "phase-10", "dashboard-demo-1600");

  const customerCtx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const customer = await customerCtx.newPage();
  await signIn(customer, "user1@ticketing.demo");
  await expect(customer.getByRole("link", { name: /Two-factor codes rejected on my new phone/ })).toBeVisible();
  await expect(customer.getByText("Waiting on you").first()).toBeVisible();
  await shot(customer, "phase-10", "enduser-home-demo-1280");
  await customerCtx.close();
});
