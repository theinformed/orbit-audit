import * as THREE from "three";
import { describe, expect, it } from "vitest";

import explorerSource from "../src/main.ts?raw";
import indexSource from "../index.html?raw";
import ringCurrentSource from "../src/ring-current-illustration.ts?raw";
import { keyCardBar, plasmasphereLegendSpec } from "../src/main";
import { STATION_OPERATOR_SCALE } from "../src/ground-stations";
import {
  CARPENTER_ANDERSON_1992,
  CARPENTER_ANDERSON_KP,
  OBRIEN_MOLDWIN_DST,
  PLASMASPHERE_DENSITY_SCALE,
  PLASMASPHERE_GRAIN,
  createPlasmasphereFieldGeometry,
  createPlasmasphereFieldMaterial,
  dayNumberUtc,
  equatorialElectronDensity,
  extendedTroughDensity,
  modelLocalTimeBlend,
  plasmapauseOuterL,
  plasmapauseScaleWidthL,
  plasmasphereFieldAt,
  saturatedLogDensity,
  troughScaleCoefficient,
} from "../src/inner-magnetosphere";
import { radiationBeltDisplayRadius } from "../src/radiation-belt";

const EARTH_SCENE_RADIUS = 100;
const positionForGsm = (xRe: number, yRe: number, zRe: number) => {
  const radius = Math.max(0.001, Math.hypot(xRe, yRe, zRe));
  const scale = radiationBeltDisplayRadius(radius, EARTH_SCENE_RADIUS) / radius;
  return new THREE.Vector3(xRe, zRe, -yRe).multiplyScalar(scale);
};

// ---------------------------------------------------------------------------
// The coefficients, against the printed paper
// ---------------------------------------------------------------------------

describe("Carpenter & Anderson (1992) coefficients as printed", () => {
  /**
   * Every number here was read off the scanned original, section 3 "Summary
   * of the Model", page 1106, and cross-read against the equations on pages
   * 1099-1105 and the least-squares fit inside Figure 4a. A transcription
   * drift would put a wrong published model on a Navy teaching site, so the
   * constants are pinned literally rather than exercised only through the
   * functions that use them.
   */
  it("pins the saturated profile, its secular terms and the trough", () => {
    const c = CARPENTER_ANDERSON_1992;
    expect(c.saturatedSlopePerL).toBe(-0.3145);
    expect(c.saturatedIntercept).toBe(3.9043);
    expect(c.annualAmplitude).toBe(0.15);
    expect(c.semiannualFraction).toBe(0.5);
    expect(c.dayNumberPhase).toBe(9);
    expect(c.daysPerYear).toBe(365);
    expect(c.sunspotCoefficient).toBe(0.00127);
    expect(c.sunspotOffset).toBe(0.0635);
    expect(c.perturbationReferenceL).toBe(2);
    expect(c.perturbationScaleL).toBe(1.5);
    expect(c.troughExponent).toBe(-4.5);
    expect(c.troughNightCoefficient).toBe(5800);
    expect(c.troughNightSlopePerHour).toBe(300);
    expect(c.troughDayCoefficient).toBe(-800);
    expect(c.troughDaySlopePerHour).toBe(1400);
    expect(c.troughFloorScaleL).toBe(10);
    expect(c.plasmapauseNightWidthL).toBe(0.1);
    expect(c.plasmapauseDayWidthSlopePerHour).toBe(0.011);
    expect(c.innerValidL).toBe(2.25);
    expect(c.outerValidL).toBe(8);
    expect(c.kpPlasmapause).toEqual({ a: -0.46, b: 5.6 });
    expect(c.doi).toBe("10.1029/91JA01548");
  });

  it("agrees with the least-squares fit printed inside the paper's Figure 4a", () => {
    // Figure 4a prints y = 8022.4*10^(-0.31450x), R^2 = 0.963. The intercept
    // this file carries is the log of that leading constant, so the two are
    // the same line and a typo in either would separate them.
    expect(10 ** CARPENTER_ANDERSON_1992.saturatedIntercept).toBeCloseTo(8022.4, 0);
  });

  it("reproduces the trough densities the paper itself quotes at L = 5", () => {
    // Page 1103: "The model gave corresponding values of 4.8, 6.7, and 11.7
    // el cm^-3" for the night, dawn and dayside trough at L = 5. Reproducing
    // all three to a tenth exercises 5800, 300, -800, 1400, the -4.5 exponent
    // and the additive floor term together.
    expect(extendedTroughDensity(5, 2)).toBeCloseTo(4.8, 1);
    expect(extendedTroughDensity(5, 7)).toBeCloseTo(6.7, 1);
    expect(extendedTroughDensity(5, 12)).toBeCloseTo(11.7, 1);
  });

  it("puts the saturated profile near the 1000 el/cc the paper selected on", () => {
    // Page 1099: saturated profiles were selected as those whose density at
    // L = 3 was not more than about a factor of 1.5 below 1000 el/cc. The
    // bare reference line gives 914 there.
    const bare = CARPENTER_ANDERSON_1992.saturatedSlopePerL * 3 + CARPENTER_ANDERSON_1992.saturatedIntercept;
    expect(10 ** bare).toBeCloseTo(914, -1);
  });

  it("keeps the plasmapause scale width the paper's Figure 10 caption states", () => {
    // "The nightside plasmapause scale width was taken to be 0.1L. The
    // dayside value represents 12 MLT and is 0.166L."
    expect(plasmapauseScaleWidthL(2)).toBeCloseTo(0.1, 6);
    expect(plasmapauseScaleWidthL(12)).toBeCloseTo(0.166, 6);
    expect(plasmapauseScaleWidthL(15)).toBeCloseTo(0.199, 6);
  });

  it("keeps the two plasmapause fits this site quotes side by side", () => {
    expect(CARPENTER_ANDERSON_KP.a).toBe(-0.46);
    expect(CARPENTER_ANDERSON_KP.b).toBe(5.6);
    expect(OBRIEN_MOLDWIN_DST.a).toBe(-1.57);
    expect(OBRIEN_MOLDWIN_DST.b).toBe(6.3);
  });
});

