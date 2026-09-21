import { chromium } from "@playwright/test";
const out = process.argv[2] ?? "/home/sdegan/space-row-scratch/shots";
const base = "http://127.0.0.1:8477/";
const SATS = process.argv.slice(3).map((a) => { const [id, key] = a.split(":"); return { id, key }; });

const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 1400 }, deviceScaleFactor: 2 });
const errs = [];
page.on("pageerror", (e) => errs.push("PAGEERROR " + e.message));
await page.addInitScript(() => { try { localStorage.setItem("space-explorer-hide-welcome-v1", "1"); } catch {} });
await page.goto(base, { waitUntil: "load" });
await page.waitForTimeout(6000);
const d = page.locator("#welcome-dialog .primary-button");
if (await d.isVisible().catch(() => false)) { await d.click(); await page.waitForTimeout(600); }

for (const s of SATS) {
  await page.evaluate(() => document.querySelector("#satellite-stack-clear")?.click());
  await page.waitForTimeout(500);
  await page.evaluate((v) => {
    const el = document.querySelector("#satellite-search");
    el.value = v; el.dispatchEvent(new Event("input", { bubbles: true }));
  }, s.id);
  await page.waitForTimeout(900);
  const ok = await page.evaluate(() => {
    const row = document.querySelector("#search-results .search-result");
    if (!row) return false; row.click(); return true;
  });
  if (!ok) { console.log(`!! no search result for ${s.id}`); continue; }
  await page.waitForTimeout(1500);
  await page.evaluate(() => {
    document.querySelectorAll("[data-sat-card].is-collapsed [data-card-toggle]").forEach((t) => t.click());
    document.querySelectorAll('[data-sat-card] [data-card-section="background"]').forEach((x) => { x.open = true; });
  });
  await page.waitForTimeout(1000);
  const m = await page.evaluate(() => {
    const c = document.querySelector("[data-sat-card]");
    return c ? { name: (c.querySelector("[data-card-name]")?.textContent || "").trim(),
                 purpose: (c.querySelector("[data-card-purpose]")?.textContent || "").trim().slice(0, 120),
                 hasSource: !!c.querySelector("[data-card-purpose-source] a") } : null;
  });
  console.log(`SHOT ${s.key} ${JSON.stringify(m)}`);
  await page.locator("#satellite-stack").screenshot({ path: `${out}/${s.key}-1440.png` }).catch((e) => console.log("shoterr", e.message));
}
console.log("errors=" + errs.length, errs.slice(0, 4).join(" | "));
await b.close();
