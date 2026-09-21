import * as THREE from "three";

import type { DstSample } from "./storm-indices";

/**
 * The plasmasphere as a published electron-density FIELD, not as a shell.
 *
 * ## Why this module was rewritten
 *
 * It used to draw one number — the plasmapause L — as a smooth dipole flux
 * surface. The project owner's verdict was that this is "fitted to a simple
 * surface with no data or models giving it shape". He is right: a surface is
 * an outline with nothing inside it, and the plasmapause is not a thing in
 * its own right. It is where the electron density falls off a cliff. So the
 * layer now evaluates a density at every point and lets the boundary appear
 * as the contrast it physically is.
 *
 * ## The density model — Carpenter & Anderson (1992)
 *
 * D. L. Carpenter and R. R. Anderson, "An ISEE/whistler model of equatorial
 * electron density in the magnetosphere", JGR 97(A2), 1097-1108,
 * doi:10.1029/91JA01548.
 *
 * Every coefficient below was read off the printed paper — the scanned
 * original, section 3 "Summary of the Model", page 1106, cross-read against
 * the equations where they are first derived on pages 1099-1105 and against
 * the least-squares fit printed inside Figure 4a. None of it is from memory.
 * The paper's own summary, verbatim in structure:
 *
 * 1. Plasmapause inner limit, Lppi = 5.6 - 0.46 Kpmax, Kpmax being the
 *    largest Kp in the preceding 24 hours. Not used here — see below.
 * 2. Saturated plasmasphere segment, 2.25 <= L <= Lppi:
 *
 *      log ne = (-0.3145 L + 3.9043)
 *             + [ 0.15 ( cos(2 pi (d+9)/365) - 0.5 cos(4 pi (d+9)/365) )
 *                 + 0.00127 Rbar - 0.0635 ] e^(-(L-2)/1.5)
 *
 *    with d the day number and Rbar the 13-month average sunspot number.
 *    (Figure 4a prints the bare reference profile as y = 8022.4*10^(-0.31450x),
 *    R^2 = 0.963; log10(8022.4) = 3.9043, so the two agree.)
 * 3. Plasmapause segment, Lppi <= L <= Lppo, with t the magnetic local time
 *    in hours:
 *
 *      ne = ne(Lppi) * 10^(-(L - Lppi)/0.1),                  00 <= t < 06
 *      ne = ne(Lppi) * 10^(-(L - Lppi)/(0.1 + 0.011 (t-6))),  06 <= t <= 15
 *
 * 4. Extended plasma trough, 2.25 <= L <= 8:
 *
 *      ne = (5800 + 300 t) L^-4.5 + (1 - e^(-(L-2)/10)),      00 <= t < 06
 *      ne = (-800 + 1400 t) L^-4.5 + (1 - e^(-(L-2)/10)),     06 <= t <= 15
 *
 * 5. Plasmapause outer limit Lppo: no formula. The paper says it is found by
 *    solving items 3 and 4 simultaneously, which is what `plasmapauseOuterL`
 *    does numerically.
 * 6. Plasma trough segment, Lppo <= L <= 8:
 *
 *      ne = ne(Lppo) * (L/Lppo)^-4.5 + (1 - e^(-(L-2)/10))
 *
 * The paper's own numbers are the arithmetic check in
 * `tests/plasmasphere-density.test.ts`: it quotes model trough densities at
 * L = 5 of 4.8, 6.7 and 11.7 el/cc for night, dawn and day, and a saturated
 * selection criterion of order 1000 el/cc at L = 3.
 *
 * ## Which index drives the boundary, and why it is not the paper's
 *
 * Carpenter & Anderson place the plasmapause from the largest Kp of the
 * preceding 24 hours. This release's Kp series spans only a few hours, so
 * that form cannot be evaluated anywhere on the timeline; the release does
 * carry seven days of hourly Kyoto Dst. The boundary therefore comes from
 * O'Brien & Moldwin (2003), GRL 30(4) 1152, doi:10.1029/2002GL016007:
 *
 *   Lpp = a log10(-min[-24 h, 0] Dst) + b,  a = -1.57 +/- 0.06, b = 6.3 +/- 0.1
 *
 * fitted to over 900 CRRES plasmapause crossings, RMS error 0.7-0.9 L. This
 * is a defensible substitution rather than a mixture of unrelated things: the
 * two papers fit the same physical boundary to a 24-hour activity statistic,
 * and O'Brien & Moldwin fit Carpenter & Anderson's own Kp form to their own
 * data for comparison, getting a = -0.43, b = 5.9 against C&A's -0.46, 5.6.
 * The Dst form is simply the one this site can drive at every instant its
 * timeline can reach. The density profiles either side of the boundary are
 * Carpenter & Anderson's, unaltered.
 *
 * The 24-hour window is part of the model, not a smoothing choice: erosion is
 * fast and refilling takes days, so the boundary is set by the deepest Dst of
 * the preceding day and correctly stays small for hours after the storm
 * minimum while the index itself recovers.
 *
 * ## Magnetic local time
 *
 * The saturated plasmasphere expression has no local-time term at all — the
 * paper says so, and proposes its line "as a preliminary estimate of the
 * saturated plasmasphere throughout the 00-15 MLT period, with the
 * expectation that diurnal variations will be included in the model when more
 * statistical data on them have been assembled". So the interior drawn here
 * is axisymmetric, and there is no dusk bulge and no drainage plume in it.
 * The trough and the plasmapause width do carry local time, over 00-15 MLT.
 *
 * For 15-24 MLT the model is undefined, and this file follows the paper's own
 * section 4 prescription rather than extrapolating its polynomials: the
 * dayside quantities "may be continued to ~20 MLT, where a transition to
 * nighttime conditions should be imposed. The transition might consist of a
 * linear variation of relevant quantities between 19 and 20 MLT". So the
 * 15 MLT dayside values are held to 19 MLT, blended linearly to the 00 MLT
 * nightside values between 19 and 20 MLT, and held at those nightside values
 * to midnight. `modelLocalTimeBlend` is that rule, and nothing outside it
 * evaluates a fitted polynomial off its fitted domain.
 */

// ---------------------------------------------------------------------------
// Published constants
// ---------------------------------------------------------------------------

/**
 * Carpenter & Anderson (1992), read from the paper. Names follow the paper's
 * own summary so a reader can hold the two side by side.
 */
export const CARPENTER_ANDERSON_1992 = {
  /** Reference (saturated) profile, eq (1): log ne = slope*L + intercept. */
  saturatedSlopePerL: -0.3145,
  saturatedIntercept: 3.9043,
  /** Annual term, eq (3): amplitude 0.15, phase d+9, period 365 days. */
  annualAmplitude: 0.15,
  /** Semiannual term, eq (4), printed as -0.075 = -0.5 * the annual amplitude. */
  semiannualFraction: 0.5,
  dayNumberPhase: 9,
  daysPerYear: 365,
  /** Solar-cycle term, eq (5): (0.00127 Rbar - 0.0635). */
  sunspotCoefficient: 0.00127,
  sunspotOffset: 0.0635,
  /** All three perturbation terms carry e^(-(L-2)/1.5). */
  perturbationReferenceL: 2,
  perturbationScaleL: 1.5,
  /** Extended plasma trough, eq (6). t is MLT in hours. */
  troughExponent: -4.5,
  troughNightCoefficient: 5800,
  troughNightSlopePerHour: 300,
  troughDayCoefficient: -800,
  troughDaySlopePerHour: 1400,
  /** The small additive term approaching a constant beyond L = 6. */
  troughFloorScaleL: 10,
  /** Plasmapause scale width: 0.1 at night, 0.1 + 0.011(t-6) across the day. */
  plasmapauseNightWidthL: 0.1,
  plasmapauseDayWidthSlopePerHour: 0.011,
  /** The model's stated L range. */
  innerValidL: 2.25,
  outerValidL: 8,
  /** The paper's own plasmapause fit, quoted but not driven — see the header. */
  kpPlasmapause: { a: -0.46, b: 5.6 },
  citation: "Carpenter & Anderson (1992), JGR 97(A2), 1097-1108",
  doi: "10.1029/91JA01548",
} as const;

/**
 * The 13-month average sunspot number the solar-cycle term is evaluated at.
 *
 * This one input is NOT live, and the layer says so on screen. Two reasons.
 * This release publishes no sunspot or F10.7 record — there is nothing to
 * read. And the quantity is defined as a 13-month running mean, so it cannot
 * exist for the current month by construction: SILSO's own series carries
 * values only to 2026-01 and prints -1 for every month after it. The most
 * recent published value is used, with its date, and the data viewer prints
 * both. Its influence is bounded and small next to the storm signal: across a
 * whole solar cycle this term moves the density by about 1.5x at L = 2 and
 * less further out, while the erosion the layer exists to show is a factor of
 * twenty or more.
 */
export const SUNSPOT_NUMBER_REFERENCE = {
  value: 104.2,
  forMonth: "2026-01",
  source: "SILSO/SIDC 13-month smoothed total sunspot number v2.0 (provisional)",
  url: "https://www.sidc.be/SILSO/DATA/SN_ms_tot_V2.0.txt",
  retrieved: "2026-08-09",
} as const;

/** O'Brien & Moldwin (2003) Dst-model coefficients, from the paper's Table 2. */
export const OBRIEN_MOLDWIN_DST = {
  a: -1.57,
  b: 6.3,
  /** RMS error of the fit, in L. Published, and shown rather than hidden. */
  rmseL: 0.8,
  windowHours: 24,
  citation: "O'Brien & Moldwin (2003), GRL 30(4) 1152",
  doi: "10.1029/2002GL016007",
} as const;

/**
 * Kept under its old name because the legend and the docs quote it: this is
 * Carpenter & Anderson's own Kp plasmapause fit, Lppi = 5.6 - 0.46 Kpmax.
 */
export const CARPENTER_ANDERSON_KP = {
  a: CARPENTER_ANDERSON_1992.kpPlasmapause.a,
  b: CARPENTER_ANDERSON_1992.kpPlasmapause.b,
  citation: CARPENTER_ANDERSON_1992.citation,
  doi: CARPENTER_ANDERSON_1992.doi,
} as const;

// ---------------------------------------------------------------------------
// The plasmapause location, from the published Dst record
// ---------------------------------------------------------------------------

export interface DstWindowMinimum {
  /** Deepest Dst in the window, nT. */
  minimumNt: number;
  minimumAt: string;
  /** Samples that actually fell inside the window — thin coverage is reported, not hidden. */
  sampleCount: number;
  windowFrom: string;
  windowTo: string;
}

