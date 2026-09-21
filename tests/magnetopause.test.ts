import { describe, expect, it } from "vitest";
import {
  MAGNETOPAUSE_MODELS,
  linBoundary,
  magnetopauseEvaluator,
  magnetopausePointGsm,
  magneticPressureNpa,
  nguyenBoundary,
  nguyenCuspProximity,
  nguyenRadiusRe,
  nguyenUnindentedRadiusRe,
  shueBoundary,
  shuePointGsm,
  shueRadiusRe,
  shueTailTheta,
} from "../src/magnetopause";

describe("Shue empirical magnetopause", () => {
  it("reproduces the published parameter equations", () => {
    const boundary = shueBoundary(2, 0);
    const expectedR0 = (10.22 + 1.29 * Math.tanh(0.184 * 8.14)) * 2 ** (-1 / 6.6);
    const expectedAlpha = 0.58 * (1 + 0.024 * Math.log(2));
    expect(boundary?.subsolarStandoffRe).toBeCloseTo(expectedR0, 12);
    expect(boundary?.flaringAlpha).toBeCloseTo(expectedAlpha, 12);
  });

  it("compresses under higher pressure and southward Bz", () => {
    const quiet = shueBoundary(1, 5)!;
    const compressed = shueBoundary(12, -15)!;
    expect(compressed.subsolarStandoffRe).toBeLessThan(quiet.subsolarStandoffRe);
    expect(compressed.flaringAlpha).toBeGreaterThan(quiet.flaringAlpha);
  });

  it("places the nose at r0 and evaluates the axisymmetric flank", () => {
    const r0 = 10;
    const alpha = 0.6;
    expect(shueRadiusRe(0, r0, alpha)).toBeCloseTo(r0, 12);
    expect(shueRadiusRe(Math.PI / 2, r0, alpha)).toBeCloseTo(r0 * 2 ** alpha, 12);
    const point = shuePointGsm(Math.PI / 2, Math.PI / 2, r0, alpha);
    expect(point.xRe).toBeCloseTo(0, 12);
    expect(point.yRe).toBeCloseTo(0, 12);
    expect(point.zRe).toBeCloseTo(point.radiusRe, 12);
  });

  it("ends the open tail on its stated physical GSM X plane", () => {
    const theta = shueTailTheta(10, 0.6, 50);
    const point = shuePointGsm(theta, 0, 10, 0.6);
    expect(point.xRe).toBeCloseTo(-50, 8);
    expect(theta).toBeGreaterThan(Math.PI / 2);
    expect(theta).toBeLessThan(170 * Math.PI / 180);
  });

  it("rejects invalid physical drivers and parameters", () => {
    expect(shueBoundary(0, 0)).toBeNull();
    expect(shueBoundary(Number.NaN, 0)).toBeNull();
    expect(Number.isNaN(shueRadiusRe(Math.PI, 10, 0.6))).toBe(true);
  });
});

/**
 * The cusped models are pinned to the published check values in
 * `docs/magnetosphere-realism-design.md`, which were themselves recovered from
 * the papers and cross-checked against two independent open implementations.
 * That matters more than usual here: both models are long polynomial-and-
 * exponential expressions over twenty-odd coefficients, and a transcription
 * error produces a surface that looks entirely plausible. The design document
 * records exactly this failure in another project's T96 port, where an
 * invented Region-2 module was off by a factor of forty in By and survived
 * eyeballing for years because the magnitudes were sensible.
 */
