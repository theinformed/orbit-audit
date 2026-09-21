/*
 * Screenshot a Learn > Layers page at a given viewport, and report whether
 * #content-view overflows horizontally — which is what tests/browser.spec.ts
 * also asserts and what an unsized <video> would break.
 *
 *   node tools/_layer-shots.mjs <outDir> [baseURL] [layerId|-] [w] [h] [scrollTop]
 *
 * With no layer id it shoots the index. Run it from the repository root so
 * @playwright/test resolves.
 */
import { chromium } from "@playwright/test";

const [outDir, base = "http://127.0.0.1:5401/", layer = "-", w = "1440", h = "900", scroll = "0"] =
  process.argv.slice(2);
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: +w, height: +h }, deviceScaleFactor: 1 });
await page.addInitScript(() => { try { localStorage.setItem("space-explorer-hide-welcome-v1", "1"); } catch {} });
const errors = [];
page.on("pageerror", (error) => errors.push(String(error.message)));
await page.goto(base, { waitUntil: "load" });
await page.waitForTimeout(2200);
const dismiss = page.locator("#welcome-dialog .primary-button");
if (await dismiss.isVisible().catch(() => false)) { await dismiss.click(); await page.waitForTimeout(400); }
await page.evaluate(() => document.querySelector('[data-view="learn-layers"]').click());
await page.waitForTimeout(900);
if (layer !== "-") {
  await page.evaluate((id) => document.querySelector(`[data-layer-page="${id}"]`).click(), layer);
  await page.waitForTimeout(900);
}
if (+scroll) {
  await page.evaluate((y) => { document.getElementById("content-view").scrollTop = y; }, +scroll);
  await page.waitForTimeout(500);
}
const overflow = await page.locator("#content-view").evaluate((el) => el.scrollWidth > el.clientWidth + 1);
const name = `${layer === "-" ? "index" : layer}-${w}`;
await page.screenshot({ path: `${outDir}/${name}.png` });
console.log(`${name}\t${w}x${h}\thoverflow=${overflow}\terrors=${errors.length}`);
await browser.close();
process.exit(overflow || errors.length ? 1 : 0);