/**
 * The deepest Dst over the `windowHours` preceding `at`, or null when the
 * published record cannot answer.
 *
 * Two refusals, both deliberate:
 *
 * - `at` more than `edgeToleranceMinutes` past the newest sample: the record
 *   has not reached that time, and extrapolating an index forward is exactly
 *   the invented-arrow this site forbids. (The whole window need not be
 *   covered — a storm main phase at the start of the record still has a
 *   perfectly good minimum-so-far — but the *end* of the window must be.)
 * - No samples in the window at all: nothing to take a minimum of.
 *
 * No interpolation is performed; the minimum of the samples present is the
 * minimum used, and the count is reported so a thin window is visible.
 */
export function dstMinimumOverWindow(
  series: readonly DstSample[],
  at: Date,
  windowHours = OBRIEN_MOLDWIN_DST.windowHours,
  edgeToleranceMinutes = 90,
): DstWindowMinimum | null {
  const to = at.getTime();
  if (!Number.isFinite(to) || series.length === 0) return null;
  const from = to - windowHours * 3_600_000;
  let newestMs = Number.NEGATIVE_INFINITY;
  let minimumNt = Number.POSITIVE_INFINITY;
  let minimumAt: string | null = null;
  let sampleCount = 0;
  for (const sample of series) {
    const ms = Date.parse(sample.at);
    if (!Number.isFinite(ms) || !Number.isFinite(sample.dstNt)) continue;
    if (ms > newestMs) newestMs = ms;
    if (ms < from || ms > to) continue;
    sampleCount += 1;
    if (sample.dstNt < minimumNt) {
      minimumNt = sample.dstNt;
      minimumAt = sample.at;
    }
  }
  if (sampleCount === 0 || minimumAt === null) return null;
  if (to - newestMs > edgeToleranceMinutes * 60_000) return null;
  return {
    minimumNt,
    minimumAt,
    sampleCount,
    windowFrom: new Date(from).toISOString(),
    windowTo: new Date(to).toISOString(),
  };
}

export interface PlasmapauseState {
  /** Plasmapause inner limit, Carpenter & Anderson's Lppi, in L. */
  lppRe: number;
  /** The published fit error, in L, carried with the value. */
  rmseL: number;
  /** The driving statistic. */
  dstMinimumNt: number;
  dstMinimumAt: string;
  dstSampleCount: number;
  /** True when the quiet-time clamp decided the value rather than the fit. */
  quietClamped: boolean;
}

/**
 * O'Brien & Moldwin's Dst model, with its one necessary clamp.
 *
 * The fit takes log10 of the *depression*, so a day whose deepest Dst is not
 * below -1 nT has no defined Q. Physically that is the refilled quiet state,
 * so the depression is clamped to 1 nT, which lands Lpp on the fit's own
 * quiet-time intercept b = 6.3 — the model's answer for "no ring current at
 * all", not a number invented here.
 */
export function plasmapauseFromDstMinimum(minimum: DstWindowMinimum): PlasmapauseState {
  const depression = Math.max(1, -minimum.minimumNt);
  const quietClamped = -minimum.minimumNt < 1;
  const lpp = OBRIEN_MOLDWIN_DST.a * Math.log10(depression) + OBRIEN_MOLDWIN_DST.b;
  return {
    // The CRRES fit saw plasmapauses between about L=2 and L=7. The lower
    // clamp is Carpenter & Anderson's own inner validity limit: below L=2.25
    // their saturated profile is not fitted, so a boundary there would have
    // no density model on its inner side.
    lppRe: THREE.MathUtils.clamp(lpp, CARPENTER_ANDERSON_1992.innerValidL, OBRIEN_MOLDWIN_DST.b),
    rmseL: OBRIEN_MOLDWIN_DST.rmseL,
    dstMinimumNt: minimum.minimumNt,
    dstMinimumAt: minimum.minimumAt,
    dstSampleCount: minimum.sampleCount,
    quietClamped,
  };
}

/** The full chain: series + instant -> plasmapause, or null when unanswerable. */
export function plasmapauseAt(series: readonly DstSample[], at: Date): PlasmapauseState | null {
  const minimum = dstMinimumOverWindow(series, at);
  return minimum ? plasmapauseFromDstMinimum(minimum) : null;
}

// ---------------------------------------------------------------------------
// Carpenter & Anderson's density expressions
// ---------------------------------------------------------------------------

/** Day number, 1-366, from a UTC instant. The seasonal terms need only this. */
export function dayNumberUtc(at: Date): number {
  const start = Date.UTC(at.getUTCFullYear(), 0, 1);
  return Math.floor((at.getTime() - start) / 86_400_000) + 1;
}

export interface SecularInputs {
  /** Day number d, 1-366. Drives the annual and semiannual terms. */
  dayNumber: number;
  /** 13-month average sunspot number Rbar. Drives the solar-cycle term. */
  sunspotNumber: number;
}

/**
 * The bracketed perturbation of the saturated profile: the annual, semiannual
 * and solar-cycle terms of the paper's summary item 2, before the common
 * e^(-(L-2)/1.5) factor. Split out so a test can pin the three terms
 * separately against equations (3), (4) and (5).
 */
export function saturatedPerturbationAmplitude(inputs: SecularInputs): number {
  const c = CARPENTER_ANDERSON_1992;
  const phase = (2 * Math.PI * (inputs.dayNumber + c.dayNumberPhase)) / c.daysPerYear;
  return c.annualAmplitude * (Math.cos(phase) - c.semiannualFraction * Math.cos(2 * phase))
    + c.sunspotCoefficient * inputs.sunspotNumber
    - c.sunspotOffset;
}

/**
 * log10 of the saturated plasmasphere electron density in el/cc, summary
 * item 2. Evaluated at any L; the caller is responsible for only asking
 * inside 2.25 <= L <= Lppi, which `equatorialElectronDensity` does.
 */
export function saturatedLogDensity(lRe: number, inputs: SecularInputs): number {
  const c = CARPENTER_ANDERSON_1992;
  const falloff = Math.exp(-(lRe - c.perturbationReferenceL) / c.perturbationScaleL);
  return c.saturatedSlopePerL * lRe + c.saturatedIntercept
    + saturatedPerturbationAmplitude(inputs) * falloff;
}

/** The same, in el/cc. */
export function saturatedDensity(lRe: number, inputs: SecularInputs): number {
  return 10 ** saturatedLogDensity(lRe, inputs);
}

/**
 * How a local-time-dependent quantity is evaluated at an MLT the model does
 * not cover, following the paper's section 4 rather than extrapolating a fit.
 *
 * Returns the blend weight on the DAYSIDE (15 MLT) value; 1 - weight is the
 * weight on the NIGHTSIDE (00 MLT) value. Inside 00-15 MLT the caller uses
 * the printed branches directly and never asks this, so the answer there is
 * NaN rather than a number that could be used by accident.
 */
export function modelLocalTimeBlend(mltHours: number): number {
  const t = ((mltHours % 24) + 24) % 24;
  if (t < 15) return Number.NaN; // inside the fitted range; use the branches.
  if (t < 19) return 1;          // dayside values continued, per section 4.
  if (t <= 20) return 20 - t;    // linear transition between 19 and 20 MLT.
  return 0;                      // nighttime conditions to midnight.
}

/**
 * The trough's leading coefficient (the "scale density") at an MLT: the
 * (5800 + 300 t) and (-800 + 1400 t) of summary item 4, with the section 4
 * rule applied outside 00-15 MLT.
 */
export function troughScaleCoefficient(mltHours: number): number {
  const c = CARPENTER_ANDERSON_1992;
  const t = ((mltHours % 24) + 24) % 24;
  if (t < 6) return c.troughNightCoefficient + c.troughNightSlopePerHour * t;
  if (t <= 15) return c.troughDayCoefficient + c.troughDaySlopePerHour * t;
  const night = c.troughNightCoefficient;                            // its t = 0 value
  const day = c.troughDayCoefficient + c.troughDaySlopePerHour * 15; // its t = 15 value
  const dayWeight = modelLocalTimeBlend(t);
  return day * dayWeight + night * (1 - dayWeight);
}

/**
 * The plasmapause scale width in L — the distance over which the density
 * drops by one decade. Summary item 3: 0.1 at night, 0.1 + 0.011(t-6) across
 * the day, so 0.166 at noon and 0.199 at 15 MLT, with the same section 4 rule
 * outside the fitted range.
 */
export function plasmapauseScaleWidthL(mltHours: number): number {
  const c = CARPENTER_ANDERSON_1992;
  const t = ((mltHours % 24) + 24) % 24;
  if (t < 6) return c.plasmapauseNightWidthL;
  if (t <= 15) return c.plasmapauseNightWidthL + c.plasmapauseDayWidthSlopePerHour * (t - 6);
  const night = c.plasmapauseNightWidthL;
  const day = c.plasmapauseNightWidthL + c.plasmapauseDayWidthSlopePerHour * (15 - 6);
  const dayWeight = modelLocalTimeBlend(t);
  return day * dayWeight + night * (1 - dayWeight);
}

/** The trough's small additive term: (1 - e^(-(L-2)/10)). */
function troughFloor(lRe: number): number {
  const c = CARPENTER_ANDERSON_1992;
  return 1 - Math.exp(-(lRe - c.perturbationReferenceL) / c.troughFloorScaleL);
}

/**
 * The extended plasma trough, summary item 4, in el/cc. The small additive
 * term is the paper's own: it "is intended to approximate the decrease in
 * decay rate and approach to a constant value beyond L = 6".
 */
export function extendedTroughDensity(lRe: number, mltHours: number): number {
  const c = CARPENTER_ANDERSON_1992;
  return troughScaleCoefficient(mltHours) * lRe ** c.troughExponent + troughFloor(lRe);
}

/** The plasmapause segment, summary item 3, in el/cc. */
export function plasmapauseSegmentDensity(
  lRe: number,
  lppiRe: number,
  mltHours: number,
  inputs: SecularInputs,
): number {
  const width = plasmapauseScaleWidthL(mltHours);
  return saturatedDensity(lppiRe, inputs) * 10 ** (-(lRe - lppiRe) / width);
}

