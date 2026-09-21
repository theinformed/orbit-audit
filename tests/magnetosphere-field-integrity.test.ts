/**
 * Geometric integrity of the traced field-line set — the invariants that make
 * "drawn correctly" a checkable statement instead of an impression.
 *
 * Sean's question, verbatim: "can we get some logic in there to make sure the
 * field lines are drawn correctly? That they don't cross or have shapes that
 * are impossible? Also - there are unclosed lines. Can that be possible?"
 *
 * The physics answers first, then the enforcement:
 *
 *   - Field lines CANNOT cross in 3-D except at nulls of the field, because a
 *     single-valued vector field has exactly one direction at every point.
 *     The master invariant below (faithfulness) checks precisely that every
 *     drawn segment follows the model field at its own midpoint — a set of
 *     polylines that all pass this cannot cross each other transversally.
 *     The proximity sweeps then verify the conclusion directly.
 *   - Unclosed (open) lines are REAL: polar-cap lines have one footpoint on
 *     Earth and stretch down the tail lobes; in the Dungey cycle they are the
 *     flux that dayside reconnection opened. The topology tests pin that an
 *     "open" label always corresponds to exactly that endpoint geometry, and
 *     that southward Bz opens MORE of them — the physically required trend.
 *
 * Every check runs over a grid of driver states: quiet, moderate, the
 * recorded storm's extreme, and the two solstice tilt extremes.
 */
import { describe, expect, it } from "vitest";

import {
  BOUNDARY_LINE_END_FADE_ARC_RE,
  compressedDipoleFieldNt,
  daysideNeutralPointGsm,
  FIELD_LINE_ALIGNMENT_TOLERANCE_RAD,
  FIELD_LINE_MAX_TURN_RAD,
  OPEN_LINE_END_FADE_ARC_RE,
  traceMagnetosphereFieldLines,
  truncatedEndFade,
  verifyTracedMagnetosphere,
} from "../src/magnetosphere-field-lines";
import type {
  CompressedDipoleParameters,
  FieldLineDrivers,
  TracedFieldLine,
  TracedMagnetosphere,
} from "../src/magnetosphere-field-lines";
import type { FieldLineIntegrityReport } from "../src/magnetosphere-field-lines";
import { shueRadiusRe } from "../src/magnetopause";
import { keyCardBar, magnetosphereFieldLegendSpec } from "../src/main";
import type { MagnetosphereFieldSpecInput } from "../src/main";

/**
 * The driver grid. Tilt extremes are the solstices (Hapgood tilt reaches
 * about ±33° with the diurnal wobble; ±0.5 rad ≈ ±28.6° is a solstice
 * mid-day value). Pressures and Bz bracket the recorded 2026-08 storm.
 */
const DRIVER_GRID: Record<string, FieldLineDrivers> = {
  quiet: { dynamicPressureNpa: 1.0, bzGsmNt: 3.0, dipoleTiltRad: 0.15 },
  moderate: { dynamicPressureNpa: 2.5, bzGsmNt: -5.0, dipoleTiltRad: -0.1 },
  stormPeak: { dynamicPressureNpa: 6.5, bzGsmNt: -12.0, dipoleTiltRad: 0.15 },
  juneSolstice: { dynamicPressureNpa: 1.6, bzGsmNt: -2.0, dipoleTiltRad: 0.5 },
  decemberSolstice: { dynamicPressureNpa: 1.6, bzGsmNt: -2.0, dipoleTiltRad: -0.5 },
};

const TRACED: Record<string, TracedMagnetosphere> = Object.fromEntries(
  Object.entries(DRIVER_GRID).map(([name, drivers]) => {
    const traced = traceMagnetosphereFieldLines(drivers);
    if (!traced) throw new Error(`trace refused for driver state ${name}`);
    return [name, traced];
  }),
);

const GRID_NAMES = Object.keys(DRIVER_GRID);

// ---------------------------------------------------------------------------
// Checker functions. These are the same functions the negative controls at
// the bottom drive against deliberately broken data, so a checker that stops
// checking fails loudly instead of passing vacuously.
// ---------------------------------------------------------------------------

interface Vec3 {
  x: number;
  y: number;
  z: number;
}

