// Two measurements the main harness does not take:
//   - the chevron's y as well as its x, across five tiles with names of very
//     different lengths (the "expander must not move" assertion);
//   - how many of the BEFORE card's words were the shared geometry block, so
//     the word-count comparison can say what moved and what was cut.
import { chromium } from "@playwright/test";
const port = process.argv[2];
const tag = process.argv[3];
const base = `http://127.0.0.1:${port}/`;
const IDS = ["37849", "58645", "29270", "23712", "25967"];
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 1400 }, deviceScaleFactor: 1 });
await page.addInitScript(() => { try { localStorage.setItem("space-explorer-hide-welcome-v1", "1"); } catch {} });
await page.goto(base, { waitUntil: "load" });
await page.waitForTimeout(3500);
for (const id of IDS) {
  await page.evaluate((v) => {
    const el = document.querySelector("#satellite-search");
    el.value = v;
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }, id);
  await page.waitForTimeout(700);
  await page.evaluate(() => document.querySelector("#search-results .search-result")?.click());
  await page.waitForTimeout(900);
}
await page.evaluate(() => {
  document.querySelectorAll("[data-sat-card].is-collapsed [data-card-toggle]").forEach((t) => t.click());
});
await page.waitForTimeout(1200);
for (const [w, scale] of [[1440, "large"], [390, "large"], [900, "largest"], [320, "largest"]]) {
  await page.evaluate((v) => {
    document.querySelector(`[data-interface-scale="${v}"]`)?.click();
    document.documentElement.dataset.interfaceScale = v;
  }, scale);
  await page.setViewportSize({ width: w, height: 1400 });
  await page.waitForTimeout(900);
  const m = await page.evaluate(() => {
    const cards = [...document.querySelectorAll("[data-sat-card]")];
    const geometry = document.getElementById("satellite-geometry-block");
    return {
      names: cards.map((c) => (c.querySelector("[data-card-name]")?.textContent || "").trim()),
      nameHeights: cards.map((c) => Math.round(c.querySelector("[data-card-name]").getBoundingClientRect().height)),
      chevronX: cards.map((c) => {
        const e = c.querySelector(".sat-card-chevron");
        return Math.round((e.getBoundingClientRect().left - c.getBoundingClientRect().left) * 100) / 100;
      }),
      chevronY: cards.map((c) => {
        const e = c.querySelector(".sat-card-chevron");
        return Math.round((e.getBoundingClientRect().top - c.getBoundingClientRect().top) * 100) / 100;
      }),
      starY: cards.map((c) => {
        const e = c.querySelector("[data-card-favorite]");
        return Math.round((e.getBoundingClientRect().top - c.getBoundingClientRect().top) * 100) / 100;
      }),
      geometryWords: geometry ? (geometry.innerText || "").trim().split(/\s+/).filter(Boolean).length : 0,
      geometryHeight: geometry ? Math.round(geometry.getBoundingClientRect().height) : 0,
    };
  });
  console.log(`EXTRA ${tag} ${w}/${scale} ${JSON.stringify(m)}`);
}
await page.close();
await b.close();
