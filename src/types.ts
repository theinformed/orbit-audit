import type { StormDriverSample, StormIndices } from "./storm-indices";

export type MissionCapability =
  | "weather"
  | "communications"
  | "missile-warning"
  | "navigation"
  | "earth-observation"
  | "science"
  | "human-spaceflight"
  | "technology"
  | "other";

export type UserSector = "military" | "civil" | "commercial" | "academic" | "mixed" | "unknown";
export type OrbitRegime = "LEO" | "MEO" | "GEO" | "IGSO" | "HEO" | "OTHER";
export type LayerStatus = "observed" | "assimilated" | "model" | "forecast" | "schematic";

export interface OmmRecord {
  [key: string]: string | number;
  OBJECT_NAME: string;
  OBJECT_ID: string;
  EPOCH: string;
  MEAN_MOTION: number;
  ECCENTRICITY: number;
  INCLINATION: number;
  RA_OF_ASC_NODE: number;
  ARG_OF_PERICENTER: number;
  MEAN_ANOMALY: number;
  EPHEMERIS_TYPE: 0 | "0";
  CLASSIFICATION_TYPE: "U" | "C";
  NORAD_CAT_ID: number;
  ELEMENT_SET_NO: number;
  REV_AT_EPOCH: number;
  BSTAR: number;
  MEAN_MOTION_DOT: number;
  MEAN_MOTION_DDOT: number;
}

/**
 * Publicly documented participation in a programme that is not this
 * spacecraft's own: a hosted payload, leased capacity, a shared bus, a guest
 * instrument, or a partner's stake in the system.
 *
 * Every element is a published statement with the citation that makes it, from
 * `data/programme_participation.json`. Nothing in it is inferred from an orbit,
 * a name or an owner, and the field is absent rather than empty where the
 * public record says nothing. `source` must always be shown with the claim.
 */
export interface ProgrammeParticipation {
  programmeId: string;
  programme: string;
  abbreviation: string | null;
  /** Who the programme belongs to — not necessarily who owns the spacecraft. */
  sponsor: string;
  /** Who flies the spacecraft. */
  operator: string;
  participation:
    | "hosted-payload"
    | "leased-capacity"
    | "shared-bus"
    | "guest-instrument"
    | "international-partnership";
  /** The same value in reader-facing words, so the UI keeps no second copy. */
  participationLabel: string;
  status: "operational" | "ended" | "unstated";
  definiteArticle: boolean;
  note: string;
  source: string;
  sourceName: string;
}

export interface ProgrammeCatalogEntry {
  programmeId: string;
  programme: string;
  abbreviation: string | null;
  summary: string;
  sponsor: string;
  source: string;
  participationKinds: ProgrammeParticipation["participation"][];
  /** Objects in the published catalog attached to this programme. */
  objects: number;
}

export interface SatelliteRecord {
  id: number;
  name: string;
  cosparId: string;
  ownerCode: string;
  ownerLabel: string;
  /**
   * The country the OPERATOR belongs to, published only when it differs from
   * `ownerLabel` above. The two are different facts: `ownerLabel` is the state
   * the registry attributes the object to, which for a rideshare smallsat is
   * routinely whoever filed the paperwork -- often the integrator. Absent means
   * "they agree" or "the operator catalogue has no row"; the release's
   * `operatorStateEvidence` says how many of each, so absence is never a
   * finding on its own.
   */
  operatorState?: string | null;
  organization: string;
  mission: MissionCapability;
  /** Roles this spacecraft also performs, each carrying its own evidence. A
   *  hosted payload is a real capability but not what the satellite is FOR, so
   *  it sits beside the primary mission rather than replacing it. */
  secondaryMissions?: {
    mission: string;
    role: string;
    system?: string;
    basis: string;
    why: string;
  }[];
  sector: UserSector;
  constellation: string | null;
  launchDate?: string | null;
  launchGroup?: string | null;
  sourceGroups: string[];
  orbit: OrbitRegime;
  periodMinutes: number;
  perigeeKm: number;
  apogeeKm: number;
  purpose: string;
  /**
   * "curated"  a description written about THIS spacecraft, with a citation.
   * "template" a family or radio-licence description: real, cited prose that
   *            is true of this object without being about it alone.
   * "class"    this site's own account of what KIND of object this is, for the
   *            objects no published source describes. It names no source, and
   *            the card must never draw it as though it did.
   */
  purposeKind: "curated" | "template" | "class";
  classificationConfidence: "high" | "medium" | "low";
  /** Absent or null unless a public source places this object in a programme. */
  programmes?: ProgrammeParticipation[] | null;
  omm: OmmRecord;
}

