/** Drawn curvature of the orbit line at the geostationary joint, by ramp width. */
import * as THREE from "three";
import { EARTH_SCENE_RADIUS, geoToSceneVector } from "../src/globe";
import { propagateOmmInFrozenEarthFrame } from "../src/orbit";
import { adaptiveOrbitPath, orbitPathTolerance } from "../src/orbit-polyline";
import { RULER_EARTH_RADIUS_KM } from "../src/radial-ruler";
import type { OmmRecord } from "../src/types";
import { ANCHOR, drawn, OMMS, periodMinutes, apogeeKm, AT } from "./geo-joint-ruler-model";

const RAMPS = [ANCHOR, 6.9, 7.0, 7.1, 7.2, 7.35, 7.5, 8.0, 9.0, 11.0];

function densePath(omm: OmmRecord, ramp: number, samples: number) {
  const span = periodMinutes(omm) * 60000;
  const pts: Array<{ v: THREE.Vector3; r: number }> = [];
  for (let i = 0; i <= samples; i += 1) {
    const t = new Date(AT.getTime() - span / 2 + (i / samples) * span);
    const s = propagateOmmInFrozenEarthFrame(omm, t, AT, undefined);
    if (!s) continue;
    const r = 1 + Math.max(0, s.altitudeKm) / RULER_EARTH_RADIUS_KM;
    pts.push({ v: geoToSceneVector(s.latitudeDeg, s.longitudeDeg, drawn(r, ramp)), r });
  }
  return pts;
}

/** Max drawn curvature inside the joint band, and the tightest bend anywhere else. */
function curvature(omm: OmmRecord, ramp: number, samples = 60000) {
  const pts = densePath(omm, ramp, samples);
  const low = ANCHOR - 0.5;
  const high = Math.max(ramp, ANCHOR) + 0.5;
  let inBand = 0;
  let outside = 0;
  for (let i = 1; i + 1 < pts.length; i += 1) {
    const back = pts[i]!.v.clone().sub(pts[i - 1]!.v);
    const fwd = pts[i + 1]!.v.clone().sub(pts[i]!.v);
    const len = (back.length() + fwd.length()) / 2;
    if (len < 1e-9) continue;
    const cos = Math.max(-1, Math.min(1, back.clone().normalize().dot(fwd.clone().normalize())));
    const k = Math.acos(cos) / len;
    const r = pts[i]!.r;
    if (r >= low && r <= high) inBand = Math.max(inBand, k);
    else outside = Math.max(outside, k);
  }
  return { jointRadius: 1 / inBand, tightestElsewhere: 1 / outside };
}

/** Worst in-band vertex turn as the sampler is refined below the shipped tolerance. */
function turnAtTolerance(omm: OmmRecord, ramp: number, divisor: number) {
  const position = (s: { latitudeDeg: number; longitudeDeg: number; altitudeKm: number }) =>
    geoToSceneVector(s.latitudeDeg, s.longitudeDeg, drawn(1 + Math.max(0, s.altitudeKm) / RULER_EARTH_RADIUS_KM, ramp));
  const reach = drawn(1 + Math.max(0, apogeeKm(omm)) / RULER_EARTH_RADIUS_KM, ramp);
  const path = adaptiveOrbitPath({
    centre: AT,
    spanMinutes: periodMinutes(omm),
    sampleAt: (t: Date) => propagateOmmInFrozenEarthFrame(omm, t, AT, undefined),
    drawnPosition: position,
    toleranceSceneUnits: orbitPathTolerance(reach) / divisor,
    maxVertices: 20000,
  });
  const v = path.map(position);
  const radii = path.map((s) => 1 + Math.max(0, s.altitudeKm) / RULER_EARTH_RADIUS_KM);
  const low = ANCHOR - 0.5;
  const high = Math.max(ramp, ANCHOR) + 0.5;
  let worst = 0;
  for (let i = 1; i + 1 < v.length; i += 1) {
    if (!(radii[i]! >= low && radii[i]! <= high)) continue;
    const back = v[i]!.clone().sub(v[i - 1]!);
    const fwd = v[i + 1]!.clone().sub(v[i]!);
    if (back.length() < 1e-9 || fwd.length() < 1e-9) continue;
    const cos = Math.max(-1, Math.min(1, back.normalize().dot(fwd.normalize())));
    worst = Math.max(worst, (Math.acos(cos) * 180) / Math.PI);
  }
  return { worst, vertices: v.length };
}

const NAMES = ["MERIDIAN 9", "THEMIS A", "CLUSTER II-FM7", "XMM"];

console.log("== drawn radius of curvature at the joint (scene units; bigger = gentler) ==");
console.log("ramp\t" + NAMES.map((n) => n + " joint / tightest elsewhere").join("\t"));
for (const ramp of RAMPS) {
  const row = [ramp === ANCHOR ? "step" : ramp.toFixed(2)];
  for (const n of NAMES) {
    const c = curvature(OMMS[n]!, ramp);
    row.push(`${c.jointRadius.toFixed(1)} / ${c.tightestElsewhere.toFixed(1)}`);
  }
  console.log(row.join("\t"));
}

console.log("\n== worst in-band vertex turn as the sampler refines (deg, vertices) ==");
console.log("ramp\tobject\ttol\ttol/4\ttol/16\ttol/64");
for (const ramp of RAMPS) {
  for (const n of NAMES) {
    const cells = [1, 4, 16, 64].map((d) => {
      const r = turnAtTolerance(OMMS[n]!, ramp, d);
      return `${r.worst.toFixed(1)} (${r.vertices})`;
    });
    console.log([ramp === ANCHOR ? "step" : ramp.toFixed(2), n].concat(cells).join("\t"));
  }
}
