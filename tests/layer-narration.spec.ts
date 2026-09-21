/**
 * The narration control, in a real browser.
 *
 * The unit tests prove the words fit and the audio was built where the marks say. Only a
 * browser can prove the three things a reader would actually notice:
 *
 *   - Nothing makes a sound on its own. Audio that starts on page load is the most hostile
 *     thing a website can do, and it is a one-line mistake away at all times.
 *   - The control works from the keyboard, and says what it is to a screen reader.
 *   - THE VOICE STAYS WITH THE PICTURE. That is Sean's acceptance criterion, not a nicety,
 *     and it is measured here by sampling both clocks while they run rather than by
 *     watching it and forming an impression.
 */

import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

// Read rather than imported: Playwright's loader wants an import attribute for JSON,
// and this file has to agree with what the AUDIO was built from, not with a copy the
// bundler happened to inline.
const bedManifest = JSON.parse(readFileSync(
  fileURLToPath(new URL("../media/narration-layers/manifest.json", import.meta.url)),
  "utf8",
)) as { clips: Array<{ clip: string; lines: Array<{ text: string }> }> };

/**
 * Wait for the voice to actually start.
 *
 * Pressing the button does not start playback immediately, and that is deliberate: nothing
 * is preloaded, so the first press has to fetch the bed, and the module waits for BOTH
 * elements to report they can play before starting either clock. Starting the picture while
 * the voice was still arriving is precisely what put the two nearly a second apart the first
 * time this was measured. So the test waits for the event rather than for a stopwatch.
 */
const untilSpeaking = async (page: import("@playwright/test").Page) => {
  await page.waitForFunction(() => {
    const audio = document.querySelector<HTMLAudioElement>("audio.narration-audio");
    return Boolean(audio) && !audio!.paused && audio!.currentTime > 0;
  }, undefined, { timeout: 30000 });
};

/**
 * Back to the layers index — by pressing the button, at every width.
 *
 * This used to fork: on a phone it reached past the pointer and called .click() in page
 * script, because the shell's own "← Back to explorer" button was `position: sticky` at the
 * top-left of the content view and came to rest ON TOP OF this page's "← All layers" button.
 * Playwright said so in as many words (`#content-close intercepts pointer events`), and it
 * was never a test artefact — a reader at the top of a layer page on a 390px screen could
 * not tap "All layers" either.
 *
 * That overlap is fixed at its cause (`.content-close` in src/styles.css: the shell draws no
 * second back button over the page any more), so the workaround comes out and this presses
 * the real button through the real pointer at every width. If the overlap ever returns, this
 * is the line that fails — which is the point of removing the route around it.
 */
const backToIndex = async (page: import("@playwright/test").Page) => {
  await page.locator("[data-layer-index]").first().click();
};

const openThermosphere = async (page: import("@playwright/test").Page) => {
  await page.addInitScript(() => {
    try {
      localStorage.setItem("space-explorer-hide-welcome-v1", "1");
    } catch {
      /* a private window is not a reason to fail the test */
    }
  });
  await page.goto("/", { waitUntil: "load" });

  // The welcome dialog is drawn AFTER load, and on a machine with nine agents on it that
  // can be several seconds later. Asking `isVisible()` the instant the page loads answers
  // "no" and moves on, and then the dialog opens over the nav and swallows the click that
  // follows — which reads as the layers index never rendering, which it did. A bounded
  // click waits for it to become clickable, dismisses it, and shrugs if it never comes.
  await page.locator("#welcome-dialog .primary-button").click({ timeout: 15000 })
    .catch(() => { /* the dialog is suppressed by localStorage; nothing to dismiss */ });

  // THE LAYERS INDEX IS NO LONGER A TOP-NAV DESTINATION. Sean, 2026-08-21: "I just worry
  // the top rail is getting too crowded." The door moved into Learn space weather's contents
  // spine, so the way in on a desktop is now two steps, and this test takes the reader's
  // route rather than the router's — if that door ever stops working, this is what says so.
  //
  // BELOW 820px THERE IS NO TOP NAV AT ALL — the phone gets two full-width doors into the
  // control sheet instead, and the nav items still exist in the document but are
  // `display: none`. A real click on one therefore waits for an element that will never
  // become actionable and burns the whole test timeout, so the FIRST step goes through the
  // router, the same guarded shape browser.spec.ts already uses for the explorer, events and
  // lessons views.
  //
  // The SECOND step is a real tap either way. The layers door is in the content body, not in
  // the hidden nav, so a phone reader really does press it — and it is the only way to the
  // layer pages on a phone now, which makes it worth pressing rather than routing past.
  // (An earlier version of this branch clicked `[data-view="learn-layers"]` at the top level.
  // That selector matched the top-nav button, which no longer exists, so `querySelector`
  // returned null and the step silently did nothing — seven mobile tests failed on a page
  // that had never been opened. A router shortcut that resolves to nothing fails silently;
  // this one asserts the door is there before it presses it.)
  if (await page.locator("#mobile-panel-toggle").isVisible()) {
    await page.evaluate(() =>
      document.querySelector<HTMLButtonElement>('[data-view="learn-weather"]')?.click());
    await expect(page.locator('#weather-layers [data-view="learn-layers"]').first()).toBeVisible();
    await page.locator('#weather-layers [data-view="learn-layers"]').first().click();
  } else {
    await page.locator('[data-view="learn-weather"]').first().click();
    await expect(page.locator('#weather-index [data-view="learn-layers"]').first()).toBeVisible();
    await page.locator('#weather-index [data-view="learn-layers"]').first().click();
  }
  // Assert the index arrived before clicking into it, so a failure says which of the two
  // steps went wrong instead of timing out on the second.
  await expect(page.locator('[data-layer-page="thermosphere"]').first()).toBeVisible();
  await page.locator('[data-layer-page="thermosphere"]').first().click();
  await expect(page.locator(".layer-narration")).toBeVisible();
};

