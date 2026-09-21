/**
 * The scene's one radial ruler, shared by every layer that draws a physical
 * radius: satellites, radiation belts, plasmasphere, ring current, the
 * empirical magnetopause set, the SWMF cut planes and the solar-wind tracers.
 *
 * ## Why the curve changed shape
 *
 * The previous ruler was purely logarithmic. That reads beautifully near
 * Earth — a 90 km ionospheric layer and a geostationary orbit fit one picture
 * — but out where the boundary physics lives it is nearly flat, and a nearly
 * flat radial map destroys angular shape. Measured with live drivers
 * (subsolar standoff 7.35 Re, Shue flaring alpha 0.711): the true
 * nose-to-flank flaring of the magnetopause is 1.64x, and the log ruler drew
 * it as 1.066x. The magnetosphere rendered as a near-sphere however correctly
 * the physics upstream of the ruler was computed. The same flatness magnified
 * transverse displacement over radial by 7-10x, which turned genuinely
 * sunward solar-wind flow into a starburst radiating out of the Earth, and it
 * collapsed the 6 Re gap between magnetopause and bow shock into 19 scene
 * units, which is why the magnetosheath never read as a region.
 *
 * ## The curve
 *
 * Three regimes, one monotone function of physical radius:
 *
 *   - r <= 6.6 Re (geostationary): the untouched logarithmic near-Earth
 *     scale. Everything below GEO — every satellite shell, the plasmasphere,
 *     the ring current, the belts' cores — is drawn exactly where it always
 *     was.
 *   - 6.6 to 7.35 Re: the JOINT RAMP. The log-log slope rises linearly in log
 *     radius from the log branch's own 0.1422 to 1, so the two regimes meet
 *     without a step. See "the joint" below: a step here drew a real corner
 *     into every curve that crossed it.
 *   - 7.35 to 13 Re: LINEAR (log-log slope 1). This band holds the whole
 *     dayside boundary system — magnetopause nose 6-11 Re, bow shock nose
 *     ~13 Re, the flank at the terminator — and drawing it linearly renders
 *     its shape in true proportion: drawn flaring equals physical flaring,
 *     and the direction of drawn motion equals the direction of physical
 *     motion (anisotropy exactly 1).
 *   - beyond 13 Re: the slope tapers smoothly (in log-radius) from 1 down to
 *     0.14 by 24 Re and stays there. This progressively foreshortens the far
 *     tail and the outer cut-plane corners, and it is the entire price of the
 *     dayside being true.
 *
 * ## The numbers that fixed the constants
 *
 * The frame budget: the camera's far plane is 3,000 scene units and framing
 * the drawn scene costs distance = 1.1 * radius / tan(fov/2) = 2.87 * radius.
 * Under this curve the -50 Re Shue tail cutoff (physical radius ~56 Re) lands
 * at 723 scene units and the SWMF cut-plane corner (65 Re) at 738, so the
 * frame distance is ~2,115 — inside a 2,200 orbit limit with the far plane
 * clear. Earth then spans about 12% of the frame height with the boundary
 * layers on, versus 18% before; that is the measured legibility cost, judged
 * acceptable against a false sphere. Full linearity all the way down the tail
 * was measured too and rejected: it puts the tail end at ~1,900 scene units,
 * the frame at ~5,500 — beyond the far plane, with Earth a 4% speck.
 *
 * The taper is C1: the slope ramps smoothly (smoothstep in log radius), so no
 * drawn surface picks up a crease at 13 or 24 Re.
 *
 * ## The geostationary joint, and why it is no longer a step
 *
 * Until 2026-08-19 the slope STEPPED at the anchor, from the log branch's own
 * 0.1422 to 1 — a 7.03x jump in radial magnification at a single radius. The
 * argument for it, written here, was that "the only surfaces crossing 6.6 Re
 * are diffuse translucent volumes (outer belt fringe), where a tangent break
 * does not read", and that smoothing it would push the ramp into 7-11 Re where
 * the magnetopause nose breathes. Both halves were wrong, and this is what
 * replaced them.
 *
 * A purely radial map refracts a crossing curve's tangent: with psi the angle
 * between the motion and the radial direction, the drawn angle is
 * atan(tan(psi) / slope). A STEP in slope is therefore a step in direction —
 * an actual corner in the drawn curve, of infinite curvature, which no amount
 * of tessellation can smooth. Marching MERIDIAN 9's drawn path through the
 * crossing at 0.5-SECOND steps left 11.96 degrees at one vertex and 21.7
 * degrees of total refraction across two; at 120-second steps it was 20.84.
 * It does not converge, because there is nothing there to converge to. With
 * the ramp below, the same march measures 0.00 degrees at 0.5 s and 0.40 at
 * 120 s: an ordinary curve, tessellated.
 *
 * The claim that only diffuse volumes crossed 6.6 Re was false three times
 * over, and all three were measured on the shipped build:
 *
 *   - The SELECTED SPACECRAFT'S ORBIT, a single bright polyline, crosses the
 *     anchor twice per revolution on every eccentric orbit. Sean photographed
 *     the result on THEMIS A: a V-shaped cusp a third of the way out from the
 *     globe. Worst drawn vertex turn at the joint against the worst anywhere
 *     else on the same line: MERIDIAN 9 16.1 vs 5.0, THEMIS A 42.7 vs 6.5,
 *     CLUSTER II-FM7 45.6 vs 8.0. A CIRCULAR orbit at that radius measures
 *     2.8, its ordinary per-vertex turn, because tangential motion does not
 *     refract — which is what identifies the corner as refraction rather than
 *     as anything about that altitude.
 *   - The TRACED MAGNETOSPHERE FIELD LINES. 107 of the 143 drawn lines cross
 *     the anchor, and the worst drawn turn among them was 45.8 degrees against
 *     7.7 degrees elsewhere on those same lines. Nobody had photographed that
 *     one; the lines are thin and additively blended, so it read as texture.
 *   - The EXTERIOR CUSP SHELL, which is a surface and not a volume. Nguyen's
 *     indentation reaches 6.567 Re under the lowest standoff in the driver
 *     history the site holds — below the anchor — so the funnel wall crossed
 *     the step too.
 *
 * ## Where the ramp ends, and why that costs the magnetopause nothing
 *
 * `noseRampEndRe` is 7.35 Re, and the reason is that the property the ruler
 * was reshaped for is a property of the interval a boundary OCCUPIES, not of
 * the whole band. The Shue surface's smallest radius is its nose: every other
 * point on it is further out. So drawn flaring equals physical flaring exactly
 * whenever the ramp ends at or below the nose, and the ramp's width below that
 * is free. Measured, on the drawn geometry rather than on the algebra: with
 * the ramp ending at 7.35 Re the nose-to-terminator ratio comes out at the
 * physical ratio to 6 decimal places for every standoff at or above 7.35 Re,
 * and `tests/magnetopause-scene-ruler.test.ts` passes unchanged.
 *
 * 7.35 Re is the standoff this ruler's own reshaping was measured against, and
 * it is also the LOWEST subsolar standoff in the driver history the site
 * currently holds — 1,087 published samples over three days, minimum 7.352 Re,
 * median 9.51, maximum 13.52. Three days is a short baseline and is not a
 * claim about the future: Shue at 8 nPa with Bz -15 nT puts the nose at
 * 6.66 Re, inside the ramp. What happens then is stated rather than hidden.
 * Drawn flaring is UNDERSTATED by 0.97% with the nose at 7.0 Re, 2.44% at
 * 6.8 Re and 4.62% at 6.6 Re, degrading from zero at a rate that starts at
 * zero, because the slope leaves 1 smoothly. For scale, the same ruler already
 * understates quiet-time flaring by 3.75%, for an unrelated reason that has
 * always been here: with the nose at 11.58 Re the terminator sits at 17.2 Re,
 * past the 13 Re taper. The exact-flaring guarantee has always been a window
 * — standoff between the ramp end and about 8 Re — and this change moves its
 * lower edge from 6.62 to 7.35 Re.
 *
 * ## The price, which is a uniform scale factor
 *
 * The ramp gives up 0.0451 of slope integral, so EVERYTHING above 7.35 Re
 * draws 4.41% closer in. That is one scale factor applied to the whole outer
 * scene: every ratio among things above the ramp — the flaring, the
 * magnetosheath gap, the tail proportions — is untouched, and the frame budget
 * improves rather than degrades. The -50 Re Shue tail cutoff moves from 723 to
 * 691 scene units and the framing distance from ~2,115 to ~2,020. Nothing at
 * or below geostationary orbit moves at all.
 *
 * The one layer that notices is the radiation-belt volume, whose bake lays its
 * radial grid uniformly in DRAWN radius out to the RBE grid edge; that grid
 * re-spaces, and the opacity table in `radiation-belt-volume.ts` was
 * re-derived in the same change rather than left to drift.
 *
 * ## Why the ramp is linear in slope, not smoothstep
 *
 * Two measured reasons. A curve's drawn bending rate goes as d(slope)/d(ln r),
 * and over a band this narrow the SHAPE of the ramp decides the worst vertex:
 * smoothstep piles about 1.5x its average into the middle of the band, linear
 * does not. And a linear slope ramp makes the drawn radius exponential in a
 * QUADRATIC, so it stays CLOSED-FORM INVERTIBLE — which is what lets the
 * radiation-belt volume's GLSL copy of this ruler keep inverting it per
 * raymarch step with a square root instead of bisecting inside a shader. The
 * price is that the SLOPE has a corner at each end of the ramp: the drawn map
 * is C1 but not C2. A curvature step, unlike a tangent step, does not read on
 * a line or on a translucent surface.
 *
 * ## What the ramp does NOT fix
 *
 * The total refraction across the joint is set by the ratio of the two slopes,
 * 1 / 0.1422 = 7.03, and only the WIDTH of the band spreads it. 6.62 to
 * 7.35 Re is 0.105 in log radius, so the drawn curve's radius of curvature
 * there is small: 100 scene units on MERIDIAN 9 against 182 for the tightest
 * bend anywhere else on that line, but 13.8 against 72.5 on THEMIS A and 8.6
 * against 111 on CLUSTER II-FM7. Those two are still visibly the tightest bend
 * on their own orbit — a curve, drawn as a curve, but a tight one. Widening
 * the ramp past the nose is what would fix them, and it is a scene-wide trade
 * against the magnetopause, not a defect to patch quietly.
 *
 * Radial distance is still compressed and still must never be read
 * quantitatively; every legend value remains the physical one. What is new is
 * that between GEO and 13 Re, *shape* — ratios of radii, directions of motion
 * — is no longer compressed at all.
 *
 * ## The two scales
 *
 * The curve above is the TEACHING scale, and it stays the default. Since
 * 2026-08 the ruler also carries a TRUE-DISTANCE scale — drawn radius exactly
 * proportional to physical geocentric radius, globe at 1 — selectable from
 * Display settings. On the true scale the belts render as the wide donuts of
 * the published depictions and all of LEO collapses into a thin shell hugging
 * the globe, both of which are the truth.
 *
 * The scale is a module-level mode rather than a parameter on purpose: every
 * consumer in the scene resolves to these three functions, so one switch
 * moves every layer together and the two scales can never mix on screen. A
 * satellite truly inside the outer belt draws inside it on both scales — that
 * cross-layer honesty is the property the shared ruler exists to protect.
 * Tests pin the teaching curve at the default and the proportionality of the
 * true curve; `activeDistanceScale()` reports which one is live.
 */

