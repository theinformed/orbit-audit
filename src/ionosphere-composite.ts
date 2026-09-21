/**
 * A four-layer ionosphere assembled from what this site actually measures.
 *
 * Why this module exists rather than a climatology
 * ------------------------------------------------
 * The site's operational field is NOAA's WAM-IPE. It resolves D and F2 and it
 * genuinely does not resolve E or F1 - measured on the live artifact, not
 * assumed: the E ledge's median prominence above the E-F valley is 0.02 dex on
 * a 5.6-decade scale (one uint8 code), the DAYSIDE median prominence is
 * -0.088 dex (negative: density climbs monotonically from E into F, so there
 * is no local E maximum to find), and the published F1 criterion resolved F1
 * over 0% of columns.
 *
 * The obvious fix is to drop in a published climatology such as IRI. This
 * module deliberately does not, because a climatology answers "what is the
 * ionosphere usually like on a day like this" and this site's whole contract
 * is to show what it is like NOW, with the evidence attached. Nothing in here
 * reads a historical table or a sunspot-number regression.
 *
 * What each layer is, and where it comes from
 * -------------------------------------------
 *   D   Wait-Spies profile, driven by solar zenith angle and the MEASURED
 *       GOES 0.1-0.8 nm X-ray flux, including flare-driven lowering.
 *       Unchanged from `d-region-empirical.ts`, which already ships EMPIRICAL.
 *   E   Chapman layer near 110 km. The SHAPE is Chapman theory; the STRENGTH
 *       is today's soundings.
 *   F1  Chapman layer near 190 km, present only in strong daylight. Same
 *       treatment as E.
 *   F2  WAM-IPE, which resolves F2 well, optionally pulled toward a nearby
 *       measured foF2.
 *
 * So the badge is COMPOSITE and it cannot honestly be anything else. It is not
 * OBSERVED - most of the globe has no sounding within thousands of kilometres.
 * It is not MODEL - the E and F1 amplitudes come from instruments that sounded
 * within the last three hours. Reporting either one alone would be a lie in a
 * different direction, which is why `composite` was added to the evidence
 * vocabulary rather than folded into an existing class.
 *
 * The Chapman shape is not a hand-wave - it was checked against the soundings
 * -------------------------------------------------------------------------
 * Chapman theory says a solar-produced layer has peak density proportional to
 * cos(chi), so its critical frequency goes as cos(chi)^0.25. Fitting a free
 * power law to every sounding in the network that had a scaled foE with the
 * sun above the horizon (n=33, 2026-08-19) gave
 *
 *     foE = 3.63 * cos(chi)^0.268        R^2 = 0.47
 *
 * against a theoretical exponent of 0.25. The measured exponent is within 7%
 * of theory. In the linearised form the theory actually predicts,
 * foE^4 = 191 * cos(chi) - 3.2 with R^2 = 0.67. That is the evidence for
 * drawing an E layer this way, and it is why `CHAPMAN_EXPONENT` is theory's
 * 0.25 rather than the fitted 0.268: the measurement CONFIRMS the theoretical
 * value, so pinning the fitted third decimal of one afternoon's network would
 * be overfitting a constant that physics already supplies.
 *
 * The F1 cut-off is measured, not quoted
 * --------------------------------------
 * F1 exists only where the sun is high. Across the whole network, foF1 was
 * present in 80% of records taken below 30 deg solar zenith angle, 43% below
 * 70 deg, and **0% above 80 deg**. The largest solar zenith angle at which any
 * station reported an F1 layer at all was **72.5 deg**, so that is the cut-off
 * this module uses. A reader who sees no F1 at night is not seeing missing
 * data; they are seeing the layer's absence, which is the correct answer.
 *
 * Where the network is thin, the anchoring visibly weakens
 * --------------------------------------------------------
 * This is the part that must not be quietly smoothed over. Area-weighted over
 * the globe on 2026-08-19, the distance to the nearest sounding less than
 * three hours old had a median of **2,643 km**; only **12.3%** of Earth's
 * surface was within 1,000 km of one and only **3.8%** within 500 km. For the
 * E layer specifically it is far worse - only 5 stations in the whole network
 * had a scaled foE, median distance **4,892 km**, with **3.1%** of the surface
 * inside 1,000 km. Asia had no fresh station at all; Africa and Australasia
 * had none with a scaled foE.
 *
 * So the anchor is a LOCAL CORRECTION, never a global field, and `anchorWeight`
 * takes it to zero over an ocean. `interpolate a value across 5,000 km of
 * Pacific` is exactly the failure this module is built to avoid.
 */

