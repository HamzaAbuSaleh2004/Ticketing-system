import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { SEED_PASSWORD, enterCode, signInPassword } from "./helpers";

async function scan(page: Page, label: string) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  const summary = results.violations.map((v) => `${v.id} (${v.impact}): ${v.nodes.length} node(s) e.g. ${v.nodes[0]?.target.join(" ")}`);
  console.log(`[axe] ${label}: ${results.violations.length} violation(s)${summary.length ? "\n  " + summary.join("\n  ") : ""}`);
  expect(summary, label).toEqual([]);
}

for (const colorScheme of ["light", "dark"] as const) {
  test(`end-user screens have no axe violations (${colorScheme})`, async ({ page }) => {
    await page.emulateMedia({ colorScheme });
    // The second sign-in step is scanned too.
    await signInPassword(page, "user1@ticketing.demo", SEED_PASSWORD);
    await expect(page.getByRole("heading", { name: "Enter your code" })).toBeVisible();
    await scan(page, `two-step verify ${colorScheme}`);
    await enterCode(page, "user1@ticketing.demo");
    await expect(page).toHaveURL(/\/$/);
    await scan(page, `home ${colorScheme}`);

    await page.getByRole("searchbox", { name: "Search help articles" }).fill("how do you protect my personal data");
    await page.keyboard.press("Enter");
    await expect(page.getByRole("region", { name: /help articles? match/ })).toBeVisible();
    await page.waitForTimeout(500);
    await scan(page, `search results ${colorScheme}`);

    await page.goto("/requests/new");
    await scan(page, `new request ${colorScheme}`);

    await page.goto("/help/how-we-handle-your-data");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await scan(page, `article ${colorScheme}`);

    await page.goto("/");
    const first = page.getByRole("list").first().getByRole("link").first();
    if (await first.count()) {
      await first.click();
      await expect(page.getByRole("form", { name: "Reply" })).toBeVisible();
      await scan(page, `request ${colorScheme}`);
    }
  });
}
