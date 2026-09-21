/**
 * The orbit-history browser: a population view plus a per-object detail view.
 *
 * Mounted the same way as `ground-track-map.ts` — one exported function that
 * takes a host element and options — so wiring it into `main.ts` is a button, a
 * dialog and one call. `docs/orbit-browser-wiring.md` has the exact patch.
 *
 * What it draws is Sean's own feature list: how often a satellite needs
 * correction, who is spending the most Delta-v, what is deorbiting, what makes
 * the same correction repeatedly, and what is behaving unusually for its class.
 * Each is a view over `objects` in the events bundle, and each carries the
 * number of days of archive its question actually needs, so a view that cannot
 * yet be answered says which day it starts working instead of rendering an
 * empty table.
 *
 * Three drawing rules, all of which come from the honesty contract rather than
 * from taste:
 *
 * 1. **A line is only drawn where the spacing justifies it.** `toSegments`
 *    breaks the series and the gap is shaded and labelled. Nothing is
 *    interpolated.
 * 2. **Points are always drawn, even where a line is not.** An element set is
 *    an observation; a run of one is still data.
 * 3. **The label a visitor reads comes from the pipeline**, via the event's
 *    detector-specific permission (with the bundle policy as compatibility
 *    fallback). This module never decides that something has been established.
 */

import "./orbit-history.css";
import { DRIFT_COLOUR, renderDriftCard, type OrbitDriftBundle } from "./orbit-drift";
import { renderRisingNow } from "./orbit-rising";
import {
  CONFIDENCE_COPY,
  DEFAULT_FILTER,
  VIEW_REQUIREMENTS,
  archiveSpanDays,
  scorableBurns,
  detrendSemiMajorAxis,
  eventLabelPermitted,
  eventNoun,
  formatDeltaV,
  formatMetres,
  ARCHIVE_OFFLINE,
  ARCHIVE_OFFLINE_ACTION,
  ARCHIVE_OFFLINE_BODY,
  ARCHIVE_OFFLINE_TITLE,
  selectPopulation,
  shardFor,
  toSegments,
  type NoDataInterval,
  type ObjectSummary,
  type OrbitEventMarker,
  type OrbitEventRecord,
  type OrbitHeadlineEvent,
  type OrbitEventsBundle,
  type OrbitHistoryObject,
  type OrbitRepeatCluster,
  type OrbitSample,
  type OrbitShardResult,
  type PopulationFilter,
  type PopulationView,
  decayRate,
  repeatCount,
} from "./orbit-history";

const SVG = "http://www.w3.org/2000/svg";
import { plotNotice as displayNotice } from "./plot-view";

const PLOT_WIDTH = 720;
const PLOT_HEIGHT = 96;
const PLOT_MARGIN = { top: 6, right: 8, bottom: 14, left: 46 } as const;

/**
 * A row of the key to the dashed event rules.
 *
 * Sixteen signatures share four colours, so a colour on a plot names a FAMILY,
 * never a signature. Unexplained that is simply unreadable: a reader sees a
 * violet rule and has no way to learn it means the orbit PLANE moved. Each row
 * names the family, spells out every signature inside it, and is drawn with the
 * same dashed mark in the same colour the plot uses.
 *
 * `lines` is a list because the largest family does not fit across the
 * 720-unit plot at a legible size, and wrapping it deliberately beats letting
 * SVG text run off the right edge, which it does silently.
 */
interface SignatureLegendRow {
  colour: string;
  family: string;
  lines: readonly string[];
}

const SIGNATURE_COLOUR: Record<string, string> = {
  "long-arc-drift": DRIFT_COLOUR,
  "along-track-raise": "var(--oh-manoeuvre)",
  "along-track-lower": "var(--oh-manoeuvre)",
  "drag-make-up": "var(--oh-manoeuvre)",
  "deorbit-lowering": "var(--oh-manoeuvre)",
  "orbit-raising": "var(--oh-manoeuvre)",
  "orbit-lowering": "var(--oh-manoeuvre)",
  "geo-east-west-keeping": "var(--oh-manoeuvre)",
  "geo-graveyard-raise": "var(--oh-manoeuvre)",
  "inclination-change": "var(--oh-plane)",
  "geo-north-south-keeping": "var(--oh-plane)",
  "node-change": "var(--oh-plane)",
  // NEVER the manoeuvre amber. This signature's own label is "above its own
  // baseline", and `eventLabelPermitted` refuses it the word "manoeuvre"
  // outright, so drawing it in the manoeuvre colour made the picture claim what
  // the sentence beside it withheld -- and the picture is what a reader takes
  // in first. It gets its own shade instead, sitting between the two tokens it
  // belongs between: the energy of a burn, the standing of an unattributed
  // change, drawn as neither. Written as a token with a literal fallback so
  // whoever owns `orbit-history.css` can adopt it into the palette without
  // this file changing, and so a missing token still paints a real colour
  // instead of defaulting to black on a dark panel.
  "thrust-excess": "var(--oh-thrust-excess, #a08356)",
  "drag-decay": "var(--oh-drag)",
  "re-entry-decay": "var(--oh-drag)",
  "drag-and-thrust-not-separable": "var(--oh-unattributed)",
  "unclassified-change": "var(--oh-unattributed)",
};

/**
 * Every signature in `SIGNATURE_COLOUR`, grouped by the colour it is drawn in.
 * The wording is the reader's, not the detector's: `drag-decay` is published as
 * "orbital decay" and `drag-and-thrust-not-separable` as "unattributed change",
 * which is what `eventNoun` puts on the cards, so the key uses the same words.
 */
const SIGNATURE_LEGEND: readonly SignatureLegendRow[] = [
  {
    colour: SIGNATURE_COLOUR["long-arc-drift"]!,
    family: "Long-arc drift · object card",
    lines: ["sustained slopes · propulsion wording requires this lane’s own control gate"],
  },
  {
    colour: "var(--oh-manoeuvre)",
    family: "In-plane change",
    lines: [
      "along-track raise · along-track lower · drag make-up · orbit raising",
      "orbit lowering · deorbit lowering · GEO east–west keeping · GEO graveyard raise",
    ],
  },
  {
    colour: "var(--oh-plane)",
    family: "Plane change",
    lines: ["inclination change · node change · GEO north–south keeping"],
  },
  {
    colour: "var(--oh-drag)",
    family: "Drag, not thrust",
    lines: ["orbital decay · re-entry decay"],
  },
  {
    colour: "var(--oh-thrust-excess, #a08356)",
    family: "Above its own baseline — no manoeuvre claimed",
    lines: ["thrust excess"],
  },
  {
    colour: "var(--oh-unattributed)",
    family: "Cause not separable",
    lines: [
      "unattributed change · unclassified change · any signature not listed above",
    ],
  },
];

export interface OrbitHistoryBrowserOptions {
  /** The whole events bundle, already fetched by the caller. */
  bundle: OrbitEventsBundle;
  /** Independent nightly artifact, cached by content path by the caller. */
  loadDrift?: () => Promise<OrbitDriftBundle>;
  /** Names from the catalogue already loaded by the application. */
  catalogNames?: ReadonlyMap<number, string>;
  /**
   * Fetch one history shard. Injected rather than done here so the caller keeps
   * ownership of the manifest, the content-addressed paths and any caching it
   * already has. Returning null is a legitimate answer and renders as "history
   * for this object has not been published yet".
   *
   * THREE-VALUED, NOT TWO. `ARCHIVE_OFFLINE` says the machine that holds the
   * shards did not answer, which since 2026-08-27 is a real and separate thing
   * that can happen: they live on bigmem-PC at Sean's house, not on the VPS
   * that served this page. Rendered as its own panel, never as `null`.
   */
  loadShard: (shard: number) => Promise<OrbitShardResult>;
  /** Small selected-object derivative; no automatic large-shard fallback. */
  loadObject?: (norad: number) => Promise<OrbitShardResult>;
  /**
   * How many shards the release was published in, from
   * `manifest.orbitHistory.shardCount`. Passed rather than assumed so this
   * module and `pipeline/orbit_release.py` cannot disagree about which file
   * holds an object. Omitted falls back to 256, today's value.
   */
  shardCount?: number;
  /** NORAD id to open on mount, if the caller already has a selection. */
  initialNorad?: number | null;
  /** Called when the visitor picks an object, so the rest of the page can follow. */
  onSelect?: (norad: number) => void;
}

