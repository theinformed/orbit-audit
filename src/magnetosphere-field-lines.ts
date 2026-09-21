/**
 * Three-dimensional magnetospheric field lines, driven by the live solar wind.
 *
 * ## What this is
 *
 * A semi-empirical vacuum-superposition field model — NOT an MHD solution and
 * NOT a Tsyganenko model — built from three citable pieces, every parameter of
 * which is driven by measured upstream data:
 *
 *   1. **Tilted centred dipole.** Moment magnitude from the same IGRF-13
 *      dipole coefficients `dipole-tilt.ts` already carries; tilt from the
 *      same Hapgood (1992) calculation the cusped boundary models use.
 *   2. **Chapman–Ferraro image dipole.** The classic construction for the
 *      magnetopause currents that confine the dayside field: an image dipole
 *      of equal moment placed sunward at twice the standoff distance, with its
 *      x-component mirrored, makes the plane x = standoff an exact zero-normal
 *      -field surface for a tilt-free dipole (Chapman & Ferraro 1931; the
 *      construction as given in Kivelson & Russell, *Introduction to Space
 *      Physics*, 1995, §6.3). It doubles the subsolar field and compresses the
 *      dayside lobes — and it produces the two dayside neutral points, which
 *      are the polar cusps of this model, for free. The standoff it is pinned
 *      to is the **live Shue et al. (1998) subsolar distance**, so rising
 *      dynamic pressure moves the image dipole earthward and visibly
 *      compresses the drawn dayside.
 *   3. **Harris-sheet magnetotail.** A tail field derived from the vector
 *      potential A_y = −B_T · D · ln cosh(z/D) · S(x) · W(y), which yields the
 *      classic Harris (1962) current-sheet profile B_x = B_T tanh(z/D) with a
 *      smooth onset ramp S(x) on the nightside and a dawn–dusk envelope W(y).
 *      Taking B from a curl keeps it exactly divergence-free, ramp and
 *      envelope included. The lobe strength B_T is driven: it scales as
 *      √(Pdyn) from pressure balance across the magnetopause, and it grows
 *      under southward IMF Bz because dayside reconnection loads flux into
 *      the tail (the Dungey cycle; tail-lobe flux loading as in Caan,
 *      McPherron & Russell 1973). The exact parameterisation is stated below
 *      and in docs/SCIENTIFIC-LAYERS.md; it is an illustrative driven
 *      approximation and is labelled as such.
 *
 * Field lines are then traced through the summed field with a fixed-step RK4
 * integrator and **truncated at the live Shue boundary**, so every drawn line
 * lives inside the empirical magnetopause the scene draws around it.
 *
 * ## What it claims and does not claim
 *
 * The model reproduces the *topology* every reference depiction of the
 * magnetosphere shows — compressed dayside loops, open polar caps, cusp
 * funnels where the dayside lines converge, and a stretched two-lobe tail —
 * and its shape responds to the measured drivers in the physically right
 * direction. No individual field-line position is a measurement or an MHD
 * solution, and the module says so in its own metadata. The NOAA BATS-R-US
 * cut planes remain the only *modelled-plasma* fields on the site; these
 * lines are the geometry lesson that surrounds them.
 *
 * This module knows no three.js: it emits polylines in physical GSM Earth
 * radii plus numeric summaries, so the physics is testable headless and the
 * renderer applies the scene's shared radial ruler unchanged.
 */

import {
  IGRF_DIPOLE_G10_NT,
  IGRF_DIPOLE_G11_NT,
  IGRF_DIPOLE_H11_NT,
} from "./dipole-tilt";
import { shueBoundary, shueRadiusRe } from "./magnetopause";

/** Everything the field model is driven by. */
export interface FieldLineDrivers {
  /** Solar-wind dynamic pressure, nPa. */
  dynamicPressureNpa: number;
  /** IMF Bz, nT GSM. */
  bzGsmNt: number;
  /** Geodipole tilt, radians, positive north-pole-sunward. */
  dipoleTiltRad: number;
  /**
   * Optional per-frame calibration of the construction's boundary to the NOAA
   * MHD magnetopause curve (see `fitShueToBoundaryCurve`). When present, the
   * image-dipole standoff and the truncation surface come from the model's own
   * extracted boundary for the loaded frame instead of Shue-from-L1; the tail
   * strength stays driven by the measured upstream pressure and Bz either way.
   */
  boundaryCalibration?: BoundaryCalibration | null;
}

/** One sample of an extracted MHD magnetopause curve: zenith angle → radius. */
export interface BoundaryCurvePoint {
  /** Angle from the subsolar direction, radians, in [0, ~140°]. */
  thetaRad: number;
  /** Boundary radius in that direction, Earth radii. */
  radiusRe: number;
}

/**
 * The result of fitting the Shue functional form to an extracted NOAA MHD
 * magnetopause curve, plus the honesty numbers the card reports.
 */
export interface BoundaryCalibration {
  /** Fitted subsolar standoff r0, Re. */
  standoffRe: number;
  /** Fitted flaring exponent alpha. */
  flaringAlpha: number;
  /** RMS radial residual of the FIT against the MHD samples, Re. */
  rmsResidualRe: number;
  /**
   * RMS radial residual of the L1-driven Shue surface against the same MHD
   * samples — the "before" number the fit is judged against. Null when no
   * L1 Shue reference was supplied.
   */
  referenceRmsResidualRe: number | null;
  /** Fitted r0 minus the curve's own most-subsolar sample, Re. */
  noseResidualRe: number;
  /** How many valid curve samples entered the fit. */
  sampleCount: number;
  /** The MHD frame the curve came from, for the card's label. */
  frameValidAt: string | null;
  source: "noaa-mhd-frame";
}

/** RMS radial mismatch between a Shue surface and a set of curve samples, Re. */
export function shueResidualRmsRe(
  points: readonly BoundaryCurvePoint[],
  standoffRe: number,
  flaringAlpha: number,
): number {
  let sum = 0;
  let count = 0;
  for (const point of points) {
    const model = shueRadiusRe(point.thetaRad, standoffRe, flaringAlpha);
    if (!Number.isFinite(model)) continue;
    sum += (model - point.radiusRe) ** 2;
    count += 1;
  }
  return count > 0 ? Math.sqrt(sum / count) : Number.NaN;
}

