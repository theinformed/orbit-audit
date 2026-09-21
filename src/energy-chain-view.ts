/**
 * "Follow the energy" — the walkthrough itself.
 *
 * This module draws the chain and drives the explorer. It owns no physics and
 * makes no judgement: everything it says comes from `energy-chain.ts`, which
 * has no DOM and is unit-tested directly.
 *
 * **Why it is a separate entry point.** Four agents are working in this
 * repository at once and `src/main.ts` is 197 KB of somebody else's actively
 * changing file. Rather than mount inside it, this module loads from its own
 * `<script type="module">` in `index.html` and integrates with the running
 * explorer through the interface the explorer already exposes to a visitor:
 *
 *   - a layer is switched by setting its checkbox and dispatching `change`,
 *     because `main.ts` only calls `globe.setLayer` from that listener;
 *   - the camera is moved by clicking `#sun-earth-view`, `#reset-view`,
 *     `#zoom-in` and `#zoom-out`, which are the same four buttons the visitor
 *     has;
 *   - time is moved by setting `#time-slider` and dispatching `input`.
 *
 * That is not a workaround, it is the honest boundary: the walkthrough can do
 * exactly what a reader could do by hand, one step at a time, with the numbers
 * written down. If it can drive it, so can they.
 *
 * **It puts the interface back.** The reader's own layer selection is captured
 * when the walkthrough opens and restored when it closes, so following the
 * chain never silently rearranges the explorer they were using.
 */

import "./energy-chain.css";

import { DEFAULT_ARTIFACT_REFRESH_INTERVAL_MS } from "./artifact-refresh";
import {
  CHAIN_LAYER_CHECKBOX,
  CHAIN_MANAGED_LAYERS,
  EVIDENCE_MEANING,
  chainLength,
  chainLinks,
  chainVerdict,
  utcLabel,
} from "./energy-chain";
import type { ChainCamera, ChainLink, ChainScale, ChainSeries, EvidenceClass } from "./energy-chain";
import type { DrapBundle } from "./drap";
import { toSegments } from "./storm-indices";
import type { ReleaseManifest, SpaceWeatherBundle } from "./types";

const PANEL_ID = "energy-chain-panel";
const LAUNCHER_ID = "energy-chain-open";
const LEARN_LAUNCHER_ID = "energy-chain-open-learn";

/** How far back the replay control rewinds. The timeline itself stops at -48 h. */
const REPLAY_SPAN_MINUTES = 2880;
const REPLAY_FRAMES = 24;
const REPLAY_FRAME_MS = 900;

// ---------------------------------------------------------------------------
// Talking to the running explorer, through the controls a visitor already has
// ---------------------------------------------------------------------------

function control<T extends HTMLElement>(id: string): T | null {
  return document.getElementById(id) as T | null;
}

function setLayer(layerKey: string, on: boolean): boolean {
  const id = CHAIN_LAYER_CHECKBOX[layerKey];
  if (!id) return false;
  const box = control<HTMLInputElement>(id);
  if (!box) return false;
  if (box.checked !== on) {
    box.checked = on;
    box.dispatchEvent(new Event("change", { bubbles: true }));
  }
  return true;
}

function layerState(): Record<string, boolean> {
  const state: Record<string, boolean> = {};
  for (const key of CHAIN_MANAGED_LAYERS) {
    const box = control<HTMLInputElement>(CHAIN_LAYER_CHECKBOX[key] ?? "");
    if (box) state[key] = box.checked;
  }
  return state;
}

/** The four camera buttons a visitor has, by the step's own vocabulary. */
const CAMERA_BUTTON: Partial<Record<ChainCamera, string>> = {
  "sun-earth": "sun-earth-view",
  "cross-section": "cross-section-view",
  polar: "polar-view",
  reset: "reset-view",
  // "layer-framed" deliberately has none: switching the radiation layer on
  // already puts the camera on the oblique belt view, and a second command
  // would fight the one the explorer just issued.
};

function moveCamera(camera: ChainCamera) {
  const id = CAMERA_BUTTON[camera];
  if (id) control<HTMLButtonElement>(id)?.click();
}

function selectedTime(): Date {
  const slider = control<HTMLInputElement>("time-slider");
  const offset = slider ? Number(slider.value) : 0;
  return new Date(Date.now() + (Number.isFinite(offset) ? offset : 0) * 60000);
}

function seekMinutes(offsetMinutes: number) {
  const slider = control<HTMLInputElement>("time-slider");
  if (!slider) return;
  const clamped = Math.max(Number(slider.min), Math.min(Number(slider.max), Math.round(offsetMinutes)));
  slider.value = String(clamped);
  slider.dispatchEvent(new Event("input", { bubbles: true }));
  slider.dispatchEvent(new Event("change", { bubbles: true }));
}

/**
 * The explorer is ready when it has stamped its own freshness chip.
 *
 * `main.ts` adds `is-live` or `is-stale` to `#data-status` at the end of its
 * first render, and until then dispatching `change` on a layer checkbox would
 * be swallowed because the listener does not exist yet.
 */
function explorerReady(): boolean {
  const status = control("data-status");
  return !!status && (status.classList.contains("is-live") || status.classList.contains("is-stale"));
}

function whenExplorerReady(timeoutMs = 30_000): Promise<boolean> {
  if (explorerReady()) return Promise.resolve(true);
  return new Promise((resolve) => {
    const status = control("data-status");
    if (!status) { resolve(false); return; }
    let settled = false;
    const finish = (value: boolean) => {
      if (settled) return;
      settled = true;
      observer.disconnect();
      window.clearTimeout(timer);
      resolve(value);
    };
    const observer = new MutationObserver(() => { if (explorerReady()) finish(true); });
    observer.observe(status, { attributes: true, attributeFilter: ["class"] });
    const timer = window.setTimeout(() => finish(false), timeoutMs);
  });
}

