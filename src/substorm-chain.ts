/**
 * The substorm chain, as timing rather than as geometry.
 *
 * ## What this module decides, and what it refuses to
 *
 * The owner's question was the right one: *"I just don't know if we can show it
 * on the main page because I don't know what data we have to derive it."*
 *
 * Nobody measures the plasma sheet's three-dimensional shape continuously, and
 * this site is not going to pretend otherwise. What IS measured, continuously
 * and by instruments this project already ingests, is every beat of the
 * SEQUENCE:
 *
 *   - **loading** — southward IMF Bz at L1, propagated to Earth arrival. 587
 *     samples at 5-minute cadence over 48.8 hours, in the same
 *     `magnetopause.driverSeries` the Shue boundary is already driven from.
 *   - **the snap** — a sharp negative excursion of the westward auroral
 *     electrojet index. That IS a substorm onset; it is the operational
 *     definition. See the evidence note below for when this site has one.
 *   - **the ring-current response** — Dst, measured hourly by Kyoto over seven
 *     days, and the Dessler-Parker-Sckopke energy derived from it.
 *
 * So the split this module enforces is the one the site uses everywhere:
 * **the geometry is empirical and badged as such; the timing and the intensity
 * are measured.** Nothing here invents an onset. If no index that can show an
 * onset is available for the window being drawn, `substormStateAt` says so in
 * `onsetEvidence` and the layer draws loading and response without a snap,
 * rather than drawing a snap the data does not support.
 *
 * ## The onset criterion, stated so it can be argued with
 *
 * `SUBSTORM_ONSET_CRITERION`. A sample is an onset when
 *
 *   1. the index falls by at least `minimumDropNt` within `windowMinutes`;
 *   2. it was NOT already falling that fast in the preceding `windowMinutes`,
 *      which is what picks the START of an expansion rather than a point in
 *      the middle of one;
 *   3. at least `refractoryMinutes` have passed since the previous onset.
 *
 * Rule 2 is the one that does the work, and it is also the one that decides the
 * false-positive behaviour: without it a single deep substorm is reported as a
 * run of consecutive onsets all the way down its own expansion. The thresholds
 * are the conventional ones for an SML-based list (Newell and Gjerloev 2011 use
 * a 15-minute window and a 100 nT fall on 1-minute data); the window here is
 * wider because the series this site can reach is decimated to 10 minutes, and
 * a criterion has to be stated against the cadence it will actually run on.
 *
 * ## Which index, and what that costs in evidence class
 *
 * **SuperMAG SML, where the site has it.** It is the real thing: a lower
 * envelope over a large ground magnetometer array. The site holds it for one
 * window — the May 2024 Gannon storm, 720 samples at 10 minutes, inside the
 * event replay, peaking at -4,057.6 nT — because SuperMAG's own mirror on
 * bigmem covers that week and because SuperMAG's position, checked with
 * JHU/APL, is that a derived VISUALISATION may be published with citation while
 * the SERIES may not be redistributed.
 *
 * **Nothing, on the live timeline.** There is no auroral-electrojet index in
 * any live feed this site fetches, and SuperMAG lags: the repository's own
 * ingest tests record 1,440 of 1,440 minutes returning the fill value for
 * recent dates. So for "now" the honest answer is that the onset TIME is not
 * known here, and this module returns `onsetEvidence: "none"`.
 *
 * **Measured Dst, as a stated second best.** A sustained fall in Dst is the
 * ring current being fed, which is the far end of the same chain. It is not an
 * onset time — Kyoto is hourly and a substorm expansion lasts about an hour —
 * and it is labelled `"ring-current-response"` rather than `"onset"` wherever
 * it is used, so a reader is never told the site knows a minute it does not.
 */

/** One sample of a geomagnetic index. */
export interface IndexSample {
  /** UTC milliseconds. */
  atMs: number;
  /** The index value, nT. Null where the source published no value. */
  valueNt: number | null;
}

export interface SubstormOnsetCriterion {
  /** How far the index must fall to count, nT. Positive number, a fall. */
  minimumDropNt: number;
  /** Over how long that fall must happen. */
  windowMinutes: number;
  /** How long after an onset another one may be reported. */
  refractoryMinutes: number;
}

/**
 * The shipped thresholds. See the module note for where they come from and for
 * what rule 2 does to the false-positive behaviour.
 */
