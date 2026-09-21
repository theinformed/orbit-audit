import { expect, test } from "@playwright/test";
import type { CoverageMeasurement } from "./footprint-fill.harness";

/**
 * The satellite coverage cap must not have holes in it.
 *
 * This is the guard for a defect that unit tests over geometry alone can miss
 * and that no amount of reading the code makes obvious. The cap is a sheet of
 * flat triangles laid on a sphere 0.78 scene units above the globe. Flat
 * triangles cannot follow a sphere: one spanning an angular step s dips
 * R(1-cos(s/2)) below it in the middle. When the cap was tessellated with a
 * fixed seven rings regardless of its size, a geostationary cap's step reached
 * about 14 degrees, the dip exceeded the lift, the cap's own triangles passed
 * inside the opaque Earth, and the Earth won the depth test in bands — a
 * coverage footprint with moving holes torn through it. It was worse the wider
 * the cap, so it hit exactly the spacecraft whose coverage matters most.
 *
 * Geometry tests in tests/globe-footprint-fill.test.ts assert the clearance
 * that prevents it. This asserts the thing the viewer actually sees, by
 * counting pixels out of the WebGL drawing buffer, so a future change to the
 * lift, the Earth mesh, the camera, the depth settings or the draw order is
 * caught even though none of them are in that geometry.
 */
const harness = "http://127.0.0.1:4174/tests/footprint-fill.harness.html";

interface CoverageCase {
  name: string;
  latitudeDeg: number;
  altitudeKm: number;
  minimumElevationDeg: number;
  cameraDistance: number;
  cameraOffsetDeg: number;
}

const cases: CoverageCase[] = [
  // Wide caps are where the sag exceeded the lift.
  { name: "geostationary, horizon mask", latitudeDeg: 11.3, altitudeKm: 35786, minimumElevationDeg: 0, cameraDistance: 330, cameraOffsetDeg: 0 },
  { name: "geostationary, 5 degree mask", latitudeDeg: 11.3, altitudeKm: 35786, minimumElevationDeg: 5, cameraDistance: 330, cameraOffsetDeg: 0 },
  { name: "medium Earth orbit", latitudeDeg: 11.3, altitudeKm: 20200, minimumElevationDeg: 0, cameraDistance: 330, cameraOffsetDeg: 0 },
  { name: "highly elliptical apogee", latitudeDeg: 11.3, altitudeKm: 60000, minimumElevationDeg: 0, cameraDistance: 330, cameraOffsetDeg: 0 },
  { name: "high latitude apogee", latitudeDeg: 78, altitudeKm: 60000, minimumElevationDeg: 0, cameraDistance: 330, cameraOffsetDeg: 0 },
  // Narrow caps, including pulled back and near the limb where depth-buffer
  // precision is worst.
  { name: "low Earth orbit", latitudeDeg: 11.3, altitudeKm: 481, minimumElevationDeg: 0, cameraDistance: 330, cameraOffsetDeg: 0 },
  { name: "low Earth orbit, pulled back", latitudeDeg: 11.3, altitudeKm: 481, minimumElevationDeg: 0, cameraDistance: 940, cameraOffsetDeg: 0 },
  { name: "low Earth orbit, near the limb", latitudeDeg: 11.3, altitudeKm: 481, minimumElevationDeg: 10, cameraDistance: 940, cameraOffsetDeg: 62 },
];

test.describe("satellite coverage cap", () => {
  test("renders without holes at every orbit, mask and viewing distance", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop", "One WebGL readback pass is enough; it is not layout-dependent.");
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(harness);
    await page.waitForFunction("window.coverageProbeReady === true", null, { timeout: 120_000 });

    for (const scenario of cases) {
      const measurement: CoverageMeasurement = await page.evaluate((probeCase) => {
        const probe = (window as unknown as Record<string, any>).coverageProbe;
        probe.showCoverage(
          probeCase.latitudeDeg,
          -47.9,
          probeCase.altitudeKm,
          probeCase.minimumElevationDeg,
          probeCase.cameraDistance,
          probeCase.cameraOffsetDeg,
        );
        return probe.measureCoverage();
      }, scenario);

      // A cap that failed to draw at all would report zero holes too. The
      // smallest case here — a 481 km cap behind a 10 degree mask, seen from
      // 940 units and near the limb — covers about 900 pixels.
      expect(measurement.covered, `${scenario.name}: cap drew nothing`).toBeGreaterThan(500);
      expect(measurement.holes, `${scenario.name}: cap has holes torn in it`).toBe(0);
      expect(measurement.holeRows, `${scenario.name}: cap has broken scanlines`).toBe(0);
    }

    expect(errors).toEqual([]);
  });
});
