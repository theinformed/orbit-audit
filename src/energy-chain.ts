/**
 * "Follow the energy" — the coupled chain, as data rather than as prose.
 *
 * The complaint this answers is the oldest one on the project: the site has
 * nine rigorous layers and no connective tissue. A visitor can switch on six
 * things and see six unrelated things in the same space. What is missing is
 * not science — every link below is already published — it is the statement
 * that they are one system, with the live number at each link and one sentence
 * saying what that link does to the next one.
 *
 * This module is the whole decision layer and it touches no DOM. It takes the
 * published artifacts and a selected UTC instant, and returns the nine links —
 * seven in the chain and a two-step photon branch that is not in it — with
 * their live readings, their honesty class, one sentence naming what is
 * actually drawn on the globe, their handoff sentence and their limits.
 * `energy-chain-view.ts` draws it and drives the globe; the
 * split is the one `storm-indices.ts` / `storm-panel.ts` already use, and it
 * exists so the tests can reach the real path rather than a copy of it.
 *
 * Three rules govern everything here, and they are the reason the site is
 * trusted:
 *
 * **No arrow is invented.** Every reading below is a field the pipeline
 * publishes. Where a link in the chain has no published field, or no layer in
 * this build draws it, the link says so in `missing` and shows nothing rather
 * than illustrating it.
 *
 * **Every reading carries its own evidence class.** A measured Bz and a
 * model-derived ring-current energy do not acquire a common class by sitting
 * in the same card.
 *
 * **It has to teach when nothing is happening.** Every sentence that reads a
 * live number is written against both states — southward and northward,
 * compressed and nominal, flaring and quiet — because in a week the numbers
 * will be dull and the physics will be identical.
 */

import type { AuroraBundle } from "./aurora-time";
import { DRAP_LIVE_EDGE_HOLD_MINUTES, drapCondition, selectDrapFrame } from "./drap";
import type { DrapBundle } from "./drap";
import { clockAngleDeg, newellBand, newellCoupling, ringCurrentNarrative, sampleDriverAt, sampleAt, stormNarrativeAt } from "./storm-indices";
import type { StormDriverSample } from "./storm-indices";
import type { SpaceWeatherBundle } from "./types";

/**
 * The site's honesty vocabulary. Declared locally because every content module
 * here does the same — there is no shared export — and because keeping the
 * copy honest is a one-line review rather than a dependency.
 */
export type EvidenceClass = "observed" | "assimilated" | "empirical" | "model" | "forecast" | "schematic";

export const EVIDENCE_MEANING: Record<EvidenceClass, string> = {
  observed: "Measured by an instrument and published as measured.",
  assimilated: "Measurements combined with a model, so the field is filled in between the observations.",
  empirical: "A formula fitted to past observations, driven by present ones.",
  model: "Simulation output. No measurement fixes any individual value shown here.",
  forecast: "A model run forward past the last observation.",
  schematic: "Drawn to explain a shape, not to report a value.",
};

export type ChainLinkId =
  | "driver"
  | "boundary"
  | "cusp"
  | "ring"
  | "belts"
  | "aurora"
  | "ground"
  | "xray"
  | "dregion";

/**
 * Checkbox ids in `index.html`, by the layer key `main.ts` uses internally.
 *
 * This is the whole integration surface with the running explorer. Setting the
 * box and dispatching `change` is the supported way in — `main.ts` only calls
 * `globe.setLayer` from that listener — and an id that is not in the document
 * is reported to the reader rather than skipped, because a layer that quietly
 * fails to appear is exactly the kind of silence this site exists to avoid.
 */
export const CHAIN_LAYER_CHECKBOX: Record<string, string> = {
  thermosphere: "layer-thermosphere",
  tec: "layer-tec",
  aurora: "layer-aurora",
  ringCurrent: "layer-ring-current",
  magnetosphere: "annotate-empirical-boundaries",
  // The polar-cusp annotation, which since 2026-08-27 is what draws the amber
  // funnels at all. Link 03 is "the gap in the shield" and its whole subject is
  // that funnel, so it has to ask for the tick as well as for the boundary --
  // before this, that step switched on the empirical surfaces and pointed at a
  // fold the reader had not asked to see and therefore could not see.
  cusps: "annotate-polar-cusps",
  // The plasma field replaced the retired curves-as-a-layer presentation:
  // the bow shock and the sheath are in this layer's colours now. The ring
  // current has no checkbox at all any more: one number is not a layer.
  geospace: "layer-geospace",
  solarWind: "layer-solar-wind",
  photons: "layer-photons",
  radiation: "layer-radiation",
  drap: "layer-drap",
};

/**
 * Every layer this walkthrough is allowed to touch. The order is load-bearing
 * in one place: `magnetosphere` (the empirical boundary annotation) must come
 * AFTER `geospace`, because switching the field layer off cascades the
 * annotation off with it — a step that wants the boundary without the field
 * has to set the boundary after that cascade has run.
 */
export const CHAIN_MANAGED_LAYERS: readonly string[] = [
  "thermosphere",
  "tec",
  "aurora",
  "ringCurrent",
  "geospace",
  "magnetosphere",
  "cusps",
  "solarWind",
  "photons",
  "radiation",
  "drap",
];

/**
 * Where the camera should be for a step, expressed as the site's own controls.
 * `cross-section` is the noon-midnight cut every textbook figure uses;
 * `polar` looks down onto the north pole with noon at the top, which is the
 * only view in which both cusp funnels and the oval share one frame.
 */
export type ChainCamera = "sun-earth" | "reset" | "layer-framed" | "cross-section" | "polar";

export interface ChainReading {
  label: string;
  /** Already formatted, including units. "—" is never emitted; the reading is omitted instead. */
  value: string;
  evidence: EvidenceClass;
  /**
   * What kind of answer this is, which decides how it is set.
   *
   * A "measure" is a number that changes and is drawn in the site's readout
   * face — monospace, tabular, large. A "name" is a word: "magnetopause
   * current sheet", "inside the published window". Both were set in the
   * readout face until 2026-08-19, and a phrase in tabular monospace at 14 px
   * reads as a measured quantity that has lost its units. Naming the two
   * kinds here rather than sniffing the string keeps the decision with the
   * person who knows which it is.
   */
  kind?: "measure" | "name";
  /** Observation or validity time for this one number, ISO, when the artifact carries one. */
  at?: string;
  note?: string;
}

/**
 * A number drawn on its own axis rather than only printed.
 *
 * The brief this answers: "carry the real numbers for the current conditions,
 * drawn where possible rather than only printed". A standoff of 9.6 R⊕ means
 * nothing to a reader who does not already carry 6.6 and 10-11 in their head;
 * put all three on one axis and the sentence is unnecessary. Every value on
 * the scale is a number the card already prints, so nothing is invented to
 * fill it — the axis is a second presentation of the same readings, and it
 * carries its own evidence class for exactly that reason.
 */
export interface ChainScale {
  label: string;
  unit: string;
  evidence: EvidenceClass;
  /** Axis range, in the scale's own unit. */
  from: number;
  to: number;
  /** The live value, and what it is. Null when there is none for this instant. */
  live: { at: number; label: string } | null;
  /** Fixed reference positions the live value is read against. */
  marks: readonly { at: number; label: string }[];
  /** A shaded range, such as the nominal quiet standoff. */
  band: { from: number; to: number; label: string } | null;
}

export interface ChainSeriesPoint {
  t: number;
  value: number | null;
}

export interface ChainSeries {
  label: string;
  unit: string;
  evidence: EvidenceClass;
  points: ChainSeriesPoint[];
  /** Longest spacing that may be joined by a line. Gaps stay gaps. */
  maximumGapMs: number;
  markZero?: boolean;
  /** Shade the part of the trace below zero — used for southward Bz. */
  shadeNegative?: boolean;
  logScale?: boolean;
}

export interface ChainLink {
  id: ChainLinkId;
  /** "01".."07" for the chain; "X1"/"X2" for the branch that is not part of it. */
  index: string;
  /**
   * False for the photon branch. The rail used to number the branch "8 of 8"
   * while its own card said "not part of the chain", which is a contradiction
   * a reader cannot resolve. The progress counter now counts only the links
   * this flag is true for.
   */
  partOfChain: boolean;
  /** Two or three words. What this link *is* in the machine. */
  role: string;
  title: string;
  /** Evidence class of the weakest thing this step shows, not the strongest. */
  evidence: EvidenceClass;
  badge: string;
  /** One or two sentences: what this link does. */
  what: string;
  /**
   * One sentence naming what is actually drawn on the globe for this step,
   * and what is not.
   *
   * Sean's complaint was that each step has to "show what it intends to
   * show". Half the failures were not the picture but the absence of a
   * caption: the ring-current step drives the PLASMASPHERE, because one
   * number has no map, and a reader who is not told that is looking at a
   * cloud and calling it the ring current. This is the sentence that closes
   * that gap on every step, including the steps where the honest answer is
   * "nothing new is drawn".
   */
  onTheGlobe: string;
  /**
   * The handoff. One or two plain sentences saying what this link does to the
   * next one, written against the live number so it changes with conditions.
   * Null on the last link of the chain and on the branch.
   */
  handoff: string | null;
  /** What this step cannot tell you. Never empty. */
  limit: string;
  readings: ChainReading[];
  series: ChainSeries | null;
  /** The step's one number on an axis, when it has one worth drawing. */
  scale: ChainScale | null;
  /**
   * Set when a field or a layer this step needs is not published in this
   * build. The card shows this instead of drawing anything.
   */
  missing: string | null;
  /**
   * Set when the numbers on this card are a current snapshot and the reader
   * has moved the timeline away from it.
   *
   * Several links publish a history for the *layer* but only the newest sample
   * for the *number* — OVATION, GloTEC and the GOES X-ray flux all do. Leaving
   * a live value under a past timestamp would be the site's worst habit, so
   * the card says which of the two it is looking at.
   */
  timeNote: string | null;
  camera: ChainCamera;
  /** Layer keys to switch on for this step. Everything managed and not listed goes off. */
  layersOn: readonly string[];
  /** Layers whose absence is expected and worth saying out loud. */
  layersNotBuilt: readonly { label: string; because: string }[];
  sources: readonly { label: string; url: string }[];
}

