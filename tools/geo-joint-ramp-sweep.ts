/**
 * Prices the geostationary joint's C1 ramp: how much of the corner it removes
 * from a real eccentric orbit line, what it costs the outer scene, and whether
 * the magnetopause's drawn flaring survives it.
 *
 * Run: npx vite-node tools/geo-joint-ramp-sweep.ts
 */
import * as THREE from "three";

import { geoToSceneVector } from "../src/globe";
import { propagateOmmInFrozenEarthFrame } from "../src/orbit";
import { adaptiveOrbitPath, orbitPathTolerance } from "../src/orbit-polyline";
import { RULER_EARTH_RADIUS_KM } from "../src/radial-ruler";
import { shueBoundary, shueRadiusRe } from "../src/magnetopause";
import type { OmmRecord } from "../src/types";
import { ANCHOR, AT, OMMS, apogeeKm, drawn, periodMinutes } from "./geo-joint-ruler-model";

/** Worst vertex turn at the joint, and worst anywhere else, on the drawn line. */
function measureOrbit(omm: OmmRecord, rampEndRe: number) {
  const position = (s: { latitudeDeg: number; longitudeDeg: number; altitudeKm: number }) =>
    geoToSceneVector(s.latitudeDeg, s.longitudeDeg, drawn(1 + Math.max(0, s.altitudeKm) / RULER_EARTH_RADIUS_KM, rampEndRe));
  const reach = drawn(1 + Math.max(0, apogeeKm(omm)) / RULER_EARTH_RADIUS_KM, rampEndRe);
  const path = adaptiveOrbitPath({
    centre: AT,
    spanMinutes: periodMinutes(omm),
    sampleAt: (t: Date) => propagateOmmInFrozenEarthFrame(omm, t, AT, undefined),
    drawnPosition: position,
    toleranceSceneUnits: orbitPathTolerance(reach),
  });
  const vertices = path.map(position);
  const radii = path.map((s) => 1 + Math.max(0, s.altitudeKm) / RULER_EARTH_RADIUS_KM);
  let inBand = 0;
  let outside = 0;
  const bandLow = ANCHOR - 0.35;
  const bandHigh = Math.max(rampEndRe, ANCHOR) + 0.35;
  for (let i = 1; i + 1 < vertices.length; i += 1) {
    const back = vertices[i]!.clone().sub(vertices[i - 1]!);
    const forward = vertices[i + 1]!.clone().sub(vertices[i]!);
    if (back.length() < 1e-9 || forward.length() < 1e-9) continue;
    const cos = Math.max(-1, Math.min(1, back.normalize().dot(forward.normalize())));
    const turn = (Math.acos(cos) * 180) / Math.PI;
    const r = radii[i]!;
    if (r >= bandLow && r <= bandHigh) inBand = Math.max(inBand, turn);
    else outside = Math.max(outside, turn);
  }
  return { joint: inBand, elsewhere: outside, vertices: vertices.length };
}

const RAMPS = [ANCHOR, 6.8, 6.9, 7.0, 7.1, 7.2, 7.3, 7.35, 7.5, 8.0, 9.0];

console.log("== joint turn (deg) by ramp end ==");
const header = ["ramp"].concat(Object.keys(OMMS)).join("\t");
console.log(header);
for (const ramp of RAMPS) {
  const row = [ramp === ANCHOR ? "step" : ramp.toFixed(2)];
  for (const name of Object.keys(OMMS)) {
    const m = measureOrbit(OMMS[name]!, ramp);
    row.push(`${m.joint.toFixed(1)} (${m.elsewhere.toFixed(1)})`);
  }
  console.log(row.join("\t"));
}

console.log("\n== outer-scene cost ==");
console.log("ramp\tshift@7.35\tshift@9\tshift@13\tshift@56(tail)\tdrawn@7.35\tframeDist");
for (const ramp of RAMPS) {
  const shift = (r: number) => (drawn(r, ramp) / drawn(r, ANCHOR) - 1) * 100;
  const tail = drawn(56, ramp);
  console.log([
    ramp === ANCHOR ? "step" : ramp.toFixed(2),
    shift(7.35).toFixed(2) + "%",
    shift(9).toFixed(2) + "%",
    shift(13).toFixed(2) + "%",
    shift(56).toFixed(2) + "%",
    drawn(7.35, ramp).toFixed(1),
    (2.87 * Math.max(tail, drawn(65, ramp))).toFixed(0),
  ].join("\t"));
}

console.log("\n== magnetopause flaring, drawn vs physical (nose -> terminator) ==");
const DRIVERS: Array<[string, number, number]> = [
  ["site min standoff (measured 7.352)", 8.1674, -8.62],
  ["site median (9.51)", 1.7, -1.0],
  ["doc moderate storm", 4.1, -14.5],
  ["quiet (test QUIET)", 0.92, 1.5],
  ["severe (test STORM)", 20, -40],
  ["Pd 6 Bz -10", 6, -10],
  ["Pd 8 Bz -15", 8, -15],
  ["Pd 10 Bz -20", 10, -20],
];
console.log("driver\tr0\tflank\tphysRatio\t" + RAMPS.map((r) => (r === ANCHOR ? "step" : r.toFixed(2))).join("\t"));
for (const [label, pd, bz] of DRIVERS) {
  const b = shueBoundary(pd, bz)!;
  const flank = shueRadiusRe(Math.PI / 2, b.subsolarStandoffRe, b.flaringAlpha);
  const phys = flank / b.subsolarStandoffRe;
  const cells = RAMPS.map((ramp) => {
    const dr = drawn(flank, ramp) / drawn(b.subsolarStandoffRe, ramp);
    return dr.toFixed(4) + (Math.abs(dr - phys) < 1e-9 ? "*" : ` (${((dr / phys - 1) * 100).toFixed(2)}%)`);
  });
  console.log([label, b.subsolarStandoffRe.toFixed(3), flank.toFixed(2), phys.toFixed(4)].concat(cells).join("\t"));
}
