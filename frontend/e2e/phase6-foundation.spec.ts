import { expect, test } from "@playwright/test";
import { shot, signIn } from "./helpers";

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`${colorScheme} theme`, () => {
    test.use({ colorScheme });

    test(`tokens and login screenshots (${colorScheme})`, async ({ page }) => {
      await page.setViewportSize({ width: 1280, height: 900 });
      await page.goto("/_tokens");
      await expect(page.getByRole("heading", { name: "Design tokens" })).toBeVisible();
      // The generated scheme, not a static palette, is on :root.
      const primary = await page.evaluate(() =>
        getComputedStyle(document.documentElement).getPropertyValue("--md-sys-color-primary").trim(),
      );
      expect(primary).toBe(colorScheme === "light" ? "#005147" : "#8dd4c5");
      await shot(page, "phase-6", `tokens-${colorScheme}`);

      await page.goto("/login");
      await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
      await shot(page, "phase-6", `login-${colorScheme}-1280`);

      await page.setViewportSize({ width: 360, height: 780 });
      await shot(page, "phase-6", `login-${colorScheme}-360`);
    });
  });
}

test("fonts: display is Google Sans Flex, body is Roboto Flex, no monospace", async ({ page }) => {
  await page.goto("/login");
  const heading = page.getByRole("heading", { name: "Sign in" });
  expect(await heading.evaluate((el) => getComputedStyle(el).fontFamily)).toContain("Google Sans Flex");
  const button = page.getByRole("button", { name: "Sign in" });
  const style = await button.evaluate((el) => {
    const s = getComputedStyle(el);
    return { font: s.fontFamily, transform: s.textTransform, shadow: s.boxShadow, radius: s.borderRadius };
  });
  expect(style.font).toContain("Roboto Flex");
  expect(style.transform).toBe("none");
  expect(style.shadow).toBe("none");
  expect(style.radius).toBe("9999px");
});

test("role-based redirect after sign-in and RoleGate", async ({ page }) => {
  await page.goto("/agent");
  await expect(page).toHaveURL(/\/login$/);

  await signIn(page, "user1@ticketing.demo");
  await expect(page).toHaveURL(/\/$/);
  await page.goto("/agent");
  await expect(page).toHaveURL(/\/$/); // an end user can't open the console
  await page.getByRole("button", { name: /Account/ }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();

  await signIn(page, "agent1@ticketing.demo");
  await expect(page).toHaveURL(/\/agent$/);
  await page.goto("/admin");
  await expect(page).toHaveURL(/\/agent$/);
  await page.getByRole("button", { name: /Account/ }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();

  await signIn(page, "admin@ticketing.demo");
  await expect(page).toHaveURL(/\/admin$/);
  await expect(page.getByRole("link", { name: "Admin" })).toHaveAttribute("aria-current", "page");
  await page.setViewportSize({ width: 1280, height: 720 });
  await shot(page, "phase-6", "admin-shell-rail-1280");
  await page.setViewportSize({ width: 360, height: 720 });
  await shot(page, "phase-6", "admin-shell-bottom-bar-360");
});

test("wrong password shows a clear error", async ({ page }) => {
  await signIn(page, "user1@ticketing.demo", "not-the-password");
  await expect(page.getByText("That email and password don't match an account.")).toBeVisible();
});

test("register creates an end-user account and lands on the portal", async ({ page }) => {
  const email = `e2e-${Date.now()}@example.com`;
  await page.goto("/register");
  await page.getByLabel("Name").fill("Pat Example");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("Password123!");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/$/);
});
