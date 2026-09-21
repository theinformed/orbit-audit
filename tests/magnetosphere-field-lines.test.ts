/**
 * Numeric proofs for the driven 3-D field-line model — the checks that must
 * pass before any screenshot of it is worth taking.
 *
 * The construction is dipole + Chapman–Ferraro image dipole + Harris tail
 * (see src/magnetosphere-field-lines.ts). What these tests pin is not the
 * artistry but the physics the layer claims:
 *
 *   - the dayside closes inside the live Shue boundary and COMPRESSES when
 *     dynamic pressure rises;
 *   - the polar caps are open and GROW when Bz turns south;
 *   - the tail is stretched, two-lobed, and stretches further in a storm;
 *   - the model's own dayside neutral points (its cusps) exist at dayside
 *     mid-latitudes and move with the drivers;
 *   - every traced point stays outside the Earth and inside the truncation
 *     boundary the scene draws.
 */
import { describe, expect, it } from "vitest";

import {
  compressedDipoleFieldNt,
  compressedDipoleParameters,
  daysideNeutralPointGsm,
  DIPOLE_B0_NT,
  FIELD_LINE_MAX_TURN_RAD,
  fitShueToBoundaryCurve,
  shueResidualRmsRe,
  tailLobeFieldNt,
  traceMagnetosphereFieldLines,
} from "../src/magnetosphere-field-lines";
import type { BoundaryCurvePoint } from "../src/magnetosphere-field-lines";
import { shueBoundary, shueRadiusRe } from "../src/magnetopause";
import {
  RADIAL_RULER,
  rulerJointBandSegments,
  sharedDisplayRadius,
} from "../src/radial-ruler";
import {
  IGRF_DIPOLE_G10_NT,
  IGRF_DIPOLE_G11_NT,
  IGRF_DIPOLE_H11_NT,
} from "../src/dipole-tilt";
import type { FieldLineDrivers } from "../src/magnetosphere-field-lines";

/** Quiet conditions near the 2026-08-08 recovery: Pd ~1 nPa, Bz north. */
const QUIET: FieldLineDrivers = { dynamicPressureNpa: 1.0, bzGsmNt: 2.0, dipoleTiltRad: 0.15 };
/** The storm main phase the 48 h replay carries: compressed and southward. */
const STORM: FieldLineDrivers = { dynamicPressureNpa: 6.5, bzGsmNt: -12.0, dipoleTiltRad: 0.15 };

describe("the field construction itself", () => {
  it("uses the IGRF dipole magnitude, not a remembered constant", () => {
    // The exact hypotenuse of the pinned IGRF-13 2020.0 terms, which
    // dipole-tilt.test.ts verifies against the published table; plus a sanity
    // window against the literature's ~30,000 nT surface equatorial field.
    expect(DIPOLE_B0_NT).toBeCloseTo(
      Math.hypot(IGRF_DIPOLE_G10_NT, IGRF_DIPOLE_G11_NT, IGRF_DIPOLE_H11_NT),
      6,
    );
    expect(DIPOLE_B0_NT).toBeGreaterThan(29_000);
    expect(DIPOLE_B0_NT).toBeLessThan(30_500);
  });

  it("doubles the subsolar field at the boundary, the Chapman–Ferraro signature", () => {
    const parameters = compressedDipoleParameters({ ...QUIET, dipoleTiltRad: 0 })!;
    const r0 = parameters.standoffRe;
    const total = compressedDipoleFieldNt(parameters, r0, 0, 0);
    const dipoleOnly = DIPOLE_B0_NT / r0 ** 3;
    // At the nose the image contributes exactly one more dipole field.
    expect(total.z / dipoleOnly).toBeCloseTo(2, 1);
    expect(Math.abs(total.x)).toBeLessThan(Math.abs(total.z) * 0.02);
  });

  it("keeps the numerical divergence of the summed field near zero, tail included", () => {
    const parameters = compressedDipoleParameters(STORM)!;
    const h = 0.01;
    const probes: Array<[number, number, number]> = [[-8, 3, 2.4], [-15, -6, -1.2], [-6, 0, 3.5], [5, 2, 3]];
    for (const [x, y, z] of probes) {
      const dx = (compressedDipoleFieldNt(parameters, x + h, y, z).x - compressedDipoleFieldNt(parameters, x - h, y, z).x) / (2 * h);
      const dy = (compressedDipoleFieldNt(parameters, x, y + h, z).y - compressedDipoleFieldNt(parameters, x, y - h, z).y) / (2 * h);
      const dz = (compressedDipoleFieldNt(parameters, x, y, z + h).z - compressedDipoleFieldNt(parameters, x, y, z - h).z) / (2 * h);
      const divergence = dx + dy + dz;
      const scale = Math.hypot(
        compressedDipoleFieldNt(parameters, x, y, z).x,
        compressedDipoleFieldNt(parameters, x, y, z).y,
        compressedDipoleFieldNt(parameters, x, y, z).z,
      );
      expect(Math.abs(divergence)).toBeLessThan(Math.max(0.05, scale * 0.02));
    }
  });

  it("drives the tail strength with pressure and southward Bz, capped", () => {
    expect(tailLobeFieldNt(QUIET)).toBeCloseTo(18 * Math.sqrt(0.5), 2);
    expect(tailLobeFieldNt(STORM)).toBeGreaterThan(tailLobeFieldNt(QUIET) * 1.8);
    expect(tailLobeFieldNt({ dynamicPressureNpa: 40, bzGsmNt: -40, dipoleTiltRad: 0 })).toBe(45);
  });
});

