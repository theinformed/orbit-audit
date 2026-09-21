import * as THREE from "three";
import { createRingCurrentVolumeMesh, setRingCurrentVolumeTime } from "./ring-current-volume";

import type { DgcpmPlasmasphereField } from "./inner-magnetosphere";

/**
 * How the ring current FORMS — an illustration, not a measurement.
 *
 * ## Read this before anything else in this file
 *
 * **There is no gridded ring-current data product in this site's feeds.** None
 * of the upstreams this release fetches publishes a ring-current ion flux on a
 * grid, at any cadence, for any time. The only ring-current *measurement* this
 * site carries is Dst — one number, whose Dessler-Parker-Sckopke conversion to
 * a total energy is already on the storm panel and in walkthrough link 04 — and
 * a single number has no map. A torus drawn from it was deleted on 2026-08-09
 * for exactly that reason and is not coming back.
 *
 * What this module draws is therefore **MODEL-DERIVED**: the drift motion of
 * energetic ions, computed from the model fields the site already publishes,
 * shown so that a reader can see the mechanism that builds the population Dst
 * then measures the energy of. Every surface of it says so — the badge, the
 * evidence class, the colour-bar label, the card, and this comment.
 *
 * It was badged ILLUSTRATION until 2026-08-19, and the file kept the name. The
 * word was right for the FIRST version of this: drift-path lines with sprites
 * marching along them, a diagram drawn over the data. Those were deleted and
 * replaced by a ray-marched volume whose region is RK4-integrated in the
 * published Volland-Stern field at published Kp, bounded by the computed
 * Alfvén layer and coloured by `energyAtLKeV`. Sean: "i thought you were going
 * to make it something that ISN'T a useless illustration but something REAL.
 * why does it still say it is an illustration?" The badge had gone stale
 * against its own layer. What did NOT change is the sentence above this one:
 * the SHAPE is derived and never observed, and every surface still says that.
 *
 * The distinction that makes this admissible where the torus was not: the torus
 * asserted *where the ring current is* from a scalar that says nothing about
 * where. This asserts *how ions move in a stated electric and magnetic field*,
 * and the field is not invented — it is the same Volland-Stern convection
 * field, at the same measured Kp, at the same instant, that the DGCPM
 * plasmasphere simulation on the next layer is already integrating. Nothing
 * here claims a flux, a density or a location for the real ring current.
 *
 * ## The physics, and where each piece came from
 *
 * A particle trapped in the inner magnetosphere does three things: it gyrates,
 * it bounces between mirror points, and it drifts slowly around the Earth. Only
 * the third motion matters at this scale, and for a particle that mirrors AT
 * the magnetic equator (pitch angle 90 degrees, the case drawn here) the
 * bounce-averaging is trivial because there is no bounce.
 *
 * Two drifts act:
 *
 * 1. **E x B drift**, `v = E x B / B^2`. Identical for every species and every
 *    energy. This is exactly the drift `pipeline/plasmasphere_dgcpm.py`
 *    integrates the cold plasma under, in exactly the same potential:
 *
 *        Phi(L, phi) = A R_E L^2 sin(phi)  -  Phi_c / L                  [V]
 *        A     = 7.05e-6 / (1 - 0.159 Kp + 0.0093 Kp^2)^3              [V/m]
 *        Phi_c = omega mu0 M / (4 pi R_E) = 91.8 kV              (corotation)
 *
 *    Volland (1973) JGR 78, 171; Stern (1975) JGR 80, 595; the Kp law from
 *    Maynard & Chen (1975) JGR 80, 1009, restated by Pierrard, Khazanov,
 *    Cabrera & Lemaire (2008), JGR 113, A08212, doi:10.1029/2007JA012612.
 *    `phi` is measured from midnight and increases eastward, which is the
 *    reference implementation's own convention and the plasmasphere module's.
 *    **A is not recomputed here**: it is read off the published DGCPM frame,
 *    so the two layers cannot disagree about the field they share. The Kp law
 *    below exists only so a test can prove they agree.
 *
 * 2. **Gradient/curvature drift**, which for an equatorially mirroring particle
 *    in a dipole is purely azimuthal:
 *
 *        v_mag = -(3 W) / (q B L R_E) phi-hat
 *        omega_mag = v_mag / (L R_E) = -3 W L / (q B_0 R_E^2)      [rad/s]
 *
 *    with `B = B_0 / L^3` the equatorial dipole field and `W` the particle's
 *    kinetic energy. **The sign is the whole teaching point**: `q > 0` gives a
 *    negative (westward) angular rate and `q < 0` a positive (eastward) one, so
 *    **ions drift westward and electrons eastward**. Opposite charges going
 *    opposite ways do not cancel — they add — and the net is a westward current
 *    encircling the Earth, whose magnetic field opposes Earth's own at the
 *    surface. That depression is Dst. Standard result; see Roederer &
 *    Zhang (2014), *Dynamics of Magnetically Trapped Particles*, ch. 2, or
 *    Kivelson & Russell (1995), *Introduction to Space Physics*, ch. 10.
 *
 * The ring current is carried **mainly by ions of a few tens to a few hundred
 * keV**, and it is energised by injection of plasma-sheet ions during
 * substorms and storms. Both facts are in the picture rather than asserted
 * beside it, because of the third piece:
 *
 * 3. **Energisation by inward transport.** The first adiabatic invariant
 *    `mu = W / B` is conserved by these slow drifts, so a particle carried from
 *    L_0 to L has
 *
 *        W(L) = W_0 (L_0 / L)^3
 *
 *    A 10 keV plasma-sheet ion that convects from L = 8 to L = 4 arrives as an
 *    80 keV ring-current ion. That is what the colour on screen is: the
 *    particle's own kinetic energy along its own drift path. The third
 *    invariant is deliberately NOT conserved — breaking it *is* radial
 *    transport — and the second is trivially conserved at 90 degrees.
 *
 * ## Why the drift paths are contours, and what that buys
 *
 * Combining the two drifts, the motion is everywhere perpendicular to the
 * gradient of
 *
 *     H(L, phi) = q Phi(L, phi) + mu B(L)
 *
 * so drift paths are contours of H and H is conserved along them exactly.
 * `tests/ring-current-illustration.test.ts` asserts that conservation against
 * the integrated trajectories, which is a check on the drift equations and on
 * the integrator at the same time — if either were wrong, H would walk.
 *
 * The contour that separates paths encircling the Earth from paths that sweep
 * in from the tail and out through the dayside is the **Alfven layer** for that
 * energy. Inside it a particle is trapped and stays: that is the ring current.
 * Outside it a particle is swept through. And because H carries the energy
 * term, **the boundary moves with energy** — which is the sentence this whole
 * layer exists to make visible:
 *
 * > The energy-dependent balance between corotation and convection sets which
 * > particles reach which L.
 *
 * At zero energy H collapses to `q Phi` and the separatrix becomes the last
 * closed equipotential — the same curve, computed the same way, that puts the
 * plasmapause where the plasmasphere layer draws it. The two boundaries on
 * screen are the same construction at two energies, and the card says so.
 *
 * Both are quoted on the MIDNIGHT meridian, which is a correction worth
 * recording because the first version of the card was not. The zero-energy
 * boundary is a teardrop: its nose is at the dusk stagnation radius `L_s` and
 * it is pinched to `(2/3) L_s` at midnight and noon and to `0.596 L_s` at dawn.
 * Printing the ion boundary at midnight beside the cold one at dusk compared
 * two local times and read as though ions were excluded from further out than
 * cold plasma. On one meridian the ordering is the physical one and it is
 * strictly monotone in energy: cold plasma is trapped closest in, and the more
 * energetic the particle the further out its drift path still closes, because a
 * fast azimuthal drift carries it right round the Earth before convection can
 * carry it out. That is the same reason the radiation belts extend past the
 * plasmapause.
 *
 * ## What is NOT claimed
 *
 * - No flux, no density, no number of particles. Nothing countable is drawn at
 *   all: there is no marker, no sprite and no line whose number a reader could
 *   read as a population. What is drawn is a volume, and what moves is the
 *   volume's own density.
 * - No pitch-angle distribution: every drawn particle mirrors at the equator.
 * - No losses. Charge exchange with the geocorona, Coulomb drag and wave
 *   scattering are what actually end a ring-current ion's life, and none of
 *   them is here, so a drawn closed path over-states how long a real ion stays.
 * - No self-consistency: these ions do not shield the convection field they
 *   are drifting in, and they do not feed back into the plasmasphere run. The
 *   Volland-Stern gamma = 2 shielding is a fixed exponent, not a response.
 * - No substorm injection event, even though a supply IS drawn arriving. The
 *   field is the steady field of the selected frame's Kp, and a real injection
 *   is a transient dipolarisation front. Worse, in a steady field a particle
 *   outside the Alfven layer can never become trapped inside it — that is the
 *   definition of the boundary — so the trapping the loop shows really happens
 *   because the boundary MOVES when convection relaxes, which one published Kp
 *   cannot express. `RING_CURRENT_FORMATION` says this again where the motion
 *   is built, and the card says it to the reader.
 * - No asymmetric/partial ring current as a measured thing. The drift paths
 *   ARE asymmetric, and that asymmetry is the mechanism behind the observed
 *   partial ring current (Liemohn et al. 2001, doi:10.1029/2000JA000326), but
 *   nothing in this release measures it.
 */

// ---------------------------------------------------------------------------
// Constants, all shared with pipeline/plasmasphere_dgcpm.py
// ---------------------------------------------------------------------------

/**
 * Every constant in this block is the DGCPM pipeline's own value, not the
 * nearest textbook one, so the two descriptions of the same field agree to the
 * last digit. `pipeline/plasmasphere_dgcpm.py` uses 6.378e6 m for the Earth
 * radius and 8.05e22 A m^2 for the dipole moment; changing either here without
 * changing it there would put the ring-current drift in a slightly different
 * field from the plasmasphere it is supposed to be riding on.
 */
export const RING_CURRENT_CONSTANTS = {
  earthRadiusM: 6.378e6,
  dipoleMomentAM2: 8.05e22,
  vacuumPermeability: 4 * Math.PI * 1e-7,
  earthAngularRateRadPerS: (2 * Math.PI) / 86_400,
  /** Volland-Stern Kp law, identical to the pipeline's `VOLLAND_STERN`. */
  vollandSternAmplitudeVPerM: 7.05e-6,
  vollandSternKpLinear: 0.159,
  vollandSternKpQuadratic: 0.0093,
} as const;

/** Equatorial dipole field at the surface, tesla. About 31,030 nT. */
export const SURFACE_EQUATORIAL_FIELD_T =
  (RING_CURRENT_CONSTANTS.vacuumPermeability * RING_CURRENT_CONSTANTS.dipoleMomentAM2)
  / (4 * Math.PI * RING_CURRENT_CONSTANTS.earthRadiusM ** 3);

/** The corotation potential scale in `-Phi_c / L`, volts. About 91.8 kV. */
export const COROTATION_POTENTIAL_SCALE_V =
  (RING_CURRENT_CONSTANTS.earthAngularRateRadPerS
    * RING_CURRENT_CONSTANTS.vacuumPermeability
    * RING_CURRENT_CONSTANTS.dipoleMomentAM2)
  / (4 * Math.PI * RING_CURRENT_CONSTANTS.earthRadiusM);

/** Equatorial dipole field strength at L, tesla. */
export function equatorialDipoleFieldT(lShell: number): number {
  return SURFACE_EQUATORIAL_FIELD_T / lShell ** 3;
}

/**
 * The Volland-Stern amplitude A at a Kp, in volts per Earth radius squared —
 * the unit the published DGCPM frame prints it in.
 *
 * The layer never drives itself from this: it reads the frame's own
 * `convectionAmplitudeVPerRe2`, so there is exactly one statement of the
 * convection field on screen. This exists so a test can prove the TypeScript
 * and the Python agree about what that field is.
 */
export function vollandSternAmplitudeVPerRe2(kp: number): number {
  const c = RING_CURRENT_CONSTANTS;
  const clamped = Math.min(Math.max(kp, 0), 9);
  const denominator = (1 - c.vollandSternKpLinear * clamped + c.vollandSternKpQuadratic * clamped * clamped) ** 3;
  return (c.vollandSternAmplitudeVPerM / denominator) * c.earthRadiusM;
}

// ---------------------------------------------------------------------------
// Geometry conventions
// ---------------------------------------------------------------------------

/** Magnetic local time, hours from midnight, from the drift angle phi. */
export function mltHoursFromPhi(phiRadians: number): number {
  const hours = (phiRadians * 12) / Math.PI;
  return ((hours % 24) + 24) % 24;
}

/** The drift angle phi, radians from midnight increasing eastward, from MLT. */
export function phiFromMltHours(mltHours: number): number {
  return (mltHours * Math.PI) / 12;
}

/**
 * Where a point of the magnetic equator sits in GSM, in Earth radii.
 *
 * GSM +x is noon and GSM +y is dusk, which is the convention every other layer
 * in this scene uses (see `createPlasmasphereFieldGeometry`, which maps its
 * grains the same way). `phi` counts from midnight, so midnight is -x, noon is
 * +x, dusk (18 MLT) is +y and dawn (06 MLT) is -y. Pinned by a test rather
 * than trusted, because a mirrored local time would put the ion drift on the
 * dawn side and quietly teach the wrong half of the physics.
 *
 * z is zero: this is a magnetic-equator model, and the drawn plane is the GSM
 * equator, the same centred-dipole approximation the radiation-belt mapping and
 * the plasmasphere stipple already declare.
 */
export function gsmFromDrift(lShell: number, phiRadians: number): { x: number; y: number; z: number } {
  return { x: -lShell * Math.cos(phiRadians), y: -lShell * Math.sin(phiRadians), z: 0 };
}

