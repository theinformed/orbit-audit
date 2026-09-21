// Measures the computed type of every text role in the two data cards, so the
// steps between roles can be read as numbers instead of guessed at.
import { chromium } from '@playwright/test';
const baseURL = process.argv[2];
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
await page.addInitScript(() => { try { window.localStorage.clear(); window.localStorage.setItem('space-explorer-hide-welcome-v1','1'); } catch {} });
await page.goto(baseURL, { waitUntil: 'load' });
await page.waitForTimeout(1500);
const dlg = page.locator('#welcome-dialog');
if (await dlg.isVisible().catch(()=>false)) { await page.locator('#welcome-dialog .primary-button').click(); await page.waitForTimeout(400); }

// A layer card.
await page.locator('[data-explorer-mode="environment"]').click();
await page.waitForTimeout(3500);
await page.evaluate(() => { document.querySelectorAll('#layer-list input[type=checkbox]').forEach((b)=>{ if (b.checked) b.click(); }); });
await page.evaluate(() => document.getElementById('layer-ring-current').click());
await page.waitForTimeout(6500);
if (await page.locator('#data-viewer').evaluate((el)=>el.classList.contains('is-collapsed'))) await page.locator('#data-viewer-head').click();
await page.waitForTimeout(1000);

// A satellite card.
await page.locator('[data-explorer-mode="satellites"]').click();
await page.waitForTimeout(2000);
await page.locator('#satellite-search').fill('PRAETORIAN');
await page.waitForTimeout(1500);
const first = page.locator('#search-results .search-result').first();
if (await first.isVisible().catch(()=>false)) { await first.click(); await page.waitForTimeout(4000); }

const rows = await page.evaluate(() => {
  const probe = (root, name, sel) => {
    const el = root && root.querySelector(sel);
    if (!el) return { role: name, missing: true };
    const s = getComputedStyle(el);
    return {
      role: name,
      px: Number.parseFloat(s.fontSize).toFixed(2),
      weight: s.fontWeight,
      family: s.fontFamily.split(',')[0].replace(/"/g, ''),
      color: s.color,
      tracking: s.letterSpacing,
      transform: s.textTransform,
      sample: (el.textContent || '').trim().slice(0, 34),
    };
  };
  const layer = document.querySelector('#data-viewer-cards [data-layer-card]');
  const sat = document.querySelector('#satellite-stack .sat-card') || document.querySelector('.sat-card:not([data-layer-card])');
  const out = { layer: [], satellite: [] };
  out.layer.push(probe(layer, 'card name', '[data-card-name]'));
  out.layer.push(probe(layer, 'evidence badge', '[data-card-mission]'));
  out.layer.push(probe(layer, 'lead prose', '[data-card-purpose]'));
  out.layer.push(probe(layer, 'section summary', '.card-section > summary'));
  out.layer.push(probe(layer, 'nested summary', '.purpose-more > summary'));
  out.layer.push(probe(layer, 'fact label', '.fact-grid span'));
  out.layer.push(probe(layer, 'fact value', '.fact-grid strong'));
  out.layer.push(probe(layer, 'ephemeris dt', '.ephemeris dt'));
  out.layer.push(probe(layer, 'ephemeris dd', '.ephemeris dd'));
  out.layer.push(probe(layer, 'link button', '.link-button'));
  out.satellite.push(probe(sat, 'card name', '.sat-card-toggle strong'));
  out.satellite.push(probe(sat, 'mission badge', '.sat-card-mission'));
  out.satellite.push(probe(sat, 'lead prose', '.satellite-purpose'));
  out.satellite.push(probe(sat, 'section summary', '.card-section > summary'));
  out.satellite.push(probe(sat, 'nested summary', '.geometry-explainer > summary'));
  out.satellite.push(probe(sat, 'fact label', '.fact-grid span'));
  out.satellite.push(probe(sat, 'fact value', '.fact-grid strong'));
  out.satellite.push(probe(sat, 'ephemeris dt', '.ephemeris dt'));
  out.satellite.push(probe(sat, 'ephemeris dd', '.ephemeris dd'));
  out.satellite.push(probe(sat, 'link button', '.link-button'));
  out.satellite.push(probe(sat, 'field label', '.field-label'));
  out.satOrder = sat ? [...sat.querySelectorAll('.sat-card-body > *')].map((n)=> n.tagName.toLowerCase() + '.' + (n.className||'').split(' ')[0] + (n.dataset.cardSection ? '[' + n.dataset.cardSection + ']' : '')) : [];
  return out;
});
for (const k of ['layer','satellite']) {
  console.log('==== ' + k.toUpperCase() + ' CARD ====');
  for (const r of rows[k]) console.log(r.missing ? ('  MISSING ' + r.role) : ('  ' + r.role.padEnd(17) + r.px.padStart(6) + 'px  w' + r.weight + '  ' + r.family.padEnd(15) + r.color.padEnd(22) + ' ls=' + r.tracking.padEnd(8) + r.transform.padEnd(10) + ' | ' + r.sample));
}
console.log('SAT BODY ORDER:', JSON.stringify(rows.satOrder, null, 1));
await browser.close();