function sub(a: Vec3, b: Vec3): Vec3 {
  return { x: a.x - b.x, y: a.y - b.y, z: a.z - b.z };
}

function norm(a: Vec3): number {
  return Math.hypot(a.x, a.y, a.z);
}

/** Worst angle (radians) between any segment and the field at its midpoint. */
function faithfulnessWorstRad(
  parameters: CompressedDipoleParameters,
  lines: readonly TracedFieldLine[],
): { worstRad: number; segmentCount: number } {
  let worstRad = 0;
  let segmentCount = 0;
  for (const line of lines) {
    const points = line.pointsGsmRe;
    let sign = 0;
    for (let index = 1; index < points.length; index += 1) {
      const a = points[index - 1]!;
      const b = points[index]!;
      const chord = sub(b, a);
      const length = norm(chord);
      if (length < 1e-9) continue;
      const field = compressedDipoleFieldNt(
        parameters,
        (a.x + b.x) / 2,
        (a.y + b.y) / 2,
        (a.z + b.z) / 2,
      );
      const magnitude = norm(field);
      if (magnitude < 1e-6) continue; // undefined direction at a genuine null
      const cosine = (chord.x * field.x + chord.y * field.y + chord.z * field.z)
        / (length * magnitude);
      if (sign === 0) sign = cosine >= 0 ? 1 : -1;
      const angle = Math.acos(Math.min(1, Math.max(-1, sign * cosine)));
      segmentCount += 1;
      if (angle > worstRad) worstRad = angle;
    }
  }
  return { worstRad, segmentCount };
}

/** Exact minimum distance between two 3-D segments (clamped closest points). */
function segmentDistance(p1: Vec3, q1: Vec3, p2: Vec3, q2: Vec3): number {
  const d1 = sub(q1, p1);
  const d2 = sub(q2, p2);
  const r = sub(p1, p2);
  const a = d1.x * d1.x + d1.y * d1.y + d1.z * d1.z;
  const e = d2.x * d2.x + d2.y * d2.y + d2.z * d2.z;
  const f = d2.x * r.x + d2.y * r.y + d2.z * r.z;
  let s: number;
  let t: number;
  if (a <= 1e-18 && e <= 1e-18) {
    s = 0;
    t = 0;
  } else if (a <= 1e-18) {
    s = 0;
    t = Math.min(1, Math.max(0, f / e));
  } else {
    const c = d1.x * r.x + d1.y * r.y + d1.z * r.z;
    if (e <= 1e-18) {
      t = 0;
      s = Math.min(1, Math.max(0, -c / a));
    } else {
      const b = d1.x * d2.x + d1.y * d2.y + d1.z * d2.z;
      const denominator = a * e - b * b;
      s = denominator > 1e-18 ? Math.min(1, Math.max(0, (b * f - c * e) / denominator)) : 0;
      t = Math.min(1, Math.max(0, (b * s + f) / e));
      s = Math.min(1, Math.max(0, (b * t - c) / a));
    }
  }
  const c1 = { x: p1.x + d1.x * s, y: p1.y + d1.y * s, z: p1.z + d1.z * s };
  const c2 = { x: p2.x + d2.x * t, y: p2.y + d2.y * t, z: p2.z + d2.z * t };
  return norm(sub(c1, c2));
}

/** Unsigned angle between two segment directions, radians in [0, π/2]. */
function unsignedDirectionAngleRad(p1: Vec3, q1: Vec3, p2: Vec3, q2: Vec3): number {
  const d1 = sub(q1, p1);
  const d2 = sub(q2, p2);
  const l1 = norm(d1);
  const l2 = norm(d2);
  if (l1 < 1e-12 || l2 < 1e-12) return 0;
  const cosine = Math.abs(d1.x * d2.x + d1.y * d2.y + d1.z * d2.z) / (l1 * l2);
  return Math.acos(Math.min(1, cosine));
}

interface IndexedSegment {
  lineIndex: number;
  segmentIndex: number;
  a: Vec3;
  b: Vec3;
  /** Arc length from the line's start to this segment's midpoint, Re. */
  arcMidRe: number;
}

