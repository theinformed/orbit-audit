import { describe, expect, it } from "vitest";

import explorerSource from "../src/main.ts?raw";

import {
  buildStreamlineTransit,
  buildTransitTables,
  illustrativeUpstreamDomain,
  streamlineXAtFraction,
  teachingFlowSpeedFactor,
  teachingFlowVelocityFactors,
  transitBandIndex,
} from "../src/solar-input-visuals";

/**
 * The owner's opening complaint on 2026-08-12 was that the wind "still doesn't
 * travel the right way… just mostly uniform flow". It was: position along the
 * Sun–Earth line was `upstreamStart − progress × span`, one identical rate for
 * every tracer everywhere, so nothing slowed at the obstacle, nothing
 * stagnated at the nose and nothing accelerated down the flanks.
 *
 * These are the three numbers that say the flow is a flow. They are the
 * classical potential-flow-past-a-sphere values, and they are checked against
 * the arithmetic rather than against a previous run of this code.
 */
describe("the local speed of the teaching flow", () => {
  const obstacle = 10;

  it("stagnates at the nose, where the wind meets the obstacle head on", () => {
    expect(teachingFlowSpeedFactor(obstacle, 0, 0, obstacle)).toBeCloseTo(0, 6);
  });

  /**
   * 3/2 U at the flank is the classical result and the reason the flanks are
   * where the wind is fastest — the flow has to get around the obstacle in the
   * same time, so it speeds up to do it.
   */
  it("reaches three halves of the free-stream speed at the flank", () => {
    expect(teachingFlowSpeedFactor(0, obstacle, 0, obstacle)).toBeCloseTo(1.5, 6);
    expect(teachingFlowSpeedFactor(0, 0, obstacle, obstacle)).toBeCloseTo(1.5, 6);
  });

  it("returns to the free-stream speed far upstream, where the obstacle is not felt", () => {
    expect(teachingFlowSpeedFactor(400, 0, 0, obstacle)).toBeCloseTo(1, 3);
  });

  /**
   * The whole profile, not just its endpoints: approaching the nose along the
   * Sun–Earth line the wind must slow monotonically. A picture that only got
   * the endpoints right would still show the wind arriving at full speed and
   * stopping dead.
   */
  it("slows monotonically along the Sun–Earth line as it approaches the nose", () => {
    const speeds = [40, 30, 22, 16, 13, 11.5, 10.5].map((xRe) => teachingFlowSpeedFactor(xRe, 0, 0, obstacle));
    for (let index = 1; index < speeds.length; index += 1) {
      expect(speeds[index]!).toBeLessThan(speeds[index - 1]!);
    }
    expect(speeds.at(-1)!).toBeLessThan(0.3);
  });

  it("reports no flow inside the obstacle, which the position solve cannot reach anyway", () => {
    expect(teachingFlowSpeedFactor(2, 0, 0, obstacle)).toBe(0);
  });

  /**
   * The axial component is what the march is parameterised by, and it is NOT
   * the speed times the cosine of the position's polar angle — the velocity is
   * not radial. Writing it that way (the first version of this code did) zeroes
   * the FLANK, where the flow is fastest, and would have piled tracers up in
   * exactly the place they should be racing through. At the nose, at the flank
   * and far upstream the flow is along x, so the two agree there and only the
   * angles between them tell the versions apart.
   */
  it("carries a flank tracer downstream fastest, not slowest", () => {
    const nose = teachingFlowVelocityFactors(obstacle, 0, 0, obstacle);
    const flank = teachingFlowVelocityFactors(0, obstacle, 0, obstacle);
    const upstream = teachingFlowVelocityFactors(400, 0, 0, obstacle);
    expect(nose.axial).toBeCloseTo(0, 6);
    expect(flank.axial).toBeCloseTo(1.5, 6);
    expect(upstream.axial).toBeCloseTo(1, 3);
    // The bug this pins: a radial reading of the velocity gives the flank
    // zero axial speed, because the position there is perpendicular to x.
    expect(flank.axial).toBeGreaterThan(flank.speed * 0.9);
  });

  it("agrees with the speed wherever the flow is along the Sun–Earth line", () => {
    for (const [x, y] of [[obstacle, 0], [0, obstacle], [400, 0]] as const) {
      const { speed, axial } = teachingFlowVelocityFactors(x, y, 0, obstacle);
      expect(axial).toBeCloseTo(speed, 6);
    }
  });
});

