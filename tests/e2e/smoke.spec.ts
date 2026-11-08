import { test, expect } from '@playwright/test';

test.describe('Smoke Health Check', () => {
  test('Aplikasi web merespons dan memiliki title', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/./);
  });
});
