import { chromium } from "@playwright/test";
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
await p.addInitScript(() => { try { localStorage.setItem("space-explorer-hide-welcome-v1","1"); } catch {} });
await p.goto("http://127.0.0.1:5401/", { waitUntil: "load" });
await p.waitForTimeout(2200);
const d = p.locator("#welcome-dialog .primary-button");
if (await d.isVisible().catch(()=>false)) { await d.click(); await p.waitForTimeout(400); }
await p.evaluate(() => document.querySelector('[data-view="learn-layers"]').click());
await p.waitForTimeout(800);
await p.evaluate(() => document.querySelector('[data-layer-page="solar-wind"]').click());
await p.waitForTimeout(900);
const r = await p.evaluate(async () => {
  const v = document.querySelector("video.layer-video");
  await v.play();
  await new Promise((res) => setTimeout(res, 2000));
  return { muted: v.muted, loop: v.loop, t: +v.currentTime.toFixed(2), dur: +v.duration.toFixed(1),
           hasAudio: v.mozHasAudio ?? (v.webkitAudioDecodedByteCount > 0) ?? null,
           decoded: v.webkitAudioDecodedByteCount ?? null, err: v.error };
});
console.log(JSON.stringify(r));
// and the other pages must still be muted+looping
await p.evaluate(() => document.querySelector("[data-layer-index]").click());
await p.waitForTimeout(500);
await p.evaluate(() => document.querySelector('[data-layer-page="radiation-belts"]').click());
await p.waitForTimeout(700);
console.log(JSON.stringify(await p.evaluate(() => {
  const v = document.querySelector("video.layer-video");
  return { page: "radiation-belts", muted: v.muted, loop: v.loop };
})));
await b.close();