describe("Nguyen et al. (2022) Model 3", () => {
  const drivers = {
    dynamicPressureNpa: 2,
    magneticPressureNpa: magneticPressureNpa(2),
    bzGsmNt: -2,
    clockAngleRad: Math.PI,
    dipoleTiltRad: 0,
  };

  it("reproduces the published noon-north meridian profile", () => {
    const evaluator = magnetopauseEvaluator("nguyen2022", drivers)!;
    const published: Array<[number, number]> = [
      [40, 10.06], [50, 10.07], [55, 10.02], [60, 9.91], [63, 9.8], [80, 11.95],
    ];
    for (const [degrees, expected] of published) {
      expect(evaluator.radiusRe((degrees * Math.PI) / 180, 0)).toBeCloseTo(expected, 1);
    }
  });

  it("indents by the paper's 24.6 percent of the local unindented radius", () => {
    const parameters = nguyenBoundary(drivers)!;
    const theta = parameters.northCuspThetaRad;
    const onAxis = nguyenRadiusRe(theta, 0, drivers, parameters);
    const unindented = nguyenUnindentedRadiusRe(theta, 0, drivers, parameters);
    // Measured against the same direction with the cusp term switched off.
    // Comparing against the flank instead would be wrong: the flaring exponent
    // itself varies with azimuth through the clock-angle terms, so the flank is
    // not the same surface minus a dimple.
    expect(1 - onAxis / unindented).toBeCloseTo(0.246, 3);
    // And the flank at the same zenith angle carries no indentation at all,
    // because the cusp term is weighted by cos^2(azimuth).
    const flank = nguyenRadiusRe(theta, Math.PI / 2, drivers, parameters);
    expect(flank).toBeCloseTo(nguyenUnindentedRadiusRe(theta, Math.PI / 2, drivers, parameters), 9);
  });

  it("moves its cusp equatorward as IMF Bz turns south", () => {
    // This is the property Lin's model does not have, and it is why Nguyen is
    // the model that can animate a storm. The cusp axis is a solar zenith
    // angle measured from the subsolar point, so *smaller* is equatorward.
    const northward = nguyenBoundary({ ...drivers, bzGsmNt: 8 })!;
    const southward = nguyenBoundary({ ...drivers, bzGsmNt: -15 })!;
    expect(southward.northCuspThetaRad).toBeLessThan(northward.northCuspThetaRad);
    expect((northward.northCuspThetaRad * 180) / Math.PI).toBeCloseTo(69, 0);
    expect((southward.northCuspThetaRad * 180) / Math.PI).toBeCloseTo(36, 0);
    // The southern cusp moves with it, symmetrically, at zero dipole tilt.
    expect(southward.southCuspThetaRad).toBeCloseTo(southward.northCuspThetaRad, 12);
  });

  it("breaks north-south symmetry only when the dipole is tilted", () => {
    const untilted = nguyenBoundary(drivers)!;
    expect(untilted.northCuspThetaRad).toBeCloseTo(untilted.southCuspThetaRad, 12);
    const tilted = nguyenBoundary({ ...drivers, dipoleTiltRad: (30 * Math.PI) / 180 })!;
    // A sunward-leaning north pole pulls the northern indentation toward the
    // nose and pushes the southern one toward the terminator.
    expect(tilted.northCuspThetaRad).toBeLessThan(untilted.northCuspThetaRad);
    expect(tilted.southCuspThetaRad).toBeGreaterThan(untilted.southCuspThetaRad);
  });

  it("compresses when the solar wind pushes harder", () => {
    const quiet = magnetopauseEvaluator("nguyen2022", { ...drivers, dynamicPressureNpa: 0.7 })!;
    const storm = magnetopauseEvaluator("nguyen2022", { ...drivers, dynamicPressureNpa: 12 })!;
    expect(storm.subsolarRe).toBeLessThan(quiet.subsolarRe);
  });
});