/**
 * Fit the Shue et al. (1998) functional form r(θ) = r0 · (2 / (1 + cos θ))^α
 * to an extracted MHD magnetopause curve, by exact linear least squares in
 * log space: ln r = ln r0 + α · ln(2 / (1 + cos θ)). Deterministic, no
 * iteration, no initial guess.
 *
 * The published curves span ±70° from the subsolar direction at 5° steps, so
 * the fit constrains exactly the dayside-and-flank region the construction
 * draws; the far tail stays the Harris sheet's business. Samples beyond 140°
 * or non-finite are ignored. The fit REFUSES (returns null) rather than
 * returning parameters outside the physically plausible window — a garbage
 * frame must fall back to Shue-from-L1, never bend the picture.
 */
export function fitShueToBoundaryCurve(
  points: readonly BoundaryCurvePoint[],
  reference?: { standoffRe: number; flaringAlpha: number } | null,
  frameValidAt?: string | null,
): BoundaryCalibration | null {
  const usable = points.filter((point) =>
    Number.isFinite(point.thetaRad)
    && Number.isFinite(point.radiusRe)
    && point.radiusRe > 2
    && point.thetaRad >= 0
    && point.thetaRad <= (140 * Math.PI) / 180);
  if (usable.length < 8) return null;
  let sumU = 0;
  let sumV = 0;
  let sumUU = 0;
  let sumUV = 0;
  for (const point of usable) {
    const u = Math.log(2 / (1 + Math.cos(point.thetaRad)));
    const v = Math.log(point.radiusRe);
    sumU += u;
    sumV += v;
    sumUU += u * u;
    sumUV += u * v;
  }
  const n = usable.length;
  const denominator = n * sumUU - sumU * sumU;
  if (Math.abs(denominator) < 1e-9) return null;
  const flaringAlpha = (n * sumUV - sumU * sumV) / denominator;
  const standoffRe = Math.exp((sumV - flaringAlpha * sumU) / n);
  if (!Number.isFinite(standoffRe) || !Number.isFinite(flaringAlpha)) return null;
  // Plausibility window: refusal beats a fabricated boundary. The observed
  // magnetopause nose lives roughly between extreme-storm ~4.5 Re and
  // quiet ~14 Re; Shue's own alpha stays near 0.4–0.8.
  if (standoffRe < 4 || standoffRe > 18 || flaringAlpha < 0.2 || flaringAlpha > 1.1) return null;
  const mostSubsolar = usable.reduce((best, point) => (point.thetaRad < best.thetaRad ? point : best));
  return {
    standoffRe,
    flaringAlpha,
    rmsResidualRe: shueResidualRmsRe(usable, standoffRe, flaringAlpha),
    referenceRmsResidualRe: reference
      ? shueResidualRmsRe(usable, reference.standoffRe, reference.flaringAlpha)
      : null,
    noseResidualRe: standoffRe - mostSubsolar.radiusRe,
    sampleCount: usable.length,
    frameValidAt: frameValidAt ?? null,
    source: "noaa-mhd-frame",
  };
}

/**
 * Surface equatorial dipole field, nT, from the IGRF-13 dipole terms already
 * pinned in `dipole-tilt.ts`: B0 = √(g10² + g11² + h11²).
 */
export const DIPOLE_B0_NT = Math.hypot(IGRF_DIPOLE_G10_NT, IGRF_DIPOLE_G11_NT, IGRF_DIPOLE_H11_NT);

/** Harris-sheet half-thickness, Re. Order of the observed plasma-sheet half-thickness. */
export const TAIL_SHEET_HALF_THICKNESS_RE = 3;

/** Dawn–dusk half-width of the tail-field envelope, Re. */
export const TAIL_SHEET_HALF_WIDTH_RE = 18;

/**
 * The driven tail-lobe field strength, nT.
 *
 * `B_T = 18 nT · √(Pdyn / 2 nPa) · (1 + 0.5 · clamp(−Bz/5, 0, 2.4))`, capped
 * at 45 nT. The √Pdyn factor is pressure balance across the boundary; the Bz
 * factor is southward-IMF flux loading, saturating near Bz = −12 nT. The
 * constants are chosen so a quiet tail sits near the observed ~15–20 nT lobe
 * field at 15–25 Re and a strong storm roughly doubles it — an illustrative
 * driven parameterisation, stated here and in the layer contract.
 */
export function tailLobeFieldNt(drivers: FieldLineDrivers): number {
  const pressure = Math.max(0.05, drivers.dynamicPressureNpa);
  const southward = Math.min(2.4, Math.max(0, -drivers.bzGsmNt / 5));
  return Math.min(45, 18 * Math.sqrt(pressure / 2) * (1 + 0.5 * southward));
}

export interface CompressedDipoleParameters {
  /** Subsolar standoff, Re — the image-dipole plane. From the MHD calibration when one is loaded, else the live Shue fit. */
  standoffRe: number;
  /** Flaring exponent of the truncation surface, from the same source. */
  flaringAlpha: number;
  /** Where the boundary geometry came from, for the card's label. */
  boundarySource: "noaa-mhd-frame" | "shue-l1";
  /** Dipole moment direction (unit), GSM. */
  momentX: number;
  momentY: number;
  momentZ: number;
  /** Image dipole position on the Sun–Earth line, Re. */
  imageXRe: number;
  /** Image moment direction (unit), GSM: x-component mirrored. */
  imageMomentX: number;
  imageMomentY: number;
  imageMomentZ: number;
  /** Driven Harris tail strength, nT. */
  tailFieldNt: number;
  drivers: FieldLineDrivers;
}

/**
 * Resolve the drivers into model parameters, or null when the Shue boundary
 * itself cannot be evaluated — the same refusal the boundary layer makes.
 */
