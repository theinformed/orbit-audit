// Drives the new magnetosphere picture end to end and captures what a reader
// would actually see: the cut-open boundary with cusp funnels and entry cue,
// the coupled structures layer, the plasmasphere density field, and the
// polar view. Run against a dev server: node tools/magnetosphere-picture-shots.mjs <outDir> <baseURL>
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";

const outDir = process.argv[2];
const baseURL = process.argv[3] ?? "http://127.0.0.1:5217/";
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
    "annotate-empirical-boundaries", "layer-plasmasphere",
    "layer-geospace", "layer-solar-wind", "layer-photons", "layer-radiation"];
  for (const id of ids) {
    const el = document.getElementById(id);
    if (!el) continue;
    if (el.checked !== wanted.includes(id)) { el.click(); await new Promise((r) => setTimeout(r, 120)); }
  }
}, on);

const shot = async (name, settle = 1200) => {
  await page.waitForTimeout(settle);
  await page.screenshot({ path: `${outDir}/${name}.png` });
};

// 1. Magnetopause layer alone, closed-shell mode (the before, for contrast).
await setLayers(["annotate-empirical-boundaries"]);
await shot("01-magnetopause-shell", 3500);

// 2. Cut it open. The toggle also moves the camera to the meridional cut.
await page.locator("#magnetopause-cut").click();
await shot("02-magnetopause-cut", 2500);

// 3. Polar view of the same: the two funnels and the entry cue from above.
await page.locator("#polar-view").click();
await shot("03-magnetopause-cut-polar", 2000);

// 4. Sean's three layers plus the cut: solar wind deflecting around a cut
//    boundary whose funnels are visible, X-rays straight through.
await setLayers(["annotate-empirical-boundaries", "layer-solar-wind", "layer-photons"]);
await page.locator("#cross-section-view").click();
await shot("04-three-layers-cut", 3500);

// 5. Add the coupled structures: bow shock, sheath, field lines around it.
await setLayers(["annotate-empirical-boundaries", "layer-solar-wind", "layer-photons", "layer-geospace"]);
await shot("05-full-picture-cross-section", 6000);
await shot("05b-full-picture-cross-section", 800);

// 6. Plasmasphere + radiation belts: the inner magnetosphere.
await setLayers(["layer-plasmasphere", "layer-radiation"]);
await page.locator("#cross-section-view").click();
await shot("06-inner-magnetosphere", 5000);

// 7. Everything at once, edge-on: the textbook figure, live.
await setLayers(["annotate-empirical-boundaries", "layer-plasmasphere",
  "layer-solar-wind", "layer-geospace", "layer-radiation"]);
await page.locator("#cross-section-view").click();
await shot("07-everything-cross-section", 5000);

// 8. The same, polar.
await page.locator("#polar-view").click();
await shot("08-everything-polar", 2000);

// 9. The plasmasphere density field alone: the inner magnetosphere,
//    cut open, without the belt volume over it.
await setLayers(["layer-plasmasphere"]);
await page.locator("#cross-section-view").click();
await shot("09-plasmasphere-cut", 2500);
await page.locator("#polar-view").click();
await shot("10-plasmasphere-polar", 1500);

// 10. The walkthrough's obstacle, cusp and store steps as a reader meets them.
await setLayers([]);
await page.locator("#energy-chain-open").click();
await page.waitForTimeout(4000);
const goToStep = async (n) => {
  await page.locator(`.chain-walk__chip >> nth=${n}`).click();
  await page.waitForTimeout(4500);
};
await goToStep(1);
await shot("11-walkthrough-obstacle", 4000);
await goToStep(2);
await shot("12-walkthrough-cusp", 2500);
await goToStep(3);
await shot("13-walkthrough-store", 2500);
await page.locator(".chain-walk__close").click();
await page.waitForTimeout(800);

// Data checks: what the app believes it drew.
const report = await page.evaluate(() => {
  const app = globalThis.__app;
  const globe = app.globe;
  return {
    magnetopauseDisplay: globe.magnetopauseDisplay,
    magnetopauseLegend: globe.getMagnetopauseLegend().map((e) => e.id),
    cuspedAttribute: document.getElementById("annotate-empirical-boundaries").getAttribute("data-magnetopause-surface"),
    plasmasphere: globe.getPlasmasphereField()?.plasmapause ?? null,
    structureRegions: ["bowShock", "magnetosheath", "magnetopause", "magneticField"]
      .map((r) => [r, globe.structureRegionEnabled(r), globe.structureRegionAvailable(r)]),
  };
});
writeFileSync(`${outDir}/report.json`, JSON.stringify({ report, errors }, null, 2));
console.log(JSON.stringify(report, null, 1));
console.log("errors", errors.slice(0, 8));
await browser.close();
