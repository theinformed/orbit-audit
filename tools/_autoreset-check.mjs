import { chromium } from "@playwright/test";
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.addInitScript(() => localStorage.setItem("space-explorer-hide-welcome-v1", "1"));
await page.goto("http://127.0.0.1:4173/");
await page.locator("#visible-count").filter({ hasText: "shown" }).waitFor({ timeout: 180000 });
await page.waitForTimeout(3000);
// Take the whole catalog, then "only GPS" off the fleet row, then untick the
// one mission those objects fly. A reader asking "just GPS — and not
// navigation?" gets an answer the site did not have to be asked for.
await page.locator('[data-orbit="all"]').click();
await page.waitForTimeout(2000);
await page.locator("#filter-stack > details").filter({ hasText: "Constellation / fleet" }).locator("summary").click();
const row = page.locator('[data-constellation="GPS"]').locator("xpath=..");
await row.hover();
await row.locator("button.facet-only").click();
await page.waitForTimeout(1500);
console.log("after only-GPS:", (await page.locator("#visible-count").textContent())?.trim(),
  "| status:", await page.locator("#filter-status").isVisible());
await page.locator('[data-mission-facet][value="navigation"]').uncheck();
await page.waitForTimeout(1500);
console.log(JSON.stringify({
  shown: (await page.locator("#visible-count").textContent())?.trim(),
  statusVisible: await page.locator("#filter-status").isVisible(),
  statusText: (await page.locator("#filter-status-text").textContent())?.trim(),
  buttonsInRow: await page.locator("#filter-status button").count(),
  checked: await page.locator("[data-mission-facet]:checked, [data-constellation]:checked, [data-owner]:checked").count(),
}, null, 1));
await page.screenshot({ path: "/tmp/sotd-shots/1440-6-autoreset.png" });
await page.locator('[data-orbit="LEO"]').click();
await page.waitForTimeout(1500);
console.log("message clears on the next action:", !(await page.locator("#filter-status").isVisible()));
await browser.close();
