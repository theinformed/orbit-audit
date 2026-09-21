// Captures the catalog-filter healing flows Sean asked for: the US Navy
// scenario end-to-end (missions emptied, then one owner click that heals),
// the calm all-deselected globe, and the "only" affordance.
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";

const outDir = process.argv[2];
const baseURL = process.argv[3] ?? "http://127.0.0.1:5346/";
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1500, height: 950 }, deviceScaleFactor: 1 });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
await page.addInitScript(() => {
  try { window.localStorage.setItem("space-explorer-hide-welcome-v1", "1"); } catch { /* ignore */ }
});
await page.goto(baseURL, { waitUntil: "load" });
await page.waitForSelector("#mission-filters input", { timeout: 60000 });
await page.waitForTimeout(8000);

// Open every facet fold so the checkbox state is visible in each shot.
await page.evaluate(() => {
  document.querySelectorAll(".filter-stack, .filter-stack details").forEach((d) => { d.open = true; });
});
await page.waitForTimeout(500);
await page.screenshot({ path: `${outDir}/a-before-everything-selected.png` });

// Sean's flow, step 1: clear every mission type. Under healing this cascades
// to the calm all-empty state — no warning, empty globe, calm status line.
await page.locator("#mission-clear-all").click();
await page.waitForTimeout(2500);
await page.screenshot({ path: `${outDir}/b-all-empty-calm-globe.png` });

// Step 2: one click on the U.S. Navy owner. Healing selects the mission type
// Navy satellites carry and the Navy birds appear.
await page.evaluate(() => {
  document.querySelector('#owner-filters [data-owner="U.S. Navy"]')?.scrollIntoView({ block: "center" });
});
await page.locator('#owner-filters [data-owner="U.S. Navy"]').click({ force: true });
await page.waitForTimeout(3500);
await page.screenshot({ path: `${outDir}/c-us-navy-healed-result.png` });

// The state of the rail itself, close up: milsatcom ticked by healing, chips
// truthful, heal note in the status row.
const rail = page.locator(".rail-section", { has: page.locator("#mission-filters") });
await rail.screenshot({ path: `${outDir}/d-rail-after-heal-closeup.png` });

// "only" — reset, then solo Starlink from the constellation grid.
await page.locator("#filter-reset").click();
await page.waitForTimeout(2000);
await page.evaluate(() => {
  document.querySelector('#constellation-filters [data-constellation="Starlink"]')
    ?.closest("label")?.scrollIntoView({ block: "center" });
});
const starlinkRow = page.locator('#constellation-filters label', {
  has: page.locator('[data-constellation="Starlink"]'),
});
await starlinkRow.hover();
await page.waitForTimeout(300);
await rail.screenshot({ path: `${outDir}/e-only-affordance-on-hover.png` });
await starlinkRow.locator(".facet-only").click();
await page.waitForTimeout(3500);
await page.screenshot({ path: `${outDir}/f-only-starlink.png` });

// And solo U.S. Navy straight from a full catalog — one click to his goal.
await page.locator("#filter-reset").click();
await page.waitForTimeout(2000);
await page.evaluate(() => {
  document.querySelector('#owner-filters [data-owner="U.S. Navy"]')
    ?.closest("label")?.scrollIntoView({ block: "center" });
});
const navyRow = page.locator("#owner-filters label", { has: page.locator('[data-owner="U.S. Navy"]') });
await navyRow.hover();
await navyRow.locator(".facet-only").click();
await page.waitForTimeout(3500);
await page.screenshot({ path: `${outDir}/g-only-us-navy.png` });

console.log("errors:", errors.length === 0 ? "none" : errors);
await browser.close();
