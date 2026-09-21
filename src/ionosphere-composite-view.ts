/**
 * The layer structure, turned into elements.
 *
 * Split from `ionosphere-composite.ts` the same way `energy-chain-view.ts` is
 * split from `energy-chain.ts`: the physics module decides everything and
 * stays free of the DOM, and this file only writes what it decided. The split
 * is not tidiness - it is what lets a harness draw the real panel with real
 * artifact data, so the picture can be looked at rather than only asserted
 * about. This project has repeatedly shipped drawing code that no test and no
 * screenshot ever reached.
 */

import { ladderGeometry, type CompositeProfile, type LayerProvenance } from "./ionosphere-composite";
import type { SoundingBundle } from "./ionosonde-soundings";

/**
 * Draw the layer ladder from the pure geometry.
 *
 * Deliberately thin: `ladderGeometry` decides everything and is tested, and
 * this only turns numbers into elements. The project has repeatedly shipped
 * drawing code no test could reach, and the split is what stops that here.
 */
export function drawLayerLadder(chart: SVGSVGElement & HTMLElement, composite: CompositeProfile) {
  const svgNs = "http://www.w3.org/2000/svg";
  const geometry = ladderGeometry(composite.layers);
  const nodes: SVGElement[] = [];

  const axis = document.createElementNS(svgNs, "line");
  axis.setAttribute("class", "probe-ladder-axis");
  axis.setAttribute("x1", String(geometry.axisX));
  axis.setAttribute("x2", String(geometry.axisX));
  axis.setAttribute("y1", "8");
  axis.setAttribute("y2", String(geometry.height - 16));
  nodes.push(axis);

  for (const tick of geometry.ticks) {
    const label = document.createElementNS(svgNs, "text");
    label.setAttribute("class", "probe-ladder-tick");
    label.setAttribute("x", "2");
    label.setAttribute("y", String(tick.y + 3));
    label.textContent = `${tick.km}`;
    nodes.push(label);
  }

  for (const bar of geometry.bars) {
    const rect = document.createElementNS(svgNs, "rect");
    // Three treatments, because there are three different claims: a filled bar
    // is a layer with a critical frequency, a dashed outline is a layer that is
    // NOT THERE, and the D region's own class is a layer that is there and has
    // no critical frequency to draw. Collapsing any two of these would tell the
    // reader something false.
    const treatment = bar.absent ? "absent" : bar.layer === "D" ? "nonreflecting" : bar.evidence;
    rect.setAttribute("class", `probe-ladder-bar ${treatment}`);
    rect.setAttribute("x", String(geometry.axisX + 2));
    rect.setAttribute("y", String(bar.y - 5));
    // An absent layer still draws a short dashed outline: a missing bar reads
    // as "we do not know", and an empty outline reads as "we looked, and the
    // layer is not there", which is the true statement.
    rect.setAttribute("width", String(bar.absent ? 18 : Math.max(2, bar.width)));
    rect.setAttribute("height", "10");
    // Opacity IS the anchor weight. This is the sparse-network fact drawn
    // rather than only written: over an ocean the E and F1 bars fade out.
    rect.setAttribute("opacity", bar.absent ? "1" : String(0.28 + 0.62 * bar.anchorWeight));
    nodes.push(rect);

    const name = document.createElementNS(svgNs, "text");
    name.setAttribute("class", "probe-ladder-name");
    name.setAttribute("x", String(geometry.axisX - 4));
    name.setAttribute("y", String(bar.y + 3));
    name.setAttribute("text-anchor", "end");
    name.textContent = bar.label;
    nodes.push(name);

    const value = document.createElementNS(svgNs, "text");
    value.setAttribute("class", "probe-ladder-value");
    value.setAttribute("x", String(geometry.width - 2));
    value.setAttribute("y", String(bar.y + 3));
    value.setAttribute("text-anchor", "end");
    value.textContent = bar.valueText;
    nodes.push(value);
  }

  chart.replaceChildren(...nodes);
}

/**
 * One layer's row: what it is, what it reads, and where that came from.
 *
 * The provenance sentence is not optional and not behind a disclosure. A
 * reader has to be able to see that F2 is NOAA's model, that E is a physical
 * shape pinned to real soundings, and that D is an empirical fit driven by a
 * measured flux — without opening anything.
 */
export function layerRow(layer: LayerProvenance): HTMLElement {
  const item = document.createElement("li");
  if (layer.absentReason) item.classList.add("absent");

  const head = document.createElement("div");
  head.className = "probe-layer-head";
  const name = document.createElement("span");
  name.textContent = layer.peakHeightKm !== null
    ? `${layer.layer} · ${Math.round(layer.peakHeightKm)} km`
    : layer.layer;
  const value = document.createElement("em");
  value.textContent = layer.absentReason !== null
    ? "not present now"
    : layer.criticalFrequencyMhz !== null
      ? `${layer.criticalFrequencyMhz.toFixed(2)} MHz`
      : layer.layer === "D"
        ? "absorbs, does not reflect"
        : "not available";
  head.append(name, value);

  const source = document.createElement("small");
  // The absence sentence REPLACES the provenance sentence, because when a
  // layer is not there the reader's question is "why not", not "from where".
  source.textContent = layer.absentReason ?? layer.plainSource;
  item.append(head, source);
  return item;
}

/**
 * What the observing network actually looks like right now.
 *
 * Published rather than hidden because it is one of the most useful things
 * this feature teaches: we only know the ionosphere where we measure it, and
 * the network is far thinner than a smooth global map implies. On
 * 2026-08-19 the upstream listed 101 stations of which 27 had sounded in the
 * last three hours, and only 5 of those had scaled an foE.
 */
export function networkNote(bundle: SoundingBundle): string {
  return `The network right now: ${bundle.stations.length} of ${bundle.upstreamStationCount} listed stations `
    + `have sounded in the last ${Math.round(bundle.freshLimitMinutes / 60)} hours; `
    + `${bundle.staleStationCount} have not and are not used. Of the ones that did, `
    + `${bundle.withFoE} scaled an E layer and ${bundle.withFoF1} an F1 layer. `
    + `${bundle.attribution}`;
}

