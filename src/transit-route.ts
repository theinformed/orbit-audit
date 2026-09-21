/**
 * Transit route: waypoints in space and time, and the continuous position
 * function built from them.
 *
 * The planner has to answer "where am I at time t" for arbitrary t, because the
 * visibility question is asked on a time grid that has nothing to do with where
 * the waypoints happen to fall. That means the route is not a list of points; it
 * is a piecewise curve parameterised by time.
 *
 * ## Track model
 *
 * Two interpolations are offered and the choice is recorded on the route, because
 * they are different tracks and the difference is not cosmetic:
 *
 * - `great-circle` (default) — the minimum-distance path between two points on a
 *   sphere. Interpolation is a slerp of the two unit position vectors, at a
 *   constant angular rate in time. This is the sensible default for a transit
 *   plan: it is what a ship routed for distance actually approximates, and it is
 *   what a planner draws first.
 * - `rhumb-line` — constant true course. A single steered heading is a loxodrome,
 *   not a great circle, and on a long east-west leg the two tracks separate by
 *   hundreds of nautical miles. Offered because a leg entered as "steer 270 until
 *   this time" is a rhumb line, and pretending otherwise moves the ship.
 *
 * Neither is a route *plan*: there is no land avoidance, no traffic separation,
 * no current or weather set-and-drift. A leg that crosses a continent will be
 * drawn crossing that continent. The planner is a geometry tool.
 *
 * ## Speed
 *
 * Speed is not an input. It falls out of the leg: distance over elapsed time.
 * The planner reports the implied speed so an unreasonable leg is visible as an
 * unreasonable speed rather than as a silently wrong answer.
 *
 * ## Time
 *
 * Every time in this module is an epoch-millisecond number in UTC. Local-time
 * entry is a presentation concern and lives in the planner UI; nothing below
 * ever sees a local time. This follows the convention `src/ground-track-map.ts`
 * already set, where the drawn ticks are UTC and say so.
 */

export type TrackModel = "great-circle" | "rhumb-line";

export interface Waypoint {
  /** Stable within one editing session; used as a DOM key and a selection handle. */
  id: string;
  label: string;
  latitudeDeg: number;
  longitudeDeg: number;
  /** UTC epoch milliseconds. */
  timeMs: number;
}

export interface RouteLeg {
  index: number;
  from: Waypoint;
  to: Waypoint;
  /** Great-circle separation, always — reported even for a rhumb-line track. */
  centralAngleRad: number;
  greatCircleKm: number;
  /** Along-track distance for the route's own track model. */
  trackDistanceKm: number;
  durationMs: number;
  /** Implied speed over the ground for the route's track model. */
  speedKnots: number;
  /** Initial true course in degrees; constant for a rhumb line. */
  initialCourseDeg: number;
}

export interface TransitRoute {
  waypoints: Waypoint[];
  trackModel: TrackModel;
}

export interface RoutePosition {
  latitudeDeg: number;
  longitudeDeg: number;
  timeMs: number;
  /** Index of the leg containing this time; equal to the waypoint index at a waypoint. */
  legIndex: number;
  /** 0 at the leg's start waypoint, 1 at its end waypoint. */
  fraction: number;
}

export interface RouteValidationIssue {
  kind:
    | "too-few-waypoints"
    | "non-monotonic-time"
    | "zero-duration-leg"
    | "out-of-range-latitude"
    | "implausible-speed";
  waypointIndex: number | null;
  legIndex: number | null;
  message: string;
}

export const EARTH_MEAN_RADIUS_KM = 6371.0088;
const KM_PER_NAUTICAL_MILE = 1.852;
const DEG = Math.PI / 180;

/**
 * Above this the leg is flagged. Not a hard error: the planner is also used to
 * teach with aircraft legs, and a hard cap would silently reject a valid lesson.
 */
export const IMPLAUSIBLE_SPEED_KNOTS = 1200;

export function normalizeLongitudeDeg(longitudeDeg: number): number {
  const normalized = (((longitudeDeg + 180) % 360) + 360) % 360 - 180;
  return Object.is(normalized, -0) ? 0 : normalized;
}

