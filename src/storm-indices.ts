/**
 * The storm narrative, browser side.
 *
 * `pipeline/storm_indices.py` fetches and reduces; this module reads what it
 * published and answers one question for the interface: **what was the storm
 * doing at the moment the visitor has scrubbed to?**
 *
 * The narrative is a causal chain with real, visible lags, and the whole point
 * of putting it on one time axis is that a visitor can watch it develop:
 *
 *   IMF Bz turns south
 *     -> the clock angle swings toward 180 degrees
 *     -> the Newell coupling function rises            within minutes
 *     -> the magnetopause standoff drops               within minutes
 *     -> the auroral oval expands equatorward          tens of minutes
 *     -> Dst falls, and Dst IS the ring current        hours
 *     -> the outer belt drops out and refills          hours to days
 *
 * Six of those seven traces come from data the site already ingested; only Dst
 * is new. The lag is not an artefact to smooth away, it is the lesson: a
 * substorm growth phase typically runs 30-90 minutes behind a southward IMF
 * turning, though a shock-compressed southward IMF has triggered expansion in
 * as little as six minutes.
 *
 * ## Three Dst traces, never merged
 *
 * The modelled series runs about seventy minutes ahead of real time; the USGS
 * observed series lands about four minutes behind it; the Kyoto hourly index
 * lands about fifty minutes behind. Drawing them as one line would be a
 * category error under `docs/SCIENTIFIC-LAYERS.md` and would also throw away
 * the best thing on the panel — a nowcast being graded in public, twice.
 *
 * ## Dst is the ring current, and the site should say so
 *
 * Via the Dessler-Parker-Sckopke relation the low-latitude surface depression
 * is proportional to the total kinetic energy of the trapped ion population.
 * Reading Dst is not a proxy for the ring current; it is a measurement of it,
 * to within the stated factor of two. `ringCurrentNarrative` exists so that
 * connection is on screen rather than left implicit.
 */

// ---------------------------------------------------------------------------
// Published shapes
// ---------------------------------------------------------------------------

export interface DstSample {
  at: string;
  dstNt: number;
}

export interface DstTrace {
  status: "model" | "observed";
  label: string;
  source: string;
  url: string;
  cadenceMinutes: number;
  latestNt: number | null;
  latestAt: string | null;
  series: DstSample[];
  forwardLeadMinutes?: number | null;
  latencySeconds?: number | null;
  citation?: string;
  statusNote?: string;
  note?: string;
}

export interface StormDrivers {
  observedAt: string;
  propagatedArrivalAt: string | null;
  speedKps: number | null;
  densityCm3: number | null;
  temperatureK: number | null;
  bxNt: number | null;
  byNt: number | null;
  bzGsmNt: number | null;
  btNt: number | null;
  vxKps: number | null;
  vyKps: number | null;
  vzKps: number | null;
  dynamicPressureNpa: number | null;
  magneticPressureNpa: number | null;
}

export interface StormDerived {
  clockAngleDeg: number | null;
  transverseImfNt: number | null;
  newellCoupling: number | null;
  newellUnits: string;
  newellCitation: string;
  newellCalibration: Array<{ label: string; value: number; representativeBzNt: number }>;
  newellCalibrationNote: string;
  epsilonGw: number | null;
  epsilonNote: string;
  boyleCpcpKv: number | null;
  boyleSaturationKv: number;
  boyleNote: string;
  speedKps?: number | null;
}

export interface StormPhase {
  label: "quiet" | "initial" | "main" | "recovery" | "unknown";
  rule: string;
  reason: string;
  minimumNt: number | null;
  minimumAt: string | null;
  intensity: "weak" | "moderate" | "intense" | "severe" | null;
}

export interface StormRingCurrent {
  status: "model-derived";
  energyJoules: number | null;
  energySourceSeries: string | null;
  energyDstNt: number | null;
  method: string;
  joulesPerNt: number;
  dipoleExternalFieldEnergyJ: number;
  relation: string;
  uncertainty: string;
  pressureCorrectedDst: { obrienMcPherronNt: number; burtonNt: number } | null;
  pressureCorrectionNote: string;
  compositionModel: string;
  compositionReality: string;
}

export interface StormIndices {
  kind: "geomagnetic-storm-indices";
  status: string;
  validAt: string;
  drivers: StormDrivers | null;
  derived: StormDerived | null;
  dst: {
    modelled: DstTrace;
    observed: DstTrace & { dst4Series?: DstSample[]; dst4LatestNt?: number | null };
    kyoto: DstTrace;
    separationNote: string;
  };
  ringCurrent: StormRingCurrent;
  phase: StormPhase;
  limitations: string[];
}

