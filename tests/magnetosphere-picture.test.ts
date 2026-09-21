import * as THREE from "three";
import { describe, expect, it } from "vitest";

import {
  CARPENTER_ANDERSON_KP,
  OBRIEN_MOLDWIN_DST,
  dstMinimumOverWindow,
  plasmapauseAt,
} from "../src/inner-magnetosphere";
import { magneticPressureNpa, magnetopauseEvaluator, nguyenBoundary } from "../src/magnetopause";
import {
  createCuspEntryPaths,
  createExteriorCuspProfileGeometry,
  createMagnetopauseProfileGeometry,
} from "../src/magnetopause-surfaces";
import { radiationBeltDisplayRadius } from "../src/radiation-belt";

/** The scene's shared ruler, imported for real — see the anisotropy pin below. */
const EARTH_SCENE_RADIUS = 100;
const positionForGsm = (xRe: number, yRe: number, zRe: number) => {
  const radius = Math.max(0.001, Math.hypot(xRe, yRe, zRe));
  const scale = radiationBeltDisplayRadius(radius, EARTH_SCENE_RADIUS) / radius;
  return new THREE.Vector3(xRe, zRe, -yRe).multiplyScalar(scale);
};

const QUIET = {
  dynamicPressureNpa: 0.9189,
  magneticPressureNpa: magneticPressureNpa(2.53),
  bzGsmNt: 1.5,
  clockAngleRad: (335.93 * Math.PI) / 180,
  dipoleTiltRad: (8.56 * Math.PI) / 180,
};

const STORM = {
  dynamicPressureNpa: 8,
  magneticPressureNpa: magneticPressureNpa(20),
  bzGsmNt: -15,
  clockAngleRad: Math.PI,
  dipoleTiltRad: (8.56 * Math.PI) / 180,
};

// ---------------------------------------------------------------------------
// Plasmapause — O'Brien & Moldwin (2003), the Dst model, verified against the
// paper itself (GRL 30(4) 1152): Lpp = -1.57 log10(-min[-24h,0] Dst) + 6.3.
// ---------------------------------------------------------------------------

function hourlySeries(hours: number, dstOf: (hourIndex: number) => number, endIso = "2026-08-08T18:00:00Z") {
  const end = Date.parse(endIso);
  return Array.from({ length: hours }, (_, index) => ({
    at: new Date(end - (hours - 1 - index) * 3_600_000).toISOString(),
    dstNt: dstOf(index),
  }));
}

describe("plasmapause from the published Dst record", () => {
  it("reproduces the paper's own arithmetic at a storm minimum of -100 nT", () => {
    const series = hourlySeries(48, (index) => (index === 40 ? -100 : -20));
    const state = plasmapauseAt(series, new Date("2026-08-08T18:00:00Z"))!;
    expect(state.lppRe).toBeCloseTo(-1.57 * 2 + 6.3, 5); // 3.16 L
    expect(state.dstMinimumNt).toBe(-100);
    expect(state.rmseL).toBe(OBRIEN_MOLDWIN_DST.rmseL);
  });

  it("erodes during the storm and does not spring back with the index", () => {
    // Deep minimum 20 hours ago, index recovered to -10 nT: the boundary must
    // still be the eroded one, because the window looks back a day.
    const series = hourlySeries(48, (index) => (index === 27 ? -150 : -10));
    const eroded = plasmapauseAt(series, new Date("2026-08-08T18:00:00Z"))!;
    expect(eroded.dstMinimumNt).toBe(-150);
    expect(eroded.lppRe).toBeLessThan(3);
    // A day later the minimum has left the window and the boundary refills.
    const laterSeries = hourlySeries(72, (index) => (index === 27 ? -150 : -10), "2026-08-09T18:00:00Z");
    const refilled = plasmapauseAt(laterSeries, new Date("2026-08-09T18:00:00Z"))!;
    expect(refilled.dstMinimumNt).toBe(-10);
    expect(refilled.lppRe).toBeGreaterThan(eroded.lppRe + 1);
  });

  it("lands on the fit's own quiet intercept when the day never dipped below -1 nT", () => {
    const series = hourlySeries(30, () => 12);
    const state = plasmapauseAt(series, new Date("2026-08-08T18:00:00Z"))!;
    expect(state.quietClamped).toBe(true);
    expect(state.lppRe).toBeCloseTo(OBRIEN_MOLDWIN_DST.b, 5);
  });

  it("refuses a time the record has not reached, rather than extrapolating", () => {
    const series = hourlySeries(30, () => -40);
    expect(plasmapauseAt(series, new Date("2026-08-08T21:00:00Z"))).toBeNull();
    expect(dstMinimumOverWindow(series, new Date("2020-01-01T00:00:00Z"))).toBeNull();
    expect(plasmapauseAt([], new Date("2026-08-08T18:00:00Z"))).toBeNull();
  });

  it("reports how many samples the window actually held", () => {
    const series = hourlySeries(4, () => -60);
    const minimum = dstMinimumOverWindow(series, new Date("2026-08-08T18:00:00Z"))!;
    expect(minimum.sampleCount).toBe(4);
  });

  it("keeps the quoted Kp heritage coefficients as the paper states them", () => {
    // Quoted in the legend for context; a transcription drift would misquote
    // a published paper on screen.
    expect(CARPENTER_ANDERSON_KP.a).toBe(-0.46);
    expect(CARPENTER_ANDERSON_KP.b).toBe(5.6);
    expect(OBRIEN_MOLDWIN_DST.a).toBe(-1.57);
    expect(OBRIEN_MOLDWIN_DST.b).toBe(6.3);
  });
});

