// Default-camera screenshots of the X-ray layer's inbound photon beam, and of
// the contrast shot that is the point of it: photons lancing straight through
// the boundary system while the charged wind bends around it.
//
//   node tools/xray-photon-shots.mjs <outDir> <baseURL>
//
// Nothing here fakes data. Two timeline moments are chosen from the published
// GOES series (its quietest and its brightest), and the one synthetic frame is
// named as such and driven through the renderer's own setPhotonFlux, never
// through the data layer.
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";

const outDir = process.argv[2];
const baseURL = process.argv[3] ?? "http://127.0.0.1:5391/";
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
    if (el.checked !== wanted.includes(id)) { el.click(); await new Promise((r) => setTimeout(r, 150)); }
  }
}, on);

/** Move the timeline to a UTC instant by its own minutes-from-now slider. */
const setTime = async (iso) => page.evaluate((target) => {
  const slider = document.getElementById("time-slider");
  const minutes = Math.round((Date.parse(target) - Date.now()) / 60000);
  slider.value = String(Math.max(Number(slider.min), Math.min(Number(slider.max), minutes)));
  slider.dispatchEvent(new Event("input", { bubbles: true }));
  slider.dispatchEvent(new Event("change", { bubbles: true }));
}, iso);

/** What the renderer says it is drawing, read from the scene itself. */
const beamState = async () => page.evaluate(() => {
  const app = globalThis.__app;
  const globe = app.globe ?? app.view ?? null;
  const visual = globe?.xrayVisual ?? null;
  if (!visual) return { found: false };
  const range = visual.streaks.geometry.drawRange;
  return {
    found: true,
    goesClass: visual.group.userData.goesClass,
    fluxWm2: visual.group.userData.currentFluxWm2,
    dataAvailable: visual.group.userData.dataAvailable,
    inboundRayCount: visual.group.userData.inboundRayCount,
    drawnSegments: range.count,
    streakOpacity: visual.streakMaterial.uniforms.opacity.value,
    streaksVisible: visual.streaks.visible,
    photonGroupVisible: visual.group.parent?.visible ?? null,
  };
});

const readings = {};
const shot = async (name, settle = 2000) => {
  await page.waitForTimeout(settle);
  await page.screenshot({ path: `${outDir}/${name}.png` });
  readings[name] = await beamState();
};

const QUIET = "2026-08-09T01:44:00Z";  // B2.1 — the published window's minimum
const BRIGHT = "2026-08-09T16:39:00Z"; // C1.7 — the published window's maximum

// 1-2. The X-ray layer alone, default camera, at both flux moments.
await setLayers(["layer-photons"]);
await setTime(QUIET);
await shot("01-xray-alone-quiet-B2", 4000);
await setTime(BRIGHT);
await shot("02-xray-alone-bright-C17", 4000);

// 3-4. The contrast shot: X-ray + solar wind + magnetosphere boundary.
await setLayers(["layer-photons", "layer-solar-wind", "annotate-empirical-boundaries"]);
await setTime(QUIET);
await shot("03-contrast-quiet-B2", 6000);
await setTime(BRIGHT);
await shot("04-contrast-bright-C17", 5000);

// 5. Same, with the coupled MHD structures on — the full boundary system the
//    rays cross without noticing.
await setLayers(["layer-photons", "layer-solar-wind", "annotate-empirical-boundaries", "layer-geospace"]);
await shot("05-contrast-with-structures", 8000);

// 6. Environmental motion off: the beam must freeze, not disappear.
await page.evaluate(() => {
  const box = document.getElementById("display-environment-motion");
  if (box && box.checked) box.click();
});
await shot("06-motion-off-frozen", 2500);
await page.evaluate(() => {
  const box = document.getElementById("display-environment-motion");
  if (box && !box.checked) box.click();
});

// 7. SYNTHETIC PROBE, not data: the published 48 h window peaks at C1.7, so
//    there is no measured M or X moment to photograph. Force an X1 through the
//    renderer's own flux setter to judge what a flare looks like. This frame is
//    a probe of the encoding, not a picture of the sky.
await setLayers(["layer-photons", "layer-solar-wind", "annotate-empirical-boundaries"]);
// The app re-applies the timeline's flux on its own clock, so pin the setter.
await page.evaluate(() => {
  const globe = globalThis.__app.globe;
  const real = globe.setPhotonFlux.bind(globe);
  globalThis.__pin = (value) => { globe.setPhotonFlux = () => real(value); real(value); };
  globalThis.__pin(1e-4);
});
await shot("07-synthetic-X1-probe", 3000);

// 8. And the no-data contract: no flux, no beam.
await page.evaluate(() => globalThis.__pin(null));
await shot("08-no-data-no-beam", 2000);

writeFileSync(`${outDir}/readings.json`, JSON.stringify({ readings, errors }, null, 2));
console.log(JSON.stringify({ readings, errors }, null, 2));
await browser.close();
