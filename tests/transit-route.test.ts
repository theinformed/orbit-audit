import { describe, expect, it } from "vitest";
import {
  buildLegs,
  centralAngleRad,
  greatCircleDistanceKm,
  initialCourseDeg,
  interpolateGreatCircle,
  interpolateRhumbLine,
  normalizeLongitudeDeg,
  positionAt,
  rhumbCourseDeg,
  rhumbDistanceKm,
  routePolyline,
  routeSpanMs,
  sampleRoute,
  validateRoute,
  type TransitRoute,
  type Waypoint,
} from "../src/transit-route";

const HOUR = 3_600_000;

function waypoint(id: string, latitudeDeg: number, longitudeDeg: number, timeMs: number): Waypoint {
  return { id, label: id, latitudeDeg, longitudeDeg, timeMs };
}

describe("great-circle geometry", () => {
  it("reproduces published great-circle distances", () => {
    // Pearl Harbor (21.35 N, 157.95 W) to Yokosuka (35.28 N, 139.67 E).
    // Published great-circle distance is about 6,200 km / 3,350 nautical miles.
    const km = greatCircleDistanceKm(21.35, -157.95, 35.28, 139.67);
    expect(km).toBeGreaterThan(6100);
    expect(km).toBeLessThan(6300);

    // A quarter of the way around the Earth is a quarter of the circumference.
    expect(greatCircleDistanceKm(0, 0, 0, 90)).toBeCloseTo(6371.0088 * Math.PI / 2, 6);
    // Pole to pole is half the circumference.
    expect(greatCircleDistanceKm(90, 0, -90, 0)).toBeCloseTo(6371.0088 * Math.PI, 6);
  });

  it("measures zero distance between a point and itself, including across the antimeridian", () => {
    expect(centralAngleRad(10, 180, 10, -180)).toBeCloseTo(0, 12);
    expect(greatCircleDistanceKm(-45.2, 179.999, -45.2, 179.999)).toBeCloseTo(0, 12);
  });

  it("gives due east as course 090 along the equator and due north as 000", () => {
    expect(initialCourseDeg(0, 0, 0, 10)).toBeCloseTo(90, 6);
    expect(initialCourseDeg(0, 0, 0, -10)).toBeCloseTo(270, 6);
    expect(initialCourseDeg(0, 0, 10, 0)).toBeCloseTo(0, 6);
    expect(initialCourseDeg(10, 0, -10, 0)).toBeCloseTo(180, 6);
  });

  it("interpolates the midpoint of an equatorial leg onto the equator", () => {
    const midpoint = interpolateGreatCircle(0, 0, 0, 60, 0.5);
    expect(midpoint.latitudeDeg).toBeCloseTo(0, 9);
    expect(midpoint.longitudeDeg).toBeCloseTo(30, 9);
  });

  it("bends a high-latitude east-west leg poleward, which a straight line would not", () => {
    // 60 N, 30 W to 60 N, 30 E. The great circle rises above 60 N; the rhumb
    // line stays exactly on it. This is the difference that matters at sea.
    const greatCircle = interpolateGreatCircle(60, -30, 60, 30, 0.5);
    const rhumb = interpolateRhumbLine(60, -30, 60, 30, 0.5);
    expect(greatCircle.latitudeDeg).toBeGreaterThan(60);
    // The vertex of this great circle is at 63.4349 N, which is the midpoint by
    // symmetry: normalising the sum of the two unit position vectors gives
    // asin(0.894427) = 63.4349. Three and a half degrees north of the rhumb
    // line, or about 210 nautical miles of cross-track separation.
    expect(greatCircle.latitudeDeg).toBeCloseTo(63.4349, 3);
    expect(rhumb.latitudeDeg).toBeCloseTo(60, 9);
    expect(greatCircle.longitudeDeg).toBeCloseTo(0, 9);
  });

  it("returns the endpoints exactly at fraction 0 and 1", () => {
    for (const interpolate of [interpolateGreatCircle, interpolateRhumbLine]) {
      const start = interpolate(12.5, -60, -33.9, 151.2, 0);
      const end = interpolate(12.5, -60, -33.9, 151.2, 1);
      expect(start.latitudeDeg).toBeCloseTo(12.5, 8);
      expect(start.longitudeDeg).toBeCloseTo(-60, 8);
      expect(end.latitudeDeg).toBeCloseTo(-33.9, 8);
      expect(end.longitudeDeg).toBeCloseTo(151.2, 8);
    }
  });

  it("takes the short way across the antimeridian rather than the long way round", () => {
    const midpoint = interpolateGreatCircle(0, 170, 0, -170, 0.5);
    expect(Math.abs(midpoint.longitudeDeg)).toBeCloseTo(180, 6);
    const rhumbMidpoint = interpolateRhumbLine(0, 170, 0, -170, 0.5);
    expect(Math.abs(rhumbMidpoint.longitudeDeg)).toBeCloseTo(180, 6);
  });
});