export interface ChainCoverage {
  /** From the release manifest, so no large bundle has to be fetched to know. */
  geospace?: { validFrom: string; validTo: string; frameCount: number } | null;
  aurora?: { validFrom: string; validTo: string; frameCount: number } | null;
  drap?: { validFrom: string; validTo: string; frameCount: number } | null;
}

export interface ChainInputs {
  weather: SpaceWeatherBundle | null;
  /** Optional and fetched only when the reader reaches the X-ray branch. */
  drap?: DrapBundle | null;
  /** Only ever supplied by a test; the walkthrough never downloads 1.2 MB for a headline. */
  aurora?: AuroraBundle | null;
  /**
   * True when this build has a control that actually draws the cusped
   * boundaries. The magnetopause layer on the globe today is the Shue surface,
   * which has no cusps by construction, so the cusp step has to say which of
   * the two the reader is looking at. The view discovers this from the page
   * rather than assuming it, so the step lights up on its own the day a cusp
   * control ships.
   */
  cuspLayerDrawn?: boolean;
  coverage?: ChainCoverage;
  at: Date;
}

// ---------------------------------------------------------------------------
// Formatting
// ---------------------------------------------------------------------------

const NOMINAL_STANDOFF_RE = 10.5;
const GEOSTATIONARY_RE = 6.6;

export function utcLabel(iso: string | null | undefined): string {
  if (!iso) return "an unknown time";
  const time = new Date(iso);
  if (Number.isNaN(time.getTime())) return "an unknown time";
  return `${time.toISOString().slice(0, 16).replace("T", " ")} UTC`;
}

function fixed(value: number | null | undefined, digits: number, unit: string): string | null {
  if (value === null || value === undefined || !Number.isFinite(value)) return null;
  return `${value.toFixed(digits)} ${unit}`.trim();
}

function group(value: number): string {
  return Math.round(value).toLocaleString("en-US");
}

function minutesBetween(from: string | null | undefined, to: string | null | undefined): number | null {
  if (!from || !to) return null;
  const a = new Date(from).getTime();
  const b = new Date(to).getTime();
  if (!Number.isFinite(a) || !Number.isFinite(b)) return null;
  return (b - a) / 60000;
}

/**
 * The NOAA R scale, from the GOES 0.1-0.8 nm flux.
 *
 * NOAA's published thresholds, not a fit: R1 at M1 (1e-5), R2 at M5 (5e-5),
 * R3 at X1 (1e-4), R4 at X10 (1e-3), R5 at X20 (2e-3) W/m^2 in the 0.1-0.8 nm
 * channel. Returned as a level so the branch card can say "no blackout"
 * honestly when the Sun is quiet, which is most of the time.
 */
export function radioBlackoutLevel(fluxWm2: number | null | undefined): { level: number; label: string } {
  if (fluxWm2 === null || fluxWm2 === undefined || !Number.isFinite(fluxWm2) || fluxWm2 < 1e-5) {
    return { level: 0, label: "none" };
  }
  if (fluxWm2 < 5e-5) return { level: 1, label: "minor" };
  if (fluxWm2 < 1e-4) return { level: 2, label: "moderate" };
  if (fluxWm2 < 1e-3) return { level: 3, label: "strong" };
  if (fluxWm2 < 2e-3) return { level: 4, label: "severe" };
  return { level: 5, label: "extreme" };
}

/**
 * How compressed the dayside boundary is, in words, against a nominal 10-11 Re.
 *
 * Written so that both answers are a lesson: a boundary at 10 Re is not a
 * failure of the walkthrough, it is the quiet state the compressed one is
 * measured against.
 */
export function standoffVerdict(standoffRe: number | null): string | null {
  if (standoffRe === null || !Number.isFinite(standoffRe)) return null;
  const insideGeo = standoffRe <= GEOSTATIONARY_RE;
  if (insideGeo) {
    return `The boundary is inside geostationary orbit (6.6 R⊕): spacecraft at GEO are, at this instant, outside Earth's magnetic field for part of their day.`;
  }
  if (standoffRe < 9) {
    return `That is ${(NOMINAL_STANDOFF_RE - standoffRe).toFixed(1)} R⊕ closer than the nominal 10-11 R⊕, and ${(standoffRe - GEOSTATIONARY_RE).toFixed(1)} R⊕ outside geostationary orbit. The obstacle has been pushed in.`;
  }
  if (standoffRe <= 12) {
    return `That is about the nominal 10-11 R⊕. The dayside is not compressed right now — this is the state a storm is measured against.`;
  }
  return `That is further out than the nominal 10-11 R⊕: low dynamic pressure, so the solar wind is barely pushing.`;
}

// ---------------------------------------------------------------------------
// Series extracted from the published artifacts
// ---------------------------------------------------------------------------

/**
 * How far the timeline may drift from a snapshot before the card says so.
 *
 * Ninety minutes, not five: the point of the caution is a reader who has
 * *scrubbed* the timeline, not the ordinary lag between an upstream sample and
 * the publish cycle that carries it. GloTEC's stamp routinely sits half an
 * hour behind the release, and a caution that fired on that would be wallpaper
 * within a minute of opening the walkthrough. The freshness of the bundle
 * itself is already the job of the live chip in the top bar, and every reading
 * carries its own observation time regardless.
 */
const SNAPSHOT_TOLERANCE_MINUTES = 90;

/**
 * The caution for a number that does not follow the timeline, or null when it
 * does not need one.
 */
export function snapshotNote(
  at: Date,
  snapshotIso: string | null | undefined,
  what: string,
  layerBehaviour: string,
): string | null {
  if (!snapshotIso) return null;
  const stamp = new Date(snapshotIso).getTime();
  if (!Number.isFinite(stamp)) return null;
  const driftMinutes = Math.abs(at.getTime() - stamp) / 60000;
  if (driftMinutes <= SNAPSHOT_TOLERANCE_MINUTES) return null;
  return `The timeline is at ${utcLabel(at.toISOString())}, but ${what} publishes only its newest sample in this bundle, taken at ${utcLabel(snapshotIso)}. `
    + `The numbers below are that sample and not the selected time. ${layerBehaviour}`;
}

function driverSeries(weather: SpaceWeatherBundle | null): readonly StormDriverSample[] {
  return weather?.magnetopause?.driverSeries ?? [];
}

function seriesFromDrivers(
  drivers: readonly StormDriverSample[],
  pick: (sample: StormDriverSample) => number | null,
): ChainSeriesPoint[] {
  const points: ChainSeriesPoint[] = [];
  for (const sample of drivers) {
    const t = new Date(sample.validAt).getTime();
    if (!Number.isFinite(t)) continue;
    const value = pick(sample);
    points.push({ t, value: value !== null && Number.isFinite(value) ? value : null });
  }
  return points.sort((a, b) => a.t - b.t);
}

// ---------------------------------------------------------------------------
// The eight links
// ---------------------------------------------------------------------------

/**
 * Plain English for the driver field names the artifact publishes.
 *
 * `cuspedBoundaries.models[].drivers` is a list of the pipeline's own field
 * identifiers — `dynamicPressureNpa`, `clockAngleDeg`. They were being printed
 * straight into a sentence a Navy officer reads, which is how a card came to
 * say "Driven here by dynamicPressureNpa, magneticPressureNpa". An identifier
 * with no entry here falls through unchanged rather than being dropped, so a
 * new driver in a future release is ugly rather than invisible.
 */
const DRIVER_FIELD_NAMES: Record<string, string> = {
  dynamicPressureNpa: "dynamic pressure",
  magneticPressureNpa: "magnetic pressure",
  clockAngleDeg: "IMF clock angle",
  bzGsmNt: "IMF Bz",
  byNt: "IMF By",
  dipoleTiltDeg: "dipole tilt",
  speedKps: "solar-wind speed",
  densityCm3: "proton density",
};

function plainDriverNames(drivers: readonly string[]): string {
  return drivers.map((name) => DRIVER_FIELD_NAMES[name] ?? name).join(", ");
}

