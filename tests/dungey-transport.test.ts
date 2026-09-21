import { describe, expect, it } from "vitest";

import {
  AURORAL_FOOT_RADIUS_RE,
  INJECTION_MLT_HALF_SPAN_HOURS,
  LOBE_APPROACH_RUN_RE,
  MIDNIGHT_MLT_HOURS,
  RING_DRIFT_MLT_HOURS,
  RING_TARGET_L,
  RING_TRAPPED_MOTION,
  TAIL_X_LINE_RE,
  activeTracerCount,
  buildDungeyReturnLeg,
  containedInMagnetopause,
  couplingDrive,
  dipoleFootpointLatitudeDeg,
  dungeyTransportCopy,
  equatorialDirection,
  gsmFromDipoleFrame,
  mltHoursOf,
  trappedMotionForPath,
} from "../src/dungey-transport";
import type { DungeyReturnInput, GsmPointRe } from "../src/dungey-transport";
import { innerEdgeRe, sheetCentreZRe } from "../src/inner-plasma-sheet";
import { dipoleMirrorLatitudeRadians, dipoleRadiationPosition } from "../src/radiation-belt";
import { shueBoundary } from "../src/magnetopause";
import { newellCoupling } from "../src/storm-indices";

/**
 * The site's own published band ladder, copied from
 * `pipeline/storm_indices.py::NEWELL_CALIBRATION`. Copied rather than imported
 * because it arrives at runtime inside a published artifact; a test that
 * invents its own ladder would be grading the drive against a scale no reader
 * ever sees.
 */
const CALIBRATION = [
  { label: "very quiet", value: 0 },
  { label: "quiet", value: 4773 },
  { label: "moderate", value: 10123 },
  { label: "storm", value: 27421 },
  { label: "severe", value: 60036 },
  { label: "extreme", value: 153333 },
];

/**
 * The most COMPRESSED corner of the driver envelope this site has published:
 * 8.99 nPa with Bz -10.22 nT, taken through the site's own Shue implementation
 * so the standoff and the flaring parameter stay a physical pair. Exactly the
 * corner `tests/inner-plasma-sheet.test.ts` holds the wedge against, and for
 * the same reason: the southward Bz that pushes the nose in also flares the
 * flanks out, so pairing a compressed standoff with a quiet alpha would invent
 * a boundary that cannot occur.
 */
const COMPRESSED = shueBoundary(8.99, -10.22)!;

/**
 * Where the ride leaves the traced open line, in Re down-tail.
 *
 * SUNWARD of the neutral line by the length of the sheetward slide, which is
 * what `buildTailReturnPaths` trims to. A fixture that handed off AT the
 * neutral line would test a leg with no room to slide — which is the geometry
 * this module was changed to stop drawing.
 */
function handoffRe(dipoleTiltRad = 0): number {
  return TAIL_X_LINE_RE * Math.cos(dipoleTiltRad) - LOBE_APPROACH_RUN_RE;
}

/** The zero-tilt hand-off, for fixtures that do not vary the tilt. */
const HANDOFF_RE = handoffRe(0);

/**
 * Lobe entry points that stand in for where a traced open field line crosses
 * the hand-off distance. Both hemispheres, both flanks, and a lobe height
 * (8 Re off the sheet) at the high end of what the traced set produces.
 */
function entryPoints(): GsmPointRe[] {
  const points: GsmPointRe[] = [];
  for (const zSign of [1, -1]) {
    for (const y of [-9, -4, 0, 4, 9]) {
      for (const z of [3, 6, 8]) {
        points.push({ x: -HANDOFF_RE, y, z: zSign * z });
      }
    }
  }
  return points;
}

/** Angle between two directions, degrees. */
function angleDeg(a: GsmPointRe, b: GsmPointRe): number {
  const na = Math.hypot(a.x, a.y, a.z) || 1;
  const nb = Math.hypot(b.x, b.y, b.z) || 1;
  const dot = (a.x * b.x + a.y * b.y + a.z * b.z) / (na * nb);
  return (Math.acos(Math.max(-1, Math.min(1, dot))) * 180) / Math.PI;
}

/** Direction from one polyline vertex to the next. */
function stepDeg(points: readonly GsmPointRe[], index: number): number {
  const before = { x: points[index]!.x - points[index - 1]!.x, y: points[index]!.y - points[index - 1]!.y, z: points[index]!.z - points[index - 1]!.z };
  const after = { x: points[index + 1]!.x - points[index]!.x, y: points[index + 1]!.y - points[index]!.y, z: points[index + 1]!.z - points[index]!.z };
  return angleDeg(before, after);
}

function leg(overrides: Partial<DungeyReturnInput> = {}) {
  return buildDungeyReturnLeg({
    entryGsmRe: { x: -HANDOFF_RE, y: 3, z: 6 },
    // The traced lobe line's own direction of travel at the hand-off:
    // antisunward, converging on the sheet at about twelve degrees, which is
    // the middle of what the traced set actually produces.
    approachTangentGsmRe: { x: -1, y: 0, z: -0.21 },
    dipoleTiltRad: (20 * Math.PI) / 180,
    innerEdgeRe: 9,
    injectionMltOffsetHours: -2,
    hemisphere: "north",
    branch: "ring-current",
    driftSense: "westward",
    ...overrides,
  });
}