export interface OrbitHistoryBrowserHandle {
  select(norad: number): void;
  destroy(): void;
}

export function mountOrbitHistoryBrowser(
  host: HTMLElement,
  options: OrbitHistoryBrowserOptions,
): OrbitHistoryBrowserHandle {
  const { bundle } = options;
  host.replaceChildren();
  host.classList.add("orbit-history");

  const filter: PopulationFilter = { ...DEFAULT_FILTER };
  const shardCache = new Map<number, OrbitShardResult>();
  let selected: number | null = options.initialNorad ?? null;
  let disposed = false;

  const status = element("section", "orbit-history__status");
  const controls = element("div", "orbit-history__controls");
  const question = element("p", "orbit-history__question");
  const tableWrap = element("div", "orbit-history__table-wrap");
  const detail = element("section", "orbit-history__detail");
  host.append(status, controls, question, tableWrap, detail);

  renderStatus(status, bundle);
  const risingHost = element("section", "orbit-history__rising-slot");
  risingHost.setAttribute("aria-live", "polite");
  status.after(risingHost);
  risingHost.textContent = options.loadDrift ? "Loading Rising now…"
    : "Rising now: no drift artifact has been published in this release.";
  if (options.loadDrift) void options.loadDrift().then(drift => {
    if (disposed) return;
    const names = options.catalogNames ?? new Map(bundle.objects.map(o => [o.norad, o.name]));
    risingHost.replaceChildren(renderRisingNow(drift, names, norad => {
      void openObject(norad).then(() => {
        if (!disposed && selected === norad) {
          detail.tabIndex = -1;
          detail.focus();
        }
      });
    }));
  }).catch(() => {
    if (!disposed) risingHost.textContent = "Rising now could not be loaded. The raising population and its label gate are unavailable.";
  });
  renderControls(controls, filter, () => {
    renderQuestion(question, filter);
    renderTable();
  });
  renderQuestion(question, filter);
  renderTable();
  if (selected !== null) void openObject(selected);
  else renderDetailPlaceholder(detail);

  function renderTable(): void {
    const result = selectPopulation(
      bundle.objects,
      filter,
      archiveSpanDays(bundle),
    );
    tableWrap.replaceChildren();
    if (result.unavailable) {
      tableWrap.append(
        emptyState(
          "Not enough archive yet for this question",
          `${result.unavailable.question} ${result.unavailable.needs}`,
          `The archive has been watching for ${formatDays(result.unavailable.haveDays)}.`,
        ),
      );
      return;
    }
    if (result.rows.length === 0) {
      tableWrap.append(
        emptyState(
          "Nothing matches",
          "No object in the archive meets this filter. That is a real answer, not a failure: over a short window most objects do nothing worth reporting.",
        ),
      );
      return;
    }
    tableWrap.append(buildTable(result.rows));
  }

  function buildTable(rows: readonly ObjectSummary[]): HTMLTableElement {
    const table = document.createElement("table");
    const head = table.createTHead().insertRow();
    for (const label of [
      "Object",
      "Regime",
      "Perigee km",
      "Incl °",
      "Δv m/s",
      "Events",
      // The two columns Sean's own list asks the population view to sort on.
      // Both come from the object's own history, so both are blank rather than
      // zero when the archive does not yet hold enough of it — a blank reads as
      // "not known", a zero reads as "never", and only one of those is true.
      "Per year",
      "Repeats",
      "Δa m/day",
      "Watched",
      "",
    ]) {
      const cell = document.createElement("th");
      cell.scope = "col";
      cell.textContent = label;
      head.append(cell);
    }
    const body = table.createTBody();
    for (const row of rows.slice(0, 400)) {
      const line = body.insertRow();
      line.tabIndex = 0;
      line.setAttribute("role", "button");
      if (row.norad === selected) line.setAttribute("aria-selected", "true");
      addCell(line, row.name);
      addCell(line, row.regime);
      addCell(line, row.perigeeAltitudeKm.toFixed(0));
      addCell(line, row.inclinationDeg.toFixed(2));
      addCell(line, formatDeltaV(row.deltaVMetresPerSecond));
      addCell(line, String(row.events));
      addCell(line, row.cadence ? row.cadence.correctionsPerYear?.toFixed(1) ?? "—" : "—");
      addCell(line, repeatCount(row) > 1 ? `×${repeatCount(row)}` : "—");
      addCell(line, decayRate(row).toFixed(1));
      addCell(line, formatDays(row.observedDays));
      const flags = document.createElement("td");
      if ((row.unusualForItself?.length ?? 0) > 0) {
        flags.append(flag("unusual for itself", "unusual"));
      }
      if (row.outOfFamilyForClass ?? row.outOfFamily) flags.append(flag("out of family", "unusual"));
      if (row.decay?.decaying ?? row.decaying) flags.append(flag("decaying", "decaying"));
      if ((row.cadence?.regularity ?? 1) < 0.25) flags.append(flag("regular cadence", "regular"));
      line.append(flags);
      const open = () => void openObject(row.norad);
      line.addEventListener("click", open);
      line.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          open();
        }
      });
    }
    return table;
  }

  async function openObject(norad: number, fullResolution = false): Promise<void> {
    selected = norad;
    detail.id = `orbit-history-object-${norad}`;
    options.onSelect?.(norad);
    for (const row of tableWrap.querySelectorAll("tbody tr")) row.removeAttribute("aria-selected");
    detail.replaceChildren(loading());

    const shardIndex = shardFor(norad, resolveShardCount(options.shardCount));
    const useView = options.loadObject && !fullResolution;
    const cacheKey = useView ? norad + 1000000 : shardIndex;
    let shard = shardCache.get(cacheKey) ?? null;
    if (!shardCache.has(cacheKey)) {
      try {
        shard = useView ? await options.loadObject!(norad) : await options.loadShard(shardIndex);
      } catch {
        shard = null;
      }
      // Keep only the selected plot in this dialog's memory.
      shardCache.clear();
      shardCache.set(cacheKey, shard);
    }
    if (disposed || selected !== norad) return;

    // `shard` is three-valued now, and ARCHIVE_OFFLINE carries no objects. It
    // is narrowed away once, here, so nothing below has to keep remembering.
    const loaded = shard === ARCHIVE_OFFLINE ? null : shard;
    const record = loaded?.objects.find((entry) => entry.norad === norad) ?? null;
    // The object's own events come from the shard, which is already fetched.
    // The bundle's list is a bounded cross-catalogue headline set — a year of
    // archive produces tens of thousands of events and shipping them all on the
    // front page would make this feature slower than the globe it hangs off —
    // so reading only the bundle would silently show a visitor a subset of an
    // object's history while looking complete. The bundle is the fallback for
    // an object whose shard has not been published yet, and for a bundle built
    // before the shards carried full records.
    // Full records come from the shard. The bundle's own list is the fallback
    // for an object whose shard has not been published yet — and it is a
    // DIFFERENT shape, not a thinner copy of the same one: `_slim()` in
    // `pipeline/orbit_release.py` strips `card`, `deltaV`, `drag`,
    // `spaceWeather`, `expectation` and `tests` before publishing it. So the
    // two are rendered by two functions rather than one, because handing a
    // headline event to `renderEvidenceCard` reads `event.card.headline` off an
    // object with no `card` and throws inside the dialog.
    const fromShard = (record?.events ?? []) as unknown as OrbitEventRecord[];
    const full = fromShard.filter((event) => event.tests !== undefined && event.card !== undefined);
    const headline = full.length > 0
      ? []
      : bundle.events.filter((event) => event.norad === norad);
    const eventCount = record?.display ? record.events.length : full.length + headline.length;
    detail.replaceChildren();
    detail.append(renderObjectHeader(norad, eventCount));
    if (options.loadDrift) {
      const driftHost = element("div", "orbit-history__drift-slot");
      driftHost.textContent = "Loading long-arc drift…";
      detail.append(driftHost);
      void options.loadDrift().then(drift => {
        if (disposed || selected !== norad || !detail.contains(driftHost)) return;
        const object = drift.objects.find(row => row.norad === norad);
        if (object) driftHost.replaceChildren(renderDriftCard(drift, object));
        else driftHost.textContent = "No long-arc drift record was published for this object.";
      }).catch(() => {
        if (!disposed && detail.contains(driftHost)) driftHost.textContent = "Long-arc drift could not be loaded; no inference is available.";
      });
    }
    if (options.loadObject) {
      const resolution = element("p", "orbit-history__provenance");
      resolution.textContent = record?.display ? displayNotice(record) : fullResolution
        ? `Full resolution: ${record?.samples.length.toLocaleString("en-US") ?? 0} points.`
        : "The small plot view is unavailable for this object. No large archive was downloaded automatically.";
      detail.append(resolution);
      const toggle = document.createElement("button");
      toggle.textContent = fullResolution ? "Use small plot view" : "Load full resolution and evidence (large download; may slow this device)";
      toggle.addEventListener("click", () => { void openObject(norad, !fullResolution); });
      detail.append(toggle);
    }
    // From the BUNDLE, not the shard, and therefore drawn before the shard is
    // checked below: the trend is computed in the streaming archive pass, which
    // owns the intervals, and travels on the object's summary row. An object
    // whose history file 404s -- which every one of them did on 2026-08-27 --
    // still gets a truthful answer to "where is this going", because that
    // answer never depended on the file that was missing.
    const summary = bundle.objects.find((row) => row.norad === norad);
    const trend = renderDecayTrend(summary?.decay);
    if (trend) detail.append(trend);
    if (useView && !record) return; // The derivative's own absence is already explained above.
    if (!record || record.samples.length === 0) {
      // TWO DIFFERENT ABSENCES, SAID DIFFERENTLY. They used to share one
      // sentence, and that is how this feature managed to contradict the card
      // in front of the owner: on 2026-08-27 every orbit-history shard was
      // 404ing on the live site while the events bundle beside them was fine,
      // so the card correctly read "could not be read" and this dialog opened
      // on a full header - name, NORAD, regime, perigee, apogee, inclination,
      // all of which come from the BUNDLE and none of which come from the
      // object's history - under a sentence that read like an ordinary young
      // archive. Sean: "It is odd that it says history unavailable yet I can
      // pull up the history." He could not; he was looking at the summary row.
      //
      // A shard that could not be READ is a fault in what was published, not a
      // statement about this spacecraft, and it is now said as one.
      if (shard === ARCHIVE_OFFLINE) {
        // THE FIFTH ABSENCE, AND THE ONLY ONE WITH SOMETHING A READER CAN DO.
        // Sean's ruling when the archive moved to bigmem: "If bigmem-pc is
        // down, we just say 'that server is offline right now, sorry, the data
        // is unavailable - email Sean and Derek for details or specific
        // requests.'" -- routed through the feedback box rather than a printed
        // address, which is the whole reason that box exists.
        const offline = emptyState(ARCHIVE_OFFLINE_TITLE, ARCHIVE_OFFLINE_BODY);
        offline.append(feedbackButton(ARCHIVE_OFFLINE_ACTION));
        detail.append(offline);
        return;
      }
      detail.append(shard === null
        ? emptyState(
          "This object's history file could not be loaded",
          "The release names an archive file for this spacecraft and the browser could not fetch it, so nothing is drawn. That is a fault in what was published, not a finding about this orbit — the summary above comes from the events bundle, which loaded.",
        )
        : emptyState(
          "No history published for this object yet",
          "The archive has not yet caught two element sets for it, or the shard that holds it has not been published in this release.",
        ));
      return;
    }
    // An event marker inside a history shard carries no object type of its own,
    // so the summary row's type is handed to the same gate the cards use.
    // Without it the plot would hedge on a different rule than the prose beside
    // it -- which is exactly how the tooltip came to say "manoeuvre" alone.
    detail.append(renderPlots(record, bundle.coverage.noDataIntervals, (event) =>
      eventLabelPermitted(
        {
          manoeuvreLabelPermitted: event.manoeuvreLabelPermitted,
          objectType: summary?.objectType,
          signature: event.signature,
        },
        bundle.labelPolicy.manoeuvreLabelPermitted,
      )));
    if (record.repeatClusters?.length) {
      detail.append(renderRepeatClusters(record.repeatClusters));
    }
    for (const event of full) detail.append(renderEvidenceCard(event, bundle));
    for (const event of headline) detail.append(renderHeadlineCard(event, bundle));
    if (eventCount === 0) {
      detail.append(
        emptyState(
          "No step event detected for this object",
          "The step channel found no reportable event in this archive. Smooth raising, station-keeping and changes below its floor can remain invisible; the long-arc drift card answers a separate question.",
        ),
      );
    }
  }

  function renderObjectHeader(norad: number, eventCount: number): HTMLElement {
    const summary = bundle.objects.find((row) => row.norad === norad);
    const wrap = element("div", "orbit-history__card");
    const title = document.createElement("h3");
    title.textContent = summary ? `${summary.name} · NORAD ${norad}` : `NORAD ${norad}`;
    wrap.append(title);
    if (summary) {
      const list = document.createElement("dl");
      appendPair(list, "Regime", summary.regime);
      appendPair(list, "Perigee", `${summary.perigeeAltitudeKm.toFixed(0)} km`);
      appendPair(list, "Apogee", `${summary.apogeeAltitudeKm.toFixed(0)} km`);
      appendPair(list, "Inclination", `${summary.inclinationDeg.toFixed(3)}°`);
      appendPair(list, "Sun-synchronous", summary.sunSynchronous ? "yes" : "no");
      appendPair(list, "Δv observed", formatDeltaV(summary.deltaVMetresPerSecond));
      appendPair(list, "Changes flagged", String(eventCount));
      appendPair(list, "Watched for", formatDays(summary.observedDays));
      if (summary.deltaVPerYearMetresPerSecond != null) {
        appendPair(list, "Δv per year", formatDeltaV(summary.deltaVPerYearMetresPerSecond));
      }
      wrap.append(list);
      wrap.append(...historyPanels(summary));
    }
    return wrap;
  }

  /**
   * The three things Sean asked the browser to be able to say about one
   * satellite, each rendered only when the archive holds enough of that
   * satellite's own history to support it.
   *
   * Each panel shows the numbers it was computed from rather than a verdict.
   * "Corrects every 14 days" on its own is a claim; "corrects every 14 days,
   * four of them, spread by under a day" is a measurement a reader can check.
   */
  function historyPanels(summary: ObjectSummary): HTMLElement[] {
    const panels: HTMLElement[] = [];
    const cadence = summary.cadence;
    if (cadence) {
      const panel = element("div", "orbit-history__panel");
      const heading = document.createElement("h4");
      heading.textContent = "How often it corrects";
      const body = document.createElement("p");
      const regularity =
        cadence.regularity == null
          ? "spacing not yet measurable"
          : cadence.regularity < 0.25
            ? "regularly spaced"
            : cadence.regularity < 0.6
              ? "roughly spaced"
              : "irregularly spaced";
      body.textContent =
        `${cadence.corrections} corrections, about every ` +
        `${cadence.medianDaysBetween.toFixed(1)} days and ${regularity} ` +
        `(spread ±${cadence.spacingScaleDays.toFixed(1)} days), over ` +
        `${formatDays(cadence.observedDays)} of archive.`;
      const caveat = document.createElement("p");
      caveat.className = "orbit-history__panel-note";
      caveat.textContent = cadence.note;
      panel.append(heading, body, caveat);
      panels.push(panel);
    }
    for (const cluster of summary.repeatClusters ?? []) {
      const panel = element("div", "orbit-history__panel");
      const heading = document.createElement("h4");
      heading.textContent = "The same correction, again";
      const body = document.createElement("p");
      const spacing =
        cluster.medianDaysBetween == null
          ? ""
          : ` about every ${cluster.medianDaysBetween.toFixed(1)} days,`;
      body.textContent =
        `${cluster.count} changes of the same kind at ` +
        `${formatDeltaV(cluster.medianDeltaVMetresPerSecond)} each` +
        `${spacing} between ${cluster.firstAt.slice(0, 10)} and ` +
        `${cluster.lastAt.slice(0, 10)}. Total ` +
        `${formatDeltaV(cluster.totalDeltaVMetresPerSecond)}.`;
      panel.append(heading, body);
      panels.push(panel);
    }
    for (const odd of summary.unusualForItself ?? []) {
      const panel = element("div", "orbit-history__panel orbit-history__panel--unusual");
      const heading = document.createElement("h4");
      heading.textContent = "Unusual for this object";
      const body = document.createElement("p");
      body.textContent =
        `On ${odd.at.slice(0, 10)}, ${formatDeltaV(odd.deltaVMetresPerSecond)} — ` +
        `${odd.why}. Its usual correction is ` +
        `${formatDeltaV(odd.usualDeltaVMetresPerSecond)}, seen ${odd.usualCount} times.`;
      panel.append(heading, body);
      panels.push(panel);
    }
    // The decay trend used to be a fourth panel here, one sentence long and
    // drawn only when `decaying` was already true -- so of the 7,943 objects
    // the live bundle carries a measured trend for, 2,905 of them (36.6 %) had
    // one computed, published and never shown, because their median rate was
    // upward or their perigee was above the altitude where the module is
    // willing to call it decay. Both of those are answers to "where is this
    // orbit going", and both were rendered as silence. It is now a block of
    // its own, `renderDecayTrend`, drawn for every object that has a rate at
    // all.
    return panels;
  }

  function renderDetailPlaceholder(target: HTMLElement): void {
    target.replaceChildren(
      emptyState(
        "Pick an object",
        "Choose a row above to see how its orbit moved, which changes cleared the noise floor, and what each one would have cost.",
      ),
    );
  }

  function destroy(): void {
    disposed = true;
    host.replaceChildren();
    host.classList.remove("orbit-history");
  }

  return { select: (norad) => void openObject(norad), destroy };
}