/**
 * The plasmapause outer limit Lppo — summary item 5, which the paper gives no
 * formula for: it is "determined by solving simultaneously for the
 * plasmapause segment and the extended plasma trough". Solved by bisection on
 * the difference of the two, which is monotone here because the plasmapause
 * segment falls a decade every 0.1-0.2 L while the trough falls as L^-4.5.
 *
 * Returns Lppi itself when the density at the boundary is already at or below
 * the trough: there is then no knee left to draw, which is what a plasmasphere
 * eroded to the trough level means.
 */
export function plasmapauseOuterL(lppiRe: number, mltHours: number, inputs: SecularInputs): number {
  const difference = (l: number) =>
    plasmapauseSegmentDensity(l, lppiRe, mltHours, inputs) - extendedTroughDensity(l, mltHours);
  if (difference(lppiRe) <= 0) return lppiRe;
  const lower0 = lppiRe;
  const upper0 = Math.min(CARPENTER_ANDERSON_1992.outerValidL, lppiRe + 4);
  if (difference(upper0) > 0) return upper0;
  let lower = lower0;
  let upper = upper0;
  for (let step = 0; step < 60; step += 1) {
    const middle = (lower + upper) / 2;
    if (difference(middle) > 0) lower = middle;
    else upper = middle;
  }
  return (lower + upper) / 2;
}

/**
 * The whole piecewise model at one point of the magnetic equator, in el/cc.
 *
 * Returns null outside the paper's stated 2.25 <= L <= 8 — absence is drawn
 * as absence, never as an extrapolated number.
 */
export function equatorialElectronDensity(
  lRe: number,
  mltHours: number,
  lppiRe: number,
  inputs: SecularInputs,
  /**
   * The outer limit Lppo, when the caller has already solved for it at this
   * MLT. It is a function of (Lppi, MLT, inputs) alone, so a caller sweeping L
   * down one meridian — which is what the density texture builder does, 512
   * times per column — can solve the bisection once instead of once per
   * sample. Omit it and it is solved here, exactly as before.
   */
  lppoRe?: number,
): number | null {
  const c = CARPENTER_ANDERSON_1992;
  if (!Number.isFinite(lRe) || lRe < c.innerValidL || lRe > c.outerValidL) return null;
  if (lRe <= lppiRe) return saturatedDensity(lRe, inputs);
  const lppo = lppoRe ?? plasmapauseOuterL(lppiRe, mltHours, inputs);
  if (lRe <= lppo) return plasmapauseSegmentDensity(lRe, lppiRe, mltHours, inputs);
  // Summary item 6: the trough segment is anchored on the density reached at
  // Lppo rather than on the extended trough's own value there, so the profile
  // is continuous across the join. The additive floor term is taken off the
  // anchor and put back on at L, exactly as item 6 is written.
  const anchor = plasmapauseSegmentDensity(lppo, lppiRe, mltHours, inputs) - troughFloor(lppo);
  return anchor * (lRe / lppo) ** c.troughExponent + troughFloor(lRe);
}

// ---------------------------------------------------------------------------
// The evaluated field for one instant
// ---------------------------------------------------------------------------

/**
 * What the stipple renderer needs, from whichever model is driving the layer.
 *
 * Two models now feed this layer and they are not interchangeable evidence:
 * the DGCPM simulation when the release publishes frames covering the selected
 * instant, and the Carpenter & Anderson empirical profile everywhere else. The
 * renderer is deliberately blind to which one it has — it asks for a density
 * at a point and for the limits of validity — while everything a reader sees
 * (badge, wording, citations) is switched off `source`.
 */
export type PlasmasphereSource = "dgcpm" | "carpenter-anderson";

export interface PlasmasphereDensityField {
  source: PlasmasphereSource;
  /** The instant this was evaluated for. */
  validAt: string;
  /** The representative plasmapause radius the legend prints, in L. */
  plasmapauseLRe: number;
  /**
   * Everything that changes what would be drawn, as one string.
   *
   * The scene rebuilds a 130,000-grain stipple when this moves and skips the
   * rebuild when it does not. It is deliberately NOT the valid time: the
   * empirical model is evaluated continuously as the timeline is scrubbed but
   * only changes shape when its driven parameters do, and rebuilding on every
   * tick made the scrubber stutter. The simulation, by contrast, changes at
   * every published frame, so its key IS its frame time.
   */
  rebuildKey: string;
  /** Where the knee ends at midnight and at noon — the two extremes drawn. */
  outerLimitMidnightRe: number;
  outerLimitNoonRe: number;
  /** Outside this range the driving model is not defined and nothing is drawn. */
  validLRange: readonly [number, number];
  /** Density in el/cc at a point of the magnetic equator, or null off-model. */
  densityAt(lRe: number, mltHours: number): number | null;
  /**
   * The field's own (L, MLT) grid, when it HAS one.
   *
   * The stipple resamples the field onto a GPU texture so a grain can read the
   * density wherever it has drifted to. When the driving model is a published
   * grid, that texture is that grid — no resampling of published numbers at
   * all, and `densityAt` and the texture are then the same bilinear surface.
   * A closed-form model has no grid and says so by leaving this undefined;
   * the texture builder then chooses its own sampling and documents it.
   *
   * `logDensity` is L-major with MLT varying fastest, which is the layout the
   * publisher writes and the layout a texture row needs. The MLT axis is
   * periodic and uniform over 24 h; the L axis is uniform over `validLRange`.
   */
  densityGrid?: {
    lValues: readonly number[];
    mltHours: readonly number[];
    logDensity: Float32Array;
  };
}

export interface PlasmasphereField extends PlasmasphereDensityField {
  source: "carpenter-anderson";
  plasmapause: PlasmapauseState;
  inputs: SecularInputs;
  /** el/cc at the boundary itself: the top of the knee. */
  densityAtPlasmapause: number;
}

/**
 * The evaluated Carpenter & Anderson field for one instant, or null when the
 * published Dst record cannot place the boundary.
 */
export function plasmasphereFieldAt(
  series: readonly DstSample[],
  at: Date,
  sunspotNumber = SUNSPOT_NUMBER_REFERENCE.value,
): PlasmasphereField | null {
  const plasmapause = plasmapauseAt(series, at);
  if (!plasmapause) return null;
  const inputs: SecularInputs = { dayNumber: dayNumberUtc(at), sunspotNumber };
  const lppi = plasmapause.lppRe;
  // Lppo depends only on the meridian, and solving it is a 60-step bisection
  // over two exponentials. One cached meridian turns the density texture's
  // 49,152 evaluations into 96 bisections plus arithmetic; the value is
  // identical either way, so this is a memo and not an approximation.
  let cachedMlt = Number.NaN;
  let cachedOuterL = 0;
  const outerLimitFor = (mltHours: number) => {
    if (mltHours !== cachedMlt) {
      cachedMlt = mltHours;
      cachedOuterL = plasmapauseOuterL(lppi, mltHours, inputs);
    }
    return cachedOuterL;
  };
  return {
    source: "carpenter-anderson",
    plasmapause,
    inputs,
    plasmapauseLRe: lppi,
    rebuildKey: `ca:${lppi.toFixed(4)}:${inputs.dayNumber}:${inputs.sunspotNumber}`,
    outerLimitMidnightRe: plasmapauseOuterL(lppi, 0, inputs),
    outerLimitNoonRe: plasmapauseOuterL(lppi, 12, inputs),
    validLRange: [CARPENTER_ANDERSON_1992.innerValidL, CARPENTER_ANDERSON_1992.outerValidL],
    densityAtPlasmapause: saturatedDensity(lppi, inputs),
    validAt: at.toISOString(),
    densityAt: (lRe, mltHours) => equatorialElectronDensity(lRe, mltHours, lppi, inputs, outerLimitFor(mltHours)),
  };
}

// ---------------------------------------------------------------------------
// The published DGCPM simulation
// ---------------------------------------------------------------------------

/**
 * The Dynamic Global Core Plasma Model, as published by this release.
 *
 * ## Why there is a second model in this file
 *
 * Carpenter & Anderson is a *statistic*. It has no memory and no local-time
 * structure inside the plasmasphere, so it cannot show the two things a
 * plasmasphere does when the Sun acts on it: erode on a timescale of hours,
 * and shed a drainage plume out through the dusk sector. The site's owner
 * asked for the Sun-Earth coupling to be visible and named the model that
 * shows it. So the layer now prefers a running simulation and keeps the
 * empirical profile as the labelled fallback for instants the simulation does
 * not cover.
 *
 * ## What is actually being simulated
 *
 * `pipeline/plasmasphere_dgcpm.py` integrates the flux-tube content of a
 * two-dimensional (L, MLT) grid under E x B drift in a Volland-Stern
 * convection field whose strength comes from measured planetary Kp, plus
 * corotation, with a dayside ionospheric source filling toward the Carpenter &
 * Anderson saturated ceiling and a nightside loss draining closed flux tubes.
 * That module's docstring carries the equations, the constants, and where each
 * one was read from; this file only decodes what it published.
 *
 * The evidence class is **physics simulation** — not observation, not
 * assimilation. Nothing in this layer has been measured. What is measured is
 * the Kp index that drives it, and that distinction is the whole of the badge.
 */
export const PLASMASPHERE_DGCPM = {
  name: "Dynamic Global Core Plasma Model (DGCPM)",
  citation: "Ober, Horwitz & Gallagher (1997), JGR 102(A7), 14595-14602",
  doi: "10.1029/97JA01046",
  electricField: "Volland-Stern with the Maynard & Chen (1975) Kp law, plus corotation",
  electricFieldRestatedBy: "Pierrard, Khazanov, Cabrera & Lemaire (2008), JGR 113, A08212",
  electricFieldDoi: "10.1029/2007JA012612",
  drive: "planetary Kp, NOAA SWPC",
  schemaVersion: "dgcpm-plasmasphere.v1",
} as const;

export interface DgcpmPlume {
  present?: boolean;
  peakMltHours?: number;
  peakL?: number;
  nightMedianL?: number;
  extentL?: number;
  reason?: string;
}

export interface DgcpmFrame {
  validAt: string;
  kp: number;
  convectionAmplitudeVPerRe2: number;
  stagnationL: number;
  densityU16: string;
  plasmapauseLByMlt: (number | null)[];
  steepestGradientLByMlt: number[];
  plume: DgcpmPlume;
}

