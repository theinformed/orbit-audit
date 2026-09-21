// Measures the Data Explorer at rest: how much of the viewport it eats, how
// many words it prints, how many controls it offers, with 1/2/3 layers on.
import { chromium } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';

const outDir = process.argv[2];
const baseURL = process.argv[3] ?? 'http://127.0.0.1:8471/';
mkdirSync(outDir, { recursive: true });

const LAYERS = [
  ['layer-geospace', 'magnetosphere'],
  ['layer-ring-current', 'ringcurrent'],
  ['layer-solar-wind', 'solarwind'],
];

async function metrics(page) {
  return page.evaluate(() => {
    const viewer = document.getElementById('data-viewer');
    if (!viewer || viewer.hidden) return null;
    const vh = window.innerHeight;
    const rect = viewer.getBoundingClientRect();
    const visible = (el) => {
      if (el.hidden) return false;
      const r = el.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) return false;
      const s = getComputedStyle(el);
      if (s.display === 'none' || s.visibility === 'hidden') return false;
      // Chromium keeps a layout box for the contents of a shut <details>, so a
      // rect test alone counted a folded settings panel's thirteen switches as
      // controls on screen. Folded is folded.
      const shut = el.closest('details:not([open])');
      return !(shut && !(el.tagName === 'SUMMARY' || el.closest('summary')));
    };
    // Words actually rendered: walk text nodes whose nearest element is laid out.
    let words = 0;
    const walker = document.createTreeWalker(viewer, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const el = n.parentElement;
      if (!el) continue;
      if (!el.offsetParent && el !== viewer) continue;
      if (el.getBoundingClientRect().height === 0) continue;
      // Chromium keeps a layout box for the contents of a shut <details>, so a
      // rect test alone counted all 906 words of the ring current's folded
      // essay as visible. Folded is folded: walk up and drop anything whose
      // own <details> is not open, but keep the <summary> that IS on screen.
      const shut = el.closest('details:not([open])');
      if (shut && !(el.tagName === 'SUMMARY' || el.closest('summary'))) continue;
      const t = n.textContent.trim();
      if (t) words += t.split(/\s+/).length;
    }
    const controls = [...viewer.querySelectorAll('input, select, textarea, button')].filter(visible);
    const factCells = [...viewer.querySelectorAll('.fact-grid > *, .ephemeris > dd')].filter(visible);
    const openSections = [...viewer.querySelectorAll('details')].filter((d) => d.open && visible(d));
    return {
      panelHeightPx: Math.round(rect.height),
      viewportHeightPx: vh,
      panelFractionOfViewport: Number((rect.height / vh).toFixed(3)),
      words,
      controls: controls.length,
      factCells: factCells.length,
      openSections: openSections.length,
      // What the reader would have to scroll through inside the panel. The
      // panel's own height is pinned by CSS, so it is the body's content
      // height that says how much material is stacked in there.
      contentHeightPx: document.getElementById('data-viewer-body').scrollHeight,
      contentOverViewport: Number((document.getElementById('data-viewer-body').scrollHeight / vh).toFixed(2)),
    };
  });
}

async function run(label, viewport, phone) {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport, deviceScaleFactor: 1 });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.addInitScript(() => {
    try {
      window.localStorage.setItem('space-explorer-hide-welcome-v1', '1');
      window.localStorage.clear();
      window.localStorage.setItem('space-explorer-hide-welcome-v1', '1');
    } catch {}
  });
  await page.goto(baseURL, { waitUntil: 'load' });
  await page.waitForTimeout(1000);
  const dlg = page.locator('#welcome-dialog');
  if (await dlg.isVisible().catch(() => false)) {
    await page.locator('#welcome-dialog .primary-button').click();
    await page.waitForTimeout(400);
  }
  const openRail = async () => {
    if (!phone) return;
    const t = page.locator('#mobile-panel-toggle');
    if (await t.isVisible().catch(() => false)) {
      const open = await page.locator('#control-rail').evaluate((el) => el.classList.contains('is-open'));
      if (!open) { await t.click(); await page.waitForTimeout(400); }
    }
  };
  const closeRail = async () => {
    if (!phone) return;
    const t = page.locator('#mobile-panel-toggle');
    if (await t.isVisible().catch(() => false)) {
      const open = await page.locator('#control-rail').evaluate((el) => el.classList.contains('is-open'));
      if (open) { await t.click(); await page.waitForTimeout(500); }
    }
  };
  await openRail();
  await page.locator('[data-explorer-mode="environment"]').click();
  await page.waitForTimeout(4000);
  // The Simple preset switches the ionosphere on; clear everything so the
  // count below is exactly the layers this run turned on.
  await page.evaluate(() => {
    document.querySelectorAll('#layer-list input[type=checkbox]').forEach((box) => {
      if (box.checked) box.click();
    });
  });
  await page.waitForTimeout(2500);

  const results = {};
  let i = 0;
  for (const [id, name] of LAYERS) {
    i += 1;
    await openRail();
    await page.locator('label:has(> #' + id + ')').click();
    await page.waitForTimeout(5000);
    await closeRail();
    // The explorer opens collapsed until a reader expands it; expand once, on
    // the first layer, and leave it expanded — that is the state complained about.
    const collapsed = await page.locator('#data-viewer').evaluate((el) => el.classList.contains('is-collapsed'));
    if (collapsed) { await page.locator('#data-viewer-head').click(); await page.waitForTimeout(800); }
    await page.waitForTimeout(2500);
    results[i + '-layer'] = await metrics(page);
    await page.screenshot({ path: outDir + '/' + label + '-' + i + 'layer-' + name + '.png' });
    console.log(label, i, 'layers:', JSON.stringify(results[i + '-layer']));
  }
  writeFileSync(outDir + '/' + label + '-metrics.json', JSON.stringify(results, null, 2));
  if (errors.length) console.log(label, 'ERRORS', errors.slice(0, 5));
  await browser.close();
}

await run('desktop', { width: 1440, height: 900 }, false);
await run('phone', { width: 390, height: 844 }, true);