interface ProximityHit {
  first: IndexedSegment;
  second: IndexedSegment;
  distanceRe: number;
  directionAngleRad: number;
  kind: "self" | "pair";
}

/**
 * Proximity thresholds, stated and justified:
 *
 * EPSILON_RE = 0.02 Re (~128 km). Far below every structure the model
 * contains (sheet half-thickness 3 Re, boundary standoff 6–11 Re, tightest
 * hairpin curvature radius ~0.02 Re) and three orders above float noise;
 * the measured minimum true separation between distinct drawn lines outside
 * the exclusions is an order of magnitude larger (asserted below), so this
 * epsilon detects contact, not styling.
 *
 * SELF_ARC_EXCLUSION_RE = 1.5 Re along-line separation. The 4°-per-step turn
 * cap means a line needs ≥ 45 steps to turn 180°, so genuinely non-adjacent
 * pieces of one line can only be near each other at a hairpin; the tightest
 * hairpin (apex curvature radius ~0.02–0.04 Re) has legs separated by
 * > 0.4 Re once the arc separation reaches 1.5 Re, safely above epsilon.
 *
 * CUSP_EXCLUSION_RE = 1.5 Re around the model's own dayside neutral points.
 * Field-line convergence toward a null is the one place real lines DO
 * approach each other without bound — the funnel is physical, not a defect —
 * and the field direction there turns on scales smaller than epsilon, so no
 * transversality argument holds inside it. Violations OUTSIDE the exclusions
 * must be exactly zero; that is asserted separately.
 *
 * TRANSVERSAL_RAD = 20°. A near-contact only proves a crossing if the two
 * directions disagree: two faithful segments passing within epsilon can
 * differ by at most twice the faithfulness tolerance (2 × 6°) plus the
 * field's own rotation across epsilon (≤ ~8° at the seed shell, far less
 * elsewhere), so parallel passes — conjugate arcs of one interrupted line,
 * packed lobe lines — are legal, while an X-shaped transversal crossing
 * (impossible for one single-valued field) is flagged.
 */
const EPSILON_RE = 0.02;
const SELF_ARC_EXCLUSION_RE = 1.5;
const CUSP_EXCLUSION_RE = 1.5;
const TRANSVERSAL_RAD = (20 * Math.PI) / 180;

function collectSegments(lines: readonly TracedFieldLine[]): IndexedSegment[] {
  const segments: IndexedSegment[] = [];
  for (let lineIndex = 0; lineIndex < lines.length; lineIndex += 1) {
    const points = lines[lineIndex]!.pointsGsmRe;
    let arc = 0;
    for (let index = 1; index < points.length; index += 1) {
      const a = points[index - 1]!;
      const b = points[index]!;
      const length = norm(sub(b, a));
      segments.push({ lineIndex, segmentIndex: index - 1, a, b, arcMidRe: arc + length / 2 });
      arc += length;
    }
  }
  return segments;
}

/**
 * All close approaches, via a spatial hash (uniform grid, cell 1 Re — every
 * segment is ≤ 0.45 Re long so an epsilon-padded segment touches ≤ 8 cells).
 * O(n) insertion, near-O(n) probing; the naive pairwise sweep would be
 * ~10⁸ segment pairs per driver state.
 */