export function compressedDipoleParameters(drivers: FieldLineDrivers): CompressedDipoleParameters | null {
  if (!Number.isFinite(drivers.dipoleTiltRad)) return null;
  const shue = shueBoundary(drivers.dynamicPressureNpa, drivers.bzGsmNt);
  if (!shue) return null;
  // The MHD frame calibration, when loaded, replaces the boundary GEOMETRY
  // only — the standoff the image dipole is pinned to and the truncation
  // surface. The tail strength stays driven by the measured upstream state,
  // which is also what the fit's own frame was driven by upstream at NOAA.
  const calibration = drivers.boundaryCalibration ?? null;
  const standoffRe = calibration?.standoffRe ?? shue.subsolarStandoffRe;
  const flaringAlpha = calibration?.flaringAlpha ?? shue.flaringAlpha;
  const tilt = drivers.dipoleTiltRad;
  // Dipole axis d̂ = (sin ψ, 0, cos ψ); the moment points along −d̂ (Earth's
  // field emerges from the southern hemisphere and enters the northern).
  const momentX = -Math.sin(tilt);
  const momentZ = -Math.cos(tilt);
  return {
    standoffRe,
    flaringAlpha,
    boundarySource: calibration ? "noaa-mhd-frame" : "shue-l1",
    momentX,
    momentY: 0,
    momentZ,
    imageXRe: 2 * standoffRe,
    // Mirror across the plane x = standoff: flip the x-component.
    imageMomentX: -momentX,
    imageMomentY: 0,
    imageMomentZ: momentZ,
    tailFieldNt: tailLobeFieldNt(drivers),
    drivers,
  };
}

function addDipoleField(
  out: { x: number; y: number; z: number },
  xRe: number,
  yRe: number,
  zRe: number,
  momentX: number,
  momentY: number,
  momentZ: number,
) {
  const r2 = xRe * xRe + yRe * yRe + zRe * zRe;
  if (r2 < 1e-8) return;
  const r = Math.sqrt(r2);
  const r5 = r2 * r2 * r;
  // B = (B0 / r^5) · (3 (m̂·r) r − r² m̂), with B0 the surface equatorial field.
  const mDotR = momentX * xRe + momentY * yRe + momentZ * zRe;
  const scale = DIPOLE_B0_NT / r5;
  out.x += scale * (3 * mDotR * xRe - r2 * momentX);
  out.y += scale * (3 * mDotR * yRe - r2 * momentY);
  out.z += scale * (3 * mDotR * zRe - r2 * momentZ);
}

/** Smoothstep in [0, 1]. */
function smooth01(t: number) {
  const clamped = Math.min(1, Math.max(0, t));
  return clamped * clamped * (3 - 2 * clamped);
}

/** Where the nightside tail ramp starts and completes, GSM x in Re. */
export const TAIL_RAMP_START_X_RE = -3;
export const TAIL_RAMP_FULL_X_RE = -12;

/**
 * The total model field at a point, nT in GSM.
 *
 * Dipole + image dipole + Harris-sheet tail from the vector potential
 * described in the module header. The tail's Bz component is the exact
 * −∂A_y/∂x of the same potential, so the summed field stays solenoidal.
 */
export function compressedDipoleFieldNt(
  parameters: CompressedDipoleParameters,
  xRe: number,
  yRe: number,
  zRe: number,
): { x: number; y: number; z: number } {
  const field = { x: 0, y: 0, z: 0 };
  addDipoleField(field, xRe, yRe, zRe, parameters.momentX, parameters.momentY, parameters.momentZ);
  addDipoleField(
    field,
    xRe - parameters.imageXRe,
    yRe,
    zRe,
    parameters.imageMomentX,
    parameters.imageMomentY,
    parameters.imageMomentZ,
  );

  // Harris tail. S(x): 0 at the ramp start, 1 tailward of the full point,
  // smoothstep between. W(y): sech envelope. Both enter through A_y, so both
  // appear in Bz through the exact x-derivative of the ramp.
  const D = TAIL_SHEET_HALF_THICKNESS_RE;
  const rampSpan = TAIL_RAMP_START_X_RE - TAIL_RAMP_FULL_X_RE;
  const t = (TAIL_RAMP_START_X_RE - xRe) / rampSpan;
  if (t > 0) {
    const envelope = 1 / Math.cosh(yRe / TAIL_SHEET_HALF_WIDTH_RE);
    const ramp = smooth01(t);
    const tanh = Math.tanh(zRe / D);
    field.x += parameters.tailFieldNt * tanh * ramp * envelope;
    if (t < 1) {
      // dS/dx = −smoothstep'(t)/rampSpan; Bz = −∂A_y/∂x · … sign worked out so
      // the closure field across the ramp is northward, bending lobe lines
      // over the sheet the way the tail's own Bz does.
      const clamped = Math.min(1, Math.max(0, t));
      const dSdT = 6 * clamped * (1 - clamped);
      const lnCosh = Math.log(Math.cosh(zRe / D));
      field.z += parameters.tailFieldNt * D * lnCosh * (dSdT / rampSpan) * envelope;
    }
  }
  return field;
}

export interface TracedFieldLine {
  /** Polyline in physical GSM Re, ordered from the northern end southward. */
  pointsGsmRe: Array<{ x: number; y: number; z: number }>;
  /** log10(|B| nT) per point, for the renderer's colour ramp. */
  logFieldNt: number[];
  /** Magnetic latitude of the seed footpoint, degrees (dipole frame). */
  seedLatitudeDeg: number;
  /** Seed magnetic local-time longitude, degrees (0 = noon). */
  seedLongitudeDeg: number;
  /**
   * `closed` returned to the surface in the opposite hemisphere; `open`
   * reached the tail cutoff or left through the polar cap; `boundary` ended
   * on the Shue surface (dayside lines interrupted by the magnetopause).
   */
  topology: "closed" | "open" | "boundary";
  /** Greatest geocentric distance reached, Re. */
  apexRadiusRe: number;
  /** GSM x of the sunward-most point, Re. */
  sunwardMostXRe: number;
  /** GSM x of the tailward-most point, Re. */
  tailwardMostXRe: number;
}

export interface FieldLineTraceOptions {
  /** MLT spokes around the dipole axis. */
  longitudeCount?: number;
  /** Seed magnetic latitudes, degrees. */
  seedLatitudesDeg?: readonly number[];
  /** Where the tail is cut off, GSM x in Re (negative). */
  tailCutoffXRe?: number;
  /** Hard step limit per line. */
  maximumSteps?: number;
}

