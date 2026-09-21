import { MLT_HALF_SPAN_HOURS, OUTER_EDGE_RE, sheetCentreZRe } from "./inner-plasma-sheet";
import { shueRadiusRe } from "./magnetopause";
// The mirror latitude is the radiation-belt layer's own arithmetic, imported
// rather than restated. A trapped particle drawn here bounces between the same
// mirror points the belt layer maps its flux onto, so if that inversion is ever
// corrected the drawn bounce moves with it instead of quietly disagreeing.
import { dipoleMirrorLatitudeRadians } from "./radiation-belt";

/**
 * The last stretch of the Dungey cycle, as a schematic transport path.
 *
 * ## What this is for
 *
 * The solar-wind layer already couples to the magnetosphere layer: when the
 * driven field lines are on screen, a share of the arriving particles stops
 * deflecting round the obstacle and rides those very lines instead — down the
 * cusp funnels to the poles, and tailward along the open lobes. That coupling
 * is built in `solar-input-visuals.ts` and it is not touched here.
 *
 * The complaint this module answers is that the ride stops there. Sean:
 *
 *   *"When we have the plasma sheet on, shouldn't we further couple the IMF
 *   and solar wind to show the movement of the particles that end up in the
 *   ring current and the aurora? Isn't that a major flow?"*
 *
 * It is the major flow. It is the Dungey (1961) cycle, and the site already
 * teaches it in prose on its own Dungey page while the picture stops one leg
 * short. This module supplies the missing legs, in the same representation the
 * existing coupling already uses — a travel-ordered polyline in physical GSM
 * Earth radii, handed to the same tracer machinery, ridden by the same
 * particles — so nothing about how a reader reads the picture changes.
 *
 * ## The evidence split, which is the whole of the honesty here
 *
 * **The driver is MEASURED.** How much of this happens at all is set by
 * `newellCoupling` in `storm-indices.ts` — Newell et al. (2007)
 * `dPhi_MP/dt = v^(4/3) B_T^(2/3) sin^(8/3)(theta_c/2)`, evaluated on the
 * propagated L1 speed, By and Bz this site already publishes and already
 * prints. It is the published, citable rate at which flux is opened at the
 * dayside, and it is exactly the quantity that decides how much material ends
 * up in the plasma sheet, the ring current and the aurora. Nothing here
 * invents it and nothing here re-derives it: `couplingDrive` below only places
 * a measured number on the site's own published band ladder.
 *
 * **The path is SCHEMATIC.** Nobody measures these trajectories. There is no
 * spacecraft following a flux tube from the lobe to the oval, and no published
 * field this site fetches contains one. What IS settled is the sequence — open
 * flux is carried antisunward over the polar cap into the lobes, reconnects at
 * a near-Earth neutral line, and the closed flux snaps earthward carrying hot
 * plasma into the inner magnetosphere, where the ions drift west into the ring
 * current and electrons precipitate into the oval. Drawing that sequence is
 * legitimate teaching. Implying we are watching it happen would not be, so
 * every polyline this module returns carries `evidence: "schematic"` and the
 * legend copy in `dungeyTransportCopy` says it in words.
 *
 * **Past the last measured driver there is nothing.** No propagated wind means
 * no coupling number, which means no rate, which means nothing to animate. The
 * layer goes dark and the card says why, in the same grammar
 * `magnetopause-forecast.ts` settled on for the boundary: an empty region is
 * what honest missing data looks like.
 *
 * ## Two geometric commitments, both testable
 *
 * Every vertex is checked against the magnetopause before it is drawn
 * (`containedInMagnetopause`). The inner plasma sheet already shipped once
 * drawing tail material on the dayside, outside the boundary, in every driver
 * state this site has recorded; a particle path that leaves the magnetopause
 * is the same defect wearing different clothes, and `buildDungeyReturnLeg`
 * refuses rather than draws when its own path fails the check.
 *
 * And the auroral end is not placed by eye. The precipitation branch follows a
 * dipole field line from where the injected plasma sits, so its footpoint
 * latitude is `arccos(sqrt(1/L))` and nothing else — about 67 degrees from an
 * inner edge at 6.6 Re and 70.5 degrees from 9 Re. That the drawn oval lands
 * where OVATION draws the measured one is a check on the construction, not a
 * number anyone chose.
 */

/** A point in physical GSM Earth radii, the units every path here speaks. */
export interface GsmPointRe {
  x: number;
  y: number;
  z: number;
}

/**
 * Where the near-Earth neutral line sits, in Earth radii down-tail.
 *
 * The substorm X-line forms out around 15-25 Re, which is why the inner plasma
 * sheet layer draws its outer edge at 14: past that is storage, not delivery.
 * 20 is the middle of the published range and it sits comfortably outside the
 * drawn wedge, so the turn is visibly the event that feeds the wedge rather
 * than something happening inside it.
 *
 * This is a schematic placement of a real feature, not a measurement. Nothing
 * this site fetches locates tonight's X-line, and if something did it would
 * move by several Earth radii through a substorm.
 */
export const TAIL_X_LINE_RE = 20;

/**
 * How much of the antisunward ride is drawn as the slide onto the sheet, Re.
 *
 * Lobe plasma does not arrive at the neutral sheet by falling into it. It
 * streams antisunward along the lobe field line while the whole flux tube is
 * carried sheetward by the convection E×B drift, so the approach is a long
 * shallow slide rather than a drop: the sheetward speed is a small fraction of
 * the streaming speed, which is exactly why the tail is shaped the way it is.
 * The version of this module that shipped first drew no approach at all — the
 * ride ran parallel to the sheet and then dropped onto it, and at zero dipole
 * tilt the drop was exactly vertical and the turn that followed it exactly 90
 * degrees. Sean, watching the live site: *"some solar wind particles travel
 * along the magnetic field lines to the plasma sheet and then turn 90 degrees
 * into the plane of the plasma sheet. Is that real physics?"* It is not.
 *
 * The run is the gap between two distances this site already draws — the outer
 * edge of the plasma-sheet wedge and the neutral line — so the ride leaves the
 * traced open line exactly where the drawn wedge ends and reaches the sheet
 * exactly where the reconnection is placed. `OUTER_EDGE_RE` is imported rather
 * than copied, so if that wedge is ever redrawn the approach moves with it
 * instead of quietly disagreeing.
 *
 * WHY NOT SIMPLY LONGER. The shared ruler compresses radial distance hard in
 * the far tail and leaves transverse distance alone: at 20 Re its local
 * log-log slope is 0.32, so a sheetward step is DRAWN about three times larger
 * than an equal antisunward one. Lengthening the run flattens the drawn slide
 * and shortening it steepens it back toward the vertical drop this replaced,
 * but a longer run also takes the ride off traced geometry earlier, and the
 * traced field line is the whole reason a reader believes the picture. Six
 * Earth radii is where that trade was made.
 */
export const LOBE_APPROACH_RUN_RE = TAIL_X_LINE_RE - OUTER_EDGE_RE;

/**
 * How far round in local time the injected ions drift before the drawn path
 * ends, in hours of MLT.
 *
 * Six hours takes a stream injected near midnight to the dusk sector, which is
 * where the partial ring current is observed to sit. The drift itself is not
 * illustrated as a full circuit: a closed drift orbit would take hours of real
 * time and drawing one would say the site is following a particle round it.
 */
