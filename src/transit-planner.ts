/**
 * Transit mission planner — the view and its controller.
 *
 * A route is laid out as waypoints with times; the planner answers, over that
 * whole route, which satellites can see the moving position and when. The
 * arithmetic lives in `src/transit-solve.ts` and `src/transit-visibility.ts`;
 * the published facts live in `data/satcom_capabilities.json` and
 * `data/programme_participation.json`; this file is the surface that puts them
 * together.
 *
 * ## The three things a reader must not be able to miss
 *
 * 1. **The elevation mask.** It is the single assumption that most changes the
 *    answer, so it is a control at the top of the panel with its consequence
 *    stated next to it, not a preference hidden behind a settings gear.
 * 2. **What the orbital elements are.** Publicly distributed mean elements
 *    propagated with SGP4 — a fitted prediction, not an operational ephemeris.
 *    The header says so before any answer is shown.
 * 3. **What the capability list is not.** Published system-level facts about
 *    who provides which service, intersected with geometry. Not an access plan,
 *    and silent about anything the public record does not state.
 *
 * ## The interaction Sean asked for
 *
 * Clicking a waypoint dims every constellation that is not overhead at that
 * waypoint and leaves the ones that are in normal weight. Dimmed, never removed:
 * "this system exists and cannot help you here" is the answer to the question,
 * and hiding the row throws it away.
 */

import "./transit-planner.css";
import type { CatalogBundle, SatelliteRecord } from "./types";
import type { LandGeoJson } from "./globe";
import { footprintAngularRadius, footprintPoints } from "./orbit";
import {
  buildLegs,
  positionAt,
  routeSpanMs,
  validateRoute,
  type TransitRoute,
  type Waypoint,
} from "./transit-route";
import {
  estimateEvaluations,
  subsatellitePoint,
  type ElementAgeBand,
  type SolveSatelliteInput,
} from "./transit-solve";
import type { SatelliteVisibilityResult } from "./transit-solve";
import { elevationDeg, type Interval } from "./transit-visibility";
import {
  resolveSystems,
  satellitesOverheadAt,
  summarizeSystemCoverage,
  systemsForNeed,
  type ResolvedSystem,
  type SystemCoverage,
} from "./satcom-capabilities";
import {
  aorReference,
  formatDuration,
  formatTime,
  parseTime,
  satcomCapabilities,
  toInputValue,
  zoneDescription,
  zoneLetter,
  type TimeConvention,
} from "./transit-planner-data";
import { AOR_BOUNDARIES, type AorBoundary } from "./data/aor-boundaries";
import {
  DEFAULT_PRESET_ID,
  TRANSIT_PRESETS,
  presetById,
  routeFromPreset,
} from "./transit-presets";
import {
  buildLandIndex,
  routeLandCrossings,
  type LandCrossing,
  type LandIndex,
} from "./transit-land";
import { audienceProfile, type Audience, type AudienceProfile } from "./transit-audience";
import { downloadCsv, exportFilename, windowsToCsv, type ExportContext } from "./transit-export";
import { TransitGlobe } from "./transit-globe";
import {
  TransitMap,
  formatLatitude,
  formatLongitude,
  type SatelliteMarker,
} from "./transit-map";
import { json2satrec, type SatRec } from "satellite.js";

/** Default evaluation ceiling. About 13 s of solve on a mid-range laptop. */
const DEFAULT_EVALUATION_BUDGET = 5_000_000;
const MASK_PRESETS = [0, 5, 10, 15, 20] as const;
/** Geostationary geocentric altitude, for the one live consequence of the mask. */
const GEOSTATIONARY_ALTITUDE_KM = 35_786;

/**
 * How far from its sub-satellite point a geostationary satellite stays above a
 * mask, in degrees of arc.
 *
 * This replaced three hard-typed numbers in a paragraph ("81.3 at 0, 76.3 at 5,
 * 71.4 at 10"). It is the same arithmetic, computed from the control the reader
 * is holding, so the fact moves when the slider moves instead of sitting in
 * prose beside it.
 */
export function geostationaryReachDeg(maskDeg: number): number {
  return (footprintAngularRadius(GEOSTATIONARY_ALTITUDE_KM, maskDeg) * 180) / Math.PI;
}

export interface TransitPlannerOptions {
  container: HTMLElement;
  catalog: CatalogBundle;
  land: LandGeoJson;
  /**
   * Which presentation to build. Defaults to "public", and the public wiring
   * patch never passes anything else — so the gated build is unreachable from
   * the public bundle by construction rather than by a runtime check, in the
   * same spirit as pipeline/discovery_page.py's unpublishable-by-construction
   * note. See docs/transit-planner-wiring.md for the gating design.
   */
  audience?: Audience;
}

type ViewMode = "globe" | "map";

interface SolveState {
  status: "idle" | "running" | "done" | "over-budget" | "error";
  message: string;
  progress: number;
  windowsBySatellite: Map<number, Interval[]>;
  results: SatelliteVisibilityResult[];
  elapsedMs: number;
  evaluations: number;
  maskDeg: number;
  solvedAtSpan: { startMs: number; endMs: number } | null;
}

let waypointSequence = 0;
const nextWaypointId = () => `wp-${(waypointSequence += 1)}`;

/** Next whole hour after a departure offset, so the times read like a plan. */
function departureTime(): number {
  return Math.round((Date.now() + 12 * 3_600_000) / 3_600_000) * 3_600_000;
}

/**
 * The opening route.
 *
 * It is a preset, and every preset is checked against the shipped coastline by
 * `tests/transit-route-land.test.ts`. The route this replaced was hand-typed
 * pier-to-pier and sailed straight across Oahu and Kauai — eleven sampled track
 * positions on land, measured against the same artifact the map draws.
 */
function defaultRoute(): TransitRoute {
  return routeFromPreset(presetById(DEFAULT_PRESET_ID)!, departureTime(), nextWaypointId);
}

export class TransitPlanner {
  private readonly container: HTMLElement;
  private readonly land: LandGeoJson;
  private readonly profile: AudienceProfile;
  private readonly catalogUpstreamAsOf: string;
  private readonly satelliteNames = new Map<number, string>();
  /** Element age per satellite from the last solve, for the answer panel. */
  private readonly ageBySatellite = new Map<number, { days: number; band: ElementAgeBand; epoch: string }>();
  private readonly systemBySatellite = new Map<number, string>();
  private readonly resolved: ResolvedSystem[];
  private readonly satrecCache = new Map<number, SatRec | null>();

  private route = defaultRoute();
  private activePresetId: string | null = DEFAULT_PRESET_ID;
  /** Built once from the release's land artifact; see src/transit-land.ts. */
  private readonly landIndex: LandIndex;
  private landCrossingsCache: { signature: string; crossings: LandCrossing[] } | null = null;
  private timeConvention: TimeConvention = "utc";
  private maskDeg = 5;
  private observerAltitudeKm = 0.02;
  private trackTimeMs: number;
  private selectedWaypointId: string | null = null;
  private selectedNeedId: string | null = null;
  private viewMode: ViewMode = "map";
  private showOnlyVisible = true;
  // OFF by default. A geostationary footprint at a 9.5 degree mask covers
  // roughly a third of the Earth, and "satellites that can see the ship now"
  // is dozens of them, so drawing all of them on load stacked into a solid
  // orange sheet that hid the coastlines, the track and the waypoints
  // underneath it. The control is genuinely useful for one or a few
  // spacecraft, which is what it is for; it is not a sensible opening state.
  private showFootprints = false;
  private readonly activeBoundaryIds = new Set<string>();

  private solve: SolveState = {
    status: "idle",
    message: "No solve yet.",
    progress: 0,
    windowsBySatellite: new Map(),
    results: [],
    elapsedMs: 0,
    evaluations: 0,
    maskDeg: 5,
    solvedAtSpan: null,
  };

  private worker: Worker | null = null;
  private requestId = 0;
  private globe: TransitGlobe | null = null;
  private map: TransitMap | null = null;
  private viewHost: HTMLElement | null = null;