const DEFAULT_SEED_LATITUDES_DEG = [58, 62, 65, 67.5, 69.5, 71.5, 73.5, 75.5, 77.5, 79.5] as const;

const SEED_RADIUS_RE = 1.08;

/**
 * Truncation surface: the live Shue magnetopause, with a small outward
 * tolerance so lines that merely graze the boundary are not clipped.
 */
function outsideShue(parameters: CompressedDipoleParameters, x: number, y: number, z: number) {
  const r = Math.hypot(x, y, z);
  if (r < 1.5) return false;
  const theta = Math.acos(Math.min(1, Math.max(-1, x / r)));
  const boundary = shueRadiusRe(theta, parameters.standoffRe, parameters.flaringAlpha);
  return Number.isFinite(boundary) && r > boundary * 1.02;
}

/** Unit direction of the traced field, ±B/|B|, or zeros at a null. */
function fieldDirection(
  parameters: CompressedDipoleParameters,
  x: number,
  y: number,
  z: number,
  sign: number,
) {
  const field = compressedDipoleFieldNt(parameters, x, y, z);
  const magnitude = Math.hypot(field.x, field.y, field.z);
  if (magnitude < 1e-12) return { x: 0, y: 0, z: 0 };
  const scale = sign / magnitude;
  return { x: field.x * scale, y: field.y * scale, z: field.z * scale };
}

/**
 * Maximum tangent turn per traced (and therefore per drawn) segment, radians.
 *
 * The drawn polyline uses the raw integration points as vertices, so the step
 * size IS the tessellation density. A radius-only step (ds = 0.09·r capped at
 * 0.45 Re) made each far-field segment a ~0.45 Re straight chord — integration
 * accuracy was fine, but wherever the line still curves (apex of mid-latitude
 * lines, the cusp funnels, the tail hinge) the polygon showed as visible
 * kinks. Capping the per-step direction change keeps every drawn corner below
 * this angle; `tests/magnetosphere-field-lines.test.ts` measures it.
 */
export const FIELD_LINE_MAX_TURN_RAD = (4 * Math.PI) / 180;

/** Angle between two unit directions, radians. */
function turnAngleRad(
  a: { x: number; y: number; z: number },
  b: { x: number; y: number; z: number },
) {
  const dot = a.x * b.x + a.y * b.y + a.z * b.z;
  return Math.acos(Math.min(1, Math.max(-1, dot)));
}

/**
 * The radius-driven step, additionally capped so the field direction turns by
 * at most `FIELD_LINE_MAX_TURN_RAD` across the step. The turn is estimated
 * from the direction at the start and at the tentative endpoint, then the cap
 * is re-checked at the shrunken step until it converges. The floor exists
 * only to guarantee termination against the model's exact nulls; it is far
 * below the sheet-hairpin curvature scale (~0.02–0.04 Re at the deep-tail
 * apex of a storm-stretched line), so the cap — not the floor — governs
 * everywhere a corner could be drawn. The turn cap also bounds total work:
 * a line's step count is at most (total tangent turn / cap) plus (arc length
 * / radius-driven ds), both small.
 */
const MINIMUM_STEP_RE = 0.004;

function curvatureCappedStep(
  parameters: CompressedDipoleParameters,
  position: { x: number; y: number; z: number },
  sign: number,
) {
  const r = Math.hypot(position.x, position.y, position.z);
  let ds = Math.max(MINIMUM_STEP_RE, Math.min(0.45, 0.09 * r));
  const start = fieldDirection(parameters, position.x, position.y, position.z, sign);
  if (start.x === 0 && start.y === 0 && start.z === 0) return ds;
  for (let refinement = 0; refinement < 4 && ds > MINIMUM_STEP_RE; refinement += 1) {
    const ahead = fieldDirection(
      parameters,
      position.x + start.x * ds,
      position.y + start.y * ds,
      position.z + start.z * ds,
      sign,
    );
    if (ahead.x === 0 && ahead.y === 0 && ahead.z === 0) break;
    const turn = turnAngleRad(start, ahead);
    if (turn <= FIELD_LINE_MAX_TURN_RAD) break;
    // Aim slightly under the cap so the re-check converges instead of
    // oscillating around it.
    ds = Math.max(MINIMUM_STEP_RE, ds * (0.85 * FIELD_LINE_MAX_TURN_RAD / turn));
  }
  return ds;
}

/** One RK4 step of the direction field b̂ = ±B/|B|, arc length ds in Re. */
function rk4Step(
  parameters: CompressedDipoleParameters,
  position: { x: number; y: number; z: number },
  sign: number,
  ds: number,
) {
  const direction = (x: number, y: number, z: number) => fieldDirection(parameters, x, y, z, sign);
  const k1 = direction(position.x, position.y, position.z);
  const k2 = direction(position.x + k1.x * ds / 2, position.y + k1.y * ds / 2, position.z + k1.z * ds / 2);
  const k3 = direction(position.x + k2.x * ds / 2, position.y + k2.y * ds / 2, position.z + k2.z * ds / 2);
  const k4 = direction(position.x + k3.x * ds, position.y + k3.y * ds, position.z + k3.z * ds);
  return {
    x: position.x + (ds / 6) * (k1.x + 2 * k2.x + 2 * k3.x + k4.x),
    y: position.y + (ds / 6) * (k1.y + 2 * k2.y + 2 * k3.y + k4.y),
    z: position.z + (ds / 6) * (k1.z + 2 * k2.z + 2 * k3.z + k4.z),
  };
}

