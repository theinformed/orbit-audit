/**
 * Spoken narration on the layer pages: how the voice reaches the reader.
 *
 * Sean asked for his own voice over these clips, and for the voice and the picture to
 * match. Everything below is in service of those two sentences and of not making the page
 * worse for anyone who does not want it.
 *
 * WHY A SEPARATE AUDIO FILE, SLAVED TO THE VIDEO
 * ----------------------------------------------
 * The six mechanism animations carry their voice muxed inside the mp4, and that is right
 * for them: they exist to be watched once, start to finish. These ten do not. Most are
 * `muted loop` ambient diagrams a reader leaves running beside the prose, and a voice burnt
 * into a loop says the same sentence every twenty seconds until it is turned off. They are
 * also not this module's files to re-encode.
 *
 * So the voice is one full-length audio bed per clip, built by tools/narrate_layers_bed.py:
 * exactly as long as the clip, every spoken line already sitting at the second it belongs
 * to, silence everywhere else. The timing is therefore baked in by ffmpeg offline, where it
 * was measured off the delivered file rather than asserted, and the only thing this module
 * has to do at run time is keep one number - the audio's clock - equal to another - the
 * video's. That is a far smaller promise than scheduling a queue of clips in a browser tab
 * that may be throttled, backgrounded or seeking.
 *
 * NOTHING PLAYS BY ITSELF
 * -----------------------
 * No autoplay, ever. `preload="none"` means a reader who never presses the button
 * downloads none of it, which also keeps the page weight where the layers work put it. The
 * bed is fetched on the first press and not before.
 *
 * EVERY SPOKEN WORD IS ALSO WRITTEN DOWN
 * --------------------------------------
 * A teaching page that puts a fact only in audio has removed it from every reader who is
 * deaf, who has the sound off, who is on a train, or who reads faster than anyone talks.
 * The transcript is rendered from the SAME manifest the audio was built from, so it cannot
 * drift from what the voice actually says, and each line is stamped with the second it is
 * spoken at, which is the useful thing a transcript can add over prose.
 *
 * REDUCED MOTION
 * --------------
 * `prefers-reduced-motion` governs motion this page starts on its own. This module starts
 * none: it adds no transition, no animation, and no auto-advance. Pressing the button is an
 * explicit request from the reader, and honouring it is not a violation of that setting -
 * refusing to do what the button says would be. What the setting does change is the label:
 * a reader who has asked for less motion is told, before they press, that the button starts
 * the animation as well as the voice.
 */

import "./layer-narration.css";
import bedManifest from "../media/narration-layers/manifest.json";

/**
 * Vite resolves `new URL(...)` asset references one directory level at a time, so the beds
 * need their own helper - the same reason src/observed-imagery.ts carries one. Without it
 * the mp3 URL points at a file that was never emitted into the bundle and the audio fails
 * silently in production, which is the worst way for audio to fail.
 */
const bedAsset = (file: string) =>
  new URL(`../media/narration-layers/${file}`, import.meta.url).href;

type BedLine = {
  id: string;
  text: string;
  beatStartSeconds: number;
  audioSeconds: number;
  source?: string;
};

type Bed = {
  clip: string;
  file: string;
  videoSeconds: number;
  voice?: string;
  lines: BedLine[];
};

const BEDS = new Map<string, Bed>(
  (bedManifest.clips as Bed[]).map((clip) => [clip.clip, clip]),
);

/**
 * THE AUDIO IS THE CLOCK, AND THE PICTURE FOLLOWS IT.
 *
 * The first version of this slaved the audio to the video, which is the obvious way round
 * and the wrong one. Measured in a real browser on a loaded machine, the voice ran up to
 * 0.92 s behind the picture: the video decodes locally and starts instantly, the audio has
 * to be fetched first because nothing is preloaded, and every correction after that was a
 * SEEK ON THE AUDIO - which is audible as a click or a swallowed syllable, and which then
 * has to re-buffer and drift again.
 *
 * Turned round, the voice is continuous and never seeks, which is what a listener actually
 * notices, and every correction lands on the PICTURE instead - where, below, it is a small
 * trim to its speed rather than a jump. The file whose timing was measured offline is the
 * one left alone.
 *
 * Nothing starts until both elements say they can play, so the fetch happens before the
 * clock does rather than during it.
 */
const RESYNC_THRESHOLD_SECONDS = 0.08;