  constructor({ container, catalog, land, audience = "public" }: TransitPlannerOptions) {
    this.container = container;
    this.land = land;
    this.landIndex = buildLandIndex(land);
    this.profile = audienceProfile(audience);
    this.catalogUpstreamAsOf = catalog.upstreamAsOf;
    this.resolved = resolveSystems(satcomCapabilities, catalog.satellites);
    for (const entry of this.resolved) {
      for (const satellite of entry.satellites) {
        this.satelliteNames.set(satellite.id, satellite.name);
        if (!this.systemBySatellite.has(satellite.id)) {
          this.systemBySatellite.set(satellite.id, entry.system.name);
        }
      }
    }
    this.trackTimeMs = this.route.waypoints[0]!.timeMs;
    this.renderShell();
    this.renderAll();
  }

  // -------------------------------------------------------------------------
  // Is the track over water?
  //
  // The planner has never routed around land and still does not: it draws the
  // track it is given. What it now does is SAY when that track crosses a
  // coastline, because shipping a default that sailed through Oahu is what
  // happens when nothing checks. Cached on the route's own geometry, so
  // scrubbing time or moving the mask never re-runs it.
  // -------------------------------------------------------------------------

  private landCrossings(): LandCrossing[] {
    const signature = `${this.route.trackModel}|${this.route.waypoints
      .map((waypoint) => `${waypoint.latitudeDeg},${waypoint.longitudeDeg}`)
      .join(";")}`;
    if (this.landCrossingsCache?.signature === signature) return this.landCrossingsCache.crossings;
    const crossings = routeLandCrossings(this.landIndex, this.route);
    this.landCrossingsCache = { signature, crossings };
    return crossings;
  }

  // -------------------------------------------------------------------------
  // Satellite selection
  // -------------------------------------------------------------------------

  /** Every catalogued satellite belonging to a system in the capability table. */
  private selectedSatellites(): SatelliteRecord[] {
    const entries = this.selectedNeedId
      ? systemsForNeed(this.resolved, this.selectedNeedId)
      : this.resolved;
    const byId = new Map<number, SatelliteRecord>();
    for (const entry of entries) {
      for (const satellite of entry.satellites) byId.set(satellite.id, satellite);
    }
    return [...byId.values()];
  }

  private solveInputs(): SolveSatelliteInput[] {
    return this.selectedSatellites().map((record) => ({
      id: record.id,
      periodMinutes: record.periodMinutes,
      omm: record.omm,
    }));
  }

  // -------------------------------------------------------------------------
  // Compute
  // -------------------------------------------------------------------------

  /**
   * How far past the catalog's own vintage this build will answer at all.
   *
   * SGP4 propagates mean elements fitted near an epoch, with no covariance and
   * no knowledge of any manoeuvre since. Error grows without a bound the numbers
   * can report, so the only honest instrument is a hard refusal. The public
   * build stops at 14 days; the gated build extends to 30 because a reader who
   * signed in can weigh a stated element age against an answer, and refusing to
   * show them anything past a fortnight would make the tool useless for the
   * horizon they actually plan on. The physics is identical in both.
   */
  private horizonProblem(): string | null {
    const span = routeSpanMs(this.route);
    if (!span) return null;
    const catalogMs = Date.parse(this.catalogUpstreamAsOf);
    if (!Number.isFinite(catalogMs)) return null;
    const days = (span.endMs - catalogMs) / 86_400_000;
    const limit = this.profile.maximumElementAgeDays;
    if (days <= limit) return null;
    return `This transit ends ${Math.round(days)} days after the orbital elements were published, `
      + `and this tool refuses to answer past ${limit}. SGP4 propagates elements fitted near a single `
      + `epoch: it carries no covariance and cannot see a manoeuvre, so error grows without any bound `
      + `the numbers themselves can report. Move the route closer to ${this.catalogUpstreamAsOf.slice(0, 10)}.`;
  }

  private startSolve() {
    const horizon = this.horizonProblem();
    if (horizon) {
      this.solve = { ...this.solve, status: "error", message: horizon };
      this.renderAll();
      return;
    }
    const issues = validateRoute(this.route);
    const blocking = issues.filter((issue) => issue.kind !== "implausible-speed");
    if (blocking.length > 0) {
      this.solve = { ...this.solve, status: "error", message: blocking[0]!.message };
      this.renderAll();
      return;
    }
    const span = routeSpanMs(this.route);
    if (!span) return;

    this.worker?.terminate();
    this.worker = new Worker(new URL("./transit-worker.ts", import.meta.url), { type: "module" });
    this.requestId += 1;
    const requestId = this.requestId;
    const maskDeg = this.maskDeg;

    this.solve = {
      ...this.solve,
      status: "running",
      message: "Propagating…",
      progress: 0,
      windowsBySatellite: new Map(),
      results: [],
    };
    this.renderAll();

    this.worker.addEventListener("message", (event: MessageEvent<Record<string, unknown>>) => {
      const data = event.data;
      if (data.requestId !== requestId) return;
      if (data.type === "progress") {
        this.solve.progress = Number(data.completed) / Math.max(1, Number(data.total));
        this.solve.message = `Propagating… ${Number(data.completed)} of ${Number(data.total)} satellites`;
        this.renderStatus();
        return;
      }
      if (data.type === "over-budget") {
        this.solve = {
          ...this.solve,
          status: "over-budget",
          message: `That request needs about ${Number(data.estimatedEvaluations).toLocaleString()} orbit propagations, over the ${Number(data.budget).toLocaleString()} limit. Narrow the capability, or shorten the transit.`,
        };
        this.renderAll();
        return;
      }
      if (data.type === "error") {
        this.solve = { ...this.solve, status: "error", message: String(data.message) };
        this.renderAll();
        return;
      }
      if (data.type !== "solved") return;
      const results = data.results as SatelliteVisibilityResult[];
      const windowsBySatellite = new Map<number, Interval[]>();
      this.ageBySatellite.clear();
      for (const result of results) {
        this.ageBySatellite.set(result.satelliteId, {
          days: result.elementAgeDaysAtEnd,
          band: result.elementAgeBand,
          epoch: result.elementEpoch,
        });
        windowsBySatellite.set(
          result.satelliteId,
          result.windows.map((window) => ({ startMs: window.startMs, endMs: window.endMs })),
        );
      }
      this.solve = {
        status: "done",
        message: `Solved ${results.length} satellites in ${(Number(data.elapsedMs) / 1000).toFixed(1)} s, ${Number(data.evaluations).toLocaleString()} orbit propagations.`,
        progress: 1,
        windowsBySatellite,
        results,
        elapsedMs: Number(data.elapsedMs),
        evaluations: Number(data.evaluations),
        maskDeg,
        solvedAtSpan: { startMs: Number(data.startMs), endMs: Number(data.endMs) },
      };
      this.renderAll();
    });

    this.worker.postMessage({
      type: "solve",
      requestId,
      satellites: this.solveInputs(),
      route: this.route,
      maskDeg,
      observerAltitudeKm: this.observerAltitudeKm,
      edgeToleranceSeconds: 2,
      evaluationBudget: DEFAULT_EVALUATION_BUDGET,
    });
  }

  /** Coverage per system, recomputed from the current solve. */
  private coverage(): SystemCoverage[] {
    const span = this.solve.solvedAtSpan;
    if (!span) return [];
    const entries = this.selectedNeedId
      ? systemsForNeed(this.resolved, this.selectedNeedId)
      : this.resolved;
    return summarizeSystemCoverage(entries, this.solve.windowsBySatellite, span.startMs, span.endMs, 1000);
  }

  // -------------------------------------------------------------------------
  // Instantaneous state, for the views
  // -------------------------------------------------------------------------

  private satrecFor(record: SatelliteRecord): SatRec | null {
    let satrec = this.satrecCache.get(record.id);
    if (satrec === undefined) {
      try {
        satrec = json2satrec(record.omm);
      } catch {
        satrec = null;
      }
      this.satrecCache.set(record.id, satrec);
    }
    return satrec;
  }

