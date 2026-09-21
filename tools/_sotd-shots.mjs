import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";
const OUT = "/tmp/sotd-shots"; mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch();

for (const [label, width, height] of [["1440", 1440, 900], ["390", 390, 844]]) {
  const context = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  await page.addInitScript(() => localStorage.setItem("space-explorer-hide-welcome-v1", "1"));
  await page.goto("http://127.0.0.1:4173/");
  await page.locator("#visible-count").filter({ hasText: "shown" }).waitFor({ timeout: 180000 });
  await page.waitForTimeout(3500);
  const phone = width < 820;
  const openRail = async () => {
    if (!phone) return;
    const cls = (await page.locator("#control-rail").getAttribute("class")) ?? "";
    if (!cls.includes("is-open")) {
      await page.locator("#mobile-panel-toggle").first().click();
      await page.waitForTimeout(900);
    }
  };
  const measure = async (stage) => ({
    stage,
    count: (await page.locator("#visible-count").textContent())?.trim(),
    litOrbitBands: await page.locator("[data-orbit].is-active").count(),
    checked: await page.locator("[data-mission-facet]:checked, [data-constellation]:checked, [data-owner]:checked").count(),
    chips: {
      mission: (await page.locator("#mission-facet-state").textContent())?.trim(),
      constellation: (await page.locator("#constellation-facet-state").textContent())?.trim(),
      owner: (await page.locator("#owner-facet-state").textContent())?.trim(),
      stack: (await page.locator("#filter-stack-state").textContent())?.trim(),
    },
    featured: (await page.locator("#featured-line").isVisible())
      ? (await page.locator("#featured-line").textContent())?.trim() : null,
    statusRowVisible: await page.locator("#filter-status").isVisible(),
    statusText: (await page.locator("#filter-status-text").textContent())?.trim(),
    recoveryButtons: await page.locator("#control-rail button").evaluateAll((nodes) => nodes
      .filter((n) => !n.hidden && n.offsetParent !== null)
      .map((n) => (n.textContent ?? "").trim())
      .filter((t) => /show (every|all)|again|restore|bring back/i.test(t))),
  });
  const out = [];
  await page.screenshot({ path: `${OUT}/${label}-1-load-globe.png` });
  await openRail();
  await page.screenshot({ path: `${OUT}/${label}-2-load-rail.png` });
  out.push(await measure("load (GPS shown)"));

  await page.locator('[data-orbit="LEO"]').click();
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${OUT}/${label}-3-leo.png` });
  out.push(await measure("LEO selected"));

  await page.locator("#mission-clear-all").click();
  await page.waitForTimeout(1800);
  await page.locator("#filter-status").scrollIntoViewIfNeeded().catch(() => {});
  await page.screenshot({ path: `${OUT}/${label}-4-cleared-in-leo.png` });
  out.push(await measure("cleared, still in LEO"));

  await page.locator('[data-orbit="LEO"]').click();
  await page.waitForTimeout(1800);
  await page.locator("#mission-clear-all").click();
  await page.waitForTimeout(1800);
  await page.screenshot({ path: `${OUT}/${label}-5-cleared-unset.png` });
  out.push(await measure("LEO deselected, all cleared"));

  console.log(JSON.stringify({ viewport: label, stages: out }, null, 1));
  await context.close();
}
await browser.close();