/**
 * Past this, the picture is not late — it is somewhere else, and is seeked.
 *
 * Under it, the picture is nudged instead. Seeking a video mid-playback costs a keyframe
 * decode, and the voice keeps running while that happens, so the picture lands behind
 * again by roughly what the seek cost: measured on a loaded machine, correcting a third of
 * a second by seeking produced a run that never converged and wandered between 0.14 and
 * 0.72 s behind. The picture was decoding at 0.997 of real time throughout, so the
 * decoder was never the problem — the corrections were.
 */
const RESEEK_THRESHOLD_SECONDS = 1.0;

/**
 * How hard the picture is allowed to be nudged. A silent diagram running 12% fast or slow
 * for a second or two is not something a viewer can see; a jump is.
 */
const MAX_RATE_TRIM = 0.12;

/** Resolves when the element can play, or when waiting is no longer worth it. */
function ready(media: HTMLMediaElement, budgetMs = 8000): Promise<void> {
  if (media.readyState >= 3) return Promise.resolve();
  return new Promise((resolve) => {
    const done = () => {
      media.removeEventListener("canplay", done);
      window.clearTimeout(timer);
      resolve();
    };
    const timer = window.setTimeout(done, budgetMs);
    media.addEventListener("canplay", done, { once: true });
    // preload="none" means nothing has been asked for yet. This is the moment the reader
    // has asked, so this is the moment to ask the network.
    media.preload = "auto";
    media.load();
  });
}

const seconds = (value: number) => `${value.toFixed(0)} s`;

const timecode = (value: number) => {
  const whole = Math.max(0, Math.round(value));
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
};

const escape = (value: string) =>
  value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

