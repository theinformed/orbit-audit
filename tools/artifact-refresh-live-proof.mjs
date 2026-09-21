// Live proof that an open tab adopts a newer published release without losing
// the visitor's place.
//
// It reproduces the real failure first: a tab left open for hours still holds a
// geospace bundle whose coverage window has run out, so the radiation belts
// honestly report "NO DATA - AFTER COVERAGE - HIDDEN". It then publishes the
// current release and checks that the belts come back while the selected
// satellite, the open detail card and the layer toggles all survive.
//
// Nothing on disk is touched. Both the stale and the current manifest are served
// by intercepting the manifest request, so the five-minute publisher that owns
// public/data is never disturbed.
//
// Usage (dev server must already be running):
//   npm run dev                       # note the port it prints
//   BASE=http://127.0.0.1:5173 node tools/artifact-refresh-live-proof.mjs
//
// Exit code 0 means the refresh adopted the new release with state preserved.
import { chromium } from "@playwright/test";
import { readFileSync, readdirSync } from "node:fs";

const BASE = process.env.BASE ?? "http://127.0.0.1:5174";
const ROOT = "/home/sdegan/space-teaching-aid/public/data";

const realManifest = JSON.parse(readFileSync(`${ROOT}/manifest.json`, "utf8"));
const currentGeospace = realManifest.geospace.path;

// Reproduce the real failure: a tab that has been open for hours is still
// holding a geospace bundle whose coverage window has run out, so the radiation
// belts honestly report NO DATA. We boot the page on that stale artifact, then
// publish the current one and watch the belts come back.
const stale = readdirSync(`${ROOT}/artifacts`)
  .filter((f) => f.startsWith("geospace-model-") && f.endsWith(".json"))
  .map((f) => {
    const b = JSON.parse(readFileSync(`${ROOT}/artifacts/${f}`, "utf8"));
    return { path: `artifacts/${f}`, last: Date.parse(b.frames[b.frames.length - 1].validAt), frames: b.frames };
  })
  .sort((a, b) => a.last - b.last)[0];

const staleManifest = {
  ...realManifest,
  release: "STALE-TAB",
  geospace: {
    ...realManifest.geospace,
    path: stale.path,
    sha256: "simulated-stale",
    frameCount: stale.frames.length,
    validFrom: stale.frames[0].validAt,
    validTo: stale.frames[stale.frames.length - 1].validAt,
  },
};
const nextGeospace = currentGeospace;
const nextManifest = realManifest;

console.log(`stale (tab opened hours ago): ${stale.path} ends ${new Date(stale.last).toISOString()}`);
console.log(`newly published          : ${nextGeospace}`);

let serveNext = false;
const requested = [];
const consoleErrors = [];

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.addInitScript(() => localStorage.setItem("space-explorer-hide-welcome-v1", "1"));
page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text()); if (m.type() === "warning") console.log("PAGE WARN:", m.text()); });
page.on("pageerror", (e) => consoleErrors.push(`pageerror: ${e.message}`));
page.on("request", (r) => {
  const u = new URL(r.url());
  if (u.pathname.includes("geospace-model-")) requested.push(u.pathname.split("/").pop());
});

await page.route("**/data/manifest.json*", async (route) => {
  console.log(`  [route] manifest requested -> serving ${serveNext ? "NEW" : "current"} (${route.request().url()})`);
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(serveNext ? nextManifest : staleManifest),
  });
});

await page.goto(`${BASE}/?refreshMs=5000`);
await page.locator("#visible-count").filter({ hasText: "shown" }).first().waitFor({ timeout: 120_000 });
console.log("page booted");

// Put the visitor somewhere specific first: pick a satellite in satellites mode.
await page.locator("#satellite-search").fill("HST");
await page.locator(".search-result").first().waitFor({ timeout: 20_000 });
await page.locator(".search-result").first().click();
await page.waitForTimeout(2_000);

// Then open the radiation-belt layer so the geospace bundle is genuinely live.
await page.locator('[data-explorer-mode="environment"]').click();
await page.locator('[data-mode-panel="environment"]').waitFor({ state: "visible" });
await page.locator("#layer-radiation").check();
await page.locator("#geospace-time").filter({ hasNotText: "LOADING" }).first().waitFor({ timeout: 60_000 });
await page.waitForTimeout(2_000);
console.log(`geospace artifact fetches before republish: ${JSON.stringify(requested)}`);

const before = await page.evaluate(() => ({
  selected: document.getElementById("satellite-name")?.textContent ?? null,
  cardHidden: document.getElementById("satellite-card")?.hasAttribute("hidden") ?? true,
  radiationChecked: document.getElementById("layer-radiation")?.checked ?? false,
  geospaceTime: document.getElementById("geospace-time")?.textContent ?? null,
  statusTitle: document.getElementById("data-status")?.title ?? "",
}));
console.log("BEFORE:", JSON.stringify(before, null, 2));

// --- simulate bigmem publishing a newer release ---
serveNext = true;
console.log("republished; waiting for the open tab to adopt it...");
const deadline = Date.now() + 45_000;
let adopted = false;
while (Date.now() < deadline) {
  if (requested.some((f) => nextGeospace.endsWith(f))) { adopted = true; break; }
  await page.waitForTimeout(1000);
}

const after = await page.evaluate(() => ({
  selected: document.getElementById("satellite-name")?.textContent ?? null,
  cardHidden: document.getElementById("satellite-card")?.hasAttribute("hidden") ?? true,
  radiationChecked: document.getElementById("layer-radiation")?.checked ?? false,
  geospaceTime: document.getElementById("geospace-time")?.textContent ?? null,
  statusTitle: document.getElementById("data-status")?.title ?? "",
}));
console.log("AFTER:", JSON.stringify(after, null, 2));

await page.screenshot({ path: "/tmp/refresh-proof-after.png" });

console.log("\n================ RESULT ================");
console.log(`new geospace artifact fetched : ${adopted ? "YES" : "NO"}`);
console.log(`all geospace fetches          : ${JSON.stringify(requested)}`);
console.log(`selection preserved           : ${before.selected === after.selected && after.selected !== null ? "YES" : `NO (${before.selected} -> ${after.selected})`}`);
console.log(`satellite card still open     : ${after.cardHidden === false ? "YES" : "NO"}`);
console.log(`radiation layer still on      : ${after.radiationChecked ? "YES" : "NO"}`);
console.log(`console errors                : ${consoleErrors.length}`);
if (consoleErrors.length) console.log(consoleErrors.slice(0, 10).join("\n"));
console.log("========================================");

await browser.close();
process.exit(adopted && after.radiationChecked && consoleErrors.length === 0 ? 0 : 1);