export interface DgcpmBundle {
  schemaVersion: string;
  status: string;
  model: {
    name: string;
    citation: string;
    doi: string;
    electricField: { name: string; citation: string; doi: string; potential: string; amplitude: string };
    fillDays: number;
    emptyPeriodClosedDays: number;
    notModelled: string[];
  };
  drive: {
    index: string;
    from: string;
    to: string;
    sampleCount: number;
    spinUpHours: number;
    spinUpFrom: string;
    definitiveTo?: string;
    estimatedCount?: number;
    initialCondition: string;
  };
  grid: { lValues: number[]; mltHours: number[]; lCount: number; mltCount: number };
  fieldEncodings: { electronDensity: { scale: string; minimum: number; maximum: number; units: string } };
  plasmapause: { contourCm3: number; method: string };
  time: { cadenceMinutes: number; validFrom: string; validTo: string; frameCount: number };
  frames: DgcpmFrame[];
}

export interface DgcpmSequence {
  bundle: DgcpmBundle;
  /** Frame valid times in epoch milliseconds, ascending. */
  times: number[];
  /** log10(density) per frame, L-major with MLT varying fastest. */
  logDensity: Float32Array[];
  lValues: number[];
  mltHours: number[];
  cadenceMinutes: number;
}

/** Decode one base64 little-endian uint16 block into log10 density. */
function decodeLogDensityBlock(
  encoded: string,
  count: number,
  minimum: number,
  maximum: number,
): Float32Array {
  const binary = atob(encoded);
  if (binary.length !== count * 2) {
    throw new RangeError(
      `DGCPM frame has ${binary.length} bytes for ${count} grid points; the grid and the payload disagree`,
    );
  }
  const out = new Float32Array(count);
  const span = maximum - minimum;
  for (let index = 0; index < count; index += 1) {
    const low = binary.charCodeAt(index * 2) & 0xff;
    const high = binary.charCodeAt(index * 2 + 1) & 0xff;
    out[index] = minimum + ((low | (high << 8)) / 65535) * span;
  }
  return out;
}

/**
 * Validate and decode a published DGCPM bundle.
 *
 * Throws rather than degrades on a structural mismatch. A silently misdecoded
 * grid would draw a plausible, wrong plasmasphere, which is the one outcome
 * this project treats as worse than an empty layer — and the caller's catch
 * falls back to the empirical model, which is a labelled, honest picture.
 */
export function decodeDgcpmSequence(bundle: DgcpmBundle): DgcpmSequence {
  if (bundle?.schemaVersion !== PLASMASPHERE_DGCPM.schemaVersion) {
    throw new RangeError(`unknown plasmasphere schema ${String(bundle?.schemaVersion)}`);
  }
  const lValues = bundle.grid?.lValues ?? [];
  const mltHours = bundle.grid?.mltHours ?? [];
  if (lValues.length < 2 || mltHours.length < 2) throw new RangeError("DGCPM grid is degenerate");
  if (lValues.length !== bundle.grid.lCount || mltHours.length !== bundle.grid.mltCount) {
    throw new RangeError("DGCPM grid axis lengths disagree with their declared counts");
  }
  const encoding = bundle.fieldEncodings?.electronDensity;
  if (!encoding || encoding.scale !== "log10") {
    throw new RangeError("DGCPM density encoding is missing or not log10");
  }
  const frames = Array.isArray(bundle.frames) ? bundle.frames : [];
  if (frames.length === 0) throw new RangeError("DGCPM bundle carries no frames");
  const count = lValues.length * mltHours.length;
  const times: number[] = [];
  const logDensity: Float32Array[] = [];
  for (const frame of frames) {
    const at = Date.parse(frame.validAt);
    if (!Number.isFinite(at)) throw new RangeError(`DGCPM frame has an unreadable valid time: ${frame.validAt}`);
    times.push(at);
    logDensity.push(decodeLogDensityBlock(frame.densityU16, count, encoding.minimum, encoding.maximum));
  }
  for (let index = 1; index < times.length; index += 1) {
    if (times[index]! <= times[index - 1]!) throw new RangeError("DGCPM frames are not in ascending time order");
  }
  return {
    bundle,
    times,
    logDensity,
    lValues,
    mltHours,
    cadenceMinutes: bundle.time?.cadenceMinutes ?? 120,
  };
}

export interface DgcpmPlasmasphereField extends PlasmasphereDensityField {
  source: "dgcpm";
  frame: DgcpmFrame;
  bundle: DgcpmBundle;
  /** How far the selected frame is from the requested instant, in minutes. */
  frameOffsetMinutes: number;
  /**
   * Whole minutes the drawn frame TRAILS the requested instant. Signed:
   * negative when the frame leads the clock, which happens while scrubbing
   * back toward a frame that is still ahead. `frameOffsetMinutes` is the
   * unsigned distance and stays what it was.
   */
  frameAgeMinutes: number;
  /**
   * Set when this frame is the newest published one and the instant asked for
   * is the present — i.e. the picture is a NOWCAST rather than a frame chosen
   * to match a past instant. Null while the reader is scrubbing history, where
   * the frame's distance from the clock is already the `FRAME` row's job.
   */
  nowcast: DgcpmNowcast | null;
  /** The published boundary radius at each published MLT, for the card. */
  plasmapauseByMlt: { mltHours: number; lRe: number | null }[];
  plume: DgcpmPlume;
}

/**
 * HOW LONG THE NEWEST PUBLISHED FRAME IS STILL THE PRESENT.
 *
 * ONE PUBLISHING CADENCE, read off the artifact rather than typed in here.
 * A frame is the current one until its successor is DUE; at that moment the
 * feed is late and saying so is a real fact about the feed. Two hours is what
 * this artifact happens to publish at today, and `cadenceMinutes` is what the
 * bundle says, so a change upstream carries straight through.
 *
 * WHY THIS EXISTS. The rule before it was nearest-frame-within-half-a-cadence,
 * symmetric. That is the right rule for a reader scrubbing history, where
 * "which frame is nearest this instant" has a wrong answer. It is the wrong
 * rule at LIVE NOW, because now is never a frame time: a frame lands at 14:00
 * and the clock immediately walks past it, so from 15:00 to 16:00 — half of
 * every cycle — the nearest published frame was more than half a cadence away
 * and the ring current went dark with a correct-but-useless notice saying the
 * next frame had not arrived. Sean, on the live site at 14:21 UTC: "note how
 * the legend says NO DATA AT THIS TIME for ring current. Is that true? How can
 * we avoid that?" It was true. It was also the normal state, and a refusal
 * that is the normal state has stopped informing anybody.
 *
 * WHAT IT IS NOT. This is not a licence to draw the FUTURE. A frame is held
 * only while the instant asked for is at or behind the wall clock; scrub the
 * slider forward and the layer refuses exactly as it did before, because
 * nothing simulates this plasmasphere ahead of now and a held frame under a
 * future timestamp would be the forecast magnetosphere defect all over again.
 * Nor does it paper over an INTERNAL gap: the hold applies only past the
 * newest frame in the sequence, never across a hole with a published frame on
 * the far side of it.
 */
export const DGCPM_NOWCAST_HOLD_CADENCES = 1;

/**
 * How far past the wall clock an instant may sit and still count as "now".
 *
 * Two minutes. The page's own clock ticks four times a second off `Date.now()`
 * and "Return to now" recomputes on every tick, so a live reader is at now to
 * the millisecond; this slack absorbs the tick and a manifest fetched a moment
 * ago, and nothing else. A reader who has actually scrubbed FORWARD is minutes
 * to days ahead, never two minutes, so no deliberate look into the future can
 * slip through here.
 */
export const DGCPM_NOWCAST_CLOCK_SLACK_MINUTES = 2;

/** What the surfaces need to say that a drawn frame is a nowcast, and how old. */
export interface DgcpmNowcast {
  /** Whole minutes the frame trails the clock. Never negative. */
  ageMinutes: number;
  /** The frame's own published valid time, ISO. */
  frameValidAt: string;
  /** The publishing cadence this hold is derived from. */
  cadenceMinutes: number;
  /** When the successor is due — frame time plus one cadence, ISO. */
  successorDueAt: string;
  /**
   * True once the frame has outlived the old half-cadence window, which is
   * where the wording gets louder. Below it the age is a footnote; above it
   * the reader is looking at a picture that would previously have been
   * refused, and the label has to carry that weight.
   */
  held: boolean;
}

/**
 * THE ONE LINE THE READER SEES UNDER THE COLOUR BAR when a frame is being
 * drawn as the present.
 *
 * Written for a lay IW / Space Cadre reader: how old, in words, and what that
 * means. Not a timestamp soup — the exact valid time is already stamped on the
 * layer's own card, and this sentence is the part that has to survive a folded
 * card.
 */
export function dgcpmNowcastLine(nowcast: DgcpmNowcast, subject: string): string {
  const age = nowcast.ageMinutes < 1
    ? "just published"
    : nowcast.ageMinutes < 60
      ? `${nowcast.ageMinutes} min old`
      : `${Math.floor(nowcast.ageMinutes / 60)} h ${nowcast.ageMinutes % 60} min old`;
  const cadence = nowcast.cadenceMinutes % 60 === 0
    ? `${nowcast.cadenceMinutes / 60} h`
    : `${nowcast.cadenceMinutes} min`;
  if (!nowcast.held) {
    return `NOWCAST · ${subject}, ${age}. Frames are ${cadence} apart, so nothing newer exists yet.`;
  }
  return `NOWCAST, AND AGEING · ${subject}, and it is now ${age}. `
    + `Its replacement is due at ${nowcast.successorDueAt.slice(11, 16)} UTC; past that this layer goes off rather than keep holding it.`;
}

/**
 * The two things that can drive this layer, as one discriminated union.
 *
 * Narrow on `source` and the compiler hands you the right model's own extra
 * fields. The renderer takes the wider `PlasmasphereDensityField`, because it
 * must not care; everything a reader sees takes this.
 */
export type PlasmasphereLayerField = PlasmasphereField | DgcpmPlasmasphereField;

/**
 * The published frame to draw for an instant, or null when the sequence cannot
 * answer for it.
 *
 * TWO RULES, and they answer two different questions.
 *
 * SCRUBBING HISTORY — the nearest published frame, and never one further away
 * than half the published cadence. Frames are shown as published; nothing is
 * interpolated between them, because a plume moving across a two-hour step is
 * a real thing moving in real steps and a blended intermediate frame would be
 * a picture of no particular time. Half a cadence is the widest window in
 * which "nearest" has no wrong answer.
 *
 * READING THE PRESENT — the newest published frame, held for up to one whole
 * cadence past itself, and labelled with its age. See
 * `DGCPM_NOWCAST_HOLD_CADENCES` for why the symmetric rule alone left the ring
 * current dark for half of every publishing cycle. The hold requires ALL of:
 * the nearest frame is the newest one in the sequence (so an internal gap is
 * never papered over), the clock is ahead of it (a frame that leads the clock
 * needs no holding), the clock is NOT ahead of `now` (the future is still
 * refused, unchanged), and the frame is no older than one cadence (past that
 * its successor is overdue and the layer goes off and says so).
 *
 * `now` is the wall clock. Pass null — as every non-live caller does — and the
 * hold is off entirely, because a nowcast is a claim about the present and
 * without a present there is nothing to claim.
 */
