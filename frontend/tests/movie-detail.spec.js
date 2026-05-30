import { test, expect } from '@playwright/test';

test('movie detail page shows full information', async ({ page }) => {
  await page.goto('/movie/32', { waitUntil: 'networkidle' }); // Twelve Monkeys

  // Title
  await expect(page.locator('.detail h1')).toBeVisible({ timeout: 10000 });

  // Meta info (year)
  await expect(page.locator('.hero-meta')).toBeVisible();

  // Genres — the key regression check
  const genreTags = page.locator('.genre-tags .tag');
  await expect(genreTags.first()).toBeVisible({ timeout: 8000 });
  const genreCount = await genreTags.count();
  expect(genreCount).toBeGreaterThan(0);

  // Verify all genre tags have non-empty text
  for (let i = 0; i < genreCount; i++) {
    const text = await genreTags.nth(i).textContent();
    expect(text.trim().length).toBeGreaterThan(0);
  }

  // Rating box
  await expect(page.locator('.rating-box .avg')).toBeVisible();
});

test('movie detail navigates from card click', async ({ page }) => {
  await page.goto('/', { waitUntil: 'networkidle' });

  // Wait for cards to load
  await expect(page.locator('.card').first()).toBeVisible({ timeout: 10000 });

  // Click first movie card
  const firstCard = page.locator('.card').first();
  const cardTitle = await firstCard.locator('.title').textContent();
  await firstCard.click();

  // Should be on detail page
  await expect(page.locator('.detail h1')).toBeVisible({ timeout: 10000 });
  const detailTitle = await page.locator('.detail h1').textContent();
  expect(detailTitle).toContain(cardTitle.substring(0, 10));
});

test('nav logo navigates back to home', async ({ page }) => {
  await page.goto('/movie/32', { waitUntil: 'networkidle' });
  await expect(page.locator('.detail h1')).toBeVisible({ timeout: 10000 });

  await page.locator('.logo').click();
  await expect(page).toHaveURL('/');
  await expect(page.locator('.hero h1')).toBeVisible();
});
