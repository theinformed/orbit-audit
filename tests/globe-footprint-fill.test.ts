import { describe, expect, it } from "vitest";
import * as THREE from "three";
import {
  EARTH_SCENE_RADIUS,
  FOOTPRINT_FILL_MINIMUM_CLEARANCE,
  FOOTPRINT_FILL_RADIUS,
  buildFootprintFillGeometry,
  footprintFillEdgePoints,
  footprintFillRingCount,
  geoToSceneVector,
  sphericalChordSag,
} from "../src/globe";
import { footprintAngularRadius, footprintPoints } from "../src/orbit";

/**
 * Reproduce exactly what the globe feeds buildFootprintFill: the production
 * footprint generator, mapped through the production coordinate transform at
 * the production boundary radius.
 */
function productionBoundary(latitudeDeg: number, longitudeDeg: number, altitudeKm: number, maskDeg: number) {
  return footprintPoints(latitudeDeg, longitudeDeg, altitudeKm, maskDeg, 96)
    .map(([longitude, latitude]) => geoToSceneVector(latitude, longitude, 100.9));
}

/**
 * Closest approach to the globe's centre over every rendered triangle, not
 * merely every vertex. Vertices always sit on the cap sphere; it is the flat
 * interior of each triangle that can fall inside the Earth.
 */
function closestApproachOverTriangles(geometry: ReturnType<typeof buildFootprintFillGeometry>) {
  const corner = (index: number) =>
    new THREE.Vector3(
      geometry.positions[index * 3]!,
      geometry.positions[index * 3 + 1]!,
      geometry.positions[index * 3 + 2]!,
    );
  const origin = new THREE.Vector3(0, 0, 0);
  const closest = new THREE.Vector3();
  let nearest = Infinity;
  for (let offset = 0; offset < geometry.indices.length; offset += 3) {
    const triangle = new THREE.Triangle(
      corner(geometry.indices[offset]!),
      corner(geometry.indices[offset + 1]!),
      corner(geometry.indices[offset + 2]!),
    );
    triangle.closestPointToPoint(origin, closest);
    nearest = Math.min(nearest, closest.length());
  }
  return nearest;
}

const altitudes: Array<[string, number]> = [
  ["ISS", 420],
  ["low Earth orbit", 481],
  ["high LEO", 1200],
  ["MEO / GPS", 20200],
  ["GEO", 35786],
  ["highly elliptical apogee", 60000],
  ["deep apogee", 120000],
];