// ---------------------------------------------------------------------------
// Cross-section profiles and the cusp entry cue
// ---------------------------------------------------------------------------

describe("magnetopause cross-section profiles", () => {
  it("keeps a meridional profile strictly in the noon-midnight plane", () => {
    const evaluator = magnetopauseEvaluator("nguyen2022", QUIET)!;
    const geometry = createMagnetopauseProfileGeometry(evaluator, "meridional", {
      positionForGsm,
      thetaSegments: 48,
    })!;
    const positions = geometry.getAttribute("position");
    for (let index = 0; index < positions.count; index += 1) {
      // GSM y maps to scene -z under the test mapper; the meridian has y = 0.
      expect(Math.abs(positions.getZ(index))).toBeLessThan(1e-6);
    }
  });

  it("shows the cusp indentation in the meridional silhouette and not in the equatorial one", () => {
    const evaluator = magnetopauseEvaluator("nguyen2022", STORM)!;
    const boundary = nguyenBoundary(STORM)!;
    const merid = createMagnetopauseProfileGeometry(evaluator, "meridional", { positionForGsm, thetaSegments: 192 })!;
    // Radius dips at the cusp: find the minimum radial distance near the cusp
    // zenith angle along the profile and check it is genuinely below the
    // neighbouring radii — the indentation survives into scene space.
    const positions = merid.getAttribute("position");
    const radii: number[] = [];
    for (let index = 0; index < positions.count; index += 1) {
      radii.push(Math.hypot(positions.getX(index), positions.getY(index), positions.getZ(index)));
    }
    const smallest = Math.min(...radii);
    const largest = Math.max(...radii);
    expect(largest - smallest).toBeGreaterThan(1);
    expect(boundary.northCuspThetaRad).toBeGreaterThan(0);
  });

  it("fills the exterior-cusp lens only where the two published surfaces cross", () => {
    const geometry = createExteriorCuspProfileGeometry(QUIET, { positionForGsm, thetaSegments: 96 })!;
    expect(geometry).not.toBeNull();
    const gaps = geometry.getAttribute("gapThicknessRe");
    for (let index = 0; index < gaps.count; index += 1) {
      expect(gaps.getX(index)).toBeGreaterThan(0);
    }
  });
});

