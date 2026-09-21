import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";

/**
 * Screenshots of the ring-current layer: one full page, one close detail, and
 * a one-per-second sequence long enough to cover a whole formation loop.
 *
 * Usage: node tools/ring-current-shots.mjs <outDir> <baseURL> [tag] [frames]
 */
const outDir = process.argv[2];
const baseURL = process.argv[3];
const tag = process.argv[4] ?? "shot";
const frames = Number(process.argv[5] ?? 20);
mkdirSync(outDir, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1500, height: 950 } });
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + String(e)));
page.on("console", (m) => {
  const text = m.text();
  if (m.type() === "error" || /shader|GLSL|THREE\./i.test(text)) errors.push(m.type() + ": " + text.slice(0, 400));
});
await page.addInitScript(() => { try { window.localStorage.setItem("space-explorer-hide-welcome-v1", "1"); } catch {} });
await page.goto(baseURL, { waitUntil: "load" });
await page.waitForTimeout(14000);
await page.evaluate(() => { document.querySelector('[data-explorer-mode="environment"]')?.click(); });
await page.waitForTimeout(3000);
await page.evaluate(() => {
  for (const id of ["layer-plasmasphere", "layer-radiation", "layer-magnetosphere", "layer-aurora", "layer-thermosphere", "layer-ionosphere", "layer-tec", "layer-solar-wind", "layer-geospace"]) {
    const box = document.getElementById(id);
    if (box && box.checked) box.click();
  }
  const rc = document.getElementById("layer-ring-current");
  if (rc && !rc.checked) rc.click();
});
await page.waitForTimeout(20000);
console.log("ring current on:", await page.evaluate(() => Boolean(document.getElementById("layer-ring-current")?.checked)));
const clip = { x: 320, y: 240, width: 480, height: 460 };
for (let index = 0; index < frames; index += 1) {
  // Re-asserted every frame: this page has other layers, a clock and a rail
  // that can all take the camera somewhere else mid-sequence.
  await page.evaluate(() => {
    const rc = document.getElementById("layer-ring-current");
    if (rc && !rc.checked) rc.click();
  }).catch(() => {});
  await page.screenshot({ path: outDir + "/" + tag + "-seq-" + String(index).padStart(2, "0") + ".png", timeout: 180000, clip });
  await page.waitForTimeout(1000);
}
await page.screenshot({ path: outDir + "/" + tag + "-full.png", timeout: 180000 });
await page.screenshot({ path: outDir + "/" + tag + "-close.png", timeout: 180000, clip: { x: 300, y: 210, width: 580, height: 560 } });
// The card itself, which is where the layer says what it is.
await page.locator("#data-viewer-head").click({ timeout: 5000 }).catch(() => {});
await page.waitForTimeout(1500);
await page.screenshot({ path: outDir + "/" + tag + "-card.png", timeout: 180000, fullPage: false });
console.log("errors", errors.length, errors.slice(0, 12));
await browser.close();