/**
 * Build the chain for one instant.
 *
 * Never throws and never returns fewer than nine links: a link with no data
 * still has to be able to say that it has no data, which is the whole point.
 *
 * Seven of them are the chain and two are the photon branch, which is not in
 * it. The branch is two steps rather than one because it makes two separate
 * claims — that light is not deflected, and that where it lands the HF band
 * closes — and one card carrying both ran 871 px past the bottom of the panel,
 * measured at 1440x900 on the shipped build.
 */
export function chainLinks(inputs: ChainInputs): ChainLink[] {
  const { weather, at } = inputs;
  const drivers = driverSeries(weather);
  const storm = weather?.storm ?? null;
  const narrative = stormNarrativeAt(storm, drivers, at);
  const driver = sampleDriverAt(drivers, at, 45);

  return [
    driverLink(weather, drivers, driver, narrative, at),
    boundaryLink(weather, drivers, driver, at),
    cuspLink(weather, driver, inputs.cuspLayerDrawn === true),
    ringLink(weather, narrative, at),
    beltsLink(inputs),
    auroraLink(weather, at),
    groundLink(weather, at),
    xrayLink(inputs),
    dRegionLink(inputs),
  ];
}

/** How many of the links are the chain itself, for "step N of M". */
export function chainLength(links: readonly ChainLink[]): number {
  return links.filter((link) => link.partOfChain).length;
}

type Narrative = ReturnType<typeof stormNarrativeAt>;

function driverLink(
  weather: SpaceWeatherBundle | null,
  drivers: readonly StormDriverSample[],
  driver: StormDriverSample | null,
  narrative: Narrative,
  at: Date,
): ChainLink {
  const readings: ChainReading[] = [];
  const derived = weather?.storm?.derived ?? null;
  let handoff: string | null = null;
  let missing: string | null = null;

  if (!driver) {
    missing = weather
      ? `No propagated solar-wind sample within 45 minutes of ${utcLabel(at.toISOString())}. The published driver series runs to ${utcLabel(drivers.at(-1)?.validAt)}; nothing is drawn for a time it does not cover.`
      : "The space-weather bundle has not loaded, so no driver can be read.";
  } else {
    const southward = driver.bzGsmNt < 0;
    const clock = driver.clockAngleDeg ?? clockAngleDeg(driver.byNt, driver.bzGsmNt);
    const coupling = driver.newellCoupling ?? newellCoupling(driver.speedKps, driver.byNt, driver.bzGsmNt);
    const band = newellBand(coupling, derived?.newellCalibration ?? []);
    const travel = minutesBetween(driver.observedAt, driver.validAt);

    readings.push({
      label: "IMF Bz (GSM)",
      value: `${driver.bzGsmNt.toFixed(2)} nT · ${southward ? "southward" : "northward"}`,
      evidence: "observed",
      at: driver.observedAt,
      note: southward
        ? "Negative is southward. This is the switch, and right now it is on."
        : "Positive is northward. The switch is off: the dayside gate is closed and everything below this link is running down, not building up.",
    });
    const clockText = fixed(clock, 1, "°");
    if (clockText) {
      readings.push({
        label: "IMF clock angle",
        value: clockText,
        evidence: "empirical",
        note: "Measured from northward. Past 90° the interplanetary field has a southward component and can merge with Earth's.",
      });
    }
    const speed = fixed(driver.speedKps, 0, "km/s");
    if (speed) readings.push({ label: "Solar-wind speed", value: speed, evidence: "observed", at: driver.observedAt });
    const density = fixed(driver.densityCm3, 2, "cm⁻³");
    if (density) readings.push({ label: "Proton density", value: density, evidence: "observed", at: driver.observedAt });
    const pressure = fixed(driver.dynamicPressureNpa, 3, "nPa");
    if (pressure) {
      readings.push({
        label: "Dynamic pressure",
        value: pressure,
        evidence: "empirical",
        note: "ρv², the mechanical push on the dayside. This is what sets how far out the boundary sits.",
      });
    }
    if (coupling !== null && Number.isFinite(coupling)) {
      readings.push({
        label: "Newell coupling",
        value: `${group(coupling)}${band ? ` · ${band}` : ""}`,
        evidence: "empirical",
        note: `${derived?.newellUnits ?? "unnormalised as published"}. ${derived?.newellCitation ?? "Newell et al. (2007)"}.`,
      });
    }
    const boyle = fixed(derived?.boyleCpcpKv, 0, "kV");
    if (boyle && derived) {
      readings.push({
        label: "Cross-polar-cap potential",
        value: `${boyle} (Boyle regression)`,
        evidence: "empirical",
        note: `${derived.boyleNote} Saturation is near ${derived.boyleSaturationKv.toFixed(0)} kV.`,
      });
    }
    if (travel !== null) {
      readings.push({
        label: "L1 to Earth",
        value: `${travel.toFixed(0)} min`,
        evidence: "empirical",
        note: `Measured upstream at ${utcLabel(driver.observedAt)}; this sample reaches Earth at ${utcLabel(driver.validAt)}. Everything downstream is reacting to a wind that was measured about an hour ago.`,
      });
    }

    handoff = southward
      ? `Bz is ${Math.abs(driver.bzGsmNt).toFixed(1)} nT southward, so the interplanetary field is anti-parallel to Earth's on the dayside and the two can merge. That opens the gate: flux is peeled off the dayside, dragged into the tail, and returned through the inner magnetosphere. Everything in links 02 to 07 is that energy arriving.`
      : `Bz is ${driver.bzGsmNt.toFixed(1)} nT, northward. The gate is closed: merging is inefficient, little energy is entering, and the links below are relaxing rather than being driven. This is the state to remember — it is what "quiet" looks like at the top of the chain.`;
  }

  const bz = seriesFromDrivers(drivers, (sample) => sample.bzGsmNt);
  const narrativePhase = narrative?.phase.label ?? null;

  return {
    id: "driver",
    index: "01",
    partOfChain: true,
    role: "The switch",
    title: "Solar wind and interplanetary magnetic field",
    evidence: "observed",
    badge: "L1 OBSERVATION · TRACERS ILLUSTRATIVE",
    what:
      "A magnetised plasma leaves the Sun and reaches Earth one to three days later. What matters is not that it arrives but which way its magnetic field points when it does — "
      + "and NOAA measures that at L1, about an hour upstream.",
    onTheGlobe:
      "The shower is the measured density and speed as tracers; the surface they are approaching is the empirical boundary link 02 explains. The particles are illustrative, the numbers they are scaled from are measured.",
    handoff,
    limit:
      "The animated flow on the globe is a tracer cue, not particle tracks — the values it is scaled from are the measured ones, the motion is illustrative. "
      + "Nothing on this site propagates a coronal mass ejection from the Sun; the chain starts at NOAA's already-propagated L1 series."
      + (narrativePhase ? ` The storm phase classified from Dst at this instant is "${narrativePhase}".` : ""),
    readings,
    timeNote: null,
    series: bz.length
      ? {
        label: "IMF Bz, 48 h",
        unit: "nT",
        evidence: "observed",
        points: bz,
        maximumGapMs: 30 * 60_000,
        markZero: true,
        shadeNegative: true,
      }
      : null,
    scale: null,
    missing,
    camera: "sun-earth",
    // Solar wind alone, under this camera, was the walkthrough's first
    // impression and its worst one: `focusSunEarthSideView` always pulls back
    // far enough to hold the whole magnetotail (nose to tail, ~56 R⊕) so that
    // whichever later step draws the boundary is never cropped — and with no
    // boundary on screen yet, that same pullback framed a tiny Earth and a
    // handful of tracer dots in a mostly empty scene. The boundary is cheap
    // (a client-side Shue evaluation of the same driver sample this step
    // already reads, no fetch), so drawing it from the first frame fills the
    // view the camera was already composing and turns "wind approaches an
    // invisible wall" into "wind approaches the wall" — which is also just a
    // preview of what link 02 explains.
    layersOn: ["solarWind", "magnetosphere"],
    layersNotBuilt: [],
    sources: [
      { label: "NOAA SWPC real-time solar wind (RTSW)", url: "https://services.swpc.noaa.gov/json/rtsw/rtsw_wind_1m.json" },
      { label: "Newell et al. 2007, JGR 112 A01206", url: "https://doi.org/10.1029/2006JA012015" },
    ],
  };
}

