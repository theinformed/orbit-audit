// Banding check. Reads pixel luminance along a radial line at full pixel
// resolution, fits a smooth local trend, and reports the residual -- concentric
// slab banding shows up as a periodic residual, so this either finds it or
// rules it out. Also captures a large clean limb view to look at.
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";

const outDir = process.argv[2];
const baseURL = process.argv[3] ?? "http://127.0.0.1:5401/";
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const page = await browser.newPage({ viewport: { width: 1400, height: 950 }, deviceScaleFactor: 1 });
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
await page.evaluate(async () => {
  const ids = ["layer-ionosphere", "layer-tec", "layer-drap", "layer-aurora",
    "layer-thermosphere", "layer-geospace", "layer-solar-wind", "layer-photons", "layer-radiation"];
  for (const id of ids) {
    const el = document.getElementById(id);
    if (!el) continue;
    if (el.checked !== (id === "layer-ionosphere")) { el.click(); await new Promise((r) => setTimeout(r, 160)); }
  }
});
await page.waitForTimeout(20000);

const result = await page.evaluate(() => {
  const globe = globalThis.__app.globe;
  const cam = globe.camera;
  const renderer = globe.renderer;
  // Hide the Earth's own glow shells so the measurement is this layer alone.
  globe.scene.traverse((n) => {
    const r = n.geometry && n.geometry.parameters && n.geometry.parameters.radius;
    if (r && r > 100.4 && r < 115 && n !== globe.ionosphereDensityVolume.mesh) n.visible = false;
  });
  cam.position.set(0, 0, 700);
  globe.controls.target.set(0, 0, 0);
  cam.updateProjectionMatrix();
  globe.controls.update();
  cam.updateMatrixWorld();
  renderer.render(globe.scene, cam);

  const gl = renderer.getContext();
  const w = gl.drawingBufferWidth, h = gl.drawingBufferHeight;
  const canvas = renderer.domElement;
  const project = (radius) => {
    const p = new cam.position.constructor(radius, 0, 0);
    p.project(cam);
    return (p.x * 0.5 + 0.5) * w;
  };
  const p0 = project(0), p1 = project(100);
  const drawnFromPx = (px) => ((px - p0) / (p1 - p0)) * 100;
  const altitudeFromDrawn = (d) => 350 * (Math.exp((d / 100 - 1) / 0.28) - 1);

  const row = Math.round(h / 2);
  const pixels = new Uint8Array(w * 4);
  gl.readPixels(0, h - 1 - row, w, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixels);

  const samples = [];
  for (let px = Math.ceil(project(100.05)); px <= Math.floor(project(160)); px += 1) {
    const drawn = drawnFromPx(px);
    if (drawn < 100.05 || drawn > 160) continue;
    const i = px * 4;
    samples.push({
      px, drawn,
      altitudeKm: altitudeFromDrawn(drawn),
      lum: 0.2126 * pixels[i] + 0.7152 * pixels[i + 1] + 0.0722 * pixels[i + 2],
    });
  }
  return { samples, pxPerDrawnUnit: (p1 - p0) / 100, w, h, canvasW: canvas.width };
});

const { samples } = result;
// Local trend by a wide moving average; residual is what banding would live in.
const WINDOW = 15;
let maxResidual = 0, signChanges = 0, previousSign = 0, band = [];
for (let i = WINDOW; i < samples.length - WINDOW; i += 1) {
  let sum = 0;
  for (let k = i - WINDOW; k <= i + WINDOW; k += 1) sum += samples[k].lum;
  const trend = sum / (2 * WINDOW + 1);
  const residual = samples[i].lum - trend;
  band.push({ altitudeKm: Math.round(samples[i].altitudeKm), residual: Math.round(residual * 100) / 100, lum: Math.round(samples[i].lum * 10) / 10 });
  if (Math.abs(residual) > maxResidual) maxResidual = Math.abs(residual);
  const sign = Math.sign(residual);
  if (sign !== 0 && previousSign !== 0 && sign !== previousSign) signChanges += 1;
  if (sign !== 0) previousSign = sign;
}
const peakLum = Math.max(...samples.map((s) => s.lum));
console.log("pixels sampled:", samples.length, " px per drawn unit:", result.pxPerDrawnUnit.toFixed(2));
console.log("peak luminance:", peakLum.toFixed(1));
console.log("max residual from local trend:", maxResidual.toFixed(2),
  `(${(100 * maxResidual / Math.max(1, peakLum)).toFixed(2)}% of peak)`);
console.log("residual sign changes:", signChanges, "over", band.length, "samples");
console.log("residual profile (every 6th):");
console.log(band.filter((_b, i) => i % 6 === 0).map((b) => `${b.altitudeKm}km:${b.residual}`).join("  "));
writeFileSync(`${outDir}/banding.json`, JSON.stringify({ band, maxResidual, signChanges, peakLum, errors }, null, 1));

// A large, clean limb picture to judge by eye as well.
await page.evaluate(() => {
  const globe = globalThis.__app.globe;
  const cam = globe.camera;
  cam.updateMatrixWorld();
  const e = cam.matrixWorld.elements;
  const limb = { x: -e[0] * 126, y: -e[1] * 126, z: -e[2] * 126 };
  globe.controls.target.set(limb.x, limb.y, limb.z);
  cam.position.set(limb.x, limb.y, limb.z + 150);
  cam.updateProjectionMatrix();
  globe.controls.update();
});
await page.waitForTimeout(2500);
await page.screenshot({ path: `${outDir}/limb-large.png`, clip: { x: 0, y: 60, width: 980, height: 860 } });
console.log("ERRORS", errors.length, errors.slice(0, 5));
await browser.close();
