import { defineConfig, devices } from "@playwright/test";

// Production targets (override via env if the URLs change).
const FRONTEND = process.env.E2E_FRONTEND ?? "https://agrioskenya.vercel.app";

export default defineConfig({
  testDir: "./tests",
  // Render free tier cold-starts can take >60s; keep timeouts generous.
  timeout: 120_000,
  expect: { timeout: 20_000 },
  // Brief: "retry transient failures once".
  retries: 1,
  workers: 1,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: FRONTEND,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    ignoreHTTPSErrors: false,
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
});