// ---------------------------------------------------------------------------
// Small DOM helpers
// ---------------------------------------------------------------------------

function element<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  className?: string,
  text?: string,
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function evidenceChip(evidence: EvidenceClass, label: string): HTMLElement {
  const chip = element("span", `layer-status ${evidence}`, label);
  chip.title = EVIDENCE_MEANING[evidence];
  return chip;
}

// ---------------------------------------------------------------------------
// The sparkline
// ---------------------------------------------------------------------------

const SVG_NS = "http://www.w3.org/2000/svg";

function svgElement<K extends keyof SVGElementTagNameMap>(
  name: K,
  attributes: Record<string, string | number> = {},
): SVGElementTagNameMap[K] {
  const node = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
  return node;
}

/**
 * One quantity over the window the artifact publishes, with the selected
 * instant marked.
 *
 * Gaps stay gaps — `toSegments` is the same function the storm strip uses, so
 * a missing hour is a break in the line and never a straight bridge across it.
 * This is the "watch a storm develop" half of the feature: the number in the
 * card is one instant, and this is the shape it came from.
 */
function renderSeries(series: ChainSeries, at: Date): HTMLElement {
  const figure = element("figure", "chain-walk__spark chain-walk__figure");
  const width = 360;
  const height = 74;
  const padTop = 12;
  const padBottom = 16;

  const values = series.points.map((point) => point.value).filter((value): value is number => value !== null && Number.isFinite(value));
  const times = series.points.map((point) => point.t).filter((t) => Number.isFinite(t));
  if (!values.length || times.length < 2) {
    figure.append(element("figcaption", "chain-walk__figure-caption", `${series.label}: no drawable samples.`));
    return figure;
  }

  const from = Math.min(...times);
  const to = Math.max(...times);
  let low = Math.min(...values);
  let high = Math.max(...values);
  if (low === high) { low -= 1; high += 1; }
  const pad = (high - low) * 0.12;
  low -= pad;
  high += pad;

  const xOf = (t: number) => ((t - from) / Math.max(1, to - from)) * width;
  const yOf = (value: number) => padTop + (1 - (value - low) / (high - low)) * (height - padTop - padBottom);

  const svg = svgElement("svg", {
    class: "chain-walk__spark-chart",
    viewBox: `0 0 ${width} ${height}`,
    role: "img",
    "aria-label": `${series.label} over the published window`,
  });

  if (series.markZero && low < 0 && high > 0) {
    svg.append(svgElement("line", { class: "chain-walk__spark-zero", x1: 0, x2: width, y1: yOf(0), y2: yOf(0) }));
  }

  const segments = toSegments(series.points, series.maximumGapMs);
  if (series.shadeNegative && low < 0) {
    const zeroY = yOf(0);
    for (const segment of segments) {
      for (let step = 1; step < segment.length; step += 1) {
        const a = segment[step - 1]!;
        const b = segment[step]!;
        if (a.value >= 0 && b.value >= 0) continue;
        svg.append(svgElement("polygon", {
          class: "chain-walk__spark-southward",
          points: `${xOf(a.t)},${zeroY} ${xOf(a.t)},${yOf(Math.min(0, a.value))} ${xOf(b.t)},${yOf(Math.min(0, b.value))} ${xOf(b.t)},${zeroY}`,
        }));
      }
    }
  }
  for (const segment of segments) {
    if (segment.length < 2) continue;
    svg.append(svgElement("polyline", {
      class: "chain-walk__spark-trace",
      points: segment.map((point) => `${xOf(point.t)},${yOf(point.value)}`).join(" "),
    }));
  }

  const marker = at.getTime();
  if (marker >= from && marker <= to) {
    svg.append(svgElement("line", {
      class: "chain-walk__spark-now", x1: xOf(marker), x2: xOf(marker), y1: 0, y2: height - padBottom,
    }));
  }

  const left = svgElement("text", { class: "chain-walk__spark-axis", x: 0, y: height - 3 });
  left.textContent = new Date(from).toISOString().slice(5, 16).replace("T", " ");
  const right = svgElement("text", { class: "chain-walk__spark-axis", x: width, y: height - 3, "text-anchor": "end" });
  right.textContent = new Date(to).toISOString().slice(5, 16).replace("T", " ");
  svg.append(left, right);
  figure.append(svg);

  const caption = element("figcaption", "chain-walk__figure-caption");
  caption.append(document.createTextNode(`${series.label} · ${series.unit} · `));
  caption.append(evidenceChip(series.evidence, series.evidence.toUpperCase()));
  figure.append(caption);
  return figure;
}

/**
 * One number on an axis, against the fixed distances it only means something
 * relative to.
 *
 * Nothing here is computed: every position comes from a value the card also
 * prints, and the evidence chip on the caption is the class of the live value,
 * not of the axis. A reference mark carries no chip because 6.6 R⊕ is a
 * definition rather than a reading.
 */