export const RING_DRIFT_MLT_HOURS = 6;

/**
 * Where the drifting branch ends, in L.
 *
 * The ring current's energy density peaks around L 3-5. The drawn branch runs
 * inward from the plasma sheet's own inner edge to 4.5, which puts its end
 * inside the torus the ring-current layer draws, so the two layers meet rather
 * than merely coexist.
 */
export const RING_TARGET_L = 4.5;

/**
 * WHAT A TRAPPED PARTICLE DOES, AND WHICH PART OF IT CAN HONESTLY BE DRAWN.
 *
 * Sean: *"for the ring current and radiation belts I thought there should be
 * some coupling to the particle."* There is now, and it is the SAME particle —
 * the one that arrived on the wind, rode the cusp or the lobe, turned at the
 * neutral line and was injected earthward. Nothing new is seeded into the
 * inner magnetosphere and no second population is drawn. What the inner
 * magnetosphere changes is HOW that particle moves, which is the site's
 * standing rule for every layer that is not the wind.
 *
 * A trapped particle does three things at once, on three wildly separated
 * clocks. Measured for the layer's own reference case — a 100 keV proton on
 * L 4.5 with a 45-degree equatorial pitch angle, in a dipole:
 *
 *   - **gyration** about the field line, period 0.19 s, radius 135 km;
 *   - **bounce** between mirror points, period 17 s;
 *   - **drift** right round the Earth, period 5,900 s, about 1.6 h.
 *
 * That is roughly 1 : 90 : 31,000. Two of the three are drawn and one is not,
 * and the reason is scale rather than taste.
 *
 * ## Gyration is not drawn, because its size is not a display choice
 *
 * 135 km is 0.021 Earth radii, against a drift path 4.5 Earth radii across:
 * one part in 214 of the circle it would be drawn on, which is thinner than
 * the line the path is drawn with at every camera distance this scene offers.
 * A spiral you can see on the globe is a spiral drawn a hundred times too fat,
 * and a reader who measured it off the screen would come away with a number
 * that is wrong by two orders of magnitude. So the globe does not draw it.
 * The `trapped-motion` mechanism clip teaches gyration at a scale where it can
 * be drawn honestly — its own frame is a few hundred kilometres wide — and the
 * card sends the reader there rather than faking it here.
 *
 * ## The bounce IS drawn, at its true amplitude and at a declared slower rate
 *
 * The bounce's AMPLITUDE is not a display choice either, and that is what
 * makes it drawable: the mirror latitude follows from the equatorial pitch
 * angle alone, and for the four angles drawn here it is 8.6, 17.9, 27.6 and
 * 35.5 degrees off the equator — a large, real, visible excursion, and the
 * shallowest of them still six times outside the 4.4-degree loss cone at this
 * shell. It comes from
 * `dipoleMirrorLatitudeRadians`, the radiation-belt layer's own inversion of
 * `B_m/B_eq = sqrt(1 + 3 sin^2 lambda) / cos^6 lambda`, imported rather than
 * restated.
 *
 * The bounce's RATE is a display choice and is declared as one. A 100 keV
 * proton fits about 87 bounces into the quarter-lap of drift this module
 * draws. Eighty-seven bounces over that arc is a solid smear, not a picture,
 * so the drawn path fits `drawnBouncesPerDrawnArc` of them into it instead —
 * about fifteen times slower than the real ratio. The direction, the shape and
 * the height of the bounce are the physics; only how often it happens per
 * degree of drift has been slowed to where a reader can see it.
 *
 * ## Why the pitch angle varies from path to path
 *
 * A real drift shell holds particles at every pitch angle at once, so it is a
 * band rather than a wire. Drawing every path at one angle would say the
 * population mirrors at one latitude, which is the same defect as drawing one
 * drift lap and calling it "the" drift period. Each path is given its own
 * angle out of `equatorialPitchAnglesDeg`, so the shallow ones stay near the
 * equator and the steep ones swing deep toward the atmosphere — which is also
 * the reason some of them reach it.
 */
export const RING_TRAPPED_MOTION = {
  /**
   * Bounces drawn across the whole drawn drift arc.
   *
   * The real figure for the reference case is about 87. See the note above:
   * this is a legibility floor, not a measurement, and it is the one number in
   * the trapped motion that has been changed from nature.
   */
  drawnBouncesPerDrawnArc: 6,
  /** The real count for the reference case, kept beside the drawn one so the ratio is checkable. */
  realBouncesPerDrawnArc: 87,
  /** Vertices per drawn bounce. Set by the no-visible-seam budget, not by taste. */
  samplesPerBounce: 20,
  /**
   * Equatorial pitch angles drawn, degrees, cycled across the paths.
   *
   * Chosen to span the trapped range rather than to look even. Inverting
   * B_m/B_eq = sqrt(1 + 3 sin^2 lambda) / cos^6 lambda for each of them gives
   * mirror latitudes of 8.6, 17.9, 27.6 and 35.5 degrees — checked against the
   * deepest latitude the drawn helix actually reaches, which agrees to three
   * decimals — so the shallowest barely leaves the equator and the steepest
   * swings most of the way toward the atmosphere.
   *
   * The loss cone at L 4.5 is 4.4 degrees at a 1.0 Re foot and 4.6 at the 1.02
   * Re foot `AURORAL_FOOT_RADIUS_RE` actually uses, so the shallowest angle
   * drawn is six times outside it — every drawn particle is genuinely trapped
   * until something scatters it.
   *
   * (Both figures were wrong in this comment until 2026-08-27, which said 10
   * to 40 degrees of mirror latitude and a loss cone "under 4 degrees". No
   * code read either number; the drawn latitudes have always come from
   * `dipoleMirrorLatitudeRadians` and were right. It was prose drift, and it
   * is recorded here rather than quietly corrected.)
   */
  equatorialPitchAnglesDeg: [72, 54, 38, 27] as const,
  /**
   * How far round the drawn drift arc each path gets before it is lost, as a
   * fraction of that arc, cycled across the paths.
   *
   * Not evenly spread and not random. A ring-current ion's charge-exchange
   * lifetime is set by how much cold geocoronal hydrogen it is flying
   * through, and the geocorona thickens inward, so losses concentrate at the
   * deep end of the drift rather than at the start of it. Every value here is
   * past halfway for that reason. What the spread buys is that the losses are
   * not synchronised: a shell shedding particles at one local time reads as a
   * jet, and a shell shedding them across a sector reads as what it is.
   */
  lossPhases: [1, 0.72, 0.9, 0.58] as const,
  /**
   * How far a neutralised atom is drawn before it fades, Re.
   *
   * It does not stop there and nothing here says it does — the tracer's own
   * end-of-path fade carries it out of the picture. A real energetic neutral
   * atom leaves the magnetosphere entirely, which is exactly why IMAGE and
   * TWINS could photograph the ring current from outside it.
   */
  neutralEscapeRe: 11,
  /** Vertices along the escape ray. */
  neutralEscapeSamples: 9,
} as const;

/** How a drawn trapped particle leaves the population. */
export type RingCurrentLossChannel = "charge-exchange" | "precipitation";