/** Great-circle central angle between two geographic points, in radians. */
export function centralAngleRad(
  latitudeADeg: number,
  longitudeADeg: number,
  latitudeBDeg: number,
  longitudeBDeg: number,
): number {
  const latitudeA = latitudeADeg * DEG;
  const latitudeB = latitudeBDeg * DEG;
  const deltaLatitude = latitudeB - latitudeA;
  const deltaLongitude = (longitudeBDeg - longitudeADeg) * DEG;
  // Haversine: stable for the small separations that dominate a ship's legs,
  // where the spherical law of cosines loses most of its significant figures.
  const haversine = Math.sin(deltaLatitude / 2) ** 2
    + Math.cos(latitudeA) * Math.cos(latitudeB) * Math.sin(deltaLongitude / 2) ** 2;
  return 2 * Math.asin(Math.min(1, Math.sqrt(Math.max(0, haversine))));
}

export function greatCircleDistanceKm(
  latitudeADeg: number,
  longitudeADeg: number,
  latitudeBDeg: number,
  longitudeBDeg: number,
): number {
  return centralAngleRad(latitudeADeg, longitudeADeg, latitudeBDeg, longitudeBDeg) * EARTH_MEAN_RADIUS_KM;
}

/** Initial true course from A toward B along the great circle, degrees 0-360. */
export function initialCourseDeg(
  latitudeADeg: number,
  longitudeADeg: number,
  latitudeBDeg: number,
  longitudeBDeg: number,
): number {
  const latitudeA = latitudeADeg * DEG;
  const latitudeB = latitudeBDeg * DEG;
  const deltaLongitude = (longitudeBDeg - longitudeADeg) * DEG;
  const y = Math.sin(deltaLongitude) * Math.cos(latitudeB);
  const x = Math.cos(latitudeA) * Math.sin(latitudeB)
    - Math.sin(latitudeA) * Math.cos(latitudeB) * Math.cos(deltaLongitude);
  return (Math.atan2(y, x) / DEG + 360) % 360;
}

/**
 * Inverse Mercator latitude ("stretched latitude"). A rhumb line is a straight
 * line in this coordinate, which is the whole reason Mercator charts exist.
 */
function mercatorLatitude(latitudeRad: number): number {
  const clamped = Math.max(-Math.PI / 2 + 1e-10, Math.min(Math.PI / 2 - 1e-10, latitudeRad));
  return Math.log(Math.tan(Math.PI / 4 + clamped / 2));
}

/** Signed shortest longitude difference B - A, in radians, within (-pi, pi]. */
function shortestLongitudeDeltaRad(longitudeADeg: number, longitudeBDeg: number): number {
  let delta = (longitudeBDeg - longitudeADeg) * DEG;
  while (delta > Math.PI) delta -= 2 * Math.PI;
  while (delta < -Math.PI) delta += 2 * Math.PI;
  return delta;
}

export function rhumbDistanceKm(
  latitudeADeg: number,
  longitudeADeg: number,
  latitudeBDeg: number,
  longitudeBDeg: number,
): number {
  const latitudeA = latitudeADeg * DEG;
  const latitudeB = latitudeBDeg * DEG;
  const deltaLatitude = latitudeB - latitudeA;
  const deltaLongitude = shortestLongitudeDeltaRad(longitudeADeg, longitudeBDeg);
  const deltaMercator = mercatorLatitude(latitudeB) - mercatorLatitude(latitudeA);
  // q is the "stretch factor"; the limit form avoids 0/0 on an east-west leg.
  const q = Math.abs(deltaMercator) > 1e-12 ? deltaLatitude / deltaMercator : Math.cos(latitudeA);
  return Math.hypot(deltaLatitude, q * deltaLongitude) * EARTH_MEAN_RADIUS_KM;
}

export function rhumbCourseDeg(
  latitudeADeg: number,
  longitudeADeg: number,
  latitudeBDeg: number,
  longitudeBDeg: number,
): number {
  const deltaMercator = mercatorLatitude(latitudeBDeg * DEG) - mercatorLatitude(latitudeADeg * DEG);
  const deltaLongitude = shortestLongitudeDeltaRad(longitudeADeg, longitudeBDeg);
  return (Math.atan2(deltaLongitude, deltaMercator) / DEG + 360) % 360;
}

/**
 * Interpolate along a great circle by slerping the unit vectors. Constant
 * angular rate, so equal time fractions are equal along-track distances.
 */
