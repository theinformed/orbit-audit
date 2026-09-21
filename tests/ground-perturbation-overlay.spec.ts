import { expect, test } from "@playwright/test";

/**
 * The storm has to be drawn over the part of the Earth it is happening on.
 *
 * The unit tests answer the geometry from numbers. This answers it from
 * pixels, because the defect this project keeps producing lives in the gap
 * between the two: the map is one equirectangular texture and the field is
 * another, and a rotation, a mirror or a half-cell slip applied to one and not
 * the other is invisible to every arithmetic test while being the whole of
 * what a reader sees.
 *
 * Both probe sites are taken from the published frame at run time — the
 * strongest and weakest cells it actually contains — so the contrast this
 * relies on is guaranteed by the data rather than by how active the Sun
 * happens to be when the test runs.
 */

// Declared locally: this file is typechecked by the project tsconfig, which
// does not carry Node types.
declare const process: { env: Record<string, string | undefined> };
const harnessOrigin = process.env.HARNESS_ORIGIN ?? "http://127.0.0.1:4174";
const harness = `${harnessOrigin}/tests/ground-perturbation-overlay.harness.html`;

interface Probe {
  latitudeDeg: number;
  longitudeDeg: number;
  cellLatitudeDeg: number;
  cellLongitudeDeg: number;
  modelNt: number;
  overlayDelta: number;
}

test.describe("ground magnetic perturbation overlay", () => {
  test("draws the disturbance where the model puts it", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop", "Overlay geography is not layout-dependent.");
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(harness);
    await page.waitForFunction(
      "window.groundFieldProbeReady === true || typeof window.groundFieldProbeError === 'string'",
      null,
      { timeout: 180_000 },
    );
    const failure = await page.evaluate(() => window.groundFieldProbeError ?? null);
    expect(failure, "the harness could not load the published ground-field artifact").toBeNull();

    const summary = await page.evaluate(() => window.groundFieldProbe!.frameSummary());
    expect(summary.status).toBe("ready");
    expect(summary.frameCount).toBeGreaterThan(0);
    // Guidance, not a nowcast: the frame is valid after the run that made it.
    expect(Date.parse(summary.validAt)).toBeGreaterThan(Date.parse(summary.runAt));
    expect(summary.leadMinutes).toBe(
      Math.round((Date.parse(summary.validAt) - Date.parse(summary.runAt)) / 60_000),
    );

    const extremes = await page.evaluate(() => window.groundFieldProbe!.extremeCells());
    const contrast = extremes.strongest.modelNt / Math.max(extremes.weakest.modelNt, 1e-6);
    expect(contrast, "the published frame is too flat for a geographic probe to mean anything")
      .toBeGreaterThan(3);

    const at = (latitudeDeg: number, longitudeDeg: number): Promise<Probe> =>
      page.evaluate(
        ([latitude, longitude]: number[]) => window.groundFieldProbe!.probe(latitude!, longitude!),
        [latitudeDeg, longitudeDeg],
      );

    const strongest = await at(extremes.strongest.latitudeDeg, extremes.strongest.longitudeDeg);
    const weakest = await at(extremes.weakest.latitudeDeg, extremes.weakest.longitudeDeg);

    // The overlay is being drawn at all. Without this every other number here
    // would be a comparison of two identical frames.
    expect(strongest.overlayDelta).toBeGreaterThan(10);
    // And it is brighter where the model is stronger.
    expect(strongest.overlayDelta).toBeGreaterThan(weakest.overlayDelta);

    // The quarter-turn control. Three other longitudes at the same latitude:
    // if the field were rotated, one of them would carry the maximum.
    const quadrants: Probe[] = [];
    for (const turn of [90, 180, 270]) {
      quadrants.push(await at(
        extremes.strongest.latitudeDeg,
        (extremes.strongest.longitudeDeg + turn) % 360,
      ));
    }
    for (const quadrant of quadrants) {
      // Only meaningful where the model itself is clearly weaker there.
      if (quadrant.modelNt > 0.66 * strongest.modelNt) continue;
      expect(
        strongest.overlayDelta,
        `a quarter-turn control at ${quadrant.cellLongitudeDeg}E was drawn at least as brightly `
        + `as the model maximum at ${strongest.cellLongitudeDeg}E`,
      ).toBeGreaterThan(quadrant.overlayDelta);
    }

    // The mirror control: the same longitude in the opposite hemisphere.
    const mirrored = await at(-extremes.strongest.latitudeDeg, extremes.strongest.longitudeDeg);
    if (mirrored.modelNt <= 0.66 * strongest.modelNt) {
      expect(strongest.overlayDelta).toBeGreaterThan(mirrored.overlayDelta);
    }

    // Each probe read the cell it meant to read, within half a cell.
    for (const probe of [strongest, weakest, mirrored, ...quadrants]) {
      expect(Math.abs(probe.cellLatitudeDeg - probe.latitudeDeg)).toBeLessThanOrEqual(2.5);
    }

    testInfo.attach("ground-field-probes", {
      body: JSON.stringify({ summary, extremes, strongest, weakest, mirrored, quadrants }, null, 1),
      contentType: "application/json",
    });
    expect(errors).toEqual([]);
  });
});