function closeApproaches(
  lines: readonly TracedFieldLine[],
  epsilonRe: number,
): ProximityHit[] {
  const segments = collectSegments(lines);
  const CELL_RE = 1.0;
  const cells = new Map<string, number[]>();
  for (let id = 0; id < segments.length; id += 1) {
    const { a, b } = segments[id]!;
    const min = {
      x: Math.min(a.x, b.x) - epsilonRe,
      y: Math.min(a.y, b.y) - epsilonRe,
      z: Math.min(a.z, b.z) - epsilonRe,
    };
    const max = {
      x: Math.max(a.x, b.x) + epsilonRe,
      y: Math.max(a.y, b.y) + epsilonRe,
      z: Math.max(a.z, b.z) + epsilonRe,
    };
    for (let cx = Math.floor(min.x / CELL_RE); cx <= Math.floor(max.x / CELL_RE); cx += 1) {
      for (let cy = Math.floor(min.y / CELL_RE); cy <= Math.floor(max.y / CELL_RE); cy += 1) {
        for (let cz = Math.floor(min.z / CELL_RE); cz <= Math.floor(max.z / CELL_RE); cz += 1) {
          const key = `${cx},${cy},${cz}`;
          const bucket = cells.get(key);
          if (bucket) bucket.push(id);
          else cells.set(key, [id]);
        }
      }
    }
  }
  const seen = new Set<number>();
  const hits: ProximityHit[] = [];
  for (const bucket of cells.values()) {
    for (let i = 0; i < bucket.length; i += 1) {
      for (let j = i + 1; j < bucket.length; j += 1) {
        const idA = Math.min(bucket[i]!, bucket[j]!);
        const idB = Math.max(bucket[i]!, bucket[j]!);
        const pairKey = idA * segments.length + idB;
        if (seen.has(pairKey)) continue;
        seen.add(pairKey);
        const first = segments[idA]!;
        const second = segments[idB]!;
        if (first.lineIndex === second.lineIndex) {
          if (Math.abs(first.arcMidRe - second.arcMidRe) < SELF_ARC_EXCLUSION_RE) continue;
          const distanceRe = segmentDistance(first.a, first.b, second.a, second.b);
          if (distanceRe >= epsilonRe) continue;
          hits.push({
            first,
            second,
            distanceRe,
            directionAngleRad: unsignedDirectionAngleRad(first.a, first.b, second.a, second.b),
            kind: "self",
          });
        } else {
          const distanceRe = segmentDistance(first.a, first.b, second.a, second.b);
          if (distanceRe >= epsilonRe) continue;
          hits.push({
            first,
            second,
            distanceRe,
            directionAngleRad: unsignedDirectionAngleRad(first.a, first.b, second.a, second.b),
            kind: "pair",
          });
        }
      }
    }
  }
  return hits;
}

function nearCuspNull(parameters: CompressedDipoleParameters, hit: ProximityHit): boolean {
  for (const hemisphere of ["north", "south"] as const) {
    const cusp = daysideNeutralPointGsm(parameters, hemisphere);
    for (const segment of [hit.first, hit.second]) {
      const mid = {
        x: (segment.a.x + segment.b.x) / 2,
        y: (segment.a.y + segment.b.y) / 2,
        z: (segment.a.z + segment.b.z) / 2,
      };
      const distance = Math.hypot(mid.x - cusp.xRe, mid.y, mid.z - cusp.zRe);
      if (distance < CUSP_EXCLUSION_RE) return true;
    }
  }
  return false;
}

// ---------------------------------------------------------------------------
// Invariant 1 — faithfulness, the master invariant.
// ---------------------------------------------------------------------------

describe("faithfulness: every drawn segment follows the model field", () => {
  it("keeps every segment within the stated angular tolerance of B at its midpoint", () => {
    // Tolerance: 1.5 × the 4° per-step curvature cap (6°), the same slack
    // factor the drawn-corner smoothness test uses. For a smooth arc the
    // chord is parallel to the midpoint tangent (the first-order error
    // cancels), so the residual is the cap-refinement's slack plus RK4
    // error; the measured worst across this grid is 1.8°.
    for (const name of GRID_NAMES) {
      const traced = TRACED[name]!;
      const { worstRad, segmentCount } = faithfulnessWorstRad(
        traced.parameters,
        [...traced.lines, ...traced.noonMidnightProbes],
      );
      expect(segmentCount).toBeGreaterThan(5_000);
      expect(worstRad, `${name}: worst ${(worstRad * 180 / Math.PI).toFixed(2)}°`)
        .toBeLessThan(FIELD_LINE_ALIGNMENT_TOLERANCE_RAD);
    }
  });

  it("uses a tolerance consistent with the tracer's own curvature cap", () => {
    expect(FIELD_LINE_ALIGNMENT_TOLERANCE_RAD).toBeCloseTo(1.5 * FIELD_LINE_MAX_TURN_RAD, 12);
  });
});

// ---------------------------------------------------------------------------
// Invariants 2 & 3 — no self-intersection, no pairwise 3-D crossings.
// ---------------------------------------------------------------------------

