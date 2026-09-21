import { describe, expect, it } from "vitest";
import {
  CH_INFERENCE,
  ISS_REBOOST,
  KOREASAT5_EAST_WEST,
  MU_WGS72,
  STARLINK_SPIRAL,
  TERRA_COMBINED_SAMPLE_EVENT,
  annualCadenceCost,
  combinedFloor,
  eccentricityFloor,
  geoNorthSouthAnnualCost,
  geoSpeedMs,
  issReboostFloor,
  issSemiMajorAxisKm,
  planeFloor,
  spiralCost,
  tangentialFloor,
} from "../src/orbit-inference";
import { satelliteFundamentalsPageView } from "../src/satellite-fundamentals";

/**
 * Chapter 07 — inferring manoeuvres.
 *
 * Same contract as tests/satellite-fundamentals.test.ts: every figure printed
 * on the page is recomputed here from closed forms written out independently,
 * never by calling the module's own helper for both sides, and the rendered
 * strings are compared against those independent numbers.
 *
 * The GROUND-TRUTH inputs (the ISS event record, the KOREASAT 5 cluster) are
 * quoted from the published bundle of 4 September 2026. This suite pins the
 * page to those dated records deliberately: if someone refreshes the records,
 * the expected strings below must be refreshed with them, which is exactly
 * the two-sided update a dated snapshot needs.
 */

const page = satelliteFundamentalsPageView("inference");

describe("the lower-bound formulas, against independent closed forms", () => {
  // The textbook forms, written out rather than routed through the module.
  const n = (aKm: number) => Math.sqrt(MU_WGS72 / (aKm * aKm * aKm));

  it("prices an along-track burn at n·da/2", () => {
    // Gauss variational: da/dt = 2v/(n²a)·f_t → impulse form da = 2·dv/n.
    const a = 7000;
    const da = 1000; // metres
    expect(tangentialFloor(a, da)).toBeCloseTo(0.5 * n(a) * da, 12);
    // And symmetric in sign: the floor prices the magnitude.
    expect(tangentialFloor(a, -da)).toBeCloseTo(tangentialFloor(a, da), 12);
  });

  it("prices a plane change at 2·V·sin(di/2) with V at apogee", () => {
    const a = 42164.17;
    const e = 0.1;
    const di = 0.5;
    const rApogee = a * (1 + e);
    const vApogee = Math.sqrt(MU_WGS72 * (2 / rApogee - 1 / a)) * 1000;
    const expected = 2 * vApogee * Math.sin((di * Math.PI) / 180 / 2);
    expect(planeFloor(a, e, di)).toBeCloseTo(expected, 9);
    // For a circular orbit apogee speed IS circular speed.
    expect(planeFloor(a, 0, di)).toBeCloseTo(2 * Math.sqrt(MU_WGS72 / a) * 1000 * Math.sin((di * Math.PI) / 360), 9);
  });

  it("prices an eccentricity change at V·de/2", () => {
    const a = 42164.17;
    expect(eccentricityFloor(a, 2.5e-5)).toBeCloseTo(0.5 * Math.sqrt(MU_WGS72 / a) * 1000 * 2.5e-5, 12);
  });

  it("takes the larger in-plane figure, never the sum, and combines in quadrature", () => {
    expect(combinedFloor(3, 4, 0)).toBe(4);
    expect(combinedFloor(4, 3, 0)).toBe(4);
    expect(combinedFloor(3, 4, 12)).toBeCloseTo(Math.hypot(4, 12), 12);
    // TERRA on 12 Oct 2022 survives the final scan: larger, not sum.
    const { tangentialMs, eccentricityMs, planeMs, publishedTotalMs } = TERRA_COMBINED_SAMPLE_EVENT;
    expect(combinedFloor(tangentialMs, eccentricityMs, planeMs)).toBeCloseTo(publishedTotalMs, 4);
    expect(tangentialMs + eccentricityMs).toBeGreaterThan(publishedTotalMs);
    expect(page).toContain("TERRA on 12 Oct 2022");
    expect(page).toContain("1.4560 m/s");
    expect(page).toContain("1.1102 m/s");
    expect(page).toContain("2.5662");
  });
});

