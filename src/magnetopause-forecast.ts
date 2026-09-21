import { shueBoundary } from "./magnetopause";

/**
 * The magnetosphere past the last measurement: NOT FORECAST, and therefore
 * NOT DRAWN.
 *
 * ## What this module used to be, and why it is not that any more
 *
 * It used to build a *forecast band*: two Shue (1998) surfaces, one at the
 * most compressed corner of the measured driver envelope and one at the most
 * relaxed, joined into a closed body and drawn past the end of the measured
 * record. The intent was honest — the width of the band was meant to BE the
 * forecast, a picture of ignorance rather than a confident boundary.
 *
 * It did not read that way. Sean, on the shipped build:
 *
 *   *"I took a screenshot of the magnetosphere. Its current and past
 *   depictions are great. But what the fuck am I seeing in the future? It
 *   looks ridiculous. If we can't get a forecasted magnetosphere, just leave
 *   it off. Have it turn off and let the legend say as much — no forecast."*
 *
 * Two commits had already tried to rescue it. `a0bf46f` built the band;
 * `a810bef` re-inked it as a Fresnel rim after it rendered as a disc of light.
 * Neither touched what was actually wrong, which was not the ink and not the
 * numbers: it was that **a boundary with nothing inside it is not a
 * magnetosphere.** Past the last measurement every other part of the picture —
 * the traced field lines, the cusps, the plasma field, the drivers on the rail
 * — correctly goes away, and what was left was a bare open bowl reaching 597
 * scene units against a camera framed for 266, stopping at a 110-degree zenith
 * cut, with the Earth a speck inside it. Whatever the caption said, the
 * picture said "here is the magnetosphere", and it was a shape nobody had
 * measured.
 *
 * ## Is a real forecast obtainable? Measured 2026-08-21, and the answer is no
 *
 * The Shue magnetopause needs exactly two numbers: solar-wind dynamic pressure
 * and IMF Bz. What NOAA publishes ahead of time is:
 *
 *   - **The three-day planetary K index forecast.** Kp is the geomagnetic
 *     RESPONSE, not a driver. There are published statistical Kp-to-Bz
 *     relations; using one here would mean inventing the number this layer
 *     exists to report. Refusing that conversion has always been the point.
 *   - **WSA-ENLIL at Earth** (`services.swpc.noaa.gov/json/enlil_time_series.json`),
 *     a genuine five-day solar-wind forecast carrying density, radial speed
 *     and a magnetic field. It is not enough, and this was measured rather
 *     than assumed. Over the 48 hours ending 2026-08-21T06:52Z, against this
 *     site's own propagated L1 record, 1,213 paired samples:
 *
 *       - ENLIL's Bz at Earth held between **-0.05 and -0.03 nT**, standard
 *         deviation **0.00 nT**, while the measured IMF Bz swung **-6.17 to
 *         +5.60 nT** with a standard deviation of 2.43 nT. It carries none of
 *         the variation that moves the boundary. That is not a defect in the
 *         model: the operational cone CMEs it propagates carry no internal
 *         magnetic field at all, so it has no Bz to give.
 *       - ENLIL's dynamic pressure ranged **1.10 to 1.30 nPa** against a
 *         measured **1.02 to 5.96 nPa** — correlated in sign (r = 0.72) but
 *         biased low by 2.1x and carrying 6% of the real variance. It missed
 *         the 5.96 nPa compression entirely.
 *
 *     Driving Shue from ENLIL would therefore draw an almost perfectly
 *     constant nose near 11 Earth radii for three days: a confident line that
 *     is a fiction, which is worse than the band, not better.
 *   - **The propagated L1 solar wind**, which reaches about 40 minutes past
 *     now. That is the travel time from the L1 spacecraft to Earth. It is a
 *     measurement in transit, not a forecast.
 *
 * **Arrival time is forecastable days ahead. Severity is not, because it turns
 * on the internal magnetic structure of whatever is arriving and nothing
 * images that. The only sensor that knows sits at L1, and it buys under an
 * hour.** That is the best teaching point in the whole subject, and it is now
 * made by the layer going off and saying so, rather than by a shape.
 *
 * ## So what this module does now
 *
 * It decides ONE thing: is the selected instant past the end of the measured
 * driver record? If it is, it returns the facts the card needs in order to say
 * plainly that there is no forecast — when the measurements stop, how far the
 * measured boundary actually moved while they were being taken, and where to
 * scrub back to. It draws nothing and it hands the globe nothing to draw.
 */

/** One row of NOAA's published three-day Kp forecast. */
export interface KpForecastRow {
  time: string | null;
  kp: number | null;
  status: "observed" | "estimated" | "predicted" | null;
}

export interface ForecastDriverSample {
  validAt: string;
  bzGsmNt: number | null;
  dynamicPressureNpa: number | null;
}