/** One published propagated solar-wind driver sample, post-guard. */
export interface StormDriverSample {
  validAt: string;
  observedAt: string;
  speedKps: number;
  densityCm3: number;
  bzGsmNt: number;
  bxNt: number | null;
  byNt: number | null;
  btNt: number | null;
  dynamicPressureNpa: number;
  magneticPressureNpa: number | null;
  clockAngleDeg: number | null;
  newellCoupling: number | null;
  subsolarStandoffRe: number | null;
  flaringAlpha: number | null;
}

// ---------------------------------------------------------------------------
// Derived quantities, mirrored so a scrubbed time can be recomputed
// ---------------------------------------------------------------------------

/** Dessler-Parker-Sckopke, joules per nT of depression, B0 = 30,100 nT. */
export const DPS_JOULES_PER_NT = 3.8918788723e13;

/** Energy of Earth's external dipole field, for the "how big is this?" line. */
export const DIPOLE_EXTERNAL_FIELD_ENERGY_J = 7.8097e17;

/**
 * IMF clock angle in radians, measured from GSM north, with the branch fix.
 *
 * `atan(|By|/Bz)` and `atan2(By, Bz)` agree from 0 to pi and diverge from pi
 * to 2 pi, so a naive implementation is wrong for **northward** IMF - which is
 * most of the time, and therefore most of what a visitor to a quiet-day site
 * actually sees.
 */
export function clockAngleRad(byNt: number | null, bzNt: number | null): number | null {
  if (byNt === null || bzNt === null || !Number.isFinite(byNt) || !Number.isFinite(bzNt)) return null;
  const transverse = Math.hypot(byNt, bzNt);
  if (!(transverse > 0)) return null;
  const safeBz = bzNt === 0 ? 0.001 : bzNt;
  let angle = Math.atan2(byNt, safeBz);
  if (transverse * Math.cos(angle) * bzNt < 0) angle += Math.PI;
  return angle;
}

export function clockAngleDeg(byNt: number | null, bzNt: number | null): number | null {
  const angle = clockAngleRad(byNt, bzNt);
  return angle === null ? null : ((angle * 180) / Math.PI % 360 + 360) % 360;
}

/** Newell et al. (2007) `dPhi_MP/dt`, unnormalised as published. */
export function newellCoupling(
  speedKps: number | null,
  byNt: number | null,
  bzNt: number | null,
): number | null {
  const angle = clockAngleRad(byNt, bzNt);
  if (angle === null || speedKps === null || !(speedKps > 0)) return null;
  const transverse = Math.hypot(byNt!, bzNt!);
  return speedKps ** 1.33333 * Math.abs(Math.sin(angle / 2)) ** 2.66667 * transverse ** 0.66667;
}

/**
 * Ring-current energy from Dst.
 *
 * Only the depressed branch is a ring current: a positive Dst is a compression
 * signature carried by the Chapman-Ferraro magnetopause current, so this
 * returns zero there rather than a fictitious energy.
 */
export function ringCurrentEnergyJoules(dstNt: number | null): number | null {
  if (dstNt === null || !Number.isFinite(dstNt)) return null;
  return DPS_JOULES_PER_NT * Math.max(0, -dstNt);
}

// ---------------------------------------------------------------------------
// Sampling at a scrubbed time
// ---------------------------------------------------------------------------

function timeOf(value: string | null | undefined): number {
  if (!value) return Number.NaN;
  return Date.parse(value);
}

/**
 * Newest sample at or before `at`, within `toleranceMinutes`.
 *
 * Never interpolates and never reaches forward. A gap in a published index is
 * a gap, and a trace that quietly borrows the next value across one asserts
 * knowledge the site does not have. The tolerance exists so an hourly index
 * can hold for an hour and a one-minute index cannot hold for an hour.
 */
export function sampleAt(
  series: readonly DstSample[],
  at: Date,
  toleranceMinutes: number,
): DstSample | null {
  const target = at.getTime();
  const window = toleranceMinutes * 60_000;
  let best: DstSample | null = null;
  let bestTime = Number.NEGATIVE_INFINITY;
  for (const sample of series) {
    const moment = timeOf(sample.at);
    if (!Number.isFinite(moment) || moment > target || moment < target - window) continue;
    if (moment > bestTime) {
      bestTime = moment;
      best = sample;
    }
  }
  return best;
}

