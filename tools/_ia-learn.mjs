import { chromium } from '@playwright/test';
const baseURL = process.argv[2];
const out = process.argv[3];
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
await page.addInitScript(() => { try { window.localStorage.clear(); window.localStorage.setItem('space-explorer-hide-welcome-v1','1'); } catch {} });
await page.goto(baseURL, { waitUntil: 'load' });
await page.waitForTimeout(1500);
const dlg = page.locator('#welcome-dialog');
if (await dlg.isVisible().catch(()=>false)) { await page.locator('#welcome-dialog .primary-button').click(); await page.waitForTimeout(400); }
await page.locator('[data-explorer-mode="environment"]').click();
await page.waitForTimeout(3500);
await page.evaluate(() => { document.querySelectorAll('#layer-list input[type=checkbox]').forEach((b)=>{ if (b.checked) b.click(); }); });
await page.evaluate(() => document.getElementById('layer-ring-current').click());
await page.waitForTimeout(7000);
if (await page.locator('#data-viewer').evaluate((el)=>el.classList.contains('is-collapsed'))) await page.locator('#data-viewer-head').click();
await page.waitForTimeout(1200);
// The door out of the card.
await page.evaluate(() => { document.querySelectorAll('#data-viewer-cards [data-card-section="provenance"]').forEach((d) => d.setAttribute('open','')); });
 await page.waitForTimeout(500);
 const link = page.locator('#data-viewer-cards [data-card-build-link]:not([hidden])').first();
console.log('BUILD LINK:', await link.textContent());
await link.click();
await page.waitForTimeout(2500);
const card = page.locator('#method-ring-current');
await card.scrollIntoViewIfNeeded();
await page.waitForTimeout(600);
console.log(await page.evaluate(() => {
  const c = document.getElementById('method-ring-current');
  if (!c) return 'NO METHOD CARD';
  const rows = [...c.querySelectorAll('.method-card-body dl > div')].map((d)=>d.querySelector('dt').textContent);
  const standing = [...c.querySelectorAll('.method-card-body .fact-grid > div')].map((d)=>d.textContent.slice(0,90));
  return JSON.stringify({ open: c.open, rows, standing }, null, 1);
}));
await page.screenshot({ path: out });
await browser.close();