// ---------------------------------------------------------------------------
// The drifting particle
// ---------------------------------------------------------------------------

export interface DriftSpecies {
  /** +1 for a singly charged ion, -1 for an electron. Sets the drift sense. */
  chargeSign: 1 | -1;
  /** Kinetic energy at `referenceL`, keV. */
  referenceEnergyKeV: number;
  /** Where that energy is quoted. The seeding shell: the plasma-sheet edge. */
  referenceL: number;
  /** What to call it on the card. */
  label: string;
}

/**
 * The ion family the layer draws by default, and the two alternatives the
 * layer's own control offers.
 *
 * All three are quoted at L = 8 because that is where the drawn domain meets
 * the inner edge of the plasma sheet, which is where storm-time injection
 * delivers ions from. Plasma-sheet ion temperatures are a few keV and the
 * injected population runs from there up to tens of keV; adiabatic transport
 * inward does the rest, and the drawn colour is the arithmetic.
 */
export const RING_CURRENT_ION_CHOICES: readonly DriftSpecies[] = [
  { chargeSign: 1, referenceEnergyKeV: 3, referenceL: 8, label: "3 keV at L 8" },
  { chargeSign: 1, referenceEnergyKeV: 10, referenceL: 8, label: "10 keV at L 8" },
  { chargeSign: 1, referenceEnergyKeV: 30, referenceL: 8, label: "30 keV at L 8" },
];

export const DEFAULT_RING_CURRENT_ION = RING_CURRENT_ION_CHOICES[1]!;

/** The electron of the same first invariant, for the counter-drift statement. */
export function counterDriftingElectron(ion: DriftSpecies): DriftSpecies {
  return { ...ion, chargeSign: -1, label: `${ion.referenceEnergyKeV} keV electron at L ${ion.referenceL}` };
}

/**
 * Kinetic energy at L, keV, from conservation of the first adiabatic invariant.
 *
 * `mu = W / B` and `B = B_0 / L^3`, so `W = W_0 (L_0/L)^3`. This is the
 * energisation the ring current is made of, and it is arithmetic rather than a
 * fitted curve.
 */
export function energyAtLKeV(species: DriftSpecies, lShell: number): number {
  return species.referenceEnergyKeV * (species.referenceL / lShell) ** 3;
}

/**
 * The gradient/curvature drift angular rate, radians per second.
 *
 * NEGATIVE IS WESTWARD, because `phi` increases eastward. A positive charge
 * therefore returns a negative rate — ions drift westward — and an electron
 * returns a positive one. The elementary charge cancels between `q` and the
 * energy expressed in electron-volts, so nothing here needs it.
 */
export function magneticDriftAngularRateRadPerS(
  lShell: number,
  energyKeV: number,
  chargeSign: 1 | -1,
): number {
  const energyVolts = energyKeV * 1000;
  return -chargeSign * (3 * energyVolts * lShell)
    / (SURFACE_EQUATORIAL_FIELD_T * RING_CURRENT_CONSTANTS.earthRadiusM ** 2);
}

/** How long one drift circuit takes at this L and energy, hours. */
export function magneticDriftPeriodHours(lShell: number, energyKeV: number): number {
  const rate = Math.abs(magneticDriftAngularRateRadPerS(lShell, energyKeV, 1));
  return rate > 0 ? (2 * Math.PI) / rate / 3600 : Number.POSITIVE_INFINITY;
}

/** Corotation's angular rate, radians per second. Eastward, so positive. */
export function corotationAngularRateRadPerS(): number {
  return COROTATION_POTENTIAL_SCALE_V
    / (SURFACE_EQUATORIAL_FIELD_T * RING_CURRENT_CONSTANTS.earthRadiusM ** 2);
}

/** Convection plus corotation potential at a point of the equator, volts. */
export function totalPotentialV(lShell: number, phiRadians: number, amplitudeVPerM: number): number {
  return amplitudeVPerM * RING_CURRENT_CONSTANTS.earthRadiusM * lShell * lShell * Math.sin(phiRadians)
    - COROTATION_POTENTIAL_SCALE_V / lShell;
}

/**
 * Where the dusk-meridian flow stops for a zero-energy particle:
 * `L_s = (Phi_c / (2 A R_E))^(1/3)`.
 *
 * This is the plasmasphere's own stagnation point — the nose of the teardrop
 * and the reason the plasmapause bulges at dusk — and it is the ZERO-ENERGY
 * limit of the Alfven layer this module computes for ions. The two numbers
 * beside each other on the card are the teaching point; a test pins this
 * function against the value the DGCPM pipeline publishes in its frames.
 */
export function zeroEnergySeparatrixL(amplitudeVPerM: number): number {
  if (!(amplitudeVPerM > 0)) throw new RangeError("convection amplitude must be positive");
  return (COROTATION_POTENTIAL_SCALE_V / (2 * amplitudeVPerM * RING_CURRENT_CONSTANTS.earthRadiusM)) ** (1 / 3);
}

/**
 * The same zero-energy boundary read on the MIDNIGHT meridian, which is where
 * the ion Alfven layer is quoted — so the two numbers on the card are the same
 * boundary at two energies rather than two boundaries at two local times.
 *
 * Closed form, not a search. The last closed equipotential passes through the
 * dusk stagnation point, so its value is
 * `Phi_s = -A R_E L_s^2 - Phi_c/L_s`, and by the definition of `L_s` above
 * `Phi_c = 2 A R_E L_s^3`, giving `Phi_s = -3 A R_E L_s^2`. At midnight
 * `sin(phi) = 0` and the potential is the corotation term alone, `-Phi_c/L`, so
 * the crossing sits at `L = Phi_c / (3 A R_E L_s^2) = (2/3) L_s`.
 *
 * That is the classic teardrop written out: widest at dusk (L_s), two thirds of
 * that at midnight and at noon, and 0.596 of it at dawn. A test checks this
 * closed form against the boundary the tracer finds for a near-zero-energy
 * particle, so the algebra cannot quietly diverge from the integrator.
 */
export function zeroEnergySeparatrixMidnightL(amplitudeVPerM: number): number {
  return (2 / 3) * zeroEnergySeparatrixL(amplitudeVPerM);
}

/**
 * The conserved quantity, in keV: `H = q Phi + mu B`, per unit charge for the
 * potential part so the two terms share a unit.
 *
 * Drift paths are contours of this. Expressed in keV because that is the unit
 * the colour bar and the card are in, and because at the energies drawn the
 * two terms are genuinely comparable — which is exactly why the balance
 * between them decides where a particle can go.
 */
export function driftHamiltonianKeV(
  species: DriftSpecies,
  lShell: number,
  phiRadians: number,
  amplitudeVPerM: number,
): number {
  return species.chargeSign * (totalPotentialV(lShell, phiRadians, amplitudeVPerM) / 1000)
    + energyAtLKeV(species, lShell);
}

export interface DriftRates {
  /** dL/dt, Earth radii per second. E x B only: the magnetic drift is azimuthal. */
  radialLPerS: number;
  /** dphi/dt, radians per second. Negative is westward. */
  angularRadPerS: number;
  /** The E x B part of the angular rate alone, for the card's comparison. */
  exbAngularRadPerS: number;
  /** The gradient/curvature part alone. */
  magneticAngularRadPerS: number;
}

/**
 * The full drift of one equatorially mirroring particle, at one point.
 *
 * The radial component is E x B and nothing else — the gradient/curvature drift
 * of an equatorially mirroring particle in an axisymmetric dipole has no radial
 * component at all, because `grad B` is purely radial and `B x grad B` is
 * therefore purely azimuthal. That is why this layer can ride the plasmasphere
 * machinery so cleanly: the radial transport is the SAME transport, and the
 * only thing the energetic population adds is an azimuthal term.
 */
export function driftRates(
  species: DriftSpecies,
  lShell: number,
  phiRadians: number,
  amplitudeVPerM: number,
): DriftRates {
  const earthRadiusM = RING_CURRENT_CONSTANTS.earthRadiusM;
  const field = equatorialDipoleFieldT(lShell);
  // The analytic derivatives of the potential, exactly as the pipeline's
  // `drift_velocity` writes them.
  const radialFieldVPerM = -(
    2 * amplitudeVPerM * lShell * Math.sin(phiRadians)
    + COROTATION_POTENTIAL_SCALE_V / (earthRadiusM * lShell * lShell)
  );
  const azimuthalFieldVPerM = -amplitudeVPerM * lShell * Math.cos(phiRadians);
  const exbAngularRadPerS = -radialFieldVPerM / (field * lShell * earthRadiusM);
  const magneticAngularRadPerS = magneticDriftAngularRateRadPerS(
    lShell,
    energyAtLKeV(species, lShell),
    species.chargeSign,
  );
  return {
    radialLPerS: azimuthalFieldVPerM / field / earthRadiusM,
    angularRadPerS: exbAngularRadPerS + magneticAngularRadPerS,
    exbAngularRadPerS,
    magneticAngularRadPerS,
  };
}

// ---------------------------------------------------------------------------
// Tracing a drift path
// ---------------------------------------------------------------------------

export interface DriftSample {
  lShell: number;
  phiRadians: number;
  mltHours: number;
  energyKeV: number;
  /** Physical seconds since the first sample of the path. Ascending. */
  elapsedSeconds: number;
}

export type DriftClosure = "closed" | "escaped" | "stalled";

export interface DriftPath {
  samples: DriftSample[];
  /**
   * `closed`  — encircles the Earth without leaving the domain: a TRAPPED
   *             particle. These are the ring current.
   * `escaped` — leaves through the outer edge: swept in from the tail and out
   *             through the dayside, the open drift paths that carry the
   *             injection.
   * `stalled` — ran out of integration budget without doing either, which
   *             happens near a stagnation point where the drift genuinely does
   *             almost stop. Reported, never quietly relabelled.
   */
  closure: DriftClosure;
  seedL: number;
  seedMltHours: number;
  /** Total physical seconds from the first sample to the last. */
  durationSeconds: number;
  minimumL: number;
  maximumL: number;
  /** The energy where the path comes closest to Earth, keV. */
  peakEnergyKeV: number;
  /** MLT at the innermost point, hours. */
  minimumLMltHours: number;
  /** Conserved along the path; the test checks that it is. */
  hamiltonianKeV: number;
  /** Net signed winding in phi, radians. Negative means the path went west. */
  windingRadians: number;
}

export interface TraceLimits {
  lMinimum: number;
  lMaximum: number;
  maximumSteps: number;
  maximumSeconds: number;
  /** The largest change in L allowed in one step. */
  stepLShell: number;
  /** The largest change in phi allowed in one step, radians. */
  stepRadians: number;
}

export const DEFAULT_TRACE_LIMITS: TraceLimits = {
  lMinimum: 1.5,
  lMaximum: 9,
  maximumSteps: 6000,
  maximumSeconds: 14 * 86_400,
  stepLShell: 0.03,
  stepRadians: 0.03,
};

interface RawLeg {
  points: Array<{ lShell: number; phiRadians: number; elapsedSeconds: number }>;
  closure: DriftClosure;
  windingRadians: number;
}

/**
 * One direction of integration, classical fourth-order Runge-Kutta with the
 * step chosen from the local drift so that neither L nor phi moves further than
 * the limits allow.
 *
 * RK4 rather than Euler because the check that matters here is that H stays put
 * — a first-order integrator walks off a contour visibly within one circuit,
 * and a drift path that spirals is a picture of the integrator rather than of
 * the physics. Measured: at these step limits H holds to a few parts in 10^7
 * over a full circuit, which the test pins.
 */
function integrateLeg(
  species: DriftSpecies,
  amplitudeVPerM: number,
  seedL: number,
  seedPhi: number,
  direction: 1 | -1,
  limits: TraceLimits,
): RawLeg {
  const points: RawLeg["points"] = [{ lShell: seedL, phiRadians: seedPhi, elapsedSeconds: 0 }];
  let lShell = seedL;
  let phi = seedPhi;
  let elapsed = 0;
  let winding = 0;
  let closure: DriftClosure = "stalled";

  const derivative = (l: number, p: number) => {
    const rates = driftRates(species, l, p, amplitudeVPerM);
    return { dL: direction * rates.radialLPerS, dPhi: direction * rates.angularRadPerS };
  };

  for (let step = 0; step < limits.maximumSteps; step += 1) {
    const first = derivative(lShell, phi);
    const speedL = Math.abs(first.dL);
    const speedPhi = Math.abs(first.dPhi);
    if (!(speedL > 0) && !(speedPhi > 0)) break;
    let dt = limits.maximumSeconds;
    if (speedL > 0) dt = Math.min(dt, limits.stepLShell / speedL);
    if (speedPhi > 0) dt = Math.min(dt, limits.stepRadians / speedPhi);
    dt = Math.min(dt, limits.maximumSeconds - elapsed);
    if (!(dt > 0)) break;

    const second = derivative(lShell + (first.dL * dt) / 2, phi + (first.dPhi * dt) / 2);
    const third = derivative(lShell + (second.dL * dt) / 2, phi + (second.dPhi * dt) / 2);
    const fourth = derivative(lShell + third.dL * dt, phi + third.dPhi * dt);
    const deltaL = ((first.dL + 2 * second.dL + 2 * third.dL + fourth.dL) / 6) * dt;
    const deltaPhi = ((first.dPhi + 2 * second.dPhi + 2 * third.dPhi + fourth.dPhi) / 6) * dt;

    lShell += deltaL;
    phi += deltaPhi;
    elapsed += dt;
    winding += deltaPhi;
    points.push({ lShell, phiRadians: phi, elapsedSeconds: elapsed });

    if (lShell >= limits.lMaximum || lShell <= limits.lMinimum) {
      closure = "escaped";
      break;
    }
    if (Math.abs(winding) >= 2 * Math.PI) {
      closure = "closed";
      break;
    }
    if (elapsed >= limits.maximumSeconds) break;
  }
  return { points, closure, windingRadians: winding };
}