/** Newest driver sample at or before `at`, within `toleranceMinutes`. */
export function sampleDriverAt(
  series: readonly StormDriverSample[],
  at: Date,
  toleranceMinutes = 30,
): StormDriverSample | null {
  const target = at.getTime();
  const window = toleranceMinutes * 60_000;
  let best: StormDriverSample | null = null;
  let bestTime = Number.NEGATIVE_INFINITY;
  for (const sample of series) {
    const moment = timeOf(sample.validAt);
    if (!Number.isFinite(moment) || moment > target || moment < target - window) continue;
    if (moment > bestTime) {
      bestTime = moment;
      best = sample;
    }
  }
  return best;
}

export interface StormNarrative {
  at: string;
  /** The driving side of the chain, from the propagated solar wind. */
  driving: {
    bzGsmNt: number | null;
    byNt: number | null;
    clockAngleDeg: number | null;
    /** True when the clock angle is past 90 degrees, i.e. the switch is on. */
    southward: boolean;
    newellCoupling: number | null;
    /** Which published band the coupling sits in. */
    newellBand: string | null;
    dynamicPressureNpa: number | null;
    subsolarStandoffRe: number | null;
  } | null;
  /** The responding side: three Dst traces and what they imply. */
  responding: {
    modelledNt: number | null;
    observedNt: number | null;
    kyotoNt: number | null;
    /** Signed difference model minus observed, when both exist. */
    nowcastErrorNt: number | null;
    ringEnergyJoules: number | null;
    ringEnergySource: "observed" | "modelled" | null;
  };
  phase: StormPhase;
}

export function newellBand(
  value: number | null,
  calibration: readonly { label: string; value: number }[],
): string | null {
  if (value === null || !Number.isFinite(value) || !calibration.length) return null;
  let band = calibration[0]!.label;
  for (const entry of calibration) {
    if (value >= entry.value) band = entry.label;
  }
  return band;
}

/**
 * Everything the storm panel needs at one instant.
 *
 * Returns the traces it can support and nulls for the rest. A beat that has no
 * data says so and shows nothing; the magnetopause layer already disappears
 * rather than freezing, and this follows it.
 */
export function stormNarrativeAt(
  storm: StormIndices | null | undefined,
  drivers: readonly StormDriverSample[] | undefined,
  at: Date,
): StormNarrative | null {
  if (!storm) return null;
  const driver = drivers ? sampleDriverAt(drivers, at) : null;
  const modelled = sampleAt(storm.dst.modelled.series, at, 10);
  const observed = sampleAt(storm.dst.observed.series, at, 30);
  const kyoto = sampleAt(storm.dst.kyoto.series, at, 90);

  const energyDst = observed?.dstNt ?? modelled?.dstNt ?? null;
  return {
    at: at.toISOString(),
    driving: driver
      ? {
        bzGsmNt: driver.bzGsmNt,
        byNt: driver.byNt,
        clockAngleDeg: driver.clockAngleDeg ?? clockAngleDeg(driver.byNt, driver.bzGsmNt),
        southward: driver.bzGsmNt < 0,
        newellCoupling: driver.newellCoupling ?? newellCoupling(driver.speedKps, driver.byNt, driver.bzGsmNt),
        newellBand: newellBand(
          driver.newellCoupling ?? newellCoupling(driver.speedKps, driver.byNt, driver.bzGsmNt),
          storm.derived?.newellCalibration ?? [],
        ),
        dynamicPressureNpa: driver.dynamicPressureNpa,
        subsolarStandoffRe: driver.subsolarStandoffRe,
      }
      : null,
    responding: {
      modelledNt: modelled?.dstNt ?? null,
      observedNt: observed?.dstNt ?? null,
      kyotoNt: kyoto?.dstNt ?? null,
      nowcastErrorNt:
        modelled && observed ? modelled.dstNt - observed.dstNt : null,
      ringEnergyJoules: ringCurrentEnergyJoules(energyDst),
      ringEnergySource: observed ? "observed" : modelled ? "modelled" : null,
    },
    phase: storm.phase,
  };
}

// ---------------------------------------------------------------------------
// Making the ring current legible
// ---------------------------------------------------------------------------

export interface RingCurrentNarrative {
  headline: string;
  tangibles: string[];
  relation: string;
  uncertainty: string;
  composition: string[];
}

/**
 * Turn the DPS energy into something a reader can hold.
 *
 * The comparisons are chosen to be checkable rather than impressive, and the
 * uncertainty travels with them in the same object so an interface cannot show
 * the number without the caveat.
 */
