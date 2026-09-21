/**
 * Is this track over water?
 *
 * ## Why a geometry tool needs this
 *
 * The planner draws whatever track you give it and says so — there is no land
 * avoidance in `transit-route.ts` and there is not going to be. That is fine
 * right up until the tool SHIPS a default route that sails through Oahu, which
 * is what it did. Sean: "this is supposed to be a Navy program. Your default
 * path has a ship sailing straight through continents."
 *
 * So the fix is not a router. It is a CHECK, run against the same published
 * Natural Earth 1:110m land artifact the map and the globe already draw
 * (`manifest.land`), used in two places:
 *
 * 1. `tests/transit-route-land.test.ts` fails if any shipped preset — the
 *    default included — puts a sampled track position on land or nearer to it
 *    than `MINIMUM_COAST_CLEARANCE_KM`. A route can no longer be eyeballed.
 * 2. The planner runs it on whatever route the reader draws, and says which leg
 *    crosses land. It is a statement about the drawing, not a routing product.
 *
 * ## What the answer is worth
 *
 * 1:110m is a world-scale generalisation. Its coastline is smoothed by tens of
 * kilometres, small islands are absent entirely, and it knows nothing about
 * depth, traffic separation or a strait's actual navigability. So "on land" here
 * means "inside the coarsest coastline the site ships", and clear of it by 10 km
 * means clear at THAT resolution and nothing more. It is enough to catch a track
 * across a continent, which is the failure it exists to catch, and it must never
 * be read as a navigational clearance.
 *
 * The antimeridian is handled by dropping ring edges that span more than 180
 * degrees of longitude — those are the wrap artifacts of a polygon that
 * straddles the date line, and crossing-counting across one is meaningless.
 */

import type { LandGeoJson } from "./globe";
import { interpolateGreatCircle, interpolateRhumbLine, normalizeLongitudeDeg, buildLegs, type TransitRoute } from "./transit-route";

const DEG = Math.PI / 180;
const EARTH_MEAN_RADIUS_KM = 6371.0088;

/**
 * How far a shipped preset must stay off the 1:110m coastline.
 *
 * 10 km is about 5.4 nautical miles. It is not a safety margin — see the module
 * note — it is a margin against the generalisation itself, so a route that only
 * "misses" because Natural Earth rounded a headland off cannot ship. Every
 * preset currently clears by at least 18 km.
 */
export const MINIMUM_COAST_CLEARANCE_KM = 10;

interface Segment {
  ax: number; ay: number; bx: number; by: number;
  minLat: number; maxLat: number;
}

export interface LandIndex {
  rings: Array<Array<[number, number]>>;
  /** Segments bucketed by whole degree of latitude, for the clearance query. */
  bands: Map<number, Segment[]>;
}

export function buildLandIndex(land: LandGeoJson): LandIndex {
  const rings: Array<Array<[number, number]>> = [];
  for (const feature of land.features) {
    const geometry = feature.geometry;
    const polygons = geometry.type === "Polygon"
      ? [geometry.coordinates as unknown as number[][][]]
      : geometry.coordinates as unknown as number[][][][];
    for (const polygon of polygons) {
      for (const ring of polygon) {
        rings.push(ring.map((coordinate) => [coordinate[0] ?? 0, coordinate[1] ?? 0] as [number, number]));
      }
    }
  }
  const bands = new Map<number, Segment[]>();
  for (const ring of rings) {
    for (let index = 1; index < ring.length; index += 1) {
      const [ax, ay] = ring[index - 1]!;
      const [bx, by] = ring[index]!;
      if (Math.abs(ax - bx) > 180) continue;
      const segment: Segment = {
        ax, ay, bx, by,
        minLat: Math.min(ay, by), maxLat: Math.max(ay, by),
      };
      for (let band = Math.floor(segment.minLat); band <= Math.floor(segment.maxLat); band += 1) {
        const list = bands.get(band);
        if (list) list.push(segment);
        else bands.set(band, [segment]);
      }
    }
  }
  return { rings, bands };
}

/** Crossing count in plate carrée, skipping the date-line wrap edges. */
export function isOnLand(index: LandIndex, longitudeDeg: number, latitudeDeg: number): boolean {
  const longitude = normalizeLongitudeDeg(longitudeDeg);
  for (const ring of index.rings) {
    let inside = false;
    // `j = i, i += 1` and not `j = i += 1`: j has to hold the PREVIOUS index.
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i, i += 1) {
      const [xi, yi] = ring[i]!;
      const [xj, yj] = ring[j]!;
      if (Math.abs(xi - xj) > 180) continue;
      if ((yi > latitudeDeg) !== (yj > latitudeDeg)
        && longitude < ((xj - xi) * (latitudeDeg - yi)) / (yj - yi) + xi) {
        inside = !inside;
      }
    }
    if (inside) return true;
  }
  return false;
}

/**
 * Distance to the nearest coastline segment, in kilometres.
 *
 * Measured in a local tangent plane centred on the query point, which is exact
 * enough over the few hundred kilometres this is ever asked about and avoids a
 * spherical point-to-arc solve per segment. Segments more than three degrees of
 * latitude or longitude away are skipped, so the answer saturates: anything
 * further than roughly 330 km comes back as `Infinity`, which is all a
 * clearance check needs.
 */
