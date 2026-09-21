// Sweeps the ionosphere volume's transfer function inside ONE browser
// session by poking the shader uniforms, so tuning does not cost a reload
// per candidate. node tools/ionosphere-volume-tune.mjs <outDir> <baseURL>
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";

const outDir = process.argv[2];
const baseURL = process.argv[3] ?? "http://127.0.0.1:5401/";
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const page = await browser.newPage({ viewport: { width: 1000, height: 700 }, deviceScaleFactor: 1 });
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
  if (body === source) throw new Error("main.ts patch point not found");
  await route.fulfill({ body, contentType: "text/javascript" });
});
page.setDefaultTimeout(180000);
await page.goto(baseURL, { waitUntil: "domcontentloaded", timeout: 180000 });
await page.waitForFunction(() => Boolean(globalThis.__app), null, { timeout: 120000 });
await page.waitForTimeout(10000);
await page.locator('[data-explorer-mode="environment"]').click();
await page.waitForTimeout(2500);

const setLayers = async (on) => page.evaluate(async (wanted) => {
  const ids = ["layer-ionosphere", "layer-tec", "layer-drap", "layer-aurora",
    "layer-thermosphere", "layer-geospace", "layer-solar-wind", "layer-photons", "layer-radiation"];
  for (const id of ids) {
    const el = document.getElementById(id);
    if (!el) continue;
    if (el.checked !== wanted.includes(id)) { el.click(); await new Promise((r) => setTimeout(r, 150)); }
  }
}, on);

await setLayers(["layer-ionosphere"]);
await page.waitForTimeout(18000);

const camera = async (distance, elevationDeg = 12, azimuthDeg = 30) => page.evaluate(({ distance, elevationDeg, azimuthDeg }) => {
  const globe = globalThis.__app.globe;
  const el = elevationDeg * Math.PI / 180;
  const az = azimuthDeg * Math.PI / 180;
  globe.controls.target.set(0, 0, 0);
  globe.camera.position.set(
    distance * Math.cos(el) * Math.sin(az),
    distance * Math.sin(el),
    distance * Math.cos(el) * Math.cos(az),
  );
  globe.camera.updateProjectionMatrix();
  globe.controls.update();
}, { distance, elevationDeg, azimuthDeg });

await camera(400);
await page.waitForTimeout(2000);

// Where is the limb on screen? Project a scene point at the volume's outer
// radius, in the plane perpendicular to the view, and read back pixels.
const limbPixel = await page.evaluate(() => {
  const globe = globalThis.__app.globe;
  const cam = globe.camera;
  cam.updateMatrixWorld();
  const e = cam.matrixWorld.elements;
  // Column 0 of the camera's world matrix is its own right axis.
  // NEGATED: the right rail overlays the right of the canvas, so the limb we
  // crop is the LEFT one, where nothing is drawn over the globe.
  const right = { x: -e[0], y: -e[1], z: -e[2] };
  const p = new cam.position.constructor(right.x * 130, right.y * 130, right.z * 130);
  p.project(cam);
  const canvas = globe.renderer.domElement;
  const rect = canvas.getBoundingClientRect();
  return {
    x: rect.left + (p.x * 0.5 + 0.5) * rect.width,
    y: rect.top + (-p.y * 0.5 + 0.5) * rect.height,
    rect: { left: rect.left, top: rect.top, width: rect.width, height: rect.height },
  };
});
console.log("limb pixel", JSON.stringify(limbPixel));

const setTransfer = async (t) => page.evaluate((t) => {
  const layer = globalThis.__app.globe.ionosphereDensityVolume;
  const u = layer.mesh.material.uniforms;
  if (t.extinction !== undefined) u.extinction.value = t.extinction;
  if (t.exponent !== undefined) u.opacityCurveExponent.value = t.exponent;
  if (t.empirical !== undefined) u.empiricalOpacityScale.value = t.empirical;
  if (t.maxAlpha !== undefined) u.minimumTransmittance.value = 1 - t.maxAlpha;
}, t);

const GLOBE = { x: 0, y: 60, width: 740, height: 640 };
const capture = async (name) => {
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${outDir}/${name}-wide.png`, clip: GLOBE });
  const cx = Math.max(160, Math.min(740 - 160, limbPixel.x));
  const cy = Math.max(160, Math.min(700 - 160, limbPixel.y));
  await page.screenshot({ path: `${outDir}/${name}-limb.png`, clip: { x: cx - 150, y: cy - 150, width: 300, height: 300 } });
  console.log("captured", name);
};

const candidates = [
  { name: "a-ext15", extinction: 0.15, exponent: 3.4, empirical: 3.0, maxAlpha: 0.72 },
  { name: "b-ext35", extinction: 0.35, exponent: 3.4, empirical: 3.0, maxAlpha: 0.72 },
  { name: "c-ext70", extinction: 0.70, exponent: 3.4, empirical: 3.0, maxAlpha: 0.72 },
  { name: "d-ext140", extinction: 1.40, exponent: 3.4, empirical: 3.0, maxAlpha: 0.80 },
  { name: "e-ext70-exp5", extinction: 0.70, exponent: 5.0, empirical: 4.0, maxAlpha: 0.80 },
  { name: "f-ext140-exp5", extinction: 1.40, exponent: 5.0, empirical: 4.0, maxAlpha: 0.85 },
  { name: "g-ext300-exp6", extinction: 3.00, exponent: 6.0, empirical: 5.0, maxAlpha: 0.88 },
];
for (const c of candidates) {
  await setTransfer(c);
  await capture(c.name);
}

writeFileSync(`${outDir}/errors.json`, JSON.stringify(errors, null, 2));
console.log("ERRORS", errors.length, errors.slice(0, 6));
await browser.close();
