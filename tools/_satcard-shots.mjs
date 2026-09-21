// Screenshots + measurements for the selected-satellites viewer.
// Usage: node tools/_satcard-shots.mjs <outDir> <port> <tag>
import { chromium } from "@playwright/test";
const out = process.argv[2] ?? "/tmp/satcard/shots";
const port = process.argv[3] ?? "5402";
const tag = process.argv[4] ?? "after";
const base = `http://127.0.0.1:${port}/`;

const SATS = [
  { id: "37849", key: "documented" },      // curated description, corroborated basis
  { id: "38352", key: "assessed" },        // assessed basis, named analysts
  { id: "41787", key: "lowconf" },         // classificationConfidence: low
  { id: "58645", key: "unknown-tianmu" },  // the card Sean named
  { id: "23712", key: "unknown-usa115" },  // one of the 1,843 with no payload named
];

const b = await chromium.launch();

async function open(page) {
  const errs = [];
  page.on("console", (m) => { if (m.type() === "error") errs.push(m.text()); });
  page.on("pageerror", (e) => errs.push("PAGEERROR " + e.message));
  await page.addInitScript(() => { try { localStorage.setItem("space-explorer-hide-welcome-v1", "1"); } catch {} });
  await page.goto(base, { waitUntil: "load" });
  await page.waitForTimeout(3500);
  const d = page.locator("#welcome-dialog .primary-button");
  if (await d.isVisible().catch(() => false)) { await d.click(); await page.waitForTimeout(500); }
  return errs;
}

async function pick(page, id) {
  await page.evaluate((v) => {
    const el = document.querySelector("#satellite-search");
    el.value = v;
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }, id);
  await page.waitForTimeout(800);
  const ok = await page.evaluate(() => {
    const row = document.querySelector("#search-results .search-result");
    if (!row) return false;
    row.click();
    return true;
  });
  await page.waitForTimeout(1200);
  if (!ok) console.log(`!! no search result for ${id}`);
}

async function clear(page) {
  await page.evaluate(() => document.querySelector("#satellite-stack-clear")?.click());
  await page.waitForTimeout(600);
}

async function expandAll(page) {
  await page.evaluate(() => {
    document.querySelectorAll("[data-sat-card].is-collapsed [data-card-toggle]").forEach((t) => t.click());
    // Open every fold so the measurement covers the words the card can show.
    document.querySelectorAll("[data-sat-card] details").forEach((d) => { d.open = true; });
  });
  await page.waitForTimeout(900);
}

async function cardMetrics(page) {
  return page.evaluate(() => [...document.querySelectorAll("[data-sat-card]")].map((c) => {
    const t = (c.innerText || "").trim();
    return {
      name: (c.querySelector("[data-card-name]")?.textContent || "").trim(),
      words: t.split(/\s+/).filter(Boolean).length,
      chars: t.length,
      height: Math.round(c.scrollHeight),
    };
  }));
}

// ---- Phase A: one satellite at a time, both widths ----
{
  const page = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  const errs = await open(page);
  for (const s of SATS) {
    await clear(page);
    await pick(page, s.id);
    for (const w of [1440, 390]) {
      await page.setViewportSize({ width: w, height: w === 1440 ? 1400 : 1200 });
      await page.waitForTimeout(700);
      // Folds shut (the shipped default) and folds open, measured separately.
      const shut = await cardMetrics(page);
      await page.locator("#satellite-stack").screenshot({ path: `${out}/${tag}-${s.key}-${w}-shut.png` }).catch(() => {});
      await expandAll(page);
      const openM = await cardMetrics(page);
      await page.locator("#satellite-stack").screenshot({ path: `${out}/${tag}-${s.key}-${w}-open.png` }).catch(() => {});
      console.log(`CARD ${tag} ${s.key} ${w} shut=${JSON.stringify(shut)} open=${JSON.stringify(openM)}`);
    }
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.waitForTimeout(300);
  }
  console.log(`errors=${errs.length}`, errs.slice(0, 6).join(" | "));
  await page.close();
}

