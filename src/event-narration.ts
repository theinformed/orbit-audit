/**
 * The spoken walkthrough over a measured event chart: how the voice drives the picture.
 *
 * Sean, 2026-09-03, watching the Starlink replay: "if you extended and timed the
 * animations right, you could have a really good overview of the event with a voice over
 * in those graphs." He was explicit that it be just over a minute, not longer.
 *
 * THE AUDIO IS THE CLOCK. THE PICTURE FOLLOWS IT.
 * ----------------------------------------------
 * There is exactly one time source in a narrated run: `audio.currentTime` on one element
 * that is never seeked by this file. Every frame reads that number and asks this module
 * where the chart's cursor belongs; nothing here integrates elapsed time of its own.
 *
 * That is the whole design, and it is a correction of the obvious alternative. The chart
 * already owns a `FrameClock` that advances a cursor by `rate x elapsed`, and the tempting
 * move is to leave it running and start the voice beside it. Two clocks with no coupling
 * drift, and the drift is the entire failure mode: `src/layer-narration.ts` measured the
 * same mistake on the layer clips at up to 0.92 s, which is a full clause of speech landing
 * over the wrong picture. A rAF loop still runs here, but only as the paint tick -- it
 * carries no time of its own, and a frame that arrives late reads a later `currentTime` and
 * draws the right frame rather than a stale one.
 *
 * THE PICTURE LEADS THE VOICE BY A FRACTION OF A SECOND
 * ----------------------------------------------------
 * Each anchor is placed at the line's start MINUS `PICTURE_LEAD_SECONDS`. A beat that lands
 * fractionally early reads as deliberate -- the thing appears and then is named. The same
 * beat landing fractionally late reads as broken.
 *
 * WHERE THE ANCHORS COME FROM
 * ---------------------------
 * From the replay payload, every time, in `orbitDecayAnchors()` below -- never from a table
 * anyone typed. The catalogue republishes on its own timer, and an anchor list copied out
 * of one afternoon's data would go on pointing at hours that had stopped meaning anything;
 * for line 05 in particular that would put "watch the traces separate" over a frame where
 * nothing separates. If an anchor cannot be derived, no walkthrough is mounted at all.
 *
 * That derivation lives HERE rather than inside the view for one reason that matters: it is
 * the actual teaching decision in this feature, and a canvas-bound class cannot be tested
 * in jsdom. As a pure function over the payload it is checked against the shipped data in
 * tests/event-narration.test.ts.
 *
 * EVERY SPOKEN WORD IS ALSO WRITTEN DOWN
 * --------------------------------------
 * The line being spoken is pushed into the chart's own caption plate as it starts, and the
 * whole script sits in a transcript fold under the control with the second each line is
 * spoken at. Both are rendered from the bed manifest the audio was stitched from, so
 * neither can drift from what the voice actually says.
 */

import bedManifest from "../media/event-charts/narration/bed-manifest.json";

/**
 * Vite resolves `new URL(...)` asset references one directory level at a time, so the beds
 * need their own helper -- the same reason src/layer-narration.ts carries one. Without it
 * the mp3 URL points at a file that was never emitted into the bundle and the audio fails
 * silently in production, which is the worst way for audio to fail.
 */
const bedAsset = (file: string) =>
  new URL(`../media/event-charts/narration/${file}`, import.meta.url).href;

export interface BedLine {
  id: string;
  startSeconds: number;
  audioSeconds: number;
  measuredStartSeconds: number;
  text: string;
}

export interface BedScene {
  scene: string;
  ok: boolean;
  file: string;
  bedSeconds: number;
  lines: BedLine[];
}

const SCENES = new Map<string, BedScene>(
  (bedManifest.scenes as BedScene[]).filter((scene) => scene.ok).map((scene) => [scene.scene, scene]),
);

/** The bed stitched for this scene, or undefined if none shipped. */
export function narrationBed(scene: string): BedScene | undefined {
  return SCENES.get(scene);
}