/** Per-path trapped-motion selection. Omit it and the first entry of each set is used. */
export interface TrappedMotionInput {
  equatorialPitchAngleDeg: number;
  /** Fraction of the drawn drift arc travelled before the loss. */
  lossPhase: number;
}

/** The trapped-motion selection for path `index`, from the declared sets. */
export function trappedMotionForPath(index: number): TrappedMotionInput {
  const angles = RING_TRAPPED_MOTION.equatorialPitchAnglesDeg;
  const phases = RING_TRAPPED_MOTION.lossPhases;
  const at = Math.max(0, Math.floor(index));
  return {
    equatorialPitchAngleDeg: angles[at % angles.length]!,
    lossPhase: phases[at % phases.length]!,
  };
}

/** Where the precipitating branch stops: the top of the atmosphere, in Re. */
export const AURORAL_FOOT_RADIUS_RE = 1.02;

/**
 * How far either side of midnight an injected stream is allowed to end up.
 *
 * Deliberately the inner plasma sheet's own span, imported rather than copied,
 * so the streams stay inside the wedge that layer draws. If that layer's span
 * is ever changed again, these move with it.
 */
export const INJECTION_MLT_HALF_SPAN_HOURS = MLT_HALF_SPAN_HOURS;

/**
 * GSM direction of a magnetic local time in the equatorial plane.
 *
 * 12 MLT at +x (sunward), 18 MLT at +y (dusk), 00 MLT at -x (midnight),
 * 06 MLT at -y (dawn). Written out because the drift directions below are
 * charge-dependent and a sign error would reverse the physics rather than
 * merely mirror the picture.
 */
export function equatorialDirection(mltHours: number): { x: number; y: number } {
  const angle = ((mltHours - 12) / 24) * Math.PI * 2;
  return { x: Math.cos(angle), y: Math.sin(angle) };
}

/**
 * Midnight, as hours rather than as zero.
 *
 * Local time is carried unwrapped through the construction — midnight is 24
 * and the injection sector runs 20 to 28 — because interpolating a stream from
 * midnight to 04 MLT through the 0/24 seam sends it the long way round the
 * planet, and it does so silently.
 */
export const MIDNIGHT_MLT_HOURS = 24;

/** The magnetic local time, in hours, of a direction in the equatorial plane. */
export function mltHoursOf(x: number, y: number): number {
  const angle = Math.atan2(y, x);
  return (((angle / (Math.PI * 2)) * 24 + 12) % 24 + 24) % 24;
}

/**
 * Rotate a point from the dipole frame into GSM.
 *
 * The dipole axis is tilted by `psi` in the GSM x-z plane, so its unit vector
 * is `(sin psi, 0, cos psi)` and the magnetic equator plane is
 * `x sin psi + z cos psi = 0` — the same plane `sheetCentreZRe` hinges onto,
 * checked against it by test rather than assumed.
 */
export function gsmFromDipoleFrame(x: number, y: number, z: number, dipoleTiltRad: number): GsmPointRe {
  const cos = Math.cos(dipoleTiltRad);
  const sin = Math.sin(dipoleTiltRad);
  return { x: x * cos + z * sin, y, z: -x * sin + z * cos };
}

/**
 * The dipole footpoint latitude of an equatorial crossing at `lShell`, degrees.
 *
 * `r = L cos^2(lat)`, so the line reaches `footRadiusRe` at
 * `lat = arccos(sqrt(footRadiusRe / L))`. This is the entire placement of the
 * auroral end of the chain: no oval latitude is chosen anywhere in this file.
 */
export function dipoleFootpointLatitudeDeg(lShell: number, footRadiusRe = AURORAL_FOOT_RADIUS_RE): number | null {
  if (!(lShell > footRadiusRe) || !Number.isFinite(lShell)) return null;
  return (Math.acos(Math.sqrt(footRadiusRe / lShell)) * 180) / Math.PI;
}

function clamp01(value: number) {
  return Math.min(1, Math.max(0, value));
}

function ease(t: number) {
  const clamped = clamp01(t);
  return clamped * clamped * (3 - 2 * clamped);
}

/**
 * Is every point inside a Shue (1998) magnetopause with these parameters?
 *
 * Shue is open down-tail and its radius diverges on the anti-solar axis, so a
 * point with no finite boundary radius cannot be outside one and is skipped.
 * `margin` is how much of its own boundary radius a point is allowed to reach:
 * the drawn path is a schematic, so it is held well inside rather than merely
 * inside, exactly as the inner plasma sheet's wedge is.
 */
export function containedInMagnetopause(
  points: readonly GsmPointRe[],
  subsolarStandoffRe: number,
  flaringAlpha: number,
  margin = 0.9,
): { contained: boolean; worstFraction: number } {
  let worst = 0;
  for (const point of points) {
    const radius = Math.hypot(point.x, point.y, point.z);
    if (!(radius > 0)) continue;
    const theta = Math.acos(Math.max(-1, Math.min(1, point.x / radius)));
    const boundary = shueRadiusRe(theta, subsolarStandoffRe, flaringAlpha);
    if (!Number.isFinite(boundary) || boundary <= 0) continue;
    worst = Math.max(worst, radius / boundary);
  }
  return { contained: worst < margin, worstFraction: worst };
}

/** Which end of the chain a return leg is drawn to. */
export type DungeyBranch = "ring-current" | "aurora";

/** Which way the injected population goes at the inner edge. */
export type DriftSense = "westward" | "eastward";

export interface DungeyReturnInput {
  /**
   * Where the particle leaves the traced open field line: the point at which
   * the lobe polyline crosses `TAIL_X_LINE_RE - LOBE_APPROACH_RUN_RE`
   * down-tail. Supplied by the caller from the drawn geometry, never invented
   * here. The hand-off is SUNWARD of the neutral line, because the last
   * stretch of the approach is the sheetward drift and that has to be drawn to
   * be seen.
   */
  entryGsmRe: GsmPointRe;
  /** Dipole tilt for the instant being drawn, radians. */
  dipoleTiltRad: number;
  /** The inner edge of the hot plasma sheet, Re. `innerEdgeRe()` supplies it. */
  innerEdgeRe: number;
  /** Where the stream ends up in local time, hours from midnight, negative toward dusk. */
  injectionMltOffsetHours: number;
  /** Which hemisphere the precipitating branch falls into. */
  hemisphere: "north" | "south";
  branch: DungeyBranch;
  /**
   * Which way the population drifts at the inner edge. Ions drift westward
   * (midnight toward dusk) and electrons eastward (midnight toward dawn) under
   * gradient and curvature drift; the caller sets it from the tracer species,
   * so the two populations visibly separate the way they do in nature.
   */
  driftSense: DriftSense;
  /**
   * The traced line's own direction of travel where the ride leaves it, GSM
   * Re. Any length: only the direction is used.
   *
   * With it, the schematic slide sets off ALONG the traced line instead of at
   * an angle to it, so there is no corner where drawn geometry hands over to
   * schematic geometry: the sheetward convergence the traced lobe line already
   * has is continued rather than restarted. Without it the slide starts
   * parallel to the sheet and leaves a small kink, so it is optional — a
   * caller with no tangent gets a slightly worse path rather than none.
   */
  approachTangentGsmRe?: GsmPointRe | null;
  /** Where the X-line sits, Re down-tail. Defaults to `TAIL_X_LINE_RE`. */
  xLineRe?: number;
  /** Samples along the earthward and terminal legs. Kept small: this runs per path. */
  segments?: number;
  /**
   * Which trapped particle this path is drawing: its equatorial pitch angle,
   * which sets how deep it bounces, and how far round the drift it gets before
   * it is lost. Omit it and `trappedMotionForPath(0)` is used, so a caller can
   * never accidentally draw a particle with no pitch angle at all.
   */
  trapping?: TrappedMotionInput | null;
}