import {
  dRegionSubsolarPoint,
  solarZenithAngleDeg,
  type GeographicPoint,
} from "./d-region-empirical";
import { PLASMA_FREQUENCY_MHZ_COEFFICIENT } from "./ionosphere-profile";
import type { Sounding } from "./ionosonde-soundings";
import { greatCircleDistanceKm } from "./ionosonde-soundings";

export const COMPOSITE_IONOSPHERE_METHOD = {
  title: "Composite four-layer ionosphere",
  evidence: "composite" as const,
  summary:
    "Chapman-shaped E and F1 layers whose strength comes from soundings taken in the "
    + "last three hours, above an empirical D region driven by measured X-ray flux, "
    + "below NOAA's modelled F2. Every layer is labelled with where it came from.",
  layers: {
    D: "Wait-Spies profile driven by solar zenith angle and measured GOES 0.1-0.8 nm flux (empirical).",
    E: "Chapman layer at 110 km. Shape from theory, strength from measured foE (composite).",
    F1: "Chapman layer at 190 km, present only below 72.5 deg solar zenith angle. Shape from theory, strength from measured foF1 (composite).",
    F2: "NOAA WAM-IPE modelled column, pulled toward a measured foF2 only where a sounding is near (model, locally anchored).",
  },
  sources: [
    { citation: "Chapman, S. (1931), Proc. Phys. Soc. 43, 26-45", doi: "https://doi.org/10.1088/0959-5309/43/1/305" },
    { citation: "Wait and Spies (1964), NBS Technical Note 300", doi: "https://doi.org/10.6028/NBS.TN.300" },
    { citation: "Reinisch and Galkin (2011), Global Ionospheric Radio Observatory, Earth Planets Space 63, 377-381", doi: "https://doi.org/10.5047/eps.2011.03.001" },
  ],
  limitations: [
    "The critical frequencies are measured; the layer THICKNESSES are not. An ionogram scaling gives foE and hmE but no E semi-thickness, so the Chapman scale heights here are assumed constants and the layer widths drawn from them are illustrative.",
    "The E and F1 amplitudes are fitted to the whole network at one instant. On 2026-08-19 only 5 fresh stations carried a scaled foE, so that fit rests on very few points and is refitted every release rather than trusted as a constant.",
    "Anchoring falls to zero beyond about 3,000 km because that is where station-pair differences reach the level of two unrelated stations. Over most ocean the E and F1 layers here are the network-wide solar fit, not a local measurement.",
    "No layer here is a forecast, and none of it is assimilated in the meteorological sense: there is no dynamical model being corrected, only a shape being scaled to fit nearby observations.",
    "Sporadic E is excluded. It is a thin irregular patch rather than a layer of the daily ionosphere, and drawing it as one would misrepresent both.",
  ],
} as const;

/**
 * Chapman's exponent: peak density goes as cos(chi), and critical frequency as
 * the square root of density, so fo goes as cos(chi)^0.25. Confirmed against
 * the network at 0.268 (see the header), which is why this stays at theory's
 * value instead of the fitted one.
 */
export const CHAPMAN_EXPONENT = 0.25;

/**
 * The largest solar zenith angle at which any station in the network reported
 * an F1 layer (2026-08-19, n=101 records at their own timestamps). Above this
 * the correct number of F1 layers is zero, and this site says so rather than
 * showing a gap.
 */
export const F1_MAX_SOLAR_ZENITH_DEG = 72.5;

/**
 * Nominal peak heights, used only when a sounding does not supply one.
 * The E value is the height the upstream autoscaler itself falls back to, and
 * the F1 value is the median hmF1 across the network's records that had one.
 */
export const NOMINAL_E_PEAK_KM = 110;
export const NOMINAL_F1_PEAK_KM = 190;

/**
 * Chapman scale heights. These are ASSUMED - see the limitations. An ionogram
 * scaling publishes critical frequencies and peak heights but not the E or F1
 * semi-thickness, so nothing measured constrains these two numbers and they
 * set the drawn width of the layers rather than their strength or position.
 */
export const E_SCALE_HEIGHT_KM = 8;
export const F1_SCALE_HEIGHT_KM = 45;

/**
 * Distance over which a sounding stops telling you anything about here.
 *
 * Measured, not assumed. Taking every pair of fresh stations in the network and
 * comparing their foF2 residuals about a common solar baseline (2026-08-19,
 * 26 stations, 325 pairs), the RMS difference between a pair's residuals ran:
 *
 *     0-500 km      0.29 MHz    11% of the value for two unrelated stations
 *     500-1,000 km  1.25 MHz    46%
 *     1,000-2,000   1.08 MHz    40%
 *     2,000-3,000   1.57 MHz    58%
 *     3,000-5,000   2.49 MHz    92%
 *     over 5,000    2.96 MHz   109%  - no information left
 *
 * A Gaussian with this e-folding distance gives weight 0.94 at 500 km, 0.37 at
 * 2,000 km and 0.10 at 3,000 km, which brackets the measured transition from
 * "tells you nearly everything" to "tells you nothing". The bins below
 * 1,000 km hold only 3 and 10 pairs, so this curve is the right SHAPE on thin
 * evidence rather than a precisely located one.
 */
