import { describe, expect, it } from "vitest";
import * as THREE from "three";
import {
  createBoundaryRimGeometry,
  createLoftedBoundaryGeometry,
  createMagnetosheathGeometry,
  createProjectedLineSegmentsGeometry,
  buildProjectedFlowAdvectionPaths,
  decodeBoundaryProfile,
  decodeProjectedStreamlines,
  sampleProjectedFlowAdvectionPath,
} from "../src/geospace-structures";
import type {
  EncodedFrameStructures,
  EncodedProjectedStreamlines,
  GeospaceStructuresDefinition,
} from "../src/geospace-structures";

function littleEndianU16(values: number[]) {
  const bytes = new Uint8Array(values.length * 2);
  values.forEach((value, index) => {
    bytes[index * 2] = value & 255;
    bytes[index * 2 + 1] = value >>> 8;
  });
  return btoa(String.fromCharCode(...bytes));
}

function littleEndianI16(values: number[]) {
  return littleEndianU16(values.map((value) => value < 0 ? value + 65536 : value));
}

const definition: GeospaceStructuresDefinition = {
  status: "model-derived-proxies",
  coordinateSystem: "GSM",
  anglesDegrees: [-10, 0, 10],
  radiusEncoding: { storage: "little-endian uint16 base64", scaleRe: 0.01, missingValue: 65535 },
  streamlineEncoding: { storage: "compact", scaleRe: 0.01, flowSpeedScaleKps: 0.1 },
};

const lines: EncodedProjectedStreamlines = {
  lineCount: 1,
  pointCount: 3,
  coordinatesI16: littleEndianI16([100, -100, 200, 0, 300, 100]),
  offsetsU16: littleEndianU16([0, 3]),
  speedU16: littleEndianU16([4000, 2000, 1000]),
};

function plane(bow: number[], magnetopause: number[]) {
  return {
    bowShockRadiusU16: littleEndianU16(bow),
    magnetopauseProxyRadiusU16: littleEndianU16(magnetopause),
    projectedMagneticStreamlines: lines,
    projectedFlowStreamlines: lines,
  };
}

const frame: EncodedFrameStructures = {
  equatorial: plane([1900, 1800, 1700], [1500, 1400, 1300]),
  meridional: plane([2000, 1800, 1600], [1450, 1400, 1250]),
};

describe("SWMF structure profiles", () => {
  it("decodes missing values and validates compact projected lines", () => {
    expect(decodeBoundaryProfile(definition, littleEndianU16([1234, 65535, 100]))).toEqual([12.34, null, 1]);
    expect(decodeProjectedStreamlines(definition, lines)).toEqual([[[1, -1], [2, 0], [3, 1]]]);
    expect(decodeProjectedStreamlines(definition, { ...lines, pointCount: 4 })).toEqual([]);
  });

  it("lofts a 3-D cue that intersects both observed model cuts", () => {
    const geometry = createLoftedBoundaryGeometry(definition, frame, "bowShock", undefined, 4);
    const positions = geometry.getAttribute("position");
    const theta = THREE.MathUtils.degToRad(10);
    expect(positions.getX(4)).toBeCloseTo(17 * Math.cos(theta));
    expect(positions.getY(4)).toBeCloseTo(17 * Math.sin(theta));
    expect(positions.getZ(4)).toBeCloseTo(0);
    expect(positions.getX(5)).toBeCloseTo(16 * Math.cos(theta));
    expect(positions.getY(5)).toBeCloseTo(0);
    expect(positions.getZ(5)).toBeCloseTo(16 * Math.sin(theta));
    expect(geometry.getIndex()!.count).toBeGreaterThan(0);
    geometry.dispose();
  });

  it("leaves unsupported profile sectors open instead of symmetry-filling them", () => {
    const supported = createMagnetosheathGeometry(definition, frame, undefined, 8);
    const frameWithGap: EncodedFrameStructures = {
      ...frame,
      meridional: plane([2000, 1800, 65535], [1450, 1400, 65535]),
    };
    const gapped = createMagnetosheathGeometry(definition, frameWithGap, undefined, 8);
    expect(gapped.getIndex()!.count).toBeLessThan(supported.getIndex()!.count);
    supported.dispose();
    gapped.dispose();
  });

  it("maps projected lines without claiming out-of-plane topology", () => {
    const geometry = createProjectedLineSegmentsGeometry(
      definition,
      lines,
      "meridional",
      (x, cross) => new THREE.Vector3(x, cross, 0),
    );
    expect(Array.from(geometry.getAttribute("position").array)).toEqual([
      1, -1, 0, 2, 0, 0,
      2, 0, 0, 3, 1, 0,
    ]);
    geometry.dispose();
  });

  it("advects along actual projected flow with model-relative slowing and rejects Earth-crossing chords", () => {
    const paths = buildProjectedFlowAdvectionPaths(definition, lines, {
      minimumRadiusRe: 0,
      maximumSegmentRe: 2,
    });
    expect(paths).toHaveLength(1);
    expect(paths[0]!.speedKps[0]).toBe(400);
    expect(paths[0]!.speedKps[2]).toBe(100);
    const halfway = sampleProjectedFlowAdvectionPath(paths[0]!, paths[0]!.elapsedModelSeconds[1]! / 2, false);
    expect(halfway).toMatchObject({ xRe: 1.5, crossRe: -0.5, speedKps: 300 });

    const crossing: EncodedProjectedStreamlines = {
      lineCount: 1,
      pointCount: 2,
      coordinatesI16: littleEndianI16([-300, 0, 300, 0]),
      offsetsU16: littleEndianU16([0, 2]),
      speedU16: littleEndianU16([4000, 4000]),
    };
    expect(buildProjectedFlowAdvectionPaths(definition, crossing, { maximumSegmentRe: 10 })).toEqual([]);
  });
});