export function ringCurrentNarrative(
  ring: StormRingCurrent,
  energyJoules: number | null,
): RingCurrentNarrative | null {
  if (!ring) return null;
  const energy = energyJoules ?? ring.energyJoules;
  if (energy === null || !Number.isFinite(energy)) {
    return {
      headline: "No ring-current energy: no Dst depression in the selected window.",
      tangibles: [],
      relation: ring.relation,
      uncertainty: ring.uncertainty,
      composition: [ring.compositionModel, ring.compositionReality],
    };
  }
  const megatonsTnt = energy / 4.184e15;
  const terawattHours = energy / 3.6e15;
  // US electricity generation is about 4,300 TWh a year, i.e. 0.49 TW average.
  const hoursOfUsElectricity = terawattHours / 0.49;
  const fractionOfDipole = energy / ring.dipoleExternalFieldEnergyJ;
  return {
    headline:
      `About ${energy.toExponential(2)} joules stored in hot ions circling the Earth, `
      + "derived from the measured depression of the surface field.",
    tangibles: [
      `${megatonsTnt.toFixed(2)} megatons of TNT`,
      `${terawattHours.toFixed(2)} TWh, or about ${hoursOfUsElectricity.toFixed(1)} hours of total US electricity generation`,
      `${(fractionOfDipole * 100).toFixed(2)}% of the energy stored in Earth's external dipole field`,
    ],
    relation: ring.relation,
    uncertainty: ring.uncertainty,
    composition: [ring.compositionModel, ring.compositionReality],
  };
}

// ---------------------------------------------------------------------------
// Strip-chart rows
// ---------------------------------------------------------------------------

export interface StripPoint {
  t: number;
  value: number | null;
}

export interface StripTrace {
  /** Stable key for styling: the renderer maps these to CSS classes. */
  kind: "driver" | "boundary" | "model" | "observed" | "kyoto";
  points: StripPoint[];
  /**
   * Longest spacing that may be joined by a line, milliseconds.
   *
   * Expressed per trace because the traces have different cadences: joining an
   * hourly index at a one-minute tolerance shatters it into dots, and joining
   * a one-minute index at an hourly tolerance welds it across an outage.
   */
  maximumGapMs: number;
}

export interface StripRow {
  key: string;
  label: string;
  /** Evidence class, shown on the row and never merged with its neighbours. */
  badge: string;
  traces: StripTrace[];
  markZero: boolean;
  shadeNegative: boolean;
  unit: string;
  decimals: number;
  /** Value at the selected instant, or null where there is no sample. */
  current: number | null;
}

/**
 * Break a series into runs of consecutive present samples.
 *
 * **A gap stays a gap.** A polyline drawn straight through a missing hour
 * asserts that the site knows what the index was doing; it does not. This is
 * the same rule the orbit-history browser follows for the same reason.
 */
export function toSegments(
  points: readonly StripPoint[],
  maximumGapMs: number,
): Array<Array<{ t: number; value: number }>> {
  const segments: Array<Array<{ t: number; value: number }>> = [];
  let current: Array<{ t: number; value: number }> = [];
  let previous: number | null = null;
  for (const point of points) {
    if (point.value === null || !Number.isFinite(point.value)) {
      if (current.length) segments.push(current);
      current = [];
      previous = null;
      continue;
    }
    if (previous !== null && point.t - previous > maximumGapMs) {
      if (current.length) segments.push(current);
      current = [];
    }
    current.push({ t: point.t, value: point.value });
    previous = point.t;
  }
  if (current.length) segments.push(current);
  return segments;
}

function withinWindow(points: StripPoint[], from: number, to: number) {
  return points
    .filter((point) => Number.isFinite(point.t) && point.t >= from && point.t <= to)
    .sort((first, second) => first.t - second.t);
}

function dstPoints(series: readonly DstSample[], from: number, to: number): StripPoint[] {
  return withinWindow(
    series.map((sample) => ({ t: Date.parse(sample.at), value: sample.dstNt })),
    from,
    to,
  );
}

function driverPoints(
  series: readonly StormDriverSample[],
  from: number,
  to: number,
  pick: (sample: StormDriverSample) => number | null,
): StripPoint[] {
  return withinWindow(
    series.map((sample) => ({ t: Date.parse(sample.validAt), value: pick(sample) })),
    from,
    to,
  );
}

export interface StripWindow {
  from: number;
  now: number;
  /** End of the axis. Extends past `now` when a modelled trace leads it. */
  to: number;
}