/** The two radial scales the scene can draw on. Never mixed within a frame. */
export type DistanceScaleId = "teaching" | "true-distance";

let activeScale: DistanceScaleId = "teaching";

/**
 * Switch every consumer of the ruler at once. Callers that hold geometry
 * baked through the old scale (belt volume, cut planes, traced field lines)
 * must rebuild after this; `SpaceGlobe.setDistanceScale` owns that sweep.
 */
export function setActiveDistanceScale(scale: DistanceScaleId) {
  activeScale = scale;
}

export function activeDistanceScale(): DistanceScaleId {
  return activeScale;
}

/** Tolerant parse for persisted preferences; anything unrecognised is null. */
export function parseDistanceScale(value: unknown): DistanceScaleId | null {
  return value === "teaching" || value === "true-distance" ? value : null;
}

/** Kilometres per Earth radius, matching the orbit propagator and altitude scale. */
export const RULER_EARTH_RADIUS_KM = 6371;

export const RADIAL_RULER = {
  /**
   * Where the near-Earth logarithmic scale hands over: geostationary orbit,
   * exactly — 35,786 km of altitude — so the highest teaching orbit is the
   * last thing the log scale places and its drawn position never moves.
   */
  anchorRe: 1 + 35786 / RULER_EARTH_RADIUS_KM,
  /** Log-log slope from the ramp end to the taper: 1 = true shape. */
  daySlope: 1,
  /**
   * Where the joint ramp finishes rising from the log branch's own slope to
   * the dayside's 1. 7.35 Re is the subsolar magnetopause standoff this
   * ruler's reshaping was measured against, and the lowest standoff in the
   * driver history the site holds. The Shue surface's smallest radius is its
   * nose, so a ramp ending at or below the nose leaves the drawn nose-to-flank
   * flaring exactly equal to the physical flaring; the header says what
   * happens on the storms that push the nose lower.
   */
  noseRampEndRe: 7.35,
  /** Where the tail taper begins, just past the bow-shock nose. */
  taperStartRe: 13,
  /** Where the taper reaches the tail slope. */
  taperEndRe: 24,
  /** Log-log slope of the far tail. The foreshortening that pays for the dayside. */
  tailSlope: 0.14,
} as const;