/**
 * How far ahead of the word the picture runs. See the header.
 *
 * One quarter of a second is about a syllable. Below roughly 0.1 s the lead is inside the
 * jitter of a frame and does nothing; above roughly 0.4 s the picture is visibly ahead of
 * the sentence rather than under it.
 */
const PICTURE_LEAD_SECONDS = 0.2;

/** One line of the script, and the moment on the chart's clock it is spoken over. */
export interface NarrationAnchor {
  /** The bed line this anchors. */
  line: string;
  /** Where the chart's cursor must be, in the view's own units. */
  at: number;
  /** The record that fixes it there. Printed nowhere; read by the next person here. */
  because: string;
}

/**
 * A monotone cubic through the anchors: audio seconds in, chart cursor out.
 *
 * PIECEWISE LINEAR WOULD HIT EVERY ANCHOR TOO, and was the first version. What it also does
 * is change speed instantly at each one, and the anchors here differ in rate by up to a
 * factor of two, so the chart visibly jerks at the exact moment a new sentence begins --
 * which is the one moment the reader is looking at it.
 *
 * Fritsch-Carlson slopes give a curve that passes through every anchor EXACTLY, has a
 * continuous first derivative, and cannot overshoot: a monotone set of anchors produces a
 * monotone sweep, so the chart can never run backwards between two beats. Both properties
 * are load-bearing and both are asserted in tests/event-narration.test.ts.
 */
export class AnchorCurve {
  private readonly ts: number[];
  private readonly vs: number[];
  private readonly ms: number[];

  constructor(knots: Array<[number, number]>) {
    this.ts = knots.map((knot) => knot[0]);
    this.vs = knots.map((knot) => knot[1]);
    const n = knots.length;
    const d: number[] = [];
    for (let i = 0; i < n - 1; i += 1) {
      d.push((this.vs[i + 1]! - this.vs[i]!) / (this.ts[i + 1]! - this.ts[i]!));
    }
    const m = new Array<number>(n).fill(0);
    for (let i = 1; i < n - 1; i += 1) {
      const a = d[i - 1]!;
      const b = d[i]!;
      if (a * b <= 0) { m[i] = 0; continue; }
      const h1 = this.ts[i]! - this.ts[i - 1]!;
      const h2 = this.ts[i + 1]! - this.ts[i]!;
      const w1 = 2 * h2 + h1;
      const w2 = h2 + 2 * h1;
      m[i] = (w1 + w2) / (w1 / a + w2 / b);
    }
    m[0] = AnchorCurve.endSlope(d[0]!, d[1] ?? d[0]!, this.ts[1]! - this.ts[0]!,
      (this.ts[2] ?? this.ts[1]!) - this.ts[1]!);
    m[n - 1] = AnchorCurve.endSlope(d[n - 2]!, d[n - 3] ?? d[n - 2]!,
      this.ts[n - 1]! - this.ts[n - 2]!, this.ts[n - 2]! - (this.ts[n - 3] ?? this.ts[n - 2]!));
    this.ms = m;
  }

  /** The one-sided end slope, clamped so an endpoint cannot break monotonicity. */
  private static endSlope(d0: number, d1: number, h0: number, h1: number): number {
    if (h0 + h1 === 0) return d0;
    const raw = ((2 * h0 + h1) * d0 - h0 * d1) / (h0 + h1);
    if (raw * d0 <= 0) return 0;
    if (Math.abs(raw) > 3 * Math.abs(d0)) return 3 * d0;
    return raw;
  }

  at(t: number): number {
    const n = this.ts.length;
    if (t <= this.ts[0]!) return this.vs[0]!;
    if (t >= this.ts[n - 1]!) return this.vs[n - 1]!;
    let i = 0;
    while (i < n - 2 && t > this.ts[i + 1]!) i += 1;
    const h = this.ts[i + 1]! - this.ts[i]!;
    const s = (t - this.ts[i]!) / h;
    const s2 = s * s;
    const s3 = s2 * s;
    return (2 * s3 - 3 * s2 + 1) * this.vs[i]!
      + (s3 - 2 * s2 + s) * h * this.ms[i]!
      + (-2 * s3 + 3 * s2) * this.vs[i + 1]!
      + (s3 - s2) * h * this.ms[i + 1]!;
  }
}