// ---- Phase B: all five in the stack, chevron alignment + control bar ----
{
  const page = await b.newPage({ viewport: { width: 1440, height: 1200 }, deviceScaleFactor: 1 });
  await open(page);
  for (const s of SATS) await pick(page, s.id);
  await page.waitForTimeout(1200);
  for (const w of [1440, 390]) {
    await page.setViewportSize({ width: w, height: w === 1440 ? 1200 : 1000 });
    await page.waitForTimeout(900);
    const m = await page.evaluate(() => {
      const cards = [...document.querySelectorAll("[data-sat-card]")];
      const bar = document.querySelector(".stack-controls");
      const btns = bar ? [...bar.querySelectorAll("button")] : [];
      const gaps = [];
      for (let i = 1; i < btns.length; i++) gaps.push(Math.round(btns[i].getBoundingClientRect().left - btns[i - 1].getBoundingClientRect().right));
      const chev = cards.map((c) => {
        const e = c.querySelector(".sat-card-chevron");
        if (!e) return null;
        return Math.round((e.getBoundingClientRect().left - c.getBoundingClientRect().left) * 100) / 100;
      });
      const star = cards.map((c) => {
        const e = c.querySelector("[data-card-favorite]");
        if (!e) return null;
        return Math.round((e.getBoundingClientRect().left - c.getBoundingClientRect().left) * 100) / 100;
      });
      return {
        heading: (document.querySelector("#satellite-stack-count")?.textContent || "").trim(),
        headTextAll: (document.querySelector(".stack-head")?.innerText || "").trim(),
        chevronLefts: chev,
        starLefts: star,
        barLabels: btns.map((x) => x.innerText.trim()),
        barGaps: gaps,
        barTops: btns.map((x) => Math.round(x.getBoundingClientRect().top * 10) / 10),
        barClipped: btns.map((x) => x.scrollWidth - x.clientWidth),
        stackWidth: Math.round(document.querySelector("#satellite-stack").getBoundingClientRect().width),
      };
    });
    console.log(`STACK ${tag} ${w} ${JSON.stringify(m)}`);
    await page.locator("#satellite-stack").screenshot({ path: `${out}/${tag}-stack-${w}.png` }).catch(() => {});
    await page.screenshot({ path: `${out}/${tag}-full-${w}.png` });
  }
  await page.close();
}

// ---- Phase C: control-bar wrap sweep, at every interface scale ----
{
  const page = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  await open(page);
  await pick(page, "37849");
  console.log(`== ${tag} WRAP SWEEP ==`);
  for (const scale of ["standard", "large", "largest"]) {
    await page.evaluate((v) => {
      document.querySelector(`[data-interface-scale="${v}"]`)?.click();
      document.documentElement.dataset.interfaceScale = v;
    }, scale);
    for (const w of [1600, 1440, 1280, 1024, 900, 820, 768, 700, 640, 560, 480, 430, 414, 400, 390, 375, 360, 340, 320]) {
      await page.setViewportSize({ width: w, height: 844 });
      await page.waitForTimeout(320);
      const r = await page.evaluate(() => {
        const bar = document.querySelector(".stack-controls");
        if (!bar) return null;
        const btns = [...bar.querySelectorAll("button")];
        const rects = btns.map((x) => x.getBoundingClientRect());
        const centres = rects.map((r) => r.top + r.height / 2);
        const spread = Math.max(...centres) - Math.min(...centres);
        const gaps = [];
        for (let i = 1; i < btns.length; i++) gaps.push(Math.round((rects[i].left - rects[i - 1].right) * 100) / 100);
        // A label wider than the box it sits in is the clipping this design
        // trades wrapping for; it must never be true of the shown label.
        const clipped = btns.map((x) => {
          const shown = [...x.querySelectorAll("span")].find((s) => getComputedStyle(s).display !== "none");
          if (!shown) return 0;
          const style = getComputedStyle(x);
          const pad = parseFloat(style.paddingLeft) + parseFloat(style.paddingRight);
          return Math.round((shown.getBoundingClientRect().width + pad - x.getBoundingClientRect().width) * 100) / 100;
        });
        return {
          oneLine: spread < 1.5,
          gaps,
          maxClip: Math.max(...clipped),
          labels: btns.map((x) => x.innerText.trim()),
          barWidth: Math.round(bar.getBoundingClientRect().width),
        };
      });
      console.log(JSON.stringify({ scale, w, ...r }));
    }
  }
  await page.close();
}
await b.close();
