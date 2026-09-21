/**
 * Data layer for the orbit-history browser: types, selection, and plot geometry.
 *
 * Deliberately free of the DOM so it can be tested without one. Everything that
 * decides *what a visitor is told* lives here or in the pipeline; the sibling
 * module `orbit-history-browser.ts` only draws.
 *
 * Two rules run through the whole file and are worth stating once:
 *
 * **Never interpolate across a gap.** The archive is a series of hourly
 * captures of a catalogue that republishes each object's elements every few
 * hours, so the natural spacing between two points is hours and the natural
 * spacing across a missed capture is days. A polyline drawn straight through
 * the second kind asserts that the site knows where the orbit was in between,
 * and it does not. `toSegments` breaks the line instead.
 *
 * **"Not enough history yet" is a designed state, not a failure.** The archive
 * began on 2026-08-07. For weeks, most panels will legitimately hold a handful
 * of points, and several features cannot run at all. Every such case has an
 * explicit reason and an explicit "available once ..." string coming from
 * `archive_maturity()` in the pipeline, so the interface can say which day it
 * starts working rather than looking broken.
 */

export interface OrbitSample {
  /** Epoch of the element set, milliseconds since the Unix epoch. */
  t: number;
  perigeeKm: number;
  apogeeKm: number;
  semiMajorAxisKm: number;
  inclinationDeg: number;
  eccentricity: number;
  bstar: number | null;
  /** "full" from the hot tier, "daily" from the forever tier. */
  tier: "full" | "daily";
  /** Display derivative: fit on ALL source points, before simplification. */
  residualMetres?: number;
  /** Original continuity, before reduction. Never infer gaps from reduced spacing. */
  joinPrevious?: boolean;
}

/**
 * A change marked on an object's plot.
 *
 * The pipeline now puts the *whole* event record here — evidence card, channel
 * tests, drag prediction, expectation — because the detail view fetches the
 * shard anyway to draw the plot, so the evidence costs no extra request, and
 * because a year of archive produces far too many events to ship them all on
 * the front page. The flat `deltaVMetresPerSecond` is retained beside the
 * structured `deltaV` it duplicates: widening a published shape by addition
 * costs one number per event, while changing it strands every browser still
 * holding the previous manifest.
 */
export type ControlStratum = { era: string; band: string } | string;
export type StratumPolicy = Record<string, Record<string, {
  manoeuvreLabelPermitted: boolean;
  gap: string | null;
}>>;

export interface OrbitEventMarker {
  startAt: string;
  endAt: string;
  signature: string;
  signatureLabel: string;
  deltaVMetresPerSecond: number | null;
  confidence: string;
  eventKey: string;
  /** Lane-specific permission; absent on bundles published before this split. */
  manoeuvreLabelPermitted?: boolean;
  controlBasis?: "cohort" | "self-history";
  controlStratum?: ControlStratum;
  /** Present when the shard carries the full record. Absent on older shards. */
  tests?: ChannelTest[];
}

/**
 * A correction this object made more than once: same signature, same cost
 * inside a tolerance band, on a repeating schedule.
 *
 * A single detection stands or falls on its detector's measured passive
 * control. Sixteen evenly-spaced burns of equal size carry an additional kind
 * of evidence: noise does not keep a 14.5-day schedule. INTELSAT 33E's
 * east-west station-keeping budget -- 5.6 m/s per year, the published figure
 * -- was recovered from element sets by exactly this grouping.
 */
export interface OrbitRepeatCluster {
  signature: string;
  count: number;
  medianDeltaVMetresPerSecond: number;
  deltaVSpreadMetresPerSecond: number;
  medianDaysBetween: number | null;
  spacingScaleDays: number | null;
  firstAt: string;
  lastAt: string;
  totalDeltaVMetresPerSecond: number;
}

export interface OrbitHistoryObject {
  norad: number;
  samples: OrbitSample[];
  display?: { method: string; originalPoints: number; displayPoints: number;
    maxErrorPixels: number; panelHeight: number; fullPath: string; evidenceNote: string };
  events: OrbitEventMarker[];
  /**
   * ABSENT means no cadence was found; it never arrives as an empty array.
   * The distinction is deliberate and the interface draws it: "this object
   * does not repeat itself" and "we did not look" are different statements,
   * and a missing key is the only one of the two that is honest here.
   */
  repeatClusters?: OrbitRepeatCluster[];
}

export interface NoDataInterval {
  from: string;
  to: string;
  /**
   * `before-bigmem-accumulation` — nothing is held before this point at all.
   * `snapshot-gap` — an hourly capture that did not run.
   * `between-backfill-and-live-capture` — a different kind of absence, and the
   * one that most needs saying: the archive holds data on BOTH sides of it, so
   * a line drawn across it would look continuous and would be an invention.
   */
  reason:
    | "before-bigmem-accumulation"
    | "snapshot-gap"
    | "between-backfill-and-live-capture"
    | string;
  note: string;
}

