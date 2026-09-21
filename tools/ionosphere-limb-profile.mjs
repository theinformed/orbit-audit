// Measures the rendered layer instead of squinting at it: reads canvas pixels
// along a radial line out from the globe's limb, converts each pixel back to a
// physical altitude through the shared ruler, and reports brightness against
// altitude. That is the only honest way to answer "do the E and F layers
// separate visually".
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
await page.evaluate(async () => {
  const ids = ["layer-ionosphere", "layer-tec", "layer-drap", "layer-aurora",
    "layer-thermosphere", "layer-geospace", "layer-solar-wind", "layer-photons", "layer-radiation"];
  for (const id of ids) {
    const el = document.getElementById(id);
    if (!el) continue;
    if (el.checked !== (id === "layer-ionosphere")) { el.click(); await new Promise((r) => setTimeout(r, 150)); }
  }
});
await page.waitForTimeout(18000);

const probe = await page.evaluate(async ({ candidates }) => {
  const globe = globalThis.__app.globe;
  const cam = globe.camera;
  const renderer = globe.renderer;
  const canvas = renderer.domElement;
  const uniforms = globe.ionosphereDensityVolume.mesh.material.uniforms;

  // Hide the Earth's own additive glow shell. It sits at drawn radius 107,
  // which this ruler maps to about 99 km -- squarely in the E region -- so
  // left on it both contaminates the measurement and masquerades as an E
  // layer in the picture.
  const hidden = [];
  globe.scene.traverse((node) => {
    const radius = node.geometry && node.geometry.parameters && node.geometry.parameters.radius;
    if (!radius || node === globe.ionosphereDensityVolume.mesh) return;
    if (radius > 100.4 && radius < 115 && node.visible) { node.visible = false; hidden.push(node.name || radius); }
  });
  globalThis.__hidden = hidden;

  // Frame the whole field with the globe centred, looking down the equator so
  // the sampled line is a clean radial cut through the limb.
  const distance = 900;
  globe.controls.target.set(0, 0, 0);
  cam.position.set(0, 0, distance);
  cam.updateProjectionMatrix();
  globe.controls.update();
  cam.updateMatrixWorld();

  // Map drawn radius -> pixel, by projecting points along +x.
  const project = (radius) => {
    const p = new cam.position.constructor(radius, 0, 0);
    p.project(cam);
    return (p.x * 0.5 + 0.5) * canvas.width;
  };
  const pxAt = {};
  for (const r of [100, 104.43, 106.41, 110, 119.15, 130.77, 145, 160.2]) pxAt[r] = project(r);

  // Ruler inverse, teaching branch: drawn = 100 * (1 + 0.28*ln(1+alt/350)).
  const altitudeFromDrawn = (drawn) => 350 * (Math.exp((drawn / 100 - 1) / 0.28) - 1);
  const drawnFromPx = (px) => {
    // Linear in x because the projection of the x axis is linear in this view.
    const p0 = project(0), p1 = project(100);
    return ((px - p0) / (p1 - p0)) * 100;
  };

  const out = {};
  for (const c of candidates) {
    if (c.extinction !== null) uniforms.extinction.value = c.extinction;
    if (c.exponent !== null) uniforms.opacityCurveExponent.value = c.exponent;
    if (c.empirical !== null) uniforms.empiricalOpacityScale.value = c.empirical;
    if (c.maxAlpha !== null) uniforms.minimumTransmittance.value = 1 - c.maxAlpha;
    renderer.render(globe.scene, cam);

    const gl = renderer.getContext();
    const w = gl.drawingBufferWidth, h = gl.drawingBufferHeight;
    const row = Math.round(h / 2);
    const pixels = new Uint8Array(w * 4);
    gl.readPixels(0, h - 1 - row, w, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixels);

    const samples = [];
    const startPx = Math.round(project(100.2) * (w / canvas.width));
    const endPx = Math.round(project(161) * (w / canvas.width));
    for (let px = startPx; px <= endPx; px += 1) {
      const drawn = drawnFromPx(px * (canvas.width / w));
      if (drawn < 100.1 || drawn > 160.5) continue;
      const i = px * 4;
      const r = pixels[i], g = pixels[i + 1], b = pixels[i + 2];
      samples.push({
        altitudeKm: Math.round(altitudeFromDrawn(drawn) * 10) / 10,
        drawn: Math.round(drawn * 100) / 100,
        luminance: Math.round((0.2126 * r + 0.7152 * g + 0.0722 * b) * 10) / 10,
        rgb: [r, g, b],
      });
    }
    out[c.name] = samples;
  }
  return { pxAt, out };
}, {
  candidates: [
    { name: "d06", extinction: 0.022, exponent: 3.0, empirical: 6.0, maxAlpha: 0.85 },
    { name: "d25", extinction: 0.022, exponent: 3.0, empirical: 25.0, maxAlpha: 0.85 },
    { name: "d80", extinction: 0.022, exponent: 3.0, empirical: 80.0, maxAlpha: 0.85 },
    { name: "d300", extinction: 0.022, exponent: 3.0, empirical: 300.0, maxAlpha: 0.85 },
  ],
});

writeFileSync(`${outDir}/profile.json`, JSON.stringify(probe, null, 1));
for (const [name, samples] of Object.entries(probe.out)) {
  console.log(`\n=== ${name} ===`);
  // Print a coarse profile: every ~8th sample, plus the local maxima.
  const at = (target) => {
    let best = samples[0];
    for (const s of samples) if (Math.abs(s.altitudeKm - target) < Math.abs(best.altitudeKm - target)) best = s;
    return best;
  };
  console.log([65, 75, 85, 95, 110, 130, 160, 200, 250, 300, 350, 400, 450, 550, 700, 900, 1200]
    .map((a) => `${a}:${at(a).luminance}`).join("  "));
  console.log("  hue at 75km", at(75).rgb, " at 400km", at(400).rgb);
  const maxima = samples.filter((s, i) =>
    i > 2 && i < samples.length - 3
    && s.luminance > samples[i - 3].luminance && s.luminance > samples[i + 3].luminance
    && s.luminance > 4);
  console.log("LOCAL MAXIMA:", maxima.map((s) => `${s.altitudeKm}km(${s.luminance})`).join(", ") || "none");
}
console.log("HIDDEN", await page.evaluate(() => globalThis.__hidden));
console.log("\nERRORS", errors.length, errors.slice(0, 5));
await browser.close();
