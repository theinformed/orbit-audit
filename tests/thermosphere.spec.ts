import { expect, test } from "@playwright/test";

import { openRail as phoneOpenRail, showLegend } from "./phone-state";

/**
 * The thermosphere layer, end to end: artifact -> decode -> surface -> legend.
 *
 * The point of the layer is that a satellite's altitude and the atmosphere's
 * height are drawn on the SAME ruler, so this checks the numbers the legend
 * reports rather than a screenshot: a surface that built from real NOAA data
 * has a real lowest and highest altitude, and they have to be plausible.
 */
test("draws the neutral atmosphere at an altitude you can compare to a satellite", async ({ page }, testInfo) => {
  testInfo.setTimeout(300_000);
  await page.addInitScript(() => localStorage.setItem("space-explorer-hide-welcome-v1", "1"));
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));

  await page.goto("./");
  await expect(page.locator("#visible-count")).toContainText("Selected", { timeout: 120_000 });

  await phoneOpenRail(page);
  // Not in the Advanced group: this layer is on in every preset, so a reader
  // meets it on arrival and it belongs at the head of the list.
  await expect(page.locator("#layer-thermosphere")).toBeVisible();
  await page.locator("#layer-thermosphere").check();

  await showLegend(page);
  const card = page.locator("#key-cards .key-card[data-layer='thermosphere']");
  await expect(card).toBeVisible({ timeout: 120_000 });
  await expect(card).toContainText("Thermosphere height");

  // The legend row is deliberately title, bar and units and nothing else — the
  // readings and the evidence class belong to the Data Explorer. So the numbers
  // a reader actually compares against a satellite are asserted there.
  const viewer = page.locator('#data-viewer-cards [data-layer="thermosphere"]');
  await expect(viewer).toContainText("LOWEST", { timeout: 120_000 });

  // A model field must never present as a measurement.
  await expect(viewer).toContainText(/MODEL|EMPIRICAL/);

  const altitudes = await viewer.evaluate((element) => {
    const text = element.textContent ?? "";
    return [...text.matchAll(/(\d{3,4})\s*km/g)].map((match) => Number(match[1]));
  });
  expect(altitudes.length).toBeGreaterThanOrEqual(2);
  // 1e-12 kg m^-3 lives in the upper thermosphere: hundreds of kilometres, not
  // tens and not thousands. A surface that came out at 120 km or 1000 km would
  // mean the decode or the ruler is wrong.
  for (const altitude of altitudes.slice(0, 2)) {
    expect(altitude).toBeGreaterThan(200);
    expect(altitude).toBeLessThan(900);
  }

  expect(errors).toEqual([]);
});