export function interpolateGreatCircle(
  latitudeADeg: number,
  longitudeADeg: number,
  latitudeBDeg: number,
  longitudeBDeg: number,
  fraction: number,
): { latitudeDeg: number; longitudeDeg: number } {
  const angle = centralAngleRad(latitudeADeg, longitudeADeg, latitudeBDeg, longitudeBDeg);
  if (angle < 1e-12) return { latitudeDeg: latitudeADeg, longitudeDeg: normalizeLongitudeDeg(longitudeADeg) };
  const sinAngle = Math.sin(angle);
  const a = Math.sin((1 - fraction) * angle) / sinAngle;
  const b = Math.sin(fraction * angle) / sinAngle;
  const latitudeA = latitudeADeg * DEG;
  const latitudeB = latitudeBDeg * DEG;
  const longitudeA = longitudeADeg * DEG;
  const longitudeB = longitudeBDeg * DEG;
  const x = a * Math.cos(latitudeA) * Math.cos(longitudeA) + b * Math.cos(latitudeB) * Math.cos(longitudeB);
  const y = a * Math.cos(latitudeA) * Math.sin(longitudeA) + b * Math.cos(latitudeB) * Math.sin(longitudeB);
  const z = a * Math.sin(latitudeA) + b * Math.sin(latitudeB);
  return {
    latitudeDeg: Math.atan2(z, Math.hypot(x, y)) / DEG,
    longitudeDeg: normalizeLongitudeDeg(Math.atan2(y, x) / DEG),
  };
}

/**
 * Interpolate along a rhumb line.
 *
 * Latitude IS linear in the fraction, and that part was always right: on a
 * loxodrome of course t the along-track distance is s = R dphi / cos t, so
 * equal fractions of time are equal steps of latitude and equal distances,
 * which is what makes `speedKnots` one number for the whole leg.
 *
 * Longitude is NOT linear in the fraction. A rhumb line is the curve that is
 * STRAIGHT IN MERCATOR LATITUDE - dlambda/dpsi = tan t - so longitude advances
 * with psi and not with phi. That is the same relation `rhumbDistanceKm` and
 * `rhumbCourseDeg` above already use; this function was the one place that did
 * not.
 *
 * CORRECTNESS FIX 2026-09-08. Interpolating linearly in longitude as well
 * produced a track that was neither a rhumb line nor a great circle: the
 * endpoints, the reported distance, the course and the speed were all correct
 * and the curve drawn between them was a third thing. Measured against the
 * loxodrome on the shipped presets, the drawn position was out by up to 57 km
 * (Grand Banks - Irminger Sea, mid-leg) and 52 km (San Diego - south of Maui);
 * on a 0 N to 60 N leg spanning 60 degrees of longitude it was 483 km out. The
 * whole reason the rhumb-line option exists is that a single steered course is
 * not a great circle, so the drawn track has to be the curve the option names.
 * `routeLandCrossings` samples this same function, so the landfall check moved
 * with it.
 */
export function interpolateRhumbLine(
  latitudeADeg: number,
  longitudeADeg: number,
  latitudeBDeg: number,
  longitudeBDeg: number,
  fraction: number,
): { latitudeDeg: number; longitudeDeg: number } {
  const deltaLongitudeDeg = shortestLongitudeDeltaRad(longitudeADeg, longitudeBDeg) / DEG;
  const latitudeDeg = latitudeADeg + (latitudeBDeg - latitudeADeg) * fraction;
  const mercatorA = mercatorLatitude(latitudeADeg * DEG);
  const deltaMercator = mercatorLatitude(latitudeBDeg * DEG) - mercatorA;
  // An east-west leg has no Mercator span to divide by. On a parallel the
  // course is due east or west and longitude really is linear in distance, so
  // the fraction is the right answer there rather than a special case.
  const longitudeFraction = Math.abs(deltaMercator) > 1e-12
    ? (mercatorLatitude(latitudeDeg * DEG) - mercatorA) / deltaMercator
    : fraction;
  return {
    latitudeDeg,
    longitudeDeg: normalizeLongitudeDeg(longitudeADeg + deltaLongitudeDeg * longitudeFraction),
  };
}