describe("rhumb-line geometry", () => {
  it("holds a constant course, and that course matches the leg", () => {
    expect(rhumbCourseDeg(0, 0, 0, 10)).toBeCloseTo(90, 6);
    expect(rhumbCourseDeg(0, 0, 10, 0)).toBeCloseTo(0, 6);
    expect(rhumbCourseDeg(40, 0, 50, 10)).toBeGreaterThan(0);
    expect(rhumbCourseDeg(40, 0, 50, 10)).toBeLessThan(90);
  });

  it("is longer than the great circle on a high-latitude east-west leg", () => {
    const rhumb = rhumbDistanceKm(60, -30, 60, 30);
    const great = greatCircleDistanceKm(60, -30, 60, 30);
    expect(rhumb).toBeGreaterThan(great);
    // On this leg the published difference is roughly 60 km out of ~3,300 km.
    expect(rhumb - great).toBeGreaterThan(30);
    expect(rhumb - great).toBeLessThan(120);
  });

  it("equals the great circle along a meridian and along the equator", () => {
    expect(rhumbDistanceKm(10, 25, 40, 25)).toBeCloseTo(greatCircleDistanceKm(10, 25, 40, 25), 6);
    expect(rhumbDistanceKm(0, -20, 0, 40)).toBeCloseTo(greatCircleDistanceKm(0, -20, 0, 40), 6);
  });
});

describe("longitude normalisation", () => {
  it("wraps into -180..180 and never produces negative zero", () => {
    expect(normalizeLongitudeDeg(190)).toBe(-170);
    expect(normalizeLongitudeDeg(-190)).toBe(170);
    // The antimeridian resolves to -180, matching `normalizeLongitude` in
    // src/ground-track-map.ts exactly. Both names for that meridian are the same
    // meridian; what matters is that the two modules agree, because the planner
    // draws through both.
    expect(normalizeLongitudeDeg(180)).toBe(-180);
    expect(normalizeLongitudeDeg(-180)).toBe(-180);
    expect(normalizeLongitudeDeg(540)).toBe(-180);
    expect(Object.is(normalizeLongitudeDeg(360), -0)).toBe(false);
    expect(normalizeLongitudeDeg(360)).toBe(0);
  });
});

describe("route position over time", () => {
  const route: TransitRoute = {
    trackModel: "great-circle",
    waypoints: [
      waypoint("a", 0, 0, 0),
      waypoint("b", 0, 30, 10 * HOUR),
      waypoint("c", 10, 30, 20 * HOUR),
    ],
  };

  it("returns the waypoint exactly at the waypoint's own time", () => {
    for (const point of route.waypoints) {
      const position = positionAt(route, point.timeMs)!;
      expect(position.latitudeDeg).toBeCloseTo(point.latitudeDeg, 8);
      expect(position.longitudeDeg).toBeCloseTo(point.longitudeDeg, 8);
    }
  });

  it("interpolates inside a leg at a constant angular rate", () => {
    const halfway = positionAt(route, 5 * HOUR)!;
    expect(halfway.legIndex).toBe(0);
    expect(halfway.fraction).toBeCloseTo(0.5, 10);
    expect(halfway.longitudeDeg).toBeCloseTo(15, 8);
    const quarter = positionAt(route, 2.5 * HOUR)!;
    expect(quarter.longitudeDeg).toBeCloseTo(7.5, 8);
  });

  it("refuses to extrapolate outside the route's own span", () => {
    expect(positionAt(route, -1)).toBeNull();
    expect(positionAt(route, 20 * HOUR + 1)).toBeNull();
    expect(positionAt(route, 0)).not.toBeNull();
    expect(positionAt(route, 20 * HOUR)).not.toBeNull();
  });

  it("assigns a time on a waypoint boundary to the earlier leg, so the boundary is not double-counted", () => {
    expect(positionAt(route, 10 * HOUR)!.legIndex).toBe(0);
    expect(positionAt(route, 10 * HOUR)!.fraction).toBeCloseTo(1, 10);
    expect(positionAt(route, 10 * HOUR + 1)!.legIndex).toBe(1);
  });

  it("reports the span only when the route has positive duration", () => {
    expect(routeSpanMs(route)).toEqual({ startMs: 0, endMs: 20 * HOUR });
    expect(routeSpanMs({ trackModel: "great-circle", waypoints: [waypoint("a", 0, 0, 0)] })).toBeNull();
    expect(routeSpanMs({
      trackModel: "great-circle",
      waypoints: [waypoint("a", 0, 0, 5), waypoint("b", 1, 1, 5)],
    })).toBeNull();
  });
});