describe("the magnetic-local-time convention", () => {
  it("puts noon sunward, dusk at +y and midnight anti-sunward", () => {
    expect(equatorialDirection(12).x).toBeCloseTo(1, 10);
    expect(equatorialDirection(18).y).toBeCloseTo(1, 10);
    expect(equatorialDirection(MIDNIGHT_MLT_HOURS).x).toBeCloseTo(-1, 10);
    expect(equatorialDirection(6).y).toBeCloseTo(-1, 10);
    expect(mltHoursOf(0, 1)).toBeCloseTo(18, 10);
  });

  /**
   * Midnight is carried as 24, not 0. A stream ending at 04 MLT has to
   * interpolate two hours across the seam, and the version of this that used 0
   * sent it twenty-two hours the other way — round the dayside, outside the
   * magnetopause, which is precisely the defect the inner plasma sheet already
   * shipped once.
   */
  it("keeps a dawnward stream on the nightside rather than sending it the long way round", () => {
    const path = leg({ injectionMltOffsetHours: 4 });
    for (const point of path.pointsGsmRe) {
      expect(point.x).toBeLessThan(1);
    }
  });
});

describe("the dipole frame", () => {
  it("agrees with the plasma sheet layer's own hinged centre plane", () => {
    const psi = (20 * Math.PI) / 180;
    // Inside the hinge the tilted magnetic equator and the drawn sheet centre
    // are the same surface, so the two independent constructions must agree.
    for (const shell of [4, 6, 8, 9.5]) {
      const point = gsmFromDipoleFrame(-shell, 0, 0, psi);
      expect(point.z).toBeCloseTo(sheetCentreZRe(point.x, psi), 6);
    }
  });

  it("places the auroral footpoint from the dipole and nothing else", () => {
    expect(dipoleFootpointLatitudeDeg(6.6)).toBeCloseTo(66.9, 1);
    expect(dipoleFootpointLatitudeDeg(9)).toBeCloseTo(70.3, 1);
    expect(dipoleFootpointLatitudeDeg(11)).toBeCloseTo(72.3, 1);
    // The whole range the inner edge can take lands inside the auroral zone,
    // which is a check on the construction rather than a chosen number.
    for (const shell of [6.6, 9, 11]) {
      const latitude = dipoleFootpointLatitudeDeg(shell)!;
      expect(latitude).toBeGreaterThan(64);
      expect(latitude).toBeLessThan(75);
    }
    expect(dipoleFootpointLatitudeDeg(1)).toBeNull();
  });

  /**
   * The direction that carries the teaching, asserted rather than assumed: a
   * loaded tail brings the inner edge of the plasma sheet EARTHWARD, and a
   * dipole line from a smaller L reaches the atmosphere at a LOWER latitude.
   * So the drawn oval widens equatorward as the tail loads, which is what the
   * measured one does. Nothing in this file chooses that; it falls out of
   * `innerEdgeRe` and `arccos(sqrt(1/L))`.
   */
  it("widens the drawn oval equatorward as the tail loads", () => {
    const quiet = dipoleFootpointLatitudeDeg(innerEdgeRe({ loading: 0, injection: 0 }))!;
    const loaded = dipoleFootpointLatitudeDeg(innerEdgeRe({ loading: 1, injection: 0 }))!;
    const injecting = dipoleFootpointLatitudeDeg(innerEdgeRe({ loading: 1, injection: 1 }))!;
    expect(loaded).toBeLessThan(quiet);
    expect(injecting).toBeLessThan(loaded);
    expect(quiet - injecting).toBeGreaterThan(3);
  });
});