function renderScale(scale: ChainScale): HTMLElement {
  const figure = element("figure", "chain-walk__scale chain-walk__figure");
  const width = 360;
  const height = 46;
  const axisY = 26;
  const padX = 6;

  const span = Math.max(1e-6, scale.to - scale.from);
  const xOf = (value: number) => padX + ((value - scale.from) / span) * (width - padX * 2);

  const svg = svgElement("svg", {
    class: "chain-walk__scale-chart",
    viewBox: `0 0 ${width} ${height}`,
    role: "img",
    "aria-label": scale.live
      ? `${scale.label}: ${scale.live.label}, against ${scale.marks.map((mark) => mark.label).join(" and ")}`
      : scale.label,
  });

  if (scale.band) {
    svg.append(svgElement("rect", {
      class: "chain-walk__scale-band",
      x: xOf(scale.band.from), y: axisY - 7,
      width: Math.max(2, xOf(scale.band.to) - xOf(scale.band.from)), height: 14,
    }));
    const bandLabel = svgElement("text", {
      class: "chain-walk__scale-tick", x: xOf((scale.band.from + scale.band.to) / 2), y: axisY + 17, "text-anchor": "middle",
    });
    bandLabel.textContent = scale.band.label;
    svg.append(bandLabel);
  }

  svg.append(svgElement("line", {
    class: "chain-walk__scale-axis", x1: padX, x2: width - padX, y1: axisY, y2: axisY,
  }));

  for (const mark of scale.marks) {
    svg.append(svgElement("line", {
      class: "chain-walk__scale-mark", x1: xOf(mark.at), x2: xOf(mark.at), y1: axisY - 5, y2: axisY + 5,
    }));
    const label = svgElement("text", {
      class: "chain-walk__scale-tick", x: xOf(mark.at), y: axisY + 17, "text-anchor": "middle",
    });
    label.textContent = mark.label;
    svg.append(label);
  }

  if (scale.live) {
    const x = xOf(scale.live.at);
    svg.append(svgElement("line", {
      class: "chain-walk__scale-live", x1: x, x2: x, y1: axisY - 12, y2: axisY + 6,
    }));
    // The live label is anchored away from the edge it is nearest, so a
    // boundary parked at 15 R⊕ does not print its own value off the figure.
    const nearRight = x > width * 0.7;
    const value = svgElement("text", {
      class: "chain-walk__scale-value", x: nearRight ? x - 5 : x + 5, y: axisY - 15,
      "text-anchor": nearRight ? "end" : "start",
    });
    value.textContent = scale.live.label;
    svg.append(value);
  }

  figure.append(svg);
  const caption = element("figcaption", "chain-walk__figure-caption");
  caption.append(document.createTextNode(`${scale.label} · `));
  caption.append(evidenceChip(scale.evidence, scale.evidence.toUpperCase()));
  figure.append(caption);
  return figure;
}

// ---------------------------------------------------------------------------
// The walkthrough
// ---------------------------------------------------------------------------

interface ChainData {
  weather: SpaceWeatherBundle | null;
  manifest: ReleaseManifest | null;
  drap: DrapBundle | null;
}

/**
 * The panel, and the two rules its layout follows.
 *
 * ONE SURFACE NAME. `styles.css` reserves tracked uppercase monospace for the
 * name of a surface, and nothing subordinate to a surface is ever set that
 * way. This panel used to break that rule six times over — the chain rail,
 * the step's role line, every reading label, the figure captions, the handoff
 * heading, the limits summary and the replay button were all tracked
 * uppercase mono, so eight things shouted at one pitch and none of them
 * ranked. There is now exactly one: the panel's own name in the header. The
 * `.layer-status` evidence badges keep the treatment, which is the deliberate
 * exception the type system already documents: they are a stamp, not a
 * heading, and they outrank every rule here.
 *
 * THE STEP IS THE CONTENT. Measured on the shipped build at 1440x900: the
 * panel was 682 px tall and the step inside it had 295-314 px, so 54% of the
 * feature was header, verdict, rail and controls, and every card ran off the
 * bottom — 962 px hidden on link 01, 1,518 px on link 04, where the reader
 * saw one sixth of the card and never reached the Dst trace. The header now
 * carries the step's own title instead of a constant one, the rail is a
 * single-row progress track instead of a three-row block of chips, and the
 * counter has moved into the track rather than occupying a control row of its
 * own.
 */
class EnergyChainWalkthrough {
  private readonly panel: HTMLElement;
  private readonly railHost: HTMLElement;
  private readonly stepHost: HTMLElement;
  private readonly verdictHost: HTMLElement;
  private readonly headingHost: HTMLElement;
  private readonly counter: HTMLElement;
  private readonly replayButton: HTMLButtonElement;

  private open = false;
  private stepIndex = 0;
  private restoreLayers: Record<string, boolean> | null = null;
  private restoreOffsetMinutes = 0;
  private replayTimer = 0;
  private refreshTimer = 0;
  private restoreAdvancedOpen: boolean | null = null;
  private data: ChainData = { weather: null, manifest: null, drap: null };
  private drapRequested = false;
  private cameraTimers: number[] = [];
  private readerMovedCamera = false;
  /** Slider offset the step asked for, so a clock the explorer moves can be reported. */
  private stepOffsetMinutes: number | null = null;
  private clockMovedNote: string | null = null;
  private restoreMagnetopauseCut: boolean | null = null;

