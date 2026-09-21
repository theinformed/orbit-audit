// Captures Sean's three-layer configuration across several frames, then the
// same thing edge-on, then the named cross-section regions.
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";

const outDir = process.argv[2];
const baseURL = process.argv[3] ?? "http://127.0.0.1:5199/";
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1500, height: 950 }, deviceScaleFactor: 1 });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
await page.addInitScript(() => {
  try { window.localStorage.setItem("space-explorer-hide-welcome-v1", "1"); } catch { /* ignore */ }
});
await page.route("**/src/main.ts*", async (route) => {
  // Fetched outside the browser: route.fetch() can be answered from the disk
  // cache with an empty body, which silently produces an unpatched module.
  const source = await fetch(route.request().url()).then((r) => r.text());
  const body = source.replace(
    "new ExplorerApp(manifest, catalog, weather, events, land);",
    "globalThis.__app = new ExplorerApp(manifest, catalog, weather, events, land);",
  );
  if (body === source) throw new Error("main.ts patch point not found");
  await route.fulfill({ body, contentType: "text/javascript" });
});
await page.goto(baseURL, { waitUntil: "load" });
await page.waitForFunction(() => Boolean(globalThis.__app), null, { timeout: 60000 });
await page.waitForTimeout(9000);
await page.locator('[data-explorer-mode="environment"]').click();
await page.waitForTimeout(2500);
const setLayers = async (on) => page.evaluate(async (wanted) => {
  const ids = ["layer-ionosphere", "layer-tec", "layer-drap", "layer-aurora", "layer-regions",
    "annotate-empirical-boundaries", "layer-geospace", "layer-solar-wind", "layer-photons", "layer-radiation"];
  for (const id of ids) {
    const el = document.getElementById(id);
    if (!el) continue;
    if (el.checked !== wanted.includes(id)) { el.click(); await new Promise((r) => setTimeout(r, 80)); }
  }
}, on);

await setLayers(["annotate-empirical-boundaries", "layer-solar-wind", "layer-photons"]);
await page.waitForTimeout(5000);
for (let i = 0; i < 4; i += 1) {
  await page.screenshot({ path: `${outDir}/a-three-layer-${i}.png` });
  await page.waitForTimeout(500);
}

// Same three layers, edge-on: the textbook cross-section geometry.
await page.evaluate(() => globalThis.__app.globe.focusMeridionalCrossSection());
await page.waitForTimeout(1500);
for (let i = 0; i < 4; i += 1) {
  await page.screenshot({ path: `${outDir}/b-cross-section-${i}.png` });
  await page.waitForTimeout(500);
}

// Load the published BATS-R-US structures, then show the named regions with
// the two-plane cut presentation still off.
const regionReport = await page.evaluate(async () => {
  const app = globalThis.__app;
  await app.loadGeospaceModel();
  const globe = app.globe;
  for (const region of ["bowShock", "magnetosheath", "magnetopause", "magneticField"]) {
    globe.setStructureRegion(region, true);
  }
  const runtime = globe.geospaceRuntime;
  return {
    state: runtime?.state?.status ?? "none",
    available: ["bowShock", "magnetosheath", "magnetopause", "magneticField", "flowStreamlines"]
      .map((r) => [r, globe.structureRegionAvailable(r), globe.geospaceRuntime.structureRegionGroup(r).visible]),
    solarWindMode: globe.solarWindVisual.mode,
  };
});
await page.waitForTimeout(2500);
await page.evaluate(() => globalThis.__app.globe.focusMeridionalCrossSection());
await page.waitForTimeout(1800);
const camera = await page.evaluate(() => {
  const c = globalThis.__app.globe.camera;
  return { x: c.position.x, y: c.position.y, z: c.position.z };
});
console.log("cross-section camera", camera);
for (let i = 0; i < 3; i += 1) {
  await page.screenshot({ path: `${outDir}/c-regions-${i}.png` });
  await page.waitForTimeout(500);
}
// The same structures without the empirical boundary shell over the top.
await page.evaluate(async () => {
  const el = document.getElementById("annotate-empirical-boundaries");
  if (el && el.checked) el.click();
});
await page.waitForTimeout(800);
await page.evaluate(() => globalThis.__app.globe.focusMeridionalCrossSection());
await page.waitForTimeout(1500);
for (let i = 0; i < 3; i += 1) {
  await page.screenshot({ path: `${outDir}/e-regions-alone-${i}.png` });
  await page.waitForTimeout(500);
}

// Field lines alone, which is the "Earth's magnetic field" curve set.
await page.evaluate(() => {
  const globe = globalThis.__app.globe;
  globe.setStructureRegion("bowShock", false);
  globe.setStructureRegion("magnetosheath", false);
  globe.setStructureRegion("magnetopause", false);
});
await page.waitForTimeout(1500);
await page.screenshot({ path: `${outDir}/d-field-lines.png` });

writeFileSync(`${outDir}/regions.json`, JSON.stringify({ regionReport, errors }, null, 2));
console.log(JSON.stringify(regionReport, null, 1));
console.log("errors", errors.slice(0, 8));
await browser.close();