  private markersAt(timeMs: number): SatelliteMarker[] {
    const observer = positionAt(this.route, timeMs);
    const markers: SatelliteMarker[] = [];
    for (const record of this.selectedSatellites()) {
      const satrec = this.satrecFor(record);
      if (!satrec) continue;
      const subpoint = subsatellitePoint(satrec, timeMs);
      if (!subpoint) continue;
      const visible = observer
        ? elevationDeg(
          observer.latitudeDeg,
          observer.longitudeDeg,
          this.observerAltitudeKm,
          subpoint.latitudeDeg,
          subpoint.longitudeDeg,
          subpoint.altitudeKm,
        ) >= this.maskDeg
        : false;
      markers.push({
        id: record.id,
        name: record.name,
        latitudeDeg: subpoint.latitudeDeg,
        longitudeDeg: subpoint.longitudeDeg,
        altitudeKm: subpoint.altitudeKm,
        colorHex: visible ? "#ffd479" : "#7fa6b6",
        visible,
      });
    }
    return markers;
  }

  // -------------------------------------------------------------------------
  // Rendering
  // -------------------------------------------------------------------------

  private renderShell() {
    this.container.innerHTML = `
      <section class="transit-planner is-${this.profile.audience}" aria-label="${escapeHtml(this.profile.title)}">
        <header class="transit-head">
          <h2>${escapeHtml(this.profile.title)}</h2>
          <p class="transit-standfirst">${escapeHtml(this.profile.standfirst)}</p>
        </header>
        ${this.disclosureMarkup()}
        ${this.lessonMarkup()}
        <div class="transit-layout">
          <aside class="transit-controls" data-transit-controls></aside>
          <div class="transit-stage">
            <div class="transit-viewbar" data-transit-viewbar></div>
            <div class="transit-view" data-transit-view></div>
            <div class="transit-scrub" data-transit-scrub></div>
          </div>
        </div>
        <div class="transit-answers" data-transit-answers></div>
        <div class="transit-reference" data-transit-reference></div>
        ${this.gatedLinkMarkup()}
      </section>`;
    this.viewHost = this.container.querySelector<HTMLElement>("[data-transit-view]");
  }

  /**
   * The lesson, public build only — now FOLDED.
   *
   * Sean's ruling was to lead with the idea that an orbit determines coverage
   * and treat the route as the worked example, and that is still what this is.
   * What changed is that 338 words of it were the first thing on the page above
   * the tool: "it has WAY too much text. Fucking ridiculous." Every word is
   * still here, one click away, and the three claims it makes are the three
   * things the controls below demonstrate. The gated build omits it entirely
   * rather than making a watch officer scroll past a lecture.
   */
  private lessonMarkup(): string {
    const lesson = this.profile.lesson;
    if (!lesson) return "";
    return `
      <details class="transit-lesson">
        <summary>${escapeHtml(lesson.heading)}</summary>
        <div class="transit-lesson-body">
          ${lesson.paragraphs.map((text) => `<p>${escapeHtml(text)}</p>`).join("")}
          <ol class="transit-lesson-points">
            ${lesson.points.map((point) => `
              <li>
                <h4>${escapeHtml(point.title)}</h4>
                <p>${escapeHtml(point.body)}</p>
              </li>`).join("")}
          </ol>
        </div>
      </details>`;
  }

  /**
   * The public build's honest pointer at the gated one. Deliberately describes
   * what is behind it and who it is for, rather than reading as a paywall.
   */
  private gatedLinkMarkup(): string {
    const link = this.profile.gatedLink;
    if (!link) return "";
    return `
      <details class="transit-gated-link">
        <summary>${escapeHtml(link.label)}</summary>
        <p>${escapeHtml(link.description)}</p>
      </details>`;
  }

  /**
   * The standing caveat: one line open, the whole argument one click away.
   *
   * The claim that has to survive being skipped is the first six words, and
   * those are still the first six words on the page. The 179 words behind them
   * are not softened, shortened or deleted — a summary a reader can shut is the
   * only version of this they will ever finish.
   */
  private disclosureMarkup(): string {
    return `
      <details class="transit-disclosure" role="note">
        <summary>
          <strong>Teaching tool. Not for operational planning.</strong>
          <span class="transit-disclosure-more">What this does and does not know</span>
        </summary>
        <div class="transit-disclosure-body">
          <p class="transit-disclosure-lead">
            Every satellite position here is computed in your browser from publicly
            distributed mean orbital elements propagated with SGP4. Those are a
            <em>fitted prediction</em>, not an operational ephemeris: accuracy degrades
            with element age, manoeuvres are invisible to them, and a satellite that has
            been repositioned since its last published element set will be in the wrong
            place. This tool models line-of-sight geometry only — it knows nothing about
            whether a beam is pointed at you, whether capacity is assigned, whether a
            terminal is certified, or whether a link would close.
          </p>
          <p class="transit-disclosure-detail">
            Capability rows come from published, cited statements about what each system
            provides. Where the public record is silent, this planner is silent. It is not
            an access plan and cannot be made into one by adding rows.
            <strong>Government and commercial systems are different answers to different
            questions</strong> — a commercial Ku-band satellite being overhead is not the
            same fact as broadcast coverage, and neither is the same as having capacity on
            it. The list keeps them apart; read the source label on every row.
          </p>
          <p class="transit-disclosure-detail">
            The track is drawn, not routed. There is no land avoidance, no traffic
            separation and no set and drift in it; a leg that crosses a coastline is
            flagged against the site's 1:110m land outline and nothing finer.
          </p>
          ${this.profile.additionalDisclosure
            ? `<p class="transit-disclosure-gated">${escapeHtml(this.profile.additionalDisclosure)}</p>`
            : ""}
        </div>
      </details>`;
  }

  private renderAll() {
    this.renderControls();
    this.renderViewBar();
    this.renderView();
    this.renderScrub();
    this.renderAnswers();
    this.renderReference();
  }

  private renderStatus() {
    const status = this.container.querySelector<HTMLElement>("[data-solve-status]");
    if (status) status.textContent = this.solve.message;
    const bar = this.container.querySelector<HTMLElement>("[data-solve-progress]");
    if (bar) bar.style.setProperty("--progress", `${Math.round(this.solve.progress * 100)}%`);
  }

