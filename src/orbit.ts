import {
  degreesLat,
  degreesLong,
  eciToGeodetic,
  gstime,
  json2satrec,
  propagate,
  type SatRec,
} from "satellite.js";
import type { OmmRecord, OrbitRegime, PropagatedState } from "./types";

export const EARTH_RADIUS_KM = 6378.137;
const WGS84_SEMI_MAJOR_KM = 6378.137;
const WGS84_SEMI_MINOR_KM = 6356.752314245;
const WGS84_ECCENTRICITY_SQUARED = 1
  - (WGS84_SEMI_MINOR_KM ** 2) / (WGS84_SEMI_MAJOR_KM ** 2);
const EARTH_MU_KM3_S2 = 398600.4418;
const SIDEREAL_DAY_MINUTES = 1436.07;
export type GeoSubtype = "geostationary" | "other-gso";

/** Greenwich sidereal rotation, in radians, for reference-frame transforms. */
export function greenwichSiderealAngle(date: Date): number {
  const angle = gstime(date);
  return ((angle % (Math.PI * 2)) + Math.PI * 2) % (Math.PI * 2);
}

export function deriveOrbit(meanMotionRevsPerDay: number, eccentricity: number, inclinationDeg: number) {
  const periodSeconds = 86400 / meanMotionRevsPerDay;
  const semiMajorKm = Math.cbrt((EARTH_MU_KM3_S2 * periodSeconds * periodSeconds) / (4 * Math.PI * Math.PI));
  const perigeeKm = semiMajorKm * (1 - eccentricity) - EARTH_RADIUS_KM;
  const apogeeKm = semiMajorKm * (1 + eccentricity) - EARTH_RADIUS_KM;
  const periodMinutes = periodSeconds / 60;
  return {
    semiMajorKm,
    perigeeKm,
    apogeeKm,
    periodMinutes,
    regime: classifyOrbit(perigeeKm, apogeeKm, periodMinutes, inclinationDeg, eccentricity),
  };
}

export function classifyOrbit(
  perigeeKm: number,
  apogeeKm: number,
  periodMinutes: number,
  inclinationDeg: number,
  eccentricity: number,
): OrbitRegime {
  const nearGeosynchronousPeriod = periodMinutes >= 1380 && periodMinutes <= 1500;
  if (nearGeosynchronousPeriod && eccentricity < 0.15 && inclinationDeg < 20) return "GEO";
  // INCLINED GEOSYNCHRONOUS -- the exact complement of the GEO test above,
  // inside the same period/eccentricity box. The 20 degree wall is not chosen
  // fresh here: it is the GEO rule's own `< 20`, read the other way, so the two
  // classes cannot drift apart and nothing in the box can fall between them.
  //
  // Before this existed, these objects failed the GEO test on inclination and
  // then failed every test below it, and the site published them as OTHER. They
  // are not an "other": they are BeiDou IGSO, IRNSS/NavIC, QZSS Michibiki, SDO
  // and AMC-14 -- a real, named class that sits in the geosynchronous belt with
  // its ground track swept into a figure-of-eight instead of parked on a point.
  //
  // The wall lands in an empty band rather than through a crowd. Measured over
  // the 8,000-object live catalog: the highest-inclination GEO is SHIYAN 9 at
  // 16.4 deg and the lowest-inclination IGSO is AMC-14 at 24.1 deg, so 20 deg
  // has 7.7 deg of clear air on either side and no object near it to misfile.
  if (nearGeosynchronousPeriod && eccentricity < 0.15 && inclinationDeg >= 20) return "IGSO";
  if (eccentricity >= 0.25 || (apogeeKm > 40000 && perigeeKm < 30000)) return "HEO";
  if (apogeeKm < 2000) return "LEO";
  if (perigeeKm >= 2000 && apogeeKm < 35000) return "MEO";
  return "OTHER";
}

export function classifyGeoSubtype(
  periodMinutes: number,
  inclinationDeg: number,
  eccentricity: number,
): GeoSubtype {
  // This is a transparent mean-element teaching test, not an operator's
  // determination of station-keeping or assigned longitude-slot status.
  const stationKeptGeometry = Math.abs(periodMinutes - SIDEREAL_DAY_MINUTES) <= 5
    && inclinationDeg <= 0.1
    && eccentricity <= 0.005;
  return stationKeptGeometry ? "geostationary" : "other-gso";
}