export interface OrbitCoverage {
  capturedFrom: string | null;
  capturedTo: string | null;
  captureCount: number;
  earliestEpoch: string | null;
  latestEpoch: string | null;
  noDataIntervals: NoDataInterval[];
  interpolationPolicy: string;
  framing: string;
}

export interface OrbitHistoryShard {
  schema: number;
  shard: number;
  shardCount: number;
  objects: OrbitHistoryObject[];
}
/**
 * The archive server did not answer at all.
 *
 * THIS IS A FIFTH STATE AND IT IS NOT "History unavailable". Since 2026-08-27
 * the 256 shards are not on the VPS: they live on bigmem-PC, Sean's machine at
 * home, because one release of them is 4.1 GB rewritten hourly and the VPS has
 * ~15 GB free. Sean's ruling: "If bigmem-pc is down, we just say 'that server
 * is offline right now, sorry, the data is unavailable'". So the site gained a
 * failure the old single-host arrangement could not have: the file is fine,
 * the release is fine, and the machine holding it is not answering.
 *
 * "History unavailable" means the browser asked for a published file and could
 * not read it -- a fault in what was published. Collapsing the two would tell a
 * reader the archive is broken when it is merely elsewhere and asleep, and
 * would send whoever investigated it looking at the wrong machine.
 *
 * A shard result is therefore three-valued, not two: the shard, `null` for
 * "asked and could not be read", and this for "nobody answered".
 */
export const ARCHIVE_OFFLINE = "archive-offline";

export type OrbitShardResult = OrbitHistoryShard | null | typeof ARCHIVE_OFFLINE;

/**
 * Which HTTP statuses mean the ARCHIVE HOST is down, rather than the file.
 *
 * Caddy on the VPS proxies /space/data/artifacts/orbit-history-* over
 * WireGuard to bigmem and answers 502 when it cannot reach it (dial_timeout is
 * 3 s, with retries off, so this arrives quickly rather than hanging a page).
 * 503 and 504 are the same claim from a gateway that got further along.
 *
 * A 404 is deliberately NOT here. A 404 is the archive host answering that it
 * does not have that file, which is "could not be read" and a different
 * sentence. Nor is a bare network error: if the browser cannot reach this
 * origin at all, the page it is reading came from that origin, so the honest
 * reading is a failed request rather than a diagnosis of a machine one hop
 * further on that the browser never spoke to.
 */
export function isArchiveOfflineStatus(status: number | undefined): boolean {
  return status === 502 || status === 503 || status === 504;
}

/** The card's state string. Kept here so the card and the dialog cannot drift. */
export const ARCHIVE_OFFLINE_STATE = "Archive server offline";

export const ARCHIVE_OFFLINE_TITLE = "The archive server is offline";

/**
 * What a reader is actually told, and why it is shaped this way.
 *
 * Sean asked for the offline path to name the fix as well as the fault, and to
 * do it WITHOUT printing an address: he built the site's feedback box precisely
 * so his and Derek's mail need not sit on a public page collecting spam. So the
 * ask goes through the box, and this paragraph says so in words rather than
 * assuming a reader will spot a button.
 *
 * It also says what is NOT affected. The header above this panel -- name,
 * NORAD, regime, perigee, apogee -- comes from the events bundle on the VPS and
 * is unaffected by bigmem being down, and a reader who is not told that reads a
 * full-looking panel under a failure notice and concludes one of them is lying.
 * That exact confusion is on the record from 2026-08-27.
 *
 * Kept to five short sentences, the weight of the two absences beside it. An
 * apology and an escape hatch are not licence for a paragraph a reader has to
 * work through to find out that nothing is wrong with the spacecraft.
 */
export const ARCHIVE_OFFLINE_BODY =
  "The orbit histories are held on a separate machine, and it is not answering right now \u2014 sorry. "
  + "Nothing is drawn here rather than something drawn from elsewhere. "
  + "The summary above is unaffected: it comes from a different file, on a different server, which loaded. "
  + "The archive usually comes back on its own. "
  + "If you need this object\u2019s stored elements now, ask below and Sean and Derek will send them.";

export const ARCHIVE_OFFLINE_ACTION = "Ask for this history";

/*
 * A shard carries no coverage record and no generation time, on purpose.
 * Artifacts are content-addressed, so a field that changes when the data has
 * not would mint 256 new files on every five-minute publish cycle. Coverage is
 * read from the events bundle, which the browser has already loaded before it
 * asks for a shard.
 */

