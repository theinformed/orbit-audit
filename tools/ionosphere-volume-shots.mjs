// The finished layer, photographed the way a reader meets it.
// node tools/ionosphere-volume-shots.mjs <outDir> <baseURL>
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";

const outDir = process.argv[2];
const baseURL = process.argv[3] ?? "http://127.0.0.1:5401/";
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const page = await browser.newPage({ viewport: { width: 1280, height: 880 }, deviceScaleFactor: 1 });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
await page.addInitScript(() => {
  try { window.localStorage.setItem("space-explorer-hide-welcome-v1", "1"); } catch { /* ignore */ }
});
await page.route("**/assets/index-*.js", async (route) => {
  const source = await fetch(route.request().url()).then((r) => r.text());
  const body = source.replace(
    "new ExplorerApp(manifest, catalog, weather, events, land);",
    "globalThis.__app = new ExplorerApp(manifest, catalog, weather, events, land);",
  );
  if (body === source) throw new Error("patch point not found");
  await route.fulfill({ body, contentType: "text/javascript" });
});
page.setDefaultTimeout(240000);
await page.goto(baseURL, { waitUntil: "domcontentloaded", timeout: 240000 });
await page.waitForFunction(() => Boolean(globalThis.__app), null, { timeout: 150000 });
await page.waitForTimeout(9000);
await page.locator('[data-explorer-mode="environment"]').click();
await page.waitForTimeout(2500);

const setLayers = async (on) => page.evaluate(async (wanted) => {
  const ids = ["layer-ionosphere", "layer-tec", "layer-drap", "layer-aurora",
    "layer-thermosphere", "layer-geospace", "layer-solar-wind", "layer-photons", "layer-radiation"];
  for (const id of ids) {
    const el = document.getElementById(id);
    if (!el) continue;
    if (el.checked !== wanted.includes(id)) { el.click(); await new Promise((r) => setTimeout(r, 160)); }
  }
}, on);

const setBand = async (value) => page.evaluate((value) => {
  const el = document.getElementById("ionosphere-altitude-range");
  el.value = value;
  el.dispatchEvent(new Event("change", { bubbles: true }));
}, value);

const place = async (distance, elevationDeg, azimuthDeg, limbRadius) => page.evaluate(({ distance, elevationDeg, azimuthDeg, limbRadius }) => {
  const globe = globalThis.__app.globe;
  const cam = globe.camera;
  const el = elevationDeg * Math.PI / 180;
  const az = azimuthDeg * Math.PI / 180;
  const view = { x: Math.cos(el) * Math.sin(az), y: Math.sin(el), z: Math.cos(el) * Math.cos(az) };
  cam.position.set(view.x * 400, view.y * 400, view.z * 400);
  globe.controls.target.set(0, 0, 0);
  cam.updateMatrixWorld();
  if (limbRadius) {
    const e = cam.matrixWorld.elements;
    const limb = { x: -e[0] * limbRadius, y: -e[1] * limbRadius, z: -e[2] * limbRadius };
    globe.controls.target.set(limb.x, limb.y, limb.z);
    cam.position.set(limb.x + view.x * distance, limb.y + view.y * distance, limb.z + view.z * distance);
  } else {
    cam.position.set(view.x * distance, view.y * distance, view.z * distance);
  }
  cam.updateProjectionMatrix();
  globe.controls.update();
}, { distance, elevationDeg, azimuthDeg, limbRadius });

const CANVAS = { x: 0, y: 62, width: 880, height: 790 };
const shot = async (name, settle = 2200) => {
  await page.waitForTimeout(settle);
  await page.screenshot({ path: `${outDir}/${name}.png`, clip: CANVAS });
  console.log("shot", name);
};

await setLayers(["layer-ionosphere"]);
await page.waitForTimeout(18000);

// 1-2. The whole column: globe view, then the limb where height reads.
await setBand("60:2655");
await place(430, 10, 35);
await shot("01-whole-column-globe");
await place(165, 6, 35, 126);
await shot("02-whole-column-limb");

// 3-5. One band at a time, each at its real height on the same ruler.
await setBand("60:90");
await shot("03-d-region-alone");
await setBand("90:175");
await shot("04-e-region-alone");
await setBand("200:800");
await shot("05-f2-and-topside");

// 6. Back to the whole column, with the TEC surface: the pairing Sean asked
//    about. TEC is the vertical integral of exactly this field.
await setBand("60:2655");
await setLayers(["layer-ionosphere", "layer-tec"]);
await place(430, 10, 35);
await shot("06-with-tec-globe");
await place(165, 6, 35, 126);
await shot("07-with-tec-limb");

// 7. TEC alone, for the comparison.
await setLayers(["layer-tec"]);
await place(430, 10, 35);
await shot("08-tec-alone");

// 8. Satellites inside the field.
await setLayers(["layer-ionosphere"]);
await page.locator('[data-explorer-mode="combined"]').click();
await page.waitForTimeout(4000);
await place(430, 10, 35);
await shot("09-with-satellites");

const state = await page.evaluate(() => {
  const b = globalThis.__app.globe.getIonosphereVolumeBake?.();
  const s = globalThis.__app.globe.getIonosphereSurfaceState?.();
  return {
    bake: b && {
      measured: b.measured, logFloor: b.logFloor, logCeiling: b.logCeiling,
      empiricalLogFloor: b.empiricalLogFloor, empiricalLogCeiling: b.empiricalLogCeiling,
      dims: [b.longitudeCount, b.latitudeCount, b.altitudeCount], frames: b.frames,
    },
    surfaces: s && {
      e: s.regions.e.supportedColumnPercent, f1: s.regions.f1.supportedColumnPercent,
      f2: s.regions.f2.meanAltitudeKm, dRegion: s.dRegion,
    },
  };
});
writeFileSync(`${outDir}/state.json`, JSON.stringify({ state, errors }, null, 2));
console.log("STATE", JSON.stringify(state, null, 1));
console.log("ERRORS", errors.length, errors.slice(0, 6));
await browser.close();