export function propagateOmm(omm: OmmRecord, date: Date, existingSatrec?: SatRec): PropagatedState | null {
  const satrec = existingSatrec ?? json2satrec(omm);
  const result = propagate(satrec, date);
  if (!result || typeof result.position === "boolean" || typeof result.velocity === "boolean") return null;
  const gmst = greenwichSiderealAngle(date);
  return stateFromEci(result.position, result.velocity, gmst);
}

/**
 * Propagate through time while holding Earth's orientation fixed at frameDate.
 * This is useful for drawing the spacecraft's path through inertial space over
 * a stationary teaching globe. A ground track must use propagateOmm instead.
 */
export function propagateOmmInFrozenEarthFrame(
  omm: OmmRecord,
  date: Date,
  frameDate: Date,
  existingSatrec?: SatRec,
): PropagatedState | null {
  const satrec = existingSatrec ?? json2satrec(omm);
  const result = propagate(satrec, date);
  if (!result || typeof result.position === "boolean" || typeof result.velocity === "boolean") return null;
  return stateFromEci(result.position, result.velocity, greenwichSiderealAngle(frameDate));
}

function stateFromEci(
  position: { x: number; y: number; z: number },
  velocity: { x: number; y: number; z: number },
  gmst: number,
): PropagatedState {
  const geodetic = eciToGeodetic(position, gmst);
  const speed = Math.hypot(velocity.x, velocity.y, velocity.z);
  const radius = EARTH_RADIUS_KM + geodetic.height;
  const latitude = geodetic.latitude;
  const longitude = geodetic.longitude;
  return {
    latitudeDeg: degreesLat(latitude),
    longitudeDeg: degreesLong(longitude),
    altitudeKm: geodetic.height,
    velocityKps: speed,
    x: radius * Math.cos(latitude) * Math.cos(longitude),
    y: radius * Math.sin(latitude),
    z: -radius * Math.cos(latitude) * Math.sin(longitude),
  };
}

export function footprintAngularRadius(altitudeKm: number, minimumElevationDeg = 0): number {
  const radius = EARTH_RADIUS_KM + Math.max(0, altitudeKm);
  const elevation = (minimumElevationDeg * Math.PI) / 180;
  return Math.acos((EARTH_RADIUS_KM / radius) * Math.cos(elevation)) - elevation;
}

export function footprintPoints(
  latitudeDeg: number,
  longitudeDeg: number,
  altitudeKm: number,
  minimumElevationDeg = 0,
  segments = 96,
): Array<[number, number]> {
  if (Math.abs(minimumElevationDeg) < 1e-9) {
    return wgs84TangentHorizonPoints(latitudeDeg, longitudeDeg, altitudeKm, segments);
  }
  const lat1 = (latitudeDeg * Math.PI) / 180;
  const lon1 = (longitudeDeg * Math.PI) / 180;
  const angularRadius = footprintAngularRadius(altitudeKm, minimumElevationDeg);
  const points: Array<[number, number]> = [];
  for (let index = 0; index <= segments; index += 1) {
    const bearing = (index / segments) * Math.PI * 2;
    const latitude = Math.asin(
      Math.sin(lat1) * Math.cos(angularRadius) +
        Math.cos(lat1) * Math.sin(angularRadius) * Math.cos(bearing),
    );
    const longitude =
      lon1 +
      Math.atan2(
        Math.sin(bearing) * Math.sin(angularRadius) * Math.cos(lat1),
        Math.cos(angularRadius) - Math.sin(lat1) * Math.sin(latitude),
      );
    points.push([(longitude * 180) / Math.PI, (latitude * 180) / Math.PI]);
  }
  return points;
}

/**
 * Zero-elevation geometric horizon on the WGS-84 reference ellipsoid.
 *
 * In ellipsoid-scaled coordinates the surface is a unit sphere. The tangent
 * points seen from the spacecraft are the circle formed by the unit sphere
 * and S·q=1, where S is the scaled spacecraft position. Mapping that circle
 * back to WGS-84 gives the horizon without assuming a spherical Earth.
 */