/**
 * A whole drift path through a seed point.
 *
 * A closed path is finished by the forward leg alone. An open one is not: the
 * seed sits somewhere in the middle of it, and drawing only the forward half
 * would show an ion appearing out of nothing at an arbitrary place. So the
 * backward leg is integrated too and prepended, and the drawn curve then runs
 * from where the particle entered the domain to where it left.
 */
export function traceDriftPath(
  species: DriftSpecies,
  amplitudeVPerM: number,
  seedL: number,
  seedMltHours: number,
  limits: TraceLimits = DEFAULT_TRACE_LIMITS,
): DriftPath {
  const seedPhi = phiFromMltHours(seedMltHours);
  const forward = integrateLeg(species, amplitudeVPerM, seedL, seedPhi, 1, limits);
  let ordered = forward.points;
  let closure = forward.closure;
  let winding = forward.windingRadians;
  if (closure !== "closed") {
    const backward = integrateLeg(species, amplitudeVPerM, seedL, seedPhi, -1, limits);
    // The backward leg's own clock runs from the seed outward; re-based so the
    // whole path's elapsed time is ascending from its first sample.
    const backwardSpan = backward.points[backward.points.length - 1]!.elapsedSeconds;
    const head = backward.points
      .slice(1)
      .reverse()
      .map((point) => ({ ...point, elapsedSeconds: backwardSpan - point.elapsedSeconds }));
    ordered = [
      ...head,
      ...forward.points.map((point) => ({ ...point, elapsedSeconds: point.elapsedSeconds + backwardSpan })),
    ];
    winding = forward.windingRadians - backward.windingRadians;
    if (backward.closure === "escaped" || forward.closure === "escaped") closure = "escaped";
  }

  const samples: DriftSample[] = ordered.map((point) => ({
    lShell: point.lShell,
    phiRadians: point.phiRadians,
    mltHours: mltHoursFromPhi(point.phiRadians),
    energyKeV: energyAtLKeV(species, point.lShell),
    elapsedSeconds: point.elapsedSeconds,
  }));

  let minimumL = Number.POSITIVE_INFINITY;
  let maximumL = 0;
  let minimumLMltHours = seedMltHours;
  for (const sample of samples) {
    if (sample.lShell < minimumL) {
      minimumL = sample.lShell;
      minimumLMltHours = sample.mltHours;
    }
    if (sample.lShell > maximumL) maximumL = sample.lShell;
  }

  return {
    samples,
    closure,
    seedL,
    seedMltHours,
    durationSeconds: samples[samples.length - 1]!.elapsedSeconds,
    minimumL,
    maximumL,
    minimumLMltHours,
    peakEnergyKeV: energyAtLKeV(species, minimumL),
    hamiltonianKeV: driftHamiltonianKeV(species, seedL, seedPhi, amplitudeVPerM),
    windingRadians: winding,
  };
}

/**
 * Where along a path a particle is after this many physical seconds, as an
 * index and a weight between two samples.
 *
 * Both the numbers and the drawn markers go through this one function, so what
 * a test measures is what the scene animates. Time wraps: a closed path is a
 * circuit and a particle on it goes round again, and an open path is a
 * continuing supply from the tail, so a marker that has left re-enters at the
 * start rather than disappearing for good.
 */
export function driftPathPhase(
  path: DriftPath,
  physicalSeconds: number,
): { index: number; weight: number; wrappedSeconds: number } {
  const span = path.durationSeconds;
  if (!(span > 0) || path.samples.length < 2) return { index: 0, weight: 0, wrappedSeconds: 0 };
  const wrapped = ((physicalSeconds % span) + span) % span;
  let low = 0;
  let high = path.samples.length - 1;
  while (high - low > 1) {
    const middle = (low + high) >> 1;
    if (path.samples[middle]!.elapsedSeconds <= wrapped) low = middle;
    else high = middle;
  }
  const from = path.samples[low]!.elapsedSeconds;
  const to = path.samples[low + 1]!.elapsedSeconds;
  const weight = to > from ? (wrapped - from) / (to - from) : 0;
  return { index: low, weight, wrappedSeconds: wrapped };
}

/** The particle's state after this many physical seconds along its path. */
export function sampleDriftPath(path: DriftPath, physicalSeconds: number): DriftSample {
  const { index, weight, wrappedSeconds } = driftPathPhase(path, physicalSeconds);
  const a = path.samples[index]!;
  const b = path.samples[Math.min(index + 1, path.samples.length - 1)]!;
  const lShell = a.lShell + (b.lShell - a.lShell) * weight;
  const phiRadians = a.phiRadians + (b.phiRadians - a.phiRadians) * weight;
  return {
    lShell,
    phiRadians,
    mltHours: mltHoursFromPhi(phiRadians),
    energyKeV: a.energyKeV + (b.energyKeV - a.energyKeV) * weight,
    elapsedSeconds: wrappedSeconds,
  };
}

// ---------------------------------------------------------------------------
// The Alfven layer
// ---------------------------------------------------------------------------

/**
 * The last closed drift path on the midnight meridian, in L, or null when the
 * domain holds no transition.
 *
 * Bisection between an L known to close and an L known to escape. Midnight is
 * the meridian to quote it on because that is the side the plasma sheet feeds:
 * "ions from the tail cannot get inside this L, and ions inside it cannot get
 * out" is the sentence, and it is only a sentence about injection at midnight.
 *
 * Returns the boundary together with the traced path AT the boundary, which is
 * the curve drawn on screen as the Alfven layer.
 */
export function lastClosedDriftPath(
  species: DriftSpecies,
  amplitudeVPerM: number,
  limits: TraceLimits = DEFAULT_TRACE_LIMITS,
  options: { scanFromL?: number; scanToL?: number; scanSteps?: number; bisectionSteps?: number } = {},
): { lShell: number; path: DriftPath } | null {
  const from = options.scanFromL ?? 2;
  const to = options.scanToL ?? limits.lMaximum - 0.2;
  const steps = options.scanSteps ?? 22;
  let closed: number | null = null;
  let open: number | null = null;
  for (let index = 0; index <= steps; index += 1) {
    const l = from + ((to - from) * index) / steps;
    const closure = traceDriftPath(species, amplitudeVPerM, l, 0, limits).closure;
    if (closure === "closed") closed = l;
    // The first escape OUTSIDE a known closed shell is the transition. An
    // escape found before any closed shell is a particle lost inward, which is
    // a different boundary and must not be mistaken for this one.
    else if (closure === "escaped" && closed !== null && open === null) open = l;
  }
  if (closed === null || open === null || !(open > closed)) return null;
  let lower = closed;
  let upper = open;
  for (let step = 0; step < (options.bisectionSteps ?? 18); step += 1) {
    const middle = (lower + upper) / 2;
    if (traceDriftPath(species, amplitudeVPerM, middle, 0, limits).closure === "closed") lower = middle;
    else upper = middle;
  }
  return { lShell: lower, path: traceDriftPath(species, amplitudeVPerM, lower, 0, limits) };
}

// ---------------------------------------------------------------------------
// The whole illustration for one instant
// ---------------------------------------------------------------------------

/** How many drift paths are seeded, and where. */
export const RING_CURRENT_SEEDS = {
  /** Seeds run up the midnight meridian: the side the plasma sheet feeds. */
  mltHours: 0,
  innerL: 2.4,
  outerL: 8,
  count: 15,
} as const;

/**
 * Display cadence, stated in the same voice the plasmasphere's corotation and
 * the solar wind's tracers use.
 *
 * The drift is integrated in PHYSICAL time and replayed at a fixed multiple of
 * it, rather than being given a fixed number of seconds per circuit. That
 * matters: at a fixed seconds-per-circuit every path would take the same time
 * on screen and the energy dependence of the drift — the thing this layer
 * exists to show — would be animated away. At a fixed multiple, a 200 keV ion
 * at L 3 visibly laps a 20 keV ion at L 6, in the ratio the physics says.
 */
export const RING_CURRENT_DRIFT_REPLAY = {
  physicalSecondsPerDisplaySecond: 400,
  /** Markers per drift path. Encodes nothing: it is not a flux. */
  markersPerPath: 5,
} as const;

export interface RingCurrentIllustration {
  species: DriftSpecies;
  /** Volland-Stern amplitude actually used, read from the published frame. */
  amplitudeVPerRe2: number;
  amplitudeVPerM: number;
  kp: number;
  /** The frame this rides on, so the card can quote the same instant. */
  validAt: string;
  paths: DriftPath[];
  /** The Alfven layer for this energy, at midnight. Null when none is in range. */
  separatrix: { lShell: number; path: DriftPath } | null;
  /**
   * The trapped region this boundary encloses, computed ONCE here.
   *
   * It used to be recomputed by whoever drew it, which meant bisecting for the
   * last closed drift path twice for one picture — a few dozen RK4 traces
   * duplicated — and, worse, left open the possibility of the card quoting one
   * boundary while the scene drew another.
   */
  region: TrappedRegion;
  /**
   * The zero-energy limit of the same boundary, on the dusk meridian: the nose
   * of the teardrop, and the reason the plasmapause bulges there.
   */
  zeroEnergySeparatrixL: number;
  /**
   * The same zero-energy boundary at MIDNIGHT, which is the meridian the ion
   * Alfven layer is quoted on. Comparing this with `separatrix` compares like
   * with like: one boundary, two energies, one local time.
   */
  zeroEnergySeparatrixMidnightL: number;
  /** The DGCPM frame's published stagnation L, for the card to show beside it. */
  publishedStagnationL: number;
  closedCount: number;
  escapedCount: number;
  stalledCount: number;
  /** How far in an open (injected) path reaches, and where. */
  deepestPenetration: { lShell: number; mltHours: number; energyKeV: number } | null;
  /** Everything that changes what would be drawn, as one string. */
  rebuildKey: string;
}

/**
 * Build the illustration for one published DGCPM frame.
 *
 * The convection field comes off the frame rather than being recomputed, which
 * is the single most important line in this file: the electric field the ions
 * drift in IS the electric field the plasmasphere on the next layer is being
 * eroded by, at the same instant, at the same measured Kp. If the two ever
 * disagreed, one of the two pictures would be a lie about the other.
 */
export function ringCurrentIllustration(
  field: DgcpmPlasmasphereField,
  species: DriftSpecies = DEFAULT_RING_CURRENT_ION,
  limits: TraceLimits = DEFAULT_TRACE_LIMITS,
): RingCurrentIllustration {
  const amplitudeVPerRe2 = field.frame.convectionAmplitudeVPerRe2;
  const amplitudeVPerM = amplitudeVPerRe2 / RING_CURRENT_CONSTANTS.earthRadiusM;
  const paths: DriftPath[] = [];
  for (let index = 0; index < RING_CURRENT_SEEDS.count; index += 1) {
    const l = RING_CURRENT_SEEDS.innerL
      + ((RING_CURRENT_SEEDS.outerL - RING_CURRENT_SEEDS.innerL) * index) / (RING_CURRENT_SEEDS.count - 1);
    paths.push(traceDriftPath(species, amplitudeVPerM, l, RING_CURRENT_SEEDS.mltHours, limits));
  }
  const separatrix = lastClosedDriftPath(species, amplitudeVPerM, limits);
  const region = trappedDriftRegion(species, amplitudeVPerM, limits);

  let deepestPenetration: RingCurrentIllustration["deepestPenetration"] = null;
  for (const path of paths) {
    if (path.closure !== "escaped") continue;
    if (deepestPenetration === null || path.minimumL < deepestPenetration.lShell) {
      deepestPenetration = {
        lShell: path.minimumL,
        mltHours: path.minimumLMltHours,
        energyKeV: path.peakEnergyKeV,
      };
    }
  }

  return {
    species,
    amplitudeVPerRe2,
    amplitudeVPerM,
    kp: field.frame.kp,
    validAt: field.frame.validAt,
    paths,
    separatrix,
    region,
    zeroEnergySeparatrixL: zeroEnergySeparatrixL(amplitudeVPerM),
    zeroEnergySeparatrixMidnightL: zeroEnergySeparatrixMidnightL(amplitudeVPerM),
    publishedStagnationL: field.frame.stagnationL,
    closedCount: paths.filter((path) => path.closure === "closed").length,
    escapedCount: paths.filter((path) => path.closure === "escaped").length,
    stalledCount: paths.filter((path) => path.closure === "stalled").length,
    deepestPenetration,
    rebuildKey: `rc:${field.frame.validAt}:${species.chargeSign}:${species.referenceEnergyKeV}:${species.referenceL}`,
  };
}


// ---------------------------------------------------------------------------
// How it forms
// ---------------------------------------------------------------------------

