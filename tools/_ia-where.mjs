import { chromium } from '@playwright/test';
const baseURL = process.argv[2] ?? 'http://127.0.0.1:8471/';
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.addInitScript(() => { try { window.localStorage.setItem('space-explorer-hide-welcome-v1','1'); } catch {} });
await page.goto(baseURL, { waitUntil: 'load' });
await page.waitForTimeout(1500);
const dlg = page.locator('#welcome-dialog');
if (await dlg.isVisible().catch(()=>false)) { await page.locator('#welcome-dialog .primary-button').click(); await page.waitForTimeout(400); }
await page.locator('[data-explorer-mode="environment"]').click();
await page.waitForTimeout(4000);
await page.evaluate(() => { document.querySelectorAll('#layer-list input[type=checkbox]').forEach((b)=>{ if (b.checked) b.click(); }); });
await page.waitForTimeout(2000);
for (const id of ['layer-geospace','layer-ring-current','layer-solar-wind']) {
  await page.evaluate((i) => document.getElementById(i).click(), id);
  await page.waitForTimeout(5000);
}
if (await page.locator('#data-viewer').evaluate((el)=>el.classList.contains('is-collapsed'))) await page.locator('#data-viewer-head').click();
await page.waitForTimeout(1500);
console.log(await page.evaluate(() => { const v=document.getElementById('data-viewer'); return JSON.stringify({cls:v.className, hidden:v.hidden, h:v.getBoundingClientRect().height, bodyH: document.getElementById('data-viewer-body').getBoundingClientRect().height}); }));
const rows = await page.evaluate(() => {
  const words = (el) => {
    let w = 0;
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const p = n.parentElement; if (!p) continue;
      if (!p.offsetParent) continue;
      if (p.getBoundingClientRect().height === 0) continue;
      const shut = p.closest('details:not([open])');
      if (shut && !(p.tagName === 'SUMMARY' || p.closest('summary'))) continue;
      const t = n.textContent.trim(); if (t) w += t.split(/\s+/).length;
    }
    return w;
  };
  const out = [];
  const kc = document.getElementById('key-conditions');
  out.push(['key-conditions (Conditions right now)', words(kc), Math.round(kc.getBoundingClientRect().height)]);
  document.querySelectorAll('#data-viewer-cards [data-layer-card]').forEach((c) => {
    out.push(['card:' + c.dataset.layer, words(c), Math.round(c.getBoundingClientRect().height)]);
    c.querySelectorAll('[data-card-section]').forEach((s) => {
      if (s.hidden) return;
      out.push(['   ' + c.dataset.layer + ' / ' + s.dataset.cardSection + (s.open ? ' [open]' : ' [shut]'), words(s), Math.round(s.getBoundingClientRect().height)]);
    });
    const pm = c.querySelector('[data-card-purpose]');
    out.push(['   ' + c.dataset.layer + ' / lead sentence', words(pm), Math.round(pm.getBoundingClientRect().height)]);
    const more = c.querySelector('[data-card-purpose-more]');
    out.push(['   ' + c.dataset.layer + ' / purpose-more ' + (more.open ? '[open]' : '[shut]') + (more.hidden ? ' hidden' : ''), words(more), Math.round(more.getBoundingClientRect().height)]);
  });
  return out;
});
for (const [n, w, h] of rows) console.log(String(w).padStart(5), String(h).padStart(5) + 'px', n);
await browser.close();
