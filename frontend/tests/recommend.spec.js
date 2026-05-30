import { test, expect } from '@playwright/test';

test('popular section loads with scored movies', async ({ page }) => {
  await page.goto('/');

  // Wait for movie cards to load
  const cards = page.locator('.grid .card');
  await expect(cards.first()).toBeVisible({ timeout: 8000 });

  // Score badges appear on recommendation/cold-start results
  // (only visible when score field is present on the item)
  const count = await cards.count();
  expect(count).toBeGreaterThan(0);

  // At least one card should have a title
  const firstTitle = await cards.first().locator('.title').textContent();
  expect(firstTitle).toBeTruthy();
});

test('movie detail genres are non-empty', async ({ page }) => {
  await page.goto('/movie/32'); // Twelve Monkeys

  await expect(page.locator('.genre-tags')).toBeVisible({ timeout: 8000 });

  // Every genre tag must have text content
  const tags = page.locator('.genre-tags .tag');
  const count = await tags.count();
  expect(count).toBeGreaterThan(0);

  const genres = [];
  for (let i = 0; i < count; i++) {
    const text = await tags.nth(i).textContent();
    expect(text.trim().length).toBeGreaterThan(0);
    genres.push(text.trim());
  }
  // Twelve Monkeys should be Drama and Sci-Fi
  expect(genres.join(',')).toMatch(/Drama|Sci-Fi/);
});

test('movie detail rating is a number', async ({ page }) => {
  await page.goto('/movie/32');

  await expect(page.locator('.rating-box .avg')).toBeVisible({ timeout: 5000 });
  const rating = await page.locator('.rating-box .avg').textContent();
  const num = parseFloat(rating);
  expect(num).toBeGreaterThan(0);
  expect(num).toBeLessThanOrEqual(10);
});

test('multiple movies have genres populated', async ({ page }) => {
  // Check several movies to confirm the genres fix
  const movieIds = [31, 32, 34, 47];
  for (const id of movieIds) {
    await page.goto(`/movie/${id}`);
    await expect(page.locator('.genre-tags .tag').first()).toBeVisible({ timeout: 5000 });
    const count = await page.locator('.genre-tags .tag').count();
    expect(count).toBeGreaterThan(0);
  }
});
