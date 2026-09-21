/**
 * The eccentric dipole — the offset that puts the South Atlantic Anomaly on
 * the map, and the reason the radiation belts are not circles.
 *
 * The belts are currently drawn about the **geographic** equator, on an ideal
 * centred dipole. Two things are dropped by that, and both are physics rather
 * than decoration:
 *
 * 1. The field's axis is tilted about 11° from the spin axis.
 * 2. The best-fit dipole is not at Earth's centre. It is displaced by about
 *    610 km — CORRECTED 2026-09-04 from "roughly 550"; `eccentricDipole()`
 *    computes 590.5 km at epoch 2020.0 and 609.7 km at 2026.67, and the same
 *    610 figure is already in this file's own comment further down and in the
 *    belt shader. 550 is still on the user-visible fact card in
 *    `layer-pages.ts` and in `satellite-fundamentals.ts`, where it is
 *    explicitly attributed to this computation; those are outside this pass —
 *    and that displacement is what drags the inner belt down to a few
 *    hundred kilometres over the South Atlantic — the SAA, which every
 *    low-Earth-orbit operator plans around and which this site has so far
 *    drawn a picture that contradicts.
 *
 * The SAA is NOT drawn here as an overlay, a hand-placed blob, or a fitted
 * patch. It is a consequence of where the dipole actually sits: put the dipole
 * in the right place and the weak-field region appears over the South Atlantic
 * on its own. That is the claim `tests/eccentric-dipole.test.ts` checks, and it
 * is the reason this is honest to draw at all.
 *
 * ## Where the numbers come from
 *
 * IGRF-13, the definitive 2020.0 coefficients and their published 2020–2025
 * secular variation, from the IAGA working group's own table:
 * <https://www.ngdc.noaa.gov/IAGA/vmod/coeffs/igrf13coeffs.txt> (retrieved
 * 2026-08-14). The degree-1 terms live in `dipole-tilt.ts` and are imported
 * rather than repeated; the degree-2 terms this file needs are below.
 *
 * ## The method
 *
 * Fraser-Smith (1987), *Reviews of Geophysics* 25, 1, "Centered and eccentric
 * geomagnetic dipoles and their poles" — the standard closed form that takes
 * the first- and second-degree Gauss coefficients to the offset of the
 * eccentric dipole. It is arithmetic over published constants, not a port of
 * anyone's code.
 *
 * ## What this is not
 *
 * An eccentric dipole is still a dipole. It reproduces the SAA's location and
 * rough depth because those follow from where the dipole sits, but it is not
 * the full IGRF field and it does not carry the higher-degree structure that
 * sets the anomaly's exact shape or its drift rate. A layer using this must
 * say "dipole", not "IGRF", and must not invite a reader to plan a dose
 * calculation on it.
 */

import {
  IGRF_DIPOLE_EPOCH_YEAR,
  IGRF_DIPOLE_G10_NT,
  IGRF_DIPOLE_G10_RATE_NT_PER_YEAR,
  IGRF_DIPOLE_G11_NT,
  IGRF_DIPOLE_G11_RATE_NT_PER_YEAR,
  IGRF_DIPOLE_H11_NT,
  IGRF_DIPOLE_H11_RATE_NT_PER_YEAR,
  dipoleAxis,
  dipoleTilt,
  decimalYear,
} from "./dipole-tilt";

/** IGRF-13 definitive quadrupole coefficients at epoch 2020.0, in nT. */
export const IGRF_G20_NT = -2499.6;
export const IGRF_G21_NT = 2982.0;
export const IGRF_H21_NT = -2991.6;
export const IGRF_G22_NT = 1677.0;
export const IGRF_H22_NT = -734.6;

/** IGRF-13 secular variation for 2020–2025, in nT per year. */
export const IGRF_G20_RATE_NT_PER_YEAR = -11.0;
export const IGRF_G21_RATE_NT_PER_YEAR = -7.0;
export const IGRF_H21_RATE_NT_PER_YEAR = -30.2;
export const IGRF_G22_RATE_NT_PER_YEAR = -2.1;
export const IGRF_H22_RATE_NT_PER_YEAR = -22.4;