/** The axis window, following the modelled trace's forward lead. */
export function stripWindow(
  storm: StormIndices,
  selectedTime: Date,
  historyHours: number,
): StripWindow {
  const now = selectedTime.getTime();
  const last = storm.dst.modelled.series.at(-1);
  const modelEnd = last ? Date.parse(last.at) : Number.NaN;
  return {
    from: now - historyHours * 3_600_000,
    now,
    to: Math.max(now, Number.isFinite(modelEnd) ? modelEnd : now),
  };
}

/**
 * The strip chart's rows: cause at the top, effect at the bottom.
 *
 * Read down the list and that is the storm: Bz turns south, the clock angle
 * swings, the coupling function rises within minutes, the magnetopause
 * standoff drops, Dst falls over hours, and the ring-current energy that Dst
 * measures rises with it.
 *
 * Rows with no data at all are dropped by the caller rather than drawn empty.
 */
export function stormStripRows(
  storm: StormIndices,
  drivers: readonly StormDriverSample[] | undefined,
  window: StripWindow,
  narrative: StormNarrative | null,
): StripRow[] {
  const series = drivers ?? [];
  const { from, to } = window;
  const minute = 60_000;
  const rows: StripRow[] = [
    {
      key: "bz",
      label: "IMF Bz (GSM)",
      badge: "observed",
      traces: [{ kind: "driver", points: driverPoints(series, from, to, (s) => s.bzGsmNt), maximumGapMs: 30 * minute }],
      markZero: true,
      shadeNegative: true,
      unit: "nT",
      decimals: 1,
      current: narrative?.driving?.bzGsmNt ?? null,
    },
    {
      key: "clock",
      label: "IMF clock angle",
      badge: "derived",
      traces: [{
        kind: "driver",
        points: driverPoints(series, from, to, (s) => s.clockAngleDeg ?? clockAngleDeg(s.byNt, s.bzGsmNt)),
        maximumGapMs: 30 * minute,
      }],
      markZero: false,
      shadeNegative: false,
      unit: "deg",
      decimals: 0,
      current: narrative?.driving?.clockAngleDeg ?? null,
    },
    {
      key: "newell",
      label: "Newell coupling",
      badge: "derived",
      traces: [{
        kind: "driver",
        points: driverPoints(series, from, to, (s) => s.newellCoupling ?? newellCoupling(s.speedKps, s.byNt, s.bzGsmNt)),
        maximumGapMs: 30 * minute,
      }],
      markZero: false,
      shadeNegative: false,
      unit: "",
      decimals: 0,
      current: narrative?.driving?.newellCoupling ?? null,
    },
    {
      key: "standoff",
      label: "Magnetopause standoff",
      badge: "empirical",
      traces: [{
        kind: "boundary",
        points: driverPoints(series, from, to, (s) => s.subsolarStandoffRe),
        maximumGapMs: 30 * minute,
      }],
      markZero: false,
      shadeNegative: false,
      unit: "Re",
      decimals: 2,
      current: narrative?.driving?.subsolarStandoffRe ?? null,
    },
    {
      key: "dst",
      label: "Dst",
      badge: "model + observed",
      traces: [
        { kind: "model", points: dstPoints(storm.dst.modelled.series, from, to), maximumGapMs: 5 * minute },
        { kind: "observed", points: dstPoints(storm.dst.observed.series, from, to), maximumGapMs: 30 * minute },
        { kind: "kyoto", points: dstPoints(storm.dst.kyoto.series, from, to), maximumGapMs: 3 * 60 * minute },
      ],
      markZero: true,
      shadeNegative: false,
      unit: "nT",
      decimals: 1,
      current: narrative?.responding.observedNt ?? narrative?.responding.modelledNt ?? null,
    },
    {
      key: "ring",
      label: "Ring current (DPS)",
      badge: "model-derived",
      traces: [{
        kind: "observed",
        points: dstPoints(storm.dst.observed.series, from, to).map((point) => ({
          t: point.t,
          value: point.value === null ? null : ringCurrentEnergyJoules(point.value),
        })),
        maximumGapMs: 30 * minute,
      }],
      markZero: false,
      shadeNegative: false,
      unit: "J",
      decimals: 0,
      current: narrative?.responding.ringEnergyJoules ?? null,
    },
  ];
  return rows;
}

/** Rows that have at least one drawable sample. Empty rows are dropped. */
export function drawableRows(rows: readonly StripRow[]): StripRow[] {
  return rows.filter((row) =>
    row.traces.some((trace) => trace.points.some((point) => point.value !== null)));
}
