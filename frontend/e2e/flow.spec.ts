import { expect, test } from "@playwright/test";

test("Início lista os 5 casos", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator('[data-testid^="case-card-"]')).toHaveCount(5);
});
