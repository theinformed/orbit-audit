// The completed particle lifecycle, end to end: arrival, trapped motion, loss.
//   node tools/lifecycle-shots.mjs <outDir> <baseURL> <width> <height>
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";

const outDir = process.argv[2];
const baseURL = process.argv[3] ?? "http://127.0.0.1:5311/";
const width = Number(process.argv[4] ?? 1440);
const height = Number(process.argv[5] ?? 900);
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1 });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
await page.addInitScript(() => {
  try { window.localStorage.setItem("space-explorer-hide-welcome-v1", "1"); } catch { /* ignore */ }
});
await page.route("**/src/main.ts*", async (route) => {
  const source = await fetch(route.request().url()).then((r) => r.text());
  await route.fulfill({
    body: source.replace(
      "new ExplorerApp(manifest, catalog, weather, events, land);",
      "globalThis.__app = new ExplorerApp(manifest, catalog, weather, events, land);",
    ),
    contentType: "text/javascript",
  });
});
page.setDefaultTimeout(90000); page.setDefaultNavigationTimeout(90000); await page.goto(baseURL, { waitUntil: "domcontentloaded" });
await page.waitForFunction(() => Boolean(globalThis.__app), null, { timeout: 120000 });
await page.waitForTimeout(9000);
const env = page.locator('[data-explorer-mode="environment"]');
if (await env.count()) { await env.click(); await page.waitForTimeout(2500); }

const shot = async (name) => {
  try { await page.screenshot({ path: `${outDir}/${name}.png`, animations: "disabled", timeout: 20000 }); }
  catch { await page.screenshot({ path: `${outDir}/${name}.png`, timeout: 20000 }); }
};

// The most strongly COUPLED instant in the measured window: the site's own
// published Newell coupling function, not a guess at which hour looked busy.
const pick = await page.evaluate(() => {
  const series = globalThis.__app?.weather?.magnetopause?.driverSeries ?? [];
  let best = null;
  for (const row of series) {
    if (!Number.isFinite(row.newellCoupling)) continue;
    if (!best || row.newellCoupling > best.newellCoupling) best = row;
  }
  return best;
});
console.log("coupling peak", JSON.stringify(pick && {
  validAt: pick.validAt, newell: pick.newellCoupling, bz: pick.bzGsmNt, v: pick.speedKps,
}));
if (pick?.validAt) {
  await page.evaluate((iso) => {
    const slider = document.getElementById("time-slider");
    const minutes = Math.round((new Date(iso).getTime() - Date.now()) / 60000);
    slider.value = String(Math.max(Number(slider.min), Math.min(Number(slider.max), minutes)));
    slider.dispatchEvent(new Event("input", { bubbles: true }));
    slider.dispatchEvent(new Event("change", { bubbles: true }));
  }, pick.validAt);
  await page.waitForTimeout(5000);
}

await page.evaluate(async () => {
  const ids = ["layer-ionosphere", "layer-tec", "layer-drap", "layer-aurora", "layer-regions",
    "annotate-empirical-boundaries", "layer-plasmasphere", "layer-thermosphere",
    "layer-geospace", "layer-solar-wind", "layer-photons", "layer-radiation", "layer-ring-current"];
  const wanted = ["layer-geospace", "layer-solar-wind", "layer-ring-current", "layer-radiation"];
  for (const id of ids) {
    const el = document.getElementById(id);
    if (!el) continue;
    if (el.checked !== wanted.includes(id)) { el.click(); await new Promise((r) => setTimeout(r, 200)); }
  }
});
await page.waitForTimeout(8000);

const report = await page.evaluate(() => {
  const globe = globalThis.__app?.globe;
  const visual = globe?.solarWindVisual ?? null;
  const paths = visual?.guidancePathsValue ?? null;
  const out = { tailReturn: globe?.getTailReturnReport?.() ?? null, drive: visual?.couplingDriveValue ?? null };
  if (paths) {
    const ring = paths.filter((p) => p.branch === "ring-current");
    out.ringCount = ring.length;
    out.neutralCount = ring.filter((p) => p.neutralFromIndex != null).length;
    // The drawn geometry itself, so the shape can be checked without trusting
    // the render: one ion path and one electron path, whole.
    const ion = ring.find((p) => p.driftSense === "westward");
    const electron = ring.find((p) => p.driftSense === "eastward");
    out.dump = [ion, electron].filter(Boolean).map((p) => ({
      driftSense: p.driftSense, schematicFromIndex: p.schematicFromIndex,
      neutralFromIndex: p.neutralFromIndex ?? null,
      points: p.pointsGsmRe.map((q) => [Number(q.x.toFixed(4)), Number(q.y.toFixed(4)), Number(q.z.toFixed(4))]),
    }));
  }
  out.legend = document.querySelector(".map-key")?.innerText ?? null;
  out.card = document.querySelector('[data-layer-panel="solarWind"]')?.innerText?.slice(0, 3000) ?? null;
  return out;
});
writeFileSync(`${outDir}/report.json`, JSON.stringify({ pick, report, errors }, null, 2));
console.log("ring", report.ringCount, "neutral", report.neutralCount, "drive", report.drive);

// 1. The whole chain: wind arriving, the tail, the inner magnetosphere.
await page.evaluate(() => globalThis.__app.globe.focusMagnetosphereObliqueView?.() ?? globalThis.__app.globe.focusSunEarthSideView());
await page.waitForTimeout(3000);
await shot("01-chain");

// 2. Down onto the equatorial plane: the drift, and the neutrals leaving it.
await page.evaluate(() => globalThis.__app.globe.focusPolarView());
await page.waitForTimeout(1200);
await page.evaluate(() => globalThis.__app.globe.zoomBy(0.55));
await page.waitForTimeout(2500);
for (let i = 0; i < 4; i += 1) { await shot(`02-plan-${i}`); await page.waitForTimeout(1600); }

// 3. Oblique and close: the bounce, which is an out-of-plane motion and does
//    not read at all from directly above.
await page.evaluate(() => globalThis.__app.globe.focusRadiationObliqueView());
await page.waitForTimeout(1200);
await page.evaluate(() => globalThis.__app.globe.zoomBy(0.62));
await page.waitForTimeout(2500);
for (let i = 0; i < 4; i += 1) { await shot(`03-trapped-${i}`); await page.waitForTimeout(1600); }

console.log("ERRORS", errors.slice(0, 8));
await browser.close();