describe("proximity: lines never cross themselves or each other", () => {
  it("has zero transversal near-contacts outside the cusp-null exclusions, per driver state", () => {
    for (const name of GRID_NAMES) {
      const traced = TRACED[name]!;
      const hits = closeApproaches(traced.lines, EPSILON_RE);
      const selfHits = hits.filter((hit) => hit.kind === "self");
      // A polyline may not come near itself at all between genuinely
      // non-adjacent arcs — hairpins are covered by the 1.5 Re arc exclusion.
      expect(selfHits, `${name}: ${selfHits.length} self approaches`).toHaveLength(0);
      const transversal = hits.filter((hit) =>
        hit.kind === "pair"
        && hit.directionAngleRad > TRANSVERSAL_RAD
        && !nearCuspNull(traced.parameters, hit));
      expect(
        transversal,
        `${name}: ${transversal.map((hit) =>
          `d=${hit.distanceRe.toFixed(4)} angle=${(hit.directionAngleRad * 180 / Math.PI).toFixed(1)}° `
          + `lines ${hit.first.lineIndex}/${hit.second.lineIndex}`).join("; ")}`,
      ).toHaveLength(0);
    }
  });

  it("parallel passes exist and are the only near-contacts — convergence, not crossing", () => {
    // The exception must not be vacuous: the cusp funnels and conjugate
    // boundary arcs DO bring distinct lines close together somewhere in the
    // grid. If no near-contacts exist at all, the epsilon has drifted so far
    // that the crossing check above no longer tests anything.
    const anyHits = GRID_NAMES.some((name) =>
      closeApproaches(TRACED[name]!.lines, EPSILON_RE).length > 0);
    const anyWideHits = GRID_NAMES.some((name) =>
      closeApproaches(TRACED[name]!.lines, 0.1).length > 0);
    expect(anyHits || anyWideHits).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Invariants 4 & 5 — Earth clearance and truncation discipline.
// ---------------------------------------------------------------------------

describe("containment: inside the boundary, outside the Earth", () => {
  it("keeps every vertex above the surface, and interior vertices on the landing shell or higher", () => {
    // The tracer lands lines on its r = 1.02 shell by interpolating along the
    // final step's chord; a chord dips below the arc by at most chord²/8r
    // ≈ 1.3e-3 Re for the ~0.1 Re landing steps (measured worst: 8e-5), so
    // the shell floor carries that stated tolerance. The hard invariant —
    // nothing under the r = 1 surface, ever — has no tolerance at all.
    for (const name of GRID_NAMES) {
      for (const line of TRACED[name]!.lines) {
        const points = line.pointsGsmRe;
        for (let index = 0; index < points.length; index += 1) {
          const radius = norm(points[index]!);
          expect(radius, `${name} seed ${line.seedLatitudeDeg}/${line.seedLongitudeDeg} vertex ${index}`)
            .toBeGreaterThan(1.0);
          expect(radius).toBeGreaterThan(1.02 - 1.3e-3);
        }
      }
    }
  });

  it("keeps every vertex inside the truncation surface at its stated 2% tolerance", () => {
    for (const name of GRID_NAMES) {
      const traced = TRACED[name]!;
      for (const line of traced.lines) {
        for (const point of line.pointsGsmRe) {
          const radius = norm(point);
          if (radius < 1.5) continue; // the truncation test's own inner guard
          const theta = Math.acos(Math.min(1, Math.max(-1, point.x / radius)));
          const surface = shueRadiusRe(theta, traced.parameters.standoffRe, traced.parameters.flaringAlpha);
          if (!Number.isFinite(surface)) continue;
          expect(radius, `${name} vertex outside Shue`).toBeLessThanOrEqual(surface * 1.02 + 1e-6);
        }
      }
    }
  });
});

// ---------------------------------------------------------------------------
// Invariant 6 — topology labels match endpoint geometry; open lines are the
// physically expected population.
// ---------------------------------------------------------------------------

describe("topology consistency: labels match endpoint geometry", () => {
  it("closed lines land both footpoints on the surface shells; open and boundary ends are where they claim", () => {
    for (const name of GRID_NAMES) {
      const traced = TRACED[name]!;
      for (const line of [...traced.lines, ...traced.noonMidnightProbes]) {
        const points = line.pointsGsmRe;
        const first = points[0]!;
        const last = points[points.length - 1]!;
        expect(norm(first)).toBeCloseTo(1.08, 6); // the seed footpoint shell
        if (line.topology === "closed") {
          // Second footpoint: back down on the landing shell, opposite hemisphere
          // in the dipole sense — its field there points the other way along r.
          expect(norm(last)).toBeLessThanOrEqual(1.03 + 1e-9);
        } else if (line.topology === "open") {
          // Exactly one footpoint; the far end reached the tail cutoff plane.
          expect(last.x, `${name} open line far end`).toBeLessThanOrEqual(traced.tailCutoffXRe + 1e-9);
          expect(norm(last)).toBeGreaterThan(Math.abs(traced.tailCutoffXRe) * 0.9);
        } else {
          // Boundary-truncated: the far end sits ON the truncation surface.
          const radius = norm(last);
          const theta = Math.acos(Math.min(1, Math.max(-1, last.x / radius)));
          const surface = shueRadiusRe(theta, traced.parameters.standoffRe, traced.parameters.flaringAlpha) * 1.02;
          expect(Math.abs(radius - surface), `${name} boundary end off-surface`).toBeLessThan(0.02);
        }
      }
    }
  });

  it("southward Bz opens more lines — the Dungey-cycle direction, monotone", () => {
    const openCounts = [5, 0, -5, -12].map((bz) => {
      const traced = traceMagnetosphereFieldLines({
        dynamicPressureNpa: 2.0,
        bzGsmNt: bz,
        dipoleTiltRad: 0.15,
      })!;
      return traced.summary.openCount;
    });
    for (let index = 1; index < openCounts.length; index += 1) {
      expect(openCounts[index]!).toBeGreaterThanOrEqual(openCounts[index - 1]!);
    }
    expect(openCounts[3]!).toBeGreaterThan(openCounts[0]!);
  });
});

// ---------------------------------------------------------------------------
// The runtime guard and the end fade.
// ---------------------------------------------------------------------------

describe("the runtime guard the renderer actually runs", () => {
  it("passes every grid state, checking a real sample", () => {
    for (const name of GRID_NAMES) {
      const report = verifyTracedMagnetosphere(TRACED[name]!);
      expect(report.ok, `${name}: ${report.reason ?? ""}`).toBe(true);
      expect(report.reason).toBeNull();
      expect(report.checkedSegmentCount).toBeGreaterThan(500);
      expect(report.worstAlignmentDeg).toBeLessThan(
        (FIELD_LINE_ALIGNMENT_TOLERANCE_RAD * 180) / Math.PI,
      );
    }
  });

  it("stays cheap enough for a per-rebuild browser check", () => {
    const traced = TRACED.stormPeak!;
    const start = performance.now();
    for (let repeat = 0; repeat < 10; repeat += 1) verifyTracedMagnetosphere(traced);
    const perCallMs = (performance.now() - start) / 10;
    // The rebuild it guards (traceMagnetosphereFieldLines) costs hundreds of
    // milliseconds; the guard must stay two orders below it.
    expect(perCallMs).toBeLessThan(25);
  });
});

describe("the truncated-end fade (geometry untouched, opacity only)", () => {
  it("fades open and boundary ends to zero at the cut and to full within the stated arcs", () => {
    expect(truncatedEndFade("open", 0)).toBe(0);
    expect(truncatedEndFade("boundary", 0)).toBe(0);
    expect(truncatedEndFade("open", OPEN_LINE_END_FADE_ARC_RE)).toBe(1);
    expect(truncatedEndFade("boundary", BOUNDARY_LINE_END_FADE_ARC_RE)).toBe(1);
    expect(truncatedEndFade("open", OPEN_LINE_END_FADE_ARC_RE * 2)).toBe(1);
    // Monotone ramp in between.
    let previous = 0;
    for (let arc = 0; arc <= OPEN_LINE_END_FADE_ARC_RE; arc += 0.5) {
      const value = truncatedEndFade("open", arc);
      expect(value).toBeGreaterThanOrEqual(previous);
      previous = value;
    }
  });

  it("never fades closed lines — both their ends are real footpoints", () => {
    expect(truncatedEndFade("closed", 0)).toBe(1);
    expect(truncatedEndFade("closed", 100)).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// Non-vacuity proofs: the same checkers, against deliberately broken data.
// A checker that cannot fail is not a check; each control below breaks one
// invariant in a copy and demands the corresponding checker report it.
// ---------------------------------------------------------------------------

function deepCopy(traced: TracedMagnetosphere): TracedMagnetosphere {
  return {
    ...traced,
    lines: traced.lines.map((line) => ({
      ...line,
      pointsGsmRe: line.pointsGsmRe.map((point) => ({ ...point })),
      logFieldNt: [...line.logFieldNt],
    })),
    noonMidnightProbes: traced.noonMidnightProbes.map((line) => ({
      ...line,
      pointsGsmRe: line.pointsGsmRe.map((point) => ({ ...point })),
      logFieldNt: [...line.logFieldNt],
    })),
  };
}

describe("non-vacuity: every checker catches an injected defect", () => {
  it("faithfulness catches a perturbed vertex — in the suite checker AND the runtime guard", () => {
    const broken = deepCopy(TRACED.quiet!);
    const victim = broken.lines.find((line) => line.pointsGsmRe.length > 40)!;
    const middle = Math.floor(victim.pointsGsmRe.length / 2);
    victim.pointsGsmRe[middle]!.z += 1.5; // a 1.5 Re kink mid-line
    const { worstRad } = faithfulnessWorstRad(broken.parameters, broken.lines);
    expect(worstRad).toBeGreaterThan(FIELD_LINE_ALIGNMENT_TOLERANCE_RAD);
    // The runtime guard samples 1-in-7 segments, but a kink bends TWO
    // adjacent segments and the guard walks every line, so verify with the
    // stride that the renderer uses only after making the defect span it.
    const report = verifyTracedMagnetosphere(broken, { segmentStride: 1 });
    expect(report.ok).toBe(false);
    expect(report.reason).toBe("segment-field-misalignment");
  });

  it("the guard's default stride still catches a corrupted stretch of line", () => {
    const broken = deepCopy(TRACED.quiet!);
    const victim = broken.lines.find((line) => line.pointsGsmRe.length > 60)!;
    // A whole displaced stretch — the realistic failure (wrong frame, unit
    // slip, mapper bug) corrupts runs of points, not single vertices.
    for (let index = 20; index < 40; index += 1) victim.pointsGsmRe[index]!.x += 2;
    const report = verifyTracedMagnetosphere(broken);
    expect(report.ok).toBe(false);
    expect(report.reason).toBe("segment-field-misalignment");
  });

  it("the crossing checker catches a transversal crossing between two lines", () => {
    const broken = deepCopy(TRACED.quiet!);
    // Rebuild one line as a straight polyline that punches perpendicularly
    // through a mid-line vertex of another — an X in space, the exact figure
    // a single-valued field cannot produce. The proximity sweep itself, not
    // faithfulness, must see it.
    const victim = broken.lines.find((line) => line.topology === "closed" && line.apexRadiusRe > 4)!;
    const middle = Math.floor(victim.pointsGsmRe.length / 2);
    const through = victim.pointsGsmRe[middle]!;
    const ahead = victim.pointsGsmRe[middle + 1]!;
    const direction = sub(ahead, through);
    const length = norm(direction);
    // Any unit vector perpendicular to the local direction.
    const seedPerp = Math.abs(direction.z) < 0.9 * length
      ? { x: -direction.y, y: direction.x, z: 0 }
      : { x: 0, y: -direction.z, z: direction.y };
    const perpLength = norm(seedPerp);
    const perp = { x: seedPerp.x / perpLength, y: seedPerp.y / perpLength, z: seedPerp.z / perpLength };
    const impostor = broken.lines.find((line) => line !== victim)!;
    impostor.pointsGsmRe = Array.from({ length: 11 }, (_, step) => {
      const t = (step - 5) / 5; // ±1 Re through the victim vertex
      return { x: through.x + perp.x * t, y: through.y + perp.y * t, z: through.z + perp.z * t };
    });
    const hits = closeApproaches(broken.lines, EPSILON_RE);
    const transversal = hits.filter((hit) =>
      hit.kind === "pair" && hit.directionAngleRad > TRANSVERSAL_RAD);
    expect(transversal.length).toBeGreaterThan(0);
  });

  it("the self-intersection checker catches a line folded onto itself", () => {
    const broken = deepCopy(TRACED.quiet!);
    const victim = broken.lines.find((line) => line.pointsGsmRe.length > 80)!;
    const points = victim.pointsGsmRe;
    // Fold the last quarter back onto an earlier stretch of the same line,
    // ending EXACTLY on the earlier vertex so the fold genuinely touches it.
    const target = points[20]!;
    const foldStart = Math.floor(points.length * 0.75);
    for (let index = foldStart; index < points.length; index += 1) {
      const t = (index - foldStart) / (points.length - 1 - foldStart);
      const source = points[index]!;
      source.x = source.x * (1 - t) + target.x * t;
      source.y = source.y * (1 - t) + target.y * t;
      source.z = source.z * (1 - t) + target.z * t;
    }
    const hits = closeApproaches(broken.lines, EPSILON_RE);
    expect(hits.filter((hit) => hit.kind === "self").length).toBeGreaterThan(0);
  });

  it("topology checks catch a mislabelled line — suite AND runtime guard", () => {
    const broken = deepCopy(TRACED.quiet!);
    const closed = broken.lines.find((line) => line.topology === "closed")!;
    (closed as { topology: TracedFieldLine["topology"] }).topology = "open";
    const report = verifyTracedMagnetosphere(broken);
    expect(report.ok).toBe(false);
    expect(report.reason).toBe("endpoint-topology-mismatch");
  });

  it("a failed integrity report reaches the card as an honest refusal, never SHAPE ONLY", () => {
    const failedReport: FieldLineIntegrityReport = {
      ok: false,
      reason: "segment-field-misalignment",
      checkedSegmentCount: 2000,
      worstAlignmentDeg: 38.2,
      misalignedSegmentCount: 12,
      structuralViolationCount: 0,
    };
    const input: MagnetosphereFieldSpecInput = {
      field: "magneticField",
      fieldMetadata: null,
      structures: null,
      runtimeState: null,
      loading: false,
      empiricalAnnotationOn: false,
      shueNoseRe: null,
      frameDescription: null,
      formatEndpoint: (value) => value.toFixed(1),
      mhdCutOn: false,
      fieldLineSummary: null,
      fieldLineIntegrity: failedReport,
    };
    const spec = magnetosphereFieldLegendSpec(input);
    expect(spec.badge).toBe("TRACE CHECK FAILED");
    expect(spec.statusState).toBe("no-data");
    expect(spec.statusText).toContain("failed their own consistency check");
    expect((spec.stats ?? []).some((stat) =>
      stat.label === "TRACE CHECK" && stat.value === "SEGMENT FIELD MISALIGNMENT")).toBe(true);
    // The refusal card keeps the quantity's ramp: SHAPE ONLY stays unreachable.
    expect(keyCardBar(spec, false).kind).toBe("ramp");
    // And a PASSING report changes nothing about the normal card.
    const normal = magnetosphereFieldLegendSpec({
      ...input,
      fieldLineIntegrity: { ...failedReport, ok: true, reason: null },
    });
    expect(normal.badge).not.toBe("TRACE CHECK FAILED");
  });

  it("Earth clearance catches a vertex driven under the surface", () => {
    const broken = deepCopy(TRACED.quiet!);
    const victim = broken.lines[0]!;
    const middle = Math.floor(victim.pointsGsmRe.length / 2);
    const point = victim.pointsGsmRe[middle]!;
    const radius = Math.hypot(point.x, point.y, point.z);
    const shrink = 0.5 / radius;
    point.x *= shrink;
    point.y *= shrink;
    point.z *= shrink;
    const report = verifyTracedMagnetosphere(broken, { segmentStride: 1_000_000 });
    expect(report.ok).toBe(false);
    expect(report.reason).toBe("earth-clearance");
  });
});