export interface CatalogBundle {
  schema: 1;
  upstreamAsOf: string;
  source: {
    name: string;
    url: string;
    attribution: string;
  };
  taxonomyVersion: string;
  /** One row per programme, with the count of retained objects attached. */
  programmeCatalog?: ProgrammeCatalogEntry[];
  totalAvailable: number;
  selectionNote: string;
  satellites: SatelliteRecord[];
}

export interface TecPoint {
  lon: number;
  lat: number;
  tec: number | null;
  anomaly: number | null;
  hmF2: number | null;
  quality: number | null;
}

export interface AuroraPoint {
  lon: number;
  lat: number;
  probability: number;
}

export interface TimeValue {
  time: string;
  value: number | null;
}

export interface SwpcScaleReading {
  level: number | null;
  label: string | null;
}

export interface SwpcScalesRecord {
  radioBlackout: SwpcScaleReading & {
    r1R2ProbabilityPercent: number | null;
    r3R5ProbabilityPercent: number | null;
  };
  solarRadiation: SwpcScaleReading & { s1OrGreaterProbabilityPercent: number | null };
  geomagnetic: SwpcScaleReading;
}

export interface SwpcOutlook {
  schemaVersion: "swpc-outlook.v1";
  retrievedAt: string | null;
  noaaScales: {
    source: string;
    latestObserved: SwpcScalesRecord & { asOf: string | null };
    rolling24HourMaximum: SwpcScalesRecord & { windowStart: string | null; windowEnd: string | null };
    forecastDays: Array<SwpcScalesRecord & { dayIndex: number; date: string | null; sourceTimestamp: string | null }>;
  };
  threeDayForecast: {
    source: string;
    issuedAt: string | null;
    rationales: { geomagnetic: string | null; solarRadiation: string | null; radioBlackout: string | null };
  };
  geomagneticForecast: {
    source: string;
    issuedAt: string | null;
    ap: {
      observed: { date: string | null; value: number | null };
      estimated: { date: string | null; value: number | null };
      predicted: Array<{ date: string | null; value: number | null }>;
    };
    activityProbabilities: Array<{
      date: string | null;
      activePercent: number | null;
      minorStormPercent: number | null;
      moderateStormPercent: number | null;
      strongToExtremeStormPercent: number | null;
    }>;
  };
  kpForecast: {
    source: string;
    issuedAt: null;
    rows: Array<{
      time: string | null;
      sourceTimeTag: string | null;
      kp: number | null;
      status: "observed" | "estimated" | "predicted" | null;
      sourceStatus: string | null;
      noaaScale: string | null;
    }>;
  };
  alerts: {
    source: string;
    label: string;
    recentNotNecessarilyActive: true;
    items: Array<{
      productId: string | null;
      issuedAt: string | null;
      sourceIssueDatetime: string | null;
      state: "recent-not-necessarily-active";
      rawMessage: string | null;
    }>;
  };
  parseWarnings: string[];
}

export interface SpaceWeatherBundle {
  schema: 1;
  teachingBrief?: {
    kind: "deterministic" | "model-assisted";
    text: string;
    caveat: string;
  };
  sources: Array<{
    product: string;
    url: string;
    status: LayerStatus;
    observedAt: string;
  }>;
  solarWind: {
    observedAt: string;
    sourceSpacecraft: string;
    speedKps: number | null;
    densityCm3: number | null;
    temperatureK: number | null;
    dynamicPressureNpa: number | null;
    series: TimeValue[];
  };
  imf: {
    observedAt: string;
    sourceSpacecraft: string;
    btNt: number | null;
    bzGsmNt: number | null;
    series: TimeValue[];
  };
  geomagnetic: {
    observedAt: string;
    kp: number | null;
    series: TimeValue[];
  };
  xray: {
    observedAt: string;
    fluxWm2: number | null;
    class: string;
    series: TimeValue[];
  };
  particles: {
    protonObservedAt: string;
    protonFlux: number | null;
    protonEnergy: string;
    electronObservedAt: string;
    electronFlux: number | null;
    electronEnergy: string;
  };
  ionosphere: {
    observedAt: string;
    status: "assimilated";
    gridDegrees: { lon: number; lat: number };
    tecRange: [number, number];
    medianHmF2Km: number | null;
    points: TecPoint[];
  };
  aurora: {
    observedAt: string;
    forecastAt: string;
    status: "forecast";
    model: string;
    maximumProbability: number;
    points: AuroraPoint[];
    caveat: string;
  };
  magnetopause: {
    status: "model";
    model: string;
    subsolarStandoffRe: number | null;
    flaringAlpha: number | null;
    driverSeries?: StormDriverSample[];
    driverSource?: string;
    caveat: string;
    /**
     * The cusped empirical boundaries the browser can evaluate from these same
     * drivers. Present from the release that added Nguyen 2022 and Lin 2010;
     * absent in older artifacts, in which case only Shue is offered.
     */
    cuspedBoundaries?: {
      status: "empirical";
      note: string;
      models: Array<{
        id: string;
        label: string;
        surface: string;
        doi: string;
        fittedTo: string;
        drivers: string[];
      }>;
      exteriorCusp: string;
    };
  };
  /**
   * Geomagnetic storm indices: three Dst traces that are never merged, plus
   * the coupling functions derived from the IMF vector NOAA was already
   * publishing and this pipeline used to discard. Optional so an older
   * artifact still loads. See `src/storm-indices.ts`.
   */
  storm?: StormIndices;
  outlook?: SwpcOutlook;
}

