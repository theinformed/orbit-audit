// Legibility check for the trapped-motion and loss legs.
//
// The measured record is QUIET (peak Newell coupling 3,544 — "very quiet"), so
// the shipped picture correctly draws about a seventh of the transport roster.
// That is the right behaviour and the wrong test: it cannot answer "does the
// bounce read as a bounce, or as a smear". So this tool FORCES the drive to 1
// — a diagnostic override, never a shipped state — and looks at a full roster.
//   node tools/lifecycle-diag.mjs <outDir> <baseURL> <width> <height> <drive>
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";

const outDir = process.argv[2];
const baseURL = process.argv[3] ?? "http://127.0.0.1:5311/";
const width = Number(process.argv[4] ?? 1440);
const height = Number(process.argv[5] ?? 900);
const drive = process.argv[6] === "measured" ? null : Number(process.argv[6] ?? 1);
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1 });
page.setDefaultTimeout(90000);
page.setDefaultNavigationTimeout(90000);
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
await page.addInitScript(() => { try { window.localStorage.setItem("space-explorer-hide-welcome-v1", "1"); } catch { /* ignore */ } });
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
await page.goto(baseURL, { waitUntil: "domcontentloaded" });
await page.waitForFunction(() => Boolean(globalThis.__app), null, { timeout: 120000 });
await page.waitForTimeout(9000);
const env = page.locator('[data-explorer-mode="environment"]');
if (await env.count()) { await env.click(); await page.waitForTimeout(2500); }

const shot = async (name) => {
  try { await page.screenshot({ path: `${outDir}/${name}.png`, animations: "disabled", timeout: 20000 }); }
  catch { await page.screenshot({ path: `${outDir}/${name}.png`, timeout: 25000 }); }
};

const pick = await page.evaluate(() => {
  const series = globalThis.__app?.weather?.magnetopause?.driverSeries ?? [];
  let best = null;
  for (const row of series) {
    if (!Number.isFinite(row.newellCoupling)) continue;
    if (!best || row.newellCoupling > best.newellCoupling) best = row;
  }
  return best;
});
if (pick?.validAt) {
  await page.evaluate((iso) => {
    const slider = document.getElementById("time-slider");
    slider.value = String(Math.max(Number(slider.min), Math.min(Number(slider.max),
      Math.round((new Date(iso).getTime() - Date.now()) / 60000))));
    slider.dispatchEvent(new Event("input", { bubbles: true }));
    slider.dispatchEvent(new Event("change", { bubbles: true }));
  }, pick.validAt);
  await page.waitForTimeout(4000);
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
await page.waitForTimeout(7000);

if (drive !== null) {
  await page.evaluate((forced) => {
    const visual = globalThis.__app.globe.solarWindVisual;
    const original = visual.setCouplingDrive.bind(visual);
    visual.setCouplingDrive = () => original(forced);
    original(forced);
  }, drive);
  await page.waitForTimeout(3000);
}

const dump = await page.evaluate(() => {
  const globe = globalThis.__app.globe;
  const visual = globe.solarWindVisual;
  const paths = visual.guidancePathsValue.filter((p) => p.branch === "ring-current");
  return {
    drive: visual.couplingDriveValue,
    paths: paths.map((p) => ({
      driftSense: p.driftSense,
      schematicFromIndex: p.schematicFromIndex,
      neutralFromIndex: p.neutralFromIndex ?? null,
      points: p.pointsGsmRe.map((q) => [+q.x.toFixed(4), +q.y.toFixed(4), +q.z.toFixed(4)]),
    })),
  };
});
writeFileSync(`${outDir}/paths.json`, JSON.stringify(dump));
console.log("drive", dump.drive, "ringPaths", dump.paths.length);

await page.evaluate(() => globalThis.__app.globe.focusPolarView());
await page.waitForTimeout(1200);
await page.evaluate(() => globalThis.__app.globe.zoomBy(0.5));
await page.waitForTimeout(2500);
for (let i = 0; i < 3; i += 1) { await shot(`plan-${i}`); await page.waitForTimeout(1500); }

await page.evaluate(() => globalThis.__app.globe.focusRadiationObliqueView());
await page.waitForTimeout(1200);
await page.evaluate(() => globalThis.__app.globe.zoomBy(0.55));
await page.waitForTimeout(2500);
for (let i = 0; i < 3; i += 1) { await shot(`oblique-${i}`); await page.waitForTimeout(1500); }

console.log("ERRORS", errors.slice(0, 6));
await browser.close();