export interface ChannelTest {
  element: string;
  delta: number;
  floorSigma: number;
  floorZ: number;
  cohortZ: number | null;
  cohortCount: number;
  cohortScreened: boolean;
  tripped: boolean;
}

export interface NarrativeCard {
  kind: string;
  headline: string;
  observation: string;
  cost: string;
  control: string;
  candidateCauses: { id: string; label: string; detail: string }[];
  alternatives: string;
  honesty: string;
  footer: string;
}

/**
 * The bundle's cross-catalogue headline list — and it is NOT an
 * `OrbitEventRecord`.
 *
 * `pipeline/orbit_release.py:_slim()` strips every nested block before the
 * headline events go into the events bundle: no `card`, no `deltaV` object, no
 * `drag`, no `spaceWeather`, no `expectation` object, no `tests`. It publishes
 * flat scalars instead, plus `expectationVerdict` where the record carries an
 * `expectation` object. The full records live only in the per-object shards.
 *
 * This type existed nowhere until 2026-08-09, and `events` was declared as
 * `OrbitEventRecord[]`. Nothing caught it because nothing rendered the bundle's
 * own events: the shard path is taken whenever a shard has been published, and
 * it always had been. The first object whose shard was missing would have
 * dereferenced `event.card.headline` on an object that has no `card` and thrown
 * inside the dialog.
 */
export interface OrbitHeadlineEvent {
  norad: number;
  name: string;
  objectType: string;
  startAt: string;
  endAt: string;
  spanDays: number;
  signature: string;
  signatureLabel: string;
  confidence: string;
  regime: string;
  perigeeAltitudeKm: number;
  apogeeAltitudeKm: number;
  inclinationDeg: number;
  /** Flat scalar here; the full record carries the whole `deltaV` breakdown. */
  deltaVMetresPerSecond: number;
  constellation: string | null;
  sunSynchronous: boolean;
  /** Flat verdict string; the full record carries the `expectation` object. */
  expectationVerdict: string | null;
  groundTruth: Record<string, unknown> | null;
  purposeLanguagePermitted: boolean;
  eventKey: string;
  manoeuvreLabelPermitted?: boolean;
  controlBasis?: "cohort" | "self-history";
  controlStratum?: ControlStratum;
}

export interface OrbitEventRecord {
  norad: number;
  name: string;
  objectType: string;
  startAt: string;
  endAt: string;
  spanDays: number;
  signature: string;
  signatureLabel: string;
  signatureExplanation: string;
  confidence: string;
  manoeuvreLabelPermitted?: boolean;
  controlBasis?: "cohort" | "self-history";
  controlStratum?: ControlStratum;
  regime: string;
  perigeeAltitudeKm: number;
  apogeeAltitudeKm: number;
  inclinationDeg: number;
  /* Published on shard records too, additively. Declared so a caller that has
   * only narrowed as far as "an event" can still read them. */
  constellation?: string | null;
  sunSynchronous?: boolean;
  deltaVMetresPerSecond?: number;
  kpMax?: number | null;
  deltaV: {
    totalMetresPerSecond: number;
    tangentialMetresPerSecond: number;
    planeChangeMetresPerSecond: number;
    eccentricityMetresPerSecond: number;
    note: string;
  };
  drag: {
    applicable: boolean;
    reason: string;
    predictedDeltaAMetres: number;
    predictedSigmaMetres: number;
    propulsiveDeltaAMetres: number;
    cohortCount: number;
    bstar: number | null;
  };
  tests: ChannelTest[];
  expectation: { verdict: string; class: string | null; reason: string; citations: unknown[] };
  spaceWeather: { kpMax: number | null; densityRatio: number | null };
  groundTruth: Record<string, unknown> | null;
  purposeLanguagePermitted: boolean;
  eventKey: string;
  card: NarrativeCard;
  narrative?: { kind: string; text: string; caveat: string; generatedAt: string };
}

