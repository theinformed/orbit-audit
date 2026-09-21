/**
 * Empirical magnetopause boundaries.
 *
 * Three published models live here and they answer three different questions.
 * Keeping them in one file is deliberate: the interesting thing about them is
 * where they disagree, and a reader comparing the code should not have to
 * chase it across modules.
 *
 * ## Shue et al. (1998) — what the site has always drawn
 *
 * `r(theta) = r0 (2/(1+cos theta))^alpha`. A function of solar zenith angle
 * and nothing else: no azimuth, no dipole tilt, no cusp term. It is not that
 * this implementation lacks cusps — **the model has no degrees of freedom for
 * them**, so no amount of live driving can put them in. Lin's held-out test
 * quantifies the cost: Shue-98 reaches sigma(d) = 0.780 Re for |Z| <= 3 Re but
 * 1.420 Re for |Z| > 3 Re, its error nearly doubling exactly where the cusps
 * are.
 *
 * ## Nguyen et al. (2022) Model 3 — the magnetopause current sheet
 *
 * doi:10.1029/2021JA029776. Fitted to 17,230 crossings from THEMIS, Cluster,
 * Double Star, MMS and ARTEMIS. Driven by dynamic + magnetic pressure, IMF Bz,
 * the IMF clock angle and dipole tilt. Its indentation is about 24.6% of the
 * local unindented radius, and unlike Lin's its **cusp latitude moves with
 * IMF Bz**.
 *
 * ## Lin et al. (2010) — the cusp inner boundary
 *
 * doi:10.1029/2009JA014235. The classic three-dimensional asymmetric model.
 * Nguyen showed its indentation is too deep to be the current sheet, because
 * its training set traced the **cusp inner boundary** instead — which is not a
 * defect for this site's purposes but the thing that makes the pair useful.
 *
 * ## Why the pair is the answer to "show me the cusps"
 *
 * The cusps are indentations, not holes. Nguyen et al. put it exactly: *"The
 * geometry of the polar cusps is described by two distinct boundaries. An
 * inner boundary that separates the cusp region from the magnetosphere and an
 * external boundary that corresponds to the magnetopause current-sheet outside
 * of which resides the magnetosheath plasma."* The "hole" picture descends
 * from the Chapman-Ferraro vacuum superposition, where the cusp is a magnetic
 * null on the boundary; in the real magnetosphere that null is a diamagnetic
 * cavity filled with magnetosheath plasma, which is why Polar measures a
 * magnetic depression of about -80 nT there rather than zero, and why Lavraud
 * et al. (2004) found no discontinuity in *total* pressure across it.
 *
 * So drawing both surfaces and shading between them renders the exterior cusp
 * as **two real published surfaces** rather than one invented indentation.
 * Deforming Shue with a hand-tuned dimple would be a fabricated boundary and
 * is forbidden by `docs/SCIENTIFIC-LAYERS.md`. Lin's `Q` term is also an
 * additive dimple on a Shue-like surface — the difference is that it is a
 * published fit to 1,482 real crossings.
 *
 * ## Conventions used throughout this file
 *
 * `theta` is the solar zenith angle from GSM +x. `azimuth` is measured from
 * GSM **+z** (north), so azimuth 0 is the north meridian, pi/2 is dusk (+y),
 * pi is the south meridian. That is the convention both reference
 * implementations use, and it differs from Lin's paper, which measures its
 * azimuth from +y; the two are related by `phi_code = pi/2 - phi_paper` with
 * the trig in beta swapped correspondingly. Getting this backwards silently
 * rotates the cusps to the flanks, so `magnetopausePointGsm` is the only place
 * that converts, and the tests pin the published cusp-axis and dusk radii.
 *
 * Every model here is **EMPIRICAL** in the site's evidence vocabulary: a
 * published relationship fitted to observations and driven by live upstream
 * data. None of them is an observation of a surface — nobody measures a
 * surface, only crossings — and none of them is MHD.
 */

