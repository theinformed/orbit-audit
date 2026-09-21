import { chromium } from '@playwright/test';
const baseURL = process.argv[2]; const dir = process.argv[3]; const tag = process.argv[4];
for (const [label, vp] of [['1440', { width: 1440, height: 900 }], ['390', { width: 390, height: 844 }]]) {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: vp, deviceScaleFactor: 1 });
  await page.addInitScript(() => { try { window.localStorage.clear(); window.localStorage.setItem('space-explorer-hide-welcome-v1','1'); } catch {} });
  await page.goto(baseURL, { waitUntil: 'load' });
  await page.waitForTimeout(1500);
  const dlg = page.locator('#welcome-dialog');
  if (await dlg.isVisible().catch(()=>false)) { await page.locator('#welcome-dialog .primary-button').click(); await page.waitForTimeout(400); }
  if (label === '390') { const t = page.locator('#mobile-panel-toggle'); if (await t.isVisible().catch(()=>false)) { await t.click(); await page.waitForTimeout(500); } }
  await page.locator('#satellite-search').fill('PRAETORIAN');
  await page.waitForTimeout(1500);
  const first = page.locator('#search-results .search-result').first();
  if (await first.isVisible().catch(()=>false)) { await first.click(); await page.waitForTimeout(4500); }
  if (label === '390') { for (let i = 0; i < 3; i += 1) { const open = await page.locator('#control-rail').evaluate((el)=>el.classList.contains('is-open')); if (!open) break; await page.locator('#mobile-panel-toggle').click(); await page.waitForTimeout(700); } }
  await page.waitForTimeout(1500);
  await page.screenshot({ path: dir + '/' + tag + '-sat-' + label + '.png' });
  const m = await page.evaluate(() => {
    const c = document.querySelector('.sat-card[data-sat-card]') || document.querySelector('#satellite-stack .sat-card');
    if (!c) return null;
    const shut = (el) => { const d = el.closest('details:not([open])'); return d && !(el.tagName==='SUMMARY'||el.closest('summary')); };
    let words = 0; const w = document.createTreeWalker(c, NodeFilter.SHOW_TEXT);
    for (let n=w.nextNode(); n; n=w.nextNode()) { const p=n.parentElement; if(!p||!p.offsetParent) continue; if(p.getBoundingClientRect().height===0) continue; if(shut(p)) continue; const t=n.textContent.trim(); if(t) words+=t.split(/\s+/).length; }
    const ctrl = [...c.querySelectorAll('input,select,textarea,button')].filter((e)=>!e.hidden && e.getBoundingClientRect().height>0 && !shut(e));
    return { heightPx: Math.round(c.getBoundingClientRect().height), viewport: window.innerHeight, words, controls: ctrl.length,
      sections: [...c.querySelectorAll('[data-card-section]')].filter((s)=>!s.hidden).map((s)=>s.dataset.cardSection+(s.open?':OPEN':':shut')) };
  });
  console.log(tag, label, JSON.stringify(m));
  await browser.close();
}
