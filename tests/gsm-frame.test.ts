/**
 * The sun-frame group's rotation must be the FULL GSM frame, not merely
 * sun-pointing.
 *
 * Everything inside `sunFrameGroup` — field lines, cusp funnels, MHD cut
 * planes, plasmasphere, solar wind — is authored in GSM coordinates, and GSM
 * is defined by its roll about the Sun line: X at the Sun, geodipole axis in
 * the X–Z plane (Y dusk-positive). The old construction,
 * `setFromUnitVectors(+x, sunDirection)`, was the minimal rotation onto the
 * Sun and left that roll arbitrary, so the field model's dipole tilt was
 * applied in the wrong meridian: drawn footpoints ringed roughly the
 * geographic pole while the OVATION aurora (geographic coordinates on the
 * Earth mesh) correctly ringed the magnetic pole ~11° away — Sean's
 * "aurora and funnel don't align", varying with time of day.
 *
 * These tests pin the definition itself: in the frame the quaternion
 * establishes, the live dipole axis must have zero GSM-Y component and a
 * positive GSM-Z component, at times spread across seasons and across a full
 * rotation of the Earth (including the hours where the old construction was
 * maximally wrong) — and the implied tilt must agree with the Hapgood
 * calculation the boundary models use.
 */
import * as THREE from "three";
import { describe, expect, it } from "vitest";

import {
  gsmFrameQuaternion,
  gsmSceneAxes,
  sceneDipoleAxisDirection,
  sceneSunDirection,
  type ReferenceFrame,
} from "../src/globe";
import { dipoleTilt } from "../src/dipole-tilt";

const TIMES = [
  // A full day at 3 h steps: the registration error of the old construction
  // rotated with the magnetic pole, so every roll phase gets sampled.
  ...Array.from({ length: 8 }, (_, i) =>
    new Date(`2026-08-09T${String(i * 3).padStart(2, "0")}:00:00Z`)),
  // Seasons: solstices and an equinox move the subsolar latitude ±23.4°.
  new Date("2026-12-21T09:00:00Z"),
  new Date("2026-06-21T03:30:00Z"),
  new Date("2026-03-20T15:00:00Z"),
];

const FRAMES: ReferenceFrame[] = ["earth-fixed", "inertial"];

/** GSM components of a scene-frame vector, per the frame quaternion. */
function gsmComponents(vector: THREE.Vector3, quaternion: THREE.Quaternion) {
  const local = vector.clone().applyQuaternion(quaternion.clone().invert());
  // gsmSceneAxes stores GSM (x, y, z) in local (x, z, −y).
  return { x: local.x, y: -local.z, z: local.y };
}

describe("the GSM frame quaternion", () => {
  it("points local +x at the Sun and stays a pure rotation", () => {
    for (const frame of FRAMES) {
      for (const time of TIMES) {
        const sun = sceneSunDirection(time, frame);
        const axis = sceneDipoleAxisDirection(time, frame);
        const quaternion = gsmFrameQuaternion(sun, axis);
        expect(quaternion.length()).toBeCloseTo(1, 10);
        const mappedX = gsmSceneAxes(1, 0, 0).applyQuaternion(quaternion);
        expect(mappedX.distanceTo(sun)).toBeLessThan(1e-10);
      }
    }
  });

  it("puts the dipole axis in the GSM x–z plane with +z north — the definition of GSM", () => {
    for (const frame of FRAMES) {
      for (const time of TIMES) {
        const sun = sceneSunDirection(time, frame);
        const axis = sceneDipoleAxisDirection(time, frame);
        const quaternion = gsmFrameQuaternion(sun, axis);
        const gsm = gsmComponents(axis, quaternion);
        expect(Math.abs(gsm.y)).toBeLessThan(1e-10);
        expect(gsm.z).toBeGreaterThan(0.8);
      }
    }
  });

  it("implies the same dipole tilt Hapgood gives the boundary models", () => {
    for (const time of TIMES) {
      const sun = sceneSunDirection(time, "earth-fixed");
      const axis = sceneDipoleAxisDirection(time, "earth-fixed");
      const quaternion = gsmFrameQuaternion(sun, axis);
      const gsm = gsmComponents(axis, quaternion);
      // Tilt is the angle of the axis off GSM +z toward the Sun: sin ψ = x_gsm.
      const impliedTiltDeg = (Math.asin(Math.max(-1, Math.min(1, gsm.x))) * 180) / Math.PI;
      const hapgood = dipoleTilt(time)!;
      // Two independent solar-position/sidereal formulations (Hapgood 1992 in
      // dipole-tilt.ts vs the globe's subsolar-point + satellite.js gstime);
      // they must agree to well under the drawn linewidth.
      expect(Math.abs(impliedTiltDeg - hapgood.degrees)).toBeLessThan(0.2);
    }
  });

  it("is frame-independent physics: the tilt matches across earth-fixed and inertial", () => {
    for (const time of TIMES) {
      const tilts = FRAMES.map((frame) => {
        const quaternion = gsmFrameQuaternion(
          sceneSunDirection(time, frame),
          sceneDipoleAxisDirection(time, frame),
        );
        return gsmComponents(sceneDipoleAxisDirection(time, frame), quaternion).x;
      });
      expect(Math.abs(tilts[0]! - tilts[1]!)).toBeLessThan(1e-9);
    }
  });

  it("rejects the old minimal-rotation construction: its roll error is real and time-varying", () => {
    // The proof that the new pin is non-vacuous: under the OLD quaternion the
    // dipole axis carries a substantial GSM-Y component for most of the day.
    const errors = TIMES.slice(0, 8).map((time) => {
      const sun = sceneSunDirection(time, "earth-fixed");
      const axis = sceneDipoleAxisDirection(time, "earth-fixed");
      const old = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(1, 0, 0), sun);
      return Math.abs(gsmComponents(axis, old).y);
    });
    expect(Math.max(...errors)).toBeGreaterThan(0.1);
  });
});
