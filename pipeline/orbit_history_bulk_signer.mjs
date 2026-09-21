// Mint a signed download URL for one file on space-track's public bulk-TLE
// share, by driving the share's own web client exactly as a visitor would.
//
// WHY THIS EXISTS
// ---------------
// space-track's API documentation rate-limits the `gp_history` class to
// "1 / lifetime" and tells callers to fetch bulk history from their cloud
// storage share instead. That share is hosted on Sync.com, whose public links
// are end-to-end encrypted: the file list and the per-file download URL are
// produced by client-side JavaScript holding the link key from the URL. There
// is no documented REST endpoint to substitute for it.
//
// So this script runs the real client once, lets it mint the signed URL, and
// prints it. The bytes are then transferred by
// `pipeline/orbit_history_backfill.py`, which can resume, verify and rate-limit
// far better than a browser can. The signed URL is a plain HTTPS GET that
// honours Range requests and serves the file decrypted.
//
// NOTHING HERE TOUCHES space-track.org. No API request, no credential, no
// session. This consumes none of Sean's space-track API rate limit.
//
//   node orbit_history_bulk_signer.mjs <share-url>                  -> listing
//   node orbit_history_bulk_signer.mjs <share-url> <name> [name...]  -> + urls
//
// Output is one JSON document on stdout.

import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
// The repository's own devDependency; resolved from the repo root so the
// script works when invoked by absolute path from anywhere.
const { chromium } = require(path.join(here, '..', 'node_modules', 'playwright'));

const SHARE = process.argv[2];
const WANTED = process.argv.slice(3);
if (!SHARE) {
  console.error('usage: orbit_history_bulk_signer.mjs <share-url> [filename...]');
  process.exit(2);
}

const browser = await chromium.launch({ headless: true });
try {
  const context = await browser.newContext({
    acceptDownloads: true,
    viewport: { width: 1280, height: 2400 },
  });
  const page = await context.newPage();

  // The link listing carries exact byte sizes; the rendered table carries the
  // (client-decrypted) names. They join on sync_id / data-row-id.
  let pathitems = [];
  page.on('response', async (response) => {
    if (!response.url().includes('/api/v1/linkpathlist')) return;
    try {
      const body = await response.json();
      if (Array.isArray(body.pathitems) && body.pathitems.length > pathitems.length) {
        pathitems = body.pathitems;
      }
    } catch { /* a non-JSON response is not fatal; the DOM is the fallback */ }
  });

  await page.goto(SHARE, { waitUntil: 'networkidle', timeout: 120000 });
  await page.waitForTimeout(4000);

  // The table is virtualised: without scrolling only the first screenful of
  // rows exists in the DOM, and an enumeration would silently come back short.
  let previous = -1;
  for (let attempt = 0; attempt < 60; attempt += 1) {
    const count = await page.locator('tr[data-row-id]').count();
    if (count === previous && attempt > 2) break;
    previous = count;
    await page.mouse.wheel(0, 4000);
    await page.waitForTimeout(700);
  }

  const rows = await page.evaluate(() =>
    [...document.querySelectorAll('tr[data-row-id]')].map((row) => {
      const cells = [...row.querySelectorAll('td')].map((c) => (c.innerText || '').trim());
      return { rowId: row.getAttribute('data-row-id'), name: cells[1], modified: cells[2] };
    }),
  );
  const bytesById = Object.fromEntries(pathitems.map((p) => [String(p.sync_id), p.size]));
  const listing = rows
    .filter((r) => r.name)
    .map((r) => ({ name: r.name, syncId: r.rowId, bytes: bytesById[r.rowId] ?? null, modified: r.modified }));

  const urls = {};
  for (const name of WANTED) {
    const row = listing.find((r) => r.name === name);
    if (!row) { urls[name] = { error: 'not present on the share' }; continue; }
    try {
      const tr = page.locator(`tr[data-row-id="${row.syncId}"]`);
      await tr.scrollIntoViewIfNeeded();
      await tr.getByRole('button', { name: 'More' }).click();
      await page.waitForTimeout(800);
      const pending = page.waitForEvent('download', { timeout: 90000 });
      await page.getByRole('menuitem', { name: /^Download$/i }).first().click();
      const download = await pending;
      urls[name] = { url: download.url(), filename: download.suggestedFilename() };
      // Cancel immediately: the browser must not transfer the bytes. Python
      // does that, with resume and verification.
      await download.cancel().catch(() => {});
      await page.waitForTimeout(1200);
    } catch (error) {
      urls[name] = { error: String(error && error.message ? error.message : error).slice(0, 300) };
    }
  }

  console.log(JSON.stringify({
    share: SHARE,
    userAgent: await page.evaluate(() => navigator.userAgent),
    listing,
    urls,
  }));
} finally {
  await browser.close();
}