export const ANCHOR_EFOLD_KM = 2_000;

/**
 * Beyond this the site refuses to let a sounding influence the reader's point
 * at all - though it still NAMES the nearest one, because "how far is the
 * nearest real observation" is a question with an answer at any distance.
 *
 * 3,000 km rather than the 5,000 km at which the pair difference reaches the
 * unrelated-station level, because the Gaussian weight is already below 0.10
 * out there and a 9% pull is not an anchor. Carrying it anyway produced a
 * panel that said "pulled 9% of the way toward a station 3,134 km away",
 * which advertises a correction that cannot survive its own error bars. The
 * arithmetic and the sentence now stop at the same place.
 */
export const ANCHOR_IGNORE_KM = 3_000;

export type LayerId = "D" | "E" | "F1" | "F2";

/** How a single layer in the composite got its value. */
export interface LayerProvenance {
  layer: LayerId;
  /** One sentence a reader can understand without reading this file. */
  plainSource: string;
  evidence: "empirical" | "observed" | "model" | "composite";
  /** Null where the layer is absent rather than unknown. */
  criticalFrequencyMhz: number | null;
  peakHeightKm: number | null;
  /** 0 when nothing nearby measured this layer, 1 when a station is on top of the point. */
  anchorWeight: number;
  anchorStationCode: string | null;
  anchorStationName: string | null;
  anchorDistanceKm: number | null;
  anchorAgeMinutes: number | null;
  /**
   * Set when the layer is genuinely not present, as opposed to not known.
   * F1 at night is the canonical case and the distinction is the teaching point.
   */
  absentReason: string | null;
}

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(maximum, Math.max(minimum, value));
}

/**
 * Electron density that reflects a vertically incident wave of this frequency.
 * The exact inverse of the plasma frequency relation the site already uses, so
 * a measured critical frequency becomes a density without a second convention.
 */
export function criticalFrequencyToDensityM3(criticalFrequencyMhz: number | null): number | null {
  if (criticalFrequencyMhz === null || !Number.isFinite(criticalFrequencyMhz)) return null;
  if (criticalFrequencyMhz <= 0) return null;
  return (criticalFrequencyMhz / PLASMA_FREQUENCY_MHZ_COEFFICIENT) ** 2;
}

/**
 * A Chapman alpha layer.
 *
 * Ne(h) = Nm * exp(0.5 * (1 - z - exp(-z))), z = (h - hm) / H.
 *
 * This is the standard form: it peaks at exactly Nm at h = hm, falls off
 * steeply below the peak where production runs out, and decays with the scale
 * height above it. It is the shape a layer takes when a single ionising
 * wavelength is absorbed in an isothermal atmosphere, which is why it is the
 * right description of E and F1 and NOT of F2 - F2 sits above the peak of
 * production and is shaped by transport, which is exactly what WAM-IPE models
 * and this function must not be used for.
 */
export function chapmanDensityM3(
  altitudeKm: number,
  peakDensityM3: number,
  peakHeightKm: number,
  scaleHeightKm: number,
): number | null {
  if (![altitudeKm, peakDensityM3, peakHeightKm, scaleHeightKm].every(Number.isFinite)) return null;
  if (peakDensityM3 <= 0 || scaleHeightKm <= 0) return null;
  const z = (altitudeKm - peakHeightKm) / scaleHeightKm;
  // exp(-z) overflows for a point far below the peak; the density there is
  // zero to any precision that matters, so clamp rather than return Infinity.
  if (z < -8) return 0;
  return peakDensityM3 * Math.exp(0.5 * (1 - z - Math.exp(-z)));
}

/**
 * Chapman's own prediction for a solar-produced critical frequency, scaled to
 * whatever the network says the overhead-sun value is right now.
 *
 * Returns null below the horizon: a layer produced by sunlight has no
 * Chapman value in darkness, and returning 0 would read as "measured, and
 * nothing there" rather than "not produced here".
 */