  private renderControls() {
    const host = this.container.querySelector<HTMLElement>("[data-transit-controls]");
    if (!host) return;
    const legs = buildLegs(this.route);
    const span = routeSpanMs(this.route);
    const issues = validateRoute(this.route);
    const selected = this.selectedSatellites();
    const estimate = span
      ? estimateEvaluations(
        selected.map((record) => ({ periodMinutes: record.periodMinutes })),
        (span.endMs - span.startMs) / 1000,
      )
      : 0;

    host.innerHTML = `
      <div class="transit-block">
        <h3>${term("Elevation mask",
          "A satellite counts as visible only above this angle above the horizon. Zero "
          + "degrees is the geometric horizon, where no terminal works: a shipboard "
          + "terminal is limited by superstructure, mast shadowing and its own mechanical "
          + "stops, so the number you put here is an operational input, and it is the one "
          + "assumption that most changes the answer.")}</h3>
        <div class="transit-mask-row">
          <input type="range" min="0" max="30" step="0.5" value="${this.maskDeg}"
                 data-mask-slider aria-label="Minimum elevation mask, degrees">
          <output class="transit-mask-value">${this.maskDeg.toFixed(1)}°</output>
        </div>
        <div class="transit-chips">
          ${MASK_PRESETS.map((mask) => `
            <button class="transit-chip ${this.maskDeg === mask ? "is-active" : ""}" data-mask-preset="${mask}">${mask}°</button>
          `).join("")}
        </div>
        <p class="transit-consequence">
          A geostationary satellite reaches
          <strong>${geostationaryReachDeg(this.maskDeg).toFixed(1)}°</strong> of arc at this mask
          <span class="transit-consequence-delta">(${geostationaryReachDeg(0).toFixed(1)}° at 0°)</span>
        </p>
      </div>

      <div class="transit-block">
        <h3>${escapeHtml(this.profile.routeHeading)}</h3>
        <div class="transit-chips transit-presets">
          ${TRANSIT_PRESETS.map((preset) => `
            <button class="transit-chip ${this.activePresetId === preset.id ? "is-active" : ""}"
                    data-route-preset="${preset.id}" title="${escapeHtml(preset.note)}">${escapeHtml(preset.label)}</button>
          `).join("")}
        </div>
        <div class="transit-row">
          <label>${term("Track",
            "Great circle is the shortest path over a sphere and is what a ship routed "
            + "for distance approximates. A rhumb line is a single steered course; on a "
            + "long east-west leg the two separate by hundreds of nautical miles.")}
            <select data-track-model>
              <option value="great-circle" ${this.route.trackModel === "great-circle" ? "selected" : ""}>Great circle</option>
              <option value="rhumb-line" ${this.route.trackModel === "rhumb-line" ? "selected" : ""}>Rhumb line</option>
            </select>
          </label>
          <label>${term("Times in",
            "Zone time is set from each waypoint's own longitude in 15-degree bands, so "
            + "a waypoint's clock changes as the route crosses the ocean, and the zone "
            + "letter is shown with every time. Your computer's local time is applied to "
            + "every waypoint wherever it is: useful for entry, misleading for reading a "
            + "transit.")}
            <select data-time-convention>
              <option value="utc" ${this.timeConvention === "utc" ? "selected" : ""}>UTC (Zulu)</option>
              <option value="zone" ${this.timeConvention === "zone" ? "selected" : ""}>Ship's zone time</option>
              <option value="browser" ${this.timeConvention === "browser" ? "selected" : ""}>This computer's local time</option>
            </select>
          </label>
        </div>
        <ol class="transit-waypoints" data-waypoint-list>
          ${this.route.waypoints.map((waypoint, index) => this.waypointMarkup(waypoint, index)).join("")}
        </ol>
        <button class="transit-button" data-add-waypoint>Add waypoint</button>
        <p class="transit-hint transit-hint-tight">Or click the map. Drag a waypoint to move it.</p>
        ${legs.length > 0 ? `
          <table class="transit-legs">
            <caption>Legs</caption>
            <thead><tr><th>Leg</th><th>Distance</th><th>Time</th><th>Speed</th><th>${this.route.trackModel === "rhumb-line" ? "Course" : "Initial course"}</th></tr></thead>
            <tbody>
              ${legs.map((leg) => `
                <tr>
                  <td>${leg.index + 1}</td>
                  <td>${Math.round(leg.trackDistanceKm / 1.852).toLocaleString()} nm</td>
                  <td>${formatDuration(leg.durationMs)}</td>
                  <td class="${leg.speedKnots > 40 ? "is-warning" : ""}">${Number.isFinite(leg.speedKnots) ? leg.speedKnots.toFixed(1) : "—"} kn</td>
                  <td>${leg.initialCourseDeg.toFixed(0).padStart(3, "0")}°</td>
                </tr>`).join("")}
            </tbody>
          </table>` : ""}
        ${this.landWarningMarkup()}
        ${issues.length > 0 ? `<ul class="transit-issues">${issues.map((issue) => `<li>${issue.message}</li>`).join("")}</ul>` : ""}
      </div>

      <div class="transit-block">
        <h3>What do you need?</h3>
        <div class="transit-chips">
          <button class="transit-chip ${this.selectedNeedId === null ? "is-active" : ""}" data-need="">Everything catalogued</button>
          ${satcomCapabilities.needs.map((need) => `
            <button class="transit-chip ${this.selectedNeedId === need.needId ? "is-active" : ""}"
                    data-need="${need.needId}" title="${escapeHtml(need.summary)}">${escapeHtml(need.label)}</button>
          `).join("")}
        </div>
      </div>

      <div class="transit-block">
        <h3>Solve</h3>
        <label class="transit-inline">Antenna height above sea level
          <input type="number" min="0" max="0.5" step="0.005" value="${this.observerAltitudeKm}" data-observer-altitude>
          <span>km</span>
        </label>
        <p class="transit-hint transit-hint-tight">
          ${selected.length.toLocaleString()} satellites selected · about
          ${estimate.toLocaleString()} orbit propagations
          ${estimate > DEFAULT_EVALUATION_BUDGET ? `<strong> — over the ${DEFAULT_EVALUATION_BUDGET.toLocaleString()} limit</strong>` : ""}
        </p>
        <button class="transit-button transit-button-primary" data-run-solve
                ${this.solve.status === "running" ? "disabled" : ""}>
          ${this.solve.status === "running" ? "Solving…" : "Compute visibility windows"}
        </button>
        <div class="transit-progress" data-solve-progress></div>
        <p class="transit-status ${this.solve.status === "error" || this.solve.status === "over-budget" ? "is-warning" : ""}" data-solve-status>${escapeHtml(this.solve.message)}</p>
        ${this.profile.exportEnabled && this.solve.status === "done" ? `
          <button class="transit-button" data-export-csv
                  title="Every row carries its own element epoch, element age, elevation mask and provenance line, because somebody will paste one line into a message and that line has to survive the journey.">Export windows as CSV</button>` : ""}
        ${this.solve.status === "done" && Math.abs(this.solve.maskDeg - this.maskDeg) > 1e-9 ? `
          <p class="transit-status is-warning">
            These results were solved at a ${this.solve.maskDeg}° mask. The mask is now
            ${this.maskDeg}°. Solve again for the answer to match the control.
          </p>` : ""}
      </div>`;

    this.bindControls(host);
  }

  /**
   * "This leg crosses land", said plainly and only when it is true.
   *
   * Not an error and not a block: the planner is a geometry tool and a lesson
   * about a track over a continent is still a valid lesson. It is a statement
   * about the drawing, at the resolution the site actually ships, and it says
   * which resolution that is so nobody reads it as a clearance.
   */
  private landWarningMarkup(): string {
    const crossings = this.landCrossings();
    if (crossings.length === 0) return "";
    const legs = [...new Set(crossings.map((crossing) => crossing.legIndex + 1))];
    const first = crossings[0]!;
    return `
      <p class="transit-land-warning">
        <strong>Leg ${legs.join(", ")} crosses land</strong> — first at
        ${formatLatitude(first.latitudeDeg)} ${formatLongitude(first.longitudeDeg)}.
        The track is drawn, not routed, and this check is against the site's 1:110m
        outline, not a chart.
      </p>`;
  }

  private waypointMarkup(waypoint: Waypoint, index: number): string {
    const selected = waypoint.id === this.selectedWaypointId;
    const zone = zoneDescription(waypoint.longitudeDeg);
    return `
      <li class="transit-waypoint ${selected ? "is-selected" : ""}" data-waypoint="${waypoint.id}">
        <div class="transit-waypoint-head">
          <span class="transit-waypoint-index">${index + 1}</span>
          <input type="text" value="${escapeHtml(waypoint.label)}" data-waypoint-label aria-label="Waypoint ${index + 1} name">
          <button class="transit-icon-button" data-remove-waypoint title="Remove waypoint ${index + 1}" aria-label="Remove waypoint ${index + 1}">×</button>
        </div>
        <div class="transit-waypoint-grid">
          <label>Lat <input type="number" step="0.01" min="-90" max="90" value="${waypoint.latitudeDeg.toFixed(3)}" data-waypoint-latitude></label>
          <label>Lon <input type="number" step="0.01" min="-180" max="180" value="${waypoint.longitudeDeg.toFixed(3)}" data-waypoint-longitude></label>
          <label class="transit-waypoint-time">Time
            <input type="datetime-local" value="${toInputValue(waypoint.timeMs, this.timeConvention, waypoint.longitudeDeg)}" data-waypoint-time>
          </label>
        </div>
        <p class="transit-waypoint-readout">
          ${formatLatitude(waypoint.latitudeDeg)} ${formatLongitude(waypoint.longitudeDeg)} ·
          ${formatTime(waypoint.timeMs, this.timeConvention, waypoint.longitudeDeg)}
          ${this.timeConvention === "zone" ? `· ZD ${zone >= 0 ? "+" : ""}${zone} (${zoneLetter(zone)})` : ""}
        </p>
      </li>`;
  }

