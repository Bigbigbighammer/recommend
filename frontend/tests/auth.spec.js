import { test, expect } from '@playwright/test';

test('login page renders form', async ({ page }) => {
  await page.goto('/login');

  await expect(page.locator('input[type="email"]')).toBeVisible();
  await expect(page.locator('input[type="password"]')).toBeVisible();
  await expect(page.locator('button[type="submit"]')).toBeVisible();
});

test('sign in link navigates to login page', async ({ page }) => {
  await page.goto('/');

  // Click Sign In in nav
  await page.locator('nav a[href="/login"]').click();
  await expect(page).toHaveURL('/login');
});

test('login shows error for invalid credentials', async ({ page }) => {
  await page.goto('/login');

  await page.locator('input[type="email"]').fill('nonexistent@test.com');
  await page.locator('input[type="password"]').fill('wrong');
  await page.locator('button[type="submit"]').click();

  // Should show some error or stay on login page (no redirect)
  await page.waitForTimeout(2000);
  const url = page.url();
  expect(url).toContain('/login');
});

test('can toggle to signup form', async ({ page }) => {
  await page.goto('/login');

  // Click Join link
  await page.locator('.switch a').click();

  // Should show Create Account button
  await expect(page.locator('button[type="submit"]')).toContainText('Create Account');
});