function traceFromSeed(
  parameters: CompressedDipoleParameters,
  seed: { x: number; y: number; z: number },
  tailCutoffXRe: number,
  maximumSteps: number,
): Omit<TracedFieldLine, "seedLatitudeDeg" | "seedLongitudeDeg"> | null {
  const initial = compressedDipoleFieldNt(parameters, seed.x, seed.y, seed.z);
  const radialDot = initial.x * seed.x + initial.y * seed.y + initial.z * seed.z;
  // Step in whichever field direction initially leads away from the Earth.
  const sign = radialDot > 0 ? 1 : -1;
  const points: Array<{ x: number; y: number; z: number }> = [{ ...seed }];
  const logField: number[] = [Math.log10(Math.max(1e-3, Math.hypot(initial.x, initial.y, initial.z)))];
  let position = { ...seed };
  let topology: TracedFieldLine["topology"] = "open";
  let apexRadiusRe = SEED_RADIUS_RE;
  let sunwardMostXRe = seed.x;
  let tailwardMostXRe = seed.x;
  for (let step = 0; step < maximumSteps; step += 1) {
    const ds = curvatureCappedStep(parameters, position, sign);
    const previous = position;
    position = rk4Step(parameters, position, sign, ds);
    let radius = Math.hypot(position.x, position.y, position.z);
    if (radius <= 1.02) {
      // The landing step can overshoot below the surface; interpolate the
      // crossing back onto r = 1.02 so no drawn point sits inside the Earth.
      const previousRadius = Math.hypot(previous.x, previous.y, previous.z);
      const fraction = previousRadius > radius
        ? Math.min(1, Math.max(0, (previousRadius - 1.02) / (previousRadius - radius)))
        : 1;
      position = {
        x: previous.x + (position.x - previous.x) * fraction,
        y: previous.y + (position.y - previous.y) * fraction,
        z: previous.z + (position.z - previous.z) * fraction,
      };
      radius = Math.hypot(position.x, position.y, position.z);
    }
    apexRadiusRe = Math.max(apexRadiusRe, radius);
    sunwardMostXRe = Math.max(sunwardMostXRe, position.x);
    tailwardMostXRe = Math.min(tailwardMostXRe, position.x);
    const field = compressedDipoleFieldNt(parameters, position.x, position.y, position.z);
    points.push({ ...position });
    logField.push(Math.log10(Math.max(1e-3, Math.hypot(field.x, field.y, field.z))));
    if (radius <= 1.03) {
      topology = "closed";
      break;
    }
    if (position.x <= tailCutoffXRe) {
      topology = "open";
      break;
    }
    if (outsideShue(parameters, position.x, position.y, position.z)) {
      // Trim the crossing step back onto the truncation surface so no drawn
      // point sits outside the boundary the scene draws around these lines.
      let inside = 0;
      let outside = 1;
      for (let iteration = 0; iteration < 20; iteration += 1) {
        const middle = (inside + outside) / 2;
        const x = previous.x + (position.x - previous.x) * middle;
        const y = previous.y + (position.y - previous.y) * middle;
        const z = previous.z + (position.z - previous.z) * middle;
        if (outsideShue(parameters, x, y, z)) outside = middle;
        else inside = middle;
      }
      const trimmed = {
        x: previous.x + (position.x - previous.x) * inside,
        y: previous.y + (position.y - previous.y) * inside,
        z: previous.z + (position.z - previous.z) * inside,
      };
      points[points.length - 1] = trimmed;
      sunwardMostXRe = Math.max(sunwardMostXRe, trimmed.x);
      tailwardMostXRe = Math.min(tailwardMostXRe, trimmed.x);
      topology = "boundary";
      break;
    }
  }
  if (points.length < 8) return null;
  return { pointsGsmRe: points, logFieldNt: logField, topology, apexRadiusRe, sunwardMostXRe, tailwardMostXRe };
}

/** A seed point at magnetic latitude/longitude in the tilted dipole frame, GSM. */
function seedPointGsm(tiltRad: number, latitudeDeg: number, longitudeDeg: number) {
  const latitude = (latitudeDeg * Math.PI) / 180;
  const longitude = (longitudeDeg * Math.PI) / 180;
  // Dipole frame: ẑ_d along the dipole axis, x̂_d in the GSM x–z plane leaning
  // sunward. Longitude 0 faces the Sun (noon MLT).
  const xd = SEED_RADIUS_RE * Math.cos(latitude) * Math.cos(longitude);
  const yd = SEED_RADIUS_RE * Math.cos(latitude) * Math.sin(longitude);
  const zd = SEED_RADIUS_RE * Math.sin(latitude);
  const cos = Math.cos(tiltRad);
  const sin = Math.sin(tiltRad);
  // Rotate the dipole frame about GSM ŷ by the tilt: axis (0,0,1) → (sin ψ, 0, cos ψ).
  return { x: xd * cos + zd * sin, y: yd, z: -xd * sin + zd * cos };
}

export interface FieldLineSummary {
  /** Standoff used for the image dipole, Re (MHD-calibrated or Shue). */
  standoffRe: number;
  /** Where the boundary geometry came from. Absent in older callers. */
  boundarySource?: "noaa-mhd-frame" | "shue-l1";
  /** The active MHD calibration, when one drove the geometry. */
  calibration?: BoundaryCalibration | null;
  /** Driven Harris lobe field, nT. */
  tailFieldNt: number;
  /** Sunward-most x reached by any closed line, Re: the drawn dayside "nose". */
  closedNoseXRe: number;
  /** Highest seed latitude that still closed, per the noon meridian, degrees. */
  lastClosedNoonLatitudeDeg: number;
  /** Lowest seed latitude that is open at midnight, degrees. */
  firstOpenMidnightLatitudeDeg: number;
  /** Count per topology. */
  closedCount: number;
  openCount: number;
  boundaryCount: number;
  /** Mean tailward reach of open lines, Re. */
  meanOpenTailReachXRe: number;
}

export interface TracedMagnetosphere {
  lines: TracedFieldLine[];
  /**
   * Dedicated noon and midnight meridian traces, per seed latitude, northern
   * hemisphere. NOT part of `lines`: the drawn set staggers its longitudes
   * (see below), so these exist to keep the summary's noon/midnight numbers
   * exact — and to give tests named meridian lines to interrogate.
   */
  noonMidnightProbes: TracedFieldLine[];
  summary: FieldLineSummary;
  parameters: CompressedDipoleParameters;
  /** The tail cutoff the trace actually used, GSM x in Re — recorded so the
   * integrity checks can verify "open" endpoints against the real plane
   * instead of re-deriving the default. */
  tailCutoffXRe: number;
}