/** The legacy logarithmic branch, unchanged below the anchor. */
function logBranch(radiusRe: number) {
  const altitudeKm = Math.max(0, radiusRe - 1) * RULER_EARTH_RADIUS_KM;
  return 1 + Math.min(2.05, 0.28 * Math.log1p(altitudeKm / 350));
}

/**
 * The log branch's own local log-log slope: f = E(1 + 0.28 ln(1 + a(r-1))),
 * slope = r f'/f with f' = 0.28 E a / (1 + a(r-1)) and a = km-per-Re / 350.
 * Below the surface the drawn radius is pinned to the Earth, so the slope is
 * zero.
 */
function logBranchSlope(radiusRe: number) {
  if (!(radiusRe > 1)) return 0;
  const a = RULER_EARTH_RADIUS_KM / 350;
  const altitudeTerm = 1 + a * Math.max(0, radiusRe - 1);
  return (0.28 * a * radiusRe) / (altitudeTerm * logBranch(radiusRe));
}

/**
 * Where the joint ramp starts, in slope: READ OFF the log branch rather than
 * written down, so the joint stays C1 if the near-Earth curve is ever
 * retuned. Currently 0.1422.
 */
const ANCHOR_SLOPE = logBranchSlope(RADIAL_RULER.anchorRe);