export function chapmanCriticalFrequencyMhz(
  overheadMhz: number,
  solarZenithDeg: number,
  exponent = CHAPMAN_EXPONENT,
): number | null {
  if (!Number.isFinite(overheadMhz) || overheadMhz <= 0) return null;
  if (!Number.isFinite(solarZenithDeg)) return null;
  const cosine = Math.cos((solarZenithDeg * Math.PI) / 180);
  if (cosine <= 0) return null;
  return overheadMhz * cosine ** exponent;
}

/**
 * How much a sounding this far away should be believed about here.
 *
 * Gaussian rather than exponential because the measured curve is flat close in
 * - a station 500 km away differs by only 11% of the unrelated-pair level -
 * and then falls away quickly, which is the shape a Gaussian has and a plain
 * exponential does not.
 */
export function anchorWeight(distanceKm: number, efoldKm = ANCHOR_EFOLD_KM): number {
  if (!Number.isFinite(distanceKm) || distanceKm < 0) return 0;
  if (distanceKm >= ANCHOR_IGNORE_KM) return 0;
  return clamp(Math.exp(-((distanceKm / efoldKm) ** 2)), 0, 1);
}

/** A station that reported the parameter in question, with its distance from the point. */
interface NearestResult {
  station: Sounding;
  distanceKm: number;
}

/**
 * The nearest station that actually scaled this parameter.
 *
 * Deliberately not "the nearest station": the nearest station may not have
 * scaled foE, and silently falling back to its foF2 or to a neighbour's would
 * attach one station's name to another station's number.
 */
export function nearestWith(
  point: GeographicPoint,
  stations: readonly Sounding[],
  parameter: (station: Sounding) => number | null,
): NearestResult | null {
  let best: NearestResult | null = null;
  for (const station of stations) {
    if (parameter(station) === null) continue;
    const distanceKm = greatCircleDistanceKm(point, station);
    if (best === null || distanceKm < best.distanceKm) best = { station, distanceKm };
  }
  return best;
}

/**
 * The overhead-sun critical frequency implied by every sounding in the network
 * that scaled this parameter right now.
 *
 * This is what makes the composite driven by today rather than by a table: the
 * amplitude of the Chapman layer is refitted from live soundings on every
 * release. Each station contributes fo / cos(chi)^0.25 - its own measurement
 * projected to overhead sun - and the median is taken because with as few as
 * five contributing stations a single mis-scaled ionogram would drag a mean
 * badly and a median barely at all.
 *
 * Returns null when too few stations contribute, and the caller must then draw
 * no layer rather than invent an amplitude.
 */
export function fitOverheadCriticalFrequencyMhz(
  stations: readonly Sounding[],
  subsolar: GeographicPoint,
  parameter: (station: Sounding) => number | null,
  minimumStations = 3,
): { overheadMhz: number; contributingStations: number } | null {
  const projected: number[] = [];
  for (const station of stations) {
    const value = parameter(station);
    if (value === null || value <= 0) continue;
    const zenith = solarZenithAngleDeg(station, subsolar);
    const cosine = Math.cos((zenith * Math.PI) / 180);
    // Below about 20 deg elevation the cos^0.25 projection divides by a small
    // number and turns a routine scaling error into a large amplitude error,
    // so those stations do not vote on the amplitude.
    if (cosine < 0.2) continue;
    projected.push(value / cosine ** CHAPMAN_EXPONENT);
  }
  if (projected.length < minimumStations) return null;
  projected.sort((a, b) => a - b);
  const middle = Math.floor(projected.length / 2);
  // Indexed access is checked in this project, and the guard above already
  // established that `projected` is non-empty, so the fallbacks are
  // unreachable rather than a silent default.
  const upper = projected[middle] ?? 0;
  const lower = projected[middle - 1] ?? upper;
  const overheadMhz = projected.length % 2 === 1 ? upper : (lower + upper) / 2;
  return { overheadMhz, contributingStations: projected.length };
}

/**
 * Blend a Chapman baseline toward a nearby measured value.
 *
 * A straight linear blend on the critical frequency, because that is the
 * quantity the ionosonde reports and the quantity a reader compares. Blending
 * densities instead would make a half-weight anchor land somewhere a reader
 * cannot predict from the two numbers on screen.
 */
export function blendTowardAnchor(
  baselineMhz: number | null,
  anchorMhz: number | null,
  weight: number,
): number | null {
  if (baselineMhz === null && anchorMhz === null) return null;
  if (anchorMhz === null || weight <= 0) return baselineMhz;
  // No baseline to blend into. This is the "model column not loaded" case, and
  // returning null unless the weight is exactly 1 meant a station 180 km away
  // - weight 0.996 - rendered as "not available" directly underneath a
  // sentence naming it. A measurement from inside the range where soundings
  // genuinely describe each other stands on its own; beyond half weight
  // (about 1,660 km) it does not, and the row says nothing rather than
  // presenting a distant sounding as this point's value.
  if (baselineMhz === null) return weight >= 0.5 ? anchorMhz : null;
  return baselineMhz + (anchorMhz - baselineMhz) * clamp(weight, 0, 1);
}

