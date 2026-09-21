// Limb-focused sweep. The vertical structure of the ionosphere lives in a
// narrow annulus just outside the globe silhouette -- on the teaching ruler
// 60 km draws at 104.4 and the F2 peak near 119, against a globe of 100 -- so
// the camera goes close and the crop is measured, not guessed.
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";

const outDir = process.argv[2];
const baseURL = process.argv[3] ?? "http://127.0.0.1:5401/";
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const page = await browser.newPage({ viewport: { width: 1200, height: 900 }, deviceScaleFactor: 1 });
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
await page.waitForTimeout(2000);

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

// Put the camera close, over the dayside, and hide the overlay chrome so the
// globe owns the frame.
await page.evaluate(() => {
  for (const sel of ["#data-explorer-panel", ".legend-panel", "#legend", ".timeline",
    ".app-header", ".explorer-rail", "aside", ".globe-controls", "#probe-panel"]) {
    document.querySelectorAll(sel).forEach((n) => { n.style.display = "none"; });
  }
});

// Look AT the limb, not at the globe centre. On the teaching ruler the whole
// field is an annulus from drawn radius 104.4 to 160.2 around a globe of 100,
// so a frame that contains the whole planet leaves the layers a few pixels
// thick. Centring on the limb is the only way to see them separated.
const place = async (distance, elevationDeg, azimuthDeg, limbRadius = 128) => page.evaluate(({ distance, elevationDeg, azimuthDeg, limbRadius }) => {
  const globe = globalThis.__app.globe;
  const cam = globe.camera;
  const el = elevationDeg * Math.PI / 180;
  const az = azimuthDeg * Math.PI / 180;
  const view = { x: Math.cos(el) * Math.sin(az), y: Math.sin(el), z: Math.cos(el) * Math.cos(az) };
  // Provisional placement so the camera has a right axis to read.
  cam.position.set(view.x * 400, view.y * 400, view.z * 400);
  globe.controls.target.set(0, 0, 0);
  cam.updateMatrixWorld();
  const e = cam.matrixWorld.elements;
  const limb = { x: -e[0] * limbRadius, y: -e[1] * limbRadius, z: -e[2] * limbRadius };
  globe.controls.target.set(limb.x, limb.y, limb.z);
  cam.position.set(limb.x + view.x * distance, limb.y + view.y * distance, limb.z + view.z * distance);
  cam.updateProjectionMatrix();
  globe.controls.update();
  globe.renderer.render(globe.scene, globe.camera);
}, { distance, elevationDeg, azimuthDeg, limbRadius });

// Measure, rather than assume, where a given drawn radius lands in pixels.
const measure = async () => page.evaluate(() => {
  const globe = globalThis.__app.globe;
  const cam = globe.camera;
  cam.updateMatrixWorld();
  const e = cam.matrixWorld.elements;
  const rect = globe.renderer.domElement.getBoundingClientRect();
  const project = (radius) => {
    const p = new cam.position.constructor(-e[0] * radius, -e[1] * radius, -e[2] * radius);
    p.project(cam);
    return { x: rect.left + (p.x * 0.5 + 0.5) * rect.width, y: rect.top + (-p.y * 0.5 + 0.5) * rect.height };
  };
  const centre = new cam.position.constructor(0, 0, 0);
  centre.project(cam);
  return {
    centre: { x: rect.left + (centre.x * 0.5 + 0.5) * rect.width, y: rect.top + (-centre.y * 0.5 + 0.5) * rect.height },
    globe: project(100), f2: project(119.3), top: project(160.2), base: project(104.4),
    rect: { w: rect.width, h: rect.height },
  };
});

const setTransfer = async (t) => page.evaluate((t) => {
  const u = globalThis.__app.globe.ionosphereDensityVolume.mesh.material.uniforms;
  if (t.extinction !== undefined) u.extinction.value = t.extinction;
  if (t.exponent !== undefined) u.opacityCurveExponent.value = t.exponent;
  if (t.empirical !== undefined) u.empiricalOpacityScale.value = t.empirical;
  if (t.maxAlpha !== undefined) u.minimumTransmittance.value = 1 - t.maxAlpha;
}, t);

await place(150, 6, 40);
const m = await measure();
console.log("PROJECTION", JSON.stringify(m));
// Crop a box that spans the globe edge outward past the top of the field.
const box = { x: Math.round(m.rect.w * 0.02), y: Math.round(m.rect.h * 0.04), width: Math.round(m.rect.w * 0.8), height: Math.round(m.rect.h * 0.85) };
console.log("CROP", JSON.stringify(box));

const candidates = [
  { name: "p1-ext70-exp34", extinction: 0.70, exponent: 3.4, empirical: 3.0, maxAlpha: 0.72 },
  { name: "p2-ext70-exp6", extinction: 0.70, exponent: 6.0, empirical: 4.0, maxAlpha: 0.85 },
  { name: "p3-ext150-exp6", extinction: 1.50, exponent: 6.0, empirical: 4.0, maxAlpha: 0.85 },
  { name: "p4-ext150-exp9", extinction: 1.50, exponent: 9.0, empirical: 6.0, maxAlpha: 0.90 },
  { name: "p5-ext400-exp9", extinction: 4.00, exponent: 9.0, empirical: 6.0, maxAlpha: 0.92 },
  { name: "p6-ext400-exp13", extinction: 4.00, exponent: 13.0, empirical: 9.0, maxAlpha: 0.94 },
];
for (const c of candidates) {
  await setTransfer(c);
  await page.waitForTimeout(900);
  await page.screenshot({ path: `${outDir}/${c.name}-limb.png`, clip: box });
  await page.screenshot({ path: `${outDir}/${c.name}-full.png` });
  console.log("captured", c.name);
}
writeFileSync(`${outDir}/meta.json`, JSON.stringify({ m, box, errors }, null, 2));
console.log("ERRORS", errors.length, errors.slice(0, 5));
await browser.close();
