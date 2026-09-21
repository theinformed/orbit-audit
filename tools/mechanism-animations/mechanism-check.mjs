/**
 * What a screenshot cannot prove about six narrated animations.
 *
 * Drives the real built page at two widths and, for every mechanism clip:
 * fetches it and reports the true byte count, plays it and confirms the decoder
 * advanced `currentTime` with a non-zero `videoWidth`, confirms `readyState`
 * reached 4, and confirms an AUDIO track actually decoded -- Chromium exposes
 * `webkitAudioDecodedByteCount`, which stays at 0 for a silent file no matter
 * how valid the container is. Also fetches every poster, and fails on any
 * console error or any 4xx/5xx.
 *
 *   node mechanism-check.mjs <outdir> <baseurl>
 */
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const outdir = process.argv[2] || "/tmp/mech-shots";
const base = process.argv[3] || "http://127.0.0.1:4173/";
mkdirSync(outdir, { recursive: true });

const STEMS = [
  "dayside-reconnection", "chapman-layer", "hf-skip-blackout",
  "trapped-motion", "eccentric-dipole-saa", "drag-orbit-decay",
];

let bad = 0;
const browser = await chromium.launch();

for (const [label, width, height] of [["desktop", 1440, 1000], ["mobile", 390, 844]]) {
  const ctx = await browser.newContext({ viewport: { width, height } });
  const page = await ctx.newPage();
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  page.on("response", (r) => {
    if (r.status() >= 400) errors.push(`HTTP ${r.status()} ${r.url()}`);
  });

  await page.goto(base, { waitUntil: "networkidle" });
  // The welcome dialog gets photographed instead of the work if it is left up.
  for (const sel of ['dialog[open] button', '.welcome-dismiss', 'button:has-text("Start")',
                     'button:has-text("Continue")', 'button:has-text("Close")']) {
    const el = page.locator(sel).first();
    if (await el.count() && await el.isVisible().catch(() => false)) {
      await el.click().catch(() => {});
      break;
    }
  }
  await page.waitForTimeout(400);
  // The library lives in the space-weather learning track, behind that track's
  // own door -- `learn-weather` is an index of pages now, not the library
  // itself. This check used to stop at the index and time out looking for a
  // section that had moved one click further in.
  // Dispatched rather than clicked, because below 820 px the top nav is
  // display:none by design -- the phone reaches the tracks through its own two
  // doors. Whether a phone can NAVIGATE here is browser.spec.ts's question;
  // this file's question is what the six video elements do once they are on
  // screen, and it should not fail on a nav design it is not testing.
  await page.evaluate(() => document.querySelector('[data-view="learn-weather"]')?.click());
  await page.waitForTimeout(600);
  await page.evaluate(() => document.querySelector('[data-weather-page="mechanisms"]')?.click());
  await page.waitForSelector("#mechanism-library", { timeout: 20000 });
  await page.waitForTimeout(600);

  const found = await page.evaluate((stems) => {
    const out = [];
    for (const s of stems) {
      const fig = document.getElementById(`mechanism-${s}`);
      if (!fig) { out.push({ stem: s, present: false }); continue; }
      const v = fig.querySelector("video");
      out.push({
        stem: s, present: true,
        src: v?.currentSrc || v?.src || "", poster: v?.getAttribute("poster") || "",
        muted: v?.muted ?? null, loop: v?.loop ?? null,
        preload: v?.getAttribute("preload"),
        controls: v?.hasAttribute("controls"),
        transcriptLines: fig.querySelectorAll(".mechanism-transcript li").length,
        transcriptOpen: !!fig.querySelector(".mechanism-transcript[open]"),
        // The number that decides whether the burned-in type is readable. A
        // caption set at font_size N in a 1080-line frame arrives at
        // N * shownWidth / 1920 CSS px, and that -- not the render size -- is
        // the reading condition. Measured rather than assumed: the column
        // these sit in is other agents' code and has been resized twice.
        shownWidth: Math.round(v?.getBoundingClientRect().width || 0),
      });
    }
    return out;
  }, STEMS);

  for (const f of found) {
    if (!f.present) { console.log(`  MISSING FIGURE ${f.stem} (${label})`); bad++; continue; }
    if (f.muted !== false) { console.log(`  STILL MUTED ${f.stem}`); bad++; }
    if (f.loop !== false) { console.log(`  STILL LOOPS ${f.stem}`); bad++; }
    if (f.preload !== "none") { console.log(`  PRELOAD ${f.preload} ${f.stem}`); bad++; }
    if (f.transcriptLines === 0) { console.log(`  NO TRANSCRIPT ${f.stem}`); bad++; }
    if (f.transcriptOpen) { console.log(`  TRANSCRIPT OPEN BY DEFAULT ${f.stem}`); bad++; }
  }

  // What the type in the frame actually measures where a reader meets it.
  //
  // A font_size is NOT a pixel count. This used to print `n * shown / 1920`,
  // which reads font_size as if it were the height of the glyph, and so
  // understated every figure by about a third. Measured through Pango, a
  // CAPITAL at font_size n stands about n * 1.36 px tall in the 1080-line
  // master; cap height is what type is compared by, so that is what is printed.
  //
  // The caption list is one number now, on purpose. Captions used to be set at
  // 44, 36 or 32 depending on how long the sentence was, and this line named
  // all three. theme.py sets every caption at FS_CAPTION and wraps rather than
  // shrinks, so if a second number ever appears here again, something has
  // started scaling captions to fit and theme.py's band guard should have said
  // so at render time.
  const shown = found.find((x) => x.present)?.shownWidth || 0;
  const CAP_PER_PT = 1.36;                       // measured: Inter cap height
  const px = (n) => (n * CAP_PER_PT * shown / 1920).toFixed(1);
  console.log(`  ${label}: clip shown ${shown} px wide -> cap heights: `
    + `caption 34pt = ${px(34)} px, label 40pt = ${px(40)} px, `
    + `corner stamp 21pt = ${px(21)} px`);

  // byte counts for every media URL the page actually references
  for (const f of found.filter((x) => x.present)) {
    for (const [kind, url] of [["clip", f.src], ["poster", f.poster]]) {
      const r = await page.evaluate(async (u) => {
        const res = await fetch(u);
        const b = await res.arrayBuffer();
        return { status: res.status, bytes: b.byteLength, type: res.headers.get("content-type") };
      }, url);
      if (r.status !== 200 || r.bytes === 0) { console.log(`  BAD ${kind} ${f.stem} ${JSON.stringify(r)}`); bad++; }
      else console.log(`  ${label} ${f.stem} ${kind} ${r.status} ${(r.bytes / 1024).toFixed(0)} KB ${r.type}`);
    }
  }

  if (label === "desktop") {
    for (const f of found.filter((x) => x.present)) {
      const play = await page.evaluate(async (stem) => {
        const v = document.querySelector(`#mechanism-${stem} video`);
        v.preload = "auto"; v.load();
        await new Promise((res) => {
          if (v.readyState >= 3) return res();
          v.addEventListener("canplay", res, { once: true });
          setTimeout(res, 20000);
        });
        const t0 = v.currentTime;
        try { await v.play(); } catch (e) { return { error: String(e) }; }
        await new Promise((r) => setTimeout(r, 1600));
        const out = {
          duration: v.duration, readyState: v.readyState,
          advanced: +(v.currentTime - t0).toFixed(3),
          videoWidth: v.videoWidth, videoHeight: v.videoHeight,
          audioBytes: v.webkitAudioDecodedByteCount ?? null,
          videoBytes: v.webkitVideoDecodedByteCount ?? null,
        };
        v.pause();
        return out;
      }, f.stem);
      const ok = play.duration > 1 && play.readyState === 4 && play.advanced > 0.2
        && play.videoWidth > 0 && play.audioBytes > 0;
      if (!ok) bad++;
      console.log(`  ${ok ? "PLAYS" : "FAILS"} ${f.stem} dur=${play.duration?.toFixed?.(2)} `
        + `readyState=${play.readyState} advanced=${play.advanced}s ${play.videoWidth}x${play.videoHeight} `
        + `audioBytes=${play.audioBytes} videoBytes=${play.videoBytes}`
        + (play.error ? ` ERROR ${play.error}` : ""));
    }
  }

  await page.locator("#mechanism-library").scrollIntoViewIfNeeded().catch(() => {});
  await page.screenshot({ path: `${outdir}/mechanisms-${label}.png`, fullPage: false });

  if (errors.length) { bad += errors.length; console.log(`  CONSOLE/HTTP (${label}):`); errors.forEach((e) => console.log("    " + e)); }
  else console.log(`  ${label}: zero console errors, zero 4xx`);
  await ctx.close();
}

await browser.close();
console.log(bad ? `\nFAILURES: ${bad}` : "\nAll mechanism clips play with audio, all posters resolve, no console errors.");
process.exit(bad ? 1 : 0);
