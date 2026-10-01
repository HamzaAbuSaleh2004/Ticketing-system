import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { apiAs } from "./api";
import { enrollTwoStep, settled, shot, signIn, signInPassword } from "./helpers";
import { nextCode } from "./totp";

/** Phase 23: self-registration is closed by default — an admin provisions
 * the account instead. What these tests actually exercise (the enrolment
 * screens, a wrong code, recovery codes) is unchanged: it's the same "no
 * two-step yet" first sign-in either way. */
async function provisionCustomer(email: string, name: string, password: string) {
  const admin = await apiAs("admin@ticketing.demo");
  await admin.post("/users", { email, name, role: "end_user", password });
}

// Phase 25: light only, regardless of the OS's own color-scheme preference
// (the dark/system options were removed from ThemeMenu; ThemeController
// hardcodes isDark = false). Both OS preferences are exercised here to prove
// that, not just the default one.
for (const osColorScheme of ["light", "dark"] as const) {
  test.describe(`OS prefers ${osColorScheme}`, () => {
    test.use({ colorScheme: osColorScheme });

    test(`renders light regardless (OS prefers ${osColorScheme})`, async ({ page }) => {
      await page.setViewportSize({ width: 1280, height: 900 });
      await page.goto("/_tokens");
      await expect(page.getByRole("heading", { name: "Design tokens" })).toBeVisible();
      // The generated scheme, not a static palette, is on :root.
      const primary = await page.evaluate(() =>
        getComputedStyle(document.documentElement).getPropertyValue("--md-sys-color-primary").trim(),
      );
      expect(primary).toBe("#006688");
      await shot(page, "phase-6", `tokens-${osColorScheme}`);

      await page.goto("/login");
      await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
      // No theme-mode picker left, only the contrast toggle.
      await page.getByRole("button", { name: "Contrast" }).click();
      await expect(page.getByRole("menuitemradio", { name: "Standard contrast" })).toBeVisible();
      await expect(page.getByRole("menuitemradio", { name: /^(Match system|Light|Dark)$/ })).toHaveCount(0);
      await page.keyboard.press("Escape");
      await shot(page, "phase-6", `login-${osColorScheme}-1280`);

      await page.setViewportSize({ width: 360, height: 780 });
      await shot(page, "phase-6", `login-${osColorScheme}-360`);
    });
  });
}

test("fonts: IBM Plex Sans everywhere, no monospace", async ({ page }) => {
  await page.goto("/login");
  const heading = page.getByRole("heading", { name: "Sign in" });
  expect(await heading.evaluate((el) => getComputedStyle(el).fontFamily)).toContain("IBM Plex Sans");
  const button = page.getByRole("button", { name: "Sign in" });
  const style = await button.evaluate((el) => {
    const s = getComputedStyle(el);
    return { font: s.fontFamily, transform: s.textTransform, shadow: s.boxShadow, radius: s.borderRadius };
  });
  expect(style.font).toContain("IBM Plex Sans");
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
  await signInPassword(page, "user1@ticketing.demo", "not-the-password");
  await expect(page.getByText("That email and password don't match an account.")).toBeVisible();
});

test("an admin-provisioned account signs in and enrols two-step verification, landing on the portal", async ({ page }) => {
  const email = `e2e-${Date.now()}@example.com`;
  await provisionCustomer(email, "Pat Example", "Password123!");
  await signInPassword(page, email, "Password123!");
  await expect(page.getByRole("heading", { name: "Set up two-step verification" })).toBeVisible();
  await enrollTwoStep(page);
  await expect(page).toHaveURL(/\/$/);
});

test("two-step verification: setup screens, a wrong code, and a recovery code", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  const email = `twostep-${Date.now()}@example.com`;
  await provisionCustomer(email, "Sam Example", "Password123!");
  await signInPassword(page, email, "Password123!");

  // Setup: QR code plus the manual key; a wrong code is refused.
  await expect(page.getByRole("heading", { name: "Set up two-step verification" })).toBeVisible();
  await expect(page.getByRole("img", { name: "QR code for setting up two-step verification" })).toBeVisible();
  await expect(page.getByLabel("Setup key")).not.toHaveText("…");
  await shot(page, "phase-11", "setup-1280");
  await page.setViewportSize({ width: 360, height: 800 });
  await shot(page, "phase-11", "setup-360");
  await page.emulateMedia({ colorScheme: "dark" });
  await shot(page, "phase-11", "setup-dark-360");
  await page.emulateMedia({ colorScheme: "light" });
  await page.setViewportSize({ width: 1280, height: 900 });
  await settled(page);
  const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  expect(axe.violations.map((v) => v.id), "setup screen axe").toEqual([]);
  await page.getByLabel("6-digit code").fill("000000");
  await page.getByRole("button", { name: "Turn on two-step verification" }).click();
  await expect(page.getByText("That code isn't right. Try the current one.")).toBeVisible();

  // The right code turns it on and shows the recovery codes once.
  const secret = (await page.getByLabel("Setup key").innerText()).replace(/\s/g, "");
  await page.getByLabel("6-digit code").fill(await nextCode(email, secret));
  await page.getByRole("button", { name: "Turn on two-step verification" }).click();
  const codes = page.getByRole("list", { name: "Recovery codes" }).getByRole("listitem");
  await expect(codes).toHaveCount(10);
  const recovery = await codes.first().innerText();
  await shot(page, "phase-11", "recovery-codes-1280");
  await page.getByRole("button", { name: "I've saved them, continue" }).click();
  await expect(page).toHaveURL(/\/$/);
  await page.getByRole("button", { name: /Account/ }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();

  // Next sign-in asks for a code; a recovery code works instead.
  await signInPassword(page, email, "Password123!");
  await expect(page.getByRole("heading", { name: "Enter your code" })).toBeVisible();
  await shot(page, "phase-11", "verify-1280");
  await page.getByRole("button", { name: "Use a recovery code instead" }).click();
  await page.getByLabel("Recovery code").fill(recovery);
  await page.getByRole("button", { name: "Verify" }).click();
  await expect(page).toHaveURL(/\/$/);
});
