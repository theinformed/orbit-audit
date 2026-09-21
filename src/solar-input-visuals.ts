import * as THREE from "three";
import {
  buildProjectedFlowAdvectionPaths,
  sampleProjectedFlowAdvectionPath,
} from "./geospace-structures";
import type {
  EncodedProjectedStreamlines,
  GeospaceStructurePlane,
  GeospaceStructuresDefinition,
  GsmPositionMapper,
  PlanePositionMapper,
  ProjectedAdvectionPath,
} from "./geospace-structures";
import {
  LOBE_APPROACH_RUN_RE,
  TAIL_X_LINE_RE,
  activeTracerCount,
  buildDungeyReturnLeg,
  containedInMagnetopause,
  trappedMotionForPath,
} from "./dungey-transport";
import type { DungeyBranch, DriftSense, GsmPointRe } from "./dungey-transport";

export type SolarWindVisualMode = "model-projected" | "illustrative-upstream";

/**
 * What each solar-wind presentation is, in the site's own evidence terms.
 *
 * The two modes are different evidence classes — a NOAA MHD solution versus
 * an idealised teaching cue — and for a long stretch the site showed the
 * fallback to anyone who switched on only the solar-wind layer, with nothing
 * on screen saying so. Sean read it, correctly, as uniform uncoupled motion
 * that ignored the data. The legend must always name which of these is
 * drawn; this table is exported so the UI cannot paraphrase the distinction
 * into something softer.
 */
export const SOLAR_WIND_MODE_PRESENTATION: Record<SolarWindVisualMode, {
  badge: string;
  headline: string;
  detail: string;
}> = {
  // CORRECTNESS FIX 2026-09-04: both entries used to promise plane tracers that
  // ride NOAA's own flow. They are built and then hidden at the render gate —
  // `DRAW_PUBLISHED_PLANE_TRACERS = false`, against Sean's "I don't think you
  // should be drawing those green lines at all" — so the 3-D shower a reader
  // sees is the IDEALISED cue on both modes, always. What actually separates
  // the two is whether an MHD frame is loaded at all, which decides whether the
  // model's flow is on the globe as cut-plane colour. The badges now say that
  // rather than claiming a flow field nothing rides.
  "model-projected": {
    badge: "MEASURED MIX · IDEALISED FLOW · MHD FRAME LOADED",
    headline: "A charge-coloured species shower driven by the measured wind, on idealised no-penetration flow; NOAA's own solution is on the globe as the cut planes' colours",
    detail: "The shower's population and brightness follow the measured density, its cadence the measured bulk speed, and its colours are the species of the plasma — protons, alphas, electrons — as an illustrative sampling of the measured bulk totals. Its PATHS are idealised incompressible no-penetration streamlines around the drawn boundary, not the model's flow. NOAA's flow solution is drawn, as the colours of the two published cut planes in the NOAA MHD cross-section option; nothing rides those planes as tracers, because beads confined to two flat cuts read as arcs hanging in space from every angle but face-on. Frozen-frame advection, not particle trajectories. The flow carries on past Earth, over the poles and down the flanks to 30 Rₑ down-tail, because that is what the solar wind does — it is deflected around the magnetosphere, not absorbed by it. Down-tail distance is compressed hard by the shared ruler, so the drawn wake is far shorter than the real tail and its length is not a distance.",
  },
  "illustrative-upstream": {
    badge: "MEASURED MIX · IDEALISED FLOW · NO MHD FRAME",
    headline: "A charge-coloured species shower on idealised no-penetration flow — the NOAA flow field is not loaded",
    detail: "Particles arrive across a PLANE-PARALLEL FRONT cut to the size of the frame — the whole upstream face of the view, not a beam from a point — and follow incompressible potential-flow streamlines around the drawn boundary in three dimensions: an honest teaching cue for deflection, but uncoupled from the modelled plasma. What becomes of a particle is decided by its impact parameter, its distance from the Sun–Earth line, and by nothing else: the wide ones pass barely bent, which is most of them; the middling ones are turned around the magnetopause and carried down the flanks; and only the ones arriving near the axis are shocked at the nose, where a minority can couple in. Because the front is as wide as the view, pulling the camera back brings wind in over the top and bottom of the frame as well as the side, exactly as a front far wider than the obstacle should. The face is sampled evenly over the DRAWN PAGE rather than evenly in space, and the tracers ride a fixed set of shared streamlines rather than one each so the flow reads as a stream; both are display choices and neither changes how many particles, or which species, are drawn. NOAA's own flow solution becomes available in the MHD cut option when the geospace bundle loads, as the colours of its two published cut planes — never as tracers in this shower. The flow carries on past Earth, over the poles and down the flanks to 30 Rₑ down-tail, because that is what the solar wind does — it is deflected around the magnetosphere, not absorbed by it. Down-tail distance is compressed hard by the shared ruler, so the drawn wake is far shorter than the real tail and its length is not a distance.",
  },
};

export const SOLAR_INPUT_VISUAL_METHOD = {
  solarWind: {
    model: "A shower of species-coloured particles — H⁺ the amber, e⁻ the pale cream of the same gold family, He²⁺ the one cool periwinkle spark: population and brightness from the measured proton density, cadence from the measured bulk speed, species mix (H⁺, He²⁺, e⁻) from the measured density with the alpha abundance stated as assumed. HOW MANY of each species is drawn is the measured mix and nothing else. Three DISPLAY CHOICES decide what each one LOOKS like, and none of them touches a count, a species or a path. (1) SIZE is an order, not a ratio: the He²⁺ glyph draws at about 1.45 times the proton's width — a little over twice its area — and e⁻ at 0.85, so the eye gets heavy / middle / light. It briefly drew the alpha at exactly the four-proton mass ratio by AREA, and that was a worse idea than it sounds: nobody can decode an area ratio off a three-pixel glyph, and combined with the brightness correction below it put about three times a proton's light into a species that is 2% of the plasma. The mass ratio of 4 is now STATED, in the legend, as the energy each species carries. (2) BRIGHTNESS is a per-colour correction: the periwinkle #8b87e8 is 1.63x darker in relative luminance than the amber H⁺, so at an equal drawn opacity on this additive sky an alpha would emit 61% of a proton's light purely because of its hex code. That is divided back out of the palette, not added to the plasma, and at this colour the whole correction fits under the shader's full-opacity ceiling instead of pinning the alphas at maximum brightness the way the old darker indigo did. (3) DEPTH: tracers passing close in front of the camera are faded toward a fifth of their opacity and distant ones drawn slightly smaller, so the wind reads as a volume around Earth instead of a screen of foreground noise. The fade is measured against the camera's own distance from Earth, so it works at every zoom, and the region within a few Earth radii of Earth — where the funnelling, the snap-back and the destinations happen — sits at the top of the ramp and is drawn as it always was. Separately, e⁻ is drawn with a streak that stays visible further behind it and He²⁺ with one that drops away sooner, so mass reads as motion character; every streak is the same fixed display length and every particle rides the same measured bulk V. The two species that make up 98% of the wind — H⁺ and e⁻ — are both drawn in the gold family so the shower reads as one thing, and the trace He²⁺ carries the colour separation, because three warm colours cannot be told apart once the brightness correction has equalised them. When the NOAA MHD cut is on, the model's own flow is on screen as the colours of its two published cut planes; no tracer in this shower rides it, because the shower's paths are the idealised no-penetration cue on every mode.",
    species: "Essentially all of the solar wind is charged — protons ~96% of ions by number, He²⁺ alphas the assumed ~4% (the L1 feed does not measure the alpha abundance), and the electrons that keep the plasma neutral. The Sun's UNCHARGED output is light: the X-ray layer, which crosses the field in a straight line. Everything drawn in this shower deflects; nothing in it is a neutral particle.",
    coupling: "A visible fraction of the arriving particles is guided along the magnetosphere model's own traced field lines, whichever layers the reader has switched on — the wind moves the same way either way. The wind draws a faint cue of the exact polylines its guided particles are riding, and nothing else, in two halves that come and go for different reasons. The SOLID half is the traced field-line model's own output, and it is drawn only while the magnetosphere layer is off, because when that layer is on it is drawing those same lines at a better weight. The DOTTED half is the schematic Dungey transport past the neutral line — the turn, the earthward injection, the trapped bounce-and-drift wound round the Earth and the two ways a trapped particle leaves — and it is drawn WHENEVER guided particles are on it, because no layer on this page draws those legs. Dotted is what says nobody measures them. The cue is a display choice and the particles are riding a MODELLED path either way; it adds no geometry, being the very polylines the tracers walk. The paths: dayside cusp-adjacent ones funnel down the boundary-truncated lines to their high-latitude footpoints, and a smaller share rides the open polar-cap lines tailward along the lobes. The guidance polylines are the field-line model's own output; entry selection is geometric and the motion along them is illustrative, not a solved reconnection rate. Funnelled particles end at the field line's footpoint latitude — the cusp band adjacent to the auroral oval — not at the measured OVATION oval. HOW MANY particles are drawn entering is DELIBERATELY EXAGGERATED for legibility, and it is not a coupling efficiency: the real magnetosphere is an obstacle in a flow, not a sink, and the overwhelming majority of the solar wind is shocked, deflected around the magnetopause and carried down the flanks without ever entering. Enough are funnelled here to read as a stream, because that entry is what this layer is teaching. The bypassing flow drawn around and past the boundary is the honest half of the same picture, and it is the larger half on screen: since the upstream face became a plane-parallel front the size of the frame it covers about 1.8 times as many pixels as the funnelled stream, counted by rendering the same frame with and without it. Neither number is a measured rate.",
    fallback: "Physics-based teaching tracers follow incompressible no-penetration streamlines around the drawn empirical magnetopause, offset outward by a fixed stand-in gap.",
    approximation: "The fallback is an idealized incompressible-flow cue, not an MHD bow-shock, magnetosheath, reconnection, or particle-transport solution. The gap between the obstacle and the drawn boundary is a fixed display offset, not a computed sheath thickness.",
    limitation: "These are teaching tracers, not observed individual trajectories. Display cadence encodes measured bulk speed; how much of the population is lit encodes measured proton density, while HOW MANY tracers exist to be lit is a legibility choice and not a number density — it was raised when the upstream face became the width of the frame, so that a wider face did not mean a thinner wind; species colour is illustrative sampling of measured bulk totals — we measure plasma, not individual particles. Glyph SIZE, glyph BRIGHTNESS, STREAK CHARACTER and DEPTH FADE encode nothing measured: size is an ordering by mass and is deliberately not a literal ratio; brightness is a per-colour correction that puts the three species on equal luminance, because the periwinkle is 1.63x darker than the amber; streak fade is a per-species drawing choice so mass reads as motion character, on one shared measured bulk speed; and the depth fade is a function of where the camera is, not of the plasma. None of them changes how many of a species is drawn, where it goes or which species it is, and each species' share of the drawn population is still its true share. The BULK ENERGIES printed on the legend are ½mv² on the measured L1 bulk speed with standard particle masses — derived from a measurement, not a new one, and not a measurement of any individual particle; the electron figure is its bulk-flow energy, the like-for-like comparison with the ions, and its thermal jiggle is far larger (order 10 eV against 0.19 eV). Each tracer's streak is the direction of its own streamline; its length is a fixed display length and encodes nothing. The size and brightness ramps have a FLOOR that was raised for legibility, so a very quiet wind is drawn larger and brighter than the ramp alone would give it; both still rise with the measurement. WHERE the tracers enter is a display choice too: the upstream face is a plane-parallel front cut to the size of the frame, sampled evenly over the DRAWN PAGE — equal drawn area carries equal numbers — and the tracers ride a fixed set of shared streamlines rather than each on one of its own, so the flow reads as a stream rather than as speckle. The real front is even in PHYSICAL space and every parcel is on a path of its own; the shared ruler compresses distance so hard that drawing it evenly in physical space stacks half the tracers into a thin halo at the edge of the frame. This moves drawn particles around and changes neither how many are drawn nor how many of each species. DRAW ORDER is a display choice as well: none of the transparent things in this scene writes depth, so which of two of them looks nearer is decided by the order they are painted in and not by where they are. The guided particles are painted after the ring-current volume and the ring-current illustration, so a particle inside those fills reads as a mark rather than being washed out by the fill it is inside; solid geometry, the Earth included, still occludes them exactly as before. Nothing about their positions, their number, their species or their opacity changes with it. HOW MANY guided tracers are lit on the tail-return legs at any instant is the measured coupling and only that; on the trapped leg inside the ring current that leaves single figures on screen at a quiet drive, which is why the path they ride is drawn under them rather than the marks being multiplied. HOW THAT PATH IS INKED is a display choice and is the evidence class made visible: solid ink is reserved for the traced field-line model's own geometry, and the schematic Dungey legs — the turn at the neutral line, the earthward injection, the trapped helix and the two ways out — are drawn as a broken line instead, because nobody measures those trajectories. The break is a fifty-fifty dash of a fixed physical length, half an Earth radius of mark and half an Earth radius of gap, so a mark is always exactly as long as the gap beside it at every zoom and the line reads as one path rather than as loose marks.",
  },
  xray: {
    model: "Soft X-ray flux in near-Earth space is a single scalar — measured uniform to 0.056% from GEO to the ground — so the only honest spatial structure left to draw is which hemisphere currently faces the Sun. A tint over the sunlit hemisphere shows the division: its brightness at each point is cos(solar zenith angle), the geometric factor for flux crossing a horizontal surface, so it concentrates where the Sun is overhead and falls to nothing at the shadow edge. That edge is drawn as a line, and the whole tint's colour and peak intensity are set by the measured flux class, so an A-class Sun is barely a wash and an X-class flare is unmistakable.",
    driver: "GOES XRS 0.1-0.8 nm irradiance and its A/B/C/M/X class.",
    photons: "Pale inbound rays arrive alongside the tint, drawn straight and parallel because that is the whole fact about them: photons carry no charge, so the bow shock, the magnetosheath and the magnetopause do nothing to them at all. Each ray ends where it is absorbed, on the dayside of the same upper-atmosphere shell the tint paints — none reaches the night side and none wraps around. How many rays are drawn and how brightly is the measured flux and nothing else: sparse and faint at A class, a dense shower at X. Their speed on screen is display cadence, not the speed of light, and it does not vary with the data, because the speed of light does not vary.",
    limitation: "The tint is a geometric exposure indicator, built from the site's own sun-direction calculation, not a photon track and not an attenuation model. The cos weighting is incidence geometry only; it is not a claim about how much any layer absorbs. The magnetosphere does not deflect X-rays, and nothing in near-Earth space attenuates this flux; it is unchanged until the D-region at 60-90 km, where the D-RAP layer picks up the consequence. The inbound rays are not individual photon tracks either: they are a drawn beam whose direction, straightness and absorption point are the physics, and whose population is the measured flux.",
    whyStraight: "X-rays are photons. They carry no charge, so the magnetic field exerts no force on them: they cross the magnetosphere in a straight line and reach the sunlit upper atmosphere unattenuated and undeflected. The solar wind is charged plasma carrying its own field, which is why it — and only it — is turned aside by the boundary.",
  },
} as const;

export interface SolarWindIntensityEncoding {
  available: boolean;
  normalizedSpeed: number;
  normalizedDensity: number;
  normalizedPressureCue: number;
  activeFraction: number;
  opacity: number;
  pointSize: number;
}

export interface XrayIrradianceEncoding {
  available: boolean;
  className: string;
  /** 0 at A1, 1 at X10 (log flux, clamped) — the position a legend ramp reads. */
  normalizedFlux: number;
  /**
   * Opacity of the sunlit tint AT THE SUB-SOLAR POINT. It falls away from
   * there as cos(solar zenith angle), so this is the maximum the tint reaches
   * anywhere, and it climbs steeply with class: a quiet A-class Sun is barely
   * a wash, an X-class flare is unmistakable.
   */
  exposureOpacity: number;
  /**
   * Opacity of the terminator rim. Deliberately never small: which hemisphere
   * faces the Sun is a geometric fact that is equally true at A1 and X10, and
   * it is the one piece of real spatial structure this scalar has. It is what
   * keeps the layer legible when the flux itself is low.
   */
  terminatorOpacity: number;
  /**
   * Fraction of the inbound-ray buffer that is drawn. This is the layer's
   * "how much flux" statement in the one currency a photon beam has to spend:
   * how many arrivals there are. Strictly increasing with log flux, so a quiet
   * A-class Sun is a thin scatter of rays and an X-class flare is a shower.
   */
  photonRayFraction: number;
  /** Brightness of an inbound ray. Rises steeply with class, like the tint's. */
  photonRayOpacity: number;
  /**
   * The operationally meaningful state, from the class letter alone: C and
   * below is background, M is a flare with HF degradation on the sunlit side,
   * X is a flare with a full sunlit-side radio blackout.
   */
  activityState: "none" | "background" | "flare" | "major-flare";
}

export interface SolarWindModelFlowInput {
  definition: GeospaceStructuresDefinition;
  projectedFlowStreamlines: Partial<Record<GeospaceStructurePlane, EncodedProjectedStreamlines>>;
}

/**
 * Physical radius of the drawn magnetopause in one GSM direction, in Earth radii.
 *
 * `thetaRad` is the solar zenith angle and `azimuthRad` is measured from GSM +z,
 * which is `magnetopausePointGsm`'s convention. Supplying this makes the flow
 * obstacle the boundary the reader can actually see; without it the obstacle
 * falls back to a sphere at the subsolar standoff.
 */
export type BoundaryRadiusField = (thetaRad: number, azimuthRad: number) => number;

export interface IllustrativeUpstreamFlowOptions {
  earthRadiusRe?: number;
  magnetopauseStandoffRe?: number;
  magnetopauseGapRe?: number;
  /**
   * The drawn magnetopause, sampled per direction.
   *
   * The obstacle used to be a sphere at `magnetopauseStandoffRe + gap`, and
   * that is only the right shape at the nose: every empirical magnetopause
   * flares, reaching about 1.4x its standoff at the terminator and more
   * beyond, so a sphere sized on the nose sits *inside* the drawn boundary
   * everywhere on the flanks. Tracers then honoured the sphere and cut
   * straight through the surface the reader was looking at.
   */
  boundaryRadiusForDirection?: BoundaryRadiusField;
  upstreamStartRe?: number;
  downstreamEndRe?: number;
  transverseExtentRe?: number;
  /**
   * How many distinct streamlines ("flow tubes") the drawn tracers share.
   *
   * 0 gives every tracer its own impact point, which draws the wind as speckle.
   * A finite count puts several tracers on one curve at independent phases, so
   * the eye joins them into a line. See `DEFAULT_FLOW_TUBE_COUNT`.
   */
  flowTubeCount?: number;
  streamCount?: number;
  samplesPerStream?: number;
  particleCount?: number;
  seed?: number;
  positionForGsm?: GsmPositionMapper;
  /**
   * Length of each tracer's motion streak, in the mapper's output units.
   *
   * Deliberately a fixed display length rather than an encoding. Direction is
   * the streamline's own tangent and carries the physics; length carries
   * nothing, and saying so keeps the streak from being read as a speed.
   */
  trailLength?: number;
}

export interface SolarWindVisualOptions extends IllustrativeUpstreamFlowOptions {
  modelFlow?: SolarWindModelFlowInput | null;
  positionForPlane?: PlanePositionMapper;
  minimumModelRadiusRe?: number;
  maximumModelSegmentRe?: number;
  tracersPerModelPath?: number;
  modelSecondsPerDisplaySecond?: number;
  pixelRatio?: number;
}

export interface XrayIrradianceVisualOptions {
  earthRadius?: number;
  upperAtmosphereRadius?: number;
  glowPolarSegments?: number;
  glowAzimuthSegments?: number;
  /**
   * Accepted for constructor-call compatibility with the shared renderer.
   * Nothing this layer draws is a screen-space glyph — the inbound rays are
   * line segments in scene space — so it is otherwise unused.
   */
  pixelRatio?: number;
  /**
   * The scene's shared radial mapping, used for exactly one thing: how far
   * sunward the drawn rays start. Everything else about the beam is in the
   * same scene units the exposure shell already uses, so a change to the
   * scene's distance scale carries the beam's entry point automatically and
   * nothing here owns a radial mapping of its own.
   */
  positionForGsm?: GsmPositionMapper;
  /** Where a ray enters the drawn scene, in Earth radii. Beyond the bow shock. */
  photonUpstreamStartRe?: number;
  /** Size of the ray buffer. The drawn prefix is the measured flux's share of it. */
  photonRayCount?: number;
  /** Fixed display length of a streak, scene units. Encodes nothing but "fast". */
  photonStreakLength?: number;
  /** Display seconds for one ray to cross from entry to absorption. */
  photonTraversalSeconds?: number;
  seed?: number;
}

/**
 * The no-penetration obstacle, sampled once per driver update.
 *
 * The empirical boundary models cost several exponentials per evaluation and
 * the streamline solve calls one of them about thirty times per tracer per
 * frame, so the shape is tabulated on a grid at least as fine as the mesh the
 * boundary is drawn with and read back by interpolation. The table is of the
 * *obstacle*, so the display gap is already in it.
 */
export interface ObstacleShape {
  radiusAt(thetaRad: number, azimuthRad: number): number;
  readonly noseRadiusRe: number;
  readonly maximumRadiusRe: number;
  readonly shaped: boolean;
  /**
   * The tabulation `radiusAt` is reading, handed over flat.
   *
   * `teachingFlowPointAroundObstacle` samples the obstacle about twenty times
   * per solve, twice per tracer, on every frame — several hundred thousand
   * times a second — and that call was measured at a quarter of the whole
   * page's JavaScript time (CPU profile, 2026-08-27, ANGLE/D3D12 on an RTX
   * 4080). Reading the grid directly lets the solve hoist the azimuth
   * interpolation, which cannot change inside a solve, out of its inner loop.
   * The arithmetic is the same arithmetic; `radiusAt` remains the interface
   * every other caller uses, and a shape without a grid still works through
   * it. Measured effect on the solve alone: 27.6 ms/frame to 9.3 ms/frame at
   * 4,600 tracers.
   */
  readonly grid?: ObstacleGrid;
}

/** A shape's own theta/azimuth grid, in the layout `radiusAt` indexes. */
export interface ObstacleGrid {
  readonly values: Float32Array;
  readonly thetaSamples: number;
  readonly azimuthSamples: number;
  readonly maximumThetaRad: number;
}

/**
 * `Math.acos`, tabulated.
 *
 * The solve below needs the polar angle of a point whose radius changes on
 * every bisection step, so it calls `Math.acos` about twenty times per solve
 * and about two hundred thousand times per frame at 4,600 tracers; it is the
 * most expensive single operation in the layer.
 *
 * WHAT THIS COSTS IN DRAWN POSITION, MEASURED RATHER THAN ASSUMED: over the
 * 4,600 tracers of a full frame, the largest disagreement between this table
 * and `Math.acos` in the returned transverse radius is 9.6e-5 Rₑ. The solve
 * already stops bisecting at 1e-4 Rₑ and argues, above the loop, that 1e-4 Rₑ
 * is a hundredth of a drawn pixel at the steepest part of the ruler. So the
 * table's error is smaller than the tolerance the answer was already only
 * known to, and no drawn position moves by a pixel anywhere in the scene.
 */
const OBSTACLE_ACOS_SAMPLES = 2048;
const OBSTACLE_ACOS_TABLE = (() => {
  const table = new Float32Array(OBSTACLE_ACOS_SAMPLES + 1);
  for (let index = 0; index <= OBSTACLE_ACOS_SAMPLES; index += 1) {
    table[index] = Math.acos((index / OBSTACLE_ACOS_SAMPLES) * 2 - 1);
  }
  return table;
})();

function acosTabulated(cosine: number): number {
  const position = (clamp(cosine, -1, 1) + 1) * 0.5 * OBSTACLE_ACOS_SAMPLES;
  const low = Math.min(OBSTACLE_ACOS_SAMPLES - 1, position | 0);
  return OBSTACLE_ACOS_TABLE[low]!
    + (OBSTACLE_ACOS_TABLE[low + 1]! - OBSTACLE_ACOS_TABLE[low]!) * (position - low);
}

export interface IllustrativeUpstreamDomain {
  earthRadiusRe: number;
  magnetopauseStandoffRe: number;
  /** The obstacle's subsolar radius. The obstacle is only a sphere of this radius when `obstacle.shaped` is false. */
  obstacleRadiusRe: number;
  obstacle: ObstacleShape;
  upstreamStartRe: number;
  downstreamEndRe: number;
}

function sphericalObstacle(radiusRe: number): ObstacleShape {
  const radius = Math.max(0.001, radiusRe);
  return {
    radiusAt: () => radius,
    noseRadiusRe: radius,
    maximumRadiusRe: radius,
    shaped: false,
    // The degenerate grid — one theta step, one azimuth step, the same value
    // at every corner — so the solve has ONE code path rather than a branch it
    // has to take on every bisection step. A sphere read off this grid returns
    // its radius exactly, whatever the direction.
    grid: {
      values: Float32Array.from([radius, radius]),
      thetaSamples: 1,
      azimuthSamples: 1,
      maximumThetaRad: Math.PI,
    },
  };
}

/**
 * Tabulate an obstacle from a boundary model plus the fixed display gap.
 *
 * `maximumThetaRad` is where the boundary models stop being evaluable; beyond
 * it the last evaluated ring is held rather than extrapolated, which is the
 * same refusal to invent a surface the fits do not support that the boundary
 * layer already makes.
 */
export function tabulateObstacleShape(
  boundaryRadiusForDirection: BoundaryRadiusField,
  gapRe: number,
  options: { thetaSamples?: number; azimuthSamples?: number; maximumThetaRad?: number; maximumRadiusRe?: number } = {},
): ObstacleShape {
  const thetaSamples = Math.max(16, Math.floor(options.thetaSamples ?? 160));
  const azimuthSamples = Math.max(8, Math.floor(options.azimuthSamples ?? 64));
  const maximumThetaRad = Math.min(Math.PI, Math.max(0.1, options.maximumThetaRad ?? (150 * Math.PI) / 180));
  const ceilingRe = Math.max(1, options.maximumRadiusRe ?? 90);
  const gap = Math.max(0, gapRe);
  const table = new Float32Array((thetaSamples + 1) * azimuthSamples);
  let maximumRadiusRe = 0;
  let previousRing: number[] = [];
  for (let thetaIndex = 0; thetaIndex <= thetaSamples; thetaIndex += 1) {
    const theta = (thetaIndex / thetaSamples) * maximumThetaRad;
    const ring: number[] = [];
    for (let azimuthIndex = 0; azimuthIndex < azimuthSamples; azimuthIndex += 1) {
      const azimuth = (azimuthIndex / azimuthSamples) * Math.PI * 2;
      const boundary = boundaryRadiusForDirection(theta, azimuth);
      const usable = Number.isFinite(boundary) && boundary > 0
        ? Math.min(ceilingRe, boundary + gap)
        : (previousRing[azimuthIndex] ?? gap + 1);
      ring.push(usable);
      table[thetaIndex * azimuthSamples + azimuthIndex] = usable;
      if (usable > maximumRadiusRe) maximumRadiusRe = usable;
    }
    previousRing = ring;
  }
  const noseRadiusRe = table[0] ?? gap + 1;
  return {
    shaped: true,
    noseRadiusRe,
    maximumRadiusRe,
    // The same array `radiusAt` reads, handed over so the streamline solve can
    // hoist the azimuth half of this interpolation out of its inner loop.
    grid: { values: table, thetaSamples, azimuthSamples, maximumThetaRad },
    radiusAt(thetaRad: number, azimuthRad: number) {
      const theta = clamp(thetaRad, 0, maximumThetaRad);
      const thetaPosition = (theta / maximumThetaRad) * thetaSamples;
      const thetaLow = Math.min(thetaSamples - 1, Math.floor(thetaPosition));
      const thetaFraction = thetaPosition - thetaLow;
      const azimuthPosition = (((azimuthRad / (Math.PI * 2)) % 1) + 1) % 1 * azimuthSamples;
      const azimuthLow = Math.floor(azimuthPosition) % azimuthSamples;
      const azimuthHigh = (azimuthLow + 1) % azimuthSamples;
      const azimuthFraction = azimuthPosition - Math.floor(azimuthPosition);
      const low = table[thetaLow * azimuthSamples + azimuthLow]!
        + (table[thetaLow * azimuthSamples + azimuthHigh]! - table[thetaLow * azimuthSamples + azimuthLow]!) * azimuthFraction;
      const high = table[(thetaLow + 1) * azimuthSamples + azimuthLow]!
        + (table[(thetaLow + 1) * azimuthSamples + azimuthHigh]! - table[(thetaLow + 1) * azimuthSamples + azimuthLow]!) * azimuthFraction;
      return low + (high - low) * thetaFraction;
    },
  };
}

export interface TeachingFlowPoint {
  xRe: number;
  yRe: number;
  zRe: number;
}

interface ModelTracer {
  path: ProjectedAdvectionPath;
  plane: GeospaceStructurePlane;
  phase: number;
}

const defaultPlanePosition: PlanePositionMapper = (xRe, crossRe, plane) =>
  plane === "equatorial"
    ? new THREE.Vector3(xRe, 0, crossRe)
    : new THREE.Vector3(xRe, crossRe, 0);

const defaultGsmPosition: GsmPositionMapper = (xRe, yRe, zRe) => new THREE.Vector3(xRe, yRe, zRe);

function clamp(value: number, minimum = 0, maximum = 1) {
  return Math.min(maximum, Math.max(minimum, value));
}

function smoothstep(edge0: number, edge1: number, value: number) {
  const normalized = clamp((value - edge0) / Math.max(Number.EPSILON, edge1 - edge0));
  return normalized * normalized * (3 - 2 * normalized);
}

function validNonnegative(value: number | null): value is number {
  return value !== null && Number.isFinite(value) && value >= 0;
}

/**
 * Maps real upstream bulk quantities to glyph prominence. This is deliberately
 * separate from glyph motion: it makes no individual-particle claim.
 */
export function solarWindIntensityEncoding(
  speedKps: number | null,
  densityCm3: number | null,
): SolarWindIntensityEncoding {
  if (!validNonnegative(speedKps) || !validNonnegative(densityCm3)) {
    return {
      available: false,
      normalizedSpeed: 0,
      normalizedDensity: 0,
      normalizedPressureCue: 0,
      activeFraction: 0,
      opacity: 0,
      pointSize: 0,
    };
  }
  const normalizedSpeed = clamp((speedKps - 250) / 650);
  const normalizedDensity = clamp(
    (Math.log10(Math.max(0.1, densityCm3)) - Math.log10(0.1))
      / (Math.log10(50) - Math.log10(0.1)),
  );
  const pressureCue = densityCm3 * (speedKps / 400) ** 2;
  const normalizedPressureCue = clamp(
    (Math.log10(Math.max(0.05, pressureCue)) - Math.log10(0.05))
      / (Math.log10(30) - Math.log10(0.05)),
  );
  return {
    available: true,
    normalizedSpeed,
    normalizedDensity,
    normalizedPressureCue,
    activeFraction: 0.14 + 0.8 * normalizedDensity,
    // GLYPH SIZE AND BRIGHTNESS, RAISED 2026-08-27.
    //
    // Sean, on the shipped build at a quiet wind: *"the particles are a bit
    // too small and diffuse now."* At his own drivers — V 260 km/s, which is
    // 0.015 of the speed range — both of these expressions sat within a few
    // percent of their floors, so the shower he was looking at was drawn at
    // very nearly the smallest and dimmest this layer can draw. The floors
    // move up; the SLOPES move up with them, so a fast dense wind is still
    // drawn bigger and brighter than a slow thin one and the encoding is not
    // flattened. Both remain display choices and both are named as such on
    // the card.
    opacity: 0.36 + 0.46 * (0.4 * normalizedSpeed + 0.6 * normalizedPressureCue),
    pointSize: 2.45 + 1.15 * (0.45 * normalizedSpeed + 0.55 * normalizedDensity),
  };
}

