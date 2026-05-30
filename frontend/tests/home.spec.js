import { test, expect } from '@playwright/test';

test('home page loads with hero and popular movies', async ({ page }) => {
  await page.goto('/');

  // Hero section
  await expect(page.locator('.hero h1')).toContainText('Discover your');

  // Popular section should load
  const sectionHeadings = page.locator('.section-head h2');
  await expect(sectionHeadings.first()).toBeVisible({ timeout: 8000 });
  const headingText = await sectionHeadings.first().textContent();
  expect(['Popular', 'For You', 'Latest']).toContain(headingText);

  // Movie cards in grid
  const cards = page.locator('.grid .card');
  await expect(cards.first()).toBeVisible({ timeout: 8000 });
  const count = await cards.count();
  expect(count).toBeGreaterThan(0);

  // Cards have titles
  const firstTitle = await cards.first().locator('.title').textContent();
  expect(firstTitle).toBeTruthy();
});

test('movie cards show genres when available', async ({ page }) => {
  await page.goto('/');

  const firstCard = page.locator('.card').first();
  await expect(firstCard).toBeVisible({ timeout: 8000 });

  // Genres should be present (our fix ensured this)
  const genres = firstCard.locator('.genres');
  await expect(genres.first()).toBeVisible({ timeout: 5000 });
  const text = await genres.first().textContent();
  expect(text.trim().length).toBeGreaterThan(0);

  // Card links to movie detail
  const href = await firstCard.getAttribute('href');
  expect(href).toMatch(/\/movie\/\d+/);
});

test('nav links are present', async ({ page }) => {
  await page.goto('/');

  await expect(page.locator('.logo')).toHaveText('Rec');
  await expect(page.locator('nav .nav-links a[href="/search"]')).toBeVisible();
  await expect(page.locator('nav .nav-links a[href="/profile"]')).toBeVisible();
});