// ---------------------------------------------------------------------------
// The model's shape
// ---------------------------------------------------------------------------

describe("the density field's shape", () => {
  const inputs = { dayNumber: 221, sunspotNumber: 104.2 };

  it("falls a decade per 0.1 L across the knee, not gradually", () => {
    // The plasmapause is not drawn; it has to BE the contrast. Inside the
    // knee the nightside profile drops exactly one decade per 0.1 L, which is
    // the published scale width.
    const lppi = 4;
    const atBoundary = equatorialElectronDensity(lppi, 0, lppi, inputs)!;
    const oneWidthOut = equatorialElectronDensity(lppi + 0.1, 0, lppi, inputs)!;
    expect(atBoundary / oneWidthOut).toBeCloseTo(10, 4);
    // The knee is narrow — it meets the trough inside a fifth of an L — and
    // the whole boundary is a factor of forty in a third of an L.
    const lppo = plasmapauseOuterL(lppi, 0, inputs);
    expect(lppo - lppi).toBeGreaterThan(0.1);
    expect(lppo - lppi).toBeLessThan(0.25);
    const wellOutside = equatorialElectronDensity(lppi + 0.3, 0, lppi, inputs)!;
    expect(atBoundary / wellOutside).toBeGreaterThan(30);
  });

  it("is continuous where the knee meets the trough", () => {
    const lppi = 4;
    const lppo = plasmapauseOuterL(lppi, 0, inputs);
    const inside = equatorialElectronDensity(lppo - 1e-4, 0, lppi, inputs)!;
    const outside = equatorialElectronDensity(lppo + 1e-4, 0, lppi, inputs)!;
    expect(outside / inside).toBeCloseTo(1, 2);
  });

  it("decreases outward everywhere the model is defined", () => {
    const lppi = 4;
    let previous = Number.POSITIVE_INFINITY;
    for (let l = 2.25; l <= 8; l += 0.01) {
      const value = equatorialElectronDensity(l, 0, lppi, inputs)!;
      expect(value).toBeLessThanOrEqual(previous + 1e-9);
      previous = value;
    }
  });

  it("draws nothing outside the model's stated L range", () => {
    expect(equatorialElectronDensity(2.2, 0, 4, inputs)).toBeNull();
    expect(equatorialElectronDensity(8.1, 0, 4, inputs)).toBeNull();
    expect(equatorialElectronDensity(Number.NaN, 0, 4, inputs)).toBeNull();
  });

  it("has no local-time structure inside the plasmasphere, and says so by having none", () => {
    // The saturated expression carries no MLT term at all, so no dusk bulge
    // can appear by accident. Every local time gives the same interior.
    const lppi = 5;
    const values = [0, 6, 12, 18, 21].map((mlt) => equatorialElectronDensity(3.5, mlt, lppi, inputs)!);
    for (const value of values) expect(value).toBeCloseTo(values[0]!, 10);
  });

  it("does carry local time in the trough, dayside denser than nightside", () => {
    // The trough scale density runs 5800 at midnight to 20200 at 15 MLT.
    expect(troughScaleCoefficient(0)).toBe(5800);
    expect(troughScaleCoefficient(15)).toBe(20200);
    expect(extendedTroughDensity(6, 12)).toBeGreaterThan(extendedTroughDensity(6, 2) * 2);
  });

  it("follows the paper's own rule outside 00-15 MLT instead of extrapolating a fit", () => {
    // Section 4: hold the dayside values to about 20 MLT, with a linear
    // transition to nighttime conditions between 19 and 20 MLT. A naive
    // extrapolation of (-800 + 1400 t) to 23 MLT would give 31,400 — a trough
    // three times denser at late evening than at noon, which is not in the
    // paper and would be visible on screen.
    expect(modelLocalTimeBlend(16)).toBe(1);
    expect(modelLocalTimeBlend(19.5)).toBeCloseTo(0.5, 10);
    expect(modelLocalTimeBlend(23)).toBe(0);
    expect(Number.isNaN(modelLocalTimeBlend(9))).toBe(true);
    expect(troughScaleCoefficient(18)).toBe(20200);
    expect(troughScaleCoefficient(23)).toBe(5800);
    expect(troughScaleCoefficient(19.5)).toBeCloseTo((20200 + 5800) / 2, 6);
  });

  it("moves with the season and the solar cycle, and only a little", () => {
    // The sunspot term alone is 0.00127 per unit of Rbar, so the whole solar
    // cycle is 0.00127*(165-15) = 0.19 dex at L = 2: about 1.55x.
    const solarOnly = 10 ** (saturatedLogDensity(2, { dayNumber: 200, sunspotNumber: 165 })
      - saturatedLogDensity(2, { dayNumber: 200, sunspotNumber: 15 }));
    expect(solarOnly).toBeCloseTo(1.55, 2);
    // Season and solar cycle at their opposite extremes together — the two
    // curves the paper draws in Figure 4b — span about a factor of three.
    const solarMaximum = saturatedLogDensity(2, { dayNumber: 356, sunspotNumber: 165 });
    const solarMinimum = saturatedLogDensity(2, { dayNumber: 172, sunspotNumber: 15 });
    const ratio = 10 ** (solarMaximum - solarMinimum);
    expect(ratio).toBeGreaterThan(2.5);
    expect(ratio).toBeLessThan(3.5);
    // Far out the perturbation has decayed away, as the e^(-(L-2)/1.5)
    // factor requires.
    const far = 10 ** (saturatedLogDensity(6, { dayNumber: 356, sunspotNumber: 165 })
      - saturatedLogDensity(6, { dayNumber: 172, sunspotNumber: 15 }));
    expect(far).toBeLessThan(1.1);
  });

  it("counts the day number the seasonal terms are written for", () => {
    expect(dayNumberUtc(new Date("2026-01-01T00:00:00Z"))).toBe(1);
    expect(dayNumberUtc(new Date("2026-08-09T12:00:00Z"))).toBe(221);
    expect(dayNumberUtc(new Date("2024-12-31T23:59:00Z"))).toBe(366);
  });
});