/* ------------------------------------------------------------------------ */
/* Status: the numbers that govern what may be said                          */
/* ------------------------------------------------------------------------ */

function renderStatus(target: HTMLElement, bundle: OrbitEventsBundle): void {
  const { controls, labelPolicy, maturity, groundTruth } = bundle;
  target.replaceChildren();

  const heading = document.createElement("h3");
  const basisPolicy = labelPolicy.byBasis;
  const stratumPolicies = Object.values(basisPolicy?.byStratum ?? {}).flatMap(Object.values);
  const mixedCalibration = (basisPolicy && basisPolicy.cohort !== basisPolicy.selfHistory)
    || (stratumPolicies.some((policy) => policy.manoeuvreLabelPermitted)
        && !labelPolicy.manoeuvreLabelPermitted);
  heading.textContent = mixedCalibration
    ? stratumPolicies.length ? "Detector calibration depends on era and perigee band" : "Detector calibration is lane-specific"
    : labelPolicy.manoeuvreLabelPermitted
      ? "Detector calibrated"
      : "Detector not yet calibrated — nothing here is called a manoeuvre";
  target.append(heading);

  const explanation = document.createElement("p");
  explanation.textContent =
    labelPolicy.reason ??
    "The false-alarm rate has been measured against objects that cannot manoeuvre and is inside the design target.";
  target.append(explanation);

  const numbers = element("div", "orbit-history__numbers");
  appendNumber(
    numbers,
    "Cohort false alarms on objects that cannot manoeuvre",
    `${controls.passiveControl.flags} / ${controls.passiveControl.intervals}`,
    controls.passiveControl.interval95
      ? `95% interval ${(controls.passiveControl.interval95[0] * 100).toFixed(2)}–${(controls.passiveControl.interval95[1] * 100).toFixed(2)}%`
      : undefined,
  );
  if (controls.selfHistory) {
    appendNumber(
      numbers,
      "Self-history false alarms on objects that cannot manoeuvre",
      `${controls.selfHistory.passive.flags} / ${controls.selfHistory.passive.intervals}`,
      controls.selfHistory.passive.jeffreys95[0] !== null
        && controls.selfHistory.passive.jeffreys95[1] !== null
        ? `95% interval ${(controls.selfHistory.passive.jeffreys95[0] * 100).toFixed(3)}–${(controls.selfHistory.passive.jeffreys95[1] * 100).toFixed(3)}%`
        : undefined,
    );
  }
  appendNumber(
    numbers,
    "Cohort flags on payloads",
    `${controls.payloadPopulation.flags} / ${controls.payloadPopulation.intervals}`,
    "Not a detection rate: most payload intervals contain no manoeuvre either.",
  );
  if (controls.selfHistory) {
    appendNumber(
      numbers,
      "Self-history flags on payloads",
      `${controls.selfHistory.payload.flags} / ${controls.selfHistory.payload.intervals}`,
      "Not a detection rate: most payload intervals contain no manoeuvre either.",
    );
  }
  appendNumber(
    numbers,
    "Is the cohort payload excess significant?",
    controls.excessSignificant ? "yes" : "not yet",
    controls.excessSignificance.z !== null
      ? `${Math.abs(controls.excessSignificance.z).toFixed(1)} standard errors`
      : undefined,
  );
  if (controls.selfHistory) {
    const selfSeparation = controls.selfHistory.separation;
    const selfSignificant = selfSeparation.z !== null
      && selfSeparation.z > 0
      && selfSeparation.approximatePValue !== null
      && selfSeparation.approximatePValue < 0.01;
    appendNumber(
      numbers,
      "Is the self-history payload excess significant?",
      selfSignificant ? "yes" : "not yet",
      selfSeparation.z !== null
        ? `${Math.abs(selfSeparation.z).toFixed(1)} standard errors`
        : undefined,
    );
  }
  const scorable = scorableBurns(bundle);
  appendNumber(
    numbers,
    "Detected against published burns",
    scorable > 0 ? `${groundTruth.detected} / ${scorable}` : "none in window",
    `${groundTruth.pending} published events pending — the archive does not cover them yet.`,
  );
  appendNumber(
    numbers,
    "Longest object watched for",
    formatDays(archiveSpanDays(bundle)),
    maturity.captureLedgerDays !== undefined
      ? `Live capture has been running ${formatDays(maturity.captureLedgerDays)}; the rest is back-filled archive.`
      : undefined,
  );
  target.append(numbers);

  const wording = element("p", "orbit-history__wording");
  wording.textContent = labelPolicy.wording;
  target.append(wording);
}

