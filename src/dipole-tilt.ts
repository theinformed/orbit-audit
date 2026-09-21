/**
 * Geodipole tilt angle, from UTC and the IGRF dipole coefficients.
 *
 * Every cusped magnetopause model takes the dipole tilt as an explicit
 * argument, and the tilt range is about ±33°, which moves the northern cusp
 * indentation from a solar zenith angle of 63° down to 31°. A tilt-blind scene
 * cannot draw any of them, so this module is a prerequisite for
 * `magnetopause.ts`'s Nguyen and Lin surfaces rather than a nicety.
 *
 * ## What the tilt is
 *
 * GSM is defined so that the geomagnetic dipole axis lies in its x–z plane,
 * with +x toward the Sun. The tilt ψ is then the angle between the dipole axis
 * and GSM +z, positive when the northern magnetic pole leans **toward** the
 * Sun. Because the dipole has no GSM y-component by construction, the unit
 * dipole vector is `(sin ψ, 0, cos ψ)` and therefore
 *
 *     sin ψ = (dipole axis) · (Sun direction)
 *
 * in any common inertial frame. That identity is the whole calculation; the
 * rest is getting the two unit vectors right.
 *
 * ## What this is not
 *
 * This is **not** a full GEO ↔ MAG ↔ GSM ↔ SM transformation chain. It answers
 * exactly one question — what is ψ at this instant — because that is what the
 * boundary models need. A later phase that draws model field lines or ingests
 * NOAA's GEO-framed ground-magnetometer grids needs the full chain, and should
 * build it deliberately rather than growing it out of this file.
 *
 * The algorithm is Hapgood (1992), *Planet. Space Sci.* 40, 711, using the
 * standard low-precision solar position. It is arithmetic over published
 * constants, not a port of anyone's code, so it carries no licence question.
 *
 * ## Accuracy, stated
 *
 * The dipole coefficients below are IGRF-13's **definitive** 2020.0 values with
 * their published 2020–2025 secular variation, extrapolated linearly outside
 * that window. Over 2020–2030 that moves the modelled pole by well under a
 * tenth of a degree, which is three orders of magnitude smaller than the ±33°
 * quantity being computed. The solar position is good to about 0.01°. Neither
 * error is visible in a drawn boundary. Updating the table to IGRF-14 when its
 * definitive coefficients are to hand is a one-line change, and
 * `tests/dipole-tilt.test.ts` pins the 2020.0 pole position so a bad edit
 * fails loudly.
 */

/** IGRF-13 definitive dipole coefficients at epoch 2020.0, in nT. */
export const IGRF_DIPOLE_EPOCH_YEAR = 2020.0;
export const IGRF_DIPOLE_G10_NT = -29404.8;
export const IGRF_DIPOLE_G11_NT = -1450.9;
export const IGRF_DIPOLE_H11_NT = 4652.5;

/**
 * IGRF-13 secular variation for 2020–2025, in nT per year.
 *
 * Checked against the IAGA table itself on 2026-08-14
 * (<https://www.ngdc.noaa.gov/IAGA/vmod/coeffs/igrf13coeffs.txt>, the
 * `2020-25` column). g11's rate was 7.6 here and is 7.4 there — a transcription
 * slip worth about 1 nT of g11 over six years, far too small to move a drawn
 * boundary, and wrong all the same. The pole-position test pins the 2020.0
 * epoch, where the rates have no effect, so nothing was watching this.
 */
export const IGRF_DIPOLE_G10_RATE_NT_PER_YEAR = 5.7;
export const IGRF_DIPOLE_G11_RATE_NT_PER_YEAR = 7.4;
export const IGRF_DIPOLE_H11_RATE_NT_PER_YEAR = -25.9;

const DEG = Math.PI / 180;

export interface DipoleAxis {
  /** Unit vector toward the **north** geomagnetic pole, in GEO. */
  geo: [number, number, number];
  /** Geographic latitude of the north geomagnetic pole, degrees. */
  poleLatitudeDeg: number;
  /** Geographic longitude of the north geomagnetic pole, degrees east. */
  poleLongitudeDeg: number;
  /** Dipole moment magnitude expressed as an equivalent surface field, nT. */
  surfaceFieldNt: number;
}

/**
 * The dipole axis at a given decimal year.
 *
 * The IGRF dipole moment vector points roughly **south** (g10 is negative,
 * because Earth's field behaves like a bar magnet whose south pole is in the
 * northern hemisphere). The axis this function returns is the negated moment,
 * i.e. the direction of the north geomagnetic pole, because that is the
 * direction whose angle to the Sun is the tilt.
 */
