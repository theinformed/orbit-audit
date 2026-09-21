/**
 * Screenshot + measurement verification of the raymarched radiation-belt
 * volume, against a pinned real RBE frame (tests/data/geospace-volume-fixture.json,
 * the live 2026-08-08T23:40Z frame). The screenshots are the layer's
 * perceptual record: whether the belts read as tori with a dark slot is a
 * question numbers cannot settle, so a human (or agent) is expected to look
 * at them after any change to the volume shader or transfer function.
 */
import { expect, test } from "@playwright/test";

declare const process: { env: Record<string, string | undefined> };
const harnessOrigin = process.env.HARNESS_ORIGIN ?? "http://127.0.0.1:4174";
const OUT = process.env.RADIATION_SHOT_DIR ?? "test-results/radiation-volume";
// -1 is COMBINED_RADIATION_ENERGY_KEV: every published channel at once.
const ENERGIES = [1345.7, 2320.1, 452.75, 88.349, -1];
const VIEWS = ["default", "oblique", "edge", "pole"] as const;

test("radiation volume renders from every viewpoint at every energy", async ({ page }, testInfo) => {
  // Fourteen full-page screenshots of a ray-marched volume, each after a settle
  // pause, on a renderer that measures 1.4-1.5 s PER FRAME in software. Measured
  // 10.4 min on the pre-plasma-sheet build and 10.5 min on the current one, so
  // the 240 s project default could never have held it. A machine-speed
  // allowance, not a performance assertion.
  testInfo.setTimeout(1_200_000);
  await page.goto(`${harnessOrigin}/tests/radiation-volume.harness.html`);
  await page.waitForFunction(() => (window as any).__ready || (window as any).__lastError, undefined, { timeout: 60000 });
  const failure = await page.evaluate(() => (window as any).__lastError);
  expect(failure).toBeNull();

  for (const energy of ENERGIES) {
    // Every energy now gets the DEFAULT framing, because the per-energy
    // opacity tuning is judged from the camera a first-time visitor has. The
    // perceptual question lives at 1.35 MeV and in the combined volume, so
    // those two also get the other three angles.
    const views = energy === 1345.7 || energy === -1
      ? VIEWS
      : (["default", "oblique"] as const);
    for (const view of views) {
      await page.evaluate(
        ([viewName, energyKev]) => (window as any).__setView(viewName, energyKev),
        [view, energy] as const,
      );
      await page.waitForTimeout(700);
      const name = energy === -1 ? "combined" : `${Math.round(energy)}kev`;
      await page.screenshot({ path: `${OUT}/rbe-${name}-${view}.png` });
    }
  }

  // Render cost with the volume on screen, and the bake cost per energy.
  await page.evaluate(() => (window as any).__setView("oblique", 1345.7));
  await page.waitForTimeout(400);
  const frameMs = await page.evaluate(() => (window as any).__measureFps(90));
  console.log(`median frame time with volume, oblique 1.35 MeV: ${frameMs.toFixed(2)} ms`);
  for (const energy of ENERGIES) {
    const bakeMs = await page.evaluate((energyKev) => (window as any).__measureBake(energyKev), energy);
    console.log(`in-browser bake at production resolution, ${energy} keV: ${bakeMs.toFixed(0)} ms`);
  }

});