export interface CompositeInput {
  point: GeographicPoint;
  time: Date;
  stations: readonly Sounding[];
  /** Measured GOES 0.1-0.8 nm irradiance, for the D region. Null when unavailable. */
  xrayFluxWm2: number | null;
  /** WAM-IPE's foF2 and hmF2 over this point, when the column has been loaded. */
  modelFoF2Mhz: number | null;
  modelHmF2Km: number | null;
  /** D-region shape from the existing empirical layer. */
  dRegionEffectiveHeightKm: number;
  dRegionBetaPerKm: number;
}

export interface CompositeProfile {
  solarZenithDeg: number;
  layers: LayerProvenance[];
  /** The single sentence shown under the profile. */
  evidenceNote: string;
  /** Distance to the nearest fresh sounding of any kind, for the honesty banner. */
  nearestStationKm: number | null;
  nearestStationName: string | null;
}

/**
 * Build the four-layer description of one point at one time.
 *
 * Every layer comes back with its own provenance, because the whole point of
 * this feature is that a reader can see that F2 is NOAA's model, E is a
 * physical shape pinned to real soundings, and D is an empirical fit driven by
 * a measured flux. A single badge over the top of all four would hide exactly
 * the thing worth teaching.
 */
export function compositeProfile(input: CompositeInput): CompositeProfile {
  const subsolar = dRegionSubsolarPoint(input.time);
  const solarZenithDeg = solarZenithAngleDeg(input.point, subsolar);
  const layers: LayerProvenance[] = [];

  // ---- D -----------------------------------------------------------------
  // Unchanged from the empirical layer the site already ships. It has no
  // sounding anchor and never will: an ionosonde cannot measure the D region.
  // Its sounding frequencies pass straight through, and the D region shows up
  // on an ionogram as absorption - as the echo it took away - not as a trace.
  // That is a fact worth saying out loud rather than an omission.
  layers.push({
    layer: "D",
    plainSource:
      "Empirical Wait-Spies profile, driven by the sun's angle here and the measured "
      + "GOES X-ray flux. No ionosonde can measure the D region - its radio waves pass "
      + "straight through and the D region shows up only as the echo it absorbs.",
    evidence: "empirical",
    criticalFrequencyMhz: null,
    peakHeightKm: input.dRegionEffectiveHeightKm,
    anchorWeight: 0,
    anchorStationCode: null,
    anchorStationName: null,
    anchorDistanceKm: null,
    anchorAgeMinutes: null,
    absentReason: null,
  });

  // ---- E and F1: Chapman shape, network amplitude, local anchor -----------
  const eFit = fitOverheadCriticalFrequencyMhz(input.stations, subsolar, (s) => s.foEMhz);
  const f1Fit = fitOverheadCriticalFrequencyMhz(input.stations, subsolar, (s) => s.foF1Mhz);

  const eNearest = nearestWith(input.point, input.stations, (s) => s.foEMhz);
  const f1Nearest = nearestWith(input.point, input.stations, (s) => s.foF1Mhz);

  const eBaseline = eFit ? chapmanCriticalFrequencyMhz(eFit.overheadMhz, solarZenithDeg) : null;
  const eWeight = eNearest ? anchorWeight(eNearest.distanceKm) : 0;
  const eValue = blendTowardAnchor(eBaseline, eNearest?.station.foEMhz ?? null, eWeight);

  layers.push({
    layer: "E",
    plainSource: eNearest && eWeight > 0.05
      ? `Chapman layer shaped by physics, pulled ${(eWeight * 100).toFixed(0)}% of the way toward the `
        + `measured foE at ${eNearest.station.name}, ${Math.round(eNearest.distanceKm).toLocaleString()} km away.`
      : eBaseline !== null
        ? "Chapman layer shaped by physics, scaled to the whole network's soundings right now. "
          + "No station near enough to anchor it locally."
        : "No E layer drawn: too few stations scaled an foE to set its strength.",
    evidence: eWeight > 0.05 ? "composite" : eBaseline !== null ? "composite" : "model",
    criticalFrequencyMhz: eValue,
    peakHeightKm: eWeight > 0.5 && eNearest?.station.hmEKm != null && !eNearest.station.eHeightIsNominal
      ? eNearest.station.hmEKm
      : NOMINAL_E_PEAK_KM,
    anchorWeight: eWeight,
    anchorStationCode: eNearest?.station.code ?? null,
    anchorStationName: eNearest?.station.name ?? null,
    anchorDistanceKm: eNearest?.distanceKm ?? null,
    anchorAgeMinutes: eNearest?.station.ageMinutes ?? null,
    absentReason: eValue === null && solarZenithDeg >= 90
      ? "The E layer is produced by sunlight and has largely recombined here after sunset."
      : null,
  });

  // F1's absence in darkness is a FACT, and it is reported as one. The site
  // never shows a null F1 as missing data.
  const f1Absent = solarZenithDeg > F1_MAX_SOLAR_ZENITH_DEG;
  const f1Baseline = f1Fit && !f1Absent
    ? chapmanCriticalFrequencyMhz(f1Fit.overheadMhz, solarZenithDeg)
    : null;
  const f1Weight = f1Nearest && !f1Absent ? anchorWeight(f1Nearest.distanceKm) : 0;
  const f1Value = f1Absent
    ? null
    : blendTowardAnchor(f1Baseline, f1Nearest?.station.foF1Mhz ?? null, f1Weight);

  layers.push({
    layer: "F1",
    plainSource: f1Absent
      ? "No F1 layer here now. F1 is a daytime-only layer: it needs a high sun and merges "
        + "into F2 as the sun drops."
      : f1Nearest && f1Weight > 0.05
        ? `Chapman layer shaped by physics, pulled ${(f1Weight * 100).toFixed(0)}% of the way toward the `
          + `measured foF1 at ${f1Nearest.station.name}, ${Math.round(f1Nearest.distanceKm).toLocaleString()} km away.`
        : "Chapman layer shaped by physics, scaled to the whole network's daylit soundings. "
          + "No station near enough to anchor it locally.",
    evidence: "composite",
    criticalFrequencyMhz: f1Value,
    peakHeightKm: f1Absent
      ? null
      : f1Weight > 0.5 && f1Nearest?.station.hmF1Km != null
        ? f1Nearest.station.hmF1Km
        : NOMINAL_F1_PEAK_KM,
    anchorWeight: f1Weight,
    anchorStationCode: f1Absent ? null : f1Nearest?.station.code ?? null,
    anchorStationName: f1Absent ? null : f1Nearest?.station.name ?? null,
    anchorDistanceKm: f1Absent ? null : f1Nearest?.distanceKm ?? null,
    anchorAgeMinutes: f1Absent ? null : f1Nearest?.station.ageMinutes ?? null,
    absentReason: f1Absent
      ? `The sun is ${solarZenithDeg.toFixed(0)} deg from overhead here. No station in the network `
        + `has ever reported an F1 layer above ${F1_MAX_SOLAR_ZENITH_DEG} deg, so this is the layer `
        + `being absent, not a gap in the data.`
      : null,
  });

  // ---- F2: the model, anchored only where a sounding is genuinely near ----
  const f2Nearest = nearestWith(input.point, input.stations, (s) => s.foF2Mhz);
  const f2Weight = f2Nearest ? anchorWeight(f2Nearest.distanceKm) : 0;
  const f2Value = blendTowardAnchor(input.modelFoF2Mhz, f2Nearest?.station.foF2Mhz ?? null, f2Weight);
  /**
   * Whether the number in this row IS a station's own measurement.
   *
   * CORRECTNESS FIX 2026-09-04. The badge and the sentence used to switch on
   * `f2Weight > 0.05`, which reaches out to `ANCHOR_IGNORE_KM` — 3,000 km. But
   * `blendTowardAnchor` only hands the anchor's value back with no model to
   * blend into at `weight >= 0.5`, about 1,665 km. Between the two thresholds
   * the row printed `criticalFrequencyMhz: null` while its badge read OBSERVED
   * and its sentence read "Measured foF2 at X, N km away" — a measurement named
   * over a value that is not there. Both now switch on the SAME gate the value
   * does, so the badge cannot outrun the number it is badging.
   *
   * (What is still open, and is the owner's call rather than this fix's: whether
   * a sounding up to 1,665 km away should read OBSERVED for the clicked point at
   * all. This module's own header argues it should not — "it is not OBSERVED —
   * most of the globe has no sounding within thousands of kilometres" — but the
   * 0.5 gate is a documented, reasoned choice and is left standing.)
   */
  const f2AnchorStandsAlone = input.modelFoF2Mhz === null && f2Weight >= 0.5;

  layers.push({
    layer: "F2",
    plainSource: input.modelFoF2Mhz === null
      ? f2AnchorStandsAlone && f2Nearest
        ? `Measured foF2 at ${f2Nearest.station.name}, ${Math.round(f2Nearest.distanceKm).toLocaleString()} km away. `
          + "The NOAA model column is not loaded, so there is nothing to combine it with."
        : "Not available: the NOAA model column is not loaded and no sounding is near enough to stand in for it."
      : f2Weight > 0.05 && f2Nearest
        ? `NOAA WAM-IPE model, pulled ${(f2Weight * 100).toFixed(0)}% of the way toward the measured `
          + `foF2 at ${f2Nearest.station.name}, ${Math.round(f2Nearest.distanceKm).toLocaleString()} km away.`
        : "NOAA WAM-IPE model column over this point. No sounding near enough to correct it.",
    evidence: f2AnchorStandsAlone ? "observed" : f2Weight > 0.05 ? "composite" : "model",
    criticalFrequencyMhz: f2Value,
    peakHeightKm: input.modelHmF2Km
      ?? (f2Weight > 0.5 ? f2Nearest?.station.hmF2Km ?? null : null),
    anchorWeight: f2Weight,
    anchorStationCode: f2Nearest?.station.code ?? null,
    anchorStationName: f2Nearest?.station.name ?? null,
    anchorDistanceKm: f2Nearest?.distanceKm ?? null,
    anchorAgeMinutes: f2Nearest?.station.ageMinutes ?? null,
    absentReason: null,
  });

  const nearestAny = nearestWith(input.point, input.stations, (s) => s.foF2Mhz ?? s.foEMhz ?? null);

  return {
    solarZenithDeg,
    layers,
    nearestStationKm: nearestAny?.distanceKm ?? null,
    nearestStationName: nearestAny?.station.name ?? null,
    evidenceNote: compositeEvidenceNote(nearestAny?.distanceKm ?? null),
  };
}