export function coastClearanceKm(index: LandIndex, longitudeDeg: number, latitudeDeg: number): number {
  const longitude = normalizeLongitudeDeg(longitudeDeg);
  const kx = Math.cos(latitudeDeg * DEG) * 111.32;
  const ky = 110.57;
  let best = Number.POSITIVE_INFINITY;
  for (let band = Math.floor(latitudeDeg) - 3; band <= Math.floor(latitudeDeg) + 3; band += 1) {
    const segments = index.bands.get(band);
    if (!segments) continue;
    for (const segment of segments) {
      const ax = (((segment.ax - longitude + 540) % 360) - 180) * kx;
      const bx = (((segment.bx - longitude + 540) % 360) - 180) * kx;
      if (Math.abs(ax) > 340 && Math.abs(bx) > 340) continue;
      const ay = (segment.ay - latitudeDeg) * ky;
      const by = (segment.by - latitudeDeg) * ky;
      const dx = bx - ax;
      const dy = by - ay;
      const lengthSquared = dx * dx + dy * dy;
      const t = lengthSquared > 0
        ? Math.max(0, Math.min(1, (-ax * dx + -ay * dy) / lengthSquared))
        : 0;
      const distance = Math.hypot(ax + t * dx, ay + t * dy);
      if (distance < best) best = distance;
    }
  }
  return best;
}

export interface LandCrossing {
  legIndex: number;
  latitudeDeg: number;
  longitudeDeg: number;
  /** 0 at the leg's start waypoint, 1 at its end. */
  fraction: number;
}

/**
 * Sample every leg of a route and report the positions that fall on land.
 *
 * Sampled at roughly `samplesPerDegree` positions per degree of great-circle
 * separation, along the route's OWN track model — a rhumb line and a great
 * circle between the same two points are different tracks and can disagree
 * about a landfall by hundreds of miles.
 */
export function routeLandCrossings(
  index: LandIndex,
  route: TransitRoute,
  samplesPerDegree = 4,
): LandCrossing[] {
  const crossings: LandCrossing[] = [];
  for (const leg of buildLegs(route)) {
    const separationDeg = leg.centralAngleRad / DEG;
    const steps = Math.max(8, Math.ceil(separationDeg * samplesPerDegree));
    for (let step = 0; step <= steps; step += 1) {
      const fraction = step / steps;
      const point = route.trackModel === "rhumb-line"
        ? interpolateRhumbLine(leg.from.latitudeDeg, leg.from.longitudeDeg, leg.to.latitudeDeg, leg.to.longitudeDeg, fraction)
        : interpolateGreatCircle(leg.from.latitudeDeg, leg.from.longitudeDeg, leg.to.latitudeDeg, leg.to.longitudeDeg, fraction);
      if (isOnLand(index, point.longitudeDeg, point.latitudeDeg)) {
        crossings.push({
          legIndex: leg.index,
          latitudeDeg: point.latitudeDeg,
          longitudeDeg: point.longitudeDeg,
          fraction,
        });
      }
    }
  }
  return crossings;
}

/** The tightest coastline clearance anywhere on the route, in kilometres. */
export function minimumCoastClearanceKm(
  index: LandIndex,
  route: TransitRoute,
  samplesPerDegree = 4,
): { km: number; latitudeDeg: number; longitudeDeg: number } {
  let best = { km: Number.POSITIVE_INFINITY, latitudeDeg: 0, longitudeDeg: 0 };
  for (const leg of buildLegs(route)) {
    const separationDeg = leg.centralAngleRad / DEG;
    const steps = Math.max(8, Math.ceil(separationDeg * samplesPerDegree));
    for (let step = 0; step <= steps; step += 1) {
      const fraction = step / steps;
      const point = route.trackModel === "rhumb-line"
        ? interpolateRhumbLine(leg.from.latitudeDeg, leg.from.longitudeDeg, leg.to.latitudeDeg, leg.to.longitudeDeg, fraction)
        : interpolateGreatCircle(leg.from.latitudeDeg, leg.from.longitudeDeg, leg.to.latitudeDeg, leg.to.longitudeDeg, fraction);
      const km = coastClearanceKm(index, point.longitudeDeg, point.latitudeDeg);
      if (km < best.km) best = { km, latitudeDeg: point.latitudeDeg, longitudeDeg: point.longitudeDeg };
    }
  }
  return best;
}

/** Great-circle distance, exported so a caller need not import the whole route module. */
export function separationKm(
  latitudeADeg: number, longitudeADeg: number,
  latitudeBDeg: number, longitudeBDeg: number,
): number {
  const latitudeA = latitudeADeg * DEG;
  const latitudeB = latitudeBDeg * DEG;
  const haversine = Math.sin((latitudeB - latitudeA) / 2) ** 2
    + Math.cos(latitudeA) * Math.cos(latitudeB) * Math.sin(((longitudeBDeg - longitudeADeg) * DEG) / 2) ** 2;
  return 2 * Math.asin(Math.min(1, Math.sqrt(Math.max(0, haversine)))) * EARTH_MEAN_RADIUS_KM;
}
