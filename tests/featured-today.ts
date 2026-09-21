/**
 * TODAY'S CONSTELLATION, asked of the rotation itself against the catalog the
 * site is actually serving.
 *
 * Never a hard-coded name. `FEATURED_ANCHOR_DAY` is 2026-08-20 and the
 * rotation advances one entry per UTC day, so the two assertions in
 * `browser.spec.ts` that named "GPS" were true for exactly one day and then
 * failed on every project, every day, until somebody looked.
 *
 * This is why the rotation lives in `src/featured-constellation.ts` rather
 * than in `src/main.ts`: a Playwright spec cannot import `main.ts` at all,
 * because its first line is `import "./styles.css"`.
 */
import { expect, type Page } from "@playwright/test";

import { featuredConstellation, utcDayNumber } from "../src/featured-constellation";

export async function featuredToday(page: Page): Promise<string> {
  // Absolute, off the page's own URL, rather than relying on the request
  // context inheriting `baseURL`: a relative path here throws "Invalid URL"
  // wherever it does not, and that failure reads like a product bug.
  const manifestUrl = new URL("data/manifest.json", page.url()).toString();
  const manifest = await (await page.request.get(manifestUrl)).json();
  const catalog = await (await page.request.get(new URL(manifest.catalog.path, manifestUrl).toString())).json();
  const pick = featuredConstellation(catalog.satellites, utcDayNumber(new Date()));
  expect(pick, "the served catalog carries at least one fleet from the rotation").not.toBeNull();
  return pick!.constellation;
}
