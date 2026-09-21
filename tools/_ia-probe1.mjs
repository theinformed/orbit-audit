import { chromium } from '@playwright/test';
const baseURL = process.argv[2];
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.addInitScript(() => { try { window.localStorage.clear(); window.localStorage.setItem('space-explorer-hide-welcome-v1','1'); } catch {} });
await page.goto(baseURL, { waitUntil: 'load' });
await page.waitForTimeout(1500);
const dlg = page.locator('#welcome-dialog');
if (await dlg.isVisible().catch(()=>false)) { await page.locator('#welcome-dialog .primary-button').click(); await page.waitForTimeout(400); }
await page.locator('[data-explorer-mode="environment"]').click();
await page.waitForTimeout(4000);
await page.evaluate(() => { document.querySelectorAll('#layer-list input[type=checkbox]').forEach((b)=>{ if (b.checked) b.click(); }); });
await page.waitForTimeout(2000);
for (const id of (process.argv[3] ?? 'layer-geospace').split(',')) {
  await page.evaluate((i) => document.getElementById(i).click(), id);
  await page.waitForTimeout(5000);
}
if (await page.locator('#data-viewer').evaluate((el)=>el.classList.contains('is-collapsed'))) await page.locator('#data-viewer-head').click();
await page.waitForTimeout(1500);
console.log(await page.evaluate(() => {
  const out = [];
  document.querySelectorAll('#data-viewer-cards [data-layer-card]').forEach((c) => {
    out.push({ layer: c.dataset.layer, collapsed: c.classList.contains('is-collapsed'), h: Math.round(c.getBoundingClientRect().height),
      sections: [...c.querySelectorAll('[data-card-section]')].map((s)=>s.dataset.cardSection + (s.hidden?':hidden':'') + (s.open?':OPEN':':shut') + '/' + Math.round(s.getBoundingClientRect().height) + 'px'),
      badge: c.querySelector('[data-card-mission]').textContent + ' | ' + c.querySelector('[data-card-mission]').className,
      badgeInHead: !!c.querySelector('.sat-card-head [data-card-mission]'),
    });
  });
  return JSON.stringify(out, null, 1);
}));
await browser.close();