/** The IGRF reference radius, km. Not the mean radius — the model's own. */
export const IGRF_REFERENCE_RADIUS_KM = 6371.2;

const DEG = Math.PI / 180;

export interface EccentricDipole {
  /** Offset of the dipole centre from Earth's centre, in GEO, km. */
  offsetKm: { x: number; y: number; z: number };
  /** How far the dipole sits from Earth's centre, km. */
  offsetMagnitudeKm: number;
  /** Unit vector toward the north geomagnetic pole, in GEO. */
  axis: { x: number; y: number; z: number };
  /** Equivalent surface field of the dipole moment, nT. */
  surfaceFieldNt: number;
}

/** The Gauss coefficients at a decimal year, linearly extrapolated. */
function coefficients(decimalYear: number) {
  const elapsed = decimalYear - IGRF_DIPOLE_EPOCH_YEAR;
  return {
    g10: IGRF_DIPOLE_G10_NT + elapsed * IGRF_DIPOLE_G10_RATE_NT_PER_YEAR,
    g11: IGRF_DIPOLE_G11_NT + elapsed * IGRF_DIPOLE_G11_RATE_NT_PER_YEAR,
    h11: IGRF_DIPOLE_H11_NT + elapsed * IGRF_DIPOLE_H11_RATE_NT_PER_YEAR,
    g20: IGRF_G20_NT + elapsed * IGRF_G20_RATE_NT_PER_YEAR,
    g21: IGRF_G21_NT + elapsed * IGRF_G21_RATE_NT_PER_YEAR,
    h21: IGRF_H21_NT + elapsed * IGRF_H21_RATE_NT_PER_YEAR,
    g22: IGRF_G22_NT + elapsed * IGRF_G22_RATE_NT_PER_YEAR,
    h22: IGRF_H22_NT + elapsed * IGRF_H22_RATE_NT_PER_YEAR,
  };
}

/**
 * The eccentric dipole at a decimal year: where it sits and which way it
 * points. Fraser-Smith (1987) equations 20–24.
 */
export function eccentricDipole(decimalYear: number): EccentricDipole {
  const { g10, g11, h11, g20, g21, h21, g22, h22 } = coefficients(decimalYear);
  const squaredMoment = g10 * g10 + g11 * g11 + h11 * h11;
  const root3 = Math.sqrt(3);

  const l0 = 2 * g10 * g20 + root3 * (g11 * g21 + h11 * h21);
  const l1 = -g11 * g20 + root3 * (g10 * g21 + g11 * g22 + h11 * h22);
  const l2 = -h11 * g20 + root3 * (g10 * h21 - h11 * g22 + g11 * h22);
  const e = (l0 * g10 + l1 * g11 + l2 * h11) / (4 * squaredMoment);

  const scale = IGRF_REFERENCE_RADIUS_KM / (3 * squaredMoment);
  const offsetKm = {
    x: scale * (l1 - g11 * e),
    y: scale * (l2 - h11 * e),
    z: scale * (l0 - g10 * e),
  };
  // The moment points roughly south (g10 is negative), so the NORTH
  // geomagnetic pole is the negated moment — the same convention
  // `dipoleAxis` uses, and the two must not disagree.
  const magnitude = Math.sqrt(squaredMoment);
  return {
    offsetKm,
    offsetMagnitudeKm: Math.hypot(offsetKm.x, offsetKm.y, offsetKm.z),
    axis: { x: -g11 / magnitude, y: -h11 / magnitude, z: -g10 / magnitude },
    surfaceFieldNt: magnitude,
  };
}

/** A geographic point at altitude, as a GEO cartesian vector in km. */
export function geographicToGeoKm(latitudeDeg: number, longitudeDeg: number, altitudeKm: number) {
  const radius = IGRF_REFERENCE_RADIUS_KM + altitudeKm;
  const latitude = latitudeDeg * DEG;
  const longitude = longitudeDeg * DEG;
  return {
    x: radius * Math.cos(latitude) * Math.cos(longitude),
    y: radius * Math.cos(latitude) * Math.sin(longitude),
    z: radius * Math.sin(latitude),
  };
}

