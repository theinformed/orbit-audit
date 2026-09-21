import { describe, expect, it } from "vitest";
import * as THREE from "three";
import {
  azimuthDifferenceDegrees,
  equirectangularLayerAzimuth,
  geoToSceneVector,
  sceneAzimuthDegrees,
} from "../src/globe";

/**
 * Longitudes that fall exactly on a vertex of every sphere the globe uses:
 * 96 width segments (Earth, D-RAP, aurora history) and 64 (TEC, aurora).
 */
const longitudes = [-180, -135, -90, -45, 0, 45, 90, 135];

function sphereLayer(radius: number, widthSegments: number, heightSegments: number) {
  return new THREE.Mesh(
    new THREE.SphereGeometry(radius, widthSegments, heightSegments),
    new THREE.MeshBasicMaterial(),
  );
}

describe("the measurement itself", () => {
  it("reports zero offset for an unrotated equirectangular sphere", () => {
    const mesh = sphereLayer(100, 96, 64);
    for (const longitudeDeg of longitudes) {
      const { azimuthDeg, textureCoordinateError } = equirectangularLayerAzimuth(mesh, longitudeDeg);
      expect(textureCoordinateError).toBeLessThan(1e-6);
      expect(Math.abs(azimuthDifferenceDegrees(azimuthDeg, longitudeDeg))).toBeLessThan(1e-6);
    }
  });

  it("catches the quarter-turn that shipped", () => {
    const mesh = sphereLayer(100, 96, 64);
    mesh.rotation.y = -Math.PI / 2;
    for (const longitudeDeg of longitudes) {
      const { azimuthDeg } = equirectangularLayerAzimuth(mesh, longitudeDeg);
      expect(azimuthDifferenceDegrees(azimuthDeg, longitudeDeg)).toBeCloseTo(-90, 6);
    }
  });

  it("agrees with the vector transform every layer is drawn against", () => {
    for (const longitudeDeg of longitudes) {
      expect(sceneAzimuthDegrees(geoToSceneVector(0, longitudeDeg, 100))).toBeCloseTo(longitudeDeg, 9);
      // And at a latitude, where the azimuth must not change.
      expect(sceneAzimuthDegrees(geoToSceneVector(53.4, longitudeDeg, 100))).toBeCloseTo(longitudeDeg, 9);
    }
  });

  it("wraps the shortest way round", () => {
    expect(azimuthDifferenceDegrees(179, -179)).toBeCloseTo(-2, 9);
    expect(azimuthDifferenceDegrees(-179, 179)).toBeCloseTo(2, 9);
    expect(azimuthDifferenceDegrees(10, 10)).toBe(0);
  });
});