/**
 * What the site actually MEASURED, and over what window.
 *
 * Kept — as a statement about the past — because it is the evidence for the
 * refusal. A reader is owed the size of the thing that is missing: the nose
 * moved several Earth radii in two days on the site's own record, so a single
 * drawn boundary three days out would not be approximately right, it would be
 * unrelated to the answer.
 */
export interface MeasuredDriverRecord {
  /** The most southward Bz in the measured record, nT. */
  minimumBzNt: number;
  /** The most northward, nT. */
  maximumBzNt: number;
  /** The lowest measured dynamic pressure, nPa. */
  minimumDynamicPressureNpa: number;
  /** The highest. */
  maximumDynamicPressureNpa: number;
  /** How many measured samples the record came from. */
  sampleCount: number;
  /** The measured window. */
  fromIso: string;
  toIso: string;
}

/**
 * The reason there is nothing on screen, past the last measurement.
 *
 * Named for what it is. There is no `compressed`, no `relaxed` and no geometry
 * anywhere on this object on purpose: nothing downstream can accidentally draw
 * one.
 */
export interface MagnetopauseNoForecast {
  /** The last instant the measured record covers. */
  measuredToIso: string;
  /** How far past that the selected instant is, in hours. */
  hoursPastMeasurement: number;
  /** What was measured, and over what window. */
  measured: MeasuredDriverRecord;
  /**
   * How far the modelled nose actually MOVED across the measured record, in
   * Earth radii — the compressed corner and the relaxed corner. A statement
   * about the recorded past. It is never plotted, and it is never offered as a
   * range the future boundary lies in. Null if Shue cannot be evaluated at
   * either corner.
   */
  measuredNoseRangeRe: readonly [number, number] | null;
  /** NOAA's forecast Kp for this hour, if the published rows cover it. */
  forecastKp: number | null;
  /** Whether that Kp row was a prediction rather than an observation. */
  forecastKpIsPredicted: boolean;
}

/**
 * The measured envelope, or null when the record is empty or unusable.
 *
 * Returns null rather than a default: a statement drawn from nothing would be
 * a claim about nothing.
 */
export function measuredDriverRecord(
  series: readonly ForecastDriverSample[],
): MeasuredDriverRecord | null {
  let minimumBzNt = Infinity;
  let maximumBzNt = -Infinity;
  let sampleCount = 0;
  let latestMs = -Infinity;
  let earliestMs = Infinity;
  let minimumDynamicPressureNpa = Infinity;
  let maximumDynamicPressureNpa = -Infinity;
  let anyPressure = false;
  for (const row of series) {
    const at = Date.parse(row.validAt);
    if (!Number.isFinite(at)) continue;
    if (row.bzGsmNt === null || !Number.isFinite(row.bzGsmNt)) continue;
    sampleCount += 1;
    minimumBzNt = Math.min(minimumBzNt, row.bzGsmNt);
    maximumBzNt = Math.max(maximumBzNt, row.bzGsmNt);
    earliestMs = Math.min(earliestMs, at);
    latestMs = Math.max(latestMs, at);
    if (row.dynamicPressureNpa !== null && Number.isFinite(row.dynamicPressureNpa)
      && row.dynamicPressureNpa > 0) {
      anyPressure = true;
      minimumDynamicPressureNpa = Math.min(minimumDynamicPressureNpa, row.dynamicPressureNpa);
      maximumDynamicPressureNpa = Math.max(maximumDynamicPressureNpa, row.dynamicPressureNpa);
    }
  }
  if (sampleCount === 0 || !anyPressure) return null;
  return {
    minimumBzNt,
    maximumBzNt,
    minimumDynamicPressureNpa,
    maximumDynamicPressureNpa,
    sampleCount,
    fromIso: new Date(earliestMs).toISOString(),
    toIso: new Date(latestMs).toISOString(),
  };
}

/** NOAA's forecast Kp for an instant, from the published three-day rows. */
export function forecastKpAt(
  rows: readonly KpForecastRow[],
  atMs: number,
): { kp: number; predicted: boolean } | null {
  let best: { kp: number; predicted: boolean; atMs: number } | null = null;
  for (const row of rows) {
    if (row.kp === null || !Number.isFinite(row.kp) || row.time === null) continue;
    const rowMs = Date.parse(row.time);
    if (!Number.isFinite(rowMs) || rowMs > atMs) continue;
    // Three-hourly rows: a row governs the three hours that follow it.
    if (atMs - rowMs > 3 * 3_600_000) continue;
    if (!best || rowMs > best.atMs) {
      best = { kp: row.kp, predicted: row.status === "predicted", atMs: rowMs };
    }
  }
  return best ? { kp: best.kp, predicted: best.predicted } : null;
}