  constructor() {
    this.panel = element("section", "chain-walk");
    this.panel.id = PANEL_ID;
    this.panel.hidden = true;
    this.panel.tabIndex = -1;
    this.panel.setAttribute("aria-label", "Follow the energy: guided walkthrough of the coupled chain");
    this.panel.setAttribute("data-globe-label-occluder", "");

    // One line, not two: kicker, progress, close. The old header spent 60 px
    // on a kicker plus a title — "One system, from the Sun to the ground" —
    // that was identical on all eight steps, above a card that could not fit.
    // That sentence is the feature's pitch, so it has moved to the launcher,
    // where a reader is deciding whether to open it.
    const head = element("header", "chain-walk__head");
    head.append(element("span", "chain-walk__kicker", "FOLLOW THE ENERGY"));
    this.counter = element("span", "chain-walk__counter");
    head.append(this.counter);
    const close = element("button", "chain-walk__close", "×");
    close.type = "button";
    close.setAttribute("aria-label", "Close the walkthrough and put the layers back");
    close.addEventListener("click", () => this.close());
    head.append(close);
    this.panel.append(head);

    this.railHost = element("nav", "chain-walk__rail");
    this.railHost.setAttribute("aria-label", "Links in the chain");
    this.panel.append(this.railHost);

    this.headingHost = element("div", "chain-walk__step-head");
    this.panel.append(this.headingHost);

    // The whole-chain state is CONTEXT, so it folds. Open on the first step,
    // where it is the subject and where the invitation to start walking lives;
    // closed after that, where the reader has already read it and it was
    // costing four lines of a 390 px screen on every card. It is one tap, and
    // the headline - the sign of Bz, which is the whole switch - never folds.
    this.verdictHost = element("details", "chain-walk__verdict");
    this.panel.append(this.verdictHost);

    this.stepHost = element("div", "chain-walk__body");
    this.panel.append(this.stepHost);

    const foot = element("footer", "chain-walk__foot");
    const back = element("button", "chain-walk__nav", "← Back");
    back.type = "button";
    back.addEventListener("click", () => this.go(this.stepIndex - 1));
    const next = element("button", "chain-walk__nav chain-walk__nav--primary", "Next →");
    next.type = "button";
    next.addEventListener("click", () => this.go(this.stepIndex + 1));
    this.replayButton = element("button", "chain-walk__replay", "▶ Replay 48 h");
    this.replayButton.type = "button";
    this.replayButton.title = "Rewind to 48 hours ago and walk the published window forward, watching this step's numbers change.";
    this.replayButton.addEventListener("click", () => this.toggleReplay());
    foot.append(back, this.replayButton, next);
    this.panel.append(foot);

    // Inside the scene, so the panel is clipped and positioned by the same box
    // the globe is drawn in. If a build has no scene shell it is attached to
    // the document instead rather than not attached at all.
    const host = document.querySelector(".scene-shell");
    if (host) host.append(this.panel);
    else {
      this.panel.classList.add("chain-walk--detached");
      document.body.append(this.panel);
    }

    control("time-slider")?.addEventListener("input", () => { if (this.open) this.render(); });

    // Whether the card is clipped, said in the layout rather than left for the
    // reader to discover. Before this a card simply stopped mid-word at the
    // fold with no fade and no cue, which reads as broken text rather than as
    // more text.
    this.stepHost.addEventListener("scroll", () => this.markClipping());
    if (typeof ResizeObserver !== "undefined") {
      new ResizeObserver(() => this.markClipping()).observe(this.stepHost);
    }

    // The reader's hand always wins. Once they have moved the view themselves,
    // this step stops re-asserting its camera.
    for (const target of [control("scene"), ...Object.values(CAMERA_BUTTON).map((id) => control(id))]) {
      target?.addEventListener("pointerdown", () => { this.readerMovedCamera = true; }, { passive: true });
      target?.addEventListener("wheel", () => { this.readerMovedCamera = true; }, { passive: true });
    }
  }

  private markClipping() {
    const clipped = this.stepHost.scrollHeight - this.stepHost.clientHeight > 8;
    const atEnd = this.stepHost.scrollTop + this.stepHost.clientHeight >= this.stepHost.scrollHeight - 8;
    this.stepHost.classList.toggle("is-clipped", clipped && !atEnd);
  }

  // -- data ----------------------------------------------------------------

  private async load(): Promise<void> {
    try {
      const manifestUrl = new URL("data/manifest.json", document.baseURI);
      const manifest = await (await fetch(manifestUrl, { cache: "no-cache" })).json() as ReleaseManifest;
      const weatherUrl = new URL(manifest.spaceWeather.path, manifestUrl);
      // The filename is content-addressed, so the default cache is correct and
      // this is a free hit on the copy `main.ts` already fetched.
      const weather = await (await fetch(weatherUrl)).json() as SpaceWeatherBundle;
      this.data = { ...this.data, manifest, weather };
    } catch (error) {
      console.warn("Follow the energy: the published bundle could not be read", error);
      this.data = { ...this.data, manifest: null, weather: null };
    }
  }

  /**
   * The D-RAP bundle, fetched only when the reader reaches the X-ray branch.
   *
   * 96 KB on the wire, and the explorer downloads the same content-addressed
   * URL the moment the D-region layer is switched on — which this step does —
   * so the reader pays for it once either way.
   */
  private async loadDrap(): Promise<void> {
    if (this.drapRequested || !this.data.manifest?.drap) return;
    this.drapRequested = true;
    try {
      const manifestUrl = new URL("data/manifest.json", document.baseURI);
      const url = new URL(this.data.manifest.drap.path, manifestUrl);
      this.data = { ...this.data, drap: await (await fetch(url)).json() as DrapBundle };
      if (this.open) this.render();
    } catch (error) {
      console.warn("Follow the energy: the D-RAP bundle could not be read", error);
    }
  }

  /**
   * Whether this build draws the cusped boundaries.
   *
   * The magnetopause layer today is the Shue surface, which is smooth over the
   * poles by construction, and the magnetosphere work that would add the
   * cusped ones is in flight. Rather than guess, look for a control and let
   * the cusp step describe whichever build it finds itself in. Any checkbox or
   * toggle whose id or data attribute names the cusp counts.
   */
  private cuspControl(): HTMLInputElement | HTMLButtonElement | null {
    return document.querySelector<HTMLInputElement | HTMLButtonElement>(
      '[id^="layer-cusp"], [id$="-cusps"], [data-layer-block="cusps"] input[type=checkbox], [data-magnetopause-surface="cusped"]',
    );
  }

  private links(): ChainLink[] {
    const manifest = this.data.manifest;
    return chainLinks({
      weather: this.data.weather,
      drap: this.data.drap,
      cuspLayerDrawn: this.cuspControl() !== null,
      at: selectedTime(),
      coverage: {
        geospace: manifest?.geospace
          ? { validFrom: manifest.geospace.validFrom, validTo: manifest.geospace.validTo, frameCount: manifest.geospace.frameCount }
          : null,
        aurora: manifest?.aurora
          ? { validFrom: manifest.aurora.validFrom, validTo: manifest.aurora.validTo, frameCount: manifest.aurora.frameCount }
          : null,
        drap: manifest?.drap
          ? { validFrom: manifest.drap.validFrom, validTo: manifest.drap.validTo, frameCount: manifest.drap.frameCount }
          : null,
      },
    });
  }

