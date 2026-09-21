// Screenshot harness for the observed-imagery blocks on the historical-events page.
//
// It does what a reader does: open Historical events, open a guided replay, and look
// at what is drawn under it. Every console error is collected and printed, because a
// green build has reported success on this site before without the page working.
//
// It also asserts the things a screenshot cannot: that the video and audio elements
// resolved to real bytes rather than 404s, and that the generated clip is never inside
// the same group element as an observed one.
//
// Usage: node media-shots.mjs <outDir> [baseURL]
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";

const outDir = process.argv[2];
const baseURL = process.argv[3] ?? "http://127.0.0.1:4173/";
mkdirSync(outDir, { recursive: true });

const errors = [];
const failedRequests = [];

async function press(page, selector) {
  return page.evaluate((sel) => {
    const node = document.querySelector(sel);
    if (!node) return false;
    node.click();
    return true;
  }, selector);
}

async function shoot(page, name, viewport) {
  await page.setViewportSize(viewport);
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${outDir}/${name}.png`, fullPage: false });
  console.log(`shot ${name} ${viewport.width}x${viewport.height}`);
}

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
page.on("requestfailed", (r) => failedRequests.push(`${r.url()} :: ${r.failure()?.errorText}`));
page.on("response", (r) => { if (r.status() >= 400) failedRequests.push(`${r.status()} ${r.url()}`); });

await page.goto(baseURL, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(3500);

// The welcome dialog is modal and covers the whole page. Dispatched clicks land
// underneath it, so every screenshot photographed the dialog instead of the work.
await page.evaluate(() => {
  const d = document.getElementById("welcome-dialog");
  if (d && typeof d.close === "function") d.close();
  document.querySelectorAll("dialog[open]").forEach((el) => el.close());
});
await page.waitForTimeout(600);

const openedNav = await press(page, '[data-view="events"]');
console.log("events nav clicked:", openedNav);
await page.waitForTimeout(1500);
await shoot(page, "events-index-1440", { width: 1440, height: 900 });

// The two events that had no media until 2026-08-21, and no voice until later the same day,
// are checked here for the same reason the other three are: this harness is what proves the
// bytes actually serve from the built bundle, and a clip nobody drives is a clip nobody knows
// about until a reader presses play.
for (const [id, label] of [
  ["gannon-2024", "gannon"],
  ["starlink-2022", "starlink"],
  ["quebec-1989", "quebec"],
  ["bastille-2000", "bastille"],
  ["stpatricks-2015", "stpatricks"],
]) {
  const ok = await press(page, `button[data-replay-event="${id}"]`);
  console.log(`open ${id}:`, ok);
  await page.waitForTimeout(1600);
  await page.evaluate(() => {
    const el = document.querySelector(".observed-imagery");
    if (el) el.scrollIntoView({ block: "center" });
  });
  await page.waitForTimeout(500);
  await shoot(page, `${label}-1440`, { width: 1440, height: 900 });
  await shoot(page, `${label}-390`, { width: 390, height: 844 });
  await page.setViewportSize({ width: 1440, height: 900 });

  // Structural + payload assertions
  const report = await page.evaluate(() => {
    const sec = document.querySelector(".observed-imagery");
    if (!sec) return { present: false };
    const groups = [...sec.querySelectorAll(".oi-group")];
    return {
      present: true,
      figures: sec.querySelectorAll(".oi-figure").length,
      observed: sec.querySelectorAll(".oi-observed").length,
      illustration: sec.querySelectorAll(".oi-illustration").length,
      absent: sec.querySelectorAll(".oi-absent").length,
      badges: [...sec.querySelectorAll(".layer-status")].map((b) => b.textContent.trim()),
      hasBreak: !!sec.querySelector(".oi-break"),
      // The rule: no group may contain both classes.
      mixedGroup: groups.some(
        (g) => g.querySelector(".oi-observed") && g.querySelector(".oi-illustration"),
      ),
      videos: [...sec.querySelectorAll("video")].map((v) => v.currentSrc || v.querySelector("source")?.src || ""),
      audios: [...sec.querySelectorAll("audio")].map((a) => a.getAttribute("src")),
      // A narration with no written form is a fact removed from every reader who cannot use
      // the audio, and it is invisible in a screenshot. Count them here instead.
      transcripts: [...sec.querySelectorAll(".oi-transcript p")].map(
        (el) => el.textContent.trim().slice(0, 48)),
      preloads: [...sec.querySelectorAll("video")].map((v) => v.getAttribute("preload")),
    };
  });
  console.log(`REPORT ${id}:`, JSON.stringify(report, null, 1));

  // Prove the media bytes exist rather than trusting the markup.
  for (const url of [...report.videos ?? [], ...report.audios ?? []].filter(Boolean)) {
    const res = await page.evaluate(async (u) => {
      try {
        const r = await fetch(u, { method: "GET" });
        const b = await r.blob();
        return { status: r.status, bytes: b.size, type: b.type };
      } catch (e) { return { error: String(e) }; }
    }, url);
    console.log(`  FETCH ${url.split("/").pop()} -> ${JSON.stringify(res)}`);
  }

  // Actually play the first video and confirm the decoder advanced a frame.
  const played = await page.evaluate(async () => {
    const v = document.querySelector(".observed-imagery video");
    if (!v) return "no video";
    try {
      v.muted = true;
      await v.play();
      await new Promise((r) => setTimeout(r, 1200));
      return { currentTime: v.currentTime, readyState: v.readyState, w: v.videoWidth, h: v.videoHeight };
    } catch (e) { return { error: String(e) }; }
  });
  console.log(`  PLAY ${id}:`, JSON.stringify(played));

  await press(page, "button[data-close-event]");
  await page.waitForTimeout(700);
}

console.log("\n=== console errors ===");
console.log(errors.length ? errors.join("\n") : "none");
console.log("=== failed/4xx requests ===");
console.log(failedRequests.length ? [...new Set(failedRequests)].join("\n") : "none");

await browser.close();
