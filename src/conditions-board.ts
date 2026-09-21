/**
 * The conditions board — the first thing on the awareness page.
 *
 * The site had every number NOAA publishes and no place that answered "is
 * anything happening, how big is it, and what is it doing" in one look. The
 * NOAA scales sat about fifteen hundred pixels down the page under a headline
 * set at seventy-four pixels; the drivers were spread between the map key over
 * the globe, the storm popover in the top bar, and the layer cards. Sean, on
 * the site as a whole: "It needs to tell a story with one glance. It needs to
 * have the important data on it."
 *
 * This module is that glance, and nothing else. It draws:
 *
 *   - the three NOAA scales, R S G, at the size of a headline rather than the
 *     size of a footnote, coloured by severity, with the rolling 24-hour
 *     maximum under each so a quiet instant during a busy day still says so;
 *   - five drivers, each as a number AND a line, because a number alone
 *     cannot say "and it has been falling for six hours".
 *
 * ## What it will not do
 *
 * Every tile states its own evidence class in a `.layer-status` badge, the
 * same badge the layer rail and the method cards use, and the badge is part of
 * the tile rather than a caption under it.
 *
 * A tile with no published value draws NO line. This is the whole reason
 * `sparkline` returns null instead of an empty path: a flat line across an
 * empty panel is a claim that the quantity was measured and did not change,
 * which is the exact failure mode a prettier layout invites. Missing is drawn
 * as missing, in words.
 *
 * Dst is named by its source in the tile itself. There are three Dst traces in
 * this site and they are never merged (`storm-indices.ts` explains why); a
 * board that printed "Dst −29 nT" without saying which one would be asserting
 * a measurement the site does not have.
 */

import type { SwpcScaleReading, TimeValue } from "./types";

// ---------------------------------------------------------------------------
// Sparkline geometry
// ---------------------------------------------------------------------------

export interface SparklineOptions {
  /** Fixed value domain. Kp is 0–9 whatever today did; speed is not. */
  domain?: [number, number];
  /** Applied to every value before scaling — log10 for X-ray flux. */
  transform?: (value: number) => number;
  /** Pad the auto domain so a flat-ish trace is not drawn as a jagged one. */
  minSpan?: number;
}

export interface Sparkline {
  /** The trace. */
  d: string;
  /** The same trace closed to the floor of the box, for a soft fill. */
  areaD: string;
  /** y of value 0, or null when the drawn range does not contain zero. */
  zeroY: number | null;
  /** The newest drawn point, so the tile can put a dot on it. */
  lastX: number;
  lastY: number;
  /** Extremes in the PUBLISHED units, never the transformed ones: the X-ray
      trace is scaled by log10 to be drawable, and a range line reading
      "−6.2 to −5.3" is a number nobody measured. */
  min: number;
  max: number;
  count: number;
  /** Wall-clock span actually covered by the drawn points. */
  spanHours: number | null;
}

/**
 * A trace, or null when there is not enough published data to draw one.
 *
 * Null on fewer than two finite samples is deliberate and load-bearing: one
 * sample is a value, not a history, and drawing it as a line across the box
 * would invent the rest of the box.
 *
 * x is real time, not sample index, so a gap in the feed reads as a long flat
 * segment rather than being silently closed up.
 */