/**
 * Turn a bed and a set of anchors into the curve the picture follows.
 *
 * The first knot is the bed's own origin rather than line 01's start: at t=0 the chart is
 * at the beginning of its window, which IS line 01's moment, and a knot pair holding the
 * same value would freeze the picture for the lead-in instead of easing off the mark.
 * The last knot is the end of the bed at the end of the chart, so the clip finishes on the
 * frame a reader who never pressed anything already sees.
 */
export function buildCurve(bed: BedScene, anchors: NarrationAnchor[], endAt: number): AnchorCurve | null {
  const byId = new Map(bed.lines.map((line) => [line.id, line]));
  const knots: Array<[number, number]> = [[0, anchors[0]?.at ?? 0]];
  for (const anchor of anchors.slice(1)) {
    const line = byId.get(anchor.line);
    if (!line) return null;
    knots.push([line.startSeconds - PICTURE_LEAD_SECONDS, anchor.at]);
  }
  knots.push([bed.bedSeconds, endAt]);
  // A curve is only honest if it is strictly increasing in time and never decreasing in
  // the picture. Anything else is an anchor table someone mistyped, and shipping the
  // walkthrough anyway would put a sentence over the wrong part of the chart.
  for (let i = 1; i < knots.length; i += 1) {
    if (knots[i]![0] <= knots[i - 1]![0]) return null;
    if (knots[i]![1] < knots[i - 1]![1]) return null;
  }
  return new AnchorCurve(knots);
}

const escape = (value: string) =>
  value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

const timecode = (value: number) => {
  const whole = Math.max(0, Math.round(value));
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
};

export interface NarrationHooks {
  /** Put the chart's cursor here. Called once per frame while the voice is running. */
  seek(at: number): void;
  /** The line now being spoken, for the chart's own caption plate. */
  say(step: number, of: number, text: string): void;
  /** The voice has stopped and the picture is the reader's again. */
  release(): void;
  /** A reader-visible request to stop whatever else is driving the picture. */
  claim(): void;
  /** Whether this reader has asked their system for less movement. */
  reduced(): boolean;
}

/**
 * The narrated walkthrough for one chart: markup, the element, and the loop.
 */
export class ChartNarration {
  private readonly audio: HTMLAudioElement;
  private readonly toggle: HTMLButtonElement;
  private readonly state: HTMLElement;
  private frame = 0;
  private spoken = -1;
  private owning = false;

  constructor(
    private readonly slot: HTMLElement,
    private readonly bed: BedScene,
    private readonly curve: AnchorCurve,
    private readonly anchors: NarrationAnchor[],
    private readonly hooks: NarrationHooks,
  ) {
    slot.innerHTML = this.markup();
    this.audio = slot.querySelector<HTMLAudioElement>("audio.replay-narration-audio")!;
    this.toggle = slot.querySelector<HTMLButtonElement>("[data-narration-toggle]")!;
    this.state = slot.querySelector<HTMLElement>(".replay-narration-state")!;

    this.toggle.addEventListener("click", () => {
      if (this.audio.paused) void this.start(); else this.stop();
    });
    this.audio.addEventListener("play", () => {
      this.owning = true;
      this.toggle.textContent = "Pause the walkthrough";
      this.toggle.setAttribute("aria-pressed", "true");
      this.state.textContent = "Playing. The chart is following the voice.";
      this.tick();
    });
    this.audio.addEventListener("pause", () => this.handleStop("Paused."));
    this.audio.addEventListener("ended", () => this.handleStop("Finished."));
    // A reader who drags the AUDIO's own scrubber is moving the clock itself, and the
    // picture follows it -- which is the supported way to jump about inside the
    // walkthrough. Dragging the CHART's scrubber is the opposite request and is handled by
    // the view, which calls stop() below: the bed is one continuous take, and seeking it to
    // match a hand-placed cursor lands mid-word every time.
    this.audio.addEventListener("seeked", () => { if (this.owning) this.paint(); });
  }