  // -- open / close --------------------------------------------------------

  async start(): Promise<void> {
    if (this.open) { this.go(0); return; }

    // Leave whatever content view is up.
    //
    // #content-close is `display: none` above 820px — the top nav carries the
    // return there and the shell no longer floats a second back button over the
    // page. The element is still in the document at every width precisely so
    // this keeps working: a programmatic .click() fires the listener main.ts
    // bound to it whether or not the button is painted.
    control<HTMLButtonElement>("content-close")?.click();
    // NO MODE TO PUT THE EXPLORER INTO. This used to click
    // `[data-explorer-mode="environment"]` first, because Satellites mode hid
    // the layer controls this walkthrough drives and switching into it called
    // `hideAllLayers()`. The mode was retired on 2026-08-28 — a plotted layer
    // now persists whichever half of the rail is open — so the layers this
    // drives are reachable and un-erasable without asking for anything first.
    // The D-region layer lives behind a closed disclosure. The X-ray branch
    // switches it on, so open the disclosure too — otherwise a layer appears
    // on the globe with no visible control, which is worse than either state.
    const advanced = document.querySelector<HTMLDetailsElement>(".advanced-environment-details");
    if (advanced) {
      this.restoreAdvancedOpen = advanced.open;
      advanced.open = true;
    }

    // THE PANEL OPENS ON THE CLICK, NOT ON THE FETCH.
    //
    // This used to await `whenExplorerReady()` and a 1.4 MB bundle before it
    // showed anything, so pressing "Follow the energy" did nothing visible for
    // as long as those took — measured at over seven seconds on a loaded
    // machine, with no spinner, no panel and no acknowledgement of the press.
    // A reader presses it again, or decides it is broken. Every link is
    // written to be able to say it has no data, which is exactly what that
    // interval needs, so the panel draws the first card immediately and fills
    // in when the numbers land.
    this.restoreLayers = layerState();
    this.restoreMagnetopauseCut = control<HTMLInputElement>("magnetopause-cut")?.checked ?? null;
    const slider = control<HTMLInputElement>("time-slider");
    this.restoreOffsetMinutes = slider ? Number(slider.value) || 0 : 0;
    this.open = true;
    this.panel.hidden = false;
    this.stepIndex = 0;
    this.render();
    this.notifyOccluders();

    const ready = await whenExplorerReady();
    if (!this.data.weather) await this.load();
    // The reader may have closed it, or walked on, while the bundle was in
    // flight. Neither is a reason to yank them back to link 01.
    if (!this.open) return;
    if (!ready) {
      this.verdictHost.replaceChildren(element(
        "summary", "chain-walk__verdict-headline",
        "The explorer has not finished loading its data bundle, so the layers below may not respond yet.",
      ));
    }
    // The layer switches only work once `main.ts` has bound its listeners,
    // which is what `whenExplorerReady` waits for, so this is the first moment
    // the step can actually build its picture.
    this.applyStep();
    this.render();
    this.refreshTimer = window.setInterval(() => {
      void this.load().then(() => { if (this.open) this.render(); });
    }, DEFAULT_ARTIFACT_REFRESH_INTERVAL_MS);
    this.panel.focus();
  }

  close(): void {
    if (!this.open) return;
    this.stopReplay();
    window.clearInterval(this.refreshTimer);
    for (const timer of this.cameraTimers) window.clearTimeout(timer);
    this.cameraTimers = [];
    // The settings the walkthrough drives that are not managed layers go back
    // with them, at the value the reader had rather than at the walkthrough's.
    if (this.restoreMagnetopauseCut !== null) {
      this.setSetting("magnetopause-cut", this.restoreMagnetopauseCut);
      this.restoreMagnetopauseCut = null;
    }
    this.open = false;
    this.panel.hidden = true;
    if (this.restoreLayers) {
      for (const [key, on] of Object.entries(this.restoreLayers)) setLayer(key, on);
      this.restoreLayers = null;
    }
    seekMinutes(this.restoreOffsetMinutes);
    if (this.restoreAdvancedOpen !== null) {
      const advanced = document.querySelector<HTMLDetailsElement>(".advanced-environment-details");
      if (advanced) advanced.open = this.restoreAdvancedOpen;
      this.restoreAdvancedOpen = null;
    }
    this.notifyOccluders();
    control<HTMLButtonElement>(LAUNCHER_ID)?.focus();
  }

  private notifyOccluders() {
    control("scene")?.dispatchEvent(new CustomEvent("explorer:occluders-changed", { bubbles: true }));
  }

  // -- stepping ------------------------------------------------------------

  private go(index: number) {
    const links = this.links();
    this.stepIndex = Math.max(0, Math.min(links.length - 1, index));
    this.applyStep();
    this.render();
    // A new step starts at its own beginning. Without this the reader presses
    // Next while scrolled to the bottom of a long card and lands halfway down
    // the next one, which reads as a missing heading.
    this.panel.scrollTop = 0;
    this.stepHost.scrollTop = 0;
  }

  /** Set an explorer checkbox that is not one of the managed layers. */
  private setSetting(id: string, on: boolean) {
    const box = control<HTMLInputElement>(id);
    if (!box || box.checked === on) return;
    box.checked = on;
    box.dispatchEvent(new Event("change", { bubbles: true }));
  }