  private bindControls(host: HTMLElement) {
    host.querySelector<HTMLInputElement>("[data-mask-slider]")?.addEventListener("input", (event) => {
      this.maskDeg = Number((event.target as HTMLInputElement).value);
      this.renderControls();
      this.renderView();
      this.renderAnswers();
    });
    host.querySelectorAll<HTMLButtonElement>("[data-mask-preset]").forEach((button) => {
      button.addEventListener("click", () => {
        this.maskDeg = Number(button.dataset.maskPreset);
        this.renderControls();
        this.renderView();
        this.renderAnswers();
      });
    });
    host.querySelectorAll<HTMLButtonElement>("[data-route-preset]").forEach((button) => {
      button.addEventListener("click", () => {
        const preset = presetById(button.dataset.routePreset!);
        if (!preset) return;
        this.route = routeFromPreset(preset, departureTime(), nextWaypointId);
        this.activePresetId = preset.id;
        this.selectedWaypointId = null;
        this.trackTimeMs = this.route.waypoints[0]!.timeMs;
        this.invalidateSolve();
        this.renderAll();
      });
    });
    host.querySelector<HTMLSelectElement>("[data-track-model]")?.addEventListener("change", (event) => {
      this.route = { ...this.route, trackModel: (event.target as HTMLSelectElement).value as TransitRoute["trackModel"] };
      this.renderAll();
    });
    host.querySelector<HTMLSelectElement>("[data-time-convention]")?.addEventListener("change", (event) => {
      this.timeConvention = (event.target as HTMLSelectElement).value as TimeConvention;
      this.renderAll();
    });
    host.querySelector<HTMLInputElement>("[data-observer-altitude]")?.addEventListener("change", (event) => {
      this.observerAltitudeKm = Math.max(0, Number((event.target as HTMLInputElement).value) || 0);
      this.renderControls();
    });
    host.querySelector<HTMLButtonElement>("[data-add-waypoint]")?.addEventListener("click", () => {
      const last = this.route.waypoints.at(-1);
      this.addWaypoint(
        last ? last.latitudeDeg : 0,
        last ? last.longitudeDeg + 10 : 0,
        last ? last.timeMs + 24 * 3_600_000 : Date.now(),
      );
    });
    host.querySelectorAll<HTMLButtonElement>("[data-need]").forEach((button) => {
      button.addEventListener("click", () => {
        this.selectedNeedId = button.dataset.need || null;
        this.renderAll();
      });
    });
    host.querySelector<HTMLButtonElement>("[data-run-solve]")?.addEventListener("click", () => this.startSolve());
    host.querySelector<HTMLButtonElement>("[data-export-csv]")?.addEventListener("click", () => this.exportCsv());

    host.querySelectorAll<HTMLElement>("[data-waypoint]").forEach((item) => {
      const id = item.dataset.waypoint!;
      item.addEventListener("click", (event) => {
        if ((event.target as HTMLElement).closest("input,button,select")) return;
        this.selectWaypoint(id);
      });
      item.querySelector<HTMLInputElement>("[data-waypoint-label]")?.addEventListener("change", (event) => {
        this.updateWaypoint(id, { label: (event.target as HTMLInputElement).value });
      });
      item.querySelector<HTMLInputElement>("[data-waypoint-latitude]")?.addEventListener("change", (event) => {
        this.updateWaypoint(id, { latitudeDeg: Number((event.target as HTMLInputElement).value) });
      });
      item.querySelector<HTMLInputElement>("[data-waypoint-longitude]")?.addEventListener("change", (event) => {
        this.updateWaypoint(id, { longitudeDeg: Number((event.target as HTMLInputElement).value) });
      });
      item.querySelector<HTMLInputElement>("[data-waypoint-time]")?.addEventListener("change", (event) => {
        const waypoint = this.route.waypoints.find((candidate) => candidate.id === id);
        if (!waypoint) return;
        const parsed = parseTime((event.target as HTMLInputElement).value, this.timeConvention, waypoint.longitudeDeg);
        if (parsed !== null) this.updateWaypoint(id, { timeMs: parsed });
      });
      item.querySelector<HTMLButtonElement>("[data-remove-waypoint]")?.addEventListener("click", () => {
        this.removeWaypoint(id);
      });
    });
  }

  /**
   * Gated build only. `profile.exportEnabled` is false on the public site and
   * the button is never rendered there; this guard is the second lock, so a
   * future refactor that renders the button cannot also produce the file.
   */
  private exportCsv() {
    if (!this.profile.exportEnabled || this.solve.status !== "done") return;
    const context: ExportContext = {
      profile: this.profile,
      route: this.route,
      maskDeg: this.solve.maskDeg,
      observerAltitudeKm: this.observerAltitudeKm,
      results: this.solve.results,
      satelliteNames: this.satelliteNames,
      systemBySatellite: this.systemBySatellite,
      catalogUpstreamAsOf: this.catalogUpstreamAsOf,
      generatedAtMs: Date.now(),
    };
    downloadCsv(exportFilename(context), windowsToCsv(context));
  }

  private renderViewBar() {
    const host = this.container.querySelector<HTMLElement>("[data-transit-viewbar]");
    if (!host) return;
    host.innerHTML = `
      <div class="transit-chips">
        <button class="transit-chip ${this.viewMode === "map" ? "is-active" : ""}" data-view-mode="map">Map</button>
        <button class="transit-chip ${this.viewMode === "globe" ? "is-active" : ""}" data-view-mode="globe">Globe</button>
      </div>
      <label class="transit-toggle">
        <input type="checkbox" ${this.showOnlyVisible ? "checked" : ""} data-only-visible>
        Show only satellites that can see the ship now
      </label>
      <label class="transit-toggle">
        <input type="checkbox" ${this.showFootprints ? "checked" : ""} data-show-footprints>
        Draw their footprints at the mask
      </label>
      ${this.viewMode === "globe" ? `
        <p class="transit-hint transit-hint-tight" data-globe-scale-note>
          Heights on the globe are drawn on the site's shared logarithmic ruler, so the whole
          catalogue fits in one frame: geostationary altitude is 6.6 Earth radii from the centre
          and draws at about 2.3. Distance between a satellite and the ship cannot be judged by
          eye here. The footprints, the coastlines, the track and every number on this page are
          on the real geometry and are unaffected.
        </p>` : ""}
      ${this.boundaryToggleMarkup()}`;
    host.querySelectorAll<HTMLButtonElement>("[data-view-mode]").forEach((button) => {
      button.addEventListener("click", () => {
        const mode = button.dataset.viewMode as ViewMode;
        if (mode === this.viewMode) return;
        this.viewMode = mode;
        this.teardownViews();
        this.renderViewBar();
        this.renderView();
      });
    });
    host.querySelector<HTMLInputElement>("[data-only-visible]")?.addEventListener("change", (event) => {
      this.showOnlyVisible = (event.target as HTMLInputElement).checked;
      this.renderView();
    });
    host.querySelector<HTMLInputElement>("[data-show-footprints]")?.addEventListener("change", (event) => {
      this.showFootprints = (event.target as HTMLInputElement).checked;
      this.renderView();
    });
    host.querySelectorAll<HTMLButtonElement>("[data-boundary]").forEach((button) => {
      button.addEventListener("click", () => {
        const id = button.dataset.boundary!;
        if (this.activeBoundaryIds.has(id)) this.activeBoundaryIds.delete(id);
        else this.activeBoundaryIds.add(id);
        this.renderViewBar();
        this.renderView();
      });
    });
  }

  /**
   * Boundaries the reader has switched on, converted for the map.
   *
   * Edge definiteness travels with the shape: a fleet area whose northern limit
   * is published as "the Kuril Islands" is drawn open on that side, because the
   * source named a landmark and not a line.
   */
  private activeBoundaries() {
    return AOR_BOUNDARIES
      .filter((boundary) => this.activeBoundaryIds.has(boundary.id))
      .map((boundary) => ({
        id: boundary.id,
        label: boundary.name,
        colorHex: boundary.kind === "numbered-fleet" ? "#a98cff" : "#76e6a5",
        rings: boundary.rings,
        labelAt: boundary.labelAt,
        indefiniteEdges: boundary.edges
          ? Object.entries(boundary.edges)
            .filter(([, edge]) => edge.kind === "indefinite")
            .map(([side]) => side)
          : [],
      }));
  }