/**
 * Integral of the log-log slope from the anchor to ln(r), in the piecewise
 * regime above the anchor. The taper is smoothstep(t) in t = normalized log
 * radius, whose running integral is t^3 - t^4/2.
 */
function slopeIntegralAbove(lnRadius: number) {
  const { anchorRe, daySlope, noseRampEndRe, taperStartRe, taperEndRe, tailSlope } = RADIAL_RULER;
  const lnAnchor = Math.log(anchorRe);
  const lnRampEnd = Math.log(noseRampEndRe);
  const lnTaperStart = Math.log(taperStartRe);
  const lnTaperEnd = Math.log(taperEndRe);
  // The joint ramp. Its slope is linear in log radius, so its integral is
  // quadratic in the ramp parameter — which is the property that keeps the
  // whole ruler closed-form invertible for the belt volume's shader copy.
  const rampT = Math.min(1, Math.max(0, (lnRadius - lnAnchor) / (lnRampEnd - lnAnchor)));
  let total = (lnRampEnd - lnAnchor)
    * (ANCHOR_SLOPE * rampT + ((daySlope - ANCHOR_SLOPE) * rampT * rampT) / 2);
  if (lnRadius > lnRampEnd) total += daySlope * (Math.min(lnRadius, lnTaperStart) - lnRampEnd);
  if (lnRadius > lnTaperStart) {
    const end = Math.min(lnRadius, lnTaperEnd);
    const t = (end - lnTaperStart) / (lnTaperEnd - lnTaperStart);
    const smoothstepIntegral = t * t * t - (t * t * t * t) / 2;
    total += daySlope * (end - lnTaperStart)
      - (daySlope - tailSlope) * (lnTaperEnd - lnTaperStart) * smoothstepIntegral;
  }
  if (lnRadius > lnTaperEnd) total += tailSlope * (lnRadius - lnTaperEnd);
  return total;
}