  /** Switch on exactly what this step needs and switch off everything else it manages. */
  private applyStep() {
    const links = this.links();
    const step = links[this.stepIndex];
    if (!step) return;
    this.readerMovedCamera = false;
    this.clockMovedNote = null;
    const slider = control<HTMLInputElement>("time-slider");
    this.stepOffsetMinutes = slider ? Number(slider.value) || 0 : null;

    const wanted = new Set(step.layersOn);
    for (const key of CHAIN_MANAGED_LAYERS) setLayer(key, wanted.has(key));

    // This step teaches from the BATS-R-US colours — the shock as a jump, the
    // sheath as a band. The magnetosphere layer opens on the 3-D field lines,
    // so the step switches the embedded MHD cross-section on before its
    // cross-section camera looks at it face-on.
    this.setSetting("geospace-mhd-cut", step.id === "boundary");
    // The walkthrough owns the boundary presentation for its duration and
    // hands it back on close. Every step wants the closed surfaces: the cut
    // profile curves are hairlines, and on the cusp card - the one step where
    // cutting them open sounded right - they photographed as two thin arcs in
    // an empty frame. A reader who arrives with the surfaces already cut open
    // would otherwise get a different picture from every other reader on the
    // same step.
    this.setSetting("magnetopause-cut", false);

    if (step.id === "dregion") void this.loadDrap();
    this.applyCamera(step.camera);
    this.watchClock();
  }

  /**
   * Hold the step's camera against the explorer's own asynchronous re-framing.
   *
   * A single command at +60 ms was being thrown away. `globe.ts` calls
   * `frameActiveLayers()` when the geospace bundle finishes arriving — the
   * comment there says so outright, "the bundle arrives asynchronously, well
   * after the toggle that requested it already re-framed the view" — and that
   * bundle is 2.7 MB. Measured on the shipped build at 1440x900: link 02 asks
   * for the meridional cross-section and was photographed in the oblique
   * magnetosphere frame in every one of six runs, so the card that teaches
   * from a face-on cut was never showing one.
   *
   * So the step re-asserts its camera on a short schedule that covers the
   * arrival, and stops the moment the reader touches the scene or presses a
   * camera button themselves. Their hand always wins; the explorer's
   * housekeeping does not.
   */
  private applyCamera(camera: ChainCamera) {
    for (const timer of this.cameraTimers) window.clearTimeout(timer);
    // The last beat is at nine seconds because the bundle has been measured
    // arriving after six on a loaded machine. It is late enough to be slightly
    // rude if the reader is already reading, and that is the right trade: a
    // card that teaches from a face-on cut and never shows one is worse.
    this.cameraTimers = [60, 900, 2200, 4500, 9000].map((delay) => window.setTimeout(() => {
      if (this.open && !this.readerMovedCamera) moveCamera(camera);
    }, delay));
  }

  /**
   * Say so when the explorer moves the clock out from under a step.
   *
   * Switching on a layer whose feed has not reached the present moves the
   * timeline back to that layer's newest published frame — deliberately, and
   * for a good reason, but it means the reader watches the time and the
   * whole-chain verdict change with no explanation. Measured on 2026-08-19:
   * link 06 moved the clock 164 minutes back and the verdict flipped from
   * "the switch is on" to "the switch is off" between one Next and the next.
   */
  private watchClock() {
    const before = this.stepOffsetMinutes;
    if (before === null) return;
    // Polled rather than checked once, because the seek happens when the
    // LAYER'S OWN archive lands: OVATION's history is a separate fetch, so the
    // clock moved 164 minutes about three seconds after the step began and a
    // single check at 900 ms saw nothing.
    for (const delay of [900, 2500, 5000, 9000]) {
      window.setTimeout(() => {
        if (!this.open || this.clockMovedNote) return;
        const slider = control<HTMLInputElement>("time-slider");
        const after = slider ? Number(slider.value) || 0 : 0;
        if (Math.abs(after - before) < 2) return;
        this.clockMovedNote =
          `This step's layer has published nothing for the time you were on, so the explorer moved the clock to ${utcLabel(selectedTime().toISOString())} — `
          + "its newest published frame. Every number below is for that time, not the one you arrived with.";
        this.render();
      }, delay);
    }
  }

  // -- replay --------------------------------------------------------------

  private toggleReplay() {
    if (this.replayTimer) { this.stopReplay(); return; }
    let frame = 0;
    this.replayButton.textContent = "■ Stop";
    this.replayButton.classList.add("is-playing");
    seekMinutes(-REPLAY_SPAN_MINUTES);
    this.replayTimer = window.setInterval(() => {
      frame += 1;
      if (frame > REPLAY_FRAMES) { this.stopReplay(); return; }
      seekMinutes(-REPLAY_SPAN_MINUTES + (REPLAY_SPAN_MINUTES * frame) / REPLAY_FRAMES);
      this.render();
    }, REPLAY_FRAME_MS);
  }

  private stopReplay() {
    if (this.replayTimer) window.clearInterval(this.replayTimer);
    this.replayTimer = 0;
    this.replayButton.textContent = "▶ Replay 48 h";
    this.replayButton.classList.remove("is-playing");
  }

  // -- drawing -------------------------------------------------------------