function boundaryLink(
  weather: SpaceWeatherBundle | null,
  drivers: readonly StormDriverSample[],
  driver: StormDriverSample | null,
  at: Date,
): ChainLink {
  const readings: ChainReading[] = [];
  let handoff: string | null = null;
  let missing: string | null = null;

  const standoff = driver?.subsolarStandoffRe ?? null;
  if (standoff === null) {
    missing = weather
      ? `The Shue boundary is evaluated from the propagated drivers, and there is no driver sample within 45 minutes of ${utcLabel(at.toISOString())}. Nothing is drawn.`
      : "The space-weather bundle has not loaded, so the boundary cannot be evaluated.";
  } else {
    readings.push({
      label: "Subsolar standoff",
      value: `${standoff.toFixed(2)} R⊕`,
      evidence: "empirical",
      at: driver?.validAt,
      note: standoffVerdict(standoff) ?? undefined,
    });
    // The nominal 10-11 R⊕ and geostationary orbit used to be a second
    // reading each. They are constants, and the scale above draws both of
    // them beside the live value, so repeating them as rows was two rows of
    // a card that was already 611 px past its own bottom edge.
    const alpha = fixed(driver?.flaringAlpha, 3, "");
    if (alpha) {
      readings.push({
        label: "Flaring parameter α",
        value: alpha,
        evidence: "empirical",
        note: "How quickly the boundary opens out downstream. Southward Bz raises it, so a storm both pulls the nose in and flares the flanks.",
      });
    }
    const finite = drivers.map((sample) => sample.subsolarStandoffRe).filter((value): value is number => value !== null && Number.isFinite(value));
    if (finite.length > 1) {
      readings.push({
        label: "Range over the published 48 h",
        value: `${Math.min(...finite).toFixed(2)} - ${Math.max(...finite).toFixed(2)} R⊕`,
        evidence: "empirical",
        note: "The same formula, the same window the timeline covers. The boundary is not a fixed shell; it breathes with the wind.",
      });
    }
    handoff =
      `The boundary is the outer wall of everything inside it. Move it in and two things follow at once: the trapped electrons in link 05 whose drift orbits now reach it are simply lost through it — nothing scattered them, the container changed shape — `
      + `and the funnels at the poles in link 03 steepen. At ${standoff.toFixed(2)} R⊕ the wall is ${(standoff - GEOSTATIONARY_RE).toFixed(2)} R⊕ ${standoff > GEOSTATIONARY_RE ? "outside" : "inside"} geostationary orbit.`;
  }

  const standoffPoints = seriesFromDrivers(drivers, (sample) => sample.subsolarStandoffRe);

  return {
    id: "boundary",
    index: "02",
    partOfChain: true,
    role: "The obstacle",
    title: "Bow shock and magnetopause",
    evidence: "empirical",
    badge: "SHUE 1998 · EMPIRICAL FIT",
    what:
      "Earth's magnetic field is an obstacle in a supersonic flow: the wind is shocked and slowed, then deflected around a cavity whose boundary is the magnetopause. "
      + "Where the nose of that cavity sits is a balance between the pressure outside and the magnetic pressure inside.",
    onTheGlobe:
      "The NOAA MHD plasma field on its published noon-midnight cut, seen face-on. The bow shock is where the colours jump, the magnetosheath is the shocked band behind it, and the magnetopause is the edge of the carved-out cavity — structure in the data, with nothing drawn on top.",
    handoff,
    limit:
      "The coloured cut is the NOAA coupled run's own published plasma field: the bow shock is where its colours jump, the magnetosheath is the shocked band "
      + "behind it, and the magnetopause is the edge of the carved-out cavity — structure in the data, with nothing drawn on top. The empirical boundary drawn "
      + "for comparison is a formula fit to observed crossings, driven by the live pressure, IMF and tilt — not a measured surface and not MHD. The full field "
      + "rides the live window; archived replay frames keep only the extracted boundary curves, and outside the published window everything vanishes rather "
      + "than freezes. Nothing here fills unobserved sectors.",
    readings,
    timeNote: null,
    series: standoffPoints.length
      ? {
        label: "Subsolar standoff, 48 h",
        unit: "R⊕",
        evidence: "empirical",
        points: standoffPoints,
        maximumGapMs: 30 * 60_000,
      }
      : null,
    // The one number of this step, on the axis that makes it mean something.
    // Earth, geostationary orbit and the nominal quiet standoff are all
    // constants the card already prints in words; putting them on one line
    // with the live value is the difference between "9.64 R⊕" and "three
    // Earth radii outside the satellites you care about".
    scale: standoff === null
      ? null
      : {
        label: "Where the dayside boundary is now",
        unit: "R⊕",
        evidence: "empirical",
        from: 0,
        to: 16,
        live: { at: standoff, label: `${standoff.toFixed(2)} R⊕` },
        marks: [
          { at: 1, label: "Earth" },
          { at: GEOSTATIONARY_RE, label: "GEO 6.6" },
        ],
        band: { from: 10, to: 11, label: "nominal" },
      },
    missing,
    camera: "cross-section",
    // Wind, field and the empirical boundary: the interaction itself, with
    // the shock and sheath emerging in the field's colours rather than as a
    // drawn outline.
    layersOn: ["solarWind", "geospace", "magnetosphere"],
    layersNotBuilt: [],
    sources: [
      { label: "Shue et al. 1998, JGR 103, 17691", url: "https://doi.org/10.1029/98JA01103" },
      { label: "NOAA SWPC geospace (SWMF) products", url: "https://services.swpc.noaa.gov/json/geospace/" },
    ],
  };
}

function cuspLink(weather: SpaceWeatherBundle | null, driver: StormDriverSample | null, cuspDrawn: boolean): ChainLink {
  const cusped = weather?.magnetopause?.cuspedBoundaries ?? null;
  const readings: ChainReading[] = [];
  let missing: string | null = null;

  if (!cusped) {
    missing =
      "This release publishes no cusped boundary models. Older artifacts carry only the Shue surface, which has no cusps by construction: its radius depends on solar zenith angle alone. "
      + "Rather than draw a funnel that is not in the data, this step shows nothing.";
  } else {
    for (const model of cusped.models) {
      readings.push({
        label: model.label,
        value: model.surface,
        // A surface's name is a name, not a measurement, and setting it in the
        // readout face made "magnetopause current sheet" look like a quantity
        // whose units had gone missing.
        kind: "name",
        evidence: "empirical",
        note: `Fitted to ${model.fittedTo}. Driven here by ${plainDriverNames(model.drivers)}. doi:${model.doi}`,
      });
    }
    if (driver) {
      const pressure = fixed(driver.dynamicPressureNpa, 3, "nPa");
      const magnetic = fixed(driver.magneticPressureNpa, 4, "nPa");
      if (pressure && magnetic) {
        readings.push({
          label: "Driving both surfaces now",
          value: `${pressure} dynamic, ${magnetic} magnetic`,
          evidence: "observed",
          at: driver.validAt,
          note: "The same propagated sample link 01 shows. Both cusp models are evaluated in the browser from it, so the funnel moves when the wind changes.",
        });
      }
      const clock = fixed(driver.clockAngleDeg, 1, "°");
      if (clock) {
        readings.push({
          label: "Clock angle into Nguyen",
          value: clock,
          evidence: "observed",
          note: "Nguyen 2022 takes the clock angle; Lin 2010 does not. The two surfaces therefore disagree in a way that itself carries information.",
        });
      }
    }
  }

  return {
    id: "cusp",
    index: "03",
    partOfChain: true,
    role: "The gap in the shield",
    title: "The polar cusps",
    evidence: "empirical",
    badge: "NGUYEN 2022 + LIN 2010 · EMPIRICAL",
    what:
      "The deflection in link 02 is not complete. Where the dayside field lines have been peeled back over the poles the boundary folds inward into two funnels, and shocked solar-wind plasma reaches the atmosphere down them almost directly. "
      + "The cusp is the one place where the answer to \"does the solar wind touch the atmosphere\" is simply yes.",
    // This card exists to show a GAP and was showing an unbroken shield. The
    // camera was the fault, not the surface. From directly above the pole the
    // boundary is a dome seen from outside and the cusp - a fold INTO it - is
    // hidden behind its own near wall; edge-on from the dawn-dusk axis the
    // same fold is a dent in the silhouette.
    //
    // Three presentations were photographed at 1440x900 on the live build
    // before this was chosen. Cutting the surfaces open with the explorer's
    // own `#magnetopause-cut` sounds right - its own copy says "the cusp
    // funnels show as the indentations they are" - but the profile curves are
    // hairlines, and the frame came out as two thin arcs crossing an empty
    // scene; zooming in only ran them off the edges. The closed shell edge-on
    // fills the frame, and its outline carries the dent. So: the meridional
    // camera, and the surface left whole.
    onTheGlobe: cusped
      ? "The two empirical surfaces edge-on from the dawn-dusk axis, Sun to the right — the cut every textbook figure of this system uses. The funnel is a fold INTO the boundary, so it shows as a dent in the silhouette at high latitude rather than as a hole. The amber shower is the wind that enters through it."
      : "The empirical boundary only. This release publishes no cusped surface, so there is no funnel in the shape you are looking at.",
    handoff:
      cusped
        ? "Two published surfaces are drawn together and the gap between them is the exterior cusp: Lin traces its inner wall, Nguyen the current sheet outside it. "
          + "The falling sparks are the entry cue — their funnel is the live pair of surfaces and their continuation follows an ideal dipole line to about 75 degrees latitude, "
          + "the dayside cusp aurora's real neighbourhood, reached by mapping rather than drawn at the answer. The motion itself is illustrative. "
          + "Plasma entering here is convected into the inner magnetosphere, where it is trapped and starts to drift — and a drifting population of trapped ions is a current, which is the next link."
        : null,
    limit:
      cusped?.exteriorCusp
        ? `${cusped.exteriorCusp} ${cusped.note}`
        : "Both surfaces are formula fits to spacecraft crossings, not observations of this moment and not simulations of it.",
    readings,
    timeNote: null,
    series: null,
    scale: null,
    missing,
    camera: "cross-section",
    // The wind rather than the oval. The oval was here so that the entry
    // cue's dipole-mapped footpoints could be seen landing just poleward of
    // it, which needs the polar camera — and the polar camera is the one that
    // cannot show the funnel. Between the two, the gap wins: this is the card
    // called "the gap in the shield". The wind is also the better companion
    // on the meridian, because it is the plasma the funnel admits, arriving
    // into it in the same frame.
    layersOn: ["magnetosphere", "cusps", "solarWind"],
    layersNotBuilt: cuspDrawn
      ? []
      : [{
        label: "The cusped surfaces",
        because:
          "The boundary on the globe in this build is the Shue surface, which is smooth over the poles by construction. "
          + "Both cusped models are published in the artifact and can be evaluated in the browser from the same drivers, but no control draws them yet — "
          + "so the numbers on this card are real and the shape beside them is not the one they describe.",
      }],
    sources: [
      { label: "Nguyen et al. 2022 (Model 3)", url: "https://doi.org/10.1029/2021JA029776" },
      { label: "Lin et al. 2010", url: "https://doi.org/10.1029/2009JA014235" },
    ],
  };
}

