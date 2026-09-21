import { expect, test } from "@playwright/test";

/**
 * A known longitude must render over the geography that belongs to it.
 *
 * The globe shipped with `rotation.y = -PI/2` on the Earth mesh and on every
 * raster layer over it, while satellites, ground tracks, footprints, the
 * graticule and the day/night terminator are vector geometry placed straight
 * from geographic coordinates. The maps were therefore drawn 90 degrees west
 * of everything laid on them: SKYTERRA 1, whose sub-point is 101.28 W over
 * North America, appeared over the Gulf of Guinea at 11.28 W.
 *
 * Unit tests pin the azimuth arithmetic. This asserts the thing a viewer
 * relies on, from the rendered pixels: point the camera at a longitude where
 * the map has land, and land is what is there.
 */
const harness = "http://127.0.0.1:4174/tests/globe-orientation.harness.html";

test.describe("globe orientation", () => {
  test("renders each longitude over the geography that belongs to it", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop", "Orientation is not layout-dependent.");
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(harness);
    await page.waitForFunction("window.orientationProbeReady === true", null, { timeout: 120_000 });

    // The harness paints continents at -100..-90 and 20..30 degrees. Each
    // probe is paired with a longitude 90 degrees away that has the opposite
    // land cover, so the quarter-turn defect inverts every answer rather than
    // merely dimming it.
    const probes: Array<{ longitudeDeg: number; land: boolean; note: string }> = [
      { longitudeDeg: -95, land: true, note: "middle of the western continent" },
      { longitudeDeg: -5, land: false, note: "ocean 90 degrees east of it" },
      { longitudeDeg: 25, land: true, note: "middle of the eastern continent" },
      { longitudeDeg: 115, land: false, note: "ocean 90 degrees east of it" },
      { longitudeDeg: 170, land: false, note: "ocean whose 90-degree neighbour is land" },
    ];

    const samples: Record<number, { red: number; green: number; blue: number; greenOverBlue: number }> = {};
    for (const probe of probes) {
      samples[probe.longitudeDeg] = await page.evaluate(
        (longitudeDeg) => (window as unknown as Record<string, any>).orientationProbe.sampleAtLongitude(longitudeDeg),
        probe.longitudeDeg,
      );
    }

    // Land is painted #143842 over an ocean gradient around #061a25, so under
    // matched illumination every land probe is brighter than every sea probe.
    const landSamples = probes.filter((probe) => probe.land);
    const seaSamples = probes.filter((probe) => !probe.land);
    const dimmestLand = Math.min(...landSamples.map((probe) => samples[probe.longitudeDeg]!.green));
    const brightestSea = Math.max(...seaSamples.map((probe) => samples[probe.longitudeDeg]!.green));
    for (const probe of probes) {
      const sample = samples[probe.longitudeDeg]!;
      const isLand = sample.green > (dimmestLand + brightestSea) / 2;
      expect(isLand, `${probe.longitudeDeg} degrees (${probe.note}) rendered the wrong surface`).toBe(probe.land);
    }
    expect(dimmestLand, "land and sea were not separable; the probe cannot decide anything")
      .toBeGreaterThan(brightestSea * 1.2);

    // And the raster layers agree with the vector frame directly.
    for (const longitudeDeg of [-135, -45, 0, 45, 135]) {
      const offsets = await page.evaluate(
        (probeLongitude) => (window as unknown as Record<string, any>).orientationProbe.layerAzimuthOffsets(probeLongitude),
        longitudeDeg,
      );
      for (const [layer, offset] of Object.entries(offsets)) {
        expect(Math.abs(offset as number), `${layer} layer is rotated away from the globe`).toBeLessThan(0.01);
      }
    }

    // The terminator. The sub-solar point is vector geometry — calculated from
    // the date, then used as the light direction — so if the map were rotated
    // away from that frame the day/night line would fall on the wrong
    // continents. Every probe above is taken with the Sun on the probe's own
    // meridian, so asserting that a land longitude renders as land under that
    // light already pins the two frames together. These two add the direct
    // statement: the same geographic point is lit at its local noon and dark
    // at its local midnight.
    const noonOverLand = await sample(page, -95, -95);
    const midnightOverLand = await sample(page, -95, 85);
    expect(noonOverLand.green, "the sub-solar meridian is not lit")
      .toBeGreaterThan(midnightOverLand.green * 2);
    expect(noonOverLand.greenOverBlue, "local noon is not falling on the continent")
      .toBeGreaterThan(samples[170]!.greenOverBlue);

    expect(errors).toEqual([]);
  });
});

async function sample(page: import("@playwright/test").Page, longitudeDeg: number, subsolarLongitudeDeg: number) {
  return page.evaluate(
    ([probeLongitude, sunLongitude]) =>
      (window as unknown as Record<string, any>).orientationProbe.sampleAtLongitude(probeLongitude, sunLongitude),
    [longitudeDeg, subsolarLongitudeDeg],
  ) as Promise<{ red: number; green: number; blue: number; greenOverBlue: number }>;
}