export function goesXrayClass(fluxWm2: number | null): string {
  if (fluxWm2 === null || !Number.isFinite(fluxWm2) || fluxWm2 <= 0) return "—";
  let letter: "A" | "B" | "C" | "M" | "X" = "A";
  let base = 1e-8;
  if (fluxWm2 >= 1e-4) {
    letter = "X";
    base = 1e-4;
  } else if (fluxWm2 >= 1e-5) {
    letter = "M";
    base = 1e-5;
  } else if (fluxWm2 >= 1e-6) {
    letter = "C";
    base = 1e-6;
  } else if (fluxWm2 >= 1e-7) {
    letter = "B";
    base = 1e-7;
  }
  const multiplier = fluxWm2 / base;
  // CORRECTNESS FIX 2026-09-04: choose the format on the ROUNDED value, not the
  // raw one. Formatting first meant any flux in [9.95e-7, 1e-6) passed the
  // `< 10` test and then rounded up inside toFixed(1), printing "B10.0" — a
  // designation that does not exist on the GOES scale, for a flux that is a
  // whisker under C1.0. The same window sits at every decade boundary. The
  // truncated tenth is printed instead of promoting the flare, because a class
  // letter is a threshold the flux either crossed or did not.
  let printed = Math.round(multiplier * 10) / 10;
  if (printed >= 10 && letter !== "X") printed = Math.floor(multiplier * 10) / 10;
  return `${letter}${printed < 10 ? printed.toFixed(1) : printed.toFixed(0)}`;
}

/**
 * The measured irradiance, turned into everything the layer draws.
 *
 * ## Why the intensities are shaped the way they are
 *
 * The first version of this gave the tint a flat opacity of 0.22 + 0.34n and
 * spread it over the whole sunlit hemisphere as pow(cos, 0.55). Two things
 * followed, and both were reported as "the layer shows nothing". The 0.55
 * exponent flattens the incidence profile, so instead of concentrating where
 * the Sun is overhead the tint was a near-uniform wash; whenever the camera
 * happened to look near the sub-solar point that wash covered the entire
 * visible disc with no edge anywhere to see it against. And its whole range,
 * 0.22 at A1 to 0.56 at X10, sat close enough to the globe's own solar
 * shading — in the globe's own cyan — that switching the layer on changed
 * nothing a reader could attribute to it.
 *
 * So the layer now says three separate things, each keyed to something real:
 *
 * - **How directly the Sun bears on each point**: the tint is now cos(solar
 *   zenith angle) exactly, unflattened. That is the true geometric factor for
 *   flux crossing a horizontal surface, it is the same cos that sets the
 *   Chapman ionization profile the D-region responds to, and it makes the
 *   picture concentrate at the sub-solar point instead of washing the disc.
 * - **How much flux**: `exposureOpacity` is the sub-solar peak and rises
 *   steeply with class, so an A-class Sun really is barely there and an X
 *   really is alarming.
 * - **Where day ends**: `terminatorOpacity` paints the shadow edge itself and
 *   stays legible at every class, because which hemisphere faces the Sun is
 *   geometry, not flux. For photons that edge is genuinely sharp — nothing
 *   bends them and nothing scatters them into the shadow — which is the
 *   contrast with the charged solar wind the site exists to teach.
 */
export function xrayIrradianceEncoding(fluxWm2: number | null): XrayIrradianceEncoding {
  if (fluxWm2 === null || !Number.isFinite(fluxWm2) || fluxWm2 <= 0) {
    return {
      available: false,
      className: "—",
      normalizedFlux: 0,
      exposureOpacity: 0,
      terminatorOpacity: 0,
      photonRayFraction: 0,
      photonRayOpacity: 0,
      activityState: "none",
    };
  }
  // A1 through X10 spans five decades. Clamping preserves honest ordering
  // without pretending that screen brightness is a calibrated radiometer.
  const normalizedFlux = clamp((Math.log10(fluxWm2) + 8) / 5);
  return {
    available: true,
    className: goesXrayClass(fluxWm2),
    normalizedFlux,
    exposureOpacity: 0.12 + 0.78 * normalizedFlux ** 1.7,
    terminatorOpacity: 0.45 + 0.35 * normalizedFlux,
    // Population is linear in the same clamped log-flux position the tint
    // uses, so the ray count and the tint tell one story. The floor is not
    // zero: a background Sun really is still delivering photons, and a layer
    // that draws nothing at A class would read as broken rather than quiet.
    photonRayFraction: 0.08 + 0.92 * normalizedFlux,
    photonRayOpacity: 0.2 + 0.7 * normalizedFlux ** 1.3,
    activityState: fluxWm2 >= 1e-4 ? "major-flare" : fluxWm2 >= 1e-5 ? "flare" : "background",
  };
}

/**
 * ## The species mix — the shower's quantity
 *
 * The solar wind is plasma, and essentially ALL of it is charged: protons
 * (the bulk by number), He²⁺ alpha particles (a few percent), and the
 * electrons that keep it neutral. The UNCHARGED thing the Sun sends this way
 * is electromagnetic radiation — the site's X-ray layer — and that is the
 * teaching point: everything in the wind is turned aside by the field to some
 * degree; light is not turned at all.
 *
 * The L1 plasma feed publishes the proton number density; it does NOT publish
 * the alpha abundance, so the canonical slow-wind value nα/np ≈ 4% is assumed
 * and stated (the observed range is roughly 1–5%, rising toward ~8% in some
 * fast streams and CMEs). Quasi-neutrality then fixes the electrons:
 * ne = np + 2·nα. Every fraction below follows from those two statements and
 * the one measured number — nothing else is invented.
 */
export const ALPHA_TO_PROTON_NUMBER_RATIO_ASSUMED = 0.04;

export type SolarWindSpecies = "proton" | "alpha" | "electron";

export interface SolarWindSpeciesMix {
  /** Number fractions of the total (p + α + e) population; sum to 1. */
  protonFraction: number;
  alphaFraction: number;
  electronFraction: number;
  /** The stated, not measured, He²⁺/H⁺ number ratio the mix assumes. */
  assumedAlphaRatio: number;
}

/** The species number fractions implied by the assumed alpha ratio. */
export function solarWindSpeciesMix(
  alphaRatio = ALPHA_TO_PROTON_NUMBER_RATIO_ASSUMED,
): SolarWindSpeciesMix {
  const ratio = Math.min(0.2, Math.max(0, alphaRatio));
  // Per unit proton density: protons 1, alphas ρ, electrons 1 + 2ρ.
  const total = 2 + 3 * ratio;
  return {
    protonFraction: 1 / total,
    alphaFraction: ratio / total,
    electronFraction: (1 + 2 * ratio) / total,
    assumedAlphaRatio: ratio,
  };
}

/**
 * One plasma, sorted by the sign of the charge and by mass.
 *
 * The three colours used to sit in one amber family. That is a defensible idea
 * and it was an illegible picture: at the size these actually render, a reader
 * saw a single undifferentiated shower, and the species split that the
 * transport goes to the trouble of drawing was invisible. They now separate on
 * the one property that decides where a particle ends up — its CHARGE. The
 * positive ions stay warm. H⁺ is THE amber and is deliberately unchanged: it is
 * the bulk of the drawn population and the thing the layer was built around.
 * e⁻ is the pale cream of the same gold family, so the 98% of the shower that
 * is H⁺ and e⁻ reads as one thing. He²⁺ is the soft periwinkle #8b87e8: the
 * single cool accent, in the one lane this site's colour ledger leaves open for
 * a rare bright mark. The card says so in those words.
 *
 * Size carries the same story on a second channel, which is what keeps this
 * readable for a reader who cannot use the hue. It is an ORDER — heavy, middle,
 * light — and as of 2026-08-27 it is deliberately NOT a literal ratio.
 *
 * It was one for a day. The alpha drew at 2.0 so that its drawn AREA would be
 * exactly the four-proton mass ratio, and Sean read the result as a rendering
 * fault: *"I think the blue dots look weird."* The arithmetic agreed with him.
 * Four times the area, times a brightness correction that pinned at the ceiling
 * (below), put about three times a proton's light into a species that is 2% of
 * the plasma — and an area ratio nobody can decode off a three-pixel glyph is
 * not teaching, so the encoding was buying a misread at full price.
 *
 * So the alpha draws at 1.45 — area about 2.1x the proton's, still unmistakably
 * the big heavy one — and the true mass ratio of 4 is STATED rather than drawn:
 * it is in the legend now, as the bulk energy each species carries at the
 * measured wind speed, which is a number a reader can actually read.
 *
 * The electron draws at 0.85. It is off the area-by-mass rule and has to be —
 * it is 1/1836 of a proton, and area-by-mass would draw it at 0.023, which is
 * nothing at all — so it is simply smaller than both ions because it is lighter
 * than both ions. It was 0.7, and 0.7 was too small for a different reason: the
 * cream's only separation from the amber is lightness and yellow-chroma, and
 * halving its area against the proton cancelled the lightness half. Sean, on
 * the shipped picture: *"it still looks like there are particles missing."* He
 * was looking for the 51% species the legend promises and could not find it.
 *
 * See `SOLAR_WIND_ALPHA_LUMINANCE_GAIN` below for the brightness half of the
 * same repair, and `SOLAR_WIND_SPECIES_TRAIL_FADE_EXPONENT` for the third
 * channel. NONE of them changes how MANY of any species is drawn.
 *
 * The choice is measured, not asserted. In CIELAB, and again through simulated
 * protanopia, deuteranopia and tritanopia, EVERY pair of species clears 25 in
 * EVERY one of those vision types, both as hex codes and AS DRAWN through the
 * luminance correction: the worst pair measures 29.3 raw and 28.2 as drawn,
 * and it is H⁺ against e⁻ under tritanopia — the gold family's own internal
 * split, not the accent. The old scheme's H⁺/He²⁺ pair was 13.7 under
 * deuteranopia, which is the arithmetic of why nobody could see it. There is
 * no colour-vision toggle behind these numbers and there is not meant to be:
 * the default has to be readable on its own. The electron is also held away from the two pale cool things already in
 * this scene — the X-ray layer's photon streaks (#dff6ff) and the boundary
 * ribs — because this layer's teaching point is that light does NOT deflect
 * and everything in this shower does. An electron that looked like a photon
 * would undo the lesson the shower exists to give.
 */
/**
 * The X-ray layer's photon streak colour, named because the species palette
 * has to be held away from it.
 *
 * This layer exists to teach that light does NOT deflect and everything in
 * the wind DOES. An electron drawn in the photons' own pale cool colour would
 * undo that lesson, so the distance between them is an invariant rather than
 * a coincidence, and `solar-wind-species-legibility.test.ts` measures it.
 * Declared here, used by `createPhotonStreakMaterial` below, so the test and
 * the shader read the same value instead of two copies drifting apart.
 */
export const XRAY_PHOTON_STREAK_COLOR_HEX = "#dff6ff";

export const SOLAR_WIND_SPECIES_PRESENTATION: Record<SolarWindSpecies, {
  label: string;
  symbol: string;
  colorHex: string;
  pointScale: number;
}> = {
  proton: { label: "proton", symbol: "H⁺", colorHex: "#f2a648", pointScale: 1 },
  alpha: { label: "alpha (He²⁺)", symbol: "He²⁺", colorHex: "#8b87e8", pointScale: 1.45 },
  electron: { label: "electron", symbol: "e⁻", colorHex: "#ffe4ab", pointScale: 0.85 },
};

/**
 * ## WHY THE SHOWER IS GOLD AGAIN, AND WHY ONE SPECIES IS NOT
 *
 * Sean, 2026-08-27: *"the solar wind looked so good when we had that golden
 * color scale. I get why you chose red and blue since those are the colors of
 * the ring current and radiation belts."*
 *
 * The second sentence is a defect report and it is correct. Measured as plain
 * CIELAB ΔE against the colours the two neighbouring layers actually draw in,
 * the palette that shipped until today sat ON TOP of them: the crimson He²⁺
 * `#d33a52` was 14 from the ring current's `#b52d2c`, and the blue e⁻
 * `#8fbdf5` was 22 from the belts' `#5ac4d8`. Below about 15 two colours read
 * as the same colour, so with all three layers on — which is how he looks at
 * it — the wind was drawn in the other two layers' own two hues. That is why
 * his screenshot reads as red-and-blue speckle instead of as a wind.
 *
 * H⁺ is 47% of the drawn population and e⁻ is 51%, so putting BOTH of them in
 * the gold family makes 98% of the drawn glyphs gold and the shower reads as
 * the golden thing he remembers. H⁺ keeps `#f2a648` exactly; e⁻ moves to the
 * pale cream `#ffe4ab`, which is very close to the `#ffe4ab` the amber family
 * used before species existed.
 *
 * ## WHY THE THIRD ONE COULD NOT JOIN THEM, MEASURED
 *
 * He²⁺ was asked to become a copper or a bronze, and it cannot, and this is
 * arithmetic rather than preference. Two facts collide:
 *
 *   - `SOLAR_WIND_ALPHA_LUMINANCE_GAIN` below equalises the LIGHT each glyph
 *     emits, which is exactly what removes LIGHTNESS as a channel. What is
 *     left to tell two species apart is chromaticity alone.
 *   - Under tritanopia the yellow–blue axis is gone as well. Two warm colours
 *     at equal luminance then differ only in a*, and two GOLDS differ in a*
 *     by almost nothing.
 *
 * Searched exhaustively on an 8-step sRGB grid — 309 candidate pale golds ×
 * 1,788 candidate coppers, every pair scored in normal vision and all three
 * dichromacies both before and after the correction — the number of warm
 * three-species palettes that clear the shipped floor of 25 with the alpha
 * still drawn at 0.75–1.35× the proton's luminance is ZERO. The best warm
 * candidate reaches 17.5. The old amber family this repo already scores as a
 * negative control fails the same way: H⁺ against He²⁺ measured 13.7.
 *
 * So the trace species carries the separation, on the one axis a gold family
 * leaves free — and the choice of cool is a fact about THIS SITE's colour
 * ledger before it is anything about colour blindness. The ring-current legend
 * ramp (`#2b1436 → #7b2f8f → #e05a8a → #ff9a5c → #ffe6a8`) already owns the
 * whole warm-and-magenta lane as meaning-carrying colour, and gold itself is
 * the other 98% of this shower, so a copper, bronze, rose or vermilion accent
 * would land a moving warm dot inside a neighbouring layer's own ramp. That is
 * the defect class that retired the crimson wind at ΔE 14.
 *
 * ## WHICH COOL, AND WHY IT MOVED ON 2026-08-27
 *
 * It shipped as `#6d5cff` for one day and Sean said *"I think the blue dots
 * look weird."* He was reading a real defect, not a preference. `#6d5cff` is
 * near-maximum chroma (Lab a* +50, b* −79) AND dark enough to demand a 2.57x
 * luminance gain — and at the quiet wind's drawn opacity of 0.52 that gain
 * lands at 0.52 x 2.57 = 1.33, which the shader's `min(1.0, …)` ceiling cuts
 * back to 1.0. Every alpha was therefore PINNED at maximum brightness while
 * its amber neighbours sat at 0.52, across the whole quiet-to-moderate range,
 * so the alphas never breathed with the field the way everything else does.
 * Round, oversized, ceiling-bright, maximum-chroma and trail-less in a warm
 * streaked field is what a rendering artifact looks like.
 *
 * `#8b87e8` is the same idea at half the shout: Lab L* 60.5, a* +24.9,
 * b* −48.7. The required gain falls to 1.63, so 0.52 x 1.63 = 0.85 fits UNDER
 * the ceiling — the full correction is applied for the first time, and the
 * alphas modulate with the measured conditions like every other glyph. The
 * ceiling now binds only above about 55% of the drive range instead of almost
 * immediately. Measured: 36 from the nearest ring-current stop and 37 from the
 * nearest belt stop, so it collides with neither; 108 from the amber and 89
 * from the cream in normal vision; and the palette scores 29.3 at its worst
 * pair raw and 28.2 as drawn across all four vision types, against a floor of
 * 25. It is 2% of the population — a rare spark in a gold shower, not a second
 * colour family.
 */

/**
 * ## Finding a species there are twenty-one of
 *
 * Sean, on the shipped shower: *"you don't really get to see the species
 * overall because e- and H+ dominate... can we exaggerate so that we see all
 * the particles a little more?"*
 *
 * Measured, at the wind blowing while this was written (V 271 km/s, nₚ 1.9
 * cm⁻³): 1,142 tracers drawn, of which 582 are electrons, 539 are protons and
 * TWENTY-ONE are alphas. They were on screen the whole time and nobody could
 * find one, which is a different problem from not being there and has a
 * different fix.
 *
 * THE FIX IS NOT TO DRAW MORE OF THEM. Over-sampling the alphas would make the
 * drawn proportions disagree with the proportions the legend prints beside
 * them, and then either the picture or the legend is lying. Every count in this
 * layer still comes from `solarWindSpeciesForIndex` on the measured mix, and
 * nothing here touches it.
 *
 * WHAT WAS ACTUALLY WRONG IS IN THE PALETTE, AND IT IS MEASURABLE. These three
 * colours were chosen for HUE separation — every pair is at least 37.9 apart in
 * CIELAB under normal vision and under all three dichromacies, which
 * `solar-wind-species-legibility.test.ts` measures. Nobody checked what they
 * do to BRIGHTNESS. In relative luminance (Rec. 709, on linearised sRGB):
 *
 *   e⁻   #8fbdf5   0.4883
 *   H⁺   #f2a648   0.4662     <- within 5% of the electron
 *   He²⁺ #d33a52   0.1748     <- 2.79x DARKER than either
 *
 * The shower draws with additive blending on a near-black sky, so light out is
 * the colour's luminance times the alpha it is drawn at. Drawn at the same
 * alpha as everything else, an alpha particle therefore emits 36% of the light
 * the other two do. The rarest species was also, by 2.7x, the dimmest — and
 * a dim #d33a52 at two pixels does not read as crimson at all, it reads as a
 * darker amber. That is a property of the hex code and not of the plasma, so it
 * is divided back out here.
 *
 * This is a CORRECTION, not an exaggeration. It puts an alpha on the same
 * footing as a proton — the same light from the same glyph at the same point in
 * its ride — so that a species' weight on screen is decided by how many there
 * are and by how big it is, and not by which colour it was assigned. The gain
 * is computed from the palette rather than typed, so it cannot drift if a
 * colour is ever revisited, and it is clamped at full opacity so no glyph can
 * be driven past what the measured conditions allow. Above about 55% of the
 * drive range the clamp binds and the alphas stop keeping up with the rest of
 * the shower; that is the honest cost of the ceiling and it is stated in the
 * test. At the old `#6d5cff` that threshold was 6% of the drive range, which
 * is to say the clamp bound at every wind anyone was ever likely to look at.
 *
 * The other half of the repair is size, and it is `SOLAR_WIND_SPECIES_PRESENTATION`'s
 * business: the alpha draws at 1.45, which makes its AREA about 2.1x the
 * proton's. It drew at 2.0 — area exactly the mass ratio of 4 — for one day,
 * and that combined with the ceiling-pinned brightness above put roughly 3x a
 * proton's light into each 2%-of-the-plasma glyph. At 1.45 with the gain no
 * longer pinned, an alpha glyph emits about 2.1x a proton's light, which is
 * exactly its drawn area: the correction equalises light PER PIXEL, so what is
 * left over is the size channel and nothing else.
 *
 * Measured on the built bundle at the live wind, three frames each, over the
 * same 520 x 540 px of drawn shower, against the shipped 1.35 and no gain —
 * the size change and this correction together:
 *
 *   brightest crimson mark        84 / 105 / 83   ->   232 / 199 / 96
 *   crimson marks found           17 /  19 / 17   ->    33 /  29 / 29
 *   largest single crimson mark    4 px           ->     8 px
 *   crimson ink                   36 /  38 / 43   ->    74 /  64 / 74
 *   ALPHAS ON SCREEN              21              ->    21   (unchanged)
 *
 * The last row is the argument: the same particles, in the same places, as the
 * same share of the population — found. (Rows two and three count what a
 * colour classifier can pick out of a screenshot, which is more than 21
 * because a bright glyph and its streak can separate; row five is arithmetic
 * on the measured mix and is the true number.)
 */
export const SOLAR_WIND_SPECIES_RELATIVE_LUMINANCE: Record<SolarWindSpecies, number> = (() => {
  const channel = (value: number) => {
    const srgb = value / 255;
    return srgb <= 0.04045 ? srgb / 12.92 : ((srgb + 0.055) / 1.055) ** 2.4;
  };
  const luminance = (hex: string) => {
    const value = Number.parseInt(hex.slice(1), 16);
    return 0.2126 * channel((value >> 16) & 0xff)
      + 0.7152 * channel((value >> 8) & 0xff)
      + 0.0722 * channel(value & 0xff);
  };
  return {
    proton: luminance(SOLAR_WIND_SPECIES_PRESENTATION.proton.colorHex),
    alpha: luminance(SOLAR_WIND_SPECIES_PRESENTATION.alpha.colorHex),
    electron: luminance(SOLAR_WIND_SPECIES_PRESENTATION.electron.colorHex),
  };
})();

/**
 * The alpha's drawn opacity is multiplied by this (1.63 at the settled
 * palette) so that its glyph emits the same light as the ANCHOR species' glyph
 * does. Read the block above for why the correction exists at all, and for why
 * the number fell from 2.57 when the accent moved to `#8b87e8`: at 2.57 the
 * ceiling below cut the correction off at the quiet wind's own opacity, so the
 * honest correction was never actually applied — it was replaced by a pin at
 * full brightness. At 1.63 it fits.
 *
 * ## WHY THE TARGET IS THE PROTON AND NO LONGER THE BRIGHTEST SPECIES
 *
 * It was the brightest, and with the old palette that made no difference: e⁻
 * and H⁺ were within 5% of each other, so "the brightest" and "the proton"
 * were the same number. With a pale cream electron they are not — the cream is
 * 1.71× the amber's luminance — and targeting the brightest would demand a
 * gain of 2.78 rather than 1.63.
 *
 * That extra gain is not free, and the cost is measurable rather than
 * aesthetic. Additive blending CLIPS: scaling a dark saturated colour past the
 * top of the gamut washes its hue out toward white, and a washed-out indigo is
 * an amber. Scored the way `solar-wind-species-legibility.test.ts` scores the
 * palette, but on the colour AS DRAWN after the gain:
 *
 *   gain target      worst pair, all four vision types
 *   the proton       28.2      <- shipped
 *   the brightest    14.7      <- below the floor of 25; the hue is gone
 *
 * So the target is the anchor. The electron is left alone: it is brighter than
 * the other two and being brighter has never been the failure mode — the rare
 * species being the DIMMEST was. This is still a correction and not an
 * exaggeration, it is still computed from the palette rather than typed, and
 * it is still clamped at full opacity in the shader.
 */
export const SOLAR_WIND_ALPHA_LUMINANCE_GAIN = Math.max(
  1,
  SOLAR_WIND_SPECIES_RELATIVE_LUMINANCE.proton / SOLAR_WIND_SPECIES_RELATIVE_LUMINANCE.alpha,
);

/**
 * ## THE STREAK IS THE THIRD CHANNEL, AND IT CARRIES MASS
 *
 * Sean, on what he likes about this layer: *"I like that we can see different
 * particles and I like that they move differently based on what they interact
 * with and their speed."* The colour channel is spent (98% of the shower has to
 * stay gold) and the size channel is nearly spent (a 2 px glyph cannot be
 * halved again). What is left is CHARACTER, and it is free.
 *
 * Every tracer's streak is the same geometric length — it is the streamline
 * tangent cut to a fixed display length, and that is unchanged. What changes
 * per species is how fast the streak FADES OUT along that length. The trail
 * geometry interpolates a fade from 1 at the head to 0 at the tail; raising it
 * to a per-species exponent bends that ramp without moving a single vertex:
 *
 *   e⁻    0.60   the ramp decays more slowly — a longer, softer, wispier streak
 *   H⁺     1.0   unchanged, the reference
 *   He²⁺  1.50   the ramp decays faster — a short, heavy, stubby mark
 *
 * So the nimble species trails, the ponderous one does not, and mass reads as
 * motion character at a glyph size where nothing else survives. This is a
 * DRAWING CHOICE and the card says so. It is emphatically NOT a speed claim:
 * every particle in this shower rides the same measured bulk V, which is true
 * of the real plasma too, and the legend now prints the energies that follow
 * from that one speed and three masses.
 *
 * Nothing here changes how many of any species is drawn, where any of them
 * are, or how long any streak is.
 */
export const SOLAR_WIND_SPECIES_TRAIL_FADE_EXPONENT: Record<SolarWindSpecies, number> = {
  proton: 1,
  alpha: 1.5,
  electron: 0.6,
};

/**
 * ## DEPTH CUEING — WHY THE SHOWER IS NOT A SCREEN OF CONFETTI
 *
 * Sean, on the shipped shower: *"The solar wind is cool. but it is a bit too
 * intrusive now. The particles in the foreground sort of obscure things."*
 *
 * One cause, and it was in the vertex shader: `gl_PointSize = pointSize *
 * scale * pixelRatio`, with no distance term at all. Every tracer drew at the
 * same screen size whether it was 5 Rₑ from the lens or 40 Rₑ beyond Earth, so
 * the wind was a flat overlay ON the picture — noise on the glass — rather
 * than a volume you look THROUGH. The particles nearest the camera are the
 * ones with nothing behind them to be about, and they were competing with the
 * magnetosphere on equal terms.
 *
 * Two terms fix it, both measured against the CAMERA-TO-EARTH distance D, so
 * they work identically at every zoom rather than at one framing:
 *
 *   NEAR FADE    below 0.55·D a tracer fades toward 0.20 of its opacity,
 *                bottoming out at 0.15·D — right in front of the lens.
 *   FAR SHRINK   glyph size ramps 1.10 → 0.75 across 0 → 2.5·D, so distance
 *                reads as distance.
 *
 * The band is chosen so that the MID-FIELD — where Earth is, at viewDist ≈ D —
 * renders essentially as it did before: nearFade = 1.0 and depthSize ≈ 0.96.
 * That is what protects the behaviours this layer exists for. Cusp funnelling,
 * the snap-back, and the plasma-sheet / belt / ring-current destinations all
 * happen within a few Rₑ of Earth, which is to say at viewDist ≈ D at any
 * framing that shows them at all, so they sit at the top of the fade ramp. The
 * guided sub-population's ×1.35 opacity and ×1.3 size boosts are untouched.
 *
 * This is a DISPLAY CHOICE and the card says so: it changes what a tracer
 * looks like from where you are standing, and it changes neither how many
 * tracers there are, nor which species they are, nor where any of them go.
 */
/**
 * ## WHERE THE PICTURE STOPS CARRYING INFORMATION, AND WHY IT FADES THERE
 *
 * Sean, looking at the shower zoomed out: *"to see the weird overall geometry
 * of the solar wind field/layer"* — the wind had a visible CONICAL SILHOUETTE,
 * a narrow neck flaring into a fan, which is not what a plane-parallel front
 * looks like. Two things made it, and only one of them was ever going to be
 * fixed by drawing more particles.
 *
 * The first is the emission face. It is cut to the frame, but capped at 400 Rₑ
 * of impact parameter, and past that the shared ruler buys so little drawn
 * radius for so much physical distance that widening it is pointless: at a
 * zoomed-out frame the cap reaches about 905 drawn units against a corner at
 * about 1,550, so the face ENDS inside the picture and ends at a hard edge.
 * The second is plain perspective: a cylinder of parallel-moving particles seen
 * from a perspective camera converges, and converging parallel edges are a cone.
 * The hard edge is what makes the second one legible as a shape at all.
 *
 * ## SEAN'S OWN ARGUMENT IS THE FIX
 *
 * *"the more you zoom out the more you draw the more you bog down CPU… I mean,
 * eventually, you get particles that just move laterally and across earth with
 * no impact from the magnetosphere, right?"*
 *
 * Right, and it is measured. Mean transverse deflection at the terminator, by
 * impact-parameter band, from this layer's own flow solve:
 *
 *   0–13.5 Rₑ   124.8%      <- the obstacle
 *   13.5–27     15.0%
 *   27–40.5      3.6%
 *   40.5–54      1.3%
 *   54–68        0.6%
 *   68–81        0.3%       <- indistinguishable from a straight line
 *
 * So the magnetosphere's influence has a FINITE RANGE, and past about 40 Rₑ of
 * impact parameter every particle in the picture is doing the same undeflected
 * thing. A thousand of them teach exactly what a hundred teach. That is a fact
 * about the physics rather than a budget, which is what makes thinning the
 * outer field honest instead of a corner cut — and it is the reason MOST of the
 * solar wind sails past, which is the thing the layer exists to show.
 *
 * ## SO THE FACE THINS, AND THEN IT ENDS WITHOUT AN EDGE
 *
 * Two terms, both on the tracer's own transverse distance from the Sun–Earth
 * line, both converted from Rₑ to drawn units through the same ruler the face
 * is cut with, so they follow the zoom:
 *
 *   THIN   from full weight at 55 Rₑ down to half by 150 Rₑ — the wind carries
 *          on, drawn quietly, because every parcel out there is alike.
 *   TAPER  the outermost sixth of the drawn face falls to nothing, so the
 *          field has no silhouette for a reader to mistake for the shape of
 *          the solar wind.
 *
 * ## THE NUMBERS ARE SMALL BECAUSE THE RULER IS BRUTAL, AND THAT IS THE POINT
 *
 * On the shared radial ruler (Earth = 100 drawn units): 20 Rₑ draws at 590,
 * 40 at 658, 55 at 688, 150 at 786, and the 400 Rₑ cap at 908. So the entire
 * 40-to-400 Rₑ outer field — 90% of the physical span the face covers — lives
 * in the outermost quarter of the drawn radius, which is about half the drawn
 * AREA. That is exactly why the cone was so prominent: a huge, uniform,
 * uninformative outer field was being drawn at full weight into a thin drawn
 * annulus with a hard rim. It is also why the floor is HALF and not a tenth:
 * dim that annulus too far and the wind appears to STOP at 55 Rₑ, which is a
 * different lie in the same place.
 *
 * Counts, positions, paths and species are untouched: this is opacity. And it
 * is species-blind by construction — species come from the tracer's INDEX and
 * the fade from its POSITION, and the two are independent — so the drawn share
 * of each species is still its true share. The tests measure that directly.
 */
/**
 * ## THE MOTION IS THE SOLAR WIND'S, NOT THE MAGNETOSPHERE LAYER'S
 *
 * Sean, 2026-08-27: *"Yeah I guess the solar wind should move the same
 * regardless of what layer is turned on… I guess we should change that. The
 * particles should show all the different movements regardless."*
 *
 * That reverses the modifier invariant, which was his own earlier rule: the
 * particles belong to this layer and OTHER layers changed how they moved, so
 * cusp funnelling, the snap-back, the plasma-sheet feeding and the belt and
 * ring-current destinations only appeared once the magnetosphere layer was
 * switched on. He now wants the whole repertoire from the solar wind alone,
 * and he is right that a reader should not have to guess which second switch
 * unlocks the interesting half of a layer's behaviour.
 *
 * ## THE PROBLEM THAT COMES WITH IT, AND THE RULING
 *
 * The guided particles ride the MAGNETOSPHERE LAYER'S OWN TRACED FIELD LINES.
 * With that layer off, those lines are not on screen — so a reader with only
 * the wind on would watch a stream hook sharply toward the poles with nothing
 * in the picture to explain it. That is worse than not drawing the motion:
 * it reads as a rendering fault and it teaches nothing, because the thing
 * doing the bending is invisible.
 *
 * RULED: draw the motion always, and when the magnetosphere layer is off,
 * draw the MINIMUM that explains it — the guidance polylines the guided
 * particles are actually riding, and nothing else. Not the boundary, not the
 * full traced set, not the cusp funnels: only the lines with a particle on
 * them, at a fraction of the field-line layer's own weight. That keeps the
 * picture self-explaining without turning the solar wind layer into the
 * magnetosphere layer, which is what the modifier invariant existed to
 * prevent. The moment the magnetosphere layer comes on, the cue comes off and
 * its own field lines take over — the same rule the obstacle silhouette
 * already follows.
 *
 * ## THE HONESTY GUARANTEE SURVIVES, VISIBLY
 *
 * A guidance path is traced field-line model up to `schematicFromIndex` and
 * schematic Dungey transport after it. The cue inks those two differently —
 * SOLID for the traced part, a fifty-fifty DASH of a fixed length in Earth
 * radii for the schematic part — so the split is drawn rather than asserted,
 * and a particle riding a line the reader can now see is still riding a
 * MODELLED line. The card says so, and the legend gives the cue its own mark
 * with its own evidence class. Why the dash is measured in Earth radii rather
 * than in tessellation segments is in `SOLAR_WIND_GUIDANCE_CUE`.
 */