/**
 * The sentence shown wherever a composite profile is displayed.
 *
 * It changes with distance because the honest claim changes with distance. At
 * 5,000 km from the nearest sounding this is a physical shape scaled by a
 * network average, and saying anything warmer than that would be a claim the
 * data does not support.
 */
export function compositeEvidenceNote(nearestStationKm: number | null): string {
  const stem =
    "COMPOSITE: not a measurement and not a single model. The D region is an empirical "
    + "fit driven by measured X-ray flux, E and F1 are Chapman layers whose strength "
    + "comes from ionosonde soundings taken in the last three hours, and F2 is NOAA's "
    + "WAM-IPE model. ";
  if (nearestStationKm === null) {
    return stem + "No sounding is available at all, so nothing here is anchored to a measurement.";
  }
  if (nearestStationKm <= 500) {
    return stem + `The nearest sounding is ${Math.round(nearestStationKm)} km away, close enough that it `
      + "constrains the layers over this point directly.";
  }
  if (nearestStationKm <= 2_000) {
    return stem + `The nearest sounding is ${Math.round(nearestStationKm).toLocaleString()} km away. It still `
      + "carries real information about this point, but it is a regional correction rather than a local one.";
  }
  if (nearestStationKm <= ANCHOR_IGNORE_KM) {
    return stem + `The nearest sounding is ${Math.round(nearestStationKm).toLocaleString()} km away, far enough `
      + "that it barely constrains this point. The E and F1 layers here are essentially the network-wide "
      + "solar fit, not a local measurement.";
  }
  return stem + `The nearest sounding is ${Math.round(nearestStationKm).toLocaleString()} km away - beyond the `
    + "range at which soundings tell you anything about each other. Nothing here is locally anchored.";
}

