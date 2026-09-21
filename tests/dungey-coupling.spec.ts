/**
 * Screenshot + measurement verification of the progressive solar-wind
 * coupling, from the wind alone to the auroral oval.
 *
 * The four captures per driver state ARE the record of what was asked for:
 * solar wind alone (unchanged), plus the magnetosphere (the coupling that
 * already shipped), plus the plasma sheet (the tail return leg), plus the
 * auroral oval (the precipitating branch). They are taken at a strongly
 * southward IMF and at a northward one, because the whole claim of this work
 * is that the picture follows the MEASURED coupling function, and a claim
 * about a difference has to be looked at rather than asserted.
 *
 * The numeric assertions below are the ones a screenshot cannot make: that the
 * ride ends at the lobes with the plasma-sheet layer off, that it does not
 * with it on, that the population thins when the IMF turns north, and that it
 * goes away entirely when the drivers do.
 */
import { expect, test } from "@playwright/test";

declare const process: { env: Record<string, string | undefined> };
const harnessOrigin = process.env.HARNESS_ORIGIN ?? "http://127.0.0.1:4174";
const OUT = process.env.DUNGEY_SHOT_DIR ?? "test-results/dungey-coupling";

const STAGES = ["wind", "magnetosphere", "plasma-sheet", "aurora"] as const;

/** Strongly southward, and northward at the same speed and density. */
const SOUTHWARD = { bzGsmNt: -12, byNt: 3, speedKps: 600, densityCm3: 8 };
const NORTHWARD = { bzGsmNt: 12, byNt: 3, speedKps: 600, densityCm3: 8 };