/**
 * WHERE THE GUIDED PARTICLES SIT IN THE TRANSPARENT DRAW ORDER, AND WHY.
 *
 * None of the transparent things in this scene write depth, so depth testing
 * cannot decide which of two of them is in front: draw order decides, and the
 * guided tracers were at the default 0 — under everything. Above them sat the
 * traced field lines and the ring-current illustration at 2, the ring-current
 * volume at 14 and the ring-current illustration group at 16, each compositing
 * over the tracers rather than behind them.
 *
 * MEASURED, on the deployed layer set (solar wind + magnetosphere + ring
 * current + aurora), 1440x900, ANGLE/D3D12 on an RTX 4080, by rendering the
 * identical scene with and without the trapped tracers and differencing:
 * the four lit tracers inside the ring current changed 88 pixels at a mean
 * delta of 47.5/765, and the SAME four tracers with the ring-current torus and
 * the field-line curtain taken away changed 104 pixels at a mean delta of
 * 191.3. So the fills in front were not hiding the marks — they were washing
 * out three quarters of their contrast.
 *
 * 18 puts the guided population above both, and below nothing it needs to be
 * under. It changes NO geometry and NO opacity: the same marks in the same
 * places, composited in the order that lets them be seen. Depth testing is
 * untouched, so the Earth — which does write depth — still occludes a tracer
 * behind it exactly as before.
 *
 * The radiation-belt volume draws at 30 with depth testing OFF and will still
 * paint over these marks when that layer is on. That is that layer's own
 * declared choice and is left alone here.
 */
export const SOLAR_WIND_GUIDED_RENDER_ORDER = 18;

export const SOLAR_WIND_GUIDANCE_CUE = {
  /** The dim end of the magnetosphere layer's own |B| ramp, so the cue is visibly that family. */
  colorHex: "#4a4390",
  /** Traced field-line model geometry. */
  tracedOpacity: 0.34,
  /**
   * Schematic transport, drawn dotted at half the weight — BESIDE THE TRACED
   * CUE, which is the only situation in which the two are on screen together.
   */
  schematicOpacity: 0.17,
  /**
   * ...and the weight it is drawn at when the magnetosphere layer is on.
   *
   * The two halves of the cue are never on screen together: the traced half
   * comes off the moment that layer draws those same lines itself. So when the
   * magnetosphere layer is ON, the dotted half is alone, and the thing a
   * reader has to be able to tell it apart from is no longer a solid cue at
   * 0.34 — it is that layer's own field-line curtain, drawn far brighter and
   * in the same colour family the cue was deliberately given.
   *
   * MEASURED, 1440x900, ANGLE/D3D12 on an RTX 4080, by rendering the identical
   * frame with the dotted cue on and off and differencing: with the
   * magnetosphere layer OFF the cue changes 3,862 pixels at a mean delta of
   * 68.6/765. With that layer ON, the same cue at the same 0.17 changes 3,665
   * pixels — the marks all survive — but at a mean delta of 41.8, because it
   * is being added to pixels its own hue has already lit. At 0.42 that comes
   * back to 69.6, which is the contrast it had against empty space.
   *
   * Nothing about the evidence class moves with this. The class is carried by
   * DOTTED versus SOLID, and the dotting is untouched; what changes is how
   * hard the dots have to be pushed to be seen through a curtain of the same
   * colour. It is a display choice and the card says so.
   */
  schematicOpacityOverField: 0.42,
  /**
   * ## The dash is a LENGTH, not a count of tessellation segments
   *
   * The schematic stretch was dotted by emitting every third vertex-to-vertex
   * segment of the polyline. That reads as a rendering fault, and the
   * measurement says exactly why: the schematic legs are not tessellated
   * evenly. A drawn segment is 0.023 Earth radii inside the trapped helix and
   * 2.04 across the earthward injection leg, a spread of eighty-nine to one,
   * so "every third segment" is not a dash pattern at all. MEASURED at Sean's
   * own camera and layer set (1400x1168, all four space-weather layers on,
   * Earth drawn 131 px across), the marks it produced ran from 2.3 px to 48.5
   * px long with gaps up to 275 px, and FIVE of them were marks over 10 px
   * with gaps more than twice their own length on both sides. A mark with
   * nothing near it is not a dash, it is an object. Sean, looking at the
   * deployed site: *"On the right side there are dashed lines and they
   * shouldn't be there. Seems to be some artifact your agents left behind."*
   *
   * So the cycle is walked in ARC LENGTH along the path instead, and the cut
   * falls wherever it falls inside a tessellation segment. Half an Earth
   * radius of ink, half an Earth radius of gap: a fifty-fifty dash, which is
   * the least solid a dash can be while still reading as one line, and which
   * can never be mistaken for the solid ink this site reserves for traced
   * geometry. Because the period is a physical length rather than a screen
   * length, the same broken line reads the same way at every zoom, with a mark
   * always exactly as long as the gap beside it at any camera distance.
   *
   * MEASURED, same frame, same camera: marks 0.7 to 13.7 px, gaps a median of
   * 2.2 px and 11.2 px at the 90th percentile, and ZERO lone marks. Total
   * drawn ink goes from 6,114 px to 9,046 px, half as much again, because the
   * drawn fraction of the path rises from a third to a half. The weight is
   * untouched: what changed is the rhythm, not the ink's opacity.
   *
   * Nothing about the evidence class moves with this. The class is carried by
   * BROKEN versus SOLID and the breaks are still there, at a duty cycle that
   * makes them more obvious rather than less.
   */
  schematicDashOnRe: 0.5,
  /** ...and the gap after it. Equal to the mark, so it can never read as solid. */
  schematicDashOffRe: 0.5,
} as const;

export const SOLAR_WIND_FACE_FADE = {
  /** Impact parameter past which the flow solve deflects a parcel by under ~1%, Rₑ. */
  thinStartRe: 55,
  /** ...and where the thinning bottoms out, Rₑ. */
  thinEndRe: 150,
  /** How brightly the far, undeflected field is drawn. Never zero: it is still there. */
  thinFloor: 0.5,
  /** The outer fraction of the drawn face over which the edge falls to nothing. */
  edgeTaper: 0.16,
} as const;

export const SOLAR_WIND_DEPTH_CUE = {
  /** Opacity multiplier at the very front of the volume. */
  nearFadeFloor: 0.2,
  /** Fade band, as fractions of the camera-to-Earth distance. */
  nearFadeStart: 0.15,
  nearFadeEnd: 0.55,
  /** Glyph size multiplier at the camera and at the far end of the ramp. */
  sizeNear: 1.1,
  sizeFar: 0.75,
  /** How many camera-to-Earth distances the size ramp spans. */
  sizeRampSpan: 2.5,
} as const;

/**
 * The shared GLSL for both terms. One copy, so the head material and the trail
 * material can never drift into cueing depth differently, and so the numbers
 * above are the only place they are written down.
 *
 * `cameraToEarth` of zero means "nobody has told this visual where the camera
 * is" — a headless build, a test, a consumer that never calls
 * `setCameraDistance` — and in that case both terms are identically 1 and the
 * rendering is exactly what it was before depth cueing existed.
 */
const SOLAR_WIND_DEPTH_CUE_GLSL = `
      uniform float cameraToEarth;
      uniform float faceThinStart;
      uniform float faceThinEnd;
      uniform float faceEdgeStart;
      uniform float faceEdgeEnd;
      // See SOLAR_WIND_FACE_FADE. Scene X is GSM X, so the transverse distance
      // from the Sun-Earth line is the length of the other two components.
      // Zero faceEdgeEnd means nobody has cut a face yet and the fade is off.
      float solarWindFaceFade(vec3 localPosition) {
        if (faceEdgeEnd <= 0.0) return 1.0;
        float transverse = length(localPosition.yz);
        float thin = mix(1.0, ${SOLAR_WIND_FACE_FADE.thinFloor.toFixed(2)}, smoothstep(faceThinStart, faceThinEnd, transverse));
        float edge = 1.0 - smoothstep(faceEdgeStart, faceEdgeEnd, transverse);
        return thin * edge;
      }
      float solarWindNearFade(float viewDist) {
        if (cameraToEarth <= 0.0) return 1.0;
        return mix(
          ${SOLAR_WIND_DEPTH_CUE.nearFadeFloor.toFixed(2)},
          1.0,
          smoothstep(${SOLAR_WIND_DEPTH_CUE.nearFadeStart.toFixed(2)} * cameraToEarth, ${SOLAR_WIND_DEPTH_CUE.nearFadeEnd.toFixed(2)} * cameraToEarth, viewDist)
        );
      }
      float solarWindDepthSize(float viewDist) {
        if (cameraToEarth <= 0.0) return 1.0;
        return mix(
          ${SOLAR_WIND_DEPTH_CUE.sizeNear.toFixed(2)},
          ${SOLAR_WIND_DEPTH_CUE.sizeFar.toFixed(2)},
          clamp(viewDist / (${SOLAR_WIND_DEPTH_CUE.sizeRampSpan.toFixed(2)} * cameraToEarth), 0.0, 1.0)
        );
      }
`;

/**
 * ## THE MASS OF EACH SPECIES, IN KILOGRAMS
 *
 * CODATA rest masses. The alpha is the bare He²⁺ NUCLEUS — two protons and two
 * neutrons, the two electrons stripped — which is what the solar wind actually
 * carries and which is why the number is 3.97 proton masses rather than a
 * round 4. These are physical constants; nothing about them is measured here.
 */
export const SOLAR_WIND_SPECIES_MASS_KG: Record<SolarWindSpecies, number> = {
  proton: 1.67262192e-27,
  alpha: 6.6446573e-27,
  electron: 9.1093837e-31,
};

const JOULES_PER_ELECTRONVOLT = 1.602176634e-19;

/**
 * ## THE BULK ENERGY EACH SPECIES CARRIES, AT THE MEASURED WIND SPEED
 *
 * E = ½mv², with v the L1 bulk speed the layer is already drawing its cadence
 * from and m a physical constant. That is the whole calculation.
 *
 * ## WHY THIS IS THE LEGEND NOW, AND THE PROPORTION BAR IS NOT
 *
 * The bar's one unique job was dominance-at-a-glance, and at 51 / 47 / 2 it
 * could not do it: 2% of a 290 px bar is 5.5 px hard against the bar's own
 * border. It was drawn proportionally and Sean read the legend as saying the
 * wind has two constituents; it was then square-root eased — a declared
 * distortion — and he read the result as *"a small sliver to the right"*. Two
 * failures at one job. His own proposal replaced it: *"Perhaps the bar doesn't
 * show the percentages by area, it lists them and it gives energy levels of
 * particles shown and the percentages are with the color labels."* Taken.
 *
 * Nothing true is lost — the percentages were always text — and something true
 * is gained. The list stops being a colour key and starts carrying the REASON
 * the three species behave differently: one wind, one measured speed, three
 * masses spanning four orders of magnitude, and therefore three energies
 * spanning four orders of magnitude, printed in a column where a reader can
 * see it. It is also where the mass ratio of 4 now lives, after the alpha
 * glyph stopped drawing it as an area nobody could decode.
 *
 * ## EVIDENCE CLASS: DERIVED FROM A MEASUREMENT
 *
 * V is measured, at L1, by the same feed that drives everything else in this
 * layer. The masses are constants. The arithmetic invents nothing — but it is
 * arithmetic on a BULK measurement, so these are the energies implied for a
 * particle riding the measured flow, not a measurement of any individual
 * particle. The He²⁺ row keeps its "assumed" tag on its SHARE: the assumption
 * is how many alphas there are, not what each one carries.
 *
 * ## THE ONE PLACE THIS COULD TEACH A FALSEHOOD
 *
 * Electrons carry random thermal motion of order 10 eV — fifty times their
 * bulk-flow energy. The 0.19 eV printed here is the like-for-like comparison
 * with the ions, on the same one speed, and it would be a lie by omission
 * without the "(bulk)" tag beside it and the sentence on the card.
 *
 * Sanity anchor for anyone checking this: at V = 440 km/s the proton line
 * reads 1.0 keV, which is the textbook solar wind number.
 */
export function solarWindSpeciesBulkEnergyEv(speedKps: number | null): Record<SolarWindSpecies, number> | null {
  if (speedKps === null || !Number.isFinite(speedKps) || speedKps <= 0) return null;
  const metresPerSecond = speedKps * 1000;
  const energy = (species: SolarWindSpecies) =>
    0.5 * SOLAR_WIND_SPECIES_MASS_KG[species] * metresPerSecond * metresPerSecond / JOULES_PER_ELECTRONVOLT;
  return { proton: energy("proton"), alpha: energy("alpha"), electron: energy("electron") };
}

/** Two significant figures, without exponent notation. */
function toSignificantFigures(value: number, digits = 2): string {
  if (!(value > 0)) return "0";
  const magnitude = Math.floor(Math.log10(value));
  return value.toFixed(Math.max(0, digits - 1 - magnitude));
}

/**
 * `~350 eV` / `~1.4 keV` / `~0.19 eV` — the legend's own rendering of one
 * energy. The tilde is not hedging the arithmetic, which is exact; it is
 * hedging the two significant figures it is printed to.
 */
export function formatSolarWindBulkEnergy(electronVolts: number): string {
  return electronVolts >= 1000
    ? `~${toSignificantFigures(electronVolts / 1000)} keV`
    : `~${toSignificantFigures(electronVolts)} eV`;
}

/**
 * ## The legend's species list — WHICH IS THE LEGEND, as of 2026-08-27
 *
 * One row per species, each carrying the colour the shower actually draws it
 * in, the number fraction the measured plasma implies, and the bulk energy
 * that species carries at the measured wind speed: three swatches, three
 * numbers, three energies, equal billing, 2% printed as 2%.
 *
 * This used to be the row UNDER a proportion bar, and the division of labour
 * was what let the bar be square-root eased at all. The bar is gone — see
 * `solarWindSpeciesBulkEnergyEv` for why, and for why removing it removed a
 * declared distortion rather than adding one. What was the key is now the
 * whole legend, and it has never printed anything but the plasma's own
 * numbers.
 *
 * The order is the order in the plasma by number, most first, so the eye walks
 * down the list and finds the three things in the order they exist.
 */
export interface SolarWindSpeciesKeyCell {
  species: SolarWindSpecies;
  /** The colour the shower draws this species in — the presentation table's own value. */
  swatch: string;
  /** `H⁺ 47%` — the symbol and the number fraction, rounded the way the legend prints it. */
  text: string;
  fraction: number;
  /** `~350 eV` at the measured V, or null when no wind speed is available. */
  energyText: string | null;
  /** The same number unrounded, in electronvolts, or null. */
  energyEv: number | null;
  /**
   * True for the electron only. Its bulk-flow energy is ~50x smaller than its
   * thermal jiggle, so the row has to say which one it is printing.
   */
  energyIsBulkOnly: boolean;
}

export function solarWindSpeciesKey(
  mix = solarWindSpeciesMix(),
  speedKps: number | null = null,
): SolarWindSpeciesKeyCell[] {
  const fractions: Record<SolarWindSpecies, number> = {
    electron: mix.electronFraction,
    proton: mix.protonFraction,
    alpha: mix.alphaFraction,
  };
  const energies = solarWindSpeciesBulkEnergyEv(speedKps);
  // Plasma order by number: the pale cream, the amber, the periwinkle spark.
  return (["electron", "proton", "alpha"] as const).map((species) => {
    const presentation = SOLAR_WIND_SPECIES_PRESENTATION[species];
    const fraction = fractions[species];
    const energyEv = energies?.[species] ?? null;
    return {
      species,
      swatch: presentation.colorHex,
      // The alpha share is the one number here the L1 feed does not measure,
      // so the cell that prints it is also the cell that says so. Everything
      // else on this row is arithmetic on a measured density or a measured
      // speed.
      text: `${presentation.symbol} ${(fraction * 100).toFixed(0)}%${species === "alpha" ? " assumed" : ""}`,
      fraction,
      energyText: energyEv === null ? null : formatSolarWindBulkEnergy(energyEv),
      energyEv,
      energyIsBulkOnly: species === "electron",
    };
  });
}

const SPECIES_GOLDEN_FRACTION = 0.61803398875;

/** Where a thinned-out tracer's trail is collapsed to. Shared, not allocated per frame. */
const ZERO_TRAIL_POINT = new THREE.Vector3(0, 0, 0);

/**
 * Deterministic, prefix-balanced species assignment.
 *
 * The drawn population is a PREFIX of the particle buffer (the draw range
 * scales with measured density), so a block assignment would change the mix
 * whenever the density changed. A golden-ratio low-discrepancy sequence keeps
 * every prefix within a fraction of a percent of the stated mix — the tests
 * measure exactly that. This is illustrative sampling of measured bulk
 * totals: we measure plasma, not individual particles, and the card says so.
 */
export function solarWindSpeciesForIndex(index: number, mix = solarWindSpeciesMix()): SolarWindSpecies {
  const position = ((index + 0.5) * SPECIES_GOLDEN_FRACTION) % 1;
  if (position < mix.electronFraction) return "electron";
  if (position < mix.electronFraction + mix.protonFraction) return "proton";
  return "alpha";
}

const SPECIES_ATTRIBUTE_VALUE: Record<SolarWindSpecies, number> = { proton: 0, alpha: 1, electron: 2 };

/**
 * The tracer speed ramp: the same 0–1000 km/s linear encoding and palette the
 * BATS-R-US speed cut uses, so one visual language covers the measured wind
 * and the modelled flow. One source of truth for the plane-tracer colour and
 * the MHD cut's colour bar. The 3-D shower itself is coloured by SPECIES in
 * the species scheme; measured speed drives its motion cadence instead.
 */
export const SOLAR_WIND_SPEED_COLOR_HEX = ["#23486b", "#76e6a5", "#f5c96a"] as const;

export const SOLAR_WIND_SPEED_GRADIENT_CSS = `linear-gradient(90deg, ${SOLAR_WIND_SPEED_COLOR_HEX.join(", ")})`;

export const SOLAR_WIND_SPEED_RANGE_KPS: readonly [number, number] = [0, 1000];

const SOLAR_WIND_SPEED_STOPS = SOLAR_WIND_SPEED_COLOR_HEX.map((hex) => new THREE.Color(hex));

/** The drawn colour of a bulk speed, on the shared 0–1000 km/s ramp. */
export function solarWindSpeedColor(speedKps: number): THREE.Color {
  const [minimum, maximum] = SOLAR_WIND_SPEED_RANGE_KPS;
  const position = clamp((speedKps - minimum) / (maximum - minimum)) * (SOLAR_WIND_SPEED_STOPS.length - 1);
  const lowIndex = Math.min(SOLAR_WIND_SPEED_STOPS.length - 2, Math.floor(position));
  return SOLAR_WIND_SPEED_STOPS[lowIndex]!.clone()
    .lerp(SOLAR_WIND_SPEED_STOPS[lowIndex + 1]!, position - lowIndex);
}

/**
 * The A1-to-X10 flux ramp, in the site's own palette. One source of truth
 * for the globe's exposure tint and the legend's colour bar, so the two can
 * never silently disagree about what a given class looks like.
 */
// The A-to-X ramp. The dark end is deliberately dark — an A-class Sun should
// barely register — but it must not be so dark that the beam it colours reads
// as uncoloured against space. #12233d measured as effectively black once the
// streak whitening was applied to it; #1d3f6b is the same hue with enough
// lightness to survive as a colour at the bottom of the scale, which is where
// the Sun spends most of its time.
/**
 * Whether the published BATS-R-US plane tracers are drawn. They are not: on
 * the two cut planes they read as a pale sheet rather than as flow, which is
 * the opposite of what they are for. This is a display decision rather than a
 * dead branch, so it is named here where it can be found.
 */
const DRAW_PUBLISHED_PLANE_TRACERS = false;

/**
 * Where the drawn shower ends, down-tail, in Earth radii. See the long note in
 * `illustrativeUpstreamDomain` for why it is here and not at the terminator.
 */
export const DEFAULT_DOWNSTREAM_END_RE = -30;

/**
 * The domain span the display cadence and the streak length were tuned at:
 * an upstream face at 32 Re and an end at the terminator.
 *
 * Both of those quantities used to be written as fractions of the domain span,
 * which is fine while the span never changes and wrong the moment it does.
 * Doubling the domain would have doubled the apparent speed of every tracer and
 * doubled the length of every streak, and neither is a physical statement about
 * anything: the cadence is display motion driven by the measured bulk speed,
 * and the streak is where the tracer was a moment ago. Normalising both against
 * this reference span keeps them meaning what they meant before the tail was
 * drawn.
 */
const CADENCE_REFERENCE_SPAN_RE = 32;

const XRAY_FLUX_COLOR_HEX = ["#1d3f6b", "#29d4e3", "#f5c96a", "#ff7b78"] as const;

export const XRAY_FLUX_GRADIENT_CSS = `linear-gradient(90deg, ${XRAY_FLUX_COLOR_HEX.join(", ")})`;

const XRAY_FLUX_COLOR_STOPS = XRAY_FLUX_COLOR_HEX.map((hex) => new THREE.Color(hex));

function xrayFluxColor(normalizedFlux: number): THREE.Color {
  const position = clamp(normalizedFlux) * (XRAY_FLUX_COLOR_STOPS.length - 1);
  const lowIndex = Math.min(XRAY_FLUX_COLOR_STOPS.length - 2, Math.floor(position));
  const fraction = position - lowIndex;
  return XRAY_FLUX_COLOR_STOPS[lowIndex]!.clone().lerp(XRAY_FLUX_COLOR_STOPS[lowIndex + 1]!, fraction);
}

export function illustrativeUpstreamDomain(
  options: IllustrativeUpstreamFlowOptions = {},
): IllustrativeUpstreamDomain {
  const earthRadiusRe = Math.max(0.001, options.earthRadiusRe ?? 1);
  const requestedMagnetopause = options.magnetopauseStandoffRe ?? 10;
  const magnetopauseStandoffRe = Math.max(earthRadiusRe + 0.05, requestedMagnetopause);
  const gapRe = Math.max(0.1, options.magnetopauseGapRe ?? 1.25);
  const obstacle = options.boundaryRadiusForDirection
    ? tabulateObstacleShape(options.boundaryRadiusForDirection, gapRe)
    : sphericalObstacle(Math.max(earthRadiusRe + 0.1, magnetopauseStandoffRe + gapRe));
  const obstacleRadiusRe = Math.max(earthRadiusRe + 0.1, obstacle.noseRadiusRe);
  const upstreamStartRe = Math.max(
    obstacleRadiusRe + 0.5,
    options.upstreamStartRe ?? 32,
  );
  // WHERE THE SHOWER STOPS, AND WHY IT IS NO LONGER THE TERMINATOR.
  //
  // Sean, on the shipped build: "we need to have the solar wind go all the way
  // across the earth. it looks like it stops at the earth now. the particles
  // just sort of fade out of existence past the poles. in reality the majority
  // of the solar wind flows right over it."
  //
  // He is describing the truth. The magnetosheath does not terminate at the
  // obstacle: it wraps the dayside, accelerates down the flanks, streams over
  // the polar caps and carries on downstream, and the tail forms in that wake.
  // A picture in which the wind ends at the planet teaches that the planet
  // consumes it, and it leaves the magnetotail — where the substorm gets its
  // energy — with no visible source.
  //
  // THE MEASUREMENT THAT PUT THE END AT THE TERMINATOR, WHICH STANDS.
  //
  // Twice, on the solar-wind layer with nothing else on, the same reader said
  // the particles "form a shell around the Earth", as if Earth were emitting
  // the wind. That was measured and the cause was found, and none of it was
  // the flow solve — with the magnetosphere layer also on, the identical cloud
  // read correctly, and it was measured identical: same domain, same 2,200
  // tracers, same streak directions in both pictures.
  //
  // What closed the picture into a shell is the shared ruler's far field. Its
  // log-log slope past 24 Re is 0.14, so beyond the bow shock a large change in
  // physical distance is almost no change in drawn distance. Measured on the
  // live build with an end at -1.35x the nose (-15.0 Re):
  //
  //   - the upstream face at 32 Re drew at 6.43 drawn Earth radii;
  //   - the far end of the domain, whose tracers have been carried out to
  //     about 20 Re on the flanks, drew at 5.9 - 8% closer in, for flow that
  //     is 60% further away and travelling the other way;
  //   - the whole cloud spanned 3.80 to 6.43 drawn Earth radii, a 1.69:1 band,
  //     for physical radii spanning 11.4 to 34.0 Re, a 2.97:1 range.
  //
  // Every one of those numbers is still true. The ruler has not changed.
  //
  // WHY THE ANSWER WAS THE WRONG ONE ANYWAY.
  //
  // The previous pass concluded from that measurement that the tail could not
  // be drawn, and cut the domain at the terminator. But the measurement it had
  // already made contains its own refutation: the SAME cloud read correctly
  // when the boundary was on screen. The defect was never that departed flow
  // draws at the arriving flow's radius - it is that a reader given a band of
  // moving glyphs and an empty cavity, and nothing to tell them what the
  // cavity IS, reads the only thing left. The missing element was the
  // obstacle, not the tail.
  //
  // So the obstacle is drawn. `createSolarWindObstacleSilhouette` puts a faint
  // outline of the very surface these streamlines are solved against into the
  // layer's own group, whenever the magnetosphere layer is not already drawing
  // it. Nothing about it is invented: it is the same `ObstacleShape` the
  // tracers cannot penetrate, so the picture now shows a wind, an obstacle, and
  // a wake, which is what the reader was missing.
  //
  // WHAT THE END OF THE DOMAIN IS NOW, AND WHY.
  //
  // -30 Re. Three reasons, in order of weight:
  //
  //   - it carries the flow visibly past the poles and well downstream of the
  //     planet, which is the thing that was wrong;
  //   - it spans the inner plasma sheet (6-12 Re) that the substorm layer
  //     draws, so the wake and the region it feeds share one picture;
  //   - it stops inside NOAA's own published cut-plane grid, which is bounded
  //     at -55 Re, so the drawn wake never runs past the model domain that the
  //     MHD option would fill the same volume with.
  //
  // What the ruler still does past the taper is stated on the layer card
  // rather than fixed, because it cannot be fixed from here: down-tail
  // distance is compressed hard, so the drawn wake is far shorter than the
  // real one and its length must not be read as a distance.
  const downstreamEndRe = Math.min(
    -earthRadiusRe - 0.5,
    options.downstreamEndRe ?? DEFAULT_DOWNSTREAM_END_RE,
  );
  return {
    earthRadiusRe,
    magnetopauseStandoffRe,
    obstacleRadiusRe,
    obstacle,
    upstreamStartRe,
    downstreamEndRe,
  };
}

/**
 * Incompressible axisymmetric flow around a no-penetration obstacle.
 *
 * The conserved Stokes streamfunction psi = w^2 (1 - a^3 / r^3) is solved for
 * the transverse radius `w`, so a tracer cannot enter the obstacle and returns
 * smoothly to its upstream impact parameter down-tail. With a constant `a` this
 * is exactly potential flow past a sphere. With `a` varying by direction it is
 * no longer irrotational — but psi = 0 still lands exactly on the obstacle
 * surface, so it remains an exact no-penetration stream surface, which is the
 * property the picture depends on. It is a teaching cue either way, and the
 * layer says so.
 *
 * Deflection is radial in the transverse plane, so a tracer keeps its azimuth.
 * That is what lets the obstacle be sampled on the tracer's own meridian.
 */
export function teachingFlowPointAroundObstacle(
  xRe: number,
  impactYRe: number,
  impactZRe: number,
  obstacle: number | ObstacleShape,
): TeachingFlowPoint {
  const shape = typeof obstacle === "number" ? sphericalObstacle(obstacle) : obstacle;
  const impactRadius = Math.max(1e-4, Math.hypot(impactYRe, impactZRe));
  // Azimuth from GSM +z, matching magnetopausePointGsm.
  const azimuth = Math.atan2(impactYRe, impactZRe);
  // THE AZIMUTH HALF OF THE OBSTACLE LOOKUP CANNOT CHANGE INSIDE ONE SOLVE.
  //
  // A tracer is deflected radially in the transverse plane, so it keeps its
  // azimuth — the comment above this function has always said so. The
  // tabulated `radiusAt` nevertheless re-derived the azimuth cell, its
  // wrap-around neighbour and the blend between them on every bisection step:
  // two floating-point remainders and two floors, about twenty times per
  // solve. They are computed once here instead, and the loop is left with the
  // theta half. Same grid, same interpolation, same answer.
  // EVERY GRID FIELD IS READ INTO A LOCAL BEFORE THE LOOP, NOT INSIDE IT.
  //
  // This is not style. Measured on the deployed layer set at 4,600 tracers,
  // leaving `grid.values`, `grid.thetaSamples`, `grid.azimuthSamples` and
  // `grid.maximumThetaRad` as property loads inside the bisection — about
  // twenty reads of each per solve, twice per tracer, every frame — cost 5.4 ms
  // a frame against the same arithmetic reading locals.
  const grid = shape.grid;
  const gridValues = grid ? grid.values : null;
  const gridThetaSamples = grid ? grid.thetaSamples : 0;
  const gridAzimuthSamples = grid ? grid.azimuthSamples : 1;
  const gridMaximumTheta = grid ? grid.maximumThetaRad : 1;
  let azimuthLow = 0;
  let azimuthHigh = 0;
  let azimuthFraction = 0;
  if (grid) {
    const azimuthPosition = ((((azimuth / (Math.PI * 2)) % 1) + 1) % 1) * gridAzimuthSamples;
    azimuthLow = Math.floor(azimuthPosition) % gridAzimuthSamples;
    azimuthHigh = (azimuthLow + 1) % gridAzimuthSamples;
    azimuthFraction = azimuthPosition - Math.floor(azimuthPosition);
  }
  const xSquared = xRe * xRe;
  const impactSquared = impactRadius * impactRadius;
  const residual = (transverseRadius: number) => {
    const radiusSquared = xSquared + transverseRadius * transverseRadius;
    const radius = Math.sqrt(radiusSquared);
    const cosine = xRe / (radius > 1e-9 ? radius : 1e-9);
    let obstacleRadius: number;
    if (gridValues === null) {
      // A shape that carries no grid — a test double, or a future shape that
      // is not tabulated. Unchanged behaviour, through the interface.
      obstacleRadius = shape.radiusAt(Math.acos(clamp(cosine, -1, 1)), azimuth);
    } else {
      const theta = clamp(acosTabulated(cosine), 0, gridMaximumTheta);
      const thetaPosition = (theta / gridMaximumTheta) * gridThetaSamples;
      const thetaLow = Math.min(gridThetaSamples - 1, thetaPosition | 0);
      const thetaFraction = thetaPosition - thetaLow;
      const rowLow = thetaLow * gridAzimuthSamples;
      const rowHigh = rowLow + gridAzimuthSamples;
      const low = gridValues[rowLow + azimuthLow]!
        + (gridValues[rowLow + azimuthHigh]! - gridValues[rowLow + azimuthLow]!) * azimuthFraction;
      const high = gridValues[rowHigh + azimuthLow]!
        + (gridValues[rowHigh + azimuthHigh]! - gridValues[rowHigh + azimuthLow]!) * azimuthFraction;
      obstacleRadius = low + (high - low) * thetaFraction;
    }
    const streamFactor = 1 - obstacleRadius ** 3 / Math.max(Number.EPSILON, radiusSquared * radius);
    return transverseRadius * transverseRadius * streamFactor - impactSquared;
  };
  // psi is non-positive everywhere inside the obstacle, so bisecting up from a
  // point that is provably not past the root can only converge on a sign
  // change outside it. That is the guarantee: the returned point is never
  // inside, whatever shape `a` takes.
  //
  // THE FLOOR IS THE IMPACT PARAMETER, NOT ZERO. The stream factor is at most
  // 1 everywhere, so psi(impactRadius) = impactRadius² (streamFactor − 1) ≤ 0:
  // the root is never below the impact parameter, for any obstacle. Starting
  // there rather than at zero is exact — it discards an interval the root
  // cannot be in — and on the plane-parallel face, where impact parameters run
  // out past 150 Rₑ, it removes most of the bracket the bisection used to have
  // to halve its way across.
  let lower = impactRadius;
  let upper = impactRadius + Math.max(shape.maximumRadiusRe, 1);
  for (let guard = 0; guard < 40 && residual(upper) < 0; guard += 1) {
    upper += upper - lower;
  }
  // STOP AT A TOLERANCE RATHER THAN AT A FIXED ITERATION COUNT.
  //
  // This solve runs twice per tracer per frame — head and streak tail — and it
  // is the whole per-frame cost of this layer, so its iteration count is what
  // decides how many particles the layer can afford. It ran 28 halvings
  // unconditionally, which resolves a 32 Rₑ bracket to 1.2e-7 Rₑ: eight
  // millimetres, against a drawn Earth radius of a hundred pixels.
  //
  // The bar that matters is the DRAWN one. The ruler's steepest slope anywhere
  // is about 1 drawn Earth radius per Rₑ near the surface, so a tenth of a
  // thousandth of an Earth radius is a hundredth of a pixel at the worst place
  // in the scene and far less everywhere else. Reaching it takes about 18
  // halvings from a 32 Rₑ bracket and about 21 from the widest face, and the
  // ceiling is kept so a pathological bracket still terminates.
  const tolerance = 1e-4;
  for (let iteration = 0; iteration < 28 && upper - lower > tolerance; iteration += 1) {
    const middle = (lower + upper) / 2;
    if (residual(middle) < 0) lower = middle;
    else upper = middle;
  }
  const transverseRadius = upper;
  const transverseScale = transverseRadius / impactRadius;
  return {
    xRe,
    yRe: impactYRe * transverseScale,
    zRe: impactZRe * transverseScale,
  };
}

