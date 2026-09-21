// The traced field lines where they cross geostationary radius.
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";
const outDir = process.argv[2];
const baseURL = process.argv[3];
mkdirSync(outDir, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1500, height: 950 }, deviceScaleFactor: 1 });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
await page.addInitScript(() => {
  try { window.localStorage.setItem("space-explorer-hide-welcome-v1", "1"); } catch { /* ignore */ }
});
await page.route("**/src/main.ts*", async (route) => {
  const source = await fetch(route.request().url()).then((r) => r.text());
  const body = source.replace(
    "new ExplorerApp(manifest, catalog, weather, events, land);",
    "globalThis.__app = new ExplorerApp(manifest, catalog, weather, events, land);",
  );
  await route.fulfill({ body, contentType: "text/javascript" });
});
await page.goto(baseURL, { waitUntil: "load" });
await page.waitForFunction(() => Boolean(globalThis.__app), null, { timeout: 90000 });
await page.waitForTimeout(9000);
await page.locator('[data-explorer-mode="environment"]').click();
await page.waitForTimeout(3000);
const box = page.locator("#layer-geospace");
if (await box.count()) {
  if (!(await box.isChecked())) await box.click();
}
await page.waitForTimeout(9000);
for (const [name, distance] of [["wide", 1400], ["joint", 620], ["joint-closer", 380]]) {
  await page.evaluate((d) => {
    const globe = globalThis.__app.globe;
    globe.camera.position.set(0.62 * d, 0.55 * d, 0.56 * d);
    globe.controls.target.set(0, 0, 0);
    globe.controls.update();
  }, distance);
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${outDir}/field-lines-${name}.png` });
}
console.log("errors", errors.length, errors.slice(0, 5));
await browser.close();