export interface ShueBoundaryParameters {
  subsolarStandoffRe: number;
  flaringAlpha: number;
}

export interface MagnetopauseGsmPoint {
  xRe: number;
  yRe: number;
  zRe: number;
  radiusRe: number;
}

/**
 * Shue et al. (1998) empirical magnetopause parameters.
 *
 * Inputs are upstream solar-wind proton dynamic pressure (nPa) and IMF Bz
 * (nT, GSM). The result is in physical Earth radii; display compression must
 * be applied only after evaluating the boundary.
 */
export function shueBoundary(dynamicPressureNpa: number, bzGsmNt: number): ShueBoundaryParameters | null {
  if (!Number.isFinite(dynamicPressureNpa) || dynamicPressureNpa <= 0 || !Number.isFinite(bzGsmNt)) return null;
  const subsolarStandoffRe = (10.22 + 1.29 * Math.tanh(0.184 * (bzGsmNt + 8.14)))
    * dynamicPressureNpa ** (-1 / 6.6);
  const flaringAlpha = (0.58 - 0.007 * bzGsmNt) * (1 + 0.024 * Math.log(dynamicPressureNpa));
  if (!Number.isFinite(subsolarStandoffRe) || subsolarStandoffRe <= 0
    || !Number.isFinite(flaringAlpha) || flaringAlpha <= 0) return null;
  return { subsolarStandoffRe, flaringAlpha };
}

/** Physical Shue boundary radius at solar-zenith angle theta. */
export function shueRadiusRe(thetaRad: number, subsolarStandoffRe: number, flaringAlpha: number): number {
  if (!Number.isFinite(thetaRad) || thetaRad < 0 || thetaRad >= Math.PI) return Number.NaN;
  if (!Number.isFinite(subsolarStandoffRe) || subsolarStandoffRe <= 0) return Number.NaN;
  if (!Number.isFinite(flaringAlpha) || flaringAlpha <= 0) return Number.NaN;
  return subsolarStandoffRe * (2 / (1 + Math.cos(thetaRad))) ** flaringAlpha;
}

/**
 * Stop the open empirical tail at a stated physical GSM X coordinate rather
 * than clipping its radial distance into a false spherical end cap.
 */
export function shueTailTheta(
  subsolarStandoffRe: number,
  flaringAlpha: number,
  tailExtentRe = 50,
): number {
  const targetX = -Math.abs(tailExtentRe);
  let lower = Math.PI / 2;
  let upper = 170 * Math.PI / 180;
  const xAt = (theta: number) => shueRadiusRe(theta, subsolarStandoffRe, flaringAlpha) * Math.cos(theta);
  if (!Number.isFinite(xAt(upper)) || xAt(upper) > targetX) return upper;
  for (let iteration = 0; iteration < 48; iteration += 1) {
    const middle = (lower + upper) / 2;
    if (xAt(middle) <= targetX) upper = middle;
    else lower = middle;
  }
  return (lower + upper) / 2;
}

/**
 * A point on the axisymmetric Shue surface in physical GSM coordinates.
 *
 * ⚠️ This function's `azimuthRad` is measured from GSM **+y**, not from +z as
 * in the cusped models below. The difference is invisible here because the
 * Shue surface is invariant under rotation about the Sun-Earth line, which is
 * exactly why the inconsistency survived; it is called out rather than quietly
 * changed because `globe.ts` calls this one and a silent 90-degree rotation of
 * a cusped surface would put the funnels on the flanks.
 */
export function shuePointGsm(
  thetaRad: number,
  azimuthRad: number,
  subsolarStandoffRe: number,
  flaringAlpha: number,
): MagnetopauseGsmPoint {
  const radiusRe = shueRadiusRe(thetaRad, subsolarStandoffRe, flaringAlpha);
  const transverseRe = radiusRe * Math.sin(thetaRad);
  return {
    xRe: radiusRe * Math.cos(thetaRad),
    yRe: transverseRe * Math.cos(azimuthRad),
    zRe: transverseRe * Math.sin(azimuthRad),
    radiusRe,
  };
}