/**
 * The formation: a tail supply that arrives, and a trapped population that
 * closes into a ring behind it.
 *
 * ## Why there is motion here again, when motion was deleted from this layer
 *
 * A previous pass removed an animation from this layer and was right to. What
 * it removed was every traced drift path drawn as a LINE with a cloud of
 * sprites marching along it, ON TOP of the region — a diagram laid over the
 * object, and Sean's word for it, twice, was "cartoon". Nothing of that returns.
 *
 * What is added is not an overlay: it is the volume's own density, in the same
 * ray-marched shader, over time. There is no line, no sprite and no marker.
 * The distinction is the whole reason this is admissible where marching dots
 * were not — the object that was buried is now the thing that moves, and the
 * claim it makes is the one the layer's title makes and never delivered:
 *
 *   plasma-sheet ions arrive from the tail, they are trapped, and they drift
 *   westward until they have closed a ring right round the Earth.
 *
 * ## Every number in the motion is traced, not chosen
 *
 * Two computed fields drive it, both out of this module's own RK4 integrator in
 * the frame's own published convection field:
 *
 * 1. **The supply** (`injectionCorridor`). Parcels are seeded across the
 *    nightside outer boundary — the inner edge of the plasma sheet, which is
 *    where storm-time injection delivers ions from — and each one is followed
 *    forward along its own drift path. The map records, for each cell of a
 *    (MLT, L) grid, the elapsed time at which a parcel first reaches it. The
 *    shader lights a cell when the clock passes that time, so what advances
 *    across the screen is a wavefront of arrival, not a particle.
 *
 *    This is the same information the deleted drift-path lines carried. Drawn
 *    as a filled field instead of as curves, it reads as plasma rather than as
 *    a diagram, and no cell of it is a marker of anything countable.
 *
 * 2. **The closing of the ring** (`lapSeconds`). A trapped population does not
 *    appear everywhere at once: ions injected near midnight drift WESTWARD —
 *    midnight to dusk to noon to dawn — and only when they have gone right
 *    round is the ring closed and symmetric. Until then it is a partial ring,
 *    heaviest in the dusk sector, which is what the real storm-time ring
 *    current is. The time to go round is not invented either: it is
 *    `DriftPath.durationSeconds` for the closed path seeded at that shell, so
 *    the inner shells visibly close first, because the drift rate goes as
 *    L^-2 once the L^-3 energisation is folded in.
 *
 * ## What the motion does NOT claim
 *
 * The supply is switched on at t = 0 across the whole nightside boundary at
 * once. A real substorm injection is a transient dipolarisation front, not a
 * step, and this field is the steady field of the frame's own Kp.
 *
 * More important: in a STEADY field a particle outside the Alfven layer can
 * never become trapped inside it — that is what "last closed drift path" means.
 * Real trapping happens because the field is not steady: convection surges, the
 * Alfven layer moves inward, plasma flows deep, and when convection relaxes the
 * boundary expands back out and leaves that plasma on closed paths behind it.
 * That relaxation is stated on the card and is NOT drawn, because the frame
 * publishes one Kp and a second one would be invented.
 *
 * And the decay at the end of the loop is a display ramp, not a computed loss.
 * Charge exchange with the geocorona is what really ends a ring-current ion,
 * and no loss is modelled anywhere in this file. It IS drawn elsewhere on the
 * site, and on the particle rather than on the volume: the transport layer's
 * ion path ends as a straight line the moment it neutralises, and its electron
 * path ends in the atmosphere. See `dungey-transport.ts`. What the ramp here
 * carries is only the SHAPE of a storm — a build and a longer recovery, in
 * that order, which is why `decayFraction` is larger than one and used not to
 * be. The loop returns to a residual rather than to nothing because the
 * quiet-time ring current is never zero, and because a torus that blinks out
 * reads as a rendering fault.
 */
export const RING_CURRENT_FORMATION = {
  /**
   * One hour of drift per second of screen time.
   *
   * Different from `RING_CURRENT_DRIFT_REPLAY`'s 400x, and deliberately: that
   * factor was chosen so a single ion's lap was watchable, and a ring current
   * does not form in one lap. It forms over the hours a storm main phase takes,
   * and at 3600x the whole of it — supply, filling, closing — fits in a loop a
   * visitor will actually stay for. The RELATIVE speeds inside the loop are
   * untouched physics: an inner shell still laps an outer one in the ratio the
   * drift gives.
   */
  physicalSecondsPerDisplaySecond: 3600,
  /** Parcels seeded across the nightside outer boundary. */
  supplySeeds: 41,
  /**
   * The arc they are seeded across, MLT hours through midnight: dusk to dawn
   * the short way. The plasma sheet feeds the nightside; seeding the dayside
   * boundary would draw a supply that does not exist.
   */
  supplyFromMlt: 17,
  supplyToMlt: 31,
  /** The arrival map's grid. */
  mltBins: 96,
  lBins: 60,
  /** The per-shell lookup's resolution. */
  shellBins: 72,
  /**
   * Hold and decay, as fractions of the fill.
   *
   * ## WHY THE DECAY IS LONGER THAN THE FILL, AND WHY IT DID NOT USE TO BE
   *
   * These shipped at 0.26 and 0.26, which made the emptying nearly four times
   * FASTER than the filling. A real ring current does the opposite, and not
   * marginally: a storm's main phase builds it over hours and the recovery
   * unwinds it over something between ten hours and days. So the drawn loop
   * had the asymmetry backwards, and a reader watching a rhythmic throb with a
   * quick collapse would have taken away a shape that no magnetometer has ever
   * recorded — the picture implying something the words then walk back, which
   * is the exact pattern this site exists to avoid.
   *
   * The fix is the SHAPE of one cycle, not the repetition. The repetition is
   * honest and stays: see `RING_CURRENT_PULSE` for why a modulo is the right
   * clock for a layer whose whole subject is a process, and for the two ways a
   * period quoted here can be false. What changed is that one cycle now reads
   * as a storm — a build, a brief turn, and a longer unwinding — so a reader
   * who does not know it is a loop still comes away with the right shape, and a
   * reader who does know is told the repeat is the replay restarting.
   *
   * The exact ratio is a DISPLAY CHOICE and is not a recovery time. The only
   * claim it makes is the direction: the emptying takes longer than the
   * filling. That is unambiguous physics whatever `fillSeconds` happens to
   * measure, which is why no hours are printed against it anywhere. The value
   * is bounded at the other end by legibility rather than by nature — real
   * recoveries run far longer than 1.5 fills, and a loop that spent nine
   * tenths of itself fading would stop showing the formation the layer is
   * named for. The decay stays a DISPLAY RAMP: no loss is modelled anywhere in
   * this file, and the two losses that ARE drawn on this site are drawn on the
   * transport path in `dungey-transport.ts`, on the particles themselves.
   */
  holdFraction: 0.10,
  decayFraction: 1.50,
  /**
   * What the trapped population falls back to between loops, as a fraction of
   * full. Not zero: the quiet-time ring current is not zero.
   */
  residualFill: 0.20,
  /**
   * Half the local-time sector the supply is delivered into, hours from
   * midnight.
   *
   * Not a point. Substorm injections are seen across a broad sector around
   * midnight — McIlwain's injection boundary, roughly 21 to 03 MLT — so the
   * nightside is fed from the start and the front propagates westward from the
   * DUSK end of that sector. Feeding one meridian instead put a knife edge in
   * the picture at midnight, where the head of the filled arc met its own tail.
   *
   * CORRECTNESS NOTE 2026-09-04: 4 hours is +-4, which is 20 to 04 MLT — a
   * third wider than the 21-03 the sentence above cites. The extra hour at each
   * end is a drawing choice, not the citation: at +-3 the feathered filling edge
   * (`fillFeatherRadians`, 0.75 rad = 1.4 h of local time) eats most of the
   * sector and the supply reads as a point source again. Left at 4 and said out
   * loud rather than quietly attributed to McIlwain.
   */
  injectionHalfWidthMltHours: 4,
  /** How soft the westward filling edge is, radians of local time. */
  fillFeatherRadians: 0.75,
  /**
   * How much wider that edge gets per radian already swept.
   *
   * A real injection is not monoenergetic: the plasma sheet delivers a spread
   * of energies, the gradient/curvature drift rate is proportional to energy,
   * and so the fast end of the population runs ahead of the slow end and the
   * front smears as it goes round. This layer draws ONE energy at a time — the
   * visitor picks which — so nothing in the trace produces that spread, and
   * without it the drawn front stays a hard edge for a whole lap. Declared as
   * a display consequence of a real dispersion rather than smuggled in as a
   * blur.
   */
  frontDispersionPerRadian: 0.30,
  /** How soft the arriving supply's front is, as a fraction of the fill time. */
  frontFeatherFraction: 0.05,
  /**
   * The drift stalls as it approaches the Alfven layer — the lap time there
   * genuinely diverges — so the outermost shells would never close on any
   * loop a visitor waits out. Lap times are capped at this multiple of the
   * median so the outer edge closes LAST and slowest, which is true, rather
   * than never, which would read as a hole in the render.
   */
  lapCapFactor: 2.4,
} as const;

/**
 * Where plasma seeded at the nightside outer boundary has got to, and when.
 *
 * `arrivalSeconds` is Infinity in a cell no traced parcel reaches; those cells
 * stay dark for the whole loop, which is the honest answer — the supply does
 * not go everywhere.
 */
export interface InjectionCorridor {
  mltBins: number;
  lBins: number;
  lMinimum: number;
  lMaximum: number;
  /** Seconds from the supply switching on, per cell, row-major (L outer). */
  arrivalSeconds: Float64Array;
  /** 0-1 taper, so the corridor has an edge rather than a staircase. */
  weight: Float32Array;
  /** The time by which the drawn corridor is essentially complete, seconds. */
  spanSeconds: number;
  seedCount: number;
  reachedCells: number;
}

function percentile(values: number[], fraction: number): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const at = Math.min(sorted.length - 1, Math.max(0, Math.round((sorted.length - 1) * fraction)));
  return sorted[at]!;
}

export function injectionCorridor(
  species: DriftSpecies,
  amplitudeVPerM: number,
  limits: TraceLimits = DEFAULT_TRACE_LIMITS,
  options: { innerL?: number } = {},
): InjectionCorridor {
  const { mltBins, lBins, supplySeeds, supplyFromMlt, supplyToMlt } = RING_CURRENT_FORMATION;
  const lMinimum = options.innerL ?? limits.lMinimum;
  const lMaximum = limits.lMaximum;
  const lSpan = lMaximum - lMinimum;
  const arrivalSeconds = new Float64Array(mltBins * lBins).fill(Number.POSITIVE_INFINITY);

  // Seeded just inside the domain edge: a parcel seeded ON the edge is
  // classified as escaped before it has moved.
  const seedL = lMaximum - 0.06;
  for (let seed = 0; seed < supplySeeds; seed += 1) {
    const mlt = supplyFromMlt + ((supplyToMlt - supplyFromMlt) * seed) / (supplySeeds - 1);
    const path = traceDriftPath(species, amplitudeVPerM, seedL, ((mlt % 24) + 24) % 24, limits);
    for (const sample of path.samples) {
      if (sample.lShell < lMinimum || sample.lShell > lMaximum) continue;
      const lBin = Math.min(lBins - 1, Math.max(0, Math.floor(((sample.lShell - lMinimum) / lSpan) * lBins)));
      const mltBin = Math.min(mltBins - 1, Math.max(0, Math.floor((sample.mltHours / 24) * mltBins)));
      // Deposited into the cell and its eight neighbours. A traced path is a
      // curve of zero width and the plasma it stands for is not; without the
      // spread, forty parcels draw forty filaments, which is the line diagram
      // this layer had deleted from it.
      for (let dl = -1; dl <= 1; dl += 1) {
        const row = lBin + dl;
        if (row < 0 || row >= lBins) continue;
        for (let dm = -1; dm <= 1; dm += 1) {
          const column = (((mltBin + dm) % mltBins) + mltBins) % mltBins;
          const index = row * mltBins + column;
          if (sample.elapsedSeconds < arrivalSeconds[index]!) arrivalSeconds[index] = sample.elapsedSeconds;
        }
      }
    }
  }

  // One dilation pass, for the same reason `trappedDriftRegion` fills a bin the
  // contour never visited: a gap between two adjacent parcels is a sampling
  // artifact of the trace, not a place the plasma does not reach.
  const dilated = Float64Array.from(arrivalSeconds);
  for (let row = 0; row < lBins; row += 1) {
    for (let column = 0; column < mltBins; column += 1) {
      const index = row * mltBins + column;
      if (Number.isFinite(arrivalSeconds[index]!)) continue;
      let best = Number.POSITIVE_INFINITY;
      for (let dl = -1; dl <= 1; dl += 1) {
        const neighbourRow = row + dl;
        if (neighbourRow < 0 || neighbourRow >= lBins) continue;
        for (let dm = -1; dm <= 1; dm += 1) {
          const neighbourColumn = (((column + dm) % mltBins) + mltBins) % mltBins;
          const value = arrivalSeconds[neighbourRow * mltBins + neighbourColumn]!;
          if (value < best) best = value;
        }
      }
      dilated[index] = best;
    }
  }

  const reached: number[] = [];
  const weight = new Float32Array(mltBins * lBins);
  for (let index = 0; index < dilated.length; index += 1) {
    if (Number.isFinite(dilated[index]!)) {
      weight[index] = 1;
      reached.push(dilated[index]!);
    }
  }
  // One box pass, so the corridor fades out at its edges instead of ending on a
  // grid line. Two smeared the shape the drift traced out into a blob, which is
  // the opposite of the point: the corridor is supposed to look like plasma
  // following a path, not like a cloud parked outside the boundary.
  let smoothed = weight;
  for (let pass = 0; pass < 1; pass += 1) {
    const next = new Float32Array(smoothed.length);
    for (let row = 0; row < lBins; row += 1) {
      for (let column = 0; column < mltBins; column += 1) {
        let total = 0;
        let count = 0;
        for (let dl = -1; dl <= 1; dl += 1) {
          const neighbourRow = row + dl;
          if (neighbourRow < 0 || neighbourRow >= lBins) continue;
          for (let dm = -1; dm <= 1; dm += 1) {
            const neighbourColumn = (((column + dm) % mltBins) + mltBins) % mltBins;
            total += smoothed[neighbourRow * mltBins + neighbourColumn]!;
            count += 1;
          }
        }
        next[row * mltBins + column] = count > 0 ? total / count : 0;
      }
    }
    smoothed = next;
  }

  // The span is a percentile, not the maximum: one parcel that stagnates near
  // the dusk stagnation point can take days, and letting it set the clock would
  // hold the whole loop open waiting for a cell nobody can see. Three quarters
  // is where the drawn corridor stops changing to the eye — the last quarter is
  // stragglers creeping along the dayside edge.
  const spanSeconds = Math.max(1, percentile(reached, 0.75));
  return {
    mltBins,
    lBins,
    lMinimum,
    lMaximum,
    arrivalSeconds: dilated,
    weight: smoothed,
    spanSeconds,
    seedCount: supplySeeds,
    reachedCells: reached.length,
  };
}

