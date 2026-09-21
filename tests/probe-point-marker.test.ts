/**
 * The probe marker's hide-on-the-far-side rule.
 *
 * This exists because the browser check for it could not be made to pay. Two
 * attempts at proving it by orbiting the globe and counting amber pixels both
 * measured the wrong thing — the first re-picked the point after every camera
 * move, so each view was reading a different place, and the second ran past ten
 * minutes on a software renderer without finishing. The rule itself is four
 * numbers and an inequality, so it is checked here instead, where it is exact.
 *
 * The geometry: Earth's centre is the scene origin, so a surface point's
 * outward normal IS the point. It is on the near face exactly while that normal
 * still has a component toward the camera.
 */
import { describe, expect, it } from "vitest";
import * as THREE from "three";

import { probePointFacesCamera } from "../src/globe";

const EARTH = 100;
const SURFACE = EARTH * 1.004;
/** Straight out along +z, the distance the globe is normally viewed from. */
const CAMERA = new THREE.Vector3(0, 0, 300);

/** A surface point at this angle away from the point facing the camera. */
function surfacePointAtAngle(degrees: number): THREE.Vector3 {
  const a = (degrees * Math.PI) / 180;
  return new THREE.Vector3(Math.sin(a) * SURFACE, 0, Math.cos(a) * SURFACE);
}

describe("which side of the globe a probed place is on", () => {
  it("shows the point under the camera", () => {
    expect(probePointFacesCamera(surfacePointAtAngle(0), CAMERA)).toBe(true);
  });

  it("hides its antipode", () => {
    expect(probePointFacesCamera(surfacePointAtAngle(180), CAMERA)).toBe(false);
  });

  /**
   * The horizon is NOT at 90 degrees for a camera at a finite distance, and
   * getting that wrong is the whole reason this tests against the camera's
   * position rather than its view direction. From 300 units out, a surface at
   * 100.4 turns away at acos(100.4/300) = 70.4 degrees — twenty degrees of
   * globe that a 90-degree rule would have drawn a marker on top of.
   */
  it("puts the horizon where perspective actually puts it, not at 90 degrees", () => {
    const horizon = (Math.acos(SURFACE / CAMERA.length()) * 180) / Math.PI;
    expect(horizon).toBeGreaterThan(70);
    expect(horizon).toBeLessThan(71);
    expect(probePointFacesCamera(surfacePointAtAngle(horizon - 1), CAMERA)).toBe(true);
    expect(probePointFacesCamera(surfacePointAtAngle(horizon + 1), CAMERA)).toBe(false);
    // A 90-degree rule would call this one visible. It is not.
    expect(probePointFacesCamera(surfacePointAtAngle(80), CAMERA)).toBe(false);
  });

  /** The rule must not depend on which way the camera happens to be parked. */
  it("holds from any camera position", () => {
    for (const camera of [
      new THREE.Vector3(300, 0, 0),
      new THREE.Vector3(0, 300, 0),
      new THREE.Vector3(-180, 140, -160),
    ]) {
      const near = camera.clone().setLength(SURFACE);
      expect(probePointFacesCamera(near, camera), `near, camera ${camera.toArray()}`).toBe(true);
      expect(probePointFacesCamera(near.clone().negate(), camera), `far, camera ${camera.toArray()}`).toBe(false);
    }
  });

  /**
   * Pulling the camera back moves the horizon toward 90 degrees, because the
   * view tends to orthographic. If this ever stopped being true the rule would
   * have quietly become a fixed-angle test.
   */
  it("widens the visible face as the camera pulls back", () => {
    const grazing = surfacePointAtAngle(85);
    expect(probePointFacesCamera(grazing, new THREE.Vector3(0, 0, 300))).toBe(false);
    expect(probePointFacesCamera(grazing, new THREE.Vector3(0, 0, 4000))).toBe(true);
  });
});