// ---------------------------------------------------------------------------
// Drivers shared by the cusped models
// ---------------------------------------------------------------------------

export interface CuspedBoundaryDrivers {
  /** Solar-wind dynamic pressure, nPa, pure-proton OMNI convention. */
  dynamicPressureNpa: number;
  /** Upstream IMF magnetic pressure, nPa. Both models use `Pd + Pm`. */
  magneticPressureNpa: number;
  /** IMF Bz in GSM, nT. */
  bzGsmNt: number;
  /** IMF clock angle in radians, measured from GSM north. Nguyen only. */
  clockAngleRad: number;
  /** Geodipole tilt in radians, positive when the north pole leans sunward. */
  dipoleTiltRad: number;
}

/** `B^2 / 2 mu0` with B in nT, result in nPa. */
export const MAGNETIC_PRESSURE_NPA_PER_NT2 = 1e-18 / (2 * 4e-7 * Math.PI) * 1e9;

export function magneticPressureNpa(btNt: number): number {
  return MAGNETIC_PRESSURE_NPA_PER_NT2 * btNt * btNt;
}

function driversAreUsable(drivers: CuspedBoundaryDrivers | null | undefined): drivers is CuspedBoundaryDrivers {
  if (!drivers) return false;
  const { dynamicPressureNpa, magneticPressureNpa: magnetic, bzGsmNt, clockAngleRad, dipoleTiltRad } = drivers;
  return (
    Number.isFinite(dynamicPressureNpa) && dynamicPressureNpa > 0
    && Number.isFinite(magnetic) && magnetic >= 0
    && Number.isFinite(bzGsmNt)
    && Number.isFinite(clockAngleRad)
    && Number.isFinite(dipoleTiltRad)
  );
}

// ---------------------------------------------------------------------------
// Nguyen et al. (2022) Model 3
// ---------------------------------------------------------------------------

/**
 * Nguyen et al. (2022) Model 3 coefficients `a0 … a17`, in the paper's order.
 *
 * Indexed rather than named because the published formula refers to them by
 * index and renaming them is how transcription errors get in. The formula is:
 *
 *   r    = r0 (2/(1+cos th))^xi (1 - a9 C cos^2 phi)
 *   r0   = a0 (Pd + Pm)^a1 (1 + a2 tanh(a3 Bz + a4))
 *   xi   = a5 + a6 gamma cos phi + a7 cos(Om) sin^2 phi + a8 cos(Om) cos^2 phi
 *   C    = e^(-|th - ln|/w)(1 + sgn cos phi) + e^(-|th - ls|/w)(1 - sgn cos phi)
 *   l_ns = (a10 + a11 tanh[a12 (Bz + a13)]) (1 -/+ a14 gamma)
 *   w    = (a15 + a16 ln Pd) (1 + a17 gamma^2)
 *
 * with `Om` the IMF clock angle and `gamma` the dipole tilt in **radians**.
 * Note the maximum of `C` is 2, so `a9 = 0.123` gives the paper's quoted 24.6%
 * indentation of the local unindented radius — a useful arithmetic check that
 * the coefficient did not shift by an index.
 */
export const NGUYEN_2022_COEFFICIENTS = [
  10.85, -0.15, 0.027, 0.296, 2.14, 0.549, 0.0745, 0.01, -0.0713,
  0.123, 0.877, 0.329, 0.211, 10.13, 0.464, 0.326, 0.08355, 0.00721,
] as const;

export interface NguyenBoundaryParameters {
  /** Unindented subsolar scale `r0`, Re. */
  scaleRe: number;
  /** Cusp-axis solar zenith angle in the north, radians. */
  northCuspThetaRad: number;
  /** Cusp-axis solar zenith angle in the south, radians. */
  southCuspThetaRad: number;
  /** 1/e angular half-width of the indentation, radians. */
  cuspWidthRad: number;
}