/**
 * Local flow speed, as a fraction of the free-stream speed, at a point in the
 * same flow the tracers already follow.
 *
 * The site drew this flow with ONE rate for every tracer everywhere: position
 * along the Sun–Earth line was `upstreamStart − progress × span`, so nothing
 * slowed at the obstacle, nothing stagnated at the nose, and nothing
 * accelerated down the flanks. Real flow does all three, and the owner's
 * opening complaint on 2026-08-12 — that the wind "still doesn't travel the
 * right way… just mostly uniform flow" — was exactly this.
 *
 * For potential flow past a sphere of radius a, with the free stream along the
 * Sun–Earth line, the classical solution is
 *
 *   v_r     = −U cos θ (1 − a³/r³)
 *   v_theta =  U sin θ (1 + a³/2r³)
 *
 * which gives 0 at the nose (a stagnation point), 1.5 U at the flank, and U
 * far upstream. Those three numbers are the whole teaching point, and they are
 * properties of the same streamfunction the tracer positions already solve, so
 * the picture stays self-consistent rather than gaining a second flow model.
 *
 * With a direction-varying obstacle this is a teaching cue rather than an
 * exact solution — the same caveat the position solve already carries and the
 * layer already states.
 */
export function teachingFlowVelocityFactors(
  xRe: number,
  yRe: number,
  zRe: number,
  obstacle: number | ObstacleShape,
): { speed: number; axial: number } {
  const shape = typeof obstacle === "number" ? sphericalObstacle(obstacle) : obstacle;
  const radius = Math.hypot(xRe, yRe, zRe);
  if (radius <= 1e-9) return { speed: 0, axial: 0 };
  const azimuth = Math.atan2(yRe, zRe);
  const polar = Math.acos(clamp(xRe / radius, -1, 1));
  const obstacleRadius = shape.radiusAt(polar, azimuth);
  // Strictly inside the obstacle there is no flow to report. The boundary
  // ITSELF is not excluded: the surface is where the classical solution has
  // its stagnation point and its 3/2 U flank maximum, and the position solve
  // puts tracers exactly there, so excluding it reported a still flank.
  if (radius < obstacleRadius) return { speed: 0, axial: 0 };
  const ratio = Math.min(1, (obstacleRadius / radius) ** 3);
  const cosine = Math.cos(polar);
  const sine = Math.sin(polar);
  const radial = -cosine * (1 - ratio);
  const tangential = sine * (1 + ratio / 2);
  // The component along the Sun–Earth line, which is what the march is
  // parameterised by. It is NOT the speed times cos(polar): the velocity is
  // not radial, and treating it as radial floors the FLANKS — where the flow
  // is fastest — to a crawl, which is the opposite of the physics.
  //   v_x = v_r cos(theta) − v_theta sin(theta)
  // and its magnitude is cos²(1 − a³/r³) + sin²(1 + a³/2r³), which is 0 at the
  // nose, 3/2 at the flank and 1 far upstream — the same three numbers as the
  // speed, because at all three the flow is along x.
  const axial = cosine * cosine * (1 - ratio) + sine * sine * (1 + ratio / 2);
  return { speed: Math.hypot(radial, tangential), axial: Math.abs(axial) };
}

/**
 * WHY THE DOWNSTREAM FLOW IS A TUBE, AND WHY THAT IS NOT A DEFECT.
 *
 * The first attempt at drawing the tail faded out "the flow the obstacle never
 * touched", on the assumption that the far half of the shell was undisturbed
 * free stream. That assumption was wrong, and measuring the obstacle is what
 * showed it. At the live drivers (standoff 9.46 Re, Shue alpha 0.614, plus the
 * 1.25 Re display gap) the boundary's TRANSVERSE radius runs:
 *
 *     theta      90     105     120     135     150 degrees
 *     x_Re     0.00   -4.83  -11.70  -22.63  -44.12
 *     w_Re    15.72   18.01   20.26   22.63   25.47
 *
 * The seeded stream is 13 Re across. Every single tracer therefore impacts
 * INSIDE the tail's own transverse radius, so every single one is swept onto
 * the boundary and ends up in the sheath: downstream there is no undisturbed
 * free stream in this domain to drop. The drawn tube of glyphs at w = 16-25 Re
 * is the magnetosheath wrapped around the magnetotail, and it is correct.
 *
 * What made it read as "a shell around the Earth" was never the tube. It was
 * that the tube had nothing inside it. The same measurement that found the
 * shell also found the cure and did not recognise it: with the magnetosphere
 * layer on, the identical cloud read correctly, measured identical - same
 * domain, same 2,200 tracers, same streak directions. A sheath is only legible
 * as a sheath when the thing it sheathes is on screen.
 *
 * So the layer now draws its own obstacle. See
 * `createSolarWindObstacleSilhouette`.
 */

/**
 * The faint outline of the obstacle the tracers are solved against.
 *
 * Nothing here is a second boundary model. `ObstacleShape` is the SAME table
 * `teachingFlowPointAroundObstacle` refuses to let a tracer through, so the
 * surface drawn is by construction the surface the flow is flowing around: if
 * they ever disagreed the tracers would visibly cross it.
 *
 * It exists because of a measurement. A sheath is only legible as a sheath when
 * the thing it sheathes is on screen - with the magnetosphere layer on, the
 * identical tracer cloud read correctly; with it off, the same cloud read as a
 * shell of particles streaming off the planet in every direction. The layer
 * that owns the flow should not depend on a different layer being switched on
 * for its own picture to make sense, so it now draws the obstacle itself, and
 * `setBoundaryDrawnElsewhere` takes it away again when the magnetosphere layer
 * is drawing the real thing at full strength.
 *
 * Drawn deliberately faint, with `depthWrite` off, so it can never occlude a
 * tracer, a satellite or a field line: it is a cue, not a surface to read
 * values off. Its evidence class is the magnetopause model's, not the wind's,
 * and the layer card says so.
 *
 * `maximumXRe` trims the tail so the silhouette stops where the drawn flow
 * stops rather than running on past it - the Shue surface reaches x = -44 Re by
 * theta = 150 degrees, which is well beyond the domain.
 */
/** Free every geometry and material under a group, then empty it. */
function disposeObject3D(root: THREE.Object3D) {
  root.traverse((node) => {
    const mesh = node as THREE.Mesh | THREE.LineSegments;
    mesh.geometry?.dispose?.();
    const material = mesh.material as THREE.Material | THREE.Material[] | undefined;
    if (Array.isArray(material)) material.forEach((entry) => entry.dispose());
    else material?.dispose?.();
  });
  root.clear();
}

export function createSolarWindObstacleSilhouette(
  obstacle: ObstacleShape,
  positionForGsm: GsmPositionMapper,
  options: { downstreamEndRe?: number; thetaSegments?: number; azimuthSegments?: number } = {},
): THREE.Group {
  const group = new THREE.Group();
  group.name = "solar-wind-obstacle-silhouette";
  const thetaSegments = Math.max(8, Math.floor(options.thetaSegments ?? 48));
  const azimuthSegments = Math.max(8, Math.floor(options.azimuthSegments ?? 64));
  const downstreamEndRe = options.downstreamEndRe ?? DEFAULT_DOWNSTREAM_END_RE;
  const point = (theta: number, azimuth: number) => {
    const radius = obstacle.radiusAt(theta, azimuth);
    const sin = Math.sin(theta);
    return {
      radius,
      xRe: radius * Math.cos(theta),
      yRe: radius * sin * Math.sin(azimuth),
      zRe: radius * sin * Math.cos(azimuth),
    };
  };
  // Where to stop, found by walking the shape rather than by assuming it: the
  // last polar angle whose surface point is still inside the drawn domain.
  //
  // Bracket first, then bisect. A coarse scan alone is not enough here: x runs
  // away as the tail flares (-22.6 Re at 135 degrees, -44.1 at 150), so the
  // sample that first crosses the domain end is already well past it, and
  // stopping there would draw a boundary the flow does not reach. A test pins
  // that the drawn surface never overshoots the drawn flow.
  const modelCutoffTheta = (150 * Math.PI) / 180;
  let maximumTheta = modelCutoffTheta;
  if (point(modelCutoffTheta, 0).xRe < downstreamEndRe) {
    let inside = 0;
    let outside = modelCutoffTheta;
    for (let index = 1; index <= 240; index += 1) {
      const theta = (index / 240) * modelCutoffTheta;
      if (point(theta, 0).xRe < downstreamEndRe) { outside = theta; break; }
      inside = theta;
    }
    for (let iteration = 0; iteration < 40; iteration += 1) {
      const middle = (inside + outside) / 2;
      if (point(middle, 0).xRe < downstreamEndRe) outside = middle;
      else inside = middle;
    }
    maximumTheta = inside;
  }
  const positions = new Float32Array((thetaSegments + 1) * (azimuthSegments + 1) * 3);
  let cursor = 0;
  for (let t = 0; t <= thetaSegments; t += 1) {
    const theta = (t / thetaSegments) * maximumTheta;
    for (let a = 0; a <= azimuthSegments; a += 1) {
      const azimuth = (a / azimuthSegments) * Math.PI * 2;
      const p = point(theta, azimuth);
      positionForGsm(p.xRe, p.yRe, p.zRe).toArray(positions, cursor);
      cursor += 3;
    }
  }
  const indices: number[] = [];
  const at = (t: number, a: number) => t * (azimuthSegments + 1) + a;
  for (let t = 0; t < thetaSegments; t += 1) {
    for (let a = 0; a < azimuthSegments; a += 1) {
      indices.push(at(t, a), at(t + 1, a), at(t + 1, a + 1));
      indices.push(at(t, a), at(t + 1, a + 1), at(t, a + 1));
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  geometry.userData.kind = "solar-wind-flow-obstacle";
  geometry.userData.source = "the same ObstacleShape the streamline solve uses";
  const material = new THREE.MeshBasicMaterial({
    color: 0x6fd8ff,
    transparent: true,
    opacity: 0.035,
    side: THREE.DoubleSide,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.name = "solar-wind-obstacle-surface";
  mesh.frustumCulled = false;
  group.add(mesh);

  // Meridian ribs. The translucent surface alone reads as a haze at this
  // opacity; the ribs are what make it read as a closed body with a tail.
  const ribPositions: number[] = [];
  for (let rib = 0; rib < 12; rib += 1) {
    const azimuth = (rib / 12) * Math.PI * 2;
    let previous: THREE.Vector3 | null = null;
    for (let t = 0; t <= thetaSegments; t += 1) {
      const p = point((t / thetaSegments) * maximumTheta, azimuth);
      const current = positionForGsm(p.xRe, p.yRe, p.zRe).clone();
      if (previous) ribPositions.push(previous.x, previous.y, previous.z, current.x, current.y, current.z);
      previous = current;
    }
  }
  const ribGeometry = new THREE.BufferGeometry();
  ribGeometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(ribPositions), 3));
  const ribs = new THREE.LineSegments(ribGeometry, new THREE.LineBasicMaterial({
    color: 0x7fe3ff,
    transparent: true,
    opacity: 0.16,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  }));
  ribs.name = "solar-wind-obstacle-ribs";
  ribs.frustumCulled = false;
  group.add(ribs);
  group.userData.maximumThetaRad = maximumTheta;
  return group;
}

/** Local flow speed as a fraction of the free stream. See above. */
export function teachingFlowSpeedFactor(
  xRe: number,
  yRe: number,
  zRe: number,
  obstacle: number | ObstacleShape,
): number {
  return teachingFlowVelocityFactors(xRe, yRe, zRe, obstacle).speed;
}

/**
 * How long a tracer takes to reach each x along one streamline, as a fraction
 * of the whole transit — the table that turns the uniform march into a flow.
 *
 * Built once per streamline family rather than per frame, and inverted by
 * lookup, so `updateFallback` stays a pure function of the clock it is passed.
 * That purity is not incidental: a consumer that accumulated its clock instead
 * shipped and made the cusp coupling invisible for weeks.
 *
 * Time is accumulated as dx / v_x, the axial component, because x is what the
 * march is parameterised by. Near the nose v_x tends to zero and the transit
 * time there tends to infinity — which is physically right and useless to
 * draw, so the axial speed is floored. A tracer aimed straight at the nose
 * therefore crawls rather than stopping forever.
 */
export function buildStreamlineTransit(
  impactYRe: number,
  impactZRe: number,
  domain: IllustrativeUpstreamDomain,
  samples = 96,
): { xRe: Float32Array; fraction: Float32Array } {
  const count = Math.max(8, Math.floor(samples));
  const xs = new Float32Array(count);
  const cumulative = new Float32Array(count);
  const span = domain.upstreamStartRe - domain.downstreamEndRe;
  let elapsed = 0;
  for (let index = 0; index < count; index += 1) {
    const xRe = domain.upstreamStartRe - (span * index) / (count - 1);
    xs[index] = xRe;
    if (index > 0) {
      // Midpoint of the step, so a step that straddles the stagnation region
      // is costed at its middle rather than at whichever end is cheaper.
      const midX = (xRe + xs[index - 1]!) / 2;
      const point = teachingFlowPointAroundObstacle(midX, impactYRe, impactZRe, domain.obstacle);
      const { axial } = teachingFlowVelocityFactors(point.xRe, point.yRe, point.zRe, domain.obstacle);
      // Floored so the stagnation region is slow rather than a division by
      // zero — a tracer aimed dead at the nose would otherwise take forever,
      // which is physically right and useless to draw.
      elapsed += (span / (count - 1)) / clamp(axial, 0.08, 4);
    }
    cumulative[index] = elapsed;
  }
  const fraction = new Float32Array(count);
  for (let index = 0; index < count; index += 1) {
    fraction[index] = elapsed > 0 ? cumulative[index]! / elapsed : index / (count - 1);
  }
  return { xRe: xs, fraction };
}

/**
 * Where along its streamline a tracer is at a given fraction of its transit.
 * The inverse of the table above, by binary search and linear interpolation.
 */
export function streamlineXAtFraction(
  table: { xRe: Float32Array; fraction: Float32Array },
  progress: number,
): number {
  const target = clamp(progress, 0, 1);
  const { fraction, xRe } = table;
  const last = fraction.length - 1;
  if (target <= 0) return xRe[0]!;
  if (target >= 1) return xRe[last]!;
  let low = 0;
  let high = last;
  while (high - low > 1) {
    const middle = (low + high) >> 1;
    if (fraction[middle]! <= target) low = middle;
    else high = middle;
  }
  const spanFraction = fraction[high]! - fraction[low]!;
  const blend = spanFraction > 0 ? (target - fraction[low]!) / spanFraction : 0;
  return xRe[low]! + (xRe[high]! - xRe[low]!) * blend;
}

/**
 * One transit table per impact-radius band, shared by every tracer in that
 * band. Transit time depends only on how far off-axis a streamline is, so a
 * band is an exact grouping for a spherical obstacle and a close one for a
 * shaped obstacle — and 24 tables is a rebuild cost, where one table per
 * tracer would be a per-frame cost.
 */
export function buildTransitTables(
  domain: IllustrativeUpstreamDomain,
  transverseExtentRe: number,
  bands = 24,
): Array<{ xRe: Float32Array; fraction: Float32Array }> {
  const count = Math.max(1, Math.floor(bands));
  return Array.from({ length: count }, (_, index) => {
    // Band centre, so the first band is not the degenerate zero-impact case.
    const impact = (transverseExtentRe * (index + 0.5)) / count;
    return buildStreamlineTransit(impact, 0, domain);
  });
}

/** Which transit band an impact parameter belongs to. */
export function transitBandIndex(impactRadiusRe: number, transverseExtentRe: number, bands: number): number {
  if (!(transverseExtentRe > 0)) return 0;
  const position = Math.floor((impactRadiusRe / transverseExtentRe) * bands);
  return Math.min(bands - 1, Math.max(0, position));
}

/**
 * ## THE UPSTREAM FACE IS A PLANE-PARALLEL FRONT THE SIZE OF THE VIEW
 *
 * Sean, 2026-08-27, having looked at the version this replaces: *"I think what
 * you needed to do is instead of having a point source where all the particles
 * come from, they originate from the entire lefthand side of the page. That
 * makes sense since the earth is far from the sun. If you zoom out more
 * particles come in from the top and bottom. But the farther they are from the
 * earth the more likely they are to pass by."*
 *
 * That is the physics, and it is better than what was here. At 1 AU the wind
 * arrives as an effectively plane-parallel front; the magnetosphere is a
 * 15–25 Rₑ obstacle standing in a flow enormous compared with it. What decides
 * a parcel's fate is its IMPACT PARAMETER — its perpendicular distance from
 * the Sun–Earth line — and nothing else:
 *
 *   - large: never meets the obstacle, sails past barely bent. Most of it.
 *   - intermediate: turned around the magnetopause and carried down the flanks.
 *   - small: shocked at the nose, and a minority couples in at the cusps.
 *
 * The flow solve already produces all three from the impact parameter alone
 * (`teachingFlowPointAroundObstacle`), so the whole of this change is WHERE
 * the tracers enter. Two numbers said the old answer was wrong:
 *
 *   - the face was 22 Rₑ across and drew only 374 scene units from the axis at
 *     a frame whose corner is 652 — a disc of wind in the middle of an empty
 *     page, which is exactly the "point source" Sean is describing;
 *   - zoomed out to a 1,376-unit frame corner, of 1,353 tracers whose entry
 *     landed on screen, ZERO entered through the top or bottom of the frame.
 *     Sean's own test, failed 1,353 to 0.
 *
 * ## SO THE FACE IS SIZED TO THE FRAME, NOT TO A FIXED RADIUS
 *
 * `SolarWindVisual.setViewFaceRadius` is handed the drawn radius of the frame's
 * corner every frame, and the face is re-cut to reach it. Each tracer keeps a
 * FACE FRACTION — a number in [0,1) it never loses — and its impact parameter
 * is that fraction's place on the current face, so zooming moves the wind
 * without rebuilding it and without changing which tracer is which species.
 *
 * ## AND IT IS SAMPLED EVENLY OVER THE PAGE, WHICH IS THE DISPLAY CHOICE
 *
 * Equal drawn area gets equal numbers: the drawn transverse radius is
 * `edge * sqrt(fraction)`, inverted back to a physical impact parameter through
 * the ruler by `impactForDrawnTransverse`. The alternative — even in PHYSICAL
 * space, which is what the real wind is — was measured and is unusable here:
 * the shared ruler's log–log slope past 24 Rₑ is 0.14, so a physically uniform
 * face stacks half its tracers into a thin halo at the edge of the frame and
 * leaves the middle empty. Drawing evenly on the page instead means the drawn
 * number density per unit PHYSICAL area falls with distance from the axis.
 *
 * That is a display choice, it is the one this file used to make with an
 * exponent instead, and it is stated on the geometry (`userData.upstreamSampling`)
 * and in words on the layer card. Nothing here touches the species mix: species
 * are assigned by tracer INDEX from the measured mix and never by position.
 */
const DEFAULT_TRANSVERSE_EXTENT_RE = 55;

/**
 * How far out the face is allowed to be cut, in Rₑ.
 *
 * The ruler compresses so hard in the far field that filling a very wide frame
 * costs enormous physical distance for very little drawn radius, and past a few
 * hundred Rₑ the flow solve is doing arithmetic on a straight line. 400 Rₑ is
 * where that stops being worth it. If a frame is wider than 400 Rₑ can reach,
 * the face stops there and the outer corners of the picture are empty — the one
 * place Sean's design is not delivered in full, and it is reported on the
 * geometry as `viewCoveredFully: false` rather than hidden.
 */
const MAXIMUM_TRANSVERSE_EXTENT_RE = 400;

/** A little past the corner, so the frame's edge is never the edge of the wind. */
const VIEW_FACE_MARGIN = 1.12;

/**
 * The face is re-cut only when the frame's drawn corner radius changes by more
 * than this ratio, so a dolly does not re-cut it sixty times a second. 1.06 is
 * about a 6% step in drawn radius, which is below what a reader can see appear.
 */
const VIEW_FACE_QUANTISATION = 1.06;

/** How many rungs the impact-parameter ↔ drawn-transverse ladder carries. */
const FACE_MAP_SAMPLES = 192;

/**
 * ## THE TRANSIT-TIME BANDS NO LONGER MOVE WITH THE FACE
 *
 * Transit time along a streamline depends only on how far off-axis it is, and
 * the tables that carry it are built once per rebuild. With a face that changes
 * size every time the camera moves, banding the tables against the FACE would
 * mean rebuilding 48 tables on every zoom step. They are banded against a fixed
 * physical grid instead, and anything wider than the grid clamps to its
 * outermost band.
 *
 * What that costs is bounded and small: at 45 Rₑ the drawn obstacle subtends
 * `1 − (a/r)³` = 0.955 of the free-stream axial speed at its closest approach,
 * so a tracer at 200 Rₑ borrows a transit that is at most 4.5% slow through the
 * waist and exactly right everywhere else. 48 bands over 45 Rₑ is 0.94 Rₑ per
 * band, which is the resolution the 24-band-over-22-Rₑ arrangement had near the
 * nose, where the stagnation makes it matter.
 */
const TRANSIT_BAND_MAX_RE = 45;
const TRANSIT_BAND_COUNT = 48;

/**
 * ## WHY THE BYPASSING WIND IS DRAWN ON SHARED STREAMLINES
 *
 * With every tracer on its own impact point the free shower is a cloud of
 * independent glyphs, and in projection a cloud of independent glyphs is
 * speckle. Counted at the same camera and instant, the free shower already
 * covered 20,399 pixels to the field-guided stream's 13,839 — half again as
 * much ink — and still did not read as a flow, because the guided stream's
 * tracers share paths and the free shower's did not. Coherence, not count, is
 * what makes a stream legible.
 *
 * The tubes are laid out on a golden-angle spiral across the upstream face, so
 * they spread evenly in three dimensions rather than banding into rings, and
 * their face fractions are stratified so they cover it evenly. Phases stay
 * independent, which is what keeps a tube a stream rather than a conveyor belt
 * of evenly spaced beads.
 *
 * The count went 132 → 300 when the face became the size of the frame: the same
 * number of tubes spread over a face five times wider in drawn radius reads as
 * a set of separate rays rather than as a flow.
 */
const DEFAULT_FLOW_TUBE_COUNT = 300;

/** The golden angle, for spreading tube impact points without rings. */
const FLOW_TUBE_GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));

/**
 * The ladder between an impact parameter and where the ruler draws it.
 *
 * `impactRe` ascending, `drawnTransverse` the distance from the Sun–Earth line
 * at which the shared ruler draws that streamline's entry point, in scene
 * units. Built from the SAME `positionForGsm` every other layer is drawn
 * through, so it cannot disagree with the picture, and rebuilt only when the
 * flow is rebuilt.
 */
export interface UpstreamFaceMap {
  impactRe: Float32Array;
  drawnTransverse: Float32Array;
}

export function buildUpstreamFaceMap(
  domain: IllustrativeUpstreamDomain,
  positionForGsm: GsmPositionMapper,
  maximumRe = MAXIMUM_TRANSVERSE_EXTENT_RE,
  samples = FACE_MAP_SAMPLES,
): UpstreamFaceMap {
  const count = Math.max(8, Math.floor(samples));
  const impactRe = new Float32Array(count);
  const drawnTransverse = new Float32Array(count);
  for (let index = 0; index < count; index += 1) {
    // Quadratic in the index, so the rungs are close together near the axis
    // where the ruler's slope is changing fastest and far apart out in the
    // far field where it is almost flat.
    const impact = maximumRe * (index / (count - 1)) ** 2;
    impactRe[index] = impact;
    const point = positionForGsm(domain.upstreamStartRe, impact, 0);
    drawnTransverse[index] = Math.hypot(point.y, point.z);
  }
  // Strictly ascending, so the inverse below is single-valued even if a ruler
  // is ever handed to this that is flat over some interval.
  for (let index = 1; index < count; index += 1) {
    if (!(drawnTransverse[index]! > drawnTransverse[index - 1]!)) {
      drawnTransverse[index] = drawnTransverse[index - 1]! + 1e-4;
    }
  }
  return { impactRe, drawnTransverse };
}

/** Where the ruler draws the entry point of the streamline with this impact parameter. */
export function drawnTransverseForImpact(map: UpstreamFaceMap, impactRe: number): number {
  const { impactRe: xs, drawnTransverse: ys } = map;
  const last = xs.length - 1;
  if (!(impactRe > xs[0]!)) return ys[0]!;
  if (impactRe >= xs[last]!) return ys[last]!;
  let low = 0;
  let high = last;
  while (high - low > 1) {
    const middle = (low + high) >> 1;
    if (xs[middle]! <= impactRe) low = middle;
    else high = middle;
  }
  const span = xs[high]! - xs[low]!;
  const blend = span > 0 ? (impactRe - xs[low]!) / span : 0;
  return ys[low]! + (ys[high]! - ys[low]!) * blend;
}

/** The inverse: the impact parameter whose entry point the ruler draws this far off-axis. */
export function impactForDrawnTransverse(map: UpstreamFaceMap, drawn: number): number {
  const { impactRe: xs, drawnTransverse: ys } = map;
  const last = ys.length - 1;
  if (!(drawn > ys[0]!)) return xs[0]!;
  if (drawn >= ys[last]!) return xs[last]!;
  let low = 0;
  let high = last;
  while (high - low > 1) {
    const middle = (low + high) >> 1;
    if (ys[middle]! <= drawn) low = middle;
    else high = middle;
  }
  const span = ys[high]! - ys[low]!;
  const blend = span > 0 ? (drawn - ys[low]!) / span : 0;
  return xs[low]! + (xs[high]! - xs[low]!) * blend;
}

/**
 * Where one tracer enters the upstream face: its FACE FRACTION's place on a
 * face whose drawn edge is `drawnEdge` scene units from the Sun–Earth line.
 *
 * `sqrt` is what makes it even over the PAGE — equal drawn area, equal numbers
 * — and the inverse map is what turns that back into a physical distance.
 */
export function impactForFaceFraction(
  map: UpstreamFaceMap,
  faceFraction: number,
  drawnEdge: number,
): number {
  const fraction = Math.min(1, Math.max(0, faceFraction));
  return impactForDrawnTransverse(map, drawnEdge * Math.sqrt(fraction));
}

function seededRandom(seed: number) {
  let state = seed >>> 0;
  return () => {
    state = (Math.imul(state, 1_664_525) + 1_013_904_223) >>> 0;
    return state / 4_294_967_296;
  };
}

/**
 * Creates deterministic teaching tracers around a no-penetration obstacle.
 * Physical GSM coordinates remain inspectable after scene-space mapping.
 */
