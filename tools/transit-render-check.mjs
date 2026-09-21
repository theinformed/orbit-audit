/**
 * Drives tools/transit-render-check.html in a real browser and reports whether
 * the planner globe draws coastlines where its transform says they are.
 *
 * Usage:
 *   npx vite --host 127.0.0.1 --port 5178 &
 *   node tools/transit-render-check.mjs
 *
 * Exits non-zero if any landmark fails, so it can be a gate rather than a
 * screenshot somebody has to look at.
 */

import { chromium } from "@playwright/test";

const baseUrl = process.env.RENDER_CHECK_URL ?? "http://127.0.0.1:5178";
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1100, height: 800 } });

page.on("console", (message) => {
  if (message.type() === "error") console.error("[page]", message.text());
});

await page.goto(`${baseUrl}/tools/transit-render-check.html`, { waitUntil: "load" });
await page.waitForFunction(() => window.transitRenderCheck?.ready === true, null, { timeout: 180_000 });
const outcome = await page.evaluate(() => window.transitRenderCheck);
await browser.close();

if (outcome.error) {
  console.error("Render check failed to run:", outcome.error);
  process.exit(2);
}

const pad = (value, width) => String(value).padEnd(width);
console.log(`\n${pad("landmark", 36)}${pad("expect", 9)}${pad("screen", 14)}${pad("coast px", 10)}result`);
for (const result of outcome.results) {
  console.log(
    pad(result.name, 36)
    + pad(result.expectCoast ? "coast" : "ocean", 9)
    + pad(`${result.screenX},${result.screenY}`, 14)
    + pad(result.coastlinePixels, 10)
    + (result.passed ? "PASS" : "FAIL"),
  );
}
console.log(`\n${outcome.allPassed ? "All landmarks registered correctly." : "REGISTRATION FAILURE."}`);
process.exit(outcome.allPassed ? 0 : 1);
