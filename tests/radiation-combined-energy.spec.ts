/**
 * The combined energy view, checked on the REAL production page.
 *
 * Seven features on this project were built, tested, merged, and reachable
 * from nothing. The unit tests prove the combined volume is the right
 * quantity; this proves the control exists in the shipped page, that clicking
 * it reaches the globe, and that the layer says which integral is on screen.
 *
 * It asserts BEHAVIOUR, not presence: the card's readings are written from the
 * renderer's own metadata for the frame it just drew, so they can only say
 * "ALL ENERGIES (COMBINED)" if the volume was actually rebuilt from the folded
 * artifact. A button that only repainted itself would fail here.
 */
import { expect, test } from "@playwright/test";

import { showLegend } from "./phone-state";

test("the belts open on every published channel at once, with no interaction", async ({ page }, testInfo) => {
  // Measured 6.7 min against the pre-plasma-sheet build and 7.2 min against the
  // current one on a quiet bigmem, so the 240 s project default was never
  // enough for it and the failure it produced was a browser session killed
  // mid-assertion — which reads like a product bug and is not one. The budget
  // is a machine-speed allowance for software WebGL, not a performance
  // assertion; the site's own speed is measured by tests/slow-machine.measure.mjs.
  testInfo.setTimeout(900_000);
  await page.addInitScript(() => localStorage.setItem("space-explorer-hide-welcome-v1", "1"));
  await page.goto("/");
  await expect(page.locator("#scene canvas")).toBeVisible({ timeout: 120_000 });

  // Into the space-weather panel, then ONE interaction: switch the layer on.
  // Nothing else. This is the state Sean was describing when he said the belts
  // were there in one screenshot and not there when you turn the layer on.
  // On a phone the rail is a bottom sheet that ships closed, so its mode
  // switch and layer toggles are off screen until it is opened. No-op on
  // desktop and tablet, where the toggle is not rendered at all.
  if (await page.locator("#mobile-panel-toggle").isVisible()
    && !await page.locator("#control-rail").evaluate((rail) => rail.classList.contains("is-open"))) {
    await page.locator("#mobile-panel-toggle").click();
  }
  await expect(page.locator(".environment-section")).toBeVisible();
  await page.locator("#layer-radiation").check();
  await page.locator('[data-layer-caret="radiation"]').click();

  const combined = page.locator('[data-radiation-energy="-1"]');
  await expect(combined).toHaveCount(1);
  await expect(combined).toHaveText(/All energies \(combined\)/);
  await expect(combined).toHaveClass(/is-active/);
  for (const channel of ["88.349", "452.75", "1345.7", "2320.1"]) {
    await expect(page.locator(`[data-radiation-energy="${channel}"]`)).not.toHaveClass(/is-active/);
  }

  // The card's readings are written from the renderer's own metadata for the
  // frame it just drew, so they can only say this if the volume was really
  // built from the folded artifact. A control that only repainted itself
  // would fail here.
  const card = page.locator('#data-viewer-cards [data-layer="radiation"]');
  await expect(card).toContainText("ALL ENERGIES (COMBINED)", { timeout: 120_000 });
  await expect(card).toContainText("TRAPEZOIDAL BAND AVERAGE");
  await expect(card).toContainText("DRAWN ABOVE");
  await expect(card).toContainText("COLOUR SCALE IS THE SAME");

  // Every single channel is still one click away, and the switch works both ways.
  await page.locator('[data-radiation-energy="1345.7"]').click();
  await expect(card).toContainText("1.35 MeV", { timeout: 120_000 });
  await expect(card).not.toContainText("ALL ENERGIES (COMBINED)");
  await combined.click();
  await expect(card).toContainText("ALL ENERGIES (COMBINED)", { timeout: 120_000 });
});

/**
 * The belt card must never show the flat SHAPE ONLY bar, not even for the two
 * seconds between switching the layer on and its first frame arriving.
 *
 * "Shape only is the worst part of this." — the presentation this whole family
 * was rebuilt to retire, and it was still reachable on the layer Sean cares
 * most about, because the card's ramp was gated on metadata that does not
 * exist yet. On a slow machine that window is thirteen seconds, not two.
 */
test("the belt key card carries its ramp from the instant the layer is switched on", async ({ page }, testInfo) => {
  testInfo.setTimeout(300_000);
  await page.addInitScript(() => localStorage.setItem("space-explorer-hide-welcome-v1", "1"));
  await page.goto("/");
  await expect(page.locator("#scene canvas")).toBeVisible({ timeout: 120_000 });
  // On a phone the rail is a bottom sheet that ships closed, so its mode
  // switch and layer toggles are off screen until it is opened. No-op on
  // desktop and tablet, where the toggle is not rendered at all.
  if (await page.locator("#mobile-panel-toggle").isVisible()
    && !await page.locator("#control-rail").evaluate((rail) => rail.classList.contains("is-open"))) {
    await page.locator("#mobile-panel-toggle").click();
  }
  await page.locator("#layer-radiation").check();

  // Sample from the moment the card appears until it is ready. Polling rather
  // than a single assertion, because the defect is a transient state: one
  // snapshot after the fact would have passed while the visitor still saw it.
  const card = page.locator("#key-cards .key-card[data-layer='radiation']").first();
  // A phone folds the legend by default AND the layer sheet opened above sits
  // over it, so the toggle itself is unreachable until the sheet is away.
  await showLegend(page);
  await card.waitFor({ state: "visible", timeout: 120_000 });
  const seen: string[] = [];
  const deadline = Date.now() + 60_000;
  let ready = false;
  while (Date.now() < deadline && !ready) {
    const text = (await card.innerText().catch(() => "")).replace(/\s+/g, " ");
    if (text) seen.push(text);
    ready = /model-native differential flux/i.test(text);
    if (!ready) await page.waitForTimeout(120);
  }
  expect(ready, "the belt card never reached its loaded state").toBe(true);
  const shapeOnly = seen.filter((text) => text.includes("SHAPE ONLY"));
  expect(shapeOnly, `card showed SHAPE ONLY in ${shapeOnly.length} of ${seen.length} samples`).toEqual([]);
  // The name has to be the view the visitor is actually getting, which is the
  // shipped default, not the single bounce shell they never selected.
  expect(seen.every((text) => !text.includes("mapped bounce shell")),
    "card named the single bounce shell while the omnidirectional volume was loading").toBe(true);
});