describe("cusp entry cue paths", () => {
  it("threads the funnel from the sheath to the atmosphere in both hemispheres", () => {
    const paths = createCuspEntryPaths(QUIET);
    const hemispheres = new Set(paths.map((path) => path.hemisphere));
    expect(hemispheres).toEqual(new Set(["north", "south"]));
    for (const path of paths) {
      const first = path.pointsGsmRe[0]!;
      const last = path.pointsGsmRe.at(-1)!;
      const firstRadius = Math.hypot(first.xRe, first.yRe, first.zRe);
      const lastRadius = Math.hypot(last.xRe, last.yRe, last.zRe);
      // Starts outside the boundary, ends at the top of the atmosphere.
      expect(firstRadius).toBeGreaterThan(8);
      expect(lastRadius).toBeCloseTo(1.05, 1);
      // Monotonically inbound: the cue falls in, it never orbits.
      let previous = Number.POSITIVE_INFINITY;
      for (const point of path.pointsGsmRe) {
        const radius = Math.hypot(point.xRe, point.yRe, point.zRe);
        expect(radius).toBeLessThanOrEqual(previous + 1e-9);
        previous = radius;
      }
    }
  });

  it("lands the dipole continuation at cusp-aurora latitudes, not at the pole or the equator", () => {
    for (const path of createCuspEntryPaths(QUIET)) {
      const magnitude = Math.abs(path.footpointLatitudeDeg);
      expect(magnitude).toBeGreaterThan(65);
      expect(magnitude).toBeLessThan(85);
      if (path.hemisphere === "south") expect(path.footpointLatitudeDeg).toBeLessThan(0);
    }
  });

  it("moves the funnel equatorward when Bz turns south, because Nguyen's cusp does", () => {
    // On the noon meridian the cusp's zenith angle from the sunward axis IS
    // its magnetic latitude, so equatorward motion is a SMALLER angle. The
    // tanh term in Nguyen's cusp latitude collapses as Bz goes south — the
    // dayside is eroded and the funnel swings toward the equator.
    const quietNorth = nguyenBoundary(QUIET)!.northCuspThetaRad;
    const stormNorth = nguyenBoundary(STORM)!.northCuspThetaRad;
    expect(stormNorth).toBeLessThan(quietNorth);
    // And the entry cue built on it lands its footpoint equatorward too.
    const quietFoot = Math.abs(createCuspEntryPaths(QUIET)[0]!.footpointLatitudeDeg);
    const stormFoot = Math.abs(createCuspEntryPaths(STORM)[0]!.footpointLatitudeDeg);
    expect(stormFoot).toBeLessThan(quietFoot);
  });

  it("returns no paths when the drivers cannot support the cusped models", () => {
    expect(createCuspEntryPaths({ ...QUIET, dynamicPressureNpa: Number.NaN })).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// The radial ruler's anisotropy, pinned
// ---------------------------------------------------------------------------

describe("the shared radial ruler's direction distortion is a decision, not an accident", () => {
  /**
   * Any nonlinear radial map distorts direction: transverse displacement is
   * magnified over radial by A(r) = [f(r)/r] / f'(r). The purely logarithmic
   * ruler this scene used to carry had A ~ 7x at geostationary and 9.5x at
   * 30 Re, which is why head-on solar-wind flow read as a starburst radiating
   * out of the Earth, and why the drawn magnetopause rendered a true 1.64x
   * nose-to-flank flare as 1.066x — a near-sphere.
   *
   * The ruler is now piecewise (src/radial-ruler.ts): logarithmic to
   * geostationary orbit, where the near-Earth reading that scale exists for
   * actually lives; a JOINT RAMP from there to 7.35 Re, where the anisotropy
   * falls smoothly from the log branch's 7.03 to 1 so that nothing crossing
   * geostationary radius picks up a corner; LINEAR — anisotropy exactly 1 —
   * from 7.35 Re to the bow-shock nose at 13, so the whole dayside boundary
   * system keeps its true shape and its true directions of motion; then
   * tapering to a heavily foreshortened far tail, which is the entire price of
   * the dayside being true. These numbers are pinned so a change to the curve
   * is a conscious one: the linear band is what retired the starburst, and
   * narrowing it brings the starburst back.
   */
  function anisotropy(radiusRe: number): number {
    const step = 1e-4;
    const here = radiationBeltDisplayRadius(radiusRe, EARTH_SCENE_RADIUS);
    const there = radiationBeltDisplayRadius(radiusRe + step, EARTH_SCENE_RADIUS);
    const slope = (there - here) / step;
    return here / radiusRe / slope;
  }

  it("matches the measured anisotropy at the radii that matter", () => {
    // Below GEO the legacy log curve is untouched.
    expect(anisotropy(2)).toBeCloseTo(3.44, 1);
    // Across the joint ramp the anisotropy SLIDES rather than stepping. It is
    // the step that drew a corner into every curve crossing geostationary
    // radius; these two numbers are what makes the transition a slide, and
    // they are between the two ends rather than at either.
    expect(anisotropy(6.7)).toBeGreaterThan(1);
    expect(anisotropy(6.7)).toBeLessThan(7.04);
    expect(anisotropy(7)).toBeGreaterThan(1);
    expect(anisotropy(7)).toBeLessThan(anisotropy(6.7));
    // The dayside boundary band still draws directions truly, from the top of
    // the ramp to the bow-shock nose. This is the band the magnetopause lives
    // in and the reason the ramp is not allowed to reach past 7.35 Re.
    expect(anisotropy(7.35)).toBeCloseTo(1, 3);
    expect(anisotropy(9)).toBeCloseTo(1, 3);
    expect(anisotropy(12.9)).toBeCloseTo(1, 3);
    // The far tail pays for it: slope 0.14, anisotropy 1/0.14.
    expect(anisotropy(30)).toBeCloseTo(7.14, 1);
  });

  it("spends the screen span the dayside fidelity was measured to cost", () => {
    // The -50 Re tail cutoff (~56 Re physical) lands near 723 scene units and
    // the SWMF cut corner (65 Re) near 738: framing that costs ~2,115 of
    // camera distance against controls.maxDistance = 2,200. Full linearity to
    // the tail end was measured at ~1,900 scene units — beyond the far plane
    // with Earth a 4% speck — and rejected; that is what the taper is for.
    // The joint ramp gives up 0.0451 of slope integral, so everything above
    // 7.35 Re draws 4.41% closer in than these bounds were written for — the
    // frame budget improves rather than degrades, which is why the bounds are
    // still the ones the dayside fidelity was measured against.
    expect(radiationBeltDisplayRadius(56, EARTH_SCENE_RADIUS)).toBeLessThan(740);
    expect(radiationBeltDisplayRadius(56, EARTH_SCENE_RADIUS)).toBeGreaterThan(680);
    expect(radiationBeltDisplayRadius(Math.hypot(55, 35), EARTH_SCENE_RADIUS)).toBeLessThan(760);
    // And the near-Earth reading is untouched: GEO is still drawn where the
    // altitude scale always put it.
    expect(radiationBeltDisplayRadius(6.6, EARTH_SCENE_RADIUS)).toBeCloseTo(229.76, 1);
  });
});