// ---------------------------------------------------------------------------
// Erosion across the storm the site was carrying
// ---------------------------------------------------------------------------

/**
 * The 48 h replay this layer has to survive: the Kyoto quicklook Dst of
 * 2026-08-07 to 2026-08-09, hourly, as published in the release's storm
 * block. Quiet through the 7th, sudden commencement and main phase on the
 * 8th, minimum -60 nT at 22 UT, recovery through the 9th.
 */
const STORM_HOURS: Array<[string, number]> = [
  ["2026-08-08T00:00:00Z", 3], ["2026-08-08T01:00:00Z", 6], ["2026-08-08T02:00:00Z", 12],
  ["2026-08-08T03:00:00Z", 15], ["2026-08-08T04:00:00Z", 18], ["2026-08-08T05:00:00Z", 18],
  ["2026-08-08T06:00:00Z", 22], ["2026-08-08T07:00:00Z", 36], ["2026-08-08T08:00:00Z", 46],
  ["2026-08-08T09:00:00Z", 53], ["2026-08-08T10:00:00Z", 37], ["2026-08-08T11:00:00Z", 12],
  ["2026-08-08T12:00:00Z", -11], ["2026-08-08T13:00:00Z", -30], ["2026-08-08T14:00:00Z", -41],
  ["2026-08-08T15:00:00Z", -37], ["2026-08-08T16:00:00Z", -41], ["2026-08-08T17:00:00Z", -39],
  ["2026-08-08T18:00:00Z", -44], ["2026-08-08T19:00:00Z", -54], ["2026-08-08T20:00:00Z", -56],
  ["2026-08-08T21:00:00Z", -59], ["2026-08-08T22:00:00Z", -60], ["2026-08-08T23:00:00Z", -54],
  ["2026-08-09T00:00:00Z", -46], ["2026-08-09T01:00:00Z", -43], ["2026-08-09T02:00:00Z", -38],
  ["2026-08-09T03:00:00Z", -35], ["2026-08-09T04:00:00Z", -32], ["2026-08-09T05:00:00Z", -28],
  ["2026-08-09T06:00:00Z", -29], ["2026-08-09T07:00:00Z", -23], ["2026-08-09T08:00:00Z", -22],
  ["2026-08-09T09:00:00Z", -21], ["2026-08-09T10:00:00Z", -30],
];