export interface IonosphereVolumeBundle {
  schema: 1;
  generatedAt: string;
  status: "forecast";
  model: string;
  /** Latest operational cycle represented; historical frames carry their own runAt. */
  runAt: string;
  coverage: {
    requestedHistoryHours: number;
    actualHistoryHours: number;
    forecastHours: number;
    validFrom: string;
    validTo: string;
    latestRunAt: string;
    sourceRetentionLimited: boolean;
  };
  source: {
    name: string;
    url: string;
    sourceCadenceMinutes: number;
    publishedCadenceMinutes: number;
  };
  grid: {
    coordinateSystem: string;
    ordering: "altitude-latitude-longitude";
    longitudesDeg: number[];
    latitudesDeg: number[];
    altitudesKm: number[];
    pointCount: number;
    sourceShape: [number, number, number];
    sampling: {
      longitudeStride: number;
      latitudeStride: number;
      altitudeSourceIndices: number[];
    };
  };
  electronDensity: {
    quantity: string;
    units: "m⁻³";
    scale: "log10";
    minimum: number;
    maximum: number;
    storage: "uint8";
  };
  ionComposition: {
    species: string[];
    quantity: string;
    units: "fraction";
    storage: "packed-uint4";
    maximumCode: 15;
    packing: string;
  };
  representation: {
    recommendedDefault: "smooth";
    native: string;
    smooth: string;
  };
  frames: Array<{
    validAt: string;
    runAt: string;
    leadMinutes: number;
    phase: "history" | "forecast";
    densityU8: string;
    validityBits: string;
    compositionU4: string;
  }>;
  caveat: string;
}

export type GeospaceField = "density" | "speed" | "pressure" | "magneticField";
export type GeospacePlane = "equatorial" | "meridional";

export interface GeospaceBundle {
  schema: 1;
  generatedAt: string;
  status: "model";
  model: string;
  coordinateSystem: string;
  source: { name: string; url: string; cadence: string };
  planes: Record<GeospacePlane, {
    count: number;
    coordinatesI16: string;
    boundsRe: [number, number, number, number];
  }>;
  fieldEncodings: Record<GeospaceField, {
    scale: "linear" | "log10";
    minimum: number;
    maximum: number;
    units: string;
  }>;
  radiationBelt: {
    count: number;
    gridShape?: { radialCount: number; magneticLocalTimeCount: number };
    energiesKev: number[];
    pitchCoordinate: number;
    encoding: {
      scale: "log10";
      minimum: number;
      maximum: number;
      quantity: string;
      units: string;
    };
  };
  frames: Array<{
    validAt: string;
    leadMinutes: number;
    runAt: string;
    planes: Record<GeospacePlane, { fieldsU16: Record<GeospaceField, string> }>;
    radiationBelt: {
      coordinatesU16: string;
      electronFluxU16: Record<string, string>;
    };
  }>;
  caveat: string;
}

export interface EventMilestone {
  /** Minutes from the event's own origin, which each event names in its prose. */
  offsetMinutes: number;
  title: string;
  description: string;
}