/* ------------------------------------------------------------------------ */
/* Controls                                                                  */
/* ------------------------------------------------------------------------ */

const VIEW_LABELS: [PopulationView, string][] = [
  ["delta-v", "Biggest spenders"],
  ["decaying", "Deorbiting"],
  ["out-of-family", "Unusual for its class"],
  ["most-corrections", "Corrected most often"],
  ["repeated", "Same correction repeatedly"],
  ["all", "Everything"],
];

function renderControls(
  target: HTMLElement,
  filter: PopulationFilter,
  onChange: () => void,
): void {
  target.replaceChildren();
  for (const [view, label] of VIEW_LABELS) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.setAttribute("aria-pressed", String(filter.view === view));
    button.addEventListener("click", () => {
      filter.view = view;
      for (const other of target.querySelectorAll("button")) {
        other.setAttribute("aria-pressed", "false");
      }
      button.setAttribute("aria-pressed", "true");
      onChange();
    });
    target.append(button);
  }
  const search = document.createElement("input");
  search.type = "search";
  search.placeholder = "Name or NORAD id";
  search.setAttribute("aria-label", "Filter objects by name or catalog number");
  search.addEventListener("input", () => {
    filter.search = search.value;
    onChange();
  });
  target.append(search);
}

function renderQuestion(target: HTMLElement, filter: PopulationFilter): void {
  target.textContent = VIEW_REQUIREMENTS[filter.view].question;
}

/* ------------------------------------------------------------------------ */
/* Plots                                                                     */
/* ------------------------------------------------------------------------ */


