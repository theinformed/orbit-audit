import { expect, test } from "@playwright/test";
import { RENDER_PROBE_IDS } from "./ground-station-probe-sites";

/**
 * A ground station has to be drawn over its own country.
 *
 * The unit tests answer this from coordinates. This answers it from pixels,
 * because the failure this project keeps producing lives in the gap between
 * the two: the map is an equirectangular texture, the pins are vector
 * geometry, and a rotation applied to one and not the other is invisible to
 * every numerical test while being the only thing a reader can see.
 *
 * Each probe aims the production camera straight down a station's geographic
 * direction, so the station belongs dead centre, and lights that meridian so
 * every probe is compared under identical illumination.
 */
/**
 * The harness dev server. Overridable because `playwright.config.ts` starts it
 * on a fixed port with `reuseExistingServer: true`, and when several worktrees
 * of this repo are open at once — which is how this project is actually worked
 * on — that silently hands the spec whichever branch got there first. Vite's
 * SPA fallback then answers the missing harness path with index.html and a 200,
 * so the failure looks like "the probe never became ready" rather than "you are
 * testing someone else's code". Set HARNESS_ORIGIN to your own port.
 */
// Declared locally: this file is typechecked by the project tsconfig, which
// does not carry Node types, and adding @types/node for one string is worse.
declare const process: { env: Record<string, string | undefined> };
const harnessOrigin = process.env.HARNESS_ORIGIN ?? "http://127.0.0.1:4174";
const harness = `${harnessOrigin}/tests/ground-station-overlay.harness.html`;

interface Patch {
  red: number;
  green: number;
  blue: number;
  /** Illumination-robust land/sea discriminator; see the harness. */
  greenOverBlue: number;
}

interface Probe {
  id: string;
  name: string;
  latitudeDeg: number;
  longitudeDeg: number;
  pinOffsetPx: number;
  mapUnderPin: Patch;
  pinDrawn: Patch;
  mapNinetyEast: Patch;
}


test.describe("ground-station overlay", () => {
  test("draws every pin over the land it belongs to", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop", "Overlay geography is not layout-dependent.");
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(harness);
    await page.waitForFunction("window.groundStationProbeReady === true", null, { timeout: 120_000 });

    const probes: Probe[] = [];
    for (const id of RENDER_PROBE_IDS) {
      probes.push(await page.evaluate(
        (stationId) => (window as unknown as Record<string, any>).groundStationProbe.probeStation(stationId),
        id,
      ) as Probe);
    }

    // 1. The pin is where the camera is pointing. If the overlay used any
    //    transform other than the globe's own, this is where it shows.
    for (const probe of probes) {
      expect(probe.pinOffsetPx, `${probe.id}: the pin is not where its coordinates point`)
        .toBeLessThan(4);
    }

    // 2. The overlay is genuinely being rendered. Without this every colour
    //    below would be a statement about an empty scene.
    for (const probe of probes) {
      const difference = Math.abs(probe.pinDrawn.red - probe.mapUnderPin.red)
        + Math.abs(probe.pinDrawn.green - probe.mapUnderPin.green)
        + Math.abs(probe.pinDrawn.blue - probe.mapUnderPin.blue);
      expect(difference, `${probe.id}: no pin was drawn at the station`).toBeGreaterThan(12);
    }

    // 3. The map under each pin is land, and the map ninety degrees east is
    //    sea. Compared on the green-over-blue ratio rather than brightness:
    //    Svalbard and Fairbanks are lit edge-on even at their own local noon,
    //    so a raw-brightness threshold cannot separate polar land from
    //    equatorial ocean. The ratio can, because the lights' colours are fixed.
    const dimmestLand = Math.min(...probes.map((probe) => probe.mapUnderPin.greenOverBlue));
    const brightestSea = Math.max(...probes.map((probe) => probe.mapNinetyEast.greenOverBlue));
    expect(dimmestLand, "land and sea were not separable; the probe cannot decide anything")
      .toBeGreaterThan(brightestSea * 1.03);
    for (const probe of probes) {
      const threshold = (dimmestLand + brightestSea) / 2;
      expect(probe.mapUnderPin.greenOverBlue, `${probe.id} is not drawn over land`)
        .toBeGreaterThan(threshold);
      expect(probe.mapNinetyEast.greenOverBlue, `${probe.id} would not have moved to sea under the quarter-turn`)
        .toBeLessThan(threshold);
    }

    expect(errors).toEqual([]);
  });

  test("fails when the quarter-turn is put back", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop", "Overlay geography is not layout-dependent.");
    await page.goto(harness);
    await page.waitForFunction("window.groundStationProbeReady === true", null, { timeout: 120_000 });

    const sample = async (id: string) => await page.evaluate(
      (stationId) => (window as unknown as Record<string, any>).groundStationProbe.probeStation(stationId),
      id,
    ) as Probe;

    const healthy: Probe[] = [];
    for (const id of RENDER_PROBE_IDS) healthy.push(await sample(id));

    await page.evaluate(() => (window as unknown as Record<string, any>).groundStationProbe.setDefect(true));
    const broken: Probe[] = [];
    for (const id of RENDER_PROBE_IDS) broken.push(await sample(id));

    // The pin does not move — that is the whole point. The map moves out from
    // under it, so the surface rendered at the station's own position changes
    // from the land it belongs on to the sea ninety degrees away.
    for (const [index, probe] of broken.entries()) {
      const before = healthy[index]!;
      expect(probe.pinOffsetPx, `${probe.id}: the pin moved, so this is not the defect under test`)
        .toBeCloseTo(before.pinOffsetPx, 1);
      expect(
        probe.mapUnderPin.greenOverBlue,
        `${probe.id}: the quarter-turn did not change what is drawn under the pin`,
      ).toBeLessThan(before.mapUnderPin.greenOverBlue);
    }

    // And stated as the assertion the healthy test makes, so the two are
    // unambiguously the same measurement: under the defect, land becomes sea.
    const dimmestLand = Math.min(...healthy.map((probe) => probe.mapUnderPin.greenOverBlue));
    const brightestSea = Math.max(...healthy.map((probe) => probe.mapNinetyEast.greenOverBlue));
    const threshold = (dimmestLand + brightestSea) / 2;
    const stillLand = broken.filter((probe) => probe.mapUnderPin.greenOverBlue > threshold);
    expect(stillLand.map((probe) => probe.id), "these stations survived the quarter-turn").toEqual([]);

    await page.evaluate(() => (window as unknown as Record<string, any>).groundStationProbe.setDefect(false));
  });

  test("puts every published station somewhere on the globe", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop", "Overlay geography is not layout-dependent.");
    await page.goto(harness);
    await page.waitForFunction("window.groundStationProbeReady === true", null, { timeout: 120_000 });
    const ids = await page.evaluate(
      () => (window as unknown as Record<string, any>).groundStationProbe.stationIds(),
    ) as string[];
    expect(ids.length).toBeGreaterThan(20);
    // Every pin, not just the six with a paired ocean control, has to project
    // to the point its coordinates name.
    for (const id of ids) {
      const probe = await page.evaluate(
        (stationId) => (window as unknown as Record<string, any>).groundStationProbe.probeStation(stationId),
        id,
      ) as Probe;
      expect(probe.pinOffsetPx, `${id}: the pin is not where its coordinates point`).toBeLessThan(4);
    }
  });
});