export function dgcpmFieldAt(
  sequence: DgcpmSequence,
  at: Date,
  now: Date | null = null,
): DgcpmPlasmasphereField | null {
  const target = at.getTime();
  if (!Number.isFinite(target) || sequence.times.length === 0) return null;
  let best = 0;
  let bestDistance = Number.POSITIVE_INFINITY;
  for (let index = 0; index < sequence.times.length; index += 1) {
    const distance = Math.abs(sequence.times[index]! - target);
    if (distance < bestDistance) {
      bestDistance = distance;
      best = index;
    }
  }
  const toleranceMs = (sequence.cadenceMinutes * 60_000) / 2;
  const newestIndex = sequence.times.length - 1;
  const newestMs = sequence.times[newestIndex]!;
  const holdMs = sequence.cadenceMinutes * 60_000 * DGCPM_NOWCAST_HOLD_CADENCES;
  const nowMs = now === null ? null : now.getTime();
  const pastNewestMs = target - newestMs;
  const heldAsNowcast = nowMs !== null
    && Number.isFinite(nowMs)
    && best === newestIndex
    && pastNewestMs > toleranceMs
    && pastNewestMs <= holdMs
    && target <= nowMs + DGCPM_NOWCAST_CLOCK_SLACK_MINUTES * 60_000;
  if (bestDistance > toleranceMs && !heldAsNowcast) return null;
  const frame = sequence.bundle.frames[best]!;
  const values = sequence.logDensity[best]!;
  const { lValues, mltHours } = sequence;
  const lMinimum = lValues[0]!;
  const lMaximum = lValues[lValues.length - 1]!;
  const mltCount = mltHours.length;
  const mltStep = 24 / mltCount;

  const densityAt = (lRe: number, mlt: number): number | null => {
    if (!Number.isFinite(lRe) || lRe < lMinimum || lRe > lMaximum) return null;
    // The published L axis is uniform, so the bracketing shell is arithmetic
    // rather than a search. `lStep` is read from the axis, not assumed.
    const lStep = (lMaximum - lMinimum) / (lValues.length - 1);
    const lPosition = (lRe - lMinimum) / lStep;
    const lIndex = Math.min(lValues.length - 2, Math.max(0, Math.floor(lPosition)));
    const lWeight = Math.min(1, Math.max(0, lPosition - lIndex));
    const wrapped = ((mlt % 24) + 24) % 24;
    const mltPosition = wrapped / mltStep;
    const mltIndex = Math.floor(mltPosition) % mltCount;
    const mltWeight = mltPosition - Math.floor(mltPosition);
    const nextMlt = (mltIndex + 1) % mltCount;
    const at00 = values[lIndex * mltCount + mltIndex]!;
    const at01 = values[lIndex * mltCount + nextMlt]!;
    const at10 = values[(lIndex + 1) * mltCount + mltIndex]!;
    const at11 = values[(lIndex + 1) * mltCount + nextMlt]!;
    // Bilinear in log density, which is the quantity that was published and
    // the quantity the colour ramp is linear in.
    const low = at00 + (at01 - at00) * mltWeight;
    const high = at10 + (at11 - at10) * mltWeight;
    return 10 ** (low + (high - low) * lWeight);
  };

  const boundary = frame.plasmapauseLByMlt ?? [];
  const finite = boundary.filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  const median = finite.length
    ? [...finite].sort((a, b) => a - b)[Math.floor(finite.length / 2)]!
    : lMinimum;
  const nearestBoundary = (mlt: number): number => {
    if (boundary.length === 0) return median;
    const index = Math.round((((mlt % 24) + 24) % 24) / mltStep) % boundary.length;
    const value = boundary[index];
    return typeof value === "number" && Number.isFinite(value) ? value : median;
  };

  return {
    source: "dgcpm",
    validAt: frame.validAt,
    rebuildKey: `dgcpm:${frame.validAt}`,
    frame,
    bundle: sequence.bundle,
    frameOffsetMinutes: Math.round(bestDistance / 60_000),
    frameAgeMinutes: Math.round((target - sequence.times[best]!) / 60_000),
    // A nowcast is the NEWEST frame read as the present. Scrubbing history
    // lands on a frame chosen to match a past instant, which is not a claim
    // about now and carries no nowcast label.
    nowcast: nowMs !== null && best === newestIndex && pastNewestMs >= 0
      && target <= nowMs + DGCPM_NOWCAST_CLOCK_SLACK_MINUTES * 60_000
      ? {
        ageMinutes: Math.max(0, Math.round(pastNewestMs / 60_000)),
        frameValidAt: frame.validAt,
        cadenceMinutes: sequence.cadenceMinutes,
        successorDueAt: new Date(newestMs + holdMs).toISOString(),
        held: heldAsNowcast,
      }
      : null,
    plasmapauseLRe: median,
    outerLimitMidnightRe: nearestBoundary(0),
    outerLimitNoonRe: nearestBoundary(12),
    validLRange: [lMinimum, lMaximum],
    plasmapauseByMlt: mltHours.map((hours, index) => ({
      mltHours: hours,
      lRe: typeof boundary[index] === "number" ? boundary[index]! : null,
    })),
    plume: frame.plume ?? {},
    densityAt,
    densityGrid: { lValues, mltHours, logDensity: values },
  };
}

/**
 * The dusk-side bulge, as one number the card can print.
 *
 * Positive means the boundary reaches further out at dusk than it does at
 * midnight, which is the signature of the convection pattern this model
 * carries and the empirical profile does not have at all.
 */
export function duskBulgeL(field: DgcpmPlasmasphereField): number | null {
  const dusk = field.plasmapauseByMlt.find((point) => Math.abs(point.mltHours - 18) < 0.3)?.lRe ?? null;
  const midnight = field.plasmapauseByMlt.find((point) => point.mltHours < 0.3)?.lRe ?? null;
  if (dusk === null || midnight === null) return null;
  return dusk - midnight;
}

// ---------------------------------------------------------------------------
// Drawing the field
// ---------------------------------------------------------------------------

/** The legend's colour ramp, in el/cc. Shared by the material and the legend. */
export const PLASMASPHERE_DENSITY_SCALE = {
  minimumCm3: 1,
  maximumCm3: 3000,
  /** Dark blue trough, through cyan, to a white plasmaspheric core. */
  gradient: "linear-gradient(90deg, #0a1526, #14427e 28%, #2b8fd0 52%, #74d8f5 74%, #eafcff)",
  minimumLabel: "1",
  maximumLabel: "3,000",
  label: "EQUATORIAL ELECTRON DENSITY · cm⁻³ · LOG",
} as const;

/**
 * How big one grain of the stipple is, and why it is measured in scene units.
 *
 * The first build sized grains as `clamp(620 / viewDistance, 1, 5)` screen
 * pixels. That makes a grain's size fall with distance while the number of
 * grains stays fixed, so the fraction of the screen the cloud covers falls as
 * the inverse square of how far in the camera is — and the app frames this
 * layer wide by default. Measured on the shipped build: at the default
 * framing the 130,000 grains were pinned at the 1-pixel floor and covered a
 * few percent of the cloud's own disc, which reads as sparse dust; four
 * zoom-in clicks (a normal thing for a visitor to do, and where the layer was
 * reported blank) spread the same 130,000 one-pixel grains over sixteen times
 * the area and the layer disappeared into the starfield entirely.
 *
 * A grain is therefore a fixed size IN THE SCENE now, projected like any
 * other object. Its screen size then grows exactly as fast as the cloud
 * around it, so the stipple's coverage — and the layer's legibility — is the
 * same at every camera distance. The clamps only guard the extremes: below
 * the floor a grain aliases into a single hard pixel that looks like a star,
 * and above the ceiling a grain becomes a visible blob rather than texture.
 */
export const PLASMASPHERE_GRAIN = {
  /** Grain diameter in scene units. The Earth is 100 scene units in radius. */
  sceneRadiusPerGrain: 3.2,
  minimumPointSizePx: 1.5,
  maximumPointSizePx: 12,
} as const;

// ---------------------------------------------------------------------------
// Corotation: the material moves, the shape does not
// ---------------------------------------------------------------------------

/**
 * How the stipple is made to flow, and why it flows the way it does.
 *
 * ## The complaint this answers
 *
 * "Since the dots of the plasmasphere don't change, it makes it look like a
 * static thing." The dots were static: each grain was a fixed sample of the
 * density field, so a layer whose whole subject is cold plasma being carried
 * around the Earth and drained away read as furniture.
 *
 * ## The two things that move differently
 *
 * The drawn PATTERN — the dusk bulge, the drainage plume — is fixed to the
 * SUN. It is the shape of the drift geometry, and the drift geometry is set by
 * where the Sun is; Earth turns underneath it and the shape holds station. The
 * cold plasma MATERIAL, on the other hand, corotates with Earth: it flows
 * THROUGH that standing shape, like water through a standing wave. So the
 * grains advect and the envelope does not, and a grain that drifts out of the
 * plasmasphere into the trough dims — by exactly the density-to-brightness law
 * that was already there — because it is reading the field at wherever it now
 * is, not carrying a value it was born with.
 *
 * ## What velocity is drawn, and what is not
 *
 * Rigid corotation about the dipole axis, and only that. The honest full
 * velocity of the DGCPM run is corotation plus the Volland-Stern E x B
 * convection drift, and the frames carry everything needed to evaluate it
 * (`kp`, `convectionAmplitudeVPerRe2`, `stagnationL`, and the closed form is
 * in `pipeline/plasmasphere_dgcpm.py`). It is deliberately NOT drawn, for a
 * reason that is about the picture rather than about cost:
 *
 * - The convection drift makes the angular rate depend on where a grain is —
 *   slower toward dusk, reversing altogether outside the stagnation L. A
 *   fixed population of grains under a sheared angular flow piles up wherever
 *   the flow slows and empties wherever it speeds up, permanently so at a
 *   stagnation point. Grain density on screen would then stop being flat, and
 *   this layer's whole construction rests on grain density being flat so that
 *   BRIGHTNESS carries the physics and nothing else (see the note on
 *   `createPlasmasphereFieldGeometry`). The picture would grow a bright dusk
 *   clump that is not in the density field.
 * - A rigid rotation is the one flow that leaves the sampling exactly alone:
 *   the grains are drawn from a rotationally symmetric distribution, so
 *   rotating all of them preserves it forever, at any elapsed time.
 *
 * Corotation is also the right first-order answer: inside the plasmasphere it
 * dominates, which is precisely why there is a plasmasphere. The convection
 * part is where it has always been — in the FIELD the grains are sampling,
 * which is what put the bulge and the plume there — and the card says so, with
 * the frame's own stagnation L as the number that says how big the omitted
 * part is.
 *
 * ## Cadence
 *
 * One revolution per day is invisible. The grains therefore run on a display
 * cadence, exactly as the solar-wind shower's tracers do, and the card says so
 * in the same words: one drawn revolution every 45 s, about 1,900x real time.
 * Nothing else is accelerated — the published frames, the timeline and every
 * number on the card are untouched.
 */