function renderPlots(
  record: OrbitHistoryObject,
  gaps: readonly NoDataInterval[],
  labelPermitted: (event: OrbitEventMarker) => boolean,
): HTMLElement {
  const wrap = element("div", "orbit-history__plots");
  const samples = record.samples;
  if (record.display) {
    const notice = element("p", "orbit-history__provenance");
    notice.textContent = displayNotice(record);
    wrap.append(notice);
  }
  const domain = timeDomain(samples);

  wrap.append(
    plotPanel("Perigee and apogee", "km", samples, domain, record, gaps, labelPermitted, [
      { colour: "var(--oh-drag)", value: (sample) => sample.perigeeKm },
      { colour: "var(--oh-manoeuvre)", value: (sample) => sample.apogeeKm },
    ]),
  );

  // The panel where steps live. Metres, because the measured element-to-element
  // noise floor is metres.
  const residuals = new Map(
    (record.display ? samples.map(s => ({ t: s.t, residualMetres: s.residualMetres! }))
      : detrendSemiMajorAxis(samples)).map((entry) => [entry.t, entry.residualMetres]),
  );
  wrap.append(
    plotPanel(
      "Semi-major axis, trend removed",
      "m",
      samples,
      domain,
      record,
      gaps,
      labelPermitted,
      [{ colour: "var(--oh-manoeuvre)", value: (sample) => residuals.get(sample.t) ?? 0 }],
      "The straight-line trend has been subtracted so a step is visible. A metre here is real: the measured element-to-element scatter is 1.67 m below 500 km and 0.10 m from 800 to 1500 km.",
    ),
  );

  wrap.append(
    plotPanel("Inclination", "°", samples, domain, record, gaps, labelPermitted, [
      { colour: "var(--oh-plane)", value: (sample) => sample.inclinationDeg },
    ]),
  );

  if (samples.some((sample) => sample.bstar !== null && sample.bstar > 0)) {
    wrap.append(
      plotPanel(
        "B* drag term",
        "log",
        samples,
        domain,
        record,
        gaps,
        labelPermitted,
        [
          {
            colour: "var(--oh-drag)",
            value: (sample) =>
              sample.bstar !== null && sample.bstar > 0 ? Math.log10(sample.bstar) : Number.NaN,
          },
        ],
        "The fitted drag term. It is an independent witness whenever the drag story is the one being told: it moves when the atmosphere the object is flying through changes, and it does not move when an operator burns.",
      ),
    );
  }
  wrap.append(renderSignatureLegend());
  return wrap;
}

/**
 * The key to the dashed event rules drawn across every panel above.
 *
 * Drawn in SVG rather than in markup for one reason: the swatch has to BE the
 * mark it explains. It is the same dashed rule, carrying the same
 * `orbit-history__event-rule` class and taking its stroke from the same
 * `SIGNATURE_COLOUR` tokens the plots read, so a colour changed in one
 * place moves in both and the key can never quietly describe a picture that is
 * no longer being drawn. It also stays inside the panel chrome this file
 * already uses -- `orbit-history__plot` for the box,
 * `orbit-history__tick` for the small type, `__provenance` for the
 * note -- rather than asking `orbit-history.css`, which another agent
 * owns, for a new rule.
 *
 * The last paragraph is not decoration. A key is where a reader learns to read
 * the picture, so it is also the right place to say, once, that the picture is
 * a set of candidates and every cost on it is a lower bound.
 */
function renderSignatureLegend(): HTMLElement {
  const FAMILY_LEADING = 14;
  const LINE_LEADING = 11;
  const ROW_GAP = 7;
  const TEXT_X = 46;

  const panel = element("div", "orbit-history__plot");
  const heading = document.createElement("h4");
  heading.textContent = "Signature colours and the drift channel";
  panel.append(heading);

  const svg = document.createElementNS(SVG, "svg");
  let y = 12;
  for (const row of SIGNATURE_LEGEND) {
    const rule = document.createElementNS(SVG, "line");
    rule.setAttribute("class", "orbit-history__event-rule");
    rule.setAttribute("stroke", row.colour);
    rule.setAttribute("x1", "10");
    rule.setAttribute("x2", "36");
    rule.setAttribute("y1", String(y - 4));
    rule.setAttribute("y2", String(y - 4));
    svg.append(rule);

    const family = document.createElementNS(SVG, "text");
    family.setAttribute("x", String(TEXT_X));
    family.setAttribute("y", String(y));
    family.setAttribute("fill", "var(--oh-ink, #e8edf5)");
    family.setAttribute("font-size", "10.5");
    family.setAttribute("font-weight", "600");
    family.textContent = row.family;
    svg.append(family);
    y += FAMILY_LEADING;

    for (const line of row.lines) {
      const text = document.createElementNS(SVG, "text");
      text.setAttribute("class", "orbit-history__tick");
      text.setAttribute("x", String(TEXT_X));
      text.setAttribute("y", String(y));
      text.textContent = line;
      svg.append(text);
      y += LINE_LEADING;
    }
    y += ROW_GAP;
  }
  // Set last: the height is only known once the rows have been laid out, and
  // `orbit-history.css` sizes these panels `width: 100%; height: auto`, which
  // needs the viewBox to have a real aspect ratio or the panel collapses.
  svg.setAttribute("viewBox", `0 0 ${PLOT_WIDTH} ${y}`);
  svg.setAttribute("role", "img");
  svg.setAttribute(
    "aria-label",
    SIGNATURE_LEGEND.map((row) => `${row.family}: ${row.lines.join(" ")}`).join(". "),
  );
  panel.append(svg);

  const note = element("p", "orbit-history__provenance");
  note.textContent =
    "A colour names a family of signatures. Long-arc drift has its own card colour. The colour says what the ELEMENTS moved like; it "
    + "never says an operator did it. Until the detector that judged an event has its "
    + "false-alarm rate bounded below the design target, every rule above is a candidate, "
    + "and every Δv quoted anywhere on this page is a lower bound on the cost.";
  panel.append(note);
  return panel;
}

interface Series {
  colour: string;
  value: (sample: OrbitSample) => number;
}