describe("Lin et al. (2010)", () => {
  // The paper's own implementer check case.
  const drivers = {
    dynamicPressureNpa: 2.056,
    magneticPressureNpa: 0.016,
    bzGsmNt: 0,
    clockAngleRad: 0,
    dipoleTiltRad: 0,
  };

  it("reproduces the published implementer check values", () => {
    const evaluator = magnetopauseEvaluator("lin2010", drivers)!;
    expect(evaluator.radiusRe(0, 0)).toBeCloseTo(10.61, 2);
    expect(evaluator.radiusRe(1.103, 0)).toBeCloseTo(9.5, 2);
    expect(evaluator.radiusRe(1.103, Math.PI / 2)).toBeCloseTo(12.18, 2);
  });

  it("has a subsolar radius that is deliberately not its own r0", () => {
    // Q is non-zero at the nose: the two exponential cusp tails still overlap
    // there, taking about 0.27 Re off. Nguyen et al. flag this as a structural
    // drawback of the model and it is a real trap for anyone reading `r0` as
    // the standoff distance.
    const parameters = linBoundary(drivers)!;
    const evaluator = magnetopauseEvaluator("lin2010", drivers)!;
    expect(parameters.scaleRe).toBeCloseTo(10.89, 2);
    expect(parameters.scaleRe - evaluator.radiusRe(0, 0)).toBeCloseTo(0.28, 1);
  });

  it("moves its cusp vertex with dipole tilt by the amount the paper states", () => {
    for (const [tiltDegrees, expectedDegrees] of [[0, 63.2], [15, 49.6], [35, 31.5]] as const) {
      const parameters = linBoundary({ ...drivers, dipoleTiltRad: (tiltDegrees * Math.PI) / 180 })!;
      expect((parameters.northCuspThetaRad * 180) / Math.PI).toBeCloseTo(expectedDegrees, 1);
    }
  });

  it("does not move its cusp with IMF Bz, and that is the model's own limit", () => {
    // Lin's Q term depends on pressure and tilt only. Anyone expecting the
    // funnel to march equatorward under southward IMF must use Nguyen.
    const northward = linBoundary({ ...drivers, bzGsmNt: 10 })!;
    const southward = linBoundary({ ...drivers, bzGsmNt: -15 })!;
    expect(southward.northCuspThetaRad).toBeCloseTo(northward.northCuspThetaRad, 12);
  });

  it("indents more deeply when the magnetosphere is less compressed", () => {
    // Depth scales as P^-0.636, so a quiet magnetosphere has the deeper funnel.
    const quiet = linBoundary({ ...drivers, dynamicPressureNpa: 1 })!;
    const compressed = linBoundary({ ...drivers, dynamicPressureNpa: 10 })!;
    expect(Math.abs(quiet.cuspDepthRe)).toBeGreaterThan(Math.abs(compressed.cuspDepthRe));
    expect(Math.abs(quiet.cuspDepthRe)).toBeCloseTo(4.4, 0);
    expect(Math.abs(compressed.cuspDepthRe)).toBeCloseTo(1.0, 0);
  });

  it("has the published 30 degree angular half-width", () => {
    const parameters = linBoundary(drivers)!;
    // The 1/e point of exp(d psi^e) is psi = (1/|d|)^(1/e).
    const halfWidthDeg =
      (((1 / Math.abs(parameters.northCuspExponentScale)) ** (1 / parameters.cuspExponent)) * 180) / Math.PI;
    expect(halfWidthDeg).toBeCloseTo(29.6, 1);
  });
});