/** The whole timing of the formation loop, in physical seconds. */
export interface RingCurrentFormation {
  corridor: InjectionCorridor;
  shellBins: number;
  shellLMinimum: number;
  shellLMaximum: number;
  /** Seconds for a drift path through this shell to go right round. */
  lapSeconds: Float64Array;
  /** Seconds until the supply first reaches this shell. */
  seedSeconds: Float64Array;
  /** The largest lap drawn, for normalising a texture. */
  lapSpanSeconds: number;
  fillSeconds: number;
  holdSeconds: number;
  decaySeconds: number;
  cycleSeconds: number;
  /** The lap the card quotes, at the region's own middle. */
  representativeLapSeconds: number;
}

/**
 * The formation timings for one illustration, all of them read off traced
 * paths rather than chosen.
 *
 * `illustration.paths` is reused rather than re-traced: those fifteen paths are
 * already integrated up the midnight meridian, they already carry
 * `durationSeconds`, and for a CLOSED path that duration is exactly the lap
 * time at its seed shell. Re-tracing would cost the same numbers twice.
 */
export function ringCurrentFormation(
  illustration: RingCurrentIllustration,
  region: TrappedRegion,
  limits: TraceLimits = DEFAULT_TRACE_LIMITS,
): RingCurrentFormation {
  const corridor = injectionCorridor(illustration.species, illustration.amplitudeVPerM, limits, {
    innerL: region.innerL,
  });
  const shellBins = RING_CURRENT_FORMATION.shellBins;
  let widestL = region.innerL;
  for (let index = 0; index < region.outerL.length; index += 1) {
    if (region.outerL[index]! > widestL) widestL = region.outerL[index]!;
  }
  const shellLMinimum = region.innerL;
  const shellLMaximum = Math.max(widestL, region.innerL + 0.2);

  const closed = illustration.paths
    .filter((path) => path.closure === "closed" && path.durationSeconds > 0)
    .map((path) => ({ lShell: path.seedL, seconds: path.durationSeconds }))
    .sort((a, b) => a.lShell - b.lShell);

  const lapSeconds = new Float64Array(shellBins);
  for (let bin = 0; bin < shellBins; bin += 1) {
    const l = shellLMinimum + ((shellLMaximum - shellLMinimum) * bin) / (shellBins - 1);
    if (closed.length === 0) {
      // No closed path was traced at all. The lap of a purely gradient-drifting
      // ion is the honest fallback and it is arithmetic, not a guess.
      lapSeconds[bin] = magneticDriftPeriodHours(l, energyAtLKeV(illustration.species, l)) * 3600;
      continue;
    }
    if (l <= closed[0]!.lShell) {
      // Outside the traced span, scaled by the drift's own law: the energy
      // falls as L^-3 and the rate goes as W L, so the lap goes as L^2.
      lapSeconds[bin] = closed[0]!.seconds * (l / closed[0]!.lShell) ** 2;
      continue;
    }
    const last = closed[closed.length - 1]!;
    if (l >= last.lShell) {
      lapSeconds[bin] = last.seconds * (l / last.lShell) ** 2;
      continue;
    }
    let upper = 1;
    while (upper < closed.length - 1 && closed[upper]!.lShell < l) upper += 1;
    const a = closed[upper - 1]!;
    const b = closed[upper]!;
    const weight = (l - a.lShell) / Math.max(1e-6, b.lShell - a.lShell);
    lapSeconds[bin] = a.seconds + (b.seconds - a.seconds) * weight;
  }
  const lapCap = percentile(Array.from(lapSeconds), 0.5) * RING_CURRENT_FORMATION.lapCapFactor;
  for (let bin = 0; bin < shellBins; bin += 1) lapSeconds[bin] = Math.min(lapSeconds[bin]!, lapCap);

  const seedSeconds = new Float64Array(shellBins);
  // Walked from the OUTSIDE IN, because that is the direction the supply
  // travels and because of what happens below the deepest shell it reaches.
  //
  // In a steady field the supply cannot get inside the Alfven layer at all —
  // that is what "last closed drift path" means — so most of the drawn shells
  // have no arrival time of their own. Filling them only once the whole
  // corridor is finished would leave the ring sitting at its residual through
  // most of the loop, which is the fault this animation exists to fix: the
  // layer promising a process and showing an object. Each unreached shell
  // therefore starts when the DEEPEST shell the supply does reach starts, which
  // is the earliest moment anything got that far in, and the westward lap then
  // does the rest at that shell's own traced rate.
  let deepestReached = Number.POSITIVE_INFINITY;
  for (let bin = shellBins - 1; bin >= 0; bin -= 1) {
    const l = shellLMinimum + ((shellLMaximum - shellLMinimum) * bin) / (shellBins - 1);
    const row = Math.min(
      corridor.lBins - 1,
      Math.max(0, Math.floor(((l - corridor.lMinimum) / (corridor.lMaximum - corridor.lMinimum)) * corridor.lBins)),
    );
    let earliest = Number.POSITIVE_INFINITY;
    for (let column = 0; column < corridor.mltBins; column += 1) {
      const value = corridor.arrivalSeconds[row * corridor.mltBins + column]!;
      if (value < earliest) earliest = value;
    }
    if (Number.isFinite(earliest)) deepestReached = earliest;
    seedSeconds[bin] = Number.isFinite(deepestReached) ? deepestReached : 0;
  }

  // A shell is closed when the front has swept from the dusk end of the
  // injection sector right round to its dawn end, which is less than a whole
  // lap by the width of the sector itself.
  const injectionHalfAngle = (RING_CURRENT_FORMATION.injectionHalfWidthMltHours * Math.PI) / 12;
  const lapFractionToClose = (2 * Math.PI - 2 * injectionHalfAngle) / (2 * Math.PI);
  const closes: number[] = [];
  for (let bin = 0; bin < shellBins; bin += 1) {
    closes.push(seedSeconds[bin]! + lapSeconds[bin]! * lapFractionToClose);
  }
  // The time by which most of the drawn shells have gone right round. Not the
  // maximum: the outermost shell is the slowest by physics, and it is allowed
  // to still be closing when the hold begins.
  // Long enough for most shells to have gone round, and never shorter than the
  // supply's own sweep: the loop must not switch the tail off while plasma is
  // still visibly arriving from it.
  const fillSeconds = Math.max(600, percentile(closes, 0.85), corridor.spanSeconds * 1.15);
  const holdSeconds = fillSeconds * RING_CURRENT_FORMATION.holdFraction;
  const decaySeconds = fillSeconds * RING_CURRENT_FORMATION.decayFraction;
  let lapSpanSeconds = 1;
  for (let bin = 0; bin < shellBins; bin += 1) lapSpanSeconds = Math.max(lapSpanSeconds, lapSeconds[bin]!);

  return {
    corridor,
    shellBins,
    shellLMinimum,
    shellLMaximum,
    lapSeconds,
    seedSeconds,
    lapSpanSeconds,
    fillSeconds,
    holdSeconds,
    decaySeconds,
    cycleSeconds: fillSeconds + holdSeconds + decaySeconds,
    representativeLapSeconds: lapSeconds[Math.floor(shellBins / 2)]!,
  };
}

// ---------------------------------------------------------------------------
// The pulse
// ---------------------------------------------------------------------------

/**
 * WHY THIS LAYER PULSES, AND WHETHER THE RHYTHM MEANS ANYTHING.
 *
 * Sean, watching the shipped build: what is the pulsing, and is its periodicity
 * real? It is real, it is exact, and nothing on the page said so.
 *
 * The pulse is `ringCurrentFormation`'s loop, and only that. The trapped
 * population fills as the traced drift fills it, holds, and ramps back to its
 * quiet-time residual; `setRingCurrentVolumeTime` then wraps the clock with
 * `physical % cycleSeconds` and it all happens again. A modulo is exactly
 * periodic, so the period is exactly `cycleSeconds` of drift — and, replayed at
 * `RING_CURRENT_FORMATION.physicalSecondsPerDisplaySecond`, exactly
 * `cycleSeconds / 3600` seconds on screen.
 *
 * ## The trap this note exists to avoid
 *
 * "Pulse period is X" is a sentence with two ways of being false here.
 *
 * 1. **A DRIFT LAP IS NOT THE PULSE, and there is no single drift lap.** Every
 *    shell has its own — that is the whole point of replaying at a fixed
 *    MULTIPLE of physical time rather than at a fixed seconds-per-circuit, as
 *    `RING_CURRENT_DRIFT_REPLAY` says at length. Measured on the 2026-08-08
 *    fixture at Kp 5.67 for the default 10 keV ion: L 2 closes in 0.60 h and
 *    L 6.08 in 6.86 h, an eleven-fold spread. Quoting any one of them as "the"
 *    period would state as a single number the very thing this layer is drawn
 *    to show is not one.
 *
 *    What IS one number is the loop that contains them all. So the quoted
 *    period is the loop's, and the spread of laps inside it is quoted as a
 *    spread, on the layer's card, beside it.
 *
 * 2. **The SHAPE of one cycle has to be a storm's, or the repetition teaches a
 *    throb.** This is the trap the first two versions of this note walked past.
 *    Saying "the repeat is a replay" on the card does not undo a picture whose
 *    single cycle fills slowly and collapses quickly, because that collapse is
 *    a claim about the physics all on its own — and it was the wrong way round.
 *    `RING_CURRENT_FORMATION.decayFraction` now makes the emptying longer than
 *    the filling, which is the one thing about a storm's Dst curve that is not
 *    in doubt. The ratio itself is a display choice and no recovery time is
 *    printed anywhere against it.
 *
 * 3. **The REPETITION is a replay, not a recurring storm.** The rate is
 *    computed — every second of it is traced drift in the frame's own published
 *    convection field — but the fact that it happens AGAIN is the loop
 *    restarting, and the decay at the end of it is a display ramp rather than a
 *    modelled loss. The surfaces say "replayed" for that reason.
 *
 * ## What moves the number
 *
 * `cycleSeconds` is `fillSeconds * (1 + holdFraction + decayFraction)`, and
 * `fillSeconds` is read off the traced closing times, so the period follows the
 * ion the visitor picked and the Kp of the frame they are on. Measured across
 * the fixture it runs from 5.73 s on screen (30 keV, Kp 5.67) to 76.84 s
 * (3 keV, Kp 0.33), a factor of thirteen — the same factor as before the
 * storm-shaped decay lengthened the loop, because that change multiplies every
 * period by the same 1.71. Nothing here may ever be hardcoded:
 * an energy selector that moves while the quoted period sits still would be a
 * worse defect than the silence this replaces.
 */
export const RING_CURRENT_PULSE = {
  /**
   * How far the legend's colour bar dims at the bottom of the loop, as an
   * opacity.
   *
   * The PHASE and the RATE of the swatch are the population's own, exactly —
   * same clock, same wrap, same envelope, so the bar and the globe cannot
   * disagree. The DEPTH is a display choice, and is declared here because of
   * it: the population itself falls to `residualFill`, 0.20, and a legend bar
   * at a fifth of its own colour is a legend nobody can read. So the drawn
   * range is the population's level remapped onto 0.55 to 1, which breathes
   * legibly without becoming a light show. Sean's standing rule for this site
   * is "nothing gimmicky, nothing stupid", and a colour bar that flashed,
   * glowed or cycled hue would be all three.
   */
  swatchFloor: 0.55,
} as const;

/** GLSL's `smoothstep`, on the CPU, so the swatch and the shader share a curve. */
function smoothstep(edge0: number, edge1: number, at: number): number {
  if (!(edge1 > edge0)) return at < edge0 ? 0 : 1;
  const t = Math.min(1, Math.max(0, (at - edge0) / (edge1 - edge0)));
  return t * t * (3 - 2 * t);
}

/**
 * Where in its loop the formation is, in PHYSICAL seconds, after this much
 * display time.
 *
 * The same wrap `setRingCurrentVolumeTime` applies to the shader's own
 * `formationSeconds` uniform, from the same replay constant. Anything that
 * reads the pulse's phase goes through this, so nothing can fall out of step
 * with what is drawn by keeping a second copy of the arithmetic.
 */
export function ringCurrentLoopSeconds(cycleSeconds: number, elapsedDisplaySeconds: number): number {
  if (!(cycleSeconds > 0)) return 0;
  const physical = elapsedDisplaySeconds * RING_CURRENT_FORMATION.physicalSecondsPerDisplaySecond;
  return ((physical % cycleSeconds) + cycleSeconds) % cycleSeconds;
}

/** The pulse's period in seconds of screen time. Exact: the clock is a modulo. */
export function ringCurrentPulsePeriodDisplaySeconds(
  formation: Pick<RingCurrentFormation, "cycleSeconds">,
): number {
  return formation.cycleSeconds / RING_CURRENT_FORMATION.physicalSecondsPerDisplaySecond;
}

/**
 * How full the trapped population is, taken as a whole, this far into the loop:
 * `residualFill` at the bottom of it and 1 at the top.
 *
 * The volume's shader computes this PER CELL, because a shell the westward
 * front has not reached yet is still at the residual while its neighbour is
 * full — that staggering IS the ring closing, and it is the thing one number
 * cannot carry. What this returns is the aggregate the eye reads as the pulse,
 * and it is built from the shader's own two factors on the shader's own clock:
 *
 *   `storm`  — character for character the fragment shader's own expression:
 *              the ramp back to the residual at the end of the loop.
 *   `closed` — the fill, aggregated. By construction `fillSeconds` is the 85th
 *              percentile of the shells' own closing times, so the ring is
 *              essentially shut when it elapses.
 *
 * A test pins the first against the shader source and the second against the
 * loop's own boundaries, so the swatch cannot quietly stop meaning the picture.
 */