describe("the transit table that turns the march into a flow", () => {
  const domain = illustrativeUpstreamDomain({ magnetopauseStandoffRe: 10, upstreamStartRe: 32 });

  it("runs from the upstream edge to the downstream edge, in order", () => {
    const table = buildStreamlineTransit(4, 0, domain);
    expect(table.xRe[0]).toBeCloseTo(domain.upstreamStartRe, 6);
    expect(table.xRe.at(-1)).toBeCloseTo(domain.downstreamEndRe, 6);
    expect(table.fraction[0]).toBe(0);
    expect(table.fraction.at(-1)).toBeCloseTo(1, 6);
    for (let index = 1; index < table.fraction.length; index += 1) {
      expect(table.fraction[index]!).toBeGreaterThanOrEqual(table.fraction[index - 1]!);
    }
  });

  /**
   * How far the timing departs from the uniform march, in EARTH RADII.
   *
   * This used to be normalised by the domain span, and that stopped being the
   * right yardstick on 2026-08-20 when the domain was extended from the
   * terminator down to -30 Re so the wind would visibly flow past the planet.
   * The stagnation region did not change and neither did the crawl through it,
   * but the same physical distortion divided by a domain twice as long came out
   * as half the fraction — the metric moved, not the property.
   *
   * Measured across that change: the near-nose streamline's worst departure was
   * 3.2 Re on the 32 Re domain and is 4.6 Re on the 62 Re one. It got LARGER,
   * because the tracer now also has the whole downstream run to fall behind on.
   * Earth radii is what a reader sees, so Earth radii is what this measures.
   */
  const departureFromUniform = (table: ReturnType<typeof buildStreamlineTransit>) => {
    const span = domain.upstreamStartRe - domain.downstreamEndRe;
    let worst = 0;
    for (let step = 0; step <= 100; step += 1) {
      const progress = step / 100;
      const uniform = domain.upstreamStartRe - progress * span;
      worst = Math.max(worst, Math.abs(streamlineXAtFraction(table, progress) - uniform));
    }
    return worst;
  };

  /**
   * The property that fixes the picture. A tracer aimed near the nose spends
   * so much of its clock crawling through the stagnation region that its
   * progress→position mapping bends a long way from the straight line the old
   * code drew. Three Earth radii is a departure nobody can miss on screen — and
   * the old uniform march had a departure of exactly zero, by construction, for
   * every tracer everywhere.
   */
  it("bends a near-nose streamline's timing far away from the uniform march", () => {
    expect(departureFromUniform(buildStreamlineTransit(0.5, 0, domain))).toBeGreaterThan(3);
  });

  /**
   * And the effect is differential rather than a global slowdown: a streamline
   * that passes well clear of the obstacle barely notices it. That contrast is
   * what makes the flow read as flow — tracers bunching ahead of the nose while
   * others sail past — instead of everything simply moving slower.
   */
  it("leaves a distant streamline close to the uniform march", () => {
    const near = departureFromUniform(buildStreamlineTransit(0.5, 0, domain));
    const far = departureFromUniform(buildStreamlineTransit(30, 0, domain));
    expect(far).toBeLessThan(near / 2);
  });

  it("interpolates inside the table and clamps outside it", () => {
    const table = buildStreamlineTransit(6, 0, domain);
    expect(streamlineXAtFraction(table, -1)).toBeCloseTo(domain.upstreamStartRe, 6);
    expect(streamlineXAtFraction(table, 2)).toBeCloseTo(domain.downstreamEndRe, 6);
    const quarter = streamlineXAtFraction(table, 0.25);
    const half = streamlineXAtFraction(table, 0.5);
    expect(quarter).toBeGreaterThan(half);
  });

  /**
   * Purity, which is not incidental here: a consumer of this clock that
   * accumulated instead of reading absolute time shipped to production and
   * made the cusp coupling invisible. The lookup must give the same answer for
   * the same fraction, every time.
   */
  it("is a pure function of the fraction it is given", () => {
    const table = buildStreamlineTransit(3, 0, domain);
    expect(streamlineXAtFraction(table, 0.42)).toBe(streamlineXAtFraction(table, 0.42));
  });
});