export interface DungeyReturnLeg {
  /** Travel-ordered polyline in physical GSM Re, entry first. */
  pointsGsmRe: GsmPointRe[];
  /** Index of the first point of the sheetward approach. */
  reconnectionIndex: number;
  /**
   * The one vertex that IS the neutral line: the last point of the approach,
   * on the current sheet, where the direction of travel reverses. It is
   * `injectionIndex - 1`, and it is returned by name because it is the only
   * vertex on the whole path that is an EVENT rather than a sample of a
   * motion — everything either side of it is the particle going where its
   * field line goes.
   */
  neutralLineIndex: number;
  /** Index of the first point of the earthward injection leg. */
  injectionIndex: number;
  /** Index of the first point of the terminal branch. */
  branchIndex: number;
  branch: DungeyBranch;
  driftSense: DriftSense;
  /** Footpoint latitude of the precipitating branch, degrees, or null. */
  footpointLatitudeDeg: number | null;
  /**
   * Index of the point at which the trapped particle is lost, or null on a
   * branch that has no trapped leg. Everything before it is trapped motion;
   * everything after it is the particle leaving the population.
   */
  lossIndex: number | null;
  /** How it leaves, or null when nothing is drawn leaving. */
  lossChannel: RingCurrentLossChannel | null;
  /**
   * Index of the first point that is no longer a charged particle, or null.
   *
   * The magnetopause containment check MUST stop here. A neutral atom is not
   * confined by the boundary — it flies straight through it, which is the
   * entire reason an energetic-neutral-atom camera outside the magnetosphere
   * can image the ring current inside it. Checking the escape ray against the
   * boundary would refuse a correct path for being correct.
   */
  neutralFromIndex: number | null;
  /** The equatorial pitch angle this path was drawn at, degrees, or null. */
  equatorialPitchAngleDeg: number | null;
}

/**
 * The schematic legs, from the lobe entry point to the end of the chain.
 *
 * Three legs, in the order the physics runs them:
 *
 *   1. **the sheetward approach, and the turn** — the flux tube carries on
 *      antisunward while the convection drift takes it in toward the neutral
 *      sheet, so the path SLIDES onto the sheet across the last
 *      `LOBE_APPROACH_RUN_RE` instead of dropping onto it. At the neutral line
 *      the direction of travel REVERSES: the field line is cut and re-joined
 *      there, and the plasma on the newly closed line is thrown back at Earth.
 *      That reversal is one vertex and it is deliberately not smoothed,
 *      because it is an event rather than a motion. What it must never look
 *      like is a particle turning a corner ACROSS the field, which is the one
 *      thing `trapped-motion` spends seventy seconds saying cannot happen —
 *      so the two legs meet nearly head on rather than at a right angle, and
 *      `dungeyTransportCopy.transport` says in words which of the two, the
 *      particle or the field, changed direction;
 *   2. **the earthward injection** — it travels in along the sheet, converging
 *      toward the injection sector, on the sheet centre plane the inner plasma
 *      sheet layer already draws (`sheetCentreZRe`, hinged, imported rather
 *      than re-derived) and blending onto the tilted dipole equator as it
 *      approaches Earth, where the two are the same surface;
 *   3. **the branch** — either a drift round toward dusk or dawn into the ring
 *      current, or a fall down the dipole field line into the oval.
 *
 * Every leg is geometry only. No time, no speed and no flux appears anywhere
 * in this function, because none of those is known for an individual particle
 * and printing one would be the invented number this site exists not to print.
 */