export function buildLegs(route: TransitRoute): RouteLeg[] {
  const legs: RouteLeg[] = [];
  for (let index = 0; index < route.waypoints.length - 1; index += 1) {
    const from = route.waypoints[index]!;
    const to = route.waypoints[index + 1]!;
    const angle = centralAngleRad(from.latitudeDeg, from.longitudeDeg, to.latitudeDeg, to.longitudeDeg);
    const greatCircleKm = angle * EARTH_MEAN_RADIUS_KM;
    const trackDistanceKm = route.trackModel === "rhumb-line"
      ? rhumbDistanceKm(from.latitudeDeg, from.longitudeDeg, to.latitudeDeg, to.longitudeDeg)
      : greatCircleKm;
    const durationMs = to.timeMs - from.timeMs;
    const hours = durationMs / 3_600_000;
    legs.push({
      index,
      from,
      to,
      centralAngleRad: angle,
      greatCircleKm,
      trackDistanceKm,
      durationMs,
      speedKnots: hours > 0 ? trackDistanceKm / KM_PER_NAUTICAL_MILE / hours : Number.POSITIVE_INFINITY,
      initialCourseDeg: route.trackModel === "rhumb-line"
        ? rhumbCourseDeg(from.latitudeDeg, from.longitudeDeg, to.latitudeDeg, to.longitudeDeg)
        : initialCourseDeg(from.latitudeDeg, from.longitudeDeg, to.latitudeDeg, to.longitudeDeg),
    });
  }
  return legs;
}

export function routeSpanMs(route: TransitRoute): { startMs: number; endMs: number } | null {
  if (route.waypoints.length < 2) return null;
  const startMs = route.waypoints[0]!.timeMs;
  const endMs = route.waypoints.at(-1)!.timeMs;
  return endMs > startMs ? { startMs, endMs } : null;
}

/**
 * Where the route is at `timeMs`. Returns null outside the route's span rather
 * than extrapolating: a plan does not say where the ship is before it sails.
 */
export function positionAt(route: TransitRoute, timeMs: number): RoutePosition | null {
  const waypoints = route.waypoints;
  if (waypoints.length === 0) return null;
  if (waypoints.length === 1) {
    const only = waypoints[0]!;
    return timeMs === only.timeMs
      ? {
        latitudeDeg: only.latitudeDeg,
        longitudeDeg: normalizeLongitudeDeg(only.longitudeDeg),
        timeMs,
        legIndex: 0,
        fraction: 0,
      }
      : null;
  }
  const startMs = waypoints[0]!.timeMs;
  const endMs = waypoints.at(-1)!.timeMs;
  if (timeMs < startMs || timeMs > endMs) return null;

  let legIndex = 0;
  for (let index = 0; index < waypoints.length - 1; index += 1) {
    if (timeMs <= waypoints[index + 1]!.timeMs) {
      legIndex = index;
      break;
    }
    legIndex = index;
  }
  const from = waypoints[legIndex]!;
  const to = waypoints[legIndex + 1]!;
  const duration = to.timeMs - from.timeMs;
  const fraction = duration > 0 ? (timeMs - from.timeMs) / duration : 0;
  const interpolated = route.trackModel === "rhumb-line"
    ? interpolateRhumbLine(from.latitudeDeg, from.longitudeDeg, to.latitudeDeg, to.longitudeDeg, fraction)
    : interpolateGreatCircle(from.latitudeDeg, from.longitudeDeg, to.latitudeDeg, to.longitudeDeg, fraction);
  return { ...interpolated, timeMs, legIndex, fraction };
}

/**
 * A uniform time grid over the route, always including the exact waypoint times
 * so that a waypoint is never straddled by two samples and missed.
 *
 * The waypoint times matter because the planner's headline interaction — click a
 * waypoint, see what is overhead *there* — is answered at exactly those instants.
 * Snapping them onto the grid rather than interpolating to them keeps the answer
 * in the list identical to the answer in the timeline.
 */
export function sampleRoute(
  route: TransitRoute,
  stepSeconds: number,
): RoutePosition[] {
  const span = routeSpanMs(route);
  if (!span || stepSeconds <= 0) return [];
  const stepMs = stepSeconds * 1000;
  const times = new Set<number>();
  for (let timeMs = span.startMs; timeMs < span.endMs; timeMs += stepMs) times.add(timeMs);
  times.add(span.endMs);
  for (const waypoint of route.waypoints) times.add(waypoint.timeMs);
  return [...times]
    .sort((a, b) => a - b)
    .flatMap((timeMs) => {
      const position = positionAt(route, timeMs);
      return position ? [position] : [];
    });
}