describe("the drawn legs", () => {
  it("runs entry, reconnection, injection and branch in that order", () => {
    const path = leg();
    expect(path.reconnectionIndex).toBe(0);
    expect(path.injectionIndex).toBeGreaterThan(path.reconnectionIndex);
    expect(path.branchIndex).toBeGreaterThan(path.injectionIndex);
    expect(path.pointsGsmRe.length).toBeGreaterThan(path.branchIndex);
  });

  it("has no seam between legs", () => {
    for (const branch of ["ring-current", "aurora"] as const) {
      const path = leg({ branch });
      let worst = 0;
      for (let index = 1; index < path.pointsGsmRe.length; index += 1) {
        const a = path.pointsGsmRe[index - 1]!;
        const b = path.pointsGsmRe[index]!;
        worst = Math.max(worst, Math.hypot(b.x - a.x, b.y - a.y, b.z - a.z));
      }
      // A visible step would read as the particle teleporting between legs.
      expect(worst).toBeLessThan(2.5);
    }
  });

  it("travels earthward once it is on the sheet", () => {
    const path = leg();
    const sheet = path.pointsGsmRe.slice(path.injectionIndex, path.branchIndex);
    for (let index = 1; index < sheet.length; index += 1) {
      const before = Math.hypot(sheet[index - 1]!.x, sheet[index - 1]!.y, sheet[index - 1]!.z);
      const after = Math.hypot(sheet[index]!.x, sheet[index]!.y, sheet[index]!.z);
      expect(after).toBeLessThanOrEqual(before + 1e-9);
    }
  });

  /**
   * ## The defect this leg was rebuilt to remove
   *
   * Sean, watching the live site: *"some solar wind particles travel along the
   * magnetic field lines to the plasma sheet and then turn 90 degrees into the
   * plane of the plasma sheet. Is that real physics? Is that what truly
   * happens?"* It was not, and it was not a viewing artifact either: measured
   * in physical GSM over the whole traced line set, the corner where the lobe
   * ride met the collapse was 77 to 102 degrees, and at zero dipole tilt the
   * collapse was an exactly vertical drop followed by an exactly 90-degree
   * turn onto the sheet.
   *
   * A path that pivots through a right angle teaches that a charged particle
   * can cross field lines, which is the opposite of what `trapped-motion`
   * spends seventy seconds establishing. So the leg now does two things
   * instead: it SLIDES onto the sheet over the last `LOBE_APPROACH_RUN_RE`,
   * which is the flux tube's sheetward convection drift and is a real
   * cross-field motion; and the sharp change of direction is left at the one
   * vertex where the field line is cut and re-joined, where it is a REVERSAL
   * rather than a corner.
   *
   * These three tests are the negative control on ever drawing that corner
   * again. They are stated as angles because an angle is the thing a reader
   * actually sees, and because the failure they guard against is a geometry
   * that still passes every containment and ordering check.
   */
  it("has no right angle anywhere on the sheetward slide", () => {
    let worst = 0;
    for (const entry of entryPoints()) {
      for (const tiltDeg of [-30, -15, 0, 15, 30]) {
        const path = leg({
          entryGsmRe: entry,
          hemisphere: entry.z >= 0 ? "north" : "south",
          dipoleTiltRad: (tiltDeg * Math.PI) / 180,
          approachTangentGsmRe: { x: -1, y: 0, z: entry.z >= 0 ? -0.21 : 0.21 },
        });
        for (let index = path.reconnectionIndex + 1; index < path.neutralLineIndex; index += 1) {
          worst = Math.max(worst, stepDeg(path.pointsGsmRe, index));
        }
      }
    }
    // The slide is a curve, and a curve is allowed to bend; what it may not do
    // is corner. Anything approaching a right angle here is the old geometry
    // back again.
    expect(worst).toBeLessThan(30);
  });

  it("reverses at the neutral line rather than turning across the field", () => {
    let sharpest = 180;
    for (const entry of entryPoints()) {
      for (const tiltDeg of [-30, -15, 0, 15, 30]) {
        const path = leg({
          entryGsmRe: entry,
          hemisphere: entry.z >= 0 ? "north" : "south",
          dipoleTiltRad: (tiltDeg * Math.PI) / 180,
          approachTangentGsmRe: { x: -1, y: 0, z: entry.z >= 0 ? -0.21 : 0.21 },
        });
        const vertex = path.neutralLineIndex;
        const arriving = path.pointsGsmRe[vertex]!;
        const before = path.pointsGsmRe[Math.max(0, vertex - 3)]!;
        const after = path.pointsGsmRe[Math.min(path.pointsGsmRe.length - 1, vertex + 3)]!;
        sharpest = Math.min(sharpest, angleDeg(
          { x: arriving.x - before.x, y: arriving.y - before.y, z: arriving.z - before.z },
          { x: after.x - arriving.x, y: after.y - arriving.y, z: after.z - arriving.z },
        ));
      }
    }
    // Greater than a right angle in every state: the two legs meet head on,
    // which is what happens when the FIELD is re-cut, not when a particle
    // turns a corner. 90 degrees or less is the shipped defect returning.
    expect(sharpest).toBeGreaterThan(100);
  });

  it("leaves the traced line along the traced line", () => {
    // The tangent is the whole point: hand it the direction the drawn field
    // line is going and the slide sets off that way, so there is no corner
    // where traced geometry becomes schematic geometry.
    const tangent = { x: -1, y: 0, z: -0.21 };
    const path = leg({ dipoleTiltRad: 0, approachTangentGsmRe: tangent });
    const first = path.pointsGsmRe[1]!;
    const start = path.pointsGsmRe[0]!;
    // A chord over a finite first step is not the tangent, so this is a few
    // degrees rather than zero. What it rules out is the slide setting off
    // parallel to the sheet while the traced line arrives converging on it,
    // which is a 12-degree kink at the one place the reader is watching the
    // drawn line hand over to a drawn schematic.
    expect(angleDeg(tangent, { x: first.x - start.x, y: first.y - start.y, z: first.z - start.z }))
      .toBeLessThan(5);
    // And without one it still builds a path — worse, but never nothing.
    const untangented = leg({ dipoleTiltRad: 0, approachTangentGsmRe: null });
    expect(untangented.pointsGsmRe.length).toBe(path.pointsGsmRe.length);
  });

  it("slides onto the sheet instead of dropping onto it", () => {
    // The failure this catches is the original leg: nearly all of the height
    // lost in nearly none of the down-tail travel.
    for (const tiltDeg of [-30, 0, 30]) {
      const psi = (tiltDeg * Math.PI) / 180;
      // Six Earth radii above the SHEET, not above the GSM equator: a traced
      // lobe line hands off at a height measured from the sheet it is about to
      // slide onto, and at a 30-degree tilt the two differ by six more.
      const handoffX = -handoffRe(psi);
      const path = leg({
        dipoleTiltRad: psi,
        entryGsmRe: { x: handoffX, y: 3, z: sheetCentreZRe(handoffX, psi) + 6 },
        approachTangentGsmRe: { x: -1, y: 0, z: -0.21 },
      });
      const start = path.pointsGsmRe[path.reconnectionIndex]!;
      const vertex = path.pointsGsmRe[path.neutralLineIndex]!;
      const travelled = Math.abs(vertex.x - start.x);
      const dropped = Math.abs((vertex.z - sheetCentreZRe(vertex.x, psi)) - (start.z - sheetCentreZRe(start.x, psi)));
      // The slide runs the whole approach, so the antisunward travel is the
      // run itself rather than the ~0 the collapse used to have.
      expect(travelled).toBeGreaterThan(LOBE_APPROACH_RUN_RE * 0.9);
      // And it is a slide, not a fall: it descends less than it travels.
      expect(dropped).toBeLessThan(travelled * 1.6);
    }
  });

  it("arrives on the current sheet at the neutral line", () => {
    const psi = (20 * Math.PI) / 180;
    const path = leg({ dipoleTiltRad: psi });
    const arrival = path.pointsGsmRe[path.injectionIndex - 1]!;
    // Reconnection puts the particle on the sheet centre, wherever the dipole
    // tilt has carried that: 3.6 Re above the GSM equator at 20 degrees.
    expect(arrival.z).toBeCloseTo(sheetCentreZRe(arrival.x, psi), 3);
    expect(sheetCentreZRe(arrival.x, psi)).toBeGreaterThan(3);
  });

  /**
   * The charge split IS the ring current. Gradient and curvature drift carry
   * ions westward from midnight toward dusk and electrons eastward toward
   * dawn, which is why the partial ring current sits in the dusk sector. A
   * sign error here would not merely mirror the picture, it would teach the
   * opposite of the physics.
   */
  it("drifts ions toward dusk and electrons toward dawn", () => {
    // Asserted at the LOSS POINT rather than at the last vertex, because the
    // last vertex is no longer the end of the drift: the ion carries on as a
    // neutral atom in a straight line and the electron falls into the
    // atmosphere. The drift is the leg between the branch and the loss.
    const trapping = { equatorialPitchAngleDeg: 72, lossPhase: 1 };
    const ions = leg({ driftSense: "westward", dipoleTiltRad: 0, injectionMltOffsetHours: 0, trapping });
    const electrons = leg({ driftSense: "eastward", dipoleTiltRad: 0, injectionMltOffsetHours: 0, trapping });
    expect(ions.pointsGsmRe[ions.lossIndex!]!.y).toBeGreaterThan(2);
    expect(electrons.pointsGsmRe[electrons.lossIndex!]!.y).toBeLessThan(-2);
    for (const path of [ions, electrons]) {
      // A full-lossPhase path drifts the whole drawn arc, so it reaches the
      // target shell — but it is bouncing when it gets there, so the radius is
      // L cos^2(lambda) and not L. Checked against the shell it is on.
      const at = path.pointsGsmRe[path.lossIndex!]!;
      const radius = Math.hypot(at.x, at.y, at.z);
      const latitude = Math.asin(at.z / radius);
      expect(radius / Math.cos(latitude) ** 2).toBeCloseTo(RING_TARGET_L, 1);
    }
    expect(RING_DRIFT_MLT_HOURS).toBeGreaterThan(0);
  });

  /**
   * THE PART OF THE LIFECYCLE THAT WAS MISSING UNTIL 2026-08-27.
   *
   * Sean: *"for the ring current and radiation belts I thought there should be
   * some coupling to the particle."* Before this, the drawn path stopped in
   * the equatorial plane at L 4.5 and the tracer faded out with nothing said
   * about why. These pin the two things that replaced that fade.
   */
  it("bounces at the mirror latitude the radiation-belt layer computes", () => {
    for (const pitchDeg of RING_TRAPPED_MOTION.equatorialPitchAnglesDeg) {
      const path = leg({
        driftSense: "westward",
        dipoleTiltRad: 0,
        injectionMltOffsetHours: 0,
        trapping: { equatorialPitchAngleDeg: pitchDeg, lossPhase: 1 },
      });
      const expected = dipoleMirrorLatitudeRadians(Math.sin((pitchDeg * Math.PI) / 180));
      let deepest = 0;
      for (let index = path.branchIndex; index <= path.lossIndex!; index += 1) {
        const at = path.pointsGsmRe[index]!;
        const radius = Math.hypot(at.x, at.y, at.z);
        deepest = Math.max(deepest, Math.abs(Math.asin(at.z / radius)));
      }
      // The AMPLITUDE is not a display choice — it follows from the pitch
      // angle alone, and it is the belt layer's own inversion, not a second
      // one. Sampling misses the exact turning point by up to one step.
      expect(deepest).toBeGreaterThan(expected * 0.93);
      expect(deepest).toBeLessThanOrEqual(expected + 1e-9);
      expect(path.equatorialPitchAngleDeg).toBe(pitchDeg);
    }
    // A shallow pitch angle stays near the equator and a steep one swings deep.
    // If this ever inverts, the picture teaches the loss cone backwards.
    expect(dipoleMirrorLatitudeRadians(Math.sin((72 * Math.PI) / 180)))
      .toBeLessThan(dipoleMirrorLatitudeRadians(Math.sin((27 * Math.PI) / 180)));
  });

  it("draws the bounce on the same shell surface the belt layer maps flux onto", () => {
    // Not "a similar helix": the same arithmetic. `dipoleRadiationPosition` is
    // radiation-belt.ts's own placement, in its own local-time convention, and
    // a drawn trapped particle has to sit on it or the two layers are drawing
    // two different inner magnetospheres.
    const path = leg({
      driftSense: "westward",
      dipoleTiltRad: 0,
      injectionMltOffsetHours: 0,
      trapping: { equatorialPitchAngleDeg: 38, lossPhase: 1 },
    });
    let checked = 0;
    for (let index = path.branchIndex; index <= path.lossIndex!; index += 3) {
      const at = path.pointsGsmRe[index]!;
      const radius = Math.hypot(at.x, at.y, at.z);
      const latitude = Math.asin(at.z / radius);
      const shell = radius / Math.cos(latitude) ** 2;
      const belt = dipoleRadiationPosition(shell, mltHoursOf(at.x, at.y), latitude);
      expect(Math.hypot(belt.x - at.x, belt.y - at.y, belt.z - at.z)).toBeLessThan(1e-6);
      checked += 1;
    }
    expect(checked).toBeGreaterThan(20);
  });

  it("ends every trapped ion as a neutral flying straight, and every electron in the atmosphere", () => {
    for (let pathIndex = 0; pathIndex < 8; pathIndex += 1) {
      const trapping = trappedMotionForPath(pathIndex);
      const ion = leg({ driftSense: "westward", dipoleTiltRad: 0, injectionMltOffsetHours: 0, trapping });
      expect(ion.lossChannel).toBe("charge-exchange");
      expect(ion.neutralFromIndex).toBeGreaterThan(ion.lossIndex!);
      // CHARGE EXCHANGE: the field stops holding it, so the path stops
      // turning. Straightness IS the physics claim, so it is measured rather
      // than assumed — every escape segment parallel to the last bound one.
      const before = ion.pointsGsmRe[ion.lossIndex! - 1]!;
      const at = ion.pointsGsmRe[ion.lossIndex!]!;
      const tangent = [at.x - before.x, at.y - before.y, at.z - before.z];
      const span = Math.hypot(...tangent);
      for (let index = ion.neutralFromIndex!; index < ion.pointsGsmRe.length; index += 1) {
        const previous = ion.pointsGsmRe[index - 1]!;
        const point = ion.pointsGsmRe[index]!;
        const step = [point.x - previous.x, point.y - previous.y, point.z - previous.z];
        const stepSpan = Math.hypot(...step);
        const cosine = (step[0]! * tangent[0]! + step[1]! * tangent[1]! + step[2]! * tangent[2]!)
          / (stepSpan * span);
        expect(cosine).toBeCloseTo(1, 6);
      }
      // And it goes somewhere: a neutral that travelled no distance is a
      // charge exchange nobody can see.
      const tip = ion.pointsGsmRe.at(-1)!;
      expect(Math.hypot(tip.x - at.x, tip.y - at.y, tip.z - at.z))
        .toBeCloseTo(RING_TRAPPED_MOTION.neutralEscapeRe, 6);

      const electron = leg({ driftSense: "eastward", dipoleTiltRad: 0, injectionMltOffsetHours: 0, trapping });
      expect(electron.lossChannel).toBe("precipitation");
      expect(electron.neutralFromIndex).toBeNull();
      const end = electron.pointsGsmRe.at(-1)!;
      expect(Math.hypot(end.x, end.y, end.z)).toBeCloseTo(AURORAL_FOOT_RADIUS_RE, 3);
      // PRECIPITATION lands where the shell it was drifting on lands, and
      // nowhere else: arccos(sqrt(1/L)) and nothing chosen.
      const at2 = electron.pointsGsmRe[electron.lossIndex!]!;
      const radius = Math.hypot(at2.x, at2.y, at2.z);
      const shell = radius / Math.cos(Math.asin(at2.z / radius)) ** 2;
      expect(electron.footpointLatitudeDeg).toBeCloseTo(dipoleFootpointLatitudeDeg(shell)!, 6);
      // Eastward drift puts it on the DAWN side, which is where the diffuse
      // aurora is observed. That is a check on the construction, not a choice.
      expect(at2.y).toBeLessThan(0);
      expect(end.y).toBeLessThan(0);
    }
  });

  it("keeps the drawn bounce rate declared, not merely chosen", () => {
    // The one number changed from nature on this path. If the drawn count is
    // ever raised toward the real one the picture becomes a smear, and if the
    // real count is ever edited to flatter the drawn one the declaration on
    // the card becomes false. Both directions go red here.
    const ratio = RING_TRAPPED_MOTION.realBouncesPerDrawnArc / RING_TRAPPED_MOTION.drawnBouncesPerDrawnArc;
    expect(ratio).toBeGreaterThan(12);
    expect(ratio).toBeLessThan(18);
    expect(dungeyTransportCopy.trapped).toContain("87");
    expect(dungeyTransportCopy.trapped).toContain("fifteen times slower");
    // No pitch angle drawn may sit inside the loss cone: a particle drawn
    // inside it was never trapped, and the whole leg would be a lie.
    for (const pitchDeg of RING_TRAPPED_MOTION.equatorialPitchAnglesDeg) {
      expect(pitchDeg).toBeGreaterThan(10);
      expect(pitchDeg).toBeLessThan(90);
    }
    // Losses concentrate at the deep end of the drift, where the geocorona is
    // thicker. Every declared phase is past halfway for that reason.
    for (const phase of RING_TRAPPED_MOTION.lossPhases) {
      expect(phase).toBeGreaterThan(0.5);
      expect(phase).toBeLessThanOrEqual(1);
    }
    expect(new Set(RING_TRAPPED_MOTION.lossPhases).size).toBeGreaterThan(2);
  });

  it("ends the precipitating branch at the top of the atmosphere", () => {
    const path = leg({ branch: "aurora", innerEdgeRe: 9 });
    const end = path.pointsGsmRe.at(-1)!;
    expect(Math.hypot(end.x, end.y, end.z)).toBeCloseTo(AURORAL_FOOT_RADIUS_RE, 3);
    expect(path.footpointLatitudeDeg).toBeCloseTo(70.3, 1);
    // North seed falls into the northern hemisphere, in the dipole frame.
    const south = leg({ branch: "aurora", hemisphere: "south", dipoleTiltRad: 0 });
    expect(path.pointsGsmRe.at(-1)!.z).toBeGreaterThan(0);
    expect(south.pointsGsmRe.at(-1)!.z).toBeLessThan(0);
  });

  it("keeps the injected stream inside the sector the plasma sheet layer draws", () => {
    for (const offset of [-8, -4, 0, 4, 8]) {
      const path = leg({ injectionMltOffsetHours: offset, dipoleTiltRad: 0 });
      const arrival = path.pointsGsmRe[path.branchIndex - 1]!;
      const hours = mltHoursOf(arrival.x, arrival.y);
      const fromMidnight = Math.abs(((hours + 12) % 24) - 12);
      expect(fromMidnight).toBeLessThanOrEqual(INJECTION_MLT_HALF_SPAN_HOURS + 0.01);
    }
  });
});