export function buildDungeyReturnLeg(input: DungeyReturnInput): DungeyReturnLeg {
  const segments = Math.max(6, Math.floor(input.segments ?? 20));
  const xLine = Math.max(6, input.xLineRe ?? TAIL_X_LINE_RE);
  const psi = input.dipoleTiltRad;
  const innerEdge = Math.max(2.5, input.innerEdgeRe);
  const offset = Math.max(
    -INJECTION_MLT_HALF_SPAN_HOURS,
    Math.min(INJECTION_MLT_HALF_SPAN_HOURS, input.injectionMltOffsetHours),
  );
  const targetMlt = 24 + offset;

  const points: GsmPointRe[] = [];

  // --- Leg 1: the sheetward approach, ending at the neutral line ----------
  //
  // TWO THINGS ARE TRUE AT ONCE IN THE LOBE and the first version of this leg
  // drew only one of them. The particle streams antisunward ALONG its field
  // line, fast; and the whole flux tube it is tied to is carried in toward the
  // neutral sheet by the convection E×B drift, slowly. The sum is a long
  // shallow slide, and it is the SAME cross-field drift this module already
  // draws at the inner edge, where gradient and curvature drift split the
  // species. What was drawn before was a ride parallel to the sheet and then a
  // collapse onto it, which at zero dipole tilt was an exactly vertical drop
  // followed by an exactly 90-degree turn. Measured over the traced line set,
  // that corner was 77 to 102 degrees in physical GSM — Sean spotted it on the
  // live site and it is not a viewing artifact.
  //
  // So the slide is drawn, over `LOBE_APPROACH_RUN_RE` of antisunward travel,
  // and the sharp change of direction is left at ONE vertex: the neutral line,
  // where the field line is cut and re-joined and the plasma on it is thrown
  // back at Earth. The two legs meet nearly head on there, which is what a
  // reversal looks like. A right angle would say the particle crossed the
  // field; a smoothed arc would say the same thing more prettily.
  //
  // The height above the sheet is a cubic Hermite rather than an ease, so both
  // ends have a stated tangent. At the hand-off it leaves along the traced
  // line's own direction, so drawn geometry and schematic geometry meet with
  // no kink. At the neutral line it arrives still converging at that same
  // shallow rate, because the sheetward drift does not stop when the flux tube
  // gets there — an arrival tangent of zero would close the two legs into a
  // needle and hide the turn instead of showing it.
  const entry = input.entryGsmRe;
  const neutralLine = sheetPoint(xLine, MIDNIGHT_MLT_HOURS, psi, entry.y);
  // Denser than the other legs on purpose. The slide is where the whole
  // direction change now lives, and the traced field lines it hands over from
  // are stepped to turn by at most four degrees per drawn segment; a slide
  // tessellated as coarsely as the earthward leg would put a visible kink in
  // the steepest cases, which is the defect this leg exists to remove coming
  // back as a polygon artifact. Measured over the whole driver envelope and
  // every dipole tilt this site can produce: at 24 samples the sharpest drawn
  // vertex on the slide is 36 degrees, and at 40 it is 17.
  const approachSegments = Math.max(20, segments * 2);
  const reconnectionIndex = points.length;
  const runX = neutralLine.x - entry.x;
  const tangent = input.approachTangentGsmRe ?? null;
  // Only the direction matters, and only where the hand-off actually has room
  // to slide: a tangent that is nearly perpendicular to the run, or a run of
  // nothing, would multiply up into a spike, so both are refused rather than
  // trusted.
  const slopeUsable = tangent !== null
    && Math.abs(tangent.x) > 0.2 * Math.hypot(tangent.x, tangent.y, tangent.z)
    && Math.abs(runX) > 0.5;
  const slopeY = slopeUsable ? tangent!.y / tangent!.x : 0;
  const slopeZ = slopeUsable ? tangent!.z / tangent!.x : 0;
  for (let step = 0; step <= approachSegments; step += 1) {
    const u = step / approachSegments;
    // Cubic Hermite on the unit interval: h00 p0 + h10 m0 + h01 p1 + h11 m1,
    // with x linear in u so a slope in Re-per-Re becomes a tangent in u by
    // multiplying by the run.
    const settle = ease(u);                      // 3u² - 2u³ = h01
    const enter = u * (1 - u) * (1 - u);         // h10
    const arrive = u * u * (u - 1);              // h11
    const carry = enter + arrive;                // both tangents are the same slope
    points.push({
      x: entry.x + runX * u,
      y: entry.y + (neutralLine.y - entry.y) * settle + slopeY * runX * carry,
      z: entry.z + (neutralLine.z - entry.z) * settle + slopeZ * runX * carry,
    });
  }
  const neutralLineIndex = points.length - 1;

  // --- Leg 2: earthward along the sheet -----------------------------------
  //
  // Local time is carried as hours from midnight rather than wrapped into
  // 0-24, so a stream ending at 04 MLT interpolates the two hours across
  // midnight instead of the twenty-two hours the long way round.
  const injectionIndex = points.length;
  const startRadius = xLine;
  for (let step = 1; step <= segments; step += 1) {
    const s = step / segments;
    const radius = startRadius + (innerEdge - startRadius) * ease(s);
    const mlt = MIDNIGHT_MLT_HOURS + (targetMlt - MIDNIGHT_MLT_HOURS) * ease(s);
    points.push(sheetPoint(radius, mlt, psi, entry.y * (1 - ease(s))));
  }

  // --- Leg 3: the branch ---------------------------------------------------
  const branchIndex = points.length;
  let footpointLatitudeDeg: number | null = null;
  let lossIndex: number | null = null;
  let lossChannel: RingCurrentLossChannel | null = null;
  let neutralFromIndex: number | null = null;
  let equatorialPitchAngleDeg: number | null = null;
  if (input.branch === "ring-current") {
    // --- Leg 3a: trapped motion -------------------------------------------
    //
    // Bounce and drift together, which on a dipole shell is a helix wound
    // round the Earth. See RING_TRAPPED_MOTION for what is true here (the
    // mirror latitude, the drift sense, the shell) and what has been slowed to
    // make it legible (how many bounces fit into the drawn arc), and for why
    // the third motion — gyration — is not drawn at all.
    const trapping = input.trapping ?? trappedMotionForPath(0);
    equatorialPitchAngleDeg = trapping.equatorialPitchAngleDeg;
    const mirrorLatitudeRad = dipoleMirrorLatitudeRadians(
      Math.sin((trapping.equatorialPitchAngleDeg * Math.PI) / 180),
    );
    const sense = input.driftSense === "westward" ? -1 : 1;
    // It arrived down one lobe, so it sets off toward that hemisphere first.
    const hemisphereSign = input.hemisphere === "north" ? 1 : -1;
    const lossPhase = Math.min(1, Math.max(0.2, trapping.lossPhase));
    const bounces = RING_TRAPPED_MOTION.drawnBouncesPerDrawnArc;
    const bounceSteps = Math.max(
      12,
      Math.round(bounces * RING_TRAPPED_MOTION.samplesPerBounce * lossPhase),
    );
    let lossShell = innerEdge;
    let lossMlt = targetMlt;
    let lossLatitudeRad = 0;
    for (let step = 1; step <= bounceSteps; step += 1) {
      const s = (step / bounceSteps) * lossPhase;
      lossMlt = targetMlt + sense * RING_DRIFT_MLT_HOURS * s;
      lossShell = innerEdge + (RING_TARGET_L - innerEdge) * ease(s);
      // Starts at the equator, which is where leg 2 delivered it: the particle
      // is handed over on the current sheet, not dropped onto a mirror point.
      lossLatitudeRad = hemisphereSign * mirrorLatitudeRad * Math.sin(2 * Math.PI * bounces * s);
      points.push(shellPoint(lossShell, lossMlt, lossLatitudeRad, psi));
    }
    lossIndex = points.length - 1;

    // --- Leg 3b: how it leaves --------------------------------------------
    //
    // Which channel is not a choice made for variety. Charge exchange with
    // cold geocoronal hydrogen is the dominant loss for a ring-current ION and
    // an electron cannot do it at all — it has no nucleus to hand a charge to.
    // Wave scattering into the loss cone is the dominant loss for the drifting
    // ELECTRONS, and it puts them into the atmosphere in the dawn sector,
    // which is where the diffuse aurora is observed to sit. So the branch that
    // already carries ions ends one way and the branch that already carries
    // electrons ends the other, out of the species split this module already
    // made, with nothing new decided here.
    if (input.driftSense === "westward") {
      // CHARGE EXCHANGE. The ion takes an electron from a cold neutral and
      // becomes a fast neutral atom itself. Nothing is bending it any more, so
      // it carries straight on in the direction it was already going: the path
      // simply stops turning. That is the whole of the drawn geometry, and it
      // is why nothing had to be invented to draw it — the escape direction is
      // the path's own tangent, not a direction anybody chose.
      lossChannel = "charge-exchange";
      neutralFromIndex = points.length;
      const before = points[points.length - 2]!;
      const at = points[points.length - 1]!;
      const dx = at.x - before.x;
      const dy = at.y - before.y;
      const dz = at.z - before.z;
      const span = Math.hypot(dx, dy, dz) || 1;
      const escapeSteps = RING_TRAPPED_MOTION.neutralEscapeSamples;
      for (let step = 1; step <= escapeSteps; step += 1) {
        const run = (RING_TRAPPED_MOTION.neutralEscapeRe * step) / escapeSteps;
        points.push({
          x: at.x + (dx / span) * run,
          y: at.y + (dy / span) * run,
          z: at.z + (dz / span) * run,
        });
      }
    } else {
      // PRECIPITATION. A wave scatters the electron's pitch angle into the
      // loss cone and its mirror point drops below the atmosphere, so the next
      // half-bounce does not turn around. Nothing places the end by hand, for
      // the same reason the auroral branch does not: the footpoint latitude of
      // the shell it was drifting on is arccos(sqrt(1/L)) and nothing else.
      // The wave itself is NOT drawn — no feed this site fetches measures one,
      // and the radiation-belt layer's own card says it draws no wave
      // scattering. What is drawn is what the scattering does.
      lossChannel = "precipitation";
      const footLatitudeDeg = dipoleFootpointLatitudeDeg(lossShell);
      if (footLatitudeDeg !== null) {
        footpointLatitudeDeg = footLatitudeDeg;
        const footLatitudeRad = (hemisphereSign * footLatitudeDeg * Math.PI) / 180;
        const dropSteps = Math.max(8, segments);
        for (let step = 1; step <= dropSteps; step += 1) {
          const s = step / dropSteps;
          const latitude = lossLatitudeRad + (footLatitudeRad - lossLatitudeRad) * ease(s);
          points.push(shellPoint(lossShell, lossMlt, latitude, psi));
        }
      }
    }
  } else {
    const latitude = dipoleFootpointLatitudeDeg(innerEdge);
    footpointLatitudeDeg = latitude;
    if (latitude !== null) {
      const sign = input.hemisphere === "north" ? 1 : -1;
      const direction = equatorialDirection(targetMlt);
      const latitudeRad = (latitude * Math.PI) / 180;
      for (let step = 1; step <= segments; step += 1) {
        const s = step / segments;
        // Even in latitude rather than in radius: a dipole line covers most of
        // its radial range in the last few degrees, so stepping in radius puts
        // almost every sample out at the equator and none of them in the part
        // a reader is watching.
        const lat = latitudeRad * ease(s);
        const radius = innerEdge * Math.cos(lat) ** 2;
        points.push(gsmFromDipoleFrame(
          radius * Math.cos(lat) * direction.x,
          radius * Math.cos(lat) * direction.y,
          sign * radius * Math.sin(lat),
          psi,
        ));
      }
    }
  }

  return {
    pointsGsmRe: points,
    reconnectionIndex,
    neutralLineIndex,
    injectionIndex,
    branchIndex,
    branch: input.branch,
    driftSense: input.driftSense,
    footpointLatitudeDeg,
    lossIndex,
    lossChannel,
    neutralFromIndex,
    equatorialPitchAngleDeg,
  };
}

