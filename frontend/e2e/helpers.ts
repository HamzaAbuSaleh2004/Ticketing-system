import { expect, type Page } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { nextCode, withCode } from "./totp";

export const SEED_PASSWORD = "ChangeMe123!";
export const SHOTS = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "docs", "screenshots");

export async function signInPassword(page: Page, email: string, password = SEED_PASSWORD) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

/** Password, then the second step, as a person would. `secret` is only
 * needed for an account enrolled with its own secret (not the shared demo
 * one), e.g. one enrolled through the API with a fresh `/2fa/setup` call. */
export async function signIn(page: Page, email: string, password = SEED_PASSWORD, secret?: string) {
  await signInPassword(page, email, password);
  await enterCode(page, email, secret);
}

/** The "Enter your code" screen, for a demo account (or any account, given
 * its own secret). */
export async function enterCode(page: Page, email: string, secret?: string) {
  await withCode(
    email,
    async (code) => {
      await page.getByLabel("6-digit code").fill(code);
      await page.getByRole("button", { name: "Verify" }).click();
      // Signed in (left /login), or the code was refused (already used).
      await page.waitForFunction(
        () => !location.pathname.startsWith("/login") || document.body.innerText.includes("That code isn't right"),
      );
      return !new URL(page.url()).pathname.startsWith("/login");
    },
    secret,
  );
}

/** First-time setup on the enrolment screen: reads the key shown under the
 * QR code, as someone typing it into their app would. Returns the secret. */
export async function enrollTwoStep(page: Page): Promise<string> {
  const key = page.getByLabel("Setup key");
  await expect(key).not.toHaveText("…");
  const secret = (await key.innerText()).replace(/\s/g, "");
  await page.getByLabel("6-digit code").fill(await nextCode(`enrol:${secret}`, secret));
  await page.getByRole("button", { name: "Turn on two-step verification" }).click();
  await expect(page.getByRole("list", { name: "Recovery codes" })).toBeVisible();
  await page.getByRole("button", { name: "I've saved them, continue" }).click();
  return secret;
}

export async function fontsReady(page: Page) {
  await page.evaluate(() => document.fonts.ready);
  const loaded = await page.evaluate(() =>
    [...document.fonts].filter((f) => f.status === "loaded").map((f) => f.family),
  );
  expect(loaded.join(",")).toContain("IBM Plex Sans");
}

/** Waits out the settled state, not a frame of an entrance, snackbar or
 * theme-switch transition (two frames first, so just-triggered ones exist).
 * Anything sampling computed styles or colours — a screenshot, an axe scan —
 * should wait for this first, or it can catch a mid-transition frame that
 * never actually appears to a person (a CSS `transition` on `background-color`
 * or `color`, e.g. after `emulateMedia`, interpolates through combinations
 * neither endpoint uses). */
export async function settled(page: Page) {
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
  // Infinite ones (spinners, skeleton pulse) never finish, so only finite ones count.
  await page.waitForFunction(() =>
    document
      .getAnimations()
      .filter((a) => a.effect?.getComputedTiming().iterations !== Infinity)
      .every((a) => a.playState !== "running"),
  );
}

export async function shot(page: Page, phase: string, name: string) {
  await fontsReady(page);
  await settled(page);
  await page.screenshot({ path: path.join(SHOTS, phase, `${name}.png`), fullPage: true });
}