function reducedMotion(): boolean {
  try {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch {
    return false;
  }
}

function markup(bed: Bed, clipId: string): string {
  const label = reducedMotion()
    ? "Play the clip with narration (this starts the animation)"
    : "Play with narration";
  const lines = bed.lines
    .map(
      (line) =>
        `<li><span class="narration-cue">${timecode(line.beatStartSeconds)}</span>${escape(line.text)}</li>`,
    )
    .join("");
  const drafted = bed.lines.some((line) => line.source === "deterministic");
  return `
    <p class="narration-head">
      <strong>Narration</strong> · Sean's own voice · ${seconds(bed.videoSeconds)}
      <span class="narration-note">Nothing plays until you press it.</span>
    </p>
    <div class="narration-controls">
      <button type="button" class="narration-toggle" data-narration-toggle
              aria-pressed="false">${label}</button>
      <span class="narration-state" role="status" aria-live="polite"></span>
    </div>
    <audio class="narration-audio" preload="none" controls
           src="${bedAsset(bed.file)}"
           aria-label="Spoken narration for the ${escape(clipId.replace(/-/g, " "))} clip"></audio>
    <details class="narration-transcript">
      <summary>Transcript · every word the voice says${drafted ? ", assembled from this page" : ""}</summary>
      <ol>${lines}</ol>
    </details>`;
}

/**
 * Wire one slot. The video is found from the slot rather than by id because the figure is
 * rebuilt every time a reader opens a layer page, so an id would either collide or go stale.
 */
function wire(slot: HTMLElement): void {
  const figure = slot.closest("figure");
  const video = figure?.querySelector<HTMLVideoElement>("video.layer-video") ?? null;
  const audio = slot.querySelector<HTMLAudioElement>("audio.narration-audio");
  const toggle = slot.querySelector<HTMLButtonElement>("[data-narration-toggle]");
  const state = slot.querySelector<HTMLElement>(".narration-state");
  if (!audio || !toggle || !state) return;

  const say = (message: string) => {
    state.textContent = message;
  };

  // The clip loops silently when nobody has asked for the voice. A narrated clip must not:
  // a voice track that restarts its first sentence forever is an irritation, and the same
  // judgement is already recorded for the coronagraph loop in src/layer-pages.ts. The
  // original value is restored when the reader turns narration back off, so the page is
  // left exactly as it was found.
  const loopedByDefault = video?.loop ?? false;
  const offLabel = () =>
    reducedMotion()
      ? "Play the clip with narration (this starts the animation)"
      : "Play with narration";

  let on = false;

  const stop = (message = "") => {
    on = false;
    audio.pause();
    toggle.setAttribute("aria-pressed", "false");
    toggle.textContent = offLabel();
    if (video) {
      video.loop = loopedByDefault;
      video.playbackRate = 1;
    }
    say(message);
  };

  /**
   * Pull the picture back onto the voice. See the note above on which follows which.
   *
   * Three regimes, and the middle one is the whole point. A long way out, seek. A little
   * out, TRIM THE PICTURE'S SPEED until it catches up — no jump, no decoder stall, and the
   * error closes smoothly instead of being re-created by the correction itself. On time,
   * hand the rate back so the clip plays as it was made.
   */
  const resync = () => {
    if (!on || !video || video.paused || video.seeking) return;
    const drift = video.currentTime - audio.currentTime;
    if (Math.abs(drift) > RESEEK_THRESHOLD_SECONDS) {
      if (audio.currentTime <= video.duration) video.currentTime = audio.currentTime;
      video.playbackRate = 1;
      return;
    }
    if (Math.abs(drift) > RESYNC_THRESHOLD_SECONDS) {
      const trim = Math.max(-MAX_RATE_TRIM, Math.min(MAX_RATE_TRIM, -drift * 0.6));
      video.playbackRate = 1 + trim;
      return;
    }
    if (video.playbackRate !== 1) video.playbackRate = 1;
  };

  toggle.addEventListener("click", () => {
    if (on) {
      stop("Narration off.");
      video?.pause();
      return;
    }
    on = true;
    toggle.setAttribute("aria-pressed", "true");
    toggle.textContent = "Stop narration";
    say("Loading the narration…");

    void (async () => {
      // Fetch first, then start the clock. Starting the picture while the voice is still
      // arriving is what put the two nearly a second apart the first time this was measured.
      await Promise.all([ready(audio), video ? ready(video) : Promise.resolve()]);
      if (!on) return;
      audio.currentTime = 0;
      if (video) {
        video.loop = false;
        video.currentTime = 0;
      }
      // A rejected play() is normal, not exceptional: a browser may decide the gesture did
      // not reach it. Saying so is better than a control that looks pressed and does nothing.
      if (video) video.playbackRate = 1;
      const results = await Promise.allSettled([audio.play(), video ? video.play() : undefined]);
      if (!on) return;
      say(audio.paused && results.length
        ? "The browser would not start playback. Press play on the clip."
        : "Playing.");
    })();
  });

  audio.addEventListener("timeupdate", resync);
  audio.addEventListener("seeked", resync);
  audio.addEventListener("play", () => {
    if (!on && video) {
      on = true;
      toggle.setAttribute("aria-pressed", "true");
      toggle.textContent = "Stop narration";
      video.loop = false;
      void video.play();
    }
    say("Playing.");
  });
  audio.addEventListener("pause", () => {
    if (on) video?.pause();
  });
  audio.addEventListener("ended", () => {
    video?.pause();
    stop("Narration finished.");
  });

  if (video) {
    // The reader may still reach for the clip's own transport. Keep the two together rather
    // than letting one run without the other.
    video.addEventListener("pause", () => {
      if (on && !audio.paused) {
        audio.pause();
        say("Paused.");
      }
    });
    video.addEventListener("play", () => {
      if (on && audio.paused) void audio.play();
    });
  }
}

/**
 * Fill every narration slot in `root` that has audio to put in it.
 *
 * A clip with no bed is left exactly as the layer pages rendered it - the slot stays empty
 * and stays `hidden`, so a page whose narration has not been recorded yet costs the reader
 * nothing and shows no broken control. That is the whole reason this reads a manifest
 * rather than a hard-coded list: the nine remaining clips appear here the moment their
 * audio is rendered, with no change to this file.
 */
export function mountLayerNarration(root: ParentNode = document): void {
  root.querySelectorAll<HTMLElement>("[data-narration-for]").forEach((slot) => {
    const clipId = slot.dataset.narrationFor ?? "";
    const bed = BEDS.get(clipId);
    if (!bed || !bed.lines.length) return;
    slot.hidden = false;
    slot.innerHTML = markup(bed, clipId);
    wire(slot);
  });
}

/**
 * Silence every narration bed on the page.
 *
 * Called wherever the layer videos are stopped. Leaving a voice talking over a page the
 * reader has already navigated away from is the single most hostile thing audio on a
 * website can do.
 */
export function stopLayerNarration(root: ParentNode = document): void {
  root.querySelectorAll<HTMLAudioElement>("audio.narration-audio").forEach((audio) => {
    audio.pause();
  });
}

/** Exposed for the tests: which clips currently have narration to play. */
export function narratedClips(): string[] {
  return [...BEDS.keys()].sort();
}