/**
 * A point on a dipole L shell, at a local time and a magnetic latitude.
 *
 * `r = L cos^2(lambda)` is the dipole shell itself, and the rest is the same
 * cylindrical placement `dipoleRadiationPosition` uses in `radiation-belt.ts`,
 * in the same local-time convention — so the bounce drawn here lands on the
 * same surface the belt layer maps its flux onto. A test holds the two to it.
 * At `latitudeRad` zero this reduces exactly to the flat equatorial drift this
 * branch drew before the bounce was added.
 */
function shellPoint(
  lShell: number,
  mltHours: number,
  latitudeRad: number,
  dipoleTiltRad: number,
): GsmPointRe {
  const direction = equatorialDirection(mltHours);
  const cosine = Math.cos(latitudeRad);
  const radius = lShell * cosine * cosine;
  const cylindrical = radius * cosine;
  return gsmFromDipoleFrame(
    cylindrical * direction.x,
    cylindrical * direction.y,
    radius * Math.sin(latitudeRad),
    dipoleTiltRad,
  );
}

/**
 * A point on the current sheet at a radius and a local time.
 *
 * The sheet centre comes from `sheetCentreZRe` — the inner plasma sheet
 * layer's own hinged, dipole-tilted surface — out where the hinge matters, and
 * blends onto the exact tilted magnetic equator as the radius comes in, where
 * the two are the same plane. `lateralRe` carries the entry point's own
 * cross-tail offset so a stream does not snap to the midnight meridian the
 * instant it reconnects.
 */
function sheetPoint(radiusRe: number, mltHours: number, dipoleTiltRad: number, lateralRe: number): GsmPointRe {
  const direction = equatorialDirection(mltHours);
  const dipole = gsmFromDipoleFrame(radiusRe * direction.x, radiusRe * direction.y + lateralRe, 0, dipoleTiltRad);
  const hinged = sheetCentreZRe(dipole.x, dipoleTiltRad);
  const blend = ease(clamp01((radiusRe - 8) / 8));
  return { x: dipole.x, y: dipole.y, z: hinged * blend + dipole.z * (1 - blend) };
}

// ---------------------------------------------------------------------------
// The measured driver
// ---------------------------------------------------------------------------

export interface NewellCalibrationBand {
  label: string;
  value: number;
}

/**
 * The measured coupling, placed on the site's own published band ladder.
 *
 * Returns 0 at "very quiet" and 1 at the top of the published ladder, linearly
 * between adjacent published band values. The ladder is the one the pipeline
 * publishes in `newellCalibration` and the one the storm panel already grades
 * with, so this introduces no constant of its own: change the published bands
 * and this moves with them.
 *
 * Null in, null out. There is no default drive and there must not be one — a
 * missing coupling number is the state where nothing is drawn at all, and a
 * fallback here would quietly animate a transport rate nobody measured.
 */
export function couplingDrive(
  coupling: number | null,
  calibration: readonly NewellCalibrationBand[],
): number | null {
  if (coupling === null || !Number.isFinite(coupling) || coupling < 0) return null;
  const ladder = calibration
    .filter((band) => Number.isFinite(band.value))
    .slice()
    .sort((a, b) => a.value - b.value);
  if (ladder.length < 2) return null;
  const top = ladder.length - 1;
  if (coupling >= ladder[top]!.value) return 1;
  for (let index = top; index >= 1; index -= 1) {
    const lower = ladder[index - 1]!;
    const upper = ladder[index]!;
    if (coupling >= lower.value) {
      const span = Math.max(1e-9, upper.value - lower.value);
      const within = (coupling - lower.value) / span;
      return clamp01((index - 1 + within) / top);
    }
  }
  return 0;
}

/**
 * How many of a path's tracers are on screen at this drive.
 *
 * The floor is deliberately not zero. At a strongly northward IMF the coupling
 * function is near zero and the Dungey cycle very nearly stops, which is the
 * lesson; an empty path with a card saying "the switch is off" teaches it,
 * whereas a path that vanishes entirely reads as a rendering fault. One tracer
 * in ten is sparse enough that nobody mistakes it for a driven state.
 */
export function activeTracerCount(total: number, drive: number | null): number {
  if (drive === null) return 0;
  if (total <= 0) return 0;
  return Math.max(1, Math.round(total * (0.1 + 0.9 * clamp01(drive))));
}

// ---------------------------------------------------------------------------
// The words
// ---------------------------------------------------------------------------

/**
 * The sentences the legend uses, written here beside the geometry so the claim
 * and the drawing cannot drift apart, and so a test can read the exact words a
 * reader sees.
 */