/* ─────────────────────────────────────────────────────────────────────────
   Drawing the stack.

   The reader asked to see D / E / F1 / F2 at their real heights, so height is
   the axis and it is linear in kilometres. It is NOT a density profile curve:
   a curve through four points, two of which are a fitted Chapman amplitude,
   would look like a measured profile and this feature must never look more
   certain than it is. Four labelled bars at four heights cannot be mistaken
   for a sounding.

   Bar LENGTH is the critical frequency, because that is the number an
   operator plans against and the number the ionosonde actually reports. Bar
   OPACITY is the anchor weight, so a layer nobody measured near this point is
   visibly faint - that is requirement 3 (the anchoring must visibly weaken
   where the network is thin) expressed in the picture rather than only in the
   prose.
   ───────────────────────────────────────────────────────────────────────── */

/** Altitude range drawn. 400 km is above every hmF2 the network reported (max
 *  306 km on the measured frame) with room for a storm-lifted F2.
 *
 *  CORRECTNESS FIX 2026-09-08. The floor was 60 km, described as "the bottom of
 *  the D region", and `yFor` clamps to it. The D bar is placed at the layer's
 *  own `peakHeightKm`, which for D is the Wait-Spies effective reflection
 *  height from `d-region-empirical.ts` — and that height comes DOWN under a
 *  flare, to 62.5 km at X1 and to the model's floor of 53 km at X45 in full
 *  daylight. So from about X1.4 upward the row printed "D · 58 km" (or 53) in
 *  words while the bar was drawn at 60, and above the E bar's true separation.
 *  50 km puts the whole published domain of the model on the axis with room to
 *  spare, so the drawing and the number agree at every flux the model accepts.
 */
