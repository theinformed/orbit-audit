import "./storm-panel.css";

import {
  type StripRow,
  type StormDriverSample,
  type StormIndices,
  type StormPhase,
  drawableRows,
  ringCurrentNarrative,
  stormNarrativeAt,
  stormStripRows,
  stripWindow,
  toSegments,
} from "./storm-indices";

/**
 * The storm strip chart: cause to effect, top to bottom, on one time axis.
 *
 * The design calls this the thing to build first, and the reason is that a
 * storm is a *sequence*, not a number. Six rows share a UTC axis:
 *
 *   1  IMF Bz (GSM)               observed, propagated to Earth arrival
 *   2  IMF clock angle            derived
 *   3  Newell coupling            derived - "how hard is it being driven"
 *   4  Magnetopause standoff      empirical (Shue), already computed
 *   5  Dst, three traces          model + two observed, never merged
 *   6  Ring-current energy        model-derived from Dst, via DPS
 *
 * Read down the panel and that is cause to effect with the real lags visible:
 * Bz turns south, the coupling function rises within minutes, the standoff
 * drops, Dst falls over hours. Nothing on it is invented, and five of the six
 * rows come from data the site already had.
 *
 * This module draws and nothing else. Every decision about *what the visitor
 * is told* - which rows exist, which samples may be joined by a line, what the
 * value at the selected instant is - lives in `storm-indices.ts`, which has no
 * DOM dependency and is unit-tested directly. That split is the same one
 * `orbit-history.ts` and `orbit-history-browser.ts` already use.
 *
 * Three drawing rules are deliberate and load-bearing:
 *
 * **Gaps stay gaps.** `toSegments` breaks the polyline; nothing is bridged.
 *
 * **The forward-lead region is shaded.** The modelled Dst runs about seventy
 * minutes into the future. An unshaded nowcast beside observations reads as a
 * measurement.
 *
 * **Every row carries its own evidence badge.** A co-displayed observation and
 * model do not acquire a common evidence class by sharing an axis, and the
 * site's layer contract says so in as many words.
 */

/** Everything the top-bar indicator needs, and nothing that needs a DOM. */
export interface StormHeadline {
  phase: StormPhase["label"];
  /** `MAIN · WEAK · Dst −38 nT` — the state and the one number defining it. */
  chipLabel: string;
  dstNt: number | null;
  /** Named because a modelled Dst must never be read as a measurement. */
  dstSource: "Kyoto quicklook Dst" | "USGS Dst3" | "physics-model nowcast" | null;
  /** Why the classifier says what it says, in its own words. */
  reason: string;
}

const MINUS = "−";

/** `−38` rather than `-38`: the site sets minus signs, not hyphens. */
function signedNt(value: number): string {
  return `${value < 0 ? MINUS : ""}${Math.abs(value).toFixed(0)} nT`;
}

/**
 * The one-line state of the storm, or null when there is nothing to say.
 *
 * Null is the important case. Sean's complaint about the old rail panel was
 * that it looked alarming "especially when we are not having one", so a quiet
 * or unclassifiable field produces no indicator at all rather than a calm chip
 * that still occupies the top bar. The NOAA scale strip already reports quiet
 * geomagnetic conditions, so nothing is lost by being absent.
 *
 * An observed index is preferred over the modelled nowcast, and whichever is
 * used is named — the modelled trace runs ahead of real time and is not a
 * measurement.
 */
export function stormHeadline(
  storm: StormIndices | null | undefined,
  drivers: readonly StormDriverSample[] | undefined,
  at: Date,
): StormHeadline | null {
  if (!storm) return null;
  const narrative = stormNarrativeAt(storm, drivers, at);
  const phase = narrative?.phase ?? storm.phase;
  if (phase.label === "quiet" || phase.label === "unknown") return null;

  const responding = narrative?.responding;
  const candidates: Array<[number | null | undefined, StormHeadline["dstSource"]]> = [
    [responding?.kyotoNt, "Kyoto quicklook Dst"],
    [responding?.observedNt, "USGS Dst3"],
    [responding?.modelledNt, "physics-model nowcast"],
  ];
  const chosen = candidates.find(([value]) => typeof value === "number" && Number.isFinite(value));
  const dstNt = chosen ? (chosen[0] as number) : null;
  const dstSource = chosen ? chosen[1] : null;

  const parts = [phase.label.toUpperCase()];
  if (phase.intensity) parts.push(phase.intensity.toUpperCase());
  if (dstNt !== null) parts.push(`Dst ${signedNt(dstNt)}`);
  return { phase: phase.label, chipLabel: parts.join(" · "), dstNt, dstSource, reason: phase.reason };
}