export const SUBSTORM_ONSET_CRITERION: SubstormOnsetCriterion = {
  minimumDropNt: 100,
  windowMinutes: 30,
  refractoryMinutes: 60,
};

export interface SubstormOnset {
  /** UTC milliseconds of the first sample of the fall. */
  atMs: number;
  /** The index at onset, nT. */
  indexNt: number;
  /**
   * How far it fell within `windowMinutes`, nT, as a positive magnitude. This
   * is the quantity the criterion tests, and it is NOT the depth of the
   * excursion — a fast shallow drop and the first thirty minutes of a deep one
   * look the same to it.
   */
  dropNt: number;
  /**
   * How deep the excursion actually went, nT, followed forward until the index
   * climbs back above where it started or `EXCURSION_SEARCH_MINUTES` runs out.
   * This is the number worth showing a reader, and it is what scales the drawn
   * injection.
   */
  minimumNt: number;
  /** When it reached that minimum. */
  minimumAtMs: number;
}

function usable(samples: readonly IndexSample[]): IndexSample[] {
  return samples
    .filter((sample) => Number.isFinite(sample.atMs) && sample.valueNt !== null && Number.isFinite(sample.valueNt))
    .sort((a, b) => a.atMs - b.atMs);
}

/**
 * The index's value at or after `fromMs`, within `spanMinutes`, at its lowest.
 * Returns null when the window holds no sample.
 */
function minimumWithin(
  samples: readonly IndexSample[],
  startIndex: number,
  spanMs: number,
  stopWhenAboveNt?: number,
) {
  const start = samples[startIndex];
  if (!start) return null;
  let lowest = start.valueNt as number;
  let lowestAt = start.atMs;
  let descended = false;
  for (let index = startIndex; index < samples.length; index += 1) {
    const sample = samples[index]!;
    if (sample.atMs - start.atMs > spanMs) break;
    const value = sample.valueNt as number;
    // Following an excursion rather than scanning a fixed window: it ends when
    // the index climbs back above where it started, which is recovery.
    //
    // `descended` is load-bearing. An onset is flagged on the LAST sample
    // before the fall, so the very next sample can still be sitting on the
    // pre-onset level; without this the excursion would end before it began
    // and every onset would report its own starting value as its depth.
    if (stopWhenAboveNt !== undefined && descended && value >= stopWhenAboveNt) break;
    if (stopWhenAboveNt !== undefined && value < stopWhenAboveNt) descended = true;
    if (value < lowest) {
      lowest = value;
      lowestAt = sample.atMs;
    }
  }
  return { lowest, lowestAt };
}

/** How far forward an excursion is followed before giving up on its recovery. */
export const EXCURSION_SEARCH_MINUTES = 240;

/**
 * Substorm onsets in an auroral-electrojet index.
 *
 * The series must be an index whose NEGATIVE excursions are the signal — SML,
 * SME's lower envelope, AL. Handing this Dst produces nonsense, which is why
 * the caller that has only Dst uses `detectRingCurrentInjections` instead.
 */
export function detectSubstormOnsets(
  samples: readonly IndexSample[],
  criterion: SubstormOnsetCriterion = SUBSTORM_ONSET_CRITERION,
): SubstormOnset[] {
  const series = usable(samples);
  if (series.length < 3) return [];
  const windowMs = criterion.windowMinutes * 60_000;
  const refractoryMs = criterion.refractoryMinutes * 60_000;
  const onsets: SubstormOnset[] = [];
  for (let index = 0; index < series.length; index += 1) {
    const sample = series[index]!;
    const value = sample.valueNt as number;
    const ahead = minimumWithin(series, index, windowMs);
    if (!ahead) continue;
    const drop = value - ahead.lowest;
    if (drop < criterion.minimumDropNt) continue;

    // Rule 2: it must not already have been falling this fast. Without this a
    // single deep substorm reports as a run of onsets down its own expansion.
    let alreadyFalling = false;
    for (let back = index - 1; back >= 0; back -= 1) {
      const previous = series[back]!;
      if (sample.atMs - previous.atMs > windowMs) break;
      if ((previous.valueNt as number) - value >= criterion.minimumDropNt) { alreadyFalling = true; break; }
    }
    if (alreadyFalling) continue;

    // Rule 3.
    const last = onsets[onsets.length - 1];
    if (last && sample.atMs - last.atMs < refractoryMs) continue;

    // How deep it actually went. The detection window is 30 minutes because
    // that is what the criterion tests; the excursion itself routinely runs
    // for hours, and reporting the window's minimum as the depth understates
    // every large substorm in the record.
    const excursion = minimumWithin(series, index, EXCURSION_SEARCH_MINUTES * 60_000, value);
    onsets.push({
      atMs: sample.atMs,
      indexNt: value,
      dropNt: drop,
      minimumNt: excursion ? excursion.lowest : ahead.lowest,
      minimumAtMs: excursion ? excursion.lowestAt : ahead.lowestAt,
    });
  }
  return onsets;
}

