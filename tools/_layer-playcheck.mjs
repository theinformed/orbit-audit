/* Does each video actually PLAY? An element that exists is not an element that works. */
import { chromium } from "@playwright/test";
const base = "http://127.0.0.1:5401/";
const ids = ["thermosphere","ionosphere","plasmasphere","radiation-belts","ring-current",
             "magnetopause","solar-wind","peak-surfaces","d-region","ground-track-footprint"];
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
await p.addInitScript(() => { try { localStorage.setItem("space-explorer-hide-welcome-v1","1"); } catch {} });
await p.goto(base, { waitUntil: "load" });
await p.waitForTimeout(2200);
const d = p.locator("#welcome-dialog .primary-button");
if (await d.isVisible().catch(()=>false)) { await d.click(); await p.waitForTimeout(400); }
await p.evaluate(() => document.querySelector('[data-view="learn-layers"]').click());
await p.waitForTimeout(800);
let bad = 0;
for (const id of ids) {
  await p.evaluate((i) => {
    const back = document.querySelector("[data-layer-index]");
    if (back) back.click();
    document.querySelector(`[data-layer-page="${i}"]`).click();
  }, id);
  await p.waitForTimeout(700);
  const r = await p.evaluate(async () => {
    const v = document.querySelector("video.layer-video");
    if (!v) return { ok: false, why: "no video element" };
    const poster = v.poster;
    try { await v.play(); } catch (e) { return { ok: false, why: "play() rejected: " + e.message }; }
    await new Promise((res) => setTimeout(res, 1400));
    return { ok: v.currentTime > 0.2 && !v.error, t: +v.currentTime.toFixed(2),
             dur: +(v.duration || 0).toFixed(1), w: v.videoWidth, h: v.videoHeight,
             poster: poster ? poster.split("/").pop() : "(none)",
             err: v.error ? v.error.code : null };
  });
  if (!r.ok) bad++;
  console.log(`${id.padEnd(17)} play=${r.ok} t=${r.t}s dur=${r.dur}s ${r.w}x${r.h} poster=${r.poster}${r.why ? " " + r.why : ""}`);
}
console.log(bad === 0 ? "ALL VIDEOS PLAY" : `${bad} FAILED`);
await b.close();
process.exit(bad === 0 ? 0 : 1);