  private render() {
    const links = this.links();
    const step = links[this.stepIndex];
    if (!step) return;
    const at = selectedTime();
    const chainSteps = chainLength(links);

    // The counter counts the CHAIN. The branch used to be numbered "8 of 8"
    // by a card whose own first line said "not part of the chain", which is a
    // contradiction the reader has no way to settle.
    this.counter.textContent = step.partOfChain
      ? `Link ${this.stepIndex + 1} of ${chainSteps}`
      : `Branch · ${step.index}`;
    this.counter.title = utcLabel(at.toISOString());

    this.renderRail(links);

    // The step's own name is the panel's heading. There is no second title
    // above it, and the role and index that used to be reprinted here from
    // the rail chip are now only in the track.
    // Role and badge share one row and the title gets the full width beneath
    // them. Beside the title the badge was taking nearly half the row, and
    // "GOES XRS OBSERVED · BEAM ILLUSTRATIVE" broke "The one input that is not
    // deflected" over three lines — a badge is the reader's first answer to
    // "how much should I believe this" and must stay whole, so the title is
    // the one that moves.
    this.headingHost.replaceChildren();
    const meta = element("div", "chain-walk__step-meta");
    meta.append(element("p", "chain-walk__step-role", step.role));
    const badge = evidenceChip(step.evidence, step.badge);
    badge.classList.add("chain-walk__step-badge");
    meta.append(badge);
    this.headingHost.append(meta);
    this.headingHost.append(element("h2", "chain-walk__step-title", step.title));

    const verdict = chainVerdict({ weather: this.data.weather, at });
    this.verdictHost.replaceChildren();
    this.verdictHost.dataset.state = verdict.state;
    const summary = element("summary", "chain-walk__verdict-headline", verdict.headline);
    this.verdictHost.append(summary);
    const detail = element("p", "chain-walk__verdict-detail", verdict.detail);
    // The invitation is true once, at the top of the walk.
    if (this.stepIndex === 0) detail.append(document.createTextNode(` ${verdict.invitation}`));
    this.verdictHost.append(detail);
    (this.verdictHost as HTMLDetailsElement).open = this.stepIndex === 0;

    this.stepHost.replaceChildren(this.renderStep(step, at));
    this.markClipping();
  }

  /**
   * The chain as a track, not a tag cloud.
   *
   * Eight chips, each carrying its number AND its role in tracked uppercase
   * monospace, wrapped onto three ragged rows and filled 90 px of a panel
   * whose card had 300. Nothing about that shape said "sequence" and nothing
   * said "you are three of the way through": it read as a list of topics, and
   * the reader's position in it was carried only by a border colour. It is
   * now one row of numbered nodes on a line, with the branch set off after a
   * gap because it is not on the line. The role words moved to the step's own
   * heading, where there is one of them instead of eight.
   */
  private renderRail(links: readonly ChainLink[]) {
    this.railHost.replaceChildren();
    const track = element("ol", "chain-walk__track");
    let branchStarted = false;
    links.forEach((link, index) => {
      const item = element("li", "chain-walk__track-item");
      if (!link.partOfChain && !branchStarted) {
        branchStarted = true;
        item.classList.add("chain-walk__track-item--branch-start");
      }
      if (!link.partOfChain) item.classList.add("is-branch");
      const node = element("button", "chain-walk__node", link.partOfChain ? link.index : link.index.replace("X", "✳"));
      node.type = "button";
      node.classList.toggle("is-active", index === this.stepIndex);
      node.classList.toggle("is-done", link.partOfChain && index < this.stepIndex);
      node.title = `${link.role} — ${link.title}`;
      node.setAttribute("aria-label", `${link.partOfChain ? `Link ${link.index}` : "Branch"}: ${link.title}`);
      node.setAttribute("aria-current", index === this.stepIndex ? "step" : "false");
      node.addEventListener("click", () => this.go(index));
      item.append(node);
      track.append(item);
    });
    this.railHost.append(track);
  }

  /** One block of prose with a bold lead-in, which is most of this card. */
  private static note(className: string, lead: string, body: string): HTMLElement {
    const note = element("p", className);
    note.append(element("b", "", lead));
    note.append(document.createTextNode(body));
    return note;
  }

  private renderStep(step: ChainLink, at: Date): HTMLElement {
    const article = element("article", "chain-walk__step");

    // The one idea, first and alone.
    article.append(element("p", "chain-walk__what", step.what));

    // Then what the reader is actually looking at. This comes before the
    // numbers because it is the caption for the picture the step just built,
    // and a reader who has been moved to a plasmasphere and told it is a ring
    // current will not trust anything under it.
    article.append(EnergyChainWalkthrough.note("chain-walk__globe", "On the globe  ", step.onTheGlobe));

    if (step.missing) {
      article.append(EnergyChainWalkthrough.note("chain-walk__missing", "Not published for this time. ", step.missing));
    }
    if (this.clockMovedNote) {
      article.append(EnergyChainWalkthrough.note("chain-walk__timenote", "The clock moved. ", this.clockMovedNote));
    }
    if (step.timeNote) {
      article.append(EnergyChainWalkthrough.note("chain-walk__timenote", "These numbers do not follow the timeline. ", step.timeNote));
    }
    // What is *not* on the globe comes before the numbers, not after them: a
    // reader who has just been moved to a bare Earth needs to know that is the
    // answer and not a fault.
    for (const absent of step.layersNotBuilt) {
      article.append(EnergyChainWalkthrough.note("chain-walk__absent", `${absent.label}: not drawn. `, absent.because));
    }

    // The drawn number before the printed ones. It used to come after every
    // reading, which on link 01 put the 48-hour Bz trace — the picture the
    // step is about — 962 px below the fold.
    if (step.scale) article.append(renderScale(step.scale));
    if (step.series) article.append(renderSeries(step.series, at));

    if (step.readings.length) {
      const list = element("dl", "chain-walk__readings");
      for (const reading of step.readings) {
        const term = element("dt", "chain-walk__reading-label");
        term.append(document.createTextNode(reading.label));
        term.append(evidenceChip(reading.evidence, reading.evidence.toUpperCase()));
        const value = element("dd", "chain-walk__reading-value");
        // A number goes in the readout face; a word does not. "magnetopause
        // current sheet" set in tabular monospace at readout size read as a
        // measurement whose units had been lost.
        const shown = element("strong", reading.kind === "name" ? "chain-walk__reading-name" : "chain-walk__reading-number", reading.value);
        value.append(shown);
        if (reading.at) value.append(element("small", "chain-walk__reading-at", utcLabel(reading.at)));
        if (reading.note) value.append(element("small", "chain-walk__reading-note", reading.note));
        list.append(term, value);
      }
      article.append(list);
    }

    if (step.handoff) {
      article.append(EnergyChainWalkthrough.note(
        "chain-walk__handoff",
        step.id === "ground" ? "What this costs you  " : "What this does next  ",
        step.handoff,
      ));
    }

    const limit = element("details", "chain-walk__limit");
    limit.append(element("summary", "", "What this step cannot tell you"));
    limit.append(element("p", "", step.limit));
    if (step.sources.length) {
      const sources = element("ul", "chain-walk__sources");
      for (const source of step.sources) {
        const item = element("li");
        const anchor = element("a", "", source.label);
        anchor.href = source.url;
        anchor.target = "_blank";
        anchor.rel = "noreferrer";
        item.append(anchor);
        sources.append(item);
      }
      limit.append(sources);
    }
    article.append(limit);

    return article;
  }
}

