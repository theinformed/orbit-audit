// Negative control for the drift measurement.
//
// The narration test reports the picture running behind the voice. Before that is treated
// as a defect in the sync, the question has to be answered: can this machine play the clip
// at real time AT ALL, with no narration involved? Nine agents share it and the load
// average is over a hundred, and headless Chromium decodes in software.
//
// So: open the same page, press play on the video ALONE, and measure how far its clock
// advances per wall-clock second. Anything near 1.0 means the decoder is keeping up and a
// drift is the sync's fault. Well under 1.0 means the picture cannot keep time with
// anything, including itself.
import { chromium } from "@playwright/test";

// BASE=http://127.0.0.1:4183 node tools/narration-decode-rate.mjs

const base = process.env.BASE ?? "http://127.0.0.1:4183";
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.addInitScript(() => {
  try { localStorage.setItem("space-explorer-hide-welcome-v1", "1"); } catch { /* ignore */ }
});
await page.goto(base, { waitUntil: "load" });
const welcome = page.locator("#welcome-dialog .primary-button");
if (await welcome.isVisible().catch(() => false)) await welcome.click();
await page.locator('[data-view="learn-layers"]').first().click();
await page.locator('[data-layer-page="thermosphere"]').first().click();
await page.waitForSelector("video.layer-video");

const result = await page.evaluate(async () => {
  const video = document.querySelector("video.layer-video");
  video.loop = false;
  video.preload = "auto";
  video.load();
  await new Promise((resolve) => {
    if (video.readyState >= 3) return resolve();
    video.addEventListener("canplay", resolve, { once: true });
    setTimeout(resolve, 15000);
  });
  video.currentTime = 0;
  await video.play();
  const t0 = performance.now();
  const c0 = video.currentTime;
  await new Promise((resolve) => setTimeout(resolve, 4000));
  const wall = (performance.now() - t0) / 1000;
  const clock = video.currentTime - c0;
  return { wallSeconds: +wall.toFixed(3), videoSeconds: +clock.toFixed(3),
           rate: +(clock / wall).toFixed(3), dropped: video.getVideoPlaybackQuality?.() ?? null };
});
console.log(JSON.stringify(result));
await browser.close();