function ringLink(weather: SpaceWeatherBundle | null, narrative: Narrative, at: Date): ChainLink {
  const storm = weather?.storm ?? null;
  const readings: ChainReading[] = [];
  let missing: string | null = null;
  let handoff: string | null = null;

  if (!storm) {
    missing = "This release publishes no storm-index block, so there is no Dst trace and no ring-current energy to report.";
  } else {
    const responding = narrative?.responding ?? null;
    const observed = responding?.observedNt ?? null;
    const kyoto = responding?.kyotoNt ?? null;
    const modelled = responding?.modelledNt ?? null;

    if (observed !== null) {
      readings.push({
        label: storm.dst.observed.label,
        value: `${observed.toFixed(1)} nT`,
        evidence: "observed",
        at: sampleAt(storm.dst.observed.series, at, 30)?.at,
        note: storm.dst.observed.note,
      });
    }
    if (kyoto !== null) {
      readings.push({
        label: "Kyoto quicklook Dst",
        value: `${kyoto.toFixed(0)} nT`,
        evidence: "observed",
        note: storm.dst.kyoto.statusNote,
      });
    }
    if (modelled !== null) {
      readings.push({
        label: "Modelled Dst (SWMF)",
        value: `${modelled.toFixed(1)} nT`,
        evidence: "model",
        note: `${storm.dst.separationNote}${storm.dst.modelled.forwardLeadMinutes ? ` This trace runs ${storm.dst.modelled.forwardLeadMinutes.toFixed(0)} minutes ahead of real time.` : ""}`,
      });
    }
    if (responding?.nowcastErrorNt !== null && responding?.nowcastErrorNt !== undefined) {
      readings.push({
        label: "Model minus observation",
        value: `${responding.nowcastErrorNt.toFixed(1)} nT`,
        evidence: "model",
        note: "Published rather than hidden. A model and a measurement disagreeing by a known amount is more useful than either alone.",
      });
    }
    readings.push({
      label: "Storm phase",
      value: storm.phase.intensity ? `${storm.phase.label} · ${storm.phase.intensity}` : storm.phase.label,
      evidence: "observed",
      // The phase is classified ONCE, for the bundle, from the run of Dst up to
      // its valid time — `stormNarrativeAt` hands `storm.phase` straight back
      // whatever instant it is asked about. Every other reading on this card
      // follows the timeline, so this one has to print the time it is actually
      // for, or a reader scrubbed back into a quiet hour reads "main phase"
      // beside a Dst of −4 nT and has no way to tell which of the two moved.
      at: storm.validAt,
      note: `${storm.phase.reason}. ${storm.phase.rule} This classification is made once for the whole release, from the Dst run up to ${utcLabel(storm.validAt)}; it does not follow the timeline the way the traces above it do.`,
    });
    if (storm.phase.minimumNt !== null) {
      readings.push({
        label: "Deepest Dst so far",
        value: `${storm.phase.minimumNt.toFixed(0)} nT at ${utcLabel(storm.phase.minimumAt)}`,
        evidence: "observed",
      });
    }

    const ring = ringCurrentNarrative(storm.ringCurrent, responding?.ringEnergyJoules ?? null);
    const energy = responding?.ringEnergyJoules ?? storm.ringCurrent.energyJoules;
    if (energy !== null && Number.isFinite(energy)) {
      readings.push({
        label: "Ring-current energy",
        value: `${energy.toExponential(2)} J`,
        evidence: "model",
        note: `${storm.ringCurrent.method} ${ring?.tangibles.length ? `That is about ${ring.tangibles[0]}, or ${ring.tangibles[2]}.` : ""}`,
      });
    }
    readings.push({
      label: "Ion composition assumed",
      value: "80% H⁺ / 20% O⁺",
      evidence: "model",
      note: `${storm.ringCurrent.compositionModel} ${storm.ringCurrent.compositionReality}`,
    });

    handoff =
      `${storm.ringCurrent.relation} The energy in this link and the energy that accelerates the electrons in the next one come from the same driving — `
      + "the convection and the wave activity that southward Bz switched on in link 01. The ring current is where a storm stores its energy; the belts are where it becomes a problem for hardware.";
  }

  const dstSeries: ChainSeriesPoint[] = (storm?.dst.observed.series ?? []).map((sample) => ({
    t: new Date(sample.at).getTime(),
    value: Number.isFinite(sample.dstNt) ? sample.dstNt : null,
  })).filter((point) => Number.isFinite(point.t)).sort((a, b) => a.t - b.t);

  return {
    id: "ring",
    index: "04",
    partOfChain: true,
    role: "The store",
    title: "Ring current and Dst",
    evidence: "model",
    badge: "DST OBSERVED · ENERGY MODEL-DERIVED",
    // Six sentences of `what` used to run 1,518 px past the bottom of the
    // panel — the reader saw one sixth of this card and never reached the
    // trace, which IS the ring current. Two of those sentences were about
    // what the globe is drawing, which now has its own place to be said, and
    // the O'Brien & Moldwin plasmapause detail belongs to the limits.
    what:
      "Ions injected into the inner magnetosphere are trapped and drift westward; electrons drift east. That circulating current is a westward ring, and its magnetic field subtracts from Earth's at the surface. "
      + "That subtraction is Dst — which is why Dst is not merely correlated with the ring current but a measurement of it. The trace below is the ring current.",
    onTheGlobe:
      "Not the ring current: the relation yields one number and no spatial ring-current field is published, and a number drawn as a solid object would claim structure nobody measured. What is drawn is the plasmasphere — cold, dense plasma whose outer edge is eroded by the same convection that injects the ring current. Scrub the timeline across a storm and watch the dense core shrink and stay small.",
    handoff,
    limit:
      storm
        ? `${storm.ringCurrent.uncertainty} The energy is a single number for the whole population, so the readings and the trace above are the whole of what this site knows: `
          + "the real storm-time ring current is partial and peaks near dusk (Liemohn et al. 2001), and no published field in this release places that structure. "
          + "A torus used to be drawn here and has been removed, because it invented a shape the number never carried. "
          + "The plasmapause on the globe is placed by the O'Brien & Moldwin (2003) fit from the deepest Dst of the preceding day — an empirical edge driven by a measured index, not an observed boundary."
        : "No storm block in this release.",
    readings,
    timeNote: null,
    series: dstSeries.length
      ? { label: "Observed Dst3, 48 h", unit: "nT", evidence: "observed", points: dstSeries, maximumGapMs: 30 * 60_000, markZero: true, shadeNegative: true }
      : null,
    scale: null,
    missing,
    camera: "reset",
    layersOn: ["ringCurrent"],
    layersNotBuilt: [],
    sources: [
      { label: "USGS Geomagnetism Program — Dst3/Dst4", url: "https://geomag.usgs.gov/ws/data/" },
      { label: "WDC Kyoto quicklook Dst", url: "https://services.swpc.noaa.gov/products/kyoto-dst.json" },
    ],
  };
}

/**
 * The NOAA alert threshold for the GOES >=2 MeV integral electron flux.
 *
 * 1,000 particles cm^-2 s^-1 sr^-1 sustained is the level NOAA issues an
 * alert at, because that is where internal charging of spacecraft dielectrics
 * becomes an operational concern. Written as a constant so the card can say
 * where the live number sits relative to it in both regimes — a quiet belt is
 * a lesson too, and it is the usual one.
 */
const GOES_ELECTRON_ALERT_PFU = 1000;

/**
 * How far below the alert level a quiet belt is, in words that stay true as it
 * approaches the level.
 *
 * "Nx below it" rounded to a whole number, which is what this printed until
 * 2026-09-08, says "1x below it" for everything from 500 up to the alert level
 * itself — and "one times below" is not a smaller number, it is the same one.
 * Under a factor of two the honest form is the percentage.
 */