export interface ObjectSummary {
  norad: number;
  name: string;
  objectType: string;
  regime: string;
  perigeeAltitudeKm: number;
  apogeeAltitudeKm: number;
  inclinationDeg: number;
  sunSynchronous: boolean;
  mission: string | null;
  sector: string | null;
  constellation: string | null;
  intervals: number;
  /**
   * Days of this object the archive actually holds — the summed spans of the
   * intervals it can join, never the calendar distance between first and last
   * epoch. The archive contains a real hole between the end of the bulk
   * bundles and the start of live capture, and an object seen for a year in
   * 2024 and an hour in 2026 has been watched for about a year.
   */
  observedDays: number;
  events: number;
  deltaVMetresPerSecond: number;
  /** Contiguous runs of coverage. A view must never draw or reason across the
   *  gap between two of them. */
  observationRuns?: { fromAt: string; toAt: string; days: number }[];
  firstSeenAt?: string;
  lastSeenAt?: string;
  deltaVPerYearMetresPerSecond?: number | null;
  /** How often this object corrects, from its own history. Null until it has
   *  made at least three corrections inside one run of coverage. */
  cadence?: {
    corrections: number;
    spacingsUsed: number;
    medianDaysBetween: number;
    spacingScaleDays: number;
    /** MAD / median of the spacings. Zero is perfectly regular. */
    regularity: number | null;
    correctionsPerYear: number | null;
    observedDays: number;
    note: string;
  } | null;
  /** Corrections that are the same correction made again: same signature, cost
   *  inside a tolerance band, with their own spacing. */
  repeatClusters?: {
    signature: string;
    count: number;
    medianDeltaVMetresPerSecond: number;
    deltaVSpreadMetresPerSecond: number;
    medianDaysBetween: number | null;
    spacingScaleDays: number | null;
    firstAt: string;
    lastAt: string;
    totalDeltaVMetresPerSecond: number;
  }[];
  /** Out of the ordinary *for this object*, which no class file can encode. */
  unusualForItself?: {
    at: string;
    signature: string;
    deltaVMetresPerSecond: number;
    why: string;
    usualSignature: string;
    usualDeltaVMetresPerSecond: number;
    usualCount: number;
  }[];
  outOfFamilyForClass?: boolean;
  decay?: {
    metresPerDay: number | null;
    perigeeAltitudeKm?: number;
    decaying?: boolean;
    upperBoundDaysToReentry?: number;
    reentryNote?: string;
    note: string;
  };
  /* Retained from the cohort-only summariser so a bundle built by either path
   * renders. Both are derivable from the fields above and neither is required. */
  medianDeltaAMetresPerDay?: number;
  repeatedSignature?: { signature: string; count: number } | null;
  outOfFamily?: boolean;
  decaying?: boolean;
  purposeLanguagePermitted: boolean;
}

/**
 * Does this row have enough of its OWN history to answer a longitudinal
 * question?
 *
 * The gating used to be a single archive-wide number from the capture ledger,
 * which was right when the archive was one continuous run of hourly captures
 * and became badly wrong the moment the bulk back-fill landed: the ledger read
 * a few hours while the archive held a full year, so every view that could
 * finally be answered stayed switched off in front of the data that answers
 * it. Maturity is a property of the object, so it is asked of the object.
 */
export function hasHistory(row: ObjectSummary, days: number): boolean {
  return row.observedDays >= days;
}

export interface ControlRates {
  kappa: number;
  passiveControl: { flags: number; intervals: number; rate: number | null; interval95: [number, number] | null };
  payloadPopulation: { flags: number; intervals: number; rate: number | null; interval95: [number, number] | null };
  excessSignificance: { z: number | null; approximatePValue: number | null; method: string; caution?: string };
  excessRate: number | null;
  sufficientToLabel: boolean;
  excessSignificant: boolean;
  designTarget: number;
  note: string;
  blockingReason: string | null;
  selfHistory?: {
    strata?: Record<string, Record<string, NonNullable<ControlRates["selfHistory"]>>>;
    matchedControlStatus?: string;
    detectorFlags?: Record<string, boolean>;
    trackingGapDroppedIntervals?: number | string;
    catalogueGeoNorthSouthKeepingEvents?: number | string;
    basis: "self-history";
    kappa: number;
    passive: {
      objects: number;
      intervals: number;
      flags: number;
      flaggedObjects: number;
      ratePerInterval: number | null;
      ratePerObjectYear: number | null;
      jeffreys95: [number | null, number | null];
      objectDays: number;
    };
    payload: {
      objects: number;
      intervals: number;
      flags: number;
      ratePerInterval: number | null;
      ratePerObjectYear: number | null;
      jeffreys95: [number | null, number | null];
      objectDays: number;
    };
    separation: { z: number | null; approximatePValue: number | null; ratio: number | null };
    targetRatePerInterval: number;
    sufficientToLabel: boolean;
    blockingReason: string | null;
    note: string;
  };
}

export interface MaturityCapability {
  id: string;
  available: boolean;
  needs: string;
  why: string;
  objectsReady?: number;
}