function plotPanel(
  title: string,
  unit: string,
  samples: readonly OrbitSample[],
  domain: [number, number],
  record: OrbitHistoryObject,
  gaps: readonly NoDataInterval[],
  /**
   * The SAME gate the cards below the plot use. Passed in rather than decided
   * here, because this module never rules on what has been established.
   */
  labelPermitted: (event: OrbitEventMarker) => boolean,
  series: readonly Series[],
  note?: string,
): HTMLElement {
  const panel = element("div", "orbit-history__plot");
  const heading = document.createElement("h4");
  heading.textContent = title;
  const range = document.createElement("span");
  heading.append(range);
  panel.append(heading);

  const values: number[] = [];
  for (const item of series) {
    for (const sample of samples) {
      const value = item.value(sample);
      if (Number.isFinite(value)) values.push(value);
    }
  }
  if (values.length === 0) {
    panel.append(emptyState("No data in this panel", "Nothing was published for this quantity."));
    return panel;
  }
  let low = Math.min(...values);
  let high = Math.max(...values);
  if (high - low < 1e-9) {
    // A flat series would otherwise divide by zero and collapse to a line at
    // the top of the panel. Padding by a visible amount keeps it centred and,
    // more importantly, keeps it honestly flat rather than falsely dramatic.
    const pad = Math.max(Math.abs(high) * 1e-6, 1e-6);
    low -= pad;
    high += pad;
  }
  range.textContent = `${formatAxis(low, unit)} … ${formatAxis(high, unit)}`;

  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("viewBox", `0 0 ${PLOT_WIDTH} ${PLOT_HEIGHT}`);
  svg.setAttribute("role", "img");
  svg.setAttribute(
    "aria-label",
    `${title} from ${new Date(domain[0]).toISOString()} to ${new Date(domain[1]).toISOString()}, ranging ${formatAxis(low, unit)} to ${formatAxis(high, unit)}`,
  );

  const x = (t: number) =>
    PLOT_MARGIN.left +
    ((t - domain[0]) / Math.max(domain[1] - domain[0], 1)) *
      (PLOT_WIDTH - PLOT_MARGIN.left - PLOT_MARGIN.right);
  const y = (value: number) =>
    PLOT_MARGIN.top +
    (1 - (value - low) / (high - low)) * (PLOT_HEIGHT - PLOT_MARGIN.top - PLOT_MARGIN.bottom);

  // Gaps first, so everything else draws over them.
  for (const gap of gaps) {
    const from = Date.parse(gap.from);
    const to = Date.parse(gap.to);
    if (!Number.isFinite(from) || !Number.isFinite(to)) continue;
    const left = Math.max(from, domain[0]);
    const right = Math.min(to, domain[1]);
    if (right <= left) continue;
    const rect = document.createElementNS(SVG, "rect");
    rect.setAttribute("class", "orbit-history__gap");
    rect.setAttribute("x", String(x(left)));
    rect.setAttribute("y", String(PLOT_MARGIN.top));
    rect.setAttribute("width", String(Math.max(x(right) - x(left), 1)));
    rect.setAttribute("height", String(PLOT_HEIGHT - PLOT_MARGIN.top - PLOT_MARGIN.bottom));
    const title = document.createElementNS(SVG, "title");
    title.textContent = gap.note;
    rect.append(title);
    svg.append(rect);
  }

  for (const item of series) {
    const drawable = samples.map((sample, index) => ({ ...sample,
      joinPrevious: index > 0 && Number.isFinite(item.value(samples[index - 1]!))
        ? sample.joinPrevious : false,
    })).filter(sample => Number.isFinite(item.value(sample)));
    const { runs, isolated } = toSegments(drawable);
    for (const run of runs) {
      const path = document.createElementNS(SVG, "path");
      path.setAttribute("class", "orbit-history__series");
      path.setAttribute("stroke", item.colour);
      path.setAttribute(
        "d",
        run
          .map(
            (sample, index) =>
              `${index === 0 ? "M" : "L"}${x(sample.t).toFixed(2)},${y(item.value(sample)).toFixed(2)}`,
          )
          .join(" "),
      );
      svg.append(path);
    }
    // Reduced curves use paths plus isolated dots, avoiding thousands of DOM
    // circles at normal zoom. Full resolution retains its individual dots.
    const isolatedTimes = new Set(isolated.map(sample => sample.t));
    for (const sample of record.display ? isolated : drawable) {
      const dot = document.createElementNS(SVG, "circle");
      dot.setAttribute("class", "orbit-history__point");
      dot.setAttribute("cx", String(x(sample.t)));
      dot.setAttribute("cy", String(y(item.value(sample))));
      dot.setAttribute("r", isolatedTimes.has(sample.t) ? "2.6" : "1.6");
      dot.setAttribute("fill", item.colour);
      svg.append(dot);
    }
  }

  for (const event of record.events) {
    const at = Date.parse(event.endAt);
    if (!Number.isFinite(at)) continue;
    const rule = document.createElementNS(SVG, "line");
    rule.setAttribute("class", "orbit-history__event-rule");
    rule.setAttribute("stroke", SIGNATURE_COLOUR[event.signature] ?? "var(--oh-unattributed)");
    rule.setAttribute("x1", String(x(at)));
    rule.setAttribute("x2", String(x(at)));
    rule.setAttribute("y1", String(PLOT_MARGIN.top));
    rule.setAttribute("y2", String(PLOT_HEIGHT - PLOT_MARGIN.bottom));
    const label = document.createElementNS(SVG, "title");
    // THE HEDGE TRAVELS WITH THE CLAIM, INCLUDING INTO A TOOLTIP. This printed
    // the raw `signatureLabel`, so hovering a rule under an uncalibrated
    // detector read "in-plane raise" flat while the evidence card a few inches
    // below it read "in-plane raise (candidate)". A tooltip is not decoration:
    // it is the only sentence a reader gets for a rule they never click, and it
    // was the one place on this page that said the word without earning it.
    label.textContent =
      `${eventNoun(event, labelPermitted(event))} · `
      + formatDeltaV(event.deltaVMetresPerSecond);
    rule.append(label);
    svg.append(rule);
  }

  const axis = document.createElementNS(SVG, "line");
  axis.setAttribute("class", "orbit-history__axis");
  axis.setAttribute("x1", String(PLOT_MARGIN.left));
  axis.setAttribute("x2", String(PLOT_WIDTH - PLOT_MARGIN.right));
  axis.setAttribute("y1", String(PLOT_HEIGHT - PLOT_MARGIN.bottom));
  axis.setAttribute("y2", String(PLOT_HEIGHT - PLOT_MARGIN.bottom));
  svg.append(axis);

  for (const [fraction, anchor] of [
    [0, "start"],
    [1, "end"],
  ] as const) {
    const text = document.createElementNS(SVG, "text");
    text.setAttribute("class", "orbit-history__tick");
    text.setAttribute("x", String(x(domain[0] + fraction * (domain[1] - domain[0]))));
    text.setAttribute("y", String(PLOT_HEIGHT - 3));
    text.setAttribute("text-anchor", anchor);
    text.textContent = new Date(domain[0] + fraction * (domain[1] - domain[0]))
      .toISOString()
      .slice(0, 16)
      .replace("T", " ");
    svg.append(text);
  }

  panel.append(svg);
  if (note) {
    const caption = element("p", "orbit-history__provenance");
    caption.textContent = note;
    panel.append(caption);
  }
  return panel;
}

function timeDomain(samples: readonly OrbitSample[]): [number, number] {
  if (samples.length === 0) {
    const now = Date.now();
    return [now - 86_400_000, now];
  }
  const head = samples[0];
  const tail = samples[samples.length - 1];
  if (head === undefined || tail === undefined) {
    const now = Date.now();
    return [now - 86_400_000, now];
  }
  const first = head.t;
  const last = tail.t;
  if (last - first < 60_000) return [first - 43_200_000, last + 43_200_000];
  return [first, last];
}

/* ------------------------------------------------------------------------ */
/* Evidence card                                                             */
/* ------------------------------------------------------------------------ */

/**
 * A headline event, drawn from what a headline event actually carries.
 *
 * This is the reduced card for an object whose shard has not been published in
 * this release. It says less than the evidence card on purpose — the evidence
 * is not in this record — and it says so, rather than leaving a reader to
 * assume the change was examined less carefully than the ones above it.
 */
/**
 * WHERE THIS ORBIT IS GOING -- the one signal on this page with no false-alarm
 * problem, and therefore the one that works on objects that cannot manoeuvre.
 *
 * Everything else here is a DETECTION: a step in the elements that had to be
 * told apart from the catalogue's own fit noise, which is why each event's
 * wording is governed by its detector's passive control. A trend is not a
 * detection. `orbit_campaigns.decay_trend()`
 * takes the MEDIAN of this object's own per-day rates rather than fitting a
 * slope, precisely so that a burn sitting inside the series cannot tilt it:
 * half the daily rates are steeper and half are shallower whether or not one
 * interval was a manoeuvre. There is no candidate to be wrong about, and on a
 * spent stage or a fragment -- which have no thrust to confuse with drag --
 * that makes it the only question this archive can answer cleanly.
 *
 * THREE THINGS IT CAN SAY, AND ONLY ONE OF THEM IS DECAY.
 *
 *   falling, and low enough to call it decay -- the module's own `decaying`,
 *     which is a negative median AND a perigee under 1,400 km. Both halves are
 *     required: TIBA-1 is losing 138.7 m of semi-major axis a day at a perigee
 *     of 35,776 km, and that is a geostationary drift cycle, not re-entry.
 *   falling, but not called decay -- reported with the altitude that
 *     disqualified it, so a reader can see the trend and see why it is not
 *     named.
 *   rising -- shown, where it used to be silence. Drag only ever takes energy
 *     out of an orbit, so a median that rises is not a drag signature at all.
 *     What it IS, the elements do not say, and this block does not guess.
 *
 * THE REMAINING-LIFE FIGURE IS AN UPPER BOUND AND IS PRINTED ONLY WHERE THE
 * MODULE OFFERS ONE. `decay_trend` withholds it above 600 km, where drag stops
 * being unambiguously the dominant term, and it is an upper bound rather than
 * an estimate because decay ACCELERATES: an object falling into denser air
 * falls faster, so a straight line drawn at today's rate always arrives late.
 * Nothing here re-derives it, extends it above 600 km, or softens the word
 * "at most".
 *
 * Long bounds are printed in years, and very long ones in thousands of years,
 * rather than through `formatDays`. That is not cosmetic. STARLINK-31328 is
 * losing 0.29 m a day at 462 km, which divides out to 1,175,003.7 -- and the
 * page was rendering "at most 1175003.7 days of altitude left", a sentence that
 * reads as a precise forecast and is arithmetic on a number near zero. "At most
 * 3 thousand years" is the same figure said in a way that cannot be mistaken
 * for a prediction.
 */