/**
 * Sustained falls in Dst — the ring current being fed.
 *
 * Deliberately a different function with a different name from the one above,
 * because it answers a different question and carries a weaker claim. Hourly
 * Dst cannot time a substorm expansion; what it can do is say that over these
 * hours the ring current was being built, which is the end of the same chain
 * and is measured.
 */
export function detectRingCurrentInjections(
  samples: readonly IndexSample[],
  options: { minimumDropNt?: number; windowMinutes?: number } = {},
): SubstormOnset[] {
  return detectSubstormOnsets(samples, {
    minimumDropNt: options.minimumDropNt ?? 20,
    windowMinutes: options.windowMinutes ?? 180,
    refractoryMinutes: 180,
  });
}

/** Where in the cycle the drawn state is. */
export type SubstormPhase = "quiet" | "growth" | "expansion" | "recovery";

/**
 * What the site knows about the onset time for the window being drawn. This is
 * the field that keeps the layer honest, and the key card prints it.
 */
export type OnsetEvidence = "observed-electrojet" | "ring-current-response" | "none";

export interface SubstormState {
  phase: SubstormPhase;
  /**
   * How loaded the tail is, 0 to 1, from the measured southward-Bz integral.
   * This is the growth phase, and it is measured wherever the driver series
   * reaches.
   */
  loading: number;
  /**
   * How hard the sheet is injecting right now, 0 to 1. Zero unless an onset is
   * known, so a window with no electrojet index never shows an injection.
   */
  injection: number;
  onset: SubstormOnset | null;
  minutesSinceOnset: number | null;
  onsetEvidence: OnsetEvidence;
  /** The southward-Bz integral itself, nT-minutes, for the card to print. */
  southwardBzNtMinutes: number | null;
  /** The measured Bz at this instant, nT, or null outside the driver record. */
  bzGsmNt: number | null;
}

export interface SubstormChainInput {
  /** Bz GSM at Earth arrival. `magnetopause.driverSeries` supplies this. */
  bz: readonly IndexSample[];
  /** An auroral-electrojet index, if the window has one. */
  electrojet?: readonly IndexSample[] | null;
  /** Dst, used only as the stated second best when there is no electrojet. */
  dst?: readonly IndexSample[] | null;
}

/**
 * How long a window of southward Bz counts as loading the tail, and how much of
 * it is a full load.
 *
 * A textbook growth phase runs 30 to 60 minutes; the reference here is 90
 * minutes of Bz at -5 nT, which is 450 nT-minutes and a solidly driven but
 * unremarkable interval. Above that the loading saturates at 1 rather than
 * running away, because the drawn thickness has to stay inside a range a reader
 * can compare across a storm.
 */
export const LOADING_WINDOW_MINUTES = 90;
export const LOADING_REFERENCE_NT_MINUTES = 450;

/** Expansion lasts about this long; recovery about this long after that. */
export const EXPANSION_MINUTES = 30;
export const RECOVERY_MINUTES = 90;

/** The drop that counts as a fully driven injection, nT. */
export const INJECTION_REFERENCE_DROP_NT = 400;

function clamp01(value: number) {
  return Math.min(1, Math.max(0, value));
}

/**
 * The time-integral of southward Bz over the loading window, in nT-minutes.
 *
 * Trapezoidal over the samples that fall inside the window, counting only the
 * southward part: northward Bz does not unload the tail on this timescale, it
 * simply stops loading it. Returns null when the window holds no measurement,
 * which is what happens forward of now and is not the same as zero.
 */