function belowAlertPhrase(fluxPfu: number): string {
  const ratio = GOES_ELECTRON_ALERT_PFU / Math.max(fluxPfu, 1e-6);
  if (ratio < 2) return `this is at ${((fluxPfu / GOES_ELECTRON_ALERT_PFU) * 100).toFixed(0)}% of it`;
  return `this is ${ratio < 10 ? ratio.toFixed(1) : group(ratio)}x below it`;
}

function beltsLink(inputs: ChainInputs): ChainLink {
  const coverage = inputs.coverage?.geospace ?? null;
  const particles = inputs.weather?.particles ?? null;
  const readings: ChainReading[] = [];
  let missing: string | null = null;

  // The measurement first, then the model. This step had no measured number
  // at all until 2026-08-19: three rows of release metadata, one of them
  // labelled "Model" carrying a MODEL badge, and not one quantity a reader
  // could act on. GOES measures the integral electron flux at geostationary
  // orbit and this site already publishes it, so the step now shows what one
  // spacecraft actually counts beside what the coupled run models everywhere
  // — which is the honest shape of this whole subject.
  if (particles && particles.electronFlux !== null && Number.isFinite(particles.electronFlux)) {
    const flux = particles.electronFlux;
    const over = flux >= GOES_ELECTRON_ALERT_PFU;
    readings.push({
      label: `GOES electron flux ${particles.electronEnergy}`,
      value: `${group(flux)} cm⁻² s⁻¹ sr⁻¹`,
      evidence: "observed",
      at: particles.electronObservedAt,
      note: over
        ? `Above NOAA's ${group(GOES_ELECTRON_ALERT_PFU)} alert level, where internal charging of spacecraft dielectrics becomes an operational concern. This is a count at one place — geostationary orbit — not the whole belt.`
        : `NOAA alerts at ${group(GOES_ELECTRON_ALERT_PFU)}, where internal charging becomes an operational concern; ${belowAlertPhrase(flux)}. A quiet belt is the state a storm is measured against. This is a count at one place — geostationary orbit — not the whole belt.`,
    });
  }

  if (!coverage) {
    missing = "This release publishes no coupled geospace bundle, so there is no radiation-belt solution to show.";
  } else {
    const inside = withinWindow(inputs.at, coverage.validFrom, coverage.validTo);
    readings.push({
      label: "Modelled everywhere else",
      value: "NOAA/NASA RBE phase-space solution",
      kind: "name",
      evidence: "model",
      note: `The same coupled operational run whose Dst appears in link 04. One driving, two outputs — that is the coupling, not a coincidence. `
        + `Published for ${utcLabel(coverage.validFrom)} to ${utcLabel(coverage.validTo)}, ${coverage.frameCount} frames; `
        + (inside
          ? "the volume on the globe is the solution for the time on the timeline."
          : "the selected time is outside that window, so nothing is drawn for this instant."),
    });
  }

  return {
    id: "belts",
    index: "05",
    partOfChain: true,
    role: "The trap",
    title: "Radiation belts",
    evidence: "model",
    badge: "COUPLED PHYSICS SIMULATION",
    what:
      "Electrons at hundreds of keV to several MeV are trapped on closed drift shells, bouncing between mirror points and drifting around the Earth. "
      + "The same storm-time convection and wave activity that fill the ring current accelerate this population, and the compressed boundary in link 02 can empty it.",
    onTheGlobe:
      "The modelled electron flux, mapped along dipole field lines into a volume so the two belts and the slot between them emerge from the field. The GOES number above is measured at one point inside it; nothing on the globe is.",
    handoff:
      "A trapped particle stays trapped only while its mirror point is above the atmosphere and its drift shell is inside the boundary. Lose either condition and it is lost — "
      + "out through the magnetopause on the dayside, or down into the atmosphere along the field line. The second of those is the next link, and it is the one you can see from the ground.",
    limit:
      "This is simulation output. No measurement fixes any individual value in it, and it does not solve magnetopause loss — the site can show you the boundary moving and it can show you a modelled belt, but it cannot show you one causing the other. "
      + "Radial distances on the globe are logarithmically compressed, so intersection with an orbit cannot be judged by eye.",
    readings,
    timeNote: null,
    series: null,
    scale: null,
    missing,
    camera: "layer-framed",
    layersOn: ["radiation"],
    layersNotBuilt: [],
    sources: [
      { label: "NOAA SWPC geospace (SWMF/RBE) products", url: "https://services.swpc.noaa.gov/json/geospace/" },
    ],
  };
}

function auroraLink(weather: SpaceWeatherBundle | null, at: Date): ChainLink {
  const aurora = weather?.aurora ?? null;
  const readings: ChainReading[] = [];
  let missing: string | null = null;
  // Compared against the observation that drives the forecast, not against the
  // forecast's own valid time: OVATION is published about an hour ahead by
  // design, and warning about that every time the reader is at "now" would
  // turn the caution into wallpaper.
  const auroraTimeNote = snapshotNote(
    at,
    aurora?.observedAt,
    "the OVATION headline",
    "The oval drawn on the globe does follow the timeline — it comes from the separate 40-hour archive — so the shape you are looking at and the percentage below are not the same instant.",
  );

  if (!aurora) {
    missing = "This release publishes no OVATION grid.";
  } else {
    readings.push({
      label: "Peak viewing probability",
      value: `${aurora.maximumProbability.toFixed(0)}%`,
      evidence: "forecast",
      at: aurora.forecastAt,
      note: "The highest value anywhere on the published grid. It is a probability of seeing aurora from the ground, not a brightness.",
    });
    readings.push({ label: "Model", value: aurora.model, kind: "name", evidence: "forecast" });
    const lead = minutesBetween(aurora.observedAt, aurora.forecastAt);
    if (lead !== null) {
      readings.push({
        label: "Forecast lead",
        value: `${lead.toFixed(0)} min`,
        evidence: "forecast",
        note: `Driven by solar wind observed at ${utcLabel(aurora.observedAt)} and valid at ${utcLabel(aurora.forecastAt)}. This is the only link in the chain that is published ahead of real time, and the lead is roughly the L1 travel time in link 01 — because that is exactly what it is.`,
      });
    }
  }

  return {
    id: "aurora",
    index: "06",
    partOfChain: true,
    role: "The visible end",
    title: "Aurora",
    evidence: "forecast",
    badge: "OVATION 2020 · FORECAST",
    what:
      "Particles that lose their trapping precipitate into the upper atmosphere along field lines and excite oxygen and nitrogen. The oval is a map of where that precipitation is landing — "
      + "and it moves equatorward as a storm grows, because the harder the driving the further down the field lines that map to the boundary reach.",
    onTheGlobe:
      "The OVATION viewing-probability grid, from above the pole so the whole oval is in one frame. An oval seen from the side is an arc on the limb, which is why this step looks down the axis.",
    handoff:
      "The light is the by-product. The consequence is the ionisation: those same particles strip electrons off the atmosphere they hit, and an atmosphere with more free electrons is a different radio and navigation environment. That is the last link.",
    limit:
      aurora?.caveat
        ?? "Model-derived viewing probability. Daylight, cloud, terrain and local viewing conditions are not represented.",
    readings,
    timeNote: auroraTimeNote,
    series: null,
    scale: null,
    missing,
    // Down the dipole axis, not the default globe. The oval is a ring around
    // the pole: the reset camera puts it on the limb as an arc, half of it
    // behind the Earth, which is the one presentation in which the shape the
    // step exists to show cannot be seen. `main.ts` makes the same argument
    // for the plasmasphere, in the same words, for the same reason.
    camera: "polar",
    layersOn: ["aurora"],
    layersNotBuilt: [],
    sources: [
      { label: "NOAA SWPC OVATION aurora forecast", url: "https://services.swpc.noaa.gov/json/ovation_aurora_latest.json" },
    ],
  };
}