function renderDecayTrend(decay: ObjectSummary["decay"]): HTMLElement | null {
  // `metresPerDay` is null when the object had no interval long enough to form
  // a rate. That is "we could not measure it", which is not a finding about the
  // orbit, so nothing is drawn -- the same rule the repeat-cluster block
  // follows for an absent key.
  if (!decay || decay.metresPerDay == null || !Number.isFinite(decay.metresPerDay)) return null;

  const rate = decay.metresPerDay;
  const perigee = decay.perigeeAltitudeKm;
  const wrap = element("section", "orbit-history__decay");

  const heading = document.createElement("h3");
  heading.textContent = "Where this orbit is going";
  wrap.append(heading);

  const lede = element("p", "orbit-history__wording");
  if (decay.decaying) {
    lede.textContent =
      "This orbit is coming down. More than half of this object's day-to-day rates "
      + "are downward, and at this perigee drag is the term that dominates.";
  } else if (rate < 0) {
    lede.textContent =
      "This orbit is losing semi-major axis, and it is NOT being called decay. "
      + (perigee != null
        ? `At a perigee of ${perigee.toFixed(0)} km, drag is not the dominant term, `
        : "Above the altitude where drag dominates, ")
      + "so the trend is reported and its cause is not attributed.";
  } else if (rate > 0) {
    lede.textContent =
      "This orbit is gaining semi-major axis. Drag only ever takes energy out, so a "
      + "rising median is not a drag signature — but what it is instead, the element "
      + "sets alone do not say.";
  } else {
    lede.textContent =
      "No net change in semi-major axis across the archive: the median of this "
      + "object's daily rates is zero.";
  }
  wrap.append(lede);

  const list = document.createElement("dl");
  const direction = rate < 0 ? "losing" : rate > 0 ? "gaining" : "holding";
  appendPair(
    list,
    "Median rate",
    `${formatMetres(rate)} of semi-major axis per day (${direction})`,
  );
  if (perigee != null) appendPair(list, "Perigee now", `${perigee.toFixed(0)} km`);
  if (decay.upperBoundDaysToReentry != null) {
    appendPair(
      list,
      "Altitude left, at most",
      formatLongDuration(decay.upperBoundDaysToReentry),
    );
  }
  wrap.append(list);

  const provenance = element("p", "orbit-history__provenance");
  provenance.textContent = decay.reentryNote ? `${decay.note} ${decay.reentryNote}` : decay.note;
  wrap.append(provenance);
  return wrap;
}

/**
 * The repeating corrections, drawn as one finding rather than N steps.
 *
 * WHY THIS ONE MAY SPEAK PLAINLY WHILE A LONE EVENT MAY NOT. `labelPolicy`
 * can forbid calling a single detection a manoeuvre when that detector's
 * passive-control bound misses the target. That bound is about ISOLATED steps.
 * A group of equal-cost steps on a fixed cadence is corroborated by its own
 * repetition: a false alarm has no reason to recur every 14.5 days at the same
 * cost, and the probability that it does so N times falls off a cliff with N.
 *
 * So the wording here is firmer than on an event card -- and it still stops
 * short of naming a cause. "A correction repeated on a schedule" is what the
 * elements show. "Station-keeping" is an inference about intent, and the site
 * does not make it for the reader.
 */
function renderRepeatClusters(clusters: OrbitRepeatCluster[]): HTMLElement {
  const wrap = element("section", "orbit-history__clusters");

  const heading = document.createElement("h3");
  heading.textContent = clusters.length === 1
    ? "A correction this object repeats"
    : "Corrections this object repeats";
  wrap.append(heading);

  const lede = element("p", "orbit-history__wording");
  lede.textContent =
    "Same signature, same size within a tolerance band, on a repeating schedule. "
    + "A single change stands on its detector's own passive control; a cadence adds "
    + "corroboration through repetition.";
  wrap.append(lede);

  for (const cluster of clusters) {
    const card = element("article", "orbit-history__card");

    const title = document.createElement("h4");
    const label = cluster.signature.replace(/-/g, " ");
    title.textContent = `${cluster.count} × ${label}`;
    card.append(title);

    const list = document.createElement("dl");
    appendPair(list, "Each one costs", formatDeltaV(cluster.medianDeltaVMetresPerSecond));
    if (cluster.deltaVSpreadMetresPerSecond > 0) {
      appendPair(list, "Spread", `± ${formatDeltaV(cluster.deltaVSpreadMetresPerSecond)}`);
    }
    if (cluster.medianDaysBetween !== null) {
      const jitter = cluster.spacingScaleDays !== null && cluster.spacingScaleDays > 0
        ? ` (± ${cluster.spacingScaleDays.toFixed(1)} d)`
        : "";
      appendPair(list, "Repeats every", `${cluster.medianDaysBetween.toFixed(1)} days${jitter}`);
    }
    appendPair(list, "Total over the run", formatDeltaV(cluster.totalDeltaVMetresPerSecond));

    // The annual rate is what makes this comparable to a published budget --
    // an operator's station-keeping allowance is quoted in m/s per year, so
    // quoting the same unit is what lets a reader check this against one.
    const spanDays =
      (Date.parse(cluster.lastAt) - Date.parse(cluster.firstAt)) / 86_400_000;
    if (Number.isFinite(spanDays) && spanDays >= 30) {
      const perYear = (cluster.totalDeltaVMetresPerSecond / spanDays) * 365.25;
      appendPair(list, "Rate", `${perYear.toFixed(2)} m/s per year, over ${Math.round(spanDays)} days`);
    }
    appendPair(list, "Seen between", `${cluster.firstAt} and ${cluster.lastAt}`);
    card.append(list);
    wrap.append(card);
  }

  const provenance = element("p", "orbit-history__provenance");
  provenance.textContent =
    "Grouped from this object's own events: same signature, cost inside a tolerance "
    + "band of the group's running median. Every Δv is a lower bound — the cheapest "
    + "manoeuvre consistent with the element change. What the schedule is FOR is not "
    + "stated here; that is an inference about intent, and this page reports what the "
    + "elements show.";
  wrap.append(provenance);
  return wrap;
}

function renderHeadlineCard(event: OrbitHeadlineEvent, bundle: OrbitEventsBundle): HTMLElement {
  const wrap = element("article", "orbit-history__card");
  const permitted = eventLabelPermitted(
    event, bundle.labelPolicy.manoeuvreLabelPermitted,
  );

  const heading = document.createElement("h3");
  heading.textContent = event.signatureLabel;
  wrap.append(heading);

  const kicker = element("p", "orbit-history__wording");
  kicker.textContent = `${eventNoun(event, permitted)} · ${event.startAt} → ${event.endAt}`;
  wrap.append(kicker);

  const list = document.createElement("dl");
  appendPair(list, "Δv (lower bound)", formatDeltaV(event.deltaVMetresPerSecond));
  appendPair(list, "Regime", event.regime);
  appendControlIdentity(list, event);
  appendPair(list, "Perigee", `${event.perigeeAltitudeKm.toFixed(0)} km`);
  appendPair(list, "Apogee", `${event.apogeeAltitudeKm.toFixed(0)} km`);
  appendPair(list, "Inclination", `${event.inclinationDeg.toFixed(3)}°`);
  if (event.expectationVerdict) {
    appendPair(list, "Expectation", event.expectationVerdict.replace(/-/g, " "));
  }
  wrap.append(list);

  const honesty = element("p", "orbit-history__provenance");
  honesty.textContent = `${CONFIDENCE_COPY[event.confidence] ?? ""} `
    + "This is the summary row from the cross-catalogue list. The per-interval tests, the drag "
    + "comparison and the concurrent space weather are published in this object's history shard, "
    + "which is not in this release.";
  wrap.append(honesty);
  return wrap;
}

function appendControlIdentity(list: HTMLDListElement, event: OrbitHeadlineEvent | OrbitEventRecord): void {
  appendPair(list, "Detector", event.controlBasis ?? "not published");
  const stratum = event.controlStratum;
  appendPair(list, "Matched control", typeof stratum === "object"
    ? `${stratum.era} · ${stratum.band} km perigee`
    : stratum ?? "not published: matched control is unavailable");
}