describe("traced topology", () => {
  const quiet = traceMagnetosphereFieldLines(QUIET)!;
  const storm = traceMagnetosphereFieldLines(STORM)!;

  it("produces all three families: closed, open, boundary-truncated", () => {
    for (const traced of [quiet, storm]) {
      expect(traced.summary.closedCount).toBeGreaterThan(20);
      expect(traced.summary.openCount).toBeGreaterThanOrEqual(4);
      expect(traced.summary.boundaryCount).toBeGreaterThan(10);
      // Both hemispheres contribute non-closed lines, so both polar caps and
      // both tail lobes are drawn.
      const northNonClosed = traced.lines.some((line) => line.topology !== "closed" && line.seedLatitudeDeg > 0);
      const southNonClosed = traced.lines.some((line) => line.topology !== "closed" && line.seedLatitudeDeg < 0);
      expect(northNonClosed).toBe(true);
      expect(southNonClosed).toBe(true);
    }
  });

  it("keeps every point outside the Earth and inside 1.05x the Shue boundary", () => {
    for (const traced of [quiet, storm]) {
      const shue = shueBoundary(traced.parameters.drivers.dynamicPressureNpa, traced.parameters.drivers.bzGsmNt)!;
      for (const line of traced.lines) {
        for (const point of line.pointsGsmRe) {
          const r = Math.hypot(point.x, point.y, point.z);
          expect(r).toBeGreaterThan(0.99);
          const theta = Math.acos(Math.min(1, Math.max(-1, point.x / r)));
          const boundary = shueRadiusRe(theta, shue.subsolarStandoffRe, shue.flaringAlpha);
          if (Number.isFinite(boundary)) expect(r).toBeLessThanOrEqual(boundary * 1.05);
        }
      }
    }
  });

  it("closes the dayside inside the standoff, and the storm compresses it", () => {
    expect(quiet.summary.closedNoseXRe).toBeGreaterThan(5);
    expect(quiet.summary.closedNoseXRe).toBeLessThanOrEqual(quiet.summary.standoffRe * 1.02);
    expect(storm.summary.standoffRe).toBeLessThan(quiet.summary.standoffRe - 2);
    // THE deformation number: the drawn dayside nose moves earthward with the
    // measured pressure, by at least two Earth radii across this storm.
    expect(storm.summary.closedNoseXRe).toBeLessThan(quiet.summary.closedNoseXRe - 2);
  });

  it("opens the polar cap, and southward Bz opens it further equatorward", () => {
    expect(quiet.summary.firstOpenMidnightLatitudeDeg).toBeGreaterThan(60);
    expect(quiet.summary.firstOpenMidnightLatitudeDeg).toBeLessThan(82);
    expect(storm.summary.firstOpenMidnightLatitudeDeg)
      .toBeLessThanOrEqual(quiet.summary.firstOpenMidnightLatitudeDeg);
  });

  it("stretches open lines down the tail to the cutoff", () => {
    expect(quiet.summary.meanOpenTailReachXRe).toBeLessThan(-25);
    expect(storm.summary.meanOpenTailReachXRe).toBeLessThan(-25);
  });

  it("separates the two tail lobes by hemisphere", () => {
    for (const traced of [quiet, storm]) {
      const deepTailPoints = traced.lines.flatMap((line) =>
        line.pointsGsmRe.filter((point) => point.x < -20));
      expect(deepTailPoints.length).toBeGreaterThan(50);
      // In the deep tail the model field is lobe-like: points cluster off the
      // current sheet rather than filling the meridian uniformly.
      const northern = deepTailPoints.filter((point) => point.z > 1).length;
      const southern = deepTailPoints.filter((point) => point.z < -1).length;
      expect(northern).toBeGreaterThan(10);
      expect(southern).toBeGreaterThan(10);
    }
  });

  it("draws smooth lines: no corner between consecutive segments exceeds 1.5x the turn cap", () => {
    // Sean: "can you make them smooth? There are kinks in them and I wonder
    // why." The polyline's vertices ARE the integration points, so tessellation
    // density is set by the step size; before the curvature-aware cap the
    // worst drawn corner measured 53° quiet / 110° storm (a ~0.45 Re chord
    // across the apex, cusp throat and tail hinge). The cap holds every
    // corner near FIELD_LINE_MAX_TURN_RAD; 1.5x is the estimate's slack.
    const limitRad = FIELD_LINE_MAX_TURN_RAD * 1.5;
    for (const traced of [quiet, storm]) {
      let worstRad = 0;
      let vertexCount = 0;
      for (const line of [...traced.lines, ...traced.noonMidnightProbes]) {
        const points = line.pointsGsmRe;
        vertexCount += points.length;
        for (let index = 2; index < points.length; index += 1) {
          const a = points[index - 2]!;
          const b = points[index - 1]!;
          const c = points[index]!;
          const ab = { x: b.x - a.x, y: b.y - a.y, z: b.z - a.z };
          const bc = { x: c.x - b.x, y: c.y - b.y, z: c.z - b.z };
          const abLength = Math.hypot(ab.x, ab.y, ab.z);
          const bcLength = Math.hypot(bc.x, bc.y, bc.z);
          if (abLength < 1e-9 || bcLength < 1e-9) continue;
          const cosine = (ab.x * bc.x + ab.y * bc.y + ab.z * bc.z) / (abLength * bcLength);
          const turn = Math.acos(Math.min(1, Math.max(-1, cosine)));
          if (turn > worstRad) worstRad = turn;
        }
      }
      expect(worstRad).toBeLessThan(limitRad);
      // The vertex budget the smoothing costs: about +35% over the old
      // radius-only step (~11k → ~14.5k traced vertices per driver state,
      // probes included). Hold the ceiling so density regressions surface.
      expect(vertexCount).toBeLessThan(18_000);
    }
  });
});