/**
 * Where a physical geocentric radius is drawn, in units of the drawn Earth
 * radius. Strictly monotone, so inside/outside readings between any two
 * layers on this ruler are exact in every direction.
 */
export function sharedDisplayRadius(radiusRe: number, earthSceneRadius: number) {
  if (!Number.isFinite(earthSceneRadius) || earthSceneRadius <= 0) {
    throw new RangeError("earthSceneRadius must be a positive finite scene length");
  }
  // True distance: drawn radius is k * physical radius with k = one drawn
  // Earth radius per physical Earth radius. Below the surface the drawn
  // radius pins to the globe, exactly as the teaching scale's log branch does.
  if (activeScale === "true-distance") return earthSceneRadius * Math.max(1, radiusRe);
  if (!(radiusRe > RADIAL_RULER.anchorRe)) return earthSceneRadius * logBranch(radiusRe);
  return earthSceneRadius * logBranch(RADIAL_RULER.anchorRe) * Math.exp(slopeIntegralAbove(Math.log(radiusRe)));
}

/**
 * The ruler's local log-log slope d ln(drawn) / d ln(r). Its reciprocal is the
 * anisotropy — how much transverse displacement is magnified over radial — so
 * a slope of 1 means drawn directions of motion are true directions.
 */
export function sharedRulerLocalSlope(radiusRe: number) {
  // True distance is the identity map in log-log: slope 1 everywhere above
  // the surface, so drawn shape and drawn motion are true by construction.
  if (activeScale === "true-distance") return radiusRe > 1 ? 1 : 0;
  const { anchorRe, daySlope, noseRampEndRe, taperStartRe, taperEndRe, tailSlope } = RADIAL_RULER;
  if (radiusRe > anchorRe) {
    // The joint ramp: slope rises linearly in log radius from the log
    // branch's own value to the dayside's, so a curve crossing the anchor
    // meets no step in direction.
    if (radiusRe < noseRampEndRe) {
      const t = (Math.log(radiusRe) - Math.log(anchorRe)) / (Math.log(noseRampEndRe) - Math.log(anchorRe));
      return ANCHOR_SLOPE + (daySlope - ANCHOR_SLOPE) * t;
    }
    if (radiusRe <= taperStartRe) return daySlope;
    if (radiusRe >= taperEndRe) return tailSlope;
    const t = (Math.log(radiusRe) - Math.log(taperStartRe)) / (Math.log(taperEndRe) - Math.log(taperStartRe));
    return daySlope - (daySlope - tailSlope) * t * t * (3 - 2 * t);
  }
  return logBranchSlope(radiusRe);
}