describe("the ISS worked example reproduces the published detection", () => {
  it("recovers the bundle's 1.527 m/s from the record's own inputs", () => {
    // Recomputed by hand: a = R + (h_p + h_a)/2, dv = n·da/2.
    const a = 6378.135 + (ISS_REBOOST.perigeeAltitudeKm + ISS_REBOOST.apogeeAltitudeKm) / 2;
    const dv = 0.5 * Math.sqrt(MU_WGS72 / (a * a * a)) * ISS_REBOOST.propulsiveDeltaAMetres;
    expect(issSemiMajorAxisKm()).toBeCloseTo(a, 9);
    expect(issReboostFloor()).toBeCloseTo(dv, 9);
    // The bundle published exactly 1.527 for this event.
    expect(issReboostFloor()).toBeCloseTo(1.527, 3);
  });

  it("stays under NASA's on-board figure, as a floor must", () => {
    expect(issReboostFloor()).toBeLessThan(ISS_REBOOST.nasaPublishedDvMs);
    // And within 1%: the credibility anchor the page claims.
    expect(issReboostFloor() / ISS_REBOOST.nasaPublishedDvMs).toBeGreaterThan(0.99);
  });

  it("prints those numbers on the page", () => {
    expect(page).toContain(issReboostFloor().toFixed(3));       // 1.527
    expect(page).toContain("1.54");                              // NASA's figure
    expect(page).toContain("2,709.6");                           // the drag-corrected step
    expect(page).toContain("74.4");                              // what drag was billed
  });
});

describe("the cadence worked example", () => {
  it("turns KOREASAT 5's rhythm into the printed annual budget", () => {
    const perYear = (KOREASAT5_EAST_WEST.medianDvMs * 365.25) / KOREASAT5_EAST_WEST.medianDaysBetween;
    expect(annualCadenceCost(KOREASAT5_EAST_WEST.medianDvMs, KOREASAT5_EAST_WEST.medianDaysBetween))
      .toBeCloseTo(perYear, 12);
    expect(perYear).toBeCloseTo(0.54, 2);
    expect(page).toContain(perYear.toFixed(2));
    expect(KOREASAT5_EAST_WEST.norad).toBe(29349);
    expect(KOREASAT5_EAST_WEST.cosparId).toBe("2006-034A");
    expect(KOREASAT5_EAST_WEST.count).toBe(70);
    expect(KOREASAT5_EAST_WEST.medianDvMs).toBe(0.0521);
    expect(KOREASAT5_EAST_WEST.medianDaysBetween).toBe(34.957);
    expect(KOREASAT5_EAST_WEST.dvSpreadMs).toBe(0.0125);
    expect(page).toContain("70 from Aug 2007 to Aug 2026");
    expect(page).toContain("six clustered corrections");
    expect(page).toContain("2.1454 m/s");
    expect(page).toContain("0.913°/yr");
  });

  it("puts the geostationary north-south scale where the literature puts it", () => {
    // Soop: cancelling 0.75–0.95°/yr of luni-solar drift ≈ 40–50 m/s per year.
    expect(geoSpeedMs()).toBeCloseTo(3074.7, 1);
    const annual = geoNorthSouthAnnualCost(0.85);
    expect(annual).toBeCloseTo(2 * 3074.7 * Math.sin((0.85 * Math.PI) / 360), 1);
    expect(annual).toBeGreaterThan(40);
    expect(annual).toBeLessThan(50);
    expect(page).toContain(annual.toFixed(1));
  });
});

describe("the low-thrust blind spot, on the published record", () => {
  it("prices a slow spiral as the difference in circular speed", () => {
    // A continuous along-track spiral has no coast, so there is no impulsive
    // transfer term: dv = |V1 - V2|. Written out here rather than routed
    // through the module for both sides of the comparison.
    const v = (aKm: number) => Math.sqrt(MU_WGS72 / aKm) * 1000;
    expect(spiralCost(STARLINK_SPIRAL.fromAKm, STARLINK_SPIRAL.toAKm))
      .toBeCloseTo(Math.abs(v(STARLINK_SPIRAL.fromAKm) - v(STARLINK_SPIRAL.toAKm)), 9);
    // Symmetric: climbing and descending the same shells cost the same floor.
    expect(spiralCost(STARLINK_SPIRAL.toAKm, STARLINK_SPIRAL.fromAKm))
      .toBeCloseTo(spiralCost(STARLINK_SPIRAL.fromAKm, STARLINK_SPIRAL.toAKm), 12);
  });

  it("prints the climb, its cost and the zero flags that came of it", () => {
    const cost = spiralCost(STARLINK_SPIRAL.fromAKm, STARLINK_SPIRAL.toAKm);
    expect(cost).toBeCloseTo(106.75, 1);
    expect(page).toContain(STARLINK_SPIRAL.name);
    expect(page).toContain(cost.toFixed(0));                       // 107 m/s
    expect(page).toContain(String(Math.round(STARLINK_SPIRAL.toAKm - STARLINK_SPIRAL.fromAKm)));
    expect(page).toContain("966");                                  // intervals
    expect(page).toContain("520.993");                              // observed days
    // The whole point of the example: a real 100 m/s climb, no events.
    expect(STARLINK_SPIRAL.eventsFlagged).toBe(0);
  });
});

