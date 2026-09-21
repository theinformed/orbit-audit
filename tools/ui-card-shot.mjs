// One card, one screenshot: the left-hand satellite card Sean flagged.
// Usage: node tools/ui-card-shot.mjs <outFile> <baseURL> [satellite]
import { chromium } from "@playwright/test";

const [outFile, baseURL, target = "NAVSTAR 68"] = process.argv.slice(2);
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
await page.addInitScript(() => {
  try { window.localStorage.setItem("space-explorer-hide-welcome-v1", "1"); } catch { /* ignore */ }
});
await page.goto(baseURL, { waitUntil: "load" });
await page.waitForTimeout(9000);
const welcome = page.locator("#welcome-dialog .primary-button");
if (await welcome.isVisible().catch(() => false)) await welcome.click();
await page.locator("#satellite-search").fill(target);
await page.waitForTimeout(1500);
await page.locator("#search-results .search-result").first().click();
await page.waitForTimeout(4000);
const card = page.locator("#satellite-stack, .satellite-card").first();
await card.screenshot({ path: outFile });
console.log("wrote", outFile);
await browser.close();