export function dipoleAxis(decimalYear: number): DipoleAxis {
  const elapsed = decimalYear - IGRF_DIPOLE_EPOCH_YEAR;
  const g10 = IGRF_DIPOLE_G10_NT + elapsed * IGRF_DIPOLE_G10_RATE_NT_PER_YEAR;
  const g11 = IGRF_DIPOLE_G11_NT + elapsed * IGRF_DIPOLE_G11_RATE_NT_PER_YEAR;
  const h11 = IGRF_DIPOLE_H11_NT + elapsed * IGRF_DIPOLE_H11_RATE_NT_PER_YEAR;
  const magnitude = Math.sqrt(g10 * g10 + g11 * g11 + h11 * h11);
  const geo: [number, number, number] = [-g11 / magnitude, -h11 / magnitude, -g10 / magnitude];
  return {
    geo,
    poleLatitudeDeg: Math.asin(geo[2]) / DEG,
    poleLongitudeDeg: Math.atan2(geo[1], geo[0]) / DEG,
    surfaceFieldNt: magnitude,
  };
}

/** Decimal year, for the secular-variation term. Leap years are handled by construction. */
export function decimalYear(time: Date): number {
  const year = time.getUTCFullYear();
  const start = Date.UTC(year, 0, 1);
  const end = Date.UTC(year + 1, 0, 1);
  return year + (time.getTime() - start) / (end - start);
}

/** Modified Julian Date. */
export function modifiedJulianDate(time: Date): number {
  return time.getTime() / 86_400_000 + 40587;
}

export interface SolarPosition {
  /** Apparent ecliptic longitude of the Sun, degrees. */
  eclipticLongitudeDeg: number;
  /** Obliquity of the ecliptic, degrees. */
  obliquityDeg: number;
  /** Greenwich mean sidereal time, degrees. */
  greenwichSiderealTimeDeg: number;
  /** Unit vector toward the Sun in GEI. */
  gei: [number, number, number];
}

/**
 * Sun direction and sidereal time, per Hapgood (1992).
 *
 * `T0` is centuries from J2000 measured to the **start of the UT day**, and the
 * hour-of-day term is carried separately; folding the two together is a
 * classic source of a slowly growing error, so they are kept apart here.
 */
export function solarPosition(time: Date): SolarPosition {
  const mjd = modifiedJulianDate(time);
  const dayStart = Math.floor(mjd);
  const hours = (mjd - dayStart) * 24;
  const t0 = (dayStart - 51544.5) / 36525.0;

  const meanAnomaly = (357.528 + 35999.05 * t0 + 0.04107 * hours) * DEG;
  const meanLongitude = 280.46 + 36000.772 * t0 + 0.04107 * hours;
  const eclipticLongitudeDeg =
    meanLongitude
    + (1.915 - 0.0048 * t0) * Math.sin(meanAnomaly)
    + 0.02 * Math.sin(2 * meanAnomaly);
  const obliquityDeg = 23.439 - 0.013 * t0;
  const greenwichSiderealTimeDeg = 100.461 + 36000.77 * t0 + 15.04107 * hours;

  const lambda = eclipticLongitudeDeg * DEG;
  const epsilon = obliquityDeg * DEG;
  return {
    eclipticLongitudeDeg: ((eclipticLongitudeDeg % 360) + 360) % 360,
    obliquityDeg,
    greenwichSiderealTimeDeg: ((greenwichSiderealTimeDeg % 360) + 360) % 360,
    gei: [
      Math.cos(lambda),
      Math.cos(epsilon) * Math.sin(lambda),
      Math.sin(epsilon) * Math.sin(lambda),
    ],
  };
}

export interface DipoleTilt {
  /** Tilt angle ψ in radians, positive when the north pole leans sunward. */
  radians: number;
  /** The same angle in degrees, which is how every paper quotes it. */
  degrees: number;
  axis: DipoleAxis;
  sun: SolarPosition;
}

/**
 * Geodipole tilt at an instant.
 *
 * Returns `null` for a non-finite or unset time rather than a plausible-looking
 * zero: a tilt of exactly 0° is a real and common value, so it must never be
 * the failure mode. A caller that receives `null` should hide the tilt-driven
 * surfaces, not draw an untilted one.
 */
export function dipoleTilt(time: Date): DipoleTilt | null {
  const milliseconds = time?.getTime?.();
  if (milliseconds === undefined || !Number.isFinite(milliseconds)) return null;
  const axis = dipoleAxis(decimalYear(time));
  const sun = solarPosition(time);
  const theta = sun.greenwichSiderealTimeDeg * DEG;
  // GEO -> GEI is a rotation about the common z axis by +GST.
  const geiX = axis.geo[0] * Math.cos(theta) - axis.geo[1] * Math.sin(theta);
  const geiY = axis.geo[0] * Math.sin(theta) + axis.geo[1] * Math.cos(theta);
  const geiZ = axis.geo[2];
  const sine = geiX * sun.gei[0] + geiY * sun.gei[1] + geiZ * sun.gei[2];
  const radians = Math.asin(Math.max(-1, Math.min(1, sine)));
  return { radians, degrees: radians / DEG, axis, sun };
}