export function nguyenBoundary(drivers: CuspedBoundaryDrivers): NguyenBoundaryParameters | null {
  if (!driversAreUsable(drivers)) return null;
  const a = NGUYEN_2022_COEFFICIENTS;
  const pressure = drivers.dynamicPressureNpa + drivers.magneticPressureNpa;
  const tilt = drivers.dipoleTiltRad;
  const scaleRe = a[0] * pressure ** a[1] * (1 + a[2] * Math.tanh(a[3] * drivers.bzGsmNt + a[4]));
  const cuspBase = a[10] + a[11] * Math.tanh(a[12] * (drivers.bzGsmNt + a[13]));
  const cuspWidthRad = (a[15] + a[16] * Math.log(drivers.dynamicPressureNpa)) * (1 + a[17] * tilt * tilt);
  if (!Number.isFinite(scaleRe) || scaleRe <= 0 || !Number.isFinite(cuspWidthRad) || cuspWidthRad <= 0) {
    return null;
  }
  return {
    scaleRe,
    // Positive tilt leans the northern pole sunward, which pulls the northern
    // indentation to a smaller solar zenith angle and pushes the southern one
    // to a larger one. The sign is the whole reason the surface is asymmetric.
    northCuspThetaRad: cuspBase * (1 - a[14] * tilt),
    southCuspThetaRad: cuspBase * (1 + a[14] * tilt),
    cuspWidthRad,
  };
}

/**
 * How close a direction is to a cusp axis, on Nguyen's own scale.
 *
 * This is `C / 2` from the model: 1 exactly on a cusp axis, falling to 1/e one
 * angular width away. It is exported because the "show both surfaces" render
 * needs it to say where the gap between the two boundaries is genuinely the
 * exterior cusp and where it is merely two models disagreeing.
 */
export function nguyenCuspProximity(
  thetaRad: number,
  azimuthRad: number,
  parameters: NguyenBoundaryParameters,
): number {
  const cosAzimuth = Math.cos(azimuthRad);
  const northWeight = (1 + Math.sign(cosAzimuth)) / 2;
  const southWeight = (1 - Math.sign(cosAzimuth)) / 2;
  const north = Math.exp(-Math.abs(thetaRad - parameters.northCuspThetaRad) / parameters.cuspWidthRad);
  const south = Math.exp(-Math.abs(thetaRad - parameters.southCuspThetaRad) / parameters.cuspWidthRad);
  return (northWeight * north + southWeight * south) * cosAzimuth * cosAzimuth;
}

/**
 * Nguyen's surface with the cusp term switched off.
 *
 * Exported because "how deep is the indentation" is only meaningful against
 * the same direction's unindented radius: the flaring exponent `xi` itself
 * varies with azimuth through the clock-angle terms, so comparing the cusp
 * axis with the flank measures two different things at once.
 */
export function nguyenUnindentedRadiusRe(
  thetaRad: number,
  azimuthRad: number,
  drivers: CuspedBoundaryDrivers,
  parameters: NguyenBoundaryParameters,
): number {
  if (!Number.isFinite(thetaRad) || thetaRad < 0 || thetaRad >= Math.PI) return Number.NaN;
  const a = NGUYEN_2022_COEFFICIENTS;
  const cosAzimuth = Math.cos(azimuthRad);
  const sinAzimuth = Math.sin(azimuthRad);
  const clock = Math.cos(drivers.clockAngleRad);
  const flaring =
    a[5]
    + a[6] * drivers.dipoleTiltRad * cosAzimuth
    + a[7] * clock * sinAzimuth * sinAzimuth
    + a[8] * clock * cosAzimuth * cosAzimuth;
  const radius = parameters.scaleRe * (2 / (1 + Math.cos(thetaRad))) ** flaring;
  return Number.isFinite(radius) && radius > 0 ? radius : Number.NaN;
}

