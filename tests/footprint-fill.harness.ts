/**
 * Browser-side half of the coverage-cap rendering guard.
 *
 * It drives the production SpaceGlobe — the real Earth mesh, the real camera,
 * the real materials — and measures the cap the only way that can catch this
 * class of defect: by reading the rendered pixels back out of WebGL. The
 * measurement is a difference of two renders of the same scene, one with the
 * cap's group visible and one without, so a "covered" pixel means the cap
 * actually changed what was drawn there rather than merely being submitted.
 */
import * as THREE from "three";
import { SpaceGlobe } from "../src/globe";
import { footprintPoints } from "../src/orbit";
import type { SatelliteRecord } from "../src/types";

const probeSatellite = {
  id: 1,
  name: "COVERAGE PROBE",
  cosparId: "0000-000A",
  ownerCode: "US",
  ownerLabel: "United States",
  organization: "None",
  mission: "communications",
  sector: "civil",
  constellation: null,
  sourceGroups: [],
  orbit: "GEO",
  periodMinutes: 1436,
  perigeeKm: 35786,
  apogeeKm: 35786,
  purpose: "rendering probe",
  purposeKind: "template",
  classificationConfidence: "high",
  omm: {},
} as unknown as SatelliteRecord;

const globe = new SpaceGlobe({
  container: document.getElementById("scene")!,
  satellites: [probeSatellite],
  land: { features: [] },
  onSelect: () => {},
});

// TypeScript's private is compile-time only; the harness deliberately reaches
// past it so the test measures the shipped objects rather than copies.
const internals = globe as unknown as Record<string, any>;

export interface CoverageMeasurement {
  /** Pixels where the cap changed the image. */
  covered: number;
  /** Pixels enclosed by the cap on their scanline where it did not. */
  holes: number;
  /** Scanlines carrying at least one such pixel. */
  holeRows: number;
}

function render() {
  const renderer = internals.renderer as THREE.WebGLRenderer;
  renderer.render(internals.scene, internals.camera);
  const size = new THREE.Vector2();
  renderer.getDrawingBufferSize(size);
  const pixels = new Uint8Array(size.x * size.y * 4);
  const gl = renderer.getContext();
  gl.readPixels(0, 0, size.x, size.y, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
  return { pixels, width: size.x, height: size.y };
}

function showCoverage(
  latitudeDeg: number,
  longitudeDeg: number,
  altitudeKm: number,
  minimumElevationDeg: number,
  cameraDistance: number,
  cameraOffsetDeg: number,
) {
  globe.setFootprintMinElevation(minimumElevationDeg);
  globe.setSelectedGeometry([], [], footprintPoints(latitudeDeg, longitudeDeg, altitudeKm, minimumElevationDeg, 96));
  const latitude = (latitudeDeg * Math.PI) / 180;
  const longitude = (longitudeDeg * Math.PI) / 180;
  const direction = new THREE.Vector3(
    Math.cos(latitude) * Math.cos(longitude),
    Math.sin(latitude),
    -Math.cos(latitude) * Math.sin(longitude),
  ).applyAxisAngle(new THREE.Vector3(0, 1, 0), (cameraOffsetDeg * Math.PI) / 180);
  internals.camera.position.copy(direction.multiplyScalar(cameraDistance));
  internals.camera.lookAt(0, 0, 0);
  internals.camera.updateMatrixWorld();
  internals.controls.target.set(0, 0, 0);
}

function measureCoverage(): CoverageMeasurement {
  const withCap = render();
  internals.selectionFootprintGroup.visible = false;
  const withoutCap = render();
  internals.selectionFootprintGroup.visible = true;

  const { width, height } = withCap;
  let covered = 0;
  let holes = 0;
  let holeRows = 0;
  for (let y = 0; y < height; y += 1) {
    let first = -1;
    let last = -1;
    for (let x = 0; x < width; x += 1) {
      const offset = (y * width + x) * 4;
      const difference = Math.abs(withCap.pixels[offset]! - withoutCap.pixels[offset]!)
        + Math.abs(withCap.pixels[offset + 1]! - withoutCap.pixels[offset + 1]!)
        + Math.abs(withCap.pixels[offset + 2]! - withoutCap.pixels[offset + 2]!);
      if (difference <= 1) continue;
      if (first < 0) first = x;
      last = x;
    }
    if (first < 0) continue;
    let rowHoles = 0;
    for (let x = first; x <= last; x += 1) {
      const offset = (y * width + x) * 4;
      const difference = Math.abs(withCap.pixels[offset]! - withoutCap.pixels[offset]!)
        + Math.abs(withCap.pixels[offset + 1]! - withoutCap.pixels[offset + 1]!)
        + Math.abs(withCap.pixels[offset + 2]! - withoutCap.pixels[offset + 2]!);
      if (difference > 1) covered += 1;
      else rowHoles += 1;
    }
    holes += rowHoles;
    if (rowHoles > 0) holeRows += 1;
  }
  return { covered, holes, holeRows };
}

Object.assign(window as unknown as Record<string, unknown>, {
  coverageProbe: { showCoverage, measureCoverage },
  coverageProbeReady: true,
});