describe("the pair, and what sits between them", () => {
  const drivers = {
    dynamicPressureNpa: 2,
    magneticPressureNpa: magneticPressureNpa(2),
    bzGsmNt: -2,
    clockAngleRad: Math.PI,
    dipoleTiltRad: 0,
  };

  it("does NOT nest the two surfaces, and the crossing is real", () => {
    // It is tempting to assume the cusp inner boundary lies inside the current
    // sheet everywhere. It does not. Lin and Nguyen are independent fits with
    // different subsolar scales, so away from the funnel Lin sits outside. The
    // exterior-cusp render depends on knowing this, and a future edit that
    // assumes nesting would shade a shell around the whole magnetosphere and
    // call it a cusp.
    const outer = magnetopauseEvaluator("nguyen2022", drivers)!;
    const inner = magnetopauseEvaluator("lin2010", drivers)!;
    expect(inner.radiusRe(0, 0)).toBeGreaterThan(outer.radiusRe(0, 0));
    const theta = (100 * Math.PI) / 180;
    expect(inner.radiusRe(theta, Math.PI / 2)).toBeGreaterThan(outer.radiusRe(theta, Math.PI / 2));
  });

  it("opens the funnel between the cusp latitudes of the two models", () => {
    // Lin's indentation is deeper and sits at a smaller zenith angle than
    // Nguyen's, so Lin dips inside the current sheet across a band that
    // straddles both cusp axes. That band is the drawn exterior cusp.
    const outer = magnetopauseEvaluator("nguyen2022", drivers)!;
    const inner = magnetopauseEvaluator("lin2010", drivers)!;
    const gapAt = (degrees: number, azimuth = 0) => {
      const theta = (degrees * Math.PI) / 180;
      return outer.radiusRe(theta, azimuth) - inner.radiusRe(theta, azimuth);
    };
    expect(gapAt(45)).toBeGreaterThan(0.5);
    expect(gapAt(55)).toBeGreaterThan(0.5);
    // Closed at both ends of the band.
    expect(gapAt(10)).toBeLessThan(0);
    expect(gapAt(90)).toBeLessThan(0.5);
    // And essentially nothing on the dawn-dusk meridian at the same angles.
    expect(gapAt(45, Math.PI / 2)).toBeLessThan(gapAt(45));
  });

  it("reports cusp proximity as 1 on the axis and 1/e one width away", () => {
    const parameters = nguyenBoundary(drivers)!;
    expect(nguyenCuspProximity(parameters.northCuspThetaRad, 0, parameters)).toBeCloseTo(1, 6);
    expect(
      nguyenCuspProximity(parameters.northCuspThetaRad + parameters.cuspWidthRad, 0, parameters),
    ).toBeCloseTo(Math.exp(-1), 6);
    // Nothing at the flank, where cos^2(azimuth) is zero.
    expect(nguyenCuspProximity(parameters.northCuspThetaRad, Math.PI / 2, parameters)).toBeCloseTo(0, 12);
  });

  it("shows Shue and the cusped models agreeing away from the cusps and not at them", () => {
    const shue = magnetopauseEvaluator("shue1998", drivers)!;
    const nguyen = magnetopauseEvaluator("nguyen2022", drivers)!;
    // Near the nose the three models are within a fraction of an Earth radius.
    expect(Math.abs(shue.subsolarRe - nguyen.subsolarRe)).toBeLessThan(0.5);
    // At the cusp they are more than an Earth radius apart, and the difference
    // is entirely a term Shue does not have.
    const theta = nguyenBoundary(drivers)!.northCuspThetaRad;
    expect(shue.radiusRe(theta, 0) - nguyen.radiusRe(theta, 0)).toBeGreaterThan(1);
    // And Shue itself is identical in every azimuth, by construction.
    expect(shue.radiusRe(theta, 0)).toBeCloseTo(shue.radiusRe(theta, Math.PI / 2), 12);
  });

  it("refuses to evaluate on drivers it cannot use", () => {
    for (const id of ["shue1998", "nguyen2022", "lin2010"] as const) {
      expect(magnetopauseEvaluator(id, { ...drivers, dynamicPressureNpa: 0 })).toBeNull();
      expect(magnetopauseEvaluator(id, { ...drivers, dipoleTiltRad: Number.NaN })).toBeNull();
      expect(magnetopauseEvaluator(id, { ...drivers, bzGsmNt: Number.NaN })).toBeNull();
    }
  });

  it("names its evidence class and its limitation on every model", () => {
    for (const id of ["shue1998", "nguyen2022", "lin2010"] as const) {
      const descriptor = MAGNETOPAUSE_MODELS[id];
      expect(descriptor.status).toBe("empirical");
      expect(descriptor.doi).toMatch(/^10\./);
      expect(descriptor.note.length).toBeGreaterThan(60);
    }
    expect(MAGNETOPAUSE_MODELS.shue1998.note).toMatch(/no cusps/i);
  });

  it("places the cusps on the noon meridian, not on the flanks", () => {
    // The azimuth convention is the single easiest thing to get backwards in
    // this file, and getting it backwards rotates both funnels 90 degrees onto
    // the dawn-dusk line, where they look plausible and are wrong.
    const evaluator = magnetopauseEvaluator("nguyen2022", drivers)!;
    const theta = nguyenBoundary(drivers)!.northCuspThetaRad;
    const north = magnetopausePointGsm(evaluator, theta, 0);
    const dusk = magnetopausePointGsm(evaluator, theta, Math.PI / 2);
    expect(north.zRe).toBeGreaterThan(0);
    expect(Math.abs(north.yRe)).toBeLessThan(1e-9);
    expect(dusk.yRe).toBeGreaterThan(0);
    expect(Math.abs(dusk.zRe)).toBeLessThan(1e-9);
    expect(north.radiusRe).toBeLessThan(dusk.radiusRe);
  });
});