export function nguyenRadiusRe(
  thetaRad: number,
  azimuthRad: number,
  drivers: CuspedBoundaryDrivers,
  parameters: NguyenBoundaryParameters,
): number {
  const unindented = nguyenUnindentedRadiusRe(thetaRad, azimuthRad, drivers, parameters);
  if (!Number.isFinite(unindented)) return Number.NaN;
  const indentation = 2 * nguyenCuspProximity(thetaRad, azimuthRad, parameters);
  const radius = unindented * (1 - NGUYEN_2022_COEFFICIENTS[9] * indentation);
  return Number.isFinite(radius) && radius > 0 ? radius : Number.NaN;
}

// ---------------------------------------------------------------------------
// Lin et al. (2010)
// ---------------------------------------------------------------------------

/**
 * Lin et al. (2010) Table 9 coefficients `a0 … a21`.
 *
 * Tables 2, 6, 7 and 8 in the paper are intermediate fits and must not be
 * used. The formula is:
 *
 *   r(th,phi) = r0 [cos(th/2) + m sin(2 th)(1 - e^-th)]^beta + Q
 *   r0    = a0 P^a1 [1 + a2 (e^(a3 Bz) - 1)/(e^(a4 Bz) + 1)],  P = Pd + Pm
 *   m     = a5
 *   beta  = beta0 + beta1 cos phi + beta2 sin phi + beta3 sin^2 phi   (phi from +Y)
 *   beta0 = a6 + a7 (e^(a8 Bz) - 1)/(e^(a9 Bz) + 1)      IMF control of tail flaring
 *   beta1 = a10                                          intrinsic dawn-dusk asymmetry
 *   beta2 = a11 + a12 psi                                tilt-driven north-south asymmetry
 *   beta3 = a13                                          tail cross-section ellipticity
 *   Q     = c_n e^(d_n psi_n^e) + c_s e^(d_s psi_s^e)    the additive cusp indentations
 *
 * Two things about `Q` are worth knowing before reading a number off this
 * model. First, **it is non-zero at the subsolar point** — about -0.27 Re at
 * nominal pressure — so Lin's `r0` is not literally the standoff distance;
 * Nguyen et al. flag this as a structural drawback. Second, **Lin's cusp has
 * no IMF Bz dependence at all**: `Q` depends only on pressure and tilt, so the
 * Lin cusp will not march equatorward when Bz turns south. The paper flags
 * this itself. If the site wants that motion it must come from Nguyen, whose
 * cusp latitude does depend on Bz.
 */
export const LIN_2010_COEFFICIENTS = [
  12.544, -0.194, 0.305, 0.0573, 2.178, 0.0571, -0.999, 16.473, 0.00152, 0.382,
  0.0431, -0.00763, -0.21, 0.0405, -4.43, -0.636, -2.6, 0.832, -5.328, 1.103,
  -0.907, 1.45,
] as const;

export interface LinBoundaryParameters {
  /** Unindented scale `r0`, Re. Not the standoff distance; see above. */
  scaleRe: number;
  beta0: number;
  beta1: number;
  beta2: number;
  beta3: number;
  /** Indentation depth coefficient, negative. */
  cuspDepthRe: number;
  northCuspExponentScale: number;
  southCuspExponentScale: number;
  northCuspThetaRad: number;
  southCuspThetaRad: number;
  cuspExponent: number;
}

export function linBoundary(drivers: CuspedBoundaryDrivers): LinBoundaryParameters | null {
  if (!driversAreUsable(drivers)) return null;
  const a = LIN_2010_COEFFICIENTS;
  const pressure = drivers.dynamicPressureNpa + drivers.magneticPressureNpa;
  const bz = drivers.bzGsmNt;
  const tilt = drivers.dipoleTiltRad;
  const scaleRe =
    a[0] * pressure ** a[1]
    * (1 + a[2] * (Math.exp(a[3] * bz) - 1) / (Math.exp(a[4] * bz) + 1));
  const beta0 = a[6] + a[7] * (Math.exp(a[8] * bz) - 1) / (Math.exp(a[9] * bz) + 1);
  const cuspDepthRe = a[14] * pressure ** a[15];
  if (!Number.isFinite(scaleRe) || scaleRe <= 0 || !Number.isFinite(beta0) || !Number.isFinite(cuspDepthRe)) {
    return null;
  }
  return {
    scaleRe,
    beta0,
    beta1: a[10],
    beta2: a[11] + a[12] * tilt,
    beta3: a[13],
    cuspDepthRe,
    northCuspExponentScale: a[16] + a[17] * tilt + a[18] * tilt * tilt,
    southCuspExponentScale: a[16] - a[17] * tilt + a[18] * tilt * tilt,
    northCuspThetaRad: a[19] + a[20] * tilt,
    southCuspThetaRad: a[19] - a[20] * tilt,
    cuspExponent: a[21],
  };
}