export interface OrbitEventsBundle {
  schema: number;
  generatedAt: string;
  kappa: number;
  coverage: OrbitCoverage;
  controls: ControlRates;
  groundTruth: {
    tableVersion: string;
    publishedEvents: number;
    /**
     * Published burns the archive can actually score. The live publisher
     * (`pipeline/orbit_campaigns.py`) calls this `scorable`; `inArchiveWindow`
     * was the name on the older `pipeline/orbit_events.py` path and has never
     * appeared in a published bundle. Read it through `scorableBurns()`.
     */
    scorable?: number;
    inArchiveWindow?: number;
    detected: number;
    notDetected: number;
    pending: number;
    detectionRate: number | null;
    matches: Record<string, unknown>[];
    misses: Record<string, unknown>[];
    pendingEvents: Record<string, unknown>[];
    note: string;
  };
  events: OrbitHeadlineEvent[];
  objects: ObjectSummary[];
  /** How much of the whole detected set the headline list above is. */
  eventsPublished?: { inThisBundle: number; total: number; rule: string };
  /**
   * Two producers have written this block and they do not agree on a single
   * field name. `pipeline/orbit_campaigns.py` — the one that actually publishes
   * — emits the first group; `pipeline/orbit_events.py:archive_maturity()`
   * emits the second, and only the second was ever declared here. Everything is
   * optional and read through `archiveSpanDays()`, because a missing number has
   * to read as "not published" rather than poison an arithmetic chain.
   */
  maturity: {
    /** The longest any single object has been watched. The archive-wide figure. */
    longestSingleObjectDays?: number;
    /** Live capture only. Explicitly NOT a measure of maturity since the back-fill. */
    captureLedgerDays?: number;
    observedObjectDays?: number;
    objectsScanned?: number;
    objectsSummarised?: number;
    objectsWithBaseline?: number;
    archive?: Record<string, unknown>;
    spanNote?: string;
    /* The older path's names. Absent from every published bundle to date. */
    observationSpanDays?: number;
    epochSpanDays?: number;
    intervals?: number;
    objectsWithIntervals?: number;
    objectsWithEightIntervals?: number;
    capabilities: MaturityCapability[];
    coverageNote: string;
  };
  labelPolicy: {
    manoeuvreLabelPermitted: boolean;
    byBasis?: { cohort: boolean; selfHistory: boolean; byStratum?: StratumPolicy };
    reason: string | null;
    wording: string;
  };
}

/**
 * The archive-wide span, in days, however this bundle chose to name it.
 *
 * `longestSingleObjectDays` first, deliberately: OPEN-WORK §0 records that the
 * capture ledger stopped being a measure of maturity the moment the bulk
 * back-fill landed — it reads under a day while the archive holds a year — so
 * gating anything on it refuses questions the data can answer. Zero when the
 * bundle publishes neither, which reads as "nothing watched yet" and is the
 * safe direction: it can only make a view say it needs more archive, never make
 * one claim history it does not have.
 */
export function archiveSpanDays(bundle: OrbitEventsBundle): number {
  const maturity = bundle.maturity ?? {};
  for (const value of [maturity.longestSingleObjectDays, maturity.observationSpanDays]) {
    if (typeof value === "number" && Number.isFinite(value)) return value;
  }
  return 0;
}

/** Published burns the archive can score, under whichever name it carries. */
export function scorableBurns(bundle: OrbitEventsBundle): number {
  const truth = bundle.groundTruth ?? ({} as OrbitEventsBundle["groundTruth"]);
  for (const value of [truth.scorable, truth.inArchiveWindow]) {
    if (typeof value === "number" && Number.isFinite(value)) return value;
  }
  return 0;
}

/* ------------------------------------------------------------------------ */
/* Line breaking                                                             */
/* ------------------------------------------------------------------------ */

/**
 * The largest gap between two element sets that may be joined by a line.
 *
 * Three days is the same bound the detector uses when it forms first
 * differences, and for the same reason: across a longer gap a step and a slow
 * trend are not distinguishable, so a line drawn across one is an assertion the
 * data does not support.
 */
export const MAX_JOINABLE_GAP_MS = 3 * 24 * 60 * 60 * 1000;

/**
 * Split a series into drawable runs, breaking wherever the data does not
 * justify a line.
 *
 * Returns runs of two or more points, plus the indices of points left isolated,
 * which the caller should still draw as dots. An element set that stands alone
 * is a real observation and dropping it would hide data; joining it to a
 * neighbour three days away would invent some.
 */
export function toSegments(
  samples: readonly OrbitSample[],
  maxGapMs: number = MAX_JOINABLE_GAP_MS,
): { runs: OrbitSample[][]; isolated: OrbitSample[] } {
  const runs: OrbitSample[][] = [];
  const isolated: OrbitSample[] = [];
  let current: OrbitSample[] = [];

  const flush = () => {
    const only = current[0];
    if (current.length >= 2) runs.push(current);
    else if (only !== undefined) isolated.push(only);
    current = [];
  };

  for (const sample of samples) {
    if (current.length === 0) {
      current.push(sample);
      continue;
    }
    const previous = current[current.length - 1];
    if (previous !== undefined && (sample.joinPrevious === false || (sample.joinPrevious === undefined && sample.t - previous.t > maxGapMs))) {
      flush();
      current = [sample];
    } else {
      current.push(sample);
    }
  }
  flush();
  return { runs, isolated };
}