  /**
   * Areas of responsibility: OUT of the fold they were hiding in.
   *
   * Sean asked for fleet and COCOM overlays and then could not find them: they
   * were five chips inside a shut `<details>` inside the view bar, off by
   * default. The chips are now a labelled row on the view bar itself, so the
   * overlay is one click and the reader can see that it exists. The citation
   * apparatus — statement, source, per-edge definiteness, caveat — stays folded
   * underneath, because that is reference and this is a control.
   *
   * The 7th Fleet area was also DRAWN WRONG until 2026-08-19, and wrong in the
   * worst possible direction: its published eastern limit is the International
   * Date Line, the +180 vertex projected onto the western edge of the sheet
   * (see `projectionLongitudeDeg` in transit-map.ts), and the box turned inside
   * out — 7th Fleet shaded over the Atlantic. A wrong AOR on a Navy tool is
   * worse than no AOR, so `tests/transit-boundaries.test.ts` now pins the drawn
   * extent of every area, not only its citation.
   */
  private boundaryToggleMarkup(): string {
    if (AOR_BOUNDARIES.length === 0) return "";
    return `
      <div class="transit-boundary-picker">
        <span class="transit-boundary-label">${term("Areas of responsibility",
          "Combatant-command areas are drawn as the countries the command publicly assigns "
          + "to it. Numbered-fleet areas are published as prose, so each edge is marked: a "
          + "dashed, faded outline is an area with at least one limit the source named as a "
          + "landmark or an approximation rather than a line. Nothing here is drawn from "
          + "memory; every area carries the sentence that published it.")}</span>
        <div class="transit-chips">
          ${AOR_BOUNDARIES.map((boundary) => `
            <button class="transit-chip ${this.activeBoundaryIds.has(boundary.id) ? "is-active" : ""}"
                    data-boundary="${boundary.id}"
                    title="${escapeHtml(boundary.name)}">${escapeHtml(boundaryChipLabel(boundary))}</button>`).join("")}
        </div>
      </div>
      <details class="transit-boundary-cites" ${this.activeBoundaryIds.size > 0 ? "open" : ""}>
        <summary>Where each area comes from</summary>
        ${[...this.activeBoundaryIds]
          .map((id) => AOR_BOUNDARIES.find((boundary) => boundary.id === id))
          .filter((boundary): boundary is AorBoundary => Boolean(boundary))
          .map((boundary) => `
            <div class="transit-boundary-cite">
              <blockquote>${escapeHtml(boundary.statement)}</blockquote>
              <p>
                <a href="${escapeHtml(boundary.source)}" target="_blank" rel="noreferrer">${escapeHtml(boundary.sourceName)}</a>,
                ${boundary.year}${boundary.archiveSource ? ` · <a href="${escapeHtml(boundary.archiveSource)}" target="_blank" rel="noreferrer">archived capture</a>` : ""}
              </p>
              ${boundary.geometrySource ? `
                <p class="transit-boundary-geometry">
                  <strong>The command published this geometry itself.</strong>
                  Not assembled here from a country list —
                  <a href="${escapeHtml(boundary.geometrySource)}" target="_blank" rel="noreferrer">the map data file</a>
                  is served from the command's own host.
                </p>` : ""}
              ${boundary.edges ? `<ul>${Object.entries(boundary.edges).map(([side, edge]) =>
                `<li><strong>${escapeHtml(side)}</strong> — ${
                  edge.kind === "indefinite" ? "<em>indefinite.</em> "
                  : edge.kind === "published-numeric" ? "<span class=\"transit-edge-numeric\">published as a coordinate.</span> "
                  : ""}${escapeHtml(edge.note)}</li>`).join("")}</ul>` : ""}
              ${boundary.caveat ? `<p class="transit-boundary-caveat">${escapeHtml(boundary.caveat)}</p>` : ""}
            </div>`).join("")}
        ${this.activeBoundaryIds.size === 0
          ? `<p class="transit-hint transit-hint-tight">Switch an area on to read the sentence that published it.</p>`
          : ""}
      </details>`;
  }

  private teardownViews() {
    this.globe?.destroy();
    this.globe = null;
    this.map?.destroy();
    this.map = null;
    if (this.viewHost) this.viewHost.replaceChildren();
  }

  private renderView() {
    if (!this.viewHost) return;
    const markers = this.markersAt(this.trackTimeMs);
    const current = positionAt(this.route, this.trackTimeMs);

    if (this.viewMode === "globe") {
      if (!this.globe) {
        this.map?.destroy();
        this.map = null;
        this.globe = new TransitGlobe({ container: this.viewHost, land: this.land });
      }
      this.globe.render({
        route: this.route,
        selectedWaypointId: this.selectedWaypointId,
        currentPosition: current,
        satellites: markers.map((marker) => ({
          id: marker.id,
          name: marker.name,
          latitudeDeg: marker.latitudeDeg,
          longitudeDeg: marker.longitudeDeg,
          altitudeKm: marker.altitudeKm,
          colorHex: marker.visible ? 0xffd479 : 0x7fa6b6,
          visible: marker.visible,
        })),
        showOnlyVisible: this.showOnlyVisible,
        showFootprints: this.showFootprints,
        maskDeg: this.maskDeg,
      });
      return;
    }

    if (!this.map) {
      this.globe?.destroy();
      this.globe = null;
      this.map = new TransitMap({
        container: this.viewHost,
        land: this.land,
        onMapClick: (latitude, longitude) => this.addWaypointAtEnd(latitude, longitude),
        onWaypointClick: (id) => this.selectWaypoint(id),
        onWaypointDrag: (id, latitude, longitude) => {
          this.updateWaypoint(id, { latitudeDeg: latitude, longitudeDeg: longitude }, false);
          this.renderView();
        },
      });
    }
    this.map.render({
      route: this.route,
      selectedWaypointId: this.selectedWaypointId,
      currentPosition: current,
      satellites: markers,
      footprints: this.showFootprints
        ? markers.filter((marker) => marker.visible).map((marker) => ({
          id: marker.id,
          colorHex: marker.colorHex,
          points: footprintPoints(marker.latitudeDeg, marker.longitudeDeg, marker.altitudeKm, this.maskDeg, 96),
        }))
        : [],
      boundaries: this.activeBoundaries(),
      showOnlyVisible: this.showOnlyVisible,
    });
  }

  private renderScrub() {
    const host = this.container.querySelector<HTMLElement>("[data-transit-scrub]");
    if (!host) return;
    const span = routeSpanMs(this.route);
    if (!span) {
      host.innerHTML = `<p class="transit-hint">Add a second waypoint with a later time to scrub the transit.</p>`;
      return;
    }
    const current = positionAt(this.route, this.trackTimeMs);
    const longitude = current?.longitudeDeg ?? 0;
    host.innerHTML = `
      <input type="range" min="${span.startMs}" max="${span.endMs}" step="60000"
             value="${Math.min(span.endMs, Math.max(span.startMs, this.trackTimeMs))}"
             data-time-scrub aria-label="Time along the transit">
      <div class="transit-scrub-readout">
        <strong>${formatTime(this.trackTimeMs, this.timeConvention, longitude)}</strong>
        ${current ? `· ${formatLatitude(current.latitudeDeg)} ${formatLongitude(current.longitudeDeg)}` : ""}
        · ${formatDuration(this.trackTimeMs - span.startMs)} into a ${formatDuration(span.endMs - span.startMs)} transit
      </div>`;
    host.querySelector<HTMLInputElement>("[data-time-scrub]")?.addEventListener("input", (event) => {
      this.trackTimeMs = Number((event.target as HTMLInputElement).value);
      this.selectedWaypointId = null;
      this.renderView();
      this.renderScrub();
      this.renderAnswers();
    });
  }

  // -------------------------------------------------------------------------
  // The answers panel — Sean's dimming interaction lives here
  // -------------------------------------------------------------------------