/** Angular distance from a cusp axis, radians. Lin's `psi_{n,s}`. */
function angleFromCuspAxis(
  thetaRad: number,
  azimuthRad: number,
  cuspThetaRad: number,
  cuspAzimuthRad: number,
): number {
  const cosine =
    Math.cos(thetaRad) * Math.cos(cuspThetaRad)
    + Math.sin(thetaRad) * Math.sin(cuspThetaRad) * Math.cos(azimuthRad - cuspAzimuthRad);
  return Math.acos(Math.max(-1, Math.min(1, cosine)));
}

export function linRadiusRe(
  thetaRad: number,
  azimuthRad: number,
  parameters: LinBoundaryParameters,
): number {
  if (!Number.isFinite(thetaRad) || thetaRad < 0 || thetaRad >= Math.PI) return Number.NaN;
  const a = LIN_2010_COEFFICIENTS;
  // Lin's paper measures azimuth from +Y; this file measures it from +Z.
  const paperAzimuth = Math.PI / 2 - azimuthRad;
  const beta =
    parameters.beta0
    + parameters.beta1 * Math.cos(paperAzimuth)
    + parameters.beta2 * Math.sin(paperAzimuth)
    + parameters.beta3 * Math.sin(paperAzimuth) ** 2;
  const shape =
    Math.cos(thetaRad / 2)
    + a[5] * Math.sin(2 * thetaRad) * (1 - Math.exp(-thetaRad));
  if (!(shape > 0)) return Number.NaN;
  const north = angleFromCuspAxis(thetaRad, azimuthRad, parameters.northCuspThetaRad, 0);
  const south = angleFromCuspAxis(thetaRad, azimuthRad, parameters.southCuspThetaRad, Math.PI);
  const indentation =
    parameters.cuspDepthRe * Math.exp(parameters.northCuspExponentScale * north ** parameters.cuspExponent)
    + parameters.cuspDepthRe * Math.exp(parameters.southCuspExponentScale * south ** parameters.cuspExponent);
  const radius = parameters.scaleRe * shape ** beta + indentation;
  return Number.isFinite(radius) && radius > 0 ? radius : Number.NaN;
}

// ---------------------------------------------------------------------------
// One evaluator over all three models
// ---------------------------------------------------------------------------

export type MagnetopauseModelId = "shue1998" | "nguyen2022" | "lin2010";

export interface MagnetopauseModelDescriptor {
  id: MagnetopauseModelId;
  label: string;
  /** What surface the model claims to trace. */
  surface: string;
  /** Evidence class, in the site's vocabulary. */
  status: "empirical";
  citation: string;
  doi: string;
  /** The one-line honesty note that must travel with the drawn surface. */
  note: string;
}