export function createIllustrativeUpstreamFlowGeometry(
  options: IllustrativeUpstreamFlowOptions = {},
) {
  const domain = illustrativeUpstreamDomain(options);
  const legacyCount = Math.max(1, Math.floor(options.streamCount ?? 35))
    * Math.max(2, Math.floor(options.samplesPerStream ?? 40));
  const pointCount = Math.max(32, Math.floor(options.particleCount ?? legacyCount));
  const transverseExtentRe = Math.max(
    0.1,
    Math.min(MAXIMUM_TRANSVERSE_EXTENT_RE, options.transverseExtentRe ?? DEFAULT_TRANSVERSE_EXTENT_RE),
  );
  const flowTubeCount = Math.max(0, Math.floor(options.flowTubeCount ?? DEFAULT_FLOW_TUBE_COUNT));
  const positionForGsm = options.positionForGsm ?? defaultGsmPosition;
  const faceMap = buildUpstreamFaceMap(domain, positionForGsm);
  const positions = new Float32Array(pointCount * 3);
  const alpha = new Float32Array(pointCount);
  const phase = new Float32Array(pointCount);
  const yRe = new Float32Array(pointCount);
  const zRe = new Float32Array(pointCount);
  const impactYRe = new Float32Array(pointCount);
  const impactZRe = new Float32Array(pointCount);
  // The two numbers a tracer keeps for life. Everything about WHERE it enters
  // is derived from these and the current frame, so re-cutting the face to a
  // new zoom moves tracers without rebuilding anything.
  const faceFraction = new Float32Array(pointCount);
  const faceAzimuth = new Float32Array(pointCount);
  const gsmXRe = new Float32Array(pointCount);
  const species = new Float32Array(pointCount);
  const speciesCounts: Record<SolarWindSpecies, number> = { proton: 0, alpha: 0, electron: 0 };
  const mix = solarWindSpeciesMix();
  const random = seededRandom(options.seed ?? 0x5f3759df);
  for (let pointIndex = 0; pointIndex < pointCount; pointIndex += 1) {
    const assigned = solarWindSpeciesForIndex(pointIndex, mix);
    species[pointIndex] = SPECIES_ATTRIBUTE_VALUE[assigned];
    speciesCounts[assigned] += 1;
    const progress = random();
    // WHERE THIS TRACER ENTERS THE UPSTREAM FACE.
    //
    // With flow tubes on, the tracer joins one of a fixed set of streamlines:
    // its face fraction is that tube's stratified place across the face and
    // its azimuth is the tube's place on the golden-angle spiral. Its PHASE is
    // still its own, so tracers sharing a tube are strung along it at
    // independent points rather than marching in step. With tubes off every
    // tracer gets its own entry point, which is the older, speckled picture.
    const tube = flowTubeCount > 0 ? Math.floor(random() * flowTubeCount) : -1;
    const fraction = tube >= 0 ? (tube + 0.5) / flowTubeCount : random();
    const azimuth = tube >= 0 ? tube * FLOW_TUBE_GOLDEN_ANGLE : random() * Math.PI * 2;
    faceFraction[pointIndex] = fraction;
    faceAzimuth[pointIndex] = azimuth;
    const radius = impactForFaceFraction(
      faceMap,
      fraction,
      drawnTransverseForImpact(faceMap, transverseExtentRe),
    );
    const streamY = radius * Math.cos(azimuth);
    const streamZ = radius * Math.sin(azimuth);
    const xRe = THREE.MathUtils.lerp(domain.upstreamStartRe, domain.downstreamEndRe, progress);
    const flowPoint = teachingFlowPointAroundObstacle(
      xRe,
      streamY,
      streamZ,
      domain.obstacle,
    );
    positionForGsm(flowPoint.xRe, flowPoint.yRe, flowPoint.zRe).toArray(positions, pointIndex * 3);
    gsmXRe[pointIndex] = flowPoint.xRe;
    yRe[pointIndex] = flowPoint.yRe;
    zRe[pointIndex] = flowPoint.zRe;
    impactYRe[pointIndex] = streamY;
    impactZRe[pointIndex] = streamZ;
    phase[pointIndex] = progress;
    alpha[pointIndex] = smoothstep(0, 0.08, progress) * (1 - smoothstep(0.88, 1, progress));
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("flowAlpha", new THREE.BufferAttribute(alpha, 1));
  geometry.setAttribute("flowPhase", new THREE.BufferAttribute(phase, 1));
  geometry.setAttribute("gsmXRe", new THREE.BufferAttribute(gsmXRe, 1));
  geometry.setAttribute("gsmYRe", new THREE.BufferAttribute(yRe, 1));
  geometry.setAttribute("gsmZRe", new THREE.BufferAttribute(zRe, 1));
  geometry.setAttribute("impactYRe", new THREE.BufferAttribute(impactYRe, 1));
  geometry.setAttribute("impactZRe", new THREE.BufferAttribute(impactZRe, 1));
  geometry.setAttribute("faceFraction", new THREE.BufferAttribute(faceFraction, 1));
  geometry.setAttribute("faceAzimuth", new THREE.BufferAttribute(faceAzimuth, 1));
  geometry.setAttribute("species", new THREE.BufferAttribute(species, 1));
  geometry.userData.domain = domain;
  // The transit tables that make the march a flow rather than a conveyor:
  // built here, once, because they depend only on the obstacle and the
  // streamline, and read by lookup every frame.
  geometry.userData.transitTables = buildTransitTables(domain, TRANSIT_BAND_MAX_RE, TRANSIT_BAND_COUNT);
  geometry.userData.transitBandMaxRe = TRANSIT_BAND_MAX_RE;
  geometry.userData.faceMap = faceMap;
  geometry.userData.transverseExtentRe = transverseExtentRe;
  geometry.userData.speciesCounts = speciesCounts;
  geometry.userData.speciesMix = mix;
  geometry.userData.speciesAssignment =
    "illustrative sampling of the measured bulk totals; He²⁺/H⁺ = 0.04 assumed (not in the L1 feed), electrons by quasi-neutrality";
  geometry.userData.kind = "physics-based-teaching-solar-wind-tracers";
  geometry.userData.physicsModel = domain.obstacle.shaped
    ? "incompressible-no-penetration-streamlines-around-the-drawn-empirical-magnetopause"
    : "axisymmetric-incompressible-potential-flow-around-sphere";
  geometry.userData.obstacle = domain.obstacle.shaped
    ? "the drawn empirical magnetopause, offset outward by a fixed display gap"
    : "a sphere at the subsolar standoff plus a fixed display gap";
  geometry.userData.classification = "teaching tracers—not observed individual trajectories";
  geometry.userData.distribution = "independent-streamline-phase-samples";
  geometry.userData.upstreamSampling = describeUpstreamFace(
    transverseExtentRe,
    drawnTransverseForImpact(faceMap, transverseExtentRe),
    flowTubeCount,
    null,
  );
  return geometry;
}

/**
 * What the drawn upstream face currently is, in words and in numbers, for the
 * geometry to carry and for a test to read.
 */
export function describeUpstreamFace(
  transverseExtentRe: number,
  drawnEdgeScene: number,
  flowTubeCount: number,
  requestedDrawnEdgeScene: number | null,
) {
  const covered = requestedDrawnEdgeScene === null
    || drawnEdgeScene >= requestedDrawnEdgeScene - 0.5;
  return {
    transverseExtentRe: Number(transverseExtentRe.toFixed(2)),
    drawnEdgeScene: Number(drawnEdgeScene.toFixed(1)),
    requestedDrawnEdgeScene: requestedDrawnEdgeScene === null
      ? null
      : Number(requestedDrawnEdgeScene.toFixed(1)),
    viewCoveredFully: covered,
    flowTubeCount,
    sampling: "even-over-the-drawn-page",
    statement:
      "The wind arrives across a PLANE-PARALLEL FRONT cut to the size of the frame — "
      + transverseExtentRe.toFixed(0)
      + " Rₑ from the Sun–Earth line here — and each tracer's fate is decided by its impact parameter alone: "
      + "wide ones pass barely bent, middling ones are turned around the boundary and carried down the flanks, "
      + "and only the ones that arrive near the axis are shocked and can couple in. "
      + "DISPLAY CHOICE: the face is sampled evenly over the DRAWN PAGE, so equal drawn area carries equal numbers. "
      + "The real front is even in PHYSICAL space, and because the shared ruler compresses distance hard, "
      + "drawing it that way would stack half the tracers into a halo at the edge of the frame. "
      + "This moves drawn particles around; it changes neither how many are drawn nor which species they are."
      + (covered ? "" : " The frame is wider than "
        + MAXIMUM_TRANSVERSE_EXTENT_RE
        + " Rₑ reaches on this ruler, so its outer corners carry no wind."),
  };
}

/**
 * The species-shower point material. Colour and size come from the species
 * attribute — protons amber, electrons a paler gold drawn a little smaller,
 * and the trace alphas a periwinkle spark drawn about 1.45x the proton's width
 * because they are the heavy ones. The two species that make up 98% of the wind share
 * the gold family, so the shower reads as one thing; the rare one carries the
 * separation, for the reasons measured above `SOLAR_WIND_SPECIES_PRESENTATION`.
 * Species selection happens per vertex from the three uniforms so the legend
 * and the pixels can never disagree about what a colour means.
 */
function createSpeciesFlowMaterial(pixelRatio: number) {
  return new THREE.ShaderMaterial({
    uniforms: {
      protonColor: { value: new THREE.Color(SOLAR_WIND_SPECIES_PRESENTATION.proton.colorHex) },
      alphaColor: { value: new THREE.Color(SOLAR_WIND_SPECIES_PRESENTATION.alpha.colorHex) },
      electronColor: { value: new THREE.Color(SOLAR_WIND_SPECIES_PRESENTATION.electron.colorHex) },
      protonScale: { value: SOLAR_WIND_SPECIES_PRESENTATION.proton.pointScale },
      alphaScale: { value: SOLAR_WIND_SPECIES_PRESENTATION.alpha.pointScale },
      electronScale: { value: SOLAR_WIND_SPECIES_PRESENTATION.electron.pointScale },
      alphaLuminanceGain: { value: SOLAR_WIND_ALPHA_LUMINANCE_GAIN },
      opacity: { value: 0 },
      pointSize: { value: 1.4 },
      pixelRatio: { value: Math.max(0.25, pixelRatio) },
      cameraToEarth: { value: 0 },
      faceThinStart: { value: 0 },
      faceThinEnd: { value: 0 },
      faceEdgeStart: { value: 0 },
      faceEdgeEnd: { value: 0 },
    },
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    vertexShader: `
      attribute float flowAlpha;
      attribute float species;
      uniform float pointSize;
      uniform float pixelRatio;
      uniform vec3 protonColor;
      uniform vec3 alphaColor;
      uniform vec3 electronColor;
      uniform float protonScale;
      uniform float alphaScale;
      uniform float electronScale;
      varying float glyphAlpha;
      varying float isAlpha;
      varying vec3 speciesColor;
${SOLAR_WIND_DEPTH_CUE_GLSL}
      void main() {
        isAlpha = species > 0.5 && species < 1.5 ? 1.0 : 0.0;
        float scale = species < 0.5 ? protonScale : (species < 1.5 ? alphaScale : electronScale);
        speciesColor = species < 0.5 ? protonColor : (species < 1.5 ? alphaColor : electronColor);
        vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
        // See SOLAR_WIND_DEPTH_CUE: tracers passing close in front of the
        // camera step back, distant ones draw smaller. Display choice; the
        // counts, the species and the paths are untouched.
        float viewDist = -mvPosition.z;
        glyphAlpha = flowAlpha * solarWindNearFade(viewDist) * solarWindFaceFade(position);
        gl_PointSize = pointSize * scale * solarWindDepthSize(viewDist) * pixelRatio;
        gl_Position = projectionMatrix * mvPosition;
      }
    `,
    fragmentShader: `
      uniform float opacity;
      uniform float alphaLuminanceGain;
      varying float glyphAlpha;
      varying float isAlpha;
      varying vec3 speciesColor;
      void main() {
        float radius = length(gl_PointCoord - vec2(0.5));
        if (radius > 0.5) discard;
        float softEdge = 1.0 - smoothstep(0.3, 0.5, radius);
        // #8b87e8 is 1.63x darker than the amber H+, so at an equal alpha it
        // emits 1.63x less light on this additive sky. Divided out here,
        // clamped, and never applied to the other two. The clamp used to bind
        // at every quiet wind and pin the alphas at full brightness; at this
        // colour the whole correction fits under it. See
        // SOLAR_WIND_ALPHA_LUMINANCE_GAIN. Counts and positions are untouched.
        float lit = min(1.0, opacity * mix(1.0, alphaLuminanceGain, isAlpha));
        gl_FragColor = vec4(speciesColor, lit * glyphAlpha * softEdge);
      }
    `,
  });
}

/** The streak material for the species shower: same per-species colour. */
function createSpeciesTrailMaterial() {
  return new THREE.ShaderMaterial({
    uniforms: {
      protonColor: { value: new THREE.Color(SOLAR_WIND_SPECIES_PRESENTATION.proton.colorHex) },
      alphaColor: { value: new THREE.Color(SOLAR_WIND_SPECIES_PRESENTATION.alpha.colorHex) },
      electronColor: { value: new THREE.Color(SOLAR_WIND_SPECIES_PRESENTATION.electron.colorHex) },
      alphaLuminanceGain: { value: SOLAR_WIND_ALPHA_LUMINANCE_GAIN },
      opacity: { value: 0 },
      protonTrailFade: { value: SOLAR_WIND_SPECIES_TRAIL_FADE_EXPONENT.proton },
      alphaTrailFade: { value: SOLAR_WIND_SPECIES_TRAIL_FADE_EXPONENT.alpha },
      electronTrailFade: { value: SOLAR_WIND_SPECIES_TRAIL_FADE_EXPONENT.electron },
      cameraToEarth: { value: 0 },
      faceThinStart: { value: 0 },
      faceThinEnd: { value: 0 },
      faceEdgeStart: { value: 0 },
      faceEdgeEnd: { value: 0 },
    },
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    vertexShader: `
      attribute float flowAlpha;
      attribute float trailFade;
      attribute float species;
      uniform vec3 protonColor;
      uniform vec3 alphaColor;
      uniform vec3 electronColor;
      uniform float protonTrailFade;
      uniform float alphaTrailFade;
      uniform float electronTrailFade;
      varying float segmentAlpha;
      varying float isAlpha;
      varying vec3 speciesColor;
${SOLAR_WIND_DEPTH_CUE_GLSL}
      void main() {
        // The streak carries the same luminance correction as its head, or a
        // particle would arrive brighter than the trail it is dragging.
        isAlpha = species > 0.5 && species < 1.5 ? 1.0 : 0.0;
        speciesColor = species < 0.5 ? protonColor : (species < 1.5 ? alphaColor : electronColor);
        // SOLAR_WIND_SPECIES_TRAIL_FADE_EXPONENT: the fade RAMP bends per
        // species so mass reads as motion character. No vertex moves; every
        // streak is the same fixed display length it was.
        float fadeExponent = species < 0.5 ? protonTrailFade : (species < 1.5 ? alphaTrailFade : electronTrailFade);
        vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
        segmentAlpha = flowAlpha * pow(max(trailFade, 0.0), fadeExponent)
          * solarWindNearFade(-mvPosition.z) * solarWindFaceFade(position);
        gl_Position = projectionMatrix * mvPosition;
      }
    `,
    fragmentShader: `
      uniform float opacity;
      uniform float alphaLuminanceGain;
      varying float segmentAlpha;
      varying float isAlpha;
      varying vec3 speciesColor;
      void main() {
        float lit = min(1.0, opacity * mix(1.0, alphaLuminanceGain, isAlpha));
        gl_FragColor = vec4(speciesColor, lit * segmentAlpha);
      }
    `,
  });
}

/**
 * The plane-tracer material: each point coloured by the model's own local
 * bulk speed on the shared 0–1000 km/s ramp, so the slowing at the shock is
 * literally a colour change along the flow — the tracers turn from green
 * toward deep blue as the model slows them.
 */
function createModelFlowMaterial(pixelRatio: number) {
  return new THREE.ShaderMaterial({
    uniforms: {
      lowColor: { value: SOLAR_WIND_SPEED_STOPS[0]!.clone() },
      middleColor: { value: SOLAR_WIND_SPEED_STOPS[1]!.clone() },
      highColor: { value: SOLAR_WIND_SPEED_STOPS[2]!.clone() },
      speedMaximum: { value: SOLAR_WIND_SPEED_RANGE_KPS[1] },
      opacity: { value: 0 },
      pointSize: { value: 1.6 },
      pixelRatio: { value: Math.max(0.25, pixelRatio) },
      cameraToEarth: { value: 0 },
      faceThinStart: { value: 0 },
      faceThinEnd: { value: 0 },
      faceEdgeStart: { value: 0 },
      faceEdgeEnd: { value: 0 },
    },
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    vertexShader: `
      attribute float flowAlpha;
      attribute float modelSpeedKps;
      uniform float pointSize;
      uniform float pixelRatio;
      uniform float speedMaximum;
      varying float glyphAlpha;
      varying float speedFraction;
${SOLAR_WIND_DEPTH_CUE_GLSL}
      void main() {
        speedFraction = clamp(modelSpeedKps / speedMaximum, 0.0, 1.0);
        vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
        float viewDist = -mvPosition.z;
        glyphAlpha = flowAlpha * solarWindNearFade(viewDist);
        gl_PointSize = pointSize * solarWindDepthSize(viewDist) * pixelRatio;
        gl_Position = projectionMatrix * mvPosition;
      }
    `,
    fragmentShader: `
      uniform vec3 lowColor;
      uniform vec3 middleColor;
      uniform vec3 highColor;
      uniform float opacity;
      varying float glyphAlpha;
      varying float speedFraction;
      void main() {
        float radius = length(gl_PointCoord - vec2(0.5));
        if (radius > 0.5) discard;
        float softEdge = 1.0 - smoothstep(0.3, 0.5, radius);
        vec3 color = speedFraction < 0.5
          ? mix(lowColor, middleColor, speedFraction * 2.0)
          : mix(middleColor, highColor, (speedFraction - 0.5) * 2.0);
        gl_FragColor = vec4(color, opacity * glyphAlpha * softEdge);
      }
    `,
  });
}

/**
 * The streak drawn behind each tracer.
 *
 * A single still frame of moving dots is indistinguishable from random
 * speckle, which is exactly how the layer read: the flow was being deflected
 * and nothing about the picture said so. The streak is the tracer's own
 * streamline tangent, so it bends where the flow bends, and it is visible
 * without waiting for motion.
 */
function createTrailMaterial() {
  return new THREE.ShaderMaterial({
    uniforms: {
      color: { value: new THREE.Color(0xf5c96a) },
      opacity: { value: 0 },
      cameraToEarth: { value: 0 },
      faceThinStart: { value: 0 },
      faceThinEnd: { value: 0 },
      faceEdgeStart: { value: 0 },
      faceEdgeEnd: { value: 0 },
    },
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    vertexShader: `
      attribute float flowAlpha;
      attribute float trailFade;
      varying float segmentAlpha;
${SOLAR_WIND_DEPTH_CUE_GLSL}
      void main() {
        vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
        segmentAlpha = flowAlpha * trailFade * solarWindNearFade(-mvPosition.z);
        gl_Position = projectionMatrix * mvPosition;
      }
    `,
    fragmentShader: `
      uniform vec3 color;
      uniform float opacity;
      varying float segmentAlpha;
      void main() {
        gl_FragColor = vec4(color, opacity * segmentAlpha);
      }
    `,
  });
}

/**
 * ## Field-guided coupling — the wind meeting the drawn field
 *
 * When the magnetosphere layer's driven field lines are on screen beside the
 * wind, a visible fraction of the arriving particles is guided ALONG those
 * very lines rather than around the obstacle: the cusp-adjacent ones funnel
 * down the dayside boundary-truncated lines to their high-latitude footpoints
 * (the cusp entry that feeds the dayside aurora), and a smaller share rides
 * the open polar-cap lines tailward along the lobes (the plasma mantle's
 * path). The guidance polylines ARE the traced field-line model's own output
 * — nothing here invents a curve — so a guided particle is on a drawn field
 * line by construction, and the tests measure that distance directly.
 *
 * The motion along the lines is illustrative (no measured velocity exists on
 * any individual line) and the entry selection is geometric, not a solved
 * reconnection rate. The card says both.
 */
export interface FieldGuidanceLine {
  /** Polyline in physical GSM Re. For the traced model this is ordered from the seed footpoint outward. */
  pointsGsmRe: ReadonlyArray<{ x: number; y: number; z: number }>;
  topology: "closed" | "open" | "boundary";
  seedLatitudeDeg: number;
  seedLongitudeDeg: number;
}

export interface GuidancePath {
  /**
   * `cusp` funnels boundary-truncated dayside lines down to their footpoints;
   * `lobe` rides open lines tailward; `return` is a lobe ride that carries on
   * round the rest of the Dungey cycle once the plasma-sheet layer asks for it;
   * `inflow` is the last stretch of that same ride, drawn as a path of its own
   * so the ARRIVAL at the current sheet is populated rather than inferred (see
   * `buildLobeInflowPath`).
   */
  role: "cusp" | "lobe" | "return" | "inflow";
  /** Travel-ordered polyline, GSM Re: entry first, exit last. */
  pointsGsmRe: Array<{ x: number; y: number; z: number }>;
  /** Cumulative arc length per point, Re. */
  cumulativeRe: number[];
  totalLengthRe: number;
  /** Where the particle joins the field line. */
  entryGsmRe: { x: number; y: number; z: number };
  /** Footpoint latitude of a cusp path (the seed's magnetic latitude); null for lobe paths. */
  footpointLatitudeDeg: number | null;
  hemisphere: "north" | "south";
  /**
   * The vertex index at which MEASURED-driver-shaped geometry stops and the
   * schematic transport begins, or null when the whole path is traced.
   *
   * Everything before it is the traced field-line model's own output, drawn on
   * screen as a field line for the particle to ride. Everything from it on is
   * `dungey-transport.ts` — the settled sequence of the Dungey cycle, drawn as
   * a schematic because nobody measures these trajectories. The index exists
   * so the split is a property of the data rather than a claim in prose, and
   * so the renderer can ink the two differently without guessing.
   */
  schematicFromIndex: number | null;
  /**
   * Which species may ride this path, or null for all of them.
   *
   * The ring-current branch is charge-split by construction: gradient and
   * curvature drift take ions west toward dusk and electrons east toward dawn.
   * A path that carried both would draw the two populations on top of each
   * other and teach the opposite of the mechanism.
   */
  speciesFilter: readonly SolarWindSpecies[] | null;
  /**
   * Where along this path the particle stops being a charged particle, or
   * absent when it never does.
   *
   * Only a charge-exchange ending has one. The magnetopause containment check
   * stops here: a neutral atom is not confined by the boundary and flies
   * straight out through it, which is the whole reason an energetic-neutral
   * camera outside the magnetosphere can image the ring current inside it.
   * Checking the escape ray against the boundary would refuse a correct path
   * for being correct.
   */
  neutralFromIndex?: number | null;
  /** Which end of the chain a return path is drawn to. */
  branch: DungeyBranch | null;
  /** Which way an injected population drifts at the inner edge. */
  driftSense: DriftSense | null;
}

export interface GuidancePathOptions {
  maximumCuspPaths?: number;
  maximumLobePaths?: number;
  /** Open lines are guided only from this radius outward, so nothing appears to launch off the planet. */
  lobeStartRadiusRe?: number;
  /**
   * Carry the lobe ride on round the rest of the Dungey cycle. Absent or null
   * and the lobe paths end where the traced open lines do, which is exactly
   * the behaviour before the plasma-sheet layer is switched on.
   */
  tailReturn?: TailReturnOptions | null;
}

/**
 * What the return leg needs to know, all of it either measured or already
 * drawn by another layer.
 *
 * There is no flux, no energy and no transit time on this object, and there
 * must not be: none of those is measured for an individual particle and
 * printing one would be the invented number this site exists not to print.
 */
export interface TailReturnOptions {
  /** Dipole tilt for the instant being drawn, radians. */
  dipoleTiltRad: number;
  /** The inner edge of the hot plasma sheet, Re — the wedge the sheet layer draws. */
  innerEdgeRe: number;
  /** Draw the precipitating branch into the oval as well as the drift branch. */
  auroraBranch: boolean;
  /**
   * Shue parameters for the MEASURED drivers, so every schematic vertex can be
   * checked against the boundary before it is drawn. Absent and the return leg
   * is refused: an unchecked path through the tail is how the inner plasma
   * sheet came to be drawn in the magnetosheath.
   */
  magnetopause: { subsolarStandoffRe: number; flaringAlpha: number } | null;
  /** Where the near-Earth neutral line is placed, Re. Defaults to `TAIL_X_LINE_RE`. */
  xLineRe?: number;
}

function polylineWithLengths(points: Array<{ x: number; y: number; z: number }>) {
  const cumulativeRe: number[] = [0];
  for (let index = 1; index < points.length; index += 1) {
    const previous = points[index - 1]!;
    const point = points[index]!;
    cumulativeRe.push(
      cumulativeRe[index - 1]!
      + Math.hypot(point.x - previous.x, point.y - previous.y, point.z - previous.z),
    );
  }
  return { cumulativeRe, totalLengthRe: cumulativeRe.at(-1) ?? 0 };
}

/** Evenly thin a list down to a cap, keeping first and last. */
function thinTo<T>(items: T[], cap: number): T[] {
  if (items.length <= cap) return items;
  const kept: T[] = [];
  for (let index = 0; index < cap; index += 1) {
    kept.push(items[Math.round((index * (items.length - 1)) / (cap - 1))]!);
  }
  return kept;
}

/**
 * Select guidance paths from the traced field-line set.
 *
 * Cusp paths: dayside `boundary`-topology lines — traced from the seed
 * footpoint out to the boundary surface — reversed, so travel runs from the
 * boundary entry point down the line to the footpoint. Lobe paths: `open`
 * lines, trimmed to start where they cross `lobeStartRadiusRe` outbound, so
 * travel runs from high over the polar cap tailward along the lobe.
 */
export function buildGuidancePaths(
  lines: readonly FieldGuidanceLine[],
  options: GuidancePathOptions = {},
): GuidancePath[] {
  // Sean's review of the first shipped coupling: deflection read clearly but
  // "we don't see much reaching earth" — the funnelled stream is the teaching
  // object, so it gets enough paths to read as a stream, not stragglers.
  const maximumCusp = Math.max(0, Math.floor(options.maximumCuspPaths ?? 28));
  const maximumLobe = Math.max(0, Math.floor(options.maximumLobePaths ?? 12));
  const lobeStartRadiusRe = Math.max(1.5, options.lobeStartRadiusRe ?? 5);

  const cuspCandidates = lines.filter((line) => {
    if (line.topology !== "boundary" || line.pointsGsmRe.length < 4) return false;
    const end = line.pointsGsmRe.at(-1)!;
    // Dayside entry only: the boundary end must sit sunward of the terminator
    // plane, where the funnel throat is; nightside truncations are not a cusp.
    return end.x > 0;
  }).sort((a, b) => a.seedLongitudeDeg - b.seedLongitudeDeg);

  const paths: GuidancePath[] = [];
  for (const line of thinTo(cuspCandidates, maximumCusp)) {
    const points = [...line.pointsGsmRe].reverse().map((point) => ({ ...point }));
    const { cumulativeRe, totalLengthRe } = polylineWithLengths(points);
    if (totalLengthRe < 2) continue;
    paths.push({
      role: "cusp",
      pointsGsmRe: points,
      cumulativeRe,
      totalLengthRe,
      entryGsmRe: { ...points[0]! },
      footpointLatitudeDeg: line.seedLatitudeDeg,
      hemisphere: line.seedLatitudeDeg >= 0 ? "north" : "south",
      schematicFromIndex: null,
      speciesFilter: null,
      branch: null,
      driftSense: null,
    });
  }

  const lobeCandidates = lines.filter((line) =>
    line.topology === "open" && line.pointsGsmRe.length >= 4,
  ).sort((a, b) => a.seedLongitudeDeg - b.seedLongitudeDeg);
  for (const line of thinTo(lobeCandidates, maximumLobe)) {
    let startIndex = 0;
    while (startIndex < line.pointsGsmRe.length) {
      const point = line.pointsGsmRe[startIndex]!;
      if (Math.hypot(point.x, point.y, point.z) >= lobeStartRadiusRe) break;
      startIndex += 1;
    }
    const points = line.pointsGsmRe.slice(startIndex).map((point) => ({ ...point }));
    if (points.length < 3) continue;
    const { cumulativeRe, totalLengthRe } = polylineWithLengths(points);
    if (totalLengthRe < 4) continue;
    paths.push({
      role: "lobe",
      pointsGsmRe: points,
      cumulativeRe,
      totalLengthRe,
      entryGsmRe: { ...points[0]! },
      footpointLatitudeDeg: null,
      hemisphere: line.seedLatitudeDeg >= 0 ? "north" : "south",
      schematicFromIndex: null,
      speciesFilter: null,
      branch: null,
      driftSense: null,
    });
  }
  return paths;
}

/**
 * ## The last stretch: carrying the lobe ride round the rest of the cycle
 *
 * Sean, on the shipped coupling: *"when we have the plasma sheet on, shouldn't
 * we further couple the IMF and solar wind to show the movement of the
 * particles that end up in the ring current and the aurora? Isn't that a major
 * flow?"* — and then, on how to build it: *"I want it done the exact same
 * way."*
 *
 * So this is not a second particle system and not a second visual grammar. It
 * takes the lobe paths the existing coupling already built, keeps the traced
 * field-line leg exactly as it is, cuts it at the near-Earth neutral line, and
 * appends the schematic legs from `dungey-transport.ts`. The result is the
 * same `GuidancePath` shape, ridden by the same tracers, drawn by the same
 * materials, advanced by the same clock. A reader who has learned to read the
 * cusp coupling has nothing new to learn.
 *
 * ## Why the ride is cut at the X-line while the drawn line carries on
 *
 * The traced open lines run to the model's own tail cutoff at 40 Re. That
 * cutoff is a limit of the model domain, not physics. Reconnection at a
 * near-Earth neutral line — around 15 to 25 Re — is the physics, and it is
 * what turns an open lobe line into a closed one and sends the plasma on it
 * back toward Earth. So the particle turns at the X-line and the drawn line
 * carries on past it, which is the honest picture of a model whose open lines
 * cannot reconnect and a magnetosphere whose real ones do.
 *
 * ## Why one lobe line becomes two or three paths
 *
 * Gradient and curvature drift are charge-dependent. Ions injected near
 * midnight drift west toward dusk and electrons east toward dawn, which is why
 * the partial ring current sits in the dusk sector. One path carrying both
 * would draw the two populations on top of each other and teach the opposite
 * of the mechanism, so the ion branch and the electron branch are separate
 * paths with a species filter, and the tracer roster honours it. With the
 * auroral oval also on, electrons get a third path that does not drift at all:
 * it follows the field line down into the atmosphere.
 *
 * ## Containment, which is not optional
 *
 * Every schematic vertex is checked against the Shue boundary for the MEASURED
 * drivers before it is drawn, and a path that fails is dropped back to its
 * plain lobe ride rather than drawn. The inner plasma sheet already shipped
 * once reaching outside the magnetopause on the dayside in every driver state
 * this site has recorded; a particle path outside the boundary is the same
 * defect, and a reader would spot it instantly.
 */
export interface TailReturnReport {
  /** How many lobe rides were carried on round the cycle. */
  extendedPathCount: number;
  /** How many were refused because their schematic legs left the magnetopause. */
  refusedPathCount: number;
  /** How many were refused because the line never reached the neutral line. */
  unreachedPathCount: number;
  /**
   * How many lobe-to-sheet inflow paths were drawn — one per extended ride,
   * so this equals `extendedPathCount` unless an inflow path was too short to
   * be worth drawing.
   */
  inflowPathCount: number;
  /** The worst vertex, as a fraction of its own boundary radius. */
  worstContainmentFraction: number;
  /** Where the turn was placed, Re down-tail. */
  xLineRe: number;
}

/**
 * How many traced vertices back the hand-off tangent is measured over.
 *
 * The traced lines are stepped so that no drawn segment turns by more than
 * four degrees, which makes an individual segment far too short to read a
 * direction off: at 20 Re the steps are a fraction of an Earth radius and the
 * last one carries as much integrator detail as trend. Six vertices is about
 * an Earth radius of the line, long enough for the lobe's own shallow
 * convergence — measured at 7 to 19 degrees off the sheet plane across the
 * driver envelope — to be what the slide continues.
 */
const APPROACH_TANGENT_VERTICES = 6;

export function buildTailReturnPaths(
  lobePaths: readonly GuidancePath[],
  options: TailReturnOptions,
): { paths: GuidancePath[]; report: TailReturnReport } {
  const xLineRe = Math.max(6, options.xLineRe ?? TAIL_X_LINE_RE);
  const paths: GuidancePath[] = [];
  const report: TailReturnReport = {
    extendedPathCount: 0,
    refusedPathCount: 0,
    unreachedPathCount: 0,
    inflowPathCount: 0,
    worstContainmentFraction: 0,
    xLineRe,
  };

  let lobeIndex = -1;
  for (const lobe of lobePaths) {
    lobeIndex += 1;
    // The ride leaves the traced line SUNWARD of the neutral line, not at it.
    // The last stretch of the approach is the flux tube's sheetward convection
    // drift, and a model whose open lines cannot reconnect cannot draw that, so
    // it is the first thing the schematic has to supply: without it the ride
    // ran parallel to the sheet and then dropped onto it at a right angle.
    // `dungey-transport.ts` builds the slide from here to the neutral line.
    //
    // The neutral line is placed at `xLineRe` in the TILTED sheet's own frame,
    // so the GSM x it actually lands at is `xLineRe * cos(tilt)` — 17.3 rather
    // than 20 at a 30-degree tilt. Trimming at a fixed GSM x would then eat the
    // slide down to three Earth radii at exactly the tilts where the lobe line
    // is furthest from the sheet and the slide is needed most, so the hand-off
    // follows the neutral line rather than the constant.
    const handoffRe = Math.max(
      6,
      xLineRe * Math.cos(options.dipoleTiltRad) - LOBE_APPROACH_RUN_RE,
    );
    const trimmed = trimToTailX(lobe.pointsGsmRe, handoffRe);
    if (!trimmed) {
      // The line never gets far enough down-tail to slide onto the sheet
      // before the neutral line, so there is nothing to turn at. It keeps its
      // ordinary lobe ride rather than being given an entry point nobody drew.
      report.unreachedPathCount += 1;
      paths.push(lobe);
      continue;
    }
    const entry = trimmed.at(-1)!;
    // The traced line's own direction of travel at the hand-off, measured back
    // along it rather than off the last segment: the trace steps so no drawn
    // segment turns by more than four degrees, so a single segment is mostly
    // integrator detail. The schematic slide sets off along this, so drawn
    // geometry and schematic geometry meet with no kink and the sheetward
    // convergence the traced line already has is continued, not restarted.
    const tangentFrom = trimmed[Math.max(0, trimmed.length - 1 - APPROACH_TANGENT_VERTICES)]!;
    const approachTangentGsmRe = {
      x: entry.x - tangentFrom.x,
      y: entry.y - tangentFrom.y,
      z: entry.z - tangentFrom.z,
    };
    // Cross-tail position survives the reconnection to first order, so a lobe
    // on the dusk flank injects on the dusk flank. Positive GSM y is dusk and
    // the injection offset is hours from midnight NEGATIVE toward dusk, hence
    // the sign. Clamped inside the sector the plasma-sheet layer draws.
    const injectionMltOffsetHours = Math.max(-3.2, Math.min(3.2, -entry.y * 0.35));

    const branches: Array<{
      branch: DungeyBranch;
      driftSense: DriftSense;
      speciesFilter: readonly SolarWindSpecies[];
    }> = [
      { branch: "ring-current", driftSense: "westward", speciesFilter: ["proton", "alpha"] },
      { branch: "ring-current", driftSense: "eastward", speciesFilter: ["electron"] },
    ];
    if (options.auroraBranch) {
      branches.push({ branch: "aurora", driftSense: "eastward", speciesFilter: ["electron"] });
    }

    let extended = false;
    // The collapse onto the current sheet, kept from whichever branch was
    // accepted first. Every branch of one lobe line shares it exactly — they
    // only diverge at the inner edge — so the inflow path below is a slice of
    // geometry already drawn and already contained, never a second guess at
    // where the plasma goes.
    let collapseSchematic: GsmPointRe[] | null = null;
    for (const variant of branches) {
      const leg = buildDungeyReturnLeg({
        entryGsmRe: entry,
        approachTangentGsmRe,
        dipoleTiltRad: options.dipoleTiltRad,
        innerEdgeRe: options.innerEdgeRe,
        injectionMltOffsetHours,
        hemisphere: lobe.hemisphere,
        branch: variant.branch,
        driftSense: variant.driftSense,
        xLineRe,
        // Each lobe line's trapped particle gets its own equatorial pitch
        // angle and its own point of loss, cycled off the declared sets. One
        // angle for every path would draw a wire where a real drift shell is a
        // band, and one loss point would make a shell that sheds particles
        // across a sector read as a jet from a single local time.
        trapping: trappedMotionForPath(lobeIndex),
      });
      // The traced leg already passed the field-line model's own integrity
      // check; what is checked here is what THIS module added.
      const schematic = leg.pointsGsmRe.slice(1);
      if (!options.magnetopause) {
        report.refusedPathCount += 1;
        continue;
      }
      // Everything up to the neutralisation is a CHARGED particle and must be
      // inside the boundary. The escape ray past it is a neutral atom and must
      // not be checked — see `neutralFromIndex`.
      const check = containedInMagnetopause(
        leg.neutralFromIndex === null
          ? schematic
          : leg.pointsGsmRe.slice(1, leg.neutralFromIndex),
        options.magnetopause.subsolarStandoffRe,
        options.magnetopause.flaringAlpha,
      );
      report.worstContainmentFraction = Math.max(report.worstContainmentFraction, check.worstFraction);
      if (!check.contained) {
        report.refusedPathCount += 1;
        continue;
      }
      const points = [...trimmed.map((point) => ({ ...point })), ...schematic.map((point) => ({ ...point }))];
      const { cumulativeRe, totalLengthRe } = polylineWithLengths(points);
      if (!collapseSchematic) collapseSchematic = leg.pointsGsmRe.slice(1, leg.injectionIndex);
      paths.push({
        role: "return",
        pointsGsmRe: points,
        cumulativeRe,
        totalLengthRe,
        entryGsmRe: { ...points[0]! },
        footpointLatitudeDeg: leg.footpointLatitudeDeg,
        hemisphere: lobe.hemisphere,
        schematicFromIndex: trimmed.length,
        // Leg indices are offset by the trimmed lead, less the shared vertex.
        neutralFromIndex: leg.neutralFromIndex === null
          ? null
          : trimmed.length + leg.neutralFromIndex - 1,
        speciesFilter: variant.speciesFilter,
        branch: variant.branch,
        driftSense: variant.driftSense,
      });
      extended = true;
    }
    if (extended) {
      report.extendedPathCount += 1;
      const inflow = collapseSchematic
        ? buildLobeInflowPath(trimmed, collapseSchematic, lobe.hemisphere)
        : null;
      if (inflow) {
        paths.push(inflow);
        report.inflowPathCount += 1;
      }
    } else paths.push(lobe);
  }
  return { paths, report };
}

/**
 * How much of the traced lobe line, measured back along it from the neutral
 * line, the inflow path covers, in Earth radii.
 *
 * The point of the lead-in is that the arrival should read as plasma COMING
 * IN rather than as particles switched on at the turn: eight Earth radii is
 * long enough to establish a direction of travel before the drop, and short
 * enough that the extra tracers stay where the reader is being asked to look.
 * The lead-in is the traced field line's own geometry, so a tracer on it is
 * on a drawn line exactly as every other guided tracer is.
 */
export const LOBE_INFLOW_LEAD_RE = 8;

/**
 * ## The lobe-to-sheet arrival, drawn as a path of its own
 *
 * Sean, on the shipped Dungey animation: *"it is hard to see particles feeding
 * the plasma sheet itself ... perhaps it needs to be a bit more stark."* The
 * downstream half of the cycle — sheet to ring current, sheet to the oval —
 * reads. The upstream half does not, and the measurement says why: the collapse
 * onto the current sheet is about four Earth radii of a fifty-Earth-radii ride,
 * so a return path spends seven to nine per cent of its journey on the one leg
 * that shows the plasma sheet being FED. At twenty-two tracers a path that is
 * one or two marks in flight per lobe line.
 *
 * The fix is the one the picture already allows: **more tracers on that leg,
 * and nothing else different**. This path is a slice of geometry the return
 * paths already draw — the last `LOBE_INFLOW_LEAD_RE` of the traced lobe line,
 * then the same collapse vertices, ending exactly where the earthward
 * injection begins. Same polyline machinery, same materials, same clock, same
 * species mix, same measured coupling deciding how many are lit. No new
 * effect, no second colour, no trail of its own: a reader sees more of the
 * same particles arriving, which is what was asked for.
 *
 * **It carries all three species on purpose.** Upstream of the inner edge the
 * population has not been sorted yet — the charge split is what gradient and
 * curvature drift do to it at the inner edge, and drawing it earlier would
 * teach the split in the wrong place.
 *
 * **It is not a new claim.** Every vertex here has already been drawn by the
 * return paths this instant, and the schematic half of it has already passed
 * the magnetopause containment check as part of them. Nothing is added to the
 * picture that was not in it; what changes is how many marks are on the part
 * of it that answers "where does the plasma sheet get its plasma".
 */
export function buildLobeInflowPath(
  tracedToNeutralLine: readonly GsmPointRe[],
  collapseGsmRe: readonly GsmPointRe[],
  hemisphere: "north" | "south",
  leadRe = LOBE_INFLOW_LEAD_RE,
): GuidancePath | null {
  if (collapseGsmRe.length < 2) return null;
  const lead = tailOfPolyline(tracedToNeutralLine, leadRe);
  if (lead.length < 2) return null;
  const points = [...lead.map((point) => ({ ...point })), ...collapseGsmRe.map((point) => ({ ...point }))];
  const { cumulativeRe, totalLengthRe } = polylineWithLengths(points);
  if (!(totalLengthRe > 1)) return null;
  return {
    role: "inflow",
    pointsGsmRe: points,
    cumulativeRe,
    totalLengthRe,
    entryGsmRe: { ...points[0]! },
    footpointLatitudeDeg: null,
    hemisphere,
    // Everything from the end of the traced lead-in on is the same schematic
    // collapse the return paths carry, and is labelled the same way.
    schematicFromIndex: lead.length,
    speciesFilter: null,
    branch: null,
    driftSense: null,
  };
}

/**
 * The last `lengthRe` of arc of a polyline, with the cut interpolated onto the
 * line so the path starts at a distance rather than at whichever traced vertex
 * happened to land nearest it.
 */
function tailOfPolyline(points: readonly GsmPointRe[], lengthRe: number): GsmPointRe[] {
  if (points.length < 2) return points.map((point) => ({ ...point }));
  const { cumulativeRe, totalLengthRe } = polylineWithLengths(points as Array<{ x: number; y: number; z: number }>);
  const start = totalLengthRe - Math.max(0, lengthRe);
  if (start <= 0) return points.map((point) => ({ ...point }));
  let index = 1;
  while (index < cumulativeRe.length - 1 && cumulativeRe[index]! < start) index += 1;
  const before = cumulativeRe[index - 1]!;
  const span = Math.max(1e-9, cumulativeRe[index]! - before);
  const fraction = clamp((start - before) / span);
  const a = points[index - 1]!;
  const b = points[index]!;
  const cut = {
    x: a.x + (b.x - a.x) * fraction,
    y: a.y + (b.y - a.y) * fraction,
    z: a.z + (b.z - a.z) * fraction,
  };
  return [cut, ...points.slice(index).map((point) => ({ ...point }))];
}

/**
 * The traced lobe polyline up to where it first crosses `xLineRe` down-tail,
 * with the crossing itself interpolated onto the line so the turn happens at
 * the neutral line rather than at whichever RK4 step landed nearest to it.
 *
 * Null when the line never gets that far.
 */
export function trimToTailX(
  points: ReadonlyArray<{ x: number; y: number; z: number }>,
  xLineRe: number,
): GsmPointRe[] | null {
  const target = -Math.abs(xLineRe);
  for (let index = 1; index < points.length; index += 1) {
    const before = points[index - 1]!;
    const after = points[index]!;
    if (before.x > target && after.x <= target) {
      const span = before.x - after.x;
      const fraction = span > 1e-9 ? (before.x - target) / span : 0;
      const crossing = {
        x: target,
        y: before.y + (after.y - before.y) * fraction,
        z: before.z + (after.z - before.z) * fraction,
      };
      const kept = points.slice(0, index).map((point) => ({ ...point }));
      kept.push(crossing);
      return kept.length >= 3 ? kept : null;
    }
  }
  return null;
}

export interface GuidedJourneySample {
  xRe: number;
  yRe: number;
  zRe: number;
  /** True once the particle is ON the field line rather than approaching it. */
  onPath: boolean;
}

/**
 * Where a guided particle is at `progress` ∈ [0, 1) of its journey: a
 * straight sunward approach leg from `approachSpanRe` upstream of the entry
 * point, then arc-length travel along the guidance polyline itself. The
 * on-path segment interpolates BETWEEN the polyline's own vertices, so a
 * guided particle's distance to the drawn field line is exactly zero — the
 * property the coupling claims, and the one the tests measure.
 */
export function sampleGuidedJourney(
  path: GuidancePath,
  progress01: number,
  approachSpanRe = 12,
): GuidedJourneySample {
  const progress = ((progress01 % 1) + 1) % 1;
  const approach = Math.max(0, approachSpanRe);
  const total = approach + path.totalLengthRe;
  const distance = progress * total;
  if (distance < approach) {
    const entry = path.entryGsmRe;
    return {
      xRe: entry.x + (approach - distance),
      yRe: entry.y,
      zRe: entry.z,
      onPath: false,
    };
  }
  const along = distance - approach;
  let segment = 1;
  while (segment < path.cumulativeRe.length - 1 && path.cumulativeRe[segment]! < along) segment += 1;
  const before = path.cumulativeRe[segment - 1]!;
  const span = Math.max(1e-9, path.cumulativeRe[segment]! - before);
  const fraction = clamp((along - before) / span);
  const start = path.pointsGsmRe[segment - 1]!;
  const end = path.pointsGsmRe[segment]!;
  return {
    xRe: start.x + (end.x - start.x) * fraction,
    yRe: start.y + (end.y - start.y) * fraction,
    zRe: start.z + (end.z - start.z) * fraction,
    onPath: true,
  };
}

interface GuidedTracer {
  pathIndex: number;
  phase: number;
  species: SolarWindSpecies;
  /** Which slot of its path's roster this is, so the measured drive can thin the roster. */
  slot: number;
}

/**
 * Pick a species for a path that only some species may ride.
 *
 * The ion branch of the ring current carries protons and alphas in the
 * MEASURED bulk ratio, renormalised over the two — the same ratio the free
 * shower samples, so the guided population stays the same wind rather than
 * becoming a new one. A single-species filter needs no arithmetic at all.
 */
function speciesFromFilter(
  index: number,
  filter: readonly SolarWindSpecies[] | null,
  mix: SolarWindSpeciesMix,
): SolarWindSpecies {
  if (!filter || filter.length === 0) return solarWindSpeciesForIndex(index, mix);
  if (filter.length === 1) return filter[0]!;
  const weightOf = (species: SolarWindSpecies) =>
    species === "proton" ? mix.protonFraction
      : species === "alpha" ? mix.alphaFraction
        : mix.electronFraction;
  const total = filter.reduce((sum, species) => sum + weightOf(species), 0);
  if (!(total > 0)) return filter[0]!;
  const position = ((index + 1) * SPECIES_GOLDEN_FRACTION) % 1;
  let cursor = 0;
  for (const species of filter) {
    cursor += weightOf(species) / total;
    if (position < cursor) return species;
  }
  return filter[filter.length - 1]!;
}

/**
 * ## There is no drawn guide under the transport, and that was a decision
 *
 * A dashed violet line under the schematic legs was built, tuned and looked
 * at, and then removed. Recorded here so nobody builds it again.
 *
 * The argument for it was honesty: on the cusp legs the particle rides a DRAWN
 * field line, and on the tail legs there is nothing measured to draw, so a
 * dashed line — this site's existing grammar for "not a measurement", the same
 * one the Kp chart uses for its forecast bars — would mark the difference.
 *
 * Three things killed it. Inked flat at 0.22 it contributed nothing against
 * the traced field lines; at 0.50 it read as scattered ticks across the whole
 * tail; and even faded to exactly where nothing else is drawn, it was the one
 * element in the picture that was not the wind itself. Sean, on what this is
 * for: *"The exact same particles, but this time you see them moving in the
 * way physics says they will. Nothing gimmicky. Nothing stupid."* A mark that
 * is not a particle and not a field line is the gimmick, however well argued.
 *
 * The evidence split it existed to carry is carried instead by the layer's own
 * card, in words — which is where the rest of this site puts it — and by
 * `evidence: "schematic"` plus `returnLegEvidence` on the drawn geometry,
 * where a test can read it.
 */

export class SolarWindVisual {
  readonly group = new THREE.Group();
  readonly material: THREE.ShaderMaterial;
  readonly trailMaterial: THREE.ShaderMaterial;
  readonly modelMaterial: THREE.ShaderMaterial;
  readonly modelTrailMaterial: THREE.ShaderMaterial;
  readonly guidedMaterial: THREE.ShaderMaterial;
  readonly guidedTrailMaterial: THREE.ShaderMaterial;
  private pointsValue: THREE.Points<THREE.BufferGeometry, THREE.ShaderMaterial>;
  private trailsValue: THREE.LineSegments<THREE.BufferGeometry, THREE.ShaderMaterial>;
  private modelPointsValue: THREE.Points<THREE.BufferGeometry, THREE.ShaderMaterial>;
  private modelTrailsValue: THREE.LineSegments<THREE.BufferGeometry, THREE.ShaderMaterial>;
  private guidedPointsValue: THREE.Points<THREE.BufferGeometry, THREE.ShaderMaterial>;
  private guidedTrailsValue: THREE.LineSegments<THREE.BufferGeometry, THREE.ShaderMaterial>;
  private readonly options: SolarWindVisualOptions;
  private readonly positionForPlane: PlanePositionMapper;
  private readonly positionForGsm: GsmPositionMapper;
  private readonly trailLength: number;
  private modelTracers: ModelTracer[] = [];
  private guidancePathsValue: GuidancePath[] = [];
  private guidedTracers: GuidedTracer[] = [];
  /**
   * Roster size per path, parallel to `guidancePathsValue`.
   *
   * Kept rather than looked up. `updateGuided` needs it once per path per
   * frame, and finding it by scanning the tracer list was 52 paths x 640
   * tracers of array walking every frame for a number that only changes when
   * the roster is rebuilt.
   */
  private guidedSlotsPerPath: number[] = [];
  private couplingActiveValue = false;
  /**
   * Whether the magnetosphere layer is drawing its own field lines. When it
   * is, the guidance cue comes off. See `SOLAR_WIND_GUIDANCE_CUE`.
   */
  private fieldLinesDrawnElsewhereValue = false;
  private guidanceCueValue: THREE.LineSegments<THREE.BufferGeometry, THREE.LineBasicMaterial> | null = null;
  private guidanceCueSchematicValue: THREE.LineSegments<THREE.BufferGeometry, THREE.LineBasicMaterial> | null = null;
  /**
   * The MEASURED drive, 0 to 1, or null when there is no coupling number.
   *
   * Null is not zero and the difference is the whole of the honesty here: zero
   * is a measured northward IMF opening almost no flux, and null is no
   * propagated solar wind at all, in which case there is no rate and nothing
   * is drawn. Only the tail-return population reads it; the cusp coupling is
   * untouched, because that picture was already right.
   */
  private couplingDriveValue: number | null = null;
  private tailReturnReportValue: TailReturnReport | null = null;
  private planeTracersVisibleValue = false;
  /**
   * The obstacle cue. Rebuilt with the flow, because it is the same shape.
   * Hidden when the magnetosphere layer is drawing the real boundary.
   */
  private obstacleSilhouetteValue: THREE.Group | null = null;
  private boundaryDrawnElsewhereValue = false;
  // The scene hands every visual the environmental-motion clock as SECONDS
  // SINCE THE CLOCK STARTED, not as a per-frame delta. Held here so a rebuild
  // mid-flight can reseed at the current time instead of snapping to zero.
  private lastElapsedDisplaySeconds = 0;
  /**
   * The drawn radius the upstream face is currently cut to, or null before the
   * scene has told this visual how big its frame is. Null means the face falls
   * back to `DEFAULT_TRANSVERSE_EXTENT_RE`, which is what an off-screen or
   * headless use of this class gets.
   */
  private viewFaceDrawnRadius: number | null = null;
  private encoding = solarWindIntensityEncoding(null, null);
  private magnetopauseStandoffRe: number;
  private boundaryRadiusForDirection: BoundaryRadiusField | null;
  private speedKps = 0;
  mode: SolarWindVisualMode = "illustrative-upstream";

  constructor(options: SolarWindVisualOptions = {}) {
    this.options = options;
    this.positionForPlane = options.positionForPlane ?? defaultPlanePosition;
    this.positionForGsm = options.positionForGsm ?? defaultGsmPosition;
    this.magnetopauseStandoffRe = options.magnetopauseStandoffRe ?? 10;
    this.boundaryRadiusForDirection = options.boundaryRadiusForDirection ?? null;
    this.trailLength = Math.max(0, options.trailLength ?? 1.5);
    this.material = createSpeciesFlowMaterial(options.pixelRatio ?? 1);
    this.trailMaterial = createSpeciesTrailMaterial();
    this.modelMaterial = createModelFlowMaterial(options.pixelRatio ?? 1);
    this.modelTrailMaterial = createTrailMaterial();
    (this.modelTrailMaterial.uniforms.color as { value: THREE.Color }).value = new THREE.Color(0x9fefff);
    this.guidedMaterial = createSpeciesFlowMaterial(options.pixelRatio ?? 1);
    this.guidedTrailMaterial = createSpeciesTrailMaterial();
    // The 3-D cloud is always on: it is what makes the layer read as a wind
    // meeting an obstacle from EVERY camera angle.
    this.pointsValue = new THREE.Points(new THREE.BufferGeometry(), this.material);
    this.pointsValue.frustumCulled = false;
    this.trailsValue = new THREE.LineSegments(new THREE.BufferGeometry(), this.trailMaterial);
    this.trailsValue.frustumCulled = false;
    this.trailsValue.name = "solar-wind-tracer-streaks";
    // The published BATS-R-US plane tracers are now part of the NOAA MHD
    // cross-section OPTION, not the solar-wind layer's default face: two
    // bright beaded curves confined to the cut planes read as an artifact
    // over the volumetric shower ("do we need those little squares?" — no).
    // They stay built and animated so switching the cut on costs nothing.
    this.modelPointsValue = new THREE.Points(new THREE.BufferGeometry(), this.modelMaterial);
    this.modelPointsValue.frustumCulled = false;
    this.modelPointsValue.name = "solar-wind-model-plane-tracers";
    this.modelPointsValue.visible = false;
    this.modelTrailsValue = new THREE.LineSegments(new THREE.BufferGeometry(), this.modelTrailMaterial);
    this.modelTrailsValue.frustumCulled = false;
    this.modelTrailsValue.name = "solar-wind-model-plane-streaks";
    this.modelTrailsValue.visible = false;
    // The field-guided sub-population: drawn only while the magnetosphere
    // layer's traced lines are on screen to be followed.
    this.guidedPointsValue = new THREE.Points(new THREE.BufferGeometry(), this.guidedMaterial);
    this.guidedPointsValue.frustumCulled = false;
    this.guidedPointsValue.name = "solar-wind-field-guided-tracers";
    this.guidedPointsValue.visible = false;
    this.guidedPointsValue.renderOrder = SOLAR_WIND_GUIDED_RENDER_ORDER;
    this.guidedTrailsValue = new THREE.LineSegments(new THREE.BufferGeometry(), this.guidedTrailMaterial);
    this.guidedTrailsValue.frustumCulled = false;
    this.guidedTrailsValue.name = "solar-wind-field-guided-streaks";
    this.guidedTrailsValue.visible = false;
    this.guidedTrailsValue.renderOrder = SOLAR_WIND_GUIDED_RENDER_ORDER;
    this.group.add(
      this.trailsValue,
      this.pointsValue,
      this.modelTrailsValue,
      this.modelPointsValue,
      this.guidedTrailsValue,
      this.guidedPointsValue,
    );
    this.group.userData.method = SOLAR_INPUT_VISUAL_METHOD.solarWind;
    this.buildFallback();
    this.setModelFlow(options.modelFlow ?? null);
  }

  /** The illustrative 3-D deflection cloud — present in every mode. */
  get points() {
    return this.pointsValue;
  }

  get trails() {
    return this.trailsValue;
  }

  /** The published BATS-R-US plane tracers; empty until the model flow loads, hidden until the MHD cut asks for them. */
  get modelPoints() {
    return this.modelPointsValue;
  }

  get modelTrails() {
    return this.modelTrailsValue;
  }

  /** The field-guided sub-population; empty until guidance lines arrive. */
  get guidedPoints() {
    return this.guidedPointsValue;
  }

  get guidedTrails() {
    return this.guidedTrailsValue;
  }

  get guidancePaths(): readonly GuidancePath[] {
    return this.guidancePathsValue;
  }

  get couplingActive() {
    return this.couplingActiveValue;
  }

  /** The measured coupling drive currently animating the return legs, or null. */
  get couplingDrive() {
    return this.couplingDriveValue;
  }

  /** What the last tail-return build did, including its containment result. */
  get tailReturnReport(): TailReturnReport | null {
    return this.tailReturnReportValue;
  }


  get planeTracersVisible() {
    return this.planeTracersVisibleValue;
  }

  get currentEncoding() {
    return this.encoding;
  }

  setPixelRatio(pixelRatio: number) {
    this.material.uniforms.pixelRatio!.value = Math.max(0.25, pixelRatio);
    this.modelMaterial.uniforms.pixelRatio!.value = Math.max(0.25, pixelRatio);
    this.guidedMaterial.uniforms.pixelRatio!.value = Math.max(0.25, pixelRatio);
  }

  /**
   * How far the camera is from Earth's centre, in scene units — the reference
   * length every depth cue is measured against. See `SOLAR_WIND_DEPTH_CUE`.
   *
   * The scene has to hand this over every frame, because it is the only thing
   * that knows where the camera is. Handing over zero, or never calling this at
   * all, turns both depth terms off and restores exactly the flat rendering
   * this replaced — which is what a headless build or a test gets.
   */
  setCameraDistance(distanceSceneUnits: number | null) {
    const value = distanceSceneUnits !== null && Number.isFinite(distanceSceneUnits) && distanceSceneUnits > 0
      ? distanceSceneUnits
      : 0;
    for (const material of [
      this.material,
      this.trailMaterial,
      this.modelMaterial,
      this.modelTrailMaterial,
      this.guidedMaterial,
      this.guidedTrailMaterial,
    ]) {
      const uniform = material.uniforms.cameraToEarth;
      if (uniform) uniform.value = value;
    }
  }

  setConditions(speedKps: number | null, densityCm3: number | null) {
    this.encoding = solarWindIntensityEncoding(speedKps, densityCm3);
    this.speedKps = this.encoding.available && speedKps !== null ? speedKps : 0;
    // Colour is SPECIES (fixed per particle, by charge sign); the measured
    // conditions drive everything else — population and brightness from
    // density, motion cadence from bulk speed, plane-tracer prominence from
    // both. No colour is recomputed here, so the legend's swatches can never
    // drift from the pixels.
    this.material.uniforms.opacity!.value = this.encoding.opacity;
    this.material.uniforms.pointSize!.value = this.encoding.pointSize;
    this.trailMaterial.uniforms.opacity!.value = this.encoding.opacity * 0.85;
    this.modelMaterial.uniforms.opacity!.value = Math.min(1, this.encoding.opacity * 1.25);
    this.modelMaterial.uniforms.pointSize!.value = this.encoding.pointSize * 1.15;
    this.modelTrailMaterial.uniforms.opacity!.value = this.encoding.opacity;
    // The guided sub-population sits slightly brighter than the free shower,
    // because it is the part of the picture the coupling exists to show.
    this.guidedMaterial.uniforms.opacity!.value = Math.min(1, this.encoding.opacity * 1.35);
    this.guidedMaterial.uniforms.pointSize!.value = this.encoding.pointSize * 1.3;
    this.guidedTrailMaterial.uniforms.opacity!.value = Math.min(1, this.encoding.opacity * 1.1);
    this.applyDrawRange();
    this.applyGuidedVisibility();
    this.group.userData.dataAvailable = this.encoding.available;
    this.group.userData.currentDrivers = {
      speedKps: this.encoding.available ? speedKps : null,
      densityCm3: this.encoding.available ? densityCm3 : null,
    };
    return this.encoding;
  }

  setMagnetopauseStandoffRe(radiusRe: number | null) {
    this.magnetopauseStandoffRe = radiusRe !== null && Number.isFinite(radiusRe)
      ? radiusRe
      : (this.options.magnetopauseStandoffRe ?? 10);
    // The 3-D cloud is always drawn now, so its obstacle always tracks the
    // live boundary — a storm compresses the deflection pattern in any mode.
    this.buildFallback();
  }

  /**
   * Hand the tracers the boundary the reader can see.
   *
   * Passing `null` returns the obstacle to a sphere at the subsolar standoff,
   * which is what happens when the boundary models cannot be evaluated for the
   * selected time and the layer has no drawn surface to respect.
   */
  setBoundaryRadiusForDirection(field: BoundaryRadiusField | null) {
    this.boundaryRadiusForDirection = field;
    this.buildFallback();
  }

  /**
   * Rebuild the obstacle cue from the domain the flow was just solved in.
   *
   * Kept in lockstep with the geometry rather than cached, because a change of
   * standoff or of the boundary field changes both, and a stale silhouette
   * would be a drawn surface the tracers walk through.
   */
  private rebuildObstacleSilhouette(domain: IllustrativeUpstreamDomain | undefined) {
    if (this.obstacleSilhouetteValue) {
      this.group.remove(this.obstacleSilhouetteValue);
      disposeObject3D(this.obstacleSilhouetteValue);
      this.obstacleSilhouetteValue = null;
    }
    if (!domain) return;
    const silhouette = createSolarWindObstacleSilhouette(domain.obstacle, this.positionForGsm, {
      downstreamEndRe: domain.downstreamEndRe,
    });
    // Sean, 2026-08-20: "get rid of the white thing under solar wind" /
    // "I have no idea where that white balloon came from". The silhouette read
    // as an opaque white balloon around Earth rather than a faint cue, and a
    // drawn surface nobody asked for is worse than no cue at all. It is kept
    // built (the tracer solve and the tests reference it) but never shown.
    silhouette.visible = false;
    this.obstacleSilhouetteValue = silhouette;
    this.group.add(silhouette);
  }

  /** The obstacle cue, for tests and for the legend. */
  get obstacleSilhouette(): THREE.Group | null {
    return this.obstacleSilhouetteValue;
  }

  /**
   * Whether the magnetosphere layer is already drawing this boundary.
   *
   * When it is, the cue comes off: two drawings of one surface at two opacities
   * is worse than either, and the magnetosphere layer's is the one with the
   * legend, the drivers and the cusp geometry attached to it.
   */
  setBoundaryDrawnElsewhere(drawn: boolean) {
    if (drawn === this.boundaryDrawnElsewhereValue) return;
    this.boundaryDrawnElsewhereValue = drawn;
    // The silhouette is never shown (see buildObstacleSilhouette); this setter
    // only records the state so the legend copy stays truthful.
    if (this.obstacleSilhouetteValue) this.obstacleSilhouetteValue.visible = false;
  }

  setModelFlow(modelFlow: SolarWindModelFlowInput | null) {
    this.modelTracers = [];
    if (modelFlow) {
      const earthRadiusRe = Math.max(0.001, this.options.earthRadiusRe ?? 1);
      const minimumRadiusRe = Math.max(
        earthRadiusRe + 0.01,
        this.options.minimumModelRadiusRe ?? 2.55,
      );
      const maximumSegmentRe = Math.max(0.01, this.options.maximumModelSegmentRe ?? 0.75);
      const tracersPerPath = Math.max(1, Math.floor(this.options.tracersPerModelPath ?? 3));
      (["equatorial", "meridional"] as const).forEach((plane) => {
        const encoded = modelFlow.projectedFlowStreamlines[plane];
        if (!encoded) return;
        const paths = buildProjectedFlowAdvectionPaths(modelFlow.definition, encoded, {
          minimumRadiusRe,
          maximumSegmentRe,
        });
        paths.forEach((path) => {
          for (let tracerIndex = 0; tracerIndex < tracersPerPath; tracerIndex += 1) {
            this.modelTracers.push({
              path,
              plane,
              phase: tracerIndex / tracersPerPath,
            });
          }
        });
      });
    }
    this.buildModelTracers();
    this.applyDrawRange();
    return this.mode;
  }

  /**
   * Hand the coupling the traced field-line set to guide particles along.
   * `null` clears it — the wind returns to pure obstacle deflection, which is
   * exactly the magnetosphere-layer-off behaviour.
   */
  setFieldGuidance(lines: readonly FieldGuidanceLine[] | null, options: GuidancePathOptions = {}) {
    const base = lines ? buildGuidancePaths(lines, options) : [];
    if (base.length > 0 && options.tailReturn) {
      // The lobe rides carry on round the rest of the Dungey cycle. Everything
      // else — the cusp funnels, the approach, the materials, the clock — is
      // untouched, because that part of the picture was already right.
      const lobe = base.filter((path) => path.role === "lobe");
      const extended = buildTailReturnPaths(lobe, options.tailReturn);
      this.guidancePathsValue = [
        ...base.filter((path) => path.role !== "lobe"),
        ...extended.paths,
      ];
      this.tailReturnReportValue = extended.report;
    } else {
      this.guidancePathsValue = base;
      this.tailReturnReportValue = null;
    }
    this.rebuildGuidedTracers();
    this.rebuildGuidanceCue();
    this.applyGuidedVisibility();
  }

  /**
   * The MEASURED rate the return legs are animated at.
   *
   * `couplingDrive()` in `dungey-transport.ts` places the published Newell
   * et al. (2007) coupling function on the site's own published band ladder;
   * this is where that number reaches the pixels. Null takes the population
   * off entirely, which is what happens past the last propagated driver.
   */
  setCouplingDrive(drive: number | null) {
    this.couplingDriveValue = drive === null || !Number.isFinite(drive)
      ? null
      : Math.min(1, Math.max(0, drive));
  }

  /**
   * Whether the guided sub-population is drawn at all.
   *
   * This used to mean "the magnetosphere layer is on screen for the wind to
   * couple to". Since 2026-08-27 it means "there are guidance paths to ride",
   * because Sean ruled that the wind should move the same way whichever layers
   * are on. See `SOLAR_WIND_GUIDANCE_CUE` for what is drawn to explain the
   * bending when the magnetosphere layer is off.
   */
  setCouplingActive(active: boolean) {
    this.couplingActiveValue = active;
    this.applyGuidedVisibility();
  }

  /**
   * Whether the published BATS-R-US plane tracers are wanted: they belong to
   * the NOAA MHD cross-section option now, never to the default shower.
   */
  setPlaneTracersVisible(visible: boolean) {
    this.planeTracersVisibleValue = visible;
    this.applyModelTracerVisibility();
  }

  /**
   * The published BATS-R-US plane tracers are built but never drawn.
   *
   * They were real model data — beads riding the flow on NOAA's own z=0 and
   * y=0 cuts, bunching where the shock slows it — and they still looked wrong,
   * because NOAA publishes that solution on TWO FLAT CUTS and nothing else. In
   * a 3-D scene, from every angle except face-on, beads confined to two planes
   * read as arcs hanging in space with no surface to belong to. Sean, with the
   * solar wind and magnetosphere both on: "I see these extra green lines that I
   * shouldn't … I don't know what they're trying to show but they don't look
   * good." Then: "I don't think you should be drawing those green lines at
   * all." A picture that makes a reader ask "what is that?" has already failed.
   *
   * HIDDEN AT THE RENDER GATE, NOT AT CONSTRUCTION, AND THAT IS LOAD-BEARING.
   * `this.mode` is `modelTracers.length > 0 ? "model-projected" :
   * "illustrative-upstream"`, so not building them would silently drop the
   * whole layer back to the idealised potential-flow fallback — the one that
   * draws as a shell around the Earth, which is the picture Sean rejected
   * earlier and the opposite of the coupled view he praised. The beads and the
   * flow model are wired to the same flag; only the beads were unwanted.
   *
   * The cut planes still draw the same field as coloured surfaces, which is
   * where that evidence belongs and where it cannot be mistaken for 3-D flow.
   */
  private applyModelTracerVisibility() {
    const shown = DRAW_PUBLISHED_PLANE_TRACERS
      && this.planeTracersVisibleValue
      && this.modelTracers.length > 0;
    this.modelPointsValue.visible = shown;
    this.modelTrailsValue.visible = shown;
  }

  private applyGuidedVisibility() {
    const shown = this.couplingActiveValue
      && this.encoding.available
      && this.guidedTracers.length > 0;
    this.guidedPointsValue.visible = shown;
    this.guidedTrailsValue.visible = shown;
    // ...and the cue that says what they are riding.
    //
    // THE TWO HALVES OF THE CUE ARE NOT DRAWN ELSEWHERE BY THE SAME PARTY.
    //
    // The TRACED half is the magnetosphere layer's own field-line output, so
    // when that layer is on it IS being drawn elsewhere, at a better weight,
    // and a second copy of it is the double-drawing this rule exists to stop.
    //
    // The SCHEMATIC half is not. Nothing else on the page draws the Dungey
    // legs — the slide onto the current sheet, the turn at the neutral line,
    // the earthward injection, the trapped helix round the Earth, and the two
    // ways a trapped particle leaves. Suppressing it whenever the
    // magnetosphere layer happened to be on took the path out from under
    // exactly the part of the journey nobody else draws, and left the tracers
    // on that leg moving through apparently empty space. Sean, having watched
    // the shipped version with the magnetosphere layer on, 2026-08-27: *"I
    // don't see anything trapped. I don't see anything that really shows
    // particles are bound for the radiation belts or the ring current."*
    //
    // It stays dotted and it stays dimmer than the traced half, so what a
    // reader gains is the path, never a claim that anybody measured it.
    if (this.guidanceCueValue) {
      this.guidanceCueValue.visible = shown && !this.fieldLinesDrawnElsewhereValue;
    }
    if (this.guidanceCueSchematicValue) {
      this.guidanceCueSchematicValue.visible = shown;
      // Weighted for what it has to be seen through: see
      // `SOLAR_WIND_GUIDANCE_CUE.schematicOpacityOverField`.
      this.guidanceCueSchematicValue.material.opacity = this.fieldLinesDrawnElsewhereValue
        ? SOLAR_WIND_GUIDANCE_CUE.schematicOpacityOverField
        : SOLAR_WIND_GUIDANCE_CUE.schematicOpacity;
    }
  }

  /**
   * Whether the magnetosphere layer is drawing the field lines itself.
   *
   * Two drawings of one set of lines at two weights is worse than either, and
   * the magnetosphere layer's is the one with the |B| ramp, the drivers and
   * the cusp geometry attached. Same rule as the obstacle silhouette.
   */
  setFieldLinesDrawnElsewhere(drawn: boolean) {
    if (drawn === this.fieldLinesDrawnElsewhereValue) return;
    this.fieldLinesDrawnElsewhereValue = drawn;
    this.applyGuidedVisibility();
  }

  /** Whether the faint TRACED guidance cue is on screen right now. */
  get guidanceCueVisible() {
    return this.guidanceCueValue?.visible === true;
  }

  /**
   * Whether the dotted SCHEMATIC guidance cue is on screen right now.
   *
   * Separate from the traced one because they come and go for different
   * reasons: see `applyGuidedVisibility`.
   */
  get guidanceCueSchematicVisible() {
    return this.guidanceCueSchematicValue?.visible === true;
  }

  /** The cue's two objects, for tests: the traced stretch and the schematic one. */
  get guidanceCue() {
    return { traced: this.guidanceCueValue, schematic: this.guidanceCueSchematicValue };
  }

  /**
   * Build the faint "this is what they are riding" cue from the guidance paths
   * themselves — no new geometry, no second model, the same arrays the tracers
   * are walking. Traced stretches draw solid; schematic ones draw dashed, by
   * walking the dash cycle in ARC LENGTH along the path and cutting wherever
   * the cycle boundary falls, which may be inside a tessellation segment.
   *
   * Cutting inside a segment invents nothing: the polyline between two
   * consecutive vertices IS a straight line, so a point interpolated along it
   * is a point of the drawn path. That is what the cue's no-new-geometry
   * invariant means, and a test holds every emitted vertex to lying ON the
   * path rather than to being one of its listed vertices.
   *
   * The cycle starts at zero at the hand-off vertex, so every schematic leg
   * begins with ink exactly where its traced half ends and the two never meet
   * across a gap.
   */
  private rebuildGuidanceCue() {
    for (const existing of [this.guidanceCueValue, this.guidanceCueSchematicValue]) {
      if (!existing) continue;
      this.group.remove(existing);
      existing.geometry.dispose();
      existing.material.dispose();
    }
    this.guidanceCueValue = null;
    this.guidanceCueSchematicValue = null;
    if (this.guidancePathsValue.length === 0) return;
    const traced: number[] = [];
    const schematic: number[] = [];
    const point = new THREE.Vector3();
    const onRe = SOLAR_WIND_GUIDANCE_CUE.schematicDashOnRe;
    const cycleRe = onRe + SOLAR_WIND_GUIDANCE_CUE.schematicDashOffRe;
    const emit = (
      from: GsmPointRe,
      to: GsmPointRe,
      startFraction: number,
      endFraction: number,
      target: number[],
    ) => {
      for (const fraction of [startFraction, endFraction]) {
        point.copy(this.positionForGsm(
          from.x + (to.x - from.x) * fraction,
          from.y + (to.y - from.y) * fraction,
          from.z + (to.z - from.z) * fraction,
        ));
        target.push(point.x, point.y, point.z);
      }
    };
    for (const path of this.guidancePathsValue) {
      const split = path.schematicFromIndex ?? path.pointsGsmRe.length;
      // Arc length walked along the SCHEMATIC stretch, which is what the dash
      // cycle is measured in. It restarts at zero at the hand-off vertex.
      let schematicRunRe = 0;
      for (let index = 1; index < path.pointsGsmRe.length; index += 1) {
        const from = path.pointsGsmRe[index - 1]!;
        const to = path.pointsGsmRe[index]!;
        // CORRECTNESS FIX 2026-09-04: `<`, not `<=`. `schematicFromIndex` is the
        // index of the FIRST schematic point, so the segment numbered `split`
        // runs from the last traced vertex to the first schematic one — it is
        // the hand-off, and half of it is not traced geometry. `<=` emitted it
        // into the solid buffer, which broke the invariant this cue exists to
        // hold: "solid ink is reserved for the traced field-line model's own
        // geometry". Measured before the fix: 0.151 Re of solid ink past the
        // hand-off on every one of the twelve tail-return paths.
        if (index < split) {
          emit(from, to, 0, 1, traced);
          continue;
        }
        const spanRe = Math.hypot(to.x - from.x, to.y - from.y, to.z - from.z);
        if (!(spanRe > 0)) continue;
        // Cut this segment wherever the dash cycle says to, and emit only the
        // inked parts. "Nobody measures these trajectories" stays visible
        // rather than said, at a rhythm a reader can follow as one path.
        let at = 0;
        while (at < 1) {
          const phaseRe = (schematicRunRe + at * spanRe) % cycleRe;
          const inked = phaseRe < onRe;
          const remainingRe = inked ? onRe - phaseRe : cycleRe - phaseRe;
          const next = Math.min(1, Math.max(at + 1e-9, at + remainingRe / spanRe));
          if (inked) emit(from, to, at, next, schematic);
          at = next;
        }
        schematicRunRe += spanRe;
      }
    }
    const build = (values: number[], opacity: number, name: string) => {
      if (values.length === 0) return null;
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(values), 3));
      const material = new THREE.LineBasicMaterial({
        color: new THREE.Color(SOLAR_WIND_GUIDANCE_CUE.colorHex),
        transparent: true,
        opacity,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      });
      const lines = new THREE.LineSegments(geometry, material);
      lines.frustumCulled = false;
      lines.name = name;
      lines.visible = false;
      lines.renderOrder = SOLAR_WIND_GUIDED_RENDER_ORDER;
      lines.userData.evidence = "model";
      lines.userData.what = name.includes("schematic")
        ? "schematic Dungey transport — nobody measures these trajectories, which is why it is drawn as a broken line"
        : "the traced field-line model's own output, drawn so the guided particles are not bending for no visible reason";
      this.group.add(lines);
      return lines;
    };
    this.guidanceCueValue = build(traced, SOLAR_WIND_GUIDANCE_CUE.tracedOpacity, "solar-wind-guidance-cue-traced");
    this.guidanceCueSchematicValue = build(schematic, SOLAR_WIND_GUIDANCE_CUE.schematicOpacity, "solar-wind-guidance-cue-schematic");
  }

  /**
   * One tracer roster per guidance set. Cusp paths get the lion's share —
   * particles falling to the poles are the point of the coupling — and every
   * tracer keeps a species from the same prefix-balanced assignment the free
   * shower uses, so the guided population is the same wind, not a new one.
   */
  private rebuildGuidedTracers() {
    const tracersPerCuspPath = 16;
    const tracersPerLobePath = 5;
    // A return ride is three to four times the arc of a lobe ride, and at
    // eight tracers spread over that arc it read as scattered dots rather than
    // as a flow — looked at, in motion, before this number was changed. Sean's
    // rule settles what to do about it: *"Sure most particles don't do this
    // interaction. But enough are drawn to highlight that it is happening."*
    // So there are enough to read, the count is stated as illustrative on the
    // card, and it is the MEASURED coupling that decides how many of them are
    // lit at any instant.
    const tracersPerReturnPath = 22;
    // The lobe-to-sheet arrival. It is a short path — a lead-in along the
    // traced lobe line plus the collapse onto the sheet, about twelve Earth
    // radii — so fourteen tracers put 1.15 marks per Earth radius on exactly
    // the leg that shows the plasma sheet being fed.
    //
    // What that is worth, counted rather than felt: a return path spreads 22
    // tracers over 12 Re of approach plus a ~50 Re ride, which is 0.36 marks
    // per Earth radius, and the two or three branches of one lobe line share
    // the collapse geometry EXACTLY, so together they already put about 1.1 on
    // it — four or five marks across a 4.2 Re drop. This DOUBLES that. Under
    // the measured thinning at the reference drivers it is about three lit
    // marks across the drop before and six after, and the ratio holds at any
    // drive because the same thinning applies to both. Sean, having seen the
    // shipped version: *"it is hard to see particles feeding the plasma sheet
    // itself ... perhaps it needs to be a bit more stark."* Stark here means
    // more of the same marks in the same treatment, which is the only lever
    // this layer allows itself.
    const tracersPerInflowPath = 14;
    this.guidedTracers = [];
    this.guidedSlotsPerPath = [];
    const mix = solarWindSpeciesMix();
    let tracerIndex = 0;
    this.guidancePathsValue.forEach((path, pathIndex) => {
      const count = path.role === "cusp"
        ? tracersPerCuspPath
        : path.role === "return"
          ? tracersPerReturnPath
          : path.role === "inflow" ? tracersPerInflowPath : tracersPerLobePath;
      this.guidedSlotsPerPath[pathIndex] = count;
      for (let slot = 0; slot < count; slot += 1) {
        this.guidedTracers.push({
          pathIndex,
          phase: (slot + (pathIndex % 3) * 0.29) / count % 1,
          species: speciesFromFilter(tracerIndex, path.speciesFilter, mix),
          slot,
        });
        tracerIndex += 1;
      }
    });
    const positions = new Float32Array(this.guidedTracers.length * 3);
    const alpha = new Float32Array(this.guidedTracers.length);
    const species = new Float32Array(this.guidedTracers.length);
    this.guidedTracers.forEach((tracer, index) => {
      species[index] = SPECIES_ATTRIBUTE_VALUE[tracer.species];
    });
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute("flowAlpha", new THREE.BufferAttribute(alpha, 1));
    geometry.setAttribute("species", new THREE.BufferAttribute(species, 1));
    geometry.userData.kind = "field-guided-solar-wind-tracers";
    geometry.userData.classification =
      "charged particles guided along the layer's own traced field lines — geometry from the drawn field-line model, motion illustrative";
    const returnPaths = this.guidancePathsValue.filter((path) => path.role === "return");
    geometry.userData.guidance = {
      cuspPathCount: this.guidancePathsValue.filter((path) => path.role === "cusp").length,
      lobePathCount: this.guidancePathsValue.filter((path) => path.role === "lobe").length,
      returnPathCount: returnPaths.length,
      // One per extended ride: the last stretch of the same ride, drawn again
      // with its own roster so the arrival at the current sheet is populated.
      inflowPathCount: this.guidancePathsValue.filter((path) => path.role === "inflow").length,
      ringCurrentPathCount: returnPaths.filter((path) => path.branch === "ring-current").length,
      auroraPathCount: returnPaths.filter((path) => path.branch === "aurora").length,
      termination: "cusp paths end at the field line's own footpoint latitude (the cusp band), not at a measured auroral oval",
      // The evidence split, carried on the drawn object itself so it is
      // machine-checkable rather than a claim made only in prose.
      returnLegEvidence: returnPaths.length === 0
        ? null
        : "SCHEMATIC past the neutral line: the Dungey-cycle sequence is settled physics and is drawn as such, but no instrument measures these trajectories. The RATE is measured — Newell et al. (2007) dPhi_MP/dt from the propagated L1 speed, By and Bz — and it sets how many particles are on the path and how fast they run.",
      returnLegContainment: this.tailReturnReportValue,
    };
    this.guidedPointsValue.geometry.dispose();
    this.guidedPointsValue.geometry = geometry;
    this.guidedTrailsValue.geometry.dispose();
    this.guidedTrailsValue.geometry = SolarWindVisual.buildTrailGeometry(this.guidedTracers.length, species);
    this.applyGuidedVisibility();
    if (this.guidedTracers.length > 0) this.updateGuided(this.lastElapsedDisplaySeconds);
  }

  /**
   * Advance the guided particles along their field lines. The full journey —
   * approach, funnel, footpoint (or lobe exit) — cycles in about ten display
   * seconds, breathing faster when the measured wind is faster; the motion is
   * display cadence, exactly like the free shower's, and says so.
   *
   * ## What the MEASURED coupling changes, and what it deliberately does not
   *
   * The tail-return population — and only that population — is thinned and
   * paced by `couplingDriveValue`, the published Newell et al. (2007) coupling
   * function placed on the site's own published band ladder. Turn the IMF
   * northward and the sine term in that function collapses, the roster empties
   * to a tenth, and the Dungey cycle visibly nearly stops. That is the whole
   * reason this was worth building.
   *
   * The cusp and lobe populations are untouched by it. Sean's judgement on the
   * existing coupling was that it is fine, so it keeps exactly the cadence it
   * shipped with; a change there would have been a regression dressed as a
   * feature.
   *
   * A return ride is three to four times the arc of a cusp ride, so its cycle
   * is scaled by its own length rather than left at the cusp figure — a
   * particle covering three times the distance in the same ten seconds would
   * be moving three times faster for no reason a reader could infer. That
   * scaling, and the modest extra urgency at a high coupling, are display
   * cadence, not a measured transit time, and the card says so.
   */
  private updateGuided(elapsedDisplaySeconds: number) {
    const geometry = this.guidedPointsValue.geometry;
    const positions = geometry.getAttribute("position") as THREE.BufferAttribute | undefined;
    const alpha = geometry.getAttribute("flowAlpha") as THREE.BufferAttribute | undefined;
    if (!positions || !alpha) return;
    const cycleSeconds = 10.5 / clamp(this.speedKps / 400, 0.5, 2);
    const approachSpanRe = 12;
    const drive = this.couplingDriveValue;
    // The inflow path starts ON the traced lobe line rather than upstream of
    // an entry point, so it has no approach leg: a straight sunward run into
    // the middle of the tail is not a thing the wind does, and drawing one
    // would put marks where no path is.
    const pathApproachRe = this.guidancePathsValue.map((path) => (path.role === "inflow" ? 0 : approachSpanRe));
    // Per path rather than per tracer: there are tens of paths and hundreds of
    // tracers, and neither quantity changes within a frame.
    const pathCycleSeconds = this.guidancePathsValue.map((path, index) => {
      if (path.role !== "return" && path.role !== "inflow") return cycleSeconds;
      const reference = 30;
      // Scaled by the path's OWN length against the same reference the return
      // rides use, so a tracer on the short inflow path covers ground at the
      // same rate as one on the long return path. The pace is not a second
      // opinion about how fast the plasma moves; it is the same opinion,
      // applied to a shorter path.
      const lengthFactor = ((pathApproachRe[index] ?? approachSpanRe) + path.totalLengthRe)
        / (approachSpanRe + reference);
      return (cycleSeconds * lengthFactor) / (0.8 + 0.6 * (drive ?? 0));
    });
    const pathActiveTracers = this.guidancePathsValue.map((path, index) => (
      // The inflow arrival is thinned by the MEASURED coupling exactly as the
      // return rides are: turn the IMF northward and the feeding of the plasma
      // sheet very nearly stops, which is the lesson the whole layer exists to
      // teach. A leg that stayed populated at a northward IMF would contradict
      // the rest of the picture.
      path.role === "return" || path.role === "inflow"
        ? activeTracerCount(this.guidedSlotsPerPath[index] ?? 0, drive)
        : Number.POSITIVE_INFINITY
    ));
    this.guidedTracers.forEach((tracer, index) => {
      const path = this.guidancePathsValue[tracer.pathIndex];
      if (!path) return;
      if (tracer.slot >= (pathActiveTracers[tracer.pathIndex] ?? 0)) {
        // Thinned out by the measured coupling. Alpha zero rather than a
        // removed vertex: the roster stays the same length, so nothing has to
        // be rebuilt when the drivers move and the trail buffer keeps its
        // stride.
        alpha.setX(index, 0);
        this.writeTrail(
          index,
          ZERO_TRAIL_POINT,
          ZERO_TRAIL_POINT,
          0,
          this.guidedTrailsValue.geometry,
        );
        return;
      }
      const progress = ((tracer.phase + elapsedDisplaySeconds / (pathCycleSeconds[tracer.pathIndex] ?? cycleSeconds)) % 1 + 1) % 1;
      const approach = pathApproachRe[tracer.pathIndex] ?? approachSpanRe;
      const sample = sampleGuidedJourney(path, progress, approach);
      const position = this.positionForGsm(sample.xRe, sample.yRe, sample.zRe);
      positions.setXYZ(index, position.x, position.y, position.z);
      // Fade in on approach, hold on the line, dissolve into the atmosphere
      // at the footpoint the way the field lines themselves do.
      const glyphAlpha = smoothstep(0, 0.06, progress) * (1 - smoothstep(0.93, 1, progress))
        * (sample.onPath ? 1 : 0.75);
      alpha.setX(index, glyphAlpha);
      const behind = sampleGuidedJourney(path, Math.max(0, progress - 0.012), approach);
      this.writeTrail(
        index,
        position,
        this.positionForGsm(behind.xRe, behind.yRe, behind.zRe),
        glyphAlpha,
        this.guidedTrailsValue.geometry,
      );
    });
    positions.needsUpdate = true;
    alpha.needsUpdate = true;
    this.commitTrails(this.guidedTrailsValue.geometry);
  }

  /**
   * Advances compressed display time. The 3-D cloud always advances; the
   * plane tracers additionally sample the model's own local travel time; the
   * guided sub-population advances along its field lines when coupling is on.
   *
   * `elapsedDisplaySeconds` is TOTAL seconds on the environmental-motion
   * clock, never a per-frame delta — that is what the scene passes. Every
   * consumer below must therefore treat it as an absolute time and map it to a
   * phase; none may accumulate it. A consumer that accumulated it advanced by
   * the whole elapsed time on EVERY frame, which put the guided particles a
   * full journey further along each frame within seconds of page load and made
   * the cusp coupling invisible on the live site. `solar-wind-species-coupling.test.ts`
   * holds the contract.
   */
  update(elapsedDisplaySeconds: number) {
    if (!Number.isFinite(elapsedDisplaySeconds)) return;
    this.lastElapsedDisplaySeconds = elapsedDisplaySeconds;
    this.updateFallback(elapsedDisplaySeconds);
    if (this.modelTracers.length > 0) this.updateModel(elapsedDisplaySeconds);
    if (this.guidedPointsValue.visible && this.guidedTracers.length > 0) {
      this.updateGuided(elapsedDisplaySeconds);
    }
  }

  dispose() {
    this.pointsValue.geometry.dispose();
    this.trailsValue.geometry.dispose();
    this.modelPointsValue.geometry.dispose();
    this.modelTrailsValue.geometry.dispose();
    this.guidedPointsValue.geometry.dispose();
    this.guidedTrailsValue.geometry.dispose();
    this.material.dispose();
    this.trailMaterial.dispose();
    this.modelMaterial.dispose();
    this.modelTrailMaterial.dispose();
    this.guidedMaterial.dispose();
    this.guidedTrailMaterial.dispose();
    if (this.obstacleSilhouetteValue) disposeObject3D(this.obstacleSilhouetteValue);
    this.obstacleSilhouetteValue = null;
    this.group.clear();
  }

  private static buildTrailGeometry(count: number, speciesPerTracer?: ArrayLike<number>) {
    const trails = new THREE.BufferGeometry();
    trails.setAttribute("position", new THREE.BufferAttribute(new Float32Array(count * 6), 3));
    trails.setAttribute("flowAlpha", new THREE.BufferAttribute(new Float32Array(count * 2), 1));
    // 1 at the head, 0 at the far end, so a streak fades out behind the tracer
    // rather than ending in a hard stop.
    const fade = new Float32Array(count * 2);
    const species = new Float32Array(count * 2);
    for (let index = 0; index < count; index += 1) {
      fade[index * 2] = 1;
      fade[index * 2 + 1] = 0;
      const value = speciesPerTracer?.[index] ?? 0;
      species[index * 2] = value;
      species[index * 2 + 1] = value;
    }
    trails.setAttribute("trailFade", new THREE.BufferAttribute(fade, 1));
    trails.setAttribute("species", new THREE.BufferAttribute(species, 1));
    trails.userData.kind = "solar-wind-tracer-streamline-streaks";
    trails.userData.encoding = "direction is the tracer's own streamline tangent; length is a fixed display length";
    return trails;
  }

  private replaceGeometry(geometry: THREE.BufferGeometry) {
    this.pointsValue.geometry.dispose();
    this.pointsValue.geometry = geometry;
    const count = geometry.getAttribute("position")?.count ?? 0;
    this.trailsValue.geometry.dispose();
    this.trailsValue.geometry = SolarWindVisual.buildTrailGeometry(
      count,
      geometry.getAttribute("species")?.array as ArrayLike<number> | undefined,
    );
  }

  /** Write one streak, oriented along the streamline and cut to a fixed length. */
  private writeTrail(
    index: number,
    head: THREE.Vector3,
    upstream: THREE.Vector3,
    alpha: number,
    geometry: THREE.BufferGeometry = this.trailsValue.geometry,
  ) {
    const positions = geometry.getAttribute("position") as THREE.BufferAttribute | undefined;
    const alphas = geometry.getAttribute("flowAlpha") as THREE.BufferAttribute | undefined;
    if (!positions || !alphas) return;
    const deltaX = upstream.x - head.x;
    const deltaY = upstream.y - head.y;
    const deltaZ = upstream.z - head.z;
    const length = Math.hypot(deltaX, deltaY, deltaZ);
    const scale = length > 1e-9 ? this.trailLength / length : 0;
    positions.setXYZ(index * 2, head.x, head.y, head.z);
    positions.setXYZ(
      index * 2 + 1,
      head.x + deltaX * scale,
      head.y + deltaY * scale,
      head.z + deltaZ * scale,
    );
    alphas.setX(index * 2, alpha);
    alphas.setX(index * 2 + 1, alpha);
  }

  private commitTrails(geometry: THREE.BufferGeometry = this.trailsValue.geometry) {
    const positions = geometry.getAttribute("position") as THREE.BufferAttribute | undefined;
    const alphas = geometry.getAttribute("flowAlpha") as THREE.BufferAttribute | undefined;
    if (positions) positions.needsUpdate = true;
    if (alphas) alphas.needsUpdate = true;
  }

  /**
   * The published plane tracers. They ADD to the 3-D cloud rather than
   * replacing it: they are the better evidence exactly on the two published
   * cuts, and the cloud is what keeps the layer three-dimensional everywhere
   * else. An empty tracer list clears them and the mode returns to the
   * labelled illustrative fallback alone.
   */
  private buildModelTracers() {
    const positions = new Float32Array(this.modelTracers.length * 3);
    const alpha = new Float32Array(this.modelTracers.length).fill(1);
    const sourceSpeed = new Float32Array(this.modelTracers.length);
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute("flowAlpha", new THREE.BufferAttribute(alpha, 1));
    geometry.setAttribute("modelSpeedKps", new THREE.BufferAttribute(sourceSpeed, 1));
    geometry.userData.kind = "bats-r-us-projected-bulk-flow";
    this.modelPointsValue.geometry.dispose();
    this.modelPointsValue.geometry = geometry;
    this.modelTrailsValue.geometry.dispose();
    this.modelTrailsValue.geometry = SolarWindVisual.buildTrailGeometry(this.modelTracers.length);
    this.mode = this.modelTracers.length > 0 ? "model-projected" : "illustrative-upstream";
    this.group.userData.visualMode = this.mode;
    this.group.userData.labeling = this.modelTracers.length > 0
      ? {
        classification: "model-projected plane tracers inside an illustrative 3-D deflection cloud",
        not: "observed individual trajectories",
        cadenceDriver: "BATS-R-US local bulk-flow speed on the two published cuts",
        populationDriver: "measured upstream proton density",
        offPlane: "the surrounding cloud is idealised no-penetration flow around the drawn boundary — illustrative",
        presentation: "the plane tracers draw only while the NOAA MHD cross-section option is on; the layer's default face is the species shower",
      }
      : this.group.userData.labeling;
    this.applyModelTracerVisibility();
    if (this.modelTracers.length > 0) this.updateModel(0);
  }

  private buildFallback() {
    const geometry = createIllustrativeUpstreamFlowGeometry({
      earthRadiusRe: this.options.earthRadiusRe,
      magnetopauseStandoffRe: this.magnetopauseStandoffRe,
      magnetopauseGapRe: this.options.magnetopauseGapRe,
      boundaryRadiusForDirection: this.boundaryRadiusForDirection ?? undefined,
      upstreamStartRe: this.options.upstreamStartRe,
      downstreamEndRe: this.options.downstreamEndRe,
      transverseExtentRe: this.options.transverseExtentRe,
      flowTubeCount: this.options.flowTubeCount,
      streamCount: this.options.streamCount,
      samplesPerStream: this.options.samplesPerStream,
      particleCount: this.options.particleCount,
      seed: this.options.seed,
      positionForGsm: this.positionForGsm,
    });
    this.replaceGeometry(geometry);
    this.rebuildObstacleSilhouette(geometry.userData.domain as IllustrativeUpstreamDomain);
    // The cloud is always illustrative; the group-level mode says whether the
    // published plane tracers are riding inside it. Its labeling is only the
    // group's when no model tracers are present.
    if (this.modelTracers.length === 0) {
      this.mode = "illustrative-upstream";
      this.group.userData.visualMode = this.mode;
      this.group.userData.labeling = {
        classification: "physics-based teaching tracers",
        not: "observed individual trajectories",
        cadenceDriver: "measured upstream bulk speed",
        populationDriver: "measured upstream proton density",
        speciesColour: geometry.userData.speciesAssignment,
        approximation: "idealized no-penetration potential flow—not an MHD solution",
        obstacle: geometry.userData.obstacle,
      };
    }
    // A rebuild lands on whatever frame is on screen, so the face is re-cut
    // before the first position is written rather than after.
    this.refaceUpstream();
    this.updateFallback(0);
    this.applyDrawRange();
  }

  /**
   * The drawn radius of the frame's far corner, handed in by the scene every
   * frame. This is what makes the upstream face the size of the VIEW rather
   * than a fixed number of Earth radii, which is the whole of Sean's design:
   * *"they originate from the entire lefthand side of the page... If you zoom
   * out more particles come in from the top and bottom."*
   *
   * Quantised, so a dolly re-cuts the face a handful of times instead of once
   * per frame, and a no-op when the frame has not moved enough to matter.
   */
  setViewFaceRadius(cornerSceneRadius: number) {
    if (!Number.isFinite(cornerSceneRadius) || cornerSceneRadius <= 0) return;
    const requested = cornerSceneRadius * VIEW_FACE_MARGIN;
    const step = Math.log(VIEW_FACE_QUANTISATION);
    const quantised = Math.exp(Math.round(Math.log(requested) / step) * step);
    if (this.viewFaceDrawnRadius !== null
      && Math.abs(quantised - this.viewFaceDrawnRadius) < 1e-6) return;
    this.viewFaceDrawnRadius = quantised;
    this.refaceUpstream();
    // With environmental motion off nothing else will run this frame, so the
    // re-cut has to carry its own redraw or the wind would sit at its old
    // impact parameters until the visitor switched motion back on.
    this.updateFallback(this.lastElapsedDisplaySeconds);
  }

  /** The face as currently cut, in Rₑ and in drawn units, for a test to read. */
  get upstreamFace() {
    return this.pointsValue.geometry.userData.upstreamSampling as
      ReturnType<typeof describeUpstreamFace> | undefined;
  }

  /**
   * Re-cut the upstream face to the current frame.
   *
   * Every tracer keeps its FACE FRACTION, so this moves particles across the
   * face without touching how many there are, which species each one is, or
   * where it is in its own ride. It is a rewrite of two attributes and a
   * binary search per tracer — no flow is solved here.
   */
  private refaceUpstream() {
    const geometry = this.pointsValue.geometry;
    const faceMap = geometry.userData.faceMap as UpstreamFaceMap | undefined;
    const fraction = geometry.getAttribute("faceFraction") as THREE.BufferAttribute | undefined;
    const azimuth = geometry.getAttribute("faceAzimuth") as THREE.BufferAttribute | undefined;
    const impactYRe = geometry.getAttribute("impactYRe") as THREE.BufferAttribute | undefined;
    const impactZRe = geometry.getAttribute("impactZRe") as THREE.BufferAttribute | undefined;
    if (!faceMap || !fraction || !azimuth || !impactYRe || !impactZRe) return;
    const fallbackEdge = drawnTransverseForImpact(
      faceMap,
      Math.min(
        MAXIMUM_TRANSVERSE_EXTENT_RE,
        this.options.transverseExtentRe ?? DEFAULT_TRANSVERSE_EXTENT_RE,
      ),
    );
    const requested = this.viewFaceDrawnRadius;
    const reachable = drawnTransverseForImpact(faceMap, MAXIMUM_TRANSVERSE_EXTENT_RE);
    const edge = Math.min(reachable, requested ?? fallbackEdge);
    let widest = 0;
    for (let index = 0; index < fraction.count; index += 1) {
      const impact = impactForFaceFraction(faceMap, fraction.getX(index), edge);
      const angle = azimuth.getX(index);
      impactYRe.setX(index, impact * Math.cos(angle));
      impactZRe.setX(index, impact * Math.sin(angle));
      if (impact > widest) widest = impact;
    }
    impactYRe.needsUpdate = true;
    impactZRe.needsUpdate = true;
    this.applyFaceFadeUniforms(faceMap, edge);
    geometry.userData.transverseExtentRe = widest;
    geometry.userData.faceFade = {
      what: "OPACITY ONLY. The drawn field thins past the range over which the "
        + "magnetosphere deflects anything, and the outermost eighth of the face "
        + "falls to nothing so the wind has no edge. Counts, positions, paths and "
        + "species are untouched.",
      thinStartRe: SOLAR_WIND_FACE_FADE.thinStartRe,
      thinEndRe: SOLAR_WIND_FACE_FADE.thinEndRe,
      thinFloor: SOLAR_WIND_FACE_FADE.thinFloor,
      edgeTaper: SOLAR_WIND_FACE_FADE.edgeTaper,
      drawnThinStart: Number(drawnTransverseForImpact(faceMap, SOLAR_WIND_FACE_FADE.thinStartRe).toFixed(2)),
      drawnThinEnd: Number(drawnTransverseForImpact(faceMap, SOLAR_WIND_FACE_FADE.thinEndRe).toFixed(2)),
      drawnEdge: Number(edge.toFixed(2)),
    };
    geometry.userData.upstreamSampling = describeUpstreamFace(
      widest,
      edge,
      (geometry.userData.upstreamSampling as { flowTubeCount?: number } | undefined)?.flowTubeCount ?? 0,
      requested,
    );
  }

  /**
   * Hand the shaders the three drawn radii the face fade needs, converted from
   * Rₑ through the same ruler the face itself is cut with — so the fade moves
   * with the zoom instead of being a fixed number of pixels. See
   * `SOLAR_WIND_FACE_FADE`.
   */
  private applyFaceFadeUniforms(faceMap: UpstreamFaceMap, edge: number) {
    const thinStart = drawnTransverseForImpact(faceMap, SOLAR_WIND_FACE_FADE.thinStartRe);
    const thinEnd = Math.max(
      thinStart + 1e-3,
      drawnTransverseForImpact(faceMap, SOLAR_WIND_FACE_FADE.thinEndRe),
    );
    const edgeEnd = Math.max(1e-3, edge);
    const edgeStart = edgeEnd * (1 - SOLAR_WIND_FACE_FADE.edgeTaper);
    for (const material of [this.material, this.trailMaterial, this.guidedMaterial, this.guidedTrailMaterial]) {
      const uniforms = material.uniforms;
      if (!uniforms.faceEdgeEnd) continue;
      uniforms.faceThinStart!.value = thinStart;
      uniforms.faceThinEnd!.value = thinEnd;
      uniforms.faceEdgeStart!.value = edgeStart;
      uniforms.faceEdgeEnd!.value = edgeEnd;
    }
  }

  /** The drawn radii the face fade is currently using, for tests and the card. */
  get faceFadeDrawnRadii() {
    const uniforms = this.material.uniforms;
    return {
      thinStart: uniforms.faceThinStart?.value as number ?? 0,
      thinEnd: uniforms.faceThinEnd?.value as number ?? 0,
      edgeStart: uniforms.faceEdgeStart?.value as number ?? 0,
      edgeEnd: uniforms.faceEdgeEnd?.value as number ?? 0,
    };
  }

  private applyDrawRange() {
    const fraction = this.encoding.available ? this.encoding.activeFraction : 0;
    const count = this.pointsValue.geometry.getAttribute("position")?.count ?? 0;
    const drawn = this.encoding.available ? Math.max(1, Math.round(count * fraction)) : 0;
    this.pointsValue.geometry.setDrawRange(0, drawn);
    this.trailsValue.geometry.setDrawRange(0, drawn * 2);
    // The plane tracers breathe with the same measured density.
    const modelCount = this.modelPointsValue.geometry.getAttribute("position")?.count ?? 0;
    const modelDrawn = this.encoding.available && modelCount > 0
      ? Math.max(1, Math.round(modelCount * fraction))
      : 0;
    this.modelPointsValue.geometry.setDrawRange(0, modelDrawn);
    this.modelTrailsValue.geometry.setDrawRange(0, modelDrawn * 2);
  }

  private updateModel(elapsedDisplaySeconds: number) {
    const geometry = this.modelPointsValue.geometry;
    const positions = geometry.getAttribute("position") as THREE.BufferAttribute | undefined;
    const speeds = geometry.getAttribute("modelSpeedKps") as THREE.BufferAttribute | undefined;
    if (!positions || !speeds) return;
    const modelSeconds = elapsedDisplaySeconds * Math.max(
      0,
      this.options.modelSecondsPerDisplaySecond ?? 45,
    );
    this.modelTracers.forEach((tracer, index) => {
      const pathTime = modelSeconds + tracer.phase * tracer.path.durationModelSeconds;
      const sample = sampleProjectedFlowAdvectionPath(tracer.path, pathTime);
      if (!sample) return;
      const position = this.positionForPlane(sample.xRe, sample.crossRe, tracer.plane);
      positions.setXYZ(index, position.x, position.y, position.z);
      speeds.setX(index, sample.speedKps);
      // The streak's far end is a genuine earlier point on the same traced
      // path, so its direction is the model's own local flow direction.
      const behind = sampleProjectedFlowAdvectionPath(
        tracer.path,
        pathTime - Math.max(1, tracer.path.durationModelSeconds * 0.02),
      );
      if (behind) {
        this.writeTrail(
          index,
          position,
          this.positionForPlane(behind.xRe, behind.crossRe, tracer.plane),
          1,
          this.modelTrailsValue.geometry,
        );
      }
    });
    positions.needsUpdate = true;
    speeds.needsUpdate = true;
    this.commitTrails(this.modelTrailsValue.geometry);
  }

  private updateFallback(elapsedDisplaySeconds: number) {
    const geometry = this.pointsValue.geometry;
    const positions = geometry.getAttribute("position") as THREE.BufferAttribute | undefined;
    const alpha = geometry.getAttribute("flowAlpha") as THREE.BufferAttribute | undefined;
    const phase = geometry.getAttribute("flowPhase") as THREE.BufferAttribute | undefined;
    const yRe = geometry.getAttribute("gsmYRe") as THREE.BufferAttribute | undefined;
    const zRe = geometry.getAttribute("gsmZRe") as THREE.BufferAttribute | undefined;
    const impactYRe = geometry.getAttribute("impactYRe") as THREE.BufferAttribute | undefined;
    const impactZRe = geometry.getAttribute("impactZRe") as THREE.BufferAttribute | undefined;
    const gsmXRe = geometry.getAttribute("gsmXRe") as THREE.BufferAttribute | undefined;
    const domain = geometry.userData.domain as IllustrativeUpstreamDomain | undefined;
    if (!positions || !alpha || !phase || !yRe || !zRe || !impactYRe || !impactZRe || !gsmXRe || !domain) return;
    const spanRe = domain.upstreamStartRe - domain.downstreamEndRe;
    const transitTables = geometry.userData.transitTables as
      Array<{ xRe: Float32Array; fraction: Float32Array }> | undefined;
    // The band grid is FIXED (see TRANSIT_BAND_MAX_RE); the face is not. An
    // impact parameter wider than the grid clamps to its outermost band, which
    // is the free-stream transit to within 4.5%.
    const transitBandMaxRe = (geometry.userData.transitBandMaxRe as number | undefined)
      ?? TRANSIT_BAND_MAX_RE;
    // This is explicitly display motion. The observed speed changes cadence,
    // but does not turn fallback glyphs into claimed proton trajectories.
    //
    // Normalised against the span the constant was tuned at, so lengthening the
    // domain down-tail does not silently speed every tracer up: one transit is
    // one pass of `progress` from 0 to 1 whatever the domain is, so without this
    // a 62 Re domain would cross the dayside in half the time a 32 Re one did,
    // for the same measured wind.
    const cyclesPerSecond = (clamp(this.speedKps / 400, 0.35, 2.4) / 7)
      * (CADENCE_REFERENCE_SPAN_RE / Math.max(1e-3, spanRe));
    // How far back along its own streamline the streak's far end is taken. A
    // fixed PHYSICAL length, for the same reason: the streak reports the local
    // speed, and it cannot do that if its own scale moves with the domain.
    const upstreamStepRe = CADENCE_REFERENCE_SPAN_RE * 0.012;
    for (let index = 0; index < positions.count; index += 1) {
      const progress = ((phase.getX(index) + elapsedDisplaySeconds * cyclesPerSecond) % 1 + 1) % 1;
      const impactY = impactYRe.getX(index);
      const impactZ = impactZRe.getX(index);
      // Progress is a fraction of the TRANSIT, not of the distance. The table
      // is what carries the physics: equal steps of progress cover less ground
      // where the flow is slow (piling tracers up ahead of the nose) and more
      // where it has accelerated around the flanks. Without a table — an older
      // geometry, or a bundle rebuilt before this shipped — it falls back to
      // the uniform march, which is wrong but is not a crash.
      const table = transitTables?.[transitBandIndex(Math.hypot(impactY, impactZ), transitBandMaxRe, transitTables.length)];
      const xRe = table
        ? streamlineXAtFraction(table, progress)
        : domain.upstreamStartRe - progress * spanRe;
      const flowPoint = teachingFlowPointAroundObstacle(xRe, impactY, impactZ, domain.obstacle);
      const position = this.positionForGsm(flowPoint.xRe, flowPoint.yRe, flowPoint.zRe);
      positions.setXYZ(index, position.x, position.y, position.z);
      gsmXRe.setX(index, flowPoint.xRe);
      yRe.setX(index, flowPoint.yRe);
      zRe.setX(index, flowPoint.zRe);
      const glyphAlpha = smoothstep(0, 0.08, progress) * (1 - smoothstep(0.88, 1, progress));
      alpha.setX(index, glyphAlpha);
      // The far end of the streak is where this same tracer was a moment
      // earlier on this same streamline. Nothing about it is drawn freehand:
      // it goes through the identical solve at a slightly earlier TRANSIT
      // TIME, which is why the streak now shortens where the flow slows and
      // stretches where it accelerates — the streak length reports the local
      // speed instead of being the same length everywhere.
      const behindX = table
        ? streamlineXAtFraction(table, progress - upstreamStepRe / spanRe)
        : Math.min(domain.upstreamStartRe, xRe + upstreamStepRe);
      const behind = teachingFlowPointAroundObstacle(
        Math.min(domain.upstreamStartRe, behindX),
        impactY,
        impactZ,
        domain.obstacle,
      );
      this.writeTrail(
        index,
        position,
        this.positionForGsm(behind.xRe, behind.yRe, behind.zRe),
        glyphAlpha,
      );
    }
    positions.needsUpdate = true;
    gsmXRe.needsUpdate = true;
    yRe.needsUpdate = true;
    zRe.needsUpdate = true;
    alpha.needsUpdate = true;
    this.commitTrails();
  }
}

