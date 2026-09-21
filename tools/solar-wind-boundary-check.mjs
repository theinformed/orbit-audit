// Do the illustrative solar-wind tracers stay outside the drawn magnetopause?
// Compared in scene space, because every layer goes through the same mapper.
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";

const outDir = process.argv[2];
const baseURL = process.argv[3] ?? "http://127.0.0.1:5199/";
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1 });
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
await page.evaluate(async () => {
  const ids = ["layer-ionosphere", "layer-tec", "layer-drap", "layer-aurora", "layer-regions",
    "annotate-empirical-boundaries", "layer-geospace", "layer-solar-wind", "layer-photons", "layer-radiation"];
  for (const id of ids) {
    const el = document.getElementById(id);
    if (el && el.checked) { el.click(); await new Promise((r) => setTimeout(r, 60)); }
  }
  for (const id of ["annotate-empirical-boundaries", "layer-solar-wind", "layer-photons"]) {
    const el = document.getElementById(id);
    if (el && !el.checked) { el.click(); await new Promise((r) => setTimeout(r, 60)); }
  }
});
await page.waitForTimeout(5000);

const report = await page.evaluate(() => {
  const globe = globalThis.__app.globe;
  globe.scene.updateMatrixWorld(true);

  // Every drawn boundary vertex, in world scene coordinates, bucketed by direction.
  const surfaces = {};
  globe.magnetosphere.children.forEach((mesh) => {
    const pos = mesh.geometry.getAttribute("position");
    const pts = [];
    const v = { x: 0, y: 0, z: 0 };
    for (let i = 0; i < pos.count; i += 1) {
      v.x = pos.getX(i); v.y = pos.getY(i); v.z = pos.getZ(i);
      const r = Math.hypot(v.x, v.y, v.z);
      if (r < 1e-6) continue;
      pts.push([v.x / r, v.y / r, v.z / r, r]);
    }
    surfaces[mesh.name] = pts;
  });

  const vis = globe.solarWindVisual;
  const geom = vis.points.geometry;
  const pos = geom.getAttribute("position");
  const drawn = Math.min(pos.count, geom.drawRange.count === Infinity ? pos.count : geom.drawRange.count);
  const tracers = [];
  for (let i = 0; i < drawn; i += 1) {
    const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i);
    const r = Math.hypot(x, y, z);
    if (r < 1e-6) continue;
    tracers.push([x / r, y / r, z / r, r]);
  }

  const results = {};
  for (const [name, pts] of Object.entries(surfaces)) {
    if (name.includes("cusp")) continue;
    let inside = 0; const worst = [];
    for (const [ux, uy, uz, r] of tracers) {
      // Nearest boundary vertex in direction.
      let best = -2; let bestR = 0;
      for (const [bx, by, bz, br] of pts) {
        const dot = ux * bx + uy * by + uz * bz;
        if (dot > best) { best = dot; bestR = br; }
      }
      // Only trust the comparison where the surface actually covers the direction.
      if (best < 0.995) continue;
      if (r < bestR) { inside += 1; worst.push({ r, boundaryR: bestR, ratio: r / bestR, dir: [ux, uy, uz] }); }
    }
    worst.sort((a, b) => a.ratio - b.ratio);
    results[name] = {
      comparedDirections: tracers.length,
      insideCount: inside,
      worst: worst.slice(0, 6),
    };
  }

  // Where the boundary noses sit, on the shared ruler, for reference.
  const noses = {};
  for (const [name, pts] of Object.entries(surfaces)) {
    let best = -2; let bestR = 0;
    for (const [bx, , , br] of pts) if (bx > best) { best = bx; bestR = br; }
    noses[name] = { sunwardMostDot: best, sceneRadius: bestR };
  }

  const domain = geom.userData.domain;
  const obstacleSceneRadius = globe.modelGsmPosition(domain.obstacleRadiusRe, 0, 0).length();

  return { results, noses, domain, obstacleSceneRadius, mode: vis.mode, drawn: tracers.length };
});

writeFileSync(`${outDir}/boundary.json`, JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 1).slice(0, 6000));
console.log("errors", errors.slice(0, 5));
await browser.close();