export const MAGNETOPAUSE_MODELS: Record<MagnetopauseModelId, MagnetopauseModelDescriptor> = {
  shue1998: {
    id: "shue1998",
    label: "Shue et al. (1998)",
    surface: "axisymmetric magnetopause",
    status: "empirical",
    citation: "Shue et al. (1998), JGR 103, 17691",
    doi: "10.1029/98JA01103",
    note:
      "Axisymmetric by construction — no cusps. r(theta) depends on solar zenith angle "
      + "only, with no azimuthal and no dipole-tilt term, so no amount of live driving "
      + "can put indentations into it.",
  },
  nguyen2022: {
    id: "nguyen2022",
    label: "Nguyen et al. (2022) Model 3",
    surface: "magnetopause current sheet, indented",
    status: "empirical",
    citation: "Nguyen, Aunai, Michotte de Welle, Jeandet, Lavraud & Fontaine (2022), JGR 127, e2021JA029776",
    doi: "10.1029/2021JA029776",
    note:
      "Fitted to 17,230 spacecraft crossings. The outer wall of the exterior cusp: "
      + "outside this surface is magnetosheath plasma. Driven by live pressure, IMF Bz, "
      + "clock angle and dipole tilt — an empirical fit, not an observation of a surface.",
  },
  lin2010: {
    id: "lin2010",
    label: "Lin et al. (2010)",
    surface: "cusp inner boundary (funnel wall)",
    status: "empirical",
    citation: "Lin, Zhang, Liu, Wang & Gong (2010), JGR 115, A04207",
    doi: "10.1029/2009JA014235",
    note:
      "Fitted to 1,482 crossings. Nguyen et al. showed its indentation is too deep for "
      + "the current sheet because its training set traced the cusp INNER boundary — "
      + "which is exactly what makes it the companion surface here. Its cusp responds to "
      + "pressure and dipole tilt but not to IMF Bz; the paper flags that itself.",
  },
};

export interface MagnetopauseEvaluator {
  model: MagnetopauseModelDescriptor;
  /** Physical radius in Re at a solar zenith angle and azimuth-from-north. */
  radiusRe: (thetaRad: number, azimuthRad: number) => number;
  /** Subsolar radius in Re, which for Lin is not the same as its `r0`. */
  subsolarRe: number;
}

/**
 * Build an evaluator for one model, or `null` if its drivers are unusable.
 *
 * Returning `null` rather than a default surface is the point: a missing
 * boundary is honest and a frozen one is not, and the magnetopause layer
 * already disappears rather than freezing when its drivers go away.
 */
export function magnetopauseEvaluator(
  id: MagnetopauseModelId,
  drivers: CuspedBoundaryDrivers,
): MagnetopauseEvaluator | null {
  const model = MAGNETOPAUSE_MODELS[id];
  if (!model || !driversAreUsable(drivers)) return null;
  if (id === "shue1998") {
    const shue = shueBoundary(drivers.dynamicPressureNpa, drivers.bzGsmNt);
    if (!shue) return null;
    return {
      model,
      radiusRe: (theta) => shueRadiusRe(theta, shue.subsolarStandoffRe, shue.flaringAlpha),
      subsolarRe: shue.subsolarStandoffRe,
    };
  }
  if (id === "nguyen2022") {
    const parameters = nguyenBoundary(drivers);
    if (!parameters) return null;
    const radiusRe = (theta: number, azimuth: number) => nguyenRadiusRe(theta, azimuth, drivers, parameters);
    return { model, radiusRe, subsolarRe: radiusRe(0, 0) };
  }
  const parameters = linBoundary(drivers);
  if (!parameters) return null;
  const radiusRe = (theta: number, azimuth: number) => linRadiusRe(theta, azimuth, parameters);
  return { model, radiusRe, subsolarRe: radiusRe(0, 0) };
}

/**
 * A point on any of the three surfaces, in physical GSM coordinates.
 *
 * Azimuth is from GSM +z, so `azimuth = 0` is the north meridian. This is the
 * single place the convention is turned into coordinates.
 */
export function magnetopausePointGsm(
  evaluator: MagnetopauseEvaluator,
  thetaRad: number,
  azimuthRad: number,
): MagnetopauseGsmPoint {
  const radiusRe = evaluator.radiusRe(thetaRad, azimuthRad);
  const transverseRe = radiusRe * Math.sin(thetaRad);
  return {
    xRe: radiusRe * Math.cos(thetaRad),
    yRe: transverseRe * Math.sin(azimuthRad),
    zRe: transverseRe * Math.cos(azimuthRad),
    radiusRe,
  };
}