export function ringCurrentFormationLevel(
  formation: Pick<RingCurrentFormation, "fillSeconds" | "holdSeconds" | "decaySeconds" | "cycleSeconds">,
  elapsedDisplaySeconds: number,
): number {
  if (!(formation.cycleSeconds > 0)) return 1;
  const at = ringCurrentLoopSeconds(formation.cycleSeconds, elapsedDisplaySeconds);
  const decayStart = formation.fillSeconds + formation.holdSeconds;
  const storm = 1 - smoothstep(decayStart, decayStart + formation.decaySeconds, at);
  const closed = smoothstep(0, formation.fillSeconds, at);
  const residual = RING_CURRENT_FORMATION.residualFill;
  return residual + (1 - residual) * closed * storm;
}

/**
 * The spread of drift laps the loop contains, at the two ends of the drawn
 * region — the honest answer to "so what IS the period", after the loop's own.
 */
export function ringCurrentLapSpread(formation: RingCurrentFormation): {
  innerL: number;
  innerHours: number;
  outerL: number;
  outerHours: number;
} {
  return {
    innerL: formation.shellLMinimum,
    innerHours: formation.lapSeconds[0]! / 3600,
    outerL: formation.shellLMaximum,
    outerHours: formation.lapSeconds[formation.shellBins - 1]! / 3600,
  };
}

/**
 * Drive one element's `--legend-pulse` custom property from the formation's own
 * clock.
 *
 * Called from the scene's animation frame with the SAME
 * `environmentalAnimationElapsedSeconds` that is handed to
 * `setRingCurrentDisplayTime` beside it, which is what makes the agreement
 * between the swatch and the globe structural rather than a coincidence of two
 * similar durations. A CSS animation with a typed duration would have been the
 * other thing: a rhythm that looks synchronised until it is measured, which is
 * the false periodicity this whole change exists to cure.
 *
 * `formation` is null when nothing is pulsing — the layer is off, or the
 * visitor has environmental motion off, which is what `prefers-reduced-motion`
 * turns off by default — and the bar then sits at full, exactly as every other
 * layer's bar is drawn.
 */
export function paintRingCurrentPulse(
  surface: { style: { setProperty(property: string, value: string): void } } | null,
  formation: Pick<RingCurrentFormation, "fillSeconds" | "holdSeconds" | "decaySeconds" | "cycleSeconds"> | null,
  elapsedDisplaySeconds: number,
): void {
  if (!surface) return;
  const floor = RING_CURRENT_PULSE.swatchFloor;
  const residual = RING_CURRENT_FORMATION.residualFill;
  const level = formation ? ringCurrentFormationLevel(formation, elapsedDisplaySeconds) : 1;
  const across = Math.min(1, Math.max(0, (level - residual) / (1 - residual)));
  surface.style.setProperty("--legend-pulse", (floor + (1 - floor) * across).toFixed(3));
}

// ---------------------------------------------------------------------------
// Drawing it
// ---------------------------------------------------------------------------

/**
 * The colour ramp, and the units under it.
 *
 * The quantity is the drifting particle's own kinetic energy, which is a real
 * computed number rather than a stylised brightness — and the label carries
 * ILLUSTRATION in the bar itself, because the bar is the one thing a reader
 * looks at without opening anything.
 *
 * The range spans the ring current and then some: a few keV in the plasma sheet
 * at the outer edge, tens to a few hundred keV where the ring current lives,
 * and past that at the inner turning points, where the same adiabatic transport
 * starts making radiation-belt energies out of the same population.
 */
/**
 * The ramp the VOLUME is shaded from. The legend's CSS gradient is DERIVED from
 * this array, never written beside it.
 *
 * It used to be written twice: this array for the shader and a hand-typed
 * `linear-gradient(...)` string for the legend swatch. They agreed, and nothing
 * made them agree -- the test checked only that the two END hexes appeared in
 * the string, so the three middle stops could drift apart silently and the key
 * would stop describing the picture it sits beside. Every other ramp on this
 * site (the belts, the thermosphere) already derives its gradient from its hex
 * array; the ring current was the one that did not.
 */
export const ENERGY_RAMP_STOPS: ReadonlyArray<{ at: number; colour: readonly [number, number, number] }> = [
  { at: 0, colour: [0.169, 0.078, 0.212] },
  { at: 0.3, colour: [0.482, 0.184, 0.561] },
  { at: 0.58, colour: [0.878, 0.353, 0.541] },
  { at: 0.8, colour: [1, 0.604, 0.361] },
  { at: 1, colour: [1, 0.902, 0.659] },
];

/** `#rrggbb` for one ramp stop's linear-RGB triple. */
function rampStopHex(colour: readonly [number, number, number]): string {
  const channel = (v: number) => Math.round(Math.min(1, Math.max(0, v)) * 255).toString(16).padStart(2, "0");
  return `#${channel(colour[0])}${channel(colour[1])}${channel(colour[2])}`;
}

/** The legend swatch, built from the stops the shader uses. One copy of the colour. */
export function energyRampGradientCss(): string {
  const stops = ENERGY_RAMP_STOPS.map(({ at, colour }) => {
    const hex = rampStopHex(colour);
    return at === 0 || at === 1 ? hex : `${hex} ${Math.round(at * 100)}%`;
  });
  return `linear-gradient(90deg, ${stops.join(", ")})`;
}

export const RING_CURRENT_ENERGY_SCALE = {
  minimumKeV: 1,
  maximumKeV: 1000,
  gradient: energyRampGradientCss(),
  minimumLabel: "1",
  maximumLabel: "1,000",
  // THE CLAIM LEADS. Measured on the shipped legend width, it was the part
  // that got ellipsised off the end ("... · ILLUSTRAT…"), which is exactly the
  // wrong half to lose: this bar is the one surface that is on screen with
  // every panel shut. Leading with it means a narrow legend can only ever
  // truncate the units, which the card repeats anyway.
  //
  // The word changed on 2026-08-19 with the layer's evidence class, from
  // ILLUSTRATION to MODEL-DERIVED. ILLUSTRATION was right for the drift-path
  // lines with sprites marching along them that this replaced; it is wrong for
  // a volume RK4-integrated in NOAA's own published convection field. What did
  // NOT change is the second half of the claim, which is the load-bearing one:
  // no upstream publishes a gridded ring current, so the SHAPE is derived and
  // never observed. The card and the badge both still say so in those words.
  label: "MODEL-DERIVED · ION ENERGY · keV · LOG",
} as const;


/** Position on the ramp, 0-1, for an energy in keV. Log, like the label says. */
export function energyRampPosition(energyKeV: number): number {
  const minimum = Math.log10(RING_CURRENT_ENERGY_SCALE.minimumKeV);
  const maximum = Math.log10(RING_CURRENT_ENERGY_SCALE.maximumKeV);
  const value = Math.log10(Math.max(energyKeV, 1e-6));
  return Math.min(1, Math.max(0, (value - minimum) / (maximum - minimum)));
}

/** The ramp itself, on the CPU. The marker shader carries the same stops. */
export function energyRampColour(energyKeV: number): [number, number, number] {
  const t = energyRampPosition(energyKeV);
  for (let index = 1; index < ENERGY_RAMP_STOPS.length; index += 1) {
    const previous = ENERGY_RAMP_STOPS[index - 1]!;
    const next = ENERGY_RAMP_STOPS[index]!;
    if (t <= next.at) {
      const span = next.at - previous.at;
      const weight = span > 0 ? (t - previous.at) / span : 0;
      return [
        previous.colour[0] + (next.colour[0] - previous.colour[0]) * weight,
        previous.colour[1] + (next.colour[1] - previous.colour[1]) * weight,
        previous.colour[2] + (next.colour[2] - previous.colour[2]) * weight,
      ];
    }
  }
  const last = ENERGY_RAMP_STOPS[ENERGY_RAMP_STOPS.length - 1]!.colour;
  return [last[0], last[1], last[2]];
}

export type GsmMapper = (xRe: number, yRe: number, zRe: number) => THREE.Vector3;

export interface RingCurrentGeometryOptions {
  positionForGsm: GsmMapper;
  /**
   * The globe's drawn radius in scene units.
   *
   * Present, the region is drawn as a ray-marched VOLUME rather than a surface
   * — the ray marcher needs the ruler directly, because it inverts it per
   * sample rather than mapping a fixed set of vertices. Absent, the flat
   * surface is drawn, which is what the module's own tests exercise.
   */
  earthSceneRadius?: number;
}

/**
 * Drawn positions for every sample of every path, in scene units.
 *
 * EVERY radius goes through the caller's mapper, which is the scene's one
 * shared radial ruler — nothing in this module knows or assumes how far out
 * L = 4 is drawn, so the illustration follows the visitor's choice between the
 * teaching scale and true distance without a second code path.
 */
function drawnPathPositions(path: DriftPath, positionForGsm: GsmMapper): Float32Array {
  const out = new Float32Array(path.samples.length * 3);
  for (let index = 0; index < path.samples.length; index += 1) {
    const sample = path.samples[index]!;
    const gsm = gsmFromDrift(sample.lShell, sample.phiRadians);
    const point = positionForGsm(gsm.x, gsm.y, gsm.z);
    out[index * 3] = point.x;
    out[index * 3 + 1] = point.y;
    out[index * 3 + 2] = point.z;
  }
  return out;
}

/** What `setRingCurrentDisplayTime` needs, hung off the marker object. */
export interface RingCurrentMotionState {
  paths: DriftPath[];
  /** Drawn positions per path, parallel to `paths`. */
  drawnPositions: Float32Array[];
  /** Which path each marker belongs to. */
  markerPath: Int32Array;
  /** The marker's phase offset along its path, in physical seconds. */
  markerOffsetSeconds: Float64Array;
  positions: THREE.BufferAttribute;
  logEnergy: THREE.BufferAttribute;
  alpha: THREE.BufferAttribute;
}

/**
 * The drift paths as line segments, coloured by the particle's own energy.
 *
 * Vertex colours rather than one colour per path: a single open path spans a
 * factor of ten in energy between where it enters and where it turns around,
 * and colouring it flat would hide the energisation that is the point.
 */
// ---------------------------------------------------------------------------
// The trapped region
// ---------------------------------------------------------------------------

/**
 * The area in which an ion of this species and energy stays trapped.
 *
 * The drift paths already drawn show HOW ions move. This shows WHERE the
 * closed ones live: the region bounded by the last closed drift path — the
 * Alfvén layer — inside which a particle circles the Earth indefinitely, and
 * outside which the convection field carries it away through the dayside.
 *
 * It is bounded by a computed contour, not sketched. Every outer radius comes
 * from `lastClosedDriftPath`, which bisects for the last L whose path closes,
 * so the shape is the field's own answer at the stated Kp.
 *
 * The opacity is FLAT, on purpose. Varying it with anything — energy, distance,
 * a notional density — would read as "there is more ring current here", and
 * this site publishes no ring-current density on a grid at all. The colour says
 * what energy an ion has at that distance; the fill says only "inside this, it
 * is trapped".
 */
export interface TrappedRegion {
  /** L of the last closed drift path at midnight, the Alfvén layer. */
  boundaryL: number;
  /** MLT of each sampled azimuth, hours. */
  mltHours: Float64Array;
  /** Outer L at each azimuth. */
  outerL: Float64Array;
  /** Inner edge of the drawn region. */
  innerL: number;
  /**
   * True when no open drift path was found inside the traced domain, so the
   * real boundary lies beyond it. The region is then drawn to the domain edge
   * and the caller must say so — drawing nothing would read as "no ring
   * current", which is the opposite of what a very quiet field means.
   */
  clippedToDomain: boolean;
  /**
   * Whether the drawn boundary TOUCHES the integration domain at any local
   * time, even though a last closed path was found at midnight.
   *
   * `clippedToDomain` answers a different question - whether any path inside
   * the domain opened at all - and it is false in exactly the case this flag
   * exists for. The Alfven layer is found by bisecting the seed radius on the
   * MIDNIGHT meridian, but the contour through that seed is widest at DAWN,
   * and `traceDriftPath` stops at `limits.lMaximum`. So a boundary that closes
   * at L 7.33 at midnight can be cut off at L 9.00 at dawn, and the widest-L
   * readout would then be reporting the edge of the integrator rather than the
   * physics.
   *
   * Measured on this module at the three ion energies the layer offers, across
   * Kp 0-6: the dawn maximum reads exactly 9.00 for the 10 keV ion at Kp 0 and
   * for the 30 keV ion at Kp 0-3, with one or two of the 96 drawn bins sitting
   * on the edge. Everywhere else it is inside the domain and this is false.
   */
  contourClippedAtDomain: boolean;
  /** The domain edge, L. */
  domainL: number;
  /** Energy an ion of this species has at the boundary, keV. */
  boundaryEnergyKeV: number;
  /**
   * The boundary's widest and narrowest points, and the local times they fall
   * at.
   *
   * Carried on the region rather than recomputed by every reader because the
   * asymmetry is not a detail: for an ION of the energies drawn here the
   * boundary is widest at DAWN and pinched at DUSK, which is the opposite way
   * round from the cold plasmapause's dusk bulge. Both boundaries are the same
   * construction at two energies, and the flip between them is a fact about
   * where a fast westward drift beats corotation first.
   */
  widestL: number;
  widestMltHours: number;
  narrowestL: number;
  narrowestMltHours: number;
}

