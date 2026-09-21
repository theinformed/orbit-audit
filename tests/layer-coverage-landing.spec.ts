import { expect, test } from "@playwright/test";

/**
 * Switching a layer on must not produce an empty globe — in the browser.
 *
 * This exists because the unit tests were green while the behaviour was
 * missing. `landOnCoverageFor` read the layer's coverage window at the instant
 * the checkbox flipped, and at that instant the layer's artifact is still in
 * flight: measured on the built bundle against the real release, the aurora
 * key card still drew its 0-100% ramp at +0 ms and only flipped to NO DATA at
 * +150 ms, #time-slider received zero input events, and the clock never moved.
 * Nothing about that is visible from a pure function, so it is checked here.
 *
 * The layer is aurora because aurora is the one that really stalls: NOAA's
 * OVATION is a 30-90 minute forecast product and its publishing stops for
 * hours at a time (measured 2026-08-19: 2.09 hours, and our newest frame was
 * identical to theirs). Whether it is stalled during any given run is NOT this
 * test's business, so it reads the release's own manifest and checks the
 * invariant that applies: a gap means land, no gap means do not touch the
 * reader's clock at all.
 */
test("a layer switched on with nothing at the current time lands the clock on its newest frame", async ({ page }) => {
  test.setTimeout(600_000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.addInitScript(() => localStorage.setItem("space-explorer-hide-welcome-v1", "1"));
  await page.goto("./");
  await expect(page.locator("#visible-count")).toContainText("Selected", { timeout: 120_000 });
  await page.locator("#control-rail button", { hasText: "Space weather" }).first().click();

  const auroraGap = await page.evaluate(async () => {
    const manifest = await fetch("data/manifest.json").then((response) => response.json()) as { aurora?: { validTo: string } };
    if (!manifest.aurora) return null;
    return { validTo: manifest.aurora.validTo, staleMinutes: (Date.now() - Date.parse(manifest.aurora.validTo)) / 60_000 };
  });
  test.skip(auroraGap === null, "this release published no aurora artifact at all");

  const auroraKey = page.locator('#key-cards [data-layer="aurora"]');
  // The sentence about the move is on the LAYER'S OWN CARD since 2026-08-27,
  // not in the legend. Sean, on the ring current's legend block: "The
  // description is too long. That should go in the layer viewer."
  const auroraCard = page.locator('#data-viewer-cards [data-layer="aurora"]');
  const clock = page.locator("#sim-time");
  await page.locator("#layer-aurora").check();
  await expect(auroraKey).toBeVisible({ timeout: 60_000 });
  // The fetch has to land before any of this means anything; the card cannot
  // say NO DATA or draw a ramp until it has.
  await page.waitForTimeout(12_000);

  if (auroraGap!.staleMinutes > 10) {
    // Landed, and landed BACKWARD: the clock now reads the newest published
    // frame rather than the present.
    const landedAt = await clock.textContent();
    expect(Date.parse(`${landedAt!.replace(" UTC", "").replace(" ", "T")}Z`)).toBeLessThan(Date.parse(auroraGap!.validTo) + 60_000);
    // Held, not merely nudged. The landing instant is a minute inside the
    // window, so a clock still running at real time would carry the reader out
    // of coverage about sixty seconds later and the layer would go blank
    // again — the defect, restored on a timer.
    await expect(page.locator("#sim-label")).toHaveText("PAUSED");
    await page.waitForTimeout(8_000);
    expect(await clock.textContent()).toBe(landedAt);
    // The layer is drawn, which is the whole point, and the move is said out
    // loud, because silently moving a reader who was looking at "now" two
    // hours into the past is its own confusion.
    await expect(auroraKey).not.toContainText("NO DATA AT THIS TIME");
    await expect(auroraCard).toContainText("The clock moved back to");
    await expect(auroraCard).toContainText("Return to now");
    // And the legend is a key again: it does not repeat the paragraph.
    await expect(auroraKey).not.toContainText("The clock moved back to");

    // And the reader's own clock beats it. Return to now puts them back in the
    // present with the message, and nothing drags them off it again.
    await page.locator("#time-now").click();
    await page.waitForTimeout(8_000);
    await expect(page.locator("#sim-label")).toHaveText("LIVE");
    await expect(auroraKey).toContainText("NO DATA AT THIS TIME");
    await expect(auroraCard).not.toContainText("The clock moved back to");
    await page.waitForTimeout(6_000);
    await expect(page.locator("#sim-label")).toHaveText("LIVE");
  } else {
    // NOAA is publishing normally. Then there is nothing to fix and the clock
    // is not the site's to move: a jump with data on screen would be the same
    // fault in the other direction.
    await expect(page.locator("#sim-label")).toHaveText("LIVE");
    await expect(auroraCard).not.toContainText("The clock moved back to");
  }
  expect(errors).toEqual([]);
});