/* ------------------------------------------------------------------------ */
/* Detrending                                                                */
/* ------------------------------------------------------------------------ */

/**
 * Semi-major axis with its own straight-line trend removed, in metres.
 *
 * This is the panel where steps live. An object at 500 km loses metres a day to
 * drag, so a plot of the raw semi-major axis over a month is a slope with the
 * interesting part invisible inside the line's own thickness. Subtracting the
 * least-squares line leaves the residual, and the y-axis is in metres because
 * the measured element-to-element noise floor is metres — 1.67 m below 500 km,
 * 0.51 m from 500 to 800, 0.10 m from 800 to 1500.
 *
 * The fit is over whatever points are supplied, so a caller that wants the
 * trend of a quiet stretch should pass the quiet stretch. With fewer than three
 * points there is no trend to remove and the raw deviation from the mean is
 * returned, which is the honest degenerate case rather than a straight line of
 * zeros.
 */
export function detrendSemiMajorAxis(
  samples: readonly OrbitSample[],
): { t: number; residualMetres: number }[] {
  if (samples.length === 0) return [];
  if (samples.length < 3) {
    const mean =
      samples.reduce((total, sample) => total + sample.semiMajorAxisKm, 0) / samples.length;
    return samples.map((sample) => ({
      t: sample.t,
      residualMetres: (sample.semiMajorAxisKm - mean) * 1000,
    }));
  }
  // Times are reduced to days from the first sample before fitting. Fitting
  // against raw millisecond epochs squares a number near 1.7e12, which loses
  // most of the mantissa in a double and produces a visibly wrong slope.
  const first = samples[0];
  if (first === undefined) return [];
  const t0 = first.t;
  const xs = samples.map((sample) => (sample.t - t0) / 86_400_000);
  const ys = samples.map((sample) => sample.semiMajorAxisKm);
  const n = xs.length;
  const meanX = xs.reduce((a, b) => a + b, 0) / n;
  const meanY = ys.reduce((a, b) => a + b, 0) / n;
  let covariance = 0;
  let variance = 0;
  for (let index = 0; index < n; index += 1) {
    const dx = (xs[index] ?? 0) - meanX;
    covariance += dx * ((ys[index] ?? 0) - meanY);
    variance += dx * dx;
  }
  const slope = variance > 0 ? covariance / variance : 0;
  const intercept = meanY - slope * meanX;
  return samples.map((sample, index) => ({
    t: sample.t,
    residualMetres: ((ys[index] ?? 0) - (intercept + slope * (xs[index] ?? 0))) * 1000,
  }));
}

/* ------------------------------------------------------------------------ */
/* Population views                                                          */
/* ------------------------------------------------------------------------ */

export type PopulationView =
  | "delta-v"
  | "most-corrections"
  | "decaying"
  | "repeated"
  | "out-of-family"
  | "all";

export interface PopulationFilter {
  view: PopulationView;
  search: string;
  regime: string | null;
  /**
   * Rates like "corrections per day" are meaningless from an archive hours
   * old. A view that reports one requires this many days of observation of the
   * object before it will show it, and says so when it shows nothing.
   */
  minimumObservedDays: number;
}

export const DEFAULT_FILTER: PopulationFilter = {
  view: "delta-v",
  search: "",
  regime: null,
  minimumObservedDays: 0,
};

/**
 * How many days of observation each view needs before its answer means
 * anything. These are not thresholds on the data, they are thresholds on the
 * *question*: "how often does this satellite need a correction" is not a
 * question an hour of archive can answer at all, and the honest interface says
 * so instead of dividing by a very small number.
 */
export const VIEW_REQUIREMENTS: Record<PopulationView, { days: number; question: string; needs: string }> = {
  "delta-v": {
    days: 0,
    question: "Which objects spent the most, in metres per second, over the archive so far?",
    needs: "Works immediately: a single pair of element sets already gives a cost.",
  },
  "most-corrections": {
    days: 7,
    question: "Which objects need correcting most often?",
    needs: "About a week, because a rate needs several corrections behind it before it is a rate.",
  },
  decaying: {
    days: 0,
    question: "What is losing altitude?",
    needs: "Works immediately: decay shows up between any two element sets.",
  },
  repeated: {
    days: 21,
    question: "What makes the same correction over and over?",
    needs:
      "About three weeks, because geostationary east-west cycles run one to four weeks and a cadence needs several complete cycles.",
  },
  "out-of-family": {
    days: 0,
    question: "What is behaving unusually for its class?",
    needs: "Works immediately: the comparison is against a published expectation, not against history.",
  },
  all: {
    days: 0,
    question: "Everything the archive has seen move.",
    needs: "Works immediately.",
  },
};