/*
 * `solarWind`, `magnetosphereCompression`, `ionosphere` and `radiation` used
 * to live on this interface: four hand-authored numbers between 0 and 1 per
 * milestone, which drove a blob's width, a line's length and a `saturate()`
 * filter. That picture is gone -- it was byte-identical for every event, so it
 * could not tell the Quebec blackout from a Starlink launch -- and the numbers
 * went with it rather than being left on the type for a future author to
 * mistake for something that was measured.
 */

export interface HistoricalEvent {
  id: string;
  title: string;
  shortTitle: string;
  date: string;
  status: "observed-reconstruction" | "historical-reconstruction" | "schematic";
  summary: string;
  /**
   * Orientation for a reader who has not met this event before, shown at the
   * TOP of the player, before the chart starts.
   *
   * Deliberately not `summary`. That field is written for the card in the grid
   * and it is written dense; it also sits BEHIND the dialog the moment the
   * replay opens, so a reader who clicks straight into a replay has, until
   * now, been handed an animated chart with no idea what they are looking at.
   * Sean, 2026-09-03: "There is no synopsis, no writeup, for any of them ...
   * They don't have anything that is sort of tieing it all together."
   */
  synopsis: string;
  lesson: string;
  /**
   * What was actually noted at the time — the half of every event this page
   * never had. Sean asked for "this is what was seen and these are some of the
   * impacts that were noted", and the second half was missing entirely.
   *
   * Every entry carries its own attribution because a consequence is a claim
   * about the world, not a reading off the replay. The replay can show the
   * field turning south; it cannot show a transformer heating up in Sweden.
   */
  impacts: Array<{ text: string; attribution: string }>;
  sources: Array<{ label: string; url: string }>;
  milestones: EventMilestone[];
  /**
   * A measured replay, when this project holds the observations for the event.
   *
   * Deliberately `unknown` here rather than a union of every replay shape: the
   * bundle is fetched from the network, so the renderer validates the payload
   * at the boundary (`mountEventReplay`) instead of a type assertion promising
   * the server sent what the compiler was told it would. An event without one
   * keeps the labelled schematic.
   */
  replay?: unknown;
}

export interface EventsBundle {
  schema: 1;
  events: HistoricalEvent[];
}

export interface TimedEnvironmentArtifactRecord {
  path: string;
  sha256: string;
  frameCount: number;
  validFrom: string;
  validTo: string;
  requestedFrom: string;
  requestedTo: string;
  coverageComplete: boolean;
  actualCoverageHours: number;
  noDataIntervalCount: number;
  sourceRetentionLimited: boolean;
}

