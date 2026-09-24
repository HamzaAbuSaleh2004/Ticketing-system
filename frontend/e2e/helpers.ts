import { expect, type Page } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const SEED_PASSWORD = "ChangeMe123!";
export const SHOTS = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "docs", "screenshots");

export async function signIn(page: Page, email: string, password = SEED_PASSWORD) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

export async function fontsReady(page: Page) {
  await page.evaluate(() => document.fonts.ready);
  const loaded = await page.evaluate(() =>
    [...document.fonts].filter((f) => f.status === "loaded").map((f) => f.family),
  );
  expect(loaded.join(",")).toContain("Roboto Flex Variable");
}

export async function shot(page: Page, phase: string, name: string) {
  await fontsReady(page);
  await page.screenshot({ path: path.join(SHOTS, phase, `${name}.png`), fullPage: true });
}