export function wgs84TangentHorizonPoints(
  latitudeDeg: number,
  longitudeDeg: number,
  altitudeKm: number,
  segments = 96,
): Array<[number, number]> {
  const latitude = latitudeDeg * Math.PI / 180;
  const longitude = longitudeDeg * Math.PI / 180;
  const height = Math.max(0, altitudeKm);
  const sinLatitude = Math.sin(latitude);
  const cosLatitude = Math.cos(latitude);
  const primeVerticalRadius = WGS84_SEMI_MAJOR_KM
    / Math.sqrt(1 - WGS84_ECCENTRICITY_SQUARED * sinLatitude ** 2);
  const satellite = {
    x: (primeVerticalRadius + height) * cosLatitude * Math.cos(longitude),
    y: (primeVerticalRadius + height) * cosLatitude * Math.sin(longitude),
    z: (primeVerticalRadius * (1 - WGS84_ECCENTRICITY_SQUARED) + height) * sinLatitude,
  };
  const scaled = {
    x: satellite.x / WGS84_SEMI_MAJOR_KM,
    y: satellite.y / WGS84_SEMI_MAJOR_KM,
    z: satellite.z / WGS84_SEMI_MINOR_KM,
  };
  const normSquared = scaled.x ** 2 + scaled.y ** 2 + scaled.z ** 2;
  if (normSquared <= 1 + 1e-12) return [[longitudeDeg, latitudeDeg]];
  const inverseNorm = 1 / Math.sqrt(normSquared);
  const normal = {
    x: scaled.x * inverseNorm,
    y: scaled.y * inverseNorm,
    z: scaled.z * inverseNorm,
  };
  const reference = Math.abs(normal.z) < 0.9
    ? { x: 0, y: 0, z: 1 }
    : { x: 0, y: 1, z: 0 };
  const cross = {
    x: reference.y * normal.z - reference.z * normal.y,
    y: reference.z * normal.x - reference.x * normal.z,
    z: reference.x * normal.y - reference.y * normal.x,
  };
  const crossNorm = Math.hypot(cross.x, cross.y, cross.z);
  const basisU = { x: cross.x / crossNorm, y: cross.y / crossNorm, z: cross.z / crossNorm };
  const basisV = {
    x: normal.y * basisU.z - normal.z * basisU.y,
    y: normal.z * basisU.x - normal.x * basisU.z,
    z: normal.x * basisU.y - normal.y * basisU.x,
  };
  const center = {
    x: scaled.x / normSquared,
    y: scaled.y / normSquared,
    z: scaled.z / normSquared,
  };
  const radius = Math.sqrt(Math.max(0, 1 - 1 / normSquared));
  const points: Array<[number, number]> = [];
  for (let index = 0; index <= Math.max(12, segments); index += 1) {
    const angle = (index / Math.max(12, segments)) * Math.PI * 2;
    const cosine = Math.cos(angle);
    const sine = Math.sin(angle);
    const qx = center.x + radius * (basisU.x * cosine + basisV.x * sine);
    const qy = center.y + radius * (basisU.y * cosine + basisV.y * sine);
    const qz = center.z + radius * (basisU.z * cosine + basisV.z * sine);
    const x = qx * WGS84_SEMI_MAJOR_KM;
    const y = qy * WGS84_SEMI_MAJOR_KM;
    const z = qz * WGS84_SEMI_MINOR_KM;
    const surfaceDistance = Math.hypot(x, y);
    const auxiliary = Math.atan2(
      z * WGS84_SEMI_MAJOR_KM,
      surfaceDistance * WGS84_SEMI_MINOR_KM,
    );
    const secondEccentricitySquared = (WGS84_SEMI_MAJOR_KM ** 2 - WGS84_SEMI_MINOR_KM ** 2)
      / WGS84_SEMI_MINOR_KM ** 2;
    const surfaceLatitude = Math.atan2(
      z + secondEccentricitySquared * WGS84_SEMI_MINOR_KM * Math.sin(auxiliary) ** 3,
      surfaceDistance - WGS84_ECCENTRICITY_SQUARED * WGS84_SEMI_MAJOR_KM * Math.cos(auxiliary) ** 3,
    );
    points.push([
      Math.atan2(y, x) * 180 / Math.PI,
      surfaceLatitude * 180 / Math.PI,
    ]);
  }
  return points;
}

export function formatAltitude(km: number): string {
  if (!Number.isFinite(km)) return "—";
  return `${Math.round(km).toLocaleString()} km`;
}

export function elementAgeDays(epoch: string, at: Date): number {
  return (at.getTime() - new Date(epoch).getTime()) / 86400000;
}