  private renderAnswers() {
    const host = this.container.querySelector<HTMLElement>("[data-transit-answers]");
    if (!host) return;

    if (this.solve.status !== "done") {
      host.innerHTML = `
        <div class="transit-block">
          <h3>Coverage over the transit</h3>
          <p class="transit-hint">${escapeHtml(this.solve.message)} Press <em>Compute visibility windows</em> to solve the route.</p>
        </div>`;
      return;
    }

    const span = this.solve.solvedAtSpan!;
    const coverage = this.coverage().sort((a, b) => {
      const order = { "entire-transit": 0, partial: 1, none: 2, "not-computed": 3 } as const;
      if (order[a.verdict] !== order[b.verdict]) return order[a.verdict] - order[b.verdict];
      return b.summary.coveredFraction - a.summary.coveredFraction;
    });

    const focusTimeMs = this.selectedWaypointId
      ? this.route.waypoints.find((waypoint) => waypoint.id === this.selectedWaypointId)?.timeMs ?? null
      : null;
    const overheadNow = focusTimeMs === null
      ? null
      : new Set(coverage
        .filter((entry) => satellitesOverheadAt(
          this.resolved.find((candidate) => candidate.system.systemId === entry.systemId)!,
          this.solve.windowsBySatellite,
          focusTimeMs,
        ).length > 0)
        .map((entry) => entry.systemId));

    const focusLabel = focusTimeMs === null
      ? ""
      : (() => {
        const waypoint = this.route.waypoints.find((candidate) => candidate.id === this.selectedWaypointId)!;
        const index = this.route.waypoints.indexOf(waypoint) + 1;
        return `
          <p class="transit-focus-note">
            Dimmed rows are the systems with nothing overhead at
            <strong>waypoint ${index}, ${escapeHtml(waypoint.label)}</strong>
            (${formatTime(waypoint.timeMs, this.timeConvention, waypoint.longitudeDeg)}).
            They are still listed, because "this system cannot help you here" is the answer.
            <button class="transit-link-button" data-clear-focus>Show the whole transit again</button>
          </p>`;
      })();

    host.innerHTML = `
      <div class="transit-block">
        <h3>Coverage over the transit</h3>
        <p class="transit-consequence">
          <strong>${this.solve.maskDeg}° mask</strong> over ${formatDuration(span.endMs - span.startMs)} ·
          ${this.solve.evaluations.toLocaleString()} propagations in ${(this.solve.elapsedMs / 1000).toFixed(1)} s ·
          ${term("Entire transit",
            "Some spacecraft of that system was above the mask at every instant — a union "
            + "across the constellation, not one satellite doing all the work.")}
        </p>
        ${this.elementAgeBannerMarkup()}
        ${focusLabel}
        <ul class="transit-coverage" data-coverage-list>
          ${coverage.map((entry) => this.coverageRowMarkup(entry, overheadNow, focusTimeMs)).join("")}
        </ul>
        ${coverage.length === 0 ? `<p class="transit-hint">No system in the capability table matches that need.</p>` : ""}
      </div>
      ${this.unsourcedMarkup()}`;

    host.querySelector<HTMLButtonElement>("[data-clear-focus]")?.addEventListener("click", () => {
      this.selectedWaypointId = null;
      this.renderAll();
    });
    host.querySelectorAll<HTMLElement>("[data-coverage-system]").forEach((row) => {
      row.addEventListener("toggle", () => undefined);
    });
  }

  private coverageRowMarkup(
    entry: SystemCoverage,
    overheadNow: Set<string> | null,
    focusTimeMs: number | null,
  ): string {
    const dimmed = overheadNow !== null && !overheadNow.has(entry.systemId);
    const verdictLabel = {
      "entire-transit": "Entire transit",
      partial: `${(entry.summary.coveredFraction * 100).toFixed(1)}% of the transit`,
      none: "Never above your mask",
      "not-computed": "Not solved",
    }[entry.verdict];
    const overheadCount = focusTimeMs === null
      ? null
      : satellitesOverheadAt(
        this.resolved.find((candidate) => candidate.system.systemId === entry.systemId)!,
        this.solve.windowsBySatellite,
        focusTimeMs,
      ).length;

    return `
      <li class="transit-coverage-row is-${entry.verdict} ${dimmed ? "is-dimmed" : ""}" data-coverage-system="${entry.systemId}">
        <details>
          <summary>
            <span class="transit-coverage-name">${escapeHtml(entry.system.name)}${entry.system.abbreviation ? ` (${escapeHtml(entry.system.abbreviation)})` : ""}</span>
            <span class="transit-coverage-verdict">${verdictLabel}</span>
            ${this.ageChipMarkup(entry.solvedSatelliteIds)}
            ${overheadCount !== null ? `<span class="transit-coverage-overhead">${overheadCount} overhead here</span>` : ""}
          </summary>
          <div class="transit-coverage-detail">
            <p>${escapeHtml(entry.system.summary)}</p>
            <dl>
              <dt>Operator</dt><dd>${escapeHtml(entry.system.operator)}</dd>
              <dt>Orbit</dt><dd>${escapeHtml(entry.system.orbitNote)}</dd>
              <dt>Spacecraft in this catalog</dt>
              <dd>${entry.solvedSatelliteIds.length}${entry.unsolvedSatelliteIds.length > 0 ? ` (${entry.unsolvedSatelliteIds.length} not solved)` : ""}</dd>
              ${entry.summary.gaps.length > 0 ? `
                <dt>Longest gap</dt><dd>${formatDuration(entry.summary.longestGapMs)} — ${entry.summary.gaps.length} gap${entry.summary.gaps.length === 1 ? "" : "s"}</dd>` : ""}
            </dl>
            ${entry.summary.gaps.length > 0 ? `
              <p class="transit-gaps">Gaps: ${entry.summary.gaps.slice(0, 6).map((gap) =>
                `${formatTime(gap.startMs, this.timeConvention, 0, false)}–${formatTime(gap.endMs, this.timeConvention, 0, false)}`,
              ).join(", ")}${entry.summary.gaps.length > 6 ? ` and ${entry.summary.gaps.length - 6} more` : ""}</p>` : ""}
            <ul class="transit-citations">
              ${entry.system.services.map((service) => `
                <li>
                  <span class="transit-service-band">${escapeHtml(this.needLabel(service.needId))}</span>
                  <q>${escapeHtml(service.statement)}</q>
                  — <a href="${escapeHtml(service.source)}" target="_blank" rel="noreferrer">${escapeHtml(service.sourceName)}</a>
                  ${service.archiveSource ? ` · <a href="${escapeHtml(service.archiveSource)}" target="_blank" rel="noreferrer">archived capture</a>` : ""}
                  <span class="transit-source-kind">${sourceKindLabel(service.sourceKind)}</span>
                </li>`).join("")}
            </ul>
            ${entry.system.supersededNote ? `<p class="transit-superseded"><strong>The current official page no longer says this.</strong> ${escapeHtml(entry.system.supersededNote)}</p>` : ""}
            ${entry.system.caveat ? `<p class="transit-caveat">${escapeHtml(entry.system.caveat)}</p>` : ""}
          </div>
        </details>
      </li>`;
  }

  /**
   * Element age, made unmissable rather than merely present.
   *
   * A window computed from two-week-old elements and one computed from
   * yesterday's look identical in a table of times, and they are not remotely
   * the same claim. This banner reports the worst case across the answer,
   * because the worst case is what decides how far to trust the weakest row.
   */
  private elementAgeBannerMarkup(): string {
    const ages = [...this.ageBySatellite.values()].filter((entry) => Number.isFinite(entry.days));
    if (ages.length === 0) return "";
    const worst = ages.reduce((a, b) => (Math.abs(b.days) > Math.abs(a.days) ? b : a));
    const best = ages.reduce((a, b) => (Math.abs(b.days) < Math.abs(a.days) ? b : a));
    const counts = new Map<ElementAgeBand, number>();
    for (const entry of ages) counts.set(entry.band, (counts.get(entry.band) ?? 0) + 1);
    const stale = (counts.get("stale") ?? 0) + (counts.get("beyond-bound") ?? 0);
    return `
      <div class="transit-age-banner is-${worst.band}">
        <strong>Elements ${best.days.toFixed(1)}–${worst.days.toFixed(1)} days old at the end of this transit.</strong>
        ${stale > 0
          ? `${stale} of ${ages.length} spacecraft are propagated from elements more than a week old — the weakest claims here.`
          : "Recent elements: as good as this method gets."}
        ${term("Why age is the only handle",
          "SGP4 cannot see a manoeuvre made after the epoch, and nothing in a published "
          + "element set reports its own uncertainty. Age is therefore the only measure "
          + "you have of how far to trust a window.")}
      </div>`;
  }

