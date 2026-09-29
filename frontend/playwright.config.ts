import { defineConfig, devices } from "@playwright/test";

// Runs against the Docker Compose stack (`docker compose up`), not a
// separately started dev server.
export default defineConfig({
  testDir: "./e2e",
  // A demo account's code works once per 30 s step, so a burst of sign-ins
  // to one account can wait up to 30 s for the next step (e2e/totp.ts).
  timeout: 120_000,
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:5173",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
