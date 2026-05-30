import { test, expect } from '@playwright/test';

test('search page has input and shows hint', async ({ page }) => {
  await page.goto('/search');

  await expect(page.locator('.search-bar input')).toBeVisible();
  await expect(page.locator('.search-bar button')).toBeVisible();
  await expect(page.locator('.hint')).toContainText('Type a keyword');
});

test('search finds movies', async ({ page }) => {
  await page.goto('/search');

  await page.locator('.search-bar input').fill('Toy');
  await page.locator('.search-bar button').click();

  // Results should appear
  await expect(page.locator('.grid .card').first()).toBeVisible({ timeout: 8000 });

  // Count badge should show results
  await expect(page.locator('.count')).toBeVisible();

  // Results should contain Toy Story
  const titles = page.locator('.card .title');
  const first = await titles.first().textContent();
  expect(first.toLowerCase()).toContain('toy');
});

test('search with no results shows empty state', async ({ page }) => {
  await page.goto('/search');

  await page.locator('.search-bar input').fill('xyznonexistentmovie');
  await page.locator('.search-bar button').click();

  await expect(page.locator('.empty')).toContainText('No results', { timeout: 5000 });
});

test('nav search link navigates to search page', async ({ page }) => {
  await page.goto('/');
  await page.locator('nav a[href="/search"]').click();
  await expect(page).toHaveURL('/search');
  await expect(page.locator('.search-bar input')).toBeVisible();
});