export function createSolarWindVisual(options: SolarWindVisualOptions = {}) {
  return new SolarWindVisual(options);
}

/**
 * Builds only the sun-facing half of a thin shell just outside the visible
 * globe: the one true spatial structure a uniform scalar flux has to show.
 *
 * `exposureWeight` is the incidence cosine, 1 at the subsolar point and 0 at
 * the terminator — a smooth read of "how directly this point faces the Sun,"
 * not a claim about how much of the flux some layer of atmosphere absorbs.
 * That claim belongs to the D-region model this layer points at, not to this
 * geometry.
 */
export function createDaysideExposureGeometry(
  radius: number,
  polarSegments = 64,
  azimuthSegments = 128,
) {
  const safeRadius = Math.max(0.001, radius);
  const polarCount = Math.max(2, Math.floor(polarSegments));
  const azimuthCount = Math.max(3, Math.floor(azimuthSegments));
  const positions = new Float32Array((polarCount + 1) * (azimuthCount + 1) * 3);
  const exposureWeight = new Float32Array((polarCount + 1) * (azimuthCount + 1));
  for (let polarIndex = 0; polarIndex <= polarCount; polarIndex += 1) {
    const theta = (polarIndex / polarCount) * Math.PI / 2;
    const x = polarIndex === polarCount ? 0 : safeRadius * Math.cos(theta);
    const crossRadius = safeRadius * Math.sin(theta);
    for (let azimuthIndex = 0; azimuthIndex <= azimuthCount; azimuthIndex += 1) {
      const azimuth = (azimuthIndex / azimuthCount) * Math.PI * 2;
      const index = polarIndex * (azimuthCount + 1) + azimuthIndex;
      positions[index * 3] = x;
      positions[index * 3 + 1] = crossRadius * Math.cos(azimuth);
      positions[index * 3 + 2] = crossRadius * Math.sin(azimuth);
      exposureWeight[index] = Math.cos(theta);
    }
  }
  const indices: number[] = [];
  for (let polarIndex = 0; polarIndex < polarCount; polarIndex += 1) {
    for (let azimuthIndex = 0; azimuthIndex < azimuthCount; azimuthIndex += 1) {
      const a = polarIndex * (azimuthCount + 1) + azimuthIndex;
      const b = a + 1;
      const c = a + azimuthCount + 2;
      const d = a + azimuthCount + 1;
      indices.push(a, d, c, a, c, b);
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("exposureWeight", new THREE.BufferAttribute(exposureWeight, 1));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  geometry.userData.kind = "dayside-exposed-hemisphere";
  return geometry;
}

/**
 * The exposure shell's appearance.
 *
 * Three separable terms, so each can be read off the picture:
 *
 * - `dayside` is cos(solar zenith angle), unmodified. Brightest where the Sun
 *   is overhead, zero at the terminator, absent behind it.
 * - `limb` brightens where the shell is seen edge-on. A shell of finite
 *   thickness genuinely presents a longer optical path at grazing incidence;
 *   this is the same cue an atmosphere gets, and it is what makes the tint
 *   read as a shell standing off the surface rather than as paint on it.
 * - `terminator` is a narrow rim right at cos = 0. The shadow edge for a
 *   photon is a real, sharp line — nothing deflects or scatters X-rays into
 *   the night side — so it is drawn as a line rather than left as a fade.
 */
function createExposureMaterial() {
  return new THREE.ShaderMaterial({
    uniforms: {
      color: { value: new THREE.Color(0x75e5f7) },
      terminatorColor: { value: new THREE.Color(0xffffff) },
      opacity: { value: 0 },
      terminatorOpacity: { value: 0 },
    },
    transparent: true,
    side: THREE.DoubleSide,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    vertexShader: `
      attribute float exposureWeight;
      varying float incidentWeight;
      varying vec3 viewNormal;
      varying vec3 viewDirection;
      void main() {
        incidentWeight = exposureWeight;
        viewNormal = normalize(normalMatrix * normal);
        vec4 viewPosition = modelViewMatrix * vec4(position, 1.0);
        viewDirection = normalize(-viewPosition.xyz);
        gl_Position = projectionMatrix * viewPosition;
      }
    `,
    fragmentShader: `
      uniform vec3 color;
      uniform vec3 terminatorColor;
      uniform float opacity;
      uniform float terminatorOpacity;
      varying float incidentWeight;
      varying vec3 viewNormal;
      varying vec3 viewDirection;
      void main() {
        float dayside = clamp(incidentWeight, 0.0, 1.0);
        float grazing = 1.0 - abs(dot(normalize(viewNormal), normalize(viewDirection)));
        float limb = 0.55 + 0.45 * pow(grazing, 2.0);
        float terminator = exp(-pow(dayside / 0.075, 2.0));
        float tint = opacity * dayside * limb;
        float edge = terminatorOpacity * terminator;
        float alpha = clamp(tint + edge, 0.0, 1.0);
        if (alpha < 0.002) discard;
        vec3 tone = (color * tint + terminatorColor * edge) / max(alpha, 1e-4);
        gl_FragColor = vec4(tone, alpha);
      }
    `,
  });
}

/**
 * ## The inbound beam — one ray of it
 *
 * A ray is fixed by where it is absorbed. Everything else follows, because
 * the beam is parallel: the transverse position it is absorbed at is the
 * transverse position it had the whole way in.
 */
export interface XrayPhotonRay {
  /** Absorption point on the dayside of the drawn upper-atmosphere shell, scene units. */
  absorption: { x: number; y: number; z: number };
  /** Where the shower is in this ray's cycle at t = 0, so arrivals are continuous. */
  phase: number;
  /** cos(solar zenith angle) at the absorption point — the same cos the tint paints. */
  incidenceCosine: number;
}

export interface XrayPhotonBeamOptions {
  /** Radius of the shell the rays end on: the one the exposure tint paints. */
  atmosphereRadius: number;
  rayCount?: number;
  seed?: number;
}

/**
 * ## Why the rays are laid out in the drawn scene rather than mapped into it
 *
 * A photon travels in a straight line. Straightness is not a decoration here;
 * it is the entire lesson, and the reason Sean asked for the animation at all
 * — "users would see that they don't deflect like the solar wind and IMF".
 *
 * The scene's radial ruler (`src/radial-ruler.ts`) compresses radius, hard,
 * below geostationary orbit. Push a physically straight sunward ray through
 * that map and the drawn path is a curve: measured on this ruler, a ray
 * absorbed at 60° solar zenith angle leaves its own chord by 44.6 scene units
 * — 45% of the drawn Earth's radius — worst exactly at geostationary orbit,
 * swinging outward as it reaches Earth. A bend, in the place the reader is
 * watching for a bend, that is a pure artifact of the display scale. Drawing
 * the arrival of unbent light as a curve toward the planet would teach the
 * opposite of the truth.
 *
 * So the beam is authored where the reader judges it: parallel to the drawn
 * Sun–Earth axis, in the same scene units the exposure shell already uses,
 * with each ray's transverse offset constant from entry to absorption. The
 * one number taken from the shared radial mapping is how far sunward a ray
 * enters, so the beam's reach still follows the scene's distance scale. This
 * is the layer's declared display choice and the card says so; the site's
 * standing rule is that drawn radius is never quantitative anyway.
 *
 * The absorption points are sampled uniformly over the projected disc, which
 * is what a parallel beam of uniform flux does: arrivals per unit of surface
 * then fall off as cos(solar zenith angle) on their own, the same cos the
 * tint is painted with and the same cos that sets where Chapman ionization
 * peaks. Nothing weights them by hand.
 */
export function buildXrayPhotonRays(options: XrayPhotonBeamOptions): XrayPhotonRay[] {
  const radius = Math.max(0.001, options.atmosphereRadius);
  // Sized against what is in frame, not against the buffer. A ray is drawn
  // along its whole crossing, but the default camera holds only the last fifth
  // of it, so a buffer that looks generous in the numbers reads as a handful
  // of streaks in the corner. Measured at the default camera: 800 rays put
  // about 16 in frame at A class and about 160 at X.
  const count = Math.max(1, Math.floor(options.rayCount ?? 800));
  const random = seededRandom(options.seed ?? 0x0f10707a);
  const rays: XrayPhotonRay[] = [];
  for (let index = 0; index < count; index += 1) {
    // Uniform in the disc: impact parameter = R * sqrt(u).
    const impact = radius * Math.sqrt(random());
    const azimuth = random() * Math.PI * 2;
    // The dayside root, always. x is non-negative by construction, so no ray
    // can terminate on, or cross into, the night side.
    const x = Math.sqrt(Math.max(0, radius * radius - impact * impact));
    rays.push({
      absorption: { x, y: impact * Math.cos(azimuth), z: impact * Math.sin(azimuth) },
      // Golden-ratio phases: any drawn prefix of the buffer is still spread
      // evenly through the cycle, so lowering the flux thins the shower
      // instead of clumping it.
      phase: ((index + 0.5) * SPECIES_GOLDEN_FRACTION) % 1,
      incidenceCosine: x / radius,
    });
  }
  return rays;
}

/**
 * Where a ray's head is at `progress01` of its crossing: a linear walk in the
 * drawn scene from `startX` down to the absorption point, at constant
 * transverse offset. Exported because the straightness guarantee is worth
 * testing against the same function the renderer calls, not a re-derivation.
 */
export function xrayPhotonRayHead(ray: XrayPhotonRay, startX: number, progress01: number) {
  const progress = clamp(progress01, 0, 1);
  return {
    x: startX + (ray.absorption.x - startX) * progress,
    y: ray.absorption.y,
    z: ray.absorption.z,
  };
}

/**
 * The streak material: one pale colour for the whole beam, the palest member
 * of the layer's own A-to-X ramp. Same trail idiom as the wind's streaks — a
 * per-vertex fade from head to tail, additive, no depth write — so the two
 * populations are drawn by the same machinery and differ only where they
 * should: colour, thinness, and speed.
 */
function createPhotonStreakMaterial() {
  return new THREE.ShaderMaterial({
    uniforms: {
      color: { value: new THREE.Color(XRAY_PHOTON_STREAK_COLOR_HEX) },
      opacity: { value: 0 },
    },
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    vertexShader: `
      attribute float flowAlpha;
      attribute float trailFade;
      varying float segmentAlpha;
      void main() {
        segmentAlpha = flowAlpha * trailFade;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform vec3 color;
      uniform float opacity;
      varying float segmentAlpha;
      void main() {
        gl_FragColor = vec4(color, opacity * segmentAlpha);
      }
    `,
  });
}

/**
 * The X-ray layer, built around what is actually true of the quantity: one
 * scalar, uniform across near-Earth space, with exactly one piece of real
 * spatial structure at Earth — which hemisphere the Sun is currently over —
 * and one true fact about how it gets here, which is that it is not deflected.
 *
 * An early release drew a field of photon glyphs scattered through the whole
 * scene, scaled by the flux. Sean's read was exact: they were massless and
 * chargeless, nothing on screen acted on them, and neither their spread nor
 * their motion carried any quantity, so they were deleted along with the
 * pretence that a scalar has a spatial field. What is drawn now is a
 * different object and makes a different claim: a parallel beam that arrives,
 * crosses every boundary the charged wind is turned by without so much as
 * bending, and stops where the energy stops — absorbed on the dayside, at the
 * shell the tint paints, which is where D-RAP picks up the consequence. Its
 * population and brightness are the measured flux; its cadence is display
 * cadence and is deliberately independent of the data, because the speed of
 * light does not vary with the weather.
 */
export class XrayIrradianceVisual {
  readonly group = new THREE.Group();
  readonly glowMaterial: THREE.ShaderMaterial;
  readonly glow: THREE.Mesh<THREE.BufferGeometry, THREE.ShaderMaterial>;
  readonly streakMaterial: THREE.ShaderMaterial;
  /** The inbound beam. Straight, parallel, dayside-terminating; never bent by anything. */
  readonly streaks: THREE.LineSegments<THREE.BufferGeometry, THREE.ShaderMaterial>;
  private readonly rays: XrayPhotonRay[];
  private readonly atmosphereRadius: number;
  private readonly earthRadius: number;
  private readonly positionForGsm: GsmPositionMapper | null;
  private readonly upstreamStartRe: number;
  private readonly streakLength: number;
  private readonly traversalSeconds: number;
  private encoding = xrayIrradianceEncoding(null);

  constructor(options: XrayIrradianceVisualOptions = {}) {
    const earthRadius = Math.max(0.001, options.earthRadius ?? 100);
    const atmosphereRadius = Math.max(earthRadius + 0.001, options.upperAtmosphereRadius ?? earthRadius * 1.035);
    this.earthRadius = earthRadius;
    this.atmosphereRadius = atmosphereRadius;
    this.positionForGsm = options.positionForGsm ?? null;
    // Beyond the bow shock nose (~13 Re) and beyond where the wind's own
    // tracers enter (32 Re), so a ray is already crossing when the reader
    // first meets it and the two populations enter the same picture together.
    this.upstreamStartRe = Math.max(1.5, options.photonUpstreamStartRe ?? 34);
    // A fixed display length, as the wind's streak is. It is set longer than
    // the wind's so the beam reads as faster even in a still frame — a streak
    // is the only speed cue a screenshot has.
    this.streakLength = Math.max(0, options.photonStreakLength ?? 46);
    this.traversalSeconds = Math.max(0.05, options.photonTraversalSeconds ?? 0.75);
    this.glowMaterial = createExposureMaterial();
    this.glow = new THREE.Mesh(
      createDaysideExposureGeometry(
        atmosphereRadius,
        options.glowPolarSegments,
        options.glowAzimuthSegments,
      ),
      this.glowMaterial,
    );
    this.glow.renderOrder = 4;
    this.rays = buildXrayPhotonRays({
      atmosphereRadius,
      rayCount: options.photonRayCount,
      seed: options.seed,
    });
    this.streakMaterial = createPhotonStreakMaterial();
    this.streaks = new THREE.LineSegments(
      XrayIrradianceVisual.buildStreakGeometry(this.rays.length),
      this.streakMaterial,
    );
    this.streaks.frustumCulled = false;
    this.streaks.name = "xray-inbound-photon-streaks";
    this.streaks.renderOrder = 3;
    this.group.add(this.glow, this.streaks);
    this.group.userData.method = SOLAR_INPUT_VISUAL_METHOD.xray;
    this.group.userData.labeling = {
      classification: "day/night exposure tint — geometry, not a photon track",
      not: "an attenuation or absorption model; nothing attenuates this flux before the D-region",
      intensityDriver: "GOES XRS 0.1-0.8 nm irradiance",
      spatialWeighting:
        "cos(solar zenith angle) exactly — the geometric factor for flux crossing a horizontal surface, "
        + "and the same cos that sets where the D-region ionization peaks. The flux itself is uniform; only the incidence varies.",
      terminator:
        "the shadow edge, drawn as a line because for photons it is one: X-rays carry no charge, "
        + "so nothing bends them around the planet and nothing scatters them into the night side",
      inboundRays:
        "a parallel beam, straight from entry to absorption: no boundary, field or driver touches it. "
        + "Population and brightness are the measured flux; the crossing cadence is display cadence and "
        + "does not vary with the data. Every ray ends on the dayside of the drawn upper-atmosphere shell.",
    };
    this.setFlux(null);
    // Lay the beam out at t = 0 immediately. A visitor who has "Environmental
    // motion" switched off never calls update(), and an unwritten position
    // buffer would collapse every streak onto the origin.
    this.update(0);
  }

  /** The inbound beam's rays, as authored: absorption point, phase, incidence. */
  get photonRays(): readonly XrayPhotonRay[] {
    return this.rays;
  }

  /** How many rays the measured flux is currently drawing. Zero with no data. */
  get drawnRayCount() {
    return Math.floor((this.streaks.geometry.drawRange.count ?? 0) / 2);
  }

  /**
   * Where a ray enters the drawn scene, in scene units along the Sun line.
   *
   * Read through the scene's shared radial mapping every frame rather than
   * cached, so a change to the scene's distance scale moves the beam's entry
   * with everything else. Without a mapper (unit tests, and only there) the
   * upstream distance falls back to a plain multiple of the drawn Earth.
   */
  private sunwardEntryX() {
    if (!this.positionForGsm) return this.earthRadius * this.upstreamStartRe;
    const mapped = this.positionForGsm(this.upstreamStartRe, 0, 0);
    const distance = Math.hypot(mapped.x, mapped.y, mapped.z);
    return Number.isFinite(distance) && distance > this.atmosphereRadius
      ? distance
      : this.earthRadius * this.upstreamStartRe;
  }

  get currentEncoding() {
    return this.encoding;
  }

  /**
   * Nothing here is a screen-space glyph — the beam is line segments in scene
   * space and the tint is geometry — so there is nothing to scale by device
   * pixel ratio. Kept as a no-op so the shared renderer needs no special case.
   */
  setPixelRatio(_pixelRatio: number) {}

  /** Applies the current irradiance immediately; no synthetic decay is kept. */
  setFlux(fluxWm2: number | null) {
    this.encoding = xrayIrradianceEncoding(fluxWm2);
    this.glowMaterial.uniforms.opacity!.value = this.encoding.exposureOpacity;
    this.glowMaterial.uniforms.terminatorOpacity!.value = this.encoding.terminatorOpacity;
    const tone = xrayFluxColor(this.encoding.normalizedFlux);
    this.glowMaterial.uniforms.color!.value.copy(tone);
    // The rim takes the flux colour lightened toward white, so it stays a
    // legible edge at every class without ever claiming a different quantity.
    this.glowMaterial.uniforms.terminatorColor!.value.copy(tone).lerp(new THREE.Color(0xffffff), 0.55);
    this.glow.visible = this.encoding.available;
    // The beam is the same measurement in a different currency: how many rays
    // arrive, and how brightly. With no measurement there is no beam — no
    // placeholder shower is ever drawn from an invented flux.
    this.streakMaterial.uniforms.opacity!.value = this.encoding.photonRayOpacity;
    // 0.32 toward white, not 0.72.
    //
    // Sean, on the deployed build: "When I put on the x-ray flux overlay, the
    // legend spans from blue to red. But i don't see those colors anywhere on
    // the site. I see white 'particles' showering over earth."
    //
    // He was reading the picture correctly. At the B9.6 the Sun was actually
    // putting out, the flux sits near the bottom of the A-to-X ramp, so the
    // tone is the deep navy-to-cyan end; bleaching that 72% toward white left
    // rays that were, to the eye, simply white. The legend then advertised a
    // four-colour scale that nothing on screen was using — the layer's own
    // colour key describing a quantity the layer was not showing.
    //
    // A third of the way to white still lifts the darkest end of the ramp off
    // a black background, which is what the whitening was for, while leaving
    // enough saturation that a reader can tell a quiet Sun from a flaring one
    // by the colour of the beam and match it to the bar.
    this.streakMaterial.uniforms.color!.value.copy(tone).lerp(new THREE.Color(0xffffff), 0.32);
    const drawn = this.encoding.available
      ? Math.max(1, Math.round(this.rays.length * this.encoding.photonRayFraction))
      : 0;
    this.streaks.geometry.setDrawRange(0, drawn * 2);
    this.streaks.visible = this.encoding.available;
    this.group.userData.dataAvailable = this.encoding.available;
    this.group.userData.goesClass = this.encoding.className;
    this.group.userData.activityState = this.encoding.activityState;
    this.group.userData.currentFluxWm2 = this.encoding.available ? fluxWm2 : null;
    this.group.userData.inboundRayCount = drawn;
    return this.encoding;
  }

  /**
   * Advance the beam.
   *
   * A pure function of the elapsed display time it is handed: the renderer
   * passes its accumulated environmental-motion clock, so when the visitor
   * turns "Environmental motion" off that clock stops advancing and the beam
   * freezes exactly where it is — a still shower of streaks, not an empty
   * layer. The tint above it never moved in the first place; the shared
   * renderer rotates it into the Sun frame.
   */
  update(elapsedDisplaySeconds: number) {
    if (!Number.isFinite(elapsedDisplaySeconds)) return;
    const geometry = this.streaks.geometry;
    const positions = geometry.getAttribute("position") as THREE.BufferAttribute | undefined;
    const alphas = geometry.getAttribute("flowAlpha") as THREE.BufferAttribute | undefined;
    if (!positions || !alphas) return;
    const entryX = this.sunwardEntryX();
    for (let index = 0; index < this.rays.length; index += 1) {
      const ray = this.rays[index]!;
      const progress = ((ray.phase + elapsedDisplaySeconds / this.traversalSeconds) % 1 + 1) % 1;
      const head = xrayPhotonRayHead(ray, entryX, progress);
      // In at the top of the crossing, and a brief dissolve at the end: the
      // ray stops being drawn where it is absorbed. It does not continue, it
      // does not reflect, and it does not reappear on the night side.
      const alpha = smoothstep(0, 0.05, progress) * (1 - smoothstep(0.9, 1, progress));
      positions.setXYZ(index * 2, head.x, head.y, head.z);
      // The streak trails sunward, along the ray's own straight path — the
      // only direction anything in this beam ever points.
      positions.setXYZ(index * 2 + 1, head.x + this.streakLength, head.y, head.z);
      alphas.setX(index * 2, alpha);
      alphas.setX(index * 2 + 1, alpha);
    }
    positions.needsUpdate = true;
    alphas.needsUpdate = true;
  }

  dispose() {
    this.glow.geometry.dispose();
    this.streaks.geometry.dispose();
    this.glowMaterial.dispose();
    this.streakMaterial.dispose();
    this.group.clear();
  }

  /** Two vertices per ray: head, then the tail the fade runs out to. */
  private static buildStreakGeometry(count: number) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(count * 6), 3));
    geometry.setAttribute("flowAlpha", new THREE.BufferAttribute(new Float32Array(count * 2), 1));
    const fade = new Float32Array(count * 2);
    for (let index = 0; index < count; index += 1) {
      fade[index * 2] = 1;
      fade[index * 2 + 1] = 0;
    }
    geometry.setAttribute("trailFade", new THREE.BufferAttribute(fade, 1));
    geometry.userData.kind = "xray-inbound-photon-beam";
    geometry.userData.encoding =
      "one straight parallel ray per segment; population and brightness are the measured GOES flux, "
      + "streak length is a fixed display length, crossing cadence is display cadence";
    geometry.userData.termination =
      "absorbed on the dayside of the drawn upper-atmosphere shell — never the night side, never wrapped";
    return geometry;
  }
}

export function createXrayIrradianceVisual(options: XrayIrradianceVisualOptions = {}) {
  return new XrayIrradianceVisual(options);
}