/**
 * Is the selected instant past the measured record? If so, the facts the card
 * needs in order to say there is no forecast.
 *
 * Null in two cases, and neither of them draws anything either:
 *
 *   - the instant is NOT past the measured record, in which case the ordinary
 *     measured boundary is the right thing on screen and this must stay out of
 *     its way;
 *   - there is no measured record at all, in which case the layer's existing
 *     "the propagated solar-wind drivers are missing" state is the true one. A
 *     gap in the feed is a different fact from the end of the record, and
 *     saying "no forecast" about a feed outage would be a lie about which of
 *     the two went wrong.
 */
export function magnetopauseNoForecastAt(
  series: readonly ForecastDriverSample[],
  kpRows: readonly KpForecastRow[],
  atMs: number,
): MagnetopauseNoForecast | null {
  const measured = measuredDriverRecord(series);
  if (!measured) return null;
  const measuredToMs = Date.parse(measured.toIso);
  if (!(atMs > measuredToMs)) return null;

  // Both corners of what was RECORDED. Southward Bz and high pressure push the
  // nose in; northward Bz and low pressure let it out. This is how far the
  // boundary is known to have moved while it was being watched — the size of
  // the thing that is not forecast, not a range it will be found in.
  const compressed = shueBoundary(measured.maximumDynamicPressureNpa, measured.minimumBzNt);
  const relaxed = shueBoundary(measured.minimumDynamicPressureNpa, measured.maximumBzNt);
  const measuredNoseRangeRe = compressed && relaxed
    ? ([compressed.subsolarStandoffRe, relaxed.subsolarStandoffRe] as const)
    : null;

  const kp = forecastKpAt(kpRows, atMs);
  return {
    measuredToIso: measured.toIso,
    hoursPastMeasurement: (atMs - measuredToMs) / 3_600_000,
    measured,
    measuredNoseRangeRe,
    forecastKp: kp?.kp ?? null,
    forecastKpIsPredicted: kp?.predicted ?? false,
  };
}

/**
 * The sentence the card leads with, and the whole of the ruling in one place.
 *
 * Written here rather than in the view so the claim and the numbers behind it
 * cannot drift apart, and so a test can read the exact words a reader sees.
 */
export function noForecastSentence(state: MagnetopauseNoForecast): string {
  const hours = (Date.parse(state.measured.toIso) - Date.parse(state.measured.fromIso)) / 3_600_000;
  // CORRECTNESS FIX 2026-09-04: "that alone" was wrong, and it named the
  // smaller of the two causes. `measuredNoseRangeRe` is Shue evaluated at the
  // COMBINED corners — `shueBoundary(maxPd, minBz)` and `shueBoundary(minPd,
  // maxBz)` — so the span is the pressure swing plus the Bz swing, and the
  // pressure dominates. Measured on the module's own 48-hour envelope (Pd
  // 1.02–5.96 nPa, Bz −6.17…+5.60 nT): combined span 3.32 Re, pressure alone
  // 2.66 Re, Bz alone 0.63–0.82 Re depending on which pressure it is held at.
  // The REFUSAL is still right — ENLIL carries no Bz — but the number handed to
  // the reader as Bz's contribution was mostly the pressure's.
  const moved = state.measuredNoseRangeRe
    ? `Over the ${hours.toFixed(0)} hours this site did measure `
      + `(${state.measured.sampleCount.toLocaleString()} samples), IMF Bz swung from `
      + `${state.measured.minimumBzNt.toFixed(1)} to ${state.measured.maximumBzNt.toFixed(1)} nT `
      + `and dynamic pressure from ${state.measured.minimumDynamicPressureNpa.toFixed(1)} to `
      + `${state.measured.maximumDynamicPressureNpa.toFixed(1)} nPa, and between them they moved the modelled nose `
      + `between ${state.measuredNoseRangeRe[0].toFixed(1)} and ${state.measuredNoseRangeRe[1].toFixed(1)} Earth radii — `
      + "most of that swing is the pressure, and the tilt is the part nobody forecasts. "
      + "That is the size of what is missing here, and it is why a single drawn boundary three days out would not be "
      + "roughly right — it would be unrelated to the answer. "
    : "";
  return "There is no forecast of the magnetosphere, so nothing is drawn. "
    + "Where the boundary sits is set almost entirely by the north–south tilt of the magnetic field in the solar wind "
    + "arriving at Earth, and nobody forecasts that: it depends on the internal magnetic structure of whatever has left "
    + "the Sun, and no instrument images that structure on the way. It is learned when the wind crosses the L1 spacecraft "
    + "about 1.5 million km upstream, and that buys under an hour. "
    + moved
    + "NOAA does forecast the ACTIVITY three days ahead — the planetary K index — but that is the Earth's response, not "
    + "the driver, and converting it back into a boundary position would be inventing the number this layer exists to "
    + "report. NOAA's WSA-ENLIL wind forecast runs five days ahead and carries a speed and a density, but the CMEs it "
    + "propagates carry no internal magnetic field, so it has no north–south tilt to give. "
    + "Arrival time is forecastable days ahead; severity is not. An empty region is what honest missing data looks like — "
    + "scrub back and the measured boundary comes straight back with it.";
}