/**
 * How many pieces a straight PHYSICAL chord must be drawn in for the joint
 * ramp not to turn it into a facet.
 *
 * Curves that choose their own step size in physical space — the traced
 * magnetosphere field lines cap their step at 4 degrees of PHYSICAL direction
 * change, the cusp entry cue walks a fixed number of steps down the funnel —
 * are handed to a radial map whose slope rises 7.03x between the anchor and
 * `noseRampEndRe`. Over that band the drawn image of a straight physical chord
 * is a CURVE, and drawing it as one segment shows as a crease even though the
 * map itself is C1.
 *
 * Measured on the 143 traced field lines, of which 107 cross the anchor: the
 * worst drawn turn in the band was 45.8 degrees with the old slope step, 30.2
 * with the C1 ramp and no subdivision, then 17.7 / 15.2 / 9.9 / 8.5 as the
 * subdivision cap went 8 / 16 / 32 / 64. The bar is the worst turn ELSEWHERE on
 * those same lines, 7.7 degrees — the joint should not be the roughest thing on
 * the line it belongs to — and the series approaches it rather than reaching
 * it, because the drawn curve there genuinely does bend hardest. 32 is where
 * the remaining excess stops being worth vertices: 9.9 degrees, 1.3x the line's
 * own worst, against 5.9x on the shipped build, for 4,797 extra vertices across
 * the whole set. Away from the band this returns 1 and costs nothing.
 */
export function rulerJointBandSegments(fromRadiusRe: number, toRadiusRe: number) {
  if (activeScale === "true-distance") return 1;
  const low = Math.min(fromRadiusRe, toRadiusRe);
  const high = Math.max(fromRadiusRe, toRadiusRe);
  const { anchorRe, noseRampEndRe } = RADIAL_RULER;
  if (high <= anchorRe || low >= noseRampEndRe) return 1;
  const spanned = (Math.min(high, noseRampEndRe) - Math.max(low, anchorRe)) / (noseRampEndRe - anchorRe);
  return Math.max(1, Math.min(32, Math.ceil(spanned * 32)));
}

/**
 * Physical radius from a drawn radius: the exact inverse of
 * `sharedDisplayRadius`. Closed-form on the logarithmic branch; bisection on
 * the piecewise branch, where no closed form exists and none is needed —
 * fifty halvings of a bounded bracket resolve far below any displayable
 * difference.
 */
export function radiusFromSharedDisplayRadius(displayRadius: number, earthSceneRadius: number) {
  if (!Number.isFinite(earthSceneRadius) || earthSceneRadius <= 0) {
    throw new RangeError("earthSceneRadius must be a positive finite scene length");
  }
  if (activeScale === "true-distance") return Math.max(1, displayRadius / earthSceneRadius);
  const anchorDisplay = earthSceneRadius * logBranch(RADIAL_RULER.anchorRe);
  if (!(displayRadius > anchorDisplay)) {
    const normalized = Math.max(0, displayRadius / earthSceneRadius - 1);
    const altitudeKm = 350 * Math.expm1(normalized / 0.28);
    return 1 + altitudeKm / RULER_EARTH_RADIUS_KM;
  }
  let lower: number = RADIAL_RULER.anchorRe;
  let upper: number = RADIAL_RULER.anchorRe * 2;
  for (let guard = 0; guard < 60 && sharedDisplayRadius(upper, earthSceneRadius) < displayRadius; guard += 1) {
    upper *= 2;
  }
  for (let iteration = 0; iteration < 50; iteration += 1) {
    const middle = (lower + upper) / 2;
    if (sharedDisplayRadius(middle, earthSceneRadius) < displayRadius) lower = middle;
    else upper = middle;
  }
  return (lower + upper) / 2;
}