/**
 * The sentence that stops the site contradicting itself.
 *
 * NOAA's G-scale is built from Kp, a three-hour planetary average of
 * mid-latitude range. Dst is a direct measure of the ring current. During
 * onset the two genuinely disagree, and the site was showing G0 two inches
 * above a MAIN · WEAK storm classification with nothing reconciling them — a
 * reader's only available conclusion was that the page was broken.
 *
 * Returns null when there is nothing to reconcile: no storm, no G reading, or
 * a G-scale that has already caught up.
 */
export function kpDstReconciliation(input: {
  kpIndex: number | null;
  gLevel: number | null;
  dstNt: number | null;
  dstSource: string | null;
}): string | null {
  const { kpIndex, gLevel, dstNt, dstSource } = input;
  if (dstNt === null || gLevel === null || gLevel > 0) return null;
  const kp = kpIndex === null || !Number.isFinite(kpIndex) ? "below the storm threshold" : `${kpIndex.toFixed(1)}`;
  return `NOAA's scale reads G0 because the G-scale is built from Kp, which is ${kp}. `
    + `Dst is at ${signedNt(dstNt)}${dstSource ? ` (${dstSource})` : ""}. `
    + "The two disagree because they measure different things: Kp is a three-hour planetary average of "
    + "mid-latitude magnetic range, while Dst measures the ring current directly. Kp cannot resolve "
    + "storm onset; Dst is the physical measure, and it is the one classifying this as a storm.";
}

export interface StormPanelOptions {
  /** UTC instant the rest of the interface is showing. */
  selectedTime: Date;
  /** How much history to draw, hours. */
  historyHours?: number;
  /** Total drawing width in CSS pixels; the SVG scales to its container. */
  width?: number;
  /** Height of one trace row. */
  rowHeight?: number;
}

const SVG = "http://www.w3.org/2000/svg";

const TRACE_CLASS: Record<StripRow["traces"][number]["kind"], string> = {
  driver: "storm-panel__trace--driver",
  boundary: "storm-panel__trace--boundary",
  model: "storm-panel__trace--model",
  observed: "storm-panel__trace--observed",
  kyoto: "storm-panel__trace--kyoto",
};

function element<K extends keyof SVGElementTagNameMap>(
  name: K,
  attributes: Record<string, string | number> = {},
): SVGElementTagNameMap[K] {
  const node = document.createElementNS(SVG, name);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
  return node;
}

function formatValue(row: StripRow, value: number): string {
  if (row.key === "ring") return `${value.toExponential(1)} J`;
  const text = value.toFixed(row.decimals);
  return row.unit ? `${text} ${row.unit}` : text;
}

function extent(row: StripRow): [number, number] | null {
  let low = Number.POSITIVE_INFINITY;
  let high = Number.NEGATIVE_INFINITY;
  for (const trace of row.traces) {
    for (const point of trace.points) {
      if (point.value === null || !Number.isFinite(point.value)) continue;
      low = Math.min(low, point.value);
      high = Math.max(high, point.value);
    }
  }
  if (!Number.isFinite(low) || !Number.isFinite(high)) return null;
  if (low === high) return [low - 1, high + 1];
  const pad = (high - low) * 0.1;
  return [low - pad, high + pad];
}

export interface StormPanelResult {
  /** The mounted root, for the caller to place or remove. */
  root: HTMLElement;
  /** Rows actually drawn. A row with no data is omitted, not faked. */
  drawnRows: string[];
}

/**
 * Build the panel into `container`, replacing whatever was there.
 *
 * Returns `null` when there is no storm block at all, so a caller can hide its
 * whole section rather than show an empty frame.
 */