/**
 * Trace the full line set.
 *
 * Seeds walk both hemispheres so the two polar caps and the two tail lobes
 * are both drawn. Closed lines are kept only from their northern seed —
 * tracing the same closed line from its southern footpoint would draw it
 * twice at double brightness.
 *
 * The longitude spokes are staggered by a golden-angle fraction per latitude
 * ring. When every latitude shared the same twelve longitudes, each shared
 * meridian plane held ~20 coplanar lines, and whenever a camera direction lay
 * in one of those planes the whole stack projected onto a single screen line
 * — an additive-blended white streak through the planet that read as an
 * artifact (it was exactly aligned in the polar view). Staggering removes
 * every shared plane while leaving the latitude coverage untouched.
 */
export function traceMagnetosphereFieldLines(
  drivers: FieldLineDrivers,
  options: FieldLineTraceOptions = {},
): TracedMagnetosphere | null {
  const parameters = compressedDipoleParameters(drivers);
  if (!parameters) return null;
  const longitudeCount = Math.max(4, Math.floor(options.longitudeCount ?? 12));
  const latitudes = options.seedLatitudesDeg ?? DEFAULT_SEED_LATITUDES_DEG;
  const tailCutoffXRe = Math.min(-10, options.tailCutoffXRe ?? -40);
  const maximumSteps = Math.max(200, Math.floor(options.maximumSteps ?? 2400));

  const lines: TracedFieldLine[] = [];
  let closedCount = 0;
  let openCount = 0;
  let boundaryCount = 0;
  const openTailReach: number[] = [];
  const spokeSpacingDeg = 360 / longitudeCount;
  const GOLDEN_FRACTION = 0.381966; // 2 - phi

  for (const hemisphereSign of [1, -1] as const) {
    for (let latitudeIndex = 0; latitudeIndex < latitudes.length; latitudeIndex += 1) {
      const latitude = latitudes[latitudeIndex]!;
      const offsetDeg = ((latitudeIndex * GOLDEN_FRACTION) % 1) * spokeSpacingDeg;
      for (let spoke = 0; spoke < longitudeCount; spoke += 1) {
        const longitudeDeg = (spoke * spokeSpacingDeg + offsetDeg) % 360;
        const seed = seedPointGsm(drivers.dipoleTiltRad, hemisphereSign * latitude, longitudeDeg);
        const traced = traceFromSeed(parameters, seed, tailCutoffXRe, maximumSteps);
        if (!traced) continue;
        if (traced.topology === "closed" && hemisphereSign === -1) continue;
        lines.push({
          ...traced,
          seedLatitudeDeg: hemisphereSign * latitude,
          seedLongitudeDeg: longitudeDeg,
        });
        if (traced.topology === "closed") closedCount += 1;
        else if (traced.topology === "open") {
          openCount += 1;
          // Only genuinely tailward-open lines belong in the tail-reach
          // statistic; boundary-truncated dayside lines would dilute it.
          openTailReach.push(traced.tailwardMostXRe);
        } else boundaryCount += 1;
      }
    }
  }
  if (lines.length === 0) return null;

  // The exact-meridian probes that carry the summary's named numbers.
  const noonMidnightProbes: TracedFieldLine[] = [];
  let closedNoseXRe = 0;
  let lastClosedNoonLatitudeDeg = Number.NaN;
  let firstOpenMidnightLatitudeDeg = Number.NaN;
  for (const latitude of latitudes) {
    for (const longitudeDeg of [0, 180] as const) {
      const seed = seedPointGsm(drivers.dipoleTiltRad, latitude, longitudeDeg);
      const traced = traceFromSeed(parameters, seed, tailCutoffXRe, maximumSteps);
      if (!traced) continue;
      noonMidnightProbes.push({ ...traced, seedLatitudeDeg: latitude, seedLongitudeDeg: longitudeDeg });
      if (longitudeDeg === 0 && traced.topology === "closed") {
        closedNoseXRe = Math.max(closedNoseXRe, traced.sunwardMostXRe);
        if (!Number.isFinite(lastClosedNoonLatitudeDeg) || latitude > lastClosedNoonLatitudeDeg) {
          lastClosedNoonLatitudeDeg = latitude;
        }
      }
      if (longitudeDeg === 180 && traced.topology !== "closed"
        && (!Number.isFinite(firstOpenMidnightLatitudeDeg) || latitude < firstOpenMidnightLatitudeDeg)) {
        firstOpenMidnightLatitudeDeg = latitude;
      }
    }
  }

  return {
    lines,
    noonMidnightProbes,
    parameters,
    tailCutoffXRe,
    summary: {
      standoffRe: parameters.standoffRe,
      boundarySource: parameters.boundarySource,
      calibration: drivers.boundaryCalibration ?? null,
      tailFieldNt: parameters.tailFieldNt,
      closedNoseXRe,
      lastClosedNoonLatitudeDeg,
      firstOpenMidnightLatitudeDeg,
      closedCount,
      openCount,
      boundaryCount,
      meanOpenTailReachXRe: openTailReach.length
        ? openTailReach.reduce((sum, value) => sum + value, 0) / openTailReach.length
        : Number.NaN,
    },
  };
}

/**
 * The model's own dayside neutral point — the polar cusp of the
 * Chapman–Ferraro construction, found rather than asserted: the |B| minimum
 * of the summed field over the dayside noon meridian. Exported so a test can
 * prove the cusp exists, sits sunward at mid-to-high latitude, and is a
 * genuine near-null instead of being taken on faith from a picture.
 */