export function sparkline(
  series: readonly TimeValue[],
  width: number,
  height: number,
  options: SparklineOptions = {},
): Sparkline | null {
  const transform = options.transform ?? ((value: number) => value);
  const points: Array<{ t: number; v: number; raw: number }> = [];
  for (const sample of series) {
    if (sample.value === null || !Number.isFinite(sample.value)) continue;
    const t = Date.parse(sample.time);
    if (!Number.isFinite(t)) continue;
    const v = transform(sample.value);
    if (!Number.isFinite(v)) continue;
    points.push({ t, v, raw: sample.value });
  }
  if (points.length < 2) return null;
  points.sort((a, b) => a.t - b.t);

  const rawMin = Math.min(...points.map((p) => p.v));
  const rawMax = Math.max(...points.map((p) => p.v));
  let lo = options.domain ? options.domain[0] : rawMin;
  let hi = options.domain ? options.domain[1] : rawMax;
  if (!options.domain) {
    const span = Math.max(hi - lo, options.minSpan ?? 0);
    const mid = (hi + lo) / 2;
    lo = mid - span / 2;
    hi = mid + span / 2;
  }
  if (!(hi > lo)) { hi = lo + 1; lo -= 1; }

  const t0 = points[0]!.t;
  const t1 = points[points.length - 1]!.t;
  const timeSpan = t1 - t0 || 1;
  const x = (t: number) => ((t - t0) / timeSpan) * width;
  const y = (v: number) => height - ((v - lo) / (hi - lo)) * height;

  const coords = points.map((p) => [x(p.t), Math.min(height, Math.max(0, y(p.v)))] as const);
  const d = coords.map(([px, py], i) => `${i === 0 ? "M" : "L"}${px.toFixed(2)} ${py.toFixed(2)}`).join(" ");
  const areaD = `${d} L${coords[coords.length - 1]![0].toFixed(2)} ${height} L${coords[0]![0].toFixed(2)} ${height} Z`;
  const zeroInside = lo <= 0 && hi >= 0;

  return {
    d,
    areaD,
    zeroY: zeroInside ? y(0) : null,
    lastX: coords[coords.length - 1]![0],
    lastY: coords[coords.length - 1]![1],
    min: Math.min(...points.map((point) => point.raw)),
    max: Math.max(...points.map((point) => point.raw)),
    count: points.length,
    spanHours: (t1 - t0) / 3_600_000,
  };
}

// ---------------------------------------------------------------------------
// The model
// ---------------------------------------------------------------------------

/** The evidence classes this board uses; the same words the badges carry. */
export type EvidenceClass = "observed" | "assimilated" | "model" | "forecast" | "empirical";

/**
 * A tile's badge, built FROM its evidence class so the word and the class
 * cannot disagree.
 *
 * They did. The board's five tiles each carried `{ text: "OBSERVED", evidence:
 * <looked up from the release> }`, and four of those lookups can legitimately
 * return "assimilated", "model" or "forecast" — `sourceEvidence` in `main.ts`
 * reads the status the pipeline published for that product — while the fifth
 * follows whichever of three Dst traces the classifier settled on, one of
 * which is the SWMF nowcast. So the moment an upstream product changed class,
 * the tile printed the word OBSERVED in the colour of a model, which is the
 * single thing this board exists not to do. No test could see it, because the
 * badge is only ever wrong for data the fixtures do not carry.
 *
 * Deriving the word removes the failure mode rather than checking for it. A
 * tile that wants different words needs a different type, not a second string
 * beside this one.
 */
export function evidenceBadge(evidence: EvidenceClass): { text: string; evidence: EvidenceClass } {
  return { text: evidence.toUpperCase(), evidence };
}

export interface DriverTile {
  key: string;
  /** What the quantity is, in words a reader can act on. */
  label: string;
  /** The evidence badge. Never omitted, never abbreviated away. */
  badge: { text: string; evidence: EvidenceClass };
  /** The printed value, already formatted, or null when nothing is published. */
  valueText: string | null;
  unit: string;
  /** Why there is no value, said out loud rather than left as a dash. */
  missingReason: string;
  series: readonly TimeValue[];
  spark: SparklineOptions;
  /** One line under the trace: what it is, what it is not. */
  note: string;
  /** Overrides how the range line prints its two extremes. X-ray flux is
      published in W/m2 and read in flare classes; printing 9.0e-7 would be
      accurate and useless. */
  rangeFormat?: (min: number, max: number) => string;
  /** Colour role for the trace, from the site palette. */
  accent: string;
}