function groundLink(weather: SpaceWeatherBundle | null, at: Date): ChainLink {
  const ionosphere = weather?.ionosphere ?? null;
  const readings: ChainReading[] = [];
  let missing: string | null = null;
  const groundTimeNote = snapshotNote(
    at,
    ionosphere?.observedAt,
    "the GloTEC headline",
    "The TEC surface and the WAM-IPE peak on the globe each follow the timeline from their own archives; these two numbers do not.",
  );

  if (!ionosphere) {
    missing = "This release publishes no GloTEC field.";
  } else {
    const range = ionosphere.tecRange;
    if (Array.isArray(range) && range.length === 2) {
      readings.push({
        label: "Vertical TEC across the globe",
        value: `${range[0].toFixed(1)} - ${range[1].toFixed(1)} TECU`,
        evidence: "assimilated",
        at: ionosphere.observedAt,
        note: "One TECU delays a GPS L1 signal by about 16 cm of apparent range. The spread between these two numbers is the positioning error a single-frequency receiver cannot see.",
      });
    }
    const hmf2 = fixed(ionosphere.medianHmF2Km, 0, "km");
    if (hmf2) {
      readings.push({
        label: "Median F2 peak height",
        value: hmf2,
        evidence: "forecast",
        note: "WAM-IPE. The height of the layer that reflects HF back to the ground; raise it and a given frequency reaches further per hop.",
      });
    }
    const kp = weather?.geomagnetic?.kp;
    if (kp !== null && kp !== undefined && Number.isFinite(kp)) {
      readings.push({
        label: "Planetary Kp",
        value: kp.toFixed(1),
        evidence: "observed",
        at: weather?.geomagnetic?.observedAt,
        note: "A three-hour index. It cannot resolve a sudden onset, which is why Dst in link 04 is the physical measure and Kp is the one the scales quote.",
      });
    }
  }

  return {
    id: "ground",
    index: "07",
    partOfChain: true,
    role: "The ground",
    title: "Ionosphere, HF and GNSS",
    evidence: "assimilated",
    badge: "GLOTEC ASSIMILATED · WAM-IPE FORECAST",
    what:
      "This is where the chain stops being astrophysics and starts being an operational problem. Precipitation and heating change the free-electron content and the height of the layers, "
      + "and every HF path, every satellite navigation fix and every low-orbit drag calculation is downstream of that.",
    onTheGlobe:
      "Two fields at once: the assimilated total electron content, and the height at which the neutral air reaches a fixed density — the one that climbs toward the satellites during a storm.",
    handoff: null,
    limit:
      "TEC is assimilated — measurements filled in by a model between them — and the F2 peak is a forecast. Neither is a measurement at any particular point. "
      + "Satellite drag responds to the *neutral* thermosphere density, not to the electron content shown here; the two rise together because the same heating drives both, but they are not the same quantity. The neutral field is published and drawn — switch on Thermosphere height to see the altitude at which the air reaches a fixed density, and watch it climb toward the satellites during a storm.",
    readings,
    timeNote: groundTimeNote,
    series: null,
    scale: null,
    missing,
    camera: "reset",
    layersOn: ["tec", "thermosphere"],
    layersNotBuilt: [],
    sources: [
      { label: "NOAA SWPC GloTEC", url: "https://www.swpc.noaa.gov/products/global-total-electron-content" },
      { label: "NOAA/NCEP WAM-IPE", url: "https://www.swpc.noaa.gov/products/wam-ipe" },
    ],
  };
}

/**
 * The photon branch, step one: the thing that is not deflected.
 *
 * Sean, on the standing rail layer this replaces: "for xray flux, I really
 * don't know what to show... I don't know if it is useful." He was right
 * about the layer and right about the number. The NUMBER is a data product
 * and it lives on Current conditions, with a sparkline and a flare-class
 * axis, where a number belongs. What the globe adds is not a second copy of
 * it — a single scalar cannot fill a globe, and at quiet-Sun flux the
 * hemisphere tint is nearly transparent, which is exactly what he saw: "I
 * see white 'particles' showering over earth."
 *
 * What the globe CAN show is a contrast, and it is a good one. Every other
 * input in this scene is charged and gets turned aside at the boundary.
 * X-rays carry no charge, so the field exerts no force on them: they cross
 * the magnetosphere dead straight and land on the dayside. That is one frame
 * with the solar wind bending around the surface and the beam going through
 * it, and it is a fact you cannot get from a graph. So the layer stops being
 * a standing rail slot and becomes this step, where the solar wind is on
 * beside it and the contrast is the whole point.
 */
function xrayLink(inputs: ChainInputs): ChainLink {
  const weather = inputs.weather;
  const at = inputs.at;
  const xray = weather?.xray ?? null;
  const readings: ChainReading[] = [];
  let missing: string | null = null;
  const xrayTimeNote = snapshotNote(
    at,
    xray?.observedAt,
    "the GOES X-ray flux",
    "The published 7-day series is rounded to zero at background levels, so there is no honest way to read this channel at a past time from this release.",
  );

  if (!xray) {
    missing = "This release publishes no GOES X-ray series.";
  } else {
    const scale = radioBlackoutLevel(xray.fluxWm2);
    readings.push({
      label: "GOES 0.1-0.8 nm flux",
      value: `${xray.class}${xray.fluxWm2 !== null ? ` · ${xray.fluxWm2.toExponential(2)} W/m²` : ""}`,
      evidence: "observed",
      at: xray.observedAt,
      note: "How many rays are drawn and how brightly is this number and nothing else: sparse and faint at A class, a dense shower at X.",
    });
    readings.push({
      label: "Deflected by the magnetosphere",
      value: "not at all",
      kind: "name",
      evidence: "observed",
      note: "Photons carry no charge, so the magnetic field exerts no force on them. The bow shock, the magnetosheath and the magnetopause do nothing to this input. Nothing in near-Earth space attenuates it either: it is unchanged until the D region at 60-90 km.",
    });
    readings.push({
      label: "Travel time from the Sun",
      value: "about 8 minutes",
      evidence: "observed",
      note: "At the speed of light, in a straight line. The plasma in links 01-07 took one to three days to make the same trip and was deflected on arrival. Same Sun, often the same active region, two completely different clocks.",
    });
    readings.push({
      label: "Radio blackout scale from this flux",
      value: scale.level === 0 ? "R0 · none" : `R${scale.level} · ${scale.label}`,
      evidence: "empirical",
      note: scale.level === 0
        ? "Below M1 (1×10⁻⁵ W/m²) there is no blackout to report. The photon path is idle at this instant — which is exactly why it is worth showing beside a chain that is not."
        : "NOAA's published thresholds applied to the flux above: R1 at M1, R2 at M5, R3 at X1, R4 at X10, R5 at X20. The dayside HF effect starts the moment the photons arrive, not hours later.",
    });
  }

  const xraySeries = drawableXraySeries(xray?.series ?? null);
  if (xray && xraySeries === null) {
    readings.push({
      label: "X-ray history",
      value: "not drawable from this release",
      kind: "name",
      evidence: "observed",
      note:
        "The published 7-day X-ray series rounds to five decimal places, and this flux is of order 10⁻⁷ W/m², so every value in it quantises to zero. "
        + "A flat line at zero would be a picture of a rounding rule, not of the Sun, so nothing is drawn here. The instantaneous flux above is unaffected, and the full trace is on the Current conditions page.",
    });
  }

  return {
    id: "xray",
    index: "X1",
    partOfChain: false,
    role: "Not part of the chain",
    title: "The one input that is not deflected",
    evidence: "observed",
    badge: "GOES XRS OBSERVED · BEAM ILLUSTRATIVE",
    what:
      "X-rays from a flare are photons. They are not deflected by the bow shock, they do not care which way Bz points, they do not get trapped and they do not drift. "
      + "They travel straight from the Sun in about eight minutes and ionise the sunlit atmosphere directly.",
    onTheGlobe:
      "Both inputs at once, which is the whole reason this step exists: the amber shower bending around the boundary, and a parallel beam going straight through it to the dayside. The beam is drawn straight because that is the physics; how many rays there are is the measured flux; their speed on screen is display cadence.",
    handoff:
      "A flare causes an HF blackout the same morning while a coronal mass ejection from the same active region causes a storm days later. Where those photons land, the D region ionises — and that is the next card.",
    limit:
      "The inbound rays and the sunlit tint are irradiance cues scaled from the measured flux, not individual photon tracks; the rays are drawn straight and absorbed on the dayside because that is what light does, but their speed on screen is display cadence. "
      + "The tint is cos(solar zenith angle) — incidence geometry only, not a claim about how much any layer absorbs. "
      + "This visual has no standing control in the rail: a single scalar cannot fill a globe on its own, and the number it is scaled from is published as a trace on Current conditions, which is where a number belongs.",
    readings,
    timeNote: xrayTimeNote,
    series: xraySeries,
    scale: null,
    missing,
    // Sun off to one side, so the beam is seen crossing the boundary rather
    // than end-on. The reset camera put the terminator on the limb and the
    // dayside facing away, which is a picture of the night side on the card
    // about what the Sun does to the day side.
    camera: "sun-earth",
    layersOn: ["photons", "solarWind", "magnetosphere"],
    layersNotBuilt: [],
    sources: [
      { label: "GOES X-ray flux, NOAA SWPC", url: "https://services.swpc.noaa.gov/json/goes/primary/xrays-7-day.json" },
    ],
  };
}

/**
 * The photon branch, step two: what the photons do where they land.
 *
 * Separated from the card above because it is a different claim measured a
 * different way — an empirical absorption model over the sunlit hemisphere,
 * not an observed irradiance — and because the two together ran 871 px past
 * the bottom of the panel.
 */