export interface PopulationResult {
  rows: ObjectSummary[];
  /** Non-null when the view cannot yet be answered; the interface renders this
   *  instead of an empty table, so an honest gap never looks like a bug. */
  unavailable: { question: string; needs: string; haveDays: number } | null;
}

/** Corrections per year: measured cadence first, events over coverage second. */
export function correctionRate(row: ObjectSummary): number {
  if (row.cadence?.correctionsPerYear != null) return row.cadence.correctionsPerYear;
  if (row.observedDays > 0) return (row.events * 365.25) / row.observedDays;
  return 0;
}

/** Metres per day of semi-major axis. Negative is falling. */
export function decayRate(row: ObjectSummary): number {
  return row.decay?.metresPerDay ?? row.medianDeltaAMetresPerDay ?? 0;
}

/** How many times the object made its most-repeated correction. */
export function repeatCount(row: ObjectSummary): number {
  const clustered = row.repeatClusters?.[0]?.count ?? 0;
  return Math.max(clustered, row.repeatedSignature?.count ?? 0);
}

export function selectPopulation(
  summaries: readonly ObjectSummary[],
  filter: PopulationFilter,
  observationSpanDays: number,
): PopulationResult {
  const requirement = VIEW_REQUIREMENTS[filter.view];
  // Asked of the objects, not of the archive. A view is answerable when some
  // object has enough of its own history to answer it — which after the
  // back-fill is true of a great many objects while the capture ledger still
  // reads a few hours. `observationSpanDays` remains the fallback for a bundle
  // built before the per-object figures existed.
  // Seeded defensively. `observationSpanDays` is absent from every bundle the
  // live pipeline has published, and `Math.max(undefined, n)` is NaN, which
  // compares false against every requirement — so a missing seed did not make
  // the gate strict, it switched the gate off entirely and silently. A view
  // that cannot be answered would have rendered an empty table instead of
  // saying which day it starts working.
  const seed = Number.isFinite(observationSpanDays) ? observationSpanDays : 0;
  const longestObserved = summaries.reduce(
    (best, row) => Math.max(best, Number.isFinite(row.observedDays) ? row.observedDays : 0),
    seed,
  );
  if (requirement.days > 0 && longestObserved < requirement.days) {
    return {
      rows: [],
      unavailable: {
        question: requirement.question,
        needs: requirement.needs,
        haveDays: longestObserved,
      },
    };
  }

  const needle = filter.search.trim().toLowerCase();
  let rows = summaries.filter((row) => {
    if (needle && !row.name.toLowerCase().includes(needle) && String(row.norad) !== needle) {
      return false;
    }
    if (filter.regime && row.regime !== filter.regime) return false;
    if (row.observedDays < filter.minimumObservedDays) return false;
    return true;
  });

  switch (filter.view) {
    case "delta-v":
      rows = rows
        .filter((row) => row.deltaVMetresPerSecond > 0)
        .sort((a, b) => b.deltaVMetresPerSecond - a.deltaVMetresPerSecond);
      break;
    case "most-corrections":
      // Ranked on the object's own measured cadence where it has one, which is
      // a rate over a span that actually contains several corrections, and on
      // events-per-observed-day otherwise. An object with one correction in
      // two hours of coverage would otherwise top a "corrects most often" list
      // for ever.
      rows = rows
        .filter((row) => hasHistory(row, requirement.days) && (row.cadence != null || row.events > 0))
        .sort((a, b) => correctionRate(b) - correctionRate(a));
      break;
    case "decaying":
      // Most negative first: the fastest-falling objects are the interesting
      // ones, and they are the ones a visitor came to this view to find.
      rows = rows
        .filter((row) => row.decay?.decaying ?? row.decaying ?? false)
        .sort((a, b) => decayRate(a) - decayRate(b));
      break;
    case "repeated":
      rows = rows
        .filter(
          (row) =>
            hasHistory(row, requirement.days) &&
            ((row.repeatClusters?.length ?? 0) > 0 || row.repeatedSignature != null),
        )
        .sort((a, b) => repeatCount(b) - repeatCount(a));
      break;
    case "out-of-family":
      rows = rows
        .filter(
          (row) =>
            (row.unusualForItself?.length ?? 0) > 0 ||
            (row.outOfFamilyForClass ?? row.outOfFamily ?? false),
        )
        .sort((a, b) => b.deltaVMetresPerSecond - a.deltaVMetresPerSecond);
      break;
    default:
      rows = rows.slice().sort((a, b) => b.deltaVMetresPerSecond - a.deltaVMetresPerSecond);
  }
  return { rows, unavailable: null };
}