describe("the cap has an edge", () => {
  /**
   * The published extraction runs only -70 to +70 degrees of polar angle, so
   * these boundaries are a cap around the subsolar point: no flanks, no tail.
   * Drawn as a translucent shell that simply stopped, the near and far halves
   * read from an oblique camera as two disconnected patches rather than as one
   * surface with a boundary. Sean described exactly that.
   *
   * A boundary that stops should look like it stops.
   */
  it("puts the rim at the outermost published angle, not at an invented one", () => {
    const rim = createBoundaryRimGeometry(definition, frame, "bowShock");
    expect(rim).not.toBeNull();
    const widest = Math.max(...definition.anglesDegrees.map(Math.abs));
    expect(rim!.thetaDegrees).toBe(widest);
    // ...and it says why it is there, so the reason survives into the scene.
    expect(String(rim!.geometry.userData.why)).toContain("extraction stops here");
  });

  it("draws a closed ring of real points", () => {
    const rim = createBoundaryRimGeometry(definition, frame, "bowShock", undefined, 64);
    const position = rim!.geometry.getAttribute("position");
    expect(position.count).toBeGreaterThan(32);
    for (let index = 0; index < position.count; index += 1) {
      expect(Number.isFinite(position.getX(index))).toBe(true);
      expect(Number.isFinite(position.getY(index))).toBe(true);
      expect(Number.isFinite(position.getZ(index))).toBe(true);
    }
  });

  it("sits on the surface it is the edge of", () => {
    // The rim must be the same lofted radii as the outermost ring of the shell,
    // or it would be a decorative ring floating near a boundary rather than
    // that boundary's actual edge.
    const rim = createBoundaryRimGeometry(definition, frame, "bowShock", undefined, 64)!;
    const surface = createLoftedBoundaryGeometry(definition, frame, "bowShock", undefined, 64);
    const surfacePositions = surface.getAttribute("position");
    const rimPositions = rim.geometry.getAttribute("position");
    const radiusOf = (attribute: THREE.BufferAttribute, index: number) =>
      Math.hypot(attribute.getX(index), attribute.getY(index), attribute.getZ(index));
    let nearest = Number.POSITIVE_INFINITY;
    const rimRadius = radiusOf(rimPositions as THREE.BufferAttribute, 0);
    for (let index = 0; index < surfacePositions.count; index += 1) {
      const radius = radiusOf(surfacePositions as THREE.BufferAttribute, index);
      if (radius > 0) nearest = Math.min(nearest, Math.abs(radius - rimRadius));
    }
    expect(nearest).toBeLessThan(1e-6);
  });

  it("returns null rather than a broken ring when the edge did not resolve", () => {
    // Half a rim implies an edge that was never extracted. Better to draw none.
    const empty = { ...frame, meridional: { ...frame.meridional } } as typeof frame;
    const rim = createBoundaryRimGeometry(
      { ...definition, anglesDegrees: [] },
      empty,
      "bowShock",
    );
    expect(rim).toBeNull();
  });
});