export function daysideNeutralPointGsm(
  parameters: CompressedDipoleParameters,
  hemisphere: "north" | "south",
): { xRe: number; zRe: number; radiusRe: number; zenithDeg: number; fieldNt: number } {
  const sign = hemisphere === "north" ? 1 : -1;
  const reach = parameters.standoffRe * 1.4;
  let best = { xRe: Number.NaN, zRe: Number.NaN, fieldNt: Number.POSITIVE_INFINITY };
  const probe = (xRe: number, zRe: number) => {
    const field = compressedDipoleFieldNt(parameters, xRe, 0, zRe);
    const magnitude = Math.hypot(field.x, field.y, field.z);
    if (magnitude < best.fieldNt) best = { xRe, zRe, fieldNt: magnitude };
  };
  for (let xRe = 0.5; xRe <= reach; xRe += 0.2) {
    for (let z = 0.5; z <= reach; z += 0.2) {
      probe(xRe, sign * z);
    }
  }
  // One local refinement pass around the coarse minimum.
  const coarse = { ...best };
  for (let dx = -0.2; dx <= 0.2; dx += 0.02) {
    for (let dz = -0.2; dz <= 0.2; dz += 0.02) {
      probe(coarse.xRe + dx, coarse.zRe + dz);
    }
  }
  const radiusRe = Math.hypot(best.xRe, best.zRe);
  return {
    xRe: best.xRe,
    zRe: best.zRe,
    radiusRe,
    zenithDeg: (Math.atan2(Math.abs(best.zRe), best.xRe) * 180) / Math.PI,
    fieldNt: best.fieldNt,
  };
}

/**
 * The log10(|B| nT) range the renderer's colour ramp and the legend both
 * read, so the two can never silently disagree about what a colour means.
 */
export const FIELD_LINE_DISPLAY_LOG_RANGE: readonly [number, number] = [0.3, 4.5];

/**
 * ## The drawn end-fade of truncated lines
 *
 * Open lines stop at the tail cutoff and boundary lines stop on the Shue
 * surface. Both stops are limits of the model domain, not physics — a lobe
 * line really continues far past x = −40 Re, and a boundary line hands over to
 * the magnetosheath draping this model does not contain. Drawn at full
 * brightness, those ends read as broken wires (Sean flagged exactly this).
 * The empirical boundary surfaces already fade their far cutoff for the same
 * reason ("an arbitrary cutoff never reads as a physical cap" —
 * `boundaryMaterial` in src/globe.ts); these constants apply the same
 * principle to the lines: the drawn OPACITY ramps to zero over the last few
 * Re of arc length, while the traced GEOMETRY is untouched — the guided
 * solar-wind particles ride the exact polylines, faded or not.
 *
 * Open lines get the longer ramp because the tail cutoff is the harsher
 * artifact (a flat plane through smooth lobes); boundary-truncated lines end
 * on a surface the scene actually draws, so they only need enough fade to
 * dissolve into it.
 */
export const OPEN_LINE_END_FADE_ARC_RE = 6;
export const BOUNDARY_LINE_END_FADE_ARC_RE = 2.5;

/**
 * Drawn opacity multiplier near a truncated line's cut end: 0 at the cut,
 * back to 1 once `remainingArcRe` (arc length still ahead before the cut, in
 * physical Re) exceeds the topology's fade ramp. Closed lines are never
 * faded here — both their ends are real footpoints, handled by the renderer's
 * footpoint fade.
 */
export function truncatedEndFade(
  topology: TracedFieldLine["topology"],
  remainingArcRe: number,
): number {
  if (topology === "closed") return 1;
  const rampRe = topology === "open" ? OPEN_LINE_END_FADE_ARC_RE : BOUNDARY_LINE_END_FADE_ARC_RE;
  const t = Math.min(1, Math.max(0, remainingArcRe / rampRe));
  return t * t * (3 - 2 * t);
}

/**
 * ## Runtime integrity guard
 *
 * The master invariant of a drawn field line: every segment must be parallel
 * to the model field at its own midpoint. A set of polylines that all satisfy
 * this cannot cross each other in 3-D away from the field's nulls, cannot
 * self-intersect, and cannot kink — a single-valued vector field has one
 * direction per point. The full pairwise proximity proof lives in
 * tests/magnetosphere-field-integrity.test.ts (spatial hash over every
 * segment pair); it is far too heavy for the browser. This guard is the
 * cheap per-rebuild subset: strided faithfulness plus exact endpoint
 * topology, Earth clearance and truncation discipline for every line.
 *
 * If it fails, the renderer must draw NOTHING for this layer and say why —
 * the same refusal grammar the boundary fit already uses — never impossible
 * geometry.
 */
export interface FieldLineIntegrityReport {
  ok: boolean;
  /** Machine-readable failure class, null when ok. */
  reason:
    | "segment-field-misalignment"
    | "endpoint-topology-mismatch"
    | "earth-clearance"
    | "truncation-overrun"
    | null;
  /** Faithfulness segments actually evaluated (strided). */
  checkedSegmentCount: number;
  /** Worst angle between a checked segment and the field at its midpoint, degrees. */
  worstAlignmentDeg: number;
  misalignedSegmentCount: number;
  /** Endpoint-topology + Earth-clearance + truncation violations, all lines. */
  structuralViolationCount: number;
}

/**
 * Faithfulness tolerance, radians: 1.5 × the tracer's own 4° per-step
 * curvature cap — the same slack factor the drawn-corner test uses. For a
 * smooth arc the chord is parallel to the midpoint tangent (the first-order
 * term cancels), so the residual is the cap-refinement's slack plus RK4
 * error; the measured worst over the full driver grid (quiet, moderate,
 * storm peak, both solstices) is 1.8°, giving this limit >3× margin while
 * still rejecting any segment that visibly disagrees with the field.
 */
export const FIELD_LINE_ALIGNMENT_TOLERANCE_RAD = 1.5 * FIELD_LINE_MAX_TURN_RAD;

/**
 * No vertex may come below this radius. The tracer lands lines on an
 * r = 1.02 shell by linear interpolation along the last step's chord, and a
 * chord dips below the arc by at most chord²/8r ≈ 1.3e-3 Re for the ~0.1 Re
 * landing steps — so the honest floor is the shell minus that dip, still
 * 0.018 Re (115 km) above the actual surface at r = 1.
 */
const EARTH_CLEARANCE_MIN_RADIUS_RE = 1.018;
/** A boundary-truncated end must sit within this of the truncation surface, Re. */
const BOUNDARY_END_TOLERANCE_RE = 0.02;