  get playing(): boolean { return !this.audio.paused; }

  private markup(): string {
    const label = this.hooks.reduced()
      ? "Play the narrated walkthrough (this animates the chart)"
      : "Play the narrated walkthrough";
    const rows = this.bed.lines
      .map((line) => `<li><span class="replay-narration-cue">${timecode(line.startSeconds)}</span>${escape(line.text)}</li>`)
      .join("");
    return `
      <p class="replay-narration-head">
        <strong>Narrated walkthrough</strong> · Sean's own voice · ${Math.round(this.bed.bedSeconds)} s
        <span class="replay-narration-note">Nothing plays until you press it. The chart follows the voice.</span>
      </p>
      <div class="replay-narration-controls">
        <button type="button" data-narration-toggle aria-pressed="false">${label}</button>
        <span class="replay-narration-state" role="status" aria-live="polite"></span>
      </div>
      <audio class="replay-narration-audio" preload="none" controls
             src="${bedAsset(this.bed.file)}"
             aria-label="Spoken walkthrough of this chart"></audio>
      <details class="replay-narration-transcript">
        <summary>Transcript · every word the voice says</summary>
        <ol>${rows}</ol>
      </details>`;
  }

  /** Fetch, then play. `preload="none"` means nothing is asked for until this moment. */
  private async start(): Promise<void> {
    this.hooks.claim();
    this.state.textContent = "Loading the voice…";
    if (this.audio.readyState < 3) {
      this.audio.preload = "auto";
      this.audio.load();
      await new Promise<void>((resolve) => {
        const done = () => { window.clearTimeout(timer); resolve(); };
        const timer = window.setTimeout(done, 8000);
        this.audio.addEventListener("canplay", done, { once: true });
      });
    }
    if (this.audio.ended || this.audio.currentTime >= this.bed.bedSeconds - 0.05) {
      this.audio.currentTime = 0;
    }
    this.spoken = -1;
    try {
      await this.audio.play();
    } catch {
      this.state.textContent = "The browser would not start the audio. Press play on the bar below.";
    }
  }

  /**
   * Give the picture back. Called by the view when the reader takes the chart over.
   *
   * SYNCHRONOUS, AND IN THIS ORDER, because `pause()` does not fire its event until a later
   * task. Measured in a real browser before this: a reader who dragged the chart's scrubber
   * to hour 500 mid-clip saw it snap back to hour 49 a frame later -- the rAF that was
   * already queued when the pause was requested painted once more, on the voice's clock,
   * over the position the reader had just chosen. Cancelling the frame and dropping
   * ownership here, rather than waiting for the event, closes that window.
   */
  stop(): void {
    this.cancelFrame();
    const released = this.owning;
    this.owning = false;
    if (!this.audio.paused) this.audio.pause();
    this.reset("Paused.");
    if (released) this.hooks.release();
  }

  private cancelFrame(): void {
    if (this.frame) window.cancelAnimationFrame(this.frame);
    this.frame = 0;
  }

  /** Put the control back to its resting label. */
  private reset(message: string): void {
    this.toggle.textContent = this.audio.ended
      ? "Play the walkthrough again"
      : (this.hooks.reduced()
        ? "Play the narrated walkthrough (this animates the chart)"
        : "Play the narrated walkthrough");
    this.toggle.setAttribute("aria-pressed", "false");
    this.state.textContent = message;
  }

  /** The voice stopped on its own -- it ended, or the reader used the audio bar. */
  private handleStop(message: string): void {
    this.cancelFrame();
    this.reset(message);
    if (this.owning) {
      this.owning = false;
      this.hooks.release();
    }
  }

