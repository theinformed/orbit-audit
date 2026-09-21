// The orbits the geostationary joint was argued over, seen face-on.
// node tools/geo-joint-orbit-shots.mjs <outDir> <baseURL>
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";

const outDir = process.argv[2];
const baseURL = process.argv[3] ?? "http://127.0.0.1:5173/";
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
await page.waitForFunction(() => Boolean(globalThis.__app), null, { timeout: 90000 });
await page.waitForTimeout(9000);

/** Look straight down the selected orbit's own plane normal, at `scale` of the framing distance. */
const faceOn = (scale) => page.evaluate((wanted) => {
  const globe = globalThis.__app.globe;
  const group = globe.selectionOrbitGroup;
  let normal = null;
  if (group) {
    let line = null;
    group.traverse((child) => {
      const attribute = child.geometry?.getAttribute?.("position");
      if (attribute && attribute.count > 8 && (!line || attribute.count > line.geometry.getAttribute("position").count)) line = child;
    });
    if (line) {
      line.updateWorldMatrix(true, false);
      const e = line.matrixWorld.elements;
      const attribute = line.geometry.getAttribute("position");
      const world = (index) => {
        const x = attribute.getX(index); const y = attribute.getY(index); const z = attribute.getZ(index);
        return [e[0] * x + e[4] * y + e[8] * z + e[12], e[1] * x + e[5] * y + e[9] * z + e[13], e[2] * x + e[6] * y + e[10] * z + e[14]];
      };
      let nx = 0; let ny = 0; let nz = 0;
      for (let index = 0; index + 1 < attribute.count; index += 1) {
        const a = world(index); const b = world(index + 1);
        nx += a[1] * b[2] - a[2] * b[1];
        ny += a[2] * b[0] - a[0] * b[2];
        nz += a[0] * b[1] - a[1] * b[0];
      }
      const length = Math.hypot(nx, ny, nz);
      if (length > 1e-6) normal = [nx / length, ny / length, nz / length];
    }
  }
  const distance = globe.camera.position.length() * wanted;
  const direction = normal ?? [0, 1, 0];
  globe.camera.position.set(direction[0] * distance, direction[1] * distance, direction[2] * distance);
  globe.controls.target.set(0, 0, 0);
  globe.controls.update();
  return { normal, distance: Math.round(distance) };
}, scale);

const objects = [["themis-a", 30580], ["xmm", 25989], ["meridian-9", 45254], ["cluster-ii-fm7", 26410]];
for (const [slug, norad] of objects) {
  await page.evaluate((id) => globalThis.__app.selectSatelliteByNorad(id), norad);
  await page.waitForTimeout(7000);
  console.log(slug, JSON.stringify(await faceOn(1)));
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${outDir}/${slug}-plan.png` });
  await faceOn(0.42);
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${outDir}/${slug}-plan-close.png` });
}

console.log("console errors:", errors.length, errors.slice(0, 8));
await browser.close();