test.describe("spoken narration on a layer page", () => {
  test("makes no sound until the reader asks for it", async ({ page }) => {
    await openThermosphere(page);
    const state = await page.evaluate(() => {
      const audio = document.querySelector<HTMLAudioElement>("audio.narration-audio");
      const video = document.querySelector<HTMLVideoElement>("video.layer-video");
      return {
        audioPresent: Boolean(audio),
        audioPaused: audio?.paused ?? null,
        preload: audio?.getAttribute("preload") ?? null,
        autoplay: audio?.hasAttribute("autoplay") ?? null,
        // With preload="none" the browser has fetched nothing, so it does not yet know
        // how long the file is. That NaN is the proof that no bytes were downloaded.
        durationKnown: Number.isFinite(audio?.duration ?? NaN),
        videoPaused: video?.paused ?? null,
        pressed: document.querySelector("[data-narration-toggle]")?.getAttribute("aria-pressed"),
      };
    });
    expect(state.audioPresent).toBe(true);
    expect(state.audioPaused).toBe(true);
    expect(state.autoplay).toBe(false);
    expect(state.preload).toBe("none");
    expect(state.durationKnown).toBe(false);
    expect(state.videoPaused).toBe(true);
    expect(state.pressed).toBe("false");
  });

  test("is reachable and operable from the keyboard alone", async ({ page }) => {
    await openThermosphere(page);
    const toggle = page.locator("[data-narration-toggle]");
    await toggle.focus();
    await expect(toggle).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(toggle).toHaveAttribute("aria-pressed", "true");
    // The reader is told what is happening while the bed is fetched, rather than being left
    // looking at a control that appears pressed and silent.
    await expect(page.locator(".narration-state")).not.toBeEmpty();
    await untilSpeaking(page);
    const playing = await page.evaluate(() => {
      const audio = document.querySelector<HTMLAudioElement>("audio.narration-audio");
      return { paused: audio?.paused, t: audio?.currentTime ?? 0 };
    });
    expect(playing.paused).toBe(false);
    expect(playing.t).toBeGreaterThan(0);
    // And off again, from the keyboard, without ever touching a mouse.
    await page.keyboard.press("Enter");
    await expect(toggle).toHaveAttribute("aria-pressed", "false");
    expect(await page.evaluate(() =>
      document.querySelector<HTMLAudioElement>("audio.narration-audio")?.paused)).toBe(true);
  });

  test("says what it is, out loud, to a screen reader", async ({ page }) => {
    await openThermosphere(page);
    const labelled = await page.evaluate(() => {
      const audio = document.querySelector<HTMLAudioElement>("audio.narration-audio");
      const state = document.querySelector(".narration-state");
      return {
        audioLabel: audio?.getAttribute("aria-label") ?? "",
        live: state?.getAttribute("aria-live"),
        role: state?.getAttribute("role"),
        summary: document.querySelector(".narration-transcript summary")?.textContent ?? "",
      };
    });
    expect(labelled.audioLabel).toContain("narration");
    expect(labelled.live).toBe("polite");
    expect(labelled.role).toBe("status");
    expect(labelled.summary.toLowerCase()).toContain("transcript");
  });

  test("writes down every word it speaks", async ({ page }) => {
    await openThermosphere(page);
    const written = await page.evaluate(() =>
      [...document.querySelectorAll(".narration-transcript li")].map((li) => li.textContent ?? ""));

    // Compared against the manifest the AUDIO was built from, not against phrases typed
    // into this test. The narration is rewritten whenever the words are improved, and a
    // test pinned to a phrase would then fail for saying something true. What must never
    // change is that the printed words are the rendered words.
    const spoken = bedManifest.clips.find((clip) => clip.clip === "thermosphere")!.lines;
    expect(written.length).toBe(spoken.length);
    spoken.forEach((line, i) => {
      expect(written[i]).toContain(line.text);
    });

    // The cue is the second the line is spoken at. Without it a transcript is just the
    // prose again, and a reader cannot follow the picture with it.
    expect(await page.locator(".narration-cue").first().textContent()).toMatch(/^\d+:\d\d$/);
  });

  test("keeps the voice with the picture, measured on both clocks while they run", async ({ page }) => {
    await openThermosphere(page);
    await page.locator("[data-narration-toggle]").click();
    await untilSpeaking(page);
    // The picture is NUDGED onto the voice rather than seeked, so it closes the start-up
    // gap over a second or so instead of snapping. Sampling during that approach measures
    // the start-up offset, not the thing this test is about, which is whether the two stay
    // together. The approach itself is still printed below.
    await page.waitForTimeout(2500);

    const samples = await page.evaluate(async () => {
      const audio = document.querySelector<HTMLAudioElement>("audio.narration-audio")!;
      const video = document.querySelector<HTMLVideoElement>("video.layer-video")!;
      const out: Array<{ video: number; audio: number; drift: number }> = [];
      for (let i = 0; i < 8; i += 1) {
        await new Promise((resolve) => setTimeout(resolve, 400));
        out.push({
          video: +video.currentTime.toFixed(3),
          audio: +audio.currentTime.toFixed(3),
          // The voice is the clock; the picture follows it. A positive number means the
          // picture is ahead of the words.
          drift: +(video.currentTime - audio.currentTime).toFixed(3),
        });
      }
      return out;
    });

    // Printed so the number is in the run log, not only in an assertion. Sean asked for
    // the measurement, so the measurement is reported whether or not it passes.
    console.log("narration drift samples (picture - voice, seconds):",
      JSON.stringify(samples.map((s) => s.drift)));

    expect(samples.some((s) => s.video > 0.5)).toBe(true);
    for (const sample of samples) {
      expect(Math.abs(sample.drift)).toBeLessThanOrEqual(0.35);
    }
  });

  test("stops the loop while it talks, and puts it back afterwards", async ({ page }) => {
    await openThermosphere(page);
    // Every layer clip but the coronagraph is a silent ambient loop. A voice burnt over a
    // loop repeats its first sentence forever, so narration turns the loop off - and turning
    // narration off has to leave the page exactly as it was found.
    expect(await page.evaluate(() =>
      document.querySelector<HTMLVideoElement>("video.layer-video")?.loop)).toBe(true);
    await page.locator("[data-narration-toggle]").click();
    await untilSpeaking(page);
    expect(await page.evaluate(() =>
      document.querySelector<HTMLVideoElement>("video.layer-video")?.loop)).toBe(false);
    await page.locator("[data-narration-toggle]").click();
    expect(await page.evaluate(() =>
      document.querySelector<HTMLVideoElement>("video.layer-video")?.loop)).toBe(true);
  });

  test("goes quiet when the reader leaves the page", async ({ page }) => {
    await openThermosphere(page);
    await page.locator("[data-narration-toggle]").click();
    await untilSpeaking(page);
    expect(await page.evaluate(() =>
      document.querySelector<HTMLAudioElement>("audio.narration-audio")?.paused)).toBe(false);
    await backToIndex(page);
    await page.waitForTimeout(300);
    const stillTalking = await page.evaluate(() =>
      [...document.querySelectorAll<HTMLAudioElement>("audio.narration-audio")]
        .some((audio) => !audio.paused));
    expect(stillTalking).toBe(false);
  });

  test("a clip with no recorded narration shows no control at all", async ({ page }) => {
    await openThermosphere(page);
    await backToIndex(page);
    await page.locator('[data-layer-page="ring-current"]').first().click();
    // The slot is rendered by the layer pages and left hidden. A page whose audio has not
    // been recorded must show nothing rather than a control that does nothing.
    const slot = page.locator('.layer-narration[data-narration-for="ring-current"]');
    await expect(slot).toBeHidden();
    expect(await slot.locator("audio").count()).toBe(0);
  });
});

test.describe("the narration control on a phone", () => {
  test("fits the one-column layout and keeps both doors", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "mobile", "phone layout only");
    await openThermosphere(page);
    const fits = await page.evaluate(() => {
      const slot = document.querySelector<HTMLElement>(".layer-narration")!;
      const rect = slot.getBoundingClientRect();
      return {
        withinViewport: rect.right <= window.innerWidth + 1,
        bodyScrollsSideways: document.documentElement.scrollWidth > window.innerWidth + 1,
        buttonHeight: document.querySelector<HTMLElement>("[data-narration-toggle]")!
          .getBoundingClientRect().height,
      };
    });
    expect(fits.withinViewport).toBe(true);
    expect(fits.bodyScrollsSideways).toBe(false);
    // A control smaller than this is not reliably hittable with a thumb.
    expect(fits.buttonHeight).toBeGreaterThanOrEqual(36);
  });
});