// ---------------------------------------------------------------------------
// Getting in
// ---------------------------------------------------------------------------

/**
 * Put the way in where the reader already is.
 *
 * Two doors, because the two audiences arrive from different places: someone
 * reading the lessons finds it at the top of "Learn space weather", which is
 * where the same chain is currently taught as prose with none of the live
 * numbers attached — and someone already turning layers on and off finds it
 * INSIDE THE MAGNETOSPHERE LAYER'S OWN CARD.
 *
 * That second placement is the one Sean sent this work back over: "for
 * magnetosphere — the follow the energy link placement doesn't make sense in
 * the rail. perhaps we have that in the card somewhere?" He is right, and the
 * reason is worth writing down. Sitting loose between two layer rows, the
 * launcher belonged to nothing: it had a border, it spanned the column, and
 * the only thing it could plausibly be about was whichever layer it happened
 * to land under, which changed with the preset. In the magnetosphere card it
 * has an owner, and the owner is the correct one — that layer is the only one
 * on this site whose subject is the COUPLING rather than a single field. Links
 * 02 to 05 of the walkthrough are all views of it: the boundary is its
 * surface, the cusps are folds in that surface, the ring current and the belts
 * are what lives inside it. A reader who has just switched on "Magnetosphere"
 * and is looking at field lines is exactly the reader who wants to know what
 * drives them and what they drive.
 *
 * It is subordinate to the layer, not competing with it: no border, no fill,
 * indented to the layer's own descriptive line. The rail's standing rule holds
 * — the layers are the content of that column and everything else is smaller
 * than the layers.
 *
 * Both doors are injected at runtime rather than written into `index.html`, so
 * this feature adds exactly one line to a file it does not own.
 */
function installLaunchers(walkthrough: EnergyChainWalkthrough) {
  const launcher = element("button", "chain-walk__launch chain-walk__launch--card", "Follow the energy →");
  launcher.id = LAUNCHER_ID;
  launcher.type = "button";
  launcher.append(element("small", "", "One system, from the Sun to the ground — walked one link at a time, with this layer at the middle of it."));
  launcher.addEventListener("click", () => void walkthrough.start());

  // THE MAGNETOSPHERE'S DATA-EXPLORER CARD. Not the rail, at any nesting.
  //
  // Sean asked twice. First: "for magnetosphere - the follow the energy link
  // placement doesn't make sense in the rail. perhaps we have that in the card
  // somewhere?" That was read as "put it inside the magnetosphere's rail ROW",
  // which is still the rail, and he said so again in blunter terms. The rail is
  // a control surface — switches for fields over the globe — and a guided
  // walkthrough is not a switch. The card is where a reader has already chosen
  // that layer and is reading about it, which is the moment the offer means
  // something.
  //
  // The card is built at runtime whenever the layer is switched on, so this
  // waits for it rather than assuming it exists at install time.
  const mountIntoCard = () => {
    if (!launcher.isConnected || launcher.dataset.mounted !== "card") {
      const card = document.querySelector('#data-viewer-cards [data-layer="geospace"]')
        ?? document.querySelector('[data-layer-panel="geospace"]');
      if (card) {
        card.append(launcher);
        launcher.dataset.mounted = "card";
        return true;
      }
    }
    return false;
  };

  if (!mountIntoCard()) {
    // The card does not exist until the layer is on. Watch for it, rather than
    // falling back into the rail — a wrong home that ships is worse than a
    // door that appears a moment later, and this one has now been wrong twice.
    const cards = document.getElementById("data-viewer-cards") ?? document.body;
    const observer = new MutationObserver(() => { if (mountIntoCard()) observer.disconnect(); });
    observer.observe(cards, { childList: true, subtree: true });
  }

  // The lessons view teaches this chain in prose. Offer the live one from the
  // top of it, and rebuild the offer each time the view is opened because
  // `main.ts` replaces the whole of `#content-body` on every navigation.
  document.querySelector<HTMLButtonElement>('[data-view="learn-weather"]')?.addEventListener("click", () => {
    window.setTimeout(() => {
      const body = document.getElementById("content-body");
      if (!body || document.getElementById(LEARN_LAUNCHER_ID)) return;
      const card = element("button", "chain-walk__launch chain-walk__launch--lesson", "Follow the energy on the live globe →");
      card.id = LEARN_LAUNCHER_ID;
      card.type = "button";
      card.append(element("small", "", "These eight lessons describe the chain. This walks it, on the globe, with the number each link is reading right now."));
      card.addEventListener("click", () => void walkthrough.start());
      // Between the hero and the lesson cards: the reader has just been told
      // the track is called "follow energy from the Sun to a system effect",
      // which is the moment to offer the live version of exactly that. It also
      // keeps clear of the floating "back to explorer" control.
      const grid = body.querySelector(".lesson-grid");
      if (grid?.parentElement) grid.parentElement.insertBefore(card, grid);
      else body.prepend(card);
    }, 0);
  });
}

if (typeof document !== "undefined") {
  const walkthrough = new EnergyChainWalkthrough();
  installLaunchers(walkthrough);
}

export { EnergyChainWalkthrough };