describe("sharing tables across streamlines", () => {
  const domain = illustrativeUpstreamDomain({ magnetopauseStandoffRe: 10 });

  it("builds one table per band and keeps every impact parameter inside the range", () => {
    const tables = buildTransitTables(domain, 13, 24);
    expect(tables).toHaveLength(24);
    expect(transitBandIndex(0, 13, 24)).toBe(0);
    expect(transitBandIndex(13, 13, 24)).toBe(23);
    expect(transitBandIndex(6.5, 13, 24)).toBe(12);
    // A tracer beyond the nominal extent still lands in a real band rather
    // than indexing off the end of the array.
    expect(transitBandIndex(400, 13, 24)).toBe(23);
    expect(transitBandIndex(-4, 13, 24)).toBe(0);
  });

  it("bends the nearest-axis band's timing most, and the outermost band's least", () => {
    const tables = buildTransitTables(domain, 13, 24);
    const span = domain.upstreamStartRe - domain.downstreamEndRe;
    const departure = (table: (typeof tables)[number]) => {
      let worst = 0;
      for (let step = 0; step <= 100; step += 1) {
        const progress = step / 100;
        worst = Math.max(
          worst,
          Math.abs(streamlineXAtFraction(table, progress) - (domain.upstreamStartRe - progress * span)) / span,
        );
      }
      return worst;
    };
    expect(departure(tables[0]!)).toBeGreaterThan(departure(tables.at(-1)!));
  });
});


describe("the solar wind arrives as a front, not a spray", () => {
  /**
   * Handoff 4.5. In Sean's screenshot the tracers fan out from a point off the
   * lower-left corner, "like spray from a nozzle". They should arrive as a
   * parallel front: the Sun is 150 million km away.
   *
   * The seeding is already right — every tracer is released on a flat plane at
   * the upstream start and marched along x — so what bends them is the shared
   * compressed radial ruler, which is deliberate and is used by every other
   * layer. Undoing it for this layer alone would put the wind on a different
   * scale from the boundary it is hitting.
   *
   * So the card says so, and points at the true-distance scale, where the
   * ruler is linear and the front is undistorted. These tests pin that the
   * explanation exists and is honest in both scales.
   */
  it("releases every tracer from the same upstream plane", () => {
    // The claim the card makes. If seeding ever became spherical the fan would
    // be real, and this would fail rather than the prose quietly becoming a lie.
    const domain = illustrativeUpstreamDomain({ magnetopauseStandoffRe: 10 });
    for (const [y, z] of [[0, 0], [3, 0], [0, -4], [5, 5]] as const) {
      const table = buildStreamlineTransit(y, z, domain, 32);
      expect(table.xRe[0]).toBeCloseTo(domain.upstreamStartRe, 9);
    }
  });

  it("says the front is parallel and names the cause of the fan", () => {
    const source = explorerSource;
    expect(source).toContain("PARALLEL FRONT");
    expect(source).toContain("compressed distance scale bending straight paths");
    expect(source).toContain("switch the distance scale to true distance");
  });

  it("drops the caveat when the scale is already undistorted", () => {
    // On true distance the ruler is linear, so the fan is genuinely gone and
    // telling a reader to go and fix it would be nonsense.
    const source = explorerSource;
    expect(source).toContain("on this true-distance scale that is what you see");
  });
});