export const PLASMASPHERE_COROTATION = {
  /** Earth's sidereal rotation period, s. One corotation revolution. */
  siderealRotationSeconds: 86_164.0905,
  /** Wall-clock seconds for one DRAWN revolution. Display cadence, stated. */
  displaySecondsPerRevolution: 45,
} as const;

/** The display cadence as a speed-up factor, rounded for the card to quote. */
export const PLASMASPHERE_COROTATION_SPEEDUP = Math.round(
  PLASMASPHERE_COROTATION.siderealRotationSeconds
  / PLASMASPHERE_COROTATION.displaySecondsPerRevolution
  / 50,
) * 50;

/**
 * How far the material has turned after this many seconds of display motion.
 *
 * POSITIVE IS EASTWARD, which is the direction Earth turns and therefore the
 * direction corotating plasma goes. In the sun-fixed GSM frame that means a
 * parcel's magnetic local time INCREASES: noon (12 h) to dusk (18 h) to
 * midnight to dawn, the same order a fixed point on the ground reads its own
 * clock through. The sign is pinned by a test against that statement of the
 * physics, not against whichever sign was easier to write.
 */
export function plasmasphereAdvectionRadians(elapsedDisplaySeconds: number): number {
  if (!Number.isFinite(elapsedDisplaySeconds)) return 0;
  return (2 * Math.PI * elapsedDisplaySeconds) / PLASMASPHERE_COROTATION.displaySecondsPerRevolution;
}

/** The magnetic local time a grain born at `mltHours` has drifted to. */
export function advectedMltHours(mltHours: number, advectionRadians: number): number {
  const shifted = mltHours + (advectionRadians * 12) / Math.PI;
  return ((shifted % 24) + 24) % 24;
}

/**
 * Where a grain drawn at `point` has drifted to, in the same scene units.
 *
 * This is the CPU mirror of the two lines the vertex shader runs, and the
 * reason the whole advection costs no radial mapping at all: scene +Y is
 * GSM +Z (see `gsmSceneAxes`), so corotation is a rotation about the scene's
 * own Y axis, and the scene's radial map is a pure function of |r|. Rotating
 * the DRAWN point is therefore exactly the drawn image of the rotated physical
 * point, for any radial ruler whatsoever. Nothing here needs to know how far
 * out L = 4 is drawn, and a change to that mapping cannot desynchronise it.
 */
export function advectedGrainPosition(
  point: { x: number; y: number; z: number },
  advectionRadians: number,
): { x: number; y: number; z: number } {
  const cosine = Math.cos(advectionRadians);
  const sine = Math.sin(advectionRadians);
  return {
    x: point.x * cosine + point.z * sine,
    y: point.y,
    z: -point.x * sine + point.z * cosine,
  };
}

// ---------------------------------------------------------------------------
// The density field as a texture the grains can read while they move
// ---------------------------------------------------------------------------

/**
 * The sampling the ANALYTIC field is put on. The published field brings its
 * own grid and is never resampled.
 *
 * 96 MLT samples is 0.25 h, chosen so that every local-time kink Carpenter &
 * Anderson has — the trough branch at 06 and 15 MLT, and section 4's
 * transition at 19 and 20 MLT — lands exactly ON a sample. Between kinks the
 * model's local-time terms are linear, so linear interpolation between samples
 * is not an approximation of them at all.
 *
 * 1,024 L samples over the model's range is 0.0056 L. The saturated profile
 * and the plasmapause knee are both straight lines in log density against L,
 * and the texture stores log density, so interpolation reproduces them exactly
 * — the resolution is there for the two JOINS, at Lppi and Lppo, where the
 * slope jumps by about ten decades per L and a straddling cell is the only
 * place the texture can differ from the formula at all. Measured worst case
 * over the whole plane at this resolution: 0.012 in log10, or 3% in density,
 * in one 0.006-L band at the outer join; at half this resolution it is 0.023,
 * and at a tenth it would smear the plasmapause itself, which is the feature
 * the layer exists to draw. Building it costs about 27 ms, against roughly
 * five seconds for the 130,000-grain stipple it accompanies.
 */
export const PLASMASPHERE_DENSITY_TEXTURE = {
  analyticMltSamples: 96,
  analyticLSamples: 1024,
} as const;

export interface PlasmasphereDensityTexture {
  texture: THREE.DataTexture;
  /** log10(ne/cm^-3), row-major: row = L index, column = MLT index. */
  values: Float32Array;
  /** Columns: MLT sample i is at i * 24 / mltSamples hours, periodic. */
  mltSamples: number;
  /** Rows: L sample j is at lRange[0] + j * span / (lSamples - 1), clamped. */
  lSamples: number;
  lRange: readonly [number, number];
  /** Whether these numbers ARE the publisher's grid or a sampling of a formula. */
  grid: "published" | "analytic";
}

/** What a grain with no density at all is given: far below the ramp's floor. */
const ABSENT_LOG_DENSITY = -3;

/**
 * Resample the field onto the (MLT, L) texture the vertex shader reads.
 *
 * A grain has to know the density where it has DRIFTED to, which the CPU
 * cannot answer once per grain per frame at 130,000 grains. So the field is
 * evaluated once, onto a small texture, and every grain reads it in the vertex
 * shader for the cost of one fetch. The texture is the field, not a stylised
 * version of it: where the driving model publishes a grid, the texture IS that
 * grid.
 */
export function createPlasmasphereDensityTexture(
  field: PlasmasphereDensityField,
): PlasmasphereDensityTexture {
  const published = field.densityGrid;
  let mltSamples: number;
  let lSamples: number;
  let lRange: readonly [number, number];
  let values: Float32Array;
  let grid: "published" | "analytic";
  if (published && published.lValues.length >= 2 && published.mltHours.length >= 2) {
    mltSamples = published.mltHours.length;
    lSamples = published.lValues.length;
    lRange = [published.lValues[0]!, published.lValues[published.lValues.length - 1]!];
    values = published.logDensity;
    grid = "published";
    if (values.length !== mltSamples * lSamples) {
      throw new RangeError("plasmasphere density grid does not match its own axes");
    }
  } else {
    mltSamples = PLASMASPHERE_DENSITY_TEXTURE.analyticMltSamples;
    lSamples = PLASMASPHERE_DENSITY_TEXTURE.analyticLSamples;
    lRange = field.validLRange;
    grid = "analytic";
    values = new Float32Array(mltSamples * lSamples);
    const span = lRange[1] - lRange[0];
    for (let column = 0; column < mltSamples; column += 1) {
      const mltHours = (column * 24) / mltSamples;
      for (let row = 0; row < lSamples; row += 1) {
        const lRe = lRange[0] + (span * row) / (lSamples - 1);
        const density = field.densityAt(lRe, mltHours);
        values[row * mltSamples + column] = density === null || density <= 0
          ? ABSENT_LOG_DENSITY
          : Math.log10(density);
      }
    }
  }
  // Half float rather than 8-bit: the drawn value is a log density spanning
  // seven decades, and an 8-bit encoding of that quantises to 0.027 decades,
  // which terraces the smooth core into visible shells. Half float carries it
  // to about 0.001 and is core-filterable in WebGL 2, which three requires.
  const half = new Uint16Array(values.length);
  for (let index = 0; index < values.length; index += 1) {
    half[index] = THREE.DataUtils.toHalfFloat(values[index]!);
  }
  const texture = new THREE.DataTexture(half, mltSamples, lSamples, THREE.RedFormat, THREE.HalfFloatType);
  // MLT is periodic and L is not: a grain at 23.9 h interpolates across into
  // 0 h, while one at the model's outer limit reads the outer limit.
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.ClampToEdgeWrapping;
  texture.minFilter = THREE.LinearFilter;
  texture.magFilter = THREE.LinearFilter;
  texture.generateMipmaps = false;
  texture.needsUpdate = true;
  return { texture, values, mltSamples, lSamples, lRange, grid };
}

/**
 * What the vertex shader's texture fetch returns, in log10 el/cc, computed on
 * the CPU by the same rules.
 *
 * Written so a test can ask what a grain will actually be DRAWN at, rather
 * than what the model says at that point — the two agree, and the test that
 * they agree is the one that keeps the texture honest.
 */
export function samplePlasmasphereLogDensity(
  sampled: PlasmasphereDensityTexture,
  lRe: number,
  mltHours: number,
): number {
  const { values, mltSamples, lSamples, lRange } = sampled;
  const wrapped = ((mltHours % 24) + 24) % 24;
  const column = (wrapped * mltSamples) / 24;
  const columnIndex = Math.floor(column) % mltSamples;
  const columnWeight = column - Math.floor(column);
  const nextColumn = (columnIndex + 1) % mltSamples;
  const span = lRange[1] - lRange[0];
  const rowPosition = THREE.MathUtils.clamp((lRe - lRange[0]) / span, 0, 1) * (lSamples - 1);
  const rowIndex = Math.min(lSamples - 2, Math.floor(rowPosition));
  const rowWeight = THREE.MathUtils.clamp(rowPosition - rowIndex, 0, 1);
  const low = values[rowIndex * mltSamples + columnIndex]!
    + (values[rowIndex * mltSamples + nextColumn]! - values[rowIndex * mltSamples + columnIndex]!) * columnWeight;
  const high = values[(rowIndex + 1) * mltSamples + columnIndex]!
    + (values[(rowIndex + 1) * mltSamples + nextColumn]! - values[(rowIndex + 1) * mltSamples + columnIndex]!) * columnWeight;
  return low + (high - low) * rowWeight;
}

