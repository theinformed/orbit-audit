import { chromium } from '@playwright/test';
import { writeFileSync } from 'node:fs';
const baseURL = process.argv[2] ?? 'http://127.0.0.1:8471/';
const out = process.argv[3];
const LAYERS = ['layer-thermosphere','layer-ionosphere','layer-tec','layer-aurora','layer-geospace','layer-ring-current','layer-solar-wind','layer-photons','layer-radiation','layer-ground-stations','layer-drap','layer-groundField'];
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
const report = {};
for (const id of LAYERS) {
  const box = page.locator('#' + id);
  if (!(await box.count())) continue;
  await page.evaluate((i) => document.getElementById(i).click(), id);
  await page.waitForTimeout(6000);
  const d = await page.evaluate(() => {
    const card = document.querySelector('#data-viewer-cards [data-layer-card]');
    if (!card) return null;
    const g = (sel) => [...card.querySelectorAll(sel)].map((n)=>n.textContent.trim());
    const readings = [...card.querySelectorAll('[data-card-readings] > *')].map((n)=>{
      const l = n.querySelector('dt, .fact-label, strong');
      return n.textContent.trim();
    });
    const controls = [...card.querySelectorAll('[data-card-controls-slot] input, [data-card-controls-slot] select, [data-card-controls-slot] button')].map((n)=>(n.id||n.name||n.textContent.trim()||n.type));
    const purpose = card.querySelector('[data-card-purpose]').textContent.trim();
    const rest = card.querySelector('[data-card-purpose-rest]').textContent.trim();
    return {
      layer: card.dataset.layer,
      name: card.querySelector('[data-card-name]').textContent.trim(),
      badge: card.querySelector('[data-card-mission]').textContent.trim(),
      leadWords: purpose.split(/\s+/).filter(Boolean).length,
      restWords: rest.split(/\s+/).filter(Boolean).length,
      readingCount: readings.length,
      readings,
      controlCount: controls.length,
      controls,
    };
  });
  report[id] = d;
  console.log(id, d ? d.layer + ' readings=' + d.readingCount + ' controls=' + d.controlCount + ' lead=' + d.leadWords + 'w rest=' + d.restWords + 'w' : 'NO CARD');
  await page.evaluate((i) => document.getElementById(i).click(), id);
  await page.waitForTimeout(2500);
}
writeFileSync(out, JSON.stringify(report, null, 2));
await browser.close();
