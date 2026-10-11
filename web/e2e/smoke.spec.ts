import { expect, test } from "@playwright/test";

// Phase-1 smoke: every route renders, the design system shows all evidence labels, no horizontal scroll.
const ROUTES = ["/", "/app", "/lab/mint", "/lab/attack", "/benchmarks", "/certificates", "/research", "/docs", "/design-system"];

for (const route of ROUTES) {
  test(`renders ${route}`, async ({ page }) => {
    const res = await page.goto(route);
    expect(res?.status()).toBe(200);
    await expect(page.locator("main#main")).toBeVisible();
    await expect(page.locator("h1")).toHaveCount(1);
    const width = page.viewportSize()?.width ?? 0;
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    expect(scrollWidth).toBeLessThanOrEqual(width);
  });
}

test("design system lists all 21 evidence labels", async ({ page }) => {
  await page.goto("/design-system");
  await expect(page.locator("#evidence [data-slot=evidence-label]")).toHaveCount(21);
});

test("API proxy answers (requires API on :8787)", async ({ request }) => {
  const res = await request.get("/api/v1/health");
  expect(res.ok()).toBeTruthy();
});