function renderEvidenceCard(event: OrbitEventRecord, bundle: OrbitEventsBundle): HTMLElement {
  const wrap = element("article", "orbit-history__card");
  const permitted = eventLabelPermitted(
    event, bundle.labelPolicy.manoeuvreLabelPermitted,
  );

  const heading = document.createElement("h3");
  heading.textContent = event.card.headline;
  wrap.append(heading);

  const kicker = element("p", "orbit-history__wording");
  kicker.textContent = `${eventNoun(event, permitted)} · ${event.startAt} → ${event.endAt}`;
  wrap.append(kicker);

  const list = document.createElement("dl");
  appendPair(list, "Δv (lower bound)", formatDeltaV(event.deltaV.totalMetresPerSecond));
  appendControlIdentity(list, event);
  appendPair(list, "Tangential", formatDeltaV(event.deltaV.tangentialMetresPerSecond));
  appendPair(list, "Plane change", formatDeltaV(event.deltaV.planeChangeMetresPerSecond));
  appendPair(
    list,
    "Drag accounts for",
    event.drag.applicable
      ? `${formatMetres(event.drag.predictedDeltaAMetres)} ± ${formatMetres(event.drag.predictedSigmaMetres, false)}`
      : "not separable",
  );
  appendPair(list, "Concurrent Kp", event.spaceWeather.kpMax?.toFixed(1) ?? "not archived");
  appendPair(list, "Expectation", event.expectation.verdict.replace(/-/g, " "));
  wrap.append(list);

  // The model's paragraph when one survived the gate, the deterministic one
  // otherwise. Both are complete; only the label differs.
  const prose = document.createElement("p");
  prose.textContent = event.narrative?.text ?? event.card.observation;
  wrap.append(prose);

  if (!event.narrative) {
    for (const section of [event.card.cost, event.card.control] as const) {
      if (!section) continue;
      const paragraph = document.createElement("p");
      paragraph.textContent = section;
      wrap.append(paragraph);
    }
  }

  const causes = element("ul", "orbit-history__causes");
  for (const cause of event.card.candidateCauses) {
    const item = document.createElement("li");
    const strong = document.createElement("strong");
    strong.textContent = cause.label;
    const detail = document.createElement("span");
    detail.textContent = ` — ${cause.detail}`;
    item.append(strong, detail);
    causes.append(item);
  }
  if (event.card.candidateCauses.length > 0) {
    const causeHeading = element("p", "orbit-history__wording");
    causeHeading.textContent = "What could produce this signature";
    wrap.append(causeHeading, causes);
  }

  if (event.groundTruth) {
    const confirmation = element("p", "orbit-history__provenance");
    confirmation.textContent =
      "This change was detected from orbital elements and independently reported by the operator. " +
      `Published as ${String(event.groundTruth.type ?? "a manoeuvre")} at ${String(event.groundTruth.occurredAt ?? "an unstated time")}.`;
    const link = document.createElement("a");
    link.href = String(event.groundTruth.source ?? "");
    link.textContent = " Source";
    link.rel = "noreferrer noopener";
    link.target = "_blank";
    if (link.href) confirmation.append(link);
    wrap.append(confirmation);
  }

  const honesty = element("p", "orbit-history__provenance");
  honesty.textContent = `${CONFIDENCE_COPY[event.confidence] ?? ""} ${event.card.honesty}`.trim();
  wrap.append(honesty);

  const footer = element("p", "orbit-history__provenance");
  footer.textContent = event.narrative
    ? `${event.narrative.caveat} ${event.card.footer} Wording assisted by a local language model, which may only phrase causes computed here and states no numbers.`
    : `${event.card.footer} Wording is generated deterministically from the computed evidence.`;
  wrap.append(footer);
  return wrap;
}

/* ------------------------------------------------------------------------ */
/* Small helpers                                                             */
/* ------------------------------------------------------------------------ */

function element<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  className: string,
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  node.className = className;
  return node;
}

function addCell(row: HTMLTableRowElement, text: string): void {
  const cell = row.insertCell();
  cell.textContent = text;
}

function flag(text: string, kind: "unusual" | "decaying" | "regular"): HTMLElement {
  const span = element("span", `orbit-history__flag orbit-history__flag--${kind}`);
  span.textContent = text;
  return span;
}

function appendPair(list: HTMLDListElement, label: string, value: string): void {
  const term = document.createElement("dt");
  term.textContent = label;
  const definition = document.createElement("dd");
  definition.textContent = value;
  list.append(term, definition);
}

function appendNumber(
  target: HTMLElement,
  label: string,
  value: string,
  note?: string,
): void {
  const wrap = document.createElement("div");
  const caption = document.createElement("span");
  caption.textContent = label;
  const strong = document.createElement("strong");
  strong.textContent = value;
  wrap.append(caption, strong);
  if (note) {
    const small = document.createElement("small");
    small.textContent = note;
    wrap.append(small);
  }
  target.append(wrap);
}

function emptyState(title: string, body: string, footnote?: string): HTMLElement {
  const wrap = element("div", "orbit-history__empty");
  const strong = document.createElement("strong");
  strong.textContent = title;
  const paragraph = document.createElement("p");
  paragraph.textContent = body;
  wrap.append(strong, paragraph);
  if (footnote) {
    const code = document.createElement("code");
    code.textContent = footnote;
    wrap.append(code);
  }
  return wrap;
}

/**
 * The one button on this panel that asks a human for something.
 *
 * `data-informed-feedback` is the whole wiring: feedback-widget.js is baked
 * into the image and binds a delegated click listener on `document`, so a
 * button created long after load works without this module importing it,
 * knowing its endpoint, or breaking when the widget is absent -- an unbound
 * button is inert, not an error.
 *
 * NO `mailto:` AND NO ADDRESS. Sean built the feedback box precisely so that
 * his and Derek's mail need not sit on a public teaching site being harvested.
 * If this ever needs to reach them another way, that is his decision, not a
 * convenience for whoever is editing this file.
 */
function feedbackButton(label: string): HTMLElement {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "secondary-button orbit-history__ask";
  button.textContent = label;
  button.setAttribute("data-informed-feedback", "");
  return button;
}

function loading(): HTMLElement {
  return emptyState("Loading history…", "Fetching this object's shard of the archive.");
}

function formatDays(days: number): string {
  if (!Number.isFinite(days)) return "—";
  if (days < 1 / 24) return `${(days * 24 * 60).toFixed(0)} minutes`;
  if (days < 1) return `${(days * 24).toFixed(1)} hours`;
  return `${days.toFixed(1)} days`;
}

/**
 * A span that may be geological, said in a unit a reader can hold.
 *
 * Separate from `formatDays` on purpose. `formatDays` serves "watched for" and
 * "repeats every", where days are the right unit and the numbers are small.
 * This serves the remaining-life bound, where dividing an altitude by a median
 * rate near zero legitimately produces six figures of days: rendering that
 * verbatim gives a sentence that reads like a forecast to the tenth of a day
 * and is nothing of the kind.
 */
function formatLongDuration(days: number): string {
  if (!Number.isFinite(days)) return "—";
  if (days < 365.25) return `${days.toFixed(0)} days`;
  const years = days / 365.25;
  if (years < 10) return `${years.toFixed(1)} years`;
  if (years < 1000) return `${years.toFixed(0)} years`;
  return `${(years / 1000).toFixed(0)} thousand years`;
}

function formatAxis(value: number, unit: string): string {
  if (unit === "log") return `1e${value.toFixed(1)}`;
  if (unit === "°") return `${value.toFixed(4)}°`;
  if (unit === "m") return `${value.toFixed(1)} m`;
  return `${value.toFixed(1)} ${unit}`;
}

/**
 * The shard count, from the caller — which is to say from the manifest.
 *
 * This used to read `shardCount` off the events bundle. The bundle has never
 * carried one: `pipeline/orbit_release.py` puts it on the *manifest* record
 * beside the shard list, so the read always came back undefined and the
 * hard-coded 256 was doing all the work. It is 256 today, so the wrong path
 * gave the right answer, which is exactly why nothing noticed.
 */
function resolveShardCount(declared: number | undefined): number {
  return typeof declared === "number" && Number.isFinite(declared) && declared > 0
    ? declared
    : 256;
}