/**
 * Field magnitude of the eccentric dipole at a geographic point, nT.
 *
 * The dipole formula |B| = (B0 a³ / r³) √(1 + 3 cos²θ), with r and θ measured
 * from the DISPLACED centre and about the tilted axis. Every part of the SAA
 * that this site can honestly draw is in that one substitution: the same
 * formula about the same axis, evaluated from where the dipole actually is.
 */
export function eccentricDipoleFieldNt(
  dipole: EccentricDipole,
  latitudeDeg: number,
  longitudeDeg: number,
  altitudeKm: number,
): number {
  const point = geographicToGeoKm(latitudeDeg, longitudeDeg, altitudeKm);
  const relative = {
    x: point.x - dipole.offsetKm.x,
    y: point.y - dipole.offsetKm.y,
    z: point.z - dipole.offsetKm.z,
  };
  const distance = Math.hypot(relative.x, relative.y, relative.z);
  if (distance <= 0) return Number.POSITIVE_INFINITY;
  const cosColatitude =
    (relative.x * dipole.axis.x + relative.y * dipole.axis.y + relative.z * dipole.axis.z) / distance;
  const scale = (IGRF_REFERENCE_RADIUS_KM / distance) ** 3;
  return dipole.surfaceFieldNt * scale * Math.sqrt(1 + 3 * cosColatitude * cosColatitude);
}

/**
 * Geomagnetic latitude about the eccentric dipole, degrees.
 *
 * This is what a belt drawn honestly is drawn about. A belt drawn about
 * geographic latitude instead is a belt with the SAA edited out of it.
 */
export function eccentricDipoleLatitudeDeg(
  dipole: EccentricDipole,
  latitudeDeg: number,
  longitudeDeg: number,
  altitudeKm: number,
): number {
  const point = geographicToGeoKm(latitudeDeg, longitudeDeg, altitudeKm);
  const relative = {
    x: point.x - dipole.offsetKm.x,
    y: point.y - dipole.offsetKm.y,
    z: point.z - dipole.offsetKm.z,
  };
  const distance = Math.hypot(relative.x, relative.y, relative.z);
  if (distance <= 0) return 0;
  const sine =
    (relative.x * dipole.axis.x + relative.y * dipole.axis.y + relative.z * dipole.axis.z) / distance;
  return Math.asin(Math.max(-1, Math.min(1, sine))) / DEG;
}

/**
 * McIlwain-style shell parameter about the eccentric dipole.
 *
 * L = r / (a cos²λ) for a dipole, with r from the displaced centre and λ the
 * geomagnetic latitude about the tilted axis. It is the coordinate the belts
 * are actually organised by, and computing it from the eccentric dipole rather
 * than the centred one is what makes a fixed L shell dip toward the ground
 * over the South Atlantic.
 */
export function eccentricDipoleShell(
  dipole: EccentricDipole,
  latitudeDeg: number,
  longitudeDeg: number,
  altitudeKm: number,
): number {
  const point = geographicToGeoKm(latitudeDeg, longitudeDeg, altitudeKm);
  const relative = {
    x: point.x - dipole.offsetKm.x,
    y: point.y - dipole.offsetKm.y,
    z: point.z - dipole.offsetKm.z,
  };
  const distance = Math.hypot(relative.x, relative.y, relative.z);
  const latitude = eccentricDipoleLatitudeDeg(dipole, latitudeDeg, longitudeDeg, altitudeKm) * DEG;
  const cosine = Math.cos(latitude);
  return distance / (IGRF_REFERENCE_RADIUS_KM * Math.max(1e-6, cosine * cosine));
}

