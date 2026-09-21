// Screenshot harness for the Space Environment Explorer UI review.
// Usage: node shoot.mjs <outDir> [baseURL]
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";

const outDir = process.argv[2];
const baseURL = process.argv[3] ?? "http://127.0.0.1:4173/";
mkdirSync(outDir, { recursive: true });

const settle = (page, ms = 2500) => page.waitForTimeout(ms);

async function dismissWelcome(page) {
  const dialog = page.locator("#welcome-dialog");
  if (await dialog.isVisible().catch(() => false)) {
    await page.locator("#welcome-dialog .primary-button").click();
    await page.waitForTimeout(400);
  }
}

async function openRail(page, phone) {
  if (!phone) return;
  const toggle = page.locator("#mobile-panel-toggle");
  if (await toggle.isVisible().catch(() => false)) {
    const open = await page.locator("#control-rail").evaluate((el) => el.classList.contains("is-open"));
    if (!open) { await toggle.click(); await page.waitForTimeout(400); }
  }
}

async function shot(page, name) {
  await page.screenshot({ path: `${outDir}/${name}.png` });
  console.log("shot", name);
}

async function run(label, viewport, phone) {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport, deviceScaleFactor: 1 });
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(String(e)));

  await page.addInitScript(() => {
    try { window.localStorage.setItem("space-explorer-hide-welcome-v1", "1"); } catch { /* ignore */ }
  });
  await page.goto(baseURL, { waitUntil: "load" });
  await dismissWelcome(page);
  await settle(page, 6000);
  await dismissWelcome(page);
  await shot(page, `${label}-01-satellites`);

  // The framing question: enabling a layer that reaches far beyond the globe
  // must pull the camera back, not slide the Earth off to one side.
  await openRail(page, phone);
  await page.locator('[data-explorer-mode="environment"]').click();
  await settle(page, 4000);
  if (phone) { await page.locator("#mobile-panel-toggle").click(); await page.waitForTimeout(600); }
  await shot(page, `${label}-10-frame-before`);
  await openRail(page, phone);
  await page.locator("label:has(> #layer-solar-wind)").click();
  await settle(page, 4000);
  if (phone) { await page.locator("#mobile-panel-toggle").click(); await page.waitForTimeout(600); }
  await shot(page, `${label}-11-frame-solar-wind`);
  await openRail(page, phone);
  await page.locator("label:has(> #layer-photons)").click();
  await settle(page, 4000);
  if (phone) { await page.locator("#mobile-panel-toggle").click(); await page.waitForTimeout(600); }
  await shot(page, `${label}-12-frame-xray`);
  await openRail(page, phone);
  await page.locator("label:has(> #layer-solar-wind)").click();
  await page.locator("label:has(> #layer-photons)").click();
  await settle(page, 4000);
  if (phone) { await page.locator("#mobile-panel-toggle").click(); await page.waitForTimeout(600); }
  await shot(page, `${label}-13-frame-restored`);
  await openRail(page, phone);

  // Space weather mode, default Simple preset (ionosphere on).
  await openRail(page, phone);
  await page.locator('[data-explorer-mode="environment"]').click();
  await settle(page, 5000);
  await shot(page, `${label}-02-weather-simple`);

  // Turn on several more layers to reproduce the crowding.
  for (const id of ["layer-tec", "layer-aurora", "annotate-empirical-boundaries", "layer-solar-wind"]) {
    await page.locator(`label:has(> #${id})`).click();
    await page.waitForTimeout(1200);
  }
  await settle(page, 5000);
  await shot(page, `${label}-03-weather-many`);
  if (phone) {
    await page.locator("#mobile-panel-toggle").click();
    await page.waitForTimeout(700);
    await shot(page, `${label}-03b-weather-many-globe`);
    await page.locator("#map-key-toggle").click();
    await page.waitForTimeout(500);
    await shot(page, `${label}-03c-weather-many-key-open`);
    await page.locator("#mobile-panel-toggle").click();
    await page.waitForTimeout(700);
  }
  await page.locator("#control-rail").evaluate((el) => { el.scrollTop = el.scrollHeight; });
  await page.waitForTimeout(600);
  await shot(page, `${label}-04-weather-many-bottom`);

  // Radiation belts + a time outside its coverage window: the no-data state.
  await page.locator("label:has(> #layer-radiation)").click();
  await settle(page, 6000);
  await page.locator("#time-slider").evaluate((el) => {
    el.value = "-2600";
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await settle(page, 8000);
  await shot(page, `${label}-05-nodata`);
  await page.locator("#control-rail").evaluate((el) => { el.scrollTop = el.scrollHeight; });
  await page.waitForTimeout(600);
  await shot(page, `${label}-06-nodata-bottom`);

  // Combined mode: filters + layers in one column.
  await page.locator("#time-now").click({ force: true }).catch(() => {});
  await page.waitForTimeout(1500);
  await page.locator('[data-explorer-mode="combined"]').click();
  await settle(page, 5000);
  await shot(page, `${label}-07-combined`);

  // A selected satellite (the left-hand card type scale).
  await page.locator("#satellite-search").fill("STARLINK-5414");
  await page.waitForTimeout(1200);
  const first = page.locator("#search-results .search-result").first();
  if (await first.isVisible().catch(() => false)) {
    await first.click();
    await settle(page, 4000);
  }
  await shot(page, `${label}-08-satellite-card`);

  console.log(label, "console errors:", errors.length, errors.slice(0, 6));
  await browser.close();
}

await run(process.env.SHOT_PREFIX ? `${process.env.SHOT_PREFIX}-desktop` : "desktop", { width: 1440, height: 900 }, false);
await run(process.env.SHOT_PREFIX ? `${process.env.SHOT_PREFIX}-phone` : "phone", { width: 390, height: 844 }, true);
