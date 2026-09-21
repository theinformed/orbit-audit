/*
 * Screenshot chapter 07 of the Satellite fundamentals track (inferring
 * manoeuvres) at a given viewport, one PNG per figure plus a full-page shot,
 * and report whether #content-view overflows horizontally.
 *
 *   node tools/_inference-shots.mjs <outDir> [baseURL] [w] [h]
 *
 * Run from the repository root so @playwright/test resolves.
 */
import { chromium } from "@playwright/test";

const [outDir, base = "http://127.0.0.1:4173/", w = "1440", h = "900"] = process.argv.slice(2);
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: +w, height: +h }, deviceScaleFactor: 1 });
await page.addInitScript(() => { try { localStorage.setItem("space-explorer-hide-welcome-v1", "1"); } catch {} });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e.message)));
await page.goto(`${base}#/learn-orbits/inference`, { waitUntil: "load" });
await page.waitForTimeout(2500);
const dismiss = page.locator("#welcome-dialog .primary-button");
if (await dismiss.isVisible().catch(() => false)) { await dismiss.click(); await page.waitForTimeout(400); }
await page.waitForTimeout(600);

const title = await page.locator("#content-view h1").first().innerText().catch(() => "?");
const figures = page.locator("#content-view figure");
const count = await figures.count();
for (let i = 0; i < count; i += 1) {
  await figures.nth(i).scrollIntoViewIfNeeded();
  await page.waitForTimeout(250);
  await figures.nth(i).screenshot({ path: `${outDir}/fig${i + 1}-${w}.png` });
}
await page.locator("#content-view").screenshot({ path: `${outDir}/page-${w}.png`, scale: "css" }).catch(async () => {
  await page.screenshot({ path: `${outDir}/page-${w}.png`, fullPage: true });
});
const overflow = await page.locator("#content-view").evaluate((el) => el.scrollWidth > el.clientWidth + 1);
console.log(`title=${JSON.stringify(title)}\tfigures=${count}\t${w}x${h}\thoverflow=${overflow}\terrors=${errors.length}`);
if (errors.length) console.log(errors.join("\n"));
await browser.close();
process.exit(overflow || errors.length ? 1 : 0);