/**
 * The offset expressed the way the scene already talks about the dipole: as a
 * geographic direction plus a distance in Earth radii.
 *
 * This is the handover between this module and the renderer. `globe.ts` already
 * turns a geographic latitude/longitude into a scene direction for the dipole
 * AXIS (`sceneDipoleAxisDirection` → `sceneDirectionFromLatLon`), and
 * `gsmFrameQuaternion` already carries the GSM roll that puts that axis in the
 * X–Z plane. Handing the OFFSET over in the same terms means the belts can be
 * displaced using the machinery that already exists, rather than growing a
 * second, independent GEO↔GSM chain — which `dipole-tilt.ts` warns against in
 * its own header.
 *
 * Distance is in Earth radii on purpose: the belts must be displaced in
 * PHYSICAL units before the shared radial ruler compresses them. The ruler
 * scales a position vector radially, so an offset applied afterwards, in scene
 * units, would be the wrong length by whatever compression applies at that
 * radius.
 */
export function eccentricOffsetGeographic(dipole: EccentricDipole): {
  latitudeDeg: number;
  longitudeDeg: number;
  distanceRe: number;
} {
  const { x, y, z } = dipole.offsetKm;
  const distanceKm = Math.hypot(x, y, z);
  if (distanceKm <= 0) return { latitudeDeg: 0, longitudeDeg: 0, distanceRe: 0 };
  return {
    latitudeDeg: Math.asin(Math.max(-1, Math.min(1, z / distanceKm))) / DEG,
    longitudeDeg: Math.atan2(y, x) / DEG,
    distanceRe: distanceKm / IGRF_REFERENCE_RADIUS_KM,
  };
}

/** What a layer drawn on this may and may not claim. */
export const ECCENTRIC_DIPOLE_LIMITATION =
  "An eccentric dipole fitted to the IGRF-13 degree-1 and degree-2 coefficients: it places the "
  + "South Atlantic Anomaly because that follows from where the dipole sits, but it is not the full "
  + "IGRF field. The anomaly's exact outline, its depth in rads, and its westward drift need the "
  + "higher-degree terms this does not carry. Nothing here is a dose calculation.";


// ---------------------------------------------------------------------------
// Where the offset points, right now
// ---------------------------------------------------------------------------

/**
 * The eccentric-dipole offset expressed in Solar Magnetic coordinates.
 *
 * The offset is fixed in GEOGRAPHIC space — about 610 km toward the western
 * Pacific — but the belts are drawn in SM, which is tied to the Sun and to the
 * dipole rather than to the ground. So as the Earth turns, the offset sweeps
 * around the SM frame once a day, and that sweep is exactly what carries the
 * inner belt down over the South Atlantic and back up again.
 *
 * The chain is GEO -> GEI -> GSM -> SM:
 *
 *   GEO -> GEI  rotate about the shared z axis by Greenwich sidereal time.
 *   GEI -> GSM  x toward the Sun; y perpendicular to the plane containing the
 *               Sun and the dipole axis; z completes it. This is what puts the
 *               dipole in the x-z plane, which is the defining property of GSM.
 *   GSM -> SM   rotate about y by minus the dipole tilt, putting z ON the
 *               dipole axis.
 *
 * Every step is a rotation, so the offset's LENGTH is invariant through the
 * whole chain. That is the property the tests lean on: if any step is wrong the
 * magnitude moves, and a wrong magnitude is a misplaced anomaly.
 *
 * Returns null when the tilt cannot be computed, for the same reason
 * `dipoleTilt` does: a zero offset is not a safe fallback, it is a silently
 * centred dipole.
 */
export interface EccentricOffsetSm {
  /** Components in SM, in Earth radii. */
  x: number;
  y: number;
  z: number;
  /** Length in Earth radii, invariant under the whole rotation chain. */
  magnitudeRe: number;
}

function crossProduct(a: readonly number[], b: readonly number[]): [number, number, number] {
  return [
    a[1]! * b[2]! - a[2]! * b[1]!,
    a[2]! * b[0]! - a[0]! * b[2]!,
    a[0]! * b[1]! - a[1]! * b[0]!,
  ];
}