test("the coupling grows with the layers the reader switches on", async ({ page }, testInfo) => {
  // Eight full screenshots of a WebGL scene rendered in software under WSL,
  // each after a settle pause. A machine-speed allowance, not an assertion.
  testInfo.setTimeout(900_000);
  // The harness is served by the dev server, which watches a very large tree
  // on this box; first navigation has been measured at over a minute under
  // load. A machine allowance, not a page budget.
  await page.goto(`${harnessOrigin}/tests/dungey-coupling.harness.html`, { timeout: 180_000 });
  await page.waitForFunction(() => (window as any).__ready || (window as any).__lastError, undefined, { timeout: 60000 });
  expect(await page.evaluate(() => (window as any).__lastError)).toBeNull();

  const measured: Record<string, any> = {};
  for (const [label, drivers] of [["southward", SOUTHWARD], ["northward", NORTHWARD]] as const) {
    for (const stage of STAGES) {
      const state = await page.evaluate(
        (options) => (window as any).__apply(options),
        { ...drivers, stage },
      );
      measured[`${label}-${stage}`] = state;
      await page.waitForTimeout(900);
      await page.screenshot({ path: `${OUT}/${label}-${stage}.png` });
    }
  }

  // --- what the pictures cannot assert -------------------------------------

  // Stage 1 and 2: the return rides now exist from the WIND ALONE.
  //
  // This assertion used to read `.toBe(0)` for both, and it was correct when it
  // was written: the coupling was gated on the plasma-sheet layer being on.
  // Sean reversed that on 2026-08-27 -- "the solar wind should move the same
  // regardless of what layer is turned on... The particles should show all the
  // different movements regardless" -- so the gate is now the existence of
  // MEASURED inputs (substorm state, driver, tilt) rather than a switch, and a
  // reader with only the solar wind on sees the whole Dungey chain.
  //
  // Pinning the new truth rather than deleting the check, because the thing
  // worth guarding did not go away, it inverted: the chain must be present
  // without the downstream layers, and it must still be DRIVEN rather than
  // decorative. A spec left asserting the old gate goes red on a correct build
  // and then catches nothing at all while it sits red.
  expect(measured["southward-wind"].returnPaths).toBeGreaterThan(0);
  expect(measured["southward-magnetosphere"].returnPaths).toBeGreaterThan(0);
  expect(measured["southward-magnetosphere"].guidance.lobePathCount).toBeGreaterThan(0);

  // Stage 3: the lobe rides become return rides, in two charge branches.
  const sheet = measured["southward-plasma-sheet"];
  expect(sheet.returnPaths).toBeGreaterThan(0);
  expect(sheet.guidance.ringCurrentPathCount).toBe(sheet.returnPaths);
  expect(sheet.guidance.auroraPathCount).toBe(0);
  expect(sheet.guidance.lobePathCount).toBe(0);
  expect(sheet.guidance.returnLegEvidence).toContain("SCHEMATIC");

  // Stage 4: the precipitating branch joins, and only then.
  const aurora = measured["southward-aurora"];
  expect(aurora.guidance.auroraPathCount).toBeGreaterThan(0);
  expect(aurora.returnPaths).toBeGreaterThan(sheet.returnPaths);

  // Nothing was refused for leaving the magnetopause, in either driver state.
  for (const key of Object.keys(measured)) {
    const report = measured[key].tailReturnReport;
    if (!report) continue;
    expect(report.refusedPathCount).toBe(0);
    expect(report.worstContainmentFraction).toBeLessThan(0.9);
  }

  // THE TEACHING MOMENT, as a measurement. Same speed, same density, IMF
  // turned north: the coupling function collapses and the transport path
  // empties. If a later change decouples the animation from the driver this
  // goes red, and it is the only assertion here that could.
  const drivenDrive = measured["southward-aurora"].couplingDrive as number;
  const quietDrive = measured["northward-aurora"].couplingDrive as number;
  expect(drivenDrive).toBeGreaterThan(0.5);
  expect(quietDrive).toBeLessThan(0.1);
  // Counted over the RETURN population only. The cusp ride is deliberately
  // untouched by the drive, so folding its 448 tracers into the comparison
  // would dilute the very effect being tested — measured at 557 against 463,
  // a difference that is entirely the return legs and reads as 1.2x.
  expect(measured["southward-aurora"].visibleReturnTracers)
    .toBeGreaterThan(measured["northward-aurora"].visibleReturnTracers * 3);

  console.log(`coupling southward ${Math.round(measured["southward-aurora"].coupling)} -> drive ${drivenDrive.toFixed(3)}, `
    + `${measured["southward-aurora"].visibleReturnTracers} of ${measured["southward-aurora"].returnTracers} return tracers lit`);
  console.log(`coupling northward ${Math.round(measured["northward-aurora"].coupling)} -> drive ${quietDrive.toFixed(3)}, `
    + `${measured["northward-aurora"].visibleReturnTracers} of ${measured["northward-aurora"].returnTracers} return tracers lit`);
  console.log(`containment worst fraction: ${measured["southward-aurora"].tailReturnReport.worstContainmentFraction.toFixed(3)}`);
});

test("past the last measured driver there is nothing to animate", async ({ page }) => {
  // The harness is served by the dev server, which watches a very large tree
  // on this box; first navigation has been measured at over a minute under
  // load. A machine allowance, not a page budget.
  await page.goto(`${harnessOrigin}/tests/dungey-coupling.harness.html`, { timeout: 180_000 });
  await page.waitForFunction(() => (window as any).__ready || (window as any).__lastError, undefined, { timeout: 60000 });
  const gone = await page.evaluate(() => (window as any).__apply({
    bzGsmNt: -12, byNt: 3, speedKps: 600, densityCm3: 8, stage: "aurora", drivers: false,
  }));
  // No propagated wind means no coupling number, so no rate, so nothing on
  // screen — the same grammar the magnetosphere layer settled on for the
  // boundary. Every one of these is a separate way of saying it.
  expect(gone.coupling).toBeNull();
  expect(gone.drive).toBeNull();
  expect(gone.couplingDrive).toBeNull();
  expect(gone.pathCount).toBe(0);
  expect(gone.returnPaths).toBe(0);
  expect(gone.guidedVisible).toBe(false);
  expect(gone.windOnScreen).toBe(false);
});