/** The extremes of a boundary, as the region reports them. */
function boundaryExtremes(mltHours: Float64Array, outerL: Float64Array) {
  let widest = 0;
  let narrowest = 0;
  for (let index = 1; index < outerL.length; index += 1) {
    if (outerL[index]! > outerL[widest]!) widest = index;
    if (outerL[index]! < outerL[narrowest]!) narrowest = index;
  }
  return {
    widestL: outerL[widest] ?? 0,
    widestMltHours: mltHours[widest] ?? 0,
    narrowestL: outerL[narrowest] ?? 0,
    narrowestMltHours: mltHours[narrowest] ?? 0,
  };
}

export function trappedDriftRegion(
  species: DriftSpecies,
  amplitudeVPerM: number,
  limits: TraceLimits = DEFAULT_TRACE_LIMITS,
  options: { azimuths?: number; innerL?: number } = {},
): TrappedRegion {
  const azimuths = options.azimuths ?? 96;
  const innerL = options.innerL ?? Math.max(limits.lMinimum, 2);
  const domainL = limits.lMaximum;
  const last = lastClosedDriftPath(species, amplitudeVPerM, limits);

  const mltHours = new Float64Array(azimuths);
  const outerL = new Float64Array(azimuths);
  for (let index = 0; index < azimuths; index += 1) {
    mltHours[index] = (24 * index) / azimuths;
  }

  if (!last) {
    // Every traced shell closed: the Alfvén layer is outside the domain. Draw
    // to the edge and flag it rather than inventing a boundary or drawing none.
    outerL.fill(domainL);
    return {
      boundaryL: domainL,
      mltHours,
      outerL,
      innerL,
      clippedToDomain: true,
      contourClippedAtDomain: true,
      domainL,
      boundaryEnergyKeV: energyAtLKeV(species, domainL),
      ...boundaryExtremes(mltHours, outerL),
    };
  }

  // The last closed path is a contour in (L, MLT). Resample it onto the drawn
  // azimuths by taking, for each bin, the largest L the path reaches there —
  // the outer edge of the trapped area at that local time.
  const filled = new Array<number | null>(azimuths).fill(null);
  for (const sample of last.path.samples) {
    const bin = Math.min(azimuths - 1, Math.max(0, Math.floor((sample.mltHours / 24) * azimuths)));
    const current = filled[bin] ?? null;
    if (current === null || sample.lShell > current) filled[bin] = sample.lShell;
  }
  // A bin the path never visited is filled from its neighbours rather than left
  // as a hole: this is one closed contour, so a gap is a sampling artifact of
  // the trace, not a place where the boundary does not exist.
  for (let index = 0; index < azimuths; index += 1) {
    if (filled[index] !== null) continue;
    let back = 1;
    let forward = 1;
    while (back < azimuths && filled[(index - back + azimuths) % azimuths] === null) back += 1;
    while (forward < azimuths && filled[(index + forward) % azimuths] === null) forward += 1;
    const before = filled[(index - back + azimuths) % azimuths] ?? last.lShell;
    const after = filled[(index + forward) % azimuths] ?? last.lShell;
    filled[index] = before + ((after - before) * back) / (back + forward);
  }
  for (let index = 0; index < azimuths; index += 1) outerL[index] = filled[index]!;

  // Did the contour itself run into the integrator's ceiling anywhere? The
  // midnight bisection cannot tell: it only ever asks about midnight.
  let contourClippedAtDomain = false;
  for (let index = 0; index < azimuths; index += 1) {
    if (outerL[index]! >= domainL - 1e-3) { contourClippedAtDomain = true; break; }
  }

  return {
    boundaryL: last.lShell,
    mltHours,
    outerL,
    innerL,
    clippedToDomain: false,
    contourClippedAtDomain,
    domainL,
    boundaryEnergyKeV: energyAtLKeV(species, last.lShell),
    ...boundaryExtremes(mltHours, outerL),
  };
}

/**
 * The region as a flat mesh in the equatorial plane.
 *
 * Radii go through the caller's mapper, the scene's one shared ruler, so the
 * region sits at the same distances as the drift paths drawn over it and as
 * every other layer.
 */
export function createTrappedRegionMesh(
  region: TrappedRegion,
  species: DriftSpecies,
  options: RingCurrentGeometryOptions,
): THREE.Mesh {
  const azimuths = region.mltHours.length;
  const rings = 12;
  const positions: number[] = [];
  const colours: number[] = [];
  const indices: number[] = [];

  for (let ring = 0; ring <= rings; ring += 1) {
    const t = ring / rings;
    for (let index = 0; index < azimuths; index += 1) {
      const l = region.innerL + (region.outerL[index]! - region.innerL) * t;
      const gsm = gsmFromDrift(l, phiFromMltHours(region.mltHours[index]!));
      const point = options.positionForGsm(gsm.x, gsm.y, gsm.z);
      positions.push(point.x, point.y, point.z);
      colours.push(...energyRampColour(energyAtLKeV(species, l)));
    }
  }
  for (let ring = 0; ring < rings; ring += 1) {
    for (let index = 0; index < azimuths; index += 1) {
      const next = (index + 1) % azimuths;
      const a = ring * azimuths + index;
      const b = ring * azimuths + next;
      const c = (ring + 1) * azimuths + index;
      const d = (ring + 1) * azimuths + next;
      indices.push(a, c, b, b, c, d);
    }
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.Float32BufferAttribute(colours, 3));
  geometry.setIndex(indices);
  geometry.userData = {
    representation: "region bounded by the last closed drift path (Alfven layer)",
    status: "illustration",
    quantity: "ion kinetic energy at that distance",
    unit: "keV",
    clippedToDomain: region.clippedToDomain,
  };
  const material = new THREE.MeshBasicMaterial({
    vertexColors: true,
    transparent: true,
    // Flat, and it must stay flat. See TrappedRegion.
    opacity: 0.18,
    side: THREE.DoubleSide,
    depthWrite: false,
  });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.name = "ring-current-trapped-region";
  return mesh;
}

export function createRingCurrentPathLines(
  illustration: RingCurrentIllustration,
  options: RingCurrentGeometryOptions,
): THREE.LineSegments {
  const positions: number[] = [];
  const colours: number[] = [];
  for (const path of illustration.paths) {
    const drawn = drawnPathPositions(path, options.positionForGsm);
    for (let index = 0; index + 1 < path.samples.length; index += 1) {
      const a = index * 3;
      const b = (index + 1) * 3;
      positions.push(drawn[a]!, drawn[a + 1]!, drawn[a + 2]!, drawn[b]!, drawn[b + 1]!, drawn[b + 2]!);
      const colourA = energyRampColour(path.samples[index]!.energyKeV);
      const colourB = energyRampColour(path.samples[index + 1]!.energyKeV);
      colours.push(...colourA, ...colourB);
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.Float32BufferAttribute(colours, 3));
  geometry.userData = {
    representation: "drift paths of equatorially mirroring ions, contours of qPhi + muB",
    status: "illustration",
    quantity: "ion kinetic energy along its own drift path",
    unit: "keV",
  };
  const material = new THREE.LineBasicMaterial({
    vertexColors: true,
    transparent: true,
    opacity: 0.55,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
  const lines = new THREE.LineSegments(geometry, material);
  lines.name = "ring-current-drift-paths";
  lines.frustumCulled = false;
  lines.renderOrder = 2;
  lines.userData = geometry.userData;
  return lines;
}

/**
 * The Alfven layer, drawn dashed so it cannot be mistaken for a particle path.
 *
 * A dashed line is the one line style in this scene that says "boundary" rather
 * than "trajectory", and this curve is a boundary: inside it a particle of this
 * energy is trapped, outside it a particle of this energy is swept through.
 */
export function createRingCurrentSeparatrix(
  illustration: RingCurrentIllustration,
  options: RingCurrentGeometryOptions,
): THREE.Line | null {
  if (!illustration.separatrix) return null;
  const drawn = drawnPathPositions(illustration.separatrix.path, options.positionForGsm);
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(drawn, 3));
  const material = new THREE.LineDashedMaterial({
    color: 0xfff0c8,
    dashSize: 6,
    gapSize: 5,
    transparent: true,
    opacity: 0.85,
    depthWrite: false,
  });
  const line = new THREE.Line(geometry, material);
  line.computeLineDistances();
  line.name = "ring-current-alfven-layer";
  line.frustumCulled = false;
  line.renderOrder = 3;
  line.userData = {
    representation: "the last closed drift path at this energy — the Alfven layer",
    status: "illustration",
    lShellAtMidnight: illustration.separatrix.lShell,
  };
  return line;
}

/**
 * The drifting ions themselves.
 *
 * The marker COUNT encodes nothing — it is not a flux, not a density and not a
 * particle number, and the card says so. What the markers carry is the two
 * things that are real: which way round they go, and how fast they go relative
 * to one another.
 */
export function createRingCurrentIons(
  illustration: RingCurrentIllustration,
  options: RingCurrentGeometryOptions,
): THREE.Points {
  const paths = illustration.paths.filter((path) => path.samples.length > 1 && path.durationSeconds > 0);
  const drawnPositions = paths.map((path) => drawnPathPositions(path, options.positionForGsm));
  const markerCount = paths.length * RING_CURRENT_DRIFT_REPLAY.markersPerPath;
  const markerPath = new Int32Array(markerCount);
  const markerOffsetSeconds = new Float64Array(markerCount);
  let cursor = 0;
  for (let pathIndex = 0; pathIndex < paths.length; pathIndex += 1) {
    const path = paths[pathIndex]!;
    for (let marker = 0; marker < RING_CURRENT_DRIFT_REPLAY.markersPerPath; marker += 1) {
      markerPath[cursor] = pathIndex;
      markerOffsetSeconds[cursor] = (path.durationSeconds * marker) / RING_CURRENT_DRIFT_REPLAY.markersPerPath;
      cursor += 1;
    }
  }

  const geometry = new THREE.BufferGeometry();
  const positions = new THREE.BufferAttribute(new Float32Array(markerCount * 3), 3);
  const logEnergy = new THREE.BufferAttribute(new Float32Array(markerCount), 1);
  const alpha = new THREE.BufferAttribute(new Float32Array(markerCount), 1);
  positions.setUsage(THREE.DynamicDrawUsage);
  logEnergy.setUsage(THREE.DynamicDrawUsage);
  alpha.setUsage(THREE.DynamicDrawUsage);
  geometry.setAttribute("position", positions);
  geometry.setAttribute("rampPosition", logEnergy);
  geometry.setAttribute("markerAlpha", alpha);

  const material = new THREE.ShaderMaterial({
    uniforms: {
      grainSceneRadius: { value: 7 },
      minimumPointSize: { value: 2.5 },
      maximumPointSize: { value: 16 },
      projectionScale: { value: 1 },
    },
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    vertexShader: `
      attribute float rampPosition;
      attribute float markerAlpha;
      uniform float grainSceneRadius;
      uniform float minimumPointSize;
      uniform float maximumPointSize;
      uniform float projectionScale;
      varying float vRamp;
      varying float vAlpha;
      void main() {
        vRamp = rampPosition;
        vAlpha = markerAlpha;
        vec4 viewPosition = modelViewMatrix * vec4(position, 1.0);
        float projected = projectionScale * grainSceneRadius / max(-viewPosition.z, 1.0);
        gl_PointSize = clamp(projected, minimumPointSize, maximumPointSize);
        gl_Position = projectionMatrix * viewPosition;
      }
    `,
    fragmentShader: `
      varying float vRamp;
      varying float vAlpha;
      // The same five stops as RING_CURRENT_ENERGY_SCALE's gradient, in order.
      vec3 ramp(float t) {
        vec3 c0 = vec3(0.169, 0.078, 0.212);
        vec3 c1 = vec3(0.482, 0.184, 0.561);
        vec3 c2 = vec3(0.878, 0.353, 0.541);
        vec3 c3 = vec3(1.000, 0.604, 0.361);
        vec3 c4 = vec3(1.000, 0.902, 0.659);
        if (t < 0.30) return mix(c0, c1, t / 0.30);
        if (t < 0.58) return mix(c1, c2, (t - 0.30) / 0.28);
        if (t < 0.80) return mix(c2, c3, (t - 0.58) / 0.22);
        return mix(c3, c4, (t - 0.80) / 0.20);
      }
      void main() {
        vec2 offset = gl_PointCoord - vec2(0.5);
        float grain = 1.0 - smoothstep(0.10, 0.5, length(offset));
        if (grain <= 0.0) discard;
        float a = vAlpha * grain;
        if (a < 0.004) discard;
        gl_FragColor = vec4(ramp(vRamp), a);
      }
    `,
  });

  const points = new THREE.Points(geometry, material);
  points.name = "ring-current-ions";
  points.frustumCulled = false;
  points.renderOrder = 4;
  const motion: RingCurrentMotionState = {
    paths,
    drawnPositions,
    markerPath,
    markerOffsetSeconds,
    positions,
    logEnergy,
    alpha,
  };
  points.userData = {
    ringCurrentMotion: motion,
    status: "illustration",
    representation: "markers on computed drift paths; the COUNT encodes nothing and is not a flux",
    motion: `drift integrated in physical time and replayed at ${RING_CURRENT_DRIFT_REPLAY.physicalSecondsPerDisplaySecond}x`,
  };
  // Same trick the plasmasphere stipple uses: a marker is a fixed size in the
  // scene, projected, so it keeps the same coverage at every camera distance.
  points.onBeforeRender = (renderer, _scene, camera) => {
    const uniform = material.uniforms.projectionScale;
    if (!uniform) return;
    if (!(camera instanceof THREE.PerspectiveCamera)) {
      uniform.value = 1;
      return;
    }
    const size = renderer.getDrawingBufferSize(new THREE.Vector2());
    const halfFov = THREE.MathUtils.degToRad(camera.fov) / 2;
    uniform.value = (size.y * 0.5) / Math.max(Math.tan(halfFov), 1e-6);
  };
  setRingCurrentDisplayTime(points, 0);
  return points;
}

/**
 * Advance the drifting ions to `elapsedDisplaySeconds` of display motion.
 *
 * Positions are interpolated between the DRAWN samples of each path — every one
 * of which already went through the scene's radial ruler — so this cannot
 * bypass the ruler and cannot go stale when the visitor switches scales
 * (the whole object is rebuilt then, by the same sweep that rebuilds the
 * plasmasphere stipple).
 *
 * An ion on an open path fades in as it enters the drawn domain and out as it
 * leaves, because a marker that pops out of existence at the edge reads as a
 * rendering fault rather than as a particle leaving through the dayside.
 */
export function setRingCurrentDisplayTime(object: THREE.Object3D, elapsedDisplaySeconds: number): void {
  // The scene hands this the whole group, because what moves is the VOLUME —
  // the object itself filling — and not a set of markers laid over it. Walking
  // the group rather than requiring the caller to find the right child is what
  // let the formation replace the marker cloud without the globe having to know
  // which of the two it is driving.
  object.traverse((child) => {
    if (child.name === "ring-current-volume") setRingCurrentVolumeTime(child, elapsedDisplaySeconds);
  });
  const motion = object.userData?.ringCurrentMotion as RingCurrentMotionState | undefined;
  if (!motion) return;
  const physicalSeconds = elapsedDisplaySeconds * RING_CURRENT_DRIFT_REPLAY.physicalSecondsPerDisplaySecond;
  const positions = motion.positions.array as Float32Array;
  const ramp = motion.logEnergy.array as Float32Array;
  const alpha = motion.alpha.array as Float32Array;
  for (let marker = 0; marker < motion.markerPath.length; marker += 1) {
    const pathIndex = motion.markerPath[marker]!;
    const path = motion.paths[pathIndex]!;
    const drawn = motion.drawnPositions[pathIndex]!;
    const { index, weight, wrappedSeconds } = driftPathPhase(
      path,
      physicalSeconds + motion.markerOffsetSeconds[marker]!,
    );
    const a = index * 3;
    const b = Math.min(index + 1, path.samples.length - 1) * 3;
    positions[marker * 3] = drawn[a]! + (drawn[b]! - drawn[a]!) * weight;
    positions[marker * 3 + 1] = drawn[a + 1]! + (drawn[b + 1]! - drawn[a + 1]!) * weight;
    positions[marker * 3 + 2] = drawn[a + 2]! + (drawn[b + 2]! - drawn[a + 2]!) * weight;
    const sampleA = path.samples[index]!;
    const sampleB = path.samples[Math.min(index + 1, path.samples.length - 1)]!;
    ramp[marker] = energyRampPosition(sampleA.energyKeV + (sampleB.energyKeV - sampleA.energyKeV) * weight);
    if (path.closure === "closed") {
      alpha[marker] = 0.95;
    } else {
      const fraction = path.durationSeconds > 0 ? wrappedSeconds / path.durationSeconds : 0;
      const edge = Math.min(fraction, 1 - fraction) / 0.06;
      alpha[marker] = 0.95 * Math.min(1, Math.max(0, edge));
    }
  }
  motion.positions.needsUpdate = true;
  motion.logEnergy.needsUpdate = true;
  motion.alpha.needsUpdate = true;
}

/**
 * The Alfven layer, named on screen.
 *
 * A dashed white teardrop with nothing beside it is a shape a reader has no way
 * to read. Sean looked at this layer and said so in as many words: he could not
 * tell what the dashed line was, and a boundary nobody can name is decoration
 * however honestly it was computed. The card explains it; the card is behind a
 * panel. This is the same sentence, on the object, in two lines: what it is,
 * and what it means.
 *
 * Anchored at the WIDEST point of the boundary, which is computed rather than
 * assumed — and it is worth saying why, because assuming would have put it in
 * the wrong place. The COLD plasmapause bulges at dusk. The boundary drawn here
 * is the same construction at a real ion energy, and at every Kp and every
 * energy this layer offers it comes out widest at DAWN and pinched at DUSK: a
 * few-tens-of-keV ion drifts westward fast enough to beat corotation on the
 * dawn side first. So the anchor is read off `region.outerL`, and the card
 * quotes both extremes rather than repeating the plasmapause's asymmetry at an
 * energy where it does not hold.
 */
export function createAlfvenLayerLabel(
  region: TrappedRegion,
  options: RingCurrentGeometryOptions,
): THREE.Object3D | null {
  if (typeof document === "undefined") return null;
  const earthSceneRadius = options.earthSceneRadius;
  if (earthSceneRadius === undefined) return null;

  const mlt = region.widestMltHours;
  const boundaryL = region.widestL;
  const phi = phiFromMltHours(mlt);
  const onBoundary = gsmFromDrift(boundaryL, phi);
  const outward = gsmFromDrift(boundaryL * 1.22, phi);
  const anchor = options.positionForGsm(onBoundary.x, onBoundary.y, onBoundary.z);
  const away = options.positionForGsm(outward.x, outward.y, outward.z);

  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 144;
  const context = canvas.getContext("2d");
  if (!context) return null;
  context.clearRect(0, 0, canvas.width, canvas.height);
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.fillStyle = "rgba(255, 240, 200, 0.96)";
  context.font = "600 46px 'DM Mono', 'SFMono-Regular', Menlo, monospace";
  context.fillText("ALFVÉN LAYER", canvas.width / 2, 44);
  context.fillStyle = "rgba(214, 232, 240, 0.82)";
  context.font = "400 32px 'DM Mono', 'SFMono-Regular', Menlo, monospace";
  context.fillText("OUTER EDGE OF TRAPPING", canvas.width / 2, 100);

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.minFilter = THREE.LinearFilter;
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    depthTest: true,
    depthWrite: false,
  }));
  const width = earthSceneRadius * 3.4;
  sprite.scale.set(width, (width * canvas.height) / canvas.width, 1);
  sprite.position.copy(away);

  // A leader from the boundary to the label, so the two are read as one thing
  // rather than as a caption floating in the field.
  const leader = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints([anchor, away]),
    new THREE.LineBasicMaterial({ color: 0xfff0c8, transparent: true, opacity: 0.42, depthWrite: false }),
  );
  leader.frustumCulled = false;

  const group = new THREE.Group();
  group.name = "ring-current-alfven-label";
  group.add(leader);
  group.add(sprite);
  group.renderOrder = 16;
  group.userData = {
    status: "illustration",
    // CORRECTNESS FIX 2026-09-04: DAWN, not dusk. This said dusk while
    // `trappedDriftRegion` twelve lines up says, and measures, the opposite:
    // an energetic ion's westward gradient drift destroys the corotation /
    // convection balance at dusk and creates one far out at dawn, so the
    // last closed path is widest at 06 MLT and pinched at 18 MLT at every Kp
    // and every energy this layer offers. Measured here at Kp 3, 10 keV:
    // widest L 7.58 at 06 MLT, narrowest L 5.31 at 18 MLT. The label is not
    // currently added to the scene, so this was a trap for whoever revives it
    // rather than a drawn error.
    representation: "the name of the last closed drift path, placed at its widest (dawn) point",
    mltHours: mlt,
    lShell: boundaryL,
  };
  return group;
}