export interface ReleaseManifest {
  schema: 1;
  release: string;
  generatedAt: string;
  catalog: { path: string; sha256: string; count: number; upstreamAsOf: string };
  spaceWeather: { path: string; sha256: string; observedAt: string };
  events: { path: string; sha256: string; count: number };
  land: { path: string; sha256: string };
  provenance: { path: string; sha256: string };
  /**
   * Measured ionosonde soundings: the only ionospheric layer parameters on this
   * site that an instrument observed. Optional in exactly the way `drap` and
   * `aurora` are: a release built without it must still load, and the E and F1
   * layers simply have no measured anchor in that release.
   */
  ionosondeSoundings?: {
    path: string;
    sha256: string;
    observedAt: string;
    /** Stations that sounded inside the freshness limit and are published. */
    stationCount: number;
    /**
     * Stations the upstream still lists but which have not sounded recently.
     * Published because the network's real condition is part of the lesson: on
     * 2026-08-19 this was 74 of 101, the oldest 11 years stale.
     */
    staleStationCount: number;
    upstreamStationCount: number;
    withFoE: number;
    withFoF1: number;
  };
  /** Exact NOAA D-RAP numeric frames accumulated and reduced on bigmem. */
  drap?: TimedEnvironmentArtifactRecord;
  /** Exact NOAA OVATION numeric frames accumulated on bigmem; gaps stay unavailable. */
  aurora?: TimedEnvironmentArtifactRecord;
  geospace?: { path: string; sha256: string; frameCount: number; validFrom: string; validTo: string };
  /**
   * Ground magnetic perturbation, reduced by `pipeline/swmf.py` from NOAA's
   * `mag_grid`. Optional in exactly the way `drap` and `aurora` are: a release
   * built without it must still load.
   */
  groundField?: {
    path: string;
    sha256: string;
    frameCount: number;
    validFrom: string;
    validTo: string;
    requestedFrom?: string;
    requestedTo?: string;
    coverageComplete?: boolean;
    noDataIntervalCount?: number;
  };
  thermosphere?: {
    path: string;
    sha256: string;
    frameCount: number;
    validFrom: string;
    validTo: string;
    cycleStart: string;
    cadenceMinutes: number;
    publishedAltitudesKm: number[];
    /** Which model produced these numbers: WAM inside its archive, else NRLMSIS. */
    model: string;
    modelLabel: string;
    modelStatus: string;
    fallbackApplied: boolean;
    /** Frames NOAA published that the build could not read. */
    skippedCount: number;
  };
  /**
   * The empirical thermosphere, published across the WHOLE slider in six-hour
   * shards.
   *
   * A separate manifest key rather than a second field on `thermosphere`
   * because it is a different model making a different class of claim, and the
   * two must be selectable, badgeable and loadable independently. NOAA WAM
   * covers about a tenth of this site's clock; this covers all of it, and the
   * browser prefers WAM wherever WAM has a frame.
   */
  thermosphereEmpirical?: {
    model: string;
    modelLabel: string;
    modelStatus: string;
    modelShortName: string;
    representation: string;
    limitation: string;
    product: string;
    productUrl: string;
    cadenceMinutes: number;
    shardHours: number;
    validFrom: string;
    validTo: string;
    frameCount: number;
    publishedAltitudesKm: number[];
    /**
     * Last hour driven by the OBSERVED Kp record. After it the model is driven
     * by NOAA's forecast, which is what entitles the layer to say FORECAST --
     * for that part of the timeline and no other.
     */
    observedThrough: string | null;
    drivers: {
      ap: { conversion: string; derivedFrom: string; observedThrough: string; validFrom: string; validTo: string };
      f107: { source: string; forecastSource: string; observedThrough: string; observedDays: number; predictedDays: number };
      f107a: { value: number; basis: string; dayCount: number | null; asOf: string | null };
    };
    outsideDriversCount: number;
    /** One record per six-hour shard; the browser fetches only the one it needs. */
    shards: {
      path: string;
      sha256: string;
      validFrom: string;
      validTo: string;
      frameCount: number;
      driverStatus: "observed" | "predicted" | "mixed";
    }[];
  };
  ionosphereModel?: {
    path: string;
    sha256: string;
    frameCount: number;
    validFrom: string;
    validTo: string;
    runAt: string;
    requestedHistoryHours?: number;
    actualHistoryHours?: number;
    forecastHours?: number;
    sourceRetentionLimited?: boolean;
  };
  /**
   * The cited ground-station table, joined to this release's catalog by NORAD
   * id. Optional because a malformed station table must degrade to "no overlay"
   * rather than take down a publish cycle.
   */
  groundStations?: { path: string; sha256: string; stationCount: number; linkCount: number };
  /**
   * The DGCPM plasmasphere simulation, run on bigmem from the published Kp
   * record by `pipeline/plasmasphere_dgcpm.py`. Optional: when it is absent
   * the plasmasphere layer falls back to the Carpenter & Anderson empirical
   * profile and says on screen that it has done so.
   */
  plasmasphere?: {
    path: string;
    sha256: string;
    frameCount: number;
    cadenceMinutes: number;
    validFrom: string;
    validTo: string;
    spinUpHours: number;
    framesWithPlume: number;
  };
  /**
   * The orbit archive, published by `pipeline/orbit_release.py` on its own
   * timer rather than the five-minute cycle. All three keys are absent whenever
   * the archive was unavailable, and their absence is what hides the browser's
   * button — so they are the gate, and no byte is fetched to decide it.
   */
  orbitEvents?: {
    path: string;
    sha256: string;
    /** Headline events in the bundle, not the total detected. */
    count: number;
    generatedAt: string;
    manoeuvreLabelPermitted: boolean;
  };
  orbitHistory?: {
    generatedAt: string;
    objects: number;
    shardCount: number;
    shards: Array<{ shard: number; path: string; sha256: string; objects: number }>;
  };
  orbitPlotViews?: { schema: number; generatedAt: string;
    objects: Array<{ norad: number; path: string; sha256: string }> };
  staticFigures?: { generatedAt: string; figures: Array<{ kind: string; path: string; sha256: string }> };
  orbitDrift?: { path: string; sha256: string; generatedAt: string; objects: number };
  orbitDrag?: { path: string; sha256: string; generatedAt: string; shells: number };
}

export interface PropagatedState {
  latitudeDeg: number;
  longitudeDeg: number;
  altitudeKm: number;
  velocityKps: number;
  x: number;
  y: number;
  z: number;
}