describe("the model's own cusps", () => {
  it("has a genuine dayside neutral point at mid-latitude in both hemispheres", () => {
    const parameters = compressedDipoleParameters(QUIET)!;
    const subsolarFieldNt = 2 * DIPOLE_B0_NT / parameters.standoffRe ** 3;
    for (const hemisphere of ["north", "south"] as const) {
      const cusp = daysideNeutralPointGsm(parameters, hemisphere);
      expect(cusp.xRe).toBeGreaterThan(0);
      expect(hemisphere === "north" ? cusp.zRe : -cusp.zRe).toBeGreaterThan(0);
      expect(cusp.zenithDeg).toBeGreaterThan(15);
      expect(cusp.zenithDeg).toBeLessThan(70);
      expect(cusp.radiusRe).toBeGreaterThan(parameters.standoffRe * 0.7);
      expect(cusp.radiusRe).toBeLessThan(parameters.standoffRe * 1.45);
      // A near-null, not a shallow dip: under 3% of the subsolar boundary field.
      expect(cusp.fieldNt).toBeLessThan(subsolarFieldNt * 0.03);
    }
  });

  it("the cusp moves earthward as pressure compresses the boundary", () => {
    const quietCusp = daysideNeutralPointGsm(compressedDipoleParameters(QUIET)!, "north");
    const stormCusp = daysideNeutralPointGsm(compressedDipoleParameters(STORM)!, "north");
    expect(stormCusp.radiusRe).toBeLessThan(quietCusp.radiusRe - 2);
  });

  it("field lines converge toward the cusp: the last closed noon lines apex near it", () => {
    const traced = traceMagnetosphereFieldLines(QUIET)!;
    const noonClosed = traced.noonMidnightProbes.filter(
      (line) => line.topology === "closed" && line.seedLongitudeDeg === 0,
    );
    expect(noonClosed.length).toBeGreaterThan(2);
    const highest = noonClosed.reduce((best, line) =>
      line.seedLatitudeDeg > best.seedLatitudeDeg ? line : best);
    // Its sunward-most point sits in the outer dayside, under the boundary —
    // the throat of the funnel — rather than near the equator or the tail.
    expect(highest.sunwardMostXRe).toBeGreaterThan(traced.summary.standoffRe * 0.45);
  });
});