/* ------------------------------------------------------------------------ */
/* Wording                                                                   */
/* ------------------------------------------------------------------------ */

/**
 * How an event may be described, given what the controls actually support.
 *
 * The whole feature turns on this function. `docs/orbit-history-design.md`
 * Section 4.3 is explicit: if the measured false-alarm rate does not exist, the
 * label does not ship and the plot does. So the pipeline computes
 * lane-specific permission and the interface reads it — the browser never
 * decides for itself that something has been established.
 */
export function eventNoun(
  event: Pick<OrbitEventRecord, "signature" | "signatureLabel" | "confidence">,
  labelPermitted: boolean,
): string {
  if (event.signature === "drag-decay") return "orbital decay";
  if (event.signature === "re-entry-decay") return "re-entry decay";
  if (event.signature === "drag-and-thrust-not-separable") return "unattributed change";
  if (!labelPermitted) return `${event.signatureLabel} (candidate)`;
  return event.signatureLabel;
}

/**
 * The only object types whose events the pipeline will ever call a manoeuvre.
 *
 * An ALLOWLIST, mirroring `_event_label_permitted` in
 * `pipeline/orbit_release.py` -- "Only a payload may inherit a detector's
 * earned manoeuvre vocabulary", i.e. `record.get("objectType") == "PAYLOAD"`.
 *
 * This interface used to carry the opposite rule: a DENYLIST of `DEBRIS` and
 * `ROCKET BODY`. That is not the same rule. Space-Track's catalogue also
 * publishes `UNKNOWN`, `TBA` and `OTHER`, and every one of those fell
 * straight through the denylist and was drawn as manoeuvre-capable by a page
 * whose own pipeline had already refused it the word. A denylist fails OPEN on
 * exactly the objects nobody thought about, which is the wrong direction for a
 * hedge; an allowlist fails closed, and the two sides now state one rule.
 */
export const MANOEUVRE_CAPABLE_TYPES: readonly string[] = ["PAYLOAD"];

/** Prefer the event's own detector control; retain compatibility with older bundles. */
export function eventLabelPermitted(
  event: {
    manoeuvreLabelPermitted?: boolean;
    objectType?: string;
    signature?: string;
  },
  bundleFallback: boolean,
): boolean {
  // A KNOWN type that is not on the allowlist ends it here. An ABSENT type is
  // not read as permission: the event markers inside a history shard carry no
  // type of their own, so the caller that holds the object's summary row passes
  // it in, and where it genuinely is not known the per-event
  // `manoeuvreLabelPermitted` below still governs -- and the pipeline computed
  // that flag under this same allowlist.
  if (event.objectType !== undefined && !MANOEUVRE_CAPABLE_TYPES.includes(event.objectType)) {
    return false;
  }
  if (event.signature === "thrust-excess") return false;
  return event.manoeuvreLabelPermitted ?? bundleFallback;
}

/** Human copy for the confidence a cohort screen could or could not give. */
export const CONFIDENCE_COPY: Record<string, string> = {
  candidate:
    "Checked against a group of comparable objects over the same hours, and it stood out from them.",
  "candidate-thin-cohort":
    "Checked against a group of comparable objects, but the group was small enough that its own spread is poorly determined.",
  "candidate-unscreened":
    "No comparable group of objects existed at this altitude and inclination over these hours, so the population check could not be run at all.",
};

export function formatDeltaV(metresPerSecond: number | null): string {
  if (metresPerSecond === null || !Number.isFinite(metresPerSecond)) return "—";
  const magnitude = Math.abs(metresPerSecond);
  if (magnitude < 0.01) return `${(metresPerSecond * 1000).toFixed(1)} mm/s`;
  if (magnitude < 1) return `${(metresPerSecond * 100).toFixed(1)} cm/s`;
  return `${metresPerSecond.toFixed(2)} m/s`;
}

export function formatMetres(metres: number | null, signed = true): string {
  if (metres === null || !Number.isFinite(metres)) return "—";
  const magnitude = Math.abs(metres);
  const sign = signed && metres > 0 ? "+" : "";
  if (magnitude >= 1000) return `${sign}${(metres / 1000).toFixed(3)} km`;
  if (magnitude >= 1) return `${sign}${metres.toFixed(1)} m`;
  return `${sign}${(metres * 100).toFixed(1)} cm`;
}

/**
 * Which shard holds an object's history. Mirrors `norad % 256` in
 * `pipeline/orbit_release.py`; a mismatch would silently fetch the wrong file,
 * so both sides derive it from the shard count carried in the manifest.
 */
export function shardFor(norad: number, shardCount: number): number {
  return ((norad % shardCount) + shardCount) % shardCount;
}