export function validateRoute(route: TransitRoute): RouteValidationIssue[] {
  const issues: RouteValidationIssue[] = [];
  if (route.waypoints.length < 2) {
    issues.push({
      kind: "too-few-waypoints",
      waypointIndex: null,
      legIndex: null,
      message: "A transit needs at least two waypoints: a departure and an arrival.",
    });
  }
  route.waypoints.forEach((waypoint, index) => {
    if (!Number.isFinite(waypoint.latitudeDeg) || Math.abs(waypoint.latitudeDeg) > 90) {
      issues.push({
        kind: "out-of-range-latitude",
        waypointIndex: index,
        legIndex: null,
        message: `Waypoint ${index + 1} latitude ${waypoint.latitudeDeg} is outside -90 to 90.`,
      });
    }
  });
  for (let index = 0; index < route.waypoints.length - 1; index += 1) {
    const from = route.waypoints[index]!;
    const to = route.waypoints[index + 1]!;
    if (to.timeMs < from.timeMs) {
      issues.push({
        kind: "non-monotonic-time",
        waypointIndex: index + 1,
        legIndex: index,
        message: `Waypoint ${index + 2} is earlier than waypoint ${index + 1}. Waypoint times must increase along the route.`,
      });
    } else if (to.timeMs === from.timeMs) {
      issues.push({
        kind: "zero-duration-leg",
        waypointIndex: index + 1,
        legIndex: index,
        message: `Waypoints ${index + 1} and ${index + 2} share a time, so leg ${index + 1} has no duration.`,
      });
    }
  }
  for (const leg of buildLegs(route)) {
    if (Number.isFinite(leg.speedKnots) && leg.speedKnots > IMPLAUSIBLE_SPEED_KNOTS) {
      issues.push({
        kind: "implausible-speed",
        waypointIndex: null,
        legIndex: leg.index,
        message: `Leg ${leg.index + 1} implies ${Math.round(leg.speedKnots).toLocaleString()} knots. Check the times.`,
      });
    }
  }
  return issues;
}

/**
 * Densify the route into drawable polyline vertices. Legs are subdivided so a
 * great circle bends on the map instead of being drawn as a straight line
 * between waypoints, which is the single most common way a planner lies.
 */
export function routePolyline(
  route: TransitRoute,
  maximumSegmentDeg = 1.5,
): Array<{ latitudeDeg: number; longitudeDeg: number; timeMs: number }> {
  const legs = buildLegs(route);
  if (legs.length === 0) {
    return route.waypoints.map((waypoint) => ({
      latitudeDeg: waypoint.latitudeDeg,
      longitudeDeg: normalizeLongitudeDeg(waypoint.longitudeDeg),
      timeMs: waypoint.timeMs,
    }));
  }
  const vertices: Array<{ latitudeDeg: number; longitudeDeg: number; timeMs: number }> = [];
  for (const leg of legs) {
    const separationDeg = (leg.centralAngleRad / DEG);
    const steps = Math.max(1, Math.ceil(separationDeg / Math.max(0.05, maximumSegmentDeg)));
    for (let step = 0; step < steps; step += 1) {
      const fraction = step / steps;
      const point = route.trackModel === "rhumb-line"
        ? interpolateRhumbLine(leg.from.latitudeDeg, leg.from.longitudeDeg, leg.to.latitudeDeg, leg.to.longitudeDeg, fraction)
        : interpolateGreatCircle(leg.from.latitudeDeg, leg.from.longitudeDeg, leg.to.latitudeDeg, leg.to.longitudeDeg, fraction);
      vertices.push({ ...point, timeMs: leg.from.timeMs + leg.durationMs * fraction });
    }
  }
  const last = legs.at(-1)!.to;
  vertices.push({
    latitudeDeg: last.latitudeDeg,
    longitudeDeg: normalizeLongitudeDeg(last.longitudeDeg),
    timeMs: last.timeMs,
  });
  return vertices;
}