/**
 * THE INVARIANT SEAN PREDICTED THE BUG FOR, BEFORE SEEING THE CODE.
 *
 * *"You can't draw it directly on the ring current/plasma sheet layer because
 * then particles will show up when the solar wind IMF layer isn't plotted.
 * Adding the layer just changes how solar wind particles move when the layer
 * is plotted."*
 *
 * The particles belong to the Solar wind & IMF layer. Plasma sheet, auroral
 * oval and the magnetosphere are MODIFIERS of how those particles move, and a
 * modifier that emits is a defect a reader spots on sight: a stream of solar
 * wind arriving from nowhere on a layer that is not about the solar wind.
 *
 * Checked by walking the scene graph rather than by reading a flag, because a
 * visible Points inside a hidden group draws nothing and the invariant is
 * about what is on screen.
 */
test("every other layer is a modifier: with the wind off, nothing of it is drawn", async ({ page }) => {
  await page.goto(`${harnessOrigin}/tests/dungey-coupling.harness.html`, { timeout: 180_000 });
  await page.waitForFunction(() => (window as any).__ready || (window as any).__lastError, undefined, { timeout: 60000 });
  for (const stage of STAGES) {
    const off = await page.evaluate(
      (options) => (window as any).__apply(options),
      { ...SOUTHWARD, stage, wind: false },
    );
    // ON SCREEN, not `visible`. `guidedPoints.visible` is genuinely true here
    // at every stage past the first, because `applyGuidedVisibility` answers
    // "is there a field to couple to", not "is this layer on" — and a visible
    // Points inside a hidden group draws exactly nothing. Asserting the flag
    // would have failed a build that is correct, which is the same mistake in
    // the other direction as a green test over a never-executed path.
    expect(off.windOnScreen, `${stage} with the wind layer off`).toBe(false);
    // And it comes straight back when the wind is switched on again, so the
    // check cannot pass by having broken the layer.
    const on = await page.evaluate(
      (options) => (window as any).__apply(options),
      { ...SOUTHWARD, stage, wind: true },
    );
    expect(on.windOnScreen, `${stage} with the wind layer on`).toBe(true);
  }
});

test("the frame cost of each stage", async ({ page }) => {
  test.setTimeout(600_000);
  // The harness is served by the dev server, which watches a very large tree
  // on this box; first navigation has been measured at over a minute under
  // load. A machine allowance, not a page budget.
  await page.goto(`${harnessOrigin}/tests/dungey-coupling.harness.html`, { timeout: 180_000 });
  await page.waitForFunction(() => (window as any).__ready || (window as any).__lastError, undefined, { timeout: 60000 });
  for (const stage of STAGES) {
    await page.evaluate((options) => (window as any).__apply(options), { ...SOUTHWARD, stage });
    await page.waitForTimeout(600);
    const fps = await page.evaluate(() => (window as any).__measureFps(60));
    // The GPU figure on this box is not a performance measurement of anything
    // a reader will ever run: WSL Chromium renders WebGL in SwiftShader, on a
    // machine that is usually carrying several agents at once. The number that
    // transfers to a phone is the per-frame CPU work this layer adds, so that
    // is measured separately and directly.
    const updateMs = await page.evaluate(() => (window as any).__measureUpdateMs(300));
    const info = await page.evaluate(() => (window as any).__renderInfo());
    const counts = await page.evaluate(() => (window as any).__counts());
    console.log(`${stage}: ${fps.toFixed(1)} fps (${(1000 / fps).toFixed(1)} ms/frame software), `
      + `solar-wind update ${updateMs.toFixed(3)} ms/frame CPU, `
      + `${counts.visibleTracers}/${counts.tracerCount} guided tracers, ${counts.returnPaths} return paths, `
      + `draw calls ${info.calls}, lines ${info.lines}, points ${info.points}`);
  }
});