export const dungeyTransportCopy = {
  /** What is drawn once the plasma-sheet/ring-current layer joins in. */
  transport:
    "With the plasma sheet layer on, the guided share does not stop at the lobes. It carries on the way the Dungey cycle "
    + "runs: antisunward over the polar cap into the tail lobes, then leaning in toward the midplane from above and from "
    + "below — that arrival is the plasma sheet being fed — until it meets the near-Earth neutral line about "
    + `${TAIL_X_LINE_RE} Earth radii down-tail, where the direction of travel reverses and the material runs back earthward `
    + "along the current sheet into the wedge this layer draws. Up to that point nothing separates the species: the wind "
    + "is one magnetised fluid and H⁺, He²⁺ and e⁻ are carried together. At the inner edge they part company, because "
    + "that is what gradient and curvature drift do to a charge: ions west toward dusk, electrons east toward dawn. That "
    + "split is the ring current forming, and which way a particle goes is decided by what it is.",
  /**
   * WHAT TURNS AT THE NEUTRAL LINE, and why the drawn path bends the way it
   * does. Sean, watching the live site: *"some solar wind particles travel
   * along the magnetic field lines to the plasma sheet and then turn 90
   * degrees into the plane of the plasma sheet. Is that real physics?"*
   *
   * It was not, and this is the sentence that has to travel with the fix. A
   * reader who has watched `trapped-motion` has been told that circling a
   * field line never carries a particle to another one -- so a path drawn
   * pivoting through a right angle reads as that particle crossing the field
   * on its own, and the reader is right to object. (Until 2026-09-03 that clip
   * said flatly that a particle "cannot cross the field", which was too strong:
   * drift does carry particles across. The clip was re-rendered; the objection
   * this comment answers survives the rewording, because the pivot still
   * attributes the direction change to the wrong thing.)
   * Two separate things were wrong and both are named here, because a picture
   * that changed without the words changing would just be a prettier claim.
   */
  turn:
    "AND THE TURN ITSELF — WHAT CHANGES DIRECTION IS THE FIELD, NOT THE PARTICLE. Two things happen on the way in, and "
    + "the picture now draws both. All the way down the lobe the particle is streaming along its field line while the "
    + "whole flux tube is carried in toward the midplane by the convection drift, so it LEANS in over the last few Earth "
    + "radii rather than arriving level and then dropping. Then at the neutral line the two lobes' field lines are cut "
    + "and re-joined, and what had been an open line trailing off down-tail is suddenly a closed line snapping back at "
    + "Earth. The particle stays on the line it is tied to; the line is what changed. That is why the path reverses "
    + "there rather than turning a corner across the field, and why the reversal is drawn as one sharp vertex — it is a "
    + "moment, not a manoeuvre. The lean in is a drift ACROSS the field, which is the same thing gradient and curvature "
    + "drift do to these particles at the inner edge, and the only cross-field motion drawn anywhere on this path.",
  /**
   * What the species distinction does and does not buy, in one place.
   *
   * Sean: *"the movement of the particles is dictated by what kind of
   * particle ... with their ultimate destinations based on what they are."*
   * It is, and this says exactly how far that goes — including the place it
   * stops, which is the alphas. A difference nobody measures is not drawn.
   *
   * WHY NO ALPHA/PROTON DIFFERENCE IS DRAWN, stated so it is not "fixed" later
   * by someone inventing one. Gradient-curvature drift rate turns on ENERGY
   * PER CHARGE, and the two defensible assumptions about an alpha disagree by
   * a factor of two. Assume the alphas arrive at the same SPEED as the protons
   * — which is what the solar wind does upstream — and an alpha carries four
   * times the energy at twice the charge, so W/q doubles and it drifts twice
   * as fast, westward, ahead of the protons. Assume instead that both were
   * energised by the same convection potential at the inner edge — which is
   * what actually accelerates a ring-current ion — and the energy gained goes
   * as the charge, W/q is identical, and the two drift at exactly the same
   * rate. Nothing this site fetches measures which is nearer the truth here:
   * the L1 feed does not publish the alpha abundance, let alone the alpha
   * energy spectrum at injection. Drawing either answer would be inventing the
   * difference rather than showing it, so what is drawn about an alpha stays
   * the one thing that is not in doubt — it is four proton masses, so it is
   * the larger, deeper mark.
   */
  species:
    "WHAT A PARTICLE IS DECIDES WHERE IT ENDS UP — but only from the inner edge on. Upstream, and all the way down the "
    + "cusps and the lobes, the wind is one magnetised fluid and every species is carried together; there is no separation "
    + "to draw and none is drawn. At the inner edge the sign of the charge takes over. Both positive species go the same "
    + "way: H⁺ and He²⁺ drift westward into the ring current together, and no difference is drawn between them, because "
    + "the drift rate turns on energy per charge and nothing this site fetches measures the alphas' energy. What IS drawn "
    + "about an alpha is that it is heavier — four proton masses, so it is the larger, deeper mark. Electrons go the other "
    + "way, eastward toward dawn, and they are the population that reaches the atmosphere and lights the oval.",
  /**
   * What happens after the injection, which is where the picture used to stop.
   *
   * Sean: *"for the ring current and radiation belts I thought there should be
   * some coupling to the particle."* The coupling is that it keeps moving.
   * `RING_TRAPPED_MOTION` holds the measurements behind every number quoted
   * here and the reasoning for the one thing that has been changed from
   * nature.
   */
  trapped:
    "AND THEN IT IS TRAPPED, WHICH IS NOT THE SAME AS STOPPING. The path carries on past the inner edge because the "
    + "particle does. It bounces between mirror points in the two hemispheres while it drifts around the Earth, and the "
    + "helix you are watching is those two motions at once. The HEIGHT of the bounce is real: it follows from the "
    + "particle's pitch angle and nothing else, and the paths are drawn across a spread of pitch angles because a real "
    + "drift shell holds every angle at once — the shallow ones barely leave the equator, the steep ones swing most of "
    + "the way toward the atmosphere. The RATE is the one thing here changed from nature, and it is changed to make it "
    + "visible: a 100 keV proton fits about 87 bounces into the quarter-turn of drift drawn here, which is a smear "
    + "rather than a picture, so six are drawn — about fifteen times slower than the real ratio. The THIRD motion, the "
    + "tight spiral around the field line itself, is NOT DRAWN AT ALL. Its radius is 135 km: one part in 214 of the "
    + "drift path it would sit on, thinner than the line that path is drawn with. A spiral you could see on this globe "
    + "would be one drawn a hundred times too fat. Mechanism clip 04 draws it at a scale where it can be drawn honestly.",
  /**
   * The loss end. Two channels drawn, two named and refused, and the reason
   * for each refusal, because "we did not draw it" and "it does not happen"
   * must never be the same silence.
   */
  losses:
    "AND THEN IT LEAVES — which is why a storm recovers. Nothing stays. Two ways out are drawn, and which one a "
    + "particle takes is decided by what it is, not chosen for variety. AN ION ENDS AS A STRAIGHT LINE: it takes an "
    + "electron from the cold hydrogen of the geocorona, becomes a fast NEUTRAL atom, and the field stops holding it — "
    + "so the path stops turning and it carries straight on the way it was already going. That is the dominant loss for "
    + "a ring-current ion, and it is not a metaphor: those neutrals are what an energetic-neutral-atom camera "
    + "photographs, and they are how IMAGE and TWINS made pictures of the ring current from outside it. AN ELECTRON "
    + "ENDS IN THE ATMOSPHERE: a wave scatters its pitch angle into the loss cone, its mirror point drops below the air, "
    + "and the next half-bounce does not turn around. Notice where those land — the dawn side, after the eastward drift, "
    + "which is where the diffuse aurora is observed to sit. The wave itself is not drawn, because nothing this site "
    + "fetches measures one. TWO MORE WAYS OUT ARE REAL AND ARE DELIBERATELY NOT DRAWN. Magnetopause shadowing — the "
    + "boundary compresses inside a drift shell and everything on that shell reaches the edge and is gone — is on the "
    + "Connections page in words, because whether it is happening at all depends on where the measured boundary is at "
    + "the moment you are looking, and drawing it always would teach that it always happens. Coulomb drag against the "
    + "cold plasmasphere has no shape: it slows a particle down where it already is, and a drawing of that is a drawing "
    + "of nothing moving. ONE LAST THING THE PICTURE IS SAYING: each path is one particle's whole life, arrival to loss. "
    + "The population holds steady not because any particle stays, but because arrivals keep pace with departures.",
  /** What the aurora layer adds. */
  aurora:
    "With the auroral oval on as well, a share of those electrons (e⁻) does not drift at all — it follows the field line down into "
    + "the atmosphere and lights the oval. Nothing places that end by hand: the branch is a dipole line from wherever the "
    // CORRECTNESS FIX 2026-09-04: the formula PRINTED was not the formula RUN.
    // `dipoleFootpointLatitudeDeg` maps to `AURORAL_FOOT_RADIUS_RE` = 1.02, the
    // top of the atmosphere where the oval actually is, not to the surface.
    // Worth 0.24 degrees at L 6.6 — small, but a reader who reproduces the
    // stated formula does not get the stated number.
    + "injected plasma sits, so its footpoint latitude is arccos(sqrt(1.02/L)) — mapped down the dipole line to the top of the atmosphere — and nothing else. Load the tail and that inner "
    + "edge comes in, so the drawn oval widens equatorward — the same way the measured one does. That it lands in the "
    + "latitudes where OVATION draws the measured oval is a check on the construction, not a number anyone chose.",
  /**
   * The answer to "are the radiation belts fed by the solar wind too?"
   *
   * Sean asked it directly, and it is a physics question before it is a
   * drawing question. The answer is *yes, indirectly, and no, not as a flow* —
   * so it is answered in words, on the card, where a reader is standing when
   * they ask it, and nothing is drawn.
   *
   * The outer belt's seed population is the plasma-sheet injection this layer
   * ALREADY draws. What makes those electrons relativistic is local: chorus
   * wave-particle acceleration and radial diffusion. Neither is a trajectory.
   * A particle energised in place does not go anywhere new, so there is no
   * path to put a tracer on, and a branch drawn into L 4-6 would be
   * indistinguishable from the ring-current electron drift already on screen
   * while implying a stream that does not exist. The inner belt has a
   * different source again. The radiation-belt layer's own stated exclusions
   * already say it draws no wave scattering and no drift phase; an arrow here
   * would contradict them.
   */
  radiationBelts:
    "AND THE RADIATION BELTS? No line is drawn from here into them, and that is an answer rather than an omission. The "
    + "outer belt's electrons ARE this population: the plasma-sheet injection on screen is its seed, so the belts are fed "
    + "by the solar wind, but indirectly and through the chain you are already watching. What is missing is a journey. "
    + "Turning a 10 keV plasma-sheet electron into a 1 MeV belt electron happens IN PLACE — chorus wave-particle "
    + "acceleration and radial diffusion — and a particle energised where it already sits has no trajectory to draw. The "
    + "inner belt is a different animal again: its protons come from cosmic-ray albedo neutron decay, not from the wind at "
    + "all. An arrow from the tail into the belts would say a stream arrives there. None does. WHAT YOU CAN SEE instead "
    + "is that the bouncing, drifting particles on screen are moving through the very shells this layer draws, doing "
    + "exactly what a belt particle does — the belts differ from them in ENERGY, not in the motion. Nothing inside the "
    + "belt volume is a position: that layer's flux carries no drift phase and no gyro phase, and says so. Every mark "
    + "that moves is this transport path's own particle.",
  /** The evidence split, which must travel with the picture. */
  evidence:
    "TWO EVIDENCE CLASSES IN ONE PICTURE. How much of this is happening is MEASURED: the Newell et al. (2007) coupling "
    + "function dΦ_MP/dt = v^(4/3) B_T^(2/3) sin^(8/3)(θc/2), evaluated on the propagated L1 speed, By and Bz shown above, "
    + "sets how many particles are on the transport path and how fast they run. Turn the IMF northward and the sine term "
    // CORRECTNESS FIX 2026-09-04: the path does not empty. `activeTracerCount`
    // has a deliberate floor of one tracer in ten, argued in its own docstring
    // — "a path that vanishes entirely reads as a rendering fault" — so at zero
    // drive a twenty-tracer path still draws two. Only a missing wind
    // measurement empties it, and that is a different state with its own
    // string. Saying "empties" made the drawn floor look like a bug.
    + "collapses and the path thins to a last tracer or two — the floor is deliberate, so a stopped cycle does not read as a broken one. That thinning is the whole lesson. The PATH ITSELF IS SCHEMATIC: nobody measures these "
    + "trajectories, no spacecraft follows a flux tube from the lobe to the oval, and no feed this site fetches contains "
    + "one. The sequence is settled physics and is drawn as such; the individual journey is not a measurement.",
  /**
   * The wind is on screen but no coupling number can be formed for it.
   *
   * THE OTHER ABSENCE IS DELIBERATELY NOT WORDED HERE. Past the end of the
   * measured record there is no propagated wind at all, the whole solar-wind
   * layer goes dark, and the layer's own coverage notice REPLACES this note
   * with the time the record stops and a button back into it. A second
   * sentence saying the same thing would be text no reader can reach,
   * pretending to be a safeguard — measured on the live page: scrub to +72 h
   * and it is the coverage notice that appears, not this.
   */
  noCoupling:
    "The transport is not drawn: there is no coupling number for this instant. It comes from the propagated bulk speed "
    + "and the whole IMF vector, and one of those is missing from this release for the time you picked. The animation is "
    + "driven by that measured rate rather than by a loop, so with no rate there is nothing to drive it with, and nothing "
    + "is drawn.",
  /**
   * Both layers are on and the drivers are here, but the transport still could
   * not be placed. Truthful about the whole set of reasons rather than naming
   * one: the traced field lines may have failed their own integrity check,
   * there may be no measured substorm state to set the plasma sheet's inner
   * edge, or no traced lobe line may reach the neutral line to turn at.
   */
  notDrawn:
    "The transport is not drawn for this instant. It is placed from three things this site measures or traces — the open "
    + "field lines the magnetosphere layer draws, the measured substorm state that sets where the plasma sheet's inner edge "
    + "is, and the measured boundary the drawn path is checked against — and at least one of them is not available here. "
    + "The guided wind still rides the field lines it does have; nothing further is drawn rather than something invented.",
  /** When the reader has the plasma sheet on but not the magnetosphere. */
  needsMagnetosphere:
    "Switch the magnetosphere layer on to see where this material comes from: the transport starts on the open lobe field "
    + "lines that layer draws, and without them there is no drawn path for it to arrive on.",
  /** When the path failed its own containment check and is refused. */
  refused:
    // CORRECTNESS FIX 2026-09-04: the check is `worst < 0.9`, so a path is
    // refused once it reaches 90% of the local boundary radius — while it is
    // still inside. The function's own docstring says "held well inside rather
    // than merely inside"; the reader-facing sentence claimed the path had
    // left the magnetosphere, which is a different and stronger fact.
    "The transport path is not drawn for this instant: at least one point of it came within a tenth of the Shue magnetopause for the "
    + "measured drivers. The path is held well inside the boundary rather than merely inside it, because a schematic that "
    + "grazes the magnetopause is one small error away from crossing it, and a particle path outside the boundary is a "
    + "physics error rather than a schematic. Nothing is drawn instead of something wrong.",
} as const;