function segmentAlignmentRad(
  parameters: CompressedDipoleParameters,
  a: { x: number; y: number; z: number },
  b: { x: number; y: number; z: number },
  sign: number,
): number | null {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const dz = b.z - a.z;
  const length = Math.hypot(dx, dy, dz);
  if (length < 1e-9) return null;
  const field = compressedDipoleFieldNt(
    parameters,
    (a.x + b.x) / 2,
    (a.y + b.y) / 2,
    (a.z + b.z) / 2,
  );
  const magnitude = Math.hypot(field.x, field.y, field.z);
  // At a genuine near-null the direction is undefined; the tracer's step
  // floor exists for the same reason. Skip rather than judge noise.
  if (magnitude < 1e-6) return null;
  const dot = (dx * field.x + dy * field.y + dz * field.z) * sign / (length * magnitude);
  return Math.acos(Math.min(1, Math.max(-1, dot)));
}

/** The trace direction sign of a line, recovered from its first usable segment. */
function lineTraceSign(
  parameters: CompressedDipoleParameters,
  line: TracedFieldLine,
): number {
  const points = line.pointsGsmRe;
  for (let index = 1; index < points.length; index += 1) {
    const angle = segmentAlignmentRad(parameters, points[index - 1]!, points[index]!, 1);
    if (angle === null) continue;
    return angle <= Math.PI / 2 ? 1 : -1;
  }
  return 1;
}

export function verifyTracedMagnetosphere(
  traced: TracedMagnetosphere,
  options: { segmentStride?: number } = {},
): FieldLineIntegrityReport {
  const stride = Math.max(1, Math.floor(options.segmentStride ?? 7));
  const parameters = traced.parameters;
  let checkedSegmentCount = 0;
  let worstAlignmentRad = 0;
  let misalignedSegmentCount = 0;
  let endpointViolationCount = 0;
  let earthViolationCount = 0;
  let truncationViolationCount = 0;

  const allLines = [...traced.lines, ...traced.noonMidnightProbes];
  for (const line of allLines) {
    const points = line.pointsGsmRe;
    if (points.length < 2) {
      endpointViolationCount += 1;
      continue;
    }

    // Endpoint topology: every line starts on the seed shell; a closed line
    // lands back on the tracer's r = 1.02 landing shell, an open line ends on
    // the tail-cutoff plane, a boundary line ends on the truncation surface.
    const first = points[0]!;
    const last = points[points.length - 1]!;
    const firstRadius = Math.hypot(first.x, first.y, first.z);
    const lastRadius = Math.hypot(last.x, last.y, last.z);
    if (Math.abs(firstRadius - SEED_RADIUS_RE) > 1e-6) endpointViolationCount += 1;
    if (line.topology === "closed") {
      if (lastRadius > 1.03 + 1e-9) endpointViolationCount += 1;
    } else if (line.topology === "open") {
      if (last.x > traced.tailCutoffXRe + 1e-9) endpointViolationCount += 1;
    } else {
      const theta = Math.acos(Math.min(1, Math.max(-1, last.x / Math.max(1e-9, lastRadius))));
      const surface = shueRadiusRe(theta, parameters.standoffRe, parameters.flaringAlpha) * 1.02;
      if (!Number.isFinite(surface) || Math.abs(lastRadius - surface) > BOUNDARY_END_TOLERANCE_RE) {
        endpointViolationCount += 1;
      }
    }

    // Earth clearance and truncation discipline: every vertex, no sampling —
    // these are single hypot/pow checks and the whole sweep costs ~1 ms.
    for (let index = 0; index < points.length; index += 1) {
      const point = points[index]!;
      const radius = Math.hypot(point.x, point.y, point.z);
      if (radius < EARTH_CLEARANCE_MIN_RADIUS_RE) earthViolationCount += 1;
      if (radius >= 1.5) {
        const theta = Math.acos(Math.min(1, Math.max(-1, point.x / radius)));
        const surface = shueRadiusRe(theta, parameters.standoffRe, parameters.flaringAlpha);
        if (Number.isFinite(surface) && radius > surface * 1.02 + 1e-6) truncationViolationCount += 1;
      }
    }

    // Strided faithfulness: segment ∥ field at segment midpoint.
    const sign = lineTraceSign(parameters, line);
    for (let index = 1; index < points.length; index += stride) {
      const angle = segmentAlignmentRad(parameters, points[index - 1]!, points[index]!, sign);
      if (angle === null) continue;
      checkedSegmentCount += 1;
      if (angle > worstAlignmentRad) worstAlignmentRad = angle;
      if (angle > FIELD_LINE_ALIGNMENT_TOLERANCE_RAD) misalignedSegmentCount += 1;
    }
  }

  const reason: FieldLineIntegrityReport["reason"] = misalignedSegmentCount > 0
    ? "segment-field-misalignment"
    : endpointViolationCount > 0
      ? "endpoint-topology-mismatch"
      : earthViolationCount > 0
        ? "earth-clearance"
        : truncationViolationCount > 0
          ? "truncation-overrun"
          : null;
  return {
    ok: reason === null,
    reason,
    checkedSegmentCount,
    worstAlignmentDeg: (worstAlignmentRad * 180) / Math.PI,
    misalignedSegmentCount,
    structuralViolationCount: endpointViolationCount + earthViolationCount + truncationViolationCount,
  };
}

/** The provenance strings the renderer and legend must carry with the lines. */
export const FIELD_LINE_METHOD = {
  status: "semi-empirical driven approximation",
  construction:
    "Tilted IGRF dipole + Chapman–Ferraro image dipole + a divergence-free Harris (1962) "
    + "current-sheet tail whose lobe strength is driven by measured dynamic pressure and IMF Bz. "
    + "The boundary the image dipole is pinned to — and the surface the RK4-traced lines are "
    + "truncated at — is the NOAA MHD frame's own extracted magnetopause curve when one is "
    + "loaded (least-squares fitted to the Shue functional form, residuals reported), and the "
    + "live Shue et al. (1998) fit from L1 otherwise.",
  citations: [
    "Chapman & Ferraro (1931), Terr. Mag. Atmos. Elect. 36, 77",
    "Harris (1962), Nuovo Cimento 23, 115",
    "Shue et al. (1998), JGR 103, 17691, doi:10.1029/98JA01103",
    "Kivelson & Russell (1995), Introduction to Space Physics, §6.3",
  ],
  not: "Not an MHD solution, not a Tsyganenko model, and no individual line is a measurement. "
    + "The topology and its response to the drivers are the claim; exact line positions are not.",
} as const;