export function southwardBzIntegral(
  samples: readonly IndexSample[],
  atMs: number,
  windowMinutes: number = LOADING_WINDOW_MINUTES,
): number | null {
  const series = usable(samples);
  const from = atMs - windowMinutes * 60_000;
  let total = 0;
  let counted = 0;
  for (let index = 1; index < series.length; index += 1) {
    const previous = series[index - 1]!;
    const current = series[index]!;
    if (current.atMs <= from || previous.atMs >= atMs) continue;
    const spanMinutes = (Math.min(current.atMs, atMs) - Math.max(previous.atMs, from)) / 60_000;
    if (!(spanMinutes > 0)) continue;
    const south = (Math.max(0, -(previous.valueNt as number)) + Math.max(0, -(current.valueNt as number))) / 2;
    total += south * spanMinutes;
    counted += 1;
  }
  return counted > 0 ? total : null;
}

/** The measured value at an instant, by nearest sample inside a tolerance. */
export function sampleAtMs(
  samples: readonly IndexSample[],
  atMs: number,
  toleranceMinutes = 30,
): number | null {
  const series = usable(samples);
  let best: number | null = null;
  let bestGap = Infinity;
  for (const sample of series) {
    const gap = Math.abs(sample.atMs - atMs);
    if (gap < bestGap) { bestGap = gap; best = sample.valueNt as number; }
  }
  return bestGap <= toleranceMinutes * 60_000 ? best : null;
}

/**
 * The whole chain at one instant.
 *
 * The one thing to read carefully here is that `injection` is zero whenever
 * `onsetEvidence` is `"none"`. That is not a fallback value, it is the point:
 * with no index that can show an onset, the site does not know that the sheet
 * snapped, and the layer must not draw it snapping.
 */
export function substormStateAt(input: SubstormChainInput, atMs: number): SubstormState {
  const bzGsmNt = sampleAtMs(input.bz, atMs, 15);
  const southwardBzNtMinutes = southwardBzIntegral(input.bz, atMs);
  const loading = southwardBzNtMinutes === null
    ? 0
    : clamp01(southwardBzNtMinutes / LOADING_REFERENCE_NT_MINUTES);

  const electrojet = input.electrojet ? usable(input.electrojet) : [];
  const hasElectrojet = electrojet.length >= 3
    && atMs >= electrojet[0]!.atMs
    && atMs <= electrojet[electrojet.length - 1]!.atMs;

  let onsets: SubstormOnset[] = [];
  let onsetEvidence: OnsetEvidence = "none";
  if (hasElectrojet) {
    onsets = detectSubstormOnsets(electrojet);
    onsetEvidence = "observed-electrojet";
  } else if (input.dst && input.dst.length >= 3) {
    const dst = usable(input.dst);
    if (dst.length >= 3 && atMs >= dst[0]!.atMs && atMs <= dst[dst.length - 1]!.atMs) {
      onsets = detectRingCurrentInjections(dst);
      onsetEvidence = "ring-current-response";
    }
  }

  let onset: SubstormOnset | null = null;
  for (const candidate of onsets) {
    if (candidate.atMs <= atMs) onset = candidate;
    else break;
  }
  const minutesSinceOnset = onset ? (atMs - onset.atMs) / 60_000 : null;

  let injection = 0;
  if (onset && minutesSinceOnset !== null && onsetEvidence !== "none") {
    const scale = clamp01(onset.dropNt / INJECTION_REFERENCE_DROP_NT);
    // Fast up, slow down: an expansion turns on in minutes and decays over an
    // hour and a half. Both numbers are display shaping of a measured event,
    // not a measurement of the injection rate, and the card says so.
    const rise = clamp01(minutesSinceOnset / 8);
    const decay = minutesSinceOnset <= EXPANSION_MINUTES
      ? 1
      : Math.exp(-(minutesSinceOnset - EXPANSION_MINUTES) / (RECOVERY_MINUTES / 2));
    injection = clamp01(scale * rise * decay);
  }

  let phase: SubstormPhase;
  if (minutesSinceOnset !== null && minutesSinceOnset >= 0 && minutesSinceOnset < EXPANSION_MINUTES) {
    phase = "expansion";
  } else if (minutesSinceOnset !== null && minutesSinceOnset >= EXPANSION_MINUTES
    && minutesSinceOnset < EXPANSION_MINUTES + RECOVERY_MINUTES) {
    phase = "recovery";
  } else if (loading >= 0.35) {
    phase = "growth";
  } else {
    phase = "quiet";
  }

  return {
    phase,
    loading,
    injection,
    onset,
    minutesSinceOnset,
    onsetEvidence,
    southwardBzNtMinutes,
    bzGsmNt,
  };
}