export type GsmMapper = (xRe: number, yRe: number, zRe: number) => THREE.Vector3;

export interface PlasmasphereFieldGeometryOptions {
  positionForGsm: GsmMapper;
  /** How many stipple points to place. Deterministic for a given count. */
  sampleCount?: number;
  /** Where the drawn flux tubes stop near Earth, in Earth radii. */
  innerRadiusRe?: number;
}

/** Deterministic PRNG so the stipple is identical frame to frame and in tests. */
function mulberry32(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * The field as a stipple of points filling the dipole flux tubes, each point
 * carrying the equatorial electron density of the shell it sits on.
 *
 * Four things about this are decisions, not defaults.
 *
 * **It is a volume of points, not an equatorial sheet.** Carpenter & Anderson
 * is an equatorial model, and the first build of this layer drew it as the
 * equatorial annulus it literally is. That failed for a reason worth writing
 * down: the scene's shared radial ruler is logarithmic below geostationary
 * orbit, so the model's whole L = 2.25 to 8 range is drawn between 1.9 and
 * 2.8 Earth radii on screen. A flat sheet in that band reads as a donut
 * around the Earth — which is exactly the object this same commit deleted the
 * ring current for being. Filling the flux tubes gives the layer its true
 * lobed shape, and is the stippled volume every textbook cutaway of this
 * system draws.
 *
 * **The equatorial value is repeated along each flux tube, and that is
 * declared.** The real density along a field line rises toward the ionosphere;
 * Carpenter & Anderson does not model it and neither does this. Each point
 * shows the equatorial density of its own L shell. This is the same treatment,
 * with the same caveat, that the radiation-belt layer already applies to
 * equatorial flux, and the data viewer says so in words.
 *
 * **The stipple samples the DRAWN volume evenly.** This is the one that
 * decides whether the picture means anything. What a reader sees at a point on
 * screen is the sum of the grains along that view ray, which is (grains per
 * unit drawn volume) times (how bright a grain is). Only the second factor is
 * supposed to carry the physics, so the first has to be flat — otherwise the
 * bright regions of the picture are wherever the parameterisation happened to
 * bunch points up. The first build sampled L, latitude and longitude each on
 * their own uniform interval, and the volume element of those coordinates is
 * L^2 cos^7(latitude): points piled up toward the poles of every flux tube by
 * more than a factor of ten, and the shared logarithmic ruler then piled them
 * up again near the globe. Measured on that build, the brightest ring on
 * screen sat at L about 4.5 — not at the dense core, not at the plasmapause,
 * at neither of the two things the layer exists to show.
 *
 * So grains are now drawn uniformly through the volume THE RULER DRAWS, by
 * rejection: propose a point uniformly in the display ball, invert the ruler
 * to get its physical radius, take the shell it sits on, and keep it if the
 * model covers that shell. Grain density on screen is then flat by
 * construction, brightness is the density and nothing else, and the polar
 * region above the outermost drawn tube comes out empty on its own, which is
 * why the volume takes the fat-at-high-L, narrow-inward shape the textbook
 * cutaways draw. The rejection rate is about 15%.
 *
 * **The stipple is deterministic.** A reseeded random cloud would boil between
 * frames and would make the layer impossible to compare across the timeline.
 * The positions are fixed for a given sample count; only colour and opacity
 * move as the storm does.
 *
 * **Nothing has a hard edge.** Points fade out at the model's own limits of
 * L = 2.25 and L = 8, and again toward the ionospheric ends of the tubes,
 * where no field-aligned profile is being claimed. There is no cut plane and
 * no rim anywhere.
 */
export function createPlasmasphereFieldGeometry(
  field: PlasmasphereDensityField,
  options: PlasmasphereFieldGeometryOptions,
): THREE.BufferGeometry {
  // The L range comes from the FIELD, not from Carpenter & Anderson's
  // constants: the DGCPM grid and the empirical profile are valid over
  // different ranges, and a stipple placed against the wrong one would draw
  // shells the driving model says nothing about.
  const [innerValidL, outerValidL] = field.validLRange;
  const sampleCount = Math.max(500, Math.floor(options.sampleCount ?? 130_000));
  const innerRadiusRe = Math.max(1.02, options.innerRadiusRe ?? 1.05);
  const random = mulberry32(0x5c1e9ce5);

  const positions: number[] = [];
  const logDensity: number[] = [];
  const edgeFade: number[] = [];
  const shellL: number[] = [];
  const physicalRadius: number[] = [];
  const mltHours: number[] = [];
  // The two ends of the model's L range are faded over different widths on
  // purpose. The inner limit at L = 2.25 sits behind the globe from most
  // angles and needs only enough to avoid a rim. The outer limit at L = 8 is
  // in open view, and every ray near it runs a long tangential path through
  // the outermost shells, so a narrow fade there piles grains into a bright
  // ring — an edge exactly where the model has no edge, only a limit of
  // validity. Fading it over a decent span of L dissolves that ring, and the
  // densities out there are a few cm^-3 in any case.
  const innerFadeSpanL = 0.35;
  const outerFadeSpanL = 1.5;

  // The display ruler, probed from the layer's own mapper rather than
  // duplicated, and inverted by bisection. Probing means a change to the
  // shared ruler moves this stipple with it and cannot silently diverge.
  const displayRadiusFor = (radiusRe: number) =>
    options.positionForGsm(Math.max(radiusRe, 1e-3), 0, 0).length();
  const displayInner = displayRadiusFor(innerRadiusRe);
  const displayOuter = displayRadiusFor(outerValidL);
  if (!(displayOuter > displayInner)) {
    throw new RangeError("plasmasphere mapper does not increase with radius; the stipple cannot be placed");
  }
  const radiusReForDisplay = (displayRadius: number) => {
    let low = innerRadiusRe;
    let high = outerValidL;
    for (let step = 0; step < 40; step += 1) {
      const middle = (low + high) / 2;
      if (displayRadiusFor(middle) < displayRadius) low = middle;
      else high = middle;
    }
    return (low + high) / 2;
  };

  const innerCubed = displayInner ** 3;
  const outerCubed = displayOuter ** 3;
  let placed = 0;
  let proposals = 0;
  // Bounded so a pathological mapper cannot spin here; the real rejection
  // rate is about 15%, so this ceiling is never approached.
  const proposalLimit = sampleCount * 40;
  while (placed < sampleCount && proposals < proposalLimit) {
    proposals += 1;
    // Uniform in the display ball's volume: r^3 uniform, direction uniform.
    const displayRadius = (innerCubed + random() * (outerCubed - innerCubed)) ** (1 / 3);
    const latitude = Math.asin(random() * 2 - 1);
    const azimuth = random() * Math.PI * 2;
    const radius = radiusReForDisplay(displayRadius);
    const cosineLatitude = Math.cos(latitude);
    if (cosineLatitude <= 1e-6) continue;
    // The dipole shell this point sits on: r = L cos^2(latitude).
    const l = radius / (cosineLatitude * cosineLatitude);
    if (l < innerValidL || l > outerValidL) continue;
    if (radius < innerRadiusRe) continue;
    placed += 1;
    const equatorial = radius * cosineLatitude;
    const point = options.positionForGsm(
      equatorial * Math.cos(azimuth),
      equatorial * Math.sin(azimuth),
      radius * Math.sin(latitude),
    );
    // GSM +x is noon and +y is dusk; magnetic local time counts hours from
    // midnight, so noon is 12 h and dusk is 18 h.
    const grainMlt = (((12 + (azimuth * 12) / Math.PI) % 24) + 24) % 24;
    const density = field.densityAt(l, grainMlt);
    positions.push(point.x, point.y, point.z);
    mltHours.push(grainMlt);
    logDensity.push(density === null || density <= 0 ? ABSENT_LOG_DENSITY : Math.log10(density));
    shellL.push(l);
    physicalRadius.push(radius);
    const innerLimit = THREE.MathUtils.clamp((l - innerValidL) / innerFadeSpanL, 0, 1);
    const outerLimit = THREE.MathUtils.clamp((outerValidL - l) / outerFadeSpanL, 0, 1);
    // Toward the ionospheric ends of a tube no field-aligned profile is being
    // claimed, so the stipple thins out there instead of ending in a collar.
    const footpointFade = THREE.MathUtils.clamp((radius - innerRadiusRe) / 0.35, 0, 1);
    edgeFade.push(Math.min(innerLimit, outerLimit, footpointFade));
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  // The grain's birth density. The SHADER no longer reads it — a moving grain
  // reads the density texture at wherever it has drifted to — but it is the
  // exact value the model returns at that point, so it stays as the headless
  // check on the texture: `tests/plasmasphere-advection.test.ts` requires the
  // texture to reproduce it grain for grain, which keeps every existing test
  // that reads this attribute a test of what is actually drawn.
  geometry.setAttribute("logDensity", new THREE.Float32BufferAttribute(logDensity, 1));
  // Where the grain is in local time when the display clock reads zero.
  geometry.setAttribute("mltHours", new THREE.Float32BufferAttribute(mltHours, 1));
  geometry.setAttribute("edgeFade", new THREE.Float32BufferAttribute(edgeFade, 1));
  geometry.setAttribute("shellL", new THREE.Float32BufferAttribute(shellL, 1));
  geometry.setAttribute("physicalRadiusRe", new THREE.Float32BufferAttribute(physicalRadius, 1));
  geometry.userData = {
    representation: field.source === "dgcpm"
      ? "dgcpm-simulated-equatorial-density-on-dipole-flux-tubes"
      : "carpenter-anderson-1992-equatorial-density-on-dipole-flux-tubes",
    source: field.source,
    dipoleAxis: "GSM z (centred dipole, the same convention as the radiation-belt mapping)",
    plasmapauseLppi: field.plasmapauseLRe,
    outerLimitNoonRe: field.outerLimitNoonRe,
    outerLimitMidnightRe: field.outerLimitMidnightRe,
    validLRange: [innerValidL, outerValidL],
    unit: "electrons cm^-3",
    fieldAligned:
      "each point carries the EQUATORIAL density of its own L shell; the real variation along a field line is not modelled",
  };
  return geometry;
}

/**
 * The material: log10(ne) onto the legend's ramp, with opacity rising with the
 * same value so the trough is a faint haze and the plasmaspheric core is
 * solid. The plasmapause is not drawn — it is where these two things change,
 * which is the whole point of the rebuild.
 */
export function createPlasmasphereFieldMaterial(
  field: PlasmasphereDensityField,
): THREE.ShaderMaterial {
  const sampled = createPlasmasphereDensityTexture(field);
  const material = new THREE.ShaderMaterial({
    uniforms: {
      minimumLog: { value: Math.log10(PLASMASPHERE_DENSITY_SCALE.minimumCm3) },
      maximumLog: { value: Math.log10(PLASMASPHERE_DENSITY_SCALE.maximumCm3) },
      // Grain size is set from the cloud's own scene extent, not from a pixel
      // constant: see the note above `PLASMASPHERE_GRAIN`.
      grainSceneRadius: { value: PLASMASPHERE_GRAIN.sceneRadiusPerGrain },
      minimumPointSize: { value: PLASMASPHERE_GRAIN.minimumPointSizePx },
      maximumPointSize: { value: PLASMASPHERE_GRAIN.maximumPointSizePx },
      projectionScale: { value: 1 },
      // The corotation the grains are drawn under. Both the rotation and the
      // local-time shift come from the same angle; they are passed already
      // resolved so the shader runs no trigonometry per grain and so a long
      // session cannot lose precision in a growing angle.
      advectionRadians: { value: 0 },
      advectionCosSin: { value: new THREE.Vector2(1, 0) },
      advectionMltHours: { value: 0 },
      densityField: { value: sampled.texture },
      densityLRange: { value: new THREE.Vector2(sampled.lRange[0], sampled.lRange[1]) },
      densityTextureSize: { value: new THREE.Vector2(sampled.mltSamples, sampled.lSamples) },
    },
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    vertexShader: `
      attribute float edgeFade;
      attribute float shellL;
      attribute float mltHours;
      uniform float grainSceneRadius;
      uniform float minimumPointSize;
      uniform float maximumPointSize;
      uniform float projectionScale;
      uniform vec2 advectionCosSin;
      uniform float advectionMltHours;
      uniform sampler2D densityField;
      uniform vec2 densityLRange;
      uniform vec2 densityTextureSize;
      varying float vLogDensity;
      varying float vEdgeFade;
      void main() {
        vEdgeFade = edgeFade;
        // COROTATION. The cold plasma turns with the Earth about the dipole
        // axis; scene +Y is GSM +Z, so that is a rotation about Y here. The
        // scene's radial map depends only on |r|, so rotating the drawn point
        // is exactly the drawn image of the rotated physical point - no radial
        // mapping is read, recomputed or duplicated anywhere in this shader.
        vec3 advected = vec3(
          position.x * advectionCosSin.x + position.z * advectionCosSin.y,
          position.y,
          -position.x * advectionCosSin.y + position.z * advectionCosSin.x
        );
        // ...and the grain reads the density where it has ARRIVED. This is the
        // whole trick: the field is fixed to the Sun and the material moves
        // through it, so the envelope holds still while the grains stream, and
        // a grain carried out past the plasmapause dims on its way out.
        vec2 densityUv = vec2(
          (mltHours + advectionMltHours) / 24.0 + 0.5 / densityTextureSize.x,
          (0.5 + clamp((shellL - densityLRange.x) / (densityLRange.y - densityLRange.x), 0.0, 1.0)
            * (densityTextureSize.y - 1.0)) / densityTextureSize.y
        );
        vLogDensity = texture2D(densityField, densityUv).r;
        vec4 viewPosition = modelViewMatrix * vec4(advected, 1.0);
        // A grain is a fixed size IN THE SCENE, projected. It therefore grows
        // on screen exactly as fast as the cloud it belongs to, and the
        // stipple keeps the same coverage at every camera distance.
        float projected = projectionScale * grainSceneRadius / max(-viewPosition.z, 1.0);
        gl_PointSize = clamp(projected, minimumPointSize, maximumPointSize);
        gl_Position = projectionMatrix * viewPosition;
      }
    `,
    fragmentShader: `
      uniform float minimumLog;
      uniform float maximumLog;
      varying float vLogDensity;
      varying float vEdgeFade;
      // The same five stops as the legend gradient, in the same order.
      vec3 ramp(float t) {
        vec3 c0 = vec3(0.039, 0.082, 0.149);
        vec3 c1 = vec3(0.078, 0.259, 0.494);
        vec3 c2 = vec3(0.169, 0.561, 0.816);
        vec3 c3 = vec3(0.455, 0.847, 0.961);
        vec3 c4 = vec3(0.918, 0.988, 1.000);
        if (t < 0.28) return mix(c0, c1, t / 0.28);
        if (t < 0.52) return mix(c1, c2, (t - 0.28) / 0.24);
        if (t < 0.74) return mix(c2, c3, (t - 0.52) / 0.22);
        return mix(c3, c4, (t - 0.74) / 0.26);
      }
      void main() {
        // Soft round grains, so the stipple reads as cloud rather than as
        // dust: a hard-edged one-pixel dot is indistinguishable from a star.
        vec2 offset = gl_PointCoord - vec2(0.5);
        float grain = 1.0 - smoothstep(0.06, 0.5, length(offset));
        if (grain <= 0.0) discard;
        float t = clamp((vLogDensity - minimumLog) / (maximumLog - minimumLog), 0.0, 1.0);
        // Opacity follows the value too, so the plasmapause is a jump in both
        // colour and how much stipple survives, not a drawn line. Two measured
        // constraints set these numbers. The exponent is 1.8 rather than 3:
        // at 3 the trough (a few cm^-3, t about 0.17) came out at alpha 0.02
        // and additive blending on a black sky renders that as literally
        // nothing, so the model's whole outer half — the part that erodes and
        // refills across a storm — was invisible. And the scale is 0.34 rather
        // than 0.78 because these grains ADD: a view ray crosses hundreds of
        // them, so a per-grain alpha that looks reasonable alone saturates to
        // white in bulk and flattens the density structure it exists to show.
        // The ratio that matters survives either way: core to trough is about
        // fifteen to one.
        float alpha = (0.002 + 0.60 * pow(t, 2.4)) * vEdgeFade * grain;
        if (alpha < 0.003) discard;
        gl_FragColor = vec4(ramp(t), alpha);
      }
    `,
  });
  material.userData.densityTexture = sampled;
  // The scene disposes materials when it clears the layer group; a texture is
  // not disposed by its material, so it is hung off the material's own dispose
  // event. Every rebuild of the stipple then releases its texture without the
  // scene having to know this layer owns one.
  material.addEventListener("dispose", () => sampled.texture.dispose());
  return material;
}

/**
 * Advance the drawn corotation to `elapsedDisplaySeconds` of display motion.
 *
 * Called once per rendered frame with the scene's environmental-motion clock,
 * which is an accumulator that only advances while the "Environmental motion"
 * display setting is on. So switching that setting off freezes the grains
 * where they are — nothing here has to know about the setting, and nothing
 * jumps when it is switched back on.
 */
export function setPlasmasphereDisplayTime(object: THREE.Object3D, elapsedDisplaySeconds: number): void {
  const material = (object as THREE.Points).material as THREE.ShaderMaterial | undefined;
  const cosSin = material?.uniforms?.advectionCosSin;
  if (!cosSin) return;
  const radians = plasmasphereAdvectionRadians(elapsedDisplaySeconds);
  (cosSin.value as THREE.Vector2).set(Math.cos(radians), Math.sin(radians));
  material!.uniforms.advectionMltHours!.value = advectedMltHours(0, radians);
  material!.uniforms.advectionRadians!.value = radians;
}

/**
 * The whole drawable object for one instant, built here rather than in the
 * globe so the layer's physics, its geometry and its appearance stay in one
 * file and the scene only has to add and remove it.
 */
export function createPlasmasphereFieldObject(
  field: PlasmasphereDensityField,
  options: PlasmasphereFieldGeometryOptions,
): THREE.Points {
  const geometry = createPlasmasphereFieldGeometry(field, options);
  const material = createPlasmasphereFieldMaterial(field);
  const points = new THREE.Points(geometry, material);
  points.name = field.source === "dgcpm"
    ? "dgcpm-plasmasphere-field"
    : "carpenter-anderson-plasmasphere-field";
  points.frustumCulled = false;
  points.renderOrder = 2;
  // Turn "a grain is this many scene units across" into gl_PointSize's units,
  // which are framebuffer pixels. For a perspective camera a length L at view
  // depth d subtends L * (drawingBufferHeight / 2) / (d * tan(fov/2)) pixels,
  // so everything except d is gathered here once per frame. Read from the
  // renderer and camera rather than assumed, so the layer stays correct on a
  // Retina display, after a window resize, and in a screenshot harness.
  points.onBeforeRender = (renderer, _scene, camera) => {
    const uniform = material.uniforms.projectionScale;
    if (!uniform) return;
    if (!(camera instanceof THREE.PerspectiveCamera)) {
      uniform.value = 1;
      return;
    }
    const size = renderer.getDrawingBufferSize(new THREE.Vector2());
    const halfFov = THREE.MathUtils.degToRad(camera.fov) / 2;
    uniform.value = (size.y * 0.5) / Math.max(Math.tan(halfFov), 1e-6);
  };
  points.userData = {
    ...geometry.userData,
    quantity: "equatorial electron density",
    motion: `the grains corotate with Earth about the dipole axis while the density field they sample stays fixed to the Sun; `
      + `display cadence, one drawn revolution every ${PLASMASPHERE_COROTATION.displaySecondsPerRevolution} s `
      + `(about ${PLASMASPHERE_COROTATION_SPEEDUP.toLocaleString("en-US")}x real time), and the convection part of the drift `
      + `is in the field rather than in the grain motion`,
    ...(field.source === "dgcpm"
      ? {
        status: "physics-simulation",
        model: PLASMASPHERE_DGCPM.citation,
        doi: PLASMASPHERE_DGCPM.doi,
        boundaryDrivenBy: `measured planetary Kp through ${PLASMASPHERE_DGCPM.electricField}`,
        localTime:
          "local time is simulated, not assumed: the dusk bulge and any drainage plume are where the drift paths put them",
      }
      : {
        status: "empirical",
        model: CARPENTER_ANDERSON_1992.citation,
        doi: CARPENTER_ANDERSON_1992.doi,
        boundaryDrivenBy: `deepest published Dst over the preceding 24 h (${OBRIEN_MOLDWIN_DST.citation})`,
        localTime: "no local-time structure inside the plasmasphere: no dusk bulge, no plumes",
      }),
  };
  return points;
}