/**
 * The whole drawable object: the trapped population as a volume, the boundary
 * that closes it, and the name of that boundary.
 *
 * Built here rather than in the globe so that the physics, the geometry and
 * the appearance of this layer stay in one file and the scene only has to add
 * and remove what it is handed.
 */
export function createRingCurrentObject(
  illustration: RingCurrentIllustration,
  options: RingCurrentGeometryOptions,
): THREE.Group {
  const group = new THREE.Group();
  group.name = "ring-current-illustration";
  // The region, the boundary that closes it, and the boundary's name.
  //
  // This used to draw the region and then put two more things ON TOP of it:
  // every traced drift path as a line, and a cloud of sprites animating around
  // those paths. The region is the physical statement — where a trapped ion
  // lives — and it was the faintest thing on screen, under a moving diagram.
  // Sean's words for the result, twice, were that it looked like a cartoon, and
  // he was right: an animation of marching dots is what a textbook draws when
  // it cannot show you the real object, and here the real object was already
  // being computed and then buried. Neither the lines nor the sprites are back.
  //
  // What IS back is time, and it is in the object rather than on top of it: the
  // volume's own density fills as the traced drift fills it. See
  // `RING_CURRENT_FORMATION` for why that is a different claim from marching
  // dots, and what it does and does not assert.
  const region = illustration.region;
  // A volume when the scene can give us the ruler, a surface otherwise.
  //
  // The surface was the right REGION and still read as a grey lid: a surface
  // has no inside, so it cannot show that the population is denser in the
  // middle than at its edges, cannot fade at the boundary, and puts everything
  // behind it behind it. Sean's reference for this layer is the NASA inner
  // magnetosphere rendering — a fat luminous doughnut with structure in it —
  // and that is a volume or it is nothing.
  let formation: RingCurrentFormation | null = null;
  if (options.earthSceneRadius === undefined) {
    group.add(createTrappedRegionMesh(region, illustration.species, options));
  } else {
    formation = ringCurrentFormation(illustration, region);
    group.add(createRingCurrentVolumeMesh({
      earthSceneRadius: options.earthSceneRadius,
      species: illustration.species,
      region,
      formation,
    }));
  }
  // NEITHER THE DASHED ALFVÉN CURVE NOR ITS LABEL IS DRAWN ON THE GLOBE.
  //
  // Sean asked what the dashed ring was; that was a complaint, and it was read
  // as a question and answered instead — so the next pass LABELLED it, which
  // made it worse. His decision: "You can move that either to the data card or
  // to the learning site but that doesn't belong on the main site."
  //
  // He is right about the globe. A dashed boundary with a leader and a caption
  // is annotation, and annotation over a rendered field competes with the field
  // — the same reason the drift-path lines and the marching sprites came off
  // this layer. The volume already ENDS at the Alfvén layer, because that is
  // what bounds the trapped region, so the boundary is visible as the edge of
  // the glow without a line drawn over it.
  //
  // The FACT is not lost, which is the rule when anything leaves a surface: the
  // layer's card still prints the boundary's L at midnight, its dawn and dusk
  // extremes and the flip between them, and the Learn card carries the physics.
  // `createRingCurrentSeparatrix` and `createAlfvenLayerLabel` are kept and
  // still tested — they are correct geometry, and a future cutaway or a Learn
  // figure is exactly where they belong.
  group.userData = {
    status: "illustration",
    // The loop timings themselves, not just a sentence about them.
    //
    // The legend swatch has to breathe on THIS object's clock - see
    // `paintRingCurrentPulse` - and the layer's card has to quote THIS
    // object's period. Both read it from here, so neither can end up
    // describing a formation the scene is not drawing. Null on the flat
    // surface path, which has no formation and does not move.
    formationState: formation,
    representation:
      "drift of equatorially mirroring ions in the SAME Volland-Stern convection + corotation field the DGCPM plasmasphere is being eroded by, plus their gradient/curvature drift",
    measured: "nothing on this map; the ring current's ENERGY is measured, as Dst, and Dst is one number with no map, which is why the shape here is reconstructed from the drift",
    importance: "a geomagnetic storm essentially IS this population intensifying: Dst, the number grading the storm in this site's own banner, is the field of this current at the ground",
    // CORRECTNESS FIX 2026-09-04: the radiation belts are no longer mapped
    // this way, so claiming a shared convention was false. The belt volume
    // rotates GSM into SM and offsets to the eccentric dipole centre
    // (`radiation-belt-volume.ts`, `smFromGsm` + `dipoleOffsetSmRe`); this
    // layer is a centred, untilted GSM-z dipole. The two are drawn about axes
    // up to 32.5 degrees apart at solstice, and the reader is owed that rather
    // than a cross-reference asserting they agree.
    dipoleAxis: "GSM z (centred, untilted dipole — the same convention as the plasmasphere stipple, but NOT the radiation-belt mapping, which is rotated into SM and offset to the eccentric dipole centre)",
    quantity: "ion kinetic energy",
    unit: "keV",
    driftSense: "ions westward, electrons eastward; the net current is westward and its field opposes Earth's at the surface, which is Dst",
    formation: formation
      ? `supply traced from ${formation.corridor.seedCount} parcels seeded across the nightside outer boundary; the ring closes westward at each shell's own traced lap time; loop ${(formation.cycleSeconds / 3600).toFixed(1)} h of drift replayed at ${RING_CURRENT_FORMATION.physicalSecondsPerDisplaySecond}×`
      : "still: no ruler was supplied, so the surface is drawn fully formed",
    trappedRegion: region.clippedToDomain
      ? `drawn to the traced domain edge, L ${region.domainL}: on a field this quiet no drift path inside the domain opens, so the Alfven layer lies beyond it`
      : region.contourClippedAtDomain
        ? `bounded by the last closed drift path, L ${region.boundaryL.toFixed(2)} at midnight; its dawn side runs into the traced domain edge at L ${region.domainL}, so the widest extent is a LOWER BOUND`
        : `bounded by the last closed drift path, L ${region.boundaryL.toFixed(2)} at midnight`,
  };
  return group;
}

/** Release everything the group owns. Geometry and materials are not shared. */
export function disposeRingCurrentObject(group: THREE.Object3D): void {
  group.traverse((child) => {
    const drawable = child as Partial<THREE.Mesh>;
    drawable.geometry?.dispose();
    const material = drawable.material;
    if (Array.isArray(material)) material.forEach((entry) => entry.dispose());
    else material?.dispose();
  });
}
