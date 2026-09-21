import { loadOrbitDrift, mountDriftControls } from "./orbit-drift";
import { EVIDENCE, type Evidence } from "./learning-evidence";
import { rememberChapterOpener, focusChapterHeading, restoreChapterOpener, mountLearningContents } from "./learning-navigation";
import "./styles.css";
import { fetchPlotObject } from "./plot-view";
import { json2satrec } from "satellite.js";
import {
  featuredConstellation,
  featuredToastText,
  utcDayNumber,
  utcIsoDay,
  type FeaturedConstellation,
} from "./featured-constellation";
import { ownerGroups, type OwnerGroup } from "./facet-groups";
// THE EIGHT CLASSIFICATION FOOTNOTES, BAKED IN AT BUILD TIME. `narration/
// build_hedge_footnotes.py` writes this file from `narration/hedge-footnote-facts.json`
// and the free local model's phrasing of it, re-checked there before it is allowed in.
// It is imported rather than fetched because there are eight of them and 1,559 marked
// cards: the answer is per KIND of missing evidence, not per spacecraft, so nothing about
// it can be worth a request. No model is asked anything when a reader opens a card.
import hedgeFootnoteFile from "../narration/hedge-footnotes.json";
import { connectionsView } from "./connections";
import { layerPageView, layerPagesIndexView } from "./layer-pages";
import { mountLayerNarration, stopLayerNarration } from "./layer-narration";
import { TransitPlanner } from "./transit-planner";
import { currentConditionsView, eventsView, eventPlayer, sourcesView, weatherLessonView, weatherLessons, weatherPageView } from "./content";
import { satelliteFundamentalsIndexView, satelliteFundamentalsPageView } from "./satellite-fundamentals";
import { orbitMethodsPageView, mountOrbitMethods } from "./orbit-methods";
import { KP_LIMITATION, kpChartGeometry, kpChartSummary, kpStormLabel, type KpRow } from "./kp-forecast";
import {
  PLASMAPAUSE_LIMITATION,
  PLASMAPAUSE_MAX_FRAME_AGE_MINUTES,
  describeFrameAge,
  plasmapauseCheckNote,
  plasmapauseDialPoint,
  plasmapauseFrameAgeMinutes,
  plasmapauseFrameClock,
  plasmapauseFrameStamp,
  plasmapauseMotion,
  plasmapauseRingGeometry,
  plasmapauseSummary,
  ringPath,
  type PlasmapauseFrame,
} from "./plasmapause-chart";
import {
  goesXrayClass,
  sampleLogTimeValue,
  sampleMagnetopauseDriver,
  type MagnetopauseDriverSample,
} from "./environment-time";
import { substormStateAt } from "./substorm-chain";
import { magnetopauseNoForecastAt, noForecastSentence } from "./magnetopause-forecast";
import type { MagnetopauseNoForecast } from "./magnetopause-forecast";
import { INNER_EDGE_INJECTED_RE, OUTER_EDGE_RE } from "./inner-plasma-sheet";
import type { IndexSample, SubstormState } from "./substorm-chain";
import { formatAuroraSelection, selectAuroraFrame, type AuroraBundle } from "./aurora-time";
import {
  drapAbsorptionDbAtFrequency,
  drapCondition,
  drapConditionSentence,
  drapNowcastEndSentence,
  selectDrapFrame,
  type DrapBundle,
} from "./drap";
import type { EnvironmentSurfaceState } from "./environment-surface-layer";
import { mountGroundTrackMap, sampleGroundTrack } from "./ground-track-map";
import type { GroundFieldBundle, GroundFieldState } from "./ground-perturbation";
import { STATION_OPERATOR_SCALE,
  GroundStationLayer,
  computeStationPasses,
  indexGroundStations,
  sampleDrapAtStation,
  sampleTecAtStation,
  stationMinimumElevationDeg,
  type GroundStation,
  type GroundStationBundle,
  type GroundStationIndex,
} from "./ground-stations";
import {
  FAVORITES_STORAGE_KEY,
  MAX_FAVORITES,
  favoriteEntries,
  favoritesCountLabel,
  parseFavorites,
  serializeFavorites,
  toggleFavorite,
} from "./favorites";
import { mountOrbitHistoryBrowser } from "./orbit-history-browser";
import { mountEventReplay, type OrbitDecayReplayView } from "./event-replay";
import {
  ARCHIVE_OFFLINE,
  ARCHIVE_OFFLINE_STATE,
  isArchiveOfflineStatus,
  shardFor,
} from "./orbit-history";
import type { OrbitEventsBundle, OrbitHistoryShard, OrbitShardResult } from "./orbit-history";
import { ALL_RADIATION_PITCH_CHANNELS, GEOSPACE_BOUNDARY_COLORS, GEOSPACE_STRUCTURE_REGIONS, OMNIDIRECTIONAL_RADIATION_PITCH } from "./geospace-runtime";
import type {
  GeospaceFieldLegendMetadata,
  GeospaceRuntimeFrameState,
  GeospaceRuntimeReadyState,
  GeospaceStructureLegendMetadata,
  PlasmaSheetLegendMetadata,
  RadiationBeltRuntimeView,
} from "./geospace-runtime";
import {
  PLASMA_SHEET_BETA_LOG_RANGE,
  PLASMA_SHEET_GRADIENT_CSS,
  PLASMA_SHEET_LIMITATION,
  PLASMA_SHEET_REPRESENTATION,
} from "./plasma-sheet";
import { isCombinedRadiationEnergy, trappedPitchIndex } from "./radiation-belt";
import { RADIATION_VOLUME_GRADIENT_CSS, RADIATION_VOLUME_TRANSFER } from "./radiation-belt-volume";
import { DEFAULT_ISOPYCNIC_KG_M3, THERMOSPHERE_LIMITATION, chooseThermosphereFrame, circularOrbitalSpeedMs, coverageBandPercent, decodeThermosphereFrame, densityKgM3, dragDecelerationMs2, shardsNear, thermosphereBadge, type DecodedFrame, type EmpiricalThermosphereShard, type ThermosphereBundle, type ThermosphereSelection } from "./thermosphere";
import { THERMOSPHERE_VOLUME_ALTITUDE_KM, THERMOSPHERE_VOLUME_COLOR_HEX } from "./thermosphere-volume";

/**
 * The spacecraft the drag figure is quoted FOR, stated rather than implied.
 *
 * 100 kg/m2 is a representative ballistic coefficient for a large LEO
 * spacecraft; 420 km is the altitude NASA names when it says the ISS orbits
 * inside the thermosphere. Naming a reference is the honest alternative to
 * printing a drag number for a specific satellite whose true mass and area the
 * catalogue does not carry.
 */
const THERMOSPHERE_DRAG_REFERENCE = { altitudeKm: 420, ballisticCoefficientKgM2: 100 } as const;
import { EXTERIOR_CUSP_COLOR, geoToSceneVector, MAGNETOPAUSE_MODEL_COLORS, resolveVisibleIndices, satelliteDisplayRadius, SpaceGlobe, type FieldRendering, type LandGeoJson, type ReferenceFrame } from "./globe";
import type { MagnetopauseModelId } from "./magnetopause";
import { adaptiveOrbitPath, orbitPathTolerance } from "./orbit-polyline";
import { parseDistanceScale, type DistanceScaleId } from "./radial-ruler";
import {
  ArtifactRefreshController,
  DEFAULT_ARTIFACT_REFRESH_INTERVAL_MS,
  type ArtifactRefreshStatus,
  type ArtifactRefreshUpdate,
} from "./artifact-refresh";
import { IonosphereSampler, selectIonosphereFrames } from "./ionosphere-volume";
import { sampleEmpiricalDRegion } from "./d-region-empirical";
import { compositeProfile, COMPOSITE_IONOSPHERE_METHOD } from "./ionosphere-composite";
import {
  allIonosphereRegionsOn,
  IONOSPHERE_REGION_BANDS,
  type IonosphereRegionId,
  type IonosphereVolumeBake,
} from "./ionosphere-density-volume";
import { drawLayerLadder, layerRow, networkNote } from "./ionosphere-composite-view";
import {
  nearestSounding,
  relevanceNote,
  soundingAgeNote,
  soundingRelevance,
  SOUNDING_EVIDENCE_NOTE,
  type SoundingBundle,
} from "./ionosonde-soundings";
import {
  ECCENTRIC_DIPOLE_LIMITATION,
  eccentricDipole,
  eccentricDipoleFieldNt,
  eccentricDipoleShell,
} from "./eccentric-dipole";
import { decimalYear } from "./dipole-tilt";
import {
  COLUMN_LIMITATION,
  GNSS_L1_MHZ,
  MUF_LIMITATION,
  mufMhz,
  profileEvidenceNote,
  sampleProfile,
  type ProfileDerivations,
  type SampledProfile,
} from "./ionosphere-profile";
import {
  classifyGeoSubtype,
  elementAgeDays,
  footprintPoints,
  formatAltitude,
  propagateOmm,
  propagateOmmInFrozenEarthFrame,
} from "./orbit";
import { OrbitPropagator } from "./propagator";
import {
  type DgcpmBundle,
  type DgcpmNowcast,
  type DgcpmPlasmasphereField,
  type DgcpmSequence,
  type PlasmasphereLayerField,
  CARPENTER_ANDERSON_1992,
  CARPENTER_ANDERSON_KP,
  OBRIEN_MOLDWIN_DST,
  PLASMASPHERE_DENSITY_SCALE,
  PLASMASPHERE_COROTATION,
  PLASMASPHERE_COROTATION_SPEEDUP,
  PLASMASPHERE_DGCPM,
  SUNSPOT_NUMBER_REFERENCE,
  DGCPM_NOWCAST_CLOCK_SLACK_MINUTES,
  DGCPM_NOWCAST_HOLD_CADENCES,
  decodeDgcpmSequence,
  dgcpmFieldAt,
  dgcpmNowcastLine,
  duskBulgeL,
  plasmasphereFieldAt,
} from "./inner-magnetosphere";
import {
  type DriftSpecies,
  type RingCurrentFormation,
  type RingCurrentIllustration,
  DEFAULT_RING_CURRENT_ION,
  RING_CURRENT_ENERGY_SCALE,
  RING_CURRENT_FORMATION,
  RING_CURRENT_ION_CHOICES,
  RING_CURRENT_SEEDS,
  corotationAngularRateRadPerS,
  energyAtLKeV,
  magneticDriftAngularRateRadPerS,
  magneticDriftPeriodHours,
  ringCurrentIllustration,
  ringCurrentLapSpread,
  ringCurrentPulsePeriodDisplaySeconds,
} from "./ring-current-illustration";
import {
  FIELD_LINE_DISPLAY_LOG_RANGE,
  FIELD_LINE_METHOD,
  type FieldLineIntegrityReport,
  type FieldLineSummary,
} from "./magnetosphere-field-lines";
import { newellBand, newellCoupling, toSegments } from "./storm-indices";
import { couplingDrive, dungeyTransportCopy } from "./dungey-transport";
import { type StormHeadline, kpDstReconciliation, renderStormPanel, stormHeadline } from "./storm-panel";
import { evidenceBadge, flareClass, renderDriverTile, renderScaleTile, scaleTile, signed, withMinusSigns } from "./conditions-board";
import type { DriverTile, EvidenceClass } from "./conditions-board";
import { drawableXraySeries, radioBlackoutLevel } from "./energy-chain";
import type { ChainSeries } from "./energy-chain";
import {
  ALPHA_TO_PROTON_NUMBER_RATIO_ASSUMED,
  SOLAR_WIND_MODE_PRESENTATION,
  XRAY_FLUX_GRADIENT_CSS,
  solarWindSpeciesKey,
  solarWindSpeciesMix,
} from "./solar-input-visuals";
import type {
  CatalogBundle,
  EventsBundle,
  GeospaceBundle,
  GeospaceField,
  GeospacePlane,
  HistoricalEvent,
  IonosphereVolumeBundle,
  MissionCapability,
  ReleaseManifest,
  SatelliteRecord,
  SpaceWeatherBundle,
  SwpcScaleReading,
  SwpcScalesRecord,
} from "./types";

type Density = "featured" | "standard" | "full";
type GeometryMode = "orbit" | "ground" | "footprint" | "all";
type GeoFilter = "all" | "geostationary" | "other-gso";
/** The orbit band. `null` is "no band chosen yet", which is a different state
 *  from "all" and has to stay one — collapsing them is what keeps relighting a
 *  button on a globe the reader has not asked anything of. */
export type OrbitScope = "all" | "LEO" | "MEO" | "GEO" | "HEO" | null;
/**
 * `magnetosphere` is no longer a rail layer: it is the empirical
 * Shue/Nguyen/Lin boundary set, demoted to an off-by-default annotation
 * checkbox inside the plasma-field layer's card. It keeps its LayerName
 * because its checkbox still drives `applyGlobeLayer` through the same
 * listener as every other toggle, and because the walkthrough drives it by
 * id. The old `structures` curves-as-a-layer presentation is gone entirely:
 * the field itself is the layer now, and the extracted curves are annotation.
 * `ringCurrent` is a layer again, and it is a different object from the one
 * that was deleted. The old one drew a TORUS from the Dessler-Parker-Sckopke
 * energy: one number rendered as a solid shape, with its radius, its width and
 * its cross-section all invented. That is still forbidden and is still gone.
 * What is here now claims nothing about where the ring current IS — it is an
 * explicitly labelled ILLUSTRATION of how it forms, drift paths computed in
 * the same published convection field the plasmasphere layer is eroded by. The
 * distinction is the whole of `src/ring-current-illustration.ts`'s header.
 */
type LayerName = "ionosphere" | "tec" | "drap" | "aurora" | "regions" | "magnetosphere" | "plasmasphere" | "ringCurrent" | "geospace" | "plasmaSheet" | "solarWind" | "photons" | "radiation" | "groundStations" | "groundField" | "thermosphere";
type RenderingProfile = "auto" | "efficient" | "quality";
type MarkerSize = "compact" | "standard" | "large";
type MotionRate = "adaptive" | "60" | "30" | "20";
type ColorMode = "mission" | "constellation" | "country";
type InterfaceScale = "standard" | "large" | "largest";
type TimedPlayback = { startMs: number; endMs: number; startedAt: number; wallDurationMs: number; label: string };
type LegendEvidence = Evidence;
export type LayerUnavailableNotice = {
  headline: string;
  because: string;
  jumpToIso?: string;
  jumpLabel?: string;
};
export type EnvironmentLegendSpec = {
  layer: LayerName;
  title: string;
  /**
   * What the legend calls this layer, when that differs from what the data
   * viewer's card calls it. The legend is a colour bar, a name and units, and
   * the name is the *layer's* — it must not change under the reader because a
   * selection changed. Only the ground-station layer needs this so far: its
   * card is renamed to the antenna a visitor just clicked, which is the clearest
   * confirmation the click landed, while its legend row stays "Ground stations".
   */
  keyTitle?: string;
  badge: string;
  evidence: LegendEvidence;
  scale?: {
    gradient: string;
    minimum: string;
    label: string;
    maximum: string;
    /**
     * ONE COLOUR PER VALUES CELL, for a bar whose cells are CATEGORIES rather
     * than the ends of a ramp.
     *
     * Almost every layer's bar is a scale: the three cells under it are a
     * minimum, the units, and a maximum, and no cell has a colour of its own.
     * The solar wind's bar is not a scale — it is a COMPOSITION, and its three
     * cells name the three species. Its He²⁺ segment is 1.9% of the bar, which
     * is five pixels against the bar's own border, so the bar cannot double as
     * the colour key and the owner read the legend as saying the wind has two
     * constituents. Set this and each cell carries the colour of the thing it
     * names; the units then move into the row's title, where they cannot
     * truncate. Left unset — every other layer — nothing changes.
     */
    cellSwatches?: readonly [string, string, string];
  };
  /**
   * A LIST WHERE A BAR WOULD BE — for a layer whose quantity is a composition
   * rather than a ramp.
   *
   * Set this and the colour bar is not drawn at all, because for this one
   * layer the bar was the defect. The solar wind is 51% e⁻, 47% H⁺ and 2%
   * He²⁺, and a 290 px bar draws that last share as 5.5 px against its own
   * border: Sean read the legend as naming two species. Easing the widths to
   * the square root of the shares fixed the pixels and cost a declared
   * distortion, and he read the result as *"a small sliver to the right"* —
   * the bar failing at its one unique job for the second time.
   *
   * His own proposal replaced it: *"Perhaps the bar doesn't show the
   * percentages by area, it lists them and it gives energy levels of particles
   * shown and the percentages are with the color labels."* Nothing true was
   * lost — the percentages were always text — and the rows now carry the
   * REASON the species behave differently, which a proportion bar never could.
   *
   * `detail` is the second column: a number in the layer's own units, on the
   * same row as the swatch and the share. `caption` names what that column is
   * and what class of claim it makes, once, under the list.
   */
  composition?: {
    caption: string;
    rows: Array<{ swatch: string; name: string; detail: string; note?: string }>;
  };
  /**
   * EVERY DRAWN THING IN THIS LAYER THAT IS NOT ON THE RAMP ABOVE.
   *
   * The legend is one colour bar per layer, which answers "what do these
   * colours mean" and answers nothing at all about a surface drawn in a flat
   * colour beside them. The magnetosphere layer draws two large amber cusp
   * funnels on its default face and, on the shipped build of 2026-08-26,
   * nothing anywhere on the page named them. Sean read them as bow shocks —
   * which is the wrong way round (a bow shock STOPS the solar wind, upstream
   * of everything here; the cusp is where it gets IN), and if the owner
   * misread it a student certainly will.
   *
   * So: one row per drawn thing, in the colour it is actually drawn in, with
   * its evidence class, in both the legend and the layer's card. A mark must
   * be listed only while the thing is genuinely on screen — a swatch for a
   * surface that is not drawn is the same defect pointing the other way.
   */
  marks?: Array<{ swatch: string; name: string; evidence: LegendEvidence; what: string }>;
  /**
   * What this layer reads RIGHT NOW. Every entry here has to pass the clock
   * test in `dataViewerSections`: move the selected time and the value moves.
   */
  stats?: Array<{ label: string; value: string }>;
  /**
   * What is true at every instant of the published record — the standing
   * physics behind the picture, quoted with its numbers so a reader can check
   * it. Not printed in the Data Explorer. It is rendered live, from this same
   * spec, into the layer's own card on Data & methods, which is where the
   * derivations live for every layer at once.
   *
   * NOTHING IS DELETED BY BEING PUT HERE, and nothing that qualifies a claim
   * belongs here: a caveat stays on the Data Explorer card, where it is read
   * beside the picture it qualifies. See `dataViewerSections` for the rule and
   * the measurement that forced it.
   */
  standing?: Array<{ label: string; value: string }>;
  note: string;
  /**
   * ONE LINE UNDER THE COLOUR BAR, saying what the layer currently reads.
   *
   * The legend is the surface that is never folded away, and it was the
   * surface with the least to say: a 3-30 MHz ramp over a bare globe, drawn
   * identically whether the D region was quiet or the artifact had failed.
   * `note` is the card's prose and the card opens collapsed; this is the
   * sentence that has to survive that. Rendered only while the layer is
   * actually drawing -- an empty layer has `unavailable.because` in this slot
   * instead, and printing both would say two different things at once.
   */
  conditionLine?: string;
  validAt?: string;
  observedAt?: string;
  source?: string;
  coverage?: string;
  statusText?: string;
  statusState?: "ready" | "no-data" | "stale" | "loading";
  /**
   * What the legend's struck-out bar says in place of "NO DATA AT THIS TIME".
   *
   * Almost every empty layer means the same thing — a frame that has not
   * arrived — and the shared phrase is right for those. The magnetosphere past
   * the last measurement means something else and permanent: there is no
   * forecast of it to draw, from anyone. Sean asked for the legend itself to
   * say that, and a layer that is off for a different reason has to be allowed
   * to give its own reason.
   */
  emptyLabel?: string;
  /**
   * The layer's own no-data notice, when the generic coverage one would be
   * wrong. `layerCoverageNotice` composes "X only goes back to ..." / "X stops
   * at ...; the next frame has not arrived yet", which is true of a feed with
   * a gap in it and false of a quantity nobody forecasts at all.
   */
  unavailable?: LayerUnavailableNotice;
};

/**
 * A renderer colour, as CSS. The swatch on a legend row has to be the same
 * colour as the surface it names, so both read the one constant rather than a
 * hex string typed out a second time.
 */
function hexColor(color: number): string {
  return `#${color.toString(16).padStart(6, "0")}`;
}

/**
 * THE MAGNETOSPHERE LAYER'S COLOUR KEY FOR EVERYTHING THAT IS NOT ON THE RAMP.
 *
 * The layer's ramp is |B| (or the chosen BATS-R-US field). Everything else it
 * can draw is a flat-coloured surface or curve, and on the shipped build of
 * 2026-08-26 none of them had a row: the amber cusp funnels (which Sean read
 * as a bow shock), and behind the two annotation ticks a bow-shock curve, a
 * magnetopause-proxy curve and three empirical fits. The prose named them; the
 * prose does not tell you WHICH orange is which.
 *
 * That mattered most for the two warm ones. The cusp funnels are `#ffb257` and
 * the extracted bow shock is `#f5c96a` — one tick apart, and the second is one
 * click away in the same settings panel. So the row that corrects the misread
 * and the row for the thing it was mistaken FOR now appear together, each in
 * the colour the renderer actually uses.
 *
 * Every swatch is read from the renderer's own constant — `EXTERIOR_CUSP_COLOR`
 * and `MAGNETOPAUSE_MODEL_COLORS` in globe.ts, `GEOSPACE_BOUNDARY_COLORS` in
 * geospace-runtime.ts — so a swatch cannot drift off the pixels it points at.
 * And every row is conditional on the thing being on screen right now: the
 * cusps on the globe's own "is the mesh in the scene" flag, the annotation
 * curves on their ticks, and the three fits on which ones the boundary pass
 * actually evaluated and drew.
 */
const EMPIRICAL_BOUNDARY_MARKS: Record<MagnetopauseModelId, { name: string; what: string }> = {
  shue1998: {
    name: "Shue (1998) magnetopause fit",
    what: "An axisymmetric fit to thousands of spacecraft crossings, driven by the live dynamic pressure and Bz. "
      + "It is the only one of the three fitted down the tail, so when the other two are drawn it is shown from "
      + "where they stop, outward.",
  },
  nguyen2022: {
    name: "Nguyen (2022) current sheet",
    what: "The outer wall of the cusp: a crossing fit that carries the dipole tilt and the IMF clock angle, so it "
      + "indents where the cusps are instead of staying smooth.",
  },
  lin2010: {
    name: "Lin (2010) cusp inner boundary",
    what: "The inner wall of the cusp, from the same kind of crossing fit. The volume between this and Nguyen's "
      + "sheet is what the polar-cusp annotation shades.",
  },
};

/**
 * Every mark the magnetosphere layer owes right now, in one list for both of
 * its faces — the driven field lines and the embedded NOAA MHD cut. The cusp
 * funnels are drawn in the field-line group, which stays on screen when the
 * cut is switched on, so the cut's own card owes the same row.
 */
function magnetosphereMarks(input: MagnetosphereFieldSpecInput): EnvironmentLegendSpec["marks"] {
  const marks: NonNullable<EnvironmentLegendSpec["marks"]> = [];
  if (input.cuspFunnelsDrawn) {
    marks.push({
      swatch: hexColor(EXTERIOR_CUSP_COLOR),
      name: "Polar cusps — north and south",
      evidence: "empirical",
      what: "Not a bow shock. The two funnels where the boundary opens and solar-wind plasma reaches the "
        + "atmosphere — the one way in on the dayside. Drawn as the volume between Lin (2010)'s cusp inner "
        + "boundary and Nguyen (2022)'s magnetopause current sheet, which is why there are two lobes on the "
        + "noon meridian rather than a shell.",
    });
  }
  if (input.extractedAnnotationOn) {
    marks.push({
      swatch: hexColor(GEOSPACE_BOUNDARY_COLORS.bowShock),
      name: "Bow shock — extracted curve",
      evidence: "model",
      what: `${GEOSPACE_STRUCTURE_REGIONS.bowShock.what} This is the only bow shock this layer can draw, and it is `
        + "the near neighbour of the cusp funnels in colour and nothing like them in physics: it stands roughly "
        + "13 R⊕ upstream and is where the wind is STOPPED, while a cusp is where it gets in. A dayside cap only — "
        + "the extraction runs 70° either side of the nose, so there are no flanks and no tail.",
    });
    marks.push({
      swatch: hexColor(GEOSPACE_BOUNDARY_COLORS.magnetopauseProxy),
      name: "Magnetopause proxy — extracted curve",
      evidence: "model",
      what: `${GEOSPACE_STRUCTURE_REGIONS.magnetopause.what} Read off the same two published NOAA cuts as the `
        + "bow-shock curve, which is what makes it a proxy: it is where the extraction finds the jump, not a "
        + "published boundary surface. The three empirical fits are the separate opinion to compare it against.",
    });
  }
  if (input.empiricalAnnotationOn) {
    (input.empiricalModelsDrawn ?? []).forEach((id) => {
      const entry = EMPIRICAL_BOUNDARY_MARKS[id];
      if (!entry) return;
      marks.push({
        swatch: hexColor(MAGNETOPAUSE_MODEL_COLORS[id]),
        name: entry.name,
        evidence: "empirical",
        what: entry.what,
      });
    });
  }
  return marks.length > 0 ? marks : undefined;
}

/**
 * One "this colour is that thing" row, shared by the legend card and the
 * layer's own card so the two can never name the same surface differently.
 *
 * The swatch is the colour the renderer actually draws with — see
 * `EXTERIOR_CUSP_COLOR` in globe.ts and `GEOSPACE_BOUNDARY_COLORS` in
 * geospace-runtime.ts, which are the single copies these read — and the
 * evidence class is the same word and the same colour the layer's own badge
 * uses, because "what is it" and "how do we know" are one answer here.
 */
function legendMarkRow(mark: { swatch: string; name: string; evidence: LegendEvidence; what: string }): HTMLLIElement {
  const row = document.createElement("li");
  row.className = "legend-mark";
  const dot = document.createElement("i");
  dot.style.setProperty("--legend", mark.swatch);
  const name = document.createElement("strong");
  name.textContent = mark.name;
  const badge = document.createElement("em");
  badge.className = `layer-status ${mark.evidence}`;
  badge.textContent = LEGEND_EVIDENCE_LABELS[mark.evidence];
  row.append(dot, name, badge);
  row.title = `${mark.name} — ${mark.what}`;
  return row;
}

/**
 * The ionosphere's four named regions, as legend marks — and, just as
 * important, as the two lists of regions that get NO mark and why.
 *
 * Sean asked for this twice. He read the picture correctly ("I see what I
 * think is the D layer in orange") and the layer had never named it; then he
 * asked for D, E, F1 and F2 to be shown somewhere. This is the naming half.
 *
 * Three states, three renderings, and they must not be collapsed:
 *
 *   DRAWN          a mark row, in the colour the renderer paints that band.
 *   SWITCHED OFF   no row, and a card line saying the reader hid it.
 *   NOT DRAWN      no row, and a card line saying nothing was published at
 *                  those heights. Different fact, different sentence.
 *
 * A row for a region that is not in the picture is its own small lie, and so
 * is leaving a reader to guess which of the two reasons applies.
 *
 * The badge on each row is the evidence class of WHAT IS DRAWN in that band.
 * D is the empirical Wait–Spies fit driven by a measured X-ray flux; the three
 * above it are WAM-IPE, and are MODEL. That is not the same list as the
 * composite profile's per-layer evidence, where E and F1 are Chapman shapes
 * anchored to ionosondes and badge COMPOSITE — because those anchored layers
 * are not what the volume paints. Claiming them here would put a sounding's
 * authority on pixels no sounding touched. The rows point at the profile
 * instead, which is where that evidence actually lives.
 *
 * Swatches are `bake.measured.regions[...].swatchHex`: the ramp colour at the
 * MEASURED median of the very byte the fragment shader feeds into the ramp for
 * that band. Not a colour chosen to describe the region — the colour the
 * renderer paints it. So the F2 row comes out near-white and the E row a dim
 * blue, and the two-decade density difference between them is in the legend
 * for free, and no swatch can drift from the pixels.
 */
export function ionosphereRegionMarks(input: {
  bake: IonosphereVolumeBake | null;
  enabled: Record<IonosphereRegionId, boolean>;
  f1CriterionPercent: number | null;
  hmF2Km: number | null;
}): {
  marks: Array<{ swatch: string; name: string; evidence: LegendEvidence; what: string }>;
  switchedOff: IonosphereRegionId[];
  notDrawn: IonosphereRegionId[];
} {
  const marks: Array<{ swatch: string; name: string; evidence: LegendEvidence; what: string }> = [];
  const switchedOff: IonosphereRegionId[] = [];
  const notDrawn: IonosphereRegionId[] = [];
  const bake = input.bake;
  // No bake means nothing is baked yet, which the card already says in its own
  // status line. Naming four regions over an empty scene would be worse than
  // saying nothing.
  if (!bake) return { marks, switchedOff, notDrawn };

  const share = (percent: number | null) =>
    percent === null ? "a vanishing share of" : `${percent.toFixed(0)}% of`;

  for (const band of IONOSPHERE_REGION_BANDS) {
    if (!input.enabled[band.region]) {
      switchedOff.push(band.region);
      continue;
    }
    const measured = bake.measured.regions[band.region];
    if (!measured || measured.drawnSampleCount === 0) {
      notDrawn.push(band.region);
      continue;
    }
    if (band.region === "D") {
      marks.push({
        swatch: measured.swatchHex,
        // CORRECTNESS FIX 2026-09-04: the D region is 60–90 km, which is what
        // this site says everywhere else it says it — `content.ts` twice ("D
        // region, 60–90 km") and the D-region layer page (`extent: "60 – 90
        // km"`). 85 km is the top of the Wait–Spies FIT's domain, not the top
        // of the region, and naming the region by its fit taught a reader
        // sitting a qualification a boundary 5 km low. The selection band this
        // row belongs to is 60–90 too (`IONOSPHERE_REGION_BANDS`), so the name
        // was not even the band it switches. The fit's own limit is a real
        // fact and now travels in the body text, where the layer page already
        // puts it.
        name: "D region · 60–90 km",
        evidence: "empirical",
        what: "The warm band at the bottom, and the only one of the four that is not the model: the Wait–Spies "
          + "profile, driven by the sun's angle over each point and the measured GOES 0.1–0.8 nm X-ray flux. It has "
          + "its own palette and its own density window because it holds two to three decades fewer electrons than "
          + "the F2 peak and would otherwise clamp to nothing. No ionosonde can measure it — sounding waves pass "
          + "straight through — so it shows up as the echo it absorbs, which is what the D-region HF absorption "
          + "layer draws. The fit's own domain stops at 85 km and the WAM-IPE grid starts at 90, so the 5 km "
          + "between them is drawn as nothing: neither model publishes it, and the seam is left rather than "
          + "interpolated across. It is 0.38 scene units wide, which reads as the seam it is.",
      });
      continue;
    }
    if (band.region === "E") {
      marks.push({
        swatch: measured.swatchHex,
        name: "E region · 90–150 km",
        evidence: "model",
        what: "WAM-IPE at E-region heights, and the model's electron density there rather than an E layer. Measured "
          + "on the live artifact rather than assumed: the E ledge's median prominence above the E–F valley is "
          + "0.02 dex, one code in 256, and on the DAYSIDE it is negative — density climbs straight out of E into F "
          + "with no local maximum to find. The E layer proper, a Chapman shape near 110 km whose strength comes from "
          + "ionosondes that sounded it within the last three hours, is in the vertical profile, one click away in "
          + "this layer's settings.",
      });
      continue;
    }
    if (band.region === "F1") {
      marks.push({
        swatch: measured.swatchHex,
        name: "F1 region · 150–200 km",
        evidence: "model",
        what: "WAM-IPE at F1 heights, on the same terms as E, and harder: the published F1 criterion finds a distinct "
          + `maximum over ${share(input.f1CriterionPercent)} columns. An F1 LAYER exists only in strong daylight — `
          + "across the whole sounding network foF1 was reported in 80% of records below 30° solar zenith angle and in "
          + "none at all above 80° — so whether there is one over a particular place is a question the vertical "
          + "profile answers and a global band cannot. This band is drawn day and night because the model publishes "
          + "plasma at these heights day and night.",
      });
      continue;
    }
    marks.push({
      swatch: measured.swatchHex,
      name: "F2 region · 200 km and above",
      evidence: "model",
      what: "The F2 peak and the whole topside out to 2,655 km, and the region WAM-IPE genuinely does resolve"
        + (input.hmF2Km !== null ? `, with hmF2 averaging ${input.hmF2Km.toFixed(0)} km right now` : "")
        + ". It is the brightest thing in the picture: the near-white end of the ramp is the peak and the topside "
        + "trails off through blue. Its electron density is derived by quasi-neutral summation of seven published "
        + "ion densities rather than published directly.",
    });
  }

  return { marks, switchedOff, notDrawn };
}

/** The word each evidence class puts on a mark's badge. */
const LEGEND_EVIDENCE_LABELS: Record<LegendEvidence, string> = {
  observed: "OBSERVED",
  assimilated: "ASSIMILATED",
  forecast: "FORECAST",
  model: "MODEL",
  empirical: "EMPIRICAL",
  composite: "COMPOSITE",
  schematic: "SCHEMATIC",
};

/**
 * Why the empirical profile is on screen instead of the simulation.
 *
 * Every one of these is a different fact about the release and the reader is
 * owed the difference: a release that never published frames is not the same
 * as one whose frames do not reach the selected time, and neither is the same
 * as a download that failed.
 */
export type PlasmasphereSimulationState =
  | "not-published"
  | "not-loaded"
  | "load-failed"
  | "outside-window";

export const PLASMASPHERE_SIMULATION_STATUS: Record<PlasmasphereSimulationState, string> = {
  "not-published": "NO SIMULATION IN THIS RELEASE",
  "not-loaded": "SIMULATION NOT LOADED YET",
  "load-failed": "SIMULATION COULD NOT BE LOADED",
  "outside-window": "OUTSIDE THE SIMULATED WINDOW",
};

/**
 * The plasmasphere layer's legend and data-viewer card, as a pure function of
 * the evaluated field.
 *
 * Pulled out of the class on purpose. The legend renderer prints
 * "SHAPE ONLY" for any layer whose spec carries no `scale`, and the project
 * owner's first acceptance check is that no shipped layer reaches that
 * branch. A test can call this and look at the real spec the interface will
 * render, rather than at a copy of the reasoning.
 */
export function plasmasphereLegendSpec(
  field: PlasmasphereLayerField | null,
  simulationState: PlasmasphereSimulationState = "not-published",
): EnvironmentLegendSpec {
  if (field?.source === "dgcpm") return dgcpmLegendSpec(field);
  const scale = PLASMASPHERE_DENSITY_SCALE;
  const c = CARPENTER_ANDERSON_1992;
  const state = field?.plasmapause ?? null;
  const sample = (lRe: number) => {
    // Quoted at midnight, which is the local time the model fits directly and
    // where the plasmapause is sharpest.
    const value = field?.densityAt(lRe, 0) ?? null;
    if (value === null) return "—";
    return value >= 100 ? value.toFixed(0) : value >= 10 ? value.toFixed(1) : value.toFixed(2);
  };
  return {
    layer: "plasmasphere",
    title: "Plasmasphere",
    badge: "EMPIRICAL PROFILE",
    evidence: "empirical",
    scale: {
      gradient: scale.gradient,
      minimum: scale.minimumLabel,
      label: scale.label,
      maximum: scale.maximumLabel,
    },
    stats: field && state ? [
      { label: "PLASMAPAUSE", value: `L ${state.lppRe.toFixed(2)} ± ${state.rmseL.toFixed(1)}` },
      { label: "nₑ AT L 2.5 / 4 / 6", value: `${sample(2.5)} / ${sample(4)} / ${sample(6)} cm⁻³` },
      { label: "DEEPEST DST, 24 H", value: `${state.dstMinimumNt.toFixed(0)} nT at ${utcMinuteLabel(state.dstMinimumAt)}` },
      { label: "KNEE WIDTH", value: `${(field.outerLimitMidnightRe - state.lppRe).toFixed(2)} L at midnight, ${(field.outerLimitNoonRe - state.lppRe).toFixed(2)} L at noon` },
      { label: "SAMPLES IN WINDOW", value: String(state.dstSampleCount) },
      { label: "SUNSPOT NUMBER R̄", value: `${SUNSPOT_NUMBER_REFERENCE.value} (${SUNSPOT_NUMBER_REFERENCE.forMonth}, not live)` },
      { label: "STATE", value: state.quietClamped ? "REFILLED · QUIET INTERCEPT" : state.lppRe < 4 ? "ERODED" : "NOMINAL" },
      {
        label: "GRAIN MOTION",
        value: `COROTATION · ONE TURN EVERY ${PLASMASPHERE_COROTATION.displaySecondsPerRevolution} s (≈${PLASMASPHERE_COROTATION_SPEEDUP.toLocaleString("en-US")}× REAL TIME)`,
      },
    ] : [{ label: "SELECTED UTC", value: "NO DST RECORD FOR THE PRECEDING DAY" }],
    note: `Colour is electron density from ${c.citation} (doi:${c.doi}), the ISEE/whistler model: a saturated profile `
      + `log₁₀nₑ = ${c.saturatedSlopePerL}·L + ${c.saturatedIntercept} plus annual, semiannual and solar-cycle terms inside the plasmapause, a decade-per-`
      + `${c.plasmapauseNightWidthL}-L knee at it, and the L^${c.troughExponent} plasma trough outside. Nothing draws the plasmapause: it is where the colour jumps, because that is what a `
      + `plasmapause is. Valid L ${c.innerValidL}–${c.outerValidL}; outside that the model is not fitted and nothing is drawn. `
      + `The boundary comes from ${OBRIEN_MOLDWIN_DST.citation} (doi:${OBRIEN_MOLDWIN_DST.doi}), Lpp = ${OBRIEN_MOLDWIN_DST.a}·log₁₀(−min Dst over 24 h) + ${OBRIEN_MOLDWIN_DST.b}, RMS about ${OBRIEN_MOLDWIN_DST.rmseL} L, `
      + `because this release's Kp series is too short to drive Carpenter & Anderson's own Lppi = ${CARPENTER_ANDERSON_KP.b} ${CARPENTER_ANDERSON_KP.a} ·Kpmax. `
      + "Erosion is fast and refilling takes days, which is why the dense core stays small after a storm peak instead of springing back with the index. "
      + "This is an EQUATORIAL model, drawn as a stipple filling the dipole flux tubes: each grain carries the equatorial density of the L shell it sits on, and the real variation along a field line is not modelled and not invented. "
      + "It resolves no local-time structure inside the plasmasphere — no dusk bulge, no drainage plume. The trough and the knee width do carry local time, over the model's own 00–15 MLT; "
      + "the 15–24 MLT sector follows the paper's section 4 instruction to hold the dayside values to about 20 MLT with a linear transition to nighttime conditions between 19 and 20 MLT. "
      + `The solar-cycle term is evaluated at R̄ = ${SUNSPOT_NUMBER_REFERENCE.value} for ${SUNSPOT_NUMBER_REFERENCE.forMonth} (${SUNSPOT_NUMBER_REFERENCE.source}); a 13-month mean cannot exist for the current month, and this release publishes no sunspot record, so that one input is not live. `
      + plasmasphereMotionNote(null),
    validAt: field?.validAt,
    source: "Kyoto WDC quicklook Dst, via this release's storm block",
    statusText: `${PLASMASPHERE_SIMULATION_STATUS[simulationState]} · EMPIRICAL PROFILE SHOWN`,
    statusState: field ? "ready" : "no-data",
  };
}

/**
 * What the card says about the grains moving.
 *
 * The layer used to draw a fixed cloud of samples, and the project owner read
 * exactly what was on screen: "since the dots of the plasmasphere don't
 * change, it makes it look like a static thing." The grains now corotate. Two
 * things have to be said out loud for that to be honest rather than decorative
 * — that the SHAPE is sun-fixed while the MATERIAL flows through it, and that
 * the speed is a display cadence, the same statement the solar-wind shower's
 * tracers already carry.
 *
 * `stagnationLRe` is the published dusk stagnation point of the frame on
 * screen, which is the honest measure of the part of the drift NOT drawn: the
 * convection that shapes the bulge and the plume lives in the field the grains
 * are sampling, not in their motion. The empirical profile has no convection
 * field at all, and passes null.
 */
export function plasmasphereMotionNote(stagnationLRe: number | null): string {
  const revolutionSeconds = PLASMASPHERE_COROTATION.displaySecondsPerRevolution;
  const speedup = PLASMASPHERE_COROTATION_SPEEDUP.toLocaleString("en-US");
  return "THE GRAINS MOVE; THE SHAPE DOES NOT. The pattern on screen is fixed to the Sun — the drift geometry that makes it is set by "
    + "where the Sun is, and Earth turns underneath it while the shape holds station. The cold plasma itself corotates with Earth and flows "
    + "THROUGH that standing shape, the way water flows through a standing wave. That is why a grain brightens as it enters the dense core and "
    + "fades as it is carried out into the trough: each grain shows the density where it is NOW, not a value it was born with. Corotation is one "
    + `turn per day and would be invisible, so the grains run on a display cadence — one drawn revolution every ${revolutionSeconds} seconds, about `
    + `${speedup}× real time, the same kind of display encoding the solar-wind shower's tracers use. Only the grain motion is accelerated: the `
    + "published frames, the timeline and every number on this card are untouched. "
    + (stagnationLRe === null
      ? "This profile carries no convection electric field of its own, so corotation is the whole of the drawn motion — and the model is "
        + "axisymmetric inside the plasmapause, so the streaming through it is genuinely subtle rather than understated for effect."
      : "The grains carry the corotation part of the drift only. The Volland-Stern convection that produced the dusk bulge and any plume is in "
        + `the FIELD they are sampling, not in their motion; at this frame's Kp it cancels corotation at L ${stagnationLRe.toFixed(2)} on the dusk `
        + "meridian, so read the drawn streaming as the first-order flow well inside that and as understated near it.")
    + " Switching off Environmental motion in Display settings freezes the grains where they are.";
}

/**
 * The plasmasphere card when the running simulation is what is on screen.
 *
 * Everything here is read off the published frame rather than recomputed, so
 * the numbers a reader sees are the numbers the model actually produced and
 * the numbers `tests/test_plasmasphere_dgcpm.py` checks.
 */
export function dgcpmLegendSpec(field: DgcpmPlasmasphereField): EnvironmentLegendSpec {
  const scale = PLASMASPHERE_DENSITY_SCALE;
  const frame = field.frame;
  const drive = field.bundle.drive;
  const sample = (lRe: number) => {
    const value = field.densityAt(lRe, 0);
    if (value === null) return "—";
    return value >= 100 ? value.toFixed(0) : value >= 10 ? value.toFixed(1) : value.toFixed(2);
  };
  const boundaryAt = (mlt: number) => {
    const found = field.plasmapauseByMlt.find((point) => Math.abs(point.mltHours - mlt) < 0.3)?.lRe ?? null;
    return found === null ? "—" : found.toFixed(2);
  };
  const bulge = duskBulgeL(field);
  // The published second measure of the same boundary: where the density falls
  // fastest, rather than where it crosses a stated level. The two disagree by
  // about an L in the outer plasmasphere because the tubes out there are only
  // partly refilled, and showing both is the honest way to say so.
  const kneeAtMidnight = field.frame.steepestGradientLByMlt?.[0] ?? null;
  const plume = field.plume;
  return {
    layer: "plasmasphere",
    title: "Plasmasphere",
    badge: "PHYSICS SIMULATION",
    evidence: "model",
    scale: {
      gradient: scale.gradient,
      minimum: scale.minimumLabel,
      label: scale.label,
      maximum: scale.maximumLabel,
    },
    stats: [
      { label: "PLASMAPAUSE, MEDIAN", value: `L ${field.plasmapauseLRe.toFixed(2)}` },
      {
        label: "BOUNDARY AT 00 / 06 / 12 / 18 MLT",
        value: `${boundaryAt(0)} / ${boundaryAt(6)} / ${boundaryAt(12)} / ${boundaryAt(18)}`,
      },
      { label: "DUSK BULGE", value: bulge === null ? "—" : `${bulge >= 0 ? "+" : ""}${bulge.toFixed(2)} L over midnight` },
      { label: "STEEPEST KNEE AT MIDNIGHT", value: kneeAtMidnight === null ? "—" : `L ${kneeAtMidnight.toFixed(2)}` },
      {
        label: "DRAINAGE PLUME",
        value: plume.present && plume.extentL !== undefined && plume.peakMltHours !== undefined
          ? `${plume.extentL.toFixed(2)} L beyond the night boundary, peaking at ${plume.peakMltHours.toFixed(1)} MLT`
          : "none in this frame",
      },
      { label: "DRIVING Kp", value: `${frame.kp.toFixed(2)} → convection A = ${frame.convectionAmplitudeVPerRe2.toFixed(0)} V Rₑ⁻²` },
      { label: "DUSK STAGNATION POINT", value: `L ${frame.stagnationL.toFixed(2)}` },
      { label: "nₑ AT L 2.5 / 4 / 6, MIDNIGHT", value: `${sample(2.5)} / ${sample(4)} / ${sample(6)} cm⁻³` },
      {
        label: "FRAME",
        value: `${utcMinuteLabel(frame.validAt)}, ${field.frameOffsetMinutes} min from the selected time`
          // The newest frame read as the present says so here as well as on
          // the legend, because a reader who has the card open is exactly the
          // reader who wants to know whether this is a frame chosen for their
          // instant or the last one published being held.
          + (field.nowcast ? ` · HELD AS THE NOWCAST — nothing newer is published${field.nowcast.held ? `, and its replacement is due at ${field.nowcast.successorDueAt.slice(11, 16)} UTC` : ""}` : ""),
      },
      { label: "SPIN-UP", value: `${drive.spinUpHours.toFixed(0)} h of measured Kp before the replay window` },
      {
        label: "GRAIN MOTION",
        value: `COROTATION · ONE TURN EVERY ${PLASMASPHERE_COROTATION.displaySecondsPerRevolution} s (≈${PLASMASPHERE_COROTATION_SPEEDUP.toLocaleString("en-US")}× REAL TIME)`,
      },
    ],
    note: `Colour is equatorial electron density from a running ${PLASMASPHERE_DGCPM.name} simulation — `
      + `${PLASMASPHERE_DGCPM.citation}, doi:${PLASMASPHERE_DGCPM.doi}. This is not a formula evaluated at a time: it is `
      + `a continuity equation for the plasma content of each magnetic flux tube, integrated forward from `
      + `${utcMinuteLabel(drive.spinUpFrom)} under the E×B drift of a Volland-Stern convection field plus corotation, `
      + `with the convection strength set by measured planetary Kp through Maynard & Chen's law `
      + `A = 0.045/(1 − 0.159 Kp + 0.0093 Kp²)³ kV Rₑ⁻² (${PLASMASPHERE_DGCPM.electricFieldRestatedBy}, doi:${PLASMASPHERE_DGCPM.electricFieldDoi}). `
      + `Flux tubes on the dayside refill from the ionosphere toward the Carpenter & Anderson saturated ceiling over about `
      + `${field.bundle.model.fillDays} days; closed tubes on the nightside drain with a ${field.bundle.model.emptyPeriodClosedDays}-day time constant; `
      + "tubes swept onto open drift paths are flushed with plasma-trough material and carried sunward. "
      + "Nothing draws the plasmapause. It is where the colour jumps, because that is what a plasmapause is — and the "
      + "dusk-side bulge and any drainage plume are where the drift paths put them, not where a shape was assumed. "
      + "IS THE PLASMASPHERE COUPLED TO ANYTHING? Yes, in one direction and honestly labelled. The solar wind is what drives "
      + "the convection electric field; Kp is a measured proxy for that field's strength, so when the wind turns southward and "
      + "geomagnetic activity rises, the convection here strengthens and the plasmasphere is eroded — the same cause that is "
      + "moving the magnetopause and the aurora on the other layers, on the same clock. The ring current is the other side of "
      + "that coin: the plasmapause sets where cold dense plasma ends, and that is where ring-current ions meet the waves "
      + "(EMIC, chorus) that scatter them, so the boundary drawn here corrals where the ring current can grow and where it "
      + "decays fastest. WHAT IS NOT MODELLED: the ring current does not feed back into this simulation, and this simulation "
      + "does not feed the ring current. There is no shielding response to the ring current's own electric field, no "
      + "sub-auroral polarisation stream, no plasmaspheric wind, and no loss to the magnetopause. "
      + "This is an EQUATORIAL model, drawn as a stipple filling the dipole flux tubes: each grain carries the equatorial "
      + `density of the L shell it sits on, and the variation along a field line is not modelled and not invented. Valid L ${field.validLRange[0]}–${field.validLRange[1]}; `
      + `outside that nothing is drawn. Frames are ${field.bundle.time.cadenceMinutes} minutes apart and are shown as published — nothing is interpolated between them. `
      + `The plasmapause radius quoted here is the outermost crossing of the ${field.bundle.plasmapause.contourCm3} cm⁻³ contour, a stated level rather than a fitted boundary. `
      + plasmasphereMotionNote(frame.stagnationL),
    validAt: frame.validAt,
    source: `${drive.index}, NOAA SWPC — ${drive.sampleCount} samples from ${utcMinuteLabel(drive.from)}`,
    // THE AGE, ON THE ONE SURFACE THAT IS NEVER FOLDED AWAY. A frame held as
    // the present is honest only while it is labelled as held; see
    // `dgcpmNowcastLine`.
    conditionLine: field.nowcast ? dgcpmNowcastLine(field.nowcast, "this density field is the newest published frame") : undefined,
    statusState: "ready",
  };
}

/**
 * The ring-current layer's legend and data-viewer card.
 *
 * ## What this card has to do, and why it is written the way it is
 *
 * It has to make TWO claims that the first version of it fused into one, and
 * fusing them is what made a reader come away thinking the layer was not worth
 * their time. Sean, looking at it: "Is the ring current really not important?
 * It just says illustration on the legend. Is it not worth showing?"
 *
 * The two claims are:
 *
 * 1. **The phenomenon is central.** A geomagnetic storm essentially IS the ring
 *    current intensifying. The westward current this population carries
 *    produces a field that opposes Earth's own at the surface, and the
 *    depression is Dst — the number in this site's own storm banner, measured
 *    hourly, grading the storm right now. Nothing else on this rail is more
 *    consequential during a storm.
 *
 * 2. **Our PICTURE of it is a reconstruction.** No upstream this site fetches
 *    publishes a ring-current ion flux on a grid, at any cadence, for any time.
 *    Dst is one number and one number has no map. So where the population is
 *    drawn comes from drift physics in the published convection field, and the
 *    word ILLUSTRATION stays on the badge, on the colour bar and in this note.
 *
 * The old card led with "WHAT IS MEASURED HERE: NOTHING" and a note that opened
 * "THIS IS AN ILLUSTRATION, NOT A MEASUREMENT, AND NOT A MODEL PRODUCT". Every
 * word of that is true and the effect of it was an apology. The provenance
 * disclosure has not been weakened by one word — it is still on four surfaces,
 * because a reader will look at exactly one of them — but it is now the SECOND
 * thing the card says, and it is about the SHAPE rather than about the subject.
 *
 * Pulled out of the class as a pure function for the same reason
 * `plasmasphereLegendSpec` was: a test can call it and inspect the real spec
 * the interface renders, in every state, and prove that none of them falls to
 * the scale-less "SHAPE ONLY" bar.
 */
/**
 * The substorm phase in the site's readout register. "Growth" is the word the
 * literature uses and it is the one that needs the gloss, because a loading
 * tail is a THINNING tail and a reader will assume the opposite.
 */
function substormPhaseLabel(state: SubstormState): string {
  switch (state.phase) {
    case "expansion": return "EXPANSION — the sheet has snapped and is injecting earthward";
    case "recovery": return "RECOVERY — the injection is decaying";
    case "growth": return "GROWTH — the tail is loading and the sheet is THINNING";
    default: return "QUIET — little southward Bz, so little is being loaded";
  }
}

/**
 * HOW LONG THE RING CURRENT'S PULSE IS, AND WHAT THAT NUMBER IS A PERIOD OF.
 *
 * Sean, on the shipped build: what is the pulsing, and is the periodicity real?
 * It is exact — `setRingCurrentVolumeTime` wraps the loop clock with a modulo —
 * and nothing on the page said so.
 *
 * These two functions are the only places the site puts a number on it, and
 * both take the loop off the DRAWN object rather than recomputing it, so a
 * quoted period can never belong to a formation the globe is not keeping.
 *
 * ## The one thing that would make this false
 *
 * A drift LAP is not the pulse, and there is no single drift lap to quote: each
 * shell has its own, and the eleven-fold spread between them at one energy is
 * the physics the layer exists to show. See `RING_CURRENT_PULSE` in
 * `ring-current-illustration.ts` for the measurement and the reasoning. So the
 * period quoted is the LOOP'S — one fill and fade of the whole ring, which is
 * genuinely one number — the ion and Kp that set it are stated beside it, and
 * the spread of laps inside it is quoted as a spread on the card.
 *
 * Every figure is derived at call time from `cycleSeconds` and the replay
 * constant. An energy selector that moved while the printed period sat still
 * would be a worse defect than the silence this replaces.
 *
 * ## WHAT THE LEGEND LINE MAY CARRY, and the measured width that decides it
 *
 * Sean, 2026-08-27, reading the shipped block: "Only that PULSE 15.7, you
 * don't need ONE FILL AND FADE. Keep it short enough to fit on one line."
 *
 * So the loop's DESCRIPTION comes off this line and the loop's NUMBER stays.
 * Nothing is lost with it. `ringCurrentPulseReading` below still prints ONE
 * FILL AND FADE OF THE RING, the hours of drift those seconds replay, that the
 * period is exact, and the spread of laps it contains — and that reading is on
 * the layer's own card, in WHAT THE MOTION CLAIMS, in every state that has a
 * formation to quote.
 *
 * The ion and the Kp DO stay here, and they are not decoration: this number
 * moves with the energy selector (3 keV / 10 keV / 30 keV give three different
 * periods), so a period printed with neither beside it is one a reader cannot
 * check or reproduce. `ring-current-illustration.test.ts` holds both to that.
 *
 * The one-line rule is a measured budget rather than a hope. The legend block
 * is `.map-key`, `min(310px, 100%)` wide, less 9 px of `.key-card` padding a
 * side: 290 px of text on a 1440-wide desktop and 350 px on a 390-wide phone,
 * where the key goes full width. `.key-card-pulse` is IBM Plex Mono at
 * `--fs-nano`, which the interface-scale control moves — 8.00 / 9.28 / 10.72 px
 * for Standard / Large (the shipped default) / Largest, measured in the browser
 * at 5.0 px per character at Large and 7.0 px at Largest. Desktop at Largest is
 * the binding case and it buys 41 characters. The longest string this function
 * can produce is "PULSE 92.2 s · 30 keV AT Kp 9.0" — 31 characters, 217 px at
 * Largest — so it is one line at both viewports at all three scales. The
 * 40-character ceiling in the test is that pixel budget written as an
 * assertion. The line this replaces was 69 characters and wrapped to two.
 *
 * ## The numbers moved on 2026-08-27, and the budget did not
 *
 * `RING_CURRENT_FORMATION.decayFraction` went from 0.26 to 1.50 so that one
 * cycle reads as a storm — a build and a LONGER recovery — instead of as a
 * symmetric throb with the asymmetry backwards. That multiplies every period
 * by 1.71 and nothing else, because the period is `fillSeconds * (1 + hold +
 * decay)` and only the second factor changed. Re-measured across the fixture
 * rather than scaled on paper: 5.73 s (30 keV, Kp 5.67) to 76.84 s (3 keV,
 * Kp 0.33), longest printed line 31 characters, which is the same 31 as before
 * because a wider number is offset by a narrower energy. The ceiling holds
 * with nine characters to spare even at a three-digit period.
 */
export function ringCurrentPulseLine(
  formation: Pick<RingCurrentFormation, "cycleSeconds"> | null,
  illustration: RingCurrentIllustration | null,
): string | null {
  if (!formation || !illustration || !(formation.cycleSeconds > 0)) return null;
  const seconds = ringCurrentPulsePeriodDisplaySeconds(formation);
  return `PULSE ${seconds.toFixed(1)} s`
    + ` · ${illustration.species.referenceEnergyKeV} keV AT Kp ${illustration.kp.toFixed(1)}`;
}

/**
 * The same fact for the layer's card, where there is room for the part the
 * legend cannot carry: that the loop contains no single lap time.
 *
 * With no formation — the flat-surface path, and every test that builds a spec
 * without a scene — it falls back to the replay rate alone, which is what this
 * clause said before the period was computable here at all.
 */
export function ringCurrentPulseReading(formation: RingCurrentFormation | null): string {
  const hoursPerSecond = RING_CURRENT_FORMATION.physicalSecondsPerDisplaySecond / 3600;
  const rate = `${hoursPerSecond} HOUR OF DRIFT PER SECOND OF SCREEN TIME`;
  if (!formation || !(formation.cycleSeconds > 0)) return rate;
  const seconds = ringCurrentPulsePeriodDisplaySeconds(formation);
  const laps = ringCurrentLapSpread(formation);
  return `${rate} · IT PULSES EVERY ${seconds.toFixed(1)} s, EXACTLY — ONE FILL AND FADE OF THE RING,`
    + ` ${(formation.cycleSeconds / 3600).toFixed(1)} h OF DRIFT, REPLAYED`
    // The SHAPE of that one cycle, which the repetition would otherwise
    // overwrite in a reader's head. It builds and then unwinds more slowly,
    // which is the one thing about a storm's Dst curve that is not in doubt;
    // the ratio is a display choice and no recovery time is claimed here or
    // anywhere else. See RING_CURRENT_FORMATION.decayFraction.
    + " · ONE CYCLE IS SHAPED LIKE A STORM: A BUILD, THEN A LONGER RECOVERY."
    + " THE REPEAT IS THE REPLAY RESTARTING, NOT A SECOND STORM"
    + ` · THAT IS THE LOOP'S PERIOD AND NOT A DRIFT LAP: THERE IS NO SINGLE LAP IN HERE, L ${laps.innerL.toFixed(1)}`
    + ` CLOSES IN ${laps.innerHours.toFixed(1)} h AND L ${laps.outerL.toFixed(1)} IN ${laps.outerHours.toFixed(1)} h`;
}

export function ringCurrentLegendSpec(
  illustration: RingCurrentIllustration | null,
  simulationState: PlasmasphereSimulationState = "not-published",
  storm: StormHeadline | null = null,
  substorm: SubstormState | null = null,
  // The loop the globe is actually drawing, when there is one. Passed in
  // rather than computed: `ringCurrentFormation` costs forty-odd RK4 traces
  // and this function is called several times a second, and a second copy of
  // it could quote a period the scene is not keeping.
  formation: RingCurrentFormation | null = null,
  // The age of the convection field this drift was traced in, when the frame
  // supplying it is the newest published one being read as the present. Passed
  // in rather than dug out of the illustration: the frame belongs to the
  // plasmasphere artifact, and this layer is a computation ON it.
  nowcast: DgcpmNowcast | null = null,
): EnvironmentLegendSpec {
  const scale = RING_CURRENT_ENERGY_SCALE;
  // These are properties of the trapped-particle physics, not of any frame, so
  // they are quoted in EVERY state including no-data. A card that goes blank
  // when the drive is missing teaches nothing; a card that keeps the invariants
  // and says which driven numbers are missing teaches the difference between
  // the two kinds of statement.
  const referenceEnergyKeV = (illustration?.species ?? DEFAULT_RING_CURRENT_ION).referenceEnergyKeV;
  const referenceL = (illustration?.species ?? DEFAULT_RING_CURRENT_ION).referenceL;
  const energyAtFour = energyAtLKeV(illustration?.species ?? DEFAULT_RING_CURRENT_ION, 4);
  const energyAtThree = energyAtLKeV(illustration?.species ?? DEFAULT_RING_CURRENT_ION, 3);
  const driftPeriodAtFour = magneticDriftPeriodHours(4, energyAtFour);
  const corotationRate = corotationAngularRateRadPerS();
  const magneticRateAtFour = Math.abs(magneticDriftAngularRateRadPerS(4, energyAtFour, 1));
  const dstNt = storm?.dstNt ?? null;

  // ONE row carries both halves of the claim, and it stays on the operational
  // card in every state.
  //
  // The card used to open with "WHAT IS MEASURED HERE: NOTHING · DST IS THE
  // ONLY RING-CURRENT MEASUREMENT THIS SITE CARRIES, AND DST HAS NO MAP". True,
  // and read by the site's owner as "this layer is not worth your time". The
  // fix is not to soften it — the provenance disclosure is not weakened by a
  // word — but to stop it standing alone. What IS measured comes first, with
  // its number, because Dst is this layer's own quantity and it is in the
  // banner at the top of the page; what is NOT measured is the SHAPE, and that
  // is a statement about the map rather than about the subject.
  //
  // The clock test allows exactly this row plus the driven ones on the card:
  // a caveat never moves to Data & methods however clock-invariant it is.
  const measured: { label: string; value: string } = {
    label: "WHAT IS MEASURED HERE",
    value: dstNt === null
      // CORRECTNESS FIX 2026-09-04: the tail of this row. The volume's spatial
      // profile was undeclared, in the layer whose own predecessor deleted
      // exactly this on principle — `ring-current-illustration.ts` still
      // carries the argument: "The opacity is FLAT, on purpose. Varying it with
      // anything — energy, distance, a notional density — would read as 'there
      // is more ring current here', and this site publishes no ring-current
      // density on a grid at all." The shipped volume varies it with both:
      // `RING_CURRENT_VOLUME_PROFILE` puts a Gaussian brightness maximum 40% of
      // the way from the inner edge to the Alfvén layer (`radialPeak` 0.40,
      // `radialCoreWidth` 0.34, over a `radialBaseFill` of 0.42) and scales
      // emission from 0.55 at the bottom of the energy ramp to 1.75 at the top,
      // a 3.2x gradient keyed on energy. Both are good drawing decisions,
      // documented in code; what was missing was the reader being told.
      //
      // It rides in THIS row — the one that already says what is not measured —
      // rather than a new one, because this card is the site's worst case for
      // height and the rule set out below is that an answer fitting inside an
      // existing row is the one that gets to stay. The long form is in the note.
      ? "DST — THE DEPRESSION THIS CURRENT PRODUCES AT THE GROUND, MEASURED HOURLY AND PLOTTED ON CURRENT CONDITIONS; NO STORM IS CLASSIFIED AT THE SELECTED TIME, SO THE BANNER CARRIES NO NUMBER · WHAT IS NOT MEASURED IS THE SHAPE — NOTHING PUBLISHES A GRIDDED RING CURRENT, SO THE MAP IS DERIVED FROM THE MODEL FIELD, NOT OBSERVED · NOR IS THE BRIGHTNESS: THE FILL PEAKS ABOUT 40% OF THE WAY OUT TO THE LAST CLOSED DRIFT PATH AND A HOT SAMPLE EMITS ABOUT 3.2× A COLD ONE, BOTH DRAWING CHOICES, NEITHER A COUNT"
      : `DST ${dstNt < 0 ? "−" : "+"}${Math.abs(dstNt).toFixed(0)} nT (${(storm?.dstSource ?? "Kyoto quicklook Dst").toUpperCase()}) — THAT DEPRESSION IS THIS CURRENT'S OWN FIELD AT THE GROUND, AND IT IS WHAT THE STORM BANNER GRADES THE STORM BY · WHAT IS NOT MEASURED IS THE SHAPE — NOTHING PUBLISHES A GRIDDED RING CURRENT, SO THE MAP IS DERIVED FROM THE MODEL FIELD, NOT OBSERVED · NOR IS THE BRIGHTNESS: THE FILL PEAKS ABOUT 40% OF THE WAY OUT TO THE LAST CLOSED DRIFT PATH AND A HOT SAMPLE EMITS ABOUT 3.2× A COLD ONE, BOTH DRAWING CHOICES, NEITHER A COUNT`,
  };

  // Standing physics: true at every instant of the published record, so it is
  // printed on this layer's Data & methods card rather than in the panel a
  // reader watches the clock in. Rendered from this same spec, so the figures
  // stay computed and still follow the ion selector.
  const standing: Array<{ label: string; value: string }> = [
    {
      label: "WHY THIS LAYER MATTERS",
      value: "A GEOMAGNETIC STORM ESSENTIALLY IS THIS POPULATION INTENSIFYING · THE WESTWARD CURRENT IT CARRIES IS WHAT DST MEASURES, AND DST IS THE NUMBER THE STORM IS GRADED BY",
    },
    {
      label: "DRIFT SENSE",
      value: "IONS WESTWARD · ELECTRONS EASTWARD · THEY ADD, AND THE NET CURRENT IS WESTWARD",
    },
    {
      label: "ENERGISATION BY INWARD TRANSPORT",
      value: `${referenceEnergyKeV} keV at L ${referenceL} → ${energyAtFour.toFixed(0)} keV at L 4 → ${energyAtThree.toFixed(0)} keV at L 3 (μ conserved, W ∝ L⁻³)`,
    },
    {
      label: "ION DRIFT PERIOD AT L 4",
      value: `${driftPeriodAtFour.toFixed(2)} h westward, against 24 h of eastward corotation`,
    },
    {
      label: "COROTATION vs GRADIENT DRIFT AT L 4",
      value: `${corotationRate.toExponential(2)} rad s⁻¹ east vs ${magneticRateAtFour.toExponential(2)} rad s⁻¹ west (${(magneticRateAtFour / corotationRate).toFixed(0)}×)`,
    },
    // WHERE THE IONS COME FROM, which is the question the layer never answered.
    //
    // Sean, on the shipped build: "why don't i see anything tied to it like I do
    // with the magnetosphere?" The ring current had no visible supply, so it read
    // as an orphan — a doughnut that simply exists. The inner plasma sheet is the
    // supply, it rides on this same toggle because they are one injection seen at
    // two radii, and these rows say what is measured about it and what is not.
    {
      label: "WHERE THESE IONS COME FROM",
      value: `THE INNER PLASMA SHEET, L ${INNER_EDGE_INJECTED_RE}–${OUTER_EDGE_RE}, DRAWN ON THIS SAME LAYER · ONE INJECTION, SEEN AT TWO RADII`,
    },
  ];

  // What the SUPPLY is doing at the selected instant. Every value here moves
  // with the clock, which is what keeps it off the standing list.
  //
  // EMPTY when there is no state, rather than two rows saying there is nothing
  // to say. The operational card's budget is the reason: it is 432 px, this
  // layer's card was the worst case on the site at 12 readings and 756 px, and
  // the rule that came out of that is that a row which cannot move with the
  // clock does not belong here. Two rows reading "not for this instant" are
  // exactly such rows, and a test pins that they are absent.
  const substormRows: Array<{ label: string; value: string }> = substorm === null ? [] : [
    {
      label: "THE SUPPLY, RIGHT NOW",
      value: `${substormPhaseLabel(substorm)} · tail loading ${(substorm.loading * 100).toFixed(0)}% from ${substorm.southwardBzNtMinutes === null ? "no measured Bz" : `${substorm.southwardBzNtMinutes.toFixed(0)} nT·min of southward Bz over the last 90 min`}${substorm.bzGsmNt === null ? "" : ` · Bz now ${substorm.bzGsmNt.toFixed(1)} nT`}`,
    },
    {
      // The honesty row. A substorm ONSET is a sharp drop in an auroral
      // electrojet index, and this site holds one for exactly one week in 2024.
      label: "CAN THE SITE TIME THE SNAP?",
      value: substorm.onsetEvidence === "observed-electrojet"
        ? `YES — onset from a measured auroral-electrojet index${substorm.minutesSinceOnset === null ? "" : `, ${substorm.minutesSinceOnset.toFixed(0)} min ago`}`
        : substorm.onsetEvidence === "ring-current-response"
          ? "NO — no auroral-electrojet index is published live to this site, so no onset time is claimed. What is drawn is the loading, from measured Bz, and the response, from measured Dst"
          : "NO — nothing measures it for this instant, so nothing snaps",
    },
  ];

  const driven: Array<{ label: string; value: string }> = illustration
    ? [
      {
        // The boundary is no longer annotated on the globe - the dashed curve
        // and its label came off on 2026-08-19, because that annotation does
        // not belong on the main site. This row is therefore the ONLY place
        // the number lives, so it carries the meaning as well as the value.
        label: "ALFVÉN LAYER AT MIDNIGHT",
        value: illustration.separatrix
          ? `L ${illustration.separatrix.lShell.toFixed(2)} — the last drift path that closes on itself. Inside it these ions circle the Earth and stay; outside it the convection field sweeps them out through the dayside.`
          : `NONE INSIDE L ${RING_CURRENT_SEEDS.innerL}–${RING_CURRENT_SEEDS.outerL} · at this Kp every drawn path encircles the Earth`,
      },
      {
        label: "AND ITS SHAPE",
        // `contourClippedAtDomain` is why this reads "at least" rather than a
        // flat number when it fires. The Alfven layer is bisected on the
        // MIDNIGHT meridian and the contour through it is widest at DAWN, so a
        // boundary that closes well inside the domain at midnight can still run
        // into the integrator's L 9 ceiling at dawn — and the widest-L readout
        // would then be quoting the edge of the integrator as if it were the
        // physics. Measured: it fires for the 10 keV ion at Kp 0 and the 30 keV
        // ion at Kp 0–3.
        value: `widest ${illustration.region.contourClippedAtDomain ? "at least " : ""}L ${illustration.region.widestL.toFixed(2)} at ${mltLabel(illustration.region.widestMltHours)}, pinched to L ${illustration.region.narrowestL.toFixed(2)} at ${mltLabel(illustration.region.narrowestMltHours)} — the OPPOSITE way round from the plasmapause's dusk bulge, because an ion this energetic beats corotation westward on the dawn side first${illustration.region.contourClippedAtDomain ? `. The dawn side runs into the traced domain edge at L ${illustration.region.domainL}, so that first number is a lower bound rather than the boundary's real reach` : ""}`,
      },
      {
        label: "SAME BOUNDARY AT ZERO ENERGY, ALSO AT MIDNIGHT",
        value: `L ${illustration.zeroEnergySeparatrixMidnightL.toFixed(2)} — cold plasma is trapped closest in; its teardrop noses out to L ${illustration.zeroEnergySeparatrixL.toFixed(2)} at dusk, which is the plasmapause the layer above draws`,
      },
      {
        label: "DEEPEST APPROACH ON AN OPEN PATH",
        value: illustration.deepestPenetration
          ? `L ${illustration.deepestPenetration.lShell.toFixed(2)} at ${illustration.deepestPenetration.mltHours.toFixed(1)} MLT, arriving at ${illustration.deepestPenetration.energyKeV.toFixed(0)} keV`
          : "—",
      },
      {
        label: "DRIFT PATHS DRAWN",
        value: `${illustration.closedCount} closed (trapped) · ${illustration.escapedCount} open (swept through)`
          + (illustration.stalledCount > 0 ? ` · ${illustration.stalledCount} stalled near a stagnation point` : ""),
      },
      {
        label: "DRIVING Kp",
        value: `${illustration.kp.toFixed(2)} → convection A = ${illustration.amplitudeVPerRe2.toFixed(0)} V Rₑ⁻², read off the plasmasphere frame`,
      },
      { label: "FRAME", value: utcMinuteLabel(illustration.validAt) },
      {
        // The pulse rides in THIS row rather than in a new one. It is what the
        // motion claims, and this card is the site's worst case for height —
        // 12 readings and 756 px in a 432 px window is the measurement the
        // clock test was written from — so an answer that fits inside a row
        // that was already here is the one that gets to stay.
        label: "WHAT THE MOTION CLAIMS",
        value: `THE POPULATION FILLING, NOT PARTICLES MARCHING · ${ringCurrentPulseReading(formation)} · NO COUNT, NO FLUX, NOTHING COUNTABLE IS DRAWN`,
      },
    ]
    : [
      { label: "SELECTED UTC", value: `${PLASMASPHERE_SIMULATION_STATUS[simulationState]} · NO CONVECTION FIELD TO DRIFT IN` },
    ];

  return {
    layer: "ringCurrent",
    title: "Plasma sheet → ring current",
    keyTitle: "Ring current · model-derived",
    // MODEL-DERIVED, not ILLUSTRATION, since 2026-08-19. Sean: "the ring
    // current is an illustration.... i thought you were going to make it
    // something that ISN'T a useless illustration but something REAL. why does
    // it still say it is an illustration?"
    //
    // He is right, and the badge had gone stale against its own layer.
    // ILLUSTRATION was the correct word for what this used to be: drift-path
    // LINES with sprites marching along them, a diagram drawn over the data.
    // That was deleted. What is drawn now is a ray-marched VOLUME whose region
    // is computed by RK4 integration in NOAA's published Volland-Stern
    // convection field, driven by published Kp, bounded by the computed
    // Alfvén layer, and coloured by `energyAtLKeV`. Every one of those is a
    // model quantity carried through arithmetic - which is the definition of
    // this site's `model` class, and the class the plasma sheet already
    // carries for exactly the same kind of thing (plasma β, computed from the
    // NOAA cuts rather than published as itself).
    //
    // The vocabulary was checked before the word was chosen: `LegendEvidence`
    // and EVIDENCE_MEANINGS already contain the class that means this, so no
    // new one was invented. EVIDENCE_MEANINGS.model reads "Simulation output.
    // No measurement fixes any individual value shown here", which is exactly
    // and only what this layer claims.
    //
    // WHAT THE CHANGE MAY NOT DO is weaken the second claim, and it does not:
    // the SHAPE is still not measured, no upstream publishes a gridded
    // ring-current product, Dst is the only ring-current measurement here and
    // one number has no map. That caveat is in the badge's own second half, in
    // the card's WHAT IS MEASURED HERE row in every state, and at length in
    // the note. Only the class changed.
    badge: "MODEL-DERIVED · SHAPE NOT MEASURED",
    evidence: "model",
    scale: {
      gradient: scale.gradient,
      minimum: scale.minimumLabel,
      label: scale.label,
      maximum: scale.maximumLabel,
    },
    // The substorm rows go HERE and not in `standing`, because they change
    // with the clock: `standing` is the layer's clock-invariant physics, and a
    // row whose value depends on the selected instant would make that list a
    // lie. A test pins the split.
    stats: [measured, ...driven, ...substormRows],
    standing,
    // CORRECTNESS FIX 2026-09-04: the long form of the brightness declaration.
    // See the WHAT THE BRIGHTNESS IS reading above for why it was owed.
    note: "WHAT THE BRIGHTNESS MEANS, BEFORE ANYTHING ELSE. Nothing publishes a gridded ring current, so no part of this "
      + "picture is a density. Two of its choices would read as one if they were not said out loud. The fill peaks about "
      + "40% of the way from the inner edge to the last closed drift path and sits on a flat base across the rest, which is "
      + "what makes the region read as a fat doughnut instead of the thin annulus an earlier version drew — it is not a "
      + "claim that there are more ions there. And a sample at the top of the energy ramp emits about 3.2 times the light of "
      + "one at the bottom, so the hot deep core is not averaged away by the ray march — that is a brightness correction on "
      + "the hue, not a second statement about how much is there. Hue means exactly what the colour bar says. "
      + "WHY THIS ONE MATTERS. During a storm the ring current is the most consequential thing on this rail, because a geomagnetic "
      + "storm essentially IS this population intensifying. Energetic ions trapped a few Earth radii out drift westward round the "
      + "planet in a current whose magnetic field opposes Earth's own at the surface, and the depression that produces is Dst — "
      + "measured hourly at four low-latitude magnetometers, carried in this site's storm banner, and the number the storm is graded "
      + "by. So this layer's quantity is measured, continuously, and it is the number you are already reading at the top of the page. "
      + "WHAT IS NOT MEASURED IS THE SHAPE. No upstream this site fetches publishes a ring-current ion flux on a grid, at any cadence, "
      + "for any time, and Dst is one number, which has no map. A torus drawn from Dst alone was deleted in August 2026 because its "
      + "radius, its width and its cross-section were all invented — a scalar says nothing about where. So the picture here is "
      + "MODEL-DERIVED: the region is integrated from NOAA's own published convection field at the measured Kp, and its colour is that "
      + "field's arithmetic, but it claims no flux, no density, no particle count and no observation of where the real ring current is "
      + "on any given day. It was badged ILLUSTRATION until 2026-08-19, and that word was right for what this used to be — drift-path "
      + "lines with sprites marching along them, a diagram over the data. Those were deleted. What is here now is a volume computed in "
      + "a published field, which is the same class of evidence as the plasma β on the magnetosphere layer. "
      + "WHAT IS ACTUALLY DRAWN: the drift motion of energetic ions that mirror at the magnetic equator, computed in the field this "
      + "release already publishes. Two drifts act on such a particle. E×B drift, identical for every species and energy — and it is "
      + "literally the same drift, in the same Volland–Stern convection plus corotation potential, at the same measured Kp, at the same "
      + "instant, that the DGCPM plasmasphere on the layer above is being eroded by; the amplitude A is read off that layer's own "
      + "published frame rather than recomputed, so the two pictures cannot disagree about the field they share. And "
      + "gradient/curvature drift, which for an equatorially mirroring particle in a dipole is purely azimuthal, proportional to the "
      + "particle's energy, and OPPOSITE IN SIGN FOR THE TWO CHARGES: ions go westward, electrons eastward. Opposite charges moving in "
      + "opposite directions do not cancel — they add — and the net westward current encircling Earth produces a field that opposes "
      + "Earth's own at the surface. That is why Dst is a measurement of this population's energy rather than a proxy for it. "
      + "COLOUR IS THE PARTICLE'S OWN KINETIC ENERGY at that distance, and it is arithmetic rather than a fitted "
      + "curve: the first adiabatic invariant μ = W/B is conserved by these slow drifts and B = B₀/L³, so a particle carried inward "
      + "gains energy as L⁻³. A 10 keV plasma-sheet ion that convects from L 8 to L 4 arrives as an 80 keV ring-current ion. That IS the "
      + "energisation, and it is why the deep core of the torus is drawn hot and its outer edge cool. "
      + "THE OUTER EDGE OF THE REGION IS THE ALFVÉN LAYER — the last drift path that closes on itself at this energy, quoted at "
      + "midnight in the readings above. Inside it a particle is trapped and stays, which is what makes a ring current; outside it a particle is swept in "
      + "from the tail, around the dusk side, and out through the dayside. Because the conserved quantity is qΦ + μB, that boundary "
      + "MOVES WITH ENERGY, and that is the teaching point: the balance between corotation and convection is energy-dependent, and it "
      + "is what sets which particles reach which L. At zero energy it collapses to the last closed equipotential, which is the "
      + "plasmapause the layer above draws — the two boundaries on screen are the same construction at two energies, and both are "
      + "quoted at midnight so that they can be compared. The ordering is the physical one: cold plasma is trapped closest in, and the "
      + "more energetic the particle the further out its drift path still closes, because a fast azimuthal drift carries it right round "
      + "the Earth before convection can carry it out. That is the same reason the radiation belts on the next layer extend past the "
      + "plasmapause. And the ASYMMETRY FLIPS between the two: the cold plasmapause bulges at dusk, while the ion boundary drawn here "
      + "comes out widest at DAWN and pinched at DUSK, because an ion of a few tens of keV drifts westward fast enough to beat "
      + "corotation on the dawn side first. It is pinched at dusk that lets tail plasma reach closest to Earth there, which is the "
      + "mechanism behind the observed dusk-favoured partial ring current (Liemohn et al. 2001, doi:10.1029/2000JA000326) — but nothing "
      + "in this release MEASURES that asymmetry, so read the dusk bias as the mechanism, never as an observation. "
      + "HOW THE FORMATION IS DRAWN, AND WHAT THAT MOTION CLAIMS. The layer is called \"how it forms\" and it now shows the forming. "
      + "Plasma-sheet parcels are seeded across the nightside outer boundary and each one is followed along its own computed drift path; "
      + "what advances across the screen outside the boundary is the field of ARRIVAL TIMES those paths trace out, not a particle and "
      + "not a marker. Inside the boundary the trapped population fills WESTWARD from the injection sector around midnight, each shell "
      + "at the lap time its own traced drift path takes, so the inner shells close into a full ring first and the outer ones lag — "
      + "which is what a real storm-time ring current does, being a lopsided partial ring before it is a symmetric one. Nothing "
      + "countable is drawn: there is no marker, no line, no sprite and no particle whose number could be read as a flux. "
      + "The loop runs at one hour of drift per second of screen time, so a strong storm visibly builds its ring faster than a quiet "
      + "field does, in the ratio the drift gives. Switching off Environmental motion in Display settings freezes it. "
      + "THE PULSE, AND WHETHER ITS PERIOD IS REAL. It is real and it is exact: the loop clock is a modulo, so the ring fills and "
      + "fades on an exactly repeating period, and the legend's colour bar breathes on that same clock rather than on an animation "
      + "of its own — which is why the two agree instead of merely looking as though they do. What that period is NOT is a drift "
      + "lap. There is no single lap in here: every shell has its own, and the spread between them is the energy dependence this "
      + "layer is drawn to show, so the number quoted is the whole loop's, with the ion and the Kp that set it beside it and the "
      + "spread of laps printed next to it. The REPETITION is a replay rather than a storm recurring. "
      + "TWO CLOCKS RUN ON THIS LAYER, and they are not the same one. The ring's pulse runs on the ANIMATION clock and keeps going "
      + "while you sit still. The dipolarisation front drawn in the plasma sheet beside it runs on the SELECTED TIME instead: it "
      + "moves only when you move the clock, it appears only in the few minutes after a MEASURED substorm onset, and it never "
      + "repeats. Its travel time is display shaping rather than a measured speed. "
      + "WHAT THE MOTION DOES NOT CLAIM: the supply is switched on across the whole nightside at once, whereas a real substorm "
      + "injection is a transient dipolarisation front; and in a STEADY field — which is what one published Kp gives — a particle "
      + "outside the Alfvén layer can never become trapped inside it, since that is precisely what \"last closed drift path\" means. "
      + "Real trapping happens because the field is not steady: convection surges, the boundary moves inward, plasma reaches deep, and "
      + "when convection relaxes the boundary expands back out and leaves that plasma behind it on closed paths. That relaxation is "
      + "not drawn, because drawing it would need a second Kp that no frame publishes. The fade at the end of each loop is a display "
      + "ramp back to a quiet-time residual, not a computed loss. "
      + "WHAT IS NOT MODELLED: no losses at all — charge exchange with the geocorona, Coulomb drag and wave scattering are what really "
      + "end a ring-current ion's life, so a drawn closed path overstates how long a real ion survives on it. No pitch-angle "
      + "distribution: every drawn particle mirrors at the equator. No self-consistency — these ions do not shield the convection field "
      + "they drift in and do not feed back into the plasmasphere run. And no species mix; the real ring current "
      + "carries a storm-dependent O⁺ fraction, which changes the mass but not the drift drawn here, since the drift depends on energy "
      + "and charge and not on mass. "
      + "The equatorial plane drawn is the GSM equator with a centred dipole, the same approximation the radiation-belt mapping and the "
      + "plasmasphere stipple already declare. Every radius goes through the scene's one shared radial ruler, so the illustration "
      + "follows the compressed teaching scale or true distance with the rest of the scene. The filling profile across the region — how "
      + "the population thins toward both edges and away from the equator — is a declared display choice, published on "
      + "RING_CURRENT_VOLUME_PROFILE, carrying no number a reader could misread as a density.",
    validAt: illustration?.validAt,
    source: illustration
      ? `Volland–Stern convection at measured planetary Kp (NOAA SWPC), read from this release's DGCPM plasmasphere frame; Dst from this release's storm indices`
      : "This release's DGCPM plasmasphere frames supply the convection field",
    statusText: illustration
      ? "MODEL · DRIFT COMPUTED IN THE PUBLISHED DGCPM CONVECTION FIELD · OBSERVED DST IS AN INDEX; THIS DISPLAY HAS NO OBSERVED SHAPE OR IN-SITU PARTICLE MAP"
      : `${PLASMASPHERE_SIMULATION_STATUS[simulationState]} · the drift paths are computed IN that simulation's electric field, so without a frame there is no field and nothing is drawn`,
    // A drawn ring current whose convection field is twenty minutes old is
    // honest when it says twenty minutes; the legend is where it says it,
    // because that is the surface a reader has in front of them without
    // opening anything.
    conditionLine: illustration && nowcast
      ? dgcpmNowcastLine(nowcast, "these drift paths are traced in the newest published frame")
      : undefined,
    // LOADING IS NOT NO-DATA, and calling it no-data moved the reader's clock.
    //
    // This layer fetches the DGCPM bundle on the toggle and reported "no-data"
    // for the second or two before it landed. `landOnCoverage` answers a
    // no-data layer by seeking the clock back into that layer's window and
    // HOLDING it there — Sean's "don't turn a layer on and have it not show
    // up" rule — and it skips a layer only while the layer says "loading".
    // So switching the ring current on at live now jumped the clock to a
    // minute inside the manifest's window (13:59 UTC on the release this was
    // measured against), paused it there, and the layer then drew a frame
    // chosen for 13:59 — which is not a nowcast, carries no age, and is one
    // minute BEFORE the newest published frame. Measured on the built bundle
    // with the page clock fixed: `#sim-label` read PAUSED and the key card
    // carried no age line at all, at both a live clock and a fixed one.
    //
    // "not-loaded" is exactly the in-flight state — the release publishes a
    // plasmasphere record and this session has not decoded it yet — so it is
    // the one that must say loading. "outside-window" means the frames are in
    // hand and genuinely do not reach the instant, which is a real no-data.
    statusState: illustration ? "ready" : simulationState === "not-loaded" ? "loading" : "no-data",
  };
}

/** `06 MLT (dawn)`. Named quadrants, because "6.0" is not a place. */
function mltLabel(hours: number): string {
  const rounded = ((hours % 24) + 24) % 24;
  const name = rounded < 3 || rounded >= 21
    ? "midnight"
    : rounded < 9
      ? "dawn"
      : rounded < 15
        ? "noon"
        : "dusk";
  return `${rounded.toFixed(0).padStart(2, "0")} MLT (${name})`;
}

/**
 * The first sentence of a satellite description, and everything after it.
 *
 * Descriptions open with the claim that matters — "Its purpose has not been
 * independently verified for this object" — and then explain the orbital
 * reasoning behind it. Showing the opening claim and folding the reasoning
 * keeps the disclosure in front of the reader while letting the numbers below
 * it come into view.
 *
 * A very short opening ("It is a GPS satellite.") carries too little on its
 * own, so sentences are taken until there is something worth reading.
 */
/**
 * Whether environmental motion starts on: the flow glyphs, the model-frame
 * advection and the plasmasphere's corotating grains.
 *
 * A visitor's own choice always wins, in both directions — that is what the
 * stored value IS, and a preference that overrode a deliberate click would be
 * a bug. With no stored choice, `prefers-reduced-motion: reduce` is honoured,
 * because a page that answers "reduce motion" with a screenful of streaming
 * particles has not answered it. The setting itself stays in Display settings
 * either way, so the visitor can turn it on and keep it.
 */
export function initialEnvironmentMotion(stored: boolean | undefined, prefersReducedMotion: boolean): boolean {
  if (typeof stored === "boolean") return stored;
  return !prefersReducedMotion;
}

/** `prefers-reduced-motion: reduce`, guarded for environments with no matchMedia. */
export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined"
    && typeof window.matchMedia === "function"
    && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function splitLeadSentence(text: string, minimumLeadLength = 60): { lead: string; rest: string } {
  const trimmed = text.trim();
  if (!trimmed) return { lead: "", rest: "" };
  const sentences = trimmed.split(/(?<=[.!?])\s+(?=[A-Z(])/);
  let taken = 0;
  let lead = "";
  while (taken < sentences.length && (lead.length < minimumLeadLength || taken === 0)) {
    lead = lead ? `${lead} ${sentences[taken]}` : sentences[taken]!;
    taken += 1;
  }
  return { lead, rest: sentences.slice(taken).join(" ") };
}

/**
 * Whether a layer's detail block starts open.
 *
 * A remembered choice always wins. With no remembered choice, detail is open
 * only when this is the single layer on screen: from the second layer onward
 * the column starts to crowd, which is the whole problem being solved here.
 */
/** The colour ramps of the four published BATS-R-US fields, matching FIELD_PALETTES in geospace-runtime.ts. */
export const GEOSPACE_FIELD_GRADIENTS: Record<GeospaceField, string> = {
  density: "linear-gradient(90deg, #1c3f66, #29d4e3, #f3ffff)",
  speed: "linear-gradient(90deg, #23486b, #76e6a5, #f5c96a)",
  magneticField: "linear-gradient(90deg, #2b2750, #a98cff, #5ce8f1)",
  pressure: "linear-gradient(90deg, #3a2b4d, #f5c96a, #ff7b78)",
};

const GEOSPACE_FIELD_SHORT_NAMES: Record<GeospaceField, string> = {
  density: "plasma density",
  speed: "plasma speed",
  pressure: "plasma pressure",
  magneticField: "field strength |B|",
};

export interface MagnetosphereFieldSpecInput {
  field: GeospaceField;
  fieldMetadata: GeospaceFieldLegendMetadata | null;
  structures: GeospaceStructureLegendMetadata | null;
  runtimeState: GeospaceRuntimeFrameState | null;
  loading: boolean;
  /** Whether the empirical Shue/Nguyen/Lin annotation overlay is switched on. */
  empiricalAnnotationOn: boolean;
  /**
   * Whether the extracted bow-shock and magnetopause-proxy curves are switched
   * on. They are drawn in flat colours over the field and had no colour-keyed
   * row of any kind until 2026-08-27; the bow shock's `#f5c96a` is one tick
   * from the cusp funnels' `#ffb257`, which is the confusion this layer has
   * already had once. Optional so older spec constructions mean "off".
   */
  extractedAnnotationOn?: boolean;
  /**
   * Which of the three empirical fits the boundary pass actually evaluated and
   * drew, read off the globe's own legend entries rather than assumed: without
   * a full IMF vector and a dipole tilt only Shue is drawable, and a swatch for
   * a surface that is not on screen is the defect this whole list exists to
   * fix, pointing the other way. Only consulted while `empiricalAnnotationOn`.
   */
  empiricalModelsDrawn?: readonly MagnetopauseModelId[];
  /** The live Shue subsolar standoff, for comparison against the model noses. */
  shueNoseRe: number | null;
  frameDescription: string | null;
  source?: string;
  coverage?: string;
  formatEndpoint: (value: number, scale: "linear" | "log10") => string;
  /**
   * Whether the embedded NOAA MHD cross-section is switched on. When it is,
   * the legend belongs to the cut's real plasma field; when it is not, the
   * layer's face is the driven 3-D field lines and the legend must describe
   * THAT, with its own quantity, instead of narrating an invisible plane.
   */
  mhdCutOn: boolean;
  /**
   * Set when the selected instant is past the end of the measured record.
   *
   * The card must then say the layer is off BECAUSE THERE IS NO FORECAST, not
   * that a frame is late. Those are different facts and only one of them ever
   * gets better. Nothing is drawn on the globe in either case — see the
   * standing note where the forecast band used to live in `globe.ts`.
   */
  noForecast?: MagnetopauseNoForecast | null;
  /** The traced field-line state; null while the live drivers are missing. */
  fieldLineSummary: FieldLineSummary | null;
  /**
   * Whether the two amber cusp funnels are in the scene right now.
   *
   * Read off the globe, never inferred from the drivers: `cuspedDrivers`
   * refuses without a dipole tilt, an IMF clock angle and a magnetic pressure,
   * and a legend row for a surface that is not drawn is exactly as wrong as
   * the drawn surface with no row that this whole field exists to fix.
   * Optional so older spec constructions mean "not drawn".
   */
  cuspFunnelsDrawn?: boolean;
  /**
   * The tracer's own per-rebuild integrity check. When it FAILED, the globe
   * drew nothing for this layer and the card must say why — the same refusal
   * grammar the boundary fit uses — instead of narrating lines that are not
   * there. Optional so older spec constructions mean "check passed".
   */
  fieldLineIntegrity?: FieldLineIntegrityReport | null;
}

/**
 * The legend and card spec for THE magnetosphere layer: the NOAA MHD plasma
 * field itself. The bow shock, the magnetosheath, the magnetopause and the
 * cusp region are structure IN this field's colours, so the layer's key card
 * must always carry a real colour ramp with units — in every state, including
 * loading and the archived replay frames that publish no field. A scale-less
 * card here would render as "SHAPE ONLY", the presentation this whole family
 * exists to retire; `tests/magnetosphere-field-legend.test.ts` fails if any
 * state loses the ramp.
 *
 * Pure and exported so the test exercises the exact function the interface
 * calls, per this project's rule that a guard must reach the real path.
 */
/**
 * ONE LAYER, ONE NAME. The card's title is the rail row's label, exactly.
 *
 * Both read "Magnetosphere" since 2026-08-27; the card said "Magnetosphere —
 * driven field & boundary" while the rail said "Magnetosphere", and they sit
 * on the same screen at the same time. Sean, on the rail wording: "instead of
 * 'fields and boundary' shouldn't it just say field lines? Because that is
 * what the default shows, right?" — and then "I think just Magnetosphere is
 * fine." All three boundary annotations ship unchecked, so a tick of that row
 * draws field lines and nothing else, and the suffix was promising a boundary
 * neither the row nor this card delivers by default. What the card is showing
 * is already said better below it: `keyTitle` names the quantity, the badge
 * names the evidence, and the stats carry the live standoff.
 *
 * The two titles that KEEP a suffix keep it deliberately, because in both the
 * suffix is a STATE the reader needs and not a description of the default
 * face: "Magnetosphere — not forecast" is the refusal past the driver record,
 * and "Magnetosphere — BATS-R-US <field>" names which published cut is on
 * screen when the MHD cross-section is switched on. Neither can be on screen
 * at the same time as the default face, so neither can disagree with the rail.
 */
export function magnetosphereFieldLegendSpec(input: MagnetosphereFieldSpecInput): EnvironmentLegendSpec {
  // The layer's default face: the driven 3-D field lines inside the live
  // empirical boundary. Its quantity is the |B| of the stated construction,
  // on the same palette as the BATS-R-US |B| cut, so SHAPE ONLY stays
  // unreachable in this mode too — the guard test drives both modes.
  if (!input.mhdCutOn) {
    const summary = input.fieldLineSummary;
    const [logLow, logHigh] = FIELD_LINE_DISPLAY_LOG_RANGE;
    const integrity = input.fieldLineIntegrity;
    if (integrity && !integrity.ok) {
      // The traced set failed its own consistency check, so the globe drew
      // NOTHING. Same refusal grammar as the boundary fit: a named reason, a
      // no-data state, and the quantity's ramp kept so the card never
      // degenerates to SHAPE ONLY.
      return {
        layer: "geospace",
        title: "Magnetosphere",
        keyTitle: "Magnetosphere · field lines |B|",
        badge: "TRACE CHECK FAILED",
        evidence: "empirical",
        scale: {
          gradient: GEOSPACE_FIELD_GRADIENTS.magneticField,
          minimum: input.formatEndpoint(logLow, "log10"),
          label: "nT · DRIVEN FIELD MODEL |B| ALONG THE TRACED LINES",
          maximum: input.formatEndpoint(logHigh, "log10"),
        },
        stats: [
          { label: "TRACE CHECK", value: (integrity.reason ?? "failed").toUpperCase().replaceAll("-", " ") },
          { label: "WORST SEGMENT VS FIELD", value: `${integrity.worstAlignmentDeg.toFixed(1)}°` },
        ],
        note: `${FIELD_LINE_METHOD.construction} ${FIELD_LINE_METHOD.not} `
          + "Before anything is drawn, every rebuilt trace is checked against its own field: segments must follow the model "
          + "field at their midpoints, endpoints must match their closed/open/boundary label, and no point may sit under the "
          + "Earth's surface or outside the truncation boundary. This trace failed that check.",
        source: "Propagated L1 solar wind · IGRF dipole · GSM",
        coverage: input.coverage,
        statusState: "no-data",
        statusText: "The traced field lines failed their own consistency check for this driver state, so NONE are drawn — "
          + "a refused trace beats impossible geometry. The check runs again on the next driver update.",
      };
    }
    const number = (value: number, digits: number, unit: string) =>
      Number.isFinite(value) ? `${value.toFixed(digits)}${unit}` : "—";
    const calibrated = summary?.boundarySource === "noaa-mhd-frame" && summary.calibration
      ? summary.calibration
      : null;

    // PAST THE LAST MEASUREMENT, AND THEREFORE OFF.
    //
    // This used to be the forecast band's card, and the band is gone. Sean, on
    // the shipped build: *"Its current and past depictions are great. But what
    // the fuck am I seeing in the future? ... If we can't get a forecasted
    // magnetosphere, just leave it off. Have it turn off and let the legend say
    // as much - no forecast."* A defensible forecast is not obtainable — the
    // measurements that settle that are in `magnetopause-forecast.ts` — so this
    // is the whole of what the future half of the clock now shows for this
    // layer: nothing on the globe, and words that say why.
    //
    // It carries its own `unavailable` notice rather than the shared coverage
    // one. "The next frame has not arrived yet" is true of a feed with a gap in
    // it and false here: no frame is coming, ever, because nobody forecasts
    // this quantity. It keeps the |B| ramp in `scale` so the card cannot
    // degenerate to SHAPE ONLY (`tests/magnetosphere-field-legend.test.ts`),
    // and the legend still strikes that bar out and prints `emptyLabel`.
    const noForecast = input.noForecast ?? null;
    if (!summary && noForecast) {
      const backTo = new Date(Math.max(
        Date.parse(noForecast.measured.fromIso),
        Date.parse(noForecast.measured.toIso) - 60_000,
      )).toISOString();
      return {
        layer: "geospace",
        title: "Magnetosphere — not forecast",
        keyTitle: "Magnetosphere · no forecast",
        badge: "NO FORECAST · LAYER OFF",
        evidence: "empirical",
        emptyLabel: "NO FORECAST · NOTHING DRAWN",
        scale: {
          gradient: GEOSPACE_FIELD_GRADIENTS.magneticField,
          minimum: input.formatEndpoint(logLow, "log10"),
          label: "nT · DRIVEN FIELD MODEL |B| ALONG THE TRACED LINES",
          maximum: input.formatEndpoint(logHigh, "log10"),
        },
        stats: [
          { label: "SELECTED UTC", value: "PAST THE LAST MEASUREMENT — THE LAYER IS OFF" },
          { label: "MEASUREMENTS RUN OUT AT", value: utcMinuteLabel(noForecast.measuredToIso) },
          {
            label: "WHAT IS NOT FORECAST, AND CANNOT BE",
            value: "IMF Bz. NOBODY PUBLISHES A FORECAST OF IT — AND IT IS MOST OF WHERE THE BOUNDARY SITS",
          },
          {
            label: "WHAT NOAA DOES FORECAST",
            value: noForecast.forecastKp === null
              ? "Kp — THE ACTIVITY, NOT THE BOUNDARY · PAST THE PUBLISHED THREE DAYS"
              : `Kp ${noForecast.forecastKp.toFixed(2)}${noForecast.forecastKpIsPredicted ? " · PREDICTED" : " · OBSERVED"} — THE ACTIVITY, NOT THE BOUNDARY`,
          },
        ],
        note: noForecastSentence(noForecast),
        source: "NOAA SWPC propagated L1 solar wind — the record it comes from, and where that record stops",
        coverage: input.coverage,
        statusState: "no-data",
        statusText: "NO FORECAST — the magnetosphere is not drawn past the last measurement. Scrub back for the measured one.",
        unavailable: {
          headline: "No magnetosphere here — it is not forecast.",
          because: "Nobody forecasts where the magnetopause will be. Its position is set almost entirely by the "
            + "north–south tilt of the magnetic field in the arriving solar wind, and that is only known once the wind "
            + "reaches the L1 spacecraft, under an hour upstream. So past the last measurement this layer draws nothing "
            + "rather than a guess. This is not a gap in a feed and it will not fill in.",
          jumpToIso: backTo,
          jumpLabel: `Go back to ${utcMinuteLabel(backTo)}`,
        },
      };
    }

    return {
      layer: "geospace",
      title: "Magnetosphere",
      keyTitle: "Magnetosphere · field lines |B|",
      badge: summary ? "SEMI-EMPIRICAL · DRIVEN" : "AWAITING LIVE DRIVERS",
      evidence: "empirical",
      // THE TWO AMBER FUNNELS, NAMED WHERE THE READER IS LOOKING.
      //
      // Sean, on the shipped build of 2026-08-26: "On the magnetosphere, we
      // still draw the bow shocks in orange, but we don't label that anywhere
      // on the page." He was right that nothing named them and wrong about
      // what they are, and the second half is the worse defect: these are the
      // POLAR CUSPS, and a bow shock is close to their opposite. A bow shock
      // stands about 13 R⊕ upstream and is where the solar wind is STOPPED;
      // the cusp is the one place on the dayside where it gets IN. Nothing in
      // this layer's default picture is a bow shock at all — the extraction
      // that produces one lives behind "Annotation: extracted boundary
      // curves" in this layer's own settings, and its own note says the
      // driven construction "contains no bow shock".
      //
      // If the owner read it that way a student certainly will, so the name
      // goes on the legend beside the picture and on the card, in the funnels'
      // own colour, and says what a cusp is rather than only what it is called.
      marks: magnetosphereMarks(input),
      scale: {
        gradient: GEOSPACE_FIELD_GRADIENTS.magneticField,
        minimum: input.formatEndpoint(logLow, "log10"),
        label: "nT · DRIVEN FIELD MODEL |B| ALONG THE TRACED LINES",
        maximum: input.formatEndpoint(logHigh, "log10"),
      },
      stats: summary ? [
        {
          label: "BOUNDARY",
          value: calibrated
            ? `NOAA MHD FRAME · FIT RMS ${calibrated.rmsResidualRe.toFixed(2)} R⊕`
            : "EMPIRICAL SHUE FROM L1",
        },
        { label: "STANDOFF", value: number(summary.standoffRe, 1, " R⊕") },
        { label: "DAYSIDE CLOSES AT", value: number(summary.closedNoseXRe, 1, " R⊕") },
        { label: "OPEN ABOVE (MIDNIGHT)", value: number(summary.firstOpenMidnightLatitudeDeg, 1, "°") },
        { label: "TAIL LOBE FIELD", value: number(summary.tailFieldNt, 0, " nT") },
      ] : [{ label: "SELECTED UTC", value: "NO PROPAGATED SOLAR-WIND DRIVERS" }],
      note: `${FIELD_LINE_METHOD.construction} ${FIELD_LINE_METHOD.not} `
        + (calibrated
          ? `Boundary calibrated to the NOAA MHD frame's extracted magnetopause (${calibrated.sampleCount} samples, fit RMS ${calibrated.rmsResidualRe.toFixed(2)} R⊕${calibrated.referenceRmsResidualRe !== null ? ` vs ${calibrated.referenceRmsResidualRe.toFixed(2)} R⊕ for the L1 Shue surface` : ""}). `
          : "Boundary from the empirical Shue fit driven by L1; it recalibrates to the NOAA MHD frame's own extracted magnetopause whenever a frame is loaded. ")
        // NAMED WHEN DRAWN, OFFERED WHEN NOT — and "not a bow shock" in both.
        // The correction is the reason the funnels were named at all, and a
        // reader who has them switched off is exactly the reader who has never
        // seen them and will meet them for the first time by ticking the box.
        + (input.cuspFunnelsDrawn
          ? "What each drawn element is: the coloured LINES are the driven field model, colour = |B|; the two amber FUNNELS are the "
            + "POLAR CUSPS — the exterior cusp, Nguyen 2022 over Lin 2010 — where the boundary-truncated lines converge. They are "
            + "NOT a bow shock: a bow shock stands about 13 R⊕ further out and is where the solar wind is stopped, while a cusp is "
            + "the one place on the dayside where it gets in. Nothing in this picture is a bow shock at all; the extracted bow-shock "
            + "curve is an off-by-default annotation in this layer's own settings. "
          : "What each drawn element is: the coloured LINES are the driven field model, colour = |B| — and that is the whole of the "
            + "default picture. The POLAR CUSPS, the two amber funnels where the boundary opens and solar-wind plasma gets in, are an "
            + "off-by-default annotation in this layer's own settings: tick \"Annotation: polar cusps\" beside the two boundary sets "
            + "and they are drawn, with a legend row of their own. They are NOT a bow shock — which is the reading they invited "
            + "while they were always on — because a bow shock stands about 13 R⊕ further out and is where the solar wind is "
            + "stopped, while a cusp is the one place on the dayside where it gets in. Nothing in this picture is a bow shock at all; "
            + "the extracted bow-shock curve is another off-by-default annotation in the same panel. ")
        + "The stretched two-lobe "
        + "TAIL is carried by the open lines themselves — no closed envelope is drawn, and the plasma sheet between the lobes is not "
        + "part of this construction: it has no place in a driven dipole-plus-Harris field, so it is a layer of its own, derived from "
        + "the NOAA pressure and |B| cuts as plasma β. Switch on \"Plasma sheet & tail lobes\" to see it inside these same lines. "
        + "With the solar-wind layer on, the amber shower is the wind, and "
        + "its guided fraction rides these exact lines into the cusps. "
        + "With the aurora layer on, the funnels land POLEWARD of the oval, not on it: the dayside cusp footprints sit near 77–80° "
        + "magnetic latitude while the main auroral oval runs about 65–75° and is brightest on the nightside — that separation is real geometry, not misregistration. "
        + "The real NOAA BATS-R-US plasma field is one click away in this layer's settings, embedded as a cross-section through this scene.",
      source: calibrated
        ? "NOAA SWMF/BATS-R-US magnetopause fit + propagated L1 solar wind · IGRF dipole · GSM"
        : "Propagated L1 solar wind · IGRF dipole · GSM",
      coverage: input.coverage,
      statusState: summary ? "ready" : "no-data",
      statusText: summary
        ? `Driven by the live standoff (${summary.standoffRe.toFixed(1)} R⊕, ${calibrated ? "MHD-calibrated" : "Shue from L1"}) and tail loading (${summary.tailFieldNt.toFixed(0)} nT); scrub the timeline to watch the storm deform it.`
        : "The propagated solar-wind drivers are missing for the selected time, so no field is drawn — nothing is frozen or invented.",
    };
  }
  const { field, fieldMetadata, structures, runtimeState, loading } = input;
  const noData = runtimeState?.status === "no-data";
  const ready = runtimeState?.status === "ready";
  const fieldDrawn = Boolean(fieldMetadata?.fieldPublished) && ready;
  const planeLabel = fieldMetadata
    ? fieldMetadata.plane === "meridional"
      ? "NOON–MIDNIGHT CUT"
      : fieldMetadata.plane === "equatorial" ? "EQUATORIAL CUT" : "BOTH CUTS"
    : "NOON–MIDNIGHT CUT";
  const scale: NonNullable<EnvironmentLegendSpec["scale"]> = fieldMetadata
    ? {
        gradient: GEOSPACE_FIELD_GRADIENTS[field],
        minimum: input.formatEndpoint(fieldMetadata.range.encodedMinimum, fieldMetadata.range.scale),
        label: `${fieldMetadata.range.units} · ${planeLabel}${fieldMetadata.displayMode === "native" ? " · NATIVE GRID" : ""}`,
        maximum: input.formatEndpoint(fieldMetadata.range.encodedMaximum, fieldMetadata.range.scale),
      }
    : {
        // Before the bundle arrives the ramp is shown with its endpoints
        // honestly unknown, never as a flat shape-only bar: the layer's
        // quantity exists whether or not it has loaded yet.
        gradient: GEOSPACE_FIELD_GRADIENTS[field],
        minimum: "…",
        label: loading ? "LOADING THE NOAA RANGE" : "RANGE LOADS WITH THE MODEL",
        maximum: "…",
      };
  const nose = (value: number | null | undefined) =>
    value === null || value === undefined ? "—" : `${value.toFixed(1)} R⊕`;
  const stats: Array<{ label: string; value: string }> = [];
  if (ready && fieldMetadata) {
    if (!fieldDrawn) {
      stats.push({ label: "FIELD", value: "NOT IN THIS ARCHIVED FRAME" });
    } else {
      stats.push(
        { label: "NATIVE VALID", value: fieldMetadata.validCount.toLocaleString() },
        { label: "NATIVE MISSING", value: fieldMetadata.missingCount.toLocaleString() },
      );
    }
    stats.push(
      { label: "BOW-SHOCK NOSE", value: nose(structures?.subsolarBowShockRe) },
      { label: "MAGNETOPAUSE NOSE", value: nose(structures?.subsolarMagnetopauseRe) },
    );
    if (input.empiricalAnnotationOn) {
      stats.push({ label: "SHUE NOSE (EMPIRICAL)", value: input.shueNoseRe === null ? "—" : `${input.shueNoseRe.toFixed(1)} R⊕` });
    }
  } else if (noData) {
    stats.push({ label: "SELECTED UTC", value: "OUTSIDE THE PUBLISHED WINDOW" });
  } else {
    stats.push({ label: "MODEL", value: loading ? "LOADING" : "LOADS THE 2.7 MB GEOSPACE BUNDLE ON FIRST USE" });
  }
  return {
    layer: "geospace",
    title: `Magnetosphere — BATS-R-US ${GEOSPACE_FIELD_SHORT_NAMES[field]}`,
    keyTitle: `Magnetosphere · ${GEOSPACE_FIELD_SHORT_NAMES[field]}`,
    badge: noData ? "NO DATA" : fieldMetadata ? "NOAA MODEL" : loading ? "LOADING" : "NOAA MODEL · ON DEMAND",
    evidence: "model",
    // The cut is a slice THROUGH the 3-D scene, not a replacement for it: the
    // field lines and anything annotated over them stay on screen behind it,
    // so this face owes exactly the same colour-key rows as the other one.
    marks: magnetosphereMarks(input),
    scale,
    stats,
    note: (fieldMetadata
      ? `${fieldMetadata.representation} ${fieldMetadata.range.endpointMeaning} `
      : "The NOAA operational BATS-R-US plasma field on its two published GSM cuts, loaded on demand; no synthetic volume is substituted. ")
      + "The bow shock, the magnetosheath, the magnetopause and the cusp region are structure in these colours — nothing is drawn on top of the field. "
      + "The shock appears as a steep ramp roughly half an Earth radius wide because that is the model grid's own resolution there; it is shown as published, not sharpened. "
      + "Masked cells are holes, never interpolation. The extracted and empirical boundary curves are off-by-default annotations in this layer's settings, for comparison against the field.",
    validAt: runtimeState?.status === "ready" ? runtimeState.structureFrameValidAt : undefined,
    source: input.source,
    coverage: input.coverage,
    statusText: noData
      ? `NO DATA FOR SELECTED UTC · ${input.frameDescription ?? "OUTSIDE THE PUBLISHED WINDOW"}. The field is HIDDEN; no stale frame is held.`
      : ready && !fieldDrawn
        ? "ARCHIVED REPLAY FRAME · The archive keeps the extracted boundary curves and streamlines but not the full field. Switch on the boundary annotations to follow the storm's compression here, or return to the live window for the field itself."
        : ready ? input.frameDescription ?? undefined : undefined,
    statusState: noData ? "no-data" : fieldMetadata ? "ready" : "loading",
  };
}

export interface PlasmaSheetSpecInput {
  metadata: PlasmaSheetLegendMetadata | null;
  runtimeState: GeospaceRuntimeFrameState | null;
  loading: boolean;
  frameDescription: string | null;
  source?: string;
  coverage?: string;
  formatEndpoint: (value: number, scale: "linear" | "log10") => string;
}

/**
 * The plasma-sheet layer's legend and card, as a pure function of what the
 * runtime measured.
 *
 * Two rules govern every branch below and both come from this project's
 * history. First, the ramp is present in EVERY state — before the bundle
 * loads, while it loads, on an archived frame that carries no plasma field,
 * and outside the published window — because a card with no `scale` renders as
 * the flat "SHAPE ONLY" bar, which is the presentation this whole family
 * exists to retire. Second, nothing here is allowed to imply a measurement
 * that was not made: every number is either measured from the frame on screen
 * or printed as an explicit refusal that names its reason.
 *
 * Exported and pure so the guard test drives the same function the interface
 * does, rather than a restatement of its reasoning.
 */
export function plasmaSheetLegendSpec(input: PlasmaSheetSpecInput): EnvironmentLegendSpec {
  const { metadata, runtimeState, loading } = input;
  const noData = runtimeState?.status === "no-data";
  const ready = runtimeState?.status === "ready";
  const [logLow, logHigh] = metadata?.logRange ?? PLASMA_SHEET_BETA_LOG_RANGE;
  const betaDrawn = Boolean(metadata?.betaPublished) && ready;
  const planeLabel = metadata
    ? metadata.plane === "meridional"
      ? "NOON–MIDNIGHT CUT"
      : metadata.plane === "equatorial" ? "EQUATORIAL CUT" : "BOTH CUTS"
    : "NOON–MIDNIGHT CUT";
  const scale: NonNullable<EnvironmentLegendSpec["scale"]> = {
    gradient: PLASMA_SHEET_GRADIENT_CSS,
    minimum: input.formatEndpoint(logLow, "log10"),
    // The units of beta are none — it is a ratio of two pressures — so the
    // label spends its space on the one number that matters instead: where
    // beta = 1 sits on the bar, because that pale band IS the sheet's edge.
    label: `PLASMA β (DIMENSIONLESS) · β = 1 AT THE PALE BAND · ${planeLabel}`
      + (metadata?.displayMode === "native" ? " · NATIVE GRID" : ""),
    maximum: input.formatEndpoint(logHigh, "log10"),
  };

  const metrics = betaDrawn ? metadata?.metrics ?? null : null;
  const stats: Array<{ label: string; value: string }> = [];
  if (ready && metadata) {
    if (!betaDrawn) {
      stats.push({ label: "PRESSURE & |B|", value: "NOT IN THIS ARCHIVED FRAME" });
    } else if (metrics && metrics.halfThicknessRe !== null) {
      stats.push({
        label: `HALF-THICKNESS AT X ${metrics.referenceXRe} R⊕`,
        value: `${metrics.halfThicknessRe.toFixed(2)} R⊕${metrics.referenceTruncated ? " · LOWER BOUND" : ""}`,
      });
      stats.push({
        label: "SHEET CENTRE THERE",
        value: metrics.centreCrossRe === null ? "—" : `Z ${metrics.centreCrossRe >= 0 ? "+" : ""}${metrics.centreCrossRe.toFixed(2)} R⊕`,
      });
      stats.push({
        label: "EQUATORIAL PLANE (Z = 0)",
        value: metrics.equatorialCutInsideSheet === null
          ? "—"
          : metrics.equatorialCutInsideSheet ? "INSIDE THE β ≥ 1 SHEET" : "IN THE LOBE, NOT THE SHEET",
      });
      stats.push({ label: "PEAK β IN THE TAIL WINDOW", value: metrics.peakBeta === null ? "—" : metrics.peakBeta.toFixed(1) });
      stats.push({
        label: "TAIL COLUMNS RESOLVING β ≥ 1",
        value: `${metrics.resolvedColumnCount} OF ${metrics.columnCount}`,
      });
      // The two rows above both say "tail window", so the window has to be a
      // number on the card. Without it they are statistics over an unstated
      // region, and the region is a choice this site made, not NOAA's.
      stats.push({
        label: "MEASURED TAIL WINDOW",
        value: `X ${metrics.window.minimumXRe} TO ${metrics.window.maximumXRe} R⊕ · |Z| ≤ ${metrics.window.maximumCrossRe} R⊕`,
      });
    } else {
      stats.push({
        label: "SHEET MEASUREMENT",
        value: metadata.metricsAvailable
          ? "NO β ≥ 1 COLUMN IN THE MEASURED TAIL WINDOW"
          : "NEEDS THE SMOOTHED DISPLAY GRID",
      });
    }
    if (betaDrawn && metadata.counts) {
      stats.push({ label: "β CELLS DRAWN", value: metadata.counts.valid.toLocaleString() });
      stats.push({ label: "β CELLS ABOVE 1", value: metadata.counts.aboveThreshold.toLocaleString() });
      // A cell whose pressure or |B| sat on its own encoding endpoint gives a
      // BOUND on beta, not a value. It is coloured — refusing to draw it would
      // punch holes through the inner magnetosphere — and it is counted here
      // so the card never lets that pass silently.
      stats.push({ label: "β BOUNDED BY A SOURCE LIMIT", value: metadata.counts.sourceBounded.toLocaleString() });
    }
  } else if (noData) {
    stats.push({ label: "SELECTED UTC", value: "OUTSIDE THE PUBLISHED WINDOW" });
  } else {
    stats.push({ label: "MODEL", value: loading ? "LOADING" : "DERIVED FROM THE GEOSPACE BUNDLE ON FIRST USE" });
  }

  return {
    layer: "plasmaSheet",
    title: "Plasma sheet — derived plasma β",
    keyTitle: "Plasma sheet · plasma β",
    badge: noData ? "NO DATA" : metadata?.betaPublished ? "MODEL-DERIVED" : loading ? "LOADING" : "MODEL-DERIVED · ON DEMAND",
    evidence: "model",
    scale,
    stats,
    // The representation and the limitation are imported constants, not
    // sentences retyped here: the runtime stamps the same two strings into the
    // layer's metadata, and the caveat is the part that must never drift.
    note: PLASMA_SHEET_REPRESENTATION
      + " Read it as a map of which pressure is in charge: the deep-blue LOBES above and below the tail are "
      + "magnetically dominated (β ≈ 10⁻³ — the field holds, and almost no plasma is there), and the hot band "
      + "between them is the PLASMA SHEET, where the particle pressure wins and the field is weak because it "
      + "reverses through it. That sheet is the reservoir the ring current and the aurora are fed from. "
      + "The pale β = 1 curve is drawn as the sheet's conventional edge, and the orange line down the tail is "
      + "the measured locus of maximum β — the sheet's own centre, which is NOT the z = 0 plane whenever the "
      + "dipole is tilted. "
      + PLASMA_SHEET_LIMITATION
      + " Watch it across the replay: the sheet thins as the tail loads and thickens again after it unloads.",
    validAt: metadata?.validAt ?? undefined,
    source: input.source,
    coverage: input.coverage,
    statusText: noData
      ? `NO DATA FOR SELECTED UTC · ${input.frameDescription ?? "OUTSIDE THE PUBLISHED WINDOW"}. Nothing is drawn; no stale frame is held.`
      : ready && !betaDrawn
        ? "ARCHIVED REPLAY FRAME · This frame keeps the extracted boundary curves but not the plasma field, so there is no pressure and no |B| to divide. Return to the live window for β."
        : ready ? input.frameDescription ?? undefined : undefined,
    statusState: noData ? "no-data" : metadata?.betaPublished ? "ready" : "loading",
  };
}

/**
 * What the key card's bar says for one layer spec: a real ramp with endpoints,
 * a struck-out no-data bar, or the flat "SHAPE ONLY" bar for a layer that
 * genuinely publishes no quantity (ground-station pins are categorical). The
 * magnetosphere family must never reach the third state — every layer in it
 * carries a quantity — and the guard test drives this exact function because
 * `renderKeyCard` delegates to it.
 */
export function keyCardBar(
  spec: Pick<EnvironmentLegendSpec, "scale" | "emptyLabel" | "composition">,
  unavailable: boolean,
): { kind: "no-data" | "ramp" | "shape-only" | "composition"; endpoints: [string, string, string] } {
  if (unavailable) return { kind: "no-data", endpoints: ["—", spec.emptyLabel ?? "NO DATA AT THIS TIME", "—"] };
  // A COMPOSITION draws no bar and no endpoint row: its rows are the legend.
  // This is not the flat "SHAPE ONLY" state and must never be confused with
  // it — that one means the layer publishes no quantity at all, and this layer
  // publishes three numbers and three energies. See `spec.composition`.
  if (spec.composition) return { kind: "composition", endpoints: ["—", "—", "—"] };
  if (spec.scale) return { kind: "ramp", endpoints: [spec.scale.minimum, spec.scale.label, spec.scale.maximum] };
  return { kind: "shape-only", endpoints: ["—", "SHAPE ONLY", "—"] };
}

/**
 * Whether a layer's SETTINGS section starts open. Never, unless this reader
 * has said otherwise for this layer.
 *
 * It used to open whenever the layer was the only one on screen, on the
 * reading that one layer cannot crowd anything. Measured on the built bundle,
 * that was wrong: the magnetosphere card ALONE carries thirteen controls — a
 * plasma-field picker, a cut-plane picker, field lines, flow lines and two
 * boundary annotations — and open they occupied 746 px, which is 3.9x the
 * 193 px of readings in the same card and more than the whole 432 px the panel
 * gets on a 900 px screen. A reader who switched on one layer was handed a
 * settings dialog with a reading attached.
 *
 * Settings are CONTROLS, not teaching, and a control is something a reader
 * goes looking for. They keep exactly one home — this layer's card, once —
 * where the summary line names them in one line and the caret on the layer's
 * own row opens them directly.
 */
export function layerDetailIsOpen(remembered: boolean | undefined): boolean {
  if (remembered !== undefined) return remembered;
  return false;
}

/**
 * Whether one layer's whole card opens expanded, or to its title row.
 *
 * EVERY card opens SHUT. Sean, given a screenshot of the panel with the
 * thermosphere on: "On the data explorer - I should only see a rectangle for
 * Thermosphere height and a box that says NOAA MODEL + FORECAST when I have
 * the thermosphere height plotted."
 *
 * This overrules the previous rule, which expanded the layer switched on most
 * recently and folded the others. That rule was written against a real
 * problem - cards all open cost 1,403 px at one layer, 2,423 px at two and
 * 2,773 px at three, in a 432 px window - and it solved it by making the
 * panel a sprawl and two stubs. Three layers on should be three tidy
 * rectangles of equal rank, because the reader is choosing between them.
 *
 * What makes shutting them safe is what was already true: the evidence badge
 * lives in the card's HEAD. Shut, the rectangle is the layer's name and the
 * class of claim it is making, and those are the two facts a reader needs
 * before they open anything. It is now the ONLY surface stating the evidence
 * class the moment a layer is drawn, the rail's chips having gone, so it is
 * also why the panel itself opens expanded rather than folded to its title.
 *
 * A card the reader has opened or shut by hand keeps that choice.
 */
export function layerCardIsOpen(remembered: boolean | undefined): boolean {
  return remembered ?? false;
}

/**
 * Every user-visible sentence that states which distance scale the globe is
 * drawn on, generated from the one active-scale value so no surface can lag
 * behind a toggle. The zoom-out tooltip is the oldest of these surfaces and
 * the one that would otherwise lie outright ("compressed scale") the moment
 * the visitor switched to true distance; the legend line is the always-current
 * statement; the LEO sentence is deliberate — on the true scale all of low
 * Earth orbit really does collapse into a film on the globe, and saying so is
 * the teaching point of offering the scale at all.
 */
export function distanceScaleStrings(scale: DistanceScaleId): {
  legend: string;
  zoomOutTitle: string;
  geometryNote: string;
  settingsNote: string;
  weatherNote: string;
  legendCompressed: string;
  /** The lead clause, shared by `legend`, `legendCompressed` and `teachingScaleLegend`. */
  legendLead: string;
  legendBoundary: string;
  legendTail: string;
} {
  if (scale === "true-distance") {
    return {
      legend: "True distance: drawn radius is proportional to real geocentric distance. The belts become wide donuts, and all of low Earth orbit collapses into a thin shell hugging the globe — that collapse is real, not an artifact.",
      legendCompressed: "True distance: drawn radius is proportional to real geocentric distance.",
      legendLead: "True distance: drawn radius is proportional to real geocentric distance",
      legendBoundary: "",
      legendTail: "",
      zoomOutTitle: "Zoom out — distances are drawn true to scale: drawn radius is proportional to real geocentric distance",
      geometryNote: "Earth hides the back side of the cyan orbit. The red trace follows the rotating Earth; radial distance is drawn true to scale.",
      settingsNote: "True distance draws every layer at its real geocentric distance on one shared ruler; low Earth orbit genuinely hugs the globe.",
      weatherNote: "The globe draws distances true to scale; values are physical.",
    };
  }
  // CORRECTNESS FIX 2026-09-04: these sentences had the SIGN of the near-Earth
  // distortion backwards, in the one line that is on screen for every layer.
  //
  // The teaching ruler's near-Earth branch is drawn = 1 + 0.28·ln(1 + alt/350)
  // in units of the drawn Earth radius (`radial-ruler.ts`). Its local log-log
  // slope near the surface is about 4, not below 1, so it MAGNIFIES altitude
  // from the ground up to a crossover at 4,795 km and only compresses above
  // that. Measured on `sharedDisplayRadius` as deployed, with the globe at 100
  // scene units, expressing the drawn height back as the altitude it would be
  // at the globe's own scale:
  //
  //      60 km -> 282 km (4.70x)      100 km -> 448 km (4.48x)
  //     300 km -> 1,104 km (3.68x)  1,000 km -> 2,408 km (2.41x)
  //   4,795 km -> 4,795 km (1.00x)     GEO   -> 8,272 km (0.23x)
  //
  // So "heights below GEO are compressed" was false across the whole 0-4,795 km
  // band — which is every ionospheric region this site teaches, the whole
  // thermosphere and all of low Earth orbit — and it was false in the direction
  // that matters: a reader told the D layer is drawn LOWER than it really sits
  // reads the picture the opposite way round from the truth. The stretch itself
  // is the reason the ionosphere is legible at all and is the owner's to keep;
  // stating its sign backwards is not a judgement call.
  //
  // The lead clause is now one string rather than three copies, so the
  // assembled variant in `teachingScaleLegend` cannot drift from it again.
  const teachingLead = "Teaching scale: near-Earth heights are stretched — a 100 km layer draws where 450 km "
    + "belongs — and distances past about 4,800 km are compressed";
  return {
    legend: `${teachingLead}; dayside boundary shape is true; the far tail is foreshortened.`,
    // Clause by clause, so the note can be assembled from what is actually
    // drawn. See `teachingScaleLegend`.
    legendCompressed: `${teachingLead}.`,
    legendLead: teachingLead,
    legendBoundary: "dayside boundary shape is true",
    legendTail: "the far tail is foreshortened",
    zoomOutTitle: "Zoom out — heights above Earth are not linear distance: near-Earth altitude is stretched about 4.5x, and past about 4,800 km it is a compressed scale",
    geometryNote: "Earth hides the back side of the cyan orbit. The red trace follows the rotating Earth; radial distance is stretched near Earth and compressed far out.",
    settingsNote: "Teaching scale stretches near-Earth heights so ionospheric structure stays visible and compresses everything past about 4,800 km; True distance shows real proportions.",
    weatherNote: "Altitudes are distorted in the globe — stretched near Earth, compressed far out; values are not.",
  };
}

/**
 * The scale note, assembled from what is actually on screen.
 *
 * It used to be one fixed sentence printed whenever the globe was drawn, so a
 * reader with only the TEC surface and the auroral oval switched on — two thin
 * shells a few hundred kilometres up — was told that "the far tail is
 * foreshortened". There is no tail in that picture. Sean's rule, and it is the
 * right one: what appears in the legend should correspond to what is turned on
 * and displayed.
 *
 * The compression clause always applies, because it is true of the globe
 * itself. The other two are claims about structures a long way out, and they
 * earn their place only when such a structure is drawn.
 */
export function teachingScaleLegend(
  scale: DistanceScaleId,
  activeLayers: Iterable<string>,
): string {
  const strings = distanceScaleStrings(scale);
  if (scale === "true-distance") return strings.legend;
  const active = new Set(activeLayers);
  // The layers that reach the dayside boundary and the tail at all. The
  // near-Earth surfaces — TEC, aurora, D-region, thermosphere, ground field —
  // are deliberately absent: none of them has a nose or a tail.
  const reachesBoundary = active.has("magnetosphere") || active.has("geospace") || active.has("solarWind");
  const reachesTail = active.has("magnetosphere") || active.has("geospace") || active.has("plasmaSheet");
  const clauses = [
    strings.legendBoundary && reachesBoundary ? strings.legendBoundary : "",
    strings.legendTail && reachesTail ? strings.legendTail : "",
  ].filter(Boolean);
  if (clauses.length === 0) return strings.legendCompressed;
  return `${strings.legendLead}; ${clauses.join("; ")}.`;
}

/**
 * WHAT THE DATA EXPLORER IS FOR.
 *
 * A reader with a layer switched on is asking three questions and no others:
 *
 *   1. WHAT AM I LOOKING AT — the layer's name and its evidence badge.
 *   2. WHAT IS THE NUMBER RIGHT NOW — the readings, below.
 *   3. HOW SURE IS IT — validity, coverage, source, evidence class.
 *
 * Everything else is a different job. The programme's three containers are the
 * RAIL (a field over the whole globe, capped at six), the PROBE (a number
 * about a place, asked for by clicking) and LEARN (how we know). The Data
 * Explorer is the rail's readout, and it had been quietly absorbing Learn:
 * measured on the built bundle with the three layers the owner had on —
 * magnetosphere, ring current, solar wind — it stacked 2,773 px of card into
 * the 432 px window it gets on a 900 px screen. Six and a half screenfuls of
 * its own panel, over the globe. Two blocks were 54% of that: the ring
 * current's twelve readings (756 px) and the magnetosphere's thirteen
 * settings, open (746 px).
 *
 * THE CLOCK TEST, which decides where a printed value lives: move the selected
 * time by an hour. If the value changes, it is a reading and it belongs here.
 * If it cannot change, it is standing physics and it belongs on Data &
 * methods, in `spec.standing`, where it is rendered from this same spec so the
 * numbers stay computed and checkable rather than frozen into prose.
 *
 * TWO THINGS OUTRANK THE CLOCK TEST, and both are about honesty rather than
 * space:
 *
 *   A CAVEAT NEVER LEAVES. "WHAT IS MEASURED HERE · NOTHING" on the ring
 *   current and "RBE model electrons only" on the belts never change with the
 *   clock, and they stay, because they are what stops a reader over-reading
 *   the picture beside them. A panel is not made simpler by moving the
 *   sentence that says what it does not know.
 *
 *   A SELECTED OBJECT'S RECORD NEVER LEAVES. The ground-station card's
 *   coordinate-precision tally is standing by the clock test and stays,
 *   because clicking a pin is a probe — a number about a place, asked for —
 *   and the tally is the reason the map may not be believed to the metre.
 *
 * How one layer's published facts then divide into the viewer's three
 * sections. Readings first and open, because they are what the reader came
 * for; then when the numbers are valid for; then where they came from.
 *
 * This is the rule the renderer calls, not a copy of it, so a test that
 * exercises this exercises what is on screen. That matters here: this codebase
 * has repeatedly shipped green tests over code no entry point reaches.
 *
 * A layer that publishes nothing for a section returns an empty list, and the
 * renderer hides that section rather than opening it onto an empty box.
 */
export function dataViewerSections(spec: EnvironmentLegendSpec): {
  readings: Array<[string, string]>;
  validity: Array<[string, string]>;
  provenance: Array<[string, string]>;
} {
  const readings: Array<[string, string]> = (spec.stats ?? []).map(({ label, value }) => [label, value]);
  // The scale endpoints are NOT repeated here. They used to be, on the reading
  // that the legend shows where a colour sits while this says what the range
  // is in words — but both surfaces are on screen together, so what the
  // visitor actually saw was `SCALE 1.6 to 53.9 / UNITS GloTEC vertical TEC ·
  // TECU` in the viewer and `1.6 … GloTEC vertical TEC · TECU … 53.9` in the
  // legend a few inches below. The legend owns the range; this owns the
  // layer's own readings. One value, one home.

  const validity: Array<[string, string]> = [];
  if (spec.validAt) validity.push(["Valid at", utcMinuteLabel(spec.validAt)]);
  if (spec.observedAt) validity.push(["Observed at", utcMinuteLabel(spec.observedAt)]);
  if (spec.coverage) validity.push(["Published coverage", spec.coverage]);
  if (spec.statusText) validity.push(["Status", spec.statusText]);

  const provenance: Array<[string, string]> = [];
  if (spec.source) provenance.push(["Source", spec.source]);
  provenance.push(["Evidence", spec.badge]);
  provenance.push(["How it is classified", EVIDENCE_MEANINGS[spec.evidence]]);
  return { readings, validity, provenance };
}

/**
 * The same layer's standing physics, for its card on Data & methods.
 *
 * The complement of `dataViewerSections().readings`, from the one spec, so a
 * value cannot be printed in both places and cannot fall out of both. The
 * renderer on the methods page calls this, and a test drives it against the
 * live specs to prove that every row the Data Explorer stopped printing is
 * still printed somewhere a reader can reach.
 */
export function standingReadings(spec: EnvironmentLegendSpec): Array<[string, string]> {
  return (spec.standing ?? []).map(({ label, value }) => [label, value]);
}

/**
 * What each evidence class actually claims. "MODEL" and "ASSIMILATED" are not
 * interchangeable, and a teaching site that shows one badge without saying so
 * is inviting a reader to treat a simulation as a measurement.
 */
const EVIDENCE_MEANINGS: Record<LegendEvidence, string> = EVIDENCE;

/** The tab title, and the mark that says a storm is running in it. */
const BASE_TITLE = "Space Environment Explorer";
const STORM_TITLE_MARK = "\u26a1";

/**
 * Where each layer's long-form derivation lives on the Data & methods page.
 *
 * The essays used to be printed inside the layer's own card on the operational
 * page, which is how one layer came to explain itself in the rail and over the
 * globe at once. They are the same prose either way; the difference is that a
 * reader now goes to them rather than scrolling past them to reach a number.
 * The ids are the `id:` fields on the method cards in `content.ts`.
 */
const LAYER_METHOD_CARD_IDS: Partial<Record<LayerName, string>> = {
  thermosphere: "method-thermosphere",
  ionosphere: "method-ionosphere",
  aurora: "method-aurora",
  geospace: "method-geospace",
  drap: "method-drap",
  tec: "method-tec",
  radiation: "method-radiation",
  solarWind: "method-solar-wind",
  photons: "method-xray",
  // These two had a method card on the page and no way to reach it from the
  // layer. The ring current's is the one that matters: it is the layer whose
  // standing physics moved off the Data Explorer card, so without this door
  // the move would be a deletion.
  ringCurrent: "method-ring-current",
  groundStations: "method-ground-stations",
};

/**
 * A clicked point in the form an officer writes it: degrees to one decimal
 * with a hemisphere letter, longitude folded to ±180 because -75.0° W is how a
 * chart is read and 285° is not.
 */
export function formatGeographicPoint(latitudeDeg: number, longitudeDeg: number): string {
  const folded = ((longitudeDeg % 360) + 540) % 360 - 180;
  const latitude = `${Math.abs(latitudeDeg).toFixed(1)}° ${latitudeDeg >= 0 ? "N" : "S"}`;
  const longitude = `${Math.abs(folded).toFixed(1)}° ${folded >= 0 ? "E" : "W"}`;
  return `${latitude}, ${longitude}`;
}

/**
 * The probe's density-against-altitude curve, drawn as an SVG polyline.
 *
 * Log density on the horizontal axis because the column spans four decades and
 * a linear axis would draw everything below the F2 peak as a single line on
 * the left edge. Levels the model does not publish BREAK the line rather than
 * being bridged: a gap in the source has to look like a gap, which is the same
 * rule the surfaces follow.
 */
export function profileChartGeometry(
  profile: Pick<SampledProfile, "levels">,
  width = 220,
  height = 240,
): { segments: string[]; peakY: number | null; densityRange: [number, number] } {
  const valid = profile.levels.filter((level) => level.electronDensityM3 !== null && level.electronDensityM3 > 0);
  if (valid.length < 2) return { segments: [], peakY: null, densityRange: [0, 0] };
  const exponents = valid.map((level) => Math.log10(level.electronDensityM3!));
  const altitudes = profile.levels.map((level) => level.altitudeKm);
  const minExponent = Math.floor(Math.min(...exponents));
  const maxExponent = Math.ceil(Math.max(...exponents));
  const minAltitude = Math.min(...altitudes);
  const maxAltitude = Math.max(...altitudes);
  const padding = 24;
  const x = (density: number) =>
    padding + ((Math.log10(density) - minExponent) / Math.max(1e-9, maxExponent - minExponent)) * (width - padding * 2);
  // Altitude increases upward, and SVG y increases downward.
  const y = (altitudeKm: number) =>
    height - padding - ((altitudeKm - minAltitude) / Math.max(1e-9, maxAltitude - minAltitude)) * (height - padding * 2);

  const segments: string[] = [];
  let current: string[] = [];
  for (const level of profile.levels) {
    if (level.electronDensityM3 === null || level.electronDensityM3 <= 0) {
      if (current.length > 1) segments.push(current.join(" "));
      current = [];
      continue;
    }
    current.push(`${x(level.electronDensityM3).toFixed(2)},${y(level.altitudeKm).toFixed(2)}`);
  }
  if (current.length > 1) segments.push(current.join(" "));
  const peak = valid.reduce((best, level) => (level.electronDensityM3! > best.electronDensityM3! ? level : best));
  return { segments, peakY: y(peak.altitudeKm), densityRange: [minExponent, maxExponent] };
}

/** Renders the profile geometry into the probe's SVG. */
function drawProfileChart(chart: SVGSVGElement & HTMLElement, profile: SampledProfile) {
  const svgNs = "http://www.w3.org/2000/svg";
  const { segments, peakY } = profileChartGeometry(profile);
  const nodes: SVGElement[] = segments.map((points) => {
    const line = document.createElementNS(svgNs, "polyline");
    line.setAttribute("points", points);
    line.setAttribute("class", "probe-curve");
    return line;
  });
  if (peakY !== null) {
    // The F2 peak, marked because it is the number the HF answer comes from.
    const marker = document.createElementNS(svgNs, "line");
    marker.setAttribute("x1", "18");
    marker.setAttribute("x2", "202");
    marker.setAttribute("y1", String(peakY));
    marker.setAttribute("y2", String(peakY));
    marker.setAttribute("class", "probe-peak");
    nodes.unshift(marker);
  }
  chart.replaceChildren(...nodes);
}

/**
 * Which of the three reading voices one value gets.
 *
 * A fact grid holds three different kinds of thing and used to set all of them
 * identically — 700 weight, 11.60 px, the brightest colour on the card — so a
 * forty-word explanation of the Alfven layer was typographically a measurement,
 * and shouted like one.
 *
 *   READOUT is a measurement: it carries a digit and it is short. Mono and
 *   tabular, which is what the type system reserves mono FOR.
 *
 *   ANSWER is a value that is a word — "Independent", "United States Space
 *   Force", "NORTH + SOUTH". Sans, same rank, because a name is not a number.
 *
 *   PROSE is a value that has become a sentence. The threshold is 44
 *   characters and it is measured rather than chosen: a fact cell is half of a
 *   grid that is about 350 px wide inside the panel, and at the reading size
 *   that half-column takes about 22 characters, so 44 is the point at which a
 *   value stops fitting on two lines of its own cell. Past it the value is set
 *   as prose and given the full width, which is both the honest voice for a
 *   sentence and fewer wrapped lines than half a column could give it.
 *
 * Deliberately mechanical and exported, so a test can drive the real rule
 * against the real values the cards print rather than a copy of it.
 */
export type FactValueVoice = "readout" | "answer" | "prose";
export const FACT_PROSE_CHARACTERS = 44;
export const FACT_HALF_COLUMN_CHARACTERS = 24;

export function factValueVoice(value: string): FactValueVoice {
  if (value.length > FACT_PROSE_CHARACTERS) return "prose";
  return /\d/.test(value) ? "readout" : "answer";
}

/**
 * Whether a value needs the whole grid row rather than half of it.
 *
 * Measured on the built bundle at the shipped interface scale: the fact grid
 * is two columns inside a panel about 350 px wide, so one column is roughly
 * 150 px, which takes about 15 characters of the 12.76 px monospace readout
 * and about 22 of the sans. "LEO · 951 km now · 103.9 min period" is 34 and
 * was wrapping to three lines in half the width it needed, directly under a
 * label that had wrapped to two. Past 24 characters a value gets the row.
 */
export function factValueSpansRow(value: string): boolean {
  return value.length > FACT_HALF_COLUMN_CHARACTERS;
}

/**
 * The few cells whose treatment is decided by the LABEL rather than the value.
 *
 * `factValueVoice` and `factValueSpansRow` both read the VALUE, which is right
 * for a grid whose values are measurements and names. It was wrong for exactly
 * one row, and wrong in a way a reader could see: the orbit class used to be
 * glued to the altitude and the period in one string, and the length of the
 * CLASS NAME then decided the colour of the two measurements beside it.
 * Measured on the shipped build, 2026-08-27:
 *
 *   LEO  `LEO · 416 km now · 92.9 min period`                     34 chars, CYAN
 *   HEO  `HEO · 38,987 km now · 717.9 min period`                 38 chars, CYAN
 *   MEO  `MEO · 20,743 km now · 718.0 min period`                 38 chars, CYAN
 *   GEO  `Other GSO / near-GEO · 35,699 km now · 1436.1 min ...`   56 chars, GREY
 *
 * Nothing about the GEO row was less certain or less measured. It crossed a
 * 44-character threshold, so `factValueVoice` called the whole thing a
 * sentence and set it as prose. Sean, holding the two cards side by side:
 * "look how odd this is... why was the MUOS satellite in grey as a sentence?"
 *
 * The row is three cells now, so each value is judged on its own and the two
 * measurements can never be dragged anywhere by the name beside them. The
 * class itself is pinned here rather than left to the classifier, for two
 * reasons. It is a CODE — LEO, MEO, HEO, and the GEO subtype — and codes are
 * what this card sets in mono already (the NORAD/COSPAR identity line, the
 * mission chip). And pinning it is what makes it the SAME for every
 * spacecraft, which is the whole defect: a value whose treatment depends on
 * how long its name happens to be is not a treatment, it is an accident.
 *
 * A HEDGED class is not marked by colour. "Other GSO" says in words that it
 * is the not-quite-geostationary case, and this site states uncertainty in
 * words or on a dashed evidence chip — never by dimming a value, which is the
 * accident being removed here.
 *
 * THE IDENTITY BLOCK IS PINNED FOR THE SAME REASON, in the same place, since
 * 2026-08-27. Sean, on the satellite card: "those three lines with the owner,
 * country, fleet — do those look okay? ... they all have grey labels above
 * them but they aren't the same font." They were not. `factValueVoice` sorts
 * by content and by a 44-character cliff, which is right for MEASUREMENTS —
 * a number should look like a number — and wrong for NAMES. On STARLINK-35128
 * "SpaceX", "United States" and "Starlink" all came out as answers; on
 * TIANMU-1 13 the operator is "Aerospace Tianmu (Chongqing) Satellite
 * Technology, a CASIC subsidiary", 68 characters, so the SAME KIND OF FACT was
 * set in grey 400-weight prose directly above two white 700-weight answers.
 * The reader was being told those three rows were three different sorts of
 * thing, and the only thing that differed was how long a company calls itself.
 *
 * So every identity label is pinned to `answer`: they are names, not readouts,
 * and a name is a name at six characters and at sixty-eight.
 *
 * NOTHING HERE TAKES THE WHOLE ROW, and that is the other half of the same
 * ruling. `Orbit type` used to be pinned `spansRow: true`, so a card always
 * carried one full-width row holding a three-letter value — Sean: "see how the
 * orbit and launch date are on separate rows?" — and on TIANMU-1 13 the length
 * rule promoted the operator, the country ("People's Republic of China", 26)
 * and the fleet ("No named fleet identified", 25) as well, which dragged the
 * launch date up with them through `factGridSpans` and left EVERY fixed fact
 * on a row of its own. The card's whole shape was decided by the length of one
 * string. Pinned cells now sit in a half column and wrap inside it, so the
 * grid is two columns on every spacecraft in the catalogue and `factGridSpans`
 * has one job left: the single lone cell an odd number of facts produces.
 */
export const FACT_CELL_OVERRIDES: ReadonlyMap<string, { voice: FactValueVoice; spansRow: boolean }> = new Map([
  ["Orbit type", { voice: "readout" as FactValueVoice, spansRow: false }],
  // WHO RUNS IT, WHERE IT IS REGISTERED, WHAT FLEET IT BELONGS TO. Names, all
  // of them, whatever their length; `ownershipRows` publishes the first two
  // under four different labels depending on what the registry and the curator
  // agree about, and all four are the same kind of fact.
  ["Owner / operator", { voice: "answer" as FactValueVoice, spansRow: false }],
  ["Operator's country", { voice: "answer" as FactValueVoice, spansRow: false }],
  ["Registering state", { voice: "answer" as FactValueVoice, spansRow: false }],
  ["Country / registry", { voice: "answer" as FactValueVoice, spansRow: false }],
  ["Constellation / fleet", { voice: "answer" as FactValueVoice, spansRow: false }],
  // WHEN IT WENT UP. Pinned to the word voice for the same reason the launch
  // date was moved up here in the first place: it is a property of the object,
  // not a reading that moves. Sean, seeing it in cyan mono beside a white
  // fleet name: "instead of the launch date in blue, we have it in white like
  // the fleet name." A date LOOKS like data to the length classifier, which is
  // why it needs pinning -- but nothing about this card re-measures it, and it
  // sits in the identity pair, not among the readings below.
  ["Launched", { voice: "answer" as FactValueVoice, spansRow: false }],
]);

/** One `.fact-grid` cell: the label above, the value below, as the satellite
 * card does it. Shared so both cards cannot drift apart.
 *
 * `forceRow` is the grid's own layout talking back: `factGridSpans` below
 * decides that a cell would otherwise be left staring at an empty half, and a
 * cell cannot see that from its own two strings. */
function factCell([label, value]: [string, string], forceRow = false): HTMLElement {
  const cell = document.createElement("div");
  const term = document.createElement("span");
  term.textContent = label;
  const fact = document.createElement("strong");
  fact.textContent = value;
  const override = FACT_CELL_OVERRIDES.get(label);
  const voice = override?.voice ?? factValueVoice(value);
  if (voice !== "answer") fact.classList.add(`is-${voice}`);
  // The cell, not just the value. A PIN BINDS IN BOTH DIRECTIONS: a pinned
  // cell's entry decides whether it takes the row, so the length rule cannot
  // promote it out of the two-column block on the one spacecraft whose
  // operator has a long name. `forceRow` is the grid's own layout talking
  // back and outranks both, because a lone cell has to be filled somehow.
  if (forceRow || override?.spansRow) cell.classList.add("spans-row");
  else if (!override && factValueSpansRow(value)) cell.classList.add("has-prose");
  cell.append(term, fact);
  return cell;
}

/**
 * WHICH CELLS TAKE THE WHOLE ROW, so that no fact is ever left beside a hole.
 *
 * Sean, on STARLINK-11600: "see how the grid of blue text values has sort of a
 * gap in it?" The gap was real and it was structural rather than a bad value.
 * `Orbit type` is pinned to the full row, a full-width cell has to begin one,
 * and the three ownership cells above it are an ODD number - so "Constellation
 * / fleet" sat alone in the left column with the right half of its row empty,
 * on every spacecraft in the catalogue.
 *
 * Ordering alone cannot fix that, because how many cells precede the orbit
 * class is not fixed: `ownershipRows` publishes one, two or three rows
 * depending on whether the operator, the registering state and the operator's
 * country are the same answer, "Also carries" appears only on a spacecraft
 * with a second job, and ANY value past 24 characters claims a row of its own
 * through `factValueSpansRow`. A hand-tuned order is correct for one card and
 * wrong for the next.
 *
 * So the rule is stated once, here, and it is one sentence: a cell that takes
 * the whole row pulls the cell before it to full width when that cell would
 * otherwise be alone. A full-width fact reads as deliberate - the grid does
 * this already for every value that has become a sentence - and an empty half
 * reads as a rendering fault, which is what Sean was looking at.
 *
 * Exported and free of the DOM so a test can drive the shipped rule over the
 * real rows rather than a copy of it.
 */
/**
 * The archive's state, written for a full-width box instead of a grid cell.
 *
 * The four states themselves do not change and are not softened - the count is
 * still never guessed, and `renderOrbitHistoryFact` still decides which of them
 * is true. Two things about a BOX change how they are said.
 *
 * The box already carries the words "Open orbit history", so a clause that
 * repeats them says history twice. And the box is one of three that must read
 * as a matched set, which means ONE LINE: measured on the built bundle,
 * 2026-08-27, the box is 281 px wide at 1440 and the interface scale does not
 * shrink the type, so a label wider than about 240 px wraps to a second line
 * and stands half a box taller than the two below it. "Open orbit history —
 * 1,284 element sets on file →" is 257 px and wrapped; "Open orbit history —
 * 1,284 element sets →" is 233 px and does not. (The phone is roomier at
 * 335 px, so the desktop is what sets the budget.)
 *
 *   History not loaded    ""                          nothing is claimed,
 *                                                     because nothing is known
 *                                                     until a reader pays for
 *                                                     the shard
 *   Archive server offline " — server offline"        the machine holding it
 *                                                     did not answer
 *   History unavailable   " — could not be read"      asked for, and failed
 *   No stored elements    " — no stored elements"     held, and empty
 *   1,284 element sets…   " — 1,284 element sets"     held, and counted
 *
 * The offline clause is SHORTER than its state on purpose, and for the same
 * width reason as the others: "Open orbit history — archive server offline" is
 * past the ~240 px the box has, "Open orbit history — server offline" is not.
 * The full state still goes in the `aria-label`, where length is free.
 *
 * The empty clause is the honest one for the ordinary case: the site has not
 * looked, so it says nothing about what is in there rather than a phrase a
 * reader would have to decode. The state is still named in full on the
 * button's `aria-label`, which is where it can be said at any length without
 * competing with the action.
 */
export function orbitHistoryActionClause(state: string): string {
  if (state === "History not loaded") return "";
  if (state === ARCHIVE_OFFLINE_STATE) return " — server offline";
  if (state === "History unavailable") return " — could not be read";
  if (state === "No stored elements") return " — no stored elements";
  // The count, without the "on file" that pushed the line over the width above.
  // The number itself is never touched.
  return ` — ${state.replace(/ on file$/, "")}`;
}

export function factGridSpans(rows: readonly (readonly [string, string])[]): boolean[] {
  const spans = rows.map(([label, value]) => {
    const override = FACT_CELL_OVERRIDES.get(label);
    return override ? override.spansRow : factValueSpansRow(value);
  });
  let column = 0;
  for (let index = 0; index < spans.length; index += 1) {
    if (spans[index]) {
      if (column === 1) spans[index - 1] = true;
      column = 0;
      continue;
    }
    column = column === 0 ? 1 : 0;
  }
  // A lone last cell has nothing to pair with either.
  if (column === 1) spans[spans.length - 1] = true;
  return spans;
}

/**
 * A published percentage of the Earth's cells, as a reading.
 *
 * `none` rather than `0.0%` when there is nothing: a zero in a column of
 * percentages reads as a measurement that came out small, and "none of the
 * globe reaches 1 dB at 10 MHz" is the fact. Two decimal places are published;
 * one is kept at the bottom, where the difference between 0.1 and 4.4 is the
 * whole of what is being said, and none at the top, where it is noise.
 */
export function percentOfGlobe(percent: number): string {
  if (!Number.isFinite(percent)) return "—";
  if (percent <= 0) return "none of the globe";
  return `${percent >= 10 ? percent.toFixed(0) : percent.toFixed(1)}% of the globe`;
}

/** `2026-08-06 22:43 UTC`, or an honest admission that the stamp is unusable. */
export function utcMinuteLabel(value: number | string): string {
  const parsed = typeof value === "number" ? value : Date.parse(value);
  if (!Number.isFinite(parsed)) return "an unknown time";
  return `${new Date(parsed).toISOString().slice(0, 16).replace("T", " ")} UTC`;
}

/**
 * The single, plain-language notice shown when a layer has nothing published
 * for the selected time — what is missing, why, and where to go instead.
 *
 * The time slider spans -48 h to +72 h because orbits are computable across
 * all of it. Every measured or modelled field has its own, much narrower,
 * published window; the coupled geospace run covers under two hours while
 * WAM-IPE covers two days back and more than a day forward. Outside a layer's
 * window the site refuses to draw anything, which is correct. This is the
 * sentence that says so once, instead of five stacked boxes of jargon.
 */
export function layerCoverageNotice(options: {
  title: string;
  selectedAtIso: string;
  window: { validFrom: string; validTo: string; sourceLabel: string } | null;
}): LayerUnavailableNotice {
  const subject = options.title.toLowerCase();
  const selectedLabel = utcMinuteLabel(options.selectedAtIso);
  const headline = `No ${subject} for ${selectedLabel}.`;
  if (!options.window) {
    return {
      headline,
      because: "Nothing was published for the time you picked, and this layer will not stand a neighbouring frame in for the one you asked for.",
    };
  }
  const from = Date.parse(options.window.validFrom);
  const to = Date.parse(options.window.validTo);
  const selected = Date.parse(options.selectedAtIso);
  if (!Number.isFinite(from) || !Number.isFinite(to) || !Number.isFinite(selected)) {
    return { headline, because: `${options.window.sourceLabel} does not cover the time you picked.` };
  }
  const beforeStart = selected < from;
  const edge = beforeStart ? from : to;
  // Land a minute inside the window rather than exactly on its boundary: the
  // edge frame is the one most likely to fall out of coverage again as the
  // clock ticks or the next release trims the history.
  const landing = beforeStart ? Math.min(edge + 60_000, to) : Math.max(edge - 60_000, from);
  return {
    headline,
    // Two different situations, and only one of them is anybody's fault.
    //
    // Scrolled PAST the end of coverage is the ordinary case, and the honest
    // words for it are that the record stops and the next frame is not here
    // yet. Every sourceLabel is a noun phrase naming a RECORD — "The GOES
    // X-ray record in this release", "NOAA's published OVATION history" — so
    // the verb has to belong to a record. An earlier draft read "NOAA's
    // published OVATION history has not published past 13:59 UTC", which used
    // the same verb twice and made a record the thing doing the publishing.
    // Measured
    // on 2026-08-19: NOAA's OVATION product had published nothing for 2.09
    // hours, and our newest frame was identical to theirs. A reader who sees
    // an empty layer and no reason concludes the site is broken; the reason is
    // what turns it into a true fact about how operational feeds behave.
    //
    // Scrolled BEFORE the start is a different thing — the archive simply does
    // not go back that far — so it does not claim anyone is late.
    because: beforeStart
      ? `${options.window.sourceLabel} only goes back to ${utcMinuteLabel(edge)}, so there is nothing published for the time you picked. Rather than draw a nearby frame and call it this one, the layer is left off.`
      : `${options.window.sourceLabel} stops at ${utcMinuteLabel(edge)}; the next frame has not arrived yet. Rather than draw the last one and call it now, the layer is left off.`,
    jumpToIso: new Date(landing).toISOString(),
    jumpLabel: `Go to ${utcMinuteLabel(landing)}`,
  };
}

/**
 * WHY THE RING CURRENT IS OFF, in the terms of the artifact it actually rides.
 *
 * The generic `layerCoverageNotice` above composes a true sentence out of a
 * validity window, and for a feed that simply stops it is the right sentence.
 * It is the wrong one here for two reasons that both bit on the live site.
 *
 * It cannot tell a reader who has SCRUBBED INTO THE FUTURE from a feed that is
 * LATE. Those are opposite facts — nobody publishes a forecast of the
 * plasmasphere at all, versus the next frame is overdue — and answering both
 * with "the next frame has not arrived yet" teaches the reader that a product
 * exists and we are waiting for it.
 *
 * And it has no idea the newest frame is HELD for a publishing cycle past
 * itself, so it named a boundary the layer does not actually refuse at.
 *
 * Returns null when the frames do cover the instant, so a caller can fall
 * through to whatever else it was going to say.
 */
export function dgcpmCoverageNotice(options: {
  title: string;
  selectedAtMs: number;
  nowMs: number;
  frameTimesMs: readonly number[];
  cadenceMinutes: number;
}): LayerUnavailableNotice | null {
  const { selectedAtMs, nowMs, cadenceMinutes } = options;
  const times = options.frameTimesMs;
  if (times.length === 0 || !Number.isFinite(selectedAtMs)) return null;
  const first = times[0]!;
  const newest = times[times.length - 1]!;
  const holdMs = cadenceMinutes * 60_000 * DGCPM_NOWCAST_HOLD_CADENCES;
  // The last instant this layer will answer for: one publishing cycle past the
  // newest frame. See `DGCPM_NOWCAST_HOLD_CADENCES`.
  const drawableTo = newest + holdMs;
  const headline = `No ${options.title.toLowerCase()} for ${utcMinuteLabel(selectedAtMs)}.`;
  // The two ways an instant IS covered, mirroring `dgcpmFieldAt` exactly: a
  // published frame within half a cadence of it, or the newest frame held as
  // the present. Answering here rather than trusting the caller keeps this
  // sentence from claiming a refusal that did not happen.
  const halfCadenceMs = (cadenceMinutes * 60_000) / 2;
  let nearestMs = first;
  for (const time of times) {
    if (Math.abs(time - selectedAtMs) < Math.abs(nearestMs - selectedAtMs)) nearestMs = time;
  }
  const scrubbedForward = selectedAtMs > nowMs + DGCPM_NOWCAST_CLOCK_SLACK_MINUTES * 60_000;
  const heldAsNowcast = !scrubbedForward && selectedAtMs > newest && selectedAtMs - newest <= holdMs;
  if (Math.abs(nearestMs - selectedAtMs) <= halfCadenceMs || heldAsNowcast) return null;
  const cadenceWords = cadenceMinutes % 60 === 0
    ? `${cadenceMinutes / 60}-hour`
    : `${cadenceMinutes}-minute`;
  // Land a minute inside the drawable edge, never on it, for the same reason
  // `layerCoverageNotice` does: a clock still running at real time would walk
  // straight back out of a landing made exactly on the boundary.
  const landing = (ms: number) => ({
    jumpToIso: new Date(Math.round(ms)).toISOString(),
    jumpLabel: `Go to ${utcMinuteLabel(Math.round(ms))}`,
  });
  const apart = (fromMs: number, toMs: number) => describeFrameAge(Math.round((toMs - fromMs) / 60_000)).replace(/ old$/, "");

  if (selectedAtMs < first) {
    return {
      headline,
      because: `The plasmasphere simulation that supplies the convection field only goes back to ${utcMinuteLabel(first)} in this release, `
        + "so there is nothing published for the time you picked. Rather than draw a nearby frame and call it this one, the layer is left off.",
      ...landing(Math.min(first + 60_000, drawableTo - 60_000)),
    };
  }
  if (scrubbedForward) {
    return {
      headline,
      because: `The clock is ${apart(nowMs, selectedAtMs)} ahead of now, and nobody publishes a forecast of the plasmasphere: `
        + "the simulation is driven by measured planetary Kp and stops where the measurements stop. So there is no convection field "
        + `for a future time and none is invented. The newest published frame is ${utcMinuteLabel(newest)}, and it is drawn as the present, not as tomorrow.`,
      ...landing(Math.min(nowMs, drawableTo - 60_000)),
    };
  }
  if (selectedAtMs > drawableTo) {
    return {
      headline,
      because: `The newest published plasmasphere frame is ${utcMinuteLabel(newest)}, ${apart(newest, selectedAtMs)} before the time you picked. `
        + `The newest frame IS drawn as the present — for one publishing cycle after itself, and these are ${cadenceWords} frames — but past that `
        + "its replacement is overdue, and holding a picture that old under a heading about now would be presenting stale output as the present.",
      ...landing(drawableTo - 60_000),
    };
  }
  // Inside the published span, and still nothing near enough: a real hole in
  // the record. Never papered over — a neighbouring frame stretched across a
  // gap is a picture of no particular time.
  return {
    headline,
    because: `This release has a hole in its plasmasphere frames there: the nearest published one is ${utcMinuteLabel(nearestMs)}, `
      + `more than half a ${cadenceWords} publishing cycle away. Rather than stretch a neighbouring frame across a gap, the layer is left off.`,
    ...landing(nearestMs),
  };
}

/**
 * Where the clock lands when a layer is switched on with nothing to draw.
 *
 * Sean's rule has two halves: "I just don't want people to turn on a layer and
 * not have it show up. If they scroll into the present just put a message on
 * then that says NOAA hasn't published yet." `layerCoverageNotice` above is
 * the message half. This is the other one — switching a layer on at a moment
 * its feed has not reached moves the clock back to that layer's newest
 * published frame, instead of leaving an empty globe and a button the reader
 * has to notice.
 *
 * Three rules, and each is here because of a way this goes wrong.
 *
 * BACKWARD ONLY. Every feed on this site has history; it is the PRESENT that
 * has the holes. Measured 2026-08-19: NOAA's OVATION product had published
 * nothing for 2.09 hours and our newest frame was identical to theirs. A past
 * frame leaves every other switched-on layer something real to draw, and there
 * is nothing published in the future to land on in the first place.
 *
 * THE EARLIEST CANDIDATE WINS, not the nearest. Two layers short of coverage
 * at two different times is the ordinary case — aurora stops at 13:59 while
 * the ring current stops somewhere else — and taking the nearest landing
 * satisfies one of them, leaves the other empty, and invites this same rule to
 * fire again: a clock that walks backwards in steps under the reader. The
 * earliest candidate is a fixed point by construction, because no active layer
 * can then ask to go earlier still. The clock lands once and stops.
 *
 * A CANDIDATE THE READER OVERTOOK IS DROPPED. Each candidate carries the
 * reader's clock-action count from the moment its layer was switched on. The
 * layer's artifact arrives some time later — measured on the built bundle, the
 * aurora key card still showed its 0-100% ramp at +0 ms and only flipped to
 * NO DATA at +150 ms — and if the reader moved the clock inside that gap, the
 * jump would take time away from somebody who had just chosen a moment. That
 * reader gets the message instead, which is what the message is for.
 */
export function coverageLandingTarget<T extends { jumpToIso?: string; armedAtActionCount: number }>(options: {
  selectedAtMs: number;
  readerActionCount: number;
  candidates: readonly T[];
}): T | null {
  let best: T | null = null;
  let bestMs = Number.POSITIVE_INFINITY;
  for (const candidate of options.candidates) {
    if (candidate.armedAtActionCount !== options.readerActionCount) continue;
    const at = candidate.jumpToIso === undefined ? Number.NaN : Date.parse(candidate.jumpToIso);
    if (!Number.isFinite(at) || at >= options.selectedAtMs) continue;
    if (at < bestMs) {
      bestMs = at;
      best = candidate;
    }
  }
  return best;
}

/**
 * What the key card says once the clock has been moved for a layer.
 *
 * Moving it silently would be its own confusion: a reader who was looking at
 * "now" would find themselves two hours earlier with nothing on screen saying
 * why, and the honest reading of that is that the site jumped. So the card
 * says where the clock went, whose publishing stopped, and how to get back.
 *
 * It says HOLDING because the clock really is held. `layerCoverageNotice`
 * lands a minute inside the window on purpose, so a clock still running at
 * real time would carry the reader back out of coverage about sixty seconds
 * later and the layer they had just switched on would vanish again — which is
 * the defect this whole path exists to remove.
 */
export function coverageLandingNotice(options: { landedAtIso: string; sourceLabel: string }): string {
  // Source labels are written to open a sentence — "The coupled NOAA geospace
  // run", "This release's DGCPM plasmasphere frames…" — so one goes in mid
  // sentence with its first word lowered. Making it the SUBJECT instead read
  // as "…frames, which supply the convection field has nothing newer", which
  // is what the browser actually printed before this: a plural subject with a
  // singular verb, because the labels are phrases of any shape and this
  // sentence cannot know which. "There is nothing newer in …" takes them all.
  const source = options.sourceLabel.replace(/^(The|This) /, (word) => word.toLowerCase());
  return `The clock moved back to ${utcMinuteLabel(options.landedAtIso)} and is holding there, so this layer has a published frame to draw. `
    + `There is nothing newer in ${source}. Use "Return to now" for the present, where this layer has nothing to draw yet.`;
}

const missionLabels: Record<string, string> = {
  weather: "METOC / weather",
  milsatcom: "MILSATCOM",
  "commercial-satcom": "Commercial SATCOM",
  communications: "Civil / other SATCOM",
  "missile-warning": "OPIR / missile warning",
  "military-other": "Other military",
  "signals-intelligence": "Signals intelligence",
  navigation: "Navigation / timing",
  "earth-observation": "Earth observation",
  science: "Science",
  "human-spaceflight": "Human spaceflight",
  technology: "Technology demo",
  other: "Other / unverified",
};

/**
 * WHAT KIND OF EVIDENCE PUT THE CATEGORY ON THIS CARD, in words a reader can
 * weigh. `pipeline/build_release.py` publishes `classificationBasis` on every
 * row and its own BASIS_EVIDENCE table is the long form of this; these are the
 * same statements, short enough to ride on a chip's tooltip and in one row of
 * the provenance list.
 *
 * `radio-licence` is in this table and is NOT in the pipeline's: a licence is
 * a filing an operator made to a regulator about this specific object, which
 * is a different and stronger thing than a name match, and the card said
 * nothing about it before.
 */
export const CLASSIFICATION_BASIS_EVIDENCE: Record<string, string> = {
  "web-corroborated": "Independent published sources, quoted and linked, agree this catalog number is this spacecraft.",
  "norad-id": "A rule written for this catalog number, so it can only ever match this object.",
  "exact-name": "A rule written for this exact name.",
  "radio-licence": "The ITU service its operator filed its transmitters under, in the SatNOGS licence record.",
  "source-group": "The category CelesTrak files this object under. Nothing has been checked against this spacecraft.",
  "name-pattern": "A programme-name pattern. Nothing has been checked against this spacecraft.",
  "withdrawn-name-collision": "A name match that two independent sources say is about a different spacecraft.",
  // Added 2026-08-20 with the pipeline's `assessed` basis. It sits with the
  // uncorroborated bases ON PURPOSE. A named analyst reading orbits and launch
  // announcements is much better evidence than a bare name match, and it is
  // still not the operator telling you what the spacecraft is for -- which is
  // what Skynet, Syracuse, SATCOMBw and WGS all have and Shentong-2, Blagovest
  // and Garpun all do not. The card names the analyst in its own sentence.
  "assessed": "An assessment by named independent analysts. No operator or government has published what this spacecraft is for.",
  "unclassified": "Not established from any source.",
};

/**
 * The bases that tie a label to THIS object rather than to a name or a filing
 * cabinet. Everything else is a claim the site is repeating, not corroborating.
 *
 * This is the whole of the Tianmu-1 11 repair. That card read "METOC /
 * WEATHER" and then, directly underneath, "Its purpose has not been
 * independently verified for this object" - a category and a retraction of it,
 * three lines apart, costing about sixty words to contradict itself. The
 * uncertainty belongs IN the chip: `source-group` means CelesTrak files the
 * object under `weather` and nothing else was checked, so the chip is drawn
 * dashed, dimmed and marked, and the sentence is gone.
 *
 * `classificationConfidence` is deliberately NOT used for this. The pipeline's
 * own comment says confidence answers "how much to trust the label" on a scale
 * that grades an anchored programme-name match "medium", and Tianmu-1 11 is
 * graded "high" while carrying the hedge - so confidence and the hedge already
 * disagree on that card. The BASIS is the field that says what was actually
 * checked, and it is the one drawn here.
 */
const CORROBORATED_BASES = new Set(["web-corroborated", "norad-id", "exact-name", "radio-licence"]);

/**
 * MISSION CORROBORATION FROM THE FLEET — a SEPARATE published field, deliberately
 * not another entry in the set above.
 *
 * `pipeline/build_release.py` publishes `missionCorroboration` beside
 * `classificationBasis`, never instead of it. A Starlink still records
 * `classificationBasis: "name-pattern"`, because a name pattern is still exactly
 * how its mission label was arrived at. What the new field adds is that the
 * object's own fleet was checked and agreed with it.
 *
 * The two are kept apart because they answer different questions and because
 * this rendering rule is expected to be revisited — see below.
 */
const MISSION_CORROBORATION_EVIDENCE: Record<string, string> = {
  "cohort-consistent":
    "Its own fleet agrees with it on owner, mission and launch, and nothing independent "
    + "disputes any member. That establishes what this spacecraft is, not which unit of "
    + "the fleet it is.",
};

export type ChipEvidence = "corroborated" | "claimed";

/** The evidence sentence for a card, always a sentence. An unrecognised basis
 *  is treated as the weakest thing it could be rather than as nothing.
 *
 *  Where a fleet vouched for the object, the fleet's sentence is the one shown —
 *  but only when the object's OWN basis is weaker. A card whose label came from a
 *  rule written for its catalogue number has better evidence than its cohort, and
 *  saying "its fleet agrees with it" there would be a downgrade dressed as an
 *  explanation. */
export function classificationBasisEvidence(
  basis: string | undefined | null,
  corroboration?: string | null,
): string {
  const fleet = corroboration ? MISSION_CORROBORATION_EVIDENCE[corroboration] : undefined;
  if (fleet && !(basis && CORROBORATED_BASES.has(basis))) return fleet;
  return CLASSIFICATION_BASIS_EVIDENCE[basis ?? "unclassified"]
    ?? "A rule this release does not describe. Nothing has been checked against this spacecraft.";
}

/**
 * BOTH published fields have to agree before a chip is drawn as corroborated.
 *
 * `classificationBasis` says what kind of check was made and
 * `classificationConfidence` says how much to trust the answer, and they are
 * written independently — the military-classification audit running alongside
 * this work sets both for PLA, Russian and allied systems. A row that carries a
 * per-object basis AND a "low" grade is a reviewer saying "I checked, and I am
 * still not sure", and the chip has to show that rather than the basis alone.
 *
 * So: corroborated needs a basis tied to this object AND a confidence that is
 * not "low". Everything else is claimed. This function only READS the two
 * fields; nothing in the site writes them.
 */
export function classificationChipEvidence(
  basis: string | undefined | null,
  confidence?: string | null,
  corroboration?: string | null,
): ChipEvidence {
  if ((confidence ?? "").trim().toLowerCase() === "low") return "claimed";
  if (corroboration && corroboration in MISSION_CORROBORATION_EVIDENCE) return "corroborated";
  return basis && CORROBORATED_BASES.has(basis) ? "corroborated" : "claimed";
}

/**
 * WHICH FOOTNOTE EXPLAINS THIS CARD'S MARK.
 *
 * The mark is one glyph and it fires for several different reasons, so the key is
 * the BASIS unless the release's own reviewer overrode it. Two overrides:
 *
 *   - `assessed` graded "low" is its own kind. Named analysts reading an orbit is
 *     real evidence and the footnote says so; a reviewer who then wrote down that
 *     the answer is unsettled is a second, different thing the reader is owed. 39
 *     cards are in exactly that position.
 *   - A basis that ties the label to THIS object, graded "low", is `low-confidence`.
 *     Nothing in the shipped catalog is in that state today. The key exists because
 *     `classificationChipEvidence` will mark such a card, and a marked card whose
 *     footnote read "independent published sources agree" would be the chip and the
 *     provenance list contradicting each other on the same screen — which is the
 *     Tianmu-1 11 defect, arriving in a new place.
 */
export function hedgeFootnoteKey(
  basis: string | undefined | null,
  confidence?: string | null,
): string {
  const low = (confidence ?? "").trim().toLowerCase() === "low";
  const name = (basis ?? "unclassified").trim();
  if (low && CORROBORATED_BASES.has(name)) return "low-confidence";
  if (low && name === "assessed") return "assessed-low";
  return name in HEDGE_FOOTNOTES ? name : "unknown";
}

const HEDGE_FOOTNOTES: Record<string, { text: string; source: string }> =
  hedgeFootnoteFile.footnotes;

/**
 * The footnote a card prints, or null where the card carries no mark to explain.
 *
 * IT ASKS `satelliteChips`, rather than re-deriving the condition. A card whose
 * facet is "other" draws NO chip at all — 65 objects in the shipped catalog are
 * `unclassified` with an unknown sector and are in exactly that state — and a
 * footnote explaining a mark that is not on the screen is a caveat about nothing.
 * Deriving "is this card marked" twice is how the two answers drift apart.
 */
export function classificationFootnote(input: {
  mission: string;
  facet: string;
  sector: string;
  basis?: string | null;
  confidence?: string | null;
  corroboration?: string | null;
}): { key: string; text: string; source: string } | null {
  const marked = satelliteChips(input).some((chip) => chip.evidence === "claimed");
  if (!marked) return null;
  const key = hedgeFootnoteKey(input.basis, input.confidence);
  const entry = HEDGE_FOOTNOTES[key] ?? HEDGE_FOOTNOTES.unknown;
  return entry ? { key, ...entry } : null;
}

/** What the mark itself is. A footnote glyph, not a question. */
export const HEDGE_MARK = "*";
/** The heading the footnote sits under, and the words the mark is announced with. */
export const HEDGE_FOOTNOTE_TERM = `${HEDGE_MARK} on the label above`;
export const HEDGE_SPOKEN = " — claimed, not independently corroborated";

/*
 * A REVISITABLE POLICY CHOICE, recorded here so it does not have to be
 * reconstructed. Sean: "I really don't know what to think about this one. I
 * trust your judgement on it. but I also don't want to come back later and want
 * to change it."
 *
 * The choice: a fleet's agreement about its members draws a SOLID chip, the
 * same one a catalogue-number rule draws.
 *
 * Why. The chip states a MISSION CLASS — "Commercial SATCOM" — and the thing
 * the catalogue is genuinely unreliable about is IDENTITY. The 18th Space
 * Defense Squadron names objects within a launch on observation and corrects
 * them afterwards; LitSat-1 and LituanicaSat-1 were transposed until Doppler
 * measurements settled it. Transposing two names inside a Starlink batch leaves
 * both objects Starlinks, so the mission class survives precisely the error the
 * identity does not. Marking it uncertain was applying identity-grade
 * scepticism to a mission-grade claim, on 6,288 of 8,000 cards — and a mark
 * that fires on four fifths of a catalogue has stopped being a mark.
 *
 * The alternatives, and why not:
 *   - A THIRD chip state between solid and dashed. Rejected: it would become
 *     the majority appearance (about 5,000 of 8,000 cards), which makes the new
 *     vocabulary the default one and blurs a binary readers have already
 *     learned. It is also three more visual signals to keep in sync, and the
 *     dashed state is deliberately drawn three ways for that exact reason.
 *   - LEAVE IT DASHED and fix the presentation elsewhere. Rejected on Sean's
 *     instruction: "Just definitely get rid of the ? from the cards."
 *   - ADD "cohort-consistent" TO `CORROBORATED_BASES`. Rejected: it is not a
 *     basis, and folding it into that set would overwrite how the label was
 *     actually arrived at. Everything above this line stays true of a Starlink:
 *     its mission label DID come from a name pattern.
 *
 * To revisit, this function and `classificationBasisEvidence` are the whole
 * surface. `missionCorroboration` and `classificationBasis` are both published
 * per object and neither destroys the other, so a different rendering rule
 * needs no rebuild and no re-derivation — only an edit here.
 */

/**
 * The two sentence shapes `template_purpose()` in build_release.py emits when
 * the site has no published description for an object.
 *
 * Measured against the shipped catalog: 2,451 of 8,000 objects carry one of
 * these, and the other 5,549 carry real prose with a citation - the Starlink
 * and OneWeb family paragraphs, the SatNOGS radio-licence sentences, and the
 * 117 hand-curated entries. So the Satellite Background section is worth
 * having, and it must be ABSENT rather than filled with the hedge: the hedge
 * is this site talking about itself, and the chip now says the same thing in
 * two words.
 *
 * Matched on content rather than on `purposeKind`, because `purposeKind` is
 * "template" for the 65 radio-licence descriptions, which are real, cited
 * prose about the object. A flag that is wrong for a lane is worse than a
 * literal that the lane cannot accidentally satisfy.
 */
export const TEMPLATE_PURPOSE_PREFIXES = [
  // The shape shipped from 2026-08-20. Fact-led: the gap gets one clause and
  // the rest of the sentence is the registry's own record for this object.
  "No public source names this spacecraft's payload",
  // The two apology-led shapes it replaced. Kept because a release built before
  // that change still carries them, and a stale artifact must not start
  // claiming it holds a published description.
  "Its purpose has not been independently verified for this object:",
  "The public catalog does not identify this spacecraft's payload or mission,",
];

export function hasPublishedDescription(purpose: string | null | undefined): boolean {
  const text = (purpose ?? "").trim();
  if (!text) return false;
  return !TEMPLATE_PURPOSE_PREFIXES.some((prefix) => text.startsWith(prefix));
}

/** The three facets whose own label already names the operator class. */
const FACETS_THAT_ENCODE_SECTOR = new Set(["milsatcom", "commercial-satcom", "military-other"]);

/** How an operator class is spelled on its chip. Absent values get no chip. */
const sectorChipLabels: Record<string, string> = {
  military: "Military",
  civil: "Civil / government",
  commercial: "Commercial",
  academic: "Academic",
  mixed: "Mixed",
};

/**
 * The two chips under a spacecraft's name, as `.layer-status` stamps - the
 * same component, tokens and border treatment the space-weather overlays use
 * for OBSERVED / MODEL / EMPIRICAL, because "what class of claim is this" is
 * the same question in both places.
 *
 * Returns the descriptions rather than the elements so the rule can be tested
 * without a DOM, in the arrangement `satelliteOrbitFacts` already uses.
 */
export interface SatelliteChip {
  kind: "category" | "operator";
  label: string;
  evidence: ChipEvidence;
  /** The sentence that rides on the chip as its tooltip and its label text. */
  why: string;
}

export function satelliteChips(input: {
  mission: string;
  facet: string;
  sector: string;
  basis?: string | null;
  confidence?: string | null;
  corroboration?: string | null;
}): SatelliteChip[] {
  const evidence = classificationChipEvidence(input.basis, input.confidence, input.corroboration);
  const why = classificationBasisEvidence(input.basis, input.corroboration);
  const chips: SatelliteChip[] = [];
  // NO CHIP when the site does not know - and the test for that is the FACET,
  // not the mission. `mission: "other"` with `sector: "military"` becomes the
  // facet "military-other", labelled OTHER MILITARY, and that says something
  // real: this object is a military spacecraft whose payload the site declines
  // to name. The 25 TJS satellites and SAPPHIRE are in exactly that position,
  // and reading `mission` here drew them no chips at all - the card lost the
  // one fact it had. Facet "other" still reads "Other / unverified", which is
  // a chip saying nothing, and it is still suppressed.
  if (input.facet !== "other") {
    chips.push({ kind: "category", label: missionLabels[input.facet] ?? input.mission, evidence, why });
  }
  // No second chip where the category chip already IS the sector. `missionFacet`
  // folds sector into the label for exactly three facets, and MILSATCOM beside
  // MILITARY, or COMMERCIAL SATCOM beside COMMERCIAL, is the same word twice —
  // the defect `sectorFactValue` used to hold off in the fact grid, arriving in
  // a new place. Everything else keeps both.
  if (FACETS_THAT_ENCODE_SECTOR.has(input.facet)) return chips;
  const sector = sectorChipLabels[input.sector?.trim().toLowerCase() ?? ""];
  if (sector) chips.push({ kind: "operator", label: sector, evidence, why });
  return chips;
}

const missionColors: Record<MissionCapability, string> = {
  weather: "#29d4e3",
  communications: "#f5c96a",
  "missile-warning": "#ff7b78",
  navigation: "#a98cff",
  "earth-observation": "#76e6a5",
  science: "#76e6a5",
  "human-spaceflight": "#ffffff",
  technology: "#b9c9d3",
  other: "#b9c9d3",
};

/**
 * One chip, as the `.layer-status` stamp the overlays use.
 *
 * A CLAIMED chip is drawn three ways at once — dashed border, dimmed, and a
 * mark — because the requirement is that an unverified claim still LOOKS
 * unverified at a glance, and a single signal is one stylesheet regression away
 * from disappearing. The same sentence is the tooltip and the screen-reader
 * text, so the chip is not a visual-only disclosure.
 *
 * THE MARK IS AN ASTERISK, NOT A QUESTION MARK (Sean, 2026-08-27: "I wouldn't put
 * a ? on the site. I'd put an * and then somewhere on details, like the written
 * details, denote what that * means."). The two glyphs do different jobs. A "?"
 * is an interrogation printed at the reader — it asks rather than tells, it
 * reads as doubt about the whole label, and on 1,559 cards it looked, in his
 * words, ridiculous. An "*" is the oldest convention in print for "there is more
 * to say about this, and it is written down below": it is quieter, it promises a
 * destination, and this one HAS a destination. Nothing else about the disclosure
 * was weakened to buy that quiet — dashed and dimmed both stay, the tooltip
 * still opens with the claim, and the screen-reader sentence is unchanged.
 *
 * The mark is a BUTTON, because a footnote a reader cannot reach is a footnote
 * that does not exist. It opens "Data Source" (until 2026-08-31, "Where these
 * numbers come from" — Sean asked for the shorter name) on this card and
 * puts the footnote under the reader's eye. Everything it does is also reachable
 * without it: the fold names the footnote in its own summary, and the tooltip
 * carries the full sentence for anyone who never presses anything.
 */
function satelliteChipElement(chip: SatelliteChip): HTMLElement {
  const element = document.createElement("span");
  element.className = `layer-status sat-chip is-${chip.kind} is-${chip.evidence}`;
  element.textContent = chip.label;
  // THE TOOLTIP STILL CARRIES THE WHOLE CLAIM. It is the surface a reader on a
  // pointer gets for free, and it must never become a pointer to somewhere else:
  // a caveat that has to be clicked for has been softened. It gains the route,
  // it does not trade the meaning for it.
  element.title = chip.evidence === "corroborated"
    ? `How this is known: ${chip.why}`
    : `Claimed, not independently corroborated. ${chip.why} `
      + `See "${HEDGE_FOOTNOTE_TERM}" under "Data Sources".`;
  if (chip.evidence === "claimed") {
    const mark = document.createElement("button");
    mark.type = "button";
    mark.className = "chip-mark";
    mark.dataset.hedgeMark = "";
    // The button's own name says where it goes. The claim itself is in the
    // `sr-only` sentence below, unchanged, so a screen reader hears WHAT is
    // being said about the label whether or not it ever reaches the button.
    mark.setAttribute("aria-label", `What the ${HEDGE_MARK} means`);
    mark.textContent = HEDGE_MARK;
    const spoken = document.createElement("span");
    spoken.className = "sr-only";
    spoken.textContent = HEDGE_SPOKEN;
    element.append(mark, spoken);
  }
  return element;
}

const INDEPENDENT_CONSTELLATION = "__independent__";

/**
 * Where a card's OWNER / OPERATOR value came from.
 *
 * "gcat-state" is the odd one and the card treats it differently: it means the
 * site knows no operator by name, and an operator-focused catalogue puts the
 * operator in a different country from the one the registry attributes the
 * object to. The value is therefore a COUNTRY, and labelling it as an operator
 * is the mistake that had a Saudi payload reading "Owner / operator: Brazil".
 */
type OrganizationSource = "curated" | "registry" | "named-program" | "web-corroborated" | "gcat-state";

/**
 * Catalog fields published by `pipeline/build_release.py` that `src/types.ts`
 * does not yet declare. `types.ts` belongs to the schema owner, so these are
 * read through a narrow accessor here rather than by widening a shared type
 * from this file. Both are optional: an older release simply omits them.
 */
type CatalogEvidenceFields = {
  fleetEvidence?: "checked" | "unavailable";
  /** Where `organization` came from. Present on every row of the current release. */
  organizationSource?: OrganizationSource;
  /** What kind of evidence attached the mission and sector labels. */
  classificationBasis?: string;
  /** Set where this object's own fleet vouched for its MISSION CLASS. Never a
   *  replacement for `classificationBasis`; absent is the ordinary case. */
  missionCorroboration?: string;
  /** The URL behind the purpose prose, where one was published. */
  purposeSource?: string | null;
  /** A shortened, at most two-paragraph opening for a description too long for the
   *  card. `purpose` still holds the whole researched text and the card still shows
   *  it, one disclosure below. Absent on most objects, and absent is the ordinary
   *  case: the card then prints `purpose` whole, exactly as it always has. */
  purposeShaped?: string[] | null;
  /** A researched paragraph about this object's FLEET, for the ~5,100 objects whose
   *  own sentence is one clause. It carries its OWN citation because it comes from
   *  a different page than the sentence above it. */
  fleetNote?: string | null;
  fleetNoteSource?: string | null;
  fleetLabel?: string | null;
  /** Counted by build_release.py over the retained catalog. NEVER written into the
   *  fleet prose: a member count is the one fact about a fleet that moves. */
  fleetMemberCount?: number | null;
};

/**
 * WHAT THE BACKGROUND SECTION ACTUALLY PRINTS: at most two paragraphs, plus whatever
 * is left over behind a disclosure.
 *
 * Sean set the format on 2026-08-27, having been shown one of the SHORT ones: "on the
 * site, I want max 2 paragraphs, and max just a few lines per paragraph. It is fine if
 * some only have 1 paragraph and it can be longer if so, with a max of maybe 6-8
 * lines." And, earlier: "I definitely don't want it to get crowded and crazy."
 *
 * Two different things can fill the second slot and they can never both apply -- a
 * shortened opening only exists for descriptions over 800 characters, and a fleet
 * paragraph only exists for fleets whose member sentence is around 130. The two sets
 * are measured disjoint (0 objects in both). This function does not TRUST that: it
 * builds the list and hands back at most two, so a future data change cannot quietly
 * put three paragraphs on a card.
 *
 * `rest` is the part of the researched description the shortened opening left out. It
 * is empty when nothing was shortened, which is most cards, and the card must then
 * show no disclosure at all -- an empty fold is worse than no fold.
 */
/** The one Source link builder. Two citations on one card is two chances to forget
 *  `rel="noreferrer noopener"` on a link the site does not control. */
function sourceLink(href: string): HTMLAnchorElement {
  const link = document.createElement("a");
  link.href = href;
  link.target = "_blank";
  link.rel = "noreferrer noopener";
  link.textContent = "Source ↗";
  return link;
}

export function backgroundParagraphs(
  purpose: string,
  shaped: string[] | null | undefined,
  fleetNote: string | null | undefined,
): { paragraphs: string[]; rest: string; shortened: boolean } {
  const short = (shaped ?? []).map((text) => (text ?? "").trim()).filter(Boolean);
  const fleet = (fleetNote ?? "").trim();
  const whole = (purpose ?? "").trim();
  // A shortening that is not actually shorter is a bug upstream, and printing it would
  // hide the bug behind a disclosure holding the same words. Fall back to the original.
  const usable = short.length > 0 && short.join(" ").length < whole.length;
  const lead = usable ? short : whole ? [whole] : [];
  const paragraphs = [...lead, ...(fleet ? [fleet] : [])].slice(0, 2);
  return { paragraphs, rest: usable ? whole : "", shortened: usable };
}

/**
 * "No named fleet identified" asserts a negative. It is only true when the
 * build actually checked fleet membership; when the CelesTrak category cache
 * was thin it checked nothing, and saying "none" there is how a transient
 * gap reads as a finding. An absent field means an older release that did
 * check — that was the only behaviour it had.
 */
export function fleetFactValue(
  constellation: string | null,
  evidence: "checked" | "unavailable" | undefined,
): string {
  if (constellation) return constellation;
  return evidence === "unavailable"
    ? "Fleet data not available in this build"
    : "No named fleet identified";
}

/**
 * Owner/operator is worth a row only when it names an operator. For roughly a
 * third of the catalog it is the registry country restated, and showing it
 * twice implies two independent sources agree when there is only one.
 */
export function operatorFact(organization: string, ownerLabel: string): string | null {
  const operator = organization.trim();
  if (!operator) return null;
  return operator.toLowerCase() === ownerLabel.trim().toLowerCase() ? null : operator;
}

/**
 * Who owns and who registered a spacecraft, as rows.
 *
 * `operatorFact` above answers "is the organization worth a row", and its
 * answer is null for 2,545 of 8,000 objects — a third of the catalog — because
 * `organization` is the registry country restated. The card then dropped the
 * "Owner / operator" row entirely, so a reader could not tell an unpublished
 * operator from a page that forgot to render one.
 *
 * The honest repair is not to guess an operator. It is to say whose answer the
 * name is. `organizationSource` is published on every row and distinguishes a
 * curated identification from the registry's own owner field, and
 * `build_release.py`'s own doctrine is that "the honest outcome is that the
 * site says the registry's answer and stops". So:
 *
 * - a distinct organization keeps both rows, as before;
 * - the registry's answer becomes ONE row that says it is the registry's,
 *   replacing the vanished row and the duplicate country row together;
 * - a curated answer that happens to equal the country gets no such suffix,
 *   because calling a curator's identification a registry record would be a
 *   false provenance claim.
 *
 * Nothing here infers an operator, and nothing prints "no operator published"
 * — that is a negative finding this site's sources cannot support.
 */
export function ownershipRows(
  organization: string,
  ownerLabel: string,
  organizationSource?: OrganizationSource,
  operatorState?: string | null,
): Array<[string, string]> {
  const operator = organization.trim();
  const registry = ownerLabel.trim();
  const country = (operatorState ?? "").trim();
  // The registering state and the operator's country genuinely differ, and the
  // honest answer is BOTH, labelled — not one overwriting the other. A UK-built
  // spacecraft flown by a French company, an SES bird licensed through the UK
  // out of Luxembourg, a Japanese cubesat inheriting the ISS 1998-067 series:
  // international registration really does work this way, and a site that
  // silently picked a winner would be asserting something no source says.
  const differs = country !== "" && country.toLowerCase() !== registry.toLowerCase();
  const operatorCountry: Array<[string, string]> = differs ? [["Operator's country", country]] : [];
  const originRows: Array<[string, string]> = differs
    ? [...operatorCountry, ["Registering state", registry]]
    : [["Country / registry", registry]];
  if (!operator) return originRows;
  // `gcat-state` means the value IS a country, arrived at from the operator
  // rather than from the register. Labelling it "Owner / operator" would claim
  // the site knows who flies the spacecraft, which is exactly the claim that
  // put a Saudi payload under Brazil in the first place.
  if (organizationSource === "gcat-state") return originRows;
  if (operator.toLowerCase() !== registry.toLowerCase()) {
    return [["Owner / operator", operator], ...originRows];
  }
  return [
    ["Owner / operator", organizationSource === "registry" ? `${registry} · registry record` : registry],
    ...operatorCountry,
  ];
}

/**
 * The sector row, when it is not already on the badge.
 *
 * `missionFacet` folds sector into the badge for the three military and
 * commercial communications facets, so for those the row restates the badge
 * verbatim — MILSATCOM was on this card three times, and this is one of them.
 * An "unknown" sector is not a fact either; the house rule is that absence
 * looks like ordinary absence rather than a finding, the same rule the
 * ground-station section and `operatorFact` already follow.
 */
export function sectorFactValue(facet: string, sector: string): string | null {
  if (facet === "milsatcom" || facet === "commercial-satcom" || facet === "military-other") return null;
  const value = sector.trim();
  return !value || value.toLowerCase() === "unknown" ? null : value;
}

/**
 * The satellite card's fact grid.
 *
 * Extracted from the renderer so a test can exercise the rule the card
 * actually uses rather than a copy of it — the same arrangement
 * `dataViewerSections` has for the layer cards, and for the same reason: this
 * codebase has repeatedly shipped green tests over code no entry point reaches.
 *
 * The diet applied here, all of it removing values that were already on screen:
 *
 * - **Velocity is gone.** It is exactly `v = √(μ(2/r − 1/a))` from the altitude
 *   and the period, both of which stay. It carried no information at all.
 * - **Orbit class, altitude and period are three cells that sit together.**
 *   The pipeline derives the orbit REGIME from the period and eccentricity
 *   (`derive_orbit`), which is why they are neighbours; they were briefly ONE
 *   STRING for the same reason, and that is what produced the run-on sentence
 *   and the colour lottery `satelliteOrbitFacts` now describes in full. The
 *   GEO subtype is still stated, because that distinction is not derivable by
 *   eye — it is just a value in a cell now rather than a clause in a sentence.
 * - **Sector defers to the badge** where the badge already encodes it.
 */
/**
 * WHERE THE SPACECRAFT IS. The card's open section, and the reason it is open.
 *
 * Every number here was already published and already on the card — at the
 * bottom of a shut "Ephemeris and provenance" list, set at 9.28 px, the
 * smallest type on the surface. The audience is Navy Space Cadre and METOC
 * officers, and for them INCLINATION is the most operationally useful number
 * on the card: it is the latitude band the spacecraft can ever reach, and no
 * other row implies it. Apogee and perigee are the whole story the moment
 * anyone opens an HEO, where a single "946 km now" is nearly meaningless — a
 * Molniya at perigee and the same Molniya at apogee are the same spacecraft
 * reporting two different worlds.
 *
 * Orbit class, altitude and period are THREE CELLS, in the same grammar as
 * every other fact here — a grey label over a value. They were one run-on
 * string, `LEO · 951 km now · 103.9 min period`, which was the only value on
 * the card written as a sentence, and it broke twice.
 *
 * It broke visually: three facts in prose, wrapping to two lines, in the
 * middle of a grid of facts. Sean: "Why write it out? It looks weird."
 *
 * And it broke INCONSISTENTLY, which is worse. One string is given one voice,
 * and `factValueVoice` picks that voice by LENGTH — past 44 characters a value
 * is a sentence. `HEO · 38,987 km now · 717.9 min period` is 38 characters and
 * came out cyan; `Other GSO / near-GEO · 35,699 km now · 1436.1 min period` is
 * 56 and came out grey. Same row, same certainty, same measurements, opposite
 * treatment — decided by how long the orbit class happened to be spelled. Both
 * GEO subtypes are long enough to cross it, so every GEO object on the site
 * printed its altitude and period in the muted prose colour and every LEO, MEO
 * and HEO printed them cyan. Sean, with the two cards side by side: "look how
 * odd this is... why was the MUOS satellite I showed you in the other
 * screenshot in grey as a sentence?"
 *
 * Split, each value is judged on its own: the altitude and the period are
 * measurements on every spacecraft and read as measurements on every
 * spacecraft, and the class name cannot drag them anywhere. `FACT_CELL_OVERRIDES`
 * pins the class cell so it is the same for a three-letter regime and a
 * twenty-character GEO subtype.
 *
 * This is NOT the "one fact three times" the diet removed. The regime IS
 * derived from the period, and that is why the three sit together and why the
 * label says `Orbit type` rather than repeating the word Orbit three times.
 * What the diet removed was VELOCITY, and it stays removed for its own reason:
 * it is exactly sqrt(mu(2/r - 1/a)) from the altitude and the period, both of
 * which are right here.
 *
 * "now" stays on the altitude label. It is the one value in the orbit block
 * that moves with the clock — perigee and apogee do not — and dropping it
 * would let a reader take 35,727 km for a fixed property of the orbit.
 */
export function satelliteOrbitFacts(input: {
  orbitLabel: string;
  altitudeNow: string | null;
  periodMinutes: number;
  inclinationDeg: number;
  perigee: string;
  apogee: string;
  subSatellitePoint: string | null;
  elementAge: string;
}): Array<[string, string]> {
  // Missing values are said in words, the way "History not loaded" is said in
  // the cell below. An empty cell reads as a rendering fault and a zero reads
  // as a measurement that came out small; neither is what is true here.
  const altitude = input.altitudeNow ?? "propagating…";
  const period = Number.isFinite(input.periodMinutes) && input.periodMinutes > 0
    ? `${input.periodMinutes.toFixed(1)} min`
    : "Period unavailable";
  // TWELVE CELLS, SIX ROWS, NO ODD ONE OUT. Perigee and apogee used to share a
  // cell as "355 km / 358 km", which made this grid hold an ODD number and
  // forced exactly one cell to take the whole row. The sub-satellite point was
  // given that row, and then had to be laid label-beside-value to use the
  // width — a second layout rule to pay for the first.
  //
  // Sean, 2026-08-31: "dont combine perigee and apogee. instead of sub
  // satellite point taking up two columns with the lable in the left and the
  // value in the right, make it like all others - value below the lable. then
  // bring down element days next to it. that way perigee and apigee can be
  // next to one another."
  //
  // Splitting them is what makes the count EVEN, so the full-width cell and its
  // label-beside-value special case both go away and every cell in the grid is
  // the same shape. Two facts that were being read as one are also now two
  // facts: a perigee and an apogee are different numbers about different points
  // in the orbit, and "355 km / 358 km" asked the reader to split them.
  return [
    ["Orbit type", input.orbitLabel],
    ["Altitude now", altitude],
    ["Period", period],
    // The label carries what the number MEANS, so the value can stay a value.
    // THE WIDEST LABEL SETS THE COLUMN, so this one was setting all of them.
    // "Inclination · latitude band" measured 114 px against a widest VALUE of
    // 112 px, so every column on the card was sized by a gloss rather than by
    // any number in it. The band is what the inclination MEANS -- an orbit at
    // 53 degrees passes over everywhere up to 53 degrees of latitude -- and
    // that belongs in the page prose, not in a column header it is doubling
    // the width of. Sean, 2026-08-31: "narrow!"
    ["Inclination", `${input.inclinationDeg.toFixed(1)}°`],
    ["Perigee", input.perigee],
    ["Apogee", input.apogee],
    ["Sub-satellite point", input.subSatellitePoint ?? "propagating…"],
    ["Element age", input.elementAge],
  ];
}

/**
 * WHO RUNS IT, and what it is for. A different question from where it is, and
 * it used to be interleaved with it under the heading "Satellite facts" —
 * which named nothing and so ranked nothing.
 */
export function satelliteCardFacts(input: {
  organization: string;
  ownerLabel: string;
  organizationSource?: OrganizationSource;
  operatorState?: string | null;
  constellationFact: string;
  secondaryMissions?: readonly { mission: string; role: string; system?: string }[];
}): Array<[string, string]> {
  const rows: Array<[string, string]> = [
    ...ownershipRows(input.organization, input.ownerLabel, input.organizationSource, input.operatorState),
    ["Constellation / fleet", input.constellationFact],
  ];
  // What else it does. Named as a second job rather than folded into the
  // mission, because a television satellite carrying a GPS augmentation
  // transponder is still a television satellite.
  const also = (input.secondaryMissions ?? [])
    .map((entry) => (entry.system ? `${entry.system} ${entry.role}` : `${entry.mission} ${entry.role}`))
    .join(" · ");
  if (also) rows.push(["Also carries", also]);
  return rows;
}

/**
 * SATELLITE DETAILS: one grid - who runs it and when it went up, then the
 * orbit class, then where it is right now.
 *
 * The launch date used to be the LAST row, under the live measurements, and it
 * moved up on 2026-08-27 for two reasons that agree. It is a fixed property of
 * the object, like the operator and the registry, and not a reading that moves
 * with the clock - it belongs with what does not change. And putting it there
 * is what makes the block below it exactly the six live measurements, in the
 * "2 columns of 3 rows without a gap" Sean asked for:
 *
 *   Altitude now         | Period
 *   Inclination          | Perigee / apogee
 *   Sub-satellite point  | Element age
 *
 * `Orbit type` follows the launch date rather than taking a full row of its
 * own. It was pinned to the whole row until 2026-08-27, which put a
 * three-letter value on a row with an empty right half in the middle of the
 * card — Sean: "see how the orbit and launch date are on separate rows? Can we
 * get them side by side?" They are not side by side, because eleven facts
 * cannot be laid out two-by-two without one of them being alone somewhere; the
 * lone cell is at the BOTTOM of the grid now instead of the middle, and it is
 * the sub-satellite point, which is the one value that wanted the width. Every
 * other row is two columns, on every spacecraft in the catalogue.
 *
 * It replaces two folds. "Where it is" was open and "What it is and who runs
 * it" was shut, so answering "whose GEO comms bird is this and how high is it"
 * meant opening a second disclosure whose heading, in the owner's words,
 * "sounds really dumb". They are one question about one object.
 *
 * The SECTOR row is gone, not moved: it is a chip in the head now, and it was
 * previously printed as a bare lowercase word ("civil") under a caption that
 * did not say what a sector was.
 */
export function satelliteDetailFacts(input: {
  identity: Array<[string, string]>;
  orbit: Array<[string, string]>;
  launchDate?: string | null;
}): Array<[string, string]> {
  const fixed: Array<[string, string]> = [...input.identity];
  if (input.launchDate) fixed.push(["Launched", input.launchDate]);
  return [...fixed, ...input.orbit];
}

/** Cards the visitor has opened, newest first. Twelve is generous for a
 * teaching session and keeps the propagator's forced set bounded no matter
 * how enthusiastically someone clicks. */
/*
 * WHICH SATELLITES THE GLOBE DRAWS is `resolveVisibleIndices()` in globe.ts,
 * called directly. `resolveStackVisibility()` used to wrap it here to add
 * every OTHER spacecraft the visitor had pinned, and `MAX_SELECTED_STACK = 12`
 * capped how many that could be. Both are deleted: with one selection the
 * wrapper reduced to `resolveVisibleIndices(filtered, active, false)` exactly,
 * and a wrapper that adds nothing is a second name for the same rule and a
 * place for a set to grow back.
 */

/**
 * Every browser filter is conjunctive, so a list with nothing ticked selects
 * nothing. That monotone arithmetic stays. What sits on top of it is Sean's
 * design of 2026-08-28: THE THREE LISTS ARE LINKED.
 *
 *   "these lists are linked to one another smartly. say i click 'METOC' under
 *    mission type. under the other two filter categories, the constellations
 *    and owners will automatically be selected for all METOC satellites... a
 *    user can then go in and deselect what they don't want... so say i plot
 *    all metoc but i only want to see china. i can click metoc and deselect
 *    the other countries and as i do the satellites will go off the viewer."
 *
 * TWO GESTURES, AND THEY ARE NOT SYMMETRICAL.
 *
 *  - A POSITIVE CLICK LINKS, ALWAYS, UNCONDITIONALLY. Tick a value in any one
 *    of the three lists and every value that co-occurs with it is ticked in
 *    the other two, so the click plots the whole population that value names.
 *    It is a UNION: whatever was ticked stays ticked, so a SECOND positive
 *    click ADDS a second population rather than replacing the first. Two
 *    reasons, and the second is the stronger one. Sean's own remedy for too
 *    much - "i can click metoc and deselect the other countries" - only reads
 *    as a remedy if the click put those countries there and left them there.
 *    And replacement would make ticking a box take satellites OFF the viewer,
 *    which is the opposite of what ticking a box says it does.
 *
 *  - A DESELECTION IS A PURE REMOVAL. Untick a value and that value goes,
 *    nothing else moves, and the viewer loses exactly the satellites that
 *    carried it. Nothing is ever re-added. Deselection is how the reader
 *    narrows, and a narrowing the site can undo is not a narrowing.
 *
 * WHY THIS IS NOT THE DEFECT THAT WAS FIXED ON 2026-08-27.
 *
 * That fix removed an auto-selection that fired UNDERNEATH a reader who had
 * already narrowed: with MILSATCOM ticked Sean cleared the owner box, ticked
 * Russian Ministry of Defence, and the site turned four other mission types
 * back on so his click would not show nothing - 117 satellites when he had
 * asked for the 50 that are both. Three things about that were wrong, and all
 * three are gone rather than reworded:
 *
 *   1. It was a REPAIR, offered only when a click would otherwise have shown
 *      nothing. Linking is not a repair. It is what the click is FOR, it runs
 *      on every positive click whatever the state, and there is no condition
 *      under which it quietly does something else.
 *   2. It ran on DESELECTION too, so a narrowing could not stick. It does not
 *      run on deselection at all now: `reportAfterDeselect` mutates nothing.
 *   3. It consulted invisible provenance - which lists the SITE had filled
 *      versus which the READER had - so two identical clicks did different
 *      things. That bookkeeping (`siteFilledFacets`, the `widenable`
 *      argument, `markReaderFacet`) is deleted, not disabled. There is no
 *      hidden state left here for a click to branch on.
 *
 * The route to the 50 is now the one Sean wrote himself: tick MILSATCOM, then
 * deselect every organization except the one. The deselections stick, and the
 * count on each owner row says how many go off the viewer as it comes off.
 *
 * A ZERO IS STILL REPORTED AND NEVER REPAIRED. A positive click can no longer
 * produce one - it always plots at least the satellites it names - so the only
 * zero left is the one a reader deselects their way into, and that one is said
 * out loud in a single line with nothing changed underneath them.
 */

/** One catalog row reduced to the three facet values the filter grids show,
 * plus whether the orbit tabs currently allow it. */
export interface FacetEntry {
  mission: string;
  constellation: string;
  owner: string;
  inOrbit: boolean;
}

export type FacetName = "mission" | "constellation" | "owner";
export const FACET_NAMES: readonly FacetName[] = ["mission", "constellation", "owner"];

export interface FacetSelection {
  mission: Set<string>;
  constellation: Set<string>;
  owner: Set<string>;
}

export interface FacetLinkResult {
  selection: FacetSelection;
  /** Matches under the live orbit band after the gesture. */
  matchCount: number;
  /** Values the click ticked in the other two lists on the reader's behalf.
   * This is the SUBSTANCE of a positive click, not a side effect of one: it
   * is what "the constellations and owners will automatically be selected"
   * means, and the rail says it out loud as well as ticking the boxes. */
  added: Partial<Record<FacetName, string[]>>;
  /**
   * Whether an empty result is the arithmetic the visitor asked for.
   *
   * Under conjunctive lists, emptying a list IS asking for zero: untick every
   * mission type and nothing can match, whatever the other two say. Sean
   * sanctioned exactly that - "if I deselect everything, take all satellites
   * off the map" - so it is a completed action and gets no words. Ticks
   * standing in all three lists and a zero result is the other case, the
   * combination died on you, and only that one is worth a line.
   */
  anyFacetEmpty: boolean;
}

/** The owner facet only constrains organizations its grid actually lists;
 * `shownOwners` carries that list so an unlisted owner can never be silently
 * excluded by a facet the visitor cannot see. (The grid now lists every
 * organization, which makes this a complete constraint in practice.) */
export function facetEntryMatches(
  entry: FacetEntry,
  selection: FacetSelection,
  shownOwners: ReadonlySet<string>,
): boolean {
  return selection.mission.has(entry.mission)
    && selection.constellation.has(entry.constellation)
    && (!shownOwners.has(entry.owner) || selection.owner.has(entry.owner));
}

export function facetMatchCount(
  entries: readonly FacetEntry[],
  selection: FacetSelection,
  shownOwners: ReadonlySet<string>,
): number {
  let count = 0;
  for (const entry of entries) {
    if (entry.inOrbit && facetEntryMatches(entry, selection, shownOwners)) count += 1;
  }
  return count;
}

export function selectionIsEmpty(selection: FacetSelection): boolean {
  return selection.mission.size === 0 && selection.constellation.size === 0 && selection.owner.size === 0;
}

function cloneSelection(selection: FacetSelection): FacetSelection {
  return {
    mission: new Set(selection.mission),
    constellation: new Set(selection.constellation),
    owner: new Set(selection.owner),
  };
}

function countAmong(pool: readonly FacetEntry[], selection: FacetSelection, shownOwners: ReadonlySet<string>): number {
  let count = 0;
  for (const entry of pool) if (facetEntryMatches(entry, selection, shownOwners)) count += 1;
  return count;
}

/** Facet values healing may tick for `facet`, given the satellites the click
 * named. For the owner facet only listed organizations are tickable. */
function coOccurringValues(
  facet: FacetName,
  named: readonly FacetEntry[],
  shownOwners: ReadonlySet<string>,
): Set<string> {
  const found = new Set<string>();
  for (const entry of named) {
    const value = entry[facet];
    if (facet === "owner" && !shownOwners.has(value)) continue;
    found.add(value);
  }
  return found;
}

function recordAdditions(
  selection: FacetSelection,
  facet: FacetName,
  values: ReadonlySet<string>,
  added: Partial<Record<FacetName, string[]>>,
) {
  const fresh: string[] = [];
  values.forEach((value) => {
    if (!selection[facet].has(value)) {
      selection[facet].add(value);
      fresh.push(value);
    }
  });
  if (fresh.length > 0) added[facet] = [...(added[facet] ?? []), ...fresh].sort();
}

/**
 * THE LINK. One pass, one rule, and no conditions on it.
 *
 * `named` is every in-band satellite carrying the clicked value. Both other
 * lists receive every value those satellites carry, unioned into whatever was
 * already ticked. Because the fill is read off `named` itself, every satellite
 * in `named` matches afterwards - so a positive click can never show nothing,
 * and this is a fixed point in one pass with nothing left to iterate.
 *
 * Nothing is consulted about who ticked what, and nothing is ever removed.
 */
export function linkAfterSelect(
  entries: readonly FacetEntry[],
  selection: FacetSelection,
  shownOwners: ReadonlySet<string>,
  anchor: FacetName,
  value: string,
): FacetLinkResult {
  const sel = cloneSelection(selection);
  const added: Partial<Record<FacetName, string[]>> = {};
  const pool = entries.filter((entry) => entry.inOrbit);
  sel[anchor].add(value);
  // The grids only offer values that exist inside the live band, so an empty
  // `named` is reachable only from a caller passing a value no row ever
  // showed. The honest answer to that is no change at all.
  const named = pool.filter((entry) => entry[anchor] === value);
  if (named.length > 0) {
    for (const facet of FACET_NAMES) {
      if (facet === anchor) continue;
      recordAdditions(sel, facet, coOccurringValues(facet, named, shownOwners), added);
    }
  }
  return {
    selection: sel,
    matchCount: countAmong(pool, sel, shownOwners),
    added,
    anyFacetEmpty: FACET_NAMES.some((facet) => sel[facet].size === 0),
  };
}

/**
 * DESELECTION TAKES NOTHING BUT WHAT WAS UNTICKED.
 *
 * There is no verb in this function. It clones, counts and reports - which is
 * the whole point, and why it is named for reporting rather than for healing.
 * It used to do more: a deselection that zeroed the result wiped all three
 * lists, on a proof that pruning could not do better. True, and beside the
 * point - the reader had asked to take ONE tick off. That is how "Clear all"
 * in the owner box also emptied Sean's mission and fleet boxes, silently,
 * twice in one session. It is also the one failure a LINKED catalog cannot
 * afford: if unticking a country re-triggered linking, or took a mission type
 * with it, the reader would be fighting the interface instead of narrowing
 * with it, and narrowing by deselection is now the whole design.
 *
 * A zero is reported, never repaired:
 *
 *  - Some list is empty. Under conjunctive lists that IS zero, and the reader
 *    emptied it a moment ago. The chip beside the heading says "none".
 *    Silence - Sean, on the old sentence: "Duh. I cleared everything. Why am
 *    I getting an error."
 *  - All three lists have ticks and the combination still comes out empty.
 *    That one the reader did not ask for and cannot see the cause of, so it
 *    gets a line - and their selection is left exactly as they set it, with
 *    nothing removed and nothing added, so the state is theirs to work out of.
 *
 * Say what re-ticking actually does, because it is easy to write the flattering
 * version: re-ticking the box just unticked does NOT restore the previous
 * state. It is a positive click, so it links, and the population comes back
 * with everything that goes with it - measured live: METOC narrowed to the
 * GOES fleet was 4 drawn, unticking NOAA / NASA took it to 0 and raised the
 * line, and re-ticking NOAA / NASA came back at 114 rather than 4. That is the
 * union rule doing exactly what it says on every other click, and the way back
 * to a small set is Clear and one tick, not an undo this file does not have.
 */
export function reportAfterDeselect(
  entries: readonly FacetEntry[],
  selection: FacetSelection,
  shownOwners: ReadonlySet<string>,
): FacetLinkResult {
  const sel = cloneSelection(selection);
  const pool = entries.filter((entry) => entry.inOrbit);
  return {
    selection: sel,
    matchCount: countAmong(pool, sel, shownOwners),
    added: {},
    anyFacetEmpty: FACET_NAMES.some((facet) => sel[facet].size === 0),
  };
}

function linkedPartsList(record: Partial<Record<FacetName, string[]>>): string[] {
  const nouns: Record<FacetName, string> = { mission: "mission type", constellation: "fleet", owner: "organization" };
  return FACET_NAMES.flatMap((facet) => {
    const values = record[facet];
    if (!values || values.length === 0) return [];
    return [`${values.length} ${nouns[facet]}${values.length === 1 ? "" : "s"}`];
  });
}

function joinList(parts: string[]): string {
  if (parts.length <= 1) return parts[0] ?? "";
  return `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`;
}

/**
 * The one-line account of what just happened that the reader did not type.
 *
 * Two things can be worth saying and nothing else ever is:
 *
 *  1. The click LINKED. It ticked values in the other two lists, and that is
 *     the point of the gesture rather than an accident of it, so it is stated
 *     in words as well as in checkboxes - the lists it filled may be folded
 *     shut, and a reader who cannot see the ticks would otherwise have to
 *     infer the whole mechanism from the globe.
 *  2. All three lists have ticks and the combination is empty anyway. The
 *     reader deselected their way into it, and nothing was changed for them -
 *     which is the whole of what the sentence promises. It does not promise an
 *     undo: re-ticking the box is a positive click and therefore links.
 *
 * A zero the reader produced by emptying a list is NOT one of them. That is a
 * completed action, the chips already read "none", and a third voice
 * explaining their own click reads as a fault report.
 */
export function describeFacetLinking(result: FacetLinkResult, anchorLabel?: string): string | null {
  const addedParts = linkedPartsList(result.added);
  if (addedParts.length > 0) {
    const carrier = anchorLabel ? `${anchorLabel} satellites carry` : "go with your selection";
    return `Also selected ${joinList(addedParts)} that ${carrier}.`;
  }
  // The bare globe, and every state the reader emptied on purpose: silence.
  if (result.anyFacetEmpty) return null;
  if (result.matchCount === 0) return "Nothing matches that combination. Nothing was changed.";
  return null;
}

/** The "all / N of M / none" chip beside each facet heading. */
export function facetChipText(selected: number, total: number): { text: string; state: "all" | "partial" | "empty" } {
  if (selected === 0) return { text: "none", state: "empty" };
  if (selected >= total) return { text: "all", state: "all" };
  return { text: `${selected} of ${total}`, state: "partial" };
}

/*
 * `filterStatusMessage()` USED TO LIVE HERE AND IS GONE ON PURPOSE.
 *
 * It was the one function that mapped "the selection is empty" onto a sentence
 * — "0 shown - nothing selected", beside a button offering to show everything
 * again — and once the site began opening on a chosen-empty catalog, that
 * mapping fired on arrival and told the reader off for a state he had picked.
 * Sean, twice: "Duh. I cleared everything. Why am I getting an error", and
 * "Stop that shit. You keep adding a feature there."
 *
 * Rewording it would have left the mapping in place for the next control to
 * call, which is how this came back four times. So the function is deleted:
 * there is now NO code path anywhere that turns an empty selection into UI.
 * The rail has exactly one message channel, `filterLinkNote`, written only by
 * `describeFacetLinking()` and only when a click changed the selection on the
 * reader's behalf.
 */

/**
 * THE FEATURED CONSTELLATION lives in `./featured-constellation` now, and is
 * unchanged by the move. It went there so a Playwright spec can ask the
 * rotation what today's pick is: a spec cannot import this file at all,
 * because line 1 is `import "./styles.css"`, and the two specs that worked
 * around that by hard-coding "GPS" expired at the next UTC midnight.
 *
 * Re-exported here because that is where every existing caller imports them
 * from, including `tests/featured-constellation.test.ts`.
 */
export {
  FEATURED_ANCHOR_DAY,
  FEATURED_BLURB_MAX_CHARS,
  FEATURED_CONSTELLATIONS,
  featuredConstellation,
  featuredFallbackSentence,
  featuredKey,
  featuredToastText,
  utcDayNumber,
  utcIsoDay,
} from "./featured-constellation";
export type { FeaturedBlurb, FeaturedConstellation, FeaturedRow } from "./featured-constellation";

/** Every organization the catalog names, audited priorities first, then by
 * how much of the sky each one owns. The full list — a truncated slice once
 * made "only US Navy" quietly impossible, because unlisted owners bypassed
 * the facet entirely. */
export function ownerFilterOrder(counts: ReadonlyMap<string, number>, priorities: readonly string[]): string[] {
  const byCount = [...counts.entries()]
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .map(([name]) => name);
  return [
    ...priorities.filter((name) => counts.has(name)),
    ...byCount.filter((name) => !priorities.includes(name)),
  ];
}

function byId<T extends HTMLElement>(id: string): T {
  const element = document.getElementById(id);
  if (!element) throw new Error(`Missing #${id}`);
  return element as T;
}

/**
 * A failed fetch that still knows WHICH failure it was.
 *
 * The message is unchanged from the plain Error this replaces, because it is
 * what every existing `console.error` in this file prints. What is new is the
 * status as a NUMBER a caller can branch on: since the orbit archive moved to
 * bigmem, a 502 from Caddy and a 404 from the archive host are two different
 * things to tell a reader, and re-parsing them back out of a message string is
 * the kind of thing that works until someone rewords the message.
 */
/**
 * One place a reader can be: a top-level view, and optionally a lesson page
 * inside one of the three learning tracks. This is the whole addressable
 * surface -- deliberately small, because every field here has to survive a
 * round trip through `history.state` and a hand-edited URL.
 */
interface NavState {
  view: string;
  page?: string;
}


class HttpStatusError extends Error {
  constructor(readonly status: number, statusText: string, url: URL) {
    super(`${status} ${statusText} for ${url.pathname}`);
    this.name = "HttpStatusError";
  }
}

async function fetchJson<T>(url: URL, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { cache: "no-cache", ...init });
  if (!response.ok) throw new HttpStatusError(response.status, response.statusText, url);
  return response.json() as Promise<T>;
}

function artifactUrl(manifestUrl: URL, path: string): URL {
  return new URL(path, manifestUrl);
}

/**
 * How often to look for a newer published release.
 *
 * Defaults to the publisher's own five-minute cadence. `?refreshMs=` overrides
 * it for diagnostics — so an operator can watch a live adoption happen instead
 * of waiting out a full cycle — and is clamped to between five seconds and one
 * hour so the override can never turn a visitor's browser into a polling storm
 * against the VPS.
 */
export function artifactRefreshIntervalMs(
  search: string = typeof location === "undefined" ? "" : location.search,
): number {
  const raw = new URLSearchParams(search).get("refreshMs");
  if (raw === null) return DEFAULT_ARTIFACT_REFRESH_INTERVAL_MS;
  const requested = Number(raw);
  if (!Number.isFinite(requested)) return DEFAULT_ARTIFACT_REFRESH_INTERVAL_MS;
  return Math.min(60 * 60_000, Math.max(5_000, requested));
}

/**
 * Put one manifest record back the way it was.
 *
 * Used when a live refresh cannot load a replacement artifact: the record has to
 * keep describing the bundle actually on screen, because the legend reads its
 * coverage and valid-time metadata straight out of the manifest.
 */
function restoreArtifactRecord(
  current: ReleaseManifest,
  previous: ReleaseManifest,
  key: string,
): ReleaseManifest {
  const merged: Record<string, unknown> = { ...current };
  const previousRecord = (previous as unknown as Record<string, unknown>)[key];
  if (previousRecord === undefined) delete merged[key];
  else merged[key] = previousRecord;
  return merged as unknown as ReleaseManifest;
}

export function missionFacet(satellite: SatelliteRecord): string {
  if (satellite.mission === "communications" && satellite.sector === "military") return "milsatcom";
  if (satellite.mission === "communications" && satellite.sector === "commercial") return "commercial-satcom";
  if (satellite.mission === "other" && satellite.sector === "military") return "military-other";
  return satellite.mission;
}

function displayNumber(value: number | null, digits = 0): string {
  return value === null || !Number.isFinite(value) ? "—" : value.toFixed(digits);
}

// The empty-timestamp trap this file used to document twice — on 2026-08-08
// NOAA's GloTEC block published `observedAt: ""` and `new Date("").toISOString()`
// threw out of initialize(), taking the whole site down — is handled by
// `utcMinuteLabel` above, which every timestamp caller now goes through.

function displayElementAge(ageDays: number): string {
  if (ageDays < -0.01) return `${Math.abs(ageDays).toFixed(2)} days ahead · future-dated element`;
  const caution = ageDays > 7 ? " · use with caution" : "";
  return `${Math.max(0, ageDays).toFixed(2)} days${caution}`;
}

function formatUtcStamp(value: string | null, prefix = "As of"): string {
  if (!value) return `${prefix} unavailable`;
  const parsed = new Date(value);
  if (!Number.isFinite(parsed.getTime())) return `${prefix} unavailable`;
  return `${prefix} ${parsed.toISOString().slice(0, 16).replace("T", " ")} UTC`;
}

function formatUtcDay(value: string | null): string {
  if (!value) return "Date unavailable";
  const parsed = new Date(`${value}T00:00:00Z`);
  if (!Number.isFinite(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("en-US", { weekday: "short", month: "short", day: "numeric", timeZone: "UTC" }).format(parsed);
}

function displayPercent(value: number | null): string {
  return value === null ? "—" : `${value}%`;
}

/** The two owner-list sort toggles, remembered per browser exactly as the map
 *  key's fold and the card sections are. */
const OWNER_SORT_STORAGE_KEY = "space-explorer-owner-sort-v1";

/**
 * The polar-cusp annotation, remembered per browser.
 *
 * Every other setting in this layer's panel is remembered only for the visit.
 * This one is remembered across visits because it is the only one whose
 * default the site has ever taken AWAY: a reader who has decided they want the
 * funnels has decided it about a picture that used to include them, and making
 * them re-find the tick on every reload would be the second half of the same
 * annoyance. Read back in `restoreCuspAnnotation`, written on the tick itself.
 */
const CUSP_ANNOTATION_STORAGE_KEY = "space-explorer-cusp-annotation-v1";

function storageGet(kind: "local" | "session", key: string): string | null {
  try {
    return (kind === "local" ? window.localStorage : window.sessionStorage).getItem(key);
  } catch {
    return null;
  }
}

function storageSet(kind: "local" | "session", key: string, value: string) {
  try {
    (kind === "local" ? window.localStorage : window.sessionStorage).setItem(key, value);
  } catch {
    // Hardened/privacy-restricted browsers may disable storage. The explorer
    // remains fully functional with in-memory defaults for this visit.
  }
}

/**
 * A stored card-fold preference that a later default has to be allowed to
 * override, once.
 *
 * `space-explorer-card-sections-v1` records which folds the reader left open,
 * and it is read back over the defaults - which is exactly right for a reader
 * preference and exactly wrong the day a section changes which way it ships.
 * The marker below names the change, not a version, so one section can be
 * reset without forgetting every other fold the reader has ever set. Give a
 * future migration a NEW string here and the same one-shot applies to it.
 */
const CARD_SECTION_MIGRATION_KEY = "space-explorer-card-sections-migration";
// "background-shut-2026-08-20" reset Background once. This marker resets both
// prose folds once more: Sean, 2026-08-31, "only the details section should
// start off expanded" — and any browser where the asterisk mark had been
// pressed had `ephemeris: true` stored by that press, so the ruling would
// never reach exactly the readers who explored the card. Details is untouched:
// a reader who shut it keeps it shut.
const CARD_SECTION_MIGRATION = "details-only-2026-08-31";

class ExplorerApp {
  // `manifest` and `weather` are replaced in place by the artifact refresh
  // controller when bigmem publishes a newer release, so neither can be
  // readonly. Every other bundle stays owned by its own lazy loader.
  private manifest: ReleaseManifest;
  private readonly catalog: CatalogBundle;
  private weather: SpaceWeatherBundle;
  private readonly events: EventsBundle;
  private readonly globe: SpaceGlobe;
  private readonly propagator: OrbitPropagator;
  /** The rendering ceiling. It was a reader-facing control until 2026-08-19;
   * it is now a guard with one value, kept because 8,000 propagated dots on a
   * weak device is a real cost and the filters are the way to ask for them. */
  /** True only while NOAA's Kp-built G-scale reads G0 and Dst is classifying
   *  a storm. Set by the storm update, said by `renderCurrentAnalysis`, so the
   *  caveat and the summary it qualifies are written together. */
  private kpDstDisagreement = false;

  /** Ten seconds, which is Sean's number. Cancelled for good the moment the
   *  reader clicks inside the note. */
  private static readonly featuredToastMs = 10_000;
  private density: Density = "featured";
  /** Whether the reader has asked for the catalog at all. False until the
   * first interaction with a control inside the Satellites section, which is
   * what keeps the opening globe bare. */
  private geometryMode: GeometryMode = "all";
  /**
   * THE ORBIT BAND IS A SCOPE, NOT A FILTER. Sean, after the fourth time this
   * area produced something he had not asked for: "All/LEO/MEO/GEO/HEO are
   * just buttons to show all satellites in that category… That is like a
   * controller - it is like a top level. The other ones are ways you can sort
   * ALL/LEO/MEO/GEO/HEO satellites… Like if I click LEO, the page will only
   * show LEO satellites. If I clear all, LEO still stays selected because when
   * I go select things, I only want things to show that are LEO."
   *
   * So it is single-select, it defines the universe the three peer facets
   * operate inside, and it SURVIVES clearing. `null` is a fourth state and a
   * real one: NO BAND CHOSEN, which is what the site opens on. It is not the
   * same as "all" — "all" is a reader saying show me everything, `null` is a
   * reader who has not said anything yet, and no button is lit for it. They
   * behave alike when the drawn set is computed and differently everywhere a
   * control is rendered, which is why they are two values and not one.
   */
  private orbitScope: OrbitScope = null;
  /** The popup's own state. `featuredToastPinned` is the whole point of it:
   *  a reader who clicks INSIDE the popup has said they are reading it, and
   *  from that moment the ten-second clock is cancelled for good and only the
   *  X or Escape closes it. A note that is yanked away mid-sentence is worse
   *  than no note.
   *
   *  What used to be here — `featured`, and the `featuredStillApplied()` that
   *  read it — went with `#featured-line`. The popup is an ANNOUNCEMENT with
   *  its own lifetime, not a running description of the selection, so it does
   *  not need to know whether the feature is still applied: any click outside
   *  it dismisses it, and a facet click is a click outside it.
   */
  private featuredToastTimer = 0;
  private featuredToastPinned = false;
  private featuredToastBound = false;
  /** The countdown repaint, and the UTC day the note is speaking for. */
  private featuredToastTick = 0;
  private featuredToastDay = "";

  /** THE OWNER ROWS, kept by name so the two sort toggles can regroup the list
   *  by MOVING the elements that already exist. Rebuilding them would take the
   *  change listeners and the ticks with them, and "toggling a sort must never
   *  change which owners are selected" is the hard requirement here. */
  private ownerRows = new Map<string, HTMLLabelElement>();
  private ownerOrder: string[] = [];
  private ownerCounts = new Map<string, number>();
  private ownerSortByCount = false;
  private ownerSortAlphabetically = false;
  /** Last rendered arrangement. A checkbox tick cannot change the grouping —
   *  the bands are cut by the ORBIT band's counts, not by the selection — so
   *  comparing this before re-rendering keeps the rows from being reparented
   *  out from under the reader's pointer on every click. */
  private ownerGroupSignature = "";
  /** The reader's own open folds, remembered while a search is forcing them
   *  open, so clearing the box gives them back rather than shutting everything. */
  private ownerGroupOpenBeforeSearch: Map<string, boolean> | null = null;

  /** Cache of the live band's facet options, rebuilt by `rescopeFacetGrids`. */
  private scopedOptions: Record<FacetName, Map<string, number>> | null = null;
  /** Whether any catalog control has been touched. Wording only — it is not a
   *  filter and nothing is drawn or withheld because of it. */
  private catalogAsked = false;
  private geoFilter: GeoFilter = "all";
  private enabledMissionFacets = new Set<string>();
  private missionFacetCount = 0;
  private enabledConstellations = new Set<string>();
  private constellationCount = 0;
  /* NO `siteFilledFacets`. It recorded whose ticks were whose, so that
     healing could widen the site's and never the reader's — invisible
     provenance, which is why two identical clicks could do different things.
     Linking needs no such branch: a positive click links, a deselection does
     not, and that is the whole rule. */
  private visibleOwnerFilters = new Set<string>();
  private enabledOwners = new Set<string>();
  /** One-line account of what the reader's last click did on their behalf,
   * shown in the status row until the next interaction replaces or clears
   * it. */
  private filterLinkNote: string | null = null;
  private visibleIndices = new Set<number>();
  /** The spacecraft whose orbit, ground trace and footprint are drawn. There
   * is exactly one of them, or none. Sean, 2026-08-28: "no multiple satellites
   * selected ... one at a time." */
  private selectedIndex: number | null = null;
  /**
   * That spacecraft's card, or null when nothing is open.
   *
   * THIS IS NOT A STACK OF ONE. It was `selectedStack: number[]` beside
   * `stackCards: Map<number, HTMLElement>`, and both are deleted rather than
   * capped at one, because a collection capped at one is still a collection:
   * every `forEach` over it, the `is-active` mark that said which member the
   * globe was drawing, the "promote the next card" branch in the remover and
   * the union inside `resolveStackVisibility` all still described a SET, and
   * the next feature to iterate one of them would have grown the stack back
   * for free. What is kept is the floating PANEL that held them — it is a
   * window, with a drag, a remembered position, an occluder registration and a
   * tiling relationship with the layer viewer, none of which was ever about
   * how many cards were inside it.
   */
  private selectedCard: HTMLElement | null = null;
  /** Shared by the satellite cards and the data viewer's layer cards, which is
   * the point: both are the same card, so "open the readings and leave them
   * open" is one preference rather than two. */
  private cardSectionOpen: Record<string, boolean> = {
    // Where the spacecraft is, open: it is the question the card is opened to
    // answer. Attribution is a different question and folds until asked.
    orbit: true,
    facts: false,
    geometry: false,
    ephemeris: false,
    // The three sections the satellite card has now. Details opens because it
    // is the question the card was opened to answer. Background SHIPS SHUT
    // (2026-08-20, Sean): the published description is worth reading, but it
    // is prose, and open by default it pushed the provenance list off a phone
    // screen behind a section nobody had asked for yet.
    details: true,
    background: false,
    // OPEN since 2026-08-19, when this block moved out of the Data Explorer
    // and into its own rail section. It was closed while it was the top card
    // of a panel a reader had opened to read a LAYER - there it was a
    // dig-down, and open by default it filled a phone screen. In the rail it
    // is behind a fold of its own that starts shut, so a reader who opens
    // "Conditions right now" has asked for exactly this grid, and finding a
    // second closed fold inside the first is a door onto a door. The seven
    // tiles are the answer, and they are drawn, not written.
    conditions: true,
    readings: true,
    validity: false,
    provenance: false,
    // The dropdown was opened to look at the storm, so the chart is the one
    // thing open; its provenance and its long-form notes are a level down.
    brief: false,
    "storm-chart": true,
    "storm-provenance": false,
    "storm-notes": false,
  };
  private footprintMinElevationDeg = 0;
  private cardPosition: { top: number; left: number } | null = null;
  private cardDragState: { pointerId: number; offsetX: number; offsetY: number } | null = null;
  /** How tall the reader has dragged the satellite card on a phone, in px. */
  private stackHeight: number | null = null;
  /** The drag ceiling tracks the card's CONTENT — Sean's 2026-08-31 ask, as
   * read: the grip stops where the content stops, and a collapsing section
   * pulls the card down with it "if needed". `false` restores the free drag,
   * where the ceiling is the scene and empty panel below the content is
   * allowed; everything else (clamp, aria, shrink-on-collapse) follows this
   * one flag through `stackSizeBounds`. */
  private static readonly STACK_CEILING_IS_CONTENT = true;
  private stackResizeState: { startY: number; startHeight: number } | null = null;
  private stackPointerId: number | null = null;
  private readonly mobileCardLayoutQuery = window.matchMedia("(max-width: 600px)");
  /**
   * WHICH RAIL IS OUT — on either surface, and never two.
   *
   * It was the phone's field alone. It is now the one piece of state behind
   * both the phone's two doors and the desktop's two tabs, because Sean asked
   * for the same behaviour on both: press a name to pull that rail out, press
   * it again to put it away, press the other name and the first goes away.
   * `null` is the collapsed site, which is what the desktop now loads as.
   *
   * The name is kept for the collision it avoids: `setMode` reads it, and the
   * mode control itself is being retired in a neighbouring change.
   */
  private mobilePanelSection: "satellites" | "environment" | null = null;
  /**
   * The phone layout's own breakpoint, and NOT `mobileCardLayoutQuery`.
   *
   * 820 px is where the stylesheet turns the rail into a bottom sheet, drops
   * the nav and pins the layer readings to the top of the scene; 600 px is
   * where the free-form drag and resize of those readings is switched off.
   * Everything in this file that answers "am I drawing the phone's chrome?"
   * has to ask the first question, not the second — the 220 px band between
   * them is exactly where a resize grip used to be drawn over a panel that
   * could not be resized.
   */
  private readonly phoneChromeQuery = window.matchMedia("(max-width: 820px)");
  /** Which layer rows in the phone's space weather panel have their card open. */
  private readonly phoneLayerCardOpen = new Set<LayerName>();
  /** Page furniture taken out of the document for the phone, and where to put it back. */
  private phoneStripped: Array<{ node: Element; anchor: Comment }> = [];
  private readonly compactClockQuery = window.matchMedia("(max-width: 1050px)");
  private selectedOrbit: Array<{ latitudeDeg: number; longitudeDeg: number; altitudeKm: number }> = [];
  /** Which ruler the orbit line's vertices were last chosen against. */
  private sampledDistanceScale: DistanceScaleId | null = null;
  private selectedGround: Array<[number, number]> = [];
  private selectedFootprint: Array<[number, number]> = [];
  private searchMatches: Array<{ satellite: SatelliteRecord; index: number }> = [];
  private searchRenderedCount = 0;
  /** NORAD numbers the visitor starred, restored from this browser's storage. */
  private favorites: number[] = [];
  private pendingFocusIndex: number | null = null;
  private timeOffsetMinutes = 0;
  private pausedAt: Date | null = null;
  private timedPlayback: TimedPlayback | null = null;
  /**
   * Layers switched on whose coverage has not been judged yet, each holding
   * the reader's clock-action count at the moment it was switched on.
   *
   * The judgement cannot be made on the toggle, and that was the bug: a
   * layer's artifact is fetched asynchronously, so at the instant the checkbox
   * flips the layer's status is "loading", it has no coverage window, and the
   * landing is skipped. Measured on the built bundle against the real release:
   * the aurora key card still drew its 0-100% ramp at +0 ms after the toggle
   * and only flipped to NO DATA at +150 ms, and #time-slider received zero
   * input events — the clock never moved at all. So the intent waits here
   * until the layer's status resolves, and `updateEnvironmentLegend` takes it;
   * that is the one call every loader makes when its bundle lands.
   */
  private pendingCoverageLanding = new Map<LayerName, number>();
  /**
   * How many times the reader has moved the clock themselves. A count, not a
   * time, because the only question ever asked of it is whether the reader
   * touched the clock between switching a layer on and that layer's data
   * arriving.
   */
  private readerClockActions = 0;
  /** Where an automatic landing put the clock, and which layer asked for it. */
  private coverageLanding: { layer: LayerName; note: string } | null = null;
  /** Re-entrancy guard: seeking redraws the legend, which runs this again. */
  private landingCoverage = false;
  private lastPlaybackGeometryUpdate = 0;
  private eventTimer = 0;
  private eventReplay: OrbitDecayReplayView | null = null;
  /** The event whose card opened the replay dialog, so closing can hand focus back to it. */
  private eventOpenerId: string | null = null;
  private transitPlanner: TransitPlanner | null = null;
  // Kept so the transit view can draw the same coastlines the globe uses.
  private readonly land: LandGeoJson;
  private propagationTimer = 0;
  private hiddenAt: number | null = null;
  private snapSolutionAtMs: number | null = null;
  private currentPreset: "simple" | "standard" | "full" = "simple";
  /**
   * THE ONE PLACE THE SITE STILL CHOOSES AN ANGLE, AND WHAT KEEPS IT HONEST.
   *
   * Sean, 2026-08-27: "I know we took the cusps off, but when we pull up
   * magnetosphere it should be oriented so that the sun is on the left of the
   * page, just like we had it before." He is remembering a real thing. Until
   * 71b1437 (whose reasoning commit 3fd8089 restates) ticking this layer
   * called `focusMagnetosphereObliqueView()`, and that preset does put the
   * Sun on the LEFT of the page. Measured on the running page, not assumed:
   * `globe.cameraPose().sunScreenX` is about -0.72 there, where negative is
   * left and -1 would be straight across the screen.
   *
   * That call was removed for a reason that is still right, and this does not
   * undo it. Sean, earlier: "When we put the plasma sheet and ring current on,
   * the projection changes to polar. And it makes navigating really
   * difficult." FOUR layers were flying the camera to presets, two of them
   * ASYNCHRONOUSLY on a later frame, after the reader had gone back to
   * navigating. That is the yank, and it is a different event from this one.
   *
   * Pulling a layer UP is a reader asking for a picture, and is answered at
   * once, inside their own click. Being mid-navigation with the layer already
   * up is not a request, and is never answered at all. So:
   *
   *   - only the magnetosphere layer's OWN checkbox, synchronously in its own
   *     change handler. No data arrival, no clock tick, no preset cascade, no
   *     mode switch, no walkthrough step, and no other layer.
   *   - only when it is switched ON.
   *   - the first pull-up of a session always gets it, because that is
   *     literally what was asked for; after that, only while the reader has
   *     not turned the globe by hand since the site last set the angle. A
   *     reader who has chosen a viewpoint keeps it across a toggle.
   *
   * Whoever reads this next: do not delete the call without reading 71b1437
   * and 3fd8089, and do not widen it back to the other three layers. Both
   * halves are load-bearing and each was asked for by name.
   */
  private magnetosphereOrientSpent = false;
  /**
   * The camera direction the last time the SITE set it, so "the reader has
   * turned the globe since" is a subtraction rather than an event to listen
   * for. Direction only: zooming is not choosing a viewpoint, and
   * `shouldReframeView` already answers for the dolly. Null until the site
   * first sets an angle, which is only reachable before the first pull-up,
   * where `magnetosphereOrientSpent` has already decided.
   */
  private siteSetCameraDirection: [number, number, number] | null = null;
  private geospaceLoading: Promise<void> | null = null;
  private geospaceLoaded = false;
  private geospaceBundle: GeospaceBundle | null = null;
  private ionosphereLoading: Promise<void> | null = null;
  private ionosphereBundle: IonosphereVolumeBundle | null = null;
  /**
   * One sampler per loaded bundle, kept because it caches decoded frames: a
   * probe walks thirty altitudes through the same one or two frames, and a
   * fresh sampler per level would decode a 62,100-point frame thirty times.
   * Cleared with the bundle on an artifact refresh.
   */
  private ionosphereSampler: IonosphereSampler | null = null;
  /** The place the probe is answering about, or null when it is closed. */
  private probePoint: { latitudeDeg: number; longitudeDeg: number } | null = null;
  /**
   * Measured soundings. Fetched without asking, unlike the 19 MB column: the
   * artifact is about 9 KB, and it is what lets the probe answer with a
   * measured layer structure the moment somebody clicks the globe.
   */
  private soundingBundle: SoundingBundle | null = null;
  private soundingLoading: Promise<void> | null = null;
  private probeProfile: SampledProfile | null = null;
  private ionosphereSelectionSignature = "";
  private ionosphereLoadFailed = false;
  // Every named region on by default: the point of the layer is that it is
  // the whole field the TEC surface integrates, and the four bands tile that
  // column exactly, so this is the picture the layer has always opened on.
  // The switches are an ISOLATE control, not a reveal one.
  private ionosphereRegionsOn: Record<IonosphereRegionId, boolean> = allIonosphereRegionsOn();
  /**
   * Whether the reader has armed the profile picker and the globe is waiting
   * for the point they want profiled. Null when it is not armed.
   */
  private profilePickArmed = false;
  private drapLoading: Promise<void> | null = null;
  private thermosphereBundle: ThermosphereBundle | null = null;
  private thermosphereLoading: Promise<void> | null = null;
  private thermosphereLoadFailed = false;
  /** The frame the scene is drawing, kept so the card can quote drag from it. */
  private thermosphereDecoded: DecodedFrame | null = null;
  /** `validAt` of the frame currently drawn, so a clock tick inside the same
   *  frame does not re-decode the artifact. */
  private thermosphereFrameValidAt: string | null = null;
  /**
   * The density level the card's height readings follow, kg m^-3.
   *
   * Held here, not read back out of the globe, because the card has to be able
   * to name it even at an instant where no frame is drawn and the layer holds
   * nothing.
   */
  private thermosphereLevel: number = DEFAULT_ISOPYCNIC_KG_M3;
  /**
   * The minute the no-coverage card was last written for, or null when a frame
   * is drawn. The gap card names the instant the reader picked and offers a
   * jump back into the window, so it goes stale as the clock moves through the
   * gap; this is what makes it rewrite once a minute rather than four times a
   * second.
   */
  private thermosphereGapMinute: string | null = null;
  /**
   * The empirical field, one six-hour shard at a time.
   *
   * NOT one bundle. NRLMSIS covers the whole 120-hour slider — 123 hourly
   * frames, 13.2 MB of JSON — and downloading all of it to draw one hour is
   * exactly the thing this map exists to avoid: a reader who opens the site at
   * `now` fetches ONE 425 kB shard. Keyed by the shard's manifest path, which
   * is content-addressed, so a shard whose drivers changed between releases is
   * a different key and cannot be served from this cache.
   */
  private thermosphereShards = new Map<string, EmpiricalThermosphereShard>();
  private thermosphereShardLoading = new Map<string, Promise<void>>();
  private thermosphereShardFailed = new Set<string>();
  /**
   * Which model produced the frame on screen, and whether it is a forecast.
   *
   * Held rather than recomputed by the card, because the card and the picture
   * disagreeing about which model is drawn is the exact failure this layer has
   * had twice: the badge said MODEL over an hour drawn by something else, and
   * over an hour drawn by nothing at all.
   */
  private thermosphereSelection: ThermosphereSelection | null = null;
  private groundFieldBundle: GroundFieldBundle | null = null;
  private groundFieldLoading: Promise<void> | null = null;
  private groundFieldLoadFailed = false;
  private drapBundle: DrapBundle | null = null;
  private drapLoadFailed = false;
  private auroraHistoryLoading: Promise<void> | null = null;
  private auroraHistoryBundle: AuroraBundle | null = null;
  private auroraHistoryLoadFailed = false;
  private plasmasphereSequence: DgcpmSequence | null = null;
  /**
   * False from the moment the layer is switched on until the frame in which it
   * first actually has a field to draw.
   *
   * The frame cannot be measured from an empty group. Switching the layer on at a
   * moment neither model can answer for — the simulation's newest frame is up
   * to two hours behind the clock, and the empirical fallback refuses when the
   * Kyoto Dst record is more than 90 minutes stale — used to frame the bare
   * globe and leave the whole layer off screen even after the field arrived a
   * second later. This makes the framing wait for the field, exactly once per
   * switch-on, so scrubbing back and forth across a coverage edge afterwards
   * never yanks the camera.
   */
  private ringCurrentFramed = true;
  /** Which ion family the ring-current illustration is drawing. */
  private ringCurrentSpecies: DriftSpecies = DEFAULT_RING_CURRENT_ION;
  /**
   * The identity of the illustration currently traced, so the 4 Hz clock does
   * not re-integrate fifteen drift paths on every tick. Tracing costs about
   * 15 ms, which is invisible once per published frame and a stutter four
   * times a second.
   */
  private ringCurrentKey = "off";
  private plasmasphereLoading: Promise<void> | null = null;
  private plasmasphereLoadFailed = false;
  private groundStations: GroundStationIndex | null = null;
  private groundStationLayer: GroundStationLayer | null = null;
  private groundStationLoading: Promise<void> | null = null;
  private groundStationLoadFailed = false;
  /** Index into `groundStationLayer.stations`, not a station id. */
  private selectedStationIndex: number | null = null;
  /**
   * The last dwell computed, and what it was computed from.
   *
   * A 24-hour dwell is 2,880 SGP4 samples and a bisection at every mask
   * crossing — measured at 32 ms in `tests/ground-station-dwell-cost.test.ts`.
   * It is read inside `environmentLegendSpec`, which runs on every environment
   * tick and several times a second during timed playback, so recomputing it
   * there would spend a whole frame's budget on a figure that does not change
   * from one second to the next. Keyed to the simulated minute: a pass schedule
   * for the next day is not a different answer sixty seconds later.
   */
  private stationDwellCache: { key: string; value: string } | null = null;
  /** Fetched on the first open of the browser: 2.4 MB gzipped, behind a button. */
  private orbitEvents: OrbitEventsBundle | null = null;
  private orbitEventsLoading: Promise<OrbitEventsBundle | null> | null = null;
  private readonly orbitShardCache = new Map<number, OrbitShardResult>();
  private renderingProfile: RenderingProfile = "auto";
  private markerSize: MarkerSize = "standard";
  private motionRate: MotionRate = "adaptive";
  private colorMode: ColorMode = "mission";
  private interfaceScale: InterfaceScale = "large";
  private referenceFrame: ReferenceFrame = "earth-fixed";
  private fieldRendering: FieldRendering = "smooth";
  /**
   * Which radial ruler the whole scene draws on. Teaching (the compressed
   * shared ruler) is the default; true distance is Sean's 2026-08 decision to
   * "offer the two scales and people can toggle". Scene-wide by construction:
   * the value only ever reaches the renderer through
   * `SpaceGlobe.setDistanceScale`, which flips every layer together.
   */
  private distanceScale: DistanceScaleId = "teaching";
  private displayStars = false;
  // Off by default for a visitor who has asked their system to reduce motion;
  // a stored choice replaces this in restoreDisplaySettings either way.
  private displayEnvironmentMotion = !prefersReducedMotion();
  private displaySatelliteLabels = true;
  private timelineTooltipVisible = false;
  /**
   * The width the Kp chart was last laid out at, in CSS pixels.
   *
   * Its geometry is built at the container's own pixel size so the axis
   * type is not scaled by the viewBox, which means a resize genuinely
   * changes the drawing rather than just stretching it. Redrawing on every
   * resize event would rebuild eighty-one bars per frame of a window drag,
   * so the width is remembered and a redraw is skipped when it has not
   * moved past a pixel.
   */
  private kpChartWidth = 0;
  /** Attached once, on first draw; see `observeKpChart`. */
  private kpChartObserver: ResizeObserver | null = null;
  private timelineTooltipHideTimer = 0;
  private lastEnvironmentSignature = "";
  private lastStormPanelSignature = "";
  private lastSurfaceEnvironmentSignature = "";
  private environmentLegendFocus: LayerName | null = null;
  private readonly layerDetailState = new Map<LayerName, boolean>();
  private mapKeyCollapsed = false;
  /** Content of the key cards as last rendered; see `updateMapKey`. */
  private renderedKeyCardSignature: string | null = null;
  /**
   * The Data Explorer has no on/off preference any more — it is present
   * whenever at least one layer is switched on and absent otherwise, which
   * `updateDataViewer` computes fresh every tick. What IS remembered is only
   * whether a visitor who has seen it wants it expanded; collapsed to one row
   * is the shipped default for a first-time visitor.
   */
  private explorerCollapsed = false;
  /** Set when the mobile layer sheet folded the readings away, so closing the
   * sheet can put them back. See `closeMobilePanel`. */
  private explorerFoldedForSheet = false;
  private explorerPosition: { top: number; left: number } | null = null;
  private explorerSize: { width: number; height: number } | null = null;
  private explorerDragState: { pointerId: number; offsetX: number; offsetY: number; startX: number; startY: number; moved: boolean } | null = null;
  private explorerResizeState: { pointerId: number; startWidth: number; startHeight: number; startX: number; startY: number } | null = null;
  private readonly layerCards = new Map<LayerName, HTMLElement>();
  private layerCardOrder = "";
  /**
   * Which layer's card is expanded when the reader has not said, and which
   * layers were on last pass so a newly switched-on one can be recognised.
   *
   * Held for the session rather than stored: opening a card is a step inside
   * one reading of the globe, not a setting. What IS remembered across passes
   * is a card the reader opened or shut BY HAND — `layerCardState` — because
   * undoing that on the next 4 Hz refresh would make the control useless.
   */
  private readonly layerCardState = new Map<LayerName, boolean>();
  private currentMagnetopauseDriver: MagnetopauseDriverSample | null = null;
  private currentXrayFlux: number | null = null;
  // Density opens the layer — the same default the runtime and the globe
  // carry; see the reasoning in GeospaceRuntime's constructor. All three
  // defaults and the is-active button in index.html must agree, or the
  // legend names a different ramp than the one on screen.
  private currentGeospaceField: GeospaceField = "density";
  private currentRadiationView: RadiationBeltRuntimeView = "dipoleMapped3d";
  private currentRadiationPitchIndex: number | null = null;
  private geospaceUiSignature = "";
  private artifactRefresh: ArtifactRefreshController<ReleaseManifest> | null = null;
  private artifactRefreshPhase: ArtifactRefreshStatus<ReleaseManifest>["phase"] = "paused";
  private lastArtifactAdoptionAt: number | null = null;

  constructor(
    manifest: ReleaseManifest,
    catalog: CatalogBundle,
    weather: SpaceWeatherBundle,
    events: EventsBundle,
    land: LandGeoJson,
  ) {
    this.manifest = manifest;
    this.catalog = catalog;
    this.weather = weather;
    this.events = events;
    this.land = land;
    this.globe = new SpaceGlobe({
      container: byId("scene"),
      satellites: catalog.satellites,
      land,
      onSelect: (index) => this.selectSatellite(index, false),
      // A click that hit no spacecraft is offered to the pins first — they are
      // small, named objects and a near-miss on one is meant for it — and only
      // then to the globe itself as a probe of the place under the pointer.
      onEmptyPick: (clientX, clientY) => {
        // An ARMED pick is about a place and nothing else. The ground-station
        // pins do not get first refusal on it either: the reader pressed a
        // button that said "click a point on Earth", and landing on a station
        // card instead would be the interface ignoring what it just asked for.
        if (this.profilePickArmed) {
          this.probeAt(clientX, clientY);
          return;
        }
        if (this.pickGroundStation(clientX, clientY)) return;
        this.probeAt(clientX, clientY);
      },
      onGeospaceFrame: (validAt, leadMinutes, runAt) => this.updateGeospaceFrame(validAt, leadMinutes, runAt),
    });
    this.propagator = new OrbitPropagator(
      catalog.satellites.map((satellite) => satellite.omm),
      ({ at, indices, states, targetStates, valid, targetValid }) => {
        const solutionAtMs = Date.parse(at);
        const waitingForSnap = this.snapSolutionAtMs !== null;
        const isRequestedSnap = waitingForSnap
          && Number.isFinite(solutionAtMs)
          && Math.abs(solutionAtMs - this.snapSolutionAtMs!) <= 1;
        if (waitingForSnap && !isRequestedSnap) return;
        const interpolate = this.pausedAt === null && !document.hidden && !isRequestedSnap;
        this.globe.updateSatellites(
          indices,
          states,
          interpolate ? targetStates : states,
          valid,
          interpolate ? targetValid : valid,
          interpolate ? this.orbitSolutionIntervalMs() : 0,
        );
        if (isRequestedSnap) {
          this.snapSolutionAtMs = null;
          if (this.pausedAt === null) this.propagate();
        }
        if (this.selectedIndex !== null) {
          this.updateSatelliteCard();
          if (this.timedPlayback) this.refreshSelectedGeometry();
        }
        if (this.pendingFocusIndex !== null && this.globe.getState(this.pendingFocusIndex)) {
          this.globe.focusSatellite(this.pendingFocusIndex);
          this.pendingFocusIndex = null;
        }
      },
    );
    this.initialize();
  }

  private initialize() {
    this.buildMissionFilters();
    this.buildConstellationFilter();
    this.buildOwnerFilters();
    this.markOrbitScope();
    this.rescopeFacetGrids();
    this.applyFeaturedConstellation();
    this.bindControls();
    // The phone's pared-down page, and both rails shut. THE SITE STARTS WITH
    // THEM COLLAPSED - Sean's words for the desktop - so there is deliberately
    // nothing here that opens one; `syncMobileTabs` writes the closed state on
    // to the four controls and leaves the workspace's third grid column at 0.
    this.applyPhonePageStrip();
    this.syncMobileTabs();
    this.restoreDisplaySettings();
    this.restoreCardPosition();
    this.restoreStackHeight();
    this.restoreExplorerPosition();
    this.restoreExplorerSize();
    this.restoreCardSections();
    this.restoreFavorites();
    this.restoreLayerDetailState();
    // BEFORE the first `setMagnetopause` below, which is the call that builds
    // the boundary and the field lines for the opening frame. Restoring after
    // it would draw the funnels a tick late, or not at all.
    this.restoreCuspAnnotation();
    this.renderSelectedCard();
    this.updateFootprintElevationNote();
    this.updateWeatherReadout();
    this.updateDataStatus();
    this.globe.updateTec(this.weather.ionosphere.points, this.weather.ionosphere.tecRange);
    // Sampled from the published driver series rather than read off the
    // current-conditions scalars, because the cusped boundaries need the IMF
    // vector and only the series carries it. Without this the very first paint
    // would draw Shue alone and then quietly swap surfaces a tick later.
    this.globe.setMagnetopause(this.magnetopauseDriverAt(this.simulationTime()));
    this.globe.setSolarWindConditions(this.weather.solarWind.speedKps, this.weather.solarWind.densityCm3);
    this.globe.setPhotonFlux(this.weather.xray.fluxWm2);
    this.updateStormPanel(this.simulationTime());
    this.bindWelcomeAndAbout();
    this.refreshVisible();
    this.startArtifactRefresh();
    this.tickClock();
    window.setInterval(() => this.tickClock(), 250);
    this.schedulePropagation();
    document.addEventListener("visibilitychange", () => this.handleVisibilityChange());
  }

  /* NO "only" CHIP ON THE ROWS ANY MORE. It existed because a plain tick used
     to intersect: "what if I want just Starlink" needed a control that cleared
     its own list first. A plain tick now LINKS, which is the same gesture with
     no chip to find and no second affordance inside a label — clicking
     Starlink is what "only Starlink" was. Sean cut it with the rest of the
     furniture: "it's still so cumbersome." */
  /**
   * THE NUMBER IS NOT PART OF THE NAME.
   *
   * It used to be, appended into the same span — and that span ellipsises,
   * because "Russian Ministry of Defence (assessed)" does not fit a half-width
   * column. So the first thing the truncation ate was the count, which is the
   * one part of the row that changes as you filter. Its own element, sized to
   * its content, so the name gives way and the number never does.
   */
  private appendFacetCount(label: HTMLElement): HTMLElement {
    const count = document.createElement("b");
    count.className = "facet-count";
    label.append(count);
    return count;
  }

  private buildMissionFilters() {
    const facets = Array.from(new Set(this.catalog.satellites.map(missionFacet)));
    // EVERY MISSION TYPE THE CATALOG PUBLISHES, and a defined place for one
    // this table has never heard of.
    //
    // `indexOf` returns -1 for an unlisted value, and -1 sorts BEFORE 0: when
    // the pipeline began publishing `signals-intelligence` the rail put it at
    // the head of the grid, under its raw hyphenated key, which is exactly
    // what Sean photographed on 2026-08-21. The list was never truncated —
    // all 13 types were on the rail — but the table it is ordered by had
    // drifted from the data. An unknown type now lands at the END, in
    // alphabetical order among its peers, and still carries its raw key so
    // the drift is visible rather than disguised.
    const preferredOrder = Object.keys(missionLabels);
    const rank = (facet: string) => {
      const index = preferredOrder.indexOf(facet);
      return index === -1 ? preferredOrder.length : index;
    };
    facets.sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));
    this.missionFacetCount = facets.length;
    const container = byId("mission-filters");
    facets.forEach((facet) => {
      // NOTHING TICKED AT REST. Sean, on a bare globe with three full grids of
      // ticks above it: "all the filters are selected. That is odd - we're not
      // showing anything so why are they selected?" He was right, and the
      // controls were the half that was lying: the sets really were full and a
      // separate gate was throwing the result away. The empty selection is now
      // the only reason nothing is drawn, so the grids, the chips, the count
      // and the globe all state the same fact.
      const label = document.createElement("label");
      const input = document.createElement("input");
      input.type = "checkbox";
      input.checked = false;
      input.value = facet;
      input.dataset.missionFacet = facet;
      const text = document.createElement("span");
      text.title = missionLabels[facet] ?? facet;
      text.textContent = text.title;
      label.append(input, text);
      this.appendFacetCount(label);
      input?.addEventListener("change", () => {
        if (input.checked) this.enabledMissionFacets.add(facet);
        else this.enabledMissionFacets.delete(facet);
        this.linkCatalogFilters(
          input.checked ? "select" : "deselect",
          "mission",
          input.checked ? missionLabels[facet] ?? facet : undefined,
          input.checked ? facet : null,
        );
        this.refreshVisible();
      });
      container.append(label);
    });
  }

  private buildConstellationFilter() {
    const counts = new Map<string, number>();
    this.catalog.satellites.forEach((satellite) => {
      const constellation = satellite.constellation ?? INDEPENDENT_CONSTELLATION;
      counts.set(constellation, (counts.get(constellation) ?? 0) + 1);
    });
    this.constellationCount = counts.size;
    const container = byId("constellation-filters");
    Array.from(counts.entries())
      .sort(([left], [right]) => left === INDEPENDENT_CONSTELLATION ? 1 : right === INDEPENDENT_CONSTELLATION ? -1 : left.localeCompare(right))
      .forEach(([constellation, count]) => {
        const label = document.createElement("label");
        const input = document.createElement("input");
        input.type = "checkbox";
        input.checked = false;
        input.value = constellation;
        input.dataset.constellation = constellation;
        const text = document.createElement("span");
        text.title = constellation === INDEPENDENT_CONSTELLATION ? "No named fleet identified" : constellation;
        text.textContent = text.title;
        label.append(input, text);
        this.appendFacetCount(label).textContent = `(${count.toLocaleString()})`;
        input.addEventListener("change", () => {
          if (input.checked) this.enabledConstellations.add(constellation);
          else this.enabledConstellations.delete(constellation);
          this.linkCatalogFilters(
            input.checked ? "select" : "deselect",
            "constellation",
            input.checked && constellation !== INDEPENDENT_CONSTELLATION ? constellation : undefined,
            input.checked ? constellation : null,
          );
          this.refreshVisible();
        });
        container.append(label);
      });
  }

  private buildOwnerFilters() {
    const counts = new Map<string, number>();
    this.catalog.satellites.forEach((satellite) => counts.set(satellite.organization, (counts.get(satellite.organization) ?? 0) + 1));
    const priorities = ["NASA", "NOAA / NASA", "U.S. Space Force", "U.S. Navy", "ESA / European Union", "EUMETSAT", "JAXA", "Japan Meteorological Agency"];
    // Every organization the catalog names. The list used to stop at 18, with
    // unlisted owners silently bypassing the facet — which made "only this
    // owner" quietly impossible and left the chips claiming "all" of a list
    // most of the catalog was not on. The grid scrolls; the search box above
    // it is how a long list stays usable.
    const shown = ownerFilterOrder(counts, priorities);
    const container = byId("owner-filters");
    shown.forEach((organization) => {
      // `visibleOwnerFilters` is the list the grid shows and constrains, which
      // is a different question from what is ticked — it stays complete.
      this.visibleOwnerFilters.add(organization);
      const label = document.createElement("label");
      const input = document.createElement("input");
      input.type = "checkbox";
      input.checked = false;
      input.dataset.owner = organization;
      const text = document.createElement("span");
      text.title = organization;
      text.textContent = organization;
      label.append(input, text);
      this.appendFacetCount(label).textContent = `(${(counts.get(organization) ?? 0).toLocaleString()})`;
      input?.addEventListener("change", () => {
        if (input.checked) this.enabledOwners.add(organization);
        else this.enabledOwners.delete(organization);
        this.linkCatalogFilters(
          input.checked ? "select" : "deselect",
          "owner",
          input.checked ? organization : undefined,
          input.checked ? organization : null,
        );
        this.refreshVisible();
      });
      container.append(label);
      this.ownerRows.set(organization, label);
    });
    this.ownerOrder = shown;
    this.ownerCounts = counts;
    // The two sort toggles are a reader preference, remembered the same way the
    // map key's fold and the card sections are. A corrupt value is no
    // preference rather than a crash.
    const storedSort = storageGet("local", OWNER_SORT_STORAGE_KEY);
    if (storedSort !== null) {
      try {
        const parsed = JSON.parse(storedSort) as { count?: unknown; alpha?: unknown };
        this.ownerSortByCount = parsed.count === true;
        this.ownerSortAlphabetically = parsed.alpha === true;
      } catch {
        this.ownerSortByCount = false;
        this.ownerSortAlphabetically = false;
      }
    }
    this.renderOwnerGroups();
  }

  /**
   * THE OWNER LIST, ARRANGED. Two independent toggles, so four states, and the
   * flat list is one of them: neither on is exactly what shipped before this,
   * in its existing order, untouched.
   *
   * The rows are MOVED, never rebuilt — see `ownerRows`. So a regroup cannot
   * change a tick, cannot drop a listener, and cannot disagree with
   * `#owner-facet-state`, which counts the selection and not the arrangement.
   */
  private renderOwnerGroups() {
    const container = byId("owner-filters");
    // Banded on the counts the ROWS show, which `rescopeFacetGrids` rewrites to
    // the live orbit band's counts.
    const counts = this.scopedOptions?.owner ?? this.ownerCounts;
    const groups = ownerGroups(
      this.ownerOrder,
      counts,
      this.ownerSortByCount,
      this.ownerSortAlphabetically,
    );
    const signature = JSON.stringify([
      this.ownerSortByCount,
      this.ownerSortAlphabetically,
      groups?.map((group) => [group.key, group.members, group.children?.map((child) => [child.key, child.members])]),
    ]);
    if (signature === this.ownerGroupSignature) return;
    this.ownerGroupSignature = signature;
    container.classList.toggle("is-grouped", groups !== null);
    const rowsFor = (names: readonly string[]) => names
      .map((name) => this.ownerRows.get(name))
      .filter((row): row is HTMLLabelElement => row !== undefined);
    container.replaceChildren(...(groups === null
      ? rowsFor(this.ownerOrder)
      : groups.map((group) => this.ownerGroupElement(group))));
    this.updateOwnerGroupVisibility();
  }

  /** One `<details>` per group, so the keyboard and screen-reader behaviour is
   *  the browser's, exactly as every other fold in this rail. Shut by default. */
  private ownerGroupElement(group: OwnerGroup): HTMLDetailsElement {
    const details = document.createElement("details");
    details.className = "facet-group";
    details.dataset.ownerGroup = group.key;
    const summary = document.createElement("summary");
    const label = document.createElement("span");
    label.textContent = group.label;
    const count = document.createElement("b");
    count.className = "facet-group-count";
    summary.append(label, count);
    details.append(summary);
    if (group.children) {
      details.append(...group.children.map((child) => this.ownerGroupElement(child)));
    } else {
      const grid = document.createElement("div");
      grid.className = "filter-grid facet-group-grid";
      grid.append(...group.members
        .map((name) => this.ownerRows.get(name))
        .filter((row): row is HTMLLabelElement => row !== undefined));
      details.append(grid);
    }
    return details;
  }

  /**
   * Every group's headline count, and whether it is on screen at all, read off
   * the rows themselves rather than recomputed — so the header can never
   * disagree with what is under it. Two independent things hide a row and the
   * header has to respect both: the orbit band (`data-scope`) and the search
   * box (`hidden`).
   */
  private updateOwnerGroupVisibility() {
    const container = byId("owner-filters");
    const onScreen = (row: HTMLElement) => row.dataset.scope !== "out" && !row.hidden;
    // Reversed document order, so a band is counted after the letters in it.
    [...container.querySelectorAll<HTMLDetailsElement>("details.facet-group")]
      .reverse()
      .forEach((group) => {
        const rows = [...group.querySelectorAll<HTMLElement>(":scope > .facet-group-grid > label")];
        const nested = [...group.querySelectorAll<HTMLDetailsElement>(":scope > details.facet-group")];
        const visible = rows.filter(onScreen).length
          + nested.reduce((total, child) => total + (child.hidden ? 0 : Number(child.dataset.ownerGroupCount ?? 0)), 0);
        group.dataset.ownerGroupCount = String(visible);
        group.hidden = visible === 0;
        const count = group.querySelector<HTMLElement>(":scope > summary > .facet-group-count");
        if (count) count.textContent = visible.toLocaleString();
      });
  }

  /** A search opens every group, so its matches are on screen rather than
   *  behind a shut header. Clearing the box puts the reader's own folds back. */
  private revealOwnerGroupsForSearch(searching: boolean) {
    const groups = [...byId("owner-filters").querySelectorAll<HTMLDetailsElement>("details.facet-group")];
    if (searching) {
      if (this.ownerGroupOpenBeforeSearch === null) {
        this.ownerGroupOpenBeforeSearch = new Map(
          groups.map((group) => [group.dataset.ownerGroup ?? "", group.open]),
        );
      }
      groups.forEach((group) => { group.open = true; });
      return;
    }
    const remembered = this.ownerGroupOpenBeforeSearch;
    if (remembered === null) return;
    groups.forEach((group) => { group.open = remembered.get(group.dataset.ownerGroup ?? "") === true; });
    this.ownerGroupOpenBeforeSearch = null;
  }

  private syncOwnerSortButtons() {
    const mark = (id: string, active: boolean) => {
      const button = document.getElementById(id);
      if (!button) return;
      button.setAttribute("aria-pressed", String(active));
      button.classList.toggle("is-active", active);
    };
    mark("owner-sort-count", this.ownerSortByCount);
    mark("owner-sort-alpha", this.ownerSortAlphabetically);
  }

  /** The three facet grids reduced to the plain values healing reasons over,
   * with the orbit tabs applied the same way refreshVisible applies them. */
  private facetEntries(): FacetEntry[] {
    return this.catalog.satellites.map((satellite) => ({
      mission: missionFacet(satellite),
      constellation: satellite.constellation ?? INDEPENDENT_CONSTELLATION,
      owner: satellite.organization,
      inOrbit: this.orbitAllows(satellite),
    }));
  }

  /**
   * THE GEO BUTTON IS THE BELT, NOT THE CODE.
   *
   * An inclined geosynchronous craft -- BeiDou IGSO, NavIC, QZSS Michibiki --
   * is at the geostationary height and takes the same sidereal day to go round.
   * It is simply tilted, so its ground track sweeps a figure-of-eight instead of
   * parking on a point. A reader who clicks GEO is asking to see the ring, and
   * an answer that leaves those nineteen out is answering a question he did not
   * ask.
   *
   * It is also what the sub-control below has been promising in shipped text --
   * "Other GSO includes inclined, drifting, and near-GEO objects" -- which until
   * IGSO existed was a cheque the filter could not honour: every one of those
   * objects classified OTHER, and OTHER answers to no band button at all, so
   * they were reachable only from All. Sean saw the other half of the same
   * defect on the card: "I do not get why other would ever be used".
   *
   * IGSO gets no sixth button. Nineteen objects out of eight thousand do not
   * earn top-level rail space beside LEO's seven thousand, and the GEO band
   * already carries the machinery to split itself -- `classifyGeoSubtype` sorts
   * an inclined object into `other-gso` with no new code, because its
   * inclination is nowhere near the 0.1 deg station-kept test. The band puts
   * them in front of the reader; the CARD is where they say IGSO.
   */
  private orbitAllows(satellite: SatelliteRecord): boolean {
    const inBand = this.orbitScope === "GEO"
      ? satellite.orbit === "GEO" || satellite.orbit === "IGSO"
      : satellite.orbit === this.orbitScope;
    if (this.orbitScope !== null && this.orbitScope !== "all" && !inBand) return false;
    if (this.orbitScope !== "GEO" || this.geoFilter === "all") return true;
    return classifyGeoSubtype(
      satellite.periodMinutes,
      satellite.omm.INCLINATION,
      satellite.omm.ECCENTRICITY,
    ) === this.geoFilter;
  }

  /**
   * Runs after every list interaction, before refreshVisible.
   *
   * A POSITIVE CLICK LINKS: `linkAfterSelect` ticks, in the other two lists,
   * every value the clicked value's satellites carry. A DESELECTION LINKS
   * NOTHING: `reportAfterDeselect` counts and reports and changes not one
   * tick, so what the reader took off stays off and the globe loses exactly
   * those satellites on this same frame.
   *
   * The healed sets are mirrored back onto the real checkboxes, and the two
   * lists a link filled are opened, because "the constellations and owners
   * will automatically be selected" is a promise the reader has to be able to
   * SEE keeping. The one-line account goes to the status row.
   */
  private linkCatalogFilters(
    kind: "select" | "deselect",
    anchor: FacetName,
    anchorLabel?: string,
    anchorValue: string | null = null,
  ) {
    const current: FacetSelection = {
      mission: this.enabledMissionFacets,
      constellation: this.enabledConstellations,
      owner: this.enabledOwners,
    };
    const entries = this.facetEntries();
    const result = kind === "select" && anchorValue !== null
      ? linkAfterSelect(entries, current, this.visibleOwnerFilters, anchor, anchorValue)
      : reportAfterDeselect(entries, current, this.visibleOwnerFilters);
    this.filterLinkNote = describeFacetLinking(result, anchorLabel);
    this.enabledMissionFacets = result.selection.mission;
    this.enabledConstellations = result.selection.constellation;
    this.enabledOwners = result.selection.owner;
    this.syncFacetCheckboxes();
    this.revealLinkedSections(result.added);
    // The band is NOT touched here. It is the scope, not a filter, and the
    // grids only list values that exist inside it, so there is no click that
    // can name an out-of-band fleet.
  }

  /** A link that filled a list OPENS that list. Sean's whole gesture is "click
   *  one thing, watch the other two fill in, then deselect what you don't
   *  want" — and Constellations and Owners ship folded shut, so a fill nobody
   *  can see is a fill nobody will trust. Only a list that actually received
   *  values is opened, and only ever opened: a reader who folds one away again
   *  keeps it folded until the next click puts something new in it. */
  private revealLinkedSections(added: Partial<Record<FacetName, string[]>>) {
    const sections: Record<FacetName, string> = {
      mission: "mission-section",
      constellation: "constellation-section",
      owner: "owner-section",
    };
    FACET_NAMES.forEach((facet) => {
      if (!added[facet]?.length) return;
      const section = document.getElementById(sections[facet]) as HTMLDetailsElement | null;
      if (section) section.open = true;
    });
  }

  /**
   * CLEAR MEANS THE CATALOG, AND IT SAYS SO WHERE IT SITS.
   *
   * It is on the "Satellite Catalog" heading row, beside the count of what is
   * drawn, so the box it empties is the one it is labelled with — the same
   * rule that made the old per-list button read "Clear this list" after
   * "Clear all" in the owner box emptied Sean's mission and fleet boxes twice
   * in one session. This control is at the top of the whole catalog, so all of
   * the catalog is its scope: the three lists, the orbit band and the GEO
   * subtype, back to the state the page opens in.
   *
   * It does not touch the search box, Favorites, or any satellite already
   * opened. Those are not catalog selection and are not on this heading.
   */
  private clearCatalogSelection() {
    this.enabledMissionFacets.clear();
    this.enabledConstellations.clear();
    this.enabledOwners.clear();
    this.orbitScope = null;
    this.geoFilter = "all";
    document.querySelectorAll<HTMLButtonElement>("[data-geo-type]").forEach((choice) => {
      const isAll = choice.dataset.geoType === "all";
      choice.classList.toggle("is-active", isAll);
      choice.setAttribute("aria-pressed", String(isAll));
    });
    this.markOrbitScope();
    this.updateGeoFilterVisibility();
    this.rescopeFacetGrids();
    this.syncFacetCheckboxes();
    this.filterLinkNote = null;
    this.refreshVisible();
  }

  /** The checkboxes are the visible record of every linked change: after a
   * click, each grid is mirrored from its set, so a value the link ticked
   * visibly changes state — never a silent mutation. */
  private syncFacetCheckboxes() {
    document.querySelectorAll<HTMLInputElement>("[data-mission-facet]").forEach((input) => {
      input.checked = this.enabledMissionFacets.has(input.dataset.missionFacet ?? "other");
    });
    document.querySelectorAll<HTMLInputElement>("[data-constellation]").forEach((input) => {
      input.checked = this.enabledConstellations.has(input.dataset.constellation ?? INDEPENDENT_CONSTELLATION);
    });
    document.querySelectorAll<HTMLInputElement>("[data-owner]").forEach((input) => {
      input.checked = input.dataset.owner !== undefined && this.enabledOwners.has(input.dataset.owner);
    });
  }

  private bindControls() {
    // THE CATALOG IS OFF UNTIL IT IS ASKED FOR. Sean: "Perhaps don't start
    // off with any satellites then. Just a globe without satellites and
    // without any layers."
    //
    // One gate and one listener rather than a flag threaded through ten
    // handlers: everything that browses the catalog - the orbit tabs, the GEO
    // subtype, the three facet grids, select-all, clear-all, and "Show every
    // satellite again" - lives inside this one section, so the first click or
    // change on any control in it IS the ask. Capture phase, so the flag is
    // already true by the time that control's own handler calls
    // refreshVisible.
    //
    // Deliberately NOT here: picking a satellite out of the search box or the
    // favourites list. That draws the one spacecraft asked for, through
    // resolveVisibleIndices, and turning the whole catalog on with it would
    // bury the thing the reader just went looking for.
    const catalogSection = document.getElementById("catalog-details");
    const askedForCatalog = (event: Event) => {
      if (this.catalogAsked) return;
      if (!(event.target as Element | null)?.closest("button, input, select")) return;
      this.catalogAsked = true;
      // For the handful of controls in here that do not refresh by themselves.
      queueMicrotask(() => this.refreshVisible());
    };
    catalogSection?.addEventListener("click", askedForCatalog, true);
    catalogSection?.addEventListener("change", askedForCatalog, true);
    // Clear sits inside the catalog fold's own <summary>, so its click has to
    // be stopped from reaching the summary and folding the section away under
    // the reader as it empties it.
    document.getElementById("catalog-clear")?.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      this.clearCatalogSelection();
    });
    // NO "Select all" / "Clear this list" IN ANY OF THE THREE LISTS. Sean cut
    // them with the rest of the scaffolding around the catalog, and linking is
    // what replaces them: "that solves the having to click a ton of boxes".
    // One tick fills the other two lists with everything that goes with it,
    // and the one clearing control left is on the catalog's own heading, where
    // its label matches its scope.
    document.querySelectorAll<HTMLButtonElement>("[data-orbit]").forEach((button) => {
      button.addEventListener("click", () => {
        // A TOP-LEVEL FILTER AND NOTHING ELSE. Sean: "when a user hits one
        // of those, nothing happens - it's just a top level filter. they have
        // to choose one of the options below to select what they want." So a
        // band press narrows what the three lists OFFER and plots nothing by
        // itself. It used to call selectAllFacets() and tick every row inside
        // the band, which is how one press could put seven thousand dots on
        // the globe. The only way a band press can change what is DRAWN is
        // rescopeFacetGrids taking values that do not exist in the band out
        // of the selection along with their rows.
        //
        // Re-clicking the live band turns the scope back off, which is the
        // only way back to the unset state without reloading.
        const chosen = (button.dataset.orbit ?? "all") as Exclude<OrbitScope, null>;
        this.orbitScope = this.orbitScope === chosen ? null : chosen;
        this.filterLinkNote = null;
        this.markOrbitScope();
        this.updateGeoFilterVisibility();
        this.rescopeFacetGrids();
        this.refreshVisible();
      });
    });
    document.querySelectorAll<HTMLButtonElement>("[data-geo-type]").forEach((button) => {
      button.addEventListener("click", () => {
        this.geoFilter = button.dataset.geoType as GeoFilter;
        this.filterLinkNote = null;
        this.markActive("[data-geo-type]", button);
        document.querySelectorAll<HTMLButtonElement>("[data-geo-type]").forEach((choice) => {
          choice.setAttribute("aria-pressed", String(choice === button));
        });
        this.rescopeFacetGrids();
        this.refreshVisible();
      });
    });
    document.querySelectorAll<HTMLButtonElement>("[data-preset]").forEach((button) => {
      button.addEventListener("click", () => {
        this.currentPreset = button.dataset.preset as typeof this.currentPreset;
        this.markActive("[data-preset]", button);
        this.applyLayerPreset(this.currentPreset);
      });
    });

    const layerMap: Record<string, LayerName> = {
      "layer-ionosphere": "ionosphere",
      "layer-tec": "tec",
      "layer-drap": "drap",
      "layer-aurora": "aurora",
      "layer-regions": "regions",
      "annotate-empirical-boundaries": "magnetosphere",
      "layer-ring-current": "ringCurrent",
      "layer-geospace": "geospace",
      "layer-solar-wind": "solarWind",
      "layer-photons": "photons",
      "layer-radiation": "radiation",
      "layer-ground-stations": "groundStations",
      "layer-groundField": "groundField",
      "layer-thermosphere": "thermosphere",
    };
    Object.entries(layerMap).forEach(([id, layer]) => {
      byId<HTMLInputElement>(id).addEventListener("change", (event) => {
        const checked = (event.currentTarget as HTMLInputElement).checked;
        this.applyGlobeLayer(layer, checked);
        if (checked) this.environmentLegendFocus = layer;
        // BEFORE the framing below, not after: the ring-current group is
        // empty until the drift paths have been traced, so framing first
        // would measure a bare globe and dolly IN to it, leaving the layer
        // the reader just asked for off screen on its own first click.
        // Measured on the shipped build before this line moved.
        if (checked && layer === "ringCurrent") {
          this.ringCurrentFramed = false;
          this.updateInnerMagnetosphere(this.simulationTime());
        }
        // ONE RULE FOR EVERY LAYER: MAKE ROOM, NEVER TAKE THE WHEEL.
        //
        // Four layers used to answer their own switch by flying the camera to
        // a preset — the belts to an oblique three-quarter view; the solar
        // wind, the plasma field and the plasma sheet to the oblique
        // magnetosphere view; the ring current straight down the dipole axis.
        // Each was argued for on its own merits (a torus seen face-on is a
        // disc; drift paths seen edge-on are a line) and each of those
        // observations is still true. They were the wrong thing to do with
        // them. Sean, on the shipped build: "When we put the plasma sheet and
        // ring current on, the projection changes to polar. And it makes
        // navigating really difficult. Can you have an agent disable that? I
        // do not like it."
        //
        // The distinction that survives is between WIDENING and ROTATING. A
        // reader who has turned the globe has chosen a viewpoint, and
        // rotating replaces it: they lose their place and have to find it
        // again, which is the whole of the complaint. Widening keeps their
        // viewpoint and only makes room — so a layer that would otherwise be
        // entirely off screen still becomes visible, which is a real problem
        // and is the whole of what frameActiveLayers() is for.
        // sceneRadiusForActiveLayers() measures every drawn layer (and, since
        // the MUOS framing fix, every drawn spacecraft) and shouldReframeView()
        // pulls back only when what is drawn no longer fits.
        //
        // The angles are not lost. The three camera buttons under the globe —
        // Sun-Earth side, meridional cross-section, polar — are exactly these
        // views, available to a reader who wants one. The site no longer
        // decides for them.
        this.globe.frameActiveLayers();
        // ...with ONE named exception, this layer only, asked for by name:
        // pulling the magnetosphere up faces it Sun-on-the-left again. The
        // whole rule and why it does not undo the paragraph above is on
        // `magnetosphereOrientSpent`. It runs AFTER the widening so the
        // preset's own framing distance is the one that survives.
        //
        // `event.isTrusted` is the reader themselves and nothing else. It is
        // false for the `change` events other code DISPATCHES at these
        // checkboxes — the energy-chain walkthrough setting each step's
        // layers, and the data explorer's X clearing them — and those must
        // not move the camera. The walkthrough in particular chooses its own
        // camera per step and would be fighting this one.
        if (checked && layer === "geospace" && event.isTrusted) this.orientMagnetosphereOnPullUp();
        this.updateModelControlVisibility();
        this.updateAuroraControlVisibility();
        this.updateThermosphereControlVisibility();
    this.updateIonosphereControlVisibility();
        if (checked && layer === "drap") void this.loadDrapModel();
        if (checked && layer === "groundStations") void this.loadGroundStations();
        if (checked && layer === "groundField") void this.loadGroundField();
        if (checked && layer === "thermosphere") void this.loadThermosphere();
        // The 19 MB density cube is the layer's only content, so the toggle is
        // its door. Without this the layer switches on and draws nothing.
        if (checked && layer === "ionosphere") void this.loadIonosphereModel();
        if (checked && layer === "aurora") void this.loadAuroraHistoryModel();
        // The plasmasphere simulation is fetched on demand and only here: it
        // is in no preset, so the toggle is the only door. Until it arrives the
        // layer draws the Carpenter & Anderson empirical profile and says so,
        // which is the same picture the site published before this artifact
        // existed rather than a blank.
        // The ring current has no artifact of its own: it is computed in the
        // plasmasphere simulation's published convection field, so it needs
        // exactly the same fetch and is unreachable without it.
        if (checked && layer === "ringCurrent") void this.loadPlasmasphere();
        // `solarWind` belongs in this list and its absence was a real defect.
        // Without the geospace bundle the tracers fall back to an axisymmetric
        // potential flow around a sphere: analytic, uniform, driven by nothing.
        // The published `projectedFlowStreamlines` — NOAA's own BATS-R-US
        // solution, whose description says it "follows slowing and deflection"
        // — was sitting in the artifact unread on the one layer where a reader
        // would look for it. Switching on the radiation belts happened to load
        // it, so the same site drew two different flow fields depending on an
        // unrelated toggle, and said nothing about which.
        // `plasmaSheet` belongs here for the same reason as the three below
        // it: its whole content is derived from this bundle's pressure and
        // |B| cuts, so without the fetch the layer would switch on and draw
        // nothing at all.
        if (checked && (layer === "geospace" || layer === "radiation"
            || layer === "plasmaSheet" || layer === "solarWind")) void this.loadGeospaceModel();
        // The empirical boundary annotation is a setting of the field layer,
        // and it dies with it: left on, it would keep drawing surfaces whose
        // only control is inside the now-hidden card. Driven through a real
        // click so its own listener clears the globe. The walkthrough is safe
        // because CHAIN_MANAGED_LAYERS sets `magnetosphere` after `geospace`,
        // so a step that wants the boundary alone re-enables it after this
        // cascade has run. The three overlay checkboxes keep their state:
        // the globe simply stops drawing their regions while the layer is off.
        if (!checked && layer === "geospace") {
          const empirical = byId<HTMLInputElement>("annotate-empirical-boundaries");
          if (empirical.checked) empirical.click();
        }
        this.updateEnvironmentLegend();
        // Switching a layer on reveals its controls and its key in place; make
        // sure the block the visitor just acted on is the one they can see.
        if (checked) {
          document
            .querySelector<HTMLElement>(`[data-layer-block="${layer}"]`)
            ?.scrollIntoView({ block: "nearest", behavior: "smooth" });
        }
      });
    });
    // The plasma-field layer's optional overlays. Each drives one or more of
    // the globe's named structure regions directly — they are settings of the
    // magnetosphere layer, not layers, so they have no rail row, no legend
    // card, and no place in any preset. All four start unchecked: the default
    // picture is the field alone, with nothing drawn on top.
    const structureOverlayBindings: Array<[string, readonly ("bowShock" | "magnetosheath" | "magnetopause" | "magneticField" | "flowStreamlines" | "flowTracers")[]]> = [
      ["geospace-field-lines", ["magneticField"]],
      ["geospace-flow-lines", ["flowStreamlines", "flowTracers"]],
      // Curves only, deliberately: the magnetosheath band is an area fill,
      // and the sheath is already the colour band the field itself draws
      // between these two curves. An annotation must stay thin.
      ["annotate-extracted-boundaries", ["bowShock", "magnetopause"]],
    ];
    structureOverlayBindings.forEach(([id, regions]) => {
      byId<HTMLInputElement>(id).addEventListener("change", (event) => {
        const checked = (event.currentTarget as HTMLInputElement).checked;
        regions.forEach((region) => this.globe.setStructureRegion(region, checked));
        if (checked) void this.loadGeospaceModel();
        this.updateEnvironmentLegend();
      });
    });
    // The embedded NOAA MHD cross-section: the real BATS-R-US plasma field,
    // drawn as a slice through the 3-D magnetosphere rather than as the
    // layer's face. The camera deliberately stays put — appearing as a slice
    // in the standing 3-D view is what makes it read as a cut through the
    // scene; the cross-section camera button is the face-on study view.
    // THE POLAR CUSPS: AN ANNOTATION LIKE THE TWO BOUNDARY SETS ABOVE IT.
    //
    // Sean, on the shipped build of 2026-08-26: "I see the polar cusps, but I
    // think what we should do is hide them, but have them able to be toggled
    // in the layer browser ... The cusps would only be shown in the legend and
    // on the screen if the user wants to see them." Both halves of that are
    // here: the globe stops building the funnels, and the legend row follows
    // because it is written from `getFieldLineCuspFunnelsDrawn()`, which is
    // set at the one statement that puts the mesh in the scene.
    //
    // Remembered across reloads, unlike the ticks above it — see
    // `CUSP_ANNOTATION_STORAGE_KEY` for why this one and not those.
    byId<HTMLInputElement>("annotate-polar-cusps").addEventListener("change", (event) => {
      const checked = (event.currentTarget as HTMLInputElement).checked;
      this.globe.setCuspFunnelsEnabled(checked);
      storageSet("local", CUSP_ANNOTATION_STORAGE_KEY, checked ? "1" : "0");
      this.environmentLegendFocus = "geospace";
      this.updateEnvironmentLegend();
    });
    byId<HTMLInputElement>("geospace-mhd-cut").addEventListener("change", (event) => {
      const checked = (event.currentTarget as HTMLInputElement).checked;
      this.globe.setMhdCutEnabled(checked);
      if (checked) void this.loadGeospaceModel();
      this.environmentLegendFocus = "geospace";
      this.updateEnvironmentLegend();
      this.updateGeospaceRuntimeUi(true);
    });
    byId("ground-station-clear").addEventListener("click", () => this.setSelectedStation(null));
    byId<HTMLSelectElement>("thermosphere-level").addEventListener("change", (event) => {
      const level = Number((event.currentTarget as HTMLSelectElement).value);
      if (!Number.isFinite(level) || level <= 0) return;
      // Recorded here as well as pushed into the globe, because the card's
      // words are written from this. Sean: "When I change Air density to follow
      // nothing changes." He was right twice over -- the drawn air is the whole
      // published column and correctly does not move with this control, and the
      // card's own sentence was hard-coded to 1e-12, so picking 1e-11 or 1e-13
      // changed three numbers while the paragraph under them went on naming a
      // level the reader had not chosen.
      this.thermosphereLevel = level;
      this.globe.setThermosphereLevel(level);
      this.updateEnvironmentLegend();
    });
    // One checkbox per named region, driven off the one band table so a
    // region can never exist in the settings and not in the shader.
    for (const band of IONOSPHERE_REGION_BANDS) {
      const box = byId<HTMLInputElement>(`ionosphere-region-${band.region.toLowerCase()}`);
      box.addEventListener("change", () => {
        this.ionosphereRegionsOn = { ...this.ionosphereRegionsOn, [band.region]: box.checked };
        this.globe.setIonosphereRegionsEnabled(this.ionosphereRegionsOn);
        this.updateEnvironmentLegend();
      });
    }
    byId("ionosphere-profile-pick").addEventListener("click", () => {
      this.setProfilePickArmed(!this.profilePickArmed);
    });
    // Escape cancels, the way every other mode and popover on this page does.
    window.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && this.profilePickArmed) this.setProfilePickArmed(false);
    });
    document.querySelectorAll<HTMLButtonElement>("[data-model-field]").forEach((button) => {
      button.addEventListener("click", () => {
        this.markActive("[data-model-field]", button);
        const field = button.dataset.modelField as GeospaceField;
        this.currentGeospaceField = field;
        this.globe.setGeospaceField(field);
        this.environmentLegendFocus = "geospace";
        this.updateGeospaceRuntimeUi(true);
      });
    });
    document.querySelectorAll<HTMLButtonElement>("[data-model-plane]").forEach((button) => {
      button.addEventListener("click", () => {
        this.markActive("[data-model-plane]", button);
        this.globe.setGeospacePlane(button.dataset.modelPlane as GeospacePlane | "both");
        this.updateGeospaceRuntimeUi(true);
      });
    });
    // The derived plasma-beta layer's own plane picker. Separate from
    // `[data-model-plane]` above on purpose: two layers, two presentations,
    // and changing one must not silently move the other.
    document.querySelectorAll<HTMLButtonElement>("[data-plasma-sheet-plane]").forEach((button) => {
      button.addEventListener("click", () => {
        this.markActive("[data-plasma-sheet-plane]", button);
        this.globe.setPlasmaSheetPlane(button.dataset.plasmaSheetPlane as GeospacePlane | "both");
        void this.loadGeospaceModel();
        this.environmentLegendFocus = "plasmaSheet";
        this.updateEnvironmentLegend();
      });
    });
    document.querySelectorAll<HTMLButtonElement>("[data-radiation-view]").forEach((button) => {
      button.addEventListener("click", () => {
        this.markActive("[data-radiation-view]", button);
        document.querySelectorAll<HTMLButtonElement>("[data-radiation-view]").forEach((choice) => {
          choice.setAttribute("aria-pressed", String(choice === button));
        });
        this.currentRadiationView = button.dataset.radiationView as RadiationBeltRuntimeView;
        this.globe.setRadiationView(this.currentRadiationView);
        this.environmentLegendFocus = "radiation";
        this.updateGeospaceRuntimeUi(true);
      });
    });
    document.querySelectorAll<HTMLButtonElement>("[data-radiation-energy]").forEach((button) => {
      button.addEventListener("click", () => {
        this.markActive("[data-radiation-energy]", button);
        const energy = Number(button.dataset.radiationEnergy);
        this.globe.setRadiationEnergy(energy);
        this.environmentLegendFocus = "radiation";
        this.updateGeospaceRuntimeUi(true);
      });
    });
    // The ring current's one setting: which plasma-sheet ion is followed. It
    // is a real physical choice rather than a display option — the whole point
    // of the layer is that the Alfven layer moves with energy, so changing it
    // moves the dashed boundary and re-colours every path.
    document.querySelectorAll<HTMLButtonElement>("[data-ring-current-energy]").forEach((button) => {
      button.addEventListener("click", () => {
        const energyKeV = Number(button.dataset.ringCurrentEnergy);
        const species = RING_CURRENT_ION_CHOICES.find((choice) => choice.referenceEnergyKeV === energyKeV);
        if (!species) return;
        this.markActive("[data-ring-current-energy]", button);
        this.ringCurrentSpecies = species;
        this.environmentLegendFocus = "ringCurrent";
        this.updateInnerMagnetosphere(this.simulationTime());
        this.updateEnvironmentLegend();
      });
    });
    byId<HTMLSelectElement>("radiation-pitch-select").addEventListener("change", (event) => {
      const pitchIndex = Number((event.currentTarget as HTMLSelectElement).value);
      // OMNIDIRECTIONAL_RADIATION_PITCH (-2) and ALL_RADIATION_PITCH_CHANNELS
      // (-1) are both legitimate selections here.
      if (!Number.isInteger(pitchIndex) || pitchIndex < OMNIDIRECTIONAL_RADIATION_PITCH) return;
      this.currentRadiationPitchIndex = pitchIndex;
      this.globe.setRadiationPitchIndex(pitchIndex);
      this.environmentLegendFocus = "radiation";
      this.updateGeospaceRuntimeUi(true);
    });

    // The owner list is audited separately and expected to grow, so it is
    // filterable in place. Hiding a row never changes whether it is selected.
    const ownerSearch = byId<HTMLInputElement>("owner-search");
    ownerSearch.addEventListener("input", () => {
      const query = ownerSearch.value.trim().toLowerCase();
      let shown = 0;
      document.querySelectorAll<HTMLElement>("#owner-filters label").forEach((label) => {
        const match = query.length === 0 || (label.textContent ?? "").toLowerCase().includes(query);
        label.hidden = !match;
        // Counted the way the reader sees it: a row the orbit band has taken
        // off the list is not a match they can act on.
        if (match && label.dataset.scope !== "out") shown += 1;
      });
      this.revealOwnerGroupsForSearch(query.length > 0);
      this.updateOwnerGroupVisibility();
      byId("owner-facet-empty").hidden = shown > 0;
    });
    // TWO INDEPENDENT TOGGLES, not a three-way picker: neither, either or both.
    // Both on means bands at the top level and A–Z inside each band. Neither on
    // is the flat list this rail has always had.
    const applyOwnerSort = () => {
      this.syncOwnerSortButtons();
      storageSet("local", OWNER_SORT_STORAGE_KEY, JSON.stringify({
        count: this.ownerSortByCount,
        alpha: this.ownerSortAlphabetically,
      }));
      this.renderOwnerGroups();
      // The search box owns `hidden` on the rows and the grouping owns the
      // headers. Re-running the live query is what keeps the two agreeing
      // across a regroup.
      ownerSearch.dispatchEvent(new Event("input"));
    };
    byId("owner-sort-count").addEventListener("click", () => {
      this.ownerSortByCount = !this.ownerSortByCount;
      applyOwnerSort();
    });
    byId("owner-sort-alpha").addEventListener("click", () => {
      this.ownerSortAlphabetically = !this.ownerSortAlphabetically;
      applyOwnerSort();
    });
    this.syncOwnerSortButtons();


    const search = byId<HTMLInputElement>("satellite-search");
    search.addEventListener("input", () => this.showSearchResults(search.value));
    search.addEventListener("focus", () => this.showSearchResults(search.value));
    search.addEventListener("keydown", (event) => {
      if (event.key === "Escape") this.hideSearchResults();
    });
    byId("search-results").addEventListener("scroll", (event) => {
      const results = event.currentTarget as HTMLElement;
      if (results.scrollTop + results.clientHeight >= results.scrollHeight - 80) this.appendSearchResults();
    });
    document.addEventListener("pointerdown", (event) => {
      if (!(event.target as Element).closest(".search-section")) this.hideSearchResults();
    });

    // NO PANEL-LEVEL X, AND NO "CLEAR SELECTED". Both emptied a LIST of chosen
    // spacecraft, and there is no list. Sean, 2026-08-28: "you'll just have the
    // card for the satellite. the favorite button is still there, and the X
    // just removes the plotted orbit and footprint and closes the card." The
    // card's own X — `[data-card-remove]`, bound in `buildSatelliteCard` — is
    // the whole of that gesture now, and it leaves the star alone exactly as it
    // always did. `fitStackControls` and its ResizeObserver went with the
    // three-cell View Selected / View All / Clear Selected bar they measured.
    byId("probe-load").addEventListener("click", () => this.loadProbeColumn());
    byId("probe-close").addEventListener("click", () => {
      this.probePoint = null;
      this.probeProfile = null;
      this.renderProbe();
    });
    // Path length changes only the secant applied to a foF2 already sampled,
    // so this redraws the readings without touching the column.
    byId("probe-range").addEventListener("change", () => {
      if (this.probeProfile) this.fillProbeReadings(this.probeProfile);
    });
    this.bindCardDrag();
    this.bindExplorerDrag();
    // The NOAA material lives on the awareness page now, not in a dialog —
    // one home for it, reachable from the rail and from the top nav.
    byId("swpc-outlook-open").addEventListener("click", () => this.openContent("now"));
    document.querySelectorAll<HTMLButtonElement>("[data-swpc-tab]").forEach((button) => {
      button.addEventListener("click", () => this.selectSwpcTab(button));
    });
    // The caret on a layer row, the map key's own fold, the conditions card,
    // and the "go to a time this layer covers" button in a no-data card.
    const mapKeyToggle = byId<HTMLButtonElement>("map-key-toggle");
    mapKeyToggle.addEventListener("click", () => {
      this.mapKeyCollapsed = !this.mapKeyCollapsed;
      storageSet("local", "space-explorer-map-key-collapsed-v1", this.mapKeyCollapsed ? "1" : "0");
      byId("map-key").classList.toggle("is-collapsed", this.mapKeyCollapsed);
      mapKeyToggle.setAttribute("aria-expanded", String(!this.mapKeyCollapsed));
      this.announceOccluderChange();
    });
    // A phone has no lower-right corner to spare, so the key opens folded to
    // its title bar there unless the visitor has said otherwise.
    const storedMapKey = storageGet("local", "space-explorer-map-key-collapsed-v1");
    this.mapKeyCollapsed = storedMapKey === null
      ? window.matchMedia("(max-width: 820px)").matches
      : storedMapKey === "1";
    mapKeyToggle.setAttribute("aria-expanded", String(!this.mapKeyCollapsed));
    // The conditions block is a rail section now, so it folds the way every
    // other rail section folds - a `details`, no script. The bespoke toggle it
    // used to carry inside the Data Explorer went with the move.
    document.querySelectorAll<HTMLElement>("#conditions-details [data-card-section]").forEach((section) => {
      section.toggleAttribute("open", this.cardSectionOpen[section.dataset.cardSection ?? ""] === true);
      this.bindCardSection(section);
    });
    // The Data Explorer has no switch: its presence follows the layers, and
    // only its collapsed/expanded state is a preference a visitor sets. The X
    // is the one control left on the panel besides that fold, and it does not
    // merely hide the window — it stops the plotting that made it appear.
    byId("data-viewer-close").addEventListener("click", () => this.closeDataExplorer());
    // EXPANDED unless this visitor folded it themselves. It used to open
    // folded to its one-line head, which was defensible while the rail carried
    // an evidence chip on every layer row: the claim was already on screen. It
    // is not any more - the chips went, because seven bordered tracked-caps
    // blocks were the loudest thing in the column - and this panel is where
    // the badge lives now. A panel that opens folded would mean a reader can
    // draw a MODEL layer and never be told it is one, which is the one thing
    // this site may not do.
    //
    // The key is v2 on purpose: a stored "collapsed" from before this change
    // would reintroduce exactly that hole for every returning visitor.
    this.explorerCollapsed = storageGet("local", "space-explorer-data-explorer-collapsed-v2") === "1";
    // The storm indicator. It is a disclosure in the top bar, so it closes on
    // Escape and on a click outside it, the way the other popovers here do.
    const stormChip = byId<HTMLButtonElement>("storm-chip");
    stormChip.addEventListener("click", () => {
      this.setStormDropdownOpen(byId("storm-dropdown").hidden);
    });
    byId("storm-dropdown-close").addEventListener("click", () => this.setStormDropdownOpen(false));
    byId("storm-show").addEventListener("click", () => this.showStormOnGlobe());
    byId("swpc-scale-conflict").addEventListener("click", () => {
      this.setStormDropdownOpen(true);
      byId("storm-reconcile").scrollIntoView({ block: "nearest" });
    });
    document.addEventListener("click", (event) => {
      if (byId("storm-dropdown").hidden) return;
      const target = event.target as Element;
      if (target.closest(".storm-shell") || target.closest("#swpc-scale-conflict")) return;
      this.setStormDropdownOpen(false);
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !byId("storm-dropdown").hidden) this.setStormDropdownOpen(false);
    });
    byId("key-cards").addEventListener("click", (event) => {
      const jump = (event.target as Element).closest<HTMLButtonElement>("[data-jump-utc]");
      if (!jump?.dataset.jumpUtc) return;
      // A time the reader picked, even though the card suggested it — so it
      // cancels any landing still pending on a layer whose fetch is in flight.
      this.noteReaderClockAction();
      this.seekToUtc(jump.dataset.jumpUtc);
    });
    byId("reset-view").addEventListener("click", () => this.globe.resetView());
    byId("zoom-in").addEventListener("click", () => this.globe.zoomBy(0.78));
    byId("zoom-out").addEventListener("click", () => this.globe.zoomBy(1.28));
    // Each of the three notes the angle it just set, which is what lets
    // `cameraTurnedByHand` tell a reader's own drag apart from the site's own
    // last move. Without it, pressing a camera button would read as a
    // hand-turn afterwards and would suppress the magnetosphere's pull-up
    // framing for the rest of the session.
    byId("sun-earth-view").addEventListener("click", () => { this.globe.focusSunEarthSideView(); this.noteSiteCameraOrientation(); });
    // The two views every textbook figure of the magnetosphere uses: the
    // noon-midnight cut, and straight down over the pole with noon at the top.
    byId("cross-section-view").addEventListener("click", () => { this.globe.focusMeridionalCrossSection(); this.noteSiteCameraOrientation(); });
    byId("polar-view").addEventListener("click", () => { this.globe.focusPolarView(); this.noteSiteCameraOrientation(); });
    byId<HTMLInputElement>("magnetopause-cut").addEventListener("change", (event) => {
      const cut = (event.currentTarget as HTMLInputElement).checked;
      this.globe.setMagnetopauseDisplay(cut ? "cross-section" : "surface");
      // No camera move. This used to swing the scene to the meridional
      // cross-section, which is the same "the site decides for you" defect the
      // layer toggles above were carrying, and here it did not even buy the
      // better picture: the cut draws profile curves in TWO planes, and the
      // meridional camera puts the equatorial one exactly edge-on, so half of
      // what the setting just switched on becomes a line. An oblique view
      // shows both. A reader who wants the textbook cut has the
      // cross-section button under the globe.
      this.updateEnvironmentLegend();
    });
    byId("time-play").addEventListener("click", () => this.toggleTime());
    byId("time-now").addEventListener("click", () => this.returnToNow());
    const playbackSettings = byId("time-playback-settings");
    const playbackToggle = byId<HTMLButtonElement>("time-playback-toggle");
    const playbackHud = playbackSettings.closest(".scene-hud--bottom");
    const closePlaybackSettings = () => {
      playbackSettings.hidden = true;
      playbackHud?.classList.remove("has-open-popover");
      playbackToggle.setAttribute("aria-expanded", "false");
    };
    playbackToggle.addEventListener("click", () => {
      const open = playbackSettings.hidden;
      playbackSettings.hidden = !open;
      playbackHud?.classList.toggle("has-open-popover", open);
      playbackToggle.setAttribute("aria-expanded", String(open));
    });
    byId("time-playback-close").addEventListener("click", closePlaybackSettings);
    const playbackDuration = byId<HTMLSelectElement>("time-playback-duration");
    const playbackPace = byId<HTMLSelectElement>("time-playback-pace");
    const savedPlaybackDuration = storageGet("local", "space-explorer-playback-duration-v1");
    const savedPlaybackPace = storageGet("local", "space-explorer-playback-pace-v1");
    if (["30", "120", "360", "1440"].includes(savedPlaybackDuration ?? "")) playbackDuration.value = savedPlaybackDuration!;
    if (["60000", "30000", "15000", "8000"].includes(savedPlaybackPace ?? "")) playbackPace.value = savedPlaybackPace!;
    playbackDuration.addEventListener("change", () => storageSet("local", "space-explorer-playback-duration-v1", playbackDuration.value));
    const updatePlaybackSummary = () => {
      const seconds = Math.round(Number(playbackPace.value) / 1000);
      byId("time-playback-summary").textContent = `Runs the selected span in ${seconds} real seconds. Pause at any point with the timeline button.`;
      storageSet("local", "space-explorer-playback-pace-v1", playbackPace.value);
    };
    playbackPace.addEventListener("change", updatePlaybackSummary);
    updatePlaybackSummary();
    byId("time-playback-start").addEventListener("click", () => {
      this.startTimedPlayback(Number(playbackDuration.value), Number(playbackPace.value));
      closePlaybackSettings();
    });
    const timeSlider = byId<HTMLInputElement>("time-slider");
    const revealTimelineTooltip = () => {
      window.clearTimeout(this.timelineTooltipHideTimer);
      this.timelineTooltipVisible = true;
      this.updateTimelineTooltip();
    };
    const scheduleTimelineTooltipHide = () => {
      window.clearTimeout(this.timelineTooltipHideTimer);
      this.timelineTooltipHideTimer = window.setTimeout(() => {
        this.timelineTooltipVisible = false;
        byId("time-slider-tooltip").classList.remove("is-visible");
      }, 900);
    };
    timeSlider.addEventListener("input", (event) => {
      revealTimelineTooltip();
      this.noteReaderClockAction();
      this.timedPlayback = null;
      this.timeOffsetMinutes = Number((event.currentTarget as HTMLInputElement).value);
      if (this.pausedAt) this.pausedAt = new Date(Date.now() + this.timeOffsetMinutes * 60000);
      this.seekSatelliteTime();
      this.refreshSelectedGeometry();
    });
    timeSlider.addEventListener("pointerdown", revealTimelineTooltip);
    timeSlider.addEventListener("pointerup", scheduleTimelineTooltipHide);
    timeSlider.addEventListener("focus", revealTimelineTooltip);
    timeSlider.addEventListener("blur", scheduleTimelineTooltipHide);
    window.addEventListener("resize", () => { if (this.timelineTooltipVisible) this.updateTimelineTooltip(); });
    const displaySettings = byId("display-settings");
    const displayToggle = byId<HTMLButtonElement>("display-settings-toggle");
    const closeDisplaySettings = () => {
      displaySettings.hidden = true;
      displayToggle.setAttribute("aria-expanded", "false");
    };
    displayToggle.addEventListener("click", () => {
      const open = displaySettings.hidden;
      displaySettings.hidden = !open;
      displayToggle.setAttribute("aria-expanded", String(open));
    });
    byId("display-settings-close").addEventListener("click", closeDisplaySettings);
    document.querySelectorAll<HTMLButtonElement>("[data-rendering-profile]").forEach((button) => {
      button.addEventListener("click", () => {
        this.renderingProfile = button.dataset.renderingProfile as RenderingProfile;
        this.markActive("[data-rendering-profile]", button);
        this.applyDisplaySettings();
      });
    });
    document.querySelectorAll<HTMLButtonElement>("[data-marker-size]").forEach((button) => {
      button.addEventListener("click", () => {
        this.markerSize = button.dataset.markerSize as MarkerSize;
        this.markActive("[data-marker-size]", button);
        this.applyDisplaySettings();
      });
    });
    document.querySelectorAll<HTMLButtonElement>("[data-interface-scale]").forEach((button) => {
      button.addEventListener("click", () => {
        this.interfaceScale = button.dataset.interfaceScale as InterfaceScale;
        this.markActive("[data-interface-scale]", button);
        this.applyDisplaySettings();
      });
    });
    document.querySelectorAll<HTMLButtonElement>("[data-motion-rate]").forEach((button) => {
      button.addEventListener("click", () => {
        this.motionRate = button.dataset.motionRate as MotionRate;
        this.markActive("[data-motion-rate]", button);
        this.applyDisplaySettings();
      });
    });
    document.querySelectorAll<HTMLButtonElement>("[data-color-mode]").forEach((button) => {
      button.addEventListener("click", () => {
        this.colorMode = button.dataset.colorMode as ColorMode;
        this.markActive("[data-color-mode]", button);
        this.applyDisplaySettings();
        this.updateSatelliteColorEncoding();
      });
    });
    document.querySelectorAll<HTMLButtonElement>("[data-reference-frame]").forEach((button) => {
      button.addEventListener("click", () => {
        this.referenceFrame = button.dataset.referenceFrame as ReferenceFrame;
        this.markActive("[data-reference-frame]", button);
        this.applyDisplaySettings();
        this.applySelectedGeometry();
      });
    });
    document.querySelectorAll<HTMLButtonElement>("[data-field-rendering]").forEach((button) => {
      button.addEventListener("click", () => {
        this.fieldRendering = button.dataset.fieldRendering as FieldRendering;
        this.markActive("[data-field-rendering]", button);
        this.applyDisplaySettings();
        this.updateGeospaceRuntimeUi(true);
      });
    });
    // The selected-spacecraft geometry controls. They were bound when the
    // shared geometry block was first cloned into a card; the block is gone and
    // they are ordinary Display settings now, so they bind with the rest.
    document.querySelectorAll<HTMLButtonElement>("[data-geometry]").forEach((button) => {
      button.addEventListener("click", () => {
        this.geometryMode = button.dataset.geometry as GeometryMode;
        this.markActive("[data-geometry]", button);
        this.applySelectedGeometry();
      });
    });
    document.querySelectorAll<HTMLButtonElement>("[data-footprint-elevation]").forEach((button) => {
      button.addEventListener("click", () => {
        this.footprintMinElevationDeg = Number(button.dataset.footprintElevation ?? "0");
        this.markActive("[data-footprint-elevation]", button);
        this.globe.setFootprintMinElevation(this.footprintMinElevationDeg);
        this.updateFootprintElevationNote();
        this.refreshSelectedGeometry();
      });
    });
    document.querySelectorAll<HTMLButtonElement>("[data-distance-scale]").forEach((button) => {
      button.addEventListener("click", () => {
        const parsed = parseDistanceScale(button.dataset.distanceScale);
        if (!parsed) return;
        this.distanceScale = parsed;
        this.markActive("[data-distance-scale]", button);
        this.applyDisplaySettings();
      });
    });
    const displayOptionBindings: Array<[string, "displayStars" | "displayEnvironmentMotion" | "displaySatelliteLabels"]> = [
      ["display-stars", "displayStars"],
      ["display-environment-motion", "displayEnvironmentMotion"],
      ["display-satellite-labels", "displaySatelliteLabels"],
    ];
    displayOptionBindings.forEach(([id, property]) => {
      byId<HTMLInputElement>(id).addEventListener("change", (event) => {
        this[property] = (event.currentTarget as HTMLInputElement).checked;
        this.applyDisplaySettings();
      });
    });
    document.addEventListener("pointerdown", (event) => {
      const target = event.target as Element;
      if (!displaySettings.hidden && !target.closest("#display-settings") && !target.closest("#display-settings-toggle")) closeDisplaySettings();
      if (!playbackSettings.hidden && !target.closest("#time-playback-settings") && !target.closest("#time-playback-toggle")) closePlaybackSettings();
    });
    // THE FOUR CONTROLS THAT OPEN A RAIL: two doors at the top of the phone,
    // two tabs on the right edge of the desktop, one rule.
    //
    // Sean, 2026-08-28: "if someone clicks satellites it brings up the
    // satellite rail and the satellites button toggles solid blue and the text
    // changes to Close Panel. hitting Close Panel closes it and the button
    // toggles back to black." And: "if one panel is, say satellites, and i
    // click the other, say space weather, the satellite panel goes down and the
    // [space weather] panel comes up."
    //
    // So each control owns exactly one panel: pressing it while ITS panel is
    // open closes it, and pressing it while the OTHER panel is open switches.
    // `#mobile-panel-toggle` used to close the sheet whatever was in it, which
    // is what made the satellites door read "Close panel" over an open space
    // weather panel — one button claiming to close a panel it had not opened.
    const railControls: Array<[string, "satellites" | "environment"]> = [
      ["mobile-panel-toggle", "satellites"],
      ["mobile-weather-toggle", "environment"],
      ["rail-tab-satellites", "satellites"],
      ["rail-tab-environment", "environment"],
    ];
    railControls.forEach(([id, section]) => {
      byId<HTMLButtonElement>(id).addEventListener("click", () => {
        if (this.mobilePanelSection === section) this.closeMobilePanel();
        else this.openMobilePanel(section);
      });
    });
    // Rotating a phone into landscape crosses 820 px into the desktop layout,
    // and back again on the way home. Both directions have real work to do:
    // the page furniture this surface does not carry has to come back, and the
    // layer cards have to move between the panel and the window over the globe.
    this.phoneChromeQuery.addEventListener("change", () => {
      this.applyPhonePageStrip();
      // The two hosts hold the same nodes, so the order guard has to be told
      // that the host itself changed, not just what is in it.
      this.layerCardOrder = "";
      this.updateEnvironmentLegend();
      this.syncMobileTabs();
      // Rotating out of the phone layout takes the reader's dragged card
      // height off with it; rotating back puts it on again, re-clamped to the
      // scene it now has.
      this.applyStackHeight();
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        this.closeMobilePanel();
        closeDisplaySettings();
        closePlaybackSettings();
      }
    });

    document.querySelectorAll<HTMLButtonElement>("[data-view]").forEach((button) => {
      button.addEventListener("click", () => {
        this.closeMobilePanel();
        this.openContent(button.dataset.view ?? "explore");
      });
    });
    byId("content-close").addEventListener("click", () => this.closeContent());

    // BACK AND FORWARD. `popstate` fires for both, and for a hash the reader
    // typed or pasted, so all three arrive on one path. A null state is a
    // deep link into a fresh tab rather than a return to something this
    // session pushed, which is why the hash is the fallback and not an error.
    window.addEventListener("popstate", (event) => {
      this.applyNav((event.state as NavState | null) ?? this.navFromHash());
    });

    // A shared or reloaded URL has to land where it says. The entry is
    // REPLACED rather than pushed: the first paint is not somewhere the reader
    // navigated to, and pushing here would put a phantom step behind them.
    const opening = this.navFromHash();
    window.history.replaceState(opening, "", this.navUrl(opening));
    if (opening.view !== "explore") this.applyNav(opening);

    this.bindEventDialog();
  }

  /** Which facet values exist inside the live orbit band, and how many
   *  objects each of them has there. The band is the universe; this is what it
   *  contains. Everything the rail draws — which rows are offered, the counts
   *  beside them, and the all/none/N-of-M chips — is read off this and only
   *  this, so the boxes cannot describe a catalog the reader is not in. */
  private scopedFacetOptions(): Record<FacetName, Map<string, number>> {
    const options: Record<FacetName, Map<string, number>> = {
      mission: new Map(),
      constellation: new Map(),
      owner: new Map(),
    };
    const bump = (map: Map<string, number>, key: string) => map.set(key, (map.get(key) ?? 0) + 1);
    this.catalog.satellites.forEach((satellite) => {
      if (!this.orbitAllows(satellite)) return;
      bump(options.mission, missionFacet(satellite));
      bump(options.constellation, satellite.constellation ?? INDEPENDENT_CONSTELLATION);
      bump(options.owner, satellite.organization);
    });
    return options;
  }

  /**
   * RE-DERIVES ALL THREE BOXES FROM THE BAND. Sean: "if I click LEO, the page
   * will only show LEO satellites… [the others] are ways you can sort
   * ALL/LEO/MEO/GEO/HEO satellites… They just have to auto update."
   *
   * The three facets are PEERS — none gates another — and every one of them
   * rescopes off the band alone. A value with nothing in the band is taken off
   * its grid AND out of the selection, because an option the reader cannot see
   * must not be quietly constraining what they can.
   *
   * `data-scope` rather than `hidden`: the owner box is also filtered by its
   * own search field, which owns `hidden`. Two independent reasons to hide a
   * row need two independent attributes or they overwrite each other.
   */
  private rescopeFacetGrids() {
    const options = this.scopedFacetOptions();
    this.scopedOptions = options;
    const apply = (
      selector: string,
      facet: FacetName,
      valueOf: (input: HTMLInputElement) => string,
      selected: Set<string>,
      withCount: boolean,
    ) => {
      document.querySelectorAll<HTMLInputElement>(selector).forEach((input) => {
        const value = valueOf(input);
        const count = options[facet].get(value) ?? 0;
        const label = input.closest("label");
        if (label) label.dataset.scope = count === 0 ? "out" : "in";
        if (count === 0) {
          selected.delete(value);
          input.checked = false;
          return;
        }
        if (!withCount) return;
        const slot = label?.querySelector(".facet-count");
        if (slot) slot.textContent = `(${count.toLocaleString()})`;
      });
    };
    apply("[data-mission-facet]", "mission", (i) => i.dataset.missionFacet ?? "other", this.enabledMissionFacets, false);
    apply("[data-constellation]", "constellation", (i) => i.dataset.constellation ?? INDEPENDENT_CONSTELLATION, this.enabledConstellations, true);
    apply("[data-owner]", "owner", (i) => i.dataset.owner ?? "", this.enabledOwners, true);
    // The owner facet only constrains organizations its grid actually lists,
    // so the list has to shrink with the band too — otherwise an owner that
    // exists only outside LEO would go on excluding objects inside it.
    this.visibleOwnerFilters = new Set(options.owner.keys());
    // The bands are cut by the counts on the rows, and those counts just
    // changed, so the arrangement is re-derived here rather than left
    // describing the previous band.
    this.renderOwnerGroups();
    this.updateOwnerGroupVisibility();
  }

  /**
   * WHAT EACH ROW IS WORTH RIGHT NOW, and the number means two different
   * things depending on whether the row is ticked — because the two clicks
   * available on it do two different things.
   *
   *  - A TICKED row is counted under the other two lists. That is how many of
   *    its satellites are drawn, and therefore exactly how many go off the
   *    viewer when the reader unticks it. This is the number Sean asked for:
   *    tick MILSATCOM, and every owner row states its MILSATCOM count, so
   *    "Russian Ministry of Defence (assessed) (50)" is on screen before he
   *    deselects the other 30 organizations.
   *
   *  - An UNTICKED row is counted under the orbit band alone. A positive click
   *    LINKS, so ticking it opens the other two lists to everything that value
   *    carries: the whole in-band population of that value is what the click
   *    delivers, and any smaller number here would understate it.
   *
   * Both numbers are exactly true of the click sitting beside them, which is
   * the only property this function has to have. One pass over the in-band
   * catalog for all three grids.
   */
  private contextualFacetCounts(): Record<FacetName, Map<string, number>> {
    const counts: Record<FacetName, Map<string, number>> = { mission: new Map(), constellation: new Map(), owner: new Map() };
    const bump = (map: Map<string, number>, key: string) => map.set(key, (map.get(key) ?? 0) + 1);
    this.catalog.satellites.forEach((satellite) => {
      if (!this.orbitAllows(satellite)) return;
      const mission = missionFacet(satellite);
      const fleet = satellite.constellation ?? INDEPENDENT_CONSTELLATION;
      const owner = satellite.organization;
      const missionOn = this.enabledMissionFacets.has(mission);
      const fleetOn = this.enabledConstellations.has(fleet);
      // The owner list only constrains organizations its own grid lists.
      const ownerOn = !this.visibleOwnerFilters.has(owner) || this.enabledOwners.has(owner);
      if (missionOn ? (fleetOn && ownerOn) : true) bump(counts.mission, mission);
      if (fleetOn ? (missionOn && ownerOn) : true) bump(counts.constellation, fleet);
      if (ownerOn ? (missionOn && fleetOn) : true) bump(counts.owner, owner);
    });
    return counts;
  }

  /**
   * Writes those numbers onto the rows, and dims — never hides — a row worth
   * zero. Hiding was the other option and it is the wrong one here: the orbit
   * band may hide a value because the value genuinely is not in the band, but
   * the three facets are PEERS, and a peer that deletes another peer's options
   * as you click turns a filter into a wizard. A dimmed row with a 0 on it
   * still says the value exists, still says what clicking it would get you,
   * and is still clickable if that is what the reader wants.
   */
  private paintFacetContext() {
    const counts = this.contextualFacetCounts();
    const band = this.scopedOptions ?? this.scopedFacetOptions();
    const paint = (selector: string, facet: FacetName, valueOf: (input: HTMLInputElement) => string) => {
      document.querySelectorAll<HTMLInputElement>(selector).forEach((input) => {
        const value = valueOf(input);
        const label = input.closest("label");
        if (!label || label.dataset.scope === "out") return;
        const here = counts[facet].get(value) ?? 0;
        const inBand = band[facet].get(value) ?? 0;
        label.dataset.context = here === 0 ? "none" : "some";
        const text = label.querySelector("span");
        const slot = label.querySelector(".facet-count");
        if (!text?.title || !slot) return;
        slot.textContent = `(${here.toLocaleString()})`;
        // The tooltip says which of the two readings this is, in words, so the
        // number never has to be guessed at.
        label.title = input.checked
          ? (here === inBand
            ? `${text.title}: all ${inBand.toLocaleString()} drawn`
            : `${text.title}: ${here.toLocaleString()} of ${inBand.toLocaleString()} drawn under your other selections`)
          : `${text.title}: ${inBand.toLocaleString()} to add`;
      });
    };
    paint("[data-mission-facet]", "mission", (i) => i.dataset.missionFacet ?? "other");
    paint("[data-constellation]", "constellation", (i) => i.dataset.constellation ?? INDEPENDENT_CONSTELLATION);
    paint("[data-owner]", "owner", (i) => i.dataset.owner ?? "");
  }

  /** Selected and available per facet, both counted inside the live band. */
  private scopedFacetCounts(): { selected: Record<FacetName, number>; available: Record<FacetName, number> } {
    const options = this.scopedOptions ?? this.scopedFacetOptions();
    const within = (selected: Set<string>, facet: FacetName) =>
      [...selected].filter((value) => options[facet].has(value)).length;
    return {
      selected: {
        mission: within(this.enabledMissionFacets, "mission"),
        constellation: within(this.enabledConstellations, "constellation"),
        owner: within(this.enabledOwners, "owner"),
      },
      available: {
        mission: options.mission.size,
        constellation: options.constellation.size,
        owner: options.owner.size,
      },
    };
  }

  /**
   * Applies today's featured constellation, as a facet selection and nothing
   * more. The orbit band is untouched — it stays unset, so no band button is
   * lit over a globe the reader has not filtered.
   */
  /**
   * CONSTELLATION OF THE DAY, said once on arrival and then out of the way.
   *
   * Sean asked for "a window that briefly pops up somewhere discreet but that
   * will be seen". It replaces the `Today: …` line that used to sit under the
   * search box, which was in the one place a reader arriving at a globe never
   * looks. Everything about its behaviour is about not being a nuisance and
   * not being a trap:
   *
   *  - ten seconds, then it goes on its own;
   *  - an X, for the reader who wants it gone now;
   *  - a click anywhere else takes it down, because it is a note and not a
   *    dialog and it must never stand between the reader and the globe;
   *  - a click INSIDE it cancels that ten-second clock PERMANENTLY. That is
   *    the whole point. A reader who has started reading must not have it
   *    yanked away mid-sentence, so from that moment only the X or Escape
   *    closes it, and an outside click no longer does.
   *
   * It is an ANNOUNCEMENT, not a dialog: `role="status"` with `aria-live`
   * on the shell, no focus stolen on load, no focus trap, Escape closes.
   *
   * The prose comes from bigmem's daily model-written blurb when that blurb is
   * about the constellation the rotation actually picked today; otherwise from
   * a sentence measured off the catalog rows. See `featuredToastText`. A failed
   * or missing fetch is an ordinary state — it is caught here and never reaches
   * the caller, so it cannot delay or break the page load or the globe.
   */
  /** ONCE A DAY, not once a load. Sean: "it should show up on the users first
   *  load of the day". The stamp is the UTC day the note was last SHOWN — set
   *  when it actually reaches the screen, not when it is scheduled, because a
   *  note that waited behind the welcome modal and never appeared has not been
   *  read. localStorage throws outright in some privacy modes, so both halves
   *  fail open: unreadable storage shows the note rather than swallowing it. */
  private static readonly featuredToastDayKey = "space-explorer-featured-toast-day-v1";

  private featuredToastSeenToday(day: string): boolean {
    try {
      return window.localStorage.getItem(ExplorerApp.featuredToastDayKey) === day;
    } catch {
      return false;
    }
  }

  private markFeaturedToastSeen() {
    if (!this.featuredToastDay) return;
    try {
      window.localStorage.setItem(ExplorerApp.featuredToastDayKey, this.featuredToastDay);
    } catch {
      /* Private mode. The note simply shows again next load. */
    }
  }

  private async announceFeaturedConstellation(pick: FeaturedConstellation) {
    const day = utcIsoDay(new Date());
    if (this.featuredToastSeenToday(day)) return;
    this.featuredToastDay = day;
    let blurb: unknown = null;
    try {
      const response = await fetch(
        new URL("data/featured-constellation.json", document.baseURI),
        { cache: "no-cache" },
      );
      if (response.ok) blurb = await response.json();
    } catch {
      blurb = null;
    }
    const said = featuredToastText(pick, this.catalog.satellites, blurb, utcIsoDay(new Date()));
    this.scheduleFeaturedToast(said.text, said.kind);
  }

  private scheduleFeaturedToast(text: string, kind: string) {
    const toast = document.getElementById("featured-toast");
    const body = document.getElementById("featured-toast-text");
    if (!toast || !body) return;
    body.textContent = text;
    toast.dataset.textKind = kind;
    const show = () => this.openFeaturedToast(toast);
    // The first-visit welcome is a MODAL, opened 250 ms after boot, and it
    // makes everything behind it inert. Popping the note up behind it would
    // spend its ten seconds where nobody could read it or reach its X, so it
    // waits for the modal to close and then appears against the globe.
    window.setTimeout(() => {
      const welcome = document.getElementById("welcome-dialog") as HTMLDialogElement | null;
      if (welcome?.open) {
        welcome.addEventListener("close", () => window.setTimeout(show, 300), { once: true });
        return;
      }
      show();
    }, 400);
  }

  private openFeaturedToast(toast: HTMLElement) {
    toast.hidden = false;
    this.markFeaturedToastSeen();
    this.featuredToastTimer = window.setTimeout(
      () => this.dismissFeaturedToast(),
      ExplorerApp.featuredToastMs,
    );
    // Painted off a deadline rather than counted down, so a throttled
    // background tab cannot leave the number disagreeing with the timeout
    // that actually closes the note. Repainted faster than it changes so the
    // digit turns over when the second does.
    const deadline = Date.now() + ExplorerApp.featuredToastMs;
    const counter = document.getElementById("featured-toast-count");
    const paint = () => {
      if (!counter) return;
      counter.textContent = `${Math.max(0, Math.ceil((deadline - Date.now()) / 1000))}s`;
    };
    paint();
    this.featuredToastTick = window.setInterval(paint, 250);
    if (this.featuredToastBound) return;
    this.featuredToastBound = true;
    document.getElementById("featured-toast-close")
      ?.addEventListener("click", () => this.dismissFeaturedToast());
    // Capture phase, so the note answers the press before anything underneath
    // it does. A press on the X pins first and closes on the click that
    // follows, which is the same outcome by a shorter route.
    document.addEventListener("pointerdown", (event) => {
      if (toast.hidden) return;
      if ((event.target as Element | null)?.closest("#featured-toast")) {
        this.pinFeaturedToast();
        return;
      }
      if (!this.featuredToastPinned) this.dismissFeaturedToast();
    }, true);
    document.addEventListener("keydown", (event) => {
      if (!toast.hidden && event.key === "Escape") this.dismissFeaturedToast();
    });
  }

  /** The reader is reading it. The clock stops for good. */
  private pinFeaturedToast() {
    if (this.featuredToastPinned) return;
    this.featuredToastPinned = true;
    window.clearTimeout(this.featuredToastTimer);
    this.featuredToastTimer = 0;
    window.clearInterval(this.featuredToastTick);
    this.featuredToastTick = 0;
    document.getElementById("featured-toast")?.classList.add("is-pinned");
  }

  private dismissFeaturedToast() {
    window.clearTimeout(this.featuredToastTimer);
    this.featuredToastTimer = 0;
    window.clearInterval(this.featuredToastTick);
    this.featuredToastTick = 0;
    const toast = document.getElementById("featured-toast");
    if (toast) toast.hidden = true;
  }

  private applyFeaturedConstellation() {
    const pick = featuredConstellation(this.catalog.satellites, utcDayNumber(new Date()));
    if (!pick) return;
    void this.announceFeaturedConstellation(pick);
    this.enabledMissionFacets.clear();
    this.enabledConstellations = new Set([pick.constellation]);
    this.enabledOwners.clear();
    // Through the same healing every reader click goes through, so mission and
    // owner end up holding exactly what these objects carry and the boxes
    // describe the drawn set rather than a hand-written guess at it.
    this.linkCatalogFilters("select", "constellation", pick.constellation, pick.constellation);
    this.filterLinkNote = null;
  }

  /* `selectAllFacets()` IS GONE. It ticked every in-band row in all three
     lists, and the two callers that wanted it were the orbit band and the GEO
     subtype — both of which Sean has now ruled are top-level filters that
     select nothing: "when a user hits one of those, nothing happens". Nothing
     else asked for an "everything" state, and with linking there is no longer
     a reason to build one: a reader who wants a whole population ticks the one
     value that names it. */

  /**
   * The band buttons light from the scope rather than from the click, because
   * `null` has to be drawable: NO button active. `markActive()` cannot express
   * that — it always leaves exactly one element lit — which is precisely how
   * "even All shouldn't be selected" kept coming back.
   */
  private markOrbitScope() {
    document.querySelectorAll<HTMLButtonElement>("[data-orbit]").forEach((button) => {
      const live = this.orbitScope !== null && button.dataset.orbit === this.orbitScope;
      button.classList.toggle("is-active", live);
      button.setAttribute("aria-pressed", String(live));
    });
  }

  private markActive(selector: string, active: HTMLElement) {
    document.querySelectorAll(selector).forEach((element) => element.classList.toggle("is-active", element === active));
  }

  private restoreDisplaySettings() {
    const saved = storageGet("local", "space-explorer-display-v1");
    if (saved) {
      try {
        const settings = JSON.parse(saved) as Partial<{
          profile: RenderingProfile;
          markerSize: MarkerSize;
          motionRate: MotionRate;
          colorMode: ColorMode;
          interfaceScale: InterfaceScale;
          referenceFrame: ReferenceFrame;
          fieldRendering: FieldRendering;
          distanceScale: string;
          stars: boolean;
          starsChosen: boolean;
          environmentalMotion: boolean;
          satelliteLabels: boolean;
        }>;
        if (["auto", "efficient", "quality"].includes(settings.profile ?? "")) this.renderingProfile = settings.profile!;
        if (["compact", "standard", "large"].includes(settings.markerSize ?? "")) this.markerSize = settings.markerSize!;
        if (["adaptive", "60", "30", "20"].includes(settings.motionRate ?? "")) this.motionRate = settings.motionRate!;
        if (["mission", "constellation", "country"].includes(settings.colorMode ?? "")) this.colorMode = settings.colorMode!;
        if (["standard", "large", "largest"].includes(settings.interfaceScale ?? "")) this.interfaceScale = settings.interfaceScale!;
        if (["earth-fixed", "inertial"].includes(settings.referenceFrame ?? "")) this.referenceFrame = settings.referenceFrame!;
        if (["smooth", "native"].includes(settings.fieldRendering ?? "")) this.fieldRendering = settings.fieldRendering!;
        this.distanceScale = parseDistanceScale(settings.distanceScale) ?? this.distanceScale;
        // `stars` (v1) is deliberately not restored: it defaulted to true for
        // every visitor, so a saved true records the old default, not a
        // choice. Only the post-default-flip key carries user intent.
        if (typeof settings.starsChosen === "boolean") this.displayStars = settings.starsChosen;
        this.displayEnvironmentMotion = initialEnvironmentMotion(settings.environmentalMotion, prefersReducedMotion());
        if (typeof settings.satelliteLabels === "boolean") this.displaySatelliteLabels = settings.satelliteLabels;
      } catch {
        // Ignore malformed or obsolete user preferences.
      }
    }
    document.querySelectorAll<HTMLElement>("[data-rendering-profile]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.renderingProfile === this.renderingProfile);
    });
    document.querySelectorAll<HTMLElement>("[data-marker-size]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.markerSize === this.markerSize);
    });
    document.querySelectorAll<HTMLElement>("[data-motion-rate]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.motionRate === this.motionRate);
    });
    document.querySelectorAll<HTMLElement>("[data-color-mode]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.colorMode === this.colorMode);
    });
    document.querySelectorAll<HTMLElement>("[data-interface-scale]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.interfaceScale === this.interfaceScale);
    });
    document.querySelectorAll<HTMLElement>("[data-reference-frame]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.referenceFrame === this.referenceFrame);
    });
    document.querySelectorAll<HTMLElement>("[data-field-rendering]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.fieldRendering === this.fieldRendering);
    });
    document.querySelectorAll<HTMLElement>("[data-distance-scale]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.distanceScale === this.distanceScale);
    });
    byId<HTMLInputElement>("display-stars").checked = this.displayStars;
    byId<HTMLInputElement>("display-environment-motion").checked = this.displayEnvironmentMotion;
    byId<HTMLInputElement>("display-satellite-labels").checked = this.displaySatelliteLabels;
    this.applyDisplaySettings();
  }

  private applyDisplaySettings() {
    const navigatorWithMemory = navigator as Navigator & { deviceMemory?: number };
    const constrainedDevice = navigator.hardwareConcurrency <= 4 || (navigatorWithMemory.deviceMemory ?? 8) <= 4;
    const effectiveProfile = this.renderingProfile === "auto"
      ? constrainedDevice ? "efficient" : "quality"
      : this.renderingProfile;
    const profileFrameRate = effectiveProfile === "efficient" ? 30 : 60;
    const maximumFrameRate = this.motionRate === "adaptive" ? profileFrameRate : Number(this.motionRate);
    const pixelRatioCap = effectiveProfile === "efficient" ? 1 : this.renderingProfile === "quality" ? 1.75 : 1.5;
    const satellitePointSize = this.markerSize === "compact" ? 2.8 : this.markerSize === "large" ? 5 : 3.7;
    this.globe.setRenderingOptions({
      pixelRatioCap,
      maximumFrameRate,
      stars: this.displayStars,
      environmentalMotion: this.displayEnvironmentMotion,
      satelliteLabels: this.displaySatelliteLabels,
      satellitePointSize,
    });
    this.globe.setReferenceFrame(this.referenceFrame);
    this.globe.setFieldRendering(this.fieldRendering);
    this.globe.setDistanceScale(this.distanceScale);
    // The orbit line's vertices are placed against whichever ruler is live —
    // the globe's own rebuild re-maps the existing vertices but cannot add the
    // ones the other scale needs — so a scale change re-samples the path.
    if (this.distanceScale !== this.sampledDistanceScale) {
      this.sampledDistanceScale = this.distanceScale;
      this.refreshSelectedGeometry();
    }
    this.applyDistanceScaleWording();
    document.documentElement.dataset.interfaceScale = this.interfaceScale;
    const frameNote = this.referenceFrame === "inertial"
      ? "Inertial keeps the star frame fixed while Earth, geography, and Earth-fixed fields rotate consistently."
      : "Earth-fixed keeps geography stationary. Motion rate changes redraw frequency, not ephemeris or source data.";
    const fieldNote = this.fieldRendering === "smooth"
      ? "Smooth fields interpolate display samples without changing source values."
      : "Native grid exposes published/reduced cells and samples.";
    byId("reference-frame-note").textContent = `${frameNote} ${fieldNote} ${distanceScaleStrings(this.distanceScale).settingsNote}`;
    const motionLabel = this.motionRate === "adaptive" ? `ADAPTIVE ${maximumFrameRate}` : this.motionRate;
    byId("display-profile-status").textContent = `${this.renderingProfile.toUpperCase()} · ${motionLabel} FPS · ${pixelRatioCap.toFixed(2).replace(/\.00$/, "")}× PIXEL DENSITY`;
    storageSet("local", "space-explorer-display-v1", JSON.stringify({
      profile: this.renderingProfile,
      markerSize: this.markerSize,
      motionRate: this.motionRate,
      colorMode: this.colorMode,
      interfaceScale: this.interfaceScale,
      referenceFrame: this.referenceFrame,
      fieldRendering: this.fieldRendering,
      distanceScale: this.distanceScale,
      starsChosen: this.displayStars,
      environmentalMotion: this.displayEnvironmentMotion,
      satelliteLabels: this.displaySatelliteLabels,
    }));
  }

  /**
   * Re-point every surface that states the active distance scale — the legend
   * line, the zoom-out tooltip and the satellite geometry note — at the one
   * generated wording, so a toggle can never leave a stale "compressed"
   * claim on screen. (The weather note and the display-settings note rebuild
   * themselves from the same strings on their own update paths.)
   */
  /**
   * The layers currently switched on, by name.
   *
   * Read off the checkboxes rather than kept as a second copy of the state:
   * the checkbox IS the state everywhere else in this file, and a mirror of it
   * would be one more thing that can fall out of step. Identities with no
   * control — the ones retired from the rail — simply do not appear, which is
   * the same rule every other walk of this map follows.
   */
  private activeGlobeLayers(): string[] {
    const active: string[] = [];
    for (const [layer, id] of Object.entries(ExplorerApp.layerCheckboxIds) as [string, string][]) {
      const checkbox = document.getElementById(id) as HTMLInputElement | null;
      if (checkbox?.checked) active.push(layer);
    }
    return active;
  }

  /**
   * The scale note under the legend, and the ONE writer of it.
   *
   * Sean's rule on this sentence is that what appears in the legend should
   * correspond to what is turned on AND DISPLAYED — see `teachingScaleLegend`.
   * A layer switched on with nothing drawn does not earn its clause, and past
   * the last measurement the magnetosphere is exactly that: on, and drawing
   * nothing, because nobody forecasts it. Leaving "dayside boundary shape is
   * true; the far tail is foreshortened" under an empty globe would describe a
   * boundary and a tail that are not there.
   *
   * Called from the distance-scale wording AND from every legend rebuild,
   * because the clock can empty a layer without any control being touched.
   */
  private updateScaleNote() {
    const drawing = this.activeGlobeLayers().filter((layer) => {
      // The boundary layers stop drawing past the end of the measured record.
      if (layer !== "geospace" && layer !== "magnetosphere") return true;
      return this.magnetopauseNoForecast() === null;
    });
    byId("map-key-scale").textContent = teachingScaleLegend(this.distanceScale, drawing);
  }

  private applyDistanceScaleWording() {
    const strings = distanceScaleStrings(this.distanceScale);
    this.updateScaleNote();
    byId<HTMLButtonElement>("zoom-out").title = strings.zoomOutTitle;
    const geometryNote = document.getElementById("satellite-geometry-scale-note");
    if (geometryNote) geometryNote.textContent = strings.geometryNote;
    // The weather readout rebuilds on its own update path, minutes apart; a
    // toggle must not leave its scale sentence lying in the meantime. Composed
    // again rather than string-replaced inside the rendered paragraph, which
    // is the same reason there is one writer at all.
    this.renderCurrentAnalysis();
  }

  private restoreCardPosition() {
    const saved = storageGet("local", "space-explorer-card-position-v1");
    if (!saved) return;
    try {
      const parsed = JSON.parse(saved) as Partial<{ top: number; left: number }>;
      if (Number.isFinite(parsed.top) && Number.isFinite(parsed.left)) {
        this.cardPosition = { top: parsed.top as number, left: parsed.left as number };
      }
    } catch {
      // Ignore malformed or obsolete stored position.
    }
  }

  /** Places the satellite stack at its remembered position, clamped to the
   * current viewport. On the phone bottom-sheet layout the stack is not
   * draggable, so any inline placement is cleared and the CSS layout wins. */
  private applyCardPosition() {
    const card = byId("satellite-stack");
    // Height is the phone's own axis and has its own breakpoint, so it is
    // settled on every path that places this card rather than inside one of
    // the two branches below.
    this.applyStackHeight();
    if (this.mobileCardLayoutQuery.matches) {
      card.style.removeProperty("top");
      card.style.removeProperty("left");
      this.announceOccluderChange();
      return;
    }
    if (!this.cardPosition) {
      this.announceOccluderChange();
      return;
    }
    const maxLeft = Math.max(4, window.innerWidth - card.offsetWidth - 4);
    const maxTop = Math.max(4, window.innerHeight - card.offsetHeight - 4);
    card.style.left = `${Math.min(Math.max(4, this.cardPosition.left), maxLeft)}px`;
    card.style.top = `${Math.min(Math.max(4, this.cardPosition.top), maxTop)}px`;
    this.announceOccluderChange();
  }

  /**
   * Panels that float over the globe carry `data-occludes-globe`, so anything
   * that needs to keep clear of them — the satellite label placer, for one —
   * can read their live rectangles out of the DOM instead of hard-coding
   * pixel constants that go stale the moment a panel is dragged, collapsed or
   * resized. This event fires whenever that set or its geometry changes.
   */
  private announceOccluderChange() {
    this.updateExplorerHeadroom();
    byId("scene").dispatchEvent(new CustomEvent("explorer:occluders-changed", { bubbles: true }));
  }

  /**
   * How far the layers panel may grow downward before it starts covering the
   * LEGEND'S OWN HEAD.
   *
   * The two windows share the scene's right-hand column: the panel hangs from
   * the top, the legend stands on the floor and grows upward with one key card
   * per drawn layer. Raising the panel's ceiling so an opened layer card fits
   * (see the note in the stylesheet) put those two on a collision course, and
   * `tests/panel-collision.spec.ts`'s own standard is the one that decides it:
   * overlapping boxes are allowed, an unreachable control is not. Measured at
   * 1440x900 with eight layers on and one card opened, a flat 600 px ceiling
   * put the panel's bottom edge at 684 and the legend's fold toggle at 620-651
   * — `elementFromPoint` on that toggle returned the PANEL. The legend could
   * not be folded, which is the one gesture that would have made room.
   *
   * So the ceiling is bounded by the room that actually exists rather than by
   * a constant: the stylesheet asks for `min(74vh, 600px, var(--viewer-headroom))`,
   * and this is where that last term comes from. It is the live gap between
   * the panel's own top edge — which the reader can drag — and the top of the
   * legend, which moves with the number of layers and with whether the reader
   * has folded it. With no legend on screen the scene's floor stands in.
   *
   * A custom property, deliberately, and never a `height`: the panel stays
   * exactly as tall as its contents and this only moves the point at which it
   * stops growing. The floor of 160 px keeps a panel that has been dragged low
   * from collapsing to a sliver — at that point the reader has moved it
   * themselves and the drag clamp in `sceneBounds` is what governs.
   */
  private updateExplorerHeadroom() {
    const explorer = byId("data-viewer");
    if (explorer.hidden) return;
    const scene = this.sceneBounds();
    const key = document.getElementById("map-key");
    const floor = key && !key.hidden ? key.getBoundingClientRect().top : scene.top + scene.height - 8;
    const headroom = Math.max(160, Math.round(floor - explorer.getBoundingClientRect().top - 10));
    explorer.style.setProperty("--viewer-headroom", `${headroom}px`);
  }

  private bindCardDrag() {
    window.addEventListener("resize", () => this.applyCardPosition());
    this.bindStackSizeGrip();
  }

  /**
   * THE SATELLITE CARD'S HEIGHT, ON A PHONE, IN THE READER'S HAND.
   *
   * Sean, 2026-08-30: "on mobile the satellite data card/window still can't be
   * resized". It never could, and nothing regressed: `startCardDrag` has always
   * returned at the phone breakpoint, and this panel has never carried a resize
   * handle at ANY width - the grip it gets compared against belongs to the Data
   * Explorer next door. So this is a build.
   *
   * WHY THE BOTTOM EDGE AND NOT A CORNER. A corner grip is the desktop
   * metaphor and it offers two axes. On a phone this card has neither of them
   * free: the stylesheet pins it to both side gutters (`width: calc(100% -
   * 20px)`) and hangs it from the top of the scene, so its width and its
   * position are not the reader's to change. The one quantity that IS theirs is
   * how much of the screen the card takes from the globe, and the edge that
   * expresses that is the bottom one. A full-width bar on that edge is reachable
   * with either thumb, needs no aim, and reads as the thing it moves; a 12 px
   * corner triangle on a sheet pinned to both edges is none of those.
   *
   * THE TARGET IS 44 px AND IT IS DRAWN EXACTLY WHERE IT WORKS. The band is
   * 26 px of layout with 9 px of overhang each way from `.stack-size-grip::after`,
   * and both the stylesheet and this handler answer to `phoneChromeQuery` - the
   * same 820 px that turns the card into a sheet. That pairing is the point: the
   * defect this area last carried was a grip drawn from 430 px down over a panel
   * whose handler switched off at 600.
   *
   * It does not fight the page. `touch-action: none` on the grip and a
   * `preventDefault` on every move phase mean the gesture is a resize from the
   * first pixel and never half a scroll.
   */
  private bindStackSizeGrip() {
    const grip = document.getElementById("satellite-stack-size");
    if (!grip) return;
    if (window.PointerEvent) {
      grip.addEventListener("pointerdown", (event) => this.startStackResize(event as PointerEvent));
      grip.addEventListener("pointermove", (event) => this.moveStackResize(event as PointerEvent));
      grip.addEventListener("pointerup", (event) => this.endStackResize(event as PointerEvent));
      grip.addEventListener("pointercancel", (event) => this.endStackResize(event as PointerEvent));
    } else {
      // A handset whose browser has touch but not Pointer Events. Same three
      // phases, the same clamp, the same preventDefault - written out rather
      // than assumed, because the whole point of this control is that a thumb
      // can work it.
      let active = false;
      grip.addEventListener("touchstart", (event) => {
        const touch = event.touches[0];
        if (!touch) return;
        active = this.beginStackResize(touch.clientY);
        if (active) event.preventDefault();
      }, { passive: false });
      grip.addEventListener("touchmove", (event) => {
        const touch = event.touches[0];
        if (!active || !touch) return;
        this.dragStackTo(touch.clientY);
        event.preventDefault();
      }, { passive: false });
      const finish = () => {
        if (!active) return;
        active = false;
        this.finishStackResize();
      };
      grip.addEventListener("touchend", finish);
      grip.addEventListener("touchcancel", finish);
    }
    // A splitter with no keyboard is a control half the readers cannot reach.
    grip.addEventListener("keydown", (event) => this.stackSizeKey(event as KeyboardEvent));
    window.addEventListener("orientationchange", () => this.applyStackHeight());
    // Content height moves when a fold opens or shuts, and the ceiling is the
    // content — so every `toggle` inside the stack re-clamps the shown height.
    // Capture, because `toggle` does not bubble off a <details>.
    byId("satellite-stack").addEventListener("toggle", (event) => {
      const fold = event.target as HTMLDetailsElement | null;
      if (fold instanceof HTMLDetailsElement && fold.open) this.revealAfterExpand(fold);
      this.applyStackHeight();
    }, true);
  }

  /**
   * The band the card's height is allowed to live in.
   *
   * The floor keeps the head and the grip on screen, so a reader who drags the
   * card shut still has something to drag back open. The ceiling is measured
   * from the scene rather than the viewport, for the same reason `sceneBounds`
   * is used everywhere else in this file: `.scene-shell` clips, so a card sized
   * past the scene's floor is not covered, it is cut off.
   */
  private stackSizeBounds(): { min: number; max: number } {
    const card = byId("satellite-stack");
    const scene = this.sceneBounds();
    const top = card.getBoundingClientRect().top - scene.top;
    const min = 96;
    let max = Math.round(scene.height - top - 12);
    // THE CEILING IS THE CONTENT (Sean, 2026-08-31: "if a section collapses
    // the window shrinks if needed"). The grip cannot pull the card past what
    // its contents can fill, so a dragged-tall card never holds a band of
    // empty panel under the last section — and `aria-valuemax` says the same
    // number, because this is the one place the bound is computed. Flip the
    // constant to let the drag run to the scene bound instead.
    if (ExplorerApp.STACK_CEILING_IS_CONTENT) {
      const content = this.stackContentHeight();
      if (content !== null) max = Math.min(max, content);
    }
    return { min, max: Math.max(min, max) };
  }

  /** The height at which the card would hold everything it currently shows:
   * the cards themselves, the scroller's padding, and the card's own chrome —
   * measured, not assumed, so a collapsed fold moves it the moment the browser
   * reflows. The chrome is summed from the pieces (the panel's borders and its
   * non-scroller children, i.e. the grip), never derived as `card height minus
   * scroller height`: the scroller has no flex-grow, so on a card dragged past
   * its content that subtraction reads the empty band below the grip as chrome
   * and the ceiling never comes down — which is exactly the state this
   * function exists to end. */
  private stackContentHeight(): number | null {
    const card = byId("satellite-stack");
    const cards = document.getElementById("satellite-stack-cards");
    if (!cards) return null;
    const kids = [...cards.children] as HTMLElement[];
    const style = getComputedStyle(cards);
    const inner = kids.length
      ? (kids[kids.length - 1]!.getBoundingClientRect().bottom - kids[0]!.getBoundingClientRect().top)
      : 0;
    const cardStyle = getComputedStyle(card);
    let chrome = parseFloat(cardStyle.borderTopWidth) + parseFloat(cardStyle.borderBottomWidth);
    for (const child of card.children) {
      if (child === cards) continue;
      // OUT-OF-FLOW CHILDREN ARE NOT CHROME. The size grip became
      // `position: absolute` when it turned into the lit corner (2026-08-31),
      // and it still reports a 46 px `offsetHeight` while contributing nothing
      // to the card's flow height. Counting it inflated the ceiling by 46 px,
      // so a card left 59 px taller than its own contents after a fold closed
      // and the "shrinks if needed" rule silently stopped firing. Measured on
      // the ISS card: shown 529, content 470, no shrink.
      const style = getComputedStyle(child as HTMLElement);
      if (style.position === "absolute" || style.position === "fixed") continue;
      chrome += (child as HTMLElement).offsetHeight;
    }
    return Math.ceil(inner + parseFloat(style.paddingTop) + parseFloat(style.paddingBottom) + chrome);
  }

  private beginStackResize(clientY: number): boolean {
    if (!this.phoneChromeQuery.matches) return false;
    const card = byId("satellite-stack");
    if (card.hidden) return false;
    this.stackResizeState = { startY: clientY, startHeight: card.getBoundingClientRect().height };
    card.classList.add("is-sizing");
    return true;
  }

  private dragStackTo(clientY: number) {
    const state = this.stackResizeState;
    if (!state) return;
    const { min, max } = this.stackSizeBounds();
    this.stackHeight = Math.min(max, Math.max(min, Math.round(state.startHeight + (clientY - state.startY))));
    this.writeStackHeight(this.stackHeight, min, max);
  }

  private finishStackResize() {
    byId("satellite-stack").classList.remove("is-sizing");
    this.stackResizeState = null;
    this.announceOccluderChange();
    if (this.stackHeight !== null) storageSet("local", "space-explorer-card-height-v1", String(this.stackHeight));
  }

  private startStackResize(event: PointerEvent) {
    if (!this.beginStackResize(event.clientY)) return;
    this.stackPointerId = event.pointerId;
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
    event.preventDefault();
    event.stopPropagation();
  }

  private moveStackResize(event: PointerEvent) {
    if (!this.stackResizeState || event.pointerId !== this.stackPointerId) return;
    this.dragStackTo(event.clientY);
    event.preventDefault();
  }

  private endStackResize(event: PointerEvent) {
    if (!this.stackResizeState || event.pointerId !== this.stackPointerId) return;
    this.stackPointerId = null;
    this.finishStackResize();
  }

  /** Arrow keys nudge, Shift jumps, Home and End go to the two ends - the
   * window-splitter keyboard contract that goes with role="separator". */
  private stackSizeKey(event: KeyboardEvent) {
    if (!this.phoneChromeQuery.matches) return;
    const { min, max } = this.stackSizeBounds();
    const current = this.stackHeight ?? Math.round(byId("satellite-stack").getBoundingClientRect().height);
    const step = event.shiftKey ? 64 : 24;
    let next: number | null = null;
    if (event.key === "ArrowDown") next = current + step;
    else if (event.key === "ArrowUp") next = current - step;
    else if (event.key === "End") next = max;
    else if (event.key === "Home") next = min;
    if (next === null) return;
    event.preventDefault();
    this.stackHeight = Math.min(max, Math.max(min, next));
    this.writeStackHeight(this.stackHeight, min, max);
    storageSet("local", "space-explorer-card-height-v1", String(this.stackHeight));
    this.announceOccluderChange();
  }

  /** Both the box and what a screen reader is told about it, from one writer,
   * so the drawn height and the announced height cannot drift apart. */
  private writeStackHeight(height: number, min: number, max: number) {
    const card = byId("satellite-stack");
    card.style.height = `${height}px`;
    card.style.maxHeight = `${height}px`;
    const grip = document.getElementById("satellite-stack-size");
    if (!grip) return;
    grip.setAttribute("aria-valuemin", String(min));
    grip.setAttribute("aria-valuemax", String(max));
    grip.setAttribute("aria-valuenow", String(height));
    grip.setAttribute("aria-valuetext", `${height} pixels tall`);
  }

  /**
   * THE STORED HEIGHT IS A PHONE FACT AND IT STAYS ON THE PHONE.
   *
   * Above 820 px every inline trace of it comes off, so a session that sized
   * the card on a handset and then rotated into landscape - or a desktop that
   * inherited the same browser profile - gets the desktop's own layout back
   * exactly as the stylesheet writes it. Sean, 2026-08-30: "leave desktop
   * versions alone right now".
   */
  private applyStackHeight() {
    const card = document.getElementById("satellite-stack");
    if (!card) return;
    if (!this.phoneChromeQuery.matches) {
      card.style.removeProperty("height");
      card.style.removeProperty("max-height");
      return;
    }
    if (this.stackHeight === null || card.hidden) return;
    const { min, max } = this.stackSizeBounds();
    // The SHOWN height is clamped; the remembered height is not. A fold
    // collapsing shrinks the card "if needed", and re-opening the fold gives
    // the reader back the height they actually dragged, rather than the
    // smallest the card has ever been.
    this.writeStackHeight(Math.min(max, Math.max(min, this.stackHeight)), min, max);
  }

  /**
   * OPENING A FOLD OPENS THE CARD A LITTLE, TOO.
   *
   * Sean, 2026-08-31: "when a user expands a section on the satellite data card
   * it should expand the window a bit. just enough to show some information
   * that is now being displayed. something useful where they can scroll and
   * read without having to manually pull the window down. and if they collapse
   * it then the window shrinks."
   *
   * The shrink half already worked, because the ceiling IS the content: a fold
   * closing drops `max` below the shown height and `applyStackHeight` clamps to
   * it. The growth half did not, and the reason is the same clamp read the
   * other way — opening a fold raises the ceiling, but the SHOWN height stays
   * at whatever the reader last dragged, so the card sat still and the new
   * content appeared only inside the scroller. That is the manual pull he is
   * describing.
   *
   * So an expand raises the FLOOR. The card grows by at most
   * `EXPAND_REVEAL_BUDGET` — a few lines, not the whole section, because a fold
   * like Data Sources can be several screens and a card that leapt to full
   * height on every press would be worse than one that never moved. Past that
   * the reader scrolls, which is what he asked for.
   *
   * It raises the remembered height rather than only the shown one, so the
   * card does not snap back the next time anything re-clamps; a later collapse
   * still shrinks it, which is the loop he described.
   */
  private static readonly EXPAND_REVEAL_BUDGET = 168;

  /** When the open card was last rebuilt, so construction toggles can be told
   *  apart from a reader pressing a fold. */
  private stackBuiltAt = 0;

  private revealAfterExpand(fold: HTMLDetailsElement) {
    if (!this.phoneChromeQuery.matches) return;
    // ONLY A READER'S EXPAND COUNTS. Building a card fires `toggle` for the
    // fold that ships open, and seeding the remembered height from THAT pinned
    // the card at whatever it measured mid-construction: an inline
    // height/max-height pair outranks every stylesheet rule, so the opening-size
    // cap could never apply and the card always came back the height it had
    // been. Measured: inline 364.5 px against a CSS cap of 26svh. Toggles inside
    // the build window are the template settling, not a press.
    if (performance.now() - this.stackBuiltAt < 500) return;
    const card = document.getElementById("satellite-stack");
    if (!card || card.hidden) return;
    // A READER WHO HAS NEVER DRAGGED IS THE ONE THIS IS FOR. Until the grip is
    // used, `stackHeight` is null and the card is sized by the stylesheet — so
    // the clamp has nothing to clamp and an early return here would skip the
    // exact person who should not have to drag. Seed the remembered height from
    // what is on screen and grow from there.
    if (this.stackHeight === null) this.stackHeight = card.getBoundingClientRect().height;
    // What the fold added, measured after the browser has laid it out.
    requestAnimationFrame(() => {
      const bounds = this.stackSizeBounds();
      const shown = card.getBoundingClientRect().height;
      const hidden = fold.getBoundingClientRect().bottom - card.getBoundingClientRect().bottom;
      if (hidden <= 0) return;
      const target = Math.min(
        bounds.max,
        shown + Math.min(hidden, ExplorerApp.EXPAND_REVEAL_BUDGET),
      );
      if (target <= shown) return;
      this.stackHeight = target;
      this.applyStackHeight();
    });
  }

  private restoreStackHeight() {
    const value = Number(storageGet("local", "space-explorer-card-height-v1"));
    if (Number.isFinite(value) && value > 0) this.stackHeight = value;
  }

  /**
   * THE PANEL'S DRAG HANDLE IS THE CARD'S OWN HEAD.
   *
   * It used to be `#satellite-stack-handle`, the bar above the cards that
   * printed "# Satellite(s) Selected" — and that bar went with the count when
   * the selection became one spacecraft at a time. Keeping it as an empty grab
   * rail would have put back the row Sean asked to delete, so the handle moved
   * onto the head the card already has: the row carrying the name, the star and
   * the X.
   *
   * The head and not the whole panel, because dragging from the body would
   * fight text selection and the panel's own scroll. `startCardDrag` returns on
   * a pointerdown inside any button, so the expander, the star, the X and the
   * hedge marks all keep their own clicks; what is left to grab is the chips
   * row and the NORAD/COSPAR line. Bound per card rather than once, because the
   * card element is rebuilt whenever a different spacecraft is opened.
   */
  private bindCardDragHandle(handle: HTMLElement) {
    handle.addEventListener("pointerdown", (event) => this.startCardDrag(event));
    handle.addEventListener("pointermove", (event) => this.dragCard(event));
    handle.addEventListener("pointerup", (event) => this.endCardDrag(event));
    handle.addEventListener("pointercancel", (event) => this.endCardDrag(event));
  }

  /**
   * The rectangle a floating panel is allowed to live in: THE SCENE, never the
   * rail.
   *
   * Sean: "I shouldn't have to drag the data explorer to the left to be able
   * to grab the resize at the bottom. It shouldn't ever overlap with the
   * rail." The resize grip was never broken. Every clamp in this file measured
   * against `window.innerWidth` and `window.innerHeight`, which include the
   * 390 px rail, so a panel could be dragged or sized until most of it lay
   * under the rail's column - and `.scene-shell` has `overflow: hidden`, so
   * what was under the rail was CLIPPED AWAY rather than merely covered. The
   * bottom-right corner, and the grip on it, simply were not on screen. The
   * reader's workaround - drag it back left first - is the tell.
   *
   * The offset parent for both floating panels is `.scene-shell`, so its own
   * box is the coordinate space AND the limit. `rect.left` is subtracted
   * rather than assumed to be zero: it is zero in today's grid, and a layout
   * that ever puts anything to the left of the scene would otherwise offset
   * every drag silently.
   */
  private sceneBounds(): { left: number; top: number; width: number; height: number } {
    const shell = document.querySelector<HTMLElement>(".scene-shell");
    if (!shell) return { left: 0, top: 0, width: window.innerWidth, height: window.innerHeight };
    const rect = shell.getBoundingClientRect();
    return { left: rect.left, top: rect.top, width: rect.width, height: rect.height };
  }

  private startCardDrag(event: PointerEvent) {
    // Phones use a fixed bottom-sheet layout for the stack; leave it in place
    // there rather than fighting that layout with free-form dragging.
    if (this.mobileCardLayoutQuery.matches) return;
    if ((event.target as Element).closest("button")) return;
    const card = byId("satellite-stack");
    const rect = card.getBoundingClientRect();
    this.cardDragState = {
      pointerId: event.pointerId,
      offsetX: event.clientX - rect.left,
      offsetY: event.clientY - rect.top,
    };
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
    card.classList.add("is-dragging");
    card.style.right = "auto";
    event.preventDefault();
  }

  private dragCard(event: PointerEvent) {
    if (!this.cardDragState || event.pointerId !== this.cardDragState.pointerId) return;
    const card = byId("satellite-stack");
    const scene = this.sceneBounds();
    const maxLeft = Math.max(4, scene.width - card.offsetWidth - 4);
    const maxTop = Math.max(4, scene.height - card.offsetHeight - 4);
    const left = Math.min(Math.max(4, event.clientX - this.cardDragState.offsetX - scene.left), maxLeft);
    const top = Math.min(Math.max(4, event.clientY - this.cardDragState.offsetY - scene.top), maxTop);
    card.style.left = `${left}px`;
    card.style.top = `${top}px`;
    this.cardPosition = { top, left };
  }

  private endCardDrag(event: PointerEvent) {
    if (!this.cardDragState || event.pointerId !== this.cardDragState.pointerId) return;
    byId("satellite-stack").classList.remove("is-dragging");
    this.cardDragState = null;
    this.announceOccluderChange();
    if (this.cardPosition) storageSet("local", "space-explorer-card-position-v1", JSON.stringify(this.cardPosition));
  }

  private restoreExplorerPosition() {
    const saved = storageGet("local", "space-explorer-data-explorer-position-v1");
    if (!saved) return;
    try {
      const parsed = JSON.parse(saved) as Partial<{ top: number; left: number }>;
      if (Number.isFinite(parsed.top) && Number.isFinite(parsed.left)) {
        this.explorerPosition = { top: parsed.top as number, left: parsed.left as number };
      }
    } catch {
      // Ignore malformed or obsolete stored position.
    }
  }

  private restoreExplorerSize() {
    const saved = storageGet("local", "space-explorer-data-explorer-size-v1");
    if (!saved) return;
    try {
      const parsed = JSON.parse(saved) as Partial<{ width: number; height: number }>;
      if (Number.isFinite(parsed.width) && Number.isFinite(parsed.height)) {
        this.explorerSize = { width: parsed.width as number, height: parsed.height as number };
      }
    } catch {
      // Ignore malformed or obsolete stored size.
    }
  }

  /** Places the space weather layers panel at its remembered position, clamped to the
   * current viewport. On the phone layout it is a fixed strip under the
   * header, not a free-floating window, so any inline placement is cleared
   * and the CSS layout wins — the same split the satellite stack draws. */
  private applyExplorerPosition() {
    const explorer = byId("data-viewer");
    if (this.mobileCardLayoutQuery.matches) {
      explorer.style.removeProperty("top");
      explorer.style.removeProperty("left");
      explorer.style.removeProperty("right");
      this.announceOccluderChange();
      return;
    }
    if (!this.explorerPosition) {
      this.announceOccluderChange();
      return;
    }
    // Clamped on RESTORE as well as on drag, which is what stops a position
    // stored from a wider window - or from before the rail was excluded -
    // putting the panel under the rail when it is reopened narrower.
    const scene = this.sceneBounds();
    const maxLeft = Math.max(4, scene.width - explorer.offsetWidth - 4);
    const maxTop = Math.max(4, scene.height - explorer.offsetHeight - 4);
    explorer.style.right = "auto";
    explorer.style.left = `${Math.min(Math.max(4, this.explorerPosition.left), maxLeft)}px`;
    explorer.style.top = `${Math.min(Math.max(4, this.explorerPosition.top), maxTop)}px`;
    this.announceOccluderChange();
  }

  /**
   * Applies a remembered resize.
   *
   * THE HEIGHT A READER DRAGS IS A CEILING, NOT A HEIGHT. This method used to
   * write the remembered height as an inline `height`, and an inline height is
   * a floor as well as a ceiling: one layer switched on, in a browser that had
   * ever been resized, opened a 432 px window holding a 59 px card and 390 px
   * of nothing. That is what Sean saw — "it starts very large even though
   * there is only one entry... that is wasted space" — and it was never a CSS
   * defect. `styles.css` sets a max-height and nothing else; a max-height
   * cannot stretch a flex column. A stored preference was propping it open.
   *
   * So the panel is always exactly as tall as its head plus its cards, and the
   * remembered height becomes an inline `max-height` instead: a reader who has
   * deliberately sized this window still gets that size honoured as the point
   * at which it stops growing and starts scrolling, and it still overrides the
   * stylesheet's own min(48vh, 480px) in both directions, but it can no longer
   * hold the panel open past its contents. Clearing the choice is the same
   * gesture it always was — drag the corner again.
   *
   * Width is a real width, and sticks even while collapsed so folding the
   * panel does not also narrow it. A width wider than its contents costs a
   * reader nothing; a height taller than its contents is the whole complaint.
   */
  private applyExplorerSize() {
    const explorer = byId("data-viewer");
    // Never leave a height behind, whichever branch runs: an earlier build of
    // this file wrote one, and a reader whose session predates the fix would
    // otherwise keep it until the next full reload.
    explorer.style.removeProperty("height");
    if (this.mobileCardLayoutQuery.matches || !this.explorerSize) {
      explorer.style.removeProperty("width");
      explorer.style.removeProperty("max-height");
      return;
    }
    const scene = this.sceneBounds();
    const maxWidth = Math.max(220, scene.width - 32);
    const maxHeight = Math.max(140, scene.height - 32);
    const width = Math.min(Math.max(220, this.explorerSize.width), maxWidth);
    const height = Math.min(Math.max(140, this.explorerSize.height), maxHeight);
    explorer.style.width = `${width}px`;
    explorer.style.maxHeight = `${height}px`;
  }

  /**
   * The panel's head is both its drag handle and its collapse toggle,
   * told apart by whether the pointer travelled: a genuine click — pointerdown
   * and pointerup with almost no movement between them — folds or unfolds the
   * panel, and anything past a few pixels of movement is a drag instead. The
   * close button is excluded from starting a drag at all, the same way the
   * satellite stack's handle excludes its own buttons.
   */
  private bindExplorerDrag() {
    const head = byId("data-viewer-head");
    head.addEventListener("pointerdown", (event) => this.startExplorerDrag(event));
    head.addEventListener("pointermove", (event) => this.dragExplorer(event));
    head.addEventListener("pointerup", (event) => this.endExplorerDrag(event));
    head.addEventListener("pointercancel", (event) => this.endExplorerDrag(event));
    head.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      this.setExplorerCollapsed(!this.explorerCollapsed);
    });
    // On a phone the head is NOT a drag handle — `startExplorerDrag` returns
    // immediately at this breakpoint — and the fold/unfold lives at the end of
    // that same drag lifecycle. So disabling the drag disabled the only way to
    // open the panel: a phone visitor could see "DATA EXPLORER · 2 layers" and
    // tap it forever without anything happening, which meant no layer readings
    // were reachable on mobile at all. A plain tap has to stand on its own.
    head.addEventListener("click", (event) => {
      if (!this.mobileCardLayoutQuery.matches) return;
      if ((event.target as Element).closest("button")) return;
      this.setExplorerCollapsed(!this.explorerCollapsed);
    });
    const resizeHandle = byId("data-viewer-resize");
    resizeHandle.addEventListener("pointerdown", (event) => this.startExplorerResize(event));
    resizeHandle.addEventListener("pointermove", (event) => this.resizeExplorer(event));
    resizeHandle.addEventListener("pointerup", (event) => this.endExplorerResize(event));
    resizeHandle.addEventListener("pointercancel", (event) => this.endExplorerResize(event));
    window.addEventListener("resize", () => {
      this.applyExplorerPosition();
      this.applyExplorerSize();
    });
  }

  private startExplorerDrag(event: PointerEvent) {
    if (this.mobileCardLayoutQuery.matches) return;
    if ((event.target as Element).closest("button")) return;
    const explorer = byId("data-viewer");
    const rect = explorer.getBoundingClientRect();
    this.explorerDragState = {
      pointerId: event.pointerId,
      offsetX: event.clientX - rect.left,
      offsetY: event.clientY - rect.top,
      startX: event.clientX,
      startY: event.clientY,
      moved: false,
    };
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
    explorer.classList.add("is-dragging");
    event.preventDefault();
  }

  private dragExplorer(event: PointerEvent) {
    const state = this.explorerDragState;
    if (!state || event.pointerId !== state.pointerId) return;
    if (!state.moved && Math.hypot(event.clientX - state.startX, event.clientY - state.startY) > 4) state.moved = true;
    if (!state.moved) return;
    const explorer = byId("data-viewer");
    const scene = this.sceneBounds();
    const maxLeft = Math.max(4, scene.width - explorer.offsetWidth - 4);
    const maxTop = Math.max(4, scene.height - explorer.offsetHeight - 4);
    const left = Math.min(Math.max(4, event.clientX - state.offsetX - scene.left), maxLeft);
    const top = Math.min(Math.max(4, event.clientY - state.offsetY - scene.top), maxTop);
    explorer.style.right = "auto";
    explorer.style.left = `${left}px`;
    explorer.style.top = `${top}px`;
    this.explorerPosition = { top, left };
  }

  private endExplorerDrag(event: PointerEvent) {
    const state = this.explorerDragState;
    if (!state || event.pointerId !== state.pointerId) return;
    byId("data-viewer").classList.remove("is-dragging");
    this.explorerDragState = null;
    this.announceOccluderChange();
    if (state.moved) {
      if (this.explorerPosition) storageSet("local", "space-explorer-data-explorer-position-v1", JSON.stringify(this.explorerPosition));
      return;
    }
    // The pointer barely moved: a click, not a drag. Fold or unfold instead.
    this.setExplorerCollapsed(!this.explorerCollapsed);
  }

  private startExplorerResize(event: PointerEvent) {
    if (this.mobileCardLayoutQuery.matches || this.explorerCollapsed) return;
    const explorer = byId("data-viewer");
    const rect = explorer.getBoundingClientRect();
    this.explorerResizeState = {
      pointerId: event.pointerId,
      startWidth: rect.width,
      startHeight: rect.height,
      startX: event.clientX,
      startY: event.clientY,
    };
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
    explorer.classList.add("is-resizing");
    event.preventDefault();
    event.stopPropagation();
  }

  private resizeExplorer(event: PointerEvent) {
    const state = this.explorerResizeState;
    if (!state || event.pointerId !== state.pointerId) return;
    const explorer = byId("data-viewer");
    const rect = explorer.getBoundingClientRect();
    const scene = this.sceneBounds();
    // Right edge stops at the scene's right edge, which is the rail's left
    // edge. Growing past it does not overlap the rail, it is clipped by
    // `.scene-shell { overflow: hidden }` - so the reader would be dragging a
    // corner that is no longer there.
    const maxWidth = Math.max(220, scene.left + scene.width - rect.left - 8);
    const maxHeight = Math.max(140, scene.top + scene.height - rect.top - 8);
    const width = Math.min(Math.max(220, state.startWidth + (event.clientX - state.startX)), maxWidth);
    const height = Math.min(Math.max(140, state.startHeight + (event.clientY - state.startY)), maxHeight);
    explorer.style.width = `${width}px`;
    // A ceiling, matching applyExplorerSize — see the note there. Dragging the
    // corner down past the last card does not open a gap under it: there is
    // nothing further to reveal, so the box stops where its contents stop and
    // the raised ceiling shows itself the moment another layer goes on.
    // `state.startHeight` is the rendered height, so the corner always works
    // from the box the reader can actually see.
    explorer.style.maxHeight = `${height}px`;
    this.explorerSize = { width, height };
    event.stopPropagation();
  }

  private endExplorerResize(event: PointerEvent) {
    const state = this.explorerResizeState;
    if (!state || event.pointerId !== state.pointerId) return;
    byId("data-viewer").classList.remove("is-resizing");
    this.explorerResizeState = null;
    this.announceOccluderChange();
    if (this.explorerSize) storageSet("local", "space-explorer-data-explorer-size-v1", JSON.stringify(this.explorerSize));
    event.stopPropagation();
  }

  /**
   * The X. Sean: "if they close it with the X in the right hand side of it,
   * all the toggles go off" — closing this panel means stop plotting,
   * not merely hide the window it happens to be showing. Every active layer's
   * real checkbox gets a real `.click()`, in the site's own layer order, so
   * every `change` cascade a reader unchecking it by hand would trigger fires
   * here too: switching geospace off also drops its empirical-boundary
   * annotation, exactly as `layerMap`'s own listener already does for a
   * manual uncheck. The panel then disappears on its own, in the same render
   * pass, because `updateDataViewer` hides it the moment no layer is active —
   * there is no separate "now hide the window" step to forget.
   */
  private closeDataExplorer() {
    // Every checkbox this site calls a layer — not only the ones with a card
    // in this panel. `layerOrder` (the card/legend list) leaves out
    // `groundField`, which is a real, independently plottable field with its
    // own rail toggle; closing the explorer must still turn it off, even
    // though it earns no card here. Screenshotted with Full plus every
    // "advanced" layer on: without this wider list, "Ground magnetic
    // perturbation" stayed lit after every other toggle went dark.
    for (const id of Object.values(ExplorerApp.layerCheckboxIds)) {
      const checkbox = byId<HTMLInputElement>(id);
      if (checkbox.checked) checkbox.click();
    }
    // Closing resets to the shipped default, collapsed, rather than merely
    // hiding whatever expand state the panel happened to be in. The next
    // layer switched on is a fresh start, not a window popping back open at
    // whatever size a much earlier session left it.
    if (!this.explorerCollapsed) this.setExplorerCollapsed(true);
  }

  private setExplorerCollapsed(collapsed: boolean) {
    this.explorerCollapsed = collapsed;
    storageSet("local", "space-explorer-data-explorer-collapsed-v2", collapsed ? "1" : "0");
    // One sheet at a time on a phone. Measured on an iPhone 13: with the layer
    // sheet open AND the readings expanded, the two together covered more than
    // the whole viewport and the globe was gone. A desktop can afford two
    // windows side by side; 390 px cannot, and the visitor who just asked for
    // readings wants to see them against the globe, not against a layer list.
    if (!collapsed && this.mobileCardLayoutQuery.matches) this.closeMobilePanel();
    this.updateEnvironmentLegend();
    this.announceOccluderChange();
  }

  private updateGeoFilterVisibility() {
    const visible = this.orbitScope === "GEO";
    const filter = byId("geo-subfilter");
    filter.classList.toggle("is-visible", visible);
    filter.setAttribute("aria-hidden", String(!visible));
    filter.toggleAttribute("inert", !visible);
    document.querySelectorAll<HTMLButtonElement>("[data-geo-type]").forEach((button) => {
      button.disabled = !visible;
    });
  }

  /**
   * THERE IS NO EXPLORER MODE. `setMode` stood here until 2026-08-28 and is
   * deleted rather than reduced to a no-op, along with the
   * Satellites / Space weather / Combined control that called it.
   *
   * Sean: "get rid of the Explorer Mode and Satellite/Space Weather/Combined
   * stuff on the mobile and on desktop version. the contents in those take up
   * the entire panel and it doesn't make sense to have it anymore." And on
   * what replaces it: "no combined on either. if you plot an environment
   * layer, it shows up and persists until you X out the layer in the viewer,
   * even if you go back to the satellite panel. same for satellites. going
   * into the space weather rail on desktop or panel in mobile doesn't take the
   * satellite off or a plotted orbit off."
   *
   * So what Combined did is the only behaviour there is. Two things this
   * method did are DELETED BEHAVIOUR rather than behaviour moved elsewhere,
   * and both are the change Sean asked for:
   *
   *  - It hid half the rail, by writing `hidden` onto every
   *    `[data-mode-panel]` section of the other half. Nothing hides now; the
   *    attribute survives on those sections as a grouping label with no reader.
   *  - Entering Satellites mode called `hideAllLayers()`. That is exactly the
   *    "going back to the satellite panel takes my plotted layer off" Sean is
   *    ruling out, so `hideAllLayers` went with its only caller. The layer
   *    viewer's own X (`closeDataExplorer`) is still how every layer is turned
   *    off, and it is now the ONLY thing that turns one off.
   *
   * It also opened the catalog filter fold on the way into Satellites mode and
   * shut it on the way out. That is the rail's business and the rail's markup
   * now states its own opening state; nothing reaches across to change it.
   */
  private applyLayerPreset(preset: "simple" | "standard" | "full", hideAll = false) {
    // The magnetosphere in a preset is the FIELD — the NOAA MHD cut whose
    // colours contain the bow shock, sheath and magnetopause — never the
    // empirical boundary annotation, which is a comparison overlay a reader
    // switches on deliberately.
    const enabled: Record<typeof preset, LayerName[]> = {
      // The thermosphere leads, because it is the field that shows storm
      // drag — the reason most of this site's audience is here.
      simple: ["thermosphere"],
      // `photons` is deliberately in none of them. The X-ray visual is a
      // single scalar and a contrast rather than a field to browse: on its
      // own it is a faint tint and some streaks, and the reason to draw it -
      // that it crosses the boundary undeflected while the wind does not -
      // only exists with the wind and the boundary drawn beside it. It is
      // reached from the photon branch of "Follow the energy", which switches
      // all three on together. Its checkbox stays in `layerCheckboxIds` below
      // and stays in the document as a hidden input, so the walkthrough can
      // still drive it and this loop can still find it.
      standard: ["thermosphere", "geospace", "solarWind"],
      full: ["thermosphere", "tec", "drap", "aurora", "geospace", "solarWind", "radiation"],
    };
    (Object.entries(ExplorerApp.layerCheckboxIds) as [LayerName, string][]).forEach(([layer, id]) => {
      const visible = !hideAll && enabled[preset].includes(layer);
      byId<HTMLInputElement>(id).checked = visible;
      this.applyGlobeLayer(layer, visible);
    });
    const activeLayers = hideAll ? [] : enabled[preset];
    if (!this.environmentLegendFocus || !activeLayers.includes(this.environmentLegendFocus)) {
      this.environmentLegendFocus = activeLayers[0] ?? null;
    }
    this.updateModelControlVisibility();
    this.updateAuroraControlVisibility();
    this.updateThermosphereControlVisibility();
    this.updateIonosphereControlVisibility();
    this.updateEnvironmentLegend();
    this.globe.frameActiveLayers();
    if (!hideAll && enabled[preset].includes("thermosphere")) void this.loadThermosphere();
    if (!hideAll && enabled[preset].includes("drap")) void this.loadDrapModel();
    if (!hideAll && enabled[preset].includes("groundStations")) void this.loadGroundStations();
    if (!hideAll && enabled[preset].includes("aurora")) void this.loadAuroraHistoryModel();
    // Same list as the per-layer handler above, and for the same reason: a
    // preset that switches the solar wind on must load the model it flows in,
    // or the Standard preset silently serves the potential-flow fallback while
    // the identical layer toggled by hand serves NOAA's.
    if (!hideAll && enabled[preset].some((layer) =>
        layer === "geospace" || layer === "radiation" || layer === "plasmaSheet" || layer === "solarWind")) {
      void this.loadGeospaceModel();
    }
  }

  /**
   * One layer's visibility on the globe. Layers pass straight through; the
   * named regions of the published BATS-R-US cross-section are no longer a
   * layer but the plasma-field layer's own overlay checkboxes, which drive
   * `globe.setStructureRegion` directly.
   */
  private applyGlobeLayer(layer: LayerName, visible: boolean) {
    if (layer === "groundStations") {
      // Not one of the globe's own layers: the pins are an overlay this class
      // owns and hands to `addEarthFixedOverlay`, so there is nothing to switch
      // until the artifact has been fetched.
      this.groundStationLayer?.setVisible(visible);
      if (!visible) this.setSelectedStation(null);
      return;
    }
    this.globe.setLayer(layer, visible);
    // The scale note is assembled from the layers that are on, so it has to be
    // rebuilt whenever that set changes, not only when the ruler flips.
    this.applyDistanceScaleWording();
    // Arm, do not decide. The layer's data is not here yet; see
    // `pendingCoverageLanding` for what that cost when this line decided.
    if (visible) this.pendingCoverageLanding.set(layer, this.readerClockActions);
    else this.pendingCoverageLanding.delete(layer);
  }

  /**
   * Switching a layer on must not produce an empty globe.
   *
   * Sean's rule: "I just don't want people to turn on a layer and not have it
   * show up. If they scroll into the present just put a message on then that
   * says NOAA hasn't published yet."
   *
   * So a layer whose feed has nothing at the selected instant moves the clock
   * back to its newest published frame rather than drawing nothing and leaving
   * a button for the reader to find. `coverageLandingTarget` holds the rules
   * for which instant that is and when the move is allowed at all; this is the
   * half that knows when the question can be answered.
   *
   * Which is NOT when the checkbox flips. Every one of these layers fetches
   * its artifact on demand, and until it arrives the layer reports "loading",
   * has no coverage window, and cannot say whether it covers this instant. A
   * pending layer therefore stays pending across as many legend rebuilds as
   * its fetch takes, and is answered on the rebuild where its status finally
   * resolves — the same rebuild that makes the jump BUTTON appear, which is
   * why the button always worked and the automatic landing never did.
   *
   * Every layer with a coverage window goes through here, not aurora alone:
   * the ring current rides the plasmasphere artifact's window and has the same
   * gap, and so will the next feed that stalls.
   */
  private landOnCoverage(specs: ReadonlyArray<{ layer: LayerName; spec: EnvironmentLegendSpec }>) {
    // Seeking redraws the legend, which lands here again. The pending map is
    // emptied before the seek so the re-entry has nothing to do, and this flag
    // says so outright rather than relying on that.
    if (this.landingCoverage) return;
    // The note describes where the clock is and which layer put it there. With
    // that layer switched off there is nobody to say it to.
    if (this.coverageLanding && !specs.some(({ layer }) => layer === this.coverageLanding!.layer)) this.coverageLanding = null;
    if (this.pendingCoverageLanding.size === 0) return;
    const candidates: Array<{ layer: LayerName; jumpToIso?: string; sourceLabel: string; armedAtActionCount: number }> = [];
    for (const { layer, spec } of specs) {
      const armedAtActionCount = this.pendingCoverageLanding.get(layer);
      if (armedAtActionCount === undefined) continue;
      // Still in flight. No window yet, so no answer yet, so it keeps waiting.
      if (spec.statusState === "loading") continue;
      this.pendingCoverageLanding.delete(layer);
      const window = this.layerCoverageWindow(layer);
      if (!window) continue;
      candidates.push({ layer, jumpToIso: this.layerUnavailable(layer, spec)?.jumpToIso, sourceLabel: window.sourceLabel, armedAtActionCount });
    }
    // A layer switched off while its fetch was still running never gets an
    // answer, and must not sit in the map waiting for one.
    for (const layer of [...this.pendingCoverageLanding.keys()]) {
      if (!specs.some((entry) => entry.layer === layer)) this.pendingCoverageLanding.delete(layer);
    }
    const target = coverageLandingTarget({
      selectedAtMs: this.simulationTime().getTime(),
      readerActionCount: this.readerClockActions,
      candidates,
    });
    if (!target?.jumpToIso) return;
    this.landingCoverage = true;
    try {
      // Set BEFORE the seek: seeking ticks the clock, which redraws the legend
      // on its way past, and that redraw must already know what it is drawing.
      this.coverageLanding = { layer: target.layer, note: coverageLandingNotice({ landedAtIso: target.jumpToIso, sourceLabel: target.sourceLabel }) };
      this.seekToUtc(target.jumpToIso, true);
    } finally {
      this.landingCoverage = false;
    }
    // The legend was built for the old instant. Rebuild it so the layer shows
    // the frame it was moved to, and so the move gets said out loud.
    this.updateEnvironmentLegend();
  }

  /**
   * The plasmasphere electron-density field for one instant.
   *
   * Driven from the Kyoto quicklook Dst series alone, deliberately: it is the
   * index O'Brien & Moldwin fitted their plasmapause against, and it is the
   * only trace in the release long enough to hold a 24-hour window everywhere
   * the timeline can reach. The USGS 1-minute trace and the model trace stay
   * on the storm panel; the site's three Dst series are never merged.
   *
   * Returns a short descriptor of what the layer can currently say, so the
   * caller can put it in the signature that decides whether the legend is
   * redrawn. "none" is a state the reader has to be told about, not a state
   * to leave the previous instant's key standing in for.
   *
   * Cheap per call: two scans of an hourly series, with the geometry rebuild
   * guarded inside the globe by whether the driven values moved.
   */
  private updateInnerMagnetosphere(time: Date): string {
    const field = this.plasmasphereFieldFor(time);
    this.globe.setPlasmasphere(field);
    // The ring-current illustration is driven from the SAME evaluated field,
    // in this one call, so the two layers can never be showing different
    // instants or different convection strengths from each other.
    const ring = this.updateRingCurrent(field);
    return `${field ? field.rebuildKey : "none"}|${ring}`;
  }

  /**
   * The ring-current drift illustration for the field already evaluated above.
   *
   * Three refusals, all deliberate:
   *
   * - The layer is off: nothing is traced at all. This is the only layer in
   *   the scene whose evaluation costs real CPU per frame rather than per
   *   rebuild, and it is off by default and in no preset.
   * - The plasmasphere answered with the Carpenter & Anderson empirical
   *   profile rather than the DGCPM simulation: that profile carries no
   *   convection electric field, so there is nothing for a particle to drift
   *   in, and an illustration drawn in an invented field is precisely what
   *   this layer must never be. The card says which state it is in.
   * - Nothing about what would be drawn has changed: the traced paths stand.
   */
  private updateRingCurrent(field: PlasmasphereLayerField | null): string {
    if (!byId<HTMLInputElement>("layer-ring-current").checked) {
      if (this.ringCurrentKey !== "off") {
        this.ringCurrentKey = "off";
        this.globe.setRingCurrent(null);
      }
      return "off";
    }
    const simulated = field?.source === "dgcpm" ? field : null;
    if (!simulated) {
      if (this.ringCurrentKey !== "none") {
        this.ringCurrentKey = "none";
        this.globe.setRingCurrent(null);
      }
      return "none";
    }
    const key = `${simulated.frame.validAt}:${this.ringCurrentSpecies.chargeSign}:${this.ringCurrentSpecies.referenceEnergyKeV}`;
    if (key === this.ringCurrentKey) return key;
    this.ringCurrentKey = key;
    this.globe.setRingCurrent(ringCurrentIllustration(simulated, this.ringCurrentSpecies));
    this.frameRingCurrentWhenItExists();
    return key;
  }

  /**
   * Make room for the ring current the first time this layer has anything to
   * make room for, and exactly once per switch-on.
   *
   * The drift paths are traced asynchronously, so the switch itself frames an
   * empty group; this is the second look, once the illustration exists. It
   * WIDENS — `frameActiveLayers` keeps the reader's viewpoint and only pulls
   * back if the drawn illustration does not fit. It used to call
   * `focusPolarView()`, which rotated the whole scene down the dipole axis
   * under the reader's hands; see the layer-toggle handler for why that went.
   *
   * Still guarded by `ringCurrentFramed` rather than run on every published
   * frame: the 4 Hz clock re-evaluates this illustration, and a camera that
   * re-framed on each evaluation would fight a reader who had zoomed.
   */
  private frameRingCurrentWhenItExists() {
    if (this.ringCurrentFramed) return;
    if (!byId<HTMLInputElement>("layer-ring-current").checked) return;
    if (this.globe.getRingCurrentState() === null) return;
    this.ringCurrentFramed = true;
    this.globe.frameActiveLayers();
  }

  /**
   * Face the magnetosphere the way it was pulled up before: Sun on the LEFT.
   *
   * The rule, the two complaints it answers and the commits behind both are
   * documented on `magnetosphereOrientSpent`. Read that before changing this.
   */
  private orientMagnetosphereOnPullUp() {
    const firstPullUp = !this.magnetosphereOrientSpent;
    this.magnetosphereOrientSpent = true;
    if (!firstPullUp && this.cameraTurnedByHand()) return;
    this.globe.focusMagnetosphereObliqueView();
    this.noteSiteCameraOrientation();
  }

  /**
   * Has the reader turned the globe since the site last set the angle?
   *
   * A subtraction rather than a listener, so it cannot disagree with where
   * the camera actually is.
   *
   * TEN DEGREES, and the number is measured rather than guessed. An untouched
   * camera does not drift at all — sampled off the running page at 2, 5, 10,
   * 20 and 40 seconds after a preset, the direction moved 0.000 degrees every
   * time, and after a drag it stops inside half a second, so damping needs no
   * allowance. What the slack is actually for is larger and was a surprise:
   * switching ANY layer on shifts the camera direction by up to 5.2 degrees
   * on its own, measured at 1.3, 2.0, 2.1, 4.9 and 5.2 across five runs. That
   * is `frameActiveLayers` re-seating the camera, it predates this rule, and
   * a two-degree line would have read it as a reader's hand.
   *
   * Ten sits clear of both sides of what was measured: a reader's deliberate
   * turn was 55 to 73 degrees, and the reorientation this guards 24 to 110.
   *
   * Both ways of being wrong are not equal, and this errs the safe way: too
   * LOOSE and the site re-frames over someone who nudged the globe, which is
   * the 3fd8089 defect; too TIGHT and it merely declines to re-frame for
   * someone who did not, which costs a camera move nobody asked for out loud.
   */
  private cameraTurnedByHand() {
    const last = this.siteSetCameraDirection;
    if (!last) return false;
    const now = this.globe.cameraPose().direction;
    const alignment = last[0] * now[0] + last[1] * now[1] + last[2] * now[2];
    return alignment < Math.cos((10 * Math.PI) / 180);
  }

  /** Remember the angle the site just set, so the next hand-turn is visible. */
  private noteSiteCameraOrientation() {
    this.siteSetCameraDirection = this.globe.cameraPose().direction;
  }

  /**
   * Which plasmasphere model answers for an instant.
   *
   * The published DGCPM simulation wins wherever its frames reach, because it
   * is the only one of the two that has memory: it carries the erosion the
   * storm actually caused and the drainage plume that erosion produced. Where
   * it does not reach — before its window, and across the whole forecast half
   * of the timeline, which nothing simulates — the Carpenter & Anderson
   * empirical profile answers instead, with its own badge and its own
   * wording. The two are never blended and the reader is never left to guess
   * which one is on screen.
   */
  private plasmasphereFieldFor(time: Date): PlasmasphereLayerField | null {
    if (this.plasmasphereSequence) {
      // The WALL CLOCK, beside the selected instant. `dgcpmFieldAt` needs both:
      // the instant to choose a frame for, and the present, to tell a reader
      // sitting at now (where the newest frame is held and labelled) from a
      // reader who has scrubbed into the future (where it is refused). Without
      // this argument the hold is off and the behaviour is exactly what it was.
      const simulated = dgcpmFieldAt(this.plasmasphereSequence, time, new Date());
      if (simulated) return simulated;
    }
    const kyotoSeries = this.weather.storm?.dst.kyoto.series ?? [];
    return plasmasphereFieldAt(kyotoSeries, time);
  }

  /** Why the empirical fallback is showing, when it is. */
  private plasmasphereSimulationState(): PlasmasphereSimulationState {
    if (this.plasmasphereSequence) return "outside-window";
    if (this.plasmasphereLoadFailed) return this.manifest.plasmasphere ? "load-failed" : "not-published";
    return this.manifest.plasmasphere ? "not-loaded" : "not-published";
  }

  /**
   * Fetch the DGCPM frames, once, on demand.
   *
   * About 150 KB gzipped for 48 hours of two-hourly frames, which is why it is
   * not in the initial bundle: the layer is off by default and in no preset.
   * A structurally bad bundle is refused rather than half-decoded — a
   * misdecoded grid would draw a plausible, wrong plasmasphere, and the
   * fallback is a labelled, honest one.
   */
  private loadPlasmasphere(): Promise<void> {
    if (this.plasmasphereSequence) return Promise.resolve();
    if (this.plasmasphereLoading) return this.plasmasphereLoading;
    const record = this.manifest.plasmasphere;
    if (!record) {
      this.plasmasphereLoadFailed = true;
      return Promise.resolve();
    }
    const manifestUrl = new URL("data/manifest.json", document.baseURI);
    this.plasmasphereLoading = fetchJson<DgcpmBundle>(artifactUrl(manifestUrl, record.path))
      .then((bundle) => {
        this.plasmasphereSequence = decodeDgcpmSequence(bundle);
        this.plasmasphereLoadFailed = false;
        this.updateInnerMagnetosphere(this.simulationTime());
        this.updateEnvironmentLegend();
      })
      .catch((error: unknown) => {
        console.error("Plasmasphere simulation could not be loaded", error);
        this.plasmasphereLoadFailed = true;
        this.updateEnvironmentLegend();
      })
      .finally(() => {
        this.plasmasphereLoading = null;
      });
    return this.plasmasphereLoading;
  }

  private densityRank(index: number): [number, number] {
    const satellite = this.catalog.satellites[index];
    if (!satellite) return [99, index];
    let rank = 8;
    if (satellite.purposeKind === "curated") rank = 0;
    else if (satellite.mission === "weather" || satellite.mission === "missile-warning" || satellite.mission === "human-spaceflight") rank = 1;
    else if (satellite.sector === "military") rank = 2;
    else if (["navigation", "science", "earth-observation"].includes(satellite.mission)) rank = 3;
    else if (satellite.constellation === null) rank = 4;
    else rank = 6;
    const stable = (satellite.id * 2654435761) >>> 0;
    return [rank, stable];
  }

  private refreshVisible() {
    let candidates = this.catalog.satellites
      .map((satellite, index) => ({ satellite, index }))
      .filter(({ satellite }) => this.orbitAllows(satellite))
      .filter(({ satellite }) => this.enabledConstellations.has(satellite.constellation ?? INDEPENDENT_CONSTELLATION))
      .filter(({ satellite }) => this.enabledMissionFacets.has(missionFacet(satellite)))
      .filter(({ satellite }) => !this.visibleOwnerFilters.has(satellite.organization) || this.enabledOwners.has(satellite.organization));

    candidates.sort((a, b) => {
      const [rankA, stableA] = this.densityRank(a.index);
      const [rankB, stableB] = this.densityRank(b.index);
      return rankA - rankB || stableA - stableB;
    });
    // A narrowed facet means the visitor asked for a specific population, so
    // the featured/standard display ceiling yields — "only Starlink" must
    // show every Starlink, and since the owner list went from a top-18 slice
    // to the complete catalog, an owner narrowing counts the same way.
    const focusedCollection = this.enabledMissionFacets.size < this.missionFacetCount
      || this.enabledConstellations.size < this.constellationCount
      || this.enabledOwners.size < this.visibleOwnerFilters.size;
    const ceiling = focusedCollection
      ? Number.POSITIVE_INFINITY
      : this.density === "featured"
        ? (window.innerWidth <= 820 ? 220 : 450)
        : this.density === "standard"
          ? 2500
          : Number.POSITIVE_INFINITY;
    candidates = candidates.slice(0, ceiling);
    // ONE SOURCE OF TRUTH. What is drawn is a pure function of {scope, facets,
    // selection} and nothing else — there is no second gate held over the top
    // of the first any more. That gate is what made the rail claim "all" over
    // an empty globe: the facets really were full and the result was being
    // discarded downstream, so the controls and the globe described different
    // states and both were faithfully reporting their own.
    const filteredIndices = candidates.map(({ index }) => index);
    // The open spacecraft is drawn whether or not the filters select it — that
    // is what puts a search hit or a favourite on the globe — and it is the
    // only addition, because there is only ever one open spacecraft. The third
    // argument is `false` for good: it was the hide-every-other-marker state
    // the deleted View Selected / View All control set, and one spacecraft
    // cannot be scoped against itself.
    this.visibleIndices = resolveVisibleIndices(filteredIndices, this.selectedIndex, false);
    this.globe.setVisible(this.visibleIndices);
    this.updateSatelliteColorEncoding();
    this.propagator.setIndices(this.visibleIndices);
    // "start with 'Satellite Catalog' and to the right 'x Selected'". It
    // counts what the catalog selection has put on the globe, which is the
    // fact the heading row is for and the fact Clear beside it undoes.
    byId("visible-count").textContent = `${this.visibleIndices.size.toLocaleString()} Selected`;
    this.updateFilterState();
    this.propagate();
  }

  /* `updateFilterStackSummary()` IS GONE with the fold it summarised. It wrote
     "2 active · 412 of 8,000" onto the "Catalog filters" summary row, and Sean
     cut both: "don't have 'catalog Filters' just Mission Types,
     Constellations/Fleets, Owners/Organizations... and no 'x active'". Each
     list still reports its own state in its own summary — none / 3 of 12 /
     all — counted inside the live band, and the catalog's heading row carries
     the only total there is now. */

  private updateFilterState() {
    const facet = (id: string, selected: number, total: number) => {
      const element = document.getElementById(id);
      if (!element) return;
      const chip = facetChipText(selected, total);
      element.textContent = chip.text;
      element.dataset.state = chip.state;
    };
    // Counted against what the band actually offers, not against the whole
    // catalog: inside LEO, "all" has to mean all of LEO. Counting the catalog
    // made every chip read "3 of 412" the moment a band was picked, which is
    // the same class of untruth as a ticked box over an empty globe.
    const scope = this.scopedFacetCounts();
    facet("mission-facet-state", scope.selected.mission, scope.available.mission);
    facet("constellation-facet-state", scope.selected.constellation, scope.available.constellation);
    facet("owner-facet-state", scope.selected.owner, scope.available.owner);
    this.paintFacetContext();

    // THE ONLY THING THAT MAY SPEAK IS A CHANGE THE READER DID NOT MAKE.
    //
    // This row used to be the site's answer to "the selection is empty" —
    // "0 shown - nothing selected", with "Show every satellite again" beside
    // it — and once the bare globe made empty the correct starting state, that
    // answer fired on arrival and nagged the reader about a state he had
    // chosen. Sean: "Duh. I cleared everything. Why am I getting an error", and
    // then, on the button: "Stop that shit. You keep adding a feature there."
    //
    // The mapping is gone rather than reworded. There is no longer a function
    // anywhere that turns "empty" into a sentence, so the next control added
    // near here cannot reintroduce one by calling it. What is left is a single
    // channel with a single writer: `filterLinkNote`, set only when healing
    // changed the selection on the reader's behalf. Everything else is silent.
    const status = byId("filter-status");
    const message = this.filterLinkNote;
    status.hidden = message === null;
    byId("filter-status-text").hidden = message === null;
    byId("filter-status-text").textContent = message ?? "";
  }

  private updateSatelliteColorEncoding() {
    const legend = byId("satellite-legend");
    // A key to nothing is worse than no key, and an empty globe is now the
    // only way to get there — Space Weather mode used to be the other, by
    // drawing no satellites at all.
    legend.hidden = this.visibleIndices.size === 0;
    const renderLegend = (entries: Array<{ label: string; color: string }>, ariaLabel: string) => {
      legend.setAttribute("aria-label", ariaLabel);
      legend.replaceChildren(...entries.map(({ label, color }) => {
        const item = document.createElement("span");
        const swatch = document.createElement("i");
        swatch.style.setProperty("--legend", color);
        item.append(swatch, label);
        return item;
      }));
    };
    if (this.colorMode === "mission") {
      this.globe.setSatelliteColors(this.catalog.satellites.map((satellite) => missionColors[satellite.mission]));
      renderLegend([
        { label: "Weather", color: "#29d4e3" },
        { label: "SATCOM", color: "#f5c96a" },
        { label: "Missile warning / OPIR", color: "#ff7b78" },
        { label: "Navigation", color: "#a98cff" },
        { label: "Science / Earth", color: "#76e6a5" },
        { label: "Other", color: "#b9c9d3" },
      ], "Satellite mission colors");
      return;
    }

    const categoryFor = (satellite: SatelliteRecord) => this.colorMode === "constellation"
      ? satellite.constellation ?? "No named fleet identified"
      : satellite.ownerLabel || "Unknown / TBD";
    const counts = new Map<string, number>();
    this.visibleIndices.forEach((index) => {
      const satellite = this.catalog.satellites[index];
      if (!satellite) return;
      const category = categoryFor(satellite);
      counts.set(category, (counts.get(category) ?? 0) + 1);
    });
    const categoryLimit = window.innerWidth <= 820 ? 4 : 7;
    const leaders = Array.from(counts.entries())
      .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
      .slice(0, categoryLimit);
    const palette = ["#29d4e3", "#f5c96a", "#ff7b78", "#a98cff", "#76e6a5", "#ff9f68", "#6fb4ff"];
    const leaderColors = new Map(leaders.map(([category], index) => [category, palette[index] ?? "#b9c9d3"]));
    const fallback = "#71858d";
    this.globe.setSatelliteColors(this.catalog.satellites.map((satellite) => leaderColors.get(categoryFor(satellite)) ?? fallback));
    const entries = leaders.map(([category, count]) => ({ label: `${category} (${count.toLocaleString()})`, color: leaderColors.get(category)! }));
    if (counts.size > leaders.length) entries.push({ label: `Other (${Array.from(counts.values()).reduce((sum, count) => sum + count, 0) - leaders.reduce((sum, [, count]) => sum + count, 0)})`, color: fallback });
    if (entries.length === 0) entries.push({ label: "No satellites shown", color: fallback });
    renderLegend(entries, this.colorMode === "constellation" ? "Satellite constellation colors" : "Satellite country colors");
  }

  private propagate() {
    const realIntervalMs = this.orbitSolutionIntervalMs();
    const simulatedHorizonMs = this.pausedAt ? 0 : Math.round(realIntervalMs * this.simulationRate());
    this.propagator.propagate(this.simulationTime(), simulatedHorizonMs);
  }

  private seekSatelliteTime(time = this.simulationTime()) {
    this.snapSolutionAtMs = time.getTime();
    this.globe.holdSatelliteInterpolation();
    this.propagator.propagate(time, 0);
  }

  private handleVisibilityChange() {
    if (document.hidden) {
      this.hiddenAt = performance.now();
      window.clearTimeout(this.propagationTimer);
      this.globe.holdSatelliteInterpolation();
      return;
    }
    if (this.hiddenAt === null) return;
    const hiddenDurationMs = Math.max(0, performance.now() - this.hiddenAt);
    this.hiddenAt = null;
    if (this.timedPlayback) this.timedPlayback.startedAt += hiddenDurationMs;
    const resumeTime = this.simulationTime();
    this.seekSatelliteTime(resumeTime);
    this.tickClock();
    this.refreshSelectedGeometry();
    this.schedulePropagation();
  }

  private schedulePropagation() {
    window.clearTimeout(this.propagationTimer);
    // Refresh before the current interpolation reaches its endpoint so worker
    // latency never creates a visible pause between orbital solutions.
    const refreshAfterMs = Math.max(500, Math.round(this.orbitSolutionIntervalMs() * 0.82));
    this.propagationTimer = window.setTimeout(() => {
      this.propagate();
      this.schedulePropagation();
    }, refreshAfterMs);
  }

  private orbitSolutionIntervalMs() {
    if (this.visibleIndices.size <= 500) return 2000;
    if (this.visibleIndices.size <= 2500) return 4000;
    return 6000;
  }

  private simulationTime(): Date {
    if (this.timedPlayback) {
      const progress = Math.min(1, Math.max(0, (performance.now() - this.timedPlayback.startedAt) / this.timedPlayback.wallDurationMs));
      return new Date(this.timedPlayback.startMs + (this.timedPlayback.endMs - this.timedPlayback.startMs) * progress);
    }
    return this.pausedAt ?? new Date(Date.now() + this.timeOffsetMinutes * 60000);
  }

  /**
   * Draw NOAA WAM's span on the timeline itself, when the layer is on.
   *
   * The number that made this necessary: the slider is 120 hours and one WAM
   * release covers 11.8 of them, 9.8%. Two models now share this layer and the
   * reader has to be able to SEE where the boundary is, not discover it by
   * scrubbing into it — so the assimilated-grade span is a mark on the track at
   * the hours it is true of, and everything either side of it is the empirical
   * field. The band is not a control and does not take pointer events; it is
   * the same class of thing as the NOW marker beside it.
   *
   * Hidden when the layer is off, when there is no WAM in the release, and when
   * WAM's span does not intersect the slider at all — `coverageBandPercent`
   * returns null for the last of those rather than a zero-width mark, because a
   * mark at 0%–0% is a claim about the first instant of the timeline.
   */
  private updateThermosphereCoverageBand() {
    const band = document.getElementById("time-coverage-band");
    if (!band) return;
    const record = this.manifest.thermosphere;
    const on = byId<HTMLInputElement>("layer-thermosphere").checked;
    const now = Date.now();
    const span = on && record
      ? coverageBandPercent(record, { startMs: now - 2880 * 60_000, endMs: now + 4320 * 60_000 })
      : null;
    if (!span) {
      band.hidden = true;
      return;
    }
    band.hidden = false;
    band.style.setProperty("--band-start", `${span.startPercent.toFixed(2)}%`);
    band.style.setProperty("--band-end", `${span.endPercent.toFixed(2)}%`);
    band.title = `NOAA WAM covers ${record!.validFrom.slice(11, 16)}Z–${record!.validTo.slice(11, 16)}Z. Everywhere else on this timeline the thermosphere is NRLMSIS, and the card says so.`;
  }

  private simulationRate() {
    if (!this.timedPlayback) return 1;
    return (this.timedPlayback.endMs - this.timedPlayback.startMs) / this.timedPlayback.wallDurationMs;
  }

  private updateTimelineTooltip() {
    if (!this.timelineTooltipVisible) return;
    const slider = byId<HTMLInputElement>("time-slider");
    const shell = byId("time-slider-shell");
    const tooltip = byId<HTMLOutputElement>("time-slider-tooltip");
    const value = Number(slider.value);
    const minimum = Number(slider.min);
    const maximum = Number(slider.max);
    const selected = new Date(Date.now() + value * 60_000);
    const strong = tooltip.querySelector("strong");
    const detail = tooltip.querySelector("span");
    if (strong) strong.textContent = selected.toISOString().slice(0, 16).replace("T", " ");
    if (detail) detail.textContent = "UTC";
    tooltip.classList.add("is-visible");
    requestAnimationFrame(() => {
      if (!this.timelineTooltipVisible) return;
      const shellBounds = shell.getBoundingClientRect();
      const sliderBounds = slider.getBoundingClientRect();
      const progress = maximum === minimum ? 0 : (value - minimum) / (maximum - minimum);
      const thumbX = sliderBounds.left - shellBounds.left + progress * sliderBounds.width;
      const width = tooltip.offsetWidth;
      const left = Math.max(0, Math.min(Math.max(0, shellBounds.width - width), thumbX - width / 2));
      const pointerX = Math.max(8, Math.min(Math.max(8, width - 8), thumbX - left));
      tooltip.style.left = `${left}px`;
      tooltip.style.setProperty("--pointer-x", `${pointerX}px`);
    });
  }

  private tickClock() {
    if (document.hidden) return;
    let time = this.simulationTime();
    if (this.timedPlayback && performance.now() - this.timedPlayback.startedAt >= this.timedPlayback.wallDurationMs) {
      const completed = this.timedPlayback;
      this.timedPlayback = null;
      this.pausedAt = new Date(completed.endMs);
      this.timeOffsetMinutes = Math.round((completed.endMs - Date.now()) / 60000);
      byId("time-play").textContent = "▶";
      byId("time-play").setAttribute("aria-label", "Resume simulation");
      time = this.pausedAt;
      this.propagate();
      this.refreshSelectedGeometry();
    }
    // The clock now shares the timeline row instead of floating over the
    // globe on its own. On narrow layouts the date would push the timeline
    // controls off the edge, so the date drops and the time keeps its Z.
    byId("sim-time").textContent = this.compactClockQuery.matches
      ? `${time.toISOString().slice(11, 19)}Z`
      : `${time.toISOString().slice(0, 19).replace("T", " ")} UTC`;
    const label = byId("sim-label");
    if (this.timedPlayback) {
      const progress = Math.min(100, Math.round(((performance.now() - this.timedPlayback.startedAt) / this.timedPlayback.wallDurationMs) * 100));
      label.textContent = `PLAYING ${this.timedPlayback.label} · ${progress}%`;
    } else {
      label.textContent = this.pausedAt ? "PAUSED" : this.timeOffsetMinutes === 0 ? "LIVE" : `${this.timeOffsetMinutes > 0 ? "+" : ""}${this.timeOffsetMinutes} MIN`;
    }
    const offset = Math.round((time.getTime() - Date.now()) / 60000);
    byId<HTMLInputElement>("time-slider").value = String(Math.max(-2880, Math.min(4320, offset)));
    this.updateTimelineTooltip();
    this.updateThermosphereCoverageBand();
    this.globe.setSimulationTime(time);
    this.globe.setSubstormState(this.substormStateAtTime(time));
    this.updateGeospaceRuntimeUi();
    this.updateSurfaceEnvironmentStatus();
    this.updateIonosphereSelection(time);
    // The thermosphere picks a frame by time like every other published field,
    // and until now was the only one never asked to pick again.
    this.applyThermosphereFrame();
    this.updateTimeSelectedEnvironment(time);
    if (this.timedPlayback && this.selectedIndex !== null && performance.now() - this.lastPlaybackGeometryUpdate >= 750) {
      this.lastPlaybackGeometryUpdate = performance.now();
      this.refreshSelectedGeometry();
    }
  }

  /**
   * The propagated solar-wind sample for one instant, or `null`.
   *
   * Extracted so the three places that rebuild the boundary — first paint, a
   * scrub, and an artifact hot-swap — all hand the globe the *same* object.
   * They used to hand it two loose numbers, which is why the cusped boundaries
   * could not be drawn at all: `By` and `Bt` never left this file.
   */
  /**
   * The measured substorm state at an instant, or null where nothing measures
   * it.
   *
   * Two published series feed this and neither is invented:
   *
   *   - `magnetopause.driverSeries` — the propagated L1 solar wind, whose
   *     `validAt` is already the Earth-arrival time. 587 samples at 5 minutes
   *     over 48.8 hours, the same rows the Shue boundary is driven from, and
   *     its `bzGsmNt` is the site's only multi-day Bz record. The 5.8-hour
   *     `imf.series` is a stub by comparison.
   *   - `storm.dst.kyoto.series` — 168 hourly samples over seven days, the
   *     measured ring-current response.
   *
   * There is no auroral-electrojet index in any live feed this site fetches,
   * so `substormStateAt` falls back to the Dst series and labels what it
   * produces `"ring-current-response"` rather than an onset. Nothing here
   * hands it an SML series: the only one this project holds is the May 2024
   * Gannon week inside the events bundle, which drives its own replay.
   *
   * Returns null forward of the driver record. The site's timeline runs 72
   * hours into the future and the propagated wind reaches about 40 minutes
   * ahead of now, so most of that half has no measured Bz — and an unloaded
   * tail drawn there would be a claim about the future.
   */
  /**
   * The MEASURED rate the Dungey-cycle transport is animated at, or null.
   *
   * `newellCoupling` is the published Newell et al. (2007) coupling function
   * — `dPhi_MP/dt = v^(4/3) B_T^(2/3) sin^(8/3)(theta_c/2)` — evaluated on the
   * propagated L1 speed, By and Bz this page already prints on the rail. It is
   * the rate at which flux is OPENED at the dayside, so it is exactly the
   * quantity that decides how much material ends up in the plasma sheet, the
   * ring current and the aurora. `couplingDrive` then places it on the band
   * ladder the pipeline publishes with the storm artifact, so no constant of
   * this page's own enters the picture.
   *
   * Null when the drivers are missing, and null is not zero: zero is a
   * measured northward IMF opening almost no flux, while null is no propagated
   * wind at all, at which point there is no rate and nothing is drawn. Null
   * also when the artifact carries no band ladder, because grading the drive
   * against a scale no reader ever sees would be worse than not drawing it.
   */
  private dungeyCouplingDrive(driver: MagnetopauseDriverSample | null | undefined): number | null {
    if (!driver) return null;
    const coupling = newellCoupling(driver.speedKps, driver.byNt, driver.bzGsmNt);
    return couplingDrive(coupling, this.weather.storm?.derived?.newellCalibration ?? []);
  }

  private substormStateAtTime(time: Date): SubstormState | null {
    const drivers = this.weather.magnetopause?.driverSeries ?? [];
    if (drivers.length === 0) return null;
    const bz: IndexSample[] = drivers.map((row) => ({
      atMs: Date.parse(row.validAt),
      valueNt: row.bzGsmNt,
    }));
    const latest = bz.reduce((newest, sample) => Math.max(newest, sample.atMs), 0);
    const earliest = bz.reduce((oldest, sample) => Math.min(oldest, sample.atMs), Infinity);
    const atMs = time.getTime();
    if (!(atMs >= earliest && atMs <= latest)) return null;
    const dst: IndexSample[] = (this.weather.storm?.dst.kyoto.series ?? []).map((row) => ({
      atMs: Date.parse(row.at),
      valueNt: row.dstNt,
    }));
    return substormStateAt({ bz, dst }, atMs);
  }

  private magnetopauseDriverAt(time: Date): MagnetopauseDriverSample | null {
    const nearCurrent = Math.abs(time.getTime() - Date.now()) <= 15 * 60_000;
    return sampleMagnetopauseDriver(this.weather.magnetopause.driverSeries ?? [], time)
      ?? (nearCurrent && this.weather.solarWind.speedKps !== null
        && this.weather.solarWind.densityCm3 !== null
        && this.weather.imf.bzGsmNt !== null
        && this.weather.magnetopause.subsolarStandoffRe !== null
        && this.weather.magnetopause.flaringAlpha !== null
        ? {
            validAt: this.weather.solarWind.observedAt,
            observedAt: this.weather.solarWind.observedAt,
            speedKps: this.weather.solarWind.speedKps,
            densityCm3: this.weather.solarWind.densityCm3,
            bzGsmNt: this.weather.imf.bzGsmNt,
            dynamicPressureNpa: this.weather.solarWind.dynamicPressureNpa ?? 0,
            subsolarStandoffRe: this.weather.magnetopause.subsolarStandoffRe,
            flaringAlpha: this.weather.magnetopause.flaringAlpha,
            // The current-conditions snapshot publishes |B| but no By, so this
            // fallback can drive Shue and nothing else. That is the honest
            // outcome: the globe falls back to Shue and says why.
            byNt: null,
            btNt: this.weather.imf.btNt ?? null,
            magneticPressureNpa: null,
          }
        : null);
  }

  private updateTimeSelectedEnvironment(time: Date) {
    const nearCurrent = Math.abs(time.getTime() - Date.now()) <= 15 * 60_000;
    const driver = this.magnetopauseDriverAt(time);
    const xrayFlux = sampleLogTimeValue(this.weather.xray.series, time)
      ?? (nearCurrent ? this.weather.xray.fluxWm2 : null);
    this.currentMagnetopauseDriver = driver;
    this.currentXrayFlux = xrayFlux;
    // The plasmasphere is evaluated HERE, before the legend is rendered, and
    // its state joins the change signature below.
    //
    // It used to be evaluated at the bottom of this method, after the legend
    // had already been drawn, and the signature that decides whether to draw
    // the legend at all was built only from the solar-wind driver and the
    // X-ray flux — nothing about the Dst record. Two failures followed, and
    // together they are exactly the reported one: the key was always one
    // instant stale, and when the solar wind and X-ray happened not to move
    // between two instants it was not redrawn at all. Scrub past the end of
    // the Kyoto Dst record and the field correctly evaluates to null, the
    // globe correctly draws nothing — and the key sits there still showing a
    // full electron-density ramp, with the no-data notice this site relies on
    // nowhere on screen. A layer that cannot answer has to say so.
    const plasmasphereSignature = this.updateInnerMagnetosphere(time);
    // The cusped boundaries also move with the dipole tilt, which changes with
    // UTC even when the solar wind is dead steady, so the selected time is part
    // of what decides whether the surfaces have to be rebuilt. It is bucketed
    // to two minutes: the tilt moves at most about a quarter of a degree a
    // minute, and three empirical surfaces plus the cusp shell is real work to
    // rebuild at the clock's 4 Hz.
    const tiltBucket = driver ? Math.round(time.getTime() / 120_000) : 0;
    const signature = (driver
      ? `${driver.speedKps.toFixed(2)}:${driver.densityCm3.toFixed(3)}:${driver.bzGsmNt.toFixed(3)}:${driver.byNt?.toFixed(3) ?? "none"}:${driver.btNt?.toFixed(3) ?? "none"}:${driver.subsolarStandoffRe.toFixed(3)}:${driver.flaringAlpha.toFixed(4)}:${tiltBucket}:${xrayFlux?.toExponential(3) ?? "none"}`
      : `none:${xrayFlux?.toExponential(3) ?? "none"}`)
      + `:${plasmasphereSignature}`;
    if (signature !== this.lastEnvironmentSignature) {
      this.lastEnvironmentSignature = signature;
      this.globe.setSolarWindConditions(driver?.speedKps ?? null, driver?.densityCm3 ?? null);
      this.globe.setDungeyCouplingDrive(this.dungeyCouplingDrive(driver));
      this.globe.setMagnetopause(driver);
      this.globe.setPhotonFlux(xrayFlux);
      // Tell the page — and through it the walkthrough, which probes for this
      // attribute — whether the boundary actually drawn right now is the
      // cusped set or the Shue fallback. Derived from what the globe drew,
      // never asserted from here.
      const magnetosphereBox = byId<HTMLInputElement>("annotate-empirical-boundaries");
      const cuspedDrawn = this.globe.getMagnetopauseLegend()
        .some((entry) => entry.id === "nguyen2022" || entry.id === "lin2010");
      if (cuspedDrawn) magnetosphereBox.setAttribute("data-magnetopause-surface", "cusped");
      else magnetosphereBox.removeAttribute("data-magnetopause-surface");
      byId("wind-speed").textContent = driver ? displayNumber(driver.speedKps) : "—";
      byId("imf-bz").textContent = driver ? displayNumber(driver.bzGsmNt, 1) : "—";
      byId("xray-class").textContent = goesXrayClass(xrayFlux);
      this.updateConditionsSummary();
      this.updateEnvironmentLegend();
    }
    // WHAT TIME THE SEVEN NUMBERS ARE FOR. It rides the fold's summary row now
    // — see the comment on it in index.html — because the line it replaced led
    // with how the numbers were obtained rather than with the fact a reader
    // needs, which is that these move with the time slider. The obtaining is
    // still here, on the row's tooltip, for anyone who wants it.
    const stamp = `${time.toISOString().slice(0, 16).replace("T", " ")} UTC`;
    const valid = byId("weather-valid-time");
    const available = driver !== null || xrayFlux !== null;
    valid.dataset.state = available ? "available" : "unavailable";
    valid.textContent = available ? stamp : `no data · ${stamp}`;
    valid.title = available
      ? `${[driver ? "Solar wind, propagated to Earth" : null, xrayFlux !== null ? "GOES X-ray" : null]
        .filter((part) => part !== null).join(" · ")}, at ${stamp}.`
      : `Neither a solar-wind nor an X-ray measurement covers ${stamp}.`;
    this.updateStormPanel(time);
  }

  /**
   * Draw the storm strip chart for the selected instant.
   *
   * `renderStormPanel` returns `null` when the artifact carries no storm block
   * at all — an older release, or one where every upstream Dst source was
   * down — and in that case the whole section is hidden rather than left as an
   * empty frame. It replaces the container's children on every call, so it is
   * safe to call on every scrub.
   *
   * The clock ticks four times a second and this rebuilds an SVG, so it is
   * gated on the artifact plus the selected minute. The chart's horizontal axis
   * spans 24 hours across roughly 570 drawn pixels: a minute is a third of a
   * pixel, so nothing visible is lost and 239 of every 240 rebuilds are.
   */
  private updateStormPanel(time: Date) {
    const storm = this.weather.storm;
    const signature = storm
      ? `${storm.validAt}:${Math.floor(time.getTime() / 60_000)}`
      : "none";
    if (signature === this.lastStormPanelSignature) return;
    this.lastStormPanelSignature = signature;

    // The indicator first, because it decides whether anything is shown at all.
    // A quiet or unclassified field produces no headline, and then there is no
    // chip, no dropdown and no reconciliation note — the top bar is untouched.
    const headline = stormHeadline(storm, this.weather.magnetopause.driverSeries, time);
    const chip = byId<HTMLButtonElement>("storm-chip");
    chip.hidden = headline === null;
    chip.dataset.phase = headline?.phase ?? "";
    byId("storm-chip-label").textContent = headline ? ` storm · ${headline.chipLabel}` : "";
    // A phone top bar has room for one short phrase. Which words survive is a
    // CSS decision, so both are written and only one is ever displayed.
    byId("storm-chip-brief").textContent = headline
      ? `Storm · ${headline.dstNt === null ? headline.chipLabel.split(" · ")[0] : headline.chipLabel.split(" · ").slice(-1)[0]}`
      : "";
    chip.title = headline ? withMinusSigns(headline.reason) : "";
    // The tab title too. A background tab is the one surface that reaches a
    // reader who is not looking at the page, which is exactly the case a storm
    // indicator exists for — and it goes back to the plain title the moment
    // the classification does, so a quiet day leaves no trace of it.
    document.title = headline
      ? `${STORM_TITLE_MARK} ${headline.chipLabel.split(" · ").slice(0, 2).join(" · ")} storm · ${BASE_TITLE}`
      : BASE_TITLE;
    if (!headline) {
      this.setStormDropdownOpen(false);
      byId("swpc-scale-conflict").hidden = true;
      return;
    }

    byId("storm-reason").textContent = withMinusSigns(`${headline.reason}.`);
    const reconciliation = kpDstReconciliation({
      kpIndex: this.weather.geomagnetic.kp,
      gLevel: this.weather.outlook?.noaaScales.latestObserved.geomagnetic.level ?? null,
      dstNt: headline.dstNt,
      dstSource: headline.dstSource,
    });
    const reconcile = byId("storm-reconcile");
    reconcile.textContent = reconciliation ?? "";
    reconcile.hidden = reconciliation === null;
    // The same fact, made visible where the contradiction is actually seen:
    // beside the G-scale strip that reads G0.
    const conflict = byId<HTMLButtonElement>("swpc-scale-conflict");
    conflict.hidden = reconciliation === null;
    conflict.textContent = reconciliation === null
      ? ""
      : `G0 disagrees with ${headline.chipLabel.split(" · ").pop()} — why? →`;
    // And once more inside Current Analysis, which is Kp-based and will state
    // the opposite of the classification in the same fold. It is ONE SENTENCE
    // in that fold's own first paragraph now, rather than a bordered panel of
    // its own in a third text size — and it is written by the same method that
    // writes the paragraph it qualifies, so the two cannot describe different
    // instants. Silent while the two agree.
    this.kpDstDisagreement = reconciliation !== null;
    this.renderCurrentAnalysis();

    renderStormPanel(
      byId("storm-panel"),
      storm,
      this.weather.magnetopause.driverSeries,
      { selectedTime: time, historyHours: 24 },
    );
    byId("storm-panel").querySelectorAll<HTMLElement>("[data-card-section]").forEach((section) => {
      const name = section.dataset.cardSection ?? "";
      if (name in this.cardSectionOpen) section.toggleAttribute("open", this.cardSectionOpen[name] === true);
      this.bindCardSection(section);
    });
  }

  private setStormDropdownOpen(open: boolean) {
    byId("storm-dropdown").hidden = !open;
    byId("storm-chip").setAttribute("aria-expanded", String(open));
  }

  /**
   * "Show me this storm."
   *
   * Dst is a global scalar — it has no map, and synthesising one from it would
   * be inventing a field. What the storm does have is a spatial signature
   * already spread across three layers this site publishes honestly and which
   * had never been connected: the auroral oval expands equatorward, the
   * magnetopause is pushed inward by the same solar wind, and the belts
   * respond. Switching those three on together is the connection Sean asked
   * for between solar wind, belts and aurora, made out of real data.
   */
  private showStormOnGlobe() {
    // There is no mode to change first any more, and that used to be this
    // method's whole correctness: `setMode` re-applied the current layer preset,
    // so enabling these three layers and THEN switching mode turned them
    // straight back off. It shipped that way to the live site on 2026-08-08 and
    // Sean saw a legend reading "1 LAYER". With the mode gone the hazard is
    // gone with it — nothing between here and the globe can un-tick a layer
    // this method ticks.
    // The storm view leads with the field: the compressed dayside and the
    // thickened sheath ARE the storm's magnetospheric signature, and they are
    // in the plasma-field colours, not in an empirical outline.
    (["aurora", "geospace", "radiation"] as const).forEach((layer) => {
      const controlId = ExplorerApp.layerCheckboxIds[layer];
      if (controlId) byId<HTMLInputElement>(controlId).checked = true;
      // Through applyGlobeLayer rather than globe.setLayer, which is the same
      // path the checkboxes themselves take: one layer in the rail can be
      // several regions on the globe, and only this wrapper knows that.
      this.applyGlobeLayer(layer, true);
    });
    this.updateModelControlVisibility();
    this.updateAuroraControlVisibility();
    this.updateEnvironmentLegend();
    this.globe.frameActiveLayers();
    void this.loadAuroraHistoryModel();
    void this.loadGeospaceModel();
    this.setStormDropdownOpen(false);
  }

  private toggleTime() {
    this.noteReaderClockAction();
    const button = byId("time-play");
    if (this.timedPlayback) {
      this.pausedAt = this.simulationTime();
      this.timedPlayback = null;
      this.timeOffsetMinutes = Math.round((this.pausedAt.getTime() - Date.now()) / 60000);
      button.textContent = "▶";
      button.setAttribute("aria-label", "Resume simulation");
    } else if (this.pausedAt) {
      this.timeOffsetMinutes = Math.round((this.pausedAt.getTime() - Date.now()) / 60000);
      this.pausedAt = null;
      button.textContent = "Ⅱ";
      button.setAttribute("aria-label", "Pause simulation");
    } else {
      this.pausedAt = this.simulationTime();
      button.textContent = "▶";
      button.setAttribute("aria-label", "Play simulation");
    }
    this.tickClock();
    this.propagate();
    this.refreshSelectedGeometry();
  }

  private startTimedPlayback(durationMinutes: number, wallDurationMs = 30_000) {
    this.noteReaderClockAction();
    const boundedDuration = [30, 120, 360, 1440].includes(durationMinutes) ? durationMinutes : 120;
    let start = this.simulationTime();
    const latestAllowed = Date.now() + 4320 * 60000;
    if (start.getTime() >= latestAllowed - 60_000) start = new Date();
    const endMs = Math.min(start.getTime() + boundedDuration * 60000, latestAllowed);
    this.pausedAt = null;
    this.timedPlayback = {
      startMs: start.getTime(),
      endMs,
      startedAt: performance.now(),
      wallDurationMs: [60_000, 30_000, 15_000, 8_000].includes(wallDurationMs) ? wallDurationMs : 30_000,
      label: boundedDuration < 60 ? `${boundedDuration}M` : `${boundedDuration / 60}H`,
    };
    this.timeOffsetMinutes = Math.round((start.getTime() - Date.now()) / 60000);
    this.lastPlaybackGeometryUpdate = 0;
    byId("time-play").textContent = "Ⅱ";
    byId("time-play").setAttribute("aria-label", "Pause timed playback");
    this.tickClock();
    this.propagate();
    this.refreshSelectedGeometry();
  }

  private returnToNow() {
    this.noteReaderClockAction();
    this.timedPlayback = null;
    this.pausedAt = null;
    this.timeOffsetMinutes = 0;
    byId<HTMLInputElement>("time-slider").value = "0";
    byId("time-play").textContent = "Ⅱ";
    byId("time-play").setAttribute("aria-label", "Pause simulation");
    this.tickClock();
    this.seekSatelliteTime();
    this.refreshSelectedGeometry();
  }

  /**
   * Move the simulation clock to a specific UTC instant, clamped to the range
   * the slider can express. This is what the "go to a time this layer covers"
   * button in a no-data key card does: it does not just explain the gap, it
   * gets the visitor out of it.
   */
  private seekToUtc(iso: string, hold = false) {
    const target = Date.parse(iso);
    if (!Number.isFinite(target)) return;
    const slider = byId<HTMLInputElement>("time-slider");
    const minimum = Number(slider.min);
    const maximum = Number(slider.max);
    const minutes = Math.round((target - Date.now()) / 60_000);
    const clamped = Math.min(Math.max(minutes, minimum), maximum);
    this.timedPlayback = null;
    this.timeOffsetMinutes = clamped;
    slider.value = String(clamped);
    // An automatic landing HOLDS the clock; a reader who pressed the button
    // does not get held, because they can see what they did and press it
    // again. The hold is not tidiness: the landing instant is a minute inside
    // the window on purpose, so a clock still running at real time carries the
    // reader out of coverage about sixty seconds later and the layer they just
    // switched on goes blank again — the defect, restored on a timer.
    //
    // Held at the instant asked for, not at the rounded minute the slider can
    // express. The slider is minute-resolution, so `clamped` is up to thirty
    // seconds away — measured: the clock read 13:57:32 while the card beside
    // it announced a move to 13:58 UTC, which is the card describing a time
    // the site is not showing. The card names the instant that is held.
    this.pausedAt = hold ? new Date(Math.min(Math.max(target, Date.now() + minimum * 60_000), Date.now() + maximum * 60_000)) : null;
    byId("time-play").textContent = hold ? "▶" : "Ⅱ";
    byId("time-play").setAttribute("aria-label", hold ? "Resume simulation" : "Pause simulation");
    this.tickClock();
    this.seekSatelliteTime();
    this.refreshSelectedGeometry();
  }

  /**
   * The reader moved the clock themselves.
   *
   * Counting it is what separates the two behaviours: a layer switched on
   * before this count changed may still land, and a layer whose data arrives
   * after it may not, because that clock position is now the reader's choice
   * and taking it away is worse than an empty layer. Clearing the landing also
   * takes down a note that describes a clock position that no longer exists.
   */
  private noteReaderClockAction() {
    this.readerClockActions += 1;
    this.coverageLanding = null;
  }

  private showSearchResults(query: string) {
    const results = byId("search-results");
    const normalized = query.trim().toUpperCase();
    this.searchMatches = this.catalog.satellites
      .map((satellite, index) => ({ satellite, index }))
      .filter(({ satellite }) => normalized.length === 0
        || satellite.name.toUpperCase().startsWith(normalized)
        || String(satellite.id).startsWith(normalized))
      .sort((left, right) => left.satellite.name.localeCompare(right.satellite.name) || left.satellite.id - right.satellite.id);
    this.searchRenderedCount = 0;
    results.replaceChildren();
    results.scrollTop = 0;
    if (this.searchMatches.length === 0) {
      const empty = document.createElement("p");
      empty.className = "search-empty";
      empty.textContent = "No satellite names or NORAD IDs begin with that text.";
      results.append(empty);
    } else {
      this.appendSearchResults();
    }
    results.hidden = false;
  }

  private appendSearchResults() {
    const results = byId("search-results");
    if (this.searchRenderedCount >= this.searchMatches.length) return;
    const next = this.searchMatches.slice(this.searchRenderedCount, this.searchRenderedCount + 80);
    results.append(...next.map(({ satellite, index }) => this.satelliteRow(
      satellite.id,
      satellite.name,
      [satellite.orbit, `NORAD ${satellite.id} · ${satellite.organization}`],
      () => {
        this.selectSatellite(index, true);
        byId<HTMLInputElement>("satellite-search").value = satellite.name;
        this.hideSearchResults();
      },
    )));
    this.searchRenderedCount += next.length;
  }

  private hideSearchResults() {
    byId("search-results").hidden = true;
  }

  /**
   * One satellite, offered on its own: the button that opens it, and the star
   * that keeps it. Search results and the favorites list are the same object
   * in two places, so they are built here rather than twice, and cannot drift
   * into looking or behaving differently.
   *
   * The wrapper takes `role="none"` so the button inside stays the listbox's
   * option — the wrapper is layout, not structure. `onSelect` is null for a
   * favorite whose object this release no longer publishes: there is nothing
   * to open, so the row is inert and greyed, but its star still works, which
   * is the only control that row needs.
   */
  private satelliteRow(id: number, name: string, lines: [string, string], onSelect: (() => void) | null): HTMLElement {
    const row = document.createElement("div");
    row.className = "search-result-row";
    row.setAttribute("role", "none");
    const button = document.createElement("button");
    button.className = "search-result";
    button.setAttribute("role", "option");
    const heading = document.createElement("strong");
    heading.textContent = name;
    button.append(heading, ...lines.map((line) => {
      const span = document.createElement("span");
      span.textContent = line;
      return span;
    }));
    if (onSelect) button.addEventListener("click", onSelect);
    else button.disabled = true;
    row.append(button, this.favoriteStar(id, name));
    return row;
  }

  /** The star affordance itself, wherever a single spacecraft is presented. */
  private favoriteStar(id: number, name: string): HTMLButtonElement {
    const star = document.createElement("button");
    star.type = "button";
    star.className = "favorite-star";
    this.bindFavoriteStar(star, id, name);
    return star;
  }

  /**
   * Point one star element at one spacecraft. Used both for the stars this
   * file creates and for the one baked into the satellite-card template, so
   * every star on the page carries the same dataset and the same handler.
   */
  private bindFavoriteStar(star: HTMLElement, id: number, name: string) {
    star.dataset.favoriteId = String(id);
    star.dataset.favoriteName = name;
    this.paintFavoriteStar(star);
    star.addEventListener("click", (event) => {
      event.stopPropagation();
      this.toggleFavoriteSatellite(id);
    });
  }

  /** Filled star = kept; hollow star = not kept. Nothing else changes. */
  private paintFavoriteStar(star: HTMLElement) {
    const id = Number(star.dataset.favoriteId ?? "0");
    const name = star.dataset.favoriteName ?? `NORAD ${id}`;
    const starred = this.favorites.includes(id);
    star.textContent = starred ? "★" : "☆";
    star.setAttribute("aria-pressed", String(starred));
    star.setAttribute("aria-label", starred ? `Remove ${name} from favorites` : `Star ${name} as a favorite`);
    star.title = starred ? "Starred. Click to remove from favorites." : "Star this satellite to keep it in favorites.";
  }

  private restoreFavorites() {
    this.favorites = parseFavorites(storageGet("local", FAVORITES_STORAGE_KEY));
    this.renderFavorites();
  }

  /**
   * Star or unstar, then write the whole list back. A refused add — the list
   * is at its cap — says so rather than doing nothing, because a star that
   * does not light up with no explanation reads as a broken button.
   */
  private toggleFavoriteSatellite(id: number) {
    const status = byId("favorites-status");
    const change = toggleFavorite(this.favorites, id);
    if (change.capped) {
      status.textContent = `Favorites are full at ${MAX_FAVORITES}. Remove one to star another.`;
      status.hidden = false;
      return;
    }
    this.favorites = change.ids;
    storageSet("local", FAVORITES_STORAGE_KEY, serializeFavorites(this.favorites));
    status.hidden = true;
    status.textContent = "";
    this.renderFavorites();
  }

  private renderFavorites() {
    const list = byId("favorites-list");
    list.replaceChildren(...favoriteEntries(this.favorites, this.catalog.satellites).map((entry) => {
      const row = this.satelliteRow(entry.id, entry.name, entry.lines, entry.index === null ? null : () => {
        this.selectSatellite(entry.index!, true);
        this.hideSearchResults();
      });
      if (entry.missing) row.classList.add("favorites-row-missing");
      return row;
    }));
    byId("favorites-count").textContent = favoritesCountLabel(this.favorites.length);
    byId("favorites-empty").hidden = this.favorites.length > 0;
    this.syncFavoriteStars();
  }

  /**
   * Repaint every star on the page after the list changes, including the one
   * on a card that is momentarily detached from the document while the panel is
   * rebuilt. One spacecraft can be starred from three places at once; all three
   * have to agree immediately.
   */
  private syncFavoriteStars() {
    const stars = new Set<HTMLElement>(document.querySelectorAll<HTMLElement>("[data-favorite-id]"));
    this.selectedCard?.querySelectorAll<HTMLElement>("[data-favorite-id]").forEach((star) => stars.add(star));
    stars.forEach((star) => this.paintFavoriteStar(star));
  }

  /**
   * ONE SPACECRAFT AT A TIME, and opening one REPLACES the one before it.
   *
   * Sean, 2026-08-28: "no multiple satellites selected ... having multiple
   * satellites in the viewer overlay is just too cumbersome. one at a time."
   * So there is no push and no list to fall back into: the previous card, its
   * orbit, its ground trace and its footprint are all replaced by this one's.
   * Re-opening the spacecraft that is already open re-expands and re-renders
   * its card rather than rebuilding it, so a search hit for the object already
   * on screen does not throw away its open sections or its scroll position.
   *
   * FAVOURITES ARE A SEPARATE CONCEPT AND ARE NOT TOUCHED HERE. Replacing a
   * card removes the card, never the star: `favorites` is its own stored list,
   * and `syncFavoriteStars` repaints whatever card is on screen from it.
   */
  private selectSatellite(index: number, focus: boolean) {
    if (!this.catalog.satellites[index]) return;
    if (this.selectedIndex !== index || !this.selectedCard) {
      this.selectedCard?.remove();
      this.selectedCard = null;
      this.buildSatelliteCard(index);
    }
    this.setCardExpanded(true);
    this.activateSatellite(index, focus);
    this.renderSelectedCard();
    this.refreshVisible();
    this.closeMobilePanel();
    this.selectedCard?.scrollIntoView({ block: "nearest" });
  }

  /** Makes one card the active card: the spacecraft whose orbit, ground trace
   * and footprint are drawn, and the one the shared geometry controls act on. */
  private activateSatellite(index: number, focus: boolean) {
    this.selectedIndex = index;
    this.globe.setSelected(index);
    this.pendingFocusIndex = focus ? index : null;
    this.updateFootprintElevationNote();
    this.propagate();
    this.refreshSelectedGeometry();
    this.updateSatelliteCard();
    // The published station record for this spacecraft. Fetched here as well as
    // from the layer toggle so the card's section is governed by the data
    // rather than by whether an unrelated overlay happens to be switched on.
    void this.loadGroundStations();
    this.renderStationLinksForSelected();
    this.updateStationRing();
  }

  private buildSatelliteCard(index: number) {
    const satellite = this.catalog.satellites[index];
    if (!satellite) return;
    const template = byId<HTMLTemplateElement>("satellite-card-template");
    const card = template.content.firstElementChild!.cloneNode(true) as HTMLElement;
    card.dataset.satelliteIndex = String(index);
    card.style.setProperty("--mission-color", missionColors[satellite.mission]);
    card.querySelector("[data-card-name]")!.textContent = satellite.name;
    const evidenceFields = satellite as SatelliteRecord & CatalogEvidenceFields;
    card.querySelector("[data-card-chips]")!.replaceChildren(...satelliteChips({
      mission: satellite.mission,
      facet: missionFacet(satellite),
      sector: satellite.sector,
      basis: evidenceFields.classificationBasis,
      confidence: satellite.classificationConfidence,
      corroboration: evidenceFields.missionCorroboration,
    }).map(satelliteChipElement));
    // SATELLITE BACKGROUND, whole. There is no lead/rest split any more: the
    // split existed to keep the honesty disclosure above the fold, and the
    // disclosure is on the chip now.
    //
    // The section renders for every object that has a description, and since
    // 2026-08-20 that is every object — because the generated description
    // stopped being an apology and became a statement of what the registry
    // establishes about the object's orbit. Sean: "why do we still have
    // satellite cards without information?" The answer was that 2,383 of them
    // opened with nineteen words about what is unknown.
    //
    // What it does NOT do, and must not: quote the object's altitude, period,
    // launch date, launch cohort or registering state. Those are rows in the
    // Details grid directly below this section, and a description that reads
    // them back is padding — "stop adding filler/fluff text to my site". A
    // sentence doing exactly that was removed from 1,205 cards on 2026-08-20,
    // for the third time; see the tombstone in pipeline/build_release.py.
    //
    // It still renders NOTHING when there is nothing — no heading, no
    // placeholder — because a release could ship an object with an empty
    // string and a titled empty box is worse than an absent one.
    const background = card.querySelector<HTMLDetailsElement>('[data-card-section="background"]')!;
    const purpose = (satellite.purpose ?? "").trim();
    const shape = backgroundParagraphs(
      purpose, evidenceFields.purposeShaped ?? null, evidenceFields.fleetNote ?? null,
    );
    background.hidden = shape.paragraphs.length === 0;
    if (shape.paragraphs.length > 0) {
      card.querySelector("[data-card-purpose]")!.textContent = shape.paragraphs[0] ?? "";
      // The second paragraph is the shortened opening's own, or the fleet's, and the
      // fleet's is the LAST slot -- so when a card somehow has both, what it loses is
      // the fleet note, not half of its own description.
      const second = card.querySelector<HTMLElement>("[data-card-purpose-second]")!;
      second.textContent = shape.paragraphs[1] ?? "";
      second.hidden = shape.paragraphs.length < 2;

      const citation = card.querySelector<HTMLElement>("[data-card-purpose-source]")!;
      const source = evidenceFields.purposeSource?.trim();
      if (source && /^https?:\/\//i.test(source)) {
        citation.replaceChildren(sourceLink(source));
        citation.hidden = false;
      }

      // WHAT THE SHORTENING LEFT OUT, whole. Only when there IS a remainder: this fold
      // was taken off the card in August because it held two sentences and Sean said
      // "the drop down is incredibly short". What it holds here is up to 2,425
      // characters, which is the wall it exists to keep off the card face.
      const more = card.querySelector<HTMLDetailsElement>("[data-card-purpose-more]")!;
      more.hidden = !shape.shortened;
      if (shape.shortened) {
        card.querySelector("[data-card-purpose-rest]")!.textContent = shape.rest;
      }

      // The fleet paragraph's own citation, and beside it the member count, computed
      // by build_release.py from the catalog rather than written into the prose.
      const fleetSource = card.querySelector<HTMLElement>("[data-card-fleet-source]")!;
      const fleetUrl = evidenceFields.fleetNoteSource?.trim();
      const showFleet = Boolean(evidenceFields.fleetNote)
        && shape.paragraphs.includes((evidenceFields.fleetNote ?? "").trim())
        && Boolean(fleetUrl && /^https?:\/\//i.test(fleetUrl));
      fleetSource.hidden = !showFleet;
      if (showFleet) {
        const count = document.createElement("span");
        count.className = "fleet-count";
        const members = evidenceFields.fleetMemberCount ?? 0;
        // Short enough to sit on one line beside the link at 280 px, which is what the
        // description column is at 1440. A longer fleet name will still wrap, and that is
        // fine for a provenance line -- what is not fine is the link wrapping alone onto
        // a second line every time, which "objects in this catalogue" did.
        count.textContent =
          `${evidenceFields.fleetLabel ?? "This fleet"} — ${members.toLocaleString()} of `
          + `${this.catalog.satellites.length.toLocaleString()} here · `;
        fleetSource.replaceChildren(count, sourceLink(fleetUrl!));
      }
    }
    card.querySelectorAll<HTMLElement>("[data-card-section]").forEach((section) => {
      const name = section.dataset.cardSection ?? "";
      section.toggleAttribute("open", this.cardSectionOpen[name] === true);
      this.bindCardSection(section);
    });
    card.querySelector("[data-card-toggle]")!.addEventListener("click", () => {
      this.setCardExpanded(card.classList.contains("is-collapsed"));
      if (!card.classList.contains("is-collapsed")) this.activateSatellite(index, false);
      this.renderSelectedCard();
    });
    // The card's star is baked into the template rather than created here, so
    // it only needs pointing at this spacecraft. Starring is independent of the
    // selection, and stayed independent when the selection stopped being a
    // list: closing this card — or replacing it by opening another spacecraft —
    // leaves the favourite, and un-starring leaves the card open.
    const favoriteStar = card.querySelector<HTMLElement>("[data-card-favorite]");
    if (favoriteStar) this.bindFavoriteStar(favoriteStar, satellite.id, satellite.name);
    card.querySelector("[data-card-remove]")!.addEventListener("click", (event) => {
      event.stopPropagation();
      this.closeSelectedCard();
    });
    // THE MARK GOES TO ITS FOOTNOTE. The chips sit in the card HEAD, which stays
    // on screen when the card is folded to its name, so the mark can be pressed
    // on a card whose body — and therefore whose provenance list — has not been
    // rendered at all. Unfolding first is not a nicety: without it the button
    // opens a section nobody can see. `selectedCard` holds the same element
    // across a re-render, so this card reference stays good.
    card.querySelectorAll<HTMLButtonElement>("[data-hedge-mark]").forEach((mark) => {
      mark.addEventListener("click", (event) => {
        event.stopPropagation();
        if (card.classList.contains("is-collapsed")) {
          this.setCardExpanded(true);
          this.activateSatellite(index, false);
          this.renderSelectedCard();
        }
        this.revealHedgeFootnote(card);
      });
    });
    card.querySelector("[data-card-export]")!.addEventListener("click", () => this.exportSatellite(index));
    // The two map/archive links are per-card now rather than one node shuffled
    // into whichever card is active. They are both inside Satellite Details:
    // the orbit archive is a CELL of the fact grid, beside the launch date it
    // continues, and the 2-D ground-track map is the first of the section's two
    // full-width actions, directly above the OMM download. (It used to be the
    // only thing inside a "Ground Data" fold; that fold was removed on
    // 2026-08-21 because a heading and a shut disclosure to reach one button is
    // three surfaces for one action.) Each activates its own spacecraft first,
    // so clicking one on a card that is not the active card opens that card's
    // object rather than someone else's.
    card.querySelector("[data-card-ground-track]")!.addEventListener("click", () => {
      this.activateSatellite(index, false);
      this.openGroundTrackMap();
    });
    const orbitHistory = card.querySelector<HTMLButtonElement>("[data-card-orbit-history]")!;
    // Manifest only — no fetch. The key is absent whenever the archive was
    // unavailable for this release, and then the box simply never appears. The
    // box IS the button now, so hiding the button is the whole of it, and
    // `.card-actions > [hidden]` takes it out of the stack rather than leaving
    // a gap where an action used to be.
    orbitHistory.hidden = !this.manifest.orbitEvents;
    orbitHistory.addEventListener("click", () => {
      this.activateSatellite(index, false);
      void this.openOrbitHistory();
    });
    // THE HEAD IS THE PANEL'S DRAG HANDLE now that the count bar above it is
    // gone. Bound here rather than once at startup, because this element is new
    // every time a different spacecraft is opened.
    const head = card.querySelector<HTMLElement>(".sat-card-head");
    if (head) this.bindCardDragHandle(head);
    // Stamped here because this is where a card becomes the open one; the
    // template's default-open fold toggles just after, and revealAfterExpand
    // uses this to tell that settling apart from a reader's press.
    this.stackBuiltAt = performance.now();
    this.selectedCard = card;
  }

  /**
   * What the box says about the archive: "Open orbit history — 1,284 element
   * sets on file →", or an honest admission that the count is not known yet.
   *
   * THE QUANTITY is the number of element sets (`OrbitSample`s) the archive
   * holds for this spacecraft, read off `record.samples.length` in the object's
   * own orbit-history shard. That is literally the number of entries in this
   * spacecraft's orbit-history file, which is what the reader is being offered
   * a way to look at.
   *
   * IT IS NEVER FETCHED FOR THE CARD. One shard is about 25 MB of JSON and the
   * events bundle beside it is larger still; both are paid for once, behind the
   * button, when a reader actually opens the archive. Counting on card render
   * would put that download on every satellite anybody clicks. So this reads
   * `orbitShardCache` — what the browser already has — and says so plainly when
   * the answer is not in it. A shard carries about forty objects, so opening
   * the history once fills the count in for this object and its shard-mates.
   *
   * AND IT IS NEVER GUESSED. Four different absences get four different
   * sentences, and none of them is a number:
   *   - the release published no archive at all: the cell is hidden entirely
   *     (handled where the card is built);
   *   - the shard has not been downloaded: "History not loaded";
   *   - the shard downloaded but failed, or holds no record for this object:
   *     "No stored elements";
   *   - the record exists with an empty series: "No stored elements".
   */
  private renderOrbitHistoryFact(card: HTMLElement, norad: number) {
    const value = card.querySelector<HTMLElement>("[data-card-orbit-history-value]");
    const button = card.querySelector<HTMLElement>("[data-card-orbit-history]");
    if (!value || !button) return;
    const shardCount = this.manifest.orbitHistory?.shardCount;
    const shard = typeof shardCount === "number" && shardCount > 0
      ? this.orbitShardCache.get(shardFor(norad, shardCount))
      : undefined;
    let text: string;
    if (shard === undefined) {
      // Nothing has been downloaded for this shard yet, which is the ordinary
      // case: the archive is paid for once, when a reader opens it.
      text = "History not loaded";
    } else if (shard === ARCHIVE_OFFLINE) {
      // The archive host itself did not answer. Since 2026-08-27 the shards
      // live on bigmem rather than the VPS, so "the file is missing" and "the
      // machine is down" are genuinely different facts and this card says
      // which. Still not a number, and still not a guess.
      text = ARCHIVE_OFFLINE_STATE;
    } else if (shard === null) {
      // Asked for and could not be read - the release published no shard for
      // this object, or the fetch failed. That is not the same statement as
      // "the archive holds nothing for it", so it does not make that one.
      text = "History unavailable";
    } else {
      const samples = shard.objects.find((entry) => entry.norad === norad)?.samples.length ?? 0;
      text = samples === 0
        ? "No stored elements"
        : `${samples.toLocaleString()} element set${samples === 1 ? "" : "s"} on file`;
    }
    value.textContent = orbitHistoryActionClause(text);
    // The same classifier that set this value while it was a grid cell, driven
    // by the same four strings, so "1,284 element sets on file" is still mono
    // and tabular and "History not loaded" is still not. The STATE is what is
    // classified, because the state is what the voice is about.
    value.classList.remove("is-readout", "is-prose");
    const voice = factValueVoice(text);
    if (voice !== "answer") value.classList.add(`is-${voice}`);
    // The box's visible clause is written for a box; the accessible name keeps
    // the state verbatim, so which of the four this is never depends on the
    // rewording.
    button.setAttribute("aria-label", `Open orbit history — ${text}`);
  }

  /** Section open/closed is a preference, not per-spacecraft state: collapse
   * "Ephemeris and provenance" once and the next spacecraft you open is
   * already collapsed too. */
  private bindCardSection(section: HTMLElement) {
    section.addEventListener("toggle", () => {
      const name = section.dataset.cardSection ?? "";
      if (!name) return;
      // A fold opened by the footnote mark's jump is not the reader stating a
      // preference; see `revealHedgeFootnote`. The card still resizes to it.
      if (section.dataset.programmaticOpen) {
        delete section.dataset.programmaticOpen;
        this.applyStackHeight();
        this.announceOccluderChange();
        return;
      }
      this.cardSectionOpen[name] = (section as HTMLDetailsElement).open;
      storageSet("local", "space-explorer-card-sections-v1", JSON.stringify(this.cardSectionOpen));
      document.querySelectorAll<HTMLDetailsElement>(`[data-card-section="${name}"]`).forEach((peer) => {
        if (peer !== section) peer.open = (section as HTMLDetailsElement).open;
      });
      this.announceOccluderChange();
    });
  }

  private restoreCardSections() {
    // ONE-TIME MIGRATION, not a key bump. "Satellite Background" started
    // shipping SHUT on 2026-08-20, and a changed default reaches nobody who
    // has ever opened a satellite card: their stored blob says
    // `background: true` and wins over the default, so the change would look
    // like it was never made - on the owner's own browser first. Bumping the
    // storage key would have fixed that by forgetting EVERY fold EVERY reader
    // has ever set, which is a large cost for one section, so instead the
    // stored value for this one section is dropped exactly once, under its own
    // marker. The marker is written even when nothing is stored yet, so a
    // reader who opens Background after this ships keeps it open.
    const migrated = storageGet("local", CARD_SECTION_MIGRATION_KEY) === CARD_SECTION_MIGRATION;
    if (!migrated) storageSet("local", CARD_SECTION_MIGRATION_KEY, CARD_SECTION_MIGRATION);
    const saved = storageGet("local", "space-explorer-card-sections-v1");
    if (!saved) return;
    try {
      const parsed = JSON.parse(saved) as Record<string, unknown>;
      if (!migrated) { delete parsed.background; delete parsed.ephemeris; }
      ([
        "facts", "geometry", "ephemeris", "conditions", "brief", "readings", "validity", "provenance",
        "details", "background",
        "storm-chart", "storm-provenance", "storm-notes",
      ] as const).forEach((name) => {
        if (typeof parsed[name] === "boolean") this.cardSectionOpen[name] = parsed[name] as boolean;
      });
    } catch {
      // Ignore malformed or obsolete stored section state.
    }
  }

  /**
   * Open the provenance fold on this card and put the footnote under the eye.
   *
   * Setting `open` fires the section's own `toggle` listener, which is what
   * stores the fold and syncs the other open cards — so the reader who presses
   * one mark gets the same section open on every card, which is the behaviour
   * every other fold on this card already has. Doing it by hand here would have
   * been a second, quieter rule for the same thing.
   *
   * The focus is the accessibility half: a keyboard or screen-reader user who
   * presses the mark is MOVED to the section, rather than left where they were
   * while something scrolled somewhere else.
   *
   * IT FOCUSES THE SUMMARY, NOT THE FOOTNOTE ROW, and the reason is measured.
   * The provenance list is rebuilt wholesale on every propagation tick, so a
   * `dd` given a tabindex and focused here is a detached node a frame later and
   * the focus silently falls back to the document body — which is what a probe
   * found: `document.activeElement` read BODY after a real click on the mark,
   * and an attribute written onto the row was gone 1.5 s later. The summary is
   * a genuine element that only ever has its text rewritten, so focus holds on
   * it, and it reads "Data Source · what the * means" and
   * is announced expanded, with the footnote in the list it opens.
   *
   * The SCROLL targets the footnote's TERM, at the START of the window, and both
   * of those were corrected after looking at the result. `block: "center"` put
   * the middle of a six-line paragraph in the middle of the six-line scroll
   * window a 390 px phone gives this panel, so pressing the mark landed the
   * reader mid-sentence with the term scrolled off the top — a caveat delivered
   * as "…name matching a known programme, and nothing about this individual".
   * Scrolling the `dt` to the top puts "* on the label above" on the first line
   * and lets the sentence run down from there, which is how a footnote is read.
   * If neither row has been rendered yet — the card was folded when the mark was
   * pressed — the section is the target and the rows arrive inside it.
   */
  private revealHedgeFootnote(card: HTMLElement) {
    const section = card.querySelector<HTMLDetailsElement>('[data-card-section="ephemeris"]');
    if (!section) return;
    // A JUMP, NOT A PREFERENCE. Setting `open` here fires the section's own
    // `toggle` listener, which records the fold as a reader preference — so one
    // press of the footnote mark used to ship every future card with the
    // provenance fold open, which is precisely what "only the details section
    // should start off expanded" (Sean, 2026-08-31) rules out. The marker below
    // is read and cleared by `bindCardSection`, which skips the store for
    // exactly this one programmatic change. Only set when the fold is shut,
    // because an already-open fold fires no toggle to clear it.
    if (!section.open) {
      section.dataset.programmaticOpen = "1";
      section.open = true;
    }
    const term = card.querySelector<HTMLElement>("dt[data-card-hedge-footnote]");
    (term ?? section).scrollIntoView({ behavior: "smooth", block: "start" });
    section.querySelector("summary")?.focus({ preventScroll: true });
  }

  private setCardExpanded(expanded: boolean) {
    const card = this.selectedCard;
    if (!card) return;
    card.classList.toggle("is-collapsed", !expanded);
    const toggle = card.querySelector<HTMLElement>("[data-card-toggle]");
    toggle?.setAttribute("aria-expanded", String(expanded));
    const chevron = card.querySelector<HTMLElement>(".sat-card-chevron");
    if (chevron) chevron.textContent = expanded ? "−" : "+";
    // Folding the whole body is the biggest content change the card has; the
    // phone height ceiling follows it like any section fold.
    this.applyStackHeight();
  }

  /**
   * THE CARD'S X, and the only way to un-draw a spacecraft.
   *
   * Sean, 2026-08-28: "the X just removes the plotted orbit and footprint and
   * closes the card." All of that and nothing else — the orbit, the ground
   * trace and the footprint go with `clearSelectedGeometry`, the marker loses
   * its selected state, and the panel goes away because there is nothing left
   * inside it.
   *
   * IT DOES NOT TOUCH THE STAR. A favourited spacecraft is still favourited
   * after its card is closed; that was already true when this removed one
   * member of a list, and `tests/favorites.test.ts` keeps saying so.
   *
   * There is no card to promote in its place. That branch belonged to the
   * stack and went with it, and so did `clearStack` — the panel-level X and
   * "Clear Selected" both existed to empty a list of several.
   */
  private closeSelectedCard() {
    this.selectedCard?.remove();
    this.selectedCard = null;
    this.selectedIndex = null;
    this.pendingFocusIndex = null;
    this.globe.setSelected(null);
    this.globe.clearSelectedGeometry();
    this.renderSelectedCard();
    this.refreshVisible();
  }

  /**
   * Put the one card in the panel, and show the panel only when there is one.
   *
   * This was `renderStack`, and it also wrote the count, re-measured the
   * three-cell scope bar and repainted which of several cards was active. All
   * three were list bookkeeping. What is left is the two facts that are still
   * true of a window holding one card: what is in it, and whether it is on
   * screen at all.
   */
  private renderSelectedCard() {
    const panel = byId("satellite-stack");
    const host = byId("satellite-stack-cards");
    host.replaceChildren(...(this.selectedCard ? [this.selectedCard] : []));
    // `is-active` used to mark WHICH of several open cards the globe was
    // drawing. With one card it never varies, so it is simply always set: the
    // accent it paints is part of how the card looks, and dropping it would
    // change the card's appearance for a reason no reader could see.
    this.selectedCard?.classList.add("is-active");
    panel.hidden = this.selectedCard === null;
    if (this.selectedCard) this.applyCardPosition();
    else this.announceOccluderChange();
  }

  /**
   * Pull ONE rail out — the phone's bottom sheet, the desktop's drawer.
   *
   * Each rail holds only its own sections; the stylesheet does that from
   * `data-open-panel` on the rail against `data-rail-panel` on each section,
   * so there is one arrangement rather than a phone one and a desktop one.
   * Sean, of the phone, 2026-08-28: "what it is bringing up is a combined rail
   * in both cases. let's just make independent ones."
   *
   * NO MODE IS SET ON THE WAY IN, because there is no mode. This used to call
   * `setMode("combined")` here, because `setMode` wrote the `hidden` attribute
   * onto the very sections the stylesheet is trying to show, and a hidden
   * section cannot be shown by a stylesheet. Combined was the value chosen
   * because entering Satellites mode called `hideAllLayers()`, so a reader with
   * the aurora and the thermosphere drawn who asked for the satellite rail lost
   * both from a press that never mentioned them.
   *
   * Sean, 2026-08-28, made that safe case the whole rule: "going into the space
   * weather rail on desktop or panel in mobile doesn't take the satellite off or
   * a plotted orbit off." The mode is retired, no rail section is `hidden`, and
   * pulling either rail out now draws nothing and erases nothing.
   */
  private openMobilePanel(section: "satellites" | "environment") {
    const rail = byId("control-rail");
    this.mobilePanelSection = section;
    rail.classList.add("is-open");
    this.syncMobileTabs();
    // A rail that only holds its own sections has nothing to scroll TO: the
    // thing the reader asked for is the first thing in it. The measured
    // scroll-into-view this replaced existed only because both rails were one
    // column and the layers were at the bottom of it.
    rail.scrollTop = 0;
  }

  /**
   * The four controls say which rail is out, and say it from one field rather
   * than from whichever of them was last pressed.
   *
   * Sean: the open one "toggles solid blue and the text changes to Close
   * Panel", and closing "toggles back to black". The other keeps its own name,
   * because pressing it is how you get to the other rail — it is not a second
   * close button. The desktop tabs carry the same state as `aria-expanded` and
   * a filled background; their labels do not change, because a vertical tab on
   * the edge of the screen is a place name, and pressing the tab you are
   * standing on is already the way back.
   */
  private syncMobileTabs() {
    const rail = byId("control-rail");
    const section = rail.classList.contains("is-open") ? this.mobilePanelSection : null;
    if (section) rail.dataset.openPanel = section;
    else delete rail.dataset.openPanel;
    // The workspace grid opens the third column from this attribute, so the
    // rail's width and the rail's contents can never disagree.
    const workspace = byId("workspace");
    if (section) workspace.dataset.railOpen = section;
    else delete workspace.dataset.railOpen;
    const doors: Array<[string, "satellites" | "environment", string]> = [
      ["mobile-panel-toggle", "satellites", "Satellites"],
      ["mobile-weather-toggle", "environment", "Space weather"],
    ];
    doors.forEach(([id, owned, name]) => {
      const button = byId<HTMLButtonElement>(id);
      const open = section === owned;
      button.setAttribute("aria-expanded", String(open));
      button.textContent = open ? "Close panel" : name;
      button.classList.toggle("is-active", open);
    });
    ([["rail-tab-satellites", "satellites"], ["rail-tab-environment", "environment"]] as const).forEach(([id, owned]) => {
      const tab = document.getElementById(id);
      tab?.setAttribute("aria-expanded", String(section === owned));
    });
  }

  private closeMobilePanel() {
    const rail = byId("control-rail");
    rail.classList.remove("is-open");
    this.mobilePanelSection = null;
    this.syncMobileTabs();
    // Give the readings back. The sheet folded them away to keep one surface
    // over the globe at a time; the sheet is gone, so the layer the visitor
    // just switched on gets to say what it is again. (Nothing sets this flag
    // any more at the phone breakpoint — there is no window over the globe to
    // fold there — but a session that crossed the breakpoint with it set still
    // has to be let out of it.)
    if (this.explorerFoldedForSheet) {
      this.explorerFoldedForSheet = false;
      this.setExplorerCollapsed(false);
    }
  }

  /**
   * WHAT A PHONE DOES NOT CARRY.
   *
   * Sean, 2026-08-28: "whatever else is on the page - it shouldn't be there for
   * mobile. mobile is pared down to make it user friendly. if the panel is
   * hidden, only the title bar and about button, the satellite and space
   * weather buttons and the viewing area show up."
   *
   * TAKEN OUT OF THE DOCUMENT, not hidden with a display rule: markup a reader
   * can reach by rotating the handset is the same defect as markup they can
   * scroll to. The nodes are kept against a comment that marks where each one
   * came from, and rotating into landscape — which crosses 820 px into the
   * desktop layout — puts every one of them back, because this is a mobile-only
   * removal and the desktop keeps that content.
   *
   * THE TWO CHECKBOXES INSIDE THE ADVANCED FOLD STAY. `#layer-drap` and
   * `#layer-groundField` are the document's only copies, `byId` reads them by
   * id from `layerCheckboxIds` on every `hideAllLayers()`, and the guided
   * energy-chain walkthrough switches them on by clicking them. So the fold's
   * visible half leaves and the bare inputs move to the same hidden holder
   * `#layer-regions` and `#layer-photons` have used for a year — a control with
   * no row, rather than a row a phone reader was never meant to see.
   */
  private applyPhonePageStrip() {
    const phone = this.phoneChromeQuery.matches;
    if (phone === (this.phoneStripped.length > 0)) return;
    if (!phone) {
      // Landscape, or a resized desktop window: put it all back where it was.
      this.phoneStripped.forEach(({ node, anchor }) => anchor.replaceWith(node));
      this.phoneStripped = [];
      const holder = document.getElementById("phone-stripped-controls");
      holder?.querySelectorAll<HTMLElement>("input[data-strip-home]").forEach((input) => {
        document.querySelector(`[data-strip-slot="${input.dataset.stripHome}"]`)?.replaceWith(input);
        delete input.dataset.stripHome;
      });
      return;
    }
    let holder = document.getElementById("phone-stripped-controls");
    if (!holder) {
      holder = document.createElement("div");
      holder.id = "phone-stripped-controls";
      holder.hidden = true;
      byId("control-rail").append(holder);
    }
    // The switches first, so the fold can leave without taking them.
    ["layer-drap", "layer-groundField"].forEach((id) => {
      const input = document.getElementById(id);
      if (!input || input.closest("#phone-stripped-controls")) return;
      const slot = document.createElement("span");
      slot.dataset.stripSlot = id;
      slot.hidden = true;
      input.replaceWith(slot);
      input.dataset.stripHome = id;
      holder!.append(input);
    });
    [
      // "it looks like it starts off with 'radio propagation and advanced
      // fields', and then below that you have 'how these layers are made.'
      // remove all that. get rid of it."
      "#control-rail .advanced-environment-details",
      "#control-rail .method-link",
      // The rail's footer: a Data & methods link into a reading surface the
      // phone does not show at all (the whole nav is display: none here, which
      // is Sean's 2026-08-20 call), and the educational-use line. That line is
      // not lost — it is in the welcome panel this site opens with and in full
      // under About, which is the one button beside the title that stays.
      "#control-rail .rail-footer",
    ].forEach((selector) => {
      const node = document.querySelector(selector);
      if (!node) return;
      const anchor = document.createComment(`phone-stripped ${selector}`);
      node.replaceWith(anchor);
      this.phoneStripped.push({ node, anchor });
    });
  }

  private exportSatellite(index: number) {
    const satellite = this.catalog.satellites[index];
    if (!satellite) return;
    const payload = {
      schema: 1,
      exportedAt: new Date().toISOString(),
      source: this.catalog.source,
      caveat: "Space-Track OMM mean elements and locally derived teaching fields; SGP4 input, not telemetry or a conjunction-quality ephemeris.",
      satellite,
    };
    const url = URL.createObjectURL(new Blob([`${JSON.stringify(payload, null, 2)}\n`], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `${satellite.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || satellite.id}-omm.json`;
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  private openGroundTrackMap() {
    if (this.selectedIndex === null) return;
    const satellite = this.catalog.satellites[this.selectedIndex];
    if (!satellite) return;
    const at = this.simulationTime();
    const geosynchronous = satellite.periodMinutes >= 1380 && satellite.periodMinutes <= 1500;
    const spanMinutes = geosynchronous ? 24 * 60 : satellite.periodMinutes;
    const samples = geosynchronous ? 288 : 180;
    const satrec = json2satrec(satellite.omm);
    // Evenly spaced in TIME is only evenly spaced on the GROUND for a circular
    // orbit. On an eccentric one the perigee pass was being drawn as a few
    // straight chords - 37 degrees of arc in one line for THEMIS D - which is
    // what made these orbits look broken. See sampleGroundTrack.
    const points = sampleGroundTrack({
      at,
      spanMinutes,
      baseSamples: samples,
      sample: (when) => {
        const state = propagateOmm(satellite.omm, when, satrec);
        return state ? { longitudeDeg: state.longitudeDeg, latitudeDeg: state.latitudeDeg } : null;
      },
    });
    const current = propagateOmm(satellite.omm, at, satrec);
    byId("ground-track-title").textContent = `${satellite.name} ground track`;
    byId("ground-track-lead").textContent = geosynchronous
      ? "A 24-hour Earth-fixed trace. Inclined geosynchronous spacecraft form north-south lobes; eccentricity adds east-west width."
      : `One ${satellite.periodMinutes.toFixed(1)}-minute orbital period projected onto the rotating Earth.`;
    mountGroundTrackMap(byId("ground-track-map"), {
      points,
      satelliteName: satellite.name,
      currentTime: at,
      currentPosition: current ? { longitudeDeg: current.longitudeDeg, latitudeDeg: current.latitudeDeg, at } : undefined,
      window: geosynchronous
        ? { kind: "geosynchronous-analemma", hours: 24 }
        : { kind: "orbital-period", periodMinutes: satellite.periodMinutes },
    });
    const dialog = byId<HTMLDialogElement>("ground-track-dialog");
    if (!dialog.open) dialog.showModal();
  }

  private selectSwpcTab(button: HTMLButtonElement) {
    const tab = button.dataset.swpcTab;
    this.markActive("[data-swpc-tab]", button);
    document.querySelectorAll<HTMLElement>("[data-swpc-panel]").forEach((panel) => {
      panel.hidden = panel.dataset.swpcPanel !== tab;
    });
  }

  private setSwpcScaleChip(id: string, prefix: "R" | "S" | "G", reading: SwpcScaleReading) {
    const chip = byId(id);
    chip.dataset.level = reading.level === null ? "" : String(reading.level);
    chip.querySelector("b")!.textContent = reading.level === null ? `${prefix}—` : `${prefix}${reading.level}`;
  }

  private swpcConditionCard(prefix: "R" | "S" | "G", label: string, reading: SwpcScaleReading) {
    const article = document.createElement("article");
    article.className = "swpc-condition-card";
    article.dataset.level = reading.level === null ? "" : String(reading.level);
    const heading = document.createElement("span");
    heading.textContent = label;
    const value = document.createElement("strong");
    value.textContent = reading.level === null ? `${prefix}—` : `${prefix}${reading.level}`;
    const description = document.createElement("small");
    description.textContent = reading.level === null
      ? "Data unavailable"
      : reading.level === 0
        ? "Below NOAA scale threshold"
        : reading.label ?? "NOAA scale event";
    article.append(heading, value, description);
    return article;
  }

  private renderSwpcConditionGrid(containerId: string, record: SwpcScalesRecord) {
    byId(containerId).replaceChildren(
      this.swpcConditionCard("R", "RADIO BLACKOUT", record.radioBlackout),
      this.swpcConditionCard("S", "SOLAR RADIATION", record.solarRadiation),
      this.swpcConditionCard("G", "GEOMAGNETIC", record.geomagnetic),
    );
  }

  private updateSwpcOutlook() {
    const outlook = this.weather.outlook;
    if (!outlook) return;
    const latest = outlook.noaaScales.latestObserved;
    const maximum = outlook.noaaScales.rolling24HourMaximum;
    byId("swpc-summary").hidden = false;
    byId("swpc-summary-time").textContent = latest.asOf
      ? `${latest.asOf.slice(11, 16)} UTC`
      : "time unavailable";
    this.setSwpcScaleChip("swpc-scale-r", "R", latest.radioBlackout);
    this.setSwpcScaleChip("swpc-scale-s", "S", latest.solarRadiation);
    this.setSwpcScaleChip("swpc-scale-g", "G", latest.geomagnetic);
    byId("swpc-current-issued").textContent = formatUtcStamp(latest.asOf);
    byId("swpc-maximum-window").textContent = `${formatUtcStamp(maximum.windowStart, "From")} · ${formatUtcStamp(maximum.windowEnd, "through")}`;
    this.renderSwpcConditionGrid("swpc-current-grid", latest);
    this.renderSwpcConditionGrid("swpc-maximum-grid", maximum);

    const alerts = outlook.alerts.items;
    byId("swpc-alert-count").textContent = `(${alerts.length} recent)`;
    byId("swpc-alert-list").replaceChildren(...alerts.map((alert) => {
      const details = document.createElement("details");
      details.className = "swpc-alert-item";
      const summary = document.createElement("summary");
      const headline = document.createElement("strong");
      const lines = (alert.rawMessage ?? "").split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
      headline.textContent = lines.find((line) => /^(?:EXTENDED\s+)?(?:ALERT|WARNING|WATCH|SUMMARY|CONTINUATION|CANCEL)/i.test(line))
        ?? alert.productId
        ?? "NOAA bulletin";
      const time = document.createElement("time");
      time.textContent = alert.issuedAt ? alert.issuedAt.slice(0, 16).replace("T", " ") + "Z" : "time unavailable";
      summary.append(headline, time);
      const raw = document.createElement("pre");
      raw.textContent = alert.rawMessage ?? "Message text unavailable.";
      details.append(summary, raw);
      return details;
    }));

    const kpRows = outlook.kpForecast.rows;
    byId("swpc-forecast-issued").textContent = `${formatUtcStamp(outlook.threeDayForecast.issuedAt, "Rationale issued")} · ${formatUtcStamp(latest.asOf, "Scale feed as of")}`;
    byId("swpc-day-grid").replaceChildren(...outlook.noaaScales.forecastDays.map((day) => {
      const article = document.createElement("article");
      article.className = "swpc-day-card";
      const heading = document.createElement("h2");
      heading.textContent = formatUtcDay(day.date);
      const rows = document.createElement("div");
      rows.className = "swpc-day-metrics";
      const dayKp = kpRows
        .filter((row) => row.time?.slice(0, 10) === day.date && row.status !== "observed" && row.kp !== null)
        .map((row) => row.kp as number);
      const metrics: Array<[string, string]> = [
        ["R1–R2 radio blackout", displayPercent(day.radioBlackout.r1R2ProbabilityPercent)],
        ["R3+ radio blackout", displayPercent(day.radioBlackout.r3R5ProbabilityPercent)],
        ["S1+ radiation storm", displayPercent(day.solarRadiation.s1OrGreaterProbabilityPercent)],
        ["Geomagnetic level", day.geomagnetic.level === null ? "—" : `G${day.geomagnetic.level}`],
        ["Highest 3-hour Kp", dayKp.length ? Math.max(...dayKp).toFixed(2) : "—"],
      ];
      metrics.forEach(([label, value]) => {
        const row = document.createElement("div");
        const term = document.createElement("span");
        term.textContent = label;
        const fact = document.createElement("strong");
        fact.textContent = value;
        row.append(term, fact);
        rows.append(row);
      });
      article.append(heading, rows);
      return article;
    }));

    const rationaleLabels: Array<[string, string | null]> = [
      ["Geomagnetic rationale", outlook.threeDayForecast.rationales.geomagnetic],
      ["Solar-radiation rationale", outlook.threeDayForecast.rationales.solarRadiation],
      ["Radio-blackout rationale", outlook.threeDayForecast.rationales.radioBlackout],
    ];
    byId("swpc-rationales").replaceChildren(...rationaleLabels.map(([label, value]) => {
      const article = document.createElement("article");
      const heading = document.createElement("strong");
      heading.textContent = label;
      const prose = document.createElement("p");
      prose.textContent = value ?? "NOAA rationale unavailable.";
      article.append(heading, prose);
      return article;
    }));

    const geomagnetic = outlook.geomagneticForecast;
    byId("swpc-geomag-issued").textContent = formatUtcStamp(geomagnetic.issuedAt, "Issued");
    const apEntries: Array<[string, string | null, number | null]> = [
      ["Observed Ap", geomagnetic.ap.observed.date, geomagnetic.ap.observed.value],
      ["Estimated Ap", geomagnetic.ap.estimated.date, geomagnetic.ap.estimated.value],
      ...geomagnetic.ap.predicted.map((entry) => ["Predicted Ap", entry.date, entry.value] as [string, string | null, number | null]),
    ];
    byId("swpc-ap-grid").replaceChildren(...apEntries.map(([label, date, value]) => {
      const article = document.createElement("article");
      const term = document.createElement("span");
      term.textContent = `${label} · ${formatUtcDay(date)}`;
      const fact = document.createElement("strong");
      fact.textContent = value === null ? "—" : String(value);
      article.append(term, fact);
      return article;
    }));

    byId("swpc-probability-grid").replaceChildren(...geomagnetic.activityProbabilities.map((day) => {
      const article = document.createElement("article");
      const heading = document.createElement("h2");
      heading.textContent = formatUtcDay(day.date);
      const probabilities: Array<[string, number | null]> = [
        ["Active", day.activePercent],
        ["Minor storm", day.minorStormPercent],
        ["Moderate storm", day.moderateStormPercent],
        ["Strong–extreme", day.strongToExtremeStormPercent],
      ];
      article.append(heading, ...probabilities.map(([label, value]) => {
        const row = document.createElement("div");
        const term = document.createElement("span");
        term.textContent = label;
        const fact = document.createElement("strong");
        fact.textContent = displayPercent(value);
        row.append(term, fact);
        return row;
      }));
      return article;
    }));

    const forecastKp = kpRows.filter((row) => row.status !== "observed" && row.time);
    const kpByDay = new Map<string, typeof forecastKp>();
    forecastKp.forEach((row) => {
      const date = row.time!.slice(0, 10);
      const rows = kpByDay.get(date) ?? [];
      rows.push(row);
      kpByDay.set(date, rows);
    });
    byId("swpc-kp-days").replaceChildren(...Array.from(kpByDay.entries()).map(([date, rows]) => {
      const article = document.createElement("article");
      article.className = "swpc-kp-day";
      const heading = document.createElement("h2");
      heading.textContent = `${formatUtcDay(date)} · 3-hour Kp`;
      const cells = document.createElement("div");
      cells.className = "swpc-kp-cells";
      rows.forEach((row) => {
        const cell = document.createElement("div");
        cell.className = "swpc-kp-cell";
        const time = document.createElement("time");
        time.textContent = row.time ? `${row.time.slice(11, 13)}–${String((Number(row.time.slice(11, 13)) + 3) % 24).padStart(2, "0")}Z` : "—";
        const value = document.createElement("strong");
        value.textContent = row.kp === null ? "—" : row.kp.toFixed(2);
        const bar = document.createElement("i");
        bar.style.setProperty("--kp-width", `${row.kp === null ? 0 : Math.min(100, row.kp / 9 * 100)}%`);
        const scale = document.createElement("small");
        scale.textContent = row.noaaScale ?? (row.status === "estimated" ? "estimated" : "");
        cell.append(time, value, bar, scale);
        cells.append(cell);
      });
      article.append(heading, cells);
      return article;
    }));

    byId("swpc-data-note").textContent = outlook.parseWarnings.length
      ? `${outlook.parseWarnings.length} NOAA field(s) could not be normalized; unavailable values are left blank rather than inferred. Issue times remain independent. Educational display only.`
      : "Issue times are shown independently because NOAA products can update at different times. Educational display only; use NOAA SWPC for official warning decisions.";
  }

  /** Live values (altitude, velocity, sub-satellite point) for the one open
   * card. A folded card prints no numbers at all, so it is skipped rather than
   * rendered into a body nobody can see. */
  private updateSatelliteCard() {
    const card = this.selectedCard;
    if (!card || this.selectedIndex === null) return;
    if (card.classList.contains("is-collapsed")) return;
    this.renderCardFields(this.selectedIndex, card);
  }

  private renderCardFields(index: number, card: HTMLElement) {
    const satellite = this.catalog.satellites[index];
    if (!satellite) return;
    const state = this.globe.getState(index);
    const orbitLabel = satellite.orbit === "GEO"
      // "Other GSO", not "Other GSO / near-GEO". Two reasons, and they agree.
      // It is what the site already CALLS this set everywhere else: the GEO
      // sub-filter's button reads "Other GSO" and the hint under it says what
      // is in it — "the rest of the belt — drifting, near-GEO, and the inclined
      // geosynchronous craft their cards call IGSO" — so the card was the only
      // surface using a different name for the same class. And the gloss was
      // carrying a job it no longer has: "near-GEO" was doing duty for the
      // inclined objects too until IGSO became a class of its own, and a
      // twenty-character value cannot sit in a 133 px half column without
      // wrapping. Nine characters can. Nothing about the class changed.
      ? classifyGeoSubtype(satellite.periodMinutes, satellite.omm.INCLINATION, satellite.omm.ECCENTRICITY) === "geostationary"
        ? "Geostationary"
        : "Other GSO"
      : satellite.orbit;
    const evidence = satellite as SatelliteRecord & CatalogEvidenceFields;
    // Null on the ~6,441 cards whose label IS corroborated, and on the 65 whose
    // facet draws no chip at all. Everything below reads it as "is this card
    // marked, and with what wording", and nothing else re-derives that.
    const footnote = classificationFootnote({
      mission: satellite.mission,
      facet: missionFacet(satellite),
      sector: satellite.sector,
      basis: evidence.classificationBasis,
      confidence: satellite.classificationConfidence,
      corroboration: evidence.missionCorroboration,
    });
    const age = elementAgeDays(satellite.omm.EPOCH, this.simulationTime());
    const orbitFacts = satelliteOrbitFacts({
      orbitLabel,
      altitudeNow: state ? formatAltitude(state.altitudeKm) : null,
      periodMinutes: satellite.periodMinutes,
      inclinationDeg: satellite.omm.INCLINATION,
      perigee: formatAltitude(satellite.perigeeKm),
      apogee: formatAltitude(satellite.apogeeKm),
      subSatellitePoint: state
        ? formatGeographicPoint(state.latitudeRad * 180 / Math.PI, state.longitudeRad * 180 / Math.PI)
        : null,
      elementAge: displayElementAge(age),
    });
    const details = satelliteDetailFacts({
      identity: satelliteCardFacts({
        organization: satellite.organization,
        ownerLabel: satellite.ownerLabel,
        organizationSource: evidence.organizationSource,
        operatorState: satellite.operatorState,
        constellationFact: fleetFactValue(satellite.constellation, evidence.fleetEvidence),
        secondaryMissions: satellite.secondaryMissions,
      }),
      orbit: orbitFacts,
      launchDate: satellite.launchDate,
    });
    // FACTS ONLY, AND NO HOLES. The orbit archive used to be lifted out of this
    // grid and put back as its last cell; it is one of the section's action
    // boxes now, so nothing is lifted and nothing has to be put back. What the
    // grid does need is the layout pass: `factGridSpans` reads the whole list
    // at once and says which cells take the full row, which is the only place
    // that can see a cell about to be left beside an empty half.
    const detailsGrid = card.querySelector("[data-card-details]")!;
    const spans = factGridSpans(details);
    detailsGrid.replaceChildren(...details.map((row, at) => factCell(row, spans[at])));
    this.renderOrbitHistoryFact(card, satellite.id);
    // How the object is NAMED, in the head beside its name. These are not
    // evidence about the spacecraft and they were opening a section called
    // "Ephemeris and provenance", which is a claim neither of them makes.
    const identity = card.querySelector<HTMLElement>("[data-card-identity]");
    if (identity) {
      identity.textContent = satellite.cosparId
        ? `NORAD ${satellite.id} · COSPAR ${satellite.cosparId}`
        : `NORAD ${satellite.id}`;
    }
    // "Purpose label — template; high confidence" is gone. It was the card
    // grading its own certainty on a scale nothing explained, on the same card
    // whose description said the purpose was unverified — Tianmu-1 11 read
    // "high confidence" beside "has not been independently verified". What a
    // reader is owed is the MECHANISM, which is what classificationBasis is,
    // and it is now stated in words here and stamped on the chip above.
    const ephemeris: Array<[string, string]> = [
      ["Element epoch", satellite.omm.EPOCH],
      ["Element source", "Space-Track OMM"],
      ["Eccentricity", satellite.omm.ECCENTRICITY.toFixed(6)],
      ...(satellite.launchGroup ? [["Launch cohort", satellite.launchGroup] as [string, string]] : []),
      ["Category evidence", classificationBasisEvidence(
        evidence.classificationBasis, evidence.missionCorroboration,
      )],
      // WHAT THE MARK ON THE LABEL MEANS, directly under the row that says what
      // kind of evidence the label rests on. Those two rows answer the reader's
      // two questions in the order the reader asks them — "what was checked?"
      // then "so what am I being told?" — and separating them would leave the
      // mechanism sentence to be read as the whole answer, which is how the
      // card ended up contradicting itself the last time.
      //
      // HERE AND NOT UNDER THE CHIP. A sentence printed under the label is the
      // Tianmu-1 11 defect: a category and a retraction of it three lines apart,
      // on every one of 1,559 cards, which is what the mark exists to avoid. A
      // footnote is a promise that the explanation is written down somewhere the
      // reader can get to, and this section is where this card writes down what
      // it knows and how it knows it. The route is the point — see the mark's
      // own button, and this section's summary, which names the footnote.
      //
      // ABSENT, not empty, on a corroborated card. `classificationFootnote`
      // returns null wherever no chip is marked, so a card with nothing to
      // explain says nothing rather than reassuring the reader in a row of its
      // own — this site does not print "no caveat applies".
      ...(footnote ? [[HEDGE_FOOTNOTE_TERM, footnote.text] as [string, string]] : []),
      // Only the NEGATIVE is worth a row. Where a description exists it is on
      // the card above with its citation beside it, and a row saying so is the
      // card describing itself.
      ...(hasPublishedDescription(satellite.purpose)
        ? []
        : [["Description", "No published source names this object's payload. What is written above describes the CLASS of object this is \u2014 what it is, why nobody has published a mission for it, and how long its own tracked orbit says it will stay up \u2014 not this spacecraft in particular."] as [string, string]]),
    ];
    // THE FOLD ADVERTISES THE FOOTNOTE. Everything the mark's button does has to
    // be reachable without pressing it — a reader who scrolls past a shut fold
    // labelled only "Data Source" has been given a mark and no
    // way to learn it means anything. On a card with nothing marked the summary
    // is left exactly as the template wrote it.
    const provenanceSummary = card.querySelector<HTMLElement>('[data-card-section="ephemeris"] > summary');
    if (provenanceSummary) {
      // NON-BREAKING INSIDE THE HINT. The panel is about 400 px wide and the
      // summary wraps; left alone it broke as "…what the *" / "means", which
      // puts a lone asterisk at the end of a line where it reads as a stray
      // glyph rather than as the mark it is naming. The whole hint moves to the
      // second line together instead.
      // 2026-08-31, owner: the "what the * means" hint read as clutter; the label is
      // "Data Sources" either way. The mark button and tooltip still route a reader
      // to the footnote; the fold no longer advertises it.
      provenanceSummary.textContent = "Data Sources";
    }
    card.querySelector("[data-card-ephemeris]")!.replaceChildren(...ephemeris.flatMap(([term, value]) => {
      const label = document.createElement("dt");
      label.textContent = term;
      const detail = document.createElement("dd");
      detail.textContent = value;
      // The footnote is the one row that something else points AT, so it is the
      // one row that needs a name. It is a SCROLL TARGET AND NOTHING MORE — it
      // carries no tabindex, because it cannot hold focus: every row of this
      // list is destroyed and rebuilt on each propagation tick (`renderCardFields`
      // runs from `propagate`, and this whole `dl` is a `replaceChildren`), so a
      // focused `dd` is a dead node about 60 ms later and the focus lands back on
      // the body. Measured, not assumed: a probe attribute written onto this row
      // was gone 1.5 s later, and `document.activeElement` read BODY after a real
      // click on the mark. `revealHedgeFootnote` focuses the section's summary,
      // which is a real element that survives the rebuild.
      if (term === HEDGE_FOOTNOTE_TERM) {
        label.dataset.cardHedgeFootnote = "";
        detail.dataset.cardHedgeFootnote = "";
      }
      // The citation behind the description used to hang off a "Purpose label"
      // row down here. It is beside the prose it supports now, in Satellite
      // Background, which is where a reader who has just read a claim is.
      return [label, detail];
    }));
  }

  /**
   * The footprint boundary is real geometry (the tangent horizon at 0°, or a
   * spherical cap at the selected mask angle otherwise); the fill's fade
   * toward the edge is a decorative gradient, not a model of signal
   * strength, which honesty contract SCIENTIFIC-LAYERS.md forbids presenting
   * as physical. This keeps that caption honest for whichever mask is active.
   */
  private updateFootprintElevationNote() {
    // The geometry controls only exist once a spacecraft has been opened.
    const note = document.getElementById("footprint-elevation-note");
    if (!note) return;
    const degrees = this.footprintMinElevationDeg;
    const boundaryDescription = degrees <= 0
      ? "where the satellite is above the horizon (0° elevation)"
      : `where the satellite clears ${degrees}° of elevation`;
    // TWO SENTENCES, and the second is the honesty claim. The 90-word
    // explanation that used to follow it — isoflux antennas, inverse-square
    // range loss, what the fade is not — is teaching, not a caveat on a
    // control, and it has been handed to the Learn section's footprint page.
    // Sean: "I would put it in a learning section on the footprint and how we
    // show it." What must never leave this control is the claim that the fade
    // is decorative, so that stays here.
    note.textContent =
      `The yellow boundary is real geometry: ${boundaryDescription}. `
      + "The fade inside it is a visual aid, not signal strength.";
  }

  /**
   * The selected spacecraft's drawn geometry: the orbit through inertial
   * space, the ground trace under it, and the footprint beneath it now.
   *
   * The orbit and the ground trace no longer share a span, and sharing one is
   * what produced Sean's "it draws part of one". Both used to run for
   * `min(period, 24 h)`. That cap is right for the trace — more than a day of
   * ground track is unreadable, and the 2-D dialog states its own window — and
   * it silently cut the ORBIT of every spacecraft that takes longer than a day
   * to go round. Twelve of the catalogue's forty HEO objects do: CLUSTER
   * II-FM7 (53.5 h period) drew 44.9% of its orbit and MMS 1 (84.7 h) drew
   * 28.4%, each stopping in empty space 407 and 259 scene units from where it
   * started. The orbit now always runs exactly one period, so it closes.
   *
   * Neither line is sampled evenly in time any more either; see
   * `src/orbit-polyline.ts` for the measurement behind that.
   */
  private refreshSelectedGeometry() {
    if (this.selectedIndex === null) return;
    const satellite = this.catalog.satellites[this.selectedIndex];
    if (!satellite) return;
    const at = this.simulationTime();
    const satrec = json2satrec(satellite.omm);
    this.selectedOrbit = adaptiveOrbitPath({
      centre: at,
      spanMinutes: satellite.periodMinutes,
      sampleAt: (sampleTime) => propagateOmmInFrozenEarthFrame(satellite.omm, sampleTime, at, satrec),
      drawnPosition: (state) => geoToSceneVector(
        state.latitudeDeg,
        state.longitudeDeg,
        satelliteDisplayRadius(state.altitudeKm),
      ),
      toleranceSceneUnits: orbitPathTolerance(satelliteDisplayRadius(Math.max(0, satellite.apogeeKm))),
    }).map((state) => ({
      latitudeDeg: state.latitudeDeg,
      longitudeDeg: state.longitudeDeg,
      altitudeKm: state.altitudeKm,
    }));
    // The trace is drawn on the globe at a fixed 100.7 scene units, so its
    // tolerance comes from the globe rather than from the orbit's reach.
    this.selectedGround = adaptiveOrbitPath({
      centre: at,
      spanMinutes: Math.min(satellite.periodMinutes, 24 * 60),
      sampleAt: (sampleTime) => propagateOmm(satellite.omm, sampleTime, satrec),
      drawnPosition: (state) => geoToSceneVector(state.latitudeDeg, state.longitudeDeg, 100.7),
      toleranceSceneUnits: orbitPathTolerance(100.7),
    }).map((state) => [state.longitudeDeg, state.latitudeDeg] as [number, number]);
    const current = propagateOmm(satellite.omm, at);
    this.selectedFootprint = current
      ? footprintPoints(current.latitudeDeg, current.longitudeDeg, current.altitudeKm, this.footprintMinElevationDeg, 96)
      : [];
    this.applySelectedGeometry();
  }

  private applySelectedGeometry() {
    const orbit = this.geometryMode === "orbit" || this.geometryMode === "all" ? this.selectedOrbit : [];
    const ground = this.geometryMode === "ground" || this.geometryMode === "all" ? this.selectedGround : [];
    const footprint = this.geometryMode === "footprint" || this.geometryMode === "all" ? this.selectedFootprint : [];
    this.globe.setSelectedGeometry(orbit, ground, footprint, this.simulationTime());
  }

  /**
   * The one-line form of the conditions card. It is read back out of the cells
   * it summarises rather than recomputed, so the collapsed line and the open
   * grid cannot drift apart.
   */
  private updateConditionsSummary() {
    const value = (id: string) => byId(id).textContent?.trim() || "—";
    byId("key-conditions-summary").textContent =
      `V ${value("wind-speed")} km/s · Bz ${value("imf-bz")} nT · Kp ${value("kp-index")} · X-ray ${value("xray-class")}`;
  }

  private updateWeatherReadout() {
    byId("wind-speed").textContent = displayNumber(this.weather.solarWind.speedKps);
    byId("imf-bz").textContent = displayNumber(this.weather.imf.bzGsmNt, 1);
    byId("kp-index").textContent = displayNumber(this.weather.geomagnetic.kp, 1);
    byId("hmf2").textContent = displayNumber(this.weather.ionosphere.medianHmF2Km);
    byId("xray-class").textContent = this.weather.xray.class;
    byId("proton-flux").textContent = this.weather.particles.protonFlux === null
      ? "—"
      : this.weather.particles.protonFlux.toExponential(1);
    byId("proton-channel").textContent = `pfu ${this.weather.particles.protonEnergy}`;
    byId("aurora-probability").textContent = `${this.weather.aurora.maximumProbability}%`;
    this.updateConditionsSummary();
    const auroraForecast = utcMinuteLabel(this.weather.aurora.forecastAt);
    byId("aurora-note").textContent = `${this.weather.aurora.model}, valid ${auroraForecast}. ${this.weather.aurora.caveat}`;
    this.renderCurrentAnalysis();
    const manifestUrl = new URL("data/manifest.json", document.baseURI);
    const weatherDownload = byId<HTMLAnchorElement>("weather-json-download");
    weatherDownload.href = artifactUrl(manifestUrl, this.manifest.spaceWeather.path).href;
    weatherDownload.download = `space-weather-${this.manifest.release}.json`;
    this.updateSwpcOutlook();
  }

  /**
   * CURRENT ANALYSIS, written as one message in two paragraphs and one text
   * size. Sean, on the four blocks this replaced: "It has three different text
   * sizes and three different colors. Can we get one cohesive message? Two
   * paragraphs max?"
   *
   * FIRST PARAGRAPH: what the conditions are, in the pipeline's own words,
   * plus its caveat, plus — only while it is true — the one sentence that
   * keeps a reader from concluding the site is broken when the summary says Kp
   * is quiet and the top bar says storm.
   *
   * SECOND PARAGRAPH: where it came from. The provenance distinction is not
   * dropped, it is a SENTENCE: a fixed rule and a language model are not the
   * same authority and a reader is entitled to know which one wrote the
   * paragraph above. Then the two observation times and the scale caveat,
   * which are the same kind of fact.
   *
   * ONE WRITER, three callers — the readout update, the storm update, and the
   * distance-scale toggle. Each of those used to write its own block on its
   * own schedule into the same fold.
   */
  private renderCurrentAnalysis() {
    const brief = this.weather.teachingBrief ?? null;
    const summary = brief ? `${brief.text} ${brief.caveat}` : null;
    const disagreement = this.kpDstDisagreement
      ? " Kp is low enough that NOAA's G-scale reads G0 while Dst is classifying a storm — they measure"
        + " different things, and the geomagnetic indicator in the top bar explains which is which."
      : "";
    if (summary !== null) byId("weather-brief-text").textContent = `${summary}${disagreement}`;
    const provenance = brief === null
      ? "This summary is not in the current release."
      : brief.kind === "model-assisted"
        ? "A language model drafted this summary and every figure in it was checked back against the published numbers."
        : "This summary is assembled from the published numbers by a fixed rule, so it states only what they state.";
    // Through utcMinuteLabel, not a bare toISOString: on 2026-08-08 NOAA's
    // GloTEC field published an empty observedAt, which threw RangeError out
    // of the readout update and out of initialize() with it. One absent stamp
    // must not take the rest of the interface down; it reads "an unknown time".
    const observed = utcMinuteLabel(this.weather.solarWind.observedAt);
    const tec = utcMinuteLabel(this.weather.ionosphere.observedAt);
    byId("weather-note").textContent = `${provenance} Solar wind: ${this.weather.solarWind.sourceSpacecraft}`
      + ` at ${observed}. GloTEC assimilated field: ${tec}. ${distanceScaleStrings(this.distanceScale).weatherNote}`;
  }

  private updateModelControlVisibility() {
    // The plasma-field controls live in the geospace layer's own panel now,
    // shown and hidden with that panel; only the RBE controls still ride the
    // radiation panel's animated fold.
    const radiationVisible = byId<HTMLInputElement>("layer-radiation").checked;
    const controls = byId("model-subcontrols");
    controls.classList.toggle("is-visible", radiationVisible);
    controls.setAttribute("aria-hidden", String(!radiationVisible));
    document.querySelectorAll<HTMLElement>('[data-model-control="radiation"]').forEach((element) => {
      element.hidden = !radiationVisible;
    });
  }

  private updateAuroraControlVisibility() {
    const visible = byId<HTMLInputElement>("layer-aurora").checked;
    const controls = byId("aurora-subcontrols");
    controls.classList.toggle("is-visible", visible);
    controls.setAttribute("aria-hidden", String(!visible));
  }

  /**
   * The altitude-band picker only means anything while the layer is on, and
   * until now it was never revealed at all: the layer lost its toggle in
   * f1312cb, so nothing ever called a handler for this panel and the control
   * sat in the markup permanently aria-hidden. It is the layer's answer to
   * "show me the D region", so it has to be reachable.
   */
  private updateIonosphereControlVisibility() {
    const visible = byId<HTMLInputElement>("layer-ionosphere").checked;
    const controls = byId("ionosphere-subcontrols");
    controls.classList.toggle("is-visible", visible);
    controls.setAttribute("aria-hidden", String(!visible));
  }

  private updateThermosphereControlVisibility() {
    const visible = byId<HTMLInputElement>("layer-thermosphere").checked;
    const controls = byId("thermosphere-subcontrols");
    controls.classList.toggle("is-visible", visible);
    controls.setAttribute("aria-hidden", String(!visible));
  }

  private surfaceLegendStatus(
    state: EnvironmentSurfaceState | null,
    loading: boolean,
    failed: boolean,
  ): { badge: string; short: string; text: string; state: "ready" | "no-data" | "stale" | "loading" } {
    if (loading) return { badge: "LOADING", short: "LOADING EXACT FRAMES", text: "Loading the verified rolling numeric artifact…", state: "loading" };
    if (failed) return { badge: "NO DATA", short: "LOAD FAILED", text: "The verified artifact could not be loaded; no fallback field is displayed.", state: "no-data" };
    if (!state) return { badge: "LOAD ON DEMAND", short: "NOT LOADED", text: "Select this layer to load its rolling numeric artifact.", state: "loading" };
    if (state.status === "ready") {
      return {
        badge: "SOURCE FRAME",
        short: "EXACT FRAME READY",
        text: state.held
          // No longer claims the age is "within its published validity
          // allowance": D-RAP's live-edge fix (see DrapSurfaceLayerController
          // .selectState) can now hold a frame well past that nominal
          // threshold, so the wording has to stay true either side of it.
          ? `Exact source frame selected; held ${Math.floor(state.ageMinutes)} minute${Math.floor(state.ageMinutes) === 1 ? "" : "s"} since its own NOAA valid time.`
          : "Exact source frame matches the selected UTC.",
        state: "ready",
      };
    }
    if (state.status === "stale") {
      return { badge: "STALE · HIDDEN", short: "STALE · HIDDEN", text: `${state.message} The map is hidden rather than holding that frame.`, state: "stale" };
    }
    return { badge: "NO DATA", short: `${state.reason.toUpperCase()} · HIDDEN`, text: `${state.message} The map is hidden and no time interpolation is invented.`, state: "no-data" };
  }

  /**
   * The ground-perturbation layer's equivalent of `surfaceLegendStatus`,
   * kept separate because `GroundFieldState` is not an `EnvironmentSurfaceState`
   * (its own snap-to-nearest coverage policy has no "stale" status: it either
   * holds a frame within `GROUND_FIELD_SNAP_MINUTES` of the selected UTC or
   * hides, in either time direction, since this is forecast-lead data that
   * can be genuinely valid a little ahead of the selected UTC too).
   */
  private groundFieldLegendStatus(
    state: GroundFieldState | null,
    loading: boolean,
    failed: boolean,
  ): { badge: string; short: string; text: string; state: "ready" | "no-data" | "loading" } {
    if (loading) return { badge: "LOADING", short: "LOADING EXACT FRAMES", text: "Loading the verified NOAA ground-perturbation artifact…", state: "loading" };
    if (failed) return { badge: "NO DATA", short: "LOAD FAILED", text: "The verified NOAA ground-perturbation artifact could not be loaded; no fallback field is displayed.", state: "no-data" };
    if (!state) return { badge: "LOAD ON DEMAND", short: "NOT LOADED", text: "Select this layer to load its rolling numeric artifact.", state: "loading" };
    if (state.status === "ready") {
      const minutes = Math.round(Math.abs(state.ageMinutes));
      return {
        badge: "NOAA MODEL · FORECAST",
        short: "EXACT FRAME READY",
        text: state.ageMinutes > 0
          ? `Exact source frame selected; it is ${minutes} minute${minutes === 1 ? "" : "s"} behind the selected UTC.`
          : minutes === 0
            ? "Exact source frame matches the selected UTC."
            : `Exact source frame selected; it is ${minutes} minute${minutes === 1 ? "" : "s"} ahead of the selected UTC, inside the model's own forecast lead.`,
        state: "ready",
      };
    }
    return { badge: "NO DATA", short: `${state.reason.toUpperCase()} · HIDDEN`, text: `${state.message} The map is hidden and no time interpolation is invented.`, state: "no-data" };
  }

  private rollingCoverage(record: ReleaseManifest["drap"] | ReleaseManifest["aurora"], fallbackFrameCount?: number) {
    if (!record) return `${fallbackFrameCount ?? 0} exact frame${fallbackFrameCount === 1 ? "" : "s"} in this release; manifest coverage metadata unavailable.`;
    const validFrom = record.validFrom.slice(5, 16).replace("T", " ");
    const validTo = record.validTo.slice(5, 16).replace("T", " ");
    const gapText = record.noDataIntervalCount === 0 ? "no recorded gaps" : `${record.noDataIntervalCount} explicit gap${record.noDataIntervalCount === 1 ? "" : "s"}`;
    const retention = record.sourceRetentionLimited ? " · upstream numeric history is retention-limited" : "";
    return `${record.frameCount} exact frame${record.frameCount === 1 ? "" : "s"} · ${validFrom}Z–${validTo}Z · ${record.actualCoverageHours.toFixed(1)} h covered · ${gapText}${retention}`;
  }

  /**
   * The ground-station card: the population when no pin is open, and the
   * conditions over one antenna when one is.
   *
   * No colour scale — pins are categorical, so this takes the SHAPE ONLY
   * treatment in the legend and puts everything it has to say in the viewer.
   * The coordinate-precision tally is deliberately a headline reading rather
   * than a footnote: three tiers live in this table, from 3 cm survey marks to
   * rows published only to the arcminute, and a map that draws all of them as
   * identical pinpoints is claiming a precision it does not have.
   */
  private groundStationLegendSpec(): EnvironmentLegendSpec {
    const index = this.groundStations;
    const bundle = index?.bundle;
    if (!bundle) {
      return {
        layer: "groundStations",
        title: "Ground stations",
        badge: "PUBLISHED RECORD",
        evidence: "observed",
        stats: [{
          label: "TABLE",
          value: this.groundStationLoadFailed
            ? (this.manifest.groundStations ? "LOAD FAILED" : "NOT IN THIS RELEASE")
            : "LOADING",
        }],
        note: this.groundStationLoadFailed
          ? "The cited station table is not available in this release, so no antenna is drawn. No position is substituted from any other source."
          : "The cited station table loads when the layer is switched on.",
        statusState: this.groundStationLoadFailed ? "no-data" : "loading",
      };
    }

    const precisionCount = (kind: GroundStation["coordinatePrecision"]) =>
      bundle.stations.filter((station) => station.coordinatePrecision === kind).length;
    const selected = this.selectedStationIndex === null
      ? null
      : this.groundStationLayer?.stations[this.selectedStationIndex] ?? null;

    const stats: Array<{ label: string; value: string }> = selected
      ? this.selectedStationStats(selected)
      : [
        { label: "ANTENNAS", value: String(bundle.stationCount) },
        { label: "NETWORKS", value: String(new Set(bundle.stations.map((station) => station.network)).size) },
        { label: "PUBLISHED LINKS", value: String(bundle.linkCount) },
        { label: "SURVEY GRADE", value: String(precisionCount("published-survey")) },
        { label: "APPROXIMATE", value: String(precisionCount("published-approximate")) },
        { label: "PRIVACY-REDUCED", value: String(precisionCount("privacy-reduced")) },
      ];

    return {
      layer: "groundStations",
      title: selected ? selected.name : "Ground stations",
      keyTitle: "Ground stations",
      badge: "PUBLISHED RECORD",
      evidence: "observed",
      // Pin colour IS a variable -- the operator category -- and the scale is
      // exported by the module that owns the colours, so legend and pins
      // cannot drift apart. Without this the spec fell through to the
      // "SHAPE ONLY" bar, which told a reader the layer carried no information.
      scale: STATION_OPERATOR_SCALE,
      stats,
      note: selected
        ? `${selected.operator} · ${selected.network}. ${selected.note ?? ""} ${bundle.limitation}`.replace(/\s+/g, " ").trim()
        : `${bundle.limitation} Select a pin on the globe for the antenna's own published record and the conditions over it.`,
      source: selected ? selected.sourceName : bundle.attribution,
      statusText: selected
        ? undefined
        : `${bundle.stationCount} antennas from published operator and agency sources. ${bundle.policy.militarySitesRationale}`,
      statusState: "ready",
    };
  }

  /**
   * One antenna's published record, plus what the layers already loaded say
   * about the sky over it. Nothing here is computed for a station that has not
   * been selected, and nothing is shown from a layer that is not loaded — a
   * blank is honest, a zero is not.
   */
  private selectedStationStats(station: GroundStation): Array<{ label: string; value: string }> {
    const precisionLabel: Record<GroundStation["coordinatePrecision"], string> = {
      "published-survey": "SURVEY GRADE",
      "published-approximate": "APPROXIMATE",
      "privacy-reduced": "PRIVACY-REDUCED BY PUBLISHER",
    };
    const mask = stationMinimumElevationDeg(station);
    const stats: Array<{ label: string; value: string }> = [
      { label: "OPERATOR", value: station.operator },
      { label: "COUNTRY", value: station.country },
      { label: "POSITION", value: `${station.latitudeDeg.toFixed(4)}°, ${station.longitudeDeg.toFixed(4)}°` },
      { label: "COORDINATE", value: precisionLabel[station.coordinatePrecision] },
      { label: "HORIZON MASK", value: `${mask.degrees}° ${mask.published ? "PUBLISHED" : "ASSUMED BY THIS SITE"}` },
    ];
    if (station.antennaDiameterM) stats.push({ label: "DISH", value: `${station.antennaDiameterM} m` });
    if (station.bands?.length) stats.push({ label: "BANDS", value: station.bands.join(", ") });

    const tec = sampleTecAtStation(this.weather.ionosphere, station);
    if (tec) stats.push({ label: "TEC OVERHEAD", value: `${tec.tecu.toFixed(1)} TECU` });

    if (this.drapBundle) {
      const drap = sampleDrapAtStation(this.drapBundle, station, this.simulationTime());
      stats.push({
        label: "D-RAP HAF",
        value: "highestAffectedFrequencyMhz" in drap
          ? `${drap.highestAffectedFrequencyMhz.toFixed(1)} MHz`
          : "NO FRAME AT THIS TIME",
      });
    }

    // Dwell for the spacecraft the visitor already has open. Never computed
    // across the catalogue looking for a match: this is one pair the reader
    // chose, and it answers "when is this above the horizon", not "who talks
    // to whom".
    const satellite = this.selectedIndex === null ? null : this.catalog.satellites[this.selectedIndex];
    if (satellite) {
      const dwell = this.stationDwell(station, satellite);
      if (dwell) stats.push({ label: `${satellite.name} · 24 H`, value: dwell });
    }
    return stats;
  }

  /** One station-spacecraft dwell, computed at most once a simulated minute. */
  private stationDwell(station: GroundStation, satellite: SatelliteRecord): string | null {
    const from = this.simulationTime();
    const key = `${station.id}|${satellite.id}|${Math.floor(from.getTime() / 60_000)}`;
    if (this.stationDwellCache?.key === key) return this.stationDwellCache.value;
    try {
      const dwell = computeStationPasses(station, satellite.omm, {
        from,
        to: new Date(from.getTime() + 24 * 3600 * 1000),
      });
      const value = dwell.continuouslyVisible
        ? "CONTINUOUSLY ABOVE MASK"
        : dwell.neverVisible
          ? "NEVER ABOVE MASK"
          : `${dwell.passes.length} passes · ${(dwell.fractionOfWindow * 100).toFixed(1)}% of the day`;
      this.stationDwellCache = { key, value };
      return value;
    } catch (error: unknown) {
      console.error("Station dwell could not be computed", error);
      return null;
    }
  }

  /**
   * The density volume's card.
   *
   * Two things it must never let a beautiful render imply. First, that this is
   * a measurement: it is an operational physics forecast, and the electron
   * density is not even a published field of that forecast but a quasi-neutral
   * sum of seven ion densities, so the badge says MODEL and the note says
   * both. Second, that the whole column comes from one place: the D band is an
   * empirical Wait-Spies fit driven by the MEASURED GOES X-ray flux, drawn in
   * its own palette, and the 5 km between the two models is claimed by
   * neither.
   */
  private ionosphereLegendSpec(): EnvironmentLegendSpec {
    const bundle = this.ionosphereBundle;
    const bake = this.globe.getIonosphereVolumeBake();
    const statusText = this.ionosphereLoadFailed
      ? "The verified WAM-IPE sequence could not be loaded. No synthetic replacement is shown."
      : this.ionosphereLoading !== null
        ? "Loading the 19 MB density cube"
        : bundle
          ? undefined
          : "No WAM-IPE bundle loaded yet";
    const statusState: "ready" | "no-data" | "loading" = this.ionosphereLoadFailed
      ? "no-data"
      : this.ionosphereLoading !== null
        ? "loading"
        : bundle ? "ready" : "no-data";
    const stats: Array<{ label: string; value: string }> = [];
    if (bake) {
      stats.push({ label: "PEAK DENSITY", value: `10^${bake.measured.modelMaxLog10.toFixed(1)} m⁻³` });
      stats.push({ label: "MODEL FLOOR · 90 KM", value: `10^${bake.measured.modelFloorMedianLog10.toFixed(1)} median` });
      stats.push({ label: "EMPIRICAL TOP · 85 KM", value: `10^${bake.measured.empiricalTopMedianLog10.toFixed(1)} median` });
      // The D band is drawn on its own window; saying so is the price of
      // drawing it at all, since on the model's window it would be invisible.
      stats.push({
        label: "D BAND WINDOW",
        value: `10^${bake.empiricalLogFloor.toFixed(1)}–10^${bake.empiricalLogCeiling.toFixed(1)}`,
      });
    }
    // What the retired peak surfaces uniquely knew, as numbers. A separate E
    // or F1 layer is not always THERE: over much of the globe the profile
    // climbs straight into F2 with no distinct maximum, and the published
    // criterion says so by supporting no column. That share is the fact the
    // holes in those surfaces were gesturing at.
    const surfaces = this.globe.getIonosphereSurfaceState();
    if (surfaces) {
      // "RESOLVED" was the wrong word and this row was quietly at war with the
      // rest of the layer. What the number counts is columns where the
      // extractor's peak criterion returned a value — for E that is 90% of the
      // globe, while the same artifact's E ledge has a median prominence of
      // 0.02 dex above the E–F valley (one code in 256) and a NEGATIVE
      // prominence on the dayside. Both facts are true because they measure
      // different things: a local maximum was found, and it is not
      // distinguishable. Saying "resolved" for the first invited the reader to
      // conclude the second. The label now says what is counted.
      stats.push({ label: "E PEAK CRITERION MET", value: `${surfaces.regions.e.supportedColumnPercent.toFixed(0)}% of columns` });
      stats.push({ label: "F1 PEAK CRITERION MET", value: `${surfaces.regions.f1.supportedColumnPercent.toFixed(0)}% of columns` });
      const hmF2 = surfaces.regions.f2.meanAltitudeKm;
      if (hmF2 !== null) stats.push({ label: "F2 PEAK HEIGHT", value: `${hmF2.toFixed(0)} km mean` });
    }
    const regions = ionosphereRegionMarks({
      bake,
      enabled: this.ionosphereRegionsOn,
      f1CriterionPercent: surfaces?.regions.f1.supportedColumnPercent ?? null,
      hmF2Km: surfaces?.regions.f2.meanAltitudeKm ?? null,
    });
    // THE THIRD STATE. A region with no row in the key is either switched off
    // or genuinely not in the picture, and those are different facts a reader
    // must not have to guess between. The rows name what is drawn; these two
    // lines name what is not, and why.
    if (regions.switchedOff.length > 0) {
      stats.push({
        label: "SWITCHED OFF",
        value: `${regions.switchedOff.join(" · ")} — HIDDEN IN THIS LAYER'S SETTINGS, NOT ABSENT`,
      });
    }
    if (regions.notDrawn.length > 0) {
      stats.push({
        label: "NOT IN THIS FRAME",
        value: `${regions.notDrawn.join(" · ")} — SWITCHED ON, BUT NOTHING PUBLISHED AT THOSE HEIGHTS`,
      });
    }
    return {
      layer: "ionosphere",
      title: "Ionosphere — electron density",
      badge: "MODEL + EMPIRICAL",
      evidence: "model",
      // THE FOUR REGIONS, NAMED WHERE THE READER IS LOOKING.
      //
      // Sean, on the shipped build of 2026-08-26: "when I plot the ionosphere,
      // I see what I think is the D layer in orange. but it isn't indicated
      // anywhere. It should be in the legend." He read the picture exactly
      // right — the warm band IS the D region — and the layer never said so.
      //
      // Each row's badge is the evidence class of what is DRAWN in that band,
      // which is why D reads EMPIRICAL and the three above it read MODEL: the
      // D band is the Wait–Spies fit driven by a measured X-ray number and the
      // rest is WAM-IPE. That difference is the whole reason the D band has its
      // own palette, and it is now stated rather than left to be inferred from
      // a colour. Where each region's own measured strength comes from — the
      // Chapman shapes anchored to ionosondes that actually sounded them — is
      // the vertical profile's answer, not this one's, and the rows say so.
      marks: regions.marks,
      // The window is measured from the frame, so the legend has to quote the
      // frame's numbers rather than the artifact's fixed 10^7-10^12.6. A fixed
      // legend over a moving window would be a wrong label on a right picture.
      scale: {
        gradient: "linear-gradient(90deg, #04070f, #12315f, #1d7ea6, #2eaebd, #b6ecdf, #f2fbff)",
        minimum: bake ? `10^${bake.logFloor.toFixed(1)}` : "—",
        label: "electron density · m⁻³",
        maximum: bake ? `10^${bake.logCeiling.toFixed(1)}` : "—",
      },
      stats,
      note: "A ray-marched volume of the whole published column, which is the field the TEC surface integrates. "
        + "It is NOT an electron-density observation or assimilation: 90 km and above is NOAA WAM-IPE operational forecast, "
        + "and its electron density is derived by quasi-neutral summation of seven published ion densities rather than published directly. "
        + "The warm band at 60–85 km is a different kind of evidence and is drawn in a different palette for that reason — "
        + "the empirical Wait–Spies D-region profile, driven by solar zenith angle and the measured GOES X-ray flux. "
        + "Neither model claims 85–90 km, so nothing is drawn there. The four named regions above are ALTITUDE BANDS of this "
        + "one column, and each can be switched off on its own in this layer's settings — the band edges are the conventional "
        + "D/E/F1/F2 boundaries, not a surface anything measured, and the model resolves a distinct peak at F2 but not at E or "
        + "F1. What a particular region is doing over a particular PLACE, with its own evidence and its own critical frequency, "
        + "is what the vertical profile answers; the settings carry a button that arms it. "
        // CORRECTNESS FIX 2026-09-04: the one stretch in this layer was not
        // declared anywhere a reader can see. `IONOSPHERE_VOLUME_TRANSFER`
        // carries `empiricalOpacityScale: 6.0`, applied in the shader as
        // `mix(shaped * empiricalOpacityScale, modelOpacity, isModel)`. The
        // module's own comment is honest about it — "NOT a physical statement"
        // — and says "the card says the window it is drawn on", which the card
        // does. But the window is not the multiplier: the card said the band is
        // "faint here by construction", which describes the opposite of a
        // six-fold boost. An undeclared exaggeration is the one thing this site
        // does not ship, so it is declared here, in the same breath as the
        // reason for it.
        + "The D band is drawn SIX TIMES more opaque than the same density would be in the model ramp above it, and on its "
        + "own three-decade window — without both it renders as nothing, because it holds two to three decades fewer "
        + "electrons than the F2 peak across a band a tenth as thick. That is a legibility choice and changes no number "
        + "on this card. "
        + "The D region holds far fewer electrons than the F peak — its faintness relative to the F2 peak is real — and the reason it matters is HF absorption, "
        + "which is the D-region absorption layer, not this one.",
      validAt: bundle?.runAt,
      source: bundle?.source.name,
      statusText,
      statusState,
    };
  }

  private environmentLegendSpec(layer: LayerName): EnvironmentLegendSpec {
    const driver = this.currentMagnetopauseDriver;
    const selectedTime = this.simulationTime().toISOString();
    if (layer === "groundStations") return this.groundStationLegendSpec();
    if (layer === "ionosphere") return this.ionosphereLegendSpec();
    if (layer === "tec") {
      const [minimum, maximum] = this.weather.ionosphere.tecRange;
      return {
        layer,
        title: "Total electron content",
        badge: "ASSIMILATED",
        evidence: "assimilated",
        scale: {
          gradient: "linear-gradient(90deg, hsl(260 92% 58%), hsl(145 92% 58%), hsl(30 92% 58%))",
          minimum: this.formatScaleValue(minimum),
          label: "GloTEC vertical TEC · TECU",
          maximum: this.formatScaleValue(maximum),
        },
        note: "Color is vertical total electron content; opacity also reflects the published GloTEC quality flag. This latest 2-D field is not a vertical density profile.",
        validAt: this.weather.ionosphere.observedAt,
      };
    }
    if (layer === "drap") {
      const bundle = this.drapBundle;
      const state = this.globe.getDrapSurfaceState();
      const selection = bundle && state?.status === "ready" ? selectDrapFrame(bundle, state.validAt) : null;
      const absorptionAtFiveMhz = selection
        ? drapAbsorptionDbAtFrequency(selection.frame.maximumHafMhz, 5)
        : null;
      const status = this.surfaceLegendStatus(state, this.drapLoading !== null, this.drapLoadFailed);
      const condition = state?.legend.condition
        ?? (selection ? drapCondition(selection.frame) : undefined);
      const scale = {
        gradient: "linear-gradient(90deg, #23bcc7, #3db5de 20%, #f3d052 42%, #f79737 62%, #eb4e3e 80%, #892bb1)",
        minimum: bundle?.legend.belowMinimumLabel ?? "<3 MHz",
        label: bundle?.legend.subtitle ?? "1 dB HAF · MHz",
        maximum: bundle?.legend.aboveMaximumLabel ?? "≥30 MHz",
      };
      const coverage = this.rollingCoverage(this.manifest.drap, state?.legend.sourceRange.frameCount);

      // PAST THE END OF THE NOWCAST, AND THEREFORE OFF.
      //
      // The second half of the same missing-state defect: the layer read
      // ACTIVE NOAA MODEL with a live legend at +72 h, three days past the
      // last frame anybody has published, because it had no expired state any
      // more than it had a quiet one. It carries its own notice rather than
      // the shared coverage one for the reason the magnetosphere does: "the
      // next frame has not arrived yet" is true of a feed with a gap in it
      // and false here. There is no future D-RAP frame to be late. The layer
      // is a nowcast and it stops at the present, permanently and by
      // construction (`time.futureAvailable` is `false` in every bundle).
      if (state?.status === "stale" && bundle) {
        const newestIso = state.lastValidAt;
        const newestLabel = utcMinuteLabel(newestIso);
        const hoursPast = state.ageMinutes / 60;
        return {
          layer,
          title: "D-region HF absorption — past the nowcast",
          keyTitle: "D-region HF absorption · nowcast ended",
          badge: "NOWCAST ONLY · LAYER OFF",
          evidence: "model",
          emptyLabel: "NOWCAST ENDED · NOTHING DRAWN",
          scale,
          stats: [
            { label: "SELECTED UTC", value: "PAST THE END OF THE NOWCAST — THE LAYER IS OFF" },
            { label: "THE RECORD STOPS AT", value: newestLabel },
            {
              label: "HOW FAR PAST",
              value: hoursPast >= 24
                ? `${(hoursPast / 24).toFixed(1)} days`
                : `${hoursPast.toFixed(1)} hours`,
            },
            { label: "FUTURE FRAMES PUBLISHED", value: "NONE — D-RAP IS A NOWCAST, NOT A FORECAST" },
          ],
          note: drapNowcastEndSentence(newestLabel),
          source: bundle.source.currentData,
          coverage,
          statusState: "no-data",
          statusText: `NOWCAST ONLY — D-RAP publishes nothing past the present. The record stops at ${newestLabel}; `
            + "scrub back for the measured map.",
          unavailable: {
            headline: "No D-region absorption here — D-RAP is a nowcast, and it stops at the present.",
            because: drapNowcastEndSentence(newestLabel),
            jumpToIso: newestIso,
            jumpLabel: `Go back to ${newestLabel}`,
          },
        };
      }

      return {
        layer,
        title: bundle?.legend.title ?? "D-region HF absorption",
        // THE BADGE CHANGES STATE, and this is the whole point of the fix.
        //
        // A folded card shows its name and its badge and nothing else, and
        // that is exactly what Sean was looking at: "D-region HF absorption /
        // ACTIVE NOAA MODEL" over an empty globe. ACTIVE was accurate about
        // provenance and wrong about presence, and presence is the question a
        // reader is actually asking when the globe is bare. All three chips
        // now carry the frame's own peak, so the badge is a reading that moves
        // under the slider rather than a fixed label.
        //
        // "NOAA MODEL" is not lost with it. The chip's colour IS the evidence
        // class -- coral for MODEL, the one stamp the stylesheet exempts from
        // its own rules -- the card's provenance section prints "Evidence" and
        // "Source" in words, and `QUIET · 0 MHz HAF` already shipped without
        // those two words in the state this replaces.
        badge: status.state === "ready" && condition ? condition.badge : status.badge,
        evidence: "model",
        scale,
        // The reader's one-glance answer, on the surface that is never folded.
        conditionLine: status.state === "ready" ? condition?.legendLine : undefined,
        stats: selection ? [
          { label: "MAP MAX HAF", value: `${selection.frame.maximumHafMhz.toFixed(1)} MHz` },
          // WHERE, not just how strong. The peak alone cannot tell a reader
          // whether a bare globe is a quiet ionosphere or a broken layer;
          // "4.4% of the globe drawn, none of it at 10 MHz, none at 30" can,
          // and all three numbers are published on the frame. Nothing is
          // drawn below 3 MHz, so the 3 MHz row is literally the share of the
          // globe carrying any colour at all.
          { label: "DRAWN AT 3 MHz", value: percentOfGlobe(selection.frame.affectedCellPercent["3MHz"]) },
          { label: "AFFECTED AT 10 MHz", value: percentOfGlobe(selection.frame.affectedCellPercent["10MHz"]) },
          { label: "AFFECTED AT 30 MHz", value: percentOfGlobe(selection.frame.affectedCellPercent["30MHz"]) },
          { label: "5 MHz @ MAP MAX", value: absorptionAtFiveMhz === null ? "—" : `${absorptionAtFiveMhz.toFixed(1)} dB` },
          // NOAA's own words for why the map reads as it does, and the only
          // two rows on this card that do not move with the clock. They stay
          // under the caveat rule in `dataViewerSections`: they are what stops
          // an empty map being read as a fault. They are shown ONLY on the
          // newest frame because that is the only frame they describe --
          // `pipeline/drap.py` parses them from the current text alone.
          ...(bundle && selection.frame.validAt === bundle.frames.at(-1)?.validAt
            ? [
              ...(bundle.messages.xrayWarning ?? bundle.messages.xray
                ? [{ label: "NOAA X-RAY STATUS", value: bundle.messages.xrayWarning ?? bundle.messages.xray! }]
                : []),
              ...(bundle.messages.protonWarning ?? bundle.messages.proton
                ? [{ label: "NOAA PROTON STATUS", value: bundle.messages.protonWarning ?? bundle.messages.proton! }]
                : []),
            ]
            : []),
          { label: "MODE", value: this.fieldRendering === "smooth" ? "SMOOTH" : "NATIVE GRID" },
        ] : [{ label: "SELECTED UTC", value: status.short }],
        note: `${bundle && selection ? `${drapConditionSentence(bundle, selection.frame)} ` : ""}Color is NOAA's 1 dB Highest Affected Frequency. At each grid cell, the documented vertical two-pass 5 MHz absorption is (HAF ÷ 5 MHz)^1.5 dB; the statistic above uses the map maximum, not a specific radio link. Oblique paths and link margin are not modeled here.`,
        validAt: state?.status === "ready" ? state.validAt : undefined,
        source: bundle?.source.currentData ?? "NOAA SWPC D-RAP native numeric grid",
        coverage,
        statusText: status.text,
        statusState: status.state,
      };
    }
    if (layer === "thermosphere") {
      const bundle = this.thermosphereBundle;
      const surface = this.globe.thermosphereSurface();
      const record = this.manifest.thermosphere;
      // Two different questions, and running them together is what let the card
      // say MODEL over an hour that was not being drawn. IS ANYTHING DRAWN is
      // answered by the frame identity -- the one thing that cannot be faked by
      // a picture that merely turns with the Earth. WHETHER THE CHOSEN LEVEL IS
      // CROSSED is a fact about that level inside the published column, and at
      // 1e-11 kg m-3 it can fail over part of the globe while the air itself is
      // drawn perfectly well.
      const drawnAt = this.thermosphereFrameValidAt;
      const heights = surface && Number.isFinite(surface.minAltitudeKm);
      const empiricalRecord = this.manifest.thermosphereEmpirical;
      // The badge follows the MODEL THAT PRODUCED THE FRAME ON SCREEN, and the
      // claim that model is entitled to make. Two things change under the
      // reader's hand and they change together: NOAA WAM's physics forecast
      // where NOAA has one, the NRL empirical fit everywhere else on a
      // 120-hour timeline WAM covers about a tenth of.
      //
      // FORECAST is on the chip when it is earned and off it when it is not.
      // Sean asked whether MODEL should be the only chip "since we don't have a
      // forecast" — the data says the opposite. Every frame a WAM cycle
      // publishes is issued before the hour it describes; and forward of the
      // last observed Kp interval the empirical field is driven by NOAA's
      // forecast of Kp and F10.7, so those hours are a forecast too. Behind
      // that boundary the drivers are the observed record and the chip drops
      // the word.
      const selection = this.thermosphereSelection;
      const chip = thermosphereBadge(drawnAt ? selection : null);
      const empirical = chip.evidence === "empirical";
      const loading = this.thermosphereLoading !== null || this.thermosphereShardLoading.size > 0;
      const status = this.thermosphereLoadFailed
        ? { text: "Artifact unavailable in this release", state: "no-data" as const, badge: "NO DATA" }
        : drawnAt
          ? { text: `Drawn for ${drawnAt.slice(11, 16)}Z · ${selection?.because ?? ""}`.trim(), state: "ready" as const, badge: chip.badge }
          : loading
            ? { text: "Loading the neutral-density field", state: "loading" as const, badge: "LOADING" }
            : { text: "No published frame covers the selected time", state: "no-data" as const, badge: "NO DATA" };
      return {
        layer,
        title: "Thermosphere height",
        badge: status.badge,
        evidence: empirical ? "empirical" : "model",
        // The scale is density now, not an altitude, because the layer draws
        // the air itself rather than one chosen surface through it. The ramp
        // runs the way the picture does: thin and transparent at the top,
        // thick and warm at the bottom, with no edge anywhere.
        // Short ends, because the legend puts minimum, label and maximum on one
        // narrow row and the middle is what gets eaten: "NEUTRAL AIR DENSITY"
        // rendered as "NE...", which names nothing. The ends carry the altitude
        // and the ramp itself carries the sense, so the words the row cannot
        // afford live in the note below it instead.
        scale: {
          gradient: `linear-gradient(90deg, ${THERMOSPHERE_VOLUME_COLOR_HEX.join(", ")})`,
          minimum: `${THERMOSPHERE_VOLUME_ALTITUDE_KM.high} km`,
          label: "AIR DENSITY",
          maximum: `${THERMOSPHERE_VOLUME_ALTITUDE_KM.low} km`,
        },
        stats: drawnAt ? [
          // The hour actually on screen, first, because it is the answer to the
          // question this layer kept getting wrong. The card used to print
          // `frames[0].validAt` here -- the first frame in the release, never
          // the drawn one -- so scrubbing across six hourly frames left this
          // line reading the same time throughout, which is a card telling the
          // reader the layer is static.
          { label: "DRAWN FOR", value: `${drawnAt.slice(11, 16)}Z` },
          // The level the two heights below answer for. It is on the card
          // because the reader chooses it on the card, and because without it
          // "HIGHEST 500 km" is a number with no question attached.
          { label: "FOLLOWING", value: `${this.thermosphereLevel.toExponential(0)} kg m⁻³` },
          // Still the isopycnic altitude, still the storm signal, but now a
          // figure on the card rather than a shell in the scene: 78 km of
          // relief on a 6,371 km globe is legible as a number and invisible as
          // geometry, and drawing it also drew a boundary that is not there.
          ...(heights ? [
            { label: "LOWEST", value: `${surface!.minAltitudeKm.toFixed(0)} km` },
            { label: "HIGHEST", value: `${surface!.maxAltitudeKm.toFixed(0)} km` },
          ] : [{ label: "HEIGHT", value: "not crossed in the column" }]),
          ...this.thermosphereDragStats(),
          // The spread IS the storm signal: a quiet atmosphere is nearly the
          // same height everywhere, a heated one bulges over the auroral zones.
          ...(heights ? [
            { label: "SPREAD", value: `${(surface!.maxAltitudeKm - surface!.minAltitudeKm).toFixed(0)} km` },
          ] : []),
          // The model that drew THIS hour, not the model named by the release.
          // With two fields on one timeline those are different questions, and
          // the release-level answer is wrong for nine tenths of the slider.
          { label: "MODEL", value: empirical ? (empiricalRecord?.modelShortName ?? "NRLMSIS 2.1") : (bundle?.model.modelShortName ?? "NOAA WAM-IPE") },
          // What the empirical model was DRIVEN by, at this hour, from the
          // frame itself. This is the teaching point the layer was built for:
          // the reader can watch ap rise and the air thicken with it.
          ...(empirical && selection?.frame.drivers ? [
            { label: "Kp / ap", value: `${selection.frame.drivers.kp.toFixed(2)} / ${selection.frame.drivers.ap}` },
            { label: "F10.7", value: `${selection.frame.drivers.f107.toFixed(0)} sfu` },
          ] : []),
        ] : [{ label: "STATE", value: status.badge }],
        // Written from the level the reader CHOSE. It used to interpolate
        // `DEFAULT_ISOPYCNIC_KG_M3`, so selecting 1e-11 or 1e-13 moved the three
        // heights above while this paragraph went on naming 1e-12 underneath
        // them — the card contradicting the control beside it. The second
        // sentence is new and answers the complaint directly: the drawn air is
        // the whole column, and is not what this control moves.
        note: `The heights above are the altitude at which the neutral air reaches ${this.thermosphereLevel.toExponential(0)} kg m⁻³, on the same ruler as the satellites, so a satellite inside that height is flying through air at least that dense. Choosing a different level re-reads those heights; it does not change the drawn air, which is the whole published column from ${THERMOSPHERE_VOLUME_ALTITUDE_KM.low} to ${THERMOSPHERE_VOLUME_ALTITUDE_KM.high} km and has no boundary in it. When a geomagnetic storm heats the upper atmosphere it expands and these heights climb — that rise is the drag. ${THERMOSPHERE_LIMITATION}`,
        // The DRAWN frame. This read `bundle.frames[0].validAt` -- the first frame
        // in the release -- so the one line on the card whose job is to say
        // which instant is on screen said the same instant at every clock
        // position, for as long as the layer has existed.
        validAt: drawnAt ?? undefined,
        source: empirical
          ? (empiricalRecord?.product ?? "NRLMSIS 2.1, evaluated from NOAA SWPC F10.7 and Kp-derived ap")
          : (bundle?.source.product ?? "NOAA/NCEP WAM-IPE Forecast System, neutral mass density"),
        // BOTH windows, always, whichever is drawn. The single most misleading
        // thing this card used to do was quote WAM's twelve hours as "the
        // coverage" while the reader was somewhere in the other hundred and
        // eight; naming the two spans side by side is what makes the boundary a
        // fact the reader can find rather than a surprise they scrub into.
        coverage: [
          record
            ? `NOAA WAM ${record.frameCount} frame${record.frameCount === 1 ? "" : "s"} · ${record.validFrom.slice(5, 16).replace("T", " ")}Z–${record.validTo.slice(5, 16).replace("T", " ")}Z${record.skippedCount ? ` · ${record.skippedCount} unreadable` : ""}`
            : "NOAA WAM: none in this release",
          empiricalRecord
            ? `NRLMSIS ${empiricalRecord.frameCount} frames · ${empiricalRecord.validFrom.slice(5, 16).replace("T", " ")}Z–${empiricalRecord.validTo.slice(5, 16).replace("T", " ")}Z`
            : "NRLMSIS: none in this release",
        ].join(" · ") || undefined,
        statusText: status.text,
        statusState: status.state,
      };
    }
    if (layer === "groundField") {
      const bundle = this.groundFieldBundle;
      const state = this.globe.getGroundFieldState();
      const legend = state?.legend;
      const status = this.groundFieldLegendStatus(state, this.groundFieldLoading !== null, this.groundFieldLoadFailed);
      return {
        layer,
        title: "Ground magnetic perturbation",
        badge: status.badge,
        evidence: "forecast",
        // Always a real ramp, never gated on a frame having loaded yet — the
        // 0-1500 nT scale and its ticks are fixed constants
        // (GROUND_FIELD_LEGEND_TICKS_NT), not per-frame data, so there is no
        // reason for this card to fall back to the "SHAPE ONLY" bar while
        // its first artifact is still in flight.
        scale: {
          gradient: "linear-gradient(90deg, #0a1f2c, #1a5488 12%, #20849c 28%, #38b098 42%, #a8c858 58%, #f0b038 72%, #ee6c38 84%, #e23c4c 93%, #b02c8c)",
          minimum: legend?.minimumLabel ?? "0 nT · no modeled disturbance",
          label: `${(legend?.systemLabel ?? "Total").toUpperCase()} · HORIZONTAL · nT`,
          maximum: legend?.maximumLabel ?? "1500 nT and above",
        },
        stats: state?.status === "ready" && legend ? [
          { label: "MAP MAX HORIZONTAL dB", value: legend.maximumHorizontalNt !== null ? `${legend.maximumHorizontalNt.toFixed(0)} nT` : "—" },
          { label: "AT", value: legend.maximumHorizontalAt ? `${legend.maximumHorizontalAt.latitudeDeg.toFixed(0)}°, ${legend.maximumHorizontalAt.longitudeDeg.toFixed(0)}°` : "—" },
          { label: "RUN LEAD", value: legend.leadMinutes !== null ? `${Math.round(legend.leadMinutes)} min` : "—" },
          { label: "MODE", value: this.fieldRendering === "smooth" ? "SMOOTH" : "NATIVE GRID" },
        ] : [{ label: "SELECTED UTC", value: status.short }],
        note: `${legend?.systemMeaning ? `${legend.systemMeaning} ` : ""}${bundle?.attribution ?? "The per-current-system split is the model's own attribution, not an observation."} Colour is the horizontal ground perturbation magnitude from NOAA's operational Geospace SWMF mag_grid; the grid stops at ${legend ? legend.latitudeLimitDeg.toFixed(0) : "85"}° latitude and nothing is drawn poleward of it.`,
        validAt: state?.status === "ready" ? state.validAt : undefined,
        source: bundle?.source.url ?? "NOAA operational Geospace SWMF mag_grid",
        coverage: legend
          ? `${legend.sourceRange.frameCount} exact frame${legend.sourceRange.frameCount === 1 ? "" : "s"}${legend.sourceRange.validFrom ? ` · ${legend.sourceRange.validFrom.slice(5, 16).replace("T", " ")}Z–${(legend.sourceRange.validTo ?? "").slice(5, 16).replace("T", " ")}Z` : ""}`
          : undefined,
        statusText: status.text,
        statusState: status.state,
      };
    }
    if (layer === "aurora") {
      const bundle = this.auroraHistoryBundle;
      const state = this.globe.getAuroraHistoryState();
      const status = this.surfaceLegendStatus(state, this.auroraHistoryLoading !== null, this.auroraHistoryLoadFailed);
      return {
        layer,
        title: bundle?.quantity.name ?? "Aurora viewing probability",
        badge: status.badge,
        evidence: "forecast",
        scale: {
          gradient: "linear-gradient(90deg, #12251f, #76e6a5 35%, #f5c96a 68%, #ff7b78)",
          minimum: "0",
          label: "OVATION · % · BOTH HEMISPHERES",
          maximum: "100",
        },
        stats: state?.status === "ready" ? [
          { label: "HEMISPHERES", value: "NORTH + SOUTH" },
          { label: "MODE", value: this.fieldRendering === "smooth" ? "SMOOTH" : "NATIVE GRID" },
          { label: "LEAD", value: state.observedAt ? `${Math.round((Date.parse(state.validAt) - Date.parse(state.observedAt)) / 60_000)} min` : "—" },
        ] : [{ label: "SELECTED UTC", value: status.short }],
        // CORRECTNESS FIX 2026-09-04: the last sentence. The colour bar runs
        // 0–100% and `auroraProbabilityColor` draws every cell at 1% or below
        // fully transparent — NOAA's lowest quantized bin, a broad skirt across
        // 40–56 N that would otherwise read as aurora over the mid-latitudes.
        // Good reason, undeclared: the equatorial seam next to it is declared
        // in full and this was not, so a reader comparing the bar to the map
        // had no way to know the bottom of the bar is never painted.
        note: "This artifact stores NOAA's 0–100% OVATION viewing-probability field for both hemispheres. It is not an energy-flux field, optical brightness, or a particle count; daylight, cloud, terrain, and light pollution are not included. NOAA's grid also carries a 1–4% numerical seam in the rows just south of the equator, disconnected from the oval by tens of degrees of zero probability; those cells are shown as missing, not as zero. Cells at 1% or below are drawn fully transparent: 1% is NOAA's lowest quantized bin rather than a resolved probability, and it covers a broad mid-latitude skirt that would read as aurora if it were painted. The source value is unchanged — only the ink stops at the bottom of the bar.",
        validAt: state?.status === "ready" ? state.validAt : undefined,
        observedAt: state?.status === "ready" ? state.observedAt ?? undefined : undefined,
        source: bundle?.source.currentNumericGrid ?? "NOAA SWPC OVATION latest native numeric grid",
        coverage: this.rollingCoverage(this.manifest.aurora, state?.legend.sourceRange.frameCount),
        statusText: status.text,
        statusState: status.state,
      };
    }
    if (layer === "regions") {
      return {
        layer,
        title: "D / E / F teaching regions",
        badge: "SCHEMATIC",
        evidence: "schematic",
        scale: {
          gradient: "linear-gradient(90deg, #ff7b78 0 31%, #f5c96a 31% 62%, #a98cff 62%)",
          minimum: "D",
          label: "CONCEPTUAL BANDS · NOT DENSITY DATA",
          maximum: "F",
        },
        note: "These shells are explicitly schematic and will not be treated as an operational ionosphere field. WAM-IPE supplies the data-driven 3-D density/composition view.",
      };
    }
    if (layer === "plasmasphere") {
      return plasmasphereLegendSpec(this.globe.getPlasmasphereField(), this.plasmasphereSimulationState());
    }
    if (layer === "ringCurrent") {
      // Dst IS this layer's quantity, and it is measured, so the card quotes
      // the same number the storm banner is grading the storm with rather than
      // describing it in the abstract.
      return ringCurrentLegendSpec(
        this.globe.getRingCurrentState(),
        this.plasmasphereSimulationState(),
        stormHeadline(this.weather.storm, this.weather.magnetopause.driverSeries, this.simulationTime()),
        this.substormStateAtTime(this.simulationTime()),
        // The loop the scene is keeping, so the printed period and the drawn
        // pulse are the same object's.
        this.globe.getRingCurrentFormation(),
        // The age of the frame the drift was traced in. Read off the SAME
        // evaluated field the illustration was built from — `updateInnerMagnetosphere`
        // sets both in one call — so the picture and the label cannot be
        // talking about different frames.
        this.dgcpmNowcastState(),
      );
    }
    if (layer === "solarWind") {
      const trueDistance = this.distanceScale === "true-distance";
      const mix = solarWindSpeciesMix();
      const magnetosphereOn = byId<HTMLInputElement>("layer-geospace").checked;
      // The three toggles the coupling is progressive across. The reader's own
      // switches decide how far down the chain the picture goes, which is what
      // Sean asked for: solar wind alone, then the boundary, then the tail,
      // then the oval.
      // Read for the reader-facing sentence below only. The MOTION no longer
      // depends on it: since 2026-08-27 the whole Dungey chain is drawn
      // whenever the measured inputs exist, whichever layers are on.
      void byId<HTMLInputElement>("layer-ring-current").checked;
      const auroralOvalOn = byId<HTMLInputElement>("layer-aurora").checked;
      const stormDerived = this.weather.storm?.derived;
      const coupling = driver ? newellCoupling(driver.speedKps, driver.byNt, driver.bzGsmNt) : null;
      const couplingBandLabel = newellBand(coupling, stormDerived?.newellCalibration ?? []);
      const couplingDriveValue = this.dungeyCouplingDrive(driver);
      const tailReturn = this.globe.getTailReturnReport();
      const tailReturnRefused = tailReturn !== null
        && tailReturn.extendedPathCount === 0
        && tailReturn.refusedPathCount > 0;
      const mhdCutOn = this.globe.mhdCutEnabled;
      // The legend's three rows, in the plasma's own order by number. THERE IS
      // NO BAR ANY MORE — see `EnvironmentLegendSpec.composition` for why the
      // proportion bar was removed rather than eased a third time. Each row
      // carries the species' colour, its true share, and the bulk energy it
      // carries at the MEASURED wind speed, which is ½mv² and nothing else.
      const speciesKey = solarWindSpeciesKey(mix, driver?.speedKps ?? null);
      return {
        layer,
        title: "Solar wind and IMF",
        // The units, in the one place on this row that cannot truncate. On a
        // scale they live in the middle cell; here the middle cell is H⁺.
        keyTitle: "Solar wind · species by number",
        badge: "OBSERVED",
        evidence: "observed",
        // The layer's quantity: the species mix of the measured plasma, listed
        // rather than drawn as areas, each row carrying the energy that species
        // rides the measured wind with. Sean's own design, after the bar failed
        // twice at the one thing a bar is for.
        composition: {
          rows: speciesKey.map((cell) => ({
            swatch: cell.swatch,
            name: cell.text,
            detail: cell.energyText ?? "—",
            note: cell.species === "electron"
              // CORRECTNESS FIX 2026-09-04: "~50x" was a constant printed
              // beside a variable. The bulk figure in this row is ½mv² on the
              // MEASURED speed, so the ratio to a ~10 eV thermal electron moves
              // with the wind: 52x at 260 km/s (the speed the sentence was
              // written at), 22x at 400, 7x at 700. The size of the thermal
              // energy is the stable fact; the ratio is not.
              ? "bulk-flow energy — the like-for-like comparison with the ions. Their random thermal motion is separate and much larger: order 10 eV, which is many times this figure at any ordinary wind speed"
              : cell.species === "alpha"
                ? "4x the proton's, because a He²⁺ nucleus is 4 proton masses on the same speed"
                : undefined,
          })),
          caption: driver
            ? `Bulk energy = ½mv² at the measured V ${driver.speedKps.toFixed(0)} km/s. DERIVED FROM MEASURED: one measured speed, three constant masses. Not a measurement of individual particles.`
            : "No propagated wind for the selected UTC, so there is no speed to derive an energy from.",
        },
        stats: driver ? [
          { label: "V", value: `${driver.speedKps.toFixed(0)} km/s` },
          { label: "nₚ", value: `${driver.densityCm3.toFixed(2)} cm⁻³` },
          { label: "Bz", value: `${driver.bzGsmNt.toFixed(1)} nT GSM` },
          { label: "Pdyn", value: `${driver.dynamicPressureNpa.toFixed(2)} nPa` },
          // The number that drives the coupling, on the card that shows the
          // coupling. It is the same quantity, from the same function, that
          // the storm panel already grades the day with — printed here so a
          // reader can watch it move and watch the transport move with it.
          ...(coupling === null ? [] : [{
            label: "Newell coupling",
            value: `${Math.round(coupling).toLocaleString()}${couplingBandLabel ? ` · ${couplingBandLabel}` : ""}`,
          }]),
          // CORRECTNESS FIX 2026-09-04: this row is the one the layer was
          // missing. `solar-input-visuals.ts` exports
          // `SOLAR_WIND_MODE_PRESENTATION` against a docstring that says "the
          // legend must always name which of these is drawn; this table is
          // exported so the UI cannot paraphrase the distinction into
          // something softer" — and the table had no consumer anywhere in
          // src/, tests/ or index.html, while `globe.getSolarWindMode()` was
          // written for the legend and never called. So a card badged OBSERVED
          // described a measured wind and never said that the PATHS every
          // particle rides are an idealised cue. That is the regression the
          // docstring records Sean catching once already.
          {
            label: "FLOW FIELD",
            value: SOLAR_WIND_MODE_PRESENTATION[this.globe.getSolarWindMode()].badge,
          },
        ] : [{ label: "SELECTED UTC", value: "NO PROPAGATED DATA" }],
        note: "WHAT IS MEASURED AND WHAT IS NOT. The population, brightness, cadence and species mix of this shower are the measured L1 wind. The PATHS are not: every particle in the 3-D shower follows an idealised incompressible no-penetration streamline around the drawn boundary — an honest teaching cue for deflection, uncoupled from the modelled plasma. NOAA's own flow solution is on this globe, as the colours of the two cut planes in the Magnetosphere layer; nothing rides it here. "
          + "ONE WIND, THREE MASSES. Every particle in the shower rides the same measured bulk speed; what tells the species apart is how heavy each one is. H⁺ protons are the amber, e⁻ electrons the pale cream of the same gold family — those two are 98% of the plasma and are meant to read as one thing — and the He²⁺ alphas are the single cool periwinkle spark, because the warm-and-magenta lane on this site already belongs to the ring current and a moving warm dot inside that ramp is a colour collision, not an accent. "
          // CORRECTNESS FIX 2026-09-04: "about twenty" was measured when the
          // shower drew 2,200 tracers. `globe.ts` raised it to 4,600 on the day
          // the sentence was written, and at the reference wind that is about
          // 45 alphas on screen — more at a fast or dense one. A count that has
          // to be re-measured every time the tracer budget moves is a claim
          // waiting to rot, so the sentence now states the PROPORTION, which is
          // what the reader is actually being told and what the mix fixes.
          + "Alphas are about one glyph in fifty, because there are only about 2% of them. FOUR DRAWING CHOICES make the three findable, and not one of them changes how many there are, which species any particle is, or where it goes. SIZE is an order and not a ratio: He²⁺ draws at about 1.45 times a proton's width and e⁻ at 0.85, so the eye gets heavy, middle, light. BRIGHTNESS is a per-colour correction: the periwinkle is 1.63x darker than the amber in relative luminance, so without it an alpha would emit 61% of a proton's light purely because of its hex code. STREAK CHARACTER is per species: e⁻ trails a longer, softer streak and He²⁺ a short heavy one, so mass reads as motion — every streak is the same fixed display length, and the shared speed is real. DEPTH is a camera effect: tracers passing right in front of the lens fade back to a fifth of their opacity and far ones draw slightly smaller, so the wind reads as a volume you look through rather than confetti on the glass; near Earth, where the funnelling and the snap-back happen, nothing is dimmed. "
          // CORRECTNESS FIX 2026-09-04: three more display choices, none of
          // them declared anywhere a reader could see. They ARE written down —
          // in `SOLAR_INPUT_VISUAL_METHOD.solarWind.limitation` and in
          // `geometry.userData.upstreamSampling`, neither of which the UI ever
          // renders, and `describeUpstreamFace` even asserts the face sampling
          // is "stated in words on the layer card". It was not. Measured: the
          // face sampling puts 17.1% of tracers inside 13.5 Re of the axis
          // against 6.0% for a real plane-parallel front at the default face,
          // and 7.65% against 0.114% zoomed out — which inflates exactly the
          // near-axis population this card teaches about. 300 impact points
          // carry 4,600 tracers. The guided set draws at 1.35x opacity and 1.3x
          // size against the free shower.
          + "THREE MORE, about where the marks are rather than what they look like. The upstream face is sampled evenly over the DRAWN PAGE, not evenly in space — equal drawn area carries equal numbers — because the shared ruler compresses distance so hard that an even physical front stacks half the tracers into a halo at the frame's edge; that puts noticeably more of them near the Sun–Earth line than a real front would. The shower rides about 300 shared streamlines rather than one each, so it reads as a stream and not as speckle. And the guided particles — the ones on the field lines — are drawn a little brighter and a little larger than the free shower so they can be picked out of it. None of the three changes how many particles are drawn, which species any of them is, or where it goes. "
          + "The alpha briefly drew at four times a proton's AREA — the literal mass ratio. That was withdrawn on 2026-08-27: nobody can decode an area ratio off a three-pixel glyph, and with the brightness correction it put three times a proton's light into a 2% species, which is why it read as a rendering fault. The mass ratio is on the legend instead, as an energy you can read. "
          + "Count and brightness follow the measured density; cadence follows the measured bulk speed. Species are an illustrative "
          + "sampling of those measured bulk totals — we measure plasma, not individual particles — and the He²⁺/H⁺ ratio is the "
          + `canonical ~${(ALPHA_TO_PROTON_NUMBER_RATIO_ASSUMED * 100).toFixed(0)}% by number, ASSUMED because the L1 feed does not measure it; electrons follow by quasi-neutrality. `
          + "Essentially all of the solar wind is charged, so all of it deflects at the boundary; the Sun's uncharged output is light — "
          + "the X-ray layer — which crosses the field in a straight line. "
          // Handoff 4.5: the tracers appear to spray from a point off one
          // corner. They are not. They are released on a FLAT plane 32 Earth
          // radii upstream and travel parallel, because the Sun is 150 million
          // km away and its wind arrives as a plane front, not as a fan. What
          // bends them is this site's shared radial ruler, which compresses
          // distance so the whole magnetosphere fits beside the Earth — the
          // same ruler every other layer is drawn on, which is why it is not
          // undone for this one alone. The undistorted view already exists.
          + (trueDistance
            ? "The wind arrives as a parallel front, released on a flat plane 32 Earth radii upstream: on this true-distance scale that is what you see. "
            : "The wind is released as a PARALLEL FRONT on a flat plane 32 Earth radii upstream — the Sun is 150 million km away, so its wind arrives as a plane, not as a spray from a point. The fan you see is this site's compressed distance scale bending straight paths, not the physics; switch the distance scale to true distance to see the front undistorted. ")
          // THE MOTION NO LONGER DEPENDS ON WHICH LAYERS ARE ON. Sean,
          // 2026-08-27: "the solar wind should move the same regardless of
          // what layer is turned on... The particles should show all the
          // different movements regardless." The sentence that used to say
          // "switch the magnetosphere on to see the coupling" was describing a
          // gate that no longer exists; what changes with that layer is only
          // whether the wind has to draw its own cue for the lines.
          + "A guided fraction follows the magnetosphere model's traced field lines: down the cusp funnels to the poles — the entry that feeds the dayside aurora — and tailward along the open lobes. Funnelled particles end at the field line's own footpoint latitude (the cusp band), not at the measured auroral oval. "
          // WHAT THE FAINT VIOLET DASHES ARE. With the magnetosphere layer
          // ON the cue's SOLID half steps aside, because that layer draws
          // those same traced lines itself at a better weight. Its BROKEN
          // half does not, because nothing else on this page draws the
          // schematic Dungey legs at all — and a reader who can see marks
          // and cannot see what they are will read them as a fault. Sean,
          // on the deployed build with all four layers on: "On the right
          // side there are dashed lines and they shouldn't be there. Seems
          // to be some artifact your agents left behind." They are ours and
          // they are deliberate, so they are named here, where he is
          // standing when he asks.
          + (magnetosphereOn
            ? "Past the neutral line the geometry stops being traced and becomes schematic, and nothing else on this page draws it — so the wind keeps its own faint violet line there, broken into a fifty-fifty dash of half an Earth radius of mark and half of gap. Those dashes are the path the tracers beside them are riding, and the break is what says nobody measures it. "
            : "The magnetosphere layer is off, so those lines are not otherwise drawn: the faint violet threads among the tracers are the wind's own cue for the polylines its guided particles are riding — solid where the geometry is the traced field-line model, and a fifty-fifty dash — half an Earth radius of mark, half of gap — where it is schematic transport nobody measures. Switch the magnetosphere layer on for the full field with its |B| ramp, and this cue steps aside. ")
          // The last stretch of the chain, offered progressively: it only
          // describes what the reader has actually switched on.
          + (true
            ? (couplingDriveValue === null
              ? `${dungeyTransportCopy.noCoupling} `
              : tailReturnRefused
                ? `${dungeyTransportCopy.refused} `
                : tailReturn === null || tailReturn.extendedPathCount === 0
                  ? `${dungeyTransportCopy.notDrawn} `
                  : `${dungeyTransportCopy.transport} `
                    // The reader has been told by mechanism clip 04, without
                    // fine print, that a charged particle cannot cross the
                    // field. The tail leg changes direction, so it owes them
                    // the reason: the field line was re-cut, and the only
                    // cross-field motion drawn is the drift that leans the
                    // approach in. Sean spotted the old right-angle turn on
                    // the live site; this sentence travels with the fix.
                    + `${dungeyTransportCopy.turn} `
                    // What a particle IS decides where it ends up, and how far
                    // that claim actually goes — including the alphas, where a
                    // difference nobody measures is deliberately not drawn.
                    + `${dungeyTransportCopy.species} `
                    // The lifecycle used to stop at the inner edge. These two
                    // are the rest of it: what the trapped particle does, and
                    // the two ways it leaves — plus the two more ways that are
                    // real and are deliberately not drawn, each with its reason.
                    + `${dungeyTransportCopy.trapped} `
                    + `${dungeyTransportCopy.losses} `
                    // Sean asked whether the belts are coupled to the wind
                    // too. They are, indirectly — and there is no flow to
                    // draw, so the answer is given in words where he asked it.
                    + (byId<HTMLInputElement>("layer-radiation").checked
                      ? `${dungeyTransportCopy.radiationBelts} `
                      : "")
                    + (auroralOvalOn
                      ? `${dungeyTransportCopy.aurora} `
                      : "Switch the auroral oval on as well and a share of those electrons stops drifting: it follows the field line down into the atmosphere and lights the oval. ")
                    + `${dungeyTransportCopy.evidence} `
                    + (coupling === null ? "" : `Right now that coupling function reads ${Math.round(coupling).toLocaleString()}${couplingBandLabel ? ` (${couplingBandLabel})` : ""} — ${stormDerived?.newellUnits ?? "unnormalised as published"}, ${stormDerived?.newellCitation ?? "Newell et al. (2007)"}. `))
            : "")
          + (mhdCutOn
            // CORRECTNESS FIX 2026-09-04: there are no beaded tracers. They are
            // built and then hidden at the render gate —
            // `DRAW_PUBLISHED_PLANE_TRACERS = false` in `solar-input-visuals.ts`,
            // against a long note recording Sean rejecting them: "I don't think
            // you should be drawing those green lines at all." This sentence
            // told a reader that the flow they were looking at was the
            // simulation's own answer; every pixel of it is the idealised cue.
            ? "The NOAA MHD cross-section carries the model's own flow as the COLOURS of its two cut planes. Nothing rides those planes as tracers: beads confined to two flat cuts read as arcs hanging in space from every angle but face-on, so they are not drawn. "
            : "")
          // THE MOST TEACHABLE NUMBER IN THIS LAYER, which existed only in an
          // agent's report until now: the magnetosphere's reach is finite and
          // measured, and it is the reason most of the wind sails past.
          // CORRECTNESS FIX 2026-09-04. Two claims in this paragraph were
          // printed as constants and are not.
          //
          // The deflection figures are a snapshot of the flow solve at ONE
          // standoff, and they reproduce only near 7.5 Earth radii — a
          // compressed, storm-time nose. Re-measured on the same solve against
          // the drawn obstacle, the 27–40 Rₑ band runs 2.4% at a 6.5 Rₑ nose,
          // 3.1% at 7.5, 4.9% at 9.5 and 7.1% at 11.5: a bigger magnetosphere
          // reaches further, by up to 2x. The sentence now says which state it
          // is quoting instead of presenting one as all of them.
          //
          // And the field is not HALVED beyond 55 Rₑ. `SOLAR_WIND_FACE_FADE`
          // is `mix(1, 0.5, smoothstep(55, 150, transverse))`, which is exactly
          // 1.00 at 55 and reaches 0.50 only at 150. The file's own comment has
          // this right; the card did not.
          + "HOW FAR THE MAGNETOSPHERE REACHES is measured on this layer's own flow solve, and it is not far. With the nose compressed to about 7.5 Earth radii, a parcel arriving within 13.5 Earth radii of the Sun–Earth line is deflected by more than its own impact parameter, one at 27–40 by 3.6%, and one past 68 by 0.3% — which is a straight line. A quiet, expanded magnetosphere reaches perhaps twice as far; a storm-compressed one rather less. That is why most of the solar wind sails past, and it is why the drawn field FADES TOWARD HALF brightness from about 55 Earth radii off-axis — reaching half at 150 — and fades out entirely at the edge of the emission face: out there every parcel is doing the same undeflected thing, so a thousand of them teach what a hundred teach, and a hard edge would read as the shape of the wind rather than the edge of the drawing. That is opacity only — no count, position, path or species changes with it. "
          + "Motion is flow context, not individual measured-particle trajectories.",
        validAt: driver?.validAt,
        statusState: driver ? "ready" : "no-data",
      };
    }
    if (layer === "photons") {
      const flux = this.currentXrayFlux;
      const blackout = radioBlackoutLevel(flux);
      return {
        layer,
        title: "GOES 0.1–0.8 nm X-ray flux",
        badge: "OBSERVED",
        evidence: "observed",
        scale: flux === null ? undefined : {
          gradient: XRAY_FLUX_GRADIENT_CSS,
          minimum: "A1",
          label: `${goesXrayClass(flux)} · ${flux.toExponential(2)} W m⁻²`,
          maximum: "X10",
        },
        stats: flux === null ? [{ label: "SELECTED UTC", value: "NO X-RAY DATA" }] : [
          { label: "CLASS", value: goesXrayClass(flux) },
          { label: "FLUX", value: `${flux.toExponential(2)} W m⁻²` },
          { label: "RADIO BLACKOUT SCALE", value: blackout.level === 0 ? "R0 · none" : `R${blackout.level} · ${blackout.label.toUpperCase()}` },
        ],
        note: "A single scalar: this flux is uniform to 0.056% from geostationary orbit to the ground, and nothing in near-Earth space attenuates it. The pale inbound rays are photons — light, which left the Sun about eight minutes ago — and they are drawn straight and parallel because they carry no charge: the bow shock, the magnetosheath and the magnetopause do nothing to them at all. Switch the solar wind on beside them and the contrast is the whole lesson: charged particles bending around the boundary, these lancing straight through it. Billiard balls and waves. Each ray ends where its energy does, absorbed high on the dayside — the D-region, 60–90 km up — which is what the tint marks and what the D-region HF absorption layer (D-RAP) draws as the consequence. How many rays and how bright is the measured flux, sparse at A class and a shower at X; how fast they cross is display cadence, not the speed of light. The tint remains the only real spatial structure this scalar has: which hemisphere the Sun is currently over.",
        validAt: flux === null ? undefined : selectedTime,
        statusState: flux === null ? "no-data" : "ready",
      };
    }
    if (layer === "geospace") {
      const field = this.currentGeospaceField;
      const metadata = this.globe.getGeospaceLegendMetadata();
      const runtimeState = this.globe.getGeospaceRuntimeState();
      const fieldMetadata = metadata?.field.field === field ? metadata.field : null;
      return magnetosphereFieldLegendSpec({
        noForecast: this.magnetopauseNoForecast(),
        field,
        fieldMetadata,
        structures: metadata?.structures ?? null,
        runtimeState,
        loading: this.geospaceLoading !== null,
        empiricalAnnotationOn: byId<HTMLInputElement>("annotate-empirical-boundaries").checked,
        extractedAnnotationOn: byId<HTMLInputElement>("annotate-extracted-boundaries").checked,
        // What the boundary pass actually drew, not what the tick asked for.
        empiricalModelsDrawn: this.globe.getMagnetopauseLegend()
          .map((entry) => entry.id)
          .filter((id): id is MagnetopauseModelId => id !== "exteriorCusp"),
        shueNoseRe: driver?.subsolarStandoffRe ?? null,
        frameDescription: runtimeState?.status === "ready"
          ? this.geospaceFrameDescription(runtimeState)
          : runtimeState?.status === "no-data"
            ? `${runtimeState.reason.toUpperCase().replaceAll("-", " ")}`
            : null,
        source: this.geospaceBundle ? `${this.geospaceBundle.source.name} · ${fieldMetadata?.coordinateSystem ?? this.geospaceBundle.coordinateSystem}` : undefined,
        coverage: this.geospaceCoverage(runtimeState),
        formatEndpoint: (value, scale) => this.formatScaleEndpoint(value, scale),
        mhdCutOn: this.globe.mhdCutEnabled,
        fieldLineSummary: this.globe.getFieldLineSummary(),
        fieldLineIntegrity: this.globe.getFieldLineIntegrity(),
        cuspFunnelsDrawn: this.globe.getFieldLineCuspFunnelsDrawn(),
      });
    }
    if (layer === "plasmaSheet") {
      const runtimeState = this.globe.getGeospaceRuntimeState();
      return plasmaSheetLegendSpec({
        metadata: this.globe.getPlasmaSheetLegendMetadata(),
        runtimeState,
        loading: this.geospaceLoading !== null,
        frameDescription: runtimeState?.status === "ready"
          ? this.geospaceFrameDescription(runtimeState)
          : runtimeState?.status === "no-data"
            ? `${runtimeState.reason.toUpperCase().replaceAll("-", " ")}`
            : null,
        source: this.geospaceBundle
          ? `${this.geospaceBundle.source.name} · pressure ÷ magnetic pressure · ${this.geospaceBundle.coordinateSystem}`
          : undefined,
        coverage: this.geospaceCoverage(runtimeState),
        formatEndpoint: (value, scale) => this.formatScaleEndpoint(value, scale),
      });
    }
    const metadata = this.globe.getGeospaceLegendMetadata();
    const runtimeState = this.globe.getGeospaceRuntimeState();
    const radiation = metadata?.radiation ?? null;
    const noData = runtimeState?.status === "no-data";
    const mapped = radiation?.view === "dipoleMapped3d" || this.currentRadiationView === "dipoleMapped3d";
    // The stacked reconstruction and a single bounce shell are different
    // objects on screen, so they are never given the same name.
    const stacked = mapped && radiation?.pitchMode === "all";
    const omnidirectional = mapped && radiation?.pitchMode === "omnidirectional";
    // Until the first frame lands there is no `radiation` metadata, so neither
    // `omnidirectional` nor `stacked` can be true and the name would fall
    // through to the single bounce shell — a view the visitor did not ask for.
    // The shipped default is the omnidirectional volume (geospace-runtime.ts),
    // so that is what a card describing the not-yet-arrived layer must name.
    const awaitingFirstFrame = mapped && radiation === null;
    const title = mapped
      ? omnidirectional || awaitingFirstFrame
        ? "RBE electron belt · omnidirectional mapped volume"
        : stacked ? "RBE electron belt · multi-pitch mapped volume" : "RBE electron belt · mapped bounce shell"
      : "RBE equatorial electron flux";
    const sourceStatus = runtimeState?.status === "ready"
      ? this.geospaceFrameDescription(runtimeState)
      : runtimeState?.status === "no-data"
        ? `${runtimeState.reason.toUpperCase().replaceAll("-", " ")} · HIDDEN`
        : this.geospaceLoading ? "LOADING VERIFIED MODEL" : "LOAD ON DEMAND";
    return {
      layer,
      title,
      badge: noData ? "NO DATA" : mapped ? "MODEL-DERIVED" : radiation ? "MODEL-NATIVE" : this.geospaceLoading ? "LOADING" : "LOAD ON DEMAND",
      evidence: "model",
      // The omnidirectional volume paints colour over the range the drawn
      // field actually occupies, not over the artifact's encoding range, so
      // its key has to quote the same two numbers or the bar would describe
      // eleven decades of colour the picture never uses. Those two numbers are
      // the SAME in every energy view, including the combined one, so the bar
      // a reader learns at 1.35 MeV still means what it said at 88 keV. Every
      // other radiation presentation still keys off the published encoding.
      // A card with no scale renders as SHAPE ONLY, and for the seconds
      // between switching the layer on and its first frame arriving that is
      // what a visitor saw — the one presentation this project set out to
      // retire, on the layer Sean most wanted to trust. The volume's two
      // endpoints are display constants, identical in every energy view and
      // independent of which dataset is loading, so the ramp can be drawn
      // before the data lands. Only the units are unknown that early, so the
      // label names the quantity instead of quoting an encoding nobody has
      // read yet. Same fix, same reasoning, as the ground-field card.
      scale: radiation === null ? (awaitingFirstFrame ? {
        gradient: RADIATION_VOLUME_GRADIENT_CSS,
        minimum: this.formatScaleEndpoint(RADIATION_VOLUME_TRANSFER.colourFloorLog10Flux, "log10"),
        label: "LOG₁₀ · DIFFERENTIAL ELECTRON FLUX",
        maximum: this.formatScaleEndpoint(RADIATION_VOLUME_TRANSFER.colourCeilingLog10Flux, "log10"),
      } : undefined) : omnidirectional ? {
        gradient: RADIATION_VOLUME_GRADIENT_CSS,
        minimum: this.formatScaleEndpoint(RADIATION_VOLUME_TRANSFER.colourFloorLog10Flux, "log10"),
        label: `LOG₁₀ · ${radiation.range.units}`,
        maximum: this.formatScaleEndpoint(RADIATION_VOLUME_TRANSFER.colourCeilingLog10Flux, "log10"),
      } : {
        gradient: "linear-gradient(90deg, #201a3b, #a98cff, #f5c96a)",
        minimum: this.formatScaleEndpoint(radiation.range.encodedMinimum, radiation.range.scale),
        label: `${radiation.range.scale === "log10" ? "LOG₁₀" : "LINEAR"} · ${radiation.range.units}`,
        maximum: this.formatScaleEndpoint(radiation.range.encodedMaximum, radiation.range.scale),
      },
      stats: radiation ? noData ? [
        { label: "SELECTED UTC", value: sourceStatus },
      ] : [
        { label: "ENERGY", value: radiation.energyLabel ?? this.formatRadiationEnergy(radiation.energyKev) },
        // The floor is re-derived from every dataset as it loads, so this row
        // is a live number and it says which dataset it came from. When the
        // derivation cannot read a frame the shipped fallback is used and the
        // row leads with that, because a floor nobody measured on the data in
        // front of you is a different claim from one that was.
        ...(omnidirectional && radiation.opacityFloorLog10Flux !== null ? [{
          label: "DRAWN ABOVE",
          value: `10^${radiation.opacityFloorLog10Flux.toFixed(2)} ${radiation.range.units} · ${
            radiation.opacityFloorSource === "shipped-fallback-table"
              ? "SHIPPED FALLBACK, NOT DERIVED FROM THIS DATASET"
              : radiation.opacityFloorSource === "explicit-override"
                ? "SET EXPLICITLY, NOT DERIVED FROM THIS DATASET"
                : "DERIVED FROM THIS DATASET AS IT LOADED"} — `
            + `${radiation.opacityFloorReason}. COLOUR SCALE IS THE SAME 10^${
              RADIATION_VOLUME_TRANSFER.colourFloorLog10Flux} TO 10^${
              RADIATION_VOLUME_TRANSFER.colourCeilingLog10Flux} RAMP IN EVERY ENERGY VIEW`,
        }] : []),
        { label: "PITCH", value: omnidirectional
          ? `OMNIDIRECTIONAL · ${radiation.displayedPitchChannelCount} OF ${radiation.sourcePitchChannelCount} PUBLISHED CHANNELS INTEGRATED OVER THE TRAPPED SOLID ANGLE`
          : stacked
            ? `ALL ${radiation.displayedPitchChannelCount}/${radiation.sourcePitchChannelCount} PUBLISHED · ${radiation.pitchAngleDegrees.toFixed(1)}° EMPHASIZED`
            : mapped
              ? `sin(α) ${radiation.pitchCoordinateSin.toFixed(5)} · ${radiation.pitchAngleDegrees.toFixed(1)}° · 1 OF ${radiation.sourcePitchChannelCount} PUBLISHED CHANNELS`
              : `sin(α) ${radiation.pitchCoordinateSin.toFixed(5)} · ${radiation.pitchAngleDegrees.toFixed(1)}°` },
        { label: "POPULATION", value: radiation.particlePopulation },
        { label: "PRESENTATION", value: mapped ? "GYROTROPIC IDEAL-DIPOLE MAPPING" : "MODEL-NATIVE EQUATORIAL" },
      ] : [{ label: "MODEL", value: this.geospaceLoading ? "LOADING" : "LOAD FOR SCALE" }],
      note: radiation
        ? `${radiation.viewStatus}. ${radiation.representation} ${radiation.sourceCoverage}; ${radiation.alongFieldInterpretation}. ${radiation.range.endpointMeaning}`
          + (omnidirectional
            ? ` The colour bar above runs over 10^${RADIATION_VOLUME_TRANSFER.colourFloorLog10Flux} to 10^${RADIATION_VOLUME_TRANSFER.colourCeilingLog10Flux} of that scale — the union of what all four published channels occupy — and it is the SAME bar in every energy view, so a given flux is the same colour at 88 keV as it is at 2.32 MeV and the channels can be compared by eye. Opacity is tuned per energy and only opacity: this view draws nothing below 10^${(radiation.opacityFloorLog10Flux ?? RADIATION_VOLUME_TRANSFER.colourFloorLog10Flux).toFixed(2)}, because ${radiation.opacityFloorReason ?? "the layer's declared display floor is 10^1"}. That floor is not a fixed setting: every dataset and every frame is measured as it loads, and the floor is that view's own deepest inter-belt minimum rounded down to the next 0.05 decade, never below the declared 10^1 — so the floor can only ever remove the skirt below the belt system, and the dark band between the belts is the model's own. Above that floor opacity stays proportional to flux, so more flux is always more opaque, and no per-energy setting can change what colour a number is.`
              + (radiation.combinedEnergyView
                ? ` "All energies (combined)" is not a sum of the four channels — differential fluxes on a logarithmically spaced energy grid cannot be added. It is the trapezoidal integral over the published 88 keV to 2.32 MeV band, weighted by energy and divided by the band's width, so it carries the same units as a single channel and asks where the radiation ENERGY is rather than where the particle count is. The plain number-flux integral was built and measured too; it is dominated by the 88 keV electrons, which are the population that fills the slot.`
                : "")
            : "")
        : "The layer opens on omnidirectional differential electron flux with all four published energies drawn at once — every locally trapped pitch channel integrated over solid angle into one volume, the same quantity AE9/AP9 and the GOES and Van Allen Probes particle products report, folded across 88 keV to 2.32 MeV by an energy-weighted band integral. That is the view in which the two belts and the slot between them are there before you touch anything. Every single energy, every individual pitch channel, the stacked reconstruction of all of them, and the model-native equatorial flux surface are all one click away, on the same colour scale, and the legend always names what is drawn. The 3-D placement is a clearly labeled ideal-dipole mapping, never native 3-D output.",
      validAt: runtimeState?.status === "ready" ? radiation?.validAt ?? runtimeState.structureFrameValidAt : undefined,
      source: this.geospaceBundle ? `${this.geospaceBundle.model} radiation-belt environment` : undefined,
      coverage: this.geospaceCoverage(runtimeState),
      statusText: noData
        ? `NO DATA FOR SELECTED UTC · ${sourceStatus}. Radiation-belt geometry is HIDDEN; no stale flux frame is held.`
        : runtimeState?.status === "ready" ? `${radiation?.viewLabel ?? (mapped ? "OMNIDIRECTIONAL DIPOLE-MAPPED ELECTRON VOLUME" : "MODEL-NATIVE EQUATORIAL FLUX")} · ${sourceStatus}` : undefined,
      statusState: noData ? "no-data" : radiation ? "ready" : "loading",
    };
  }

  /**
   * The rail control for each layer that HAS one.
   *
   * Partial on purpose. A legend identity is not the same thing as a rail
   * layer: `plasmasphere` still has a legend spec, still tested, but its grain
   * cloud left the rail on 2026-08-18 and its boundary moved to the Current
   * conditions page. Everything that walks this map skips identities with no
   * control rather than reaching for an element that is not there.
   */
  private static readonly layerCheckboxIds: Partial<Record<LayerName, string>> = {
    ionosphere: "layer-ionosphere",
    tec: "layer-tec",
    drap: "layer-drap",
    aurora: "layer-aurora",
    regions: "layer-regions",
    magnetosphere: "annotate-empirical-boundaries",
    ringCurrent: "layer-ring-current",
    geospace: "layer-geospace",
    solarWind: "layer-solar-wind",
    photons: "layer-photons",
    radiation: "layer-radiation",
    groundStations: "layer-ground-stations",
    groundField: "layer-groundField",
    thermosphere: "layer-thermosphere",
  };

  /**
   * The layers that get a key card and a data-viewer card. `magnetosphere`
   * is deliberately absent: as an annotation of the plasma-field layer it has
   * no card of its own — its numbers ride on the field layer's card — and a
   * card here would be a scale-less "SHAPE ONLY" row, which is exactly the
   * presentation this family retired.
   */
  private static readonly layerOrder: LayerName[] = [
    "thermosphere", "ionosphere", "tec", "drap", "groundField", "aurora", "geospace", "plasmaSheet", "ringCurrent", "solarWind", "photons", "radiation", "regions", "groundStations",
  ];

  private activeLayers(): LayerName[] {
    return ExplorerApp.layerOrder.filter((layer) => {
      const id = ExplorerApp.layerCheckboxIds[layer];
      return id !== undefined && byId<HTMLInputElement>(id).checked;
    });
  }

  /**
   * Three surfaces, three jobs, and no value with two homes.
   *
   * The rail is a control surface: a layer's toggle, its own settings, and the
   * note explaining what those settings do. The legend over the globe carries
   * one colour ramp per drawn layer with the units it is measured in, and
   * nothing else — it has to stay small however many layers are on. Everything
   * else the data says (the derived heights, the validity, the mode, where it
   * came from) is in the data viewer, which is off until it is asked for.
   *
   * Before this, the key carried all three of those and the rail carried the
   * prose half of the third, so the same layer was explained twice on screen
   * and neither place was small.
   */
  private updateEnvironmentLegend() {
    const active = this.activeLayers();
    if (!this.environmentLegendFocus || !active.includes(this.environmentLegendFocus)) this.environmentLegendFocus = active[0] ?? null;

    document.querySelectorAll<HTMLElement>("[data-layer-panel]").forEach((panel) => {
      panel.classList.toggle("is-visible", active.includes(panel.dataset.layerPanel as LayerName));
    });
    const specs = active.map((layer) => ({ layer, spec: this.environmentLegendSpec(layer) }));
    this.updateMapKey(specs);
    // After the key cards, because a rebuild replaces the node this hands over.
    this.syncRingCurrentPulse();
    this.updateDataViewer(specs);
    // Last, and here rather than on the checkbox, because this is the one call
    // every asynchronous artifact loader makes when its bundle finally lands.
    this.landOnCoverage(specs);
    // The CLOCK can empty a layer with no control being touched, so the scale
    // note is recomposed on every rebuild. After the landing, not before: a
    // landing moves the clock, and the note describes what is drawn at the
    // instant the reader ends up on. `tests/panel-readout-split.test.ts` reads
    // the first 900 characters of this method looking for `landOnCoverage`, so
    // nothing may be inserted above it either.
    this.updateScaleNote();
  }

  /**
   * The ring current's colour bar, and the one line under it saying how long
   * its pulse is.
   *
   * Sean asked for exactly this, in these words: "If the periodicity is exact,
   * that is awesome. Just have some note about it in the layer. Have the same
   * color scale pulsing at the rate shown and put a very short text saying
   * pulse period is X."
   *
   * The rate is not typed anywhere. The bar is handed to the globe, which
   * writes its `--legend-pulse` from the SAME `environmentalAnimationElapsedSeconds`
   * it hands the volume, on the same frame — so the swatch cannot pulse at a
   * rate the ring does not, which is the one way this could have made the
   * false periodicity it exists to cure. It also freezes with the volume when
   * environmental motion is off, which is what `prefers-reduced-motion` turns
   * off by default, and the line of text still says what the rhythm was.
   *
   * Re-run after every key-card rebuild because a rebuild replaces the node.
   * The note is written here rather than in the spec so that this layer can
   * answer its own question without the shared legend renderer growing a field
   * that only one layer would ever set.
   */
  private syncRingCurrentPulse() {
    const card = document.querySelector<HTMLElement>('#key-cards .key-card[data-layer="ringCurrent"]');
    const bar = card?.querySelector<HTMLElement>(".key-card-scale") ?? null;
    const line = ringCurrentPulseLine(this.globe.getRingCurrentFormation(), this.globe.getRingCurrentState());
    // A card that is struck out has no ramp to breathe and no period to print.
    const pulsing = bar !== null && !bar.classList.contains("key-card-scale--empty") && line !== null;
    this.globe.setRingCurrentPulseSurface(pulsing ? bar : null);
    const existing = card?.querySelector<HTMLElement>(".key-card-pulse") ?? null;
    if (!pulsing || !card) {
      existing?.remove();
      return;
    }
    const note = existing ?? document.createElement("p");
    if (!existing) {
      note.className = "key-card-pulse";
      card.querySelector(".key-card-values")!.after(note);
    }
    if (note.textContent !== line) note.textContent = line;
  }

  /** This layer's control panel, wherever it currently is. */
  private layerControlPanel(layer: LayerName): HTMLElement | null {
    return document.querySelector<HTMLElement>(`[data-layer-panel="${layer}"]`);
  }

  /**
   * Remembered per layer. With no remembered choice, detail opens only when
   * this is the single layer on screen; from the second layer onward it starts
   * folded, because that is the point at which the column starts to crowd.
   */
  private layerDetailOpen(layer: LayerName): boolean {
    return layerDetailIsOpen(this.layerDetailState.get(layer));
  }

  private setLayerDetailOpen(layer: LayerName, open: boolean) {
    this.layerDetailState.set(layer, open);
    storageSet("local", "space-explorer-layer-detail-v1", JSON.stringify(Object.fromEntries(this.layerDetailState)));
  }

  /**
   * The polar-cusp annotation, as the reader last left it.
   *
   * Absent or unreadable storage means OFF, which is the shipped default: this
   * reads a stored "1" rather than testing for a stored "0", so a browser with
   * storage disabled gets the default picture rather than a surprise.
   */
  private restoreCuspAnnotation() {
    const on = storageGet("local", CUSP_ANNOTATION_STORAGE_KEY) === "1";
    byId<HTMLInputElement>("annotate-polar-cusps").checked = on;
    this.globe.setCuspFunnelsEnabled(on);
  }

  private restoreLayerDetailState() {
    const saved = storageGet("local", "space-explorer-layer-detail-v1");
    if (!saved) return;
    try {
      const parsed = JSON.parse(saved) as Record<string, unknown>;
      Object.entries(parsed).forEach(([layer, open]) => {
        if (typeof open === "boolean" && layer in ExplorerApp.layerCheckboxIds) {
          this.layerDetailState.set(layer as LayerName, open);
        }
      });
    } catch {
      /* A corrupt preference must never stop the explorer from starting. */
    }
  }

  /**
   * The legend in the lower-right corner: one compact ramp per drawn layer,
   * each with its units, and nothing else. It grows only with the layers
   * actually drawn and it can be folded to its title bar — it sits over the
   * globe, and burying the Earth is the complaint this redesign answers.
   */
  private updateMapKey(specs: Array<{ layer: LayerName; spec: EnvironmentLegendSpec }>) {
    const key = byId("map-key");
    key.hidden = specs.length === 0;
    byId("map-key-count").textContent = specs.length === 0
      ? "NO LAYERS"
      : `${specs.length} ${specs.length === 1 ? "LAYER" : "LAYERS"}`;
    // The same number on the rail's Space weather summary row, written from
    // the same array, so a folded section and the key over the globe cannot
    // disagree about how many layers are drawn.
    const railCount = document.getElementById("active-layer-count");
    if (railCount) railCount.textContent = `${specs.length} on`;
    key.classList.toggle("is-collapsed", this.mapKeyCollapsed);
    // Rebuild the cards only when their CONTENT changed.
    //
    // This ran on every environment update — measured at 4.3 DOM replacements
    // per second — and a card that is replaced every ~230 ms cannot be clicked
    // reliably: a pointer press and release land on two different nodes, so no
    // click event is produced at all. That silently broke the "Go to
    // <time> UTC" button every no-data card offers, which is the one control a
    // visitor needs at exactly the moment the layer has nothing to show. The
    // handler was always correct; it just never received the event.
    //
    // The signature is the rendered content, not object identity, because the
    // specs are rebuilt fresh each pass and would never compare equal.
    //
    // THE LANDING NOTE IS NO LONGER IN HERE, because it is no longer drawn on
    // these cards: it moved to the layer's own card on 2026-08-27. It was
    // listed here for a real reason — it is rendered content that is in no
    // spec, and a signature of specs alone is identical either side of a
    // landing, so leaving it out meant it was never drawn at all: measured on
    // the built bundle, the aurora card came back with its 0-100% ramp and
    // said nothing whatever about the two-and-a-half-hour jump the reader had
    // just been given. That failure mode cannot follow it to its new home.
    // `fillLayerCard` REFILLS every layer card on every environment update —
    // cards there are kept and refilled, never rebuilt — so nothing on that
    // surface waits on a signature to be told its content changed.
    //
    // The no-data notice IS still in the signature, and for the reason the
    // landing note used to be: it is rendered content that is in no spec. It is written from
    // the SELECTED INSTANT — which minute the reader is on, which edge of the
    // window they went past, and where the "Go to" button should send them —
    // and the spec either side of a move through the gap is identical, so
    // without it the card freezes on the first gap message it ever drew.
    // Measured on the built bundle with the thermosphere: scrubbed from
    // 06:00Z, sixteen hours before the release, to 2026-08-21 12:00Z, a day and
    // a half after it, the legend card still read "only goes back to
    // 2026-08-19 20:00 UTC" and still offered a jump to the START of the
    // window, while the Data Explorer beside it — which refills rather than
    // rebuilds — correctly read "stops at 2026-08-20 07:50 UTC".
    //
    // This adds a rebuild once a minute while a layer is out of coverage,
    // against the 4.3 per second that broke the button, so the click the note
    // above protects is not put back at risk.
    const signature = JSON.stringify([
      specs.map(({ layer, spec }) => [layer, spec, this.layerUnavailable(layer, spec)]),
    ]);
    if (signature !== this.renderedKeyCardSignature) {
      this.renderedKeyCardSignature = signature;
      byId("key-cards").replaceChildren(...specs.map(({ layer, spec }) => this.renderKeyCard(layer, spec)));
    }
    this.announceOccluderChange();
  }

  /**
   * The space weather layers panel: present whenever at least one layer is drawn and
   * absent otherwise — "you have to have it visible if you plot data" — with
   * one card per active layer plus the measured drivers at the top. It opens
   * collapsed to its one-line head unless the visitor has left it expanded
   * before. It is the satellite card's shape on purpose — Sean named that
   * card as the model, because it opens with a sentence and lets the reader
   * dig from there.
   */
  private updateDataViewer(specs: Array<{ layer: LayerName; spec: EnvironmentLegendSpec }>) {
    const viewer = byId("data-viewer");
    const active = specs.length > 0;
    // "Conditions right now" is not in here any more. Sean, on opening the
    // panel: "Why does it start with 'measured drivers'? What the fuck is
    // that?" It was scene-wide material at the top of a panel that answers
    // "what do the layers I switched on say?". What is left is one rectangle
    // per layer and nothing above them.
    //
    // Where it went: the control rail, under SPACE WEATHER. It spent a while
    // in the rail in all three modes, on the theory that conditions are true
    // of the scene rather than of a mode. Sean's ruling on 2026-08-21 is that
    // they are not wanted in Satellites mode, so the section carries
    // `data-mode-panel="environment"` like the layer list does — Space weather
    // and Combined show it, Satellites does not.
    // GONE ON A PHONE, not merely empty. Sean, 2026-08-28: "only on mobile...
    // no more layer info window inside the viewing area. i want it on the panel
    // under the layer." The cards move into the space weather panel below, so
    // what would be left over the globe is a title bar counting layers the
    // reader can already see listed in the panel — and it would still be taking
    // the top of the scene. The `hidden` attribute rather than a display rule,
    // so it leaves the accessibility tree with the layout.
    const phone = this.phoneChromeQuery.matches;
    viewer.hidden = !active || phone;
    viewer.classList.toggle("is-collapsed", this.explorerCollapsed);
    byId("data-viewer-head").setAttribute("aria-expanded", String(!this.explorerCollapsed));
    // "1 Space Weather Layer" / "3 Space Weather Layers". Sean, 2026-08-21:
    // "Don't call it Data Explorer. That is cheesy. Just say '# Space Weather
    // Layers' and the X on the other side." The number used to be printed in a
    // chip beside a "DATA EXPLORER" kicker, which said it twice; there is one
    // line now, in the same "# Satellite(s) Selected" shape the satellite
    // stack's head opposite already uses. The singular is not cosmetic — one
    // layer is the commonest state this panel is ever in.
    byId("data-viewer-title").textContent = `${specs.length} Space Weather ${specs.length === 1 ? "Layer" : "Layers"}`;
    // ...and WHICH layers, on the line beneath it.
    //
    // Sean, 2026-08-26: "when we add a layer the layer browser window starts
    // collapsed. The window should at least start showing the collapsed layer
    // - the name of the layer - so that people can see what is being shown."
    // A count with no subject is what a folded panel used to be: something is
    // plotting, and the only way to learn what was to unfold it.
    //
    // The names are the card titles, so the folded head and the opened card
    // say the same words about the same layer. The stylesheet draws this line
    // only while the panel is folded and ellipses it against the same slot as
    // the count; an ellipsis hides no layer's EXISTENCE, because the count is
    // on the line directly above, and the full list is on the head's title and
    // in the aside's aria-label for anyone — pointer or screen reader — who
    // wants it without unfolding.
    const layerNames = specs.map((entry) => entry.spec.title);
    const layerLine = byId("data-viewer-layers");
    layerLine.textContent = layerNames.join(" · ");
    layerLine.hidden = layerNames.length === 0;
    const head = byId("data-viewer-head");
    head.title = layerNames.length
      ? `${layerNames.join(" · ")}\nDrag to move. Click to expand or collapse.`
      : "Drag to move. Click to expand or collapse.";
    // The aria-label was a fixed sentence, so a screen-reader user got the
    // same "readings for every layer switched on" whether one layer was on or
    // eight. It names them now, for the same reason the line above does.
    viewer.setAttribute(
      "aria-label",
      layerNames.length
        ? `Space weather layers: readings for ${layerNames.join(", ")}`
        : "Space weather layers: readings for every layer switched on",
    );
    this.updateMeasuredDriversDedupe(specs.map((entry) => entry.layer));
    // Cards are kept and refilled, never rebuilt, exactly as the satellite
    // stack keeps its cards. Rebuilding looked fine in a screenshot and was
    // unusable in the hand: updateEnvironmentLegend runs on every driver
    // update, so a freshly built <details> was detached from under the pointer
    // before a click on it could land. Found by driving the real page.
    if (active) {
      const host = byId("data-viewer-cards");
      const panelHost = byId("layer-control-panels");
      for (const [layer, card] of this.layerCards) {
        if (!specs.some((entry) => entry.layer === layer)) {
          // Hand the layer's controls back before the card goes. They are the
          // document's only copy and main.ts holds listeners on them, so
          // dropping them with the card would take the bindings with them.
          const panel = card.querySelector<HTMLElement>("[data-layer-panel]");
          if (panel) panelHost.append(panel);
          card.remove();
          this.layerCards.delete(layer);
        }
      }
      // No "focused" card any more, and no bookkeeping to decide which one it
      // would be: every card opens shut, so they are peers. See
      // `layerCardIsOpen`.
      specs.forEach(({ layer, spec }) => this.fillLayerCard(this.layerCard(layer), layer, spec));
      const order = specs.map(({ layer }) => layer).join(",");
      if (phone) {
        this.placeLayerCardsInRail(specs.map(({ layer }) => layer));
        this.layerCardOrder = "";
      } else {
        this.clearRailLayerCards();
        if (order !== this.layerCardOrder) {
          host.replaceChildren(...specs.map(({ layer }) => this.layerCard(layer)));
          this.layerCardOrder = order;
        }
      }
      this.applyExplorerPosition();
      this.applyExplorerSize();
    } else if (phone) {
      this.placeLayerCardsInRail([]);
    }
  }

  /**
   * Hides a "Measured drivers" row in the header card for exactly as long as
   * a switched-on layer's own data-viewer card already carries that number in
   * more detail — solar wind speed and IMF Bz against the solar-wind layer,
   * GOES X-ray class against the photon layer, F2 peak against the ionosphere
   * layer. `dataViewerSections` is where a layer's OWN readings are built;
   * this is the header card's half of the same "no value with two homes"
   * rule, applied against layers rather than within one.
   *
   * Then finds the true last VISIBLE row and marks it, because `nth-child`
   * cannot see which earlier siblings are `[hidden]` and would otherwise
   * misjudge whether the grid's final row is the odd one needing to span.
   */
  private updateMeasuredDriversDedupe(active: readonly LayerName[]) {
    const rows = [...document.querySelectorAll<HTMLElement>("#weather-readout [data-drivers-dedupe]")];
    rows.forEach((row) => { row.hidden = active.includes(row.dataset.driversDedupe as LayerName); });
    const visible = [...document.querySelectorAll<HTMLElement>("#weather-readout > article")].filter((row) => !row.hidden);
    visible.forEach((row, index) => {
      row.classList.toggle("is-last-odd", index === visible.length - 1 && visible.length % 2 === 1);
    });
  }

  /**
   * What is missing, why, and what to do about it — in one place, in English.
   *
   * The time slider spans -48 h to +72 h because orbits are computable across
   * all of it. Each measured or modelled field has its own, much narrower,
   * published window. Outside that window the site correctly refuses to draw
   * anything; it used to say so up to five times per layer, in words like
   * "BEFORE COVERAGE · HIDDEN", and never said how to get back to data.
   */
  private layerUnavailable(layer: LayerName, spec: EnvironmentLegendSpec): LayerUnavailableNotice | null {
    if (spec.statusState !== "no-data" && spec.statusState !== "stale") return null;
    // A layer that knows exactly why it is empty says so in its own words.
    if (spec.unavailable) return spec.unavailable;
    // The ring current has no artifact of its own — it is drift traced in the
    // DGCPM plasmasphere frames — so its emptiness is always about THOSE, and
    // `dgcpmCoverageNotice` can tell a scrub into the future from a late feed
    // where the generic sentence cannot.
    if (layer === "ringCurrent" && this.plasmasphereSequence) {
      const notice = dgcpmCoverageNotice({
        title: spec.title,
        selectedAtMs: this.simulationTime().getTime(),
        nowMs: Date.now(),
        frameTimesMs: this.plasmasphereSequence.times,
        cadenceMinutes: this.plasmasphereSequence.cadenceMinutes,
      });
      if (notice) return notice;
    }
    return layerCoverageNotice({
      title: spec.title,
      selectedAtIso: this.simulationTime().toISOString(),
      window: this.layerCoverageWindow(layer),
    });
  }

  /**
   * Is the selected instant past the end of the measured solar-wind record?
   *
   * Read straight from `this.weather` and the clock rather than from anything
   * the globe holds, because the globe no longer holds anything for the future
   * — the answer is "draw nothing", and a renderer is the wrong place to keep
   * a fact whose whole content is that there is nothing to render.
   */
  private magnetopauseNoForecast(): MagnetopauseNoForecast | null {
    return magnetopauseNoForecastAt(
      this.weather.magnetopause?.driverSeries ?? [],
      this.weather.outlook?.kpForecast?.rows ?? [],
      this.simulationTime().getTime(),
    );
  }

  /**
   * The published window for one layer, in the layer's own terms. These differ
   * by a factor of thirty: WAM-IPE carries two days of history and a day and a
   * half of forecast, while the coupled geospace run covers under two hours.
   */
  /**
   * The nowcast state of the plasmasphere frame currently on screen, or null
   * when the field is not a held newest frame.
   *
   * Read off the globe's own field rather than recomputed, for the reason the
   * ring current's formation is read off the drawn object: a second evaluation
   * could answer for a different frame than the one being drawn.
   */
  private dgcpmNowcastState(): DgcpmNowcast | null {
    const field = this.globe.getPlasmasphereField();
    return field?.source === "dgcpm" ? field.nowcast : null;
  }

  private layerCoverageWindow(layer: LayerName): { validFrom: string; validTo: string; sourceLabel: string } | null {
    const fromRecord = (record: { validFrom?: string; validTo?: string } | undefined, sourceLabel: string) =>
      record?.validFrom && record?.validTo ? { validFrom: record.validFrom, validTo: record.validTo, sourceLabel } : null;
    if (layer === "aurora") return fromRecord(this.manifest.aurora, "NOAA's published OVATION history");
    if (layer === "drap") return fromRecord(this.manifest.drap, "NOAA's published D-RAP history");
    if (layer === "groundField") return fromRecord(this.manifest.groundField, "NOAA's published ground-perturbation window");
    // The window a reader can be jumped BACK INTO is now the empirical one,
    // not WAM's. It is the wider of the two by a factor of ten and it is the
    // one that decides whether anything can be drawn at all; offering to jump
    // to WAM's twelve hours from an hour NRLMSIS covers perfectly well would
    // send the reader away from a field that is on screen.
    if (layer === "thermosphere") {
      return fromRecord(this.manifest.thermosphereEmpirical, "The NRLMSIS field this release publishes, driven by NOAA's Kp and F10.7")
        ?? fromRecord(this.manifest.thermosphere, "The NOAA WAM neutral-density run in this release");
    }
    if (layer === "geospace" || layer === "radiation" || layer === "plasmaSheet") return fromRecord(this.manifest.geospace, "The coupled NOAA geospace run");
    // The ring current rides the plasmasphere simulation's convection field, so
    // the window it can answer for is that artifact's window rather than a
    // second, independently stated one that could drift away from it.
    if (layer === "ringCurrent") {
      // FROM THE FRAMES IN HAND, NOT FROM THE MANIFEST. Those two diverge, and
      // the divergence is what the owner photographed. The manifest is
      // re-fetched every five minutes; the DGCPM bundle was fetched once and
      // never again, so a tab open across a publish had a manifest saying the
      // frames reached 14:00 UTC and a decoded sequence that stopped at 12:00.
      // The legend then refused to draw AND quoted a frame that existed —
      // words and picture disagreeing about the same layer. The bundle is now
      // hot-swapped like every other artifact (see `hotSwapArtifact`), and this
      // window is read from the sequence so the two cannot drift again.
      const times = this.plasmasphereSequence?.times ?? [];
      const first = times[0];
      const newest = times[times.length - 1];
      if (first === undefined || newest === undefined) {
        return fromRecord(this.manifest.plasmasphere, "This release's DGCPM plasmasphere frames, which supply the convection field");
      }
      const holdMs = (this.plasmasphereSequence?.cadenceMinutes ?? 120) * 60_000 * DGCPM_NOWCAST_HOLD_CADENCES;
      return {
        validFrom: new Date(first).toISOString(),
        // The DRAWABLE edge, which is one publishing cycle past the newest
        // frame — the layer really can answer for that stretch, and a landing
        // that stopped at the frame time would step the reader further back
        // than it needs to.
        validTo: new Date(newest + holdMs).toISOString(),
        sourceLabel: "This release's DGCPM plasmasphere frames, which supply the convection field",
      };
    }
    if (layer === "plasmasphere") {
      const series = this.weather.storm?.dst.kyoto.series ?? [];
      const first = series[0]?.at;
      const last = series[series.length - 1]?.at;
      return first && last ? { validFrom: first, validTo: last, sourceLabel: "The Kyoto quicklook Dst record in this release" } : null;
    }
    if (layer === "magnetosphere" || layer === "solarWind") {
      const series = this.weather.magnetopause.driverSeries ?? [];
      const first = series[0]?.validAt;
      const last = series[series.length - 1]?.validAt;
      return first && last ? { validFrom: first, validTo: last, sourceLabel: "NOAA's propagated solar-wind record" } : null;
    }
    if (layer === "photons") {
      const series = this.weather.xray.series ?? [];
      const first = series[0]?.time;
      const last = series[series.length - 1]?.time;
      return first && last ? { validFrom: first, validTo: last, sourceLabel: "The GOES X-ray record in this release" } : null;
    }
    return null;
  }

  /**
   * One legend row, and every row is the same three things: the layer's name,
   * a bar, and the units under it with the two endpoints either side.
   *
   * Sean asked for "just the color bar or whatever, the name, and the units —
   * compact", and for it to look the same for everything that can appear here.
   * So the three states a layer can be in do not get three different shapes:
   * a measured layer shows its ramp and its endpoints; a shape-only layer such
   * as the magnetopause shows a flat bar in its own colour and says so where
   * the units go; a layer with no data for the selected time shows a struck-out
   * bar and says that. The reasoning behind any of it is in the data viewer.
   *
   * The one thing that is not a readout stays: the button that moves the clock
   * to a time the layer does cover. It is an action, it is the only way out of
   * an empty layer, and folding it into a window that is off by default would
   * strand the reader. It only ever appears in the no-data state.
   */
  private renderKeyCard(layer: LayerName, spec: EnvironmentLegendSpec): HTMLElement {
    const card = document.createElement("article");
    card.className = "key-card";
    card.dataset.layer = layer;

    const heading = document.createElement("div");
    heading.className = "key-card-title";
    const title = document.createElement("strong");
    title.textContent = spec.keyTitle ?? spec.title;
    heading.append(title);
    card.append(heading);

    const scale = document.createElement("div");
    scale.className = "key-card-scale";
    const values = document.createElement("div");
    values.className = "key-card-values";

    const unavailable = this.layerUnavailable(layer, spec);
    const bar = keyCardBar(spec, unavailable !== null);
    const endpoints = bar.endpoints;
    if (bar.kind === "composition") {
      // No bar, no endpoint row: the rows below ARE the legend. See
      // `EnvironmentLegendSpec.composition`.
      const list = document.createElement("ul");
      list.className = "key-card-composition";
      for (const row of spec.composition!.rows) {
        const item = document.createElement("li");
        item.className = "legend-mark";
        const dot = document.createElement("i");
        dot.style.setProperty("--legend", row.swatch);
        const name = document.createElement("strong");
        name.textContent = row.name;
        const detail = document.createElement("em");
        detail.className = "composition-detail";
        detail.textContent = row.detail;
        item.append(dot, name, detail);
        if (row.note) {
          const note = document.createElement("small");
          note.textContent = row.note;
          item.append(note);
        }
        list.append(item);
      }
      const caption = document.createElement("p");
      caption.className = "key-card-composition-caption";
      caption.textContent = spec.composition!.caption;
      card.append(list, caption);
    } else if (bar.kind === "no-data") {
      card.classList.add("is-unavailable");
      scale.classList.add("key-card-scale--empty");
      // The full sentence is a hover away and printed in the data viewer's
      // "Validity and coverage"; the legend has room for neither.
      card.title = `${unavailable!.headline} ${unavailable!.because}`;
    } else if (bar.kind === "ramp") {
      scale.style.setProperty("--legend-scale", spec.scale!.gradient);
    } else {
      // Flat, in the layer's own colour — which the stylesheet keys off the
      // card's data-layer, so the bar and the dot beside that layer's checkbox
      // in the rail are the same colour without a second copy of the palette.
      scale.classList.add("key-card-scale--flat");
    }
    // A ramp's cells are bare text. A COMPOSITION's cells each name a thing
    // that is drawn in a colour, so each carries that colour beside it. See
    // `scale.cellSwatches`; only the solar wind's species row sets it.
    const cellSwatches = bar.kind === "ramp" ? spec.scale?.cellSwatches : undefined;
    endpoints.forEach((value, index) => {
      const cell = document.createElement("span");
      const swatch = cellSwatches?.[index];
      if (swatch) {
        cell.classList.add("is-keyed");
        const dot = document.createElement("i");
        dot.style.setProperty("--legend", swatch);
        cell.append(dot);
      }
      cell.append(document.createTextNode(value));
      values.append(cell);
    });
    if (bar.kind !== "composition") card.append(scale, values);

    // ...and every drawn thing that is NOT on that bar. See `marks`.
    //
    // The legend's own note in index.html says "one compact ramp per drawn
    // layer with the units it is measured in", and that is still what this
    // card is. These rows are not a second reading: they are the rest of the
    // answer to the question the ramp is here to answer, for the parts of the
    // picture a ramp cannot reach. A layer with nothing off-ramp draws none.
    if (spec.marks?.length && bar.kind !== "no-data") {
      const list = document.createElement("ul");
      list.className = "key-card-marks";
      list.append(...spec.marks.map((mark) => legendMarkRow(mark)));
      card.append(list);
    }

    // WHY there is nothing, not just that there is nothing.
    //
    // The card used to print "NO DATA AT THIS TIME" and a jump button and stop
    // there, and Sean read exactly what anyone would read: that the site was
    // broken. It was not — on the day he asked, NOAA's own OVATION feed had
    // published nothing for 2.09 hours, and our newest frame WAS their newest
    // frame. A blank layer with no reason attached makes an upstream gap look
    // like our fault, and it teaches nothing; the same gap with its reason
    // attached teaches that these are real feeds that really stall.
    //
    // The sentence was already being composed and then thrown away.
    if (unavailable?.because) {
      const why = document.createElement("p");
      why.className = "key-card-why";
      why.textContent = unavailable.because;
      card.append(why);
    } else if (spec.conditionLine) {
      // ...and WHAT there is, when there is barely any of it. The other half
      // of the same defect: a layer that is drawing, correctly, almost
      // nothing looks exactly like a layer that has failed, and the legend
      // was the one surface in a position to tell them apart without the
      // reader unfolding anything. See `EnvironmentLegendSpec.conditionLine`.
      const reading = document.createElement("p");
      reading.className = "key-card-why";
      reading.textContent = spec.conditionLine;
      card.append(reading);
    }
    // THE CLOCK-LANDING SENTENCE IS NOT DRAWN HERE ANY MORE. Sean, 2026-08-27,
    // on the ring current's legend block: "The description is too long. That
    // should go in the layer viewer." It was four lines of prose in a key that
    // stacks one block per drawn layer, and it is not a key to anything: it
    // explains the layer's STATE — that the clock was moved back for it, so it
    // has a frame, and that Return to now would leave it with nothing to draw.
    // `fillLayerCard` prints it on the layer's own card now, word for word.
    if (unavailable?.jumpToIso && unavailable.jumpLabel) {
      const jump = document.createElement("button");
      jump.type = "button";
      jump.className = "key-card-jump";
      jump.dataset.jumpUtc = unavailable.jumpToIso;
      jump.textContent = unavailable.jumpLabel;
      card.append(jump);
    }
    return card;
  }

  /**
   * One data-viewer card, cloned from the same template shape as a satellite
   * card and then kept: the layer's name, its evidence class, the opening
   * sentence of what it shows, and three sections the reader opens when they
   * want them. The rest of the description folds behind "More about this
   * description" exactly as a spacecraft's does.
   */
  /**
   * THE LAYER'S CARD, IN THE PANEL, UNDER THE LAYER — the phone's arrangement.
   *
   * Sean, 2026-08-28: "i want it on the panel under the layer. when a layer is
   * toggled on, a collapse arrow appears on the layer line and the other layers
   * shift down for the contents of what would show up in the viewer. collapsing
   * it moves all the layers below back up so the only thing that looks
   * different is the appearance of the dropdown/expand arrow. in fact, i want
   * it to start off collapsed."
   *
   * So the caret appears on the row the moment the layer is on, the slot under
   * it is EMPTY OF HEIGHT until the caret is pressed, and both are gone again
   * the moment the layer goes off. `phoneLayerCardOpen` is per layer and starts
   * empty on every load, which is the "start off collapsed" — a layer switched
   * on draws itself, puts its scale in the legend over the globe, and adds one
   * arrow to its own row. Nothing else moves.
   *
   * THE CARD IS THE SAME NODE the window over the globe uses on a desktop, not
   * a copy. It carries the layer's own settings panel, moved into it by
   * `fillLayerCard`, and main.ts bound listeners to those controls at startup;
   * a second copy would be a set of switches that look live and are not.
   */
  private placeLayerCardsInRail(active: readonly LayerName[]) {
    const wanted = new Set(active);
    document.querySelectorAll<HTMLElement>("#control-rail .layer-block[data-layer-block]").forEach((block) => {
      if (wanted.has(block.dataset.layerBlock as LayerName)) return;
      block.querySelector(".layer-card-caret")?.remove();
      block.querySelector(".layer-card-slot")?.remove();
      this.phoneLayerCardOpen.delete(block.dataset.layerBlock as LayerName);
    });
    let orphans = document.getElementById("layer-cards-orphan");
    active.forEach((layer) => {
      const card = this.layerCard(layer);
      const block = document.querySelector<HTMLElement>(`#control-rail .layer-block[data-layer-block="${layer}"]`);
      const row = block?.querySelector<HTMLElement>(".layer-row");
      if (!block || !row) {
        // No row of its own: the X-ray photon box and the region annotation are
        // driven by hidden checkboxes and appear only from the guided
        // walkthrough. Their card still has to be somewhere a reader can find
        // it, so it goes open at the foot of the list rather than nowhere.
        if (!orphans) {
          orphans = document.createElement("div");
          orphans.id = "layer-cards-orphan";
          orphans.className = "layer-cards-orphan";
          byId("layer-list").after(orphans);
        }
        if (card.parentElement !== orphans) orphans.append(card);
        this.setLayerCardCollapsed(card, false);
        return;
      }
      let caret = row.querySelector<HTMLButtonElement>(".layer-card-caret");
      if (!caret) {
        caret = document.createElement("button");
        caret.type = "button";
        caret.className = "layer-card-caret";
        caret.setAttribute("aria-controls", `layer-card-slot-${layer}`);
        caret.addEventListener("click", () => this.togglePhoneLayerCard(layer));
        row.append(caret);
      }
      let slot = block.querySelector<HTMLElement>(".layer-card-slot");
      if (!slot) {
        slot = document.createElement("div");
        slot.className = "layer-card-slot";
        slot.id = `layer-card-slot-${layer}`;
        block.append(slot);
      }
      if (card.parentElement !== slot) slot.append(card);
      // Open INSIDE the slot, always: the caret is the fold now, and a card
      // that kept its own collapsed state would need two presses to read.
      this.setLayerCardCollapsed(card, false);
      this.drawLayerCaret(layer, this.phoneLayerCardOpen.has(layer));
    });
    if (orphans && !orphans.childElementCount) { orphans.remove(); }
  }

  /** The caret's three faces: the glyph, the ARIA, and whether the slot has height. */
  private drawLayerCaret(layer: LayerName, open: boolean) {
    const block = document.querySelector<HTMLElement>(`#control-rail .layer-block[data-layer-block="${layer}"]`);
    const slot = block?.querySelector<HTMLElement>(".layer-card-slot");
    const caret = block?.querySelector<HTMLButtonElement>(".layer-card-caret");
    if (slot) slot.hidden = !open;
    if (!caret) return;
    caret.setAttribute("aria-expanded", String(open));
    // The name is read off the card rather than restated here, so the button's
    // accessible name and the card it opens can never drift apart.
    const name = this.layerCards.get(layer)?.querySelector("[data-card-name]")?.textContent ?? "this layer";
    caret.setAttribute("aria-label", open ? `Hide the readings and source for ${name}` : `Show the readings and source for ${name}`);
    caret.textContent = open ? "\u25b4" : "\u25be";
  }

  private togglePhoneLayerCard(layer: LayerName) {
    const open = !this.phoneLayerCardOpen.has(layer);
    if (open) this.phoneLayerCardOpen.add(layer);
    else this.phoneLayerCardOpen.delete(layer);
    this.drawLayerCaret(layer, open);
  }

  /** Back to the desktop: every caret and slot goes, and the cards are handed
   *  to the window over the globe by the caller's `replaceChildren`. */
  private clearRailLayerCards() {
    document.querySelectorAll("#control-rail .layer-card-caret").forEach((caret) => caret.remove());
    document.querySelectorAll("#control-rail .layer-card-slot").forEach((slot) => slot.remove());
    document.getElementById("layer-cards-orphan")?.remove();
  }

  private layerCard(layer: LayerName): HTMLElement {
    const existing = this.layerCards.get(layer);
    if (existing) return existing;
    const template = byId<HTMLTemplateElement>("layer-card-template");
    const card = template.content.firstElementChild!.cloneNode(true) as HTMLElement;
    card.dataset.layer = layer;
    card.querySelectorAll<HTMLElement>("[data-card-section]").forEach((section) => {
      // The settings section keeps its own per-layer memory below: which
      // spacecraft facts you last had open is one preference across every card,
      // but whether the belts' energy picker is open has nothing to say about
      // the ionosphere's altitude picker.
      if (section.hasAttribute("data-card-controls")) return;
      section.toggleAttribute("open", this.cardSectionOpen[section.dataset.cardSection ?? ""] === true);
      this.bindCardSection(section);
    });
    // The layer's own settings, folded, below the readings. See
    // `layerDetailIsOpen` for the measurement: the magnetosphere's thirteen
    // controls were 746 px of an open card against 193 px of readings in the
    // same card, so a reader who asked for one field got a settings dialog.
    // They are controls and they keep one home: this fold, on the layer's own
    // card. (It used to say the caret on the rail row opened them directly.
    // 8c771ca deleted that caret from the site, so the card fold is the only
    // way in and this comment was describing a control a reader cannot find.)
    const controls = card.querySelector<HTMLDetailsElement>("[data-card-controls]")!;
    controls.toggleAttribute("open", this.layerDetailOpen(layer));
    controls.addEventListener("toggle", () => this.setLayerDetailOpen(layer, controls.open));
    // Bound here rather than by the startup [data-view] sweep: this node is a
    // fresh clone of a <template>, so it did not exist in the document when
    // that sweep ran and a data-view attribute on it would never fire.
    card.querySelector<HTMLButtonElement>("[data-card-build-link]")!.addEventListener("click", (event) => {
      const target = (event.currentTarget as HTMLElement).dataset.methodCard;
      this.openContent("sources");
      if (!target) return;
      const methodCard = document.getElementById(target);
      if (!(methodCard instanceof HTMLDetailsElement)) return;
      methodCard.open = true;
      methodCard.scrollIntoView({ block: "center" });
    });
    const toggle = card.querySelector<HTMLButtonElement>("[data-card-toggle]")!;
    toggle.addEventListener("click", () => {
      const collapsed = card.classList.toggle("is-collapsed");
      toggle.setAttribute("aria-expanded", String(!collapsed));
      const chevron = toggle.querySelector<HTMLElement>(".sat-card-chevron");
      if (chevron) chevron.textContent = collapsed ? "+" : "−";
      // Remembered from here on. `fillLayerCard` reapplies the open rule on
      // every refresh — four times a second — so without this the reader's
      // click would be undone before they finished reading the card.
      this.layerCardState.set(layer, !collapsed);
      this.announceOccluderChange();
    });
    this.layerCards.set(layer, card);
    return card;
  }

  /** Sets one card's open state and the three things that have to agree with
   * it: the class the stylesheet reads, the button's ARIA, and the chevron. */
  private setLayerCardCollapsed(card: HTMLElement, collapsed: boolean) {
    if (card.classList.contains("is-collapsed") === collapsed) return;
    card.classList.toggle("is-collapsed", collapsed);
    const toggle = card.querySelector<HTMLButtonElement>("[data-card-toggle]");
    toggle?.setAttribute("aria-expanded", String(!collapsed));
    const chevron = toggle?.querySelector<HTMLElement>(".sat-card-chevron");
    if (chevron) chevron.textContent = collapsed ? "+" : "−";
  }

  /** Refills a kept card in place. Only text and grid contents change, so the
   * disclosures the visitor is reaching for stay where they were. */
  private fillLayerCard(card: HTMLElement, layer: LayerName, spec: EnvironmentLegendSpec) {
    card.querySelector("[data-card-name]")!.textContent = spec.title;
    // The evidence badge lives in the card's HEAD, beside the name, so it is on
    // screen whether the card is open or shut. This is what makes collapsing a
    // card safe: a folded card still states what class of thing it is drawing,
    // and ILLUSTRATION cannot be folded away. `.layer-status` is the
    // stylesheet's one documented exception to the tracked-mono rule — it is a
    // stamp with its own border and colour, not a heading — and the evidence
    // class picks the colour, the same one the rail's own chip uses.
    const badge = card.querySelector<HTMLElement>("[data-card-mission]")!;
    badge.textContent = spec.badge;
    badge.className = `layer-status ${spec.evidence}`;

    // Every card folded to name and badge until the reader opens it. See
    // `layerCardIsOpen`.
    this.setLayerCardCollapsed(card, !layerCardIsOpen(this.layerCardState.get(layer)));

    // This layer's controls, moved in rather than copied. There is exactly one
    // copy of each of them in the document and main.ts bound its listeners at
    // startup, so moving the node keeps every one of those bindings alive —
    // the same arrangement the satellite geometry block already uses. Rebuilding
    // them here would silently produce dead controls.
    const slot = card.querySelector<HTMLElement>("[data-card-controls-slot]")!;
    const panel = this.layerControlPanel(layer);
    if (panel && panel.parentElement !== slot) slot.append(panel);
    const controlsSection = card.querySelector<HTMLElement>("[data-card-controls]")!;
    controlsSection.hidden = !panel?.querySelector("input, select, button, textarea");

    // A layer that is on but not drawn explains itself here; the legend only
    // has room for the headline.
    const unavailable = this.layerUnavailable(layer, spec);
    const purpose = splitLeadSentence(unavailable ? `${unavailable.headline} ${unavailable.because}` : spec.note);
    card.querySelector("[data-card-purpose]")!.textContent = purpose.lead;
    const purposeMore = card.querySelector<HTMLDetailsElement>("[data-card-purpose-more]")!;
    purposeMore.hidden = purpose.rest.length === 0;
    card.querySelector("[data-card-purpose-rest]")!.textContent = purpose.rest;
    card.classList.toggle("is-unavailable", Boolean(unavailable));

    // WHERE THE CLOCK WENT, AND WHY THIS LAYER HAS A FRAME AT ALL.
    //
    // Switching a layer on at a moment its feed has not reached moves the clock
    // back to that layer's newest published frame, and a silent move is its own
    // kind of dishonesty: a reader who was looking at "now" is now two hours
    // earlier. This sentence says where the clock went, whose publishing
    // stopped, and how to get back — and it is careful about a distinction that
    // is easy to lose: the layer HAS something to draw BECAUSE the clock was
    // moved, and Return to now takes the reader to a present where it does not.
    //
    // It lived on the legend card until 2026-08-27, where it was four lines of
    // prose in a key. Sean: "The description is too long. That should go in the
    // layer viewer." Word for word, that is what moved — `coverageLandingNotice`
    // still composes it and this is now its only reader.
    //
    // Only ever said by the layer that asked for the move, and only while that
    // move actually worked: a landing that still leaves the layer empty has
    // nothing to congratulate itself about, and the card's own no-data sentence
    // is the true thing to say instead.
    const landed = card.querySelector<HTMLElement>("[data-card-landed]")!;
    const landedNote = this.coverageLanding?.layer === layer && !unavailable
      ? this.coverageLanding.note
      : null;
    landed.textContent = landedNote ?? "";
    landed.hidden = landedNote === null;

    // WHAT IS DRAWN, beside the sentence about it — the same rows as the
    // legend's, with the one-line "what it is" that the legend has no room
    // for. It sits directly under the opening sentence rather than inside a
    // fold, because "what is that orange thing" is asked while looking at the
    // orange thing, and an answer behind a disclosure triangle is an answer
    // the reader has to already suspect exists.
    const marks = card.querySelector<HTMLElement>("[data-card-marks]")!;
    const drawnMarks = unavailable ? [] : (spec.marks ?? []);
    marks.hidden = drawnMarks.length === 0;
    marks.replaceChildren(...drawnMarks.map((mark) => {
      const row = legendMarkRow(mark);
      const what = document.createElement("small");
      what.textContent = mark.what;
      row.append(what);
      return row;
    }));

    const sections = dataViewerSections(spec);
    card.querySelector("[data-card-readings]")!.replaceChildren(...sections.readings.map((row) => factCell(row)));
    card.querySelector("[data-card-validity]")!.replaceChildren(...sections.validity.map((row) => factCell(row)));
    card.querySelector("[data-card-provenance]")!.replaceChildren(...sections.provenance.flatMap(([label, value]) => {
      const term = document.createElement("dt");
      term.textContent = label;
      const detail = document.createElement("dd");
      detail.textContent = value;
      return [term, detail];
    }));
    // One link out to where this layer's derivation is written, instead of the
    // essay itself. The operational page is for the view, the legend and the
    // numbers; the science is a page of its own and this is the door to it.
    const buildLink = card.querySelector<HTMLButtonElement>("[data-card-build-link]")!;
    const cardId = LAYER_METHOD_CARD_IDS[layer];
    buildLink.hidden = !cardId;
    if (cardId) {
      // Named for what is actually behind it. A layer whose standing physics
      // moved out of this card has to say where it went, or the move reads as
      // a deletion to the one reader who noticed it was there yesterday.
      const standing = standingReadings(spec).length;
      buildLink.textContent = standing > 0
        ? `How ${spec.title} is built, with ${standing} standing ${standing === 1 ? "figure" : "figures"} →`
        : `How ${spec.title} is built →`;
      buildLink.dataset.methodCard = cardId;
    }

    // The X-ray layer is the one card with a chart: the series is real now
    // (the sig-fig rounding that used to zero the whole 48 h history was
    // fixed in a131c8e), and a flat scalar is exactly the kind of quantity a
    // history trace tells you something about that an instantaneous reading
    // cannot. No other card in this template has anything like it.
    if (layer === "photons") this.fillXrayTraceSection(card);
    // The plasmasphere card is the second to carry a chart, and for the same
    // reason: the layer draws a rotationally symmetric cloud whose bright core
    // is provably a still image, so the one thing that MOVES — the boundary —
    // is invisible in it and has to be drawn as a curve to be seen at all.

    card.querySelectorAll<HTMLElement>("[data-card-section]").forEach((section) => {
      // The settings section decides its own visibility above, from whether the
      // layer has any controls; it holds no fact grid and this rule would hide
      // it every time.
      if (section.hasAttribute("data-card-controls")) return;
      // The X-ray trace section manages its own always-shown content, above —
      // an SVG chart or its "not drawable" explanation, neither of which is a
      // `.fact-grid` or `.ephemeris`, so this rule would hide it either way.
      if (section.dataset.cardSection === "xray-trace") return;
      // Same exemption, same reason: an SVG is neither a .fact-grid nor an
      // .ephemeris, so the emptiness rule below would hide it every refill.
      if (section.dataset.cardSection === "plasmapause") return;
      // A section with nothing in it would open onto an empty box.
      const filled = [...section.querySelectorAll<HTMLElement>(".fact-grid, .ephemeris")]
        .some((body) => body.childElementCount > 0);
      section.hidden = !filled;
    });
  }

  /**
   * The X-ray layer's 48 h flux trace.
   *
   * There is nowhere in the shared card template for a chart — every other
   * layer's card is readings and prose — so this one section is built once
   * per card and refreshed here, using the same `card-section` shell so it
   * opens and collapses exactly like the sections the template already has.
   */
  /**
   * The plasmapause, drawn as a curve on the plasmasphere's own card.
   *
   * Measured on the live artifacts: at L = 2 the cloud's density varies 1.16×
   * across all 24 h of local time and 1.10× between frames — about 1% of the
   * colour ramp — because the grains are seeded rotationally symmetric and then
   * rigidly rotated, and rotating a symmetric cloud returns an identical image.
   * The owner's "it looks like a static field that rotates" was right about the
   * brightest part of the layer.
   *
   * The ramp is not the problem: it spans 1–3,000 cm⁻³ and the data occupies
   * 87% of it. What IS happening is that the boundary moves kilometres between
   * frames, and a cloud cannot show that. A ring can.
   *
   * The card already prints the boundary L at 00/06/12/18 MLT, the median, the
   * dusk bulge and the plume, so this adds only what those cannot: the SHAPE as
   * a shape, and the motion ACROSS frames.
   */
  /** The plasmapause boundary at the foot of the Current conditions page. */
  private mountPlasmapause() {
    const host = document.getElementById("now-plasmapause");
    if (!host) return;
    this.fillPlasmapauseSection(host);
    // The coda ends by handing the reader on to the layer page rather than
    // trailing off. The page's markup is injected by openContent(), so the
    // start-up [data-view] sweep never bound anything inside it; this is the
    // one control on the page that goes somewhere in the app, and it is bound
    // here, beside the thing it belongs to.
    const onward = document.querySelector<HTMLButtonElement>("[data-plasmapause-layer-page]");
    if (onward && !onward.dataset.bound) {
      onward.dataset.bound = "1";
      onward.addEventListener("click", () => {
        this.openContent("learn-layers");
        byId("content-body").innerHTML = layerPageView("plasmasphere");
        byId("content-view").scrollTop = 0;
        this.mountLayerPages();
      });
    }
  }

  private fillPlasmapauseSection(card: HTMLElement) {
    let section = card.querySelector<HTMLDetailsElement>('[data-card-section="plasmapause"]');
    if (!section) {
      section = document.createElement("details");
      section.className = "card-section";
      section.dataset.cardSection = "plasmapause";
      section.open = true;
      const summary = document.createElement("summary");
      summary.textContent = "Where the boundary is, and how far it moved";
      const content = document.createElement("div");
      content.className = "plasmapause-chart";
      section.append(summary, content);
      // The layer card had a body wrapper; the Current conditions page hands
      // this a plain host with no such element, and assuming the old shape is
      // what threw "Cannot read properties of null (reading 'append')" the
      // moment the page mounted it.
      (card.querySelector("[data-card-body]") ?? card).append(section);
    }
    const content = section.querySelector<HTMLElement>(".plasmapause-chart")!;
    // WHICH FRAME, AND WHY NOT THE GLOBE'S.
    //
    // This used to read `this.globe.getPlasmasphereField()` — the frame nearest
    // the SELECTED INSTANT, refused unless one lay within half a cadence of it.
    // On this page the selected instant is now, and the newest published frame
    // is never at now: the pipeline anchors frames to a fixed two-hourly UTC
    // grid, so the last one is 0–120 minutes old the moment it is published and
    // a symmetric ±60-minute tolerance threw the whole series away for at least
    // half of every cycle. Live on 2026-08-26 that read "Not drawable at this
    // time" at 15:55 UTC and drew the ring at 16:06 UTC with nothing changed in
    // between. See plasmapause-chart.ts for the measurement.
    //
    // So the page reads the published sequence directly and draws the NEWEST
    // frame, stamped with its own valid time and age. It also no longer depends
    // on the globe having evaluated a field at all, which is one fewer thing
    // between the artifact and the picture.
    const frames = (this.plasmasphereSequence?.bundle.frames ?? []) as unknown as PlasmapauseFrame[];
    const newest = frames.length > 0 ? frames[frames.length - 1]! : null;
    const ageMinutes = newest ? plasmapauseFrameAgeMinutes(newest, new Date()) : null;
    // Absence is stated in words, never as a blank box or a spinner, and the
    // three reasons are different facts so they get three different sentences.
    const refusal = !this.manifest.plasmasphere
      ? "Not drawable: this release publishes no plasmasphere simulation, so no boundary exists to draw."
      : !newest
        ? "Not drawable: the published plasmasphere simulation could not be loaded, so there is no boundary to draw. Nothing is drawn in its place."
        : ageMinutes !== null && ageMinutes > PLASMAPAUSE_MAX_FRAME_AGE_MINUTES
          ? `Not drawable: the newest published boundary is valid ${plasmapauseFrameClock(newest)}, ${Math.floor(ageMinutes / 60)} hours ago, which is past the `
            + `${PLASMAPAUSE_MAX_FRAME_AGE_MINUTES / 60} hours this chart will call current. The simulation has stopped being refreshed; nothing is drawn in its place.`
          : null;
    if (refusal !== null || newest === null) {
      content.replaceChildren();
      content.classList.add("plasmapause-chart--empty");
      content.textContent = refusal ?? "";
      return;
    }
    content.classList.remove("plasmapause-chart--empty");
    // The publisher's own outermost traced shell, so the caption can say
    // "the edge of the model's grid" as a fact read from the bundle rather
    // than as a number this file believes.
    const shells = this.plasmasphereSequence?.bundle.grid.lValues ?? [];
    const domainMaxL = shells.length > 0 ? Math.max(...shells) : null;
    content.replaceChildren(
      plasmapauseFigure(this.buildPlasmapauseSvg(newest), newest),
      plasmapauseCaption(frames, plasmapauseCheckNote(newest, domainMaxL)),
    );
  }

  /** The boundary ring for one frame, with the published check overplotted. */
  private buildPlasmapauseSvg(frame: PlasmapauseFrame): SVGSVGElement {
    const ns = "http://www.w3.org/2000/svg";
    const size = 240;
    const geometry = plasmapauseRingGeometry(frame, size);
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", `0 0 ${size} ${size}`);
    svg.setAttribute("class", "plasmapause-svg");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", plasmapauseSummary([frame]));

    for (const ring of geometry.rings) {
      const circle = document.createElementNS(ns, "circle");
      circle.setAttribute("cx", String(geometry.centre.x));
      circle.setAttribute("cy", String(geometry.centre.y));
      circle.setAttribute("r", ring.radius.toFixed(2));
      circle.setAttribute("class", "plasmapause-shell");
      const label = document.createElementNS(ns, "text");
      label.setAttribute("x", String(geometry.centre.x + 2));
      label.setAttribute("y", (geometry.centre.y - ring.radius + 7).toFixed(2));
      label.setAttribute("class", "plasmapause-axis");
      label.textContent = `L ${ring.lRe}`;
      svg.append(circle, label);
    }
    // Earth, so the picture has a scale a reader already knows.
    const earth = document.createElementNS(ns, "circle");
    earth.setAttribute("cx", String(geometry.centre.x));
    earth.setAttribute("cy", String(geometry.centre.y));
    earth.setAttribute("r", geometry.earthRadius.toFixed(2));
    earth.setAttribute("class", "plasmapause-earth");
    svg.append(earth);

    if (geometry.check.length > 2) {
      const check = document.createElementNS(ns, "path");
      check.setAttribute("d", ringPath(geometry.check));
      check.setAttribute("class", "plasmapause-check");
      svg.append(check);
    }
    const boundary = document.createElementNS(ns, "path");
    boundary.setAttribute("d", ringPath(geometry.boundary));
    boundary.setAttribute("class", "plasmapause-boundary");
    svg.append(boundary);

    if (geometry.plume) {
      const plume = document.createElementNS(ns, "circle");
      plume.setAttribute("cx", geometry.plume.x.toFixed(2));
      plume.setAttribute("cy", geometry.plume.y.toFixed(2));
      plume.setAttribute("r", "3.2");
      plume.setAttribute("class", "plasmapause-plume");
      svg.append(plume);
    }
    // The dial labels come from the SAME projection the ring does. They used to
    // carry their own copy of it — the −π/2-phase-with-negated-cosine version
    // that plasmapause-chart.ts records as the bug the geometry was corrected
    // from — so the live page named every quadrant backwards: "00 MLT" printed
    // at the top over a midnight that is drawn at the bottom, and "18" on the
    // right over a dusk bulge drawn on the left. On a plasmapause chart that is
    // not a cosmetic error; the bulge is the teaching point and the labels put
    // it on the dawn side.
    for (const [mlt, text] of [[0, "00 MLT"], [6, "06"], [12, "12"], [18, "18"]] as const) {
      const radius = size / 2 - 9;
      const at = plasmapauseDialPoint(mlt, radius, geometry.centre);
      const tick = document.createElementNS(ns, "text");
      tick.setAttribute("x", at.x.toFixed(2));
      tick.setAttribute("y", (at.y + 3).toFixed(2));
      tick.setAttribute("text-anchor", "middle");
      tick.setAttribute("class", "plasmapause-axis");
      tick.textContent = text;
      svg.append(tick);
    }
    return svg;
  }

  private fillXrayTraceSection(card: HTMLElement) {
    let section = card.querySelector<HTMLDetailsElement>('[data-card-section="xray-trace"]');
    if (!section) {
      section = document.createElement("details");
      section.className = "card-section";
      section.dataset.cardSection = "xray-trace";
      section.open = true;
      const summary = document.createElement("summary");
      summary.textContent = "48 h flux trace";
      const content = document.createElement("div");
      content.className = "xray-trace";
      section.append(summary, content);
      card.querySelector("[data-card-body]")!.append(section);
    }
    const content = section.querySelector<HTMLElement>(".xray-trace")!;
    const series = drawableXraySeries(this.weather.xray.series ?? null);
    if (!series) {
      content.replaceChildren();
      content.classList.add("xray-trace--empty");
      content.textContent = "Not drawable from this release: the published series rounds to five decimal places, and background flux quantises to exactly zero. The instantaneous reading above is unaffected.";
      return;
    }
    content.classList.remove("xray-trace--empty");
    content.replaceChildren(this.buildXrayTraceSvg(series, this.simulationTime()));
  }

  /**
   * A minimal SVG trace: log₁₀ flux against UTC, gaps left as gaps (the same
   * rule `storm-panel.ts` draws by, reused here rather than reinvented), and
   * a marker at the selected instant.
   */
  private buildXrayTraceSvg(series: ChainSeries, at: Date): SVGSVGElement {
    const width = 300;
    const height = 84;
    const marginLeft = 2;
    const marginRight = 2;
    const plotTop = 6;
    const plotBottom = height - 16;
    const svgNs = "http://www.w3.org/2000/svg";
    const times = series.points.map((point) => point.t).filter((t) => Number.isFinite(t));
    const from = Math.min(...times);
    const to = Math.max(...times);
    const values = series.points
      .map((point) => point.value)
      .filter((value): value is number => value !== null && Number.isFinite(value));
    const low = Math.min(...values);
    const high = Math.max(...values);
    const pad = (high - low) * 0.08 || 0.2;
    const yLow = low - pad;
    const yHigh = high + pad;
    const xOf = (t: number) => marginLeft + ((t - from) / Math.max(1, to - from)) * (width - marginLeft - marginRight);
    const yOf = (value: number) => plotBottom - ((value - yLow) / Math.max(1e-9, yHigh - yLow)) * (plotBottom - plotTop);

    const svg = document.createElementNS(svgNs, "svg");
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.setAttribute("class", "xray-trace-svg");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", `${series.label} over the published 48 hour window`);

    for (const segment of toSegments(series.points, series.maximumGapMs)) {
      if (segment.length < 2) continue;
      const polyline = document.createElementNS(svgNs, "polyline");
      polyline.setAttribute("class", "xray-trace-line");
      polyline.setAttribute("points", segment.map((point) => `${xOf(point.t)},${yOf(point.value)}`).join(" "));
      svg.append(polyline);
    }

    const nowMs = at.getTime();
    if (Number.isFinite(nowMs) && nowMs >= from && nowMs <= to) {
      const now = document.createElementNS(svgNs, "line");
      now.setAttribute("class", "xray-trace-now");
      now.setAttribute("x1", String(xOf(nowMs)));
      now.setAttribute("x2", String(xOf(nowMs)));
      now.setAttribute("y1", String(plotTop));
      now.setAttribute("y2", String(plotBottom));
      svg.append(now);
    }

    const axisStart = document.createElementNS(svgNs, "text");
    axisStart.setAttribute("class", "xray-trace-axis");
    axisStart.setAttribute("x", String(marginLeft));
    axisStart.setAttribute("y", String(height - 4));
    axisStart.textContent = `${new Date(from).toISOString().slice(0, 16).replace("T", " ")}Z`;
    svg.append(axisStart);

    const axisEnd = document.createElementNS(svgNs, "text");
    axisEnd.setAttribute("class", "xray-trace-axis xray-trace-axis--end");
    axisEnd.setAttribute("x", String(width - marginRight));
    axisEnd.setAttribute("y", String(height - 4));
    axisEnd.setAttribute("text-anchor", "end");
    axisEnd.textContent = `${new Date(to).toISOString().slice(0, 16).replace("T", " ")}Z`;
    svg.append(axisEnd);

    return svg;
  }

  /**
   * The cited station table, fetched once and kept.
   *
   * 12.8 KB gzipped, so this is cheap enough to run from two places: switching
   * the overlay on, and opening a spacecraft's card. The second matters — the
   * card's "Ground stations" section must either always reflect the published
   * record or never appear, and a section that shows up only when an unrelated
   * layer happens to be on is worse than one that is never there.
   */
  private loadGroundStations(): Promise<void> {
    if (this.groundStations) return Promise.resolve();
    if (this.groundStationLoading) return this.groundStationLoading;
    const record = this.manifest.groundStations;
    if (!record) {
      this.groundStationLoadFailed = true;
      return Promise.resolve();
    }
    const manifestUrl = new URL("data/manifest.json", document.baseURI);
    this.groundStationLoading = fetchJson<GroundStationBundle>(artifactUrl(manifestUrl, record.path))
      .then((bundle) => {
        this.groundStations = indexGroundStations(bundle);
        const layer = new GroundStationLayer({ stations: bundle.stations });
        this.groundStationLayer = layer;
        this.globe.addEarthFixedOverlay(layer.group);
        layer.setVisible(byId<HTMLInputElement>("layer-ground-stations").checked);
        this.groundStationLoadFailed = false;
        // The spacecraft already open now has a record to show, and the layer
        // card now has counts instead of "loading".
        this.renderStationLinksForSelected();
        this.updateEnvironmentLegend();
      })
      .catch((error: unknown) => {
        console.error("Ground-station artifact could not be loaded", error);
        this.groundStationLoadFailed = true;
        this.updateEnvironmentLegend();
      })
      .finally(() => {
        this.groundStationLoading = null;
      });
    return this.groundStationLoading;
  }

  /**
   * Which pin is open. Selection drives the layer card, and — when a spacecraft
   * is also selected — the visibility ring, which is the coverage footprint
   * already drawn for that spacecraft seen from the other end of the link.
   */
  private setSelectedStation(index: number | null) {
    this.selectedStationIndex = index;
    byId("ground-station-clear").hidden = index === null;
    this.updateStationRing();
    this.updateEnvironmentLegend();
  }

  private updateStationRing() {
    const layer = this.groundStationLayer;
    if (!layer) return;
    const index = this.selectedStationIndex;
    const station = index === null ? null : layer.stations[index];
    const satellite = this.selectedIndex === null ? null : this.catalog.satellites[this.selectedIndex];
    if (index === null || !station || !satellite) {
      layer.showVisibilityRing(null, 0, 0);
      return;
    }
    const state = propagateOmm(satellite.omm, this.simulationTime());
    if (!state) {
      layer.showVisibilityRing(null, 0, 0);
      return;
    }
    layer.showVisibilityRing(index, state.altitudeKm, stationMinimumElevationDeg(station).degrees);
  }

  /**
   * A click on the globe that hit no spacecraft. It may still have hit a pin.
   * Reports whether it did, so a miss can fall through to the probe rather
   * than being swallowed here.
   */
  private pickGroundStation(clientX: number, clientY: number): boolean {
    const layer = this.groundStationLayer;
    if (!layer || !byId<HTMLInputElement>("layer-ground-stations").checked) return false;
    const hit = this.globe.pickOverlay(clientX, clientY, (x, y, camera, width, height) =>
      layer.pick(x, y, camera, width, height));
    if (hit === null) return false;
    this.setSelectedStation(hit);
    // The readings live in the Data Explorer, which is where every layer's
    // numbers live; expanding it is the only way a click on a pin can show
    // them (it is already present, since the ground-station layer is on).
    if (this.explorerCollapsed) this.setExplorerCollapsed(false);
    this.environmentLegendFocus = "groundStations";
    this.updateEnvironmentLegend();
    return true;
  }

  /**
   * Fills the awareness page: the NOAA panels are moved in from the markup
   * they already live in, and the Kp chart is drawn.
   *
   * Moving rather than copying is the same rule the layer cards follow for
   * their control panels. There is exactly one copy of each NOAA panel in the
   * document, so this page and any other surface cannot drift apart or state
   * different numbers, and the listeners bound at startup survive.
   */
  private mountCurrentConditions() {
    const mount = document.getElementById("now-swpc-mount");
    if (mount) {
      for (const id of ["swpc-panel-conditions", "swpc-panel-forecast", "swpc-panel-geomagnetic"]) {
        const panel = document.getElementById(id);
        if (panel) mount.append(panel);
      }
      // On a page there is no room for tabs to hide two thirds of the answer:
      // everything NOAA published is shown at once, in order.
      mount.querySelectorAll<HTMLElement>(".swpc-panel").forEach((panel) => { panel.hidden = false; });
    }
    // The outlook renderer writes into these ids; run it now that they are on
    // screen, so the page is never blank on first open.
    this.updateSwpcOutlook();
    // The board first: it is above everything the block above just filled in,
    // and it is the only part of the page a reader is guaranteed to see.
    this.drawConditionsBoard();
    this.drawKpChart();
    // The plasmapause belongs here now: it is driven by the same Kp the chart
    // above plots, and it is the part of the plasmasphere worth keeping — the
    // boundary moving, with the published check overplotted.
    void this.loadPlasmasphere().then(() => this.mountPlasmapause());
  }

  /**
   * The published status of one ingested product, by its own name.
   *
   * The evidence badge on every tile comes from here rather than from a
   * constant in this file. The pipeline already records, per product, whether
   * what it fetched was observed, assimilated, modelled or forecast; hard-
   * coding "OBSERVED" beside a number would be the site asserting a claim on
   * NOAA's behalf, and would go stale silently the day a feed changed.
   */
  private sourceEvidence(product: string, fallback: EvidenceClass): EvidenceClass {
    const status = this.weather.sources.find((entry) => entry.product === product)?.status;
    // "schematic" is a drawing class and never describes an ingested number,
    // so it is not in EvidenceClass; anything unexpected falls back rather
    // than being printed as a badge nobody has styled.
    if (status === "observed" || status === "assimilated" || status === "model" || status === "forecast") return status;
    return fallback;
  }

  /**
   * The conditions board: the three NOAA scales and five drivers, at the top
   * of the awareness page.
   *
   * Everything drawn here was already published in the release the page is
   * reading; nothing is computed, smoothed, or filled in. Where a value is
   * absent the tile says so in words — see `conditions-board.ts` for why an
   * empty sparkline is a lie rather than a blank.
   */
  private drawConditionsBoard() {
    const scalesHost = document.getElementById("now-scales");
    const driversHost = document.getElementById("now-drivers");
    const verdict = document.getElementById("now-verdict");
    const foot = document.getElementById("now-board-foot");
    if (!scalesHost || !driversHost || !verdict || !foot) return;

    const outlook = this.weather.outlook;
    if (outlook) {
      const latest = outlook.noaaScales.latestObserved;
      const day = outlook.noaaScales.rolling24HourMaximum;
      scalesHost.replaceChildren(
        renderScaleTile(scaleTile("R", "Radio blackout", latest.radioBlackout, day.radioBlackout)),
        renderScaleTile(scaleTile("S", "Solar radiation", latest.solarRadiation, day.solarRadiation)),
        renderScaleTile(scaleTile("G", "Geomagnetic", latest.geomagnetic, day.geomagnetic)),
      );
    } else {
      scalesHost.replaceChildren();
    }

    // The headline is computed first, because the Dst tile has to print the
    // SAME trace the classifier used. Three traces disagree by 10-15 nT at the
    // same instant; a verdict quoting USGS Dst3 above a tile quoting Kyoto is
    // a page contradicting itself in two places a reader can see at once.
    const headline = stormHeadline(this.weather.storm, this.weather.magnetopause.driverSeries, this.simulationTime());
    const wind = this.weather.solarWind;
    const imf = this.weather.imf;
    const kp = this.weather.geomagnetic;
    const xray = this.weather.xray;
    // Whichever trace the classifier settled on, or Kyoto when nothing is
    // classified. Naming it on the tile is not pedantry: this site carries
    // three Dst traces that disagree by 10-15 nT and never merges them.
    const dstTraces = this.weather.storm?.dst ?? null;
    const dst = dstTraces
      ? headline?.dstSource === "USGS Dst3"
        ? dstTraces.observed
        : headline?.dstSource === "physics-model nowcast"
          ? dstTraces.modelled
          : dstTraces.kyoto
      : null;

    const tiles: DriverTile[] = [
      {
        key: "kp",
        label: "Planetary K index",
        badge: evidenceBadge(this.sourceEvidence("Planetary K index", "observed")),
        valueText: kp.kp === null ? null : kp.kp.toFixed(1),
        unit: "",
        missingReason: "NOAA published no planetary K value in this release.",
        series: kp.series,
        // Fixed 0-9, so a quiet day looks quiet instead of being stretched to
        // fill the box. G1 begins at Kp 5, which is the middle of this domain.
        spark: { domain: [0, 9] },
        // Naming the product is not pedantry: this page prints TWO planetary K
        // values. This tile is NOAA's 1-minute running estimate; the chart
        // below plots the three-hour index, and while a three-hour period is
        // still open the two can be a whole band apart. The site never merges
        // its three Dst traces for the same reason and says so on the tile.
        note: "NOAA's 1-minute running estimate. The chart below plots the three-hour index, which can read higher while a period is still open.",
        accent: "var(--amber)",
      },
      {
        key: "dst",
        // The badge WORD has to move with the badge CLASS. This tile follows
        // whichever of the three Dst traces the classifier settled on, and one
        // of the three is the SWMF nowcast — so when neither observatory had a
        // sample near the selected instant, the tile carried the model's colour
        // under the word OBSERVED, which is the one thing this board exists not
        // to do. (Fixed 2026-09-08.)
        label: "Dst · ring current",
        badge: evidenceBadge(dst?.status === "model" ? "model" : "observed"),
        valueText: dst?.latestNt === null || dst?.latestNt === undefined ? null : signed(dst.latestNt),
        unit: "nT",
        missingReason: "No Dst trace is published in this release.",
        series: dst?.series.map((sample) => ({ time: sample.at, value: sample.dstNt })) ?? [],
        spark: {},
        note: dst
          ? dst.status === "model"
            ? `${dst.label}. A modelled depression, not a measured one — no observatory trace covered this instant. Where it is measured, that depression IS the ring current, to within a factor of two.`
            : `${dst.label}. This depression IS the ring current, to within a factor of two.`
          : "",
        accent: "var(--violet)",
      },
      {
        key: "wind",
        label: "Solar wind speed",
        badge: evidenceBadge(this.sourceEvidence("Real-time solar wind plasma", "observed")),
        valueText: wind.speedKps === null ? null : wind.speedKps.toFixed(0),
        unit: "km/s",
        missingReason: "The real-time plasma feed published no speed.",
        series: wind.series,
        spark: { minSpan: 40 },
        note: `Measured at L1 by ${wind.sourceSpacecraft}, roughly 40-60 minutes upstream of Earth.`,
        accent: "var(--mint)",
      },
      {
        key: "bz",
        label: "IMF Bz (GSM)",
        badge: evidenceBadge(this.sourceEvidence("Real-time interplanetary magnetic field", "observed")),
        valueText: imf.bzGsmNt === null ? null : signed(imf.bzGsmNt, 1),
        unit: "nT",
        missingReason: "The real-time magnetometer feed published no Bz.",
        series: imf.series,
        spark: { minSpan: 6 },
        note: "Southward — below the dashed zero line — is what opens the magnetosphere to the solar wind.",
        accent: "var(--cyan-bright)",
      },
      {
        key: "xray",
        label: "Solar X-ray flux",
        badge: evidenceBadge(this.sourceEvidence("GOES X-ray flux", "observed")),
        valueText: xray.fluxWm2 === null ? null : xray.class,
        unit: "",
        missingReason: "GOES published no X-ray flux in this release.",
        series: xray.series,
        // Log, because the flare classes A-B-C-M-X are decades. On a linear
        // axis every quiet day is a flat line on the floor of the box.
        spark: { transform: (value: number) => (value > 0 ? Math.log10(value) : Number.NaN) },
        rangeFormat: (min, max) => `${flareClass(min)} to ${flareClass(max)}`,
        note: "GOES 0.1-0.8 nm. Each class letter is ten times the one below it, so this is a log axis.",
        accent: "var(--coral)",
      },
    ];
    driversHost.replaceChildren(...tiles.map((tile) => renderDriverTile(tile)));

    // The verdict. It is the storm classification when there is one, because
    // that is the loudest true thing the site can say; otherwise it is the
    // highest NOAA scale at threshold; otherwise it says plainly that nothing
    // is. It never invents a state to have something to report.
    const latest = outlook?.noaaScales.latestObserved ?? null;
    const highest = latest
      ? ([
          ["R", "radio blackout", latest.radioBlackout],
          ["S", "solar radiation storm", latest.solarRadiation],
          ["G", "geomagnetic storm", latest.geomagnetic],
        ] as const)
          .filter(([, , reading]) => (reading.level ?? 0) > 0)
          .sort((a, b) => (b[2].level ?? 0) - (a[2].level ?? 0))[0] ?? null
      : null;
    if (headline) {
      verdict.dataset.state = headline.phase === "main" ? "storm-main" : "storm";
      verdict.textContent = withMinusSigns(`${headline.reason}. The ring current is `
        + `${headline.phase === "recovery" ? "unwinding" : "being loaded"}`
        + `${headline.dstSource ? `, measured by ${headline.dstSource}` : ""}.`);
    } else if (highest) {
      verdict.dataset.state = "storm";
      verdict.textContent = `NOAA is reporting ${highest[0]}${highest[2].level} — ${highest[2].label ?? `${highest[1]} in progress`}.`;
    } else if (latest) {
      verdict.dataset.state = "";
      verdict.textContent = "No NOAA space-weather scale is at threshold right now. The drivers below are what would change that.";
    } else {
      verdict.dataset.state = "";
      verdict.textContent = "This release carries no NOAA scale record, so the site cannot say what the operational level is.";
    }

    // The same reconciliation the storm popover carries, on the board where
    // the reader is looking at G0 and a storm classification side by side. A
    // reader who sees those two without a word about why concludes the site is
    // broken, and this is now the most prominent place the pair appears.
    const conflictNode = document.getElementById("now-scale-conflict");
    if (conflictNode) {
      const reconciliation = kpDstReconciliation({
        kpIndex: this.weather.geomagnetic.kp,
        gLevel: latest?.geomagnetic.level ?? null,
        dstNt: headline?.dstNt ?? null,
        dstSource: headline?.dstSource ?? null,
      });
      conflictNode.hidden = reconciliation === null;
      conflictNode.textContent = reconciliation === null ? "" : withMinusSigns(reconciliation);
    }

    foot.textContent = `${formatUtcStamp(latest?.asOf ?? this.weather.solarWind.observedAt, "Latest observed values")}. `
      + "Measurements and forecasts are drawn differently everywhere on this page, because they are different claims. "
      + "Nothing here is a warning product; NOAA SWPC is.";
  }

  /** Hands the NOAA panels back to their own markup when the page closes. */
  private returnOutlookPanels() {
    const home = document.getElementById("swpc-dialog-panels");
    if (!home) return;
    for (const id of ["swpc-panel-conditions", "swpc-panel-forecast", "swpc-panel-geomagnetic"]) {
      const panel = document.getElementById(id);
      if (panel && panel.parentElement !== home) home.append(panel);
    }
  }

  /**
   * Watch the Kp chart's own box and redraw it when its width changes.
   *
   * A `resize` listener on the window is not enough and a single draw at mount
   * is worse. This chart's geometry is built at the container's measured pixel
   * width, and the awareness page is mounted while it is still hidden: the
   * first `drawKpChart` measures ZERO, and a chart drawn at a guessed width
   * and then stretched to the real one is exactly the fault this rebuild
   * exists to remove — measured on the built page, a chart laid out at 320
   * units and rendered 1,018 px wide put its 10.4 px axis type on screen at
   * 33 px. The observer fires when the element is first laid out, and again on
   * any later change, which covers the window resize as well.
   *
   * Redrawing does change the element's HEIGHT, through the viewBox aspect, so
   * the callback compares WIDTH only; a height change must not re-enter.
   */
  private observeKpChart(chart: Element): boolean {
    if (typeof ResizeObserver === "undefined") return false;
    if (this.kpChartObserver) return true;
    this.kpChartObserver = new ResizeObserver(() => {
      const measured = Math.round(chart.getBoundingClientRect().width);
      if (measured < 1 || measured === this.kpChartWidth) return;
      this.drawKpChart();
    });
    this.kpChartObserver.observe(chart);
    return true;
  }

  /**
   * The Kp series, seven days behind and three ahead.
   *
   * Observed, estimated and forecast bars are drawn differently because they
   * are different claims; the G-scale thresholds are ruled across so a bar's
   * operational meaning is readable without a legend lookup; and the boundary
   * between the last measurement and the first forecast is marked, because
   * that is the most important line on the chart.
   *
   * Sizing, since the axis rebuild of 2026-08-19: the geometry is built at the
   * element's measured CSS width, so one viewBox unit is one rendered pixel
   * and `.now-kp-axis` renders at the size it is declared. Before this the
   * viewBox was a fixed 320 units against a 1,018 px render, and the same 5 px
   * declaration came out 15.9 px on a desktop and 5.2 px on a phone.
   */
  private drawKpChart() {
    const chart = document.getElementById("now-kp-chart");
    if (!chart) return;
    // A release without an outlook draws no chart and says so, rather than an
    // empty axis pretending the index is flat.
    const outlook = this.weather.outlook;
    if (!outlook) {
      const summaryNode = document.getElementById("now-kp-summary");
      if (summaryNode) summaryNode.textContent = "No NOAA outlook is published in this release.";
      return;
    }
    const rows = outlook.kpForecast.rows as KpRow[];
    // Measured, not assumed. A hidden or unlaid-out element measures 0, and a
    // zero-width chart would collapse every bar onto one column; the floor is
    // the narrowest viewport this site is built for.
    const observing = this.observeKpChart(chart);
    const measured = Math.round(chart.getBoundingClientRect().width);
    // A hidden or not-yet-laid-out chart measures zero. Draw nothing into it:
    // the observer above will call back the moment it has a real width, and a
    // guessed width would be stretched to the real one by the viewBox, which
    // is what put the axis type on screen at three times its declared size.
    // Without an observer there is nothing to wait for, so a guess is drawn.
    if (measured < 1 && observing) return;
    // Remember what was MEASURED, not what was drawn: below the 300 px floor
    // the two differ, and comparing against the clamp would redraw forever.
    this.kpChartWidth = measured;
    const width = Math.max(300, Math.min(1120, measured || 320));
    const height = Math.round(Math.max(190, Math.min(300, width * 0.3)));
    const geometry = kpChartGeometry(rows, this.simulationTime().toISOString(), width, height);
    const { left, right, top, bottom } = geometry.plot;
    const ns = "http://www.w3.org/2000/svg";
    const nodes: SVGElement[] = [];
    const node = <K extends keyof SVGElementTagNameMap>(name: K, attributes: Record<string, string | number>) => {
      const created = document.createElementNS(ns, name);
      for (const [key, value] of Object.entries(attributes)) created.setAttribute(key, String(value));
      return created;
    };

    // The forecast region, shaded before anything is drawn over it. The dashed
    // outline on each predicted bar says the same thing bar by bar; the shade
    // says it once, at a glance, which is how a reader finds the edge of the
    // measured record without reading a legend.
    if (geometry.forecastBoundaryX !== null) {
      nodes.push(node("rect", {
        class: "now-kp-lead",
        x: geometry.forecastBoundaryX,
        y: top,
        width: Math.max(0, right - geometry.forecastBoundaryX),
        height: bottom - top,
      }));
    }

    // The value axis: Kp on the left because that is what is plotted, the G
    // band on the right because that is what it means. The old axis carried
    // only G1 through G5 — every one of them at Kp 5 or above — so a quiet
    // week's bars all sat in an unlabelled 55% of the box.
    for (const tick of geometry.valueTicks) {
      nodes.push(node("line", {
        class: `now-kp-rule${tick.kp === 0 ? " is-baseline" : ""}${tick.level > 0 ? " is-storm" : ""}`,
        x1: left, x2: right, y1: tick.y, y2: tick.y,
      }));
      const value = node("text", { class: "now-kp-axis", x: left - 6, y: tick.y + 3.5, "text-anchor": "end" });
      value.textContent = String(tick.kp);
      nodes.push(value);
      if (tick.gLabel) {
        const band = node("text", { class: "now-kp-axis is-band", x: right + 6, y: tick.y + 3.5 });
        band.textContent = tick.gLabel;
        nodes.push(band);
      }
    }

    for (const bar of geometry.bars) {
      const rect = node("rect", {
        x: bar.x.toFixed(2),
        y: bar.y.toFixed(2),
        width: bar.width.toFixed(2),
        // A Kp of 0 is a real, common reading; give it a visible baseline tick
        // rather than drawing nothing, which would read as missing data.
        height: Math.max(1, bar.height).toFixed(2),
        class: `now-kp-bar is-${bar.status} g${bar.level}`,
      });
      const title = document.createElementNS(ns, "title");
      title.textContent = `${bar.timeIso.slice(0, 16).replace("T", " ")} UTC · Kp ${bar.kp.toFixed(2)}`
        + `${kpStormLabel(bar.kp) ? ` · ${kpStormLabel(bar.kp)}` : ""} · ${bar.status}`;
      rect.append(title);
      nodes.push(rect);
    }

    // The time axis. Eleven UTC midnights were computed here and discarded for
    // as long as this chart has existed, which left a picture captioned "seven
    // days behind, three ahead" carrying no date at all.
    for (const tick of geometry.dayTicks) {
      nodes.push(node("line", { class: "now-kp-day", x1: tick.x, x2: tick.x, y1: top, y2: bottom }));
      if (!tick.labelled) continue;
      // The first and last dates are centred on ticks that sit on the plot
      // edges, so they anchor inward instead of hanging off the box.
      const anchor = tick.x - left < 16 ? "start" : right - tick.x < 16 ? "end" : "middle";
      const label = node("text", { class: "now-kp-axis", x: tick.x, y: bottom + 16, "text-anchor": anchor });
      label.textContent = tick.label;
      nodes.push(label);
    }

    if (geometry.forecastBoundaryX !== null) {
      nodes.push(node("line", {
        class: "now-kp-boundary",
        x1: geometry.forecastBoundaryX, x2: geometry.forecastBoundaryX, y1: top, y2: bottom,
      }));
    }
    // Now, interpolated inside its own three-hour period. The forecast
    // boundary is not a substitute: the last measured period and the first
    // forecast period can be up to three hours apart.
    if (geometry.nowX !== null) {
      nodes.push(node("line", {
        class: "now-kp-now", x1: geometry.nowX, x2: geometry.nowX, y1: top - 6, y2: bottom,
      }));
      const stamp = node("text", {
        class: "now-kp-axis is-now",
        x: Math.min(geometry.nowX, right - 4),
        y: top - 9,
        "text-anchor": geometry.nowX > right - 30 ? "end" : "middle",
      });
      stamp.textContent = geometry.nowLabel ?? "";
      nodes.push(stamp);
    }

    chart.setAttribute("viewBox", `0 0 ${geometry.width} ${geometry.height}`);
    chart.replaceChildren(...nodes);
    const summary = kpChartSummary(rows);
    chart.setAttribute("aria-label", summary);
    const summaryNode = document.getElementById("now-kp-summary");
    if (summaryNode) summaryNode.textContent = summary;
    const limitation = document.getElementById("now-kp-limitation");
    if (limitation) limitation.textContent = KP_LIMITATION;
  }

  /**
   * The probe: everything this site can say about the place under the pointer.
   *
   * The rail is capped at six fields over the whole globe and never grows; a
   * question about ONE PLACE belongs here instead, where it costs nothing until
   * it is asked. The vertical profile is the reason this exists — the site has
   * been drawing three peak surfaces from an artifact that carries the whole
   * 90–2,655 km column at every grid point, and nested shells hide each other
   * from outside no matter what colour scale they are given.
   *
   * The cube is a 19 MB artifact that loads only when the ionosphere layer is
   * switched on, so a probe on a cold page loads it first and says so.
   */
  /**
   * Arm or cancel the explicit profile pick.
   *
   * Why there is a mode at all: the vertical profile has always been reachable
   * by clicking bare globe, and nobody discovers that. Sean asked for the four
   * regions to be "plotted" twice while a complete, tested altitude ladder of
   * exactly those four sat one undiscoverable click away. The ladder is fine.
   * The door was missing, so this is the door.
   *
   * It STAYS ARMED after a pick, deliberately. A confirmation step was
   * considered and rejected: clicking a point on a globe is free and instantly
   * reversible, so a confirm dialog is friction charged on every single use to
   * insure against a mistake that costs one more click to undo. Staying armed
   * is one click shorter AND makes the thing a reader actually wants to do —
   * compare two places — fast, because the next click just re-picks. The
   * button says how to leave, and Escape leaves.
   */
  private setProfilePickArmed(armed: boolean) {
    this.profilePickArmed = armed;
    this.globe.setPointPickMode(armed);
    const button = byId("ionosphere-profile-pick");
    button.setAttribute("aria-pressed", String(armed));
    button.textContent = armed ? "Stop picking points" : "Show a vertical profile →";
    button.classList.toggle("is-armed", armed);
    byId("ionosphere-profile-hint").hidden = !armed;
  }

  private probeAt(clientX: number, clientY: number) {
    const point = this.globe.pickGeographicPoint(clientX, clientY);
    if (!point) return;
    this.probePoint = point;
    this.renderProbe();
  }

  /**
   * Fetches the column on request and redraws. Separate from the click so the
   * cost is always something the visitor asked for.
   */
  private loadProbeColumn() {
    const point = this.probePoint;
    this.renderProbe("Loading the WAM-IPE column…");
    void this.loadIonosphereModel().then(() => {
      // Only redraw if this click is still the one on screen: a visitor who
      // clicked twice while a 19 MB artifact was in flight should get the
      // second answer, not the first arriving late over it.
      if (this.probePoint === point) this.renderProbe();
    });
  }

  /**
   * Draws the probe for the currently held point, sampling the column at the
   * simulation time. Re-entered on a time change and on a path-length change,
   * so it must be cheap: one sampler is kept for the bundle's lifetime, which
   * is what makes thirty levels one decode rather than thirty.
   */
  private renderProbe(pending?: string) {
    const panel = byId("probe-panel");
    const point = this.probePoint;
    if (!point) {
      panel.hidden = true;
      this.globe.setProbePoint(null);
      return;
    }
    panel.hidden = false;
    // The globe says WHERE, the panel says WHAT. Set here rather than at the
    // three call sites because every one of them — the pick, the close button
    // and the timeline — already funnels through this method, so the marker
    // cannot get out of step with the panel by someone adding a fourth.
    this.globe.setProbePoint(point);
    byId("probe-place").textContent = formatGeographicPoint(point.latitudeDeg, point.longitudeDeg);
    const status = byId("probe-status");
    const body = byId("probe-body");
    const load = byId("probe-load");
    load.hidden = true;
    if (pending) {
      status.hidden = false;
      status.textContent = pending;
      body.hidden = true;
      return;
    }
    const model = byId("probe-model-section");
    const bundle = this.ionosphereBundle;
    let profile: SampledProfile | null = null;
    if (bundle) {
      this.ionosphereSampler ??= new IonosphereSampler(bundle);
      profile = sampleProfile(this.ionosphereSampler, bundle.grid.altitudesKm, {
        latitudeDeg: point.latitudeDeg,
        longitudeDeg: point.longitudeDeg,
        time: this.simulationTime(),
      });
      this.probeProfile = profile;
    }

    // The measured layer structure is drawn FIRST and independently of the
    // model column. It needs a 9 KB soundings artifact, and gating four
    // measured critical frequencies behind a 19 MB download would be a cost
    // with no reason behind it. The body therefore opens whether or not the
    // column is present, and only the model half of it is hidden below.
    body.hidden = false;
    this.renderCompositeLayers(point, profile?.derivations ?? null);

    if (!bundle) {
      status.hidden = false;
      model.hidden = true;
      if (this.ionosphereLoadFailed) {
        status.textContent = "The WAM-IPE column could not be loaded, so there is no model profile to compare against.";
        return;
      }
      // Not an error — just not fetched yet. The visitor decides.
      status.textContent = "The modelled column over this point comes from WAM-IPE, which is not loaded yet.";
      load.hidden = false;
      return;
    }
    if (profile!.unavailable) {
      status.hidden = false;
      status.textContent = profile!.unavailable;
      model.hidden = true;
      return;
    }
    status.hidden = true;
    model.hidden = false;
    this.fillProbeReadings(profile!);
    drawProfileChart(byId<SVGSVGElement & HTMLElement>("probe-chart"), profile!);
    byId("probe-evidence").textContent = profileEvidenceNote();
    byId("probe-muf-limit").textContent = MUF_LIMITATION;
    byId("probe-column-limit").textContent = COLUMN_LIMITATION;
    byId("probe-field-limit").textContent = ECCENTRIC_DIPOLE_LIMITATION;
  }

  /**
   * Fetch the measured soundings.
   *
   * Single-flight and idempotent, in the shape `loadIonosphereModel` uses. A
   * release built without the lane must still work: the probe then draws no
   * layer section at all rather than a section full of empty rows, because an
   * empty layer table is a claim that the layers are missing and they are not.
   */
  private loadSoundings(): Promise<void> {
    if (this.soundingBundle) return Promise.resolve();
    if (this.soundingLoading) return this.soundingLoading;
    const record = this.manifest.ionosondeSoundings;
    if (!record) return Promise.resolve();
    const manifestUrl = new URL("data/manifest.json", document.baseURI);
    this.soundingLoading = fetchJson<SoundingBundle>(artifactUrl(manifestUrl, record.path))
      .then((bundle) => {
        this.soundingBundle = bundle;
        // A click that landed before the fetch returned must be answered once
        // it does, or the reader sees an empty panel that silently fills only
        // if they click again.
        if (this.probePoint) this.renderProbe();
      })
      .catch((error: unknown) => {
        console.warn("ionosonde soundings unavailable", error);
      })
      .finally(() => {
        this.soundingLoading = null;
      });
    return this.soundingLoading;
  }

  /**
   * Draw the four-layer structure over this point.
   *
   * The three things this must never do, which are the reasons it is written
   * the way it is:
   *
   * 1. It must never let a distant sounding pass as a local measurement. The
   *    station line names the station and its distance every single time, and
   *    it is graded: area-weighted over the globe the nearest sounding under
   *    three hours old has a median distance of 2,643 km, so the far case is
   *    the ordinary case and it gets the honest wording.
   * 2. It must never render an absent layer as missing data. F1 vanishes at
   *    night, and the panel says so in those words.
   * 3. It must never imply the anchor reaches further than it does. Bar
   *    opacity is the anchor weight, so a layer nobody measured near this
   *    point is visibly faint.
   */
  private renderCompositeLayers(
    point: { latitudeDeg: number; longitudeDeg: number },
    derived: ProfileDerivations | null,
  ) {
    const section = byId("probe-layers");
    const bundle = this.soundingBundle;
    if (!bundle) {
      section.hidden = true;
      void this.loadSoundings();
      return;
    }
    section.hidden = false;
    const time = this.simulationTime();
    const dRegion = sampleEmpiricalDRegion(point.latitudeDeg, point.longitudeDeg, time, this.currentXrayFlux);
    const composite = compositeProfile({
      point,
      time,
      stations: bundle.stations,
      xrayFluxWm2: this.currentXrayFlux,
      modelFoF2Mhz: derived?.foF2Mhz ?? null,
      modelHmF2Km: derived?.hmF2Km ?? null,
      dRegionEffectiveHeightKm: dRegion.effectiveHeightKm,
      dRegionBetaPerKm: dRegion.betaPerKm,
    });

    this.fillProbeStationLine(point, bundle);
    drawLayerLadder(byId<SVGSVGElement & HTMLElement>("probe-ladder"), composite);
    byId("probe-layer-list").replaceChildren(...composite.layers.map(layerRow));
    byId("probe-composite-evidence").textContent = composite.evidenceNote;
    byId("probe-sounding-evidence").textContent = SOUNDING_EVIDENCE_NOTE;
    byId("probe-network-note").textContent = networkNote(bundle);
    byId("probe-composite-limit").textContent = COMPOSITE_IONOSPHERE_METHOD.limitations[0];
  }

  /**
   * The station line, which is the honesty line for this whole feature.
   *
   * It is written from the nearest station of ANY kind rather than from the
   * nearest one that happened to scale a particular layer, because the reader's
   * question is "how close is the nearest real observation to where I clicked"
   * and that has one answer.
   */
  private fillProbeStationLine(
    point: { latitudeDeg: number; longitudeDeg: number },
    bundle: SoundingBundle,
  ) {
    const line = byId("probe-station");
    const nearest = nearestSounding(point, bundle.stations);
    if (!nearest) {
      line.className = "probe-station unrelated";
      line.textContent = "No station in the network has sounded recently enough to use, so nothing here is anchored to a measurement.";
      return;
    }
    const relevance = soundingRelevance(nearest.distanceKm);
    line.className = `probe-station ${relevance}`;
    const named = document.createElement("b");
    named.textContent = `${nearest.station.name} · ${Math.round(nearest.distanceKm).toLocaleString()} km`;
    line.replaceChildren(
      named,
      document.createTextNode(` · ${soundingAgeNote(nearest.station.ageMinutes)} ${relevanceNote(relevance)}`),
    );
  }

  /**
   * The operational numbers, in the order an officer asks for them: what
   * reflects, what a link of the chosen length can use, what the column costs a
   * GNSS receiver, and when the model says it.
   */
  private fillProbeReadings(profile: SampledProfile) {
    const rows: Array<[string, string]> = [];
    const derived = profile.derivations;
    if (derived) {
      rows.push(["foF2", `${derived.foF2Mhz.toFixed(1)} MHz`]);
      rows.push(["hmF2", `${Math.round(derived.hmF2Km)} km`]);
      const rangeKm = Number(byId<HTMLSelectElement>("probe-range").value);
      const muf = mufMhz(derived.foF2Mhz, derived.hmF2Km, rangeKm);
      if (muf !== null) {
        rows.push([rangeKm === 0 ? "MUF · vertical" : `MUF · ${rangeKm.toLocaleString()} km hop`, `${muf.toFixed(1)} MHz`]);
      }
      rows.push(["Vertical TEC", `${derived.verticalTecu.toFixed(1)} TECU`]);
      rows.push(["GNSS L1 range error", `${derived.gnssRangeErrorL1M.toFixed(1)} m at zenith`]);
      rows.push(["Frequency", `${GNSS_L1_MHZ.toFixed(2)} MHz (L1)`]);
    }
    const levels = profile.levels.filter((level) => level.electronDensityM3 !== null).length;
    rows.push(["Levels published", `${levels} of ${profile.levels.length}`]);
    if (profile.frames) rows.push(["Model frame", utcMinuteLabel(profile.frames.startValidAt)]);

    // The field over this place, from the eccentric dipole. This is what makes
    // the South Atlantic Anomaly a NUMBER rather than a shape somebody drew:
    // click over Brazil and the field strength is visibly lower than anywhere
    // else at that latitude, because of where the dipole actually sits.
    const dipole = eccentricDipole(decimalYear(this.simulationTime()));
    const fieldNt = eccentricDipoleFieldNt(dipole, profile.latitudeDeg, profile.longitudeDeg, 500);
    const shell = eccentricDipoleShell(dipole, profile.latitudeDeg, profile.longitudeDeg, 500);
    rows.push(["Field at 500 km", `${(fieldNt / 1000).toFixed(1)} µT`]);
    rows.push(["L shell at 500 km", shell.toFixed(2)]);
    byId("probe-readings").replaceChildren(...rows.map((row) => factCell(row)));
  }

  /**
   * The published ground-station record for the open spacecraft, from the
   * spacecraft's side. Renders nothing at all when no operator has published a
   * link for it: absence has to look like ordinary absence rather than a "no
   * known stations" finding, which is a claim this site cannot make.
   */
  private renderStationLinksForSelected() {
    const card = this.selectedCard;
    const index = this.selectedIndex;
    if (!card || index === null) return;
    // The BLOCK hides, and nothing around it: the station list now sits
    // inside Satellite Details, directly above that section's two full-width
    // actions. Only the list is contingent on somebody having published a
    // link; the ground-track map below it is available for every spacecraft.
    const section = card.querySelector<HTMLElement>("[data-card-station-block]");
    const host = card.querySelector<HTMLElement>("[data-card-stations]");
    if (!section || !host) return;
    const satellite = this.catalog.satellites[index];
    const pairs = satellite ? this.groundStations?.stationsForSatellite(satellite.id) ?? [] : [];
    section.hidden = pairs.length === 0;
    if (pairs.length === 0) {
      host.replaceChildren();
      return;
    }
    host.replaceChildren(...pairs.map(({ station, link }) => {
      const entry = document.createElement("article");
      entry.className = "station-link";
      const name = document.createElement("strong");
      name.textContent = `${station.name} · ${station.country}`;
      const role = document.createElement("em");
      role.textContent = link.relationshipLabel;
      const evidence = document.createElement("p");
      // The publisher's own sentence, always shown. This site never
      // paraphrases the claim that makes the relationship.
      evidence.textContent = link.evidence;
      const source = document.createElement("a");
      source.href = link.source;
      source.textContent = `${link.sourceName} ↗`;
      source.rel = "noreferrer noopener";
      source.target = "_blank";
      entry.append(name, role, evidence, source);
      return entry;
    }));
  }

  /**
   * The orbit-manoeuvre browser, in a dialog, with its bundle fetched here on
   * the first open rather than at manifest load.
   *
   * The bundle is 2.4 MB gzipped — larger than the whole satellite catalogue —
   * and opening one object then pulls a 1.4 MB history shard on top of it. That
   * is affordable behind a button and would not be affordable on every visit,
   * which is why `manifest.orbitEvents` alone decides whether the button is
   * shown and no byte is spent making that decision.
   */
  private async openOrbitHistory(risingNow = false): Promise<void> {
    const record = this.manifest.orbitEvents;
    if (!record) return;
    const satellite = this.selectedIndex === null ? null : this.catalog.satellites[this.selectedIndex];
    const dialog = byId<HTMLDialogElement>("orbit-history-dialog");
    const host = byId("orbit-history-host");
    if (!this.orbitEvents) {
      host.textContent = "Loading the orbit archive… this is a large download and happens once.";
      if (!dialog.open) dialog.showModal();
    }
    const bundle = await this.loadOrbitEvents(record.path);
    if (!bundle) {
      host.textContent = "The orbit archive could not be loaded. Nothing is shown rather than a partial history.";
      if (!dialog.open) dialog.showModal();
      return;
    }
    const shards = this.manifest.orbitHistory?.shards ?? [];
    mountOrbitHistoryBrowser(host, {
      bundle,
      initialNorad: risingNow ? null : satellite?.id ?? null,
      catalogNames: new Map(this.catalog.satellites.map(object => [object.id, object.name])),
      loadDrift: this.manifest.orbitDrift ? () => loadOrbitDrift(this.manifest.orbitDrift!.path) : undefined,
      // The manifest owns the shard count and the content-addressed paths; the
      // browser never derives either.
      shardCount: this.manifest.orbitHistory?.shardCount,
      loadObject: async (norad) => {
        const ref = this.manifest.orbitPlotViews?.objects.find(entry => entry.norad === norad);
        if (!ref) return null;
        try {
          const object = await fetchPlotObject(`data/${ref.path}`);
          return { schema: 1, shard: norad % (this.manifest.orbitHistory?.shardCount ?? 256),
            shardCount: this.manifest.orbitHistory?.shardCount ?? 256, objects: [object] };
        } catch (error) { console.error("Small history view unavailable", error); return null; }
      },
      loadShard: async (index) => {
        if (this.orbitShardCache.has(index)) return this.orbitShardCache.get(index) ?? null;
        const shard = shards.find((entry) => entry.shard === index);
        if (!shard) {
          this.orbitShardCache.set(index, null);
          return null;
        }
        const manifestUrl = new URL("data/manifest.json", document.baseURI);
        try {
          const loaded = await fetchJson<OrbitHistoryShard>(artifactUrl(manifestUrl, shard.path));
          this.orbitShardCache.clear();
          this.orbitShardCache.set(index, loaded);
          return loaded;
        } catch (error) {
          console.error("Orbit-history shard could not be loaded", error);
          // WHICH failure, not just THAT one. These URLs no longer resolve on
          // this host: Caddy proxies them to the archive server on bigmem, and
          // answers 502/503/504 when that machine is not there. That is a
          // statement about a machine; a 404 or a parse failure is a statement
          // about the file. The reader is told the right one of those.
          const offline = error instanceof HttpStatusError
            && isArchiveOfflineStatus(error.status);
          const result = offline ? ARCHIVE_OFFLINE : null;
          this.orbitShardCache.set(index, result);
          return result;
        }
      },
      onSelect: (norad) => this.selectSatelliteByNorad(norad),
    });
    if (!dialog.open) dialog.showModal();
  }

  private loadOrbitEvents(path: string): Promise<OrbitEventsBundle | null> {
    if (this.orbitEvents) return Promise.resolve(this.orbitEvents);
    if (this.orbitEventsLoading) return this.orbitEventsLoading;
    const manifestUrl = new URL("data/manifest.json", document.baseURI);
    this.orbitEventsLoading = fetchJson<OrbitEventsBundle>(artifactUrl(manifestUrl, path))
      .then((bundle) => {
        this.orbitEvents = bundle;
        return bundle;
      })
      .catch((error: unknown) => {
        console.error("Orbit-events artifact could not be loaded", error);
        return null;
      })
      .finally(() => {
        this.orbitEventsLoading = null;
      });
    return this.orbitEventsLoading;
  }

  /** Follow the browser's own selection back onto the globe, by catalog id. */
  private selectSatelliteByNorad(norad: number) {
    const index = this.catalog.satellites.findIndex((satellite) => satellite.id === norad);
    if (index >= 0) this.selectSatellite(index, true);
  }

  /**
   * Ground magnetic perturbation: the dB/dt field a magnetometer on the
   * surface would see.
   *
   * This layer was built, tested and merged, and then sat unreachable: nothing
   * on the page fetched it, so it had zero entry points and no visitor could
   * ever have seen it. `tests/ground-perturbation-reachability.test.ts` walks
   * the chain from the module out to the checkbox for exactly that reason.
   *
   * Absent artifact is a normal release, not a failure - `groundField` is
   * optional in the manifest, the same as `drap` and `aurora` - so the layer
   * reports itself unavailable rather than drawing a substitute.
   */
  /**
   * The neutral atmosphere: the field that decides satellite drag.
   *
   * Optional in the manifest like every other model layer, so a release
   * built while NOAA's archive was unreachable reports the layer
   * unavailable instead of drawing a substitute.
   */
  private loadThermosphere(): Promise<void> {
    // Two models, two artifacts, and the layer is alive if EITHER is. NOAA WAM
    // is one file covering about twelve hours; NRLMSIS is a set of six-hour
    // shards covering the whole slider, and only the shards the clock reaches
    // are ever fetched. A release built while NOAA's WAM archive was
    // unreachable still draws the empirical field rather than nothing, and
    // says which it is drawing.
    void this.ensureThermosphereShards();
    if (this.thermosphereBundle) return Promise.resolve();
    if (this.thermosphereLoading) return this.thermosphereLoading;
    const record = this.manifest.thermosphere;
    if (!record) {
      // No WAM in this release is not a dead layer any more. It is only dead
      // if the empirical set is missing too.
      this.thermosphereLoadFailed = !this.manifest.thermosphereEmpirical;
      if (this.thermosphereLoadFailed) this.globe.setLayer("thermosphere", false);
      this.updateEnvironmentLegend();
      return Promise.resolve();
    }
    this.thermosphereLoadFailed = false;
    this.updateEnvironmentLegend();
    const manifestUrl = new URL("data/manifest.json", document.baseURI);
    this.thermosphereLoading = fetchJson<ThermosphereBundle>(artifactUrl(manifestUrl, record.path))
      .then((bundle) => {
        this.thermosphereBundle = bundle;
        this.applyThermosphereFrame();
        this.updateEnvironmentLegend();
      })
      .catch((error: unknown) => {
        console.error("Thermosphere artifact could not be loaded", error);
        // Only fatal if the empirical set cannot stand in. It covers ten times
        // the timeline WAM does, so losing WAM costs fidelity over twelve
        // hours, not the layer.
        this.thermosphereLoadFailed = !this.manifest.thermosphereEmpirical;
        if (this.thermosphereLoadFailed) this.globe.setLayer("thermosphere", false);
        this.updateEnvironmentLegend();
      })
      .finally(() => {
        this.thermosphereLoading = null;
      });
    return this.thermosphereLoading;
  }

  /**
   * Fetch the empirical shards the clock can reach, and no others.
   *
   * `shardsNear` widens the window by half a cadence at each end, so the shard
   * holding the NEXT hour is fetched before the clock needs it — without that,
   * the last fifteen minutes of every six-hour block would draw NO DATA even
   * though the frame exists, twenty times across the timeline.
   *
   * A shard that fails is remembered as failed and not retried on every clock
   * tick: four attempts a second against a 404 is a denial of service aimed at
   * our own origin.
   */
  private ensureThermosphereShards(at: Date = this.simulationTime()): Promise<void> {
    const record = this.manifest.thermosphereEmpirical;
    if (!record?.shards?.length) return Promise.resolve();
    const halfCadence = ((record.cadenceMinutes || 60) * 60_000) / 2;
    const wanted = shardsNear(record.shards, at, halfCadence);
    const manifestUrl = new URL("data/manifest.json", document.baseURI);
    const pending: Promise<void>[] = [];
    for (const shard of wanted) {
      if (this.thermosphereShards.has(shard.path) || this.thermosphereShardFailed.has(shard.path)) continue;
      const already = this.thermosphereShardLoading.get(shard.path);
      if (already) {
        pending.push(already);
        continue;
      }
      const load = fetchJson<EmpiricalThermosphereShard>(artifactUrl(manifestUrl, shard.path))
        .then((loaded) => {
          this.thermosphereShards.set(shard.path, loaded);
          this.applyThermosphereFrame();
          this.updateEnvironmentLegend();
        })
        .catch((error: unknown) => {
          console.error("Empirical thermosphere shard could not be loaded", shard.path, error);
          this.thermosphereShardFailed.add(shard.path);
          this.updateEnvironmentLegend();
        })
        .finally(() => {
          this.thermosphereShardLoading.delete(shard.path);
        });
      this.thermosphereShardLoading.set(shard.path, load);
      pending.push(load);
    }
    return Promise.all(pending).then(() => undefined);
  }

  /** Every empirical frame currently in memory that could serve one instant. */
  private empiricalThermosphereFrames(at: Date): EmpiricalThermosphereShard | null {
    const record = this.manifest.thermosphereEmpirical;
    if (!record?.shards?.length) return null;
    const halfCadence = ((record.cadenceMinutes || 60) * 60_000) / 2;
    const loaded = shardsNear(record.shards, at, halfCadence)
      .map((shard) => this.thermosphereShards.get(shard.path))
      .filter((shard): shard is EmpiricalThermosphereShard => shard !== undefined);
    if (loaded.length === 0) return null;
    if (loaded.length === 1) return loaded[0]!;
    // Two shards meet at this instant. Selecting across the union is what makes
    // the boundary between them invisible — which is the ONE seam in this layer
    // that should be invisible, because both sides of it are the same model.
    return {
      ...loaded[0]!,
      frames: loaded.flatMap((shard) => shard.frames),
      frameCount: loaded.reduce((total, shard) => total + shard.frameCount, 0),
    };
  }

  /**
   * Draw the frame nearest the simulation time, and only if one is close.
   *
   * Frames are hourly, so anything more than half an hour away is a
   * different atmosphere; drawing it would quietly show the wrong hour
   * rather than admitting the release does not cover this moment.
   */
  /**
   * Pick the published frame nearest the selected time, and REDRAW WHEN IT
   * CHANGES.
   *
   * This used to be called from exactly one place — the `.then()` after the
   * artifact downloaded — so the layer chose a frame at load and then never
   * moved again. Sean, correctly: "why doesn't the thermosphere change with
   * time? Why is it a static field?" The bundle carries 13 hourly frames over
   * about twelve hours, and the layer's own rail line promises "the height that
   * climbs in a storm", so a frozen field was the one thing it must not be.
   *
   * The re-decode is guarded on the CHOSEN FRAME rather than on the clock: the
   * clock ticks many times a second and a frame lasts an hour, so decoding on
   * every tick would unpack a 1.4 MB artifact for a picture that cannot have
   * changed. Guarding on `validAt` means the work happens once per frame
   * boundary crossed, which is also exactly when the drawn field should move.
   */
  private applyThermosphereFrame(): void {
    const bundle = this.thermosphereBundle;
    const at = this.simulationTime();
    // Fetch what this instant needs before choosing, so scrubbing into a shard
    // that is not in memory starts the download rather than silently drawing
    // nothing until something else happens to ask.
    void this.ensureThermosphereShards(at);
    const empirical = this.empiricalThermosphereFrames(at);
    if ((!bundle || bundle.frames.length === 0) && !empirical) return;
    const chosen = chooseThermosphereFrame(
      bundle && bundle.frames.length > 0 ? bundle : null,
      empirical,
      at,
    );
    const best = chosen?.frame ?? null;

    // OUT OF COVERAGE MEANS DRAW NOTHING, and this branch is the second half
    // of the same defect as the missing redraw above.
    //
    // It used to be a bare `return`, which left the last frame it happened to
    // choose standing in the scene. The timeline reaches 48 hours back and 72
    // forward -- 120 hours -- and a WAM release covers five or six, so for
    // about 95% of the slider the layer was showing an hour the reader was not
    // asking for and saying MODEL while it did. Measured on the shipped build:
    // at 06:00Z, twelve hours before the release began, the sky-annulus mean
    // brightness was 40.9 against 43.3 at a covered instant, and the card badge
    // still read MODEL. Clearing hands the legend a null surface, which is what
    // flips the card to NO DATA and puts up the "go to a time this layer
    // covers" jump the aurora and D-RAP layers already offer.
    if (!best) {
      // Rewritten as the clock moves through the gap, not only on the way in.
      // The card names the instant picked and explains which EDGE of the window
      // was passed, so a reader scrubbing from before the release to after it
      // would otherwise be reading the first explanation at the far end.
      const minute = at.toISOString().slice(0, 16);
      if (this.thermosphereFrameValidAt === null && this.thermosphereGapMinute === minute) return;
      this.thermosphereGapMinute = minute;
      this.thermosphereFrameValidAt = null;
      this.thermosphereDecoded = null;
      this.thermosphereSelection = null;
      this.globe.clearThermosphereFrame();
      this.markThermosphereFrameDrawn(null, null);
      this.updateEnvironmentLegend();
      return;
    }

    this.thermosphereGapMinute = null;
    // Guarded on the MODEL as well as the hour. Crossing from NOAA's WAM into
    // the empirical field can land on a frame with a different `validAt` -- but
    // it need not, and a reader who scrubs out of WAM coverage onto an hour
    // NRLMSIS publishes at the same instant must see the picture and the badge
    // change together. Guarding on the timestamp alone would leave WAM's field
    // on screen under an EMPIRICAL badge, which is the same class of lie the
    // stale-frame defect was.
    if (best.validAt === this.thermosphereFrameValidAt
      && chosen!.model === this.thermosphereSelection?.model) return;
    this.thermosphereFrameValidAt = best.validAt;
    this.thermosphereSelection = chosen;
    const decoded = decodeThermosphereFrame(best);
    this.thermosphereDecoded = decoded;
    this.globe.setThermosphereFrame(decoded);
    this.markThermosphereFrameDrawn(best.validAt, chosen!.model);
    // The card quotes the drawn hour and the heights read off it, so it has to
    // be rewritten when the hour changes -- otherwise crossing a frame boundary
    // moves the picture and leaves the numbers beside it describing the hour
    // before.
    this.updateEnvironmentLegend();
  }

  /**
   * Publish WHICH frame is on screen, as an attribute on the layer's own
   * switch.
   *
   * Same device as `data-magnetopause-surface` on the boundary checkbox, and
   * for a stronger reason. This layer has been reported static four times and
   * declared fixed twice, and every one of those verifications argued from
   * pixels: a crop that included the globe changed because the Earth turns, a
   * crop outside the glow was black in every frame, and a `getImageData`
   * readback measured nothing at all because the WebGL context is not created
   * with `preserveDrawingBuffer`. A rotating picture can fake a change and a
   * badly chosen crop can hide one; the identity of the frame handed to the
   * renderer can do neither. Absent means nothing is drawn, which is now a real
   * state rather than a stale picture.
   */
  private markThermosphereFrameDrawn(validAt: string | null, model: string | null): void {
    const toggle = document.getElementById("layer-thermosphere");
    if (!toggle) return;
    if (validAt) toggle.setAttribute("data-thermosphere-frame", validAt);
    else toggle.removeAttribute("data-thermosphere-frame");
    // WHICH MODEL, published beside which hour, for the same reason the hour is
    // published at all: with two fields on one timeline, "the picture changed"
    // is no longer enough to know the right thing is on screen. A test can now
    // assert that scrubbing across the boundary changes the model, and that it
    // changes at the instant the badge does.
    if (model) toggle.setAttribute("data-thermosphere-model", model);
    else toggle.removeAttribute("data-thermosphere-model");
  }

  /**
   * What the air is doing to a satellite, as a number.
   *
   * Density alone does not answer "so what". Drag does: a = rho v^2 / (2 B),
   * where B is the ballistic coefficient. The catalogue does not hold B for
   * real objects, so this quotes a STATED reference spacecraft rather than
   * naming one whose true value is unknown -- `dragDecelerationMs2` requires
   * the coefficient as an argument for exactly that reason.
   *
   * The spread matters as much as the value. Sampling right round the globe at
   * one altitude gives the range of drag a satellite meets on a single orbit,
   * which is the "some regions are worse than others" fact, and in a storm both
   * the value and the spread climb together.
   */
  private thermosphereDragStats(): { label: string; value: string }[] {
    const frame = this.thermosphereDecoded;
    if (!frame) return [];
    const altitudeKm = THERMOSPHERE_DRAG_REFERENCE.altitudeKm;
    const speed = circularOrbitalSpeedMs(altitudeKm);
    let lowest = Number.POSITIVE_INFINITY;
    let highest = 0;
    for (let latitude = -80; latitude <= 80; latitude += 10) {
      for (let longitude = 0; longitude < 360; longitude += 15) {
        const density = densityKgM3(frame, latitude, longitude, altitudeKm);
        if (density === null || !Number.isFinite(density) || density <= 0) continue;
        if (density < lowest) lowest = density;
        if (density > highest) highest = density;
      }
    }
    if (highest <= 0 || !Number.isFinite(lowest)) return [];
    const peak = dragDecelerationMs2(highest, speed, THERMOSPHERE_DRAG_REFERENCE.ballisticCoefficientKgM2);
    return [
      { label: `DRAG ${altitudeKm} KM`, value: `${peak.toExponential(1)} m/s²` },
      { label: "VARIES BY", value: `${(highest / lowest).toFixed(1)}×` },
    ];
  }

  private loadGroundField(): Promise<void> {
    if (this.groundFieldBundle) return Promise.resolve();
    if (this.groundFieldLoading) return this.groundFieldLoading;
    const record = this.manifest.groundField;
    if (!record) {
      this.groundFieldLoadFailed = true;
      this.globe.setLayer("groundField", false);
      this.updateEnvironmentLegend();
      return Promise.resolve();
    }
    this.groundFieldLoadFailed = false;
    this.updateEnvironmentLegend();
    const manifestUrl = new URL("data/manifest.json", document.baseURI);
    this.groundFieldLoading = fetchJson<GroundFieldBundle>(artifactUrl(manifestUrl, record.path))
      .then((bundle) => {
        this.groundFieldBundle = bundle;
        this.globe.setGroundFieldModel(bundle);
        this.updateEnvironmentLegend();
      })
      .catch((error: unknown) => {
        console.error("Ground magnetic perturbation artifact could not be loaded", error);
        this.groundFieldLoadFailed = true;
        this.globe.setLayer("groundField", false);
        this.updateEnvironmentLegend();
      })
      .finally(() => {
        this.groundFieldLoading = null;
      });
    return this.groundFieldLoading;
  }

  private loadDrapModel(): Promise<void> {
    if (this.drapBundle) return Promise.resolve();
    if (this.drapLoading) return this.drapLoading;
    const record = this.manifest.drap;
    if (!record) {
      this.drapLoadFailed = true;
      byId("drap-note").textContent = "No verified D-RAP numeric artifact is available in this release. No substitute field is shown.";
      this.updateEnvironmentLegend();
      return Promise.resolve();
    }
    this.drapLoadFailed = false;
    byId("drap-note").textContent = "Loading exact NOAA D-RAP numeric frames…";
    this.updateEnvironmentLegend();
    const manifestUrl = new URL("data/manifest.json", document.baseURI);
    this.drapLoading = fetchJson<DrapBundle>(artifactUrl(manifestUrl, record.path))
      .then((bundle) => {
        this.drapBundle = bundle;
        this.globe.setDrapModel(bundle);
        this.updateSurfaceEnvironmentStatus(true);
      })
      .catch((error: unknown) => {
        console.error("NOAA D-RAP artifact could not be loaded", error);
        this.drapLoadFailed = true;
        byId("drap-note").textContent = "The verified D-RAP artifact could not be loaded. No synthetic or stale replacement is shown.";
        this.updateEnvironmentLegend();
      })
      .finally(() => {
        this.drapLoading = null;
        this.updateSurfaceEnvironmentStatus(true);
      });
    return this.drapLoading;
  }

  private loadAuroraHistoryModel(): Promise<void> {
    if (this.auroraHistoryBundle) return Promise.resolve();
    if (this.auroraHistoryLoading) return this.auroraHistoryLoading;
    const record = this.manifest.aurora;
    if (!record) {
      this.auroraHistoryLoadFailed = true;
      byId("aurora-note").textContent = "No verified rolling OVATION numeric artifact is available. The legacy current snapshot is not substituted on the timeline.";
      this.updateEnvironmentLegend();
      return Promise.resolve();
    }
    this.auroraHistoryLoadFailed = false;
    byId("aurora-note").textContent = "Loading exact NOAA OVATION frames for both hemispheres…";
    this.updateEnvironmentLegend();
    const manifestUrl = new URL("data/manifest.json", document.baseURI);
    this.auroraHistoryLoading = fetchJson<AuroraBundle>(artifactUrl(manifestUrl, record.path))
      .then((bundle) => {
        this.auroraHistoryBundle = bundle;
        this.globe.setAuroraHistoryModel(bundle);
        this.updateSurfaceEnvironmentStatus(true);
      })
      .catch((error: unknown) => {
        console.error("NOAA OVATION history artifact could not be loaded", error);
        this.auroraHistoryLoadFailed = true;
        byId("aurora-note").textContent = "The verified OVATION history could not be loaded. No image reconstruction or stale current field is shown.";
        this.updateEnvironmentLegend();
      })
      .finally(() => {
        this.auroraHistoryLoading = null;
        this.updateSurfaceEnvironmentStatus(true);
      });
    return this.auroraHistoryLoading;
  }

  private updateSurfaceEnvironmentStatus(force = false) {
    const drap = this.globe.getDrapSurfaceState();
    const aurora = this.globe.getAuroraHistoryState();
    const auroraSelection = this.auroraHistoryBundle
      ? selectAuroraFrame(this.auroraHistoryBundle, this.simulationTime())
      : null;
    const stateSignature = (state: EnvironmentSurfaceState | null) => state
      ? state.status === "ready"
        ? `ready:${state.validAt}:${state.observedAt ?? ""}:${Math.floor(state.ageMinutes)}`
        : state.status === "stale"
          ? `stale:${state.lastValidAt}:${Math.floor(state.ageMinutes)}`
          : `no-data:${state.reason}:${state.previousValidAt ?? ""}:${state.nextValidAt ?? ""}`
      : "unloaded";
    const signature = `${stateSignature(drap)}|${stateSignature(aurora)}|${auroraSelection?.available ? auroraSelection.selectionBasis : auroraSelection?.reason ?? "unloaded"}|${this.fieldRendering}`;
    if (!force && signature === this.lastSurfaceEnvironmentSignature) return;
    this.lastSurfaceEnvironmentSignature = signature;

    if (drap) {
      const status = this.surfaceLegendStatus(drap, false, this.drapLoadFailed);
      byId("drap-note").textContent = drap.status === "ready"
        ? `${drap.legend.condition?.summary ? `${drap.legend.condition.summary} ` : ""}${status.text} Valid ${drap.validAt.slice(0, 16).replace("T", " ")} UTC; unavailable timeline periods remain blank.`
        : status.text;
    }
    if (aurora) {
      const status = this.surfaceLegendStatus(aurora, false, this.auroraHistoryLoadFailed);
      byId("aurora-probability").textContent = auroraSelection?.available
        ? `${auroraSelection.frame.maximumProbabilityPercent}%`
        : "—";
      byId("aurora-note").textContent = aurora.status === "ready"
        ? `${status.text} Both official hemispheres · ${auroraSelection ? formatAuroraSelection(auroraSelection) : `valid ${aurora.validAt.slice(0, 16).replace("T", " ")} UTC`}.`
        : status.text;
    }
    this.updateEnvironmentLegend();
  }

  private loadIonosphereModel(): Promise<void> {
    if (this.ionosphereBundle) return Promise.resolve();
    if (this.ionosphereLoading) return this.ionosphereLoading;
    const record = this.manifest.ionosphereModel;
    if (!record) {
      this.ionosphereLoadFailed = true;
      this.globe.setIonosphereDataAvailable(false);
      byId("ionosphere-model-note").textContent = "No verified WAM-IPE bundle is in this release. A schematic replacement is not shown.";
      this.updateEnvironmentLegend();
      return Promise.resolve();
    }
    this.ionosphereLoadFailed = false;
    this.updateEnvironmentLegend();
    const manifestUrl = new URL("data/manifest.json", document.baseURI);
    this.ionosphereLoading = fetchJson<IonosphereVolumeBundle>(artifactUrl(manifestUrl, record.path))
      .then((bundle) => {
        this.ionosphereBundle = bundle;
        this.globe.setIonosphereModel(bundle);
        this.globe.setIonosphereRegionsEnabled(this.ionosphereRegionsOn);
        this.updateIonosphereSelection(this.simulationTime(), true);
        byId("ionosphere-model-note").textContent = `${bundle.model}. ${bundle.caveat}`;
      })
      .catch((error: unknown) => {
        console.error("WAM-IPE ionosphere model could not be loaded", error);
        this.ionosphereLoadFailed = true;
        this.globe.setIonosphereDataAvailable(false);
        byId("ionosphere-model-note").textContent = "The verified WAM-IPE sequence could not be loaded. No synthetic replacement is shown.";
        this.updateEnvironmentLegend();
      })
      .finally(() => {
        this.ionosphereLoading = null;
      });
    this.updateEnvironmentLegend();
    return this.ionosphereLoading;
  }

  private updateIonosphereSelection(time: Date, force = false) {
    const bundle = this.ionosphereBundle;
    if (!bundle) return;
    const selection = selectIonosphereFrames(bundle, time);
    const available = selection.state === "within";
    this.globe.setIonosphereDataAvailable(available);
    const surfaceState = this.globe.getIonosphereSurfaceState();
    const f2Time = surfaceState?.regions.f2.validAt;
    // The probe answers for a time as much as for a place, so it follows the
    // timeline rather than freezing at whatever moment it was opened. It is
    // refreshed BEFORE the signature gate below: that gate asks whether the
    // rendered FRAMES changed, and the probe interpolates between them, so its
    // numbers move with the blend while the signature stays put.
    if (this.probePoint) this.renderProbe();
    const signature = `${selection.state}:${selection.startIndex}:${selection.endIndex}:${f2Time?.start ?? ""}:${f2Time?.end ?? ""}`;
    if (!force && signature === this.ionosphereSelectionSignature) return;
    this.ionosphereSelectionSignature = signature;
    this.updateEnvironmentLegend();
  }

  private loadGeospaceModel(): Promise<void> {
    if (this.geospaceLoaded) return Promise.resolve();
    if (this.geospaceLoading) return this.geospaceLoading;
    const record = this.manifest.geospace;
    if (!record) {
      byId("geospace-note").textContent = "The site will not substitute a decorative model when the verified NOAA bundle is unavailable.";
      return Promise.resolve();
    }
    const manifestUrl = new URL("data/manifest.json", document.baseURI);
    this.geospaceLoading = fetchJson<GeospaceBundle>(artifactUrl(manifestUrl, record.path))
      .then((bundle) => {
        this.globe.setGeospaceModel(bundle);
        this.geospaceBundle = bundle;
        this.geospaceLoaded = true;
        this.configureRadiationControls();
        this.updateGeospaceRuntimeUi(true);
        byId("geospace-note").textContent = `${bundle.model}. ${bundle.caveat}`;
      })
      .catch((error: unknown) => {
        console.error("NOAA geospace model could not be loaded", error);
        byId("geospace-note").textContent = "The verified NOAA model sequence could not be loaded. No synthetic replacement is shown.";
      })
      .finally(() => {
        this.geospaceLoading = null;
        this.updateEnvironmentLegend();
      });
    return this.geospaceLoading;
  }

  /**
   * Adopt a newer published release without losing the visitor's place.
   *
   * bigmem republishes roughly every five minutes, but before this was wired up
   * the page read its manifest exactly once at boot. A tab left open longer than
   * an artifact's coverage window therefore aged out of its own data and
   * honestly reported "NO DATA FOR SELECTED UTC" — most visibly on the
   * radiation belts, whose geospace bundle spans only about 100 minutes.
   */
  private startArtifactRefresh() {
    if (this.artifactRefresh) return;
    this.artifactRefresh = new ArtifactRefreshController<ReleaseManifest>({
      manifestUrl: new URL("data/manifest.json", document.baseURI),
      initialManifest: this.manifest,
      intervalMs: artifactRefreshIntervalMs(),
      onArtifactsChanged: (update) => this.applyArtifactRefresh(update),
      onStatus: (status) => this.handleArtifactRefreshStatus(status),
    });
    this.artifactRefresh.start();
  }

  /**
   * Swap in whichever artifacts actually changed.
   *
   * If any single artifact fails to load we rethrow after restoring that one
   * manifest record. The controller then leaves its last-known-good manifest
   * where it is, so the next cycle retries the failure instead of silently
   * stranding a layer whose legend would otherwise describe a release its data
   * no longer comes from.
   */
  private async applyArtifactRefresh(update: ArtifactRefreshUpdate<ReleaseManifest>): Promise<void> {
    const previousManifest = this.manifest;
    // Point the lazy loaders at the new release first: a layer the visitor has
    // never opened needs no fetch here, only the new path when they do open it.
    this.manifest = update.manifest;
    const failures: string[] = [];
    for (const change of update.changes) {
      if (update.signal.aborted) return;
      try {
        await this.hotSwapArtifact(change.key, update.signal);
      } catch (error) {
        if (update.signal.aborted) return;
        console.error(`Live refresh could not adopt the new ${change.key} artifact`, error);
        failures.push(change.key);
        this.manifest = restoreArtifactRecord(this.manifest, previousManifest, change.key);
      }
    }
    if (failures.length > 0) {
      throw new Error(`artifact refresh could not adopt: ${failures.join(", ")}`);
    }
  }

  /**
   * Replace one artifact in place.
   *
   * Two rules keep this safe. The replacement is fetched BEFORE the bundle in
   * hand is discarded, so a transient network failure leaves a working layer
   * untouched rather than blanking it. And a layer the visitor has not loaded is
   * left alone entirely. Selected UTC, selected satellite, layer toggles, and
   * display settings all live in fields this method never writes, so the
   * visitor's place survives the swap.
   *
   * Returns true when a live bundle was actually replaced.
   */
  private async hotSwapArtifact(key: string, signal: AbortSignal): Promise<boolean> {
    const manifestUrl = new URL("data/manifest.json", document.baseURI);
    const fetchArtifact = <T>(path: string): Promise<T> =>
      fetchJson<T>(artifactUrl(manifestUrl, path), { signal });

    switch (key) {
      case "spaceWeather": {
        const record = this.manifest.spaceWeather;
        if (!record) return false;
        const bundle = await fetchArtifact<SpaceWeatherBundle>(record.path);
        if (signal.aborted) return false;
        this.weather = bundle;
        this.globe.updateTec(bundle.ionosphere.points, bundle.ionosphere.tecRange);
        this.globe.setMagnetopause(this.magnetopauseDriverAt(this.simulationTime()));
        this.globe.setSolarWindConditions(bundle.solarWind.speedKps, bundle.solarWind.densityCm3);
        this.globe.setPhotonFlux(bundle.xray.fluxWm2);
        this.updateWeatherReadout();
        this.updateDataStatus();
        // Driver-sampled visuals recompute from the new series on the next tick.
        this.lastEnvironmentSignature = "";
        this.lastSurfaceEnvironmentSignature = "";
        // The strip chart is gated on the storm block's own validity time, and
        // a swap can land a block with the same one; clear it so a replaced
        // artifact always redraws.
        this.lastStormPanelSignature = "";
        this.updateStormPanel(this.simulationTime());
        return true;
      }
      case "geospace": {
        if (this.geospaceLoading) await this.geospaceLoading;
        if (!this.geospaceLoaded) return false;
        const record = this.manifest.geospace;
        if (!record) return false;
        const bundle = await fetchArtifact<GeospaceBundle>(record.path);
        if (signal.aborted) return false;
        this.globe.setGeospaceModel(bundle);
        this.geospaceBundle = bundle;
        this.configureRadiationControls();
        this.updateGeospaceRuntimeUi(true);
        byId("geospace-note").textContent = `${bundle.model}. ${bundle.caveat}`;
        return true;
      }
      case "ionosphereModel": {
        if (this.ionosphereLoading) await this.ionosphereLoading;
        if (!this.ionosphereBundle) return false;
        const record = this.manifest.ionosphereModel;
        if (!record) return false;
        const bundle = await fetchArtifact<IonosphereVolumeBundle>(record.path);
        if (signal.aborted) return false;
        this.ionosphereBundle = bundle;
        // The sampler caches frames DECODED FROM THE OLD BUNDLE. Keeping it
        // across a release would answer the probe from the previous artifact.
        this.ionosphereSampler = null;
        this.globe.setIonosphereModel(bundle);
        this.globe.setIonosphereRegionsEnabled(this.ionosphereRegionsOn);
        this.updateIonosphereSelection(this.simulationTime(), true);
        byId("ionosphere-model-note").textContent = `${bundle.model}. ${bundle.caveat}`;
        return true;
      }
      case "ionosondeSoundings": {
        // Soundings refresh every 5-15 minutes upstream, which is the cadence
        // this controller already polls at. Unlike the model column there is no
        // decoded cache to drop - the bundle IS the data - but an open probe
        // has to be redrawn, or it keeps showing the previous release's
        // sounding ages and they only get more wrong.
        const record = this.manifest.ionosondeSoundings;
        if (!record) return false;
        if (this.soundingLoading) await this.soundingLoading;
        if (!this.soundingBundle) return false;
        const bundle = await fetchArtifact<SoundingBundle>(record.path);
        if (signal.aborted) return false;
        this.soundingBundle = bundle;
        if (this.probePoint) this.renderProbe();
        return true;
      }
      case "drap": {
        if (this.drapLoading) await this.drapLoading;
        if (!this.drapBundle) return false;
        const record = this.manifest.drap;
        if (!record) return false;
        const bundle = await fetchArtifact<DrapBundle>(record.path);
        if (signal.aborted) return false;
        this.drapBundle = bundle;
        this.globe.setDrapModel(bundle);
        this.updateSurfaceEnvironmentStatus(true);
        return true;
      }
      case "aurora": {
        if (this.auroraHistoryLoading) await this.auroraHistoryLoading;
        if (!this.auroraHistoryBundle) return false;
        const record = this.manifest.aurora;
        if (!record) return false;
        const bundle = await fetchArtifact<AuroraBundle>(record.path);
        if (signal.aborted) return false;
        this.auroraHistoryBundle = bundle;
        this.globe.setAuroraHistoryModel(bundle);
        this.updateSurfaceEnvironmentStatus(true);
        return true;
      }
      // THE ONE ARTIFACT THAT WAS NEVER SWAPPED, and the tab-left-open half of
      // the defect the owner photographed. `loadPlasmasphere` returns early
      // once a sequence exists, so the DGCPM bundle was fetched at most once
      // per visit while the manifest beside it was re-fetched every five
      // minutes. A tab open across a publish therefore held frames stopping at
      // 12:00 UTC under a manifest saying 14:00, and the layer refused to draw
      // while its own notice quoted a frame that had in fact been published.
      case "plasmasphere": {
        if (this.plasmasphereLoading) await this.plasmasphereLoading;
        // Never opened this layer, so there is nothing in hand to replace; the
        // lazy loader will fetch the new path when the reader does open it.
        if (!this.plasmasphereSequence) return false;
        const record = this.manifest.plasmasphere;
        if (!record) return false;
        const bundle = await fetchArtifact<DgcpmBundle>(record.path);
        if (signal.aborted) return false;
        // Decoded BEFORE the sequence in hand is discarded: a structurally bad
        // bundle throws here and leaves the working layer untouched, which is
        // the same rule every other swap above follows.
        const sequence = decodeDgcpmSequence(bundle);
        this.plasmasphereSequence = sequence;
        // Both layers this artifact drives are re-evaluated in one call, so
        // they cannot end up on different frames.
        this.updateInnerMagnetosphere(this.simulationTime());
        this.updateEnvironmentLegend();
        return true;
      }
      default:
        return false;
    }
  }

  /**
   * Plain-language account of the live refresh, shown in the data-status
   * tooltip. It never claims data is current when the last check failed.
   */
  private artifactRefreshSummary(): string {
    const adopted = this.lastArtifactAdoptionAt === null
      ? "No newer release has been adopted in this visit yet."
      : `Newer data last adopted at ${new Date(this.lastArtifactAdoptionAt).toISOString().slice(11, 16)} UTC.`;
    switch (this.artifactRefreshPhase) {
      case "error":
        return `Live update check FAILED; the last verified bundle stays on screen. ${adopted}`;
      case "paused":
        return `Live updates pause while this tab is hidden. ${adopted}`;
      case "stopped":
        return `Live updates are stopped. ${adopted}`;
      case "checking":
        return `Checking for a newer published release… ${adopted}`;
      default:
        return `Checks for a newer published release every five minutes. ${adopted}`;
    }
  }

  private handleArtifactRefreshStatus(status: ArtifactRefreshStatus<ReleaseManifest>) {
    this.artifactRefreshPhase = status.phase;
    if (status.phase === "updated") this.lastArtifactAdoptionAt = status.checkedAt;
    if (status.phase === "error") {
      console.warn(
        "Live data refresh could not complete; the last verified bundle stays on screen",
        status.error,
      );
    }
    this.updateDataStatus();
  }

  /**
   * Populate the RBE pitch control.
   *
   * The layer opens on one channel — the trapped, near-90° one, which is the
   * population that actually forms the belts. Every published channel stays in
   * this list, and so does the stacked "all channels" reconstruction; it is one
   * selection away rather than the thing a first-time visitor is shown.
   */
  private configureRadiationControls() {
    const choices = this.globe.getRadiationChoices();
    const select = byId<HTMLSelectElement>("radiation-pitch-select");
    if (!choices || choices.pitchCoordinatesSin.length === 0) {
      select.disabled = true;
      return;
    }
    const optionCount = Math.min(choices.pitchCoordinatesSin.length, choices.pitchAnglesDegrees.length);
    const trappedIndex = trappedPitchIndex(choices.pitchCoordinatesSin.slice(0, optionCount));
    const requested = this.currentRadiationPitchIndex ?? OMNIDIRECTIONAL_RADIATION_PITCH;
    const selectedIndex = requested === ALL_RADIATION_PITCH_CHANNELS || requested === OMNIDIRECTIONAL_RADIATION_PITCH
      ? requested
      : Math.max(0, Math.min(requested, optionCount - 1));
    const options = Array.from({ length: optionCount }, (_, index) => {
      const option = document.createElement("option");
      const coordinate = choices.pitchCoordinatesSin[index]!;
      const angle = choices.pitchAnglesDegrees[index]!;
      option.value = String(index);
      option.textContent = `sin(α) ${coordinate.toFixed(5)} · ${angle.toFixed(1)}°${index === trappedIndex ? " · trapped" : ""}`;
      return option;
    });
    const omnidirectionalOption = document.createElement("option");
    omnidirectionalOption.value = String(OMNIDIRECTIONAL_RADIATION_PITCH);
    omnidirectionalOption.textContent = `Omnidirectional \u2014 all ${optionCount} channels integrated`;
    const allOption = document.createElement("option");
    allOption.value = String(ALL_RADIATION_PITCH_CHANNELS);
    allOption.textContent = `All ${optionCount} published channels (stacked)`;
    select.replaceChildren(omnidirectionalOption, ...options, allOption);
    select.disabled = false;
    select.value = String(selectedIndex);
    this.currentRadiationPitchIndex = selectedIndex;
    this.globe.setRadiationPitchIndex(selectedIndex);
  }

  private formatScaleEndpoint(value: number, scale: "linear" | "log10") {
    return scale === "log10" ? `10^${this.formatScaleValue(value)}` : this.formatScaleValue(value);
  }

  private formatRadiationEnergy(energyKev: number) {
    // The combined view is not a channel and has no energy to print; it says
    // what it is instead of printing a sentinel number as if it were one.
    if (isCombinedRadiationEnergy(energyKev)) return "ALL ENERGIES (COMBINED)";
    return energyKev < 1000 ? `${energyKev.toFixed(0)} keV` : `${(energyKev / 1000).toFixed(2)} MeV`;
  }

  private formatScaleValue(value: number) {
    if (value !== 0 && (Math.abs(value) < 0.01 || Math.abs(value) >= 10_000)) return value.toExponential(1);
    if (Math.abs(value) < 0.1) return value.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
    if (Math.abs(value) < 10) return value.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
    return value.toLocaleString(undefined, { maximumFractionDigits: 1 });
  }

  private formatGeospaceUtc(value: string) {
    const date = new Date(value);
    return Number.isFinite(date.getTime()) ? date.toISOString().slice(5, 16).replace("T", " ") : "UNAVAILABLE";
  }

  private geospaceFrameDescription(state: GeospaceRuntimeReadyState) {
    const [lower, upper] = state.sourceFrames;
    const lead = state.leadMinutes === 0 ? "ANALYSIS" : `LEAD +${state.leadMinutes}M`;
    const source = lower === upper
      ? `SOURCE ${this.formatGeospaceUtc(lower)}Z`
      : `SOURCE ${this.formatGeospaceUtc(lower)}Z → ${this.formatGeospaceUtc(upper)}Z · INTERPOLATION ${Math.round(state.interpolationFraction * 100)}%`;
    const hold = state.edgeHoldMinutes > 0
      ? ` · LATEST FRAME HELD ${Math.max(1, Math.round(state.edgeHoldMinutes))}M FOR MODEL LATENCY`
      : "";
    return `RUN ${this.formatGeospaceUtc(state.runAt)}Z · VALID ${this.formatGeospaceUtc(state.structureFrameValidAt)}Z · ${lead} · ${source}${hold}`;
  }

  private geospaceCoverage(state: GeospaceRuntimeFrameState | null) {
    const coverage = state?.status === "no-data" ? state.coverage : null;
    const validFrom = coverage?.validFrom ?? this.manifest.geospace?.validFrom;
    const validTo = coverage?.validTo ?? this.manifest.geospace?.validTo;
    if (!validFrom || !validTo) return undefined;
    return `${this.formatGeospaceUtc(validFrom)}Z–${this.formatGeospaceUtc(validTo)}Z · ${this.manifest.geospace?.frameCount ?? this.geospaceBundle?.frames.length ?? 0} source frames`;
  }

  private updateGeospaceRuntimeUi(force = false) {
    const state = this.globe.getGeospaceRuntimeState();
    const metadata = this.globe.getGeospaceLegendMetadata();
    if (!state || !metadata) {
      if (force) this.updateEnvironmentLegend();
      return;
    }
    const stateSignature = state.status === "ready"
      ? `${state.sourceFrames.join(":")}:${Math.round(state.interpolationFraction * 100)}:${state.structureFrameValidAt}:${state.runAt}:${state.leadMinutes}:${Math.round(state.edgeHoldMinutes)}`
      : `${state.reason}:${Math.floor(Date.parse(state.requestedAt) / 60_000)}:${state.coverage.validFrom}:${state.coverage.validTo}`;
    const radiationSignature = metadata.radiation
      ? `${metadata.radiation.energyKev}:${metadata.radiation.pitchIndex}:${metadata.radiation.view}`
      : "none";
    const signature = `${state.status}:${stateSignature}:${metadata.field.field}:${metadata.field.displayMode}:${metadata.field.plane}:${radiationSignature}`;
    if (!force && signature === this.geospaceUiSignature) return;
    this.geospaceUiSignature = signature;
    this.updateEnvironmentLegend();
  }

  private updateGeospaceFrame(validAt: string, leadMinutes: number, runAt: string) {
    void validAt;
    void leadMinutes;
    void runAt;
    this.updateGeospaceRuntimeUi();
  }

  private bindWelcomeAndAbout() {
    const welcome = byId<HTMLDialogElement>("welcome-dialog");
    const about = byId<HTMLDialogElement>("about-dialog");
    const preference = byId<HTMLInputElement>("welcome-hide");
    let openAboutAfterWelcome = false;
    byId("about-button").addEventListener("click", () => {
      if (!about.open) about.showModal();
    });
    byId("welcome-about").addEventListener("click", () => {
      openAboutAfterWelcome = true;
    });
    welcome.addEventListener("close", () => {
      if (preference.checked) storageSet("local", "space-explorer-hide-welcome-v1", "1");
      if (openAboutAfterWelcome) {
        openAboutAfterWelcome = false;
        window.setTimeout(() => about.showModal(), 0);
      }
    });
    const hiddenPermanently = storageGet("local", "space-explorer-hide-welcome-v1") === "1";
    const seenThisSession = storageGet("session", "space-explorer-welcome-seen-v1") === "1";
    if (!document.documentElement.dataset.deliveryEntered && !hiddenPermanently && !seenThisSession) {
      storageSet("session", "space-explorer-welcome-seen-v1", "1");
      window.setTimeout(() => {
        if (!welcome.open) welcome.showModal();
      }, 250);
    }
  }

  private updateDataStatus() {
    const status = byId("data-status");
    const ageMinutes = (Date.now() - new Date(this.weather.solarWind.observedAt).getTime()) / 60000;
    status.classList.remove("is-live", "is-stale");
    if (ageMinutes <= 20) {
      status.classList.add("is-live");
      status.lastChild!.textContent = ` NOAA data ${Math.max(0, Math.round(ageMinutes))} min old`;
    } else {
      status.classList.add("is-stale");
      status.lastChild!.textContent = ` Last verified bundle ${this.manifest.generatedAt.slice(11, 16)} UTC`;
    }
    status.title = `${this.catalog.selectionNote}\n\n${this.artifactRefreshSummary()}`;
  }

  private weatherTrackBound = false;

  private weatherIndexScroll = 0;

  /**
   * BROWSER BACK, INSIDE THE SITE.
   *
   * Until 2026-09-03 this file contained no pushState, no popstate and no hash
   * handling of any kind. Every navigation swapped `#content-body`'s innerHTML
   * and left the URL exactly as it was, so the whole visit was ONE history
   * entry: a reader four levels deep in a lesson who pressed Back left for
   * whatever site they were on beforehand. Sean: "it takes me out of the space
   * site completely and to the last website I was on before I went there."
   *
   * The fix is one entry per place a reader can be, addressed by hash rather
   * than by path. Hash was chosen deliberately: this bundle is served from
   * several prefixes (/space/, and /space/planner/ for the gated build) and a
   * path-based entry would have to agree with the server about every one of
   * them. A hash cannot 404 and cannot disagree with Caddy.
   *
   * `navApplying` is the guard that keeps this honest. Restoring a state calls
   * the same render paths a click does, and those paths push; without the flag
   * every Back would push a new entry and the reader would be trapped.
   */
  private navApplying = false;

  private navUrl(state: NavState): string {
    if (state.view === "explore") return "#/";
    return state.page ? `#/${state.view}/${state.page}` : `#/${state.view}`;
  }

  /** Record where the reader now is, unless we are replaying history. */
  private pushNav(state: NavState) {
    if (this.navApplying) return;
    const current = window.history.state as NavState | null;
    if (current && current.view === state.view && current.page === state.page) return;
    window.history.pushState(state, "", this.navUrl(state));
  }

  private navFromHash(): NavState {
    const raw = window.location.hash.replace(/^#\/?/, "");
    if (!raw) return { view: "explore" };
    // `noUncheckedIndexedAccess` is on, and a hand-edited hash really can be
    // empty between the slashes, so neither half is assumed to exist.
    const parts = raw.split("/").filter(Boolean);
    const view = parts[0] ?? "explore";
    const page = parts[1];
    return page ? { view, page } : { view };
  }

  /**
   * Put the reader back where a history entry says they were.
   *
   * Only ever called from popstate and from first paint, and always with the
   * guard up, so nothing in here adds an entry of its own.
   */
  private applyNav(state: NavState) {
    this.navApplying = true;
    try {
      if (!state || state.view === "explore") {
        this.closeContent();
        return;
      }
      this.openContent(state.view);
      // The events view addresses a replay by id rather than a lesson page, so
      // it restores the dialog instead of swapping the body's markup.
      if (state.view === "events") {
        const event = state.page
          ? this.events.events.find((item) => item.id === state.page)
          : undefined;
        if (event) this.openEventPlayer(event);
        else this.closeEventPlayer();
        return;
      }
      if (state.page) this.openTrackPage(state.view, state.page);
      else if (state.view.startsWith("learn-")) restoreChapterOpener(byId("content-body"), state.view);
    } finally {
      this.navApplying = false;
    }
  }

  /**
   * Render one lesson page inside whichever track owns it.
   *
   * The three tracks each had their own inline click handler that swapped the
   * markup; restoring a history entry needs the same swap without the click, so
   * the render half lives here and the handlers call it. The weather track
   * shows and hides two SIBLING elements instead of replacing one, which is why
   * it is not simply a third call to the same shape.
   */
  private openTrackPage(view: string, page: string) {
    const body = byId("content-body");
    rememberChapterOpener(body, view);
    if (view === "learn-orbits") {
      body.innerHTML = satelliteFundamentalsPageView(page);
      byId("content-view").scrollTop = 0;
      this.mountSatelliteFundamentals();
      focusChapterHeading(body);
      return;
    }
    if (view === "learn-layers") {
      this.stopLayerVideos();
      body.innerHTML = layerPageView(page);
      byId("content-view").scrollTop = 0;
      this.mountLayerPages();
      focusChapterHeading(body);
      return;
    }
    if (view === "learn-weather") {
      const index = byId("weather-index");
      const pageEl = byId("weather-page");
      this.stopLayerVideos();
      pageEl.innerHTML = ["dungey", "engine", "mechanisms"].includes(page) ? weatherPageView(page) : weatherLessonView(page);
      pageEl.hidden = false;
      index.hidden = true;
      byId("content-view").scrollTop = 0;
      focusChapterHeading(pageEl);
    }
  }

  private openContent(view: string) {
    if (view === "explore") {
      this.closeContent();
      this.pushNav({ view: "explore" });
      return;
    }
    window.clearInterval(this.eventTimer);
    this.eventReplay?.destroy();
    this.eventReplay = null;
    const contentView = byId("content-view");
    const body = byId("content-body");
    this.transitPlanner?.destroy();
    this.transitPlanner = null;
    // Leaving any page hands the NOAA panels back to their own markup, so the
    // "one copy in the document" rule holds no matter how the visitor leaves.
    this.returnOutlookPanels();
    if (view === "now") {
      body.innerHTML = currentConditionsView();
      this.mountCurrentConditions();
    }
    else if (view === "events") body.innerHTML = eventsView(this.events);
    else if (view === "learn-orbits") {
      body.innerHTML = satelliteFundamentalsIndexView();
      this.mountSatelliteFundamentals();
    }
    else if (view === "learn-weather") {
      body.innerHTML = weatherLessons();
      this.mountWeatherTrack();
    }
    else if (view === "learn-layers") {
      body.innerHTML = layerPagesIndexView();
      this.mountLayerPages();
    }
    else if (view === "learn-methods") {
      body.innerHTML = orbitMethodsPageView();
      mountOrbitMethods(body);
    }
    else if (view === "connections") body.innerHTML = connectionsView();
    else if (view === "transit") {
      body.replaceChildren();
      // The gated build is selected by the PATH the page was served from, not by
      // anything the browser can assert. Caddy only proxies /space/planner/ after
      // forward_auth accepts the session cookie, so reaching that path is itself
      // the proof. A visitor on the public path cannot ask for the gated build,
      // and a visitor who cannot authenticate never reaches the gated path at all.
      const gated = window.location.pathname.startsWith("/space/planner");
      this.transitPlanner = new TransitPlanner({
        container: body,
        catalog: this.catalog,
        land: this.land,
        audience: gated ? "gated" : "public",
      });
    }
    else {
      body.innerHTML = sourcesView();
      this.mountLayerStandingReadings();
    }
    contentView.hidden = false;
    contentView.scrollTop = 0;
    contentView.focus();
    mountLearningContents(body);
    focusChapterHeading(body);
    // WHICH NAV CELL LIGHTS UP. Usually the one whose view this is - but
    // "learn-layers" no longer has a cell of its own. Its door moved into Learn
    // space weather's contents spine on 2026-08-21 (nine of its ten pages are
    // that track's layers, and it is already labelled LEARNING TRACK 03 to that
    // page's 02), so the reader who is on it is inside track 02 and the bar has
    // to say so. Without this every cell goes muted and the top bar stops
    // answering "where am I" for one whole section of the site.
    const navView = view === "learn-layers" ? "learn-weather" : view;
    document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("is-active", (item as HTMLElement).dataset.view === navView));
    if (view === "events") this.bindEventCards();
    this.pushNav({ view });
  }

  /**
   * Bind the Satellite fundamentals chapter navigation.
   *
   * Same contract, and the same reason, as mountLayerPages() below: the
   * [data-view] sweep in the start-up binder runs once, so a button injected
   * into #content-body afterwards would never fire. These are bound every time
   * the markup is replaced, and replacing the markup is how the index and a
   * chapter swap places.
   *
   * data-fundamentals-goto is the "see it live" door. It routes through
   * openContent() rather than reaching into controls directly, so a recipe can
   * never leave the reader in a half-changed state, and "explore" simply
   * closes the content view and hands back the globe as the visitor left it.
   */
  private mountSatelliteFundamentals() {
    const body = byId("content-body");
    if (this.manifest) void mountDriftControls(body, this.manifest.orbitDrift?.path);
    body.querySelectorAll<HTMLAnchorElement>("[data-orbit-rising-open]").forEach(link => {
      link.addEventListener("click", event => {
        event.preventDefault();
        void this.openOrbitHistory(true);
      });
    });
    body.querySelectorAll<HTMLButtonElement>("[data-fundamentals-page]").forEach((button) => {
      button.addEventListener("click", () => {
        const page = button.dataset.fundamentalsPage ?? "";
        rememberChapterOpener(body, "learn-orbits", button);
        this.openTrackPage("learn-orbits", page);
        this.pushNav({ view: "learn-orbits", page });
      });
    });
    body.querySelectorAll<HTMLButtonElement>("[data-fundamentals-index]").forEach((button) => {
      button.addEventListener("click", () => {
        body.innerHTML = satelliteFundamentalsIndexView();
        byId("content-view").scrollTop = 0;
        this.mountSatelliteFundamentals();
        restoreChapterOpener(body, "learn-orbits");
        this.pushNav({ view: "learn-orbits" });
      });
    });
    body.querySelectorAll<HTMLButtonElement>("[data-fundamentals-goto]").forEach((button) => {
      button.addEventListener("click", () => this.openContent(button.dataset.fundamentalsGoto ?? "explore"));
    });
  }

  /**
   * Bind the Learn > Layers navigation.
   *
   * The [data-view] sweep in the start-up binder runs once, so a button
   * injected into #content-body afterwards would never fire - the same reason
   * layerCard() binds its own build link. These are therefore bound here, every
   * time the markup is replaced, and replacing the markup is how the index and
   * a layer page swap places.
   */
  /**
   * The space-weather track: an index, eight module pages and three long-form
   * pages, all inside one view.
   *
   * WHY THE INDEX IS HIDDEN RATHER THAN REPLACED. `energy-chain-view.ts` — a
   * separate entry point, owned by another agent — injects its "Follow the
   * energy on the live globe" launcher into this page by finding `.lesson-grid`
   * and inserting before it, once per click on the nav button. If opening a
   * module overwrote `#content-body`, coming back would render an index with
   * that door missing until the visitor re-navigated. So the index STAYS in the
   * document and the sub-page is a sibling; the launcher survives every trip in
   * and out. It also means returning from a module restores the reader's scroll
   * position in the index instead of dumping them at the top.
   *
   * One delegated listener, attached to `#content-body` exactly once, because
   * that element outlives every innerHTML swap the router performs.
   */
  private mountWeatherTrack() {
    if (!this.weatherTrackBound) {
      byId("content-body").addEventListener("click", (event) => this.onWeatherTrackClick(event));
      this.weatherTrackBound = true;
    }
  }

  private onWeatherTrackClick(event: MouseEvent) {
    const target = event.target as HTMLElement | null;
    const button = target?.closest<HTMLElement>(
      "[data-weather-lesson],[data-weather-page],[data-weather-index],[data-weather-scroll],[data-open-layer]",
    );
    if (!button) {
      // A `data-view` button INSIDE this track is injected markup, so the
      // start-up [data-view] sweep never bound it. Bind it here, and only here,
      // so no other page's controls are double-handled.
      const nav = target?.closest<HTMLElement>("[data-view]");
      if (nav && nav.closest("#weather-index, #weather-page")) this.openContent(nav.dataset.view ?? "explore");
      return;
    }
    const index = byId("weather-index");
    const page = byId("weather-page");
    const showPage = (markup: string) => {
      rememberChapterOpener(byId("content-body"), "learn-weather", button);
      this.stopLayerVideos();
      // One scroller serves both siblings, so opening a page has to remember
      // where the index was. Without this a reader who opens module 08 from
      // the bottom of the index is returned to the middle of it, because the
      // scroller keeps the sub-page's offset and the browser clamps it.
      this.weatherIndexScroll = byId("content-view").scrollTop;
      page.innerHTML = markup;
      page.hidden = false;
      index.hidden = true;
      byId("content-view").scrollTop = 0;
      focusChapterHeading(page);
    };
    if (button.dataset.weatherLesson !== undefined) {
      showPage(weatherLessonView(button.dataset.weatherLesson));
      this.pushNav({ view: "learn-weather", page: button.dataset.weatherLesson });
      return;
    }
    if (button.dataset.weatherPage !== undefined) {
      showPage(weatherPageView(button.dataset.weatherPage));
      // A module that maps onto a Dungey stage links straight AT that stage.
      // A door that lands the reader at the top of a long page and leaves them
      // to find the card is not a link to the card.
      const stage = button.dataset.weatherStage;
      if (stage) {
        const card = page.querySelector<HTMLDetailsElement>(`.stage-card[data-stage="${stage}"]`);
        if (card) {
          card.open = true;
          card.querySelector("summary")?.focus({ preventScroll: true });
          card.scrollIntoView({ block: "start" });
        }
      }
      return;
    }
    if (button.dataset.weatherIndex !== undefined) {
      this.stopLayerVideos();
      page.hidden = true;
      page.replaceChildren();
      index.hidden = false;
      byId("content-view").scrollTop = this.weatherIndexScroll;
      restoreChapterOpener(byId("content-body"), "learn-weather");
      return;
    }
    if (button.dataset.weatherScroll !== undefined) {
      const destination = document.getElementById(button.dataset.weatherScroll);
      if (destination) {
        focusChapterHeading(destination);
        destination.scrollIntoView({ block: "start", behavior: prefersReducedMotion() ? "auto" : "smooth" });
      }
      return;
    }
    // "Switch on <layer>": do exactly what the reader would do by hand — set
    // the checkbox and dispatch `change`, which is the only path `main.ts`
    // calls `globe.setLayer` from — then leave the page for the globe, because
    // a layer switched on behind a full-screen article has not been seen.
    const checkbox = document.getElementById(button.dataset.openLayer ?? "") as HTMLInputElement | null;
    if (checkbox && !checkbox.checked) {
      checkbox.checked = true;
      checkbox.dispatchEvent(new Event("change", { bubbles: true }));
    }
    this.openContent("explore");
  }

  private mountLayerPages() {
    const body = byId("content-body");
    // The narration slot is rendered empty and hidden by layer-pages.ts; this fills the
    // ones that have audio to put in them. It runs on every rebuild for the same reason
    // the buttons are bound here - the markup is replaced whenever the index and a layer
    // page swap places, and a listener bound to markup that no longer exists never fires.
    mountLayerNarration(body);
    body.querySelectorAll<HTMLButtonElement>("[data-layer-page]").forEach((button) => {
      button.addEventListener("click", () => {
        const page = button.dataset.layerPage ?? "";
        rememberChapterOpener(body, "learn-layers", button);
        this.openTrackPage("learn-layers", page);
        this.pushNav({ view: "learn-layers", page });
      });
    });
    body.querySelectorAll<HTMLButtonElement>("[data-layer-index]").forEach((button) => {
      button.addEventListener("click", () => {
        this.stopLayerVideos();
        body.innerHTML = layerPagesIndexView();
        byId("content-view").scrollTop = 0;
        this.mountLayerPages();
        restoreChapterOpener(body, "learn-layers");
        this.pushNav({ view: "learn-layers" });
      });
    });
  }

  /** Pause every layer video in the content body, wherever the visitor is going. */
  private stopLayerVideos() {
    document.querySelectorAll<HTMLVideoElement>("#content-body video.layer-video")
      .forEach((video) => video.pause());
    // And its voice. A narration left talking over a page the reader has already navigated
    // away from is the most hostile thing audio on a website can do.
    stopLayerNarration(byId("content-body"));
  }

  /**
   * The standing physics of every layer, printed on its own method card.
   *
   * This is the other half of the Data Explorer's clock test. A value that
   * cannot move when the clock moves is not a reading, so it is not on the
   * operational panel — but it is not deleted either, and it is not retyped
   * into prose here: it is rendered from the SAME `EnvironmentLegendSpec` the
   * panel builds, so the ring current's `10 keV at L 8 → 80 keV at L 4` stays
   * a computed figure that follows the ion selector, exactly as it did when it
   * was on the card.
   *
   * It goes into the method card's existing definition list, before "Do not
   * infer", so it reads in the same rhythm as the three rows already there and
   * introduces no new type treatment. A layer whose spec cannot be built right
   * now (its artifact has not loaded) simply contributes nothing, and says so
   * in the console rather than taking the page down.
   */
  private mountLayerStandingReadings() {
    for (const [layer, cardId] of Object.entries(LAYER_METHOD_CARD_IDS) as Array<[LayerName, string]>) {
      const list = document.querySelector<HTMLElement>(`#${cardId} .method-card-body dl`);
      if (!list) continue;
      let rows: Array<[string, string]>;
      try {
        rows = standingReadings(this.environmentLegendSpec(layer));
      } catch (error: unknown) {
        console.error(`Standing readings for ${layer} could not be built`, error);
        continue;
      }
      if (rows.length === 0) continue;
      const row = document.createElement("div");
      const term = document.createElement("dt");
      term.textContent = "True at every instant";
      const detail = document.createElement("dd");
      const grid = document.createElement("div");
      grid.className = "fact-grid";
      grid.append(...rows.map((row) => factCell(row)));
      detail.append(grid);
      row.append(term, detail);
      // Before "Do not infer", which is the card's closing caveat and stays
      // last on every card whether or not this section exists.
      list.insertBefore(row, list.children[list.children.length - 1] ?? null);
    }
  }

  private closeContent() {
    this.pushNav({ view: "explore" });
    // A layer page leaves its <video> in #content-body, because the router
    // hides the section rather than emptying it. An element left playing keeps
    // buffering behind a hidden page, so it is stopped on the way out.
    this.stopLayerVideos();
    // The replay dialog is in the top layer, so hiding #content-view underneath
    // it would leave it on screen over the globe. Closing it also runs the
    // teardown in bindEventDialog(), which is what stops the replay's clock.
    this.closeEventPlayer();
    window.clearInterval(this.eventTimer);
    this.eventReplay?.destroy();
    this.eventReplay = null;
    // Hand the NOAA panels back before the page goes out of view. The
    // awareness page MOVES them rather than copying them, so there is exactly
    // one of each in the document; leaving them inside a hidden subtree would
    // strand them there for any surface that wants them next.
    this.returnOutlookPanels();
    byId("content-view").hidden = true;
    document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("is-active", (item as HTMLElement).dataset.view === "explore"));
    byId("scene").focus();
  }

  private bindEventCards() {
    document.querySelectorAll<HTMLButtonElement>("[data-replay-event]").forEach((button) => {
      button.addEventListener("click", () => {
        const event = this.events.events.find((item) => item.id === button.dataset.replayEvent);
        if (!event) return;
        this.openEventPlayer(event);
        this.pushNav({ view: "events", page: event.id });
      });
    });
  }

  /**
   * Open ONE historical event, on top of the grid.
   *
   * What this used to do, and why it looked wrong: `#event-player` was a hidden
   * div rendered by `eventsView()` ABOVE the six cards. This method filled it
   * and called `scrollIntoView({ behavior: "smooth" })`, so a reader who
   * clicked the last card watched the page glide back up past every other card
   * to a player at the top. Only one event was ever open — but the animation
   * scrolled through all of them to get there, which is what Sean was
   * describing on 2026-08-21.
   *
   * `#event-player` now lives inside `#event-dialog` and is shown with
   * `showModal()`. Nothing scrolls. The browser gives us the top layer, the
   * inert page behind, the focus trap and Escape; `bindEventDialog()` owns
   * what happens on the way out, including stopping the replay's clock.
   */
  private openEventPlayer(event: HistoricalEvent) {
    const dialog = byId<HTMLDialogElement>("event-dialog");
    const player = byId("event-player");
    // Which card to hand focus back to. Stored as an id rather than as the
    // element, because the events view is re-rendered from scratch on every
    // visit and the button object the reader clicked may not survive.
    this.eventOpenerId = event.id;
    player.innerHTML = eventPlayer(event);
    // An event that holds measurements draws them, and brings its own clock.
    // The milestone stepper below is built only for events that do not, so the
    // visitor is never given two scrubbers for one story.
    this.eventReplay?.destroy();
    this.eventReplay = null;
    const replayHost = player.querySelector<HTMLElement>("[data-event-replay]");
    // The milestones travel with the replay: an event that has no landmarks of
    // its own on the chart's clock captions itself from this same sourced
    // prose, so the caption and the list below it cannot disagree.
    if (replayHost) {
      // The id travels with the replay so a chart that has a stitched narration bed
      // can find it. An event with no bed mounts exactly as it always did.
      this.eventReplay = mountEventReplay(replayHost, event.replay, event.milestones, event.id);
    }
    if (!dialog.open) dialog.showModal();
    // A dialog reused for a second event keeps the scroll offset of the first.
    dialog.scrollTop = 0;
    // showModal() focuses the first tabbable descendant, which is the corner ×,
    // so a screen reader would open on the word "close". Move it to the dialog
    // itself — the ARIA authoring practice when there is no logical first field
    // — and the reader gets the role and the event's own title, which is what
    // aria-labelledby points at.
    dialog.focus({ preventScroll: true });
    // Close is bound HERE, above the milestone stepper, because the guard below
    // returns early when there is no timeline to bind — which is exactly the
    // case for a replay event. Bound after that guard, as it used to be, the
    // Close button would be dead on any event this file cannot step through.
    //
    // It only asks the dialog to close. Everything that has to be torn down —
    // the milestone timer, the replay's own clock, the <video> and <audio>
    // elements in the imagery block — is done once in the dialog's `close`
    // handler, so Escape, the corner ×, this button and leaving the page all
    // take the identical path and none of them can leave a clock running.
    player.querySelector("[data-close-event]")?.addEventListener("click", () => this.closeEventPlayer());
    const timeline = player.querySelector<HTMLInputElement>("[data-event-timeline]");
    const play = player.querySelector<HTMLButtonElement>("[data-event-play]");
    if (!timeline || !play) return;
    const render = () => {
      const index = Number(timeline.value);
      const milestone = event.milestones[index];
      if (!milestone) return;
      const title = player.querySelector<HTMLElement>("[data-event-title]");
      const description = player.querySelector<HTMLElement>("[data-event-description]");
      const step = player.querySelector<HTMLElement>("[data-event-step]");
      if (title) title.textContent = milestone.title;
      if (description) description.textContent = milestone.description;
      if (step) step.textContent = `${index + 1} / ${event.milestones.length}`;
    };
    timeline.addEventListener("input", render);
    play.addEventListener("click", () => {
      if (this.eventTimer) {
        window.clearInterval(this.eventTimer);
        this.eventTimer = 0;
        play.textContent = "Play";
        return;
      }
      play.textContent = "Pause";
      this.eventTimer = window.setInterval(() => {
        const next = Number(timeline.value) + 1;
        timeline.value = String(next >= event.milestones.length ? 0 : next);
        render();
      }, 2800);
    });
    render();
  }

  /** Ask the dialog to close. The `close` handler does the tearing down. */
  private closeEventPlayer() {
    const dialog = byId<HTMLDialogElement>("event-dialog");
    if (!dialog.open) return;
    dialog.close();
    // The replay owns a history entry, so leaving it has to CONSUME that entry
    // rather than leave it behind -- otherwise the reader's next Back press
    // re-opens the replay they just closed. When the close is already the
    // result of a Back press, `navApplying` is up and history is left alone.
    const state = window.history.state as NavState | null;
    if (!this.navApplying && state?.view === "events" && state.page) window.history.back();
  }

  /**
   * Bound once, at start-up, on the dialog itself.
   *
   * `close` fires for every way out — the Close button, the corner ×, the
   * Escape key, and `closeContent()` on the way off the page — so this is the
   * only place that has to know how to stop a replay. THE CLOCK MUST STOP:
   * every replay in `src/event-replay.ts` drives itself with
   * `requestAnimationFrame`, and six of them left running behind a closed
   * panel would burn a phone battery for a picture nobody can see. Emptying the
   * player also removes the imagery block's <video> and <audio> elements,
   * which is the only thing that reliably stops a clip a reader had playing.
   */
  private bindEventDialog() {
    const dialog = byId<HTMLDialogElement>("event-dialog");
    dialog.addEventListener("close", () => {
      window.clearInterval(this.eventTimer);
      this.eventTimer = 0;
      this.eventReplay?.destroy();
      this.eventReplay = null;
      byId("event-player").innerHTML = "";
      // Back to the card the reader opened, not to the top of the document.
      const opener = this.eventOpenerId
        ? document.querySelector<HTMLButtonElement>(`[data-replay-event="${this.eventOpenerId}"]`)
        : null;
      this.eventOpenerId = null;
      opener?.focus({ preventScroll: true });
    });
    dialog.querySelector("[data-close-event]")?.addEventListener("click", () => this.closeEventPlayer());
  }
}

async function boot() {
  const manifestUrl = new URL("data/manifest.json", document.baseURI);
  try {
    const manifest = await fetchJson<ReleaseManifest>(manifestUrl);
    const [catalog, weather, events, land] = await Promise.all([
      fetchJson<CatalogBundle>(artifactUrl(manifestUrl, manifest.catalog.path)),
      fetchJson<SpaceWeatherBundle>(artifactUrl(manifestUrl, manifest.spaceWeather.path)),
      fetchJson<EventsBundle>(artifactUrl(manifestUrl, manifest.events.path)),
      fetchJson<LandGeoJson>(artifactUrl(manifestUrl, manifest.land.path)),
    ]);
    new ExplorerApp(manifest, catalog, weather, events, land);
  } catch (error) {
    console.error(error);
    const status = byId("data-status");
    status.classList.add("is-stale");
    status.lastChild!.textContent = " Bundle unavailable";
    byId("scene").innerHTML = `<div style="padding:2rem;max-width:42rem"><h1>The verified data bundle could not be loaded.</h1><p>The explorer does not substitute silent demo data. Please try again shortly; the last-known-good bundle remains on the server during normal upstream outages.</p></div>`;
    if (document.documentElement.dataset.deliveryEntered) {
      status.lastChild!.textContent = " Interactive view unavailable";
      byId("scene").innerHTML = `<div style="padding:2rem;max-width:42rem"><h1>The interactive view could not start.</h1><p>A required download or graphics operation failed. <a href="./study.html">Read the static lessons</a> or change Connection &amp; display options.</p></div>`;
    }
  }
}

// Booting is a side effect of loading the page, not of importing the module.
// The guard lets the unit tests exercise the real exported decision functions
// in this file rather than a copy of them written for the test.
if (typeof document !== "undefined") void boot();

/**
 * The ring in the same figure shell the Kp chart two sections up uses: a plot,
 * then a `<figcaption>` that is a KEY and a provenance stamp.
 *
 * The chart shipped without a key at all, so the dashed second curve and the
 * dot on the boundary were unexplained marks — and at the size it used to be
 * drawn, the dashed curve was the loudest thing on the page. Naming the three
 * marks is what lets the picture be small.
 *
 * The plume swatch appears only on a frame that HAS a plume, because a key
 * entry for a mark the picture does not contain is a claim that it does.
 */
function plasmapauseFigure(svg: SVGSVGElement, frame: PlasmapauseFrame): HTMLElement {
  const figure = document.createElement("figure");
  figure.className = "now-figure plasmapause-figure";
  const plot = document.createElement("div");
  plot.className = "plasmapause-plot";
  plot.append(svg);
  const caption = document.createElement("figcaption");
  const key = (modifier: string, text: string) => {
    const item = document.createElement("span");
    item.className = "now-key";
    const swatch = document.createElement("i");
    swatch.className = `plasmapause-swatch ${modifier}`;
    item.append(swatch, document.createTextNode(text));
    return item;
  };
  caption.append(
    key("is-boundary", "Plasmapause (50 cm\u207b\u00b3 contour)"),
    key("is-check", "Steepest-gradient check"),
  );
  if (frame.plume?.present) caption.append(key("is-plume", "Plume peak"));
  const stamp = document.createElement("span");
  stamp.className = "plasmapause-stamp";
  stamp.textContent = plasmapauseFrameStamp(frame, new Date());
  caption.append(stamp);
  figure.append(plot, caption);
  return figure;
}

/**
 * The caption under the plasmapause ring: how far the boundary travelled across
 * the published window, and what the drawing is allowed to claim.
 *
 * This is the quantity the card's own rows cannot carry — they each report one
 * frame, and the point of the chart is what happens BETWEEN frames.
 */
function plasmapauseCaption(frames: readonly PlasmapauseFrame[], checkNote: string | null = null): HTMLElement {
  const caption = document.createElement("p");
  caption.className = "plasmapause-note";
  const motion = plasmapauseMotion(frames);
  caption.textContent = motion
    ? `Across the ${frames.length} published frames the midnight boundary moved `
      + `${Math.round(motion.midnight.travelKm).toLocaleString("en-US")} km (L `
      + `${motion.midnight.minimumL.toFixed(2)}–${motion.midnight.maximumL.toFixed(2)}), on Kp `
      + `${motion.kp.minimum.toFixed(2)}–${motion.kp.maximum.toFixed(2)}. ${PLASMAPAUSE_LIMITATION}`
    : PLASMAPAUSE_LIMITATION;
  // The disagreement between the two published curves, when there is one big
  // enough to be misread as a second boundary. Its own paragraph, because it is
  // a statement about THIS frame while the sentence above is about the window.
  if (checkNote) {
    const note = document.createElement("span");
    note.className = "plasmapause-check-note";
    note.textContent = checkNote;
    caption.append(note);
  }
  return caption;
}