  private ageChipMarkup(satelliteIds: readonly number[]): string {
    const ages = satelliteIds
      .map((id) => this.ageBySatellite.get(id))
      .filter((entry): entry is { days: number; band: ElementAgeBand; epoch: string } =>
        Boolean(entry) && Number.isFinite(entry!.days));
    if (ages.length === 0) return "";
    const worst = ages.reduce((a, b) => (Math.abs(b.days) > Math.abs(a.days) ? b : a));
    return `<span class="transit-age-chip is-${worst.band}" title="Oldest elements in this system: epoch ${escapeHtml(worst.epoch)}">elements ${worst.days.toFixed(1)} d old</span>`;
  }

  private needLabel(needId: string): string {
    return satcomCapabilities.needs.find((need) => need.needId === needId)?.label ?? needId;
  }

  private unsourcedMarkup(): string {
    if (satcomCapabilities.unsourced.length === 0) return "";
    return `
      <div class="transit-block">
        <h3>${term("Deliberately absent",
          "Systems a planner might expect to find here, and why they are not. An empty row "
          + "is a statement about the public record, not about the system.")}</h3>
        <ul class="transit-absent">
          ${satcomCapabilities.unsourced.map((item) => `
            <li><strong>${escapeHtml(item.name)}</strong> — ${escapeHtml(item.reason)}</li>`).join("")}
        </ul>
      </div>`;
  }

  private renderReference() {
    const host = this.container.querySelector<HTMLElement>("[data-transit-reference]");
    if (!host) return;
    const overlay = aorReference.boundaryOverlay;
    host.innerHTML = `
      <details class="transit-block transit-reference-fold">
        <summary>Fleet and combatant-command areas: how they are sourced, and what is not drawn</summary>
        <div class="transit-reference-body">
          <p class="transit-lead">${escapeHtml(overlay.headline)}</p>
          <ul class="transit-reasons">
            ${overlay.howItIsBuilt.map((reason) => `<li>${escapeHtml(reason)}</li>`).join("")}
          </ul>
          <p class="transit-hint"><strong>Not drawn:</strong> ${escapeHtml(overlay.whatIsNotDrawn)}</p>
          <details>
            <summary>The published wording, quoted</summary>
            <div class="transit-aor">
              <h4>Combatant commands</h4>
              ${aorReference.combatantCommands.map(aorMarkup).join("")}
              <h4>Numbered fleets</h4>
              ${aorReference.numberedFleets.map(aorMarkup).join("")}
            </div>
          </details>
        </div>
      </details>`;
  }

  // -------------------------------------------------------------------------
  // Route editing
  // -------------------------------------------------------------------------

  private selectWaypoint(id: string) {
    this.selectedWaypointId = this.selectedWaypointId === id ? null : id;
    const waypoint = this.route.waypoints.find((candidate) => candidate.id === this.selectedWaypointId);
    if (waypoint) this.trackTimeMs = waypoint.timeMs;
    this.renderAll();
  }

  private addWaypointAtEnd(latitudeDeg: number, longitudeDeg: number) {
    const last = this.route.waypoints.at(-1);
    this.addWaypoint(
      latitudeDeg,
      longitudeDeg,
      last ? last.timeMs + 24 * 3_600_000 : Date.now(),
    );
  }

  private addWaypoint(latitudeDeg: number, longitudeDeg: number, timeMs: number) {
    this.activePresetId = null;
    this.route = {
      ...this.route,
      waypoints: [...this.route.waypoints, {
        id: nextWaypointId(),
        label: `Waypoint ${this.route.waypoints.length + 1}`,
        latitudeDeg,
        longitudeDeg,
        timeMs,
      }],
    };
    this.invalidateSolve();
    this.renderAll();
  }

  private removeWaypoint(id: string) {
    if (this.route.waypoints.length <= 2) return;
    this.activePresetId = null;
    this.route = { ...this.route, waypoints: this.route.waypoints.filter((waypoint) => waypoint.id !== id) };
    if (this.selectedWaypointId === id) this.selectedWaypointId = null;
    this.invalidateSolve();
    this.renderAll();
  }

  private updateWaypoint(id: string, patch: Partial<Waypoint>, rerender = true) {
    this.activePresetId = null;
    this.route = {
      ...this.route,
      waypoints: this.route.waypoints.map((waypoint) =>
        waypoint.id === id ? { ...waypoint, ...patch } : waypoint),
    };
    this.invalidateSolve();
    if (rerender) this.renderAll();
  }

  /**
   * A solve describes one route at one mask. Changing either makes the displayed
   * answer stale, and a stale answer that still looks authoritative is the worst
   * thing this panel could show.
   */
  private invalidateSolve() {
    if (this.solve.status === "done") {
      this.solve = {
        ...this.solve,
        status: "idle",
        message: "The route changed. Solve again.",
        windowsBySatellite: new Map(),
        results: [],
        solvedAtSpan: null,
      };
    }
    const span = routeSpanMs(this.route);
    if (span) this.trackTimeMs = Math.min(span.endMs, Math.max(span.startMs, this.trackTimeMs));
  }

  destroy() {
    this.worker?.terminate();
    this.worker = null;
    this.teardownViews();
    this.container.replaceChildren();
  }
}

function aorMarkup(entry: { name: string; statement: string; source: string; sourceName: string; archiveSource: string | null; drawabilityNote: string }): string {
  return `
    <div class="transit-aor-entry">
      <h5>${escapeHtml(entry.name)}</h5>
      <blockquote>${escapeHtml(entry.statement)}</blockquote>
      <p class="transit-aor-source">
        <a href="${escapeHtml(entry.source)}" target="_blank" rel="noreferrer">${escapeHtml(entry.sourceName)}</a>
        ${entry.archiveSource ? ` · <a href="${escapeHtml(entry.archiveSource)}" target="_blank" rel="noreferrer">archived capture</a>` : ""}
      </p>
      <p class="transit-aor-note">${escapeHtml(entry.drawabilityNote)}</p>
    </div>`;
}

/**
 * A chip label short enough to be a chip.
 *
 * The generated dataset carries the command's full published name, which is the
 * right thing to carry and the wrong thing to print on a button: "U.S. Naval
 * Forces Europe-Africa / 6th Fleet" is a paragraph in a chip row. The full name
 * is on the button's title and in the citation block, so nothing is lost.
 * `tests/transit-boundaries.test.ts` fails if a new area has no short label,
 * rather than letting one silently fall back to its full name.
 */
const BOUNDARY_CHIP_LABELS: Record<string, string> = {
  usafricom: "AFRICOM",
  useucom: "EUCOM",
  c5f: "5th Fleet",
  c6f: "6th Fleet",
  c7f: "7th Fleet",
};

export function boundaryChipLabel(boundary: Pick<AorBoundary, "id" | "name">): string {
  return BOUNDARY_CHIP_LABELS[boundary.id] ?? boundary.name;
}

export const BOUNDARY_CHIP_LABEL_IDS = Object.keys(BOUNDARY_CHIP_LABELS);

function sourceKindLabel(kind: string): string {
  return {
    "us-government": "U.S. Government source",
    "allied-government": "Allied government source",
    operator: "Operator's own statement",
    "prime-contractor": "Prime contractor's statement",
  }[kind] ?? kind;
}

/**
 * A term that carries its own definition, instead of a paragraph that explains it.
 *
 * Sean's ruling on this page: "If the text is important, some of it needs to be
 * in popups for definitions, or in places we can collapse." So a definition sits
 * ON the word it defines, opens on hover or keyboard focus, and costs nothing at
 * rest. No new type treatment: the card is BODY inside a surface, and the term
 * itself keeps the type of whatever it is embedded in.
 *
 * The definition text is inside the element rather than in a `title`, so it is
 * reachable by keyboard and readable by a screen reader, which a tooltip is not.
 */
function term(label: string, definition: string): string {
  return `<span class="transit-term" tabindex="0"
    ><span class="transit-term-word">${escapeHtml(label)}</span
    ><span class="transit-term-card" role="note">${escapeHtml(definition)}</span></span>`;
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function mountTransitPlanner(options: TransitPlannerOptions): TransitPlanner {
  return new TransitPlanner(options);
}