describe("legs", () => {
  it("computes an implied speed that a navigator would recognise", () => {
    // 600 nautical miles in 30 hours is 20 knots.
    const distanceKm = 600 * 1.852;
    const degrees = (distanceKm / 6371.0088) * (180 / Math.PI);
    const legs = buildLegs({
      trackModel: "great-circle",
      waypoints: [waypoint("a", 0, 0, 0), waypoint("b", 0, degrees, 30 * HOUR)],
    });
    expect(legs).toHaveLength(1);
    expect(legs[0]!.speedKnots).toBeCloseTo(20, 6);
    expect(legs[0]!.initialCourseDeg).toBeCloseTo(90, 6);
  });

  it("reports infinite speed rather than dividing by zero on a zero-duration leg", () => {
    const legs = buildLegs({
      trackModel: "great-circle",
      waypoints: [waypoint("a", 0, 0, 0), waypoint("b", 0, 10, 0)],
    });
    expect(legs[0]!.speedKnots).toBe(Number.POSITIVE_INFINITY);
  });

  it("uses the route's own track model for the along-track distance", () => {
    const waypoints = [waypoint("a", 60, -30, 0), waypoint("b", 60, 30, 10 * HOUR)];
    const great = buildLegs({ trackModel: "great-circle", waypoints })[0]!;
    const rhumb = buildLegs({ trackModel: "rhumb-line", waypoints })[0]!;
    expect(rhumb.trackDistanceKm).toBeGreaterThan(great.trackDistanceKm);
    expect(rhumb.greatCircleKm).toBeCloseTo(great.greatCircleKm, 9);
    expect(rhumb.speedKnots).toBeGreaterThan(great.speedKnots);
    expect(rhumb.initialCourseDeg).toBeCloseTo(90, 6);
    expect(great.initialCourseDeg).toBeLessThan(90);
  });
});

describe("sampling", () => {
  const route: TransitRoute = {
    trackModel: "great-circle",
    waypoints: [
      waypoint("a", 0, 0, 0),
      // Deliberately not on a round step boundary.
      waypoint("b", 5, 20, 3_723_000),
      waypoint("c", 10, 40, 9_000_000),
    ],
  };

  it("always includes every waypoint time exactly, whatever the step", () => {
    for (const stepSeconds of [60, 300, 1000, 3600]) {
      const times = new Set(sampleRoute(route, stepSeconds).map((point) => point.timeMs));
      for (const point of route.waypoints) expect(times.has(point.timeMs)).toBe(true);
    }
  });

  it("includes both ends and stays sorted", () => {
    const samples = sampleRoute(route, 600);
    expect(samples[0]!.timeMs).toBe(0);
    expect(samples.at(-1)!.timeMs).toBe(9_000_000);
    for (let index = 1; index < samples.length; index += 1) {
      expect(samples[index]!.timeMs).toBeGreaterThan(samples[index - 1]!.timeMs);
    }
  });

  it("returns nothing for a degenerate route or a non-positive step", () => {
    expect(sampleRoute(route, 0)).toEqual([]);
    expect(sampleRoute({ trackModel: "great-circle", waypoints: [waypoint("a", 0, 0, 0)] }, 60)).toEqual([]);
  });
});

