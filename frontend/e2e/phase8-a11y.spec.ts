import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { signIn } from "./helpers";

async function scan(page: Page, label: string) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  const summary = results.violations.map((v) => `${v.id} (${v.impact}): ${v.nodes.length} node(s) e.g. ${v.nodes[0]?.target.join(" ")} ${v.nodes[0]?.failureSummary?.split("\n")[1] ?? ""}`);
  console.log(`[axe] ${label}: ${results.violations.length} violation(s)${summary.length ? "\n  " + summary.join("\n  ") : ""}`);
  expect(summary, label).toEqual([]);
}

for (const colorScheme of ["light", "dark"] as const) {
  test(`agent screens have no axe violations (${colorScheme})`, async ({ page }) => {
    await page.emulateMedia({ colorScheme });
    await page.setViewportSize({ width: 1440, height: 900 });
    await signIn(page, "agent1@ticketing.demo");
    await expect(page.getByRole("table", { name: "Tickets" })).toBeVisible();
    await scan(page, `queue ${colorScheme}`);
    await page.getByRole("table", { name: "Tickets" }).getByRole("link").first().click();
    await expect(page.getByRole("complementary", { name: "Ticket properties" })).toBeVisible();
    await page.getByRole("button", { name: "Internal note" }).click();
    await scan(page, `ticket ${colorScheme}`);
  });
}
