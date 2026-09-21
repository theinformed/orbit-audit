/**
 * The measured event replays: four events, four pictures, one rule.
 *
 * ## What this replaces, and why it had to be replaced
 *
 * Every historical event on this page used to animate through the SAME three
 * CSS custom properties — a blob that narrowed, a two-pixel line that
 * lengthened, and a `saturate()` filter over the whole box — driven by four
 * hand-authored numbers between 0 and 1 per milestone. The markup was
 * byte-identical for the Quebec blackout and for a Starlink launch, so the
 * picture could not tell them apart, and none of it came from a measurement.
 * It was decoration standing in the place where this site puts evidence.
 *
 * ## The rule every drawing in this file obeys
 *
 * - **No point is invented.** Every vertex is one real sample carrying its own
 *   timestamp. Series are thinned by SELECTING real samples near a grid time,
 *   never by interpolating between two of them.
 * - **A gap stays a gap.** A hole in an archive breaks the stroke rather than
 *   being bridged, so the eye is never shown a line the record did not support.
 * - **Every series says what class of thing it is.** A measurement and a model
 *   run are drawn differently, labelled differently, and never merged into one
 *   curve. Where both are present the page says which is which in the legend,
 *   not in a footnote.
 * - **The limitation travels with the picture.** Each replay prints, under the
 *   drawing, what it is drawn from and what it cannot claim.
 *
 * ## The six
 *
 * | id | kind | what the picture is |
 * |---|---|---|
 * | `starlink-2022` | `orbit-decay` | 21 catalogued objects from one launch, from their own element sets |
 * | `gannon-2024` | `thermosphere-inflation` | Swarm-C's measured density against WAM-IPE at the same point, and the model's global field |
 * | `halloween-2003` | `three-clocks` | X-rays, protons and Dst on one logarithmic axis from the flare |
 * | `bastille-2000` | `three-clocks` | the same three lanes, forty minutes and thirty-eight hours instead of two hours and sixty |
 * | `stpatricks-2015` | `southward-turning` | the arriving field's Bz, the wind's speed and SYM/H on one linear axis |
 * | `quebec-1989` | `gic-chain` | Ottawa's one-minute dB/dt through the minute the grid failed |
 *
 * Two events share `three-clocks` ON PURPOSE. One chart of that kind teaches
 * that the three arrivals are separated; only a second one, drawn by the same
 * code on the same axis, can teach that the separation is not a constant.
 *
 * The renderer owns no data. Everything it draws arrives in the `replay` block
 * of the events artifact, built by `pipeline/event_replays.py` on bigmem.
 */

import "./event-replay.css";
import { worldOutlines } from "./data/world-outlines";

/**
 * Media under `media/`, resolved the way the rest of this site resolves it.
 *
 * The video path deliberately does NOT come out of the events artifact. A URL
 * in JSON is a string the bundler cannot see, so it would ship as a link to a
 * file that was never emitted — silently, and only in production. Vite can
 * follow `new URL(..., import.meta.url)`, hashes the asset, and fails the build
 * if the file is missing, which is the failure mode worth having.
 */
import { ChartNarration, mountOrbitDecayNarration } from "./event-narration";

const mediaAsset = (file: string) => new URL(`../media/${file}`, import.meta.url).href;

/**
 * Anything this module will mount.
 *
 * `timeline()` is the seam the narrated walkthrough drives the picture through. It is
 * OPTIONAL because only one view has a stitched bed behind it, and a view that has none
 * must not be made to pretend it has a narratable clock: the caller checks for it rather
 * than being handed a stub that silently does nothing.
 */
export interface EventReplayView {
  destroy(): void;
  timeline?(): ReplayTimeline | null;
}

/**
 * A picture that can be driven from a clock outside itself.
 *
 * `at` is in the view's OWN cursor units -- event-hours for the orbit-decay chart -- and
 * never in seconds of audio. Translating one to the other is the narration's job, because
 * that mapping is where the teaching decision lives; the view only knows how to be at an
 * hour.
 */
export interface ReplayTimeline {
  /** Put the cursor here and redraw. Whatever else was driving the picture has stopped. */
  seek(at: number): void;
  /** The last moment this view can be at. */
  readonly endsAt: number;
}

/** Retained so `src/main.ts` keeps compiling; every view satisfies it. */
export type OrbitDecayReplayView = EventReplayView;

/** One thinned element set: hours from window start, perigee km, apogee km. */
export type ReplaySample = [number, number, number];

export interface ReplayObject {
  norad: number;
  intl: string;
  outcome: "lost" | "raised";
  elsetCount: number;
  firstEpoch: string;
  lastEpoch: string;
  lastPerigeeKm: number;
  samples: ReplaySample[];
}

export interface OrbitDecayReplay {
  kind: "orbit-decay";
  status: string;
  title: string;
  startsAt: string;
  endsAt: string;
  axis: { label: string; unit: string; min: number; max: number };
  objects: ReplayObject[];
  counts: {
    catalogued: number;
    lost: number;
    raised: number;
    launched: number;
    publiclyReportedLost: number;
  };
  driver: {
    label: string;
    source: string;
    hours: number[];
    kp: number[];
    ap: number[];
    peakKp: number;
    peakKpWindow: string;
  };
  provenance: {
    elements: string;
    elementsNote: string;
    driver: string;
    method: string;
    catalogueStart: string;
    limitation: string;
  };
}

export interface InflationSeries {
  label: string;
  detail: string;
  evidence: "measurement" | "model";
  baselineSi: number;
  /** hours from window start, ratio to the quiet day, density × 1e13 kg m⁻³ */
  points: Array<[number, number, number]>;
  /** hours, the PREVIOUS forecast cycle's value for the same moment */
  spread?: Array<[number, number]>;
}

export interface ThermosphereInflationReplay {
  kind: "thermosphere-inflation";
  status: string;
  title: string;
  startsAt: string;
  endsAt: string;
  axis: { label: string; min: number; max: number };
  series: { measured: InflationSeries; model: InflationSeries };
  map: {
    label: string;
    evidence: "model";
    lonCount: number;
    latCount: number;
    lonStart: number;
    lonStep: number;
    latStart: number;
    latStep: number;
    log2Min: number;
    log2Span: number;
    noData: number;
    hours: number[];
    frames: string[];
  };
  driver: {
    label: string;
    name: string;
    unit: string;
    evidence: "measurement";
    source: string;
    points: Array<[number, number]>;
    peak: number;
    peakAt: string;
    citation: string;
    usage: string;
  };
  findings: {
    globalPeak: number;
    globalPeakAt: string;
    globalTrough: number;
    globalTroughAt: string;
    measuredPeak: number;
    measuredPeakAt: string;
    measuredAltitudeKm: number;
    worstSpread: number | null;
    worstSpreadAt: string | null;
  };
  provenance: Record<string, string>;
}

export interface ClockLane {
  id: string;
  label: string;
  unit: string;
  scale: "log" | "linear";
  min: number;
  max: number;
  instrument: string;
  evidence: "measurement";
  points: Array<[number, number]>;
  guides: Array<{ value: number; label: string }>;
}

export interface ThreeClocksReplay {
  kind: "three-clocks";
  status: string;
  title: string;
  originAt: string;
  originLabel: string;
  minMinutes: number;
  maxMinutes: number;
  lanes: ClockLane[];
  arrivals: Array<{
    id: string;
    label: string;
    detail: string;
    minutes: number;
    value: string;
    note: string;
  }>;
  provenance: Record<string, string>;
}

/**
 * One lane of the southward-turning chart.
 *
 * A point is `[minutes from the window start, the real sample nearest the bin
 * centre, the smallest real sample in the bin, the largest real sample in the
 * bin]`. All four numbers are measurements; none of them is an average.
 */
export interface TurningLane {
  id: string;
  label: string;
  unit: string;
  scale: "linear";
  min: number;
  max: number;
  instrument: string;
  evidence: "measurement";
  points: Array<[number, number, number, number]>;
  guides: Array<{ value: number; label: string }>;
  /** Bins in the window with no valid sample at all. Drawn as breaks, counted here. */
  emptyBins: number;
  binCount: number;
}

export interface SouthwardTurningReplay {
  kind: "southward-turning";
  status: string;
  title: string;
  startAt: string;
  endAt: string;
  spanMinutes: number;
  binMinutes: number;
  lanes: TurningLane[];
  marks: Array<{
    id: string;
    label: string;
    detail: string;
    minutes: number;
    at: string;
    value: string;
    note: string;
  }>;
  findings: Record<string, number>;
  provenance: Record<string, string>;
}

export interface GicChainReplay {
  kind: "gic-chain";
  status: string;
  title: string;
  startsAt: string;
  endsAt: string;
  rate: {
    label: string;
    short: string;
    unit: string;
    evidence: "measurement";
    station: string;
    instrument: string;
    max: number;
    stepMinutes: number;
    values: Array<number | null>;
    quietMedian: number;
    peak: number;
    peakAt: string;
    atBlackout: number;
  };
  index: {
    label: string;
    unit: string;
    evidence: "measurement";
    instrument: string;
    min: number;
    max: number;
    points: Array<[number, number]>;
  };
  marks: Array<{
    id: string;
    hours: number;
    at: string;
    label: string;
    detail: string;
    value: string;
  }>;
  gapHours: number;
  ratioAtBlackout: number;
  video?: {
    /** File stem under `media/`; expects `<stem>.mp4` and `<stem>.jpg`. */
    stem: string;
    durationSeconds: number;
    width: number;
    height: number;
    caption: string;
    transcript: Array<{ at: number; text: string }>;
  };
  provenance: Record<string, string>;
}

export type EventReplay =
  | OrbitDecayReplay
  | ThermosphereInflationReplay
  | ThreeClocksReplay
  | SouthwardTurningReplay
  | GicChainReplay;

const PALETTE = {
  lost: "#ff7b78",
  raised: "#5ce8f1",
  driver: "#f5c96a",
  measured: "#5ce8f1",
  model: "#f5c96a",
  accent: "#a98cff",
  grid: "rgba(132,194,214,0.13)",
  gridStrong: "rgba(132,220,235,0.26)",
  text: "#edf8fb",
  muted: "#8da8b3",
} as const;

const MONO = '"IBM Plex Mono", ui-monospace, monospace';
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function utcStamp(millis: number, withHour = true): string {
  const at = new Date(millis);
  const day = String(at.getUTCDate()).padStart(2, "0");
  const hour = String(at.getUTCHours()).padStart(2, "0");
  const minute = String(at.getUTCMinutes()).padStart(2, "0");
  const date = `${at.getUTCFullYear()}-${MONTHS[at.getUTCMonth()]}-${day}`;
  return withHour ? `${date}  ${hour}:${minute} UTC` : date;
}

/**
 * "1 h 13 min", "2 d 11 h" — an elapsed time a person reads at a glance.
 *
 * The remainder is rounded, so it can round UP INTO the next whole unit and
 * has to be carried. Without the carry, the end of a five-day chart printed
 * "4 d 24 h" and the end of an hour printed "3 h 60 min" — never wrong by
 * more than a rounding, always wrong in the way that makes a reader distrust
 * every other number on the page.
 */
function elapsed(minutes: number): string {
  if (minutes < 1) return `${(minutes * 60).toFixed(0)} s`;
  if (minutes < 90) return `${minutes.toFixed(minutes < 10 ? 1 : 0)} min`;
  if (minutes < 48 * 60) {
    let whole = Math.floor(minutes / 60);
    let rest = Math.round(minutes - whole * 60);
    if (rest === 60) { whole += 1; rest = 0; }
    return `${whole} h ${String(rest).padStart(2, "0")} min`;
  }
  let days = Math.floor(minutes / 1440);
  let hours = Math.round((minutes - days * 1440) / 60);
  if (hours === 24) { days += 1; hours = 0; }
  return `${days} d ${hours} h`;
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"]/g, (character) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[character] as string);
}

/**
 * The method block under every picture: what it is drawn from, and what it
 * cannot claim.
 *
 * SPLIT IN TWO, 2026-09-03, for flow (Sean: "there just isn’t any flow for a
 * reader"). On a phone this block ran a screen and a half of provenance
 * reference between the chart and the milestone list, and every reader paid
 * for it whether or not they were checking a source. The rows now fold behind
 * a summary line — the same house grammar as a clip’s "Where this came from"
 * disclosure — with ONE exception: the "What this cannot show" row stays
 * outside the fold, always visible. That row is the limitation, and on this
 * site the limitation travels with the drawing and is not an optional
 * disclosure; the provenance behind each line is checkable on demand, but
 * what the picture cannot support is part of the picture.
 */
function methodBlock(rows: Array<[string, string | undefined]>): string {
  const row = ([term, body]: [string, string]) =>
    `<div><b>${escapeHtml(term)}</b><p>${escapeHtml(body)}</p></div>`;
  const kept = rows.filter((pair): pair is [string, string] => Boolean(pair[1]));
  if (kept.length === 0) return "";
  const limits = kept.filter(([term]) => /cannot/i.test(term));
  const folded = kept.filter(([term]) => !/cannot/i.test(term));
  return `<div class="replay-method">${limits.map(row).join("")}<details class="replay-method-fold"><summary>How this picture is made, record by record</summary>${folded.map(row).join("")}</details></div>`;
}

// ---------------------------------------------------------------------------
// Playback and captions — shared by every view in this file
// ---------------------------------------------------------------------------

/**
 * The most animation time one frame may carry.
 *
 * Generous on purpose. Its job is to absorb a pathological stall -- a tab that
 * was in the background, a long garbage collection -- and not to smooth
 * ordinary frames, which on any machine drawing at 30 fps or better are 33 ms
 * and never come near it. Set it small and a slow machine stops running the
 * animation at wall-clock speed and starts running it in slow motion, which is
 * a different lie from the one this replaces.
 */
const MAX_FRAME_SECONDS = 0.25;

/**
 * A play loop that runs on the DISPLAY's clock and integrates by ELAPSED TIME.
 *
 * What it replaces, and why: every replay here used to advance on
 * `window.setInterval(..., 32)`, adding a FIXED amount to the cursor on each
 * tick. Two things are wrong with that and both are visible. A 32 ms interval
 * does not divide into a 16.7 ms display refresh, so the picture lands one
 * frame early and one frame late in a repeating beat. Worse, a tick DELAYED by
 * anything else on the page still advances the same fixed amount when it
 * finally runs — so the replay's speed is whatever the main thread had left
 * over, and this page has a WebGL globe drawing behind the dialog. Measured on
 * the built page in this repository's own capture harness, the Starlink
 * replay's 32 ms interval was arriving roughly every 385 ms and the same
 * animation ran between 8 and 66 event-hours per second within one play.
 *
 * Integrating `rate x elapsed` instead fixes the wall-clock speed: a machine
 * that cannot keep up draws FEWER FRAMES of the same motion rather than slower
 * motion. The elapsed time is clamped per frame, so a tab that was in the
 * background resumes where it was instead of leaping forward by the length of
 * the coffee break.
 */
class FrameClock {
  private frame = 0;
  private dwell = 0;
  private last = 0;
  private step: ((seconds: number) => boolean) | null = null;

  /** True while playing, INCLUDING while held on a caption. */
  get running(): boolean { return this.frame !== 0 || this.dwell !== 0; }

  /** `step` receives seconds elapsed and returns true to be called again. */
  start(step: (seconds: number) => boolean): void {
    this.stop();
    this.step = step;
    this.resume();
  }

  /** Hold the picture still for `millis` — a caption dwell — then carry on. */
  hold(millis: number): void {
    this.cancelFrame();
    if (this.dwell) window.clearTimeout(this.dwell);
    this.dwell = window.setTimeout(() => { this.dwell = 0; this.resume(); }, millis);
  }

  stop(): void {
    this.cancelFrame();
    if (this.dwell) window.clearTimeout(this.dwell);
    this.dwell = 0;
    this.step = null;
  }

  private cancelFrame(): void {
    if (this.frame) window.cancelAnimationFrame(this.frame);
    this.frame = 0;
  }

  private resume(): void {
    if (!this.step) return;
    this.last = 0;
    this.frame = window.requestAnimationFrame(this.tick);
  }

  private tick = (now: number): void => {
    this.frame = 0;
    const step = this.step;
    if (!step) return;
    // The first frame of a run, and the first after a dwell, carries no
    // elapsed time: the gap since the previous frame was not animation.
    const seconds = this.last === 0 ? 0 : Math.min((now - this.last) / 1000, MAX_FRAME_SECONDS);
    this.last = now;
    if (step(seconds) && this.step && !this.dwell) {
      this.frame = window.requestAnimationFrame(this.tick);
    }
  };
}