/**
 * THE CHECK THE INNER PLASMA SHEET HAD TO SHIP TWICE TO LEARN.
 *
 * That layer went out spanning eight hours of local time either side of
 * midnight, which put its far corner 60 degrees from the Sun-Earth line on the
 * dayside, drawn to 14 Re, where Shue puts the boundary at 9.2-13.1 Re for
 * this site's whole measured driver envelope. It was drawing plasma sheet in
 * the magnetosheath. A particle path is the same defect wearing different
 * clothes and a reader would spot it instantly, so every vertex of every leg
 * this module can produce is checked against the most compressed boundary the
 * published record has produced.
 */
describe("containment inside the magnetopause", () => {
  it("holds every leg inside a compressed Shue boundary, in every branch", () => {
    let worst = 0;
    for (const entry of entryPoints()) {
      for (const tiltDeg of [-30, -20, 0, 20, 30]) {
        for (const loading of [0, 0.5, 1]) {
          for (const injection of [0, 1]) {
            const inner = innerEdgeRe({ loading, injection });
            for (const branch of ["ring-current", "aurora"] as const) {
              for (const driftSense of ["westward", "eastward"] as const) {
                for (const offset of [-4, 0, 4]) {
                  const path = buildDungeyReturnLeg({
                    entryGsmRe: entry,
                    dipoleTiltRad: (tiltDeg * Math.PI) / 180,
                    innerEdgeRe: inner,
                    injectionMltOffsetHours: offset,
                    hemisphere: entry.z >= 0 ? "north" : "south",
                    branch,
                    driftSense,
                  });
                  // The charged part of the path, which is all of it up to a
                  // charge exchange. A NEUTRAL atom is not confined by the
                  // magnetopause — it flies straight out through it, which is
                  // exactly why IMAGE and TWINS could photograph the ring
                  // current from outside the boundary. Checking the escape ray
                  // here would refuse a correct path for being correct, and
                  // `buildTailReturnPaths` slices at the same index for the
                  // same reason.
                  const charged = path.neutralFromIndex === null
                    ? path.pointsGsmRe
                    : path.pointsGsmRe.slice(0, path.neutralFromIndex);
                  const check = containedInMagnetopause(
                    charged,
                    COMPRESSED.subsolarStandoffRe,
                    COMPRESSED.flaringAlpha,
                  );
                  worst = Math.max(worst, check.worstFraction);
                  expect(check.contained).toBe(true);
                }
              }
            }
          }
        }
      }
    }
    // Recorded so a later change that pushes the X-line out, widens the
    // injection sector or lets the drift wander sunward goes red before a
    // reader ever sees it.
    expect(worst).toBeLessThan(0.9);
    expect(worst).toBeGreaterThan(0.2);
  });

  /**
   * The negative control. Without one, a containment test that can never fail
   * is a test that proves nothing — the elimination-is-not-proof rule.
   */
  it("refuses a path that reaches outside the boundary", () => {
    const bogus = buildDungeyReturnLeg({
      entryGsmRe: { x: -HANDOFF_RE, y: 0, z: 6 },
      dipoleTiltRad: 0,
      // An "inner edge" out at 30 Re on the dusk flank is exactly the shape of
      // the shipped defect: a nightside structure reaching round to where the
      // boundary is only 18 Re away.
      innerEdgeRe: 30,
      injectionMltOffsetHours: -4,
      hemisphere: "north",
      branch: "ring-current",
      driftSense: "westward",
    });
    const check = containedInMagnetopause(
      bogus.pointsGsmRe,
      COMPRESSED.subsolarStandoffRe,
      COMPRESSED.flaringAlpha,
    );
    expect(check.contained).toBe(false);
    expect(check.worstFraction).toBeGreaterThan(1);
  });
});