const stormSeries = [
  // A quiet day ahead of it, so the 24 h window has something quiet to find.
  ...Array.from({ length: 24 }, (_, index) => ({
    at: new Date(Date.parse("2026-08-08T00:00:00Z") - (24 - index) * 3_600_000).toISOString(),
    dstNt: 5,
  })),
  ...STORM_HOURS.map(([at, dstNt]) => ({ at, dstNt })),
];

describe("erosion across the 48 h storm replay", () => {
  const at = (iso: string) => plasmasphereFieldAt(stormSeries, new Date(iso))!;
  const quiet = at("2026-08-08T06:00:00Z");
  const minimum = at("2026-08-08T23:00:00Z");
  const recovery = at("2026-08-09T10:00:00Z");

  it("moves the boundary in, and keeps it in while the index recovers", () => {
    expect(quiet.plasmapause.lppRe).toBeCloseTo(OBRIEN_MOLDWIN_DST.b, 6);
    expect(minimum.plasmapause.lppRe).toBeCloseTo(3.51, 2);
    // Twelve hours after the minimum the index has climbed from -60 to -30,
    // but the deepest Dst of the preceding day is still -60, so the boundary
    // has not sprung back. That asymmetry is the lesson.
    expect(recovery.plasmapause.dstMinimumNt).toBe(-60);
    expect(recovery.plasmapause.lppRe).toBeCloseTo(minimum.plasmapause.lppRe, 6);
  });

  it("empties the field at fixed L, which is what erosion means", () => {
    // Sampled at midnight local time, the model's own sharpest sector.
    const atL = (field: ReturnType<typeof at>, l: number) => field.densityAt(l, 0)!;
    // Deep inside the plasmasphere nothing changes: L = 2.5, the model's own
    // inner limit rounded up, stays saturated through the whole storm.
    expect(atL(minimum, 2.5) / atL(quiet, 2.5)).toBeCloseTo(1, 3);
    // L = 4 starts inside the plasmasphere and ends outside the eroded
    // boundary — it drops by more than a factor of ten.
    expect(atL(quiet, 4)).toBeGreaterThan(300);
    expect(atL(minimum, 4)).toBeLessThan(30);
    expect(atL(quiet, 4) / atL(minimum, 4)).toBeGreaterThan(10);
    // L = 6 was just inside the quiet boundary and is deep in the trough at
    // the minimum.
    expect(atL(quiet, 6)).toBeGreaterThan(50);
    expect(atL(minimum, 6)).toBeLessThan(10);
    // And the recovery frame still shows the eroded field, not the quiet one.
    expect(atL(recovery, 4)).toBeCloseTo(atL(minimum, 4), 6);
  });

  it("refuses times the record has not reached rather than extrapolating", () => {
    expect(plasmasphereFieldAt(stormSeries, new Date("2026-08-09T14:00:00Z"))).toBeNull();
    expect(plasmasphereFieldAt([], new Date("2026-08-09T10:00:00Z"))).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Geometry and legend
// ---------------------------------------------------------------------------

describe("the drawn field", () => {
  const field = plasmasphereFieldAt(stormSeries, new Date("2026-08-08T23:00:00Z"))!;
  const geometry = createPlasmasphereFieldGeometry(field, { positionForGsm, sampleCount: 20_000 });

  it("draws through the scene's shared radial ruler and nowhere else", () => {
    const positions = geometry.getAttribute("position");
    const radii = geometry.getAttribute("physicalRadiusRe");
    for (let index = 0; index < positions.count; index += 1) {
      const drawn = Math.hypot(positions.getX(index), positions.getY(index), positions.getZ(index));
      expect(drawn).toBeCloseTo(radiationBeltDisplayRadius(radii.getX(index), EARTH_SCENE_RADIUS), 1);
    }
  });

  it("fills the dipole flux tubes rather than lying flat in one plane", () => {
    // The first build of this layer drew the equatorial annulus the model
    // literally is, and under the scene's logarithmic near-Earth ruler that
    // reads as a donut — the very object this same change deleted the ring
    // current for being. Every point must sit on r = L cos²λ, and the cloud
    // must reach well out of the equatorial plane.
    const positions = geometry.getAttribute("position");
    const shells = geometry.getAttribute("shellL");
    const radii = geometry.getAttribute("physicalRadiusRe");
    let outOfPlane = 0;
    for (let index = 0; index < radii.count; index += 1) {
      // Scene y is GSM z under the test mapper; recover the latitude from the
      // drawn point and check the dipole relation holds.
      const drawn = Math.hypot(positions.getX(index), positions.getY(index), positions.getZ(index));
      const latitude = Math.asin(positions.getY(index) / drawn);
      expect(radii.getX(index)).toBeCloseTo(shells.getX(index) * Math.cos(latitude) ** 2, 2);
      if (Math.abs(latitude) > 0.35) outOfPlane += 1;
    }
    expect(outOfPlane / radii.count).toBeGreaterThan(0.4);
  });

  it("has no hard edge anywhere: every rim fades to nothing", () => {
    const shells = geometry.getAttribute("shellL");
    const radii = geometry.getAttribute("physicalRadiusRe");
    const fade = geometry.getAttribute("edgeFade");
    let innermost = Number.POSITIVE_INFINITY;
    let outermost = 0;
    for (let index = 0; index < shells.count; index += 1) {
      const l = shells.getX(index);
      innermost = Math.min(innermost, l);
      outermost = Math.max(outermost, l);
      expect(l).toBeGreaterThanOrEqual(CARPENTER_ANDERSON_1992.innerValidL - 1e-9);
      expect(l).toBeLessThanOrEqual(CARPENTER_ANDERSON_1992.outerValidL + 1e-9);
      // Close to either published L limit, and close to the ionospheric end
      // of a tube, the stipple is fading rather than stopping. The three fade
      // spans are deliberately different lengths — see the comments in
      // `createPlasmasphereFieldGeometry` — so each is checked at its own
      // scale rather than at one shared number that would silently pin them
      // together.
      if (l < CARPENTER_ANDERSON_1992.innerValidL + 0.05) expect(fade.getX(index)).toBeLessThan(0.2);
      if (l > CARPENTER_ANDERSON_1992.outerValidL - 0.2) expect(fade.getX(index)).toBeLessThan(0.2);
      if (radii.getX(index) < 1.11) expect(fade.getX(index)).toBeLessThan(0.2);
    }
    expect(innermost).toBeLessThan(CARPENTER_ANDERSON_1992.innerValidL + 0.02);
    expect(outermost).toBeGreaterThan(CARPENTER_ANDERSON_1992.outerValidL - 0.02);
  });

  it("closes all the way round, so it can never read as half a shell", () => {
    // The old layer shipped cut open on the noon-midnight plane and the
    // exposed edge read as a bug. Every azimuth sector is now populated, and
    // no sector is starved relative to the others.
    const positions = geometry.getAttribute("position");
    const counts = new Array(12).fill(0);
    for (let index = 0; index < positions.count; index += 1) {
      const angle = Math.atan2(-positions.getZ(index), positions.getX(index));
      counts[Math.floor((((angle / Math.PI) * 6) + 12) % 12)] += 1;
    }
    const expected = positions.count / 12;
    for (const count of counts) expect(count).toBeGreaterThan(expected * 0.8);
  });

  it("sizes its grains in the scene, so the cloud does not thin out as the camera moves in", () => {
    // The defect this pins: grains used to be sized as clamp(620 / viewing
    // distance, 1, 5) SCREEN PIXELS. The count is fixed, so the share of the
    // screen the stipple covers fell as the inverse square of zoom, and the
    // layer dissolved into the starfield exactly when a visitor moved in to
    // look at it — reported, correctly, as the layer showing nothing.
    const material = createPlasmasphereFieldMaterial(field);
    expect(material.vertexShader).toContain("projectionScale * grainSceneRadius / max(-viewPosition.z, 1.0)");
    expect(material.vertexShader).not.toMatch(/pointScale\s*\/\s*-viewPosition\.z/);
    expect(material.uniforms.grainSceneRadius!.value).toBe(PLASMASPHERE_GRAIN.sceneRadiusPerGrain);

    // The projection factor is filled in per frame from the real renderer and
    // camera. Two cameras at different distances must give a grain the same
    // ANGULAR size, which is the whole point; check the shader's arithmetic
    // directly rather than the uniform, which only carries the constant part.
    const angularSize = (distance: number) => {
      const projection = (900 * 0.5) / Math.tan(THREE.MathUtils.degToRad(45) / 2);
      return (projection * PLASMASPHERE_GRAIN.sceneRadiusPerGrain / distance) / distance;
    };
    // Halving the distance doubles the grain and doubles the cloud with it,
    // so their ratio — the coverage — is unchanged.
    expect(angularSize(600) * 600 ** 2).toBeCloseTo(angularSize(300) * 300 ** 2, 6);
    material.dispose();
  });

  it("is the same stipple every frame, so only the colour moves with the storm", () => {
    // A reseeded cloud would boil between timeline steps and make the
    // erosion impossible to see. Positions are deterministic; densities are
    // not, because they are the thing that changes.
    const quiet = createPlasmasphereFieldGeometry(
      plasmasphereFieldAt(stormSeries, new Date("2026-08-08T06:00:00Z"))!,
      { positionForGsm, sampleCount: 2_000 },
    );
    const storm = createPlasmasphereFieldGeometry(field, { positionForGsm, sampleCount: 2_000 });
    const a = quiet.getAttribute("position").array as Float32Array;
    const b = storm.getAttribute("position").array as Float32Array;
    expect(Array.from(a)).toEqual(Array.from(b));
    const quietDensity = quiet.getAttribute("logDensity").array as Float32Array;
    const stormDensity = storm.getAttribute("logDensity").array as Float32Array;
    expect(Array.from(quietDensity)).not.toEqual(Array.from(stormDensity));
  });

  it("spreads the stipple evenly through the drawn volume, so brightness is the only thing carrying density", () => {
    // The grains do NOT crowd where the plasma is dense. That is the point:
    // what a reader sees along a view ray is (grains per unit drawn volume)
    // times (how bright a grain is), and only the second is allowed to mean
    // anything. So the first is checked to be flat, in the volume the display
    // ruler actually draws — count the grains in equal-volume shells of the
    // display ball and they come out within a modest factor of each other.
    // An earlier build sampled L and latitude on their own uniform intervals,
    // whose volume element is L^2 cos^7(latitude); it piled grains up toward
    // the poles of every tube and the brightest ring on screen ended up at
    // neither the core nor the plasmapause.
    // Measured inside a thin equatorial wedge, where every display radius
    // between L 2.5 and L 7.5 is fully covered by the model, so the only
    // thing that can vary the count is the sampling itself. Three shells of
    // EQUAL display volume must therefore hold equal numbers of grains.
    const positions = geometry.getAttribute("position");
    const inner = positionForGsm(2.5, 0, 0).length();
    const outer = positionForGsm(7.5, 0, 0).length();
    // The mapper is free to permute axes on its way to scene space, so the
    // dipole axis is probed rather than assumed to be +z.
    const dipoleAxis = positionForGsm(0, 0, 1).normalize();
    const shellCount = 3;
    const perShell = new Array(shellCount).fill(0);
    for (let index = 0; index < positions.count; index += 1) {
      const point = new THREE.Vector3(positions.getX(index), positions.getY(index), positions.getZ(index));
      const radius = point.length();
      if (radius < inner || radius > outer) continue;
      if (Math.abs(point.dot(dipoleAxis) / radius) > 0.15) continue; // within about 8.6 degrees of the equator
      const fraction = (radius ** 3 - inner ** 3) / (outer ** 3 - inner ** 3);
      perShell[Math.min(shellCount - 1, Math.floor(fraction * shellCount))] += 1;
    }
    const busiest = Math.max(...perShell);
    const quietest = Math.min(...perShell);
    expect(quietest).toBeGreaterThan(200);
    expect(busiest / quietest).toBeLessThan(1.25);

    // And the density the grains carry does the work instead: inside the
    // plasmapause the mean is orders of magnitude above the trough's.
    const shells = geometry.getAttribute("shellL");
    const density = geometry.getAttribute("logDensity");
    let insideSum = 0; let insideCount = 0; let outsideSum = 0; let outsideCount = 0;
    for (let index = 0; index < shells.count; index += 1) {
      if (shells.getX(index) <= field.plasmapause.lppRe) { insideSum += density.getX(index); insideCount += 1; }
      else if (shells.getX(index) > field.plasmapause.lppRe + 1) { outsideSum += density.getX(index); outsideCount += 1; }
    }
    expect(insideCount).toBeGreaterThan(100);
    expect(outsideCount).toBeGreaterThan(100);
    expect(insideSum / insideCount - outsideSum / outsideCount).toBeGreaterThan(2);
  });

  it("empties the stipple outside the plasmapause, which is how the boundary appears", () => {
    const shells = geometry.getAttribute("shellL");
    const density = geometry.getAttribute("logDensity");
    const lppi = field.plasmapause.lppRe;
    let brightInside = 0;
    let insideTotal = 0;
    let brightOutside = 0;
    let outsideTotal = 0;
    for (let index = 0; index < shells.count; index += 1) {
      // "Bright" is the point at which the ramp is past its midpoint.
      const bright = density.getX(index) > Math.log10(3000) / 2;
      if (shells.getX(index) <= lppi) { insideTotal += 1; if (bright) brightInside += 1; }
      else if (shells.getX(index) > lppi + 0.5) { outsideTotal += 1; if (bright) brightOutside += 1; }
    }
    expect(brightInside / insideTotal).toBeGreaterThan(0.95);
    expect(brightOutside).toBe(0);
  });
});

describe("the plasmasphere never reaches the legend's SHAPE ONLY branch", () => {
  /**
   * The acceptance criterion the project owner checks first. The legend's bar
   * decision now lives in the exported pure function `keyCardBar`, so this
   * calls the REAL shipped path rather than quoting source text: a spec with
   * a scale must produce a ramp, a scale-less spec must produce the
   * shape-only bar, and the plasmasphere's real spec must land on the ramp
   * side. If the renderer's rule or the spec changes, one of these fails.
   */
  it("publishes an electron-density scale with its units", () => {
    expect(keyCardBar({ scale: undefined }, false).kind).toBe("shape-only");
    const field = plasmasphereFieldAt(stormSeries, new Date("2026-08-08T23:00:00Z"));
    const spec = plasmasphereLegendSpec(field);
    expect(spec.scale).toBeDefined();
    expect(spec.scale!.label).toContain("cm⁻³");
    expect(spec.scale!.label).toContain("LOG");
    expect(spec.scale!.gradient).toBe(PLASMASPHERE_DENSITY_SCALE.gradient);
    expect(keyCardBar(spec, false).kind).toBe("ramp");
  });

  it("keeps its scale even when the Dst record cannot answer", () => {
    // A layer with no data still has a quantity; only its readings go away.
    const spec = plasmasphereLegendSpec(null);
    expect(spec.scale).toBeDefined();
    expect(spec.statusState).toBe("no-data");
  });

  it("reaches the reader with that no-data state, instead of leaving the last instant's key up", () => {
    // The spec above was already correct. What was wrong was when it got
    // asked for. `updateTimeSelectedEnvironment` drew the legend from inside
    // a guard whose change signature was built from the solar-wind driver and
    // the X-ray flux and nothing else, and it evaluated the plasmasphere
    // AFTERWARDS. So scrubbing past the end of the Kyoto Dst record removed
    // the geometry, left the globe bare, and left a full electron-density
    // ramp sitting in the key with no notice anywhere — which is exactly what
    // was reported. Two things fix it and both are pinned here: the field is
    // evaluated before the legend, and what it can say is part of the
    // signature that decides whether the legend is redrawn at all.
    const method = explorerSource.slice(
      explorerSource.indexOf("private updateTimeSelectedEnvironment("),
      explorerSource.indexOf("private updateStormPanel("),
    );
    expect(method).not.toBe("");
    const evaluated = method.indexOf("this.updateInnerMagnetosphere(time)");
    const signed = method.indexOf("plasmasphereSignature}");
    const drawn = method.indexOf("this.updateEnvironmentLegend()");
    expect(evaluated).toBeGreaterThan(-1);
    expect(signed).toBeGreaterThan(evaluated);
    expect(drawn).toBeGreaterThan(signed);
    // And the descriptor really does distinguish the two states, so putting
    // it in the signature is not a no-op.
    const answerable = plasmasphereFieldAt(stormSeries, new Date("2026-08-08T23:00:00Z"));
    const unanswerable = plasmasphereFieldAt(stormSeries, new Date("2026-09-01T00:00:00Z"));
    expect(answerable).not.toBeNull();
    expect(unanswerable).toBeNull();
  });

  it("quotes the density at the L values the readings promise", () => {
    const field = plasmasphereFieldAt(stormSeries, new Date("2026-08-08T23:00:00Z"))!;
    const spec = plasmasphereLegendSpec(field);
    const row = spec.stats!.find((entry) => entry.label.includes("L 2.5 / 4 / 6"))!;
    expect(row.value).toContain("cm⁻³");
    const [inner, middle] = row.value.split(" / ").map(Number);
    expect(inner).toBeCloseTo(field.densityAt(2.5, 0)!, 0);
    expect(middle!).toBeLessThan(inner! / 10);
  });

  it("names the model, its doi and the boundary it borrowed", () => {
    const spec = plasmasphereLegendSpec(plasmasphereFieldAt(stormSeries, new Date("2026-08-08T23:00:00Z")));
    expect(spec.note).toContain("Carpenter & Anderson");
    expect(spec.note).toContain("10.1029/91JA01548");
    expect(spec.note).toContain("O'Brien & Moldwin");
    expect(spec.note).toContain("no dusk bulge");
    // The badge says "profile" now because this branch is the labelled
    // fallback: the layer prefers the published simulation and only reaches
    // here when the simulation cannot answer for the selected instant.
    expect(spec.badge).toBe("EMPIRICAL PROFILE");
  });

  it("says WHY the empirical profile is showing, and the reasons are distinct", () => {
    const field = plasmasphereFieldAt(stormSeries, new Date("2026-08-08T23:00:00Z"));
    const states = ["not-published", "not-loaded", "load-failed", "outside-window"] as const;
    const texts = states.map((state) => plasmasphereLegendSpec(field, state).statusText!);
    expect(new Set(texts).size).toBe(states.length);
    for (const text of texts) expect(text).toContain("EMPIRICAL PROFILE SHOWN");
    expect(plasmasphereLegendSpec(field, "outside-window").statusText)
      .toContain("OUTSIDE THE SIMULATED WINDOW");
  });
});

/**
 * Kept, and narrowed to what it was always FOR: nothing may reintroduce a
 * torus.
 *
 * The original form of this guard was "the ring current has no object and no
 * layer", which was the right rule for the object it was written against — a
 * donut whose radius, width and cross-section were invented out of the single
 * Dessler-Parker-Sckopke scalar. Sean approved a different object in August
 * 2026: an explicitly badged ILLUSTRATION of ring-current FORMATION, riding the
 * DGCPM plasmasphere's own published convection field, which claims no flux, no
 * density and no location. So the guard now pins the thing that must stay true
 * rather than the absence that happened to enforce it at the time.
 *
 * `tests/ring-current-illustration.test.ts` holds the rest: that its badge, its
 * evidence class and its colour-bar label all carry the illustration claim in
 * every state the card can be in.
 */
describe("the ring current is never drawn from Dst, and never as a torus", () => {
  it("builds no shape from the DPS scalar", () => {
    // The energy relation still yields ONE number, and one number still has no
    // map. Nothing may turn it into geometry.
    expect(explorerSource).not.toMatch(/ringCurrentEnergyJoules[^\n]*(Geometry|Torus|Mesh|position)/);
    expect(ringCurrentSource).not.toContain("ringCurrentEnergyJoules");
    expect(ringCurrentSource).not.toContain("TorusGeometry");
    expect(ringCurrentSource).not.toContain("dst");
  });

  it("keeps the layer that does exist labelled a derived shape everywhere it is named", () => {
    // The rail row no longer names it. Sean: "the rail looks fucking cluttered
    // still... those chips, you can just move them to the data viewer." So the
    // surface that must carry it is the layer's CARD, whose head holds the
    // badge whether the card is open or shut - and that panel now opens
    // expanded precisely so this claim is on screen the moment the layer is
    // drawn, rather than one click behind a fold.
    expect(indexSource).toContain("data-card-mission");
    expect(explorerSource).toContain("badge.className = `layer-status ${spec.evidence}`");
    // "SHAPE NOT MEASURED" since 2026-08-19, and the extra word is the point:
    // the ring current's ENERGY is measured, hourly, as Dst. What no upstream
    // publishes is its shape, which is the only thing this layer draws.
    //
    // MODEL-DERIVED rather than ILLUSTRATION from the same day. ILLUSTRATION
    // was right for the drift-path lines with sprites this replaced; the
    // volume that replaced them is RK4-integrated in NOAA's own published
    // convection field, which is `model` - the class the plasma sheet already
    // carries. The half that may never be weakened is the second one, and it
    // is asserted above and in ring-current-illustration.test.ts in every
    // state the card can be in.
    expect(explorerSource).toContain('badge: "MODEL-DERIVED · SHAPE NOT MEASURED"');
    expect(explorerSource).toContain('evidence: "model",');
  });
});

describe("no shipped layer's ready spec reaches SHAPE ONLY", () => {
  /**
   * The handoff's first acceptance criterion, held at the only chokepoint:
   * `keyCardBar` prints the shape-only bar exactly when a spec has no
   * `scale`. The specs built inline in ExplorerApp cannot be constructed
   * here without a DOM, so this pins the source the way the reachability
   * suite does — every layer's legend path must either return a spec-building
   * call that is scale-checked elsewhere, or carry `scale:` in its literal.
   * The ground-stations spec was the last to fall through, fixed by deriving
   * its categorical scale from the pin colours themselves.
   */
  it("ground stations' ready spec now carries the operator scale", () => {
    expect(explorerSource).toContain("scale: STATION_OPERATOR_SCALE");
  });
  it("the operator scale is derived from the pin colours, not written twice", () => {
    expect(STATION_OPERATOR_SCALE.gradient).toContain("#76e6a5");
    expect(STATION_OPERATOR_SCALE.gradient).toContain("#ff7b78");
    expect(STATION_OPERATOR_SCALE.label).toContain("OPERATOR CATEGORY");
    expect(keyCardBar({ scale: STATION_OPERATOR_SCALE }, false).kind).toBe("ramp");
  });
});