describe("per-frame MHD boundary calibration", () => {
  /** A synthetic curve sampled exactly like the published one: ±70°, 5° steps. */
  function curveFromShue(standoffRe: number, alpha: number, noise = 0): BoundaryCurvePoint[] {
    const points: BoundaryCurvePoint[] = [];
    for (let angle = -70; angle <= 70; angle += 5) {
      const thetaRad = (Math.abs(angle) * Math.PI) / 180;
      const radius = shueRadiusRe(thetaRad, standoffRe, alpha);
      // Deterministic pseudo-noise so the test never flakes.
      const wobble = noise * Math.sin(angle * 12.9898);
      points.push({ thetaRad, radiusRe: radius + wobble });
    }
    return points;
  }

  it("recovers a known Shue surface exactly — the fit is the inverse of the form", () => {
    const fit = fitShueToBoundaryCurve(curveFromShue(9.3, 0.55))!;
    expect(fit.standoffRe).toBeCloseTo(9.3, 6);
    expect(fit.flaringAlpha).toBeCloseTo(0.55, 6);
    expect(fit.rmsResidualRe).toBeLessThan(1e-9);
    expect(fit.noseResidualRe).toBeCloseTo(0, 6);
    expect(fit.source).toBe("noaa-mhd-frame");
  });

  it("beats the mismatched L1 reference on the frame's own curve, and reports both residuals", () => {
    // The MHD boundary sits at 10.6 Re with mild extraction noise; the L1
    // Shue surface of the moment says 9.1. The fit must land near the MHD
    // curve and carry the before/after numbers for the card.
    const curve = curveFromShue(10.6, 0.52, 0.12);
    const fit = fitShueToBoundaryCurve(curve, { standoffRe: 9.1, flaringAlpha: 0.58 }, "2026-08-09T19:20:00Z")!;
    expect(fit.standoffRe).toBeCloseTo(10.6, 1);
    expect(fit.referenceRmsResidualRe).not.toBeNull();
    expect(fit.rmsResidualRe).toBeLessThan(fit.referenceRmsResidualRe!);
    expect(fit.referenceRmsResidualRe!).toBeGreaterThan(1);
    expect(fit.rmsResidualRe).toBeLessThan(0.2);
    expect(fit.frameValidAt).toBe("2026-08-09T19:20:00Z");
    // The reference residual is computed by the same exported arithmetic.
    expect(fit.referenceRmsResidualRe!).toBeCloseTo(shueResidualRmsRe(
      curve.filter((point) => point.radiusRe > 2),
      9.1,
      0.58,
    ), 9);
  });

  it("refuses garbage rather than bending the drawn field to it", () => {
    expect(fitShueToBoundaryCurve([])).toBeNull();
    expect(fitShueToBoundaryCurve(curveFromShue(9.3, 0.55).slice(0, 4))).toBeNull();
    // A curve whose fit lands outside the plausible window is refused whole.
    expect(fitShueToBoundaryCurve(curveFromShue(25, 0.55))).toBeNull();
    expect(fitShueToBoundaryCurve(
      curveFromShue(9.3, 0.55).map((point) => ({ ...point, radiusRe: Number.NaN })),
    )).toBeNull();
  });

  it("drives the whole construction: standoff, image dipole, truncation and label", () => {
    const calibration = fitShueToBoundaryCurve(curveFromShue(8.2, 0.5))!;
    const plain = compressedDipoleParameters(QUIET)!;
    const calibrated = compressedDipoleParameters({ ...QUIET, boundaryCalibration: calibration })!;
    expect(plain.boundarySource).toBe("shue-l1");
    expect(calibrated.boundarySource).toBe("noaa-mhd-frame");
    expect(calibrated.standoffRe).toBeCloseTo(8.2, 6);
    expect(calibrated.flaringAlpha).toBeCloseTo(0.5, 6);
    expect(calibrated.imageXRe).toBeCloseTo(16.4, 6);
    // And the traced set honours it: the summary names the source, and every
    // drawn point stays inside the CALIBRATED boundary, which here is well
    // inside the quiet L1 Shue surface.
    const traced = traceMagnetosphereFieldLines({ ...QUIET, boundaryCalibration: calibration })!;
    expect(traced.summary.boundarySource).toBe("noaa-mhd-frame");
    expect(traced.summary.calibration?.standoffRe).toBeCloseTo(8.2, 6);
    expect(traced.summary.standoffRe).toBeCloseTo(8.2, 6);
    for (const line of traced.lines) {
      for (const point of line.pointsGsmRe) {
        const r = Math.hypot(point.x, point.y, point.z);
        const theta = Math.acos(Math.min(1, Math.max(-1, point.x / r)));
        const boundary = shueRadiusRe(theta, 8.2, 0.5);
        if (Number.isFinite(boundary)) expect(r).toBeLessThanOrEqual(boundary * 1.05);
      }
    }
  });
});