describe("the measured driver", () => {
  it("is the published Newell coupling, placed on the published band ladder", () => {
    expect(couplingDrive(null, CALIBRATION)).toBeNull();
    expect(couplingDrive(Number.NaN, CALIBRATION)).toBeNull();
    // No ladder means no scale, and inventing one would grade the drive
    // against something no reader ever sees.
    expect(couplingDrive(10123, [])).toBeNull();
    expect(couplingDrive(0, CALIBRATION)).toBe(0);
    expect(couplingDrive(4773, CALIBRATION)).toBeCloseTo(0.2, 6);
    expect(couplingDrive(27421, CALIBRATION)).toBeCloseTo(0.6, 6);
    expect(couplingDrive(153333, CALIBRATION)).toBe(1);
    expect(couplingDrive(1e9, CALIBRATION)).toBe(1);
  });

  it("is monotonic in the coupling", () => {
    let previous = -1;
    for (let value = 0; value < 200000; value += 977) {
      const drive = couplingDrive(value, CALIBRATION)!;
      expect(drive).toBeGreaterThanOrEqual(previous);
      previous = drive;
    }
  });

  /**
   * The teaching moment, stated as an assertion: the same wind speed with the
   * IMF turned north opens almost no flux, so almost nothing is transported.
   * The numbers here are the measured drivers' own — nothing is scaled by
   * hand.
   */
  it("empties the transport path when the IMF turns northward", () => {
    const southward = newellCoupling(600, 3, -12);
    const northward = newellCoupling(600, 3, 12);
    expect(southward).not.toBeNull();
    expect(northward).not.toBeNull();
    expect(southward!).toBeGreaterThan(northward! * 20);

    const driven = couplingDrive(southward, CALIBRATION)!;
    const quiet = couplingDrive(northward, CALIBRATION)!;
    expect(driven).toBeGreaterThan(0.5);
    expect(quiet).toBeLessThan(0.1);

    expect(activeTracerCount(60, driven)).toBeGreaterThan(activeTracerCount(60, quiet) * 3);
    // Sparse, not absent: an empty path with a card saying the switch is off
    // teaches; a path that vanishes reads as a rendering fault.
    expect(activeTracerCount(60, quiet)).toBeGreaterThanOrEqual(1);
    // No drivers is a different state from a quiet one, and it draws nothing.
    expect(activeTracerCount(60, null)).toBe(0);
  });
});