function normalise(v: readonly number[]): [number, number, number] {
  const length = Math.hypot(v[0]!, v[1]!, v[2]!);
  if (!(length > 0)) return [0, 0, 0];
  return [v[0]! / length, v[1]! / length, v[2]! / length];
}

export function eccentricOffsetSm(time: Date): EccentricOffsetSm | null {
  const tilt = dipoleTilt(time);
  if (!tilt) return null;
  const year = decimalYear(time);
  const dipole = eccentricDipole(year);
  const axis = dipoleAxis(year);
  const sun = tilt.sun;

  // GEO -> GEI, a rotation about z by Greenwich sidereal time.
  const theta = sun.greenwichSiderealTimeDeg * (Math.PI / 180);
  const cos = Math.cos(theta);
  const sin = Math.sin(theta);
  const toGei = (v: readonly number[]): [number, number, number] => [
    v[0]! * cos - v[1]! * sin,
    v[0]! * sin + v[1]! * cos,
    v[2]!,
  ];

  const offsetGeoRe: [number, number, number] = [
    dipole.offsetKm.x / IGRF_REFERENCE_RADIUS_KM,
    dipole.offsetKm.y / IGRF_REFERENCE_RADIUS_KM,
    dipole.offsetKm.z / IGRF_REFERENCE_RADIUS_KM,
  ];
  const offsetGei = toGei(offsetGeoRe);
  const axisGei = toGei(axis.geo);

  // GEI -> GSM.
  const gsmX = normalise(sun.gei);
  const gsmY = normalise(crossProduct(axisGei, gsmX));
  const gsmZ = crossProduct(gsmX, gsmY);
  const dot = (a: readonly number[], b: readonly number[]) =>
    a[0]! * b[0]! + a[1]! * b[1]! + a[2]! * b[2]!;
  const gsm: [number, number, number] = [
    dot(offsetGei, gsmX),
    dot(offsetGei, gsmY),
    dot(offsetGei, gsmZ),
  ];

  // GSM -> SM, a rotation about y by -psi.
  const psi = tilt.radians;
  const cosPsi = Math.cos(-psi);
  const sinPsi = Math.sin(-psi);
  const x = gsm[0] * cosPsi + gsm[2] * sinPsi;
  const y = gsm[1];
  const z = -gsm[0] * sinPsi + gsm[2] * cosPsi;

  return { x, y, z, magnitudeRe: Math.hypot(x, y, z) };
}

/**
 * The same chain applied to the dipole AXIS, which must come out as SM z.
 *
 * Exported because it is the honest way to test the chain: SM is DEFINED as the
 * frame whose z axis is the dipole, so if this does not return (0, 0, 1) the
 * transform is wrong and the offset it produces is pointing somewhere else.
 */
export function dipoleAxisInSm(time: Date): [number, number, number] | null {
  const tilt = dipoleTilt(time);
  if (!tilt) return null;
  const axis = dipoleAxis(decimalYear(time));
  const sun = tilt.sun;
  const theta = sun.greenwichSiderealTimeDeg * (Math.PI / 180);
  const cos = Math.cos(theta);
  const sin = Math.sin(theta);
  const axisGei: [number, number, number] = [
    axis.geo[0] * cos - axis.geo[1] * sin,
    axis.geo[0] * sin + axis.geo[1] * cos,
    axis.geo[2],
  ];
  const gsmX = normalise(sun.gei);
  const gsmY = normalise(crossProduct(axisGei, gsmX));
  const gsmZ = crossProduct(gsmX, gsmY);
  const dot = (a: readonly number[], b: readonly number[]) =>
    a[0]! * b[0]! + a[1]! * b[1]! + a[2]! * b[2]!;
  const gsm: [number, number, number] = [dot(axisGei, gsmX), dot(axisGei, gsmY), dot(axisGei, gsmZ)];
  const psi = tilt.radians;
  const cosPsi = Math.cos(-psi);
  const sinPsi = Math.sin(-psi);
  return [
    gsm[0] * cosPsi + gsm[2] * sinPsi,
    gsm[1],
    -gsm[0] * sinPsi + gsm[2] * cosPsi,
  ];
}