describe("deformation across the recorded storm replay", () => {
  it("the drawn shape moves substantially and monotonically with pressure", () => {
    const noses: number[] = [];
    for (const pressure of [0.8, 2, 4, 8]) {
      const traced = traceMagnetosphereFieldLines({ dynamicPressureNpa: pressure, bzGsmNt: -3, dipoleTiltRad: 0.1 })!;
      noses.push(traced.summary.closedNoseXRe);
    }
    for (let index = 1; index < noses.length; index += 1) {
      expect(noses[index]!).toBeLessThan(noses[index - 1]!);
    }
    expect(noses[0]! - noses[3]!).toBeGreaterThan(2.5);
  });
});

describe("the drawn line, not the traced one: the shared ruler's joint band", () => {
  /**
   * The tracer caps its step at 4 degrees of PHYSICAL direction change, which
   * says nothing about the DRAWN line: the scene's radial ruler magnifies
   * near-Earth radius 7.03x harder than far-Earth radius, and it makes that
   * transition between geostationary radius and 7.35 Re. Anything crossing
   * that band at an angle bends there, and 107 of the 143 drawn lines cross it.
   *
   * This was a real defect nobody had photographed. On the shipped build the
   * worst drawn turn in that band was 45.8 degrees against 7.7 degrees
   * elsewhere on the same lines — 5.9x, and the ruler's slope STEPPED, so it
   * was a true corner. Making the ruler C1 took it to 30.2, and drawing each
   * crossing chord in the pieces `rulerJointBandSegments` asks for takes it to
   * 9.9, which is 1.3x. The bar below is that ratio, not a fixed angle,
   * because the quantity that matters is whether the joint stands out of the
   * line it belongs to.
   */
  const DRIVERS: FieldLineDrivers = { dynamicPressureNpa: 1.7, bzGsmNt: -1.0, dipoleTiltRad: 0.15 };

  /** Exactly what `SpaceGlobe` emits for a field line, in drawn scene units. */
  function drawnPolyline(points: ReadonlyArray<{ x: number; y: number; z: number }>) {
    const drawn: Array<[number, number, number]> = [];
    const radii: number[] = [];
    const place = (x: number, y: number, z: number) => {
      const radius = Math.max(0.001, Math.hypot(x, y, z));
      const scale = sharedDisplayRadius(radius, 100) / radius;
      drawn.push([x * scale, y * scale, z * scale]);
      radii.push(radius);
    };
    for (let index = 0; index < points.length; index += 1) {
      const point = points[index]!;
      const previous = index > 0 ? points[index - 1]! : null;
      const pieces = previous
        ? rulerJointBandSegments(
          Math.hypot(previous.x, previous.y, previous.z),
          Math.hypot(point.x, point.y, point.z),
        )
        : 1;
      for (let piece = 1; piece < pieces; piece += 1) {
        const amount = piece / pieces;
        place(
          previous!.x + (point.x - previous!.x) * amount,
          previous!.y + (point.y - previous!.y) * amount,
          previous!.z + (point.z - previous!.z) * amount,
        );
      }
      place(point.x, point.y, point.z);
    }
    return { drawn, radii };
  }

  function worstDrawnTurns() {
    const traced = traceMagnetosphereFieldLines(DRIVERS, { longitudeCount: 12 })!;
    let inBand = 0;
    let elsewhere = 0;
    let crossing = 0;
    for (const line of traced.lines) {
      const radiiPhysical = line.pointsGsmRe.map((point) => Math.hypot(point.x, point.y, point.z));
      if (!(Math.min(...radiiPhysical) < RADIAL_RULER.anchorRe
        && Math.max(...radiiPhysical) > RADIAL_RULER.anchorRe)) continue;
      crossing += 1;
      const { drawn, radii } = drawnPolyline(line.pointsGsmRe);
      for (let index = 1; index + 1 < drawn.length; index += 1) {
        const before = drawn[index - 1]!;
        const here = drawn[index]!;
        const after = drawn[index + 1]!;
        const back = [here[0] - before[0], here[1] - before[1], here[2] - before[2]] as const;
        const forward = [after[0] - here[0], after[1] - here[1], after[2] - here[2]] as const;
        const backLength = Math.hypot(...back);
        const forwardLength = Math.hypot(...forward);
        if (backLength < 1e-9 || forwardLength < 1e-9) continue;
        const cosine = (back[0] * forward[0] + back[1] * forward[1] + back[2] * forward[2])
          / (backLength * forwardLength);
        const turn = (Math.acos(Math.max(-1, Math.min(1, cosine))) * 180) / Math.PI;
        const radius = radii[index]!;
        if (radius > RADIAL_RULER.anchorRe - 0.6 && radius < RADIAL_RULER.noseRampEndRe + 0.6) {
          inBand = Math.max(inBand, turn);
        } else elsewhere = Math.max(elsewhere, turn);
      }
    }
    return { inBand, elsewhere, crossing };
  }

  it("draws no crease where the lines cross geostationary radius", () => {
    const { inBand, elsewhere, crossing } = worstDrawnTurns();
    // The defect was general, not a one-line accident: most of the drawn set
    // crosses the band.
    expect(crossing).toBeGreaterThan(80);
    expect(inBand).toBeLessThan(1.4 * elsewhere);
  });

  it("asks for subdivision only where the ruler's magnification is changing", () => {
    // The cost side of the same rule. A chord entirely below the anchor or
    // entirely above the ramp end is drawn exactly as it always was.
    expect(rulerJointBandSegments(2, 4)).toBe(1);
    expect(rulerJointBandSegments(8, 20)).toBe(1);
    expect(rulerJointBandSegments(RADIAL_RULER.anchorRe, RADIAL_RULER.noseRampEndRe)).toBe(32);
    expect(rulerJointBandSegments(3, 40)).toBe(32);
    expect(rulerJointBandSegments(RADIAL_RULER.noseRampEndRe - 0.02, 9)).toBeLessThan(5);
  });
});