describe("validation", () => {
  it("accepts a well-formed route", () => {
    expect(validateRoute({
      trackModel: "great-circle",
      waypoints: [waypoint("a", 21.3, -157.9, 0), waypoint("b", 35.3, 139.7, 10 * 24 * HOUR)],
    })).toEqual([]);
  });

  it("rejects a route whose times run backwards", () => {
    const issues = validateRoute({
      trackModel: "great-circle",
      waypoints: [waypoint("a", 0, 0, 10 * HOUR), waypoint("b", 0, 10, 0)],
    });
    expect(issues.map((issue) => issue.kind)).toContain("non-monotonic-time");
  });

  it("flags a leg that implies an impossible speed rather than silently answering", () => {
    const issues = validateRoute({
      trackModel: "great-circle",
      waypoints: [waypoint("a", 0, 0, 0), waypoint("b", 0, 179, HOUR)],
    });
    expect(issues.map((issue) => issue.kind)).toContain("implausible-speed");
  });

  it("flags an out-of-range latitude and a single-waypoint route", () => {
    const issues = validateRoute({ trackModel: "great-circle", waypoints: [waypoint("a", 95, 0, 0)] });
    expect(issues.map((issue) => issue.kind)).toContain("out-of-range-latitude");
    expect(issues.map((issue) => issue.kind)).toContain("too-few-waypoints");
  });
});

describe("drawable polyline", () => {
  it("densifies a long leg so a great circle is not drawn as a straight line", () => {
    const vertices = routePolyline({
      trackModel: "great-circle",
      waypoints: [waypoint("a", 60, -30, 0), waypoint("b", 60, 30, 10 * HOUR)],
    }, 1.5);
    expect(vertices.length).toBeGreaterThan(20);
    expect(Math.max(...vertices.map((vertex) => vertex.latitudeDeg))).toBeGreaterThan(62);
    expect(vertices[0]!.latitudeDeg).toBeCloseTo(60, 8);
    expect(vertices.at(-1)!.latitudeDeg).toBeCloseTo(60, 8);
    expect(vertices.at(-1)!.timeMs).toBe(10 * HOUR);
  });

  it("keeps a rhumb-line leg on its own latitude", () => {
    const vertices = routePolyline({
      trackModel: "rhumb-line",
      waypoints: [waypoint("a", 60, -30, 0), waypoint("b", 60, 30, 10 * HOUR)],
    }, 1.5);
    expect(Math.max(...vertices.map((vertex) => vertex.latitudeDeg))).toBeCloseTo(60, 8);
  });

  it("carries a monotonic time along the drawn track", () => {
    const vertices = routePolyline({
      trackModel: "great-circle",
      waypoints: [waypoint("a", 0, 0, 0), waypoint("b", 20, 40, 5 * HOUR), waypoint("c", -10, 90, 12 * HOUR)],
    });
    for (let index = 1; index < vertices.length; index += 1) {
      expect(vertices[index]!.timeMs).toBeGreaterThan(vertices[index - 1]!.timeMs);
    }
  });
});

describe("the drawn rhumb line is the loxodrome it says it is", () => {
  /**
   * A rhumb line is DEFINED by holding one course. So the course from the
   * start of the leg to any point drawn on it must be the course of the leg —
   * that is the claim, and it is the one the interpolator has to satisfy.
   *
   * Interpolating linearly in longitude as well as latitude, which is what
   * this did until 2026-09-08, fails it: on this leg the drawn midpoint sat
   * on a course of about 47 degrees against the leg's 42, roughly 480 km from
   * the loxodrome.
   */
  it("holds the leg's own course at every point it draws", () => {
    const legCourse = rhumbCourseDeg(0, 0, 60, 60);
    for (const fraction of [0.1, 0.25, 0.5, 0.75, 0.9]) {
      const point = interpolateRhumbLine(0, 0, 60, 60, fraction);
      expect(rhumbCourseDeg(0, 0, point.latitudeDeg, point.longitudeDeg)).toBeCloseTo(legCourse, 6);
      expect(rhumbCourseDeg(point.latitudeDeg, point.longitudeDeg, 60, 60)).toBeCloseTo(legCourse, 6);
    }
  });

  /**
   * And the speed the planner reports is one number for the whole leg, so
   * equal fractions of time have to be equal along-track distances.
   */
  it("advances a constant distance per unit fraction", () => {
    const total = rhumbDistanceKm(0, 0, 60, 60);
    for (const fraction of [0.2, 0.4, 0.6, 0.8]) {
      const point = interpolateRhumbLine(0, 0, 60, 60, fraction);
      expect(rhumbDistanceKm(0, 0, point.latitudeDeg, point.longitudeDeg)).toBeCloseTo(total * fraction, 6);
    }
  });

  /** An east-west leg has no Mercator span; longitude is linear in distance there. */
  it("still walks a parallel evenly", () => {
    const point = interpolateRhumbLine(60, -30, 60, 30, 0.25);
    expect(point.latitudeDeg).toBeCloseTo(60, 9);
    expect(point.longitudeDeg).toBeCloseTo(-15, 9);
  });
});