describe("what the reader is told", () => {
  it("names both evidence classes and the citation", () => {
    expect(dungeyTransportCopy.evidence).toContain("MEASURED");
    expect(dungeyTransportCopy.evidence).toContain("SCHEMATIC");
    expect(dungeyTransportCopy.evidence).toContain("Newell");
    expect(dungeyTransportCopy.evidence).toContain("2007");
    expect(dungeyTransportCopy.evidence).toContain("nobody measures these");
  });

  /**
   * Every absence gets its own words, and none of them borrows another's.
   *
   * The state this file used to word — no propagated wind at all — is NOT here
   * on purpose. The solar-wind layer already goes dark for it and its own
   * coverage notice replaces this whole note, measured on the live page by
   * scrubbing to +72 h. A sentence for it would have been unreachable text
   * dressed as a safeguard, which is the shape of half the defects this
   * project has had to find twice.
   */
  it("says why there is nothing to see, in the states a reader can actually reach", () => {
    expect(dungeyTransportCopy.noCoupling).toContain("no coupling number");
    expect(dungeyTransportCopy.noCoupling).toContain("nothing is drawn");
    expect(dungeyTransportCopy.noCoupling).toContain("rather than by a loop");
    expect(dungeyTransportCopy.notDrawn).toContain("not drawn for this instant");
    expect(dungeyTransportCopy.notDrawn).toContain("rather than something invented");
    // CORRECTNESS FIX 2026-09-04: this pinned the wrong claim. The containment
    // check refuses at 0.9 of the local boundary radius, so a refused path was
    // still INSIDE the magnetopause; the copy said it had left. Pin what the
    // check actually does, so the sentence cannot drift back.
    expect(dungeyTransportCopy.refused).toContain("within a tenth of the Shue magnetopause");
    expect(dungeyTransportCopy.refused).toContain("held well inside the boundary");
    // The three refusals must not be the same sentence wearing three labels.
    const wordings = new Set([
      dungeyTransportCopy.noCoupling,
      dungeyTransportCopy.notDrawn,
      dungeyTransportCopy.refused,
    ]);
    expect(wordings.size).toBe(3);
  });

  it("explains the charge split rather than leaving it decorative", () => {
    expect(dungeyTransportCopy.transport).toContain("ions west toward dusk");
    expect(dungeyTransportCopy.transport).toContain("electrons east toward dawn");
    // The formula printed must be the one `dipoleFootpointLatitudeDeg` runs,
    // which maps to AURORAL_FOOT_RADIUS_RE and not to the surface.
    expect(dungeyTransportCopy.aurora).toContain("arccos(sqrt(1.02/L))");
  });

  /**
   * Sean: *"the movement of the particles is dictated by what kind of
   * particle ... with their ultimate destinations based on what they are."*
   * It is — from the inner edge on. What is pinned here is that the copy says
   * where that claim STARTS and where it stops, because the honest answer for
   * the two positive species is that this site draws no difference between
   * them and says so rather than inventing one.
   */
  /**
   * Sean: *"should there be any coupling of the radiation belts to the solar
   * wind? I can't remember if those are fed by the solar wind but I think
   * so."* They are, indirectly, and there is still no flow to draw. What is
   * pinned here is that the answer is given rather than dodged, and that it
   * names the mechanism that makes it undrawable.
   */
  it("answers the radiation-belt question in physics, without drawing a flow", () => {
    expect(dungeyTransportCopy.radiationBelts).toContain("seed");
    expect(dungeyTransportCopy.radiationBelts).toContain("chorus");
    expect(dungeyTransportCopy.radiationBelts).toContain("IN PLACE");
    expect(dungeyTransportCopy.radiationBelts).toContain("cosmic-ray albedo neutron decay");
    expect(dungeyTransportCopy.radiationBelts).toContain("None does");
    // It must not promise a drawn path anywhere.
    expect(dungeyTransportCopy.radiationBelts).toContain("No line is drawn");
  });

  it("says how far the species distinction goes, including where it stops", () => {
    expect(dungeyTransportCopy.species).toContain("H⁺");
    expect(dungeyTransportCopy.species).toContain("He²⁺");
    // Upstream there is nothing to separate, and the copy must not imply there is.
    expect(dungeyTransportCopy.species).toContain("one magnetised fluid");
    expect(dungeyTransportCopy.species).toContain("no difference is drawn between them");
    expect(dungeyTransportCopy.species).toContain("energy per charge");
    // The feeding of the sheet is now drawn, so the words have to name it.
    // The card must say WHICH of the two changed direction, because the
    // picture changes direction and mechanism clip 04 tells the reader that
    // circling a field line never carries a particle to another one.
    expect(dungeyTransportCopy.turn).toContain("THE FIELD, NOT THE PARTICLE");
    expect(dungeyTransportCopy.turn).toContain("cut");
    expect(dungeyTransportCopy.turn).toContain("re-joined");
    expect(dungeyTransportCopy.turn).toContain("reverses");
    // And it must name the one cross-field motion it DOES draw on this leg,
    // rather than leaving the lean-in looking like a particle bending.
    expect(dungeyTransportCopy.turn).toContain("drift ACROSS the field");
    expect(dungeyTransportCopy.transport).toContain("from above and from below");
    expect(dungeyTransportCopy.transport).toContain("plasma sheet being fed");
  });
});