describe("satellite coverage-cap tessellation", () => {
  it.each(altitudes)("keeps the %s cap above the globe at every elevation mask", (_name, altitudeKm) => {
    for (const maskDeg of [0, 5, 10]) {
      for (const latitudeDeg of [0, 11.3, 51.6, 82]) {
        const geometry = buildFootprintFillGeometry(productionBoundary(latitudeDeg, -47.9, altitudeKm, maskDeg));
        expect(closestApproachOverTriangles(geometry)).toBeGreaterThanOrEqual(
          EARTH_SCENE_RADIUS + FOOTPRINT_FILL_MINIMUM_CLEARANCE,
        );
      }
    }
  });

  it("cuts into the globe under the construction that shipped, and not under this one", () => {
    // Frozen copy of the pre-fix construction: seven rings whatever the cap's
    // size, positioned by normalised linear interpolation. Kept here only to
    // demonstrate the defect this module now avoids, never called by the app.
    const shippedSevenRingCap = (boundary: THREE.Vector3[]) => {
      const edge = boundary.at(-1)?.distanceTo(boundary[0]!) === 0 ? boundary.slice(0, -1) : boundary;
      const center = edge
        .reduce((sum, point) => sum.add(point.clone().normalize()), new THREE.Vector3())
        .normalize();
      const positions: number[] = [center.x * 100.78, center.y * 100.78, center.z * 100.78];
      for (let ring = 1; ring <= 7; ring += 1) {
        edge.forEach((point) => {
          const placed = center.clone()
            .lerp(point.clone().normalize(), ring / 7)
            .normalize()
            .multiplyScalar(100.78);
          positions.push(placed.x, placed.y, placed.z);
        });
      }
      const indices: number[] = [];
      for (let segment = 0; segment < edge.length; segment += 1) {
        indices.push(0, 1 + segment, 1 + ((segment + 1) % edge.length));
      }
      for (let ring = 1; ring < 7; ring += 1) {
        const inner = 1 + (ring - 1) * edge.length;
        const outer = 1 + ring * edge.length;
        for (let segment = 0; segment < edge.length; segment += 1) {
          const next = (segment + 1) % edge.length;
          indices.push(inner + segment, outer + segment, inner + next);
          indices.push(inner + next, outer + segment, outer + next);
        }
      }
      return { positions: Float32Array.from(positions), edgeAmounts: new Float32Array(), indices, rings: 7, angularRadiusRad: 0 };
    };

    const boundary = productionBoundary(11.3, -47.9, 35786, 0);
    expect(closestApproachOverTriangles(shippedSevenRingCap(boundary))).toBeLessThan(EARTH_SCENE_RADIUS);
    expect(closestApproachOverTriangles(buildFootprintFillGeometry(boundary)))
      .toBeGreaterThanOrEqual(EARTH_SCENE_RADIUS + FOOTPRINT_FILL_MINIMUM_CLEARANCE);

    // Both halves of the fix matter: more rings, and rings at an even step.
    const geoAngularRadius = footprintAngularRadius(35786, 0);
    expect(footprintFillRingCount(geoAngularRadius, 96)).toBeGreaterThan(7);
    expect(sphericalChordSag(FOOTPRINT_FILL_RADIUS, geoAngularRadius / 7))
      .toBeGreaterThan(FOOTPRINT_FILL_RADIUS - EARTH_SCENE_RADIUS - FOOTPRINT_FILL_MINIMUM_CLEARANCE);
  });

  it("spends more rings on wider caps and never fewer than the smooth-shading floor", () => {
    const leo = footprintFillRingCount(footprintAngularRadius(420, 0), 96);
    const meo = footprintFillRingCount(footprintAngularRadius(20200, 0), 96);
    const geo = footprintFillRingCount(footprintAngularRadius(35786, 0), 96);
    expect(leo).toBe(7);
    expect(meo).toBeGreaterThan(leo);
    expect(geo).toBeGreaterThan(meo);
    expect(footprintFillRingCount(0, 96)).toBe(7);
  });

  it("drops the repeated closing vertex the generators emit", () => {
    const boundary = productionBoundary(11.3, -47.9, 35786, 0);
    const last = boundary.at(-1)!;
    // The closing point is recomputed rather than copied, so an exact equality
    // test — which is what shipped — never fires on it.
    expect(last.equals(boundary[0]!)).toBe(false);
    expect(last.distanceTo(boundary[0]!)).toBeLessThan(1e-9);
    expect(footprintFillEdgePoints(boundary)).toHaveLength(boundary.length - 1);
  });

  it("keeps an open boundary intact", () => {
    const open = [
      new THREE.Vector3(100.9, 0, 0),
      new THREE.Vector3(0, 100.9, 0),
      new THREE.Vector3(0, 0, 100.9),
      new THREE.Vector3(-100.9, 0, 0),
    ];
    expect(footprintFillEdgePoints(open)).toHaveLength(4);
  });

  it("indexes every generated vertex and emits no degenerate triangles", () => {
    const geometry = buildFootprintFillGeometry(productionBoundary(11.3, -47.9, 35786, 0));
    const vertexCount = geometry.positions.length / 3;
    expect(geometry.edgeAmounts).toHaveLength(vertexCount);
    expect(Math.max(...geometry.indices)).toBe(vertexCount - 1);
    for (let offset = 0; offset < geometry.indices.length; offset += 3) {
      const a = geometry.indices[offset]!;
      const b = geometry.indices[offset + 1]!;
      const c = geometry.indices[offset + 2]!;
      expect(a === b || b === c || a === c).toBe(false);
    }
  });

  it("reports the cap's own angular radius", () => {
    const geometry = buildFootprintFillGeometry(productionBoundary(11.3, -47.9, 35786, 0));
    expect(geometry.angularRadiusRad).toBeCloseTo(footprintAngularRadius(35786, 0), 2);
  });
});