describe("the chapter keeps its own honesty rules", () => {
  it("is registered as chapter 07 with the inference id", () => {
    expect(CH_INFERENCE.id).toBe("inference");
    expect(CH_INFERENCE.index).toBe("07");
  });

  it("dates every measured claim to its bundle", () => {
    // The chapter's one defence against rot: measured numbers carry the
    // bundle date, and the date appears wherever the counts do.
    expect(page.match(/4 September 2026/g)?.length ?? 0).toBeGreaterThanOrEqual(4);
  });

  it("never turns a detector-qualified word into confirmation", () => {
    // One lane may eventually earn "manoeuvre" while another remains at
    // candidate. Neither result may erase the inference boundary.
    expect(page).toContain("CANDIDATE");
    expect(page.toLowerCase()).toContain("false alarm");
    expect(page).toContain("the cause remains an inference");
    expect(page).toContain("the Δv remains a lower bound");
    expect(page).not.toMatch(/confirmed manoeuvre/i);
  });

  it("names the structural blind spots", () => {
    for (const miss of [
      "Continuous low thrust", "Small burns", "Storms mask thrust",
      "The newest changes are the ones we decline",
    ]) {
      expect(page).toContain(miss);
    }
  });

  it("does not leave low thrust looking unanswered", () => {
    // The pipeline answers this one with a sustained-rate lane rather than a
    // better step detector, and a limitations section that omitted that would
    // have been out of date the day it shipped. The answer must sit next to
    // the miss, and must keep the refusal that comes with it.
    expect(page).toContain("So the site asks a different question");
    expect(page).toContain("cannot put it back");
    expect(page).toContain("we cannot tell here");
  });

  it("names both blanks rather than averaging them into one figure", () => {
    // The cohort screen and the self-history screen measure different things
    // on different samples and disagree; a page that quoted only the flatter
    // number would be hiding which control did the work. Both must be on it.
    expect(page).toContain("2,314 of 98,707");
    // Refreshed 2026-09-08 from the published bundle
    // orbit-events-b3112145df7493d8, when the chapter snapshot was corrected:
    // it had been rendering GATE PASSED for a lane the bundle calls shut.
    expect(page).toContain("39,920 of 89,179,650");
    expect(page).toContain("23.443 per 1,000");
    expect(page).toContain("0.448 per 1,000");
    expect(page).toContain("190,877 / 62,566,722");
    expect(page).toContain("95% upper bound 0.452 per 1,000");
    expect(page).toContain("cohort κ = 8");
    expect(page).toContain("self-history κ = 32");
    expect(page).toContain("Its gate is closed");
    expect(page).toContain("Its gate passes");
    expect(page).toContain("cannot lend certainty to a cohort-only event");
  });

  it("pins the final positive control and removes the known miss", () => {
    expect(page).toContain("18 of 27");
    expect(page).toContain("1.093 vs 1.09");
    expect(page).not.toContain("21 of 27");
    expect(page).not.toContain("0.538 vs 0.50");
    expect(page).not.toContain("3 Sep 2025 reboost");
  });

  it("keeps calibration and node results explicitly historical", () => {
    expect(page).toContain("historical κ = 8 calibration");
    expect(page).toContain("not part of the current snapshot");
    expect(page).toContain("current complete-archive lanes below use cohort κ = 8 and self-history κ = 32");
  });

  it("says what the gates are applied to without pinning a channel count", () => {
    // This paragraph went stale once already, when the experimental node and
    // apse-line channels landed and the page still said three of six were screened.
    // It must describe the SHAPE of the answer -- five elements of shape and
    // orientation, one of phase that gets no channel -- and must not print a
    // count that a pipeline change can falsify.
    expect(page).toContain("What the gates are applied to");
    expect(page).toContain("argument of perigee");
    expect(page).toContain("node and apse-line channels were built and measured, but remain disabled");
    expect(page).toContain("cohort detector independently retains its node screen");
    expect(page).toContain("observed node change minus predicted J₂ drift");
    expect(page).toContain("63,190 passive intervals");
    expect(page).toContain("1.5 times the ordinary threshold");
    expect(page).not.toMatch(/Three elements of six/);
    expect(page).not.toMatch(/not yet screened/);
  });
});