  /**
   * One paint. The time comes from the audio element and from nowhere else.
   *
   * REDUCED MOTION. A reader who has asked their system for less movement gets the chart
   * STEPPED to the anchor of the line being spoken rather than swept between anchors: six
   * changes across the clip instead of a continuous sweep. The words still land on the
   * right picture, which is the promise; the motion between them is the part they asked
   * not to have. Pressing the button is itself an explicit request, so the voice plays.
   */
  private paint(): void {
    if (!this.owning) return;
    const now = this.audio.currentTime;
    // The same fraction of a second the swept picture leads by, so the stepped picture and
    // the caption change a beat ahead of the word too rather than exactly on it.
    const step = this.lineAt(now + PICTURE_LEAD_SECONDS);
    this.hooks.seek(this.hooks.reduced()
      ? (this.anchors[Math.max(0, step)]?.at ?? this.curve.at(now))
      : this.curve.at(now));
    if (step !== this.spoken) {
      this.spoken = step;
      const line = this.bed.lines[step];
      if (line) this.hooks.say(step + 1, this.bed.lines.length, line.text);
    }
  }

  /** Which line is sounding, or the last one spoken while a gap runs. -1 before the first. */
  private lineAt(seconds: number): number {
    let index = -1;
    this.bed.lines.forEach((line, at) => { if (seconds >= line.startSeconds) index = at; });
    return index;
  }

  private tick = (): void => {
    this.paint();
    if (!this.audio.paused) this.frame = window.requestAnimationFrame(this.tick);
  };

  destroy(): void {
    this.cancelFrame();
    this.owning = false;
    this.audio.pause();
    // Leaving a fetch running for a dialog the reader has already closed is the single most
    // hostile thing audio on a page can do. src/layer-narration.ts states the same rule.
    this.audio.removeAttribute("src");
    this.audio.load();
    this.slot.innerHTML = "";
  }
}

// ---------------------------------------------------------------------------
// Where the six lines belong on the orbit-decay chart's own clock
// ---------------------------------------------------------------------------

/**
 * The part of an orbit-decay payload the anchors are derived from.
 *
 * Structural rather than imported from `event-replay.ts`, so the derivation can be checked
 * against a fixture — and so this module does not import the module that imports it.
 */
export interface AnchorReplay {
  startsAt: string;
  driver: { hours: number[]; kp: number[] };
  objects: Array<{ outcome: "lost" | "raised"; samples: Array<[number, number, number]> }>;
}

/** Hours from the start of the window to the next UTC midnight after it. */
function hoursToNextUtcDay(startsAt: string): number {
  const base = Date.parse(startsAt);
  const start = new Date(base);
  const next = Date.UTC(start.getUTCFullYear(), start.getUTCMonth(), start.getUTCDate() + 1);
  return (next - base) / 3600_000;
}

/**
 * The first three-hourly Kp at or above 5 — NOAA's G1 line — at or after `after`.
 *
 * NOT the chart's own `peakDriverHour()`. That returns the FIRST hour holding the peak
 * value, and this event's driver record reaches Kp 5.33 twice: at hour 9 (2022-02-03 09:00)
 * and again at hour 39 (2022-02-04 15:00). Hour 9 is on the launch day, and the line being
 * spoken says the storm arrived the NEXT day, so the narrated anchor is the first G1
 * interval after the day boundary. The chart's dashed storm rule still sits on hour 9;
 * that is a separate question about the silent chart and is not changed here.
 */
function firstStormHour(replay: AnchorReplay, after: number): number | null {
  const { hours, kp } = replay.driver;
  for (let i = 0; i < hours.length; i += 1) {
    const hour = hours[i];
    const level = kp[i];
    if (hour === undefined || level === undefined) break;
    if (hour >= after && level >= 5) return hour;
  }
  return null;
}

/** The earliest hour any object of this outcome has an element set for. */
function firstHourOf(replay: AnchorReplay, outcome: "lost" | "raised"): number | null {
  const firsts = replay.objects
    .filter((object) => object.outcome === outcome)
    .map((object) => object.samples[0]?.[0])
    .filter((hour): hour is number => hour !== undefined);
  return firsts.length ? Math.min(...firsts) : null;
}

