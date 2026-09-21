// The shipped lifecycle, as a reader sees it.
//   node tools/lifecycle-final.mjs <outDir> <baseURL> <width> <height> <drive|measured>
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
const outDir = process.argv[2];
const baseURL = process.argv[3] ?? "http://127.0.0.1:5312/";
const width = Number(process.argv[4] ?? 1440);
const height = Number(process.argv[5] ?? 900);
const driveArg = process.argv[6] ?? "measured";
const drive = driveArg === "measured" ? null : Number(driveArg);
mkdirSync(outDir, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1, isMobile: width < 500, hasTouch: width < 500 });
page.setDefaultTimeout(600000); page.setDefaultNavigationTimeout(600000);
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
await page.addInitScript(() => { try { window.localStorage.setItem("space-explorer-hide-welcome-v1", "1"); } catch {} });
await page.route("**/src/main.ts*", async (route) => {
  const s = await fetch(route.request().url()).then((r) => r.text());
  await route.fulfill({ body: s.replace("new ExplorerApp(manifest, catalog, weather, events, land);", "globalThis.__app = new ExplorerApp(manifest, catalog, weather, events, land);"), contentType: "text/javascript" });
});
console.log("goto"); await page.goto(baseURL, { waitUntil: "domcontentloaded" }); console.log("loaded");
await page.waitForFunction(() => Boolean(globalThis.__app), null, { timeout: 900000 });
console.log("app up"); await page.waitForTimeout(11000);
// A DOM click, not a Playwright one: at 390 the mode control lives inside a
// collapsed panel, and waiting for it to be visible hangs the capture.
await page.evaluate(() => {
  const el = document.querySelector('[data-explorer-mode="environment"]');
  if (el) el.click();
});
await page.waitForTimeout(3000);
const pick = await page.evaluate(() => {
  const s = globalThis.__app?.weather?.magnetopause?.driverSeries ?? [];
  let best = null;
  for (const r of s) { if (!Number.isFinite(r.newellCoupling)) continue; if (!best || r.newellCoupling > best.newellCoupling) best = r; }
  return best;
});
if (pick?.validAt) {
  await page.evaluate((iso) => {
    const sl = document.getElementById("time-slider");
    sl.value = String(Math.max(Number(sl.min), Math.min(Number(sl.max), Math.round((new Date(iso).getTime() - Date.now()) / 60000))));
    sl.dispatchEvent(new Event("input", { bubbles: true }));
    sl.dispatchEvent(new Event("change", { bubbles: true }));
  }, pick.validAt);
  await page.waitForTimeout(4000);
}
await page.evaluate(async () => {
  const ids = ["layer-ionosphere","layer-tec","layer-drap","layer-aurora","layer-regions","annotate-empirical-boundaries","layer-plasmasphere","layer-thermosphere","layer-geospace","layer-solar-wind","layer-photons","layer-radiation","layer-ring-current"];
  const wanted = ["layer-geospace","layer-solar-wind","layer-ring-current","layer-radiation"];
  for (const id of ids) { const el = document.getElementById(id); if (!el) continue; if (el.checked !== wanted.includes(id)) { el.click(); await new Promise((r)=>setTimeout(r,220)); } }
});
await page.waitForTimeout(9000);
if (drive !== null) {
  await page.evaluate((f) => { const v = globalThis.__app.globe.solarWindVisual; const o = v.setCouplingDrive.bind(v); v.setCouplingDrive = () => o(f); o(f); }, drive);
  await page.waitForTimeout(2500);
}
console.log("shooting"); const shot = async (n) => { try { await page.screenshot({ path: `${outDir}/${n}.png`, animations: "disabled", timeout: 40000 }); } catch { await page.screenshot({ path: `${outDir}/${n}.png`, timeout: 60000 }); } };
await page.evaluate(() => globalThis.__app.globe.focusMagnetosphereObliqueView());
await page.waitForTimeout(3500);
await shot("a-arrival-and-chain");
await page.evaluate(() => globalThis.__app.globe.focusRadiationObliqueView());
await page.waitForTimeout(1500);
await page.evaluate(() => globalThis.__app.globe.zoomBy(0.55));
await page.waitForTimeout(3500);
await shot("b-trapped-and-loss-0");
await page.waitForTimeout(2200);
await shot("b-trapped-and-loss-1");
await page.evaluate(() => globalThis.__app.globe.focusPolarView());
await page.waitForTimeout(1500);
await page.evaluate(() => globalThis.__app.globe.zoomBy(0.5));
await page.waitForTimeout(3500);
await shot("c-plan-drift-and-neutrals");
const card = await page.evaluate(() => document.querySelector('[data-layer-panel="solarWind"]')?.innerText ?? null);
writeFileSync(`${outDir}/card.txt`, card ?? "");
writeFileSync(`${outDir}/meta.json`, JSON.stringify({ pick, errors }, null, 2));
console.log("done", driveArg, width, "errors", errors.length);
await browser.close();
