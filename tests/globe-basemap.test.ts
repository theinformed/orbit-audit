import * as THREE from "three";
import { describe, expect, it } from "vitest";
import {
  azimuthDifferenceDegrees,
  coastlineSegmentPositions,
  earthTextureWidth,
  equirectangularLayerAzimuth,
  geoToSceneVector,
  sceneAzimuthDegrees,
  type LandGeoJson,
} from "../src/globe";

const twoIslands: LandGeoJson = {
  features: [
    {
      geometry: {
        type: "Polygon",
        coordinates: [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
      },
    },
    {
      geometry: {
        type: "MultiPolygon",
        coordinates: [[[[-100, -20], [-99, -20], [-99, -19], [-100, -20]]]],
      },
    },
  ],
};

describe("coastline geometry", () => {
  it("emits one segment per pair of consecutive ring points", () => {
    const positions = coastlineSegmentPositions(twoIslands, 100);
    // 4 segments from the square, 3 from the triangle, two vertices each.
    expect(positions.length).toBe((4 + 3) * 2 * 3);
  });

  it("breaks a ring at the antimeridian instead of drawing across the map", () => {
    const crossing: LandGeoJson = {
      features: [{
        geometry: { type: "Polygon", coordinates: [[[179, 0], [-179, 0], [-179, 1], [179, 0]]] },
      }],
    };
    // Three point pairs, but the first and the last each step across the seam.
    expect(coastlineSegmentPositions(crossing, 100).length).toBe(1 * 2 * 3);
  });

  it("draws a border shared by two countries once, not twice", () => {
    const neighbours: LandGeoJson = {
      features: [
        { geometry: { type: "Polygon", coordinates: [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]] } },
        // Shares the [1,0]-[1,1] edge, walked in the opposite direction.
        { geometry: { type: "Polygon", coordinates: [[[1, 1], [1, 0], [2, 0], [2, 1], [1, 1]]] } },
      ],
    };
    // 4 + 4 ring segments, minus the one shared edge.
    expect(coastlineSegmentPositions(neighbours, 100).length).toBe(7 * 2 * 3);
  });

  /**
   * The coastline is drawn as geometry and the land fill underneath it is
   * drawn as a texture, by two different pieces of code. If those two ever
   * disagree the coastline floats off its own coast — which is the visible
   * form of the 90-degree registration bug, now with a line on top making it
   * obvious rather than a graticule hiding it.
   *
   * globe-texture-alignment.test.ts checks the raster side against the
   * geometry convention. This checks the coastline against the raster, so the
   * chain from GeoJSON longitude to painted pixel is closed end to end.
   */
  // equirectangularLayerAzimuth reports the nearest mesh vertex, so these are
  // longitudes that land exactly on one: the Earth sphere has 96 width
  // segments, or 3.75 degrees apart.
  it.each([0, 45, -90, 150, 180, -78.75])("puts the coastline at longitude %s on the basemap column that paints it", (longitude) => {
    const equatorialCoast: LandGeoJson = {
      features: [{
        geometry: { type: "Polygon", coordinates: [[[longitude, 0], [longitude, 1]]] },
      }],
    };
    const positions = coastlineSegmentPositions(equatorialCoast, 100);
    const coastPoint = new THREE.Vector3(positions[0]!, positions[1]!, positions[2]!);

    const basemap = new THREE.Mesh(
      new THREE.SphereGeometry(100, 96, 64),
      new THREE.MeshBasicMaterial(),
    );
    const { azimuthDeg } = equirectangularLayerAzimuth(basemap, longitude);

    expect(Math.abs(azimuthDifferenceDegrees(sceneAzimuthDegrees(coastPoint), azimuthDeg))).toBeLessThan(1e-6);
  });

  it("places a coastline vertex exactly where geoToSceneVector places it", () => {
    const positions = coastlineSegmentPositions(twoIslands, 100);
    const expected = geoToSceneVector(0, 0, 100);
    expect(positions[0]).toBeCloseTo(expected.x, 9);
    expect(positions[1]).toBeCloseTo(expected.y, 9);
    expect(positions[2]).toBeCloseTo(expected.z, 9);
  });
});

describe("basemap texture size", () => {
  it("asks for 2048, which is all a smooth-colour basemap needs", () => {
    expect(earthTextureWidth({ maxTextureSize: 16384 })).toBe(2048);
  });

  it("never asks a device for a texture larger than it supports", () => {
    expect(earthTextureWidth({ maxTextureSize: 1024 })).toBe(1024);
  });
});