export interface ScaleTile {
  prefix: "R" | "S" | "G";
  label: string;
  level: number | null;
  levelText: string;
  description: string;
  /** The rolling 24-hour maximum for the same scale, phrased for a reader. */
  dayMax: string;
}

const MINUS = "−";

/**
 * Upstream prose sets a hyphen where a minus belongs.
 *
 * The classifier's own sentence — "Dst at or below -30 nT and still falling" —
 * is published as text by the pipeline and is now the largest sentence on the
 * awareness page, where a hyphen beside 30 reads as a dash and not as a sign.
 * Only a hyphen immediately before a digit is touched, so hyphenated words and
 * ranges written with an en dash are left exactly as published.
 */
export function withMinusSigns(text: string): string {
  return text.replace(/(^|[\s(\[])-(?=\d)/g, `$1${MINUS}`);
}

/** `−29` rather than `-29`: the site sets minus signs, not hyphens. */
export function signed(value: number, digits = 0): string {
  return `${value < 0 ? MINUS : ""}${Math.abs(value).toFixed(digits)}`;
}

export function scaleTile(
  prefix: "R" | "S" | "G",
  label: string,
  latest: SwpcScaleReading,
  dayMaximum: SwpcScaleReading,
): ScaleTile {
  return {
    prefix,
    label,
    level: latest.level,
    levelText: latest.level === null ? `${prefix}—` : `${prefix}${latest.level}`,
    description: latest.level === null
      ? "NOAA published no value"
      : latest.level === 0
        ? "Below NOAA scale threshold"
        : latest.label ?? "NOAA scale event",
    // The instant can be quiet inside a day that was not. Saying so is the
    // difference between "nothing is happening" and "nothing is happening
    // right this minute", and only one of those is true.
    dayMax: dayMaximum.level === null
      ? "24 h maximum not published"
      : dayMaximum.level === 0
        ? "Quiet for 24 h"
        : `24 h maximum ${prefix}${dayMaximum.level}${dayMaximum.label ? ` · ${dayMaximum.label}` : ""}`,
  };
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

const SVG = "http://www.w3.org/2000/svg";
/** The drawn box. `preserveAspectRatio="none"` stretches it to the tile. */
const SPARK_W = 220;
const SPARK_H = 40;

function el<K extends keyof HTMLElementTagNameMap>(tag: K, className?: string, text?: string) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

export function renderScaleTile(tile: ScaleTile): HTMLElement {
  const article = el("article", "now-scale");
  // The level drives the colour, and an unpublished level gets no colour at
  // all rather than the green that would read as "all clear".
  article.dataset.level = tile.level === null ? "" : String(tile.level);
  article.append(
    el("span", "now-scale-name", tile.label),
    el("strong", "now-scale-level", tile.levelText),
    el("small", "now-scale-note", tile.description),
    el("small", "now-scale-day", tile.dayMax),
  );
  return article;
}

/**
 * One driver: the number, the trace, and the badge that says what kind of
 * claim both of them are.
 *
 * The order is deliberate — badge before value. A reader who takes only the
 * top line of a tile has to have taken the evidence class with it.
 */
export function renderDriverTile(tile: DriverTile): HTMLElement {
  const article = el("article", "now-driver");
  article.style.setProperty("--accent", tile.accent);

  const head = el("header", "now-driver-head");
  head.append(el("span", "now-driver-label", tile.label));
  const badge = el("em", `layer-status ${tile.badge.evidence}`, tile.badge.text);
  head.append(badge);
  article.append(head);

  const value = el("p", "now-driver-value");
  if (tile.valueText === null) {
    value.classList.add("is-missing");
    value.append(el("strong", undefined, "—"));
  } else {
    value.append(el("strong", undefined, tile.valueText));
    if (tile.unit) value.append(el("small", undefined, tile.unit));
  }
  article.append(value);

  const spark = tile.valueText === null ? null : sparkline(tile.series, SPARK_W, SPARK_H, tile.spark);
  if (spark) {
    const svg = document.createElementNS(SVG, "svg");
    svg.setAttribute("class", "now-spark");
    svg.setAttribute("viewBox", `0 0 ${SPARK_W} ${SPARK_H}`);
    svg.setAttribute("preserveAspectRatio", "none");
    // The trace is decoration for the number beside it; the number and the
    // range line below carry the same information to a screen reader.
    svg.setAttribute("aria-hidden", "true");
    if (spark.zeroY !== null) {
      const zero = document.createElementNS(SVG, "line");
      zero.setAttribute("x1", "0");
      zero.setAttribute("x2", String(SPARK_W));
      zero.setAttribute("y1", spark.zeroY.toFixed(2));
      zero.setAttribute("y2", spark.zeroY.toFixed(2));
      zero.setAttribute("class", "now-spark-zero");
      svg.append(zero);
    }
    const area = document.createElementNS(SVG, "path");
    area.setAttribute("d", spark.areaD);
    area.setAttribute("class", "now-spark-area");
    const line = document.createElementNS(SVG, "path");
    line.setAttribute("d", spark.d);
    line.setAttribute("class", "now-spark-line");
    // vector-effect keeps the stroke 1.4 px after the non-uniform stretch;
    // without it a 220x40 box scaled to 240x34 draws a visibly fatter line
    // horizontally than vertically.
    line.setAttribute("vector-effect", "non-scaling-stroke");
    const dot = document.createElementNS(SVG, "circle");
    dot.setAttribute("cx", spark.lastX.toFixed(2));
    dot.setAttribute("cy", spark.lastY.toFixed(2));
    dot.setAttribute("r", "2.4");
    dot.setAttribute("class", "now-spark-dot");
    dot.setAttribute("vector-effect", "non-scaling-stroke");
    svg.append(area, line, dot);
    article.append(svg);
  } else {
    // No trace, and the box says why rather than sitting empty.
    article.append(el("p", "now-spark-absent", tile.valueText === null
      ? tile.missingReason
      : "No series published for this window."));
  }

  if (spark) {
    // What the trace covers and how far it moved, in the mono voice the rest
    // of the site uses for numbers. It also carries the range to a reader who
    // cannot see the line at all.
    article.append(el("p", "now-driver-range",
      `${describeSpan(spark.spanHours)} · ${tile.rangeFormat ? tile.rangeFormat(spark.min, spark.max) : formatRange(spark.min, spark.max, tile.unit)}`));
  }
  if (tile.note) article.append(el("p", "now-driver-note", tile.note));
  return article;
}

/**
 * A GOES 0.1-0.8 nm flux in W/m2 as its flare class.
 *
 * The letters are decades on a fixed grid - A at 1e-8, B at 1e-7, C at 1e-6,
 * M at 1e-5, X at 1e-4 - and the digit is the mantissa within the decade.
 * Below A1 there is no class, and NOAA does not invent one, so neither does
 * this: it says so.
 */
export function flareClass(fluxWm2: number): string {
  if (!Number.isFinite(fluxWm2) || fluxWm2 < 1e-8) return "below A1";
  const letters = ["A", "B", "C", "M", "X"] as const;
  const decade = Math.min(4, Math.floor(Math.log10(fluxWm2)) + 8);
  const mantissa = fluxWm2 / 10 ** (decade - 8);
  return `${letters[decade]}${mantissa.toFixed(1)}`;
}

function describeSpan(hours: number | null): string {
  if (hours === null || !Number.isFinite(hours) || hours <= 0) return "single window";
  if (hours < 1.5) return `${Math.round(hours * 60)} min`;
  if (hours < 48) return `${Math.round(hours)} h`;
  return `${Math.round(hours / 24)} d`;
}

function formatRange(min: number, max: number, unit: string): string {
  const digits = Math.abs(max) < 10 && Math.abs(min) < 10 ? 1 : 0;
  return `${signed(min, digits)} to ${signed(max, digits)}${unit ? ` ${unit}` : ""}`;
}