export function renderStormPanel(
  container: HTMLElement,
  storm: StormIndices | null | undefined,
  drivers: readonly StormDriverSample[] | undefined,
  options: StormPanelOptions,
): StormPanelResult | null {
  container.replaceChildren();
  if (!storm) return null;

  const historyHours = options.historyHours ?? 24;
  const width = options.width ?? 720;
  const rowHeight = options.rowHeight ?? 46;
  const window_ = stripWindow(storm, options.selectedTime, historyHours);
  const narrative = stormNarrativeAt(storm, drivers, options.selectedTime);
  const drawn = drawableRows(stormStripRows(storm, drivers, window_, narrative));

  const root = document.createElement("section");
  root.className = "storm-panel";

  const head = document.createElement("div");
  head.className = "storm-panel__head";
  // No title here: the surface this is mounted in already names it, and the
  // duplicate heading was one of the things making the old rail block read as
  // a wall. What the head carries is the state and its defining number.
  const headline = stormHeadline(storm, drivers, options.selectedTime);
  const title = document.createElement("h3");
  title.className = "storm-panel__title";
  title.textContent = headline?.dstNt === null || headline === null
    ? "Dst unavailable"
    : `Dst ${headline.dstNt < 0 ? MINUS : ""}${Math.abs(headline.dstNt).toFixed(0)} nT`;
  title.title = headline?.dstSource ? `Source: ${headline.dstSource}` : "";
  head.append(title);
  const phase = document.createElement("span");
  phase.className = "storm-panel__phase";
  phase.dataset.phase = storm.phase.label;
  phase.textContent = storm.phase.intensity
    ? `${storm.phase.label} \u00b7 ${storm.phase.intensity}`
    : storm.phase.label;
  phase.title = `${storm.phase.reason}. ${storm.phase.rule}`;
  head.append(phase);
  root.append(head);

  if (!drawn.length) {
    const empty = document.createElement("p");
    empty.className = "storm-panel__empty";
    empty.textContent =
      "No storm indices are available for the selected window. Nothing is drawn, rather "
      + "than a frozen last value.";
    root.append(empty);
    container.append(root);
    return { root, drawnRows: [] };
  }

  const labelWidth = 150;
  const valueWidth = 92;
  const plotLeft = labelWidth;
  const plotWidth = Math.max(120, width - labelWidth - valueWidth);
  const height = drawn.length * rowHeight + 22;
  const svg = element("svg", {
    class: "storm-panel__chart",
    viewBox: `0 0 ${width} ${height}`,
    role: "img",
    "aria-label": "Geomagnetic storm strip chart",
  });
  const xOf = (t: number) =>
    plotLeft + ((t - window_.from) / Math.max(1, window_.to - window_.from)) * plotWidth;

  if (window_.to > window_.now) {
    svg.append(element("rect", {
      class: "storm-panel__lead",
      x: xOf(window_.now),
      y: 0,
      width: Math.max(0, xOf(window_.to) - xOf(window_.now)),
      height: drawn.length * rowHeight,
    }));
  }

  drawn.forEach((row, index) => {
    const top = index * rowHeight + 4;
    const bottom = top + rowHeight - 12;
    const span = extent(row);
    if (!span) return;
    const [low, high] = span;
    const yOf = (value: number) => bottom - ((value - low) / (high - low)) * (bottom - top);

    svg.append(element("line", {
      class: "storm-panel__rule", x1: plotLeft, x2: plotLeft + plotWidth, y1: bottom, y2: bottom,
    }));
    if (row.markZero && low < 0 && high > 0) {
      svg.append(element("line", {
        class: "storm-panel__zero", x1: plotLeft, x2: plotLeft + plotWidth, y1: yOf(0), y2: yOf(0),
      }));
    }
    if (row.shadeNegative && low < 0) {
      // Southward IMF is the switch that governs dayside reconnection, so it
      // gets its own shading rather than a colour change: the reader should be
      // able to see *when* the switch was on.
      const zeroY = Math.min(bottom, Math.max(top, yOf(0)));
      for (const trace of row.traces) {
        for (const segment of toSegments(trace.points, trace.maximumGapMs)) {
          for (let step = 1; step < segment.length; step += 1) {
            const a = segment[step - 1]!;
            const b = segment[step]!;
            if (a.value >= 0 && b.value >= 0) continue;
            svg.append(element("polygon", {
              class: "storm-panel__southward",
              points: `${xOf(a.t)},${zeroY} ${xOf(a.t)},${yOf(Math.min(0, a.value))} `
                + `${xOf(b.t)},${yOf(Math.min(0, b.value))} ${xOf(b.t)},${zeroY}`,
            }));
          }
        }
      }
    }

    for (const trace of row.traces) {
      for (const segment of toSegments(trace.points, trace.maximumGapMs)) {
        if (segment.length < 2) continue;
        svg.append(element("polyline", {
          class: `storm-panel__trace ${TRACE_CLASS[trace.kind]}`,
          points: segment.map((point) => `${xOf(point.t)},${yOf(point.value)}`).join(" "),
        }));
      }
    }

    const label = element("text", { class: "storm-panel__row-label", x: 0, y: top + 10 });
    label.textContent = row.label;
    svg.append(label);
    const badge = element("text", { class: "storm-panel__row-label", x: 0, y: top + 22 });
    badge.textContent = row.badge.toUpperCase();
    svg.append(badge);
    const value = element("text", {
      class: "storm-panel__row-value", x: plotLeft + plotWidth + 8, y: top + 16,
    });
    value.textContent = row.current === null ? "\u2014" : formatValue(row, row.current);
    svg.append(value);
  });

  svg.append(element("line", {
    class: "storm-panel__now",
    x1: xOf(window_.now), x2: xOf(window_.now), y1: 0, y2: drawn.length * rowHeight,
  }));
  const axisLeft = element("text", { class: "storm-panel__axis", x: plotLeft, y: height - 6 });
  axisLeft.textContent = `${new Date(window_.from).toISOString().slice(0, 16).replace("T", " ")}Z`;
  svg.append(axisLeft);
  const axisRight = element("text", {
    class: "storm-panel__axis", x: plotLeft + plotWidth, y: height - 6, "text-anchor": "end",
  });
  axisRight.textContent = `${new Date(window_.to).toISOString().slice(0, 16).replace("T", " ")}Z`;
  svg.append(axisRight);

  // The chart is why the dropdown was opened, so it is the one thing open by
  // default. Everything else — provenance, then the long-form notes — is a
  // level down, the same progressive disclosure the layer and satellite cards
  // use. All of this used to be at depth zero, permanently, in the rail.
  const chartSection = document.createElement("details");
  chartSection.className = "card-section";
  chartSection.dataset.cardSection = "storm-chart";
  chartSection.open = true;
  const chartSummary = document.createElement("summary");
  chartSummary.textContent = "Cause to effect, on one time axis";
  chartSection.append(chartSummary, svg);
  root.append(chartSection);

  const provenance = document.createElement("details");
  provenance.className = "card-section";
  provenance.dataset.cardSection = "storm-provenance";
  const provenanceSummary = document.createElement("summary");
  provenanceSummary.textContent = "Which Dst is which";
  provenance.append(provenanceSummary);

  const legend = document.createElement("div");
  legend.className = "storm-panel__legend";
  const legendEntries: Array<[string, string, string]> = [
    ["storm-panel__trace--model", storm.dst.modelled.label, "model"],
    ["storm-panel__trace--observed", storm.dst.observed.label, "observed"],
    ["storm-panel__trace--kyoto", storm.dst.kyoto.label, "observed"],
  ];
  for (const [traceClass, text, badge] of legendEntries) {
    const item = document.createElement("span");
    item.className = "storm-panel__legend-item";
    const swatch = document.createElement("i");
    swatch.className = `storm-panel__swatch ${traceClass}`;
    item.append(swatch);
    const caption = document.createElement("span");
    caption.textContent = text;
    item.append(caption);
    const tag = document.createElement("span");
    tag.className = "storm-panel__badge";
    tag.textContent = badge;
    item.append(tag);
    legend.append(item);
  }
  provenance.append(legend);
  root.append(provenance);

  const notes = document.createElement("ul");
  notes.className = "storm-panel__notes";
  const ring = ringCurrentNarrative(storm.ringCurrent, narrative?.responding.ringEnergyJoules ?? null);
  const lines: string[] = [storm.dst.separationNote];
  if (storm.dst.modelled.forwardLeadMinutes) {
    lines.push(
      `The modelled trace runs ${storm.dst.modelled.forwardLeadMinutes.toFixed(0)} minutes ahead of `
      + "the selected time (shaded); the observed traces land on top of it as they arrive.",
    );
  }
  const error = narrative?.responding.nowcastErrorNt;
  if (error !== null && error !== undefined) {
    lines.push(
      "At the selected time the nowcast differs from the USGS observation by "
      + `${error.toFixed(1)} nT.`,
    );
  }
  if (ring) {
    lines.push(storm.ringCurrent.relation);
    // One comparison, not four. The same number in megatons, terawatt-hours,
    // hours of US generation and a fraction of the dipole field is padding
    // after the first: the first is the vivid one, and the rest follow it as
    // their own line for anyone who wants the arithmetic.
    if (ring.tangibles.length) {
      lines.push(`Ring-current energy: ${ring.tangibles[0]}.`);
      if (ring.tangibles.length > 1) {
        lines.push(`The same energy, other ways: ${ring.tangibles.slice(1).join("; ")}.`);
      }
    }
    lines.push(ring.uncertainty);
  }
  if (storm.dst.kyoto.citation) lines.push(storm.dst.kyoto.citation);
  lines.push(...storm.limitations);
  for (const text of lines.filter(Boolean)) {
    const item = document.createElement("li");
    item.textContent = text;
    notes.append(item);
  }
  const notesSection = document.createElement("details");
  notesSection.className = "card-section";
  notesSection.dataset.cardSection = "storm-notes";
  const notesSummary = document.createElement("summary");
  notesSummary.textContent = "Notes, limitations and sources";
  notesSection.append(notesSummary, notes);
  root.append(notesSection);

  container.append(root);
  return { root, drawnRows: drawn.map((row) => row.key) };
}