function dRegionLink(inputs: ChainInputs): ChainLink {
  const at = inputs.at;
  const drap = inputs.drap ?? null;
  const readings: ChainReading[] = [];
  let missing: string | null = null;

  if (!drap) {
    missing = inputs.coverage?.drap
      ? "The D-region absorption field is still loading."
      : "This release publishes no D-region absorption field.";
  } else {
    // The absorption field is the one part of this branch with a real
    // archive, so it is selected at the time on the timeline rather than
    // pinned to the newest frame. `selectDrapFrame` reaches BACKWARD only and
    // never interpolates; it does not refuse a stale frame, it reports the
    // age, so the forward end of the timeline is refused here instead. D-RAP
    // publishes no future frames at all and the slider runs 72 h past the last
    // one, which is how this branch used to report a three-day-old maximum as
    // the current state of the D region.
    const selection = selectDrapFrame(drap, at);
    const newestFrame = drap.frames.at(-1);
    const pastNowcast = selection !== null && newestFrame !== undefined
      && at.getTime() > Date.parse(newestFrame.validAt)
      && selection.ageMinutes > DRAP_LIVE_EDGE_HOLD_MINUTES;
    const frame = pastNowcast ? null : selection?.frame ?? null;
    if (frame) {
      // The quiet clause used to fire only at EXACTLY zero, which is a state
      // the live artifact reaches on none of its 446 frames. `drapCondition`
      // is the layer's own three-state reading and says the same thing about
      // a peak below the 3 MHz floor and about one that clears it by a
      // fraction and paints 4% of the globe.
      const condition = drapCondition(frame);
      readings.push({
        label: drap.quantity.shortName,
        value: `${frame.maximumHafMhz.toFixed(1)} MHz maximum`,
        evidence: "model",
        at: frame.validAt,
        note: `${drap.quantity.definition} ${frame.affectedCellPercent["3MHz"].toFixed(1)}% of the grid is above 3 MHz`
          + `${condition.status === "active" ? "" : " — almost nothing in the HF band, which is what a quiet Sun looks like on this field"}.`,
      });
    } else if (pastNowcast) {
      missing = `D-RAP is a nowcast and publishes no future frames; its record stops at ${utcLabel(drap.time.validTo)}, before the time on the timeline. Rather than hold the last map and call it this hour, nothing is reported.`;
    } else {
      missing = `The D-RAP archive runs ${utcLabel(drap.time.validFrom)} to ${utcLabel(drap.time.validTo)}, and nothing is published for the time on the timeline. Rather than draw a nearby frame and call it this one, nothing is reported.`;
    }
    if (drap.messages.xray) {
      readings.push({ label: "NOAA D-RAP status", value: drap.messages.xray, kind: "name", evidence: "model" });
    }
    const observed = inputs.weather?.outlook?.noaaScales?.latestObserved;
    if (observed) {
      readings.push({
        label: "NOAA's own scales right now",
        value: `R${observed.radioBlackout.level ?? 0} · S${observed.solarRadiation.level ?? 0} · G${observed.geomagnetic.level ?? 0}`,
        evidence: "observed",
        at: observed.asOf ?? undefined,
        note: "Radio, radiation and geomagnetic: three scales, three different physical paths from the same star. They routinely disagree, and that disagreement is the whole lesson of this branch.",
      });
    }
  }

  return {
    id: "dregion",
    index: "X2",
    partOfChain: false,
    role: "Not part of the chain",
    title: "Where the photons land: the D region",
    evidence: "model",
    badge: "D-RAP · NOAA MODEL",
    what:
      "Soft X-rays are absorbed at 60-90 km, on the sunlit side only, and the free electrons they leave behind absorb HF instead of reflecting it. "
      + "That is a radio blackout: it begins the moment the photons arrive and it ends when the flare does.",
    onTheGlobe:
      "NOAA's D-RAP field — the highest frequency absorbed by 1 dB on a vertical two-pass path — over the hemisphere the beam in the previous card is landing on. It follows the timeline from its own archive.",
    handoff: null,
    limit:
      "D-RAP is empirical model guidance for a vertical two-pass path, not an outage report, and it omits auroral-electron absorption entirely — which means the one absorption mechanism that *does* belong to the chain in links 01-07 is the one it leaves out.",
    readings,
    timeNote: null,
    series: null,
    scale: null,
    missing,
    camera: "reset",
    layersOn: ["drap", "photons"],
    layersNotBuilt: [],
    sources: [
      { label: "NOAA D-Region Absorption Predictions", url: "https://www.spaceweather.gov/products/d-region-absorption-predictions-d-rap" },
    ],
  };
}

/**
 * The GOES X-ray series, or null when this release cannot support a trace.
 *
 * `build_release.py` rounds every downsampled series to five decimal places.
 * X-ray flux at background is of order 1e-7 W/m^2, so the whole 576-point
 * series quantises to exactly zero and only rises above the rounding floor
 * during a flare. Drawing it would be drawing the rounding rule.
 *
 * The rule is deliberately expressed as "fewer than two points that are
 * positive" rather than "the current release is broken", so that the trace
 * comes back on its own the day an M-class flare pushes the values above
 * 1e-5 — and so that a fixed publisher needs no change here.
 */
export function drawableXraySeries(
  series: readonly { time: string; value: number | null }[] | null,
): ChainSeries | null {
  if (!series?.length) return null;
  const points: ChainSeriesPoint[] = [];
  let positive = 0;
  for (const sample of series) {
    const t = new Date(sample.time).getTime();
    if (!Number.isFinite(t)) continue;
    const usable = sample.value !== null && Number.isFinite(sample.value) && sample.value > 0;
    if (usable) positive += 1;
    points.push({ t, value: usable ? Math.log10(sample.value as number) : null });
  }
  if (positive < 2) return null;
  points.sort((a, b) => a.t - b.t);
  return {
    label: "GOES 0.1-0.8 nm flux",
    unit: "log₁₀ W/m²",
    evidence: "observed",
    points,
    maximumGapMs: 60 * 60_000,
    logScale: true,
  };
}

function withinWindow(at: Date, from: string, to: string): boolean {
  const start = new Date(from).getTime();
  const end = new Date(to).getTime();
  if (!Number.isFinite(start) || !Number.isFinite(end)) return false;
  return at.getTime() >= start && at.getTime() <= end;
}

// ---------------------------------------------------------------------------
// The one-line summary that has to be true in both regimes
// ---------------------------------------------------------------------------

export interface ChainVerdict {
  /** "driven" when the switch is on, "relaxing" when it is not, "unknown" with no driver. */
  state: "driven" | "relaxing" | "unknown";
  headline: string;
  detail: string;
  /**
   * The sentence that tells a reader to start walking.
   *
   * Split out of `detail` because it is true once. It was being reprinted
   * above every card — "Walk the seven links below and every one of them is
   * responding to that sign" — including above link 06, by which point the
   * reader has walked five of them and is being invited to start. The view
   * shows it on the first step only.
   */
  invitation: string;
}

/**
 * What the chain is doing right now, in one sentence, from the two numbers
 * that decide it: the sign of Bz and the depth of Dst.
 *
 * Deliberately deterministic. No language model is consulted, and the quiet
 * answer is written to be as informative as the stormy one — a reader who
 * arrives on a dull Tuesday should learn what "off" looks like.
 */
export function chainVerdict(inputs: ChainInputs): ChainVerdict {
  const drivers = driverSeries(inputs.weather);
  const driver = sampleDriverAt(drivers, inputs.at, 45);
  const storm = inputs.weather?.storm ?? null;
  const narrative = stormNarrativeAt(storm, drivers, inputs.at);
  const dst = narrative?.responding.observedNt ?? narrative?.responding.kyotoNt ?? null;
  const phase = storm?.phase;

  if (!driver) {
    return {
      state: "unknown",
      headline: "No propagated solar-wind sample for this time.",
      detail: "The chain is driven from L1 and nothing is published for the instant on the timeline, so the walkthrough reports no state rather than the last one it saw.",
      invitation: "Move the timeline back inside the published window to read the chain.",
    };
  }

  const southward = driver.bzGsmNt < 0;
  const standoff = driver.subsolarStandoffRe;
  const dstText = dst === null ? "" : ` Dst is ${dst.toFixed(0)} nT`;
  const standoffText = standoff === null ? "" : ` and the dayside boundary is at ${standoff.toFixed(1)} R⊕`;

  if (southward) {
    // The sign is what opens the gate; the coupling function is how far. A
    // headline that read "the switch is on" identically at -1.9 nT and -25 nT
    // would teach the sign and hide the magnitude, so the published Newell
    // band goes in the same sentence.
    const coupling = driver.newellCoupling ?? newellCoupling(driver.speedKps, driver.byNt, driver.bzGsmNt);
    const band = newellBand(coupling, inputs.weather?.storm?.derived?.newellCalibration ?? []);
    return {
      state: "driven",
      headline: `The switch is on: IMF Bz is ${driver.bzGsmNt.toFixed(1)} nT, southward${band ? `, driving at the "${band}" level` : ""}.`,
      detail:
        `Energy is entering the system.${dstText}${standoffText}.`
        + (phase ? ` The Dst trace classifies this as ${phase.intensity ? `${phase.label} phase, ${phase.intensity}` : `${phase.label} phase`}.` : ""),
      invitation: "Walk the seven links below and every one of them is responding to that sign.",
    };
  }
  return {
    state: "relaxing",
    headline: `The switch is off: IMF Bz is ${driver.bzGsmNt.toFixed(1)} nT, northward.`,
    detail: `Dayside merging is inefficient, so little energy is entering.${dstText}${standoffText}.`,
    invitation: "Walk the links anyway: this is what the quiet state of each one looks like, and it is the baseline every storm is measured against.",
  };
}
