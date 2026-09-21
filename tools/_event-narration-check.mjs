/*
 * Measure the seam between the voice and the picture on the narrated Starlink chart.
 *
 *   BASE=http://127.0.0.1:4187 OUT=/tmp/shots W=1440 H=900 node tools/_event-narration-check.mjs
 *
 * Presses the narrated control, then samples `audio.currentTime` against what the chart is
 * actually showing -- its scrubber's hour, its raising/lost tallies, its clock readout --
 * ten times a second for the whole clip, and screenshots the frame each spoken line opens
 * on. The point is the ANCHOR CHECK at the bottom: line 05 says "watch the traces
 * separate", and the eleven raised traces must appear on the frame it opens on, not before
 * and not after.
 */
import { readFileSync } from "node:fs";
import { chromium } from "@playwright/test";

const base = process.env.BASE ?? "http://127.0.0.1:4187";
const out = process.env.OUT ?? "/tmp/narr-shots";
const width = Number(process.env.W ?? 1440);
const height = Number(process.env.H ?? 900);
const tag = process.env.TAG ?? String(width);

const manifest = JSON.parse(readFileSync(new URL("../media/event-charts/narration/bed-manifest.json", import.meta.url)));
const bed = manifest.scenes.find((scene) => scene.scene === "starlink-2022-chart");

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1,
  reducedMotion: process.env.REDUCED ? "reduce" : "no-preference" });
await page.addInitScript(() => { try { localStorage.setItem("space-explorer-hide-welcome-v1", "1"); } catch {} });
const errors = [];
page.on("pageerror", (error) => errors.push(String(error.message)));

await page.goto(base, { waitUntil: "domcontentloaded", timeout: 120000 });
await page.waitForSelector('[data-view="events"]', { state: "attached", timeout: 120000 });
// The welcome dialog opens shortly after first paint and swallows clicks.
await page.waitForTimeout(3000);
await page.evaluate(() => document.querySelectorAll("dialog[open]").forEach((d) => d.close()));
await page.waitForTimeout(300);

await page.evaluate(() => document.querySelector('[data-view="events"]').click());
await page.waitForTimeout(900);
await page.evaluate(() => document.querySelector('[data-replay-event="starlink-2022"]').click());
await page.waitForSelector("[data-narration-toggle]", { timeout: 15000 });
await page.waitForTimeout(600);

const beforePress = await page.evaluate(() => {
  const audio = document.querySelector("audio.replay-narration-audio");
  return {
    preload: audio.preload,
    networkState: audio.networkState,   // 0 EMPTY / 1 IDLE means nothing has been fetched
    readyState: audio.readyState,
    paused: audio.paused,
    chartHour: Number(document.querySelector("[data-replay-range]").value),
  };
});

await page.evaluate(() => document.querySelector(".replay-narration").scrollIntoView({ block: "center" }));
await page.waitForTimeout(400);
await page.screenshot({ path: `${out}/control-${tag}.png` });

// Record IN THE PAGE, one row per animation frame. Sampling over the protocol costs a
// round trip per sample -- on a loaded machine that is most of a second, which is larger
// than the drift being measured and would make this instrument the noise. The rows are
// pulled out once, at the end.
await page.evaluate(() => {
  const audio = document.querySelector("audio.replay-narration-audio");
  const range = document.querySelector("[data-replay-range]");
  window.__narrationTrace = [];
  const step = () => {
    if (!audio.paused) {
      window.__narrationTrace.push([audio.currentTime, Number(range.value),
        Number(document.querySelector("[data-tally-raised]").textContent),
        Number(document.querySelector("[data-tally-lost]").textContent)]);
    }
    requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
});

await page.evaluate(() => document.querySelector("[data-narration-toggle]").click());
// The beat screenshots have to show the CHART, so put the canvas on screen once the
// clip is running rather than the control that started it.
await page.evaluate(() => document.querySelector(".replay-canvas-wrap").scrollIntoView({ block: "start" }));

const samples = [];
const shot = new Map();
const started = Date.now();
while (Date.now() - started < 90000) {
  const now = await page.evaluate(() => {
    const audio = document.querySelector("audio.replay-narration-audio");
    return {
      t: audio.currentTime,
      paused: audio.paused,
      ended: audio.ended,
      ready: audio.readyState,
      hour: Number(document.querySelector("[data-replay-range]").value),
      raised: document.querySelector("[data-tally-raised]").textContent,
      lost: document.querySelector("[data-tally-lost]").textContent,
      clock: document.querySelector("[data-replay-clock]").textContent.trim(),
      caption: document.querySelector("[data-caption-body]").textContent.slice(0, 46),
      step: document.querySelector("[data-caption-count]").textContent,
    };
  });
  if (!now.paused || now.t > 0) samples.push({ wall: (Date.now() - started) / 1000, ...now });
  for (const [index, line] of bed.lines.entries()) {
    if (!shot.has(index) && now.t >= line.startSeconds && !now.paused) {
      shot.set(index, { t: now.t, hour: now.hour, raised: now.raised, lost: now.lost, clock: now.clock });
      await page.screenshot({ path: `${out}/line0${index + 1}-${tag}.png` });
    }
  }
  if (now.ended || (now.paused && now.t >= bed.bedSeconds - 0.5)) break;
  if (now.paused && samples.length > 12 && now.t === 0) break;
  await page.waitForTimeout(100);
}

await page.screenshot({ path: `${out}/final-${tag}.png` });
const trace = await page.evaluate(() => window.__narrationTrace);
const transcript = await page.evaluate(() => [...document.querySelectorAll(".replay-narration-transcript li")]
  .map((li) => li.textContent.trim()));

// --- scrub, with the voice running -----------------------------------------
const scrub = await page.evaluate(async () => {
  const audio = document.querySelector("audio.replay-narration-audio");
  audio.currentTime = 20;
  await audio.play();
  await new Promise((r) => setTimeout(r, 700));
  const range = document.querySelector("[data-replay-range]");
  const during = { t: audio.currentTime, paused: audio.paused, hour: Number(range.value) };
  range.value = "500";
  range.dispatchEvent(new Event("input", { bubbles: true }));
  await new Promise((r) => setTimeout(r, 400));
  return {
    during,
    after: { t: audio.currentTime, paused: audio.paused, hour: Number(range.value),
             caption: document.querySelector("[data-caption-body]").textContent.slice(0, 46) },
  };
});

// --- the silent replay must be exactly what it always was -------------------
const silent = await page.evaluate(async () => {
  const audio = document.querySelector("audio.replay-narration-audio");
  const range = document.querySelector("[data-replay-range]");
  range.value = "0";
  range.dispatchEvent(new Event("input", { bubbles: true }));
  const play = document.querySelector("[data-replay-play]");
  play.click();
  await new Promise((r) => setTimeout(r, 2500));
  const moved = Number(range.value);
  play.click();
  return { moved, label: play.textContent, audioPaused: audio.paused };
});

console.log(JSON.stringify({
  tag, base, errors,
  bedSeconds: bed.bedSeconds,
  beforePress,
  beats: bed.lines.map((line, index) => ({
    line: line.id,
    voiceAt: line.startSeconds,
    seen: shot.get(index) ?? null,
  })),
  scrub, silent,
  samples,
  transcript,
  trace,
}, null, 1));

await browser.close();