export const LADDER_MIN_KM = 50;
export const LADDER_MAX_KM = 400;

/**
 * Full scale for bar length. 12 MHz is above every foF2 in the network on the
 * measured frame (max 10.35 MHz at Boa Vista) so a normal day never clips, and
 * low enough that a 2.3 MHz night F2 is still a visible bar rather than a dot.
 */
export const LADDER_FULL_SCALE_MHZ = 12;

export interface LadderBar {
  layer: LayerId;
  /** Vertical position in view units, top-down. */
  y: number;
  /** Bar length in view units. Zero where the layer has no critical frequency. */
  width: number;
  /** 0..1 anchor weight, used as opacity by the renderer. */
  anchorWeight: number;
  label: string;
  /** The right-hand value text, or the absence sentence. */
  valueText: string;
  /** True when the layer is genuinely not there, which is drawn differently from a zero. */
  absent: boolean;
  evidence: LayerProvenance["evidence"];
}

export interface LadderGeometry {
  width: number;
  height: number;
  axisX: number;
  bars: LadderBar[];
  /** Tick positions for the altitude axis. */
  ticks: { y: number; km: number }[];
}

/**
 * Lay out the ladder.
 *
 * Pure, and exported, because this project has repeatedly shipped drawing code
 * that no test could reach: the geometry is checked here and the DOM writer
 * that consumes it stays trivial enough to read.
 */
export function ladderGeometry(
  layers: readonly LayerProvenance[],
  width = 232,
  height = 168,
): LadderGeometry {
  const top = 8;
  const bottom = height - 16;
  // The altitude ticks live at the far left and the layer names immediately
  // left of the axis. At the original 30 units they shared the same 30 px and
  // "300" sat on top of "F2" whenever the F2 peak landed near a tick, which it
  // does on most days. 46 leaves the ticks x=2..22 and the names ending at
  // x=40, with a clear gap between them.
  const axisX = 46;
  const usableWidth = width - axisX - 62;

  const yFor = (km: number) => {
    const clamped = Math.min(LADDER_MAX_KM, Math.max(LADDER_MIN_KM, km));
    return bottom - ((clamped - LADDER_MIN_KM) / (LADDER_MAX_KM - LADDER_MIN_KM)) * (bottom - top);
  };

  const bars: LadderBar[] = layers.map((layer) => {
    const fo = layer.criticalFrequencyMhz;
    const absent = layer.absentReason !== null;
    return {
      layer: layer.layer,
      y: yFor(layer.peakHeightKm ?? nominalHeightFor(layer.layer)),
      // A layer with no critical frequency gets a fixed short band rather than
      // a bar of length zero. The D region is the permanent case: it has no
      // critical frequency and never will, because it absorbs rather than
      // reflects, and a 2 px stub at the axis read as "nothing is here" when
      // the true statement is "something is here that this axis cannot show".
      width: fo === null ? 26 : Math.max(2, (Math.min(fo, LADDER_FULL_SCALE_MHZ) / LADDER_FULL_SCALE_MHZ) * usableWidth),
      // The D region has no critical frequency and no sounding can give it one,
      // so it draws at the empirical layer's own confidence rather than at an
      // anchor weight of zero, which would read as "we have no idea".
      anchorWeight: layer.layer === "D" ? 0.55 : layer.anchorWeight,
      label: layer.layer,
      valueText: absent
        ? "none now"
        : fo === null
          ? layer.layer === "D" ? "absorbs, does not reflect" : "not available"
          : `${fo.toFixed(2)} MHz`,
      absent,
      evidence: layer.evidence,
    };
  });

  const ticks = [100, 200, 300, 400].map((km) => ({ y: yFor(km), km }));

  return { width, height, axisX, bars, ticks };
}

function nominalHeightFor(layer: LayerId): number {
  // Only reached for a layer with no height at all, which is drawn faint at its
  // nominal place rather than dropped - a missing bar would read as "no layer".
  if (layer === "D") return 75;
  if (layer === "E") return NOMINAL_E_PEAK_KM;
  if (layer === "F1") return NOMINAL_F1_PEAK_KM;
  return 300;
}
