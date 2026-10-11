import { defineConfig, devices } from "@playwright/test";

// Chromium only (disk budget). Browser revision is pinned via @playwright/test 1.62.0 (chromium-1234,
// already in ~/Library/Caches/ms-playwright). Start API + web yourself or let webServer do it.
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  retries: 0,
  reporter: [["list"]],
  use: { baseURL: process.env.QMINT_WEB_URL ?? "http://localhost:3000", trace: "retain-on-failure" },
  projects: [
    { name: "desktop-1440", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
    { name: "mobile-390", use: { ...devices["Desktop Chrome"], viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
  webServer: process.env.QMINT_WEB_URL
    ? undefined
    : { command: "pnpm dev", url: "http://localhost:3000/design-system", reuseExistingServer: true, timeout: 120_000 },
});