/** The last hour any object the catalogue lost still had an element set. */
function lastLossHour(replay: AnchorReplay): number | null {
  const lasts = replay.objects
    .filter((object) => object.outcome === "lost")
    .map((object) => object.samples[object.samples.length - 1]?.[0])
    .filter((hour): hour is number => hour !== undefined);
  return lasts.length ? Math.max(...lasts) : null;
}

/**
 * Where each spoken line belongs on the orbit-decay chart's clock.
 *
 *   01  hour 0        the window opens on the launch day; the empty plot is itself the
 *                     fact that the catalogue has not caught up yet
 *   02  hour 24.0     the next UTC midnight after the window opens
 *   03  hour 39.0     the first three-hourly Kp >= 5 after that boundary — the G1 the line
 *                     calls "the bottom of the scale"
 *   04  hour 64.18    the earliest element set anything in this chart has. The first traces
 *                     appear as the mechanism is described, and the first four losses
 *                     (hours 72.0, 72.0, 77.5, 86.2) all fall inside that sentence
 *   05  hour 138.0    THE ONE THAT MATTERS. The ten lost objects begin publishing at hour
 *                     64.18; all eleven raised ones appear together at hour 138.0. So 138.0
 *                     is the first frame on which both families are on the plot, and the
 *                     first on which they can be seen to part. What follows is the parting:
 *                     median perigee across the eleven runs 247 km at hour 140 to 315 km at
 *                     hour 300, while the surviving lost ones run 201 km down to 156 km —
 *                     a gap opening from 46 km to 158 km. "Watch the traces separate" runs
 *                     9.5 s and covers hours 140 to 296 of that.
 *   06  hour 303.28   the last object the catalogue stopped publishing for, so every cross
 *                     on the plot is already placed as the reentries are named
 *
 * Null when any of them cannot be derived. Silence is the correct failure: a chart with no
 * walkthrough keeps exactly the controls it always had.
 */
export function orbitDecayAnchors(scene: string, replay: AnchorReplay): NarrationAnchor[] | null {
  const boundary = hoursToNextUtcDay(replay.startsAt);
  const storm = firstStormHour(replay, boundary);
  const firstDrawn = firstHourOf(replay, "lost");
  const firstRaised = firstHourOf(replay, "raised");
  const lastLoss = lastLossHour(replay);
  if (storm === null || firstDrawn === null || firstRaised === null || lastLoss === null) return null;
  const separation = Math.max(firstDrawn, firstRaised);
  const anchors: NarrationAnchor[] = [
    { line: `${scene}-01`, at: 0, because: "the start of the replay window" },
    { line: `${scene}-02`, at: boundary, because: "the next UTC midnight after it" },
    { line: `${scene}-03`, at: storm, because: "first three-hourly Kp >= 5 after that boundary" },
    { line: `${scene}-04`, at: Math.min(firstDrawn, firstRaised), because: "earliest published element set" },
    { line: `${scene}-05`, at: separation, because: "both outcomes first on the plot together" },
    { line: `${scene}-06`, at: lastLoss, because: "the last object the catalogue lost" },
  ];
  // A non-monotone anchor list is a payload this timeline cannot describe, not something to
  // paper over: buildCurve() would refuse it anyway, and refusing here says why.
  for (let i = 1; i < anchors.length; i += 1) {
    if (anchors[i]!.at <= anchors[i - 1]!.at) return null;
  }
  return anchors;
}

/**
 * Build the whole walkthrough for an orbit-decay chart, or return null and ship none.
 */
export function mountOrbitDecayNarration(
  slot: HTMLElement,
  scene: string,
  replay: AnchorReplay,
  endsAt: number,
  hooks: NarrationHooks,
): ChartNarration | null {
  const bed = narrationBed(scene);
  if (!bed) return null;
  const anchors = orbitDecayAnchors(scene, replay);
  if (!anchors) return null;
  const curve = buildCurve(bed, anchors, endsAt);
  if (!curve) return null;
  return new ChartNarration(slot, bed, curve, anchors, hooks);
}