/** A visitor who has asked their system for less movement gets less movement. */
function prefersReducedMotion(): boolean {
  return typeof window.matchMedia === "function"
    && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** The sourced prose beside the picture. Structurally `EventMilestone`. */
export interface ReplayMilestone {
  offsetMinutes: number;
  title: string;
  description: string;
}

/** One stop in a replay: a moment on the chart's OWN clock, and what it is. */
export interface ReplayCaption {
  /** In the view's own cursor units — hours for some views, minutes for others. */
  at: number;
  title: string;
  text: string;
  /**
   * Whether the picture STOPS here, or the caption is shown as the sweep goes
   * past it. Default true, which is every stop in this file except the ones
   * `OrbitDecayView` places before its chart has drawn anything: a hold on a
   * frame with nothing on it does not read as a pause, it reads as a break.
   */
  hold?: boolean;
}

/**
 * Shorten sourced prose the way a quotation is shortened: by taking whole
 * sentences off the front, never by paraphrasing.
 *
 * Nothing in a caption may be a sentence this file wrote. The full paragraph
 * is on the page under the picture — the milestone list for a milestone, the
 * arrivals list for an arrival — so a caption is a pointer into text the
 * reader can finish, not a second version of it that could disagree with it.
 */
function firstSentences(text: string, budget: number): string {
  const whole = text.trim();
  if (whole.length <= budget) return whole;
  const sentences = whole.match(/[^.!?]+[.!?]+(\s+|$)/g);
  if (!sentences) return whole;
  let out = "";
  for (const sentence of sentences) {
    if (out && out.length + sentence.length > budget) break;
    out += sentence;
  }
  return out.trim() || whole;
}

/**
 * How long the picture holds still on one caption.
 *
 * Long enough to start reading it without hurrying, short enough that a
 * visitor who came to watch the chart is not detained at every stop. The
 * caption STAYS on screen after the hold ends and while the chart moves on, so
 * this is time to begin reading rather than time to finish, and the Pause
 * button beneath it holds the frame for as long as anyone wants.
 */
function dwellMillis(text: string): number {
  const words = text.trim().split(/\s+/).length;
  return Math.min(6500, Math.max(3000, 1500 + words * 190));
}

/**
 * The caption box.
 *
 * It sits in the normal flow BETWEEN the picture and the controls, in its own
 * bordered plate, rather than floating over the drawing. That is the whole
 * reason it cannot overlap anything: there is no position to get wrong at any
 * width, on the plot, the axes, the in-chart labels, the scrubber or the next
 * caption. It also keeps the phone case honest — a plate over a 390 px chart
 * would cover the traces it is describing.
 *
 * `role="status"` with `aria-live="polite"` announces each caption as it
 * changes without interrupting anything the reader is already hearing.
 */
const CAPTIONS = `
  <div class="replay-captions" data-replay-captions role="status" aria-live="polite" hidden>
    <p class="replay-caption-step" data-caption-count></p>
    <p class="replay-caption-line"><strong data-caption-title></strong><span data-caption-body></span></p>
  </div>`;

/**
 * The stops a replay pauses at, and the box that says what each one is.
 *
 * A track with no stops never unhides its box, so a view that has nothing
 * sourced to say at a stated time says nothing at all.
 */
class CaptionTrack {
  private served = 0;
  private readonly box: HTMLElement | null;
  private readonly count: HTMLElement | null;
  private readonly title: HTMLElement | null;
  private readonly body: HTMLElement | null;

  constructor(root: HTMLElement, private readonly stops: ReplayCaption[]) {
    this.box = stops.length > 0 ? root.querySelector<HTMLElement>("[data-replay-captions]") : null;
    this.count = root.querySelector<HTMLElement>("[data-caption-count]");
    this.title = root.querySelector<HTMLElement>("[data-caption-title]");
    this.body = root.querySelector<HTMLElement>("[data-caption-body]");
    if (this.box) this.box.hidden = false;
  }

  /** Back to the first stop, for a replay that has just rewound. */
  rewind(): void { this.served = 0; }

  /** Where the next stop is, for a reduced-motion player that jumps to it. */
  nextAt(): number | null {
    const stop = this.box ? this.stops[this.served] : undefined;
    return stop ? stop.at : null;
  }

  /**
   * If the sweep has reached the next stop, serve it: show its caption and
   * report the exact moment to snap to and how long to hold there.
   */
  arriving(to: number): { at: number; dwell: number; hold: boolean } | null {
    const stop = this.box ? this.stops[this.served] : undefined;
    if (!stop || stop.at > to) return null;
    this.served += 1;
    this.render(this.served - 1);
    return { at: stop.at, dwell: dwellMillis(stop.text), hold: stop.hold !== false };
  }

  /**
   * Borrow the plate for a line the VOICE is speaking.
   *
   * The narrated walkthrough drives the cursor directly, so no stop is ever "arrived at"
   * during it and the milestone captions never fire -- which would leave whichever caption
   * was last shown sitting under a sentence about something else. The spoken line goes here
   * instead, which also keeps the site's standing rule: a fact that is spoken is on the
   * screen in text at the moment it is spoken, not only in a transcript fold.
   *
   * `showFor()` puts the milestone track back when the voice stops.
   */
  speak(step: number, of: number, text: string): void {
    if (!this.box) return;
    if (this.count) this.count.textContent = `Narration ${step} of ${of}`;
    if (this.title) this.title.textContent = "";
    if (this.body) this.body.textContent = text;
  }

  /** Show whichever caption the cursor is standing in — after a scrub, or on open. */
  showFor(cursor: number): void {
    if (!this.box) return;
    let index = -1;
    this.stops.forEach((stop, at) => { if (stop.at <= cursor) index = at; });
    this.served = index + 1;
    this.render(index);
  }

  private render(index: number): void {
    if (!this.box) return;
    const stop = this.stops[index];
    if (this.count) {
      this.count.textContent = stop
        ? `Step ${index + 1} of ${this.stops.length}`
        : `${this.stops.length} steps`;
    }
    if (this.title) this.title.textContent = stop ? stop.title : "";
    if (this.body) {
      this.body.textContent = stop
        ? stop.text
        : "Press play: the replay stops at each moment below and says what is happening.";
    }
  }
}

/**
 * The chrome every replay shares: a clock, a scrubber, a canvas that resizes,
 * and a method block underneath.
 *
 * Only the drawing differs between the four events, so only the drawing is
 * written four times. A subclass supplies its head, its canvases, its method
 * rows and its `draw()`, and inherits the play loop, the resize handling and
 * the keyboard-reachable slider.
 */
abstract class ReplayChrome implements EventReplayView {
  protected readonly root: HTMLElement;
  private range!: HTMLInputElement;
  private playButton!: HTMLButtonElement;
  protected clock!: HTMLElement;
  private observer!: ResizeObserver;
  private readonly playback = new FrameClock();
  private captions!: CaptionTrack;
  private slider = 0;
  private reduced = false;

  /** Cursor position in the subclass's own units (hours, or minutes). */
  protected cursor = 0;

  /**
   * NOTHING IS BUILT HERE, and that is deliberate rather than tidy.
   *
   * `tsconfig.json` sets `useDefineForClassFields`, so a subclass's constructor
   * parameter properties — `private readonly replay` and friends — are assigned
   * only after `super()` has returned. A base constructor that called
   * `this.markup()` would therefore run subclass code against a subclass whose
   * fields were all still undefined, and every one of these views would throw
   * on mount. The DOM is built in `start()` instead, which the subclass calls
   * once its own fields are real.
   */
  constructor(root: HTMLElement, private readonly limit: number, private readonly stepMillis = 32) {
    this.root = root;
  }

  /** Called by the subclass once its own fields are ready to be drawn from. */
  protected start(): void {
    const root = this.root;
    root.classList.add("replay");
    root.innerHTML = this.markup();
    this.range = root.querySelector<HTMLInputElement>("[data-replay-range]")!;
    this.playButton = root.querySelector<HTMLButtonElement>("[data-replay-play]")!;
    this.clock = root.querySelector<HTMLElement>("[data-replay-clock]")!;

    this.range.min = "0";
    this.range.max = "1000";
    this.range.addEventListener("input", () => {
      this.stop();
      this.slider = Number(this.range.value);
      this.cursor = this.fromSlider(this.slider);
      this.captions.showFor(this.cursor);
      this.draw();
    });
    this.playButton.addEventListener("click", () => (this.playback.running ? this.stop() : this.play()));

    this.captions = new CaptionTrack(root, this.captionsEnabled() ? this.captionStops() : []);
    this.observer = new ResizeObserver(() => this.measureAll());
    this.observer.observe(root);

    this.measureAll();
    // Every replay opens on its final frame, so a visitor who never presses
    // Play still sees the whole result rather than an empty chart. Play rewinds.
    this.cursor = this.limit;
    this.slider = 1000;
    this.range.value = "1000";
    this.captions.showFor(this.cursor);
    this.draw();
  }

  destroy(): void {
    this.stop();
    this.observer?.disconnect();
  }

  /**
   * Where this replay pauses, and what it says there. Empty by default: a view
   * with nothing sourced to say at a stated time shows no caption box at all.
   */
  protected captionStops(): ReplayCaption[] { return []; }

  /**
   * Whether this replay STOPS for its captions.
   *
   * Sean, 2026-08-26, having watched the first captioned build: "most of the
   * historical events are great, it is just the starlink one that I want to
   * fix." That is a judgement about cost, and it is the right one. A caption
   * holds the picture still while it is read. Measured on this repository's
   * own capture harness, that turns the St Patrick's replay from a 4.5 s sweep
   * into a 21.6 s guided tour, and Halloween from 4.5 s into 36.9 s. Where a
   * reader is stranded in front of a chart they cannot parse, that trade is
   * worth making. On a replay he has already looked at and liked, it is an
   * unasked-for change to something that works, and the cost lands on him.
   *
   * So every view still WORKS OUT its stops -- `captionStops()` stays live,
   * sourced and tested on all of them -- and only a view that was asked for
   * them SERVES them. A `CaptionTrack` built with no stops never unhides its
   * plate and never holds the clock, so a view that returns false here plays
   * exactly as it did before any of this landed. Turning them on later is one
   * line: override this to return true.
   *
   * The Starlink replay, the one he asked to have fixed, is `OrbitDecayView`.
   * It is not in this hierarchy and captions unconditionally.
   */
  protected captionsEnabled(): boolean { return false; }

  // ---- the slider is 0..1000 whatever the underlying units are ------------
  /**
   * Some of these axes are logarithmic and a linear slider over a logarithmic
   * axis spends nine tenths of its travel in the last decade. `toSlider` and
   * `fromSlider` are inverses and a subclass overrides both together.
   */
  protected fromSlider(value: number): number { return (value / 1000) * this.limit; }
  protected toSlider(value: number): number { return Math.round((value / this.limit) * 1000); }

  private play(): void {
    if (this.cursor >= this.limit) {
      this.cursor = 0;
      this.captions.rewind();
    }
    this.slider = this.toSlider(this.cursor);
    this.reduced = prefersReducedMotion();
    this.playButton.textContent = "Pause";
    this.playback.start((seconds) => this.advance(seconds));
  }

  /**
   * One frame of playback.
   *
   * The sweep is integrated in SLIDER units rather than in the subclass's own
   * units, and deliberately: two of these axes are logarithmic, the scrubber
   * is logarithmic with them, and sweeping the scrubber at a constant rate is
   * what makes eight minutes and three days both legible on the way past. That
   * is the pacing these four replays were photographed and approved with, and
   * it is unchanged — `6 units every stepMillis` is the same speed written as
   * a rate per second instead of a rate per tick.
   */
  private advance(seconds: number): boolean {
    const perSecond = 6000 / this.stepMillis;
    const slider = this.reduced
      ? this.toSlider(this.captions.nextAt() ?? this.limit)
      : Math.min(1000, this.slider + perSecond * seconds);
    const cursor = slider >= 1000 ? this.limit : this.fromSlider(slider);
    const stop = this.captions.arriving(cursor);
    this.slider = stop ? this.toSlider(stop.at) : slider;
    this.cursor = stop ? stop.at : cursor;
    this.range.value = String(Math.round(this.slider));
    this.draw();
    if (stop) {
      this.playback.hold(stop.dwell);
      return true;
    }
    if (this.slider >= 1000) {
      this.stop();
      return false;
    }
    return true;
  }

  protected stop(): void {
    this.playback.stop();
    if (this.playButton) this.playButton.textContent = this.cursor >= this.limit ? "Replay" : "Play";
  }

  // ---- canvases -----------------------------------------------------------
  /**
   * A canvas sized in CSS pixels with a device-pixel backing store, so a line
   * that says one pixel is one pixel on a phone as well as on a monitor.
   */
  protected fitCanvas(canvas: HTMLCanvasElement, logicalHeight: number): CanvasRenderingContext2D {
    const width = Math.max(280, Math.round(canvas.clientWidth || canvas.parentElement?.clientWidth || 720));
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(logicalHeight * ratio);
    canvas.style.aspectRatio = `${width} / ${logicalHeight}`;
    const context = canvas.getContext("2d")!;
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    return context;
  }

  protected abstract markup(): string;
  protected abstract measureAll(): void;
  protected abstract draw(): void;
}

/** Head row: the clock on the left, live readouts on the right. */
function chromeHead(readouts: Array<{ key: string; label: string; tone?: string }>): string {
  return `
    <div class="replay-head">
      <div class="replay-clock" data-replay-clock></div>
      <div class="replay-tallies">
        ${readouts.map((readout) => `
          <div class="replay-tally${readout.tone ? ` is-${readout.tone}` : ""}">
            <b data-readout="${readout.key}">—</b><span>${escapeHtml(readout.label)}</span>
          </div>`).join("")}
      </div>
    </div>`;
}

/*
 * The caption plate is emitted with the controls, so every view that has a
 * scrubber has a place for a caption. It stays hidden unless that view's
 * `captionStops()` returns something.
 */
const CONTROLS = `${CAPTIONS}
  <div class="replay-controls">
    <button type="button" data-replay-play>Play</button>
    <input type="range" data-replay-range min="0" max="1000" step="1" value="1000"
           aria-label="Replay time" />
  </div>`;

/**
 * A dark plate behind text that has to sit on top of a picture.
 *
 * The density map runs from near-black to near-white depending on the storm, so
 * there is no single label colour that stays legible across it. A plate is the
 * honest fix: it never covers data it is not directly annotating, and the text
 * on it reads at every frame.
 */
function plate(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
): void {
  context.save();
  context.fillStyle = "rgba(2,7,12,0.86)";
  context.fillRect(x, y, width, height);
  context.strokeStyle = "rgba(132,194,214,0.20)";
  context.lineWidth = 1;
  context.strokeRect(x + 0.5, y + 0.5, width - 1, height - 1);
  context.restore();
}

/** Draw one polyline, breaking it wherever the gap exceeds `breakAt`. */
function strokeBroken(
  context: CanvasRenderingContext2D,
  points: Array<[number, number]>,
  x: (value: number) => number,
  y: (value: number) => number,
  breakAt: number,
): void {
  let open = false;
  let previous = Number.NaN;
  context.beginPath();
  for (const [at, value] of points) {
    if (!Number.isFinite(value)) { open = false; continue; }
    if (!open || at - previous > breakAt) context.moveTo(x(at), y(value));
    else context.lineTo(x(at), y(value));
    open = true;
    previous = at;
  }
  context.stroke();
}

// ---------------------------------------------------------------------------
// starlink-2022 — every catalogued member of one launch
// ---------------------------------------------------------------------------

/**
 * Twenty-one real objects. The February 2022 Starlink launch is the closest
 * thing space weather offers to a controlled experiment: forty-nine spacecraft
 * on one vehicle, into one insertion orbit, on one day, and then a storm. The
 * chart is nothing but each catalogued member's own published element sets,
 * converted to perigee and apogee and drawn against time, with the Kp index
 * underneath on the same axis.
 *
 * Nobody has to be told what happened. The traces separate on their own.
 *
 * This view predates `ReplayChrome` and still owns its own play loop, because
 * it is the one replay whose speed is not uniform: it runs slowly through the
 * days where the whole event happens and faster through the climb-out
 * afterwards. It shares the base's `FrameClock` and `CaptionTrack`.
 */

/**
 * Two consecutive samples further apart than this are NOT joined.
 *
 * The published cadence is three-hourly through the first sixteen days and
 * daily afterwards, so the threshold has to clear a legitimate daily step
 * while still catching a real hole in the catalogue. Sixty hours does both.
 */
const GAP_BREAK_HOURS = 60;

/**
 * How fast this replay runs, in event-hours per second of wall clock.
 *
 * The loop this replaces stepped 3 hours per tick until hour 336 and 12 hours
 * per tick afterwards: a FOURFOLD change of speed inside one frame, at a
 * moment nothing on the chart marks, which is the most likely thing anyone
 * means when they say the animation jumps. The INTENT behind it was sound —
 * the days where the event happens should not be rushed, and the fortnight of
 * empty climb-out afterwards should not be dwelt on — so the intent is kept
 * and the step is not. The rate eases from slow to fast with a smoothstep,
 * beginning only AFTER the last object the catalogue lost, so no measured
 * moment is ever sped through and no frame advances four times as far as the
 * frame before it.
 */
const DECAY_SLOW_HOURS_PER_SECOND = 60;
const DECAY_FAST_HOURS_PER_SECOND = 200;
/** How long the change of speed takes. Long enough that no frame shows a step. */
const DECAY_EASE_HOURS = 96;

/**
 * THE OPENING IS SWEPT, NOT HELD.
 *
 * Sean, 2026-08-26, on the deployed page: "the starlink video doesn't play
 * now." It was playing. What he watched was the first caption's hold, taken at
 * hour 0 over a plot that has nothing on it — the catalogue publishes no
 * element set for any of these objects until hour 64.2 — followed immediately
 * by the second caption's hold at hour 9, over the same empty plot. Measured
 * on this repository's capture harness before this change: the cursor did not
 * move for 6.47 s after Play, and the first trace was not drawn until 13.05 s.
 * A picture that stands still for six seconds the instant you press Play is
 * indistinguishable from a broken one, and he read it exactly that way.
 *
 * The fix keeps both captions, keeps them on the moments they belong to, and
 * keeps the reading time they were given. It converts the FIRST hold into a
 * sweep of the same length: the empty run-up to the first element set is
 * crossed slowly enough to read the caption over, rather than held still with
 * the caption on top of it. Every stop before the first drawn element set is
 * therefore served without stopping the clock (`hold: false`), and the rate
 * across that run-up is whatever covers it in the time that first hold used to
 * take. Nothing moves the captions off their own moments, so nothing here can
 * make a false claim about when something happened.
 *
 * A reader who has asked for reduced motion still gets the holds: there is no
 * motion to protect and the dwell is the only thing giving them time to read.
 */
const DECAY_LEADIN_EASE_HOURS = 24;

const PAD = { left: 58, right: 18, top: 18, bottom: 96 };
const DRIVER_HEIGHT = 46;
const DRIVER_GAP = 26;
const LOGICAL_HEIGHT = 430;

function formatClock(base: number, hours: number): string {
  const at = new Date(base + hours * 3600_000);
  const day = String(at.getUTCDate()).padStart(2, "0");
  const hour = String(at.getUTCHours()).padStart(2, "0");
  return `${at.getUTCFullYear()}-${MONTHS[at.getUTCMonth()]}-${day}  ${hour}:00 UTC`;
}

/** The Kp value in force at a given hour: a step function, never interpolated. */
function driverAt(replay: OrbitDecayReplay, hours: number): number | null {
  const { hours: stamps, kp } = replay.driver;
  let value: number | null = null;
  for (let i = 0; i < stamps.length; i += 1) {
    const stamp = stamps[i];
    const level = kp[i];
    if (stamp === undefined || level === undefined || stamp > hours) break;
    value = level;
  }
  return value;
}

class OrbitDecayView implements EventReplayView {
  private readonly canvas: HTMLCanvasElement;
  private readonly context: CanvasRenderingContext2D;
  private readonly range: HTMLInputElement;
  private readonly playButton: HTMLButtonElement;
  private readonly clock: HTMLElement;
  private readonly tallyRaised: HTMLElement;
  private readonly tallyLost: HTMLElement;
  private readonly tallyDriver: HTMLElement;
  private readonly replay: OrbitDecayReplay;
  private readonly baseMillis: number;
  private readonly maxHours: number;
  private readonly resize: ResizeObserver;
  private readonly playback = new FrameClock();
  private readonly captions: CaptionTrack;
  private readonly easeFrom: number;
  private readonly easeTo: number;
  /** The first hour this chart has an element set to draw. 0 if it draws from the start. */
  private readonly firstDrawnHour: number;
  /** Event-hours per second across the empty run-up to that hour. */
  private readonly leadInHoursPerSecond: number;
  private reduced = false;
  /** The spoken walkthrough, when a bed shipped for this event. */
  private narration: ChartNarration | null = null;

  private cursor = 0;
  private width = 900;

  constructor(
    private readonly root: HTMLElement,
    replay: OrbitDecayReplay,
    private readonly milestones: ReplayMilestone[] = [],
    /** The event this chart belongs to. Names the narration bed, if one shipped. */
    private readonly eventId: string = "",
  ) {
    this.replay = replay;
    this.baseMillis = Date.parse(replay.startsAt);
    this.maxHours = (Date.parse(replay.endsAt) - this.baseMillis) / 3600_000;

    root.classList.add("replay");
    root.innerHTML = this.markup();

    this.canvas = root.querySelector("canvas")!;
    this.context = this.canvas.getContext("2d")!;
    this.range = root.querySelector<HTMLInputElement>("[data-replay-range]")!;
    this.playButton = root.querySelector<HTMLButtonElement>("[data-replay-play]")!;
    this.clock = root.querySelector<HTMLElement>("[data-replay-clock]")!;
    this.tallyRaised = root.querySelector<HTMLElement>("[data-tally-raised]")!;
    this.tallyLost = root.querySelector<HTMLElement>("[data-tally-lost]")!;
    this.tallyDriver = root.querySelector<HTMLElement>("[data-tally-driver]")!;

    this.range.max = String(Math.round(this.maxHours));
    this.range.addEventListener("input", () => {
      // Dragging the chart's own scrubber is the reader taking the picture back, so the
      // voice STOPS rather than being seeked to match. Seeking the bed lands mid-word --
      // it is one continuous take, not six files a browser is scheduling -- and a scrub
      // that dropped into one of its silences would give no sign anything had happened.
      // The audio element keeps its own position and its own visible scrubber, so a reader
      // who wants to move about INSIDE the walkthrough drags that instead, and the picture
      // follows it, because the audio is the clock.
      this.narration?.stop();
      this.stop();
      this.cursor = Number(this.range.value);
      this.captions.showFor(this.cursor);
      this.draw();
    });
    this.playButton.addEventListener("click", () => {
      // One clock owns the picture at a time. Play is the silent replay asking for it.
      this.narration?.stop();
      if (this.playback.running) this.stop(); else this.play();
    });

    // The speed only changes once every object this chart can lose has been
    // lost, so the change of pace can never hurry a measurement past a reader.
    const lastLoss = this.lostHours();
    this.easeFrom = lastLoss.length ? (lastLoss[lastLoss.length - 1] as number) : this.maxHours;
    this.easeTo = Math.min(this.maxHours, this.easeFrom + DECAY_EASE_HOURS);

    // The run-up, and the speed that crosses it in the time the caption served
    // over it used to be HELD for. Both are worked out before the caption track
    // is built, because `captionStops()` needs the run-up to know which of its
    // stops must not stop the clock.
    this.firstDrawnHour = this.firstSampleHour();
    const stops = this.captionStops();
    const opening = stops.filter((stop) => stop.hold === false);
    const readingSeconds = opening.length ? dwellMillis(opening[0]!.text) / 1000 : 0;
    this.leadInHoursPerSecond = readingSeconds > 0
      ? Math.min(DECAY_SLOW_HOURS_PER_SECOND, this.firstDrawnHour / readingSeconds)
      : DECAY_SLOW_HOURS_PER_SECOND;

    this.captions = new CaptionTrack(root, stops);

    this.resize = new ResizeObserver(() => this.measure());
    this.resize.observe(root);
    this.measure();

    // The replay opens on its final frame, so a visitor who never presses Play
    // still sees the whole result rather than an empty chart. Play rewinds.
    this.cursor = this.maxHours;
    this.range.value = String(Math.round(this.maxHours));
    this.captions.showFor(this.cursor);
    this.draw();

    this.mountNarration();
  }

  destroy(): void {
    this.narration?.destroy();
    this.narration = null;
    this.stop();
    this.resize.disconnect();
  }

  /** The seam an outside clock drives this picture through. */
  timeline(): ReplayTimeline {
    return {
      seek: (at: number) => {
        // Only if it is actually running: this is called once per frame, and unconditionally
        // rewriting the Play button's label sixty times a second is work for nothing.
        if (this.playback.running) this.stop();
        this.cursor = Math.max(0, Math.min(this.maxHours, at));
        this.range.value = String(Math.round(this.cursor));
        this.draw();
      },
      endsAt: this.maxHours,
    };
  }

  /**
   * The earliest hour ANY object in this chart has an element set for.
   *
   * Before it the plot is genuinely empty — not sparse, empty — and that is a
   * fact about the catalogue rather than about the storm. It is stated in the
   * method block under the picture ("Where the traces start") and it is what
   * the opening sweep is paced against.
   */
  private firstSampleHour(): number {
    const firsts = this.replay.objects
      .map((object) => object.samples[0]?.[0])
      .filter((hour): hour is number => hour !== undefined);
    return firsts.length ? Math.min(...firsts) : 0;
  }

  /** Every hour at which an object's element sets stopped, earliest first. */
  private lostHours(): number[] {
    return this.replay.objects
      .filter((object) => object.outcome === "lost")
      .map((object) => object.samples[object.samples.length - 1]?.[0])
      .filter((hour): hour is number => hour !== undefined)
      .sort((a, b) => a - b);
  }

  /**
   * The hour the driver strip reaches its highest Kp — where the storm rule is drawn.
   *
   * THE PEAK THE STORM STORY IS ABOUT, NOT THE FIRST OF EQUAL SIZE. February 2022
   * reaches Kp 5.33 twice: hour 9, which is BEFORE the launch, and hour 39, the
   * storm that took the spacecraft down. Returning the first match drew the rule at
   * the far left of an empty plot, a day before anything this event is about had
   * happened. It went unnoticed while the chart was silent; the narrated walkthrough
   * says "the storm that arrived the next day" over it and the two plainly disagreed.
   *
   * The peaks are the same value, so the driver series cannot break the tie, and
   * nothing in the payload carries a launch time to break it with either. What is
   * derivable is when the objects become OBSERVABLE — the first published element
   * set — and the useful peak is the LAST one before that: the disturbance that
   * immediately precedes the outcome the chart goes on to draw. For this event that
   * is hour 39 (first element set at 64.18), which is the storm the narration means.
   *
   * Falls back to the last peak in the window, then to the first, so an event whose
   * objects never publish still draws a rule somewhere defensible.
   */
  private peakDriverHour(): number | null {
    const { hours, kp, peakKp } = this.replay.driver;
    const at: number[] = [];
    for (let i = 0; i < hours.length; i += 1) {
      const hour = hours[i];
      if (hour === undefined || hour > 336) break;
      if (kp[i] === peakKp) at.push(hour);
    }
    if (!at.length) return null;
    const observable = this.firstSampleHour();
    const before = observable > 0 ? at.filter((hour) => hour <= observable) : [];
    const chosen = before.length ? before[before.length - 1] : at[at.length - 1];
    return chosen ?? null;
  }

  /**
   * Build the walkthrough, if this event has a bed and its anchors can be derived.
   *
   * Silence is the correct failure. A chart with no bed, or one whose anchors no longer
   * make a monotone timeline, simply keeps the controls it always had -- a reader who never
   * presses the narrated control gets exactly the behaviour that shipped before this.
   */
  private mountNarration(): void {
    const slot = this.root.querySelector<HTMLElement>("[data-replay-narration]");
    if (!slot || !this.eventId) return;
    const timeline = this.timeline();
    this.narration = mountOrbitDecayNarration(
      slot, `${this.eventId}-chart`, this.replay, this.maxHours, {
        seek: (at) => timeline.seek(at),
        say: (step, of, text) => this.captions.speak(step, of, text),
        release: () => this.captions.showFor(this.cursor),
        claim: () => this.stop(),
        reduced: () => prefersReducedMotion(),
      });
  }

  /**
   * Where each milestone's prose belongs on THIS chart's clock.
   *
   * NOT at `milestone.offsetMinutes`. Those offsets are minutes from the
   * event's own narrative origin, and for this event that origin is not the
   * start of the replay window: the third milestone sits at 21 h, and the
   * catalogue publishes no element set for any of these twenty-one objects
   * before 64 h. Timing the captions from the offsets would put two of the
   * four over an empty chart — not a pacing problem but a false claim about
   * when something happened.
   *
   * Each caption is anchored instead to a moment this chart's OWN record
   * defines, taken in milestone order:
   *
   * 1. the start of the window — the launch falls inside its first day, and
   *    the empty plot is itself the fact that the catalogue has not caught up;
   * 2. the hour the Kp strip reaches its highest value — the same moment the
   *    chart already rules and labels as the storm;
   * 3. the first object whose element sets stop — the first cross on the plot;
   * 4. the last one — after which every remaining trace is climbing.
   *
   * A milestone with no such moment gets no caption. It keeps its place in the
   * sourced list under the picture, which is where the full text is anyway.
   */
  private captionStops(): ReplayCaption[] {
    const lost = this.lostHours();
    const anchors: Array<number | null | undefined> = [
      0,
      this.peakDriverHour(),
      lost[0],
      lost[lost.length - 1],
    ];
    const stops: ReplayCaption[] = [];
    let previous = -1;
    this.milestones.forEach((milestone, index) => {
      const at = anchors[index];
      if (at === undefined || at === null || at <= previous || at > this.maxHours) return;
      previous = at;
      stops.push({
        at,
        title: milestone.title,
        text: firstSentences(milestone.description, 170),
        // A stop that lands before the first published element set is shown as
        // the sweep goes past it, never held: see DECAY_LEADIN_EASE_HOURS.
        ...(at < this.firstDrawnHour ? { hold: false } : {}),
      });
    });
    return stops;
  }

  private markup(): string {
    const { counts, driver, provenance } = this.replay;
    return `
      <div class="replay-head">
        <div class="replay-clock" data-replay-clock></div>
        <div class="replay-tallies">
          <div class="replay-tally is-raised"><b data-tally-raised>0</b><span>Raising orbit</span></div>
          <div class="replay-tally is-lost"><b data-tally-lost>0</b><span>Last element set</span></div>
          <div class="replay-tally is-driver"><b data-tally-driver>—</b><span>${driver.label} · ${driver.source}</span></div>
        </div>
      </div>
      <p class="replay-lede">Each of the ${counts.catalogued} catalogued spacecraft is drawn as two thin lines &mdash; the low point and the high point of its orbit, worked out from its own published element sets. Height in kilometres runs up the side; the thirty days from launch run across the bottom; the strip underneath is Kp, the geomagnetic index. A line that climbs is a spacecraft raising its orbit. A line that falls and ends in a cross is one the catalogue stopped publishing for.</p>
      <div class="replay-canvas-wrap"><canvas></canvas></div>
      ${CAPTIONS}
      <div class="replay-controls">
        <button type="button" data-replay-play>Play</button>
        <input type="range" data-replay-range min="0" max="100" step="1" value="0"
               aria-label="Replay time" />
      </div>
      <div class="replay-narration" data-replay-narration></div>
      ${methodBlock([
        ["Drawn from", `${provenance.elements}. ${provenance.elementsNote}`],
        ["Driver", `${provenance.driver}. Peak Kp ${driver.peakKp.toFixed(2)} over ${driver.peakKpWindow} — a G1, the mildest storm level NOAA names.`],
        ["How the altitude is obtained", provenance.method],
        ["Where the traces start", provenance.catalogueStart],
        ["What this cannot show", provenance.limitation],
        ["The count", `${counts.launched} spacecraft were launched and ${counts.publiclyReportedLost} are publicly reported as reentered. This chart draws the ${counts.catalogued} that received a catalogue number: ${counts.raised} raised their orbits and ${counts.lost} stopped producing element sets inside the first fortnight.`],
      ])}
    `;
  }

  private measure(): void {
    const width = Math.max(340, Math.round(this.root.clientWidth || 900));
    if (width === this.width && this.canvas.width) return;
    this.width = width;
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    this.canvas.width = Math.round(width * ratio);
    this.canvas.height = Math.round(LOGICAL_HEIGHT * ratio);
    this.canvas.style.aspectRatio = `${width} / ${LOGICAL_HEIGHT}`;
    this.context.setTransform(ratio, 0, 0, ratio, 0, 0);
    this.draw();
  }

  private play(): void {
    if (this.cursor >= this.maxHours) {
      this.cursor = 0;
      this.captions.rewind();
    }
    this.reduced = prefersReducedMotion();
    this.playButton.textContent = "Pause";
    this.playback.start((seconds) => this.advance(seconds));
  }

  /**
   * How fast the empty run-up is crossed, easing up to the normal rate as the
   * first element sets are drawn. Returns the normal rate everywhere else, so
   * a chart with no empty run-up plays exactly as it always did.
   */
  private openingRate(hours: number): number {
    const from = this.firstDrawnHour;
    if (from <= 0 || this.leadInHoursPerSecond >= DECAY_SLOW_HOURS_PER_SECOND) {
      return DECAY_SLOW_HOURS_PER_SECOND;
    }
    if (hours <= from) return this.leadInHoursPerSecond;
    const to = from + DECAY_LEADIN_EASE_HOURS;
    if (hours >= to) return DECAY_SLOW_HOURS_PER_SECOND;
    const along = Math.max(0, Math.min(1, (hours - from) / (to - from)));
    const eased = along * along * (3 - 2 * along);
    return this.leadInHoursPerSecond
      + (DECAY_SLOW_HOURS_PER_SECOND - this.leadInHoursPerSecond) * eased;
  }

  /** Event-hours per second of wall clock, eased rather than stepped. */
  private rate(hours: number): number {
    const slow = this.openingRate(hours);
    if (this.easeTo <= this.easeFrom) return slow;
    const along = Math.max(0, Math.min(1, (hours - this.easeFrom) / (this.easeTo - this.easeFrom)));
    const eased = along * along * (3 - 2 * along);
    return slow + (DECAY_FAST_HOURS_PER_SECOND - slow) * eased;
  }

  private advance(seconds: number): boolean {
    const target = this.reduced
      ? Math.min(this.maxHours, this.captions.nextAt() ?? this.maxHours)
      : Math.min(this.maxHours, this.cursor + this.rate(this.cursor) * seconds);
    const stop = this.captions.arriving(target);
    this.cursor = stop ? stop.at : target;
    this.range.value = String(Math.round(this.cursor));
    this.draw();
    // A stop marked `hold: false` sits over an empty plot: the caption is
    // shown and the sweep carries on underneath it. A reader who asked for
    // reduced motion gets the hold regardless — the dwell is the only thing
    // giving them time to read.
    if (stop && (stop.hold || this.reduced)) {
      this.playback.hold(stop.dwell);
      return true;
    }
    if (this.cursor >= this.maxHours) {
      this.stop();
      return false;
    }
    return true;
  }

  private stop(): void {
    this.playback.stop();
    this.playButton.textContent = this.cursor >= this.maxHours ? "Replay" : "Play";
  }

  // ---- geometry -----------------------------------------------------------

  private plotWidth(): number { return this.width - PAD.left - PAD.right; }
  private plotHeight(): number { return LOGICAL_HEIGHT - PAD.top - PAD.bottom; }
  private x(hours: number): number { return PAD.left + (hours / this.maxHours) * this.plotWidth(); }

  private y(km: number): number {
    const { min, max } = this.replay.axis;
    const fraction = (km - min) / (max - min);
    return PAD.top + (1 - Math.min(1, Math.max(0, fraction))) * this.plotHeight();
  }

  // ---- drawing ------------------------------------------------------------

  private draw(): void {
    const ctx = this.context;
    ctx.clearRect(0, 0, this.width, LOGICAL_HEIGHT);
    this.drawAtmosphere();
    this.drawGrid();
    this.drawObjects();
    this.drawDriver();
    this.drawStormMarker();
    this.drawCursor();
    this.updateReadout();
  }

  /**
   * A faint darkening toward the bottom of the frame.
   *
   * It carries no number and is labelled with none. Its only job is to stop the
   * chart reading as an abstract plane, because the reason these traces bend is
   * that the bottom of the picture is where the air is. Nothing is inferable
   * from its opacity and nothing on the page refers to it as data.
   */
  private drawAtmosphere(): void {
    const ctx = this.context;
    const gradient = ctx.createLinearGradient(0, PAD.top, 0, PAD.top + this.plotHeight());
    gradient.addColorStop(0, "rgba(41,212,227,0.00)");
    gradient.addColorStop(0.62, "rgba(41,212,227,0.025)");
    gradient.addColorStop(1, "rgba(245,201,106,0.075)");
    ctx.fillStyle = gradient;
    ctx.fillRect(PAD.left, PAD.top, this.plotWidth(), this.plotHeight());
  }

  private drawGrid(): void {
    const ctx = this.context;
    const { min, max } = this.replay.axis;
    ctx.font = '500 10px "IBM Plex Mono", ui-monospace, monospace';
    ctx.textBaseline = "middle";

    for (let km = Math.ceil(min / 50) * 50; km <= max; km += 50) {
      const y = this.y(km);
      ctx.strokeStyle = PALETTE.grid;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(PAD.left, y + 0.5);
      ctx.lineTo(this.width - PAD.right, y + 0.5);
      ctx.stroke();
      ctx.fillStyle = PALETTE.muted;
      ctx.textAlign = "right";
      ctx.fillText(String(km), PAD.left - 10, y);
    }

    ctx.save();
    ctx.translate(16, PAD.top + this.plotHeight() / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = "center";
    ctx.fillStyle = PALETTE.muted;
    ctx.fillText("ALTITUDE  km", 0, 0);
    ctx.restore();

    // Day ticks: weekly labels across a forty-five day window.
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    const axisY = PAD.top + this.plotHeight();
    for (let day = 0; day * 24 <= this.maxHours; day += 5) {
      const x = this.x(day * 24);
      ctx.strokeStyle = PALETTE.grid;
      ctx.beginPath();
      ctx.moveTo(x + 0.5, PAD.top);
      ctx.lineTo(x + 0.5, axisY + 4);
      ctx.stroke();
      const at = new Date(this.baseMillis + day * 24 * 3600_000);
      ctx.fillStyle = PALETTE.muted;
      ctx.fillText(`${MONTHS[at.getUTCMonth()]} ${at.getUTCDate()}`, x, axisY + 8);
    }

    ctx.strokeStyle = PALETTE.gridStrong;
    ctx.beginPath();
    ctx.moveTo(PAD.left, axisY + 0.5);
    ctx.lineTo(this.width - PAD.right, axisY + 0.5);
    ctx.stroke();
  }

  private drawObjects(): void {
    const ctx = this.context;
    // Lost first, raised on top: by the end of the replay the surviving traces
    // are the ones the eye should be able to follow out of the crowd.
    const order = [...this.replay.objects].sort((a, b) => (a.outcome === "lost" ? -1 : 1) - (b.outcome === "lost" ? -1 : 1));

    for (const object of order) {
      const visible = object.samples.filter((sample) => sample[0] <= this.cursor);
      if (visible.length === 0) continue;
      const lost = object.outcome === "lost";

      ctx.strokeStyle = lost ? PALETTE.lost : PALETTE.raised;
      ctx.lineJoin = "round";
      ctx.lineCap = "round";

      // Apogee first and faint, perigee over it and solid. Two thin lines per
      // object rather than a filled band between them: with twenty-one objects
      // the fills overlapped into two coloured smears that hid the very traces
      // they were meant to describe, and a fill drawn only up to the cursor
      // ends in a hard vertical edge that reads as a rectangle rather than as
      // a moment in time. Two lines carry the same fact — the gap between them
      // closing IS the orbit circularising — and stay legible when twenty of
      // them overlap.
      ctx.lineWidth = 1;
      ctx.globalAlpha = 0.3;
      this.eachRun(visible, (run) => this.strokeRun(run, 2));
      ctx.lineWidth = 1.6;
      ctx.globalAlpha = 0.86;
      this.eachRun(visible, (run) => this.strokeRun(run, 1));
      ctx.globalAlpha = 1;

      const last = visible[visible.length - 1];
      if (!last) continue;
      const head = { x: this.x(last[0]), y: this.y(last[1]) };
      const finished = last === object.samples[object.samples.length - 1];

      if (lost && finished) {
        // The catalogue's last word on this object. Not a computed reentry
        // time — the point at which space-track stopped publishing for it.
        ctx.strokeStyle = PALETTE.lost;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(head.x - 4, head.y - 4);
        ctx.lineTo(head.x + 4, head.y + 4);
        ctx.moveTo(head.x + 4, head.y - 4);
        ctx.lineTo(head.x - 4, head.y + 4);
        ctx.stroke();
      } else if (!finished) {
        ctx.fillStyle = lost ? PALETTE.lost : PALETTE.raised;
        ctx.beginPath();
        ctx.arc(head.x, head.y, 2.4, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    this.drawFamilyLabels();
  }

  /** Stroke one unbroken run, taking either the perigee or the apogee column. */
  private strokeRun(run: ReplaySample[], column: 1 | 2): void {
    const ctx = this.context;
    ctx.beginPath();
    run.forEach((sample, index) => {
      const x = this.x(sample[0]);
      const y = this.y(sample[column]);
      if (index === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();
  }

  /** Split one object's visible samples into unbroken runs at real gaps. */
  private eachRun(samples: ReplaySample[], render: (run: ReplaySample[]) => void): void {
    let run: ReplaySample[] = [];
    for (const sample of samples) {
      const previous = run[run.length - 1];
      if (previous && sample[0] - previous[0] > GAP_BREAK_HOURS) {
        if (run.length > 1) render(run);
        run = [];
      }
      run.push(sample);
    }
    if (run.length > 1) render(run);
  }

  /**
   * Name each family where its own traces are, not in a corner.
   *
   * A legend in the top-left makes the reader carry a colour across the frame.
   * These sit at the leading edge of the group they name, so the label and the
   * thing it names are the same glance.
   */
  private drawFamilyLabels(): void {
    const ctx = this.context;
    ctx.font = '600 10px "IBM Plex Mono", ui-monospace, monospace';
    ctx.textBaseline = "middle";

    const heads = (outcome: "lost" | "raised") => this.replay.objects
      .filter((object) => object.outcome === outcome)
      .map((object) => object.samples.filter((sample) => sample[0] <= this.cursor))
      .filter((visible) => visible.length > 0)
      .map((visible) => visible[visible.length - 1])
      .filter((sample): sample is ReplaySample => sample !== undefined);

    const raised = heads("raised");
    if (raised.length) {
      const x = Math.max(...raised.map((sample) => this.x(sample[0])));
      const y = Math.min(...raised.map((sample) => this.y(sample[2])));
      ctx.fillStyle = PALETTE.raised;
      ctx.textAlign = x > this.width - PAD.right - 150 ? "right" : "left";
      ctx.fillText(`${raised.length} RAISING ORBIT`, x + (ctx.textAlign === "right" ? -8 : 8), y - 12);
    }

    const gone = this.replay.objects.filter((object) => {
      const final = object.samples[object.samples.length - 1];
      return object.outcome === "lost" && final !== undefined && final[0] <= this.cursor;
    });
    if (gone.length) {
      const last = gone
        .map((object) => object.samples[object.samples.length - 1])
        .filter((sample): sample is ReplaySample => sample !== undefined);
      const x = Math.max(...last.map((sample) => this.x(sample[0])));
      const y = Math.max(...last.map((sample) => this.y(sample[1])));
      ctx.fillStyle = PALETTE.lost;
      ctx.textAlign = "left";
      ctx.fillText(`${gone.length} LAST ELEMENT SET`, x + 10, y + 6);
    }
  }

  /**
   * The storm, marked where it happened.
   *
   * Without this the reader has to find the tallest bar in a strip of two
   * hundred and forty and carry that x-position up into the chart. The whole
   * argument of the picture is that this small disturbance did that, so the
   * moment gets a line through both halves of the frame and its own number.
   */
  private drawStormMarker(): void {
    const ctx = this.context;
    const { peakKp } = this.replay.driver;
    const peakHour = this.peakDriverHour();
    if (peakHour === null || peakHour > this.cursor) return;

    const x = this.x(peakHour);
    ctx.strokeStyle = "rgba(245,201,106,0.42)";
    ctx.setLineDash([2, 4]);
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x + 0.5, PAD.top);
    ctx.lineTo(x + 0.5, PAD.top + this.plotHeight() + DRIVER_GAP + DRIVER_HEIGHT);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.font = '600 10px "IBM Plex Mono", ui-monospace, monospace';
    ctx.textAlign = "left";
    ctx.textBaseline = "top";
    ctx.fillStyle = PALETTE.driver;
    ctx.fillText(`Kp ${peakKp.toFixed(2)}  ·  G1`, x + 7, PAD.top + 4);
  }

  private drawDriver(): void {
    const ctx = this.context;
    const top = PAD.top + this.plotHeight() + DRIVER_GAP;
    const { hours, kp } = this.replay.driver;
    const step = this.plotWidth() / ((this.maxHours / 3) || 1);
    const barWidth = Math.max(1.5, step - 0.6);

    ctx.font = '500 9px "IBM Plex Mono", ui-monospace, monospace';
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    ctx.fillStyle = PALETTE.muted;
    ctx.fillText("Kp", PAD.left - 10, top + DRIVER_HEIGHT / 2);

    // Kp 5 is the G1 line: the level at which NOAA first calls it a storm.
    const stormY = top + DRIVER_HEIGHT * (1 - 5 / 9);
    ctx.strokeStyle = "rgba(245,201,106,0.34)";
    ctx.setLineDash([3, 3]);
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(PAD.left, stormY + 0.5);
    ctx.lineTo(this.width - PAD.right, stormY + 0.5);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.textAlign = "left";
    ctx.fillStyle = "rgba(245,201,106,0.7)";
    ctx.fillText("G1", this.width - PAD.right - 18, stormY - 7);

    for (let i = 0; i < hours.length; i += 1) {
      const hour = hours[i];
      const level = kp[i];
      if (hour === undefined || level === undefined || hour > this.maxHours) break;
      const height = Math.max(1, (level / 9) * DRIVER_HEIGHT);
      const x = this.x(hour);
      const reached = hour <= this.cursor;
      ctx.fillStyle = reached
        ? (level >= 5 ? PALETTE.driver : "rgba(245,201,106,0.55)")
        : "rgba(245,201,106,0.13)";
      ctx.fillRect(x, top + DRIVER_HEIGHT - height, barWidth, height);
    }

    ctx.strokeStyle = PALETTE.grid;
    ctx.beginPath();
    ctx.moveTo(PAD.left, top + DRIVER_HEIGHT + 0.5);
    ctx.lineTo(this.width - PAD.right, top + DRIVER_HEIGHT + 0.5);
    ctx.stroke();
  }

  private drawCursor(): void {
    if (this.cursor <= 0) return;
    const ctx = this.context;
    const x = this.x(this.cursor);
    ctx.strokeStyle = "rgba(237,248,251,0.30)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x + 0.5, PAD.top);
    ctx.lineTo(x + 0.5, PAD.top + this.plotHeight() + DRIVER_GAP + DRIVER_HEIGHT);
    ctx.stroke();
  }

  private updateReadout(): void {
    this.clock.textContent = formatClock(this.baseMillis, this.cursor);

    const raising = this.replay.objects.filter((object) => {
      const first = object.samples[0];
      return object.outcome === "raised" && first !== undefined && first[0] <= this.cursor;
    }).length;
    const stopped = this.replay.objects.filter((object) => {
      const final = object.samples[object.samples.length - 1];
      return object.outcome === "lost" && final !== undefined && final[0] <= this.cursor;
    }).length;

    this.tallyRaised.textContent = String(raising);
    this.tallyLost.textContent = String(stopped);
    const kp = driverAt(this.replay, this.cursor);
    this.tallyDriver.textContent = kp === null ? "—" : kp.toFixed(2);
  }
}

// ---------------------------------------------------------------------------
// gannon-2024 — the air swells, and a spacecraft feels it
// ---------------------------------------------------------------------------

/**
 * Two pictures of the same four days, side by side, in two different evidence
 * classes, and the page never lets them blur into one another.
 *
 * **Left, the map.** WAM-IPE's density at 400 km, divided cell by cell by the
 * same cell's mean on the quiet day. Dividing is what makes it legible: the raw
 * field is dominated by the day/night bulge, which is not the storm, and which
 * would be the only thing an animation of raw density showed. What is left after
 * the division is what the storm did. It is model output from end to end and it
 * carries no measurement anywhere, which the label says.
 *
 * **Right, the curves.** Swarm-C's own accelerometer against WAM-IPE read at
 * Swarm-C's own latitude, longitude and altitude — the same physical quantity at
 * the same point, so the comparison is fair rather than rhetorical. The solid
 * line is the measurement. The dashed line is the forecast. They part company
 * during the storm and that parting is the reason this replay exists.
 *
 * **The whiskers.** WAM publishes four cycles a day and most valid times are
 * covered by more than one. Where the archive holds the previous cycle's
 * forecast for the same moment, it is drawn as a tick from the fresh value to
 * the stale one. On the quiet days there is nothing to see. Through the recovery
 * the model disagrees with its own six-hour-old self by a factor of three. That
 * is honest, free uncertainty on a model layer and it is never averaged away,
 * because the average would be a trajectory neither run produced.
 */
class ThermosphereInflationView extends ReplayChrome {
  private mapCanvas!: HTMLCanvasElement;
  private chartCanvas!: HTMLCanvasElement;
  private mapContext!: CanvasRenderingContext2D;
  private chartContext!: CanvasRenderingContext2D;
  private mapHeight = 240;
  private chartHeight = 360;
  private readonly tile: HTMLCanvasElement;
  private readonly frames: Uint8Array[];
  private readonly baseMillis: number;
  private readonly maxHours: number;

  constructor(root: HTMLElement, private readonly replay: ThermosphereInflationReplay) {
    super(root, (Date.parse(replay.endsAt) - Date.parse(replay.startsAt)) / 3600_000);
    this.baseMillis = Date.parse(replay.startsAt);
    this.maxHours = (Date.parse(replay.endsAt) - this.baseMillis) / 3600_000;
    this.frames = replay.map.frames.map((frame) => {
      const binary = atob(frame);
      const bytes = new Uint8Array(binary.length);
      for (let index = 0; index < binary.length; index += 1) {
        bytes[index] = binary.charCodeAt(index);
      }
      return bytes;
    });
    this.tile = document.createElement("canvas");
    this.tile.width = replay.map.lonCount;
    this.tile.height = replay.map.latCount;
    this.start();
  }

  protected markup(): string {
    const { series, driver, findings, provenance, map } = this.replay;
    return `
      ${chromeHead([
        { key: "measured", label: "Swarm-C · measured", tone: "raised" },
        { key: "model", label: "WAM-IPE · forecast", tone: "driver" },
        { key: "sml", label: `${driver.label} · ${driver.source}`, tone: "lost" },
      ])}
      <div class="replay-panels">
        <figure class="replay-panel">
          <canvas data-canvas="map"></canvas>
          <figcaption>
            <span class="replay-badge is-model">Model</span>
            ${escapeHtml(map.label)}
          </figcaption>
        </figure>
        <figure class="replay-panel">
          <canvas data-canvas="chart"></canvas>
          <figcaption>
            <span class="replay-badge is-measured">Measured</span>
            <span class="replay-badge is-model">Model</span>
            ${escapeHtml(series.measured.detail)}, against the forecast at the same point
          </figcaption>
        </figure>
      </div>
      ${CONTROLS}
      <div class="replay-figures">
        <div><b>×${findings.measuredPeak.toFixed(2)}</b><span>the drag Swarm-C felt at the peak, against its quiet day</span></div>
        <div><b>×${findings.globalPeak.toFixed(2)}</b><span>model global mean at 400 km, ${utcStamp(Date.parse(findings.globalPeakAt))}</span></div>
        <div><b>×${findings.globalTrough.toFixed(2)}</b><span>and then thinner than before it started, two days later</span></div>
        <div><b>${Math.round(driver.peak).toLocaleString()} nT</b><span>peak westward electrojet, ${utcStamp(Date.parse(driver.peakAt))}</span></div>
      </div>
      ${methodBlock([
        ["Measured", provenance.measured],
        ["Model", provenance.model],
        ["Which cycle", provenance.cycleRule],
        ["Driver", driver.citation],
        ["How they are compared", provenance.method],
        ["What this means for drag", provenance.drag],
        ["What this cannot show", provenance.limitation],
      ])}`;
  }

  protected measureAll(): void {
    this.mapCanvas ??= this.root.querySelector<HTMLCanvasElement>("[data-canvas=map]")!;
    this.chartCanvas ??= this.root.querySelector<HTMLCanvasElement>("[data-canvas=chart]")!;
    const width = Math.max(280, this.mapCanvas.parentElement?.clientWidth ?? 640);
    this.mapHeight = Math.round(width / 2);
    this.chartHeight = Math.max(300, Math.min(420, Math.round(width * 0.72)));
    this.mapContext = this.fitCanvas(this.mapCanvas, this.mapHeight);
    this.chartContext = this.fitCanvas(this.chartCanvas, this.chartHeight);
    this.draw();
  }

  protected draw(): void {
    this.drawMap();
    this.drawChart();
    this.updateReadout();
  }

  // ---- the map ------------------------------------------------------------

  /**
   * The ratio ramp. One is nearly black, because "nothing changed here" should
   * not glow; deviation in either direction lights up, thinner toward violet
   * and thicker toward amber and then white. So the picture is literally a map
   * of where the storm changed the air, and the quiet parts get out of the way.
   */
  private ramp(ratio: number): [number, number, number] {
    const stops: Array<[number, [number, number, number]]> = [
      [0.35, [169, 140, 255]],
      [0.75, [58, 62, 110]],
      [1.0, [10, 22, 30]],
      [1.6, [41, 212, 227]],
      [2.6, [245, 201, 106]],
      [4.5, [255, 240, 214]],
      [8.0, [255, 255, 255]],
    ];
    const key = Math.log2(Math.max(0.2, Math.min(9, ratio)));
    for (let index = 0; index < stops.length - 1; index += 1) {
      const current = stops[index];
      const next = stops[index + 1];
      if (!current || !next) break;
      const [lowRatio, low] = current;
      const [highRatio, high] = next;
      const lo = Math.log2(lowRatio);
      const hi = Math.log2(highRatio);
      if (key <= hi || index === stops.length - 2) {
        const t = Math.max(0, Math.min(1, (key - lo) / (hi - lo)));
        return [
          Math.round(low[0] + (high[0] - low[0]) * t),
          Math.round(low[1] + (high[1] - low[1]) * t),
          Math.round(low[2] + (high[2] - low[2]) * t),
        ];
      }
    }
    return [255, 255, 255];
  }

  private frameIndex(): number {
    const { hours } = this.replay.map;
    let index = 0;
    for (let step = 0; step < hours.length; step += 1) {
      const hour = hours[step];
      if (hour === undefined || hour > this.cursor) break;
      index = step;
    }
    return index;
  }

  private drawMap(): void {
    const context = this.mapContext;
    const width = this.mapCanvas.clientWidth || this.mapCanvas.width;
    const height = this.mapHeight;
    const { lonCount, latCount, noData } = this.replay.map;
    const bytes = this.frames[this.frameIndex()] ?? new Uint8Array(lonCount * latCount).fill(noData);

    context.clearRect(0, 0, width, height);
    context.fillStyle = "#02070c";
    context.fillRect(0, 0, width, height);

    // The field is painted at cell resolution into an off-screen tile and then
    // scaled up with the browser's own smoothing. Drawing 1,395 rectangles by
    // hand would give a grid of hard squares and imply a resolution the model
    // does not have; a smooth interpolation implies exactly the resolution it
    // does. Row zero of the payload is the southernmost latitude, so the tile
    // is written bottom-up to put north at the top.
    const tileContext = this.tile.getContext("2d")!;
    const image = tileContext.createImageData(lonCount, latCount);
    const { log2Min, log2Span } = this.replay.map;
    for (let row = 0; row < latCount; row += 1) {
      for (let column = 0; column < lonCount; column += 1) {
        const value = bytes[row * lonCount + column] ?? noData;
        const target = ((latCount - 1 - row) * lonCount + column) * 4;
        if (value === noData) {
          image.data[target] = 12; image.data[target + 1] = 18; image.data[target + 2] = 24;
          image.data[target + 3] = 255;
          continue;
        }
        const ratio = 2 ** (log2Min + (value / 254) * log2Span);
        const [red, green, blue] = this.ramp(ratio);
        image.data[target] = red;
        image.data[target + 1] = green;
        image.data[target + 2] = blue;
        image.data[target + 3] = 255;
      }
    }
    tileContext.putImageData(image, 0, 0);
    context.imageSmoothingEnabled = true;
    context.imageSmoothingQuality = "high";
    // Half a cell of bleed on every side so the smoothing samples cell centres
    // rather than edges, which is where a half-cell shift in the coastline
    // registration would come from.
    const cellWidth = width / lonCount;
    const cellHeight = height / latCount;
    context.drawImage(this.tile, -cellWidth / 2, -cellHeight / 2, width + cellWidth, height + cellHeight);

    this.drawCoastlines(context, width, height);
    this.drawMapChrome(context, width, height);
  }

  private drawCoastlines(context: CanvasRenderingContext2D, width: number, height: number): void {
    const { lonStart } = this.replay.map;
    const project = (lon: number, lat: number): [number, number] => {
      let east = lon - lonStart;
      while (east < 0) east += 360;
      while (east >= 360) east -= 360;
      return [(east / 360) * width, ((90 - lat) / 180) * height];
    };
    context.save();
    context.strokeStyle = "rgba(2,7,12,0.72)";
    context.lineWidth = 1.4;
    context.lineJoin = "round";
    for (const ring of worldOutlines().land) {
      context.beginPath();
      let previousX = Number.NaN;
      ring.forEach(([lon, lat], index) => {
        const [x, y] = project(lon, lat);
        // A polygon that crosses the seam would otherwise be drawn back across
        // the whole map as a horizontal bar.
        if (index === 0 || Math.abs(x - previousX) > width / 2) context.moveTo(x, y);
        else context.lineTo(x, y);
        previousX = x;
      });
      context.stroke();
    }
    context.restore();
  }

  private drawMapChrome(context: CanvasRenderingContext2D, width: number, height: number): void {
    context.save();
    context.strokeStyle = "rgba(237,248,251,0.16)";
    context.lineWidth = 1;
    context.setLineDash([2, 5]);
    for (const lat of [-60, -30, 0, 30, 60]) {
      const y = ((90 - lat) / 180) * height;
      context.beginPath();
      context.moveTo(0, y + 0.5);
      context.lineTo(width, y + 0.5);
      context.stroke();
    }
    context.setLineDash([]);

    // The colour key, inside the frame, because a legend a scroll away from
    // the picture is a legend nobody reads.
    const keyWidth = Math.min(190, width * 0.42);
    const keyHeight = 8;
    const left = 20;
    const top = height - 28;
    plate(context, left - 8, top - 8, keyWidth + 16, keyHeight + 26);
    for (let step = 0; step <= keyWidth; step += 1) {
      const ratio = 2 ** (-1.4 + (step / keyWidth) * (Math.log2(6) + 1.4));
      const [red, green, blue] = this.ramp(ratio);
      context.fillStyle = `rgb(${red},${green},${blue})`;
      context.fillRect(left + step, top, 1.4, keyHeight);
    }
    context.strokeStyle = "rgba(237,248,251,0.28)";
    context.lineWidth = 1;
    context.strokeRect(left - 0.5, top - 0.5, keyWidth + 1, keyHeight + 1);
    context.font = `500 9px ${MONO}`;
    context.fillStyle = PALETTE.muted;
    context.textBaseline = "top";
    context.textAlign = "left";
    context.fillText("×0.4", left, top + keyHeight + 4);
    context.textAlign = "center";
    context.fillText("×1", left + keyWidth * (1.4 / (Math.log2(6) + 1.4)), top + keyHeight + 4);
    context.textAlign = "right";
    context.fillText("×6", left + keyWidth, top + keyHeight + 4);

    // The frame's own valid time. The map is two-hourly and the clock above the
    // picture is not, so without this the reader cannot tell which of the two
    // hours they are looking at. It goes beside the title on a wide panel and
    // under it on a narrow one, because at phone width the two plates otherwise
    // overlap and neither is readable.
    const frameHours = this.replay.map.hours[this.frameIndex()] ?? 0;
    const stamp = utcStamp(this.baseMillis + frameHours * 3600_000);
    const stacked = width < 430;
    plate(context, 12, 8, 200, stacked ? 48 : 34);
    context.textAlign = "left";
    context.textBaseline = "top";
    context.font = `600 10px ${MONO}`;
    context.fillStyle = "rgba(237,248,251,0.92)";
    context.fillText("400 km · WAM-IPE forecast", 20, 14);
    context.font = `500 9px ${MONO}`;
    context.fillStyle = PALETTE.muted;
    context.fillText("model output · no measurement in it", 20, 28);
    context.font = `500 10px ${MONO}`;
    if (stacked) {
      context.fillStyle = "rgba(237,248,251,0.88)";
      context.fillText(stamp, 20, 42);
    } else {
      const stampWidth = context.measureText(stamp).width + 16;
      plate(context, width - stampWidth - 12, 8, stampWidth, 20);
      context.fillStyle = "rgba(237,248,251,0.88)";
      context.fillText(stamp, width - stampWidth - 4, 13);
    }
    context.restore();
  }

  // ---- the curves ---------------------------------------------------------

  private drawChart(): void {
    const context = this.chartContext;
    const width = this.chartCanvas.clientWidth || this.chartCanvas.width;
    const height = this.chartHeight;
    const pad = { left: 46, right: 34, top: 26, bottom: 92 };
    const driverHeight = 42;
    const plotWidth = width - pad.left - pad.right;
    const plotHeight = height - pad.top - pad.bottom;
    const { min, max } = this.replay.axis;

    const x = (hours: number) => pad.left + (hours / this.maxHours) * plotWidth;
    const y = (ratio: number) =>
      pad.top + (1 - Math.max(0, Math.min(1, (ratio - min) / (max - min)))) * plotHeight;

    context.clearRect(0, 0, width, height);

    // Horizontal rules at whole multiples, and the one at ×1 drawn stronger,
    // because "the same as the quiet day" is the only line on this axis that
    // means something on its own.
    context.font = `500 10px ${MONO}`;
    context.textBaseline = "middle";
    for (let ratio = 1; ratio <= max; ratio += 1) {
      const at = y(ratio);
      context.strokeStyle = ratio === 1 ? PALETTE.gridStrong : PALETTE.grid;
      context.lineWidth = 1;
      context.beginPath();
      context.moveTo(pad.left, at + 0.5);
      context.lineTo(width - pad.right, at + 0.5);
      context.stroke();
      context.fillStyle = ratio === 1 ? "rgba(237,248,251,0.75)" : PALETTE.muted;
      context.textAlign = "right";
      context.fillText(`×${ratio}`, pad.left - 8, at);
    }
    context.textAlign = "left";
    context.fillStyle = "rgba(237,248,251,0.6)";
    context.font = `500 9px ${MONO}`;
    context.fillText("the quiet day", pad.left + 6, y(1) - 9);

    // Day ticks along the bottom of the plot.
    const axisY = pad.top + plotHeight;
    context.textAlign = "center";
    context.textBaseline = "top";
    context.font = `500 10px ${MONO}`;
    for (let hours = 0; hours <= this.maxHours; hours += 24) {
      const at = x(hours);
      context.strokeStyle = PALETTE.grid;
      context.beginPath();
      context.moveTo(at + 0.5, pad.top);
      context.lineTo(at + 0.5, axisY + 4);
      context.stroke();
      const when = new Date(this.baseMillis + hours * 3600_000);
      context.fillStyle = PALETTE.muted;
      context.fillText(`${MONTHS[when.getUTCMonth()]} ${when.getUTCDate()}`, at, axisY + 8);
    }
    context.strokeStyle = PALETTE.gridStrong;
    context.beginPath();
    context.moveTo(pad.left, axisY + 0.5);
    context.lineTo(width - pad.right, axisY + 0.5);
    context.stroke();

    const visible = (points: Array<[number, number, number]>) =>
      points.filter((point) => point[0] <= this.cursor).map(([at, ratio]) => [at, ratio] as [number, number]);

    // The forecast first and dashed, the measurement over it and solid: where
    // they overlap the eye should end up on the measurement.
    const model = visible(this.replay.series.model.points);
    context.strokeStyle = PALETTE.model;
    context.lineWidth = 1.6;
    context.setLineDash([5, 4]);
    context.lineJoin = "round";
    strokeBroken(context, model, x, y, 3.5);
    context.setLineDash([]);

    this.drawSpread(context, x, y);

    const measured = visible(this.replay.series.measured.points);
    context.strokeStyle = PALETTE.measured;
    context.lineWidth = 2.2;
    strokeBroken(context, measured, x, y, 3.5);

    for (const [series, colour] of [[measured, PALETTE.measured], [model, PALETTE.model]] as const) {
      const head = series[series.length - 1];
      if (!head) continue;
      context.fillStyle = colour;
      context.beginPath();
      context.arc(x(head[0]), y(head[1]), 3, 0, Math.PI * 2);
      context.fill();
    }

    this.drawLegend(context, pad.left + 8, pad.top + 6);
    this.drawDriver(context, x, width, pad, plotHeight, driverHeight);

    // The cursor, through both halves of the frame.
    if (this.cursor > 0 && this.cursor < this.maxHours) {
      context.strokeStyle = "rgba(237,248,251,0.28)";
      context.lineWidth = 1;
      context.beginPath();
      context.moveTo(x(this.cursor) + 0.5, pad.top);
      context.lineTo(x(this.cursor) + 0.5, axisY + 26 + driverHeight);
      context.stroke();
    }
  }

  /**
   * The forecast against its own six-hour-old self.
   *
   * A tick from the value the fresh cycle produced to the value the previous
   * cycle produced for the same minute. On the quiet days the tick has no
   * length. Through the recovery it is longer than the distance between the
   * two curves, which is the point: before asking whether the model matched the
   * spacecraft, ask whether it matched itself.
   */
  private drawSpread(
    context: CanvasRenderingContext2D,
    x: (hours: number) => number,
    y: (ratio: number) => number,
  ): void {
    const spread = this.replay.series.model.spread ?? [];
    const fresh = new Map(this.replay.series.model.points.map((point) => [point[0], point[1]]));
    context.save();
    context.strokeStyle = "rgba(245,201,106,0.55)";
    context.lineWidth = 1;
    for (const [hours, stale] of spread) {
      if (hours > this.cursor) continue;
      const now = fresh.get(hours);
      if (now === undefined) continue;
      const top = y(Math.max(now, stale));
      const bottom = y(Math.min(now, stale));
      if (bottom - top < 2) continue;
      const at = x(hours);
      context.beginPath();
      context.moveTo(at + 0.5, top);
      context.lineTo(at + 0.5, bottom);
      context.moveTo(at - 2.5, top + 0.5);
      context.lineTo(at + 3.5, top + 0.5);
      context.moveTo(at - 2.5, bottom - 0.5);
      context.lineTo(at + 3.5, bottom - 0.5);
      context.stroke();
    }
    context.restore();
  }

  private drawLegend(context: CanvasRenderingContext2D, left: number, top: number): void {
    const rows: Array<[string, string, boolean]> = [
      [PALETTE.measured, "Swarm-C · measured", false],
      [PALETTE.model, "WAM-IPE · forecast", true],
    ];
    context.save();
    context.font = `500 10px ${MONO}`;
    context.textBaseline = "middle";
    context.textAlign = "left";
    rows.forEach(([colour, label, dashed], index) => {
      const y = top + index * 15;
      context.strokeStyle = colour;
      context.lineWidth = dashed ? 1.6 : 2.2;
      context.setLineDash(dashed ? [5, 4] : []);
      context.beginPath();
      context.moveTo(left, y);
      context.lineTo(left + 22, y);
      context.stroke();
      context.setLineDash([]);
      context.fillStyle = "rgba(237,248,251,0.78)";
      context.fillText(label, left + 29, y);
    });
    context.restore();
  }

  /**
   * The electrojet underneath, hanging downward because SML is negative and
   * drawing it upward would invert the one index on the page whose sign is its
   * meaning.
   */
  private drawDriver(
    context: CanvasRenderingContext2D,
    x: (hours: number) => number,
    width: number,
    pad: { left: number; right: number; top: number; bottom: number },
    plotHeight: number,
    driverHeight: number,
  ): void {
    const top = pad.top + plotHeight + 26;
    const { points, peak } = this.replay.driver;
    const floor = Math.min(-500, peak);
    const y = (value: number) => top + Math.max(0, Math.min(1, value / floor)) * driverHeight;

    context.save();
    context.beginPath();
    context.moveTo(x(0), top);
    let open = false;
    for (const [hours, value] of points) {
      if (hours > this.cursor) break;
      const at = x(hours);
      if (!open) { context.lineTo(at, y(value)); open = true; }
      else context.lineTo(at, y(value));
    }
    const last = points.filter((point) => point[0] <= this.cursor).slice(-1)[0];
    if (open && last) {
      context.lineTo(x(last[0]), top);
      context.closePath();
      context.fillStyle = "rgba(255,123,120,0.30)";
      context.fill();
      context.strokeStyle = "rgba(255,123,120,0.85)";
      context.lineWidth = 1;
      context.stroke();
    }
    context.strokeStyle = PALETTE.grid;
    context.beginPath();
    context.moveTo(pad.left, top + 0.5);
    context.lineTo(width - pad.right, top + 0.5);
    context.stroke();
    context.font = `500 9px ${MONO}`;
    context.textAlign = "right";
    context.textBaseline = "top";
    context.fillStyle = PALETTE.muted;
    context.fillText("SML", pad.left - 8, top + 2);
    context.fillText(`${Math.round(floor)}`, pad.left - 8, top + driverHeight - 8);
    context.textAlign = "left";
    context.fillStyle = "rgba(255,123,120,0.75)";
    context.fillText("westward electrojet · measured, ~500 magnetometers", pad.left + 6, top + driverHeight + 6);
    context.restore();
  }

  private valueAt(points: Array<[number, number, number]> | Array<[number, number]>): number | null {
    let value: number | null = null;
    for (const point of points as Array<[number, number]>) {
      if (point[0] > this.cursor) break;
      value = point[1];
    }
    return value;
  }

  private updateReadout(): void {
    this.clock.textContent = utcStamp(this.baseMillis + this.cursor * 3600_000);
    const set = (key: string, text: string) => {
      const node = this.root.querySelector<HTMLElement>(`[data-readout="${key}"]`);
      if (node) node.textContent = text;
    };
    const measured = this.valueAt(this.replay.series.measured.points);
    const model = this.valueAt(this.replay.series.model.points);
    const sml = this.valueAt(this.replay.driver.points);
    set("measured", measured === null ? "—" : `×${measured.toFixed(2)}`);
    set("model", model === null ? "—" : `×${model.toFixed(2)}`);
    set("sml", sml === null ? "—" : `${Math.round(sml)} nT`);
  }
}

// ---------------------------------------------------------------------------
// halloween-2003 — three arrivals, three clocks
// ---------------------------------------------------------------------------

/**
 * One eruption. Three things arrive at Earth. They arrive minutes, hours and
 * days apart, and almost every operational mistake in space weather comes from
 * treating them as one event.
 *
 * The x-axis is logarithmic in time from the moment the flare's light left the
 * Sun, and that is the whole design rather than a presentation choice. On a
 * linear axis over five days the flare is thinner than the axis line and the
 * proton onset is inside it. On a logarithmic axis eight minutes, one hour,
 * nineteen hours and two and a half days are all legible at once and the
 * SEPARATIONS are what the eye reads — which is the lesson.
 *
 * The zero of that axis is the only calculated time on the page: the observed
 * X-ray peak minus 499 seconds, the light travel time over one astronomical
 * unit. It is stated as such under the picture rather than folded in silently.
 *
 * The scrubber moves logarithmically too, because a linear scrubber over this
 * axis would spend nine tenths of its travel inside the last day.
 */
class ThreeClocksView extends ReplayChrome {
  private canvas!: HTMLCanvasElement;
  private context!: CanvasRenderingContext2D;
  private height = 430;
  private readonly originMillis: number;
  private readonly logMin: number;
  private readonly logMax: number;

  constructor(root: HTMLElement, private readonly replay: ThreeClocksReplay) {
    super(root, replay.maxMinutes, 26);
    this.originMillis = Date.parse(replay.originAt);
    this.logMin = Math.log10(replay.minMinutes);
    this.logMax = Math.log10(replay.maxMinutes);
    this.start();
  }

  protected fromSlider(value: number): number {
    return 10 ** (this.logMin + (value / 1000) * (this.logMax - this.logMin));
  }

  protected toSlider(value: number): number {
    const clamped = Math.max(this.replay.minMinutes, Math.min(this.replay.maxMinutes, value));
    return Math.round(((Math.log10(clamped) - this.logMin) / (this.logMax - this.logMin)) * 1000);
  }

  /** How long after the light one named arrival happened, in words. */
  private sinceLight(id: string): string | null {
    const light = this.replay.arrivals.find((arrival) => arrival.id === "light");
    const target = this.replay.arrivals.find((arrival) => arrival.id === id);
    if (!light || !target) return null;
    return elapsed(target.minutes - light.minutes);
  }

  /**
   * The three separations, printed as numbers under the picture.
   *
   * Sean, 2026-08-26, having looked at both three-clock charts: "They seem to
   * have the same animation. I think there is some sort of error there." There
   * is no error — the two events carry genuinely different measurements — but
   * he is pointing at a real failure, and it is this file's. On a logarithmic
   * axis running from half a minute to five days, a proton onset at 40 minutes
   * and one at 2 h 22 min are about a centimetre apart, and the reader is
   * asked to hold that centimetre in their head while they navigate to the
   * other event. The CONTRAST is the entire reason the second chart exists, so
   * the contrast is now stated as three numbers rather than left to be
   * measured off the axis. Nothing here is new data: each is one published
   * arrival minus the published arrival of the light.
   */
  private separations(): string {
    const rows: Array<[string | null, string]> = [
      [this.sinceLight("flarePeak"), "from the light to the flare's own peak"],
      [this.sinceLight("protons"), "from the light to the radiation storm — protons above 10 MeV crossing 10 pfu"],
      [this.sinceLight("fieldMin"), "from the light to the deepest Dst, the floor of the geomagnetic storm"],
    ];
    const cells = rows
      .filter(([value]) => value !== null)
      .map(([value, label]) => `<div><b>${escapeHtml(value as string)}</b><span>${label}</span></div>`)
      .join("");
    return cells ? `<div class="replay-figures">${cells}</div>` : "";
  }

  protected captionStops(): ReplayCaption[] {
    return this.replay.arrivals.map((arrival) => ({
      at: arrival.minutes,
      title: `${arrival.label} · + ${elapsed(arrival.minutes)}`,
      text: firstSentences(arrival.note, 170),
    }));
  }

  protected markup(): string {
    const { arrivals, provenance, lanes } = this.replay;
    return `
      ${chromeHead([
        { key: "elapsed", label: "since the light left the Sun" },
        { key: "xray", label: "X-ray · W m⁻²", tone: "driver" },
        { key: "protons", label: "protons > 10 MeV · pfu", tone: "raised" },
        { key: "dst", label: "Dst · nT", tone: "lost" },
      ])}
      <p class="replay-lede">One eruption, and three different things leaving the Sun because of it. Each band is one instrument: X-rays, protons above 10 MeV, and Dst, the ground measure of the geomagnetic storm. Time runs across the bottom from the moment the flare&rsquo;s light left the Sun, and it is logarithmic, so eight minutes and five days are both legible on one axis. The purple rules are the arrivals. How far apart they stand is the whole lesson, and it is not the same twice &mdash; the numbers under the picture are this event&rsquo;s.</p>
      <div class="replay-canvas-wrap"><canvas></canvas></div>
      ${CONTROLS}
      ${this.separations()}
      <ol class="replay-arrivals">
        ${arrivals.map((arrival) => `
          <li data-arrival="${arrival.id}">
            <b>${escapeHtml(arrival.label)}</b>
            <em>+ ${escapeHtml(elapsed(arrival.minutes))}</em>
            <span>${escapeHtml(arrival.value)} · ${escapeHtml(arrival.detail)}</span>
            <p>${escapeHtml(arrival.note)}</p>
          </li>`).join("")}
      </ol>
      ${methodBlock([
        ["X-rays", provenance.xray],
        ["Protons", provenance.protons],
        ["Dst", provenance.dst],
        ["The zero of the axis", provenance.origin],
        ["How the points were chosen", provenance.method],
        ["What this cannot show", provenance.limitation],
        ["Instruments", lanes.map((lane) => lane.instrument).join(" · ")],
      ])}`;
  }

  protected measureAll(): void {
    this.canvas ??= this.root.querySelector<HTMLCanvasElement>("canvas")!;
    const width = Math.max(280, this.canvas.parentElement?.clientWidth ?? 720);
    this.height = width < 560 ? 490 : 450;
    this.context = this.fitCanvas(this.canvas, this.height);
    this.draw();
  }

  private x(minutes: number, width: number, left: number, right: number): number {
    const clamped = Math.max(this.replay.minMinutes, minutes);
    return left + ((Math.log10(clamped) - this.logMin) / (this.logMax - this.logMin)) * (width - left - right);
  }

  protected draw(): void {
    const context = this.context;
    const width = this.canvas.clientWidth || this.canvas.width;
    const left = 58;
    const right = 34;
    const top = 44;
    const bottom = 30;
    const laneGap = 16;
    const lanes = this.replay.lanes;
    const laneHeight = (this.height - top - bottom - laneGap * (lanes.length - 1)) / lanes.length;
    const x = (minutes: number) => this.x(minutes, width, left, right);

    context.clearRect(0, 0, width, this.height);

    // Decade rules across the whole frame, labelled in units a person uses.
    // On a phone the last three land within forty pixels of each other, so the
    // narrow set drops the two that are only there for texture and keeps the
    // ones the arrivals actually fall between.
    const wide = width >= 560;
    const ticks: Array<[number, string]> = wide
      ? [[1, "1 min"], [10, "10 min"], [60, "1 h"], [360, "6 h"],
         [1440, "1 day"], [4320, "3 days"], [7200, "5 days"]]
      : [[1, "1 min"], [10, "10 min"], [60, "1 h"], [1440, "1 day"], [7200, "5 days"]];
    context.font = `500 10px ${MONO}`;
    context.textAlign = "center";
    context.textBaseline = "top";
    for (const [minutes, label] of ticks) {
      if (minutes > this.replay.maxMinutes) continue;
      const at = x(minutes);
      context.strokeStyle = PALETTE.grid;
      context.lineWidth = 1;
      context.beginPath();
      context.moveTo(at + 0.5, top);
      context.lineTo(at + 0.5, this.height - bottom + 4);
      context.stroke();
      context.fillStyle = PALETTE.muted;
      context.fillText(label, at, this.height - bottom + 8);
    }

    lanes.forEach((lane, index) => {
      const laneTop = top + index * (laneHeight + laneGap);
      this.drawLane(context, lane, laneTop, laneHeight, left, width - right, x);
    });

    this.drawArrivals(context, x, top, this.height - bottom, wide);

    if (this.cursor > this.replay.minMinutes) {
      const at = x(this.cursor);
      context.strokeStyle = "rgba(237,248,251,0.32)";
      context.lineWidth = 1;
      context.beginPath();
      context.moveTo(at + 0.5, top);
      context.lineTo(at + 0.5, this.height - bottom);
      context.stroke();
    }

    this.updateReadout();
  }

  private drawLane(
    context: CanvasRenderingContext2D,
    lane: ClockLane,
    top: number,
    height: number,
    left: number,
    rightEdge: number,
    x: (minutes: number) => number,
  ): void {
    const logarithmic = lane.scale === "log";
    const lo = logarithmic ? Math.log10(lane.min) : lane.min;
    const hi = logarithmic ? Math.log10(lane.max) : lane.max;
    const y = (value: number) => {
      const key = logarithmic ? Math.log10(Math.max(lane.min, value)) : value;
      return top + (1 - Math.max(0, Math.min(1, (key - lo) / (hi - lo)))) * height;
    };
    const colour = { xray: PALETTE.driver, protons: PALETTE.raised, dst: PALETTE.lost }[lane.id]
      ?? PALETTE.raised;

    context.save();
    context.fillStyle = "rgba(132,194,214,0.045)";
    context.fillRect(left, top, rightEdge - left, height);

    context.font = `500 9px ${MONO}`;
    context.textBaseline = "middle";

    // Numbers on the y-axis. A lane whose only vertical annotation is the word
    // "log" is a lane a reader cannot get a quantity out of, and two of these
    // three span five decades.
    context.textAlign = "right";
    context.fillStyle = PALETTE.muted;
    if (logarithmic) {
      for (let power = Math.ceil(lo); power <= Math.floor(hi); power += 1) {
        const at = y(10 ** power);
        if (at < top + 8 || at > top + height - 4) continue;
        context.strokeStyle = "rgba(132,194,214,0.10)";
        context.beginPath();
        context.moveTo(left, at + 0.5);
        context.lineTo(rightEdge, at + 0.5);
        context.stroke();
        context.fillText(`1e${power}`, left - 8, at);
      }
    } else {
      for (let value = Math.ceil(lo / 100) * 100; value <= hi; value += 100) {
        const at = y(value);
        if (at < top + 8 || at > top + height - 4) continue;
        context.strokeStyle = "rgba(132,194,214,0.10)";
        context.beginPath();
        context.moveTo(left, at + 0.5);
        context.lineTo(rightEdge, at + 0.5);
        context.stroke();
        context.fillText(String(value), left - 8, at);
      }
    }

    for (const guide of lane.guides) {
      const at = y(guide.value);
      if (at < top || at > top + height) continue;
      context.strokeStyle = "rgba(237,248,251,0.22)";
      context.setLineDash([3, 4]);
      context.lineWidth = 1;
      context.beginPath();
      context.moveTo(left, at + 0.5);
      context.lineTo(rightEdge, at + 0.5);
      context.stroke();
      context.setLineDash([]);
      context.fillStyle = "rgba(237,248,251,0.62)";
      context.textAlign = "right";
      context.fillText(guide.label, rightEdge - 8, at - 8);
    }

    const points = lane.points.filter((point) => point[0] <= this.cursor);
    context.strokeStyle = colour;
    context.lineWidth = 1.8;
    context.lineJoin = "round";
    // The break threshold is a multiple of the elapsed time, not a fixed number
    // of minutes, because the sampling is log-thinned: at ten minutes a
    // one-hour hole is a hole, and at three days it is the cadence.
    let open = false;
    let previous = 0;
    context.beginPath();
    for (const [minutes, value] of points) {
      const at = x(minutes);
      const level = y(value);
      if (!open || minutes - previous > Math.max(6, previous * 1.4)) context.moveTo(at, level);
      else context.lineTo(at, level);
      open = true;
      previous = minutes;
    }
    context.stroke();

    const head = points[points.length - 1];
    if (head) {
      context.fillStyle = colour;
      context.beginPath();
      context.arc(x(head[0]), y(head[1]), 2.8, 0, Math.PI * 2);
      context.fill();
    }

    context.strokeStyle = PALETTE.grid;
    context.lineWidth = 1;
    context.strokeRect(left - 0.5, top - 0.5, rightEdge - left + 1, height + 1);

    context.font = `600 10px ${MONO}`;
    context.textAlign = "left";
    context.textBaseline = "top";
    context.fillStyle = colour;
    context.fillText(lane.label.toUpperCase(), left + 8, top + 6);
    context.font = `500 9px ${MONO}`;
    context.fillStyle = PALETTE.muted;
    context.textAlign = "left";
    context.fillText(`${lane.unit} · ${lane.scale === "log" ? "log" : "linear"}`, left + 8, top + 19);
    context.restore();
  }

  private drawArrivals(
    context: CanvasRenderingContext2D,
    x: (minutes: number) => number,
    top: number,
    bottom: number,
    withLabels: boolean,
  ): void {
    context.save();
    context.font = `600 9px ${MONO}`;
    context.textBaseline = "bottom";
    // Six arrivals land inside two decades near the right of a logarithmic
    // axis, so a single row of labels overprints itself. Each label is placed
    // on the first of three rows whose previous occupant it does not touch,
    // and flips to the left of its own rule when it would run off the frame.
    const occupied = [0, 0, 0];
    for (const arrival of this.replay.arrivals) {
      if (arrival.minutes > this.cursor) continue;
      const at = x(arrival.minutes);
      const text = arrival.label.toUpperCase();
      const textWidth = withLabels ? context.measureText(text).width : 0;
      const flip = at + textWidth + 10 > this.canvas.clientWidth - 8;
      const startX = flip ? at - textWidth - 5 : at + 5;
      let row = occupied.findIndex((edge) => startX > edge + 6);
      if (row < 0) row = 0;
      occupied[row] = startX + textWidth;
      context.strokeStyle = "rgba(169,140,255,0.5)";
      context.lineWidth = 1;
      context.setLineDash([2, 3]);
      context.beginPath();
      context.moveTo(at + 0.5, top - 3 - row * 11);
      context.lineTo(at + 0.5, bottom);
      context.stroke();
      context.setLineDash([]);
      // Below the label breakpoint the rules stay and the words go. Four of the
      // six arrivals land inside the last decade of a 358-pixel axis, where no
      // stagger keeps them apart; the list under the chart names them in order
      // and is the readable surface at that width.
      if (!withLabels) continue;
      context.fillStyle = PALETTE.accent;
      context.textAlign = "left";
      context.fillText(text, startX, top - 5 - row * 11);
    }
    context.restore();
  }

  private laneValue(id: string): number | null {
    const lane = this.replay.lanes.find((candidate) => candidate.id === id);
    if (!lane) return null;
    let value: number | null = null;
    for (const [minutes, level] of lane.points) {
      if (minutes > this.cursor) break;
      value = level;
    }
    return value;
  }

  private updateReadout(): void {
    this.clock.textContent = `T + ${elapsed(this.cursor)}  ·  ${utcStamp(this.originMillis + this.cursor * 60_000)}`;
    const set = (key: string, text: string) => {
      const node = this.root.querySelector<HTMLElement>(`[data-readout="${key}"]`);
      if (node) node.textContent = text;
    };
    set("elapsed", elapsed(this.cursor));
    const xray = this.laneValue("xray");
    const protons = this.laneValue("protons");
    const dst = this.laneValue("dst");
    set("xray", xray === null ? "—" : xray.toExponential(1));
    set("protons", protons === null ? "—" : protons >= 100 ? Math.round(protons).toLocaleString() : protons.toFixed(1));
    set("dst", dst === null ? "—" : String(Math.round(dst)));
    for (const arrival of this.replay.arrivals) {
      const node = this.root.querySelector<HTMLElement>(`[data-arrival="${arrival.id}"]`);
      node?.classList.toggle("is-passed", arrival.minutes <= this.cursor);
    }
  }
}

// ---------------------------------------------------------------------------
// stpatricks-2015 — cause, effect, and the quantity that looks like the cause
// ---------------------------------------------------------------------------

/**
 * Three measured lanes on one LINEAR UTC axis, and four extrema.
 *
 * Every other chart in this file starts at the Sun. This one starts at the
 * magnetosphere's front door and answers the question the others leave open:
 * the cloud has arrived, is this going to be a storm? The answer is not in how
 * fast it is going — the wind here is still speeding up a full day after the
 * storm has bottomed out and begun recovering — it is in the sign of the
 * magnetic field the cloud carries.
 *
 * Two things this view draws that the others do not, both for the same reason:
 *
 * - **The axis is linear, not logarithmic.** The three-clock charts are
 *   logarithmic because eight minutes and three days have to share one axis
 *   and the SEPARATIONS are their lesson. Here everything happens inside two
 *   and a half days at one cadence, and the lesson is the ORDER and the LAG,
 *   which a linear axis states directly and a logarithmic one would distort.
 * - **Every point carries a band.** The published record is a ten-minute bin
 *   holding the real sample nearest its centre and the true smallest and
 *   largest real samples inside it. The line is the measurement; the band is
 *   what the thinning would otherwise have hidden. Plain decimation of a
 *   one-minute series can drop the deepest southward excursion in a storm and
 *   leave no sign that it did.
 *
 * The zero line on the Bz lane is drawn as an actual boundary rather than as
 * another grid rule, and the region below it is tinted, because the whole
 * chart turns on which side of it the trace is.
 */
class SouthwardTurningView extends ReplayChrome {
  private canvas!: HTMLCanvasElement;
  private context!: CanvasRenderingContext2D;
  private height = 440;
  private readonly startMillis: number;

  constructor(root: HTMLElement, private readonly replay: SouthwardTurningReplay) {
    super(root, replay.spanMinutes, 26);
    this.startMillis = Date.parse(replay.startAt);
    this.start();
  }

  protected captionStops(): ReplayCaption[] {
    return this.replay.marks.map((mark) => ({
      at: mark.minutes,
      title: `${mark.label} · ${mark.value}`,
      text: firstSentences(mark.note, 170),
    }));
  }

  protected markup(): string {
    const { marks, provenance, lanes } = this.replay;
    return `
      ${chromeHead([
        { key: "elapsed", label: "into the window" },
        { key: "bz", label: "Bz · nT", tone: "driver" },
        { key: "speed", label: "speed · km/s", tone: "raised" },
        { key: "symh", label: "SYM/H · nT", tone: "lost" },
      ])}
      <div class="replay-canvas-wrap"><canvas></canvas></div>
      ${CONTROLS}
      <ol class="replay-arrivals">
        ${marks.map((mark) => `
          <li data-arrival="${mark.id}">
            <b>${escapeHtml(mark.label)}</b>
            <em>${escapeHtml(utcStamp(Date.parse(mark.at)))}</em>
            <span>${escapeHtml(mark.value)} · ${escapeHtml(mark.detail)}</span>
            <p>${escapeHtml(mark.note)}</p>
          </li>`).join("")}
      </ol>
      ${methodBlock([
        ["Field and speed", provenance.field],
        ["The storm index", provenance.symh],
        ["Measured upstream, drawn at Earth", provenance.shift],
        ["How the points were chosen", provenance.method],
        ["Licence and credit", provenance.licence],
        ["What this cannot show", provenance.limitation],
        ["Instruments", lanes.map((lane) => lane.instrument).join(" · ")],
      ])}`;
  }

  protected measureAll(): void {
    this.canvas ??= this.root.querySelector<HTMLCanvasElement>("canvas")!;
    const width = Math.max(280, this.canvas.parentElement?.clientWidth ?? 720);
    this.height = width < 560 ? 500 : 460;
    this.context = this.fitCanvas(this.canvas, this.height);
    this.draw();
  }

  protected draw(): void {
    const context = this.context;
    const width = this.canvas.clientWidth || this.canvas.width;
    const left = 58;
    const right = 34;
    const top = 44;
    const bottom = 30;
    const laneGap = 16;
    const lanes = this.replay.lanes;
    const laneHeight = (this.height - top - bottom - laneGap * (lanes.length - 1)) / lanes.length;
    const span = this.replay.spanMinutes;
    const x = (minutes: number) =>
      left + (Math.max(0, Math.min(span, minutes)) / span) * (width - left - right);

    context.clearRect(0, 0, width, this.height);

    // A rule every six hours, labelled with the UTC hour, and the date printed
    // once per day. A reader has to be able to say "this happened on the
    // seventeenth at about one in the afternoon" without counting boxes.
    const wide = width >= 560;
    const stepHours = wide ? 6 : 12;
    context.font = `500 10px ${MONO}`;
    context.textAlign = "center";
    context.textBaseline = "top";
    for (let minutes = 0; minutes <= span; minutes += stepHours * 60) {
      const at = x(minutes);
      const when = new Date(this.startMillis + minutes * 60_000);
      const midnight = when.getUTCHours() === 0;
      context.strokeStyle = midnight ? PALETTE.gridStrong : PALETTE.grid;
      context.lineWidth = 1;
      context.beginPath();
      context.moveTo(at + 0.5, top);
      context.lineTo(at + 0.5, this.height - bottom + 4);
      context.stroke();
      context.fillStyle = PALETTE.muted;
      const hour = `${String(when.getUTCHours()).padStart(2, "0")}Z`;
      context.fillText(hour, at, this.height - bottom + 8);
      if (midnight) {
        context.fillStyle = PALETTE.text;
        context.fillText(utcStamp(when.getTime(), false).slice(5), at, this.height - bottom + 19);
      }
    }

    lanes.forEach((lane, index) => {
      const laneTop = top + index * (laneHeight + laneGap);
      this.drawLane(context, lane, laneTop, laneHeight, left, width - right, x, wide);
    });

    this.drawMarks(context, x, top, this.height - bottom, wide);

    if (this.cursor > 0) {
      const at = x(this.cursor);
      context.strokeStyle = "rgba(237,248,251,0.32)";
      context.lineWidth = 1;
      context.beginPath();
      context.moveTo(at + 0.5, top);
      context.lineTo(at + 0.5, this.height - bottom);
      context.stroke();
    }

    this.updateReadout();
  }

  private drawLane(
    context: CanvasRenderingContext2D,
    lane: TurningLane,
    top: number,
    height: number,
    left: number,
    rightEdge: number,
    x: (minutes: number) => number,
    wide: boolean,
  ): void {
    const y = (value: number) =>
      top + (1 - Math.max(0, Math.min(1, (value - lane.min) / (lane.max - lane.min)))) * height;
    const colour = { bz: PALETTE.driver, speed: PALETTE.raised, symh: PALETTE.lost }[lane.id]
      ?? PALETTE.raised;

    context.save();
    context.fillStyle = "rgba(132,194,214,0.045)";
    context.fillRect(left, top, rightEdge - left, height);

    // The southward half of the field lane, tinted. This is the one place on
    // the page where the SIGN of a quantity is the whole subject, so the two
    // halves of the lane are not allowed to look alike.
    if (lane.id === "bz" && lane.min < 0 && lane.max > 0) {
      const zero = y(0);
      context.fillStyle = "rgba(255,123,120,0.09)";
      context.fillRect(left, zero, rightEdge - left, top + height - zero);
      context.font = `500 9px ${MONO}`;
      context.textAlign = "left";
      context.textBaseline = "top";
      context.fillStyle = "rgba(255,123,120,0.75)";
      // On a phone this caption is longer than the lane is wide and the trace
      // runs straight through it. The tint says the same thing without words,
      // and the list under the chart says it in full.
      if (wide) context.fillText("SOUTHWARD — the door is open", left + 8, zero + 4);
    }

    // Numbers on the y-axis, at a step the lane's own range chooses, so a lane
    // spanning 60 nT and one spanning 500 km/s both get four or five labels.
    const range = lane.max - lane.min;
    const step = [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500]
      .find((candidate) => range / candidate <= 6) ?? 1000;
    context.font = `500 9px ${MONO}`;
    context.textBaseline = "middle";
    context.textAlign = "right";
    for (let value = Math.ceil(lane.min / step) * step; value <= lane.max; value += step) {
      const at = y(value);
      if (at < top + 8 || at > top + height - 4) continue;
      context.strokeStyle = "rgba(132,194,214,0.10)";
      context.lineWidth = 1;
      context.beginPath();
      context.moveTo(left, at + 0.5);
      context.lineTo(rightEdge, at + 0.5);
      context.stroke();
      context.fillStyle = PALETTE.muted;
      context.fillText(String(value), left - 8, at);
    }

    for (const guide of lane.guides) {
      const at = y(guide.value);
      if (at < top || at > top + height) continue;
      const boundary = lane.id === "bz" && guide.value === 0;
      context.strokeStyle = boundary ? "rgba(237,248,251,0.55)" : "rgba(237,248,251,0.22)";
      context.lineWidth = boundary ? 1.4 : 1;
      if (!boundary) context.setLineDash([3, 4]);
      context.beginPath();
      context.moveTo(left, at + 0.5);
      context.lineTo(rightEdge, at + 0.5);
      context.stroke();
      context.setLineDash([]);
      context.fillStyle = "rgba(237,248,251,0.62)";
      context.textAlign = "right";
      // A guide label wider than a fifth of the lane is a label sitting on the
      // data. Below the breakpoint the zero line keeps its rule and loses its
      // caption; the axis numbers beside it already say where zero is.
      if (context.measureText(guide.label).width < (rightEdge - left) * 0.2) {
        context.fillText(guide.label, rightEdge - 8, at - 8);
      }
    }

    // ---- the band, then the line -----------------------------------------
    // Runs of consecutive bins are drawn as separate shapes. A bin with no
    // valid sample is simply absent from the payload, and the break in the
    // stroke is how the reader sees that the archive had nothing there.
    const points = lane.points.filter((point) => point[0] <= this.cursor);
    const gapMinutes = this.replay.binMinutes * 1.75;
    const runs: Array<Array<[number, number, number, number]>> = [];
    for (const point of points) {
      const run = runs[runs.length - 1];
      if (!run || point[0] - run[run.length - 1]![0] > gapMinutes) runs.push([point]);
      else run.push(point);
    }

    for (const run of runs) {
      if (run.length < 2) continue;
      context.beginPath();
      run.forEach((point, index) => {
        const at = x(point[0]);
        const level = y(point[3]);
        if (index === 0) context.moveTo(at, level);
        else context.lineTo(at, level);
      });
      for (let index = run.length - 1; index >= 0; index -= 1) {
        const point = run[index]!;
        context.lineTo(x(point[0]), y(point[2]));
      }
      context.closePath();
      context.fillStyle = colour;
      context.globalAlpha = 0.22;
      context.fill();
      context.globalAlpha = 1;
    }

    context.strokeStyle = colour;
    context.lineWidth = 1.6;
    context.lineJoin = "round";
    for (const run of runs) {
      context.beginPath();
      run.forEach((point, index) => {
        const at = x(point[0]);
        const level = y(point[1]);
        if (index === 0) context.moveTo(at, level);
        else context.lineTo(at, level);
      });
      context.stroke();
    }

    const head = points[points.length - 1];
    if (head) {
      context.fillStyle = colour;
      context.beginPath();
      context.arc(x(head[0]), y(head[1]), 2.8, 0, Math.PI * 2);
      context.fill();
    }

    context.strokeStyle = PALETTE.grid;
    context.lineWidth = 1;
    context.strokeRect(left - 0.5, top - 0.5, rightEdge - left + 1, height + 1);

    // The header sits on a plate. SYM/H spans -260..100, so its own zero line
    // — a guide, drawn dashed right across the lane — lands within a few
    // pixels of the sub-label and struck it through. Plating the two lines is
    // the fix that keeps working whatever range a future lane declares.
    context.font = `600 10px ${MONO}`;
    context.textAlign = "left";
    context.textBaseline = "top";
    const missing = lane.emptyBins > 0 ? ` · ${lane.emptyBins} empty bins` : "";
    const sub = `${lane.unit} · ${this.replay.binMinutes} min bins${missing}`;
    const headWidth = Math.max(
      context.measureText(lane.label.toUpperCase()).width,
      (() => { context.font = `500 9px ${MONO}`; return context.measureText(sub).width; })(),
    );
    plate(context, left + 4, top + 3, headWidth + 8, 27);
    context.font = `600 10px ${MONO}`;
    context.fillStyle = colour;
    context.fillText(lane.label.toUpperCase(), left + 8, top + 6);
    context.font = `500 9px ${MONO}`;
    context.fillStyle = PALETTE.muted;
    context.fillText(sub, left + 8, top + 19);
    context.restore();
  }

  private drawMarks(
    context: CanvasRenderingContext2D,
    x: (minutes: number) => number,
    top: number,
    bottom: number,
    withLabels: boolean,
  ): void {
    context.save();
    context.font = `600 9px ${MONO}`;
    context.textBaseline = "bottom";
    const occupied = [0, 0];
    for (const mark of this.replay.marks) {
      if (mark.minutes > this.cursor) continue;
      const at = x(mark.minutes);
      const text = mark.label.toUpperCase();
      const textWidth = withLabels ? context.measureText(text).width : 0;
      const flip = at + textWidth + 10 > this.canvas.clientWidth - 8;
      const startX = flip ? at - textWidth - 5 : at + 5;
      let row = occupied.findIndex((edge) => startX > edge + 6);
      if (row < 0) row = 0;
      occupied[row] = startX + textWidth;
      context.strokeStyle = "rgba(169,140,255,0.5)";
      context.lineWidth = 1;
      context.setLineDash([2, 3]);
      context.beginPath();
      context.moveTo(at + 0.5, top - 3 - row * 11);
      context.lineTo(at + 0.5, bottom);
      context.stroke();
      context.setLineDash([]);
      if (!withLabels) continue;
      context.fillStyle = PALETTE.accent;
      context.textAlign = "left";
      context.fillText(text, startX, top - 5 - row * 11);
    }
    context.restore();
  }

  private laneValue(id: string): number | null {
    const lane = this.replay.lanes.find((candidate) => candidate.id === id);
    if (!lane) return null;
    let value: number | null = null;
    for (const point of lane.points) {
      if (point[0] > this.cursor) break;
      value = point[1];
    }
    return value;
  }

  private updateReadout(): void {
    this.clock.textContent = `${utcStamp(this.startMillis + this.cursor * 60_000)}  ·  ${elapsed(this.cursor)} in`;
    const set = (key: string, text: string) => {
      const node = this.root.querySelector<HTMLElement>(`[data-readout="${key}"]`);
      if (node) node.textContent = text;
    };
    set("elapsed", elapsed(this.cursor));
    const bz = this.laneValue("bz");
    const speed = this.laneValue("speed");
    const symh = this.laneValue("symh");
    set("bz", bz === null ? "—" : bz.toFixed(1));
    set("speed", speed === null ? "—" : String(Math.round(speed)));
    set("symh", symh === null ? "—" : String(Math.round(symh)));
    for (const mark of this.replay.marks) {
      const node = this.root.querySelector<HTMLElement>(`[data-arrival="${mark.id}"]`);
      node?.classList.toggle("is-passed", mark.minutes <= this.cursor);
    }
  }
}

// ---------------------------------------------------------------------------
// quebec-1989 — the rate, not the depth
// ---------------------------------------------------------------------------

/** The Dst half of the blackout mark's value, e.g. "Dst -143 nT". */
function dstAtBlackout(mark: GicChainReplay["marks"][number] | undefined): string {
  const half = mark?.value.split("·")[1];
  return half ? half.trim() : "—";
}

/**
 * Two measured curves and one honest surprise.
 *
 * The top lane is Ottawa's one-minute magnetogram, differenced: how far the
 * horizontal field moved between one minute and the next. It is drawn as an
 * impulse per minute rather than as a line, because at one-minute cadence over
 * sixty hours a line would be a solid block and the individual minutes are the
 * whole subject. On a quiet minute at Ottawa that number is about 1.4 nT. In
 * the minute the province went dark it was 435.
 *
 * The bottom lane is Kyoto's hourly Dst — the index everyone quotes for this
 * storm. At the moment of the failure it stood at −143 nT, and it would not
 * reach its record −589 for another seventeen hours. Watching the deepest
 * hourly index of the twentieth century arrive long after the grid had already
 * failed is the fastest way to learn that the number on the wall is not the
 * quantity that hurts you.
 *
 * The picture is deliberately drawn over the WHOLE storm rather than the
 * blackout hour, because the honest reading is visible only at that width:
 * Ottawa saw LARGER excursions the following morning and nothing failed. Rate
 * is the right quantity to watch and it is still not sufficient by itself.
 */
class GicChainView extends ReplayChrome {
  private canvas!: HTMLCanvasElement;
  private context!: CanvasRenderingContext2D;
  private height = 380;
  private readonly baseMillis: number;
  private readonly maxHours: number;

  constructor(root: HTMLElement, private readonly replay: GicChainReplay) {
    super(root, (Date.parse(replay.endsAt) - Date.parse(replay.startsAt)) / 3600_000, 26);
    this.baseMillis = Date.parse(replay.startsAt);
    this.maxHours = (Date.parse(replay.endsAt) - this.baseMillis) / 3600_000;
    this.start();
  }

  /**
   * Two stops, and they carry the mark's own words rather than a sentence
   * written here: this replay's marks publish a value and a detail but no
   * note, so the caption is exactly what the list under the picture prints.
   */
  protected captionStops(): ReplayCaption[] {
    return this.replay.marks.map((mark) => ({
      at: mark.hours,
      title: `${mark.label} · ${mark.value}`,
      text: mark.detail,
    }));
  }

  protected markup(): string {
    const { rate, marks, provenance, gapHours, ratioAtBlackout, video } = this.replay;
    const blackout = marks.find((mark) => mark.id === "blackout");
    return `
      ${chromeHead([
        { key: "rate", label: `${rate.short} · ${rate.unit}`, tone: "raised" },
        { key: "dst", label: "Dst · nT", tone: "driver" },
      ])}
      <div class="replay-canvas-wrap"><canvas></canvas></div>
      ${CONTROLS}
      <div class="replay-figures">
        <div><b>${rate.atBlackout.toFixed(0)} nT/min</b><span>at Ottawa in the minute Hydro-Québec separated — ${ratioAtBlackout}× a quiet minute</span></div>
        <div><b>${escapeHtml(dstAtBlackout(blackout))}</b><span>what Dst read at that same moment</span></div>
        <div><b>${gapHours.toFixed(0)} hours later</b><span>before Dst reached its record −589 nT</span></div>
        <div><b>${rate.peak.toFixed(0)} nT/min</b><span>the storm's largest minute, ${utcStamp(Date.parse(rate.peakAt))} — and nothing failed</span></div>
      </div>
      ${video ? `
      <figure class="replay-video">
        <figcaption class="replay-video-head">
          <span class="replay-badge is-schematic">Schematic · not footage</span>
          <strong>How a magnetic storm reaches a transformer</strong>
        </figcaption>
        <video controls preload="none" playsinline
               poster="${mediaAsset(`${video.stem}.jpg`)}"
               width="${video.width}" height="${video.height}"
               aria-label="Mechanism animation: the geomagnetically induced current chain">
          <source src="${mediaAsset(`${video.stem}.mp4`)}" type="video/mp4" />
        </video>
        <p class="replay-video-caption">${escapeHtml(video.caption)}</p>
        <details class="replay-transcript">
          <summary>What the narration says</summary>
          <ol>${video.transcript.map((line) =>
            `<li><b>${Math.floor(line.at / 60)}:${String(Math.round(line.at % 60)).padStart(2, "0")}</b>${escapeHtml(line.text)}</li>`).join("")}</ol>
        </details>
      </figure>` : ""}
      ${methodBlock([
        ["The rate", provenance.rate],
        ["Where it was measured", `${rate.station}. ${rate.instrument}.`],
        ["The index", provenance.index],
        ["How the rate is obtained", provenance.method],
        ["The time of the failure", provenance.blackoutTime],
        ["The mechanism panel", provenance.animation],
        ["What this cannot show", provenance.limitation],
      ])}`;
  }

  protected measureAll(): void {
    this.canvas ??= this.root.querySelector<HTMLCanvasElement>("canvas")!;
    const width = Math.max(280, this.canvas.parentElement?.clientWidth ?? 720);
    this.height = width < 560 ? 420 : 380;
    this.context = this.fitCanvas(this.canvas, this.height);
    this.draw();
  }

  protected draw(): void {
    const context = this.context;
    const width = this.canvas.clientWidth || this.canvas.width;
    const left = 52;
    const right = 34;
    const top = 22;
    const bottom = 34;
    const gap = 28;
    const rateHeight = Math.round((this.height - top - bottom - gap) * 0.62);
    const indexHeight = this.height - top - bottom - gap - rateHeight;
    const x = (hours: number) => left + (hours / this.maxHours) * (width - left - right);

    context.clearRect(0, 0, width, this.height);
    this.drawRate(context, x, left, width - right, top, rateHeight);
    this.drawIndex(context, x, left, width - right, top + rateHeight + gap, indexHeight);
    this.drawTimeAxis(context, x, left, width - right, this.height - bottom);
    this.drawMarks(context, x, top, this.height - bottom);
    this.drawGap(context, x, top + rateHeight + gap - 13);

    if (this.cursor > 0 && this.cursor < this.maxHours) {
      context.strokeStyle = "rgba(237,248,251,0.30)";
      context.lineWidth = 1;
      context.beginPath();
      context.moveTo(x(this.cursor) + 0.5, top);
      context.lineTo(x(this.cursor) + 0.5, this.height - bottom);
      context.stroke();
    }
    this.updateReadout();
  }

  private drawRate(
    context: CanvasRenderingContext2D,
    x: (hours: number) => number,
    left: number,
    rightEdge: number,
    top: number,
    height: number,
  ): void {
    const { values, max, stepMinutes, quietMedian } = this.replay.rate;
    const y = (value: number) => top + height - Math.max(0, Math.min(1, value / max)) * height;

    context.save();
    context.font = `500 9px ${MONO}`;
    context.textBaseline = "middle";
    context.textAlign = "right";
    for (let level = 0; level <= max; level += 200) {
      const at = y(level);
      context.strokeStyle = level === 0 ? PALETTE.gridStrong : PALETTE.grid;
      context.lineWidth = 1;
      context.beginPath();
      context.moveTo(left, at + 0.5);
      context.lineTo(rightEdge, at + 0.5);
      context.stroke();
      context.fillStyle = PALETTE.muted;
      context.fillText(String(level), left - 8, at);
    }

    // A quiet minute, drawn so the spikes have something to be large against.
    const quiet = y(quietMedian);
    context.strokeStyle = "rgba(169,140,255,0.5)";
    context.setLineDash([3, 4]);
    context.beginPath();
    context.moveTo(left, quiet + 0.5);
    context.lineTo(rightEdge, quiet + 0.5);
    context.stroke();
    context.setLineDash([]);
    context.fillStyle = "rgba(169,140,255,0.85)";
    context.textAlign = "left";
    context.fillText(`a quiet minute: ${quietMedian.toFixed(1)}`, left + 6, quiet - 8);

    // One vertical stroke per real minute. Sub-pixel strokes are drawn at
    // whatever the device gives them rather than being binned, because binning
    // by maximum would exaggerate and binning by mean would erase the event.
    context.strokeStyle = PALETTE.measured;
    context.lineWidth = Math.max(0.6, (rightEdge - left) / values.length);
    context.globalAlpha = 0.9;
    context.beginPath();
    for (let slot = 0; slot < values.length; slot += 1) {
      const value = values[slot];
      if (value === null || value === undefined) continue;
      const hours = (slot * stepMinutes) / 60;
      if (hours > this.cursor) break;
      const at = x(hours);
      context.moveTo(at, top + height);
      context.lineTo(at, y(value));
    }
    context.stroke();
    context.globalAlpha = 1;

    // The one minute this whole event is about, called out where it happened.
    const blackout = this.replay.marks.find((mark) => mark.id === "blackout");
    if (blackout && blackout.hours <= this.cursor) {
      const at = x(blackout.hours);
      const level = y(this.replay.rate.atBlackout);
      context.strokeStyle = PALETTE.lost;
      context.lineWidth = 1;
      context.beginPath();
      context.arc(at, level, 4.5, 0, Math.PI * 2);
      context.stroke();
      context.font = `600 10px ${MONO}`;
      context.textAlign = "right";
      context.textBaseline = "middle";
      context.fillStyle = PALETTE.lost;
      context.fillText(`${this.replay.rate.atBlackout.toFixed(0)} nT/min`, at - 9, level);
    }

    context.font = `600 10px ${MONO}`;
    context.textAlign = "left";
    context.textBaseline = "top";
    context.fillStyle = PALETTE.measured;
    context.fillText(`${this.replay.rate.short}  ${this.replay.rate.unit.toUpperCase()}`, left + 6, top + 4);
    context.font = `500 9px ${MONO}`;
    context.fillStyle = PALETTE.muted;
    context.fillText("Ottawa · one-minute definitive magnetogram · measured", left + 6, top + 18);
    context.restore();
  }

  private drawIndex(
    context: CanvasRenderingContext2D,
    x: (hours: number) => number,
    left: number,
    rightEdge: number,
    top: number,
    height: number,
  ): void {
    const { points, min, max } = this.replay.index;
    const y = (value: number) => top + (1 - (value - min) / (max - min)) * height;

    context.save();
    context.strokeStyle = PALETTE.grid;
    context.lineWidth = 1;
    context.font = `500 9px ${MONO}`;
    context.textBaseline = "middle";
    context.textAlign = "right";
    for (const level of [0, -200, -400, -600]) {
      if (level < min || level > max) continue;
      const at = y(level);
      context.beginPath();
      context.moveTo(left, at + 0.5);
      context.lineTo(rightEdge, at + 0.5);
      context.stroke();
      context.fillStyle = PALETTE.muted;
      context.fillText(String(level), left - 8, at);
    }

    const visible = points.filter((point) => point[0] <= this.cursor);
    const first = visible[0];
    const final = visible[visible.length - 1];
    if (first && final && visible.length > 1) {
      context.beginPath();
      context.moveTo(x(first[0]), y(0));
      for (const [hours, value] of visible) context.lineTo(x(hours), y(value));
      context.lineTo(x(final[0]), y(0));
      context.closePath();
      context.fillStyle = "rgba(245,201,106,0.10)";
      context.fill();
      context.strokeStyle = PALETTE.driver;
      context.lineWidth = 1.8;
      context.lineJoin = "round";
      strokeBroken(context, visible, x, y, 2);
    }

    context.font = `600 10px ${MONO}`;
    context.textAlign = "left";
    context.textBaseline = "top";
    context.fillStyle = PALETTE.driver;
    context.fillText("DST  nT", left + 6, top + 4);
    context.font = `500 9px ${MONO}`;
    context.fillStyle = PALETTE.muted;
    context.fillText("Kyoto · hourly · measured", left + 6, top + 18);
    context.restore();
  }

  private drawTimeAxis(
    context: CanvasRenderingContext2D,
    x: (hours: number) => number,
    left: number,
    rightEdge: number,
    axisY: number,
  ): void {
    context.save();
    context.strokeStyle = PALETTE.gridStrong;
    context.lineWidth = 1;
    context.beginPath();
    context.moveTo(left, axisY + 0.5);
    context.lineTo(rightEdge, axisY + 0.5);
    context.stroke();
    context.font = `500 10px ${MONO}`;
    context.textAlign = "center";
    context.textBaseline = "top";
    const first = Math.ceil(new Date(this.baseMillis).getUTCHours() / 6) * 6
      - new Date(this.baseMillis).getUTCHours();
    for (let hours = first; hours <= this.maxHours; hours += 12) {
      const when = new Date(this.baseMillis + hours * 3600_000);
      const at = x(hours);
      context.strokeStyle = PALETTE.grid;
      context.beginPath();
      context.moveTo(at + 0.5, axisY);
      context.lineTo(at + 0.5, axisY + 4);
      context.stroke();
      context.fillStyle = PALETTE.muted;
      const hour = String(when.getUTCHours()).padStart(2, "0");
      context.fillText(`${MONTHS[when.getUTCMonth()]} ${when.getUTCDate()} ${hour}Z`, at, axisY + 8);
    }
    context.restore();
  }

  private drawMarks(
    context: CanvasRenderingContext2D,
    x: (hours: number) => number,
    top: number,
    bottom: number,
  ): void {
    context.save();
    context.font = `600 10px ${MONO}`;
    context.textBaseline = "bottom";
    for (const mark of this.replay.marks) {
      if (mark.hours > this.cursor) continue;
      const at = x(mark.hours);
      const colour = mark.id === "blackout" ? PALETTE.lost : PALETTE.driver;
      context.strokeStyle = colour;
      context.globalAlpha = 0.7;
      context.lineWidth = 1;
      context.setLineDash(mark.id === "blackout" ? [] : [3, 4]);
      context.beginPath();
      context.moveTo(at + 0.5, top);
      context.lineTo(at + 0.5, bottom);
      context.stroke();
      context.setLineDash([]);
      context.globalAlpha = 1;
      context.fillStyle = colour;
      const flip = at > x(this.maxHours) * 0.72;
      context.textAlign = flip ? "right" : "left";
      context.fillText(mark.label.toUpperCase(), at + (flip ? -5 : 5), top + 10);
    }
    context.restore();
  }

  /**
   * The seventeen hours, drawn between the two marks rather than only stated
   * underneath. The distance between "the grid failed" and "the index was at
   * its worst" is the entire argument of this picture, and an argument about a
   * distance should be a distance on the page.
   */
  private drawGap(
    context: CanvasRenderingContext2D,
    x: (hours: number) => number,
    y: number,
  ): void {
    const blackout = this.replay.marks.find((mark) => mark.id === "blackout");
    const minimum = this.replay.marks.find((mark) => mark.id === "minimum");
    if (!blackout || !minimum || minimum.hours > this.cursor) return;
    const from = x(blackout.hours);
    const to = x(minimum.hours);
    context.save();
    context.strokeStyle = "rgba(169,140,255,0.75)";
    context.lineWidth = 1;
    context.beginPath();
    context.moveTo(from, y - 4);
    context.lineTo(from, y + 4);
    context.moveTo(to, y - 4);
    context.lineTo(to, y + 4);
    context.moveTo(from, y + 0.5);
    context.lineTo(to, y + 0.5);
    context.stroke();
    const text = `${this.replay.gapHours.toFixed(1)} h`;
    context.font = `600 10px ${MONO}`;
    const width = context.measureText(text).width + 12;
    const middle = (from + to) / 2;
    context.fillStyle = "#02070c";
    context.fillRect(middle - width / 2, y - 7, width, 14);
    context.fillStyle = PALETTE.accent;
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillText(text, middle, y);
    context.restore();
  }

  private updateReadout(): void {
    this.clock.textContent = utcStamp(this.baseMillis + this.cursor * 3600_000);
    const set = (key: string, text: string) => {
      const node = this.root.querySelector<HTMLElement>(`[data-readout="${key}"]`);
      if (node) node.textContent = text;
    };
    const { values, stepMinutes } = this.replay.rate;
    const slot = Math.max(0, Math.min(values.length - 1, Math.floor((this.cursor * 60) / stepMinutes)));
    const rate = values[slot];
    set("rate", rate === null || rate === undefined ? "—" : rate.toFixed(0));
    let dst: number | null = null;
    for (const [hours, value] of this.replay.index.points) {
      if (hours > this.cursor) break;
      dst = value;
    }
    set("dst", dst === null ? "—" : String(dst));
  }
}

/**
 * Mount whichever replay this event carries. Returns null when it carries none.
 *
 * The dispatch is on `kind` at the boundary rather than by type assertion,
 * because the payload arrives over the network and a shape check here is the
 * only thing standing between a malformed artifact and a blank event page.
 *
 * `milestones` is the event's own sourced prose, handed in so a replay can
 * caption itself from the same text the page prints beside it. Only the
 * orbit-decay view uses it; the others caption themselves from arrivals and
 * marks, which are landmarks their own measured record already carries on the
 * replay's clock.
 */
export function mountEventReplay(
  host: HTMLElement,
  replay: unknown,
  milestones: ReplayMilestone[] = [],
  /** The event's own id. Names the narration bed, where one has been stitched. */
  eventId = "",
): EventReplayView | null {
  const candidate = replay as EventReplay | undefined;
  if (!candidate || typeof candidate !== "object" || !("kind" in candidate)) return null;
  switch (candidate.kind) {
    case "orbit-decay":
      if (!Array.isArray(candidate.objects) || candidate.objects.length === 0) return null;
      return new OrbitDecayView(host, candidate, milestones, eventId);
    case "thermosphere-inflation":
      if (!candidate.map?.frames?.length || !candidate.series?.measured?.points?.length) return null;
      return new ThermosphereInflationView(host, candidate);
    case "three-clocks":
      if (!Array.isArray(candidate.lanes) || candidate.lanes.length === 0) return null;
      return new ThreeClocksView(host, candidate);
    case "southward-turning":
      if (!Array.isArray(candidate.lanes) || candidate.lanes.length === 0) return null;
      return new SouthwardTurningView(host, candidate);
    case "gic-chain":
      if (!Array.isArray(candidate.rate?.values) || candidate.rate.values.length === 0) return null;
      return new GicChainView(host, candidate);
    default:
      return null;
  }
}
