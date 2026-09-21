/**
 * THE CONSTELLATION OF THE DAY POPUP, driven rather than described.
 *
 * Sean's requirements are all behavioural and none of them can be checked from
 * a unit test: it appears on load, it goes on its own after ten seconds, an X
 * closes it, a click anywhere else closes it, and a click INSIDE it stops the
 * clock for good so a reader who is reading it does not have it yanked away.
 *
 * NOTHING IN HERE NAMES A CONSTELLATION. `FEATURED_ANCHOR_DAY` is 2026-08-20
 * and the rotation advances one entry per UTC day, so the two assertions in
 * `browser.spec.ts` that hard-coded "GPS" were correct for exactly one day and
 * then failed on every project every day after. The expected name is computed
 * here from the rotation itself against the catalog the site is actually
 * serving, so this file cannot expire at a midnight.
 */
import { expect, test, type Page } from "@playwright/test";

import { featuredToday } from "./featured-today";

const SHOTS = ".agent-scratch-railtoast/shots";

async function load(page: Page): Promise<void> {
  // c48ca6d made the note a ONCE-A-DAY event, stamped in localStorage the
  // moment it reaches the screen, and did not come back here. Two tests below
  // reload the page inside the same context and expect the note again; under
  // the day stamp that is impossible, so "closes on its X, and on a click
  // anywhere else" went red on a reload that had nothing to do with closing.
  // Diagnosed by clearing the stamp before the reload, which turns the same
  // failure green. Each test wants a fresh day, so every load starts as one.
  await page.addInitScript(() => {
    localStorage.setItem("space-explorer-hide-welcome-v1", "1");
    localStorage.removeItem("space-explorer-featured-toast-day-v1");
  });
  await page.goto("./");
  await expect(page.locator("#visible-count")).toContainText("Selected", { timeout: 120_000 });
}

test("says today's constellation on load, and says it about today's fleet", async ({ page }, testInfo) => {
  testInfo.setTimeout(300_000);
  await load(page);
  const toast = page.locator("#featured-toast");
  await expect(toast).toBeVisible({ timeout: 90_000 });
  const expected = await featuredToday(page);
  await expect(page.locator("#featured-toast-text")).toContainText(expected);
  // The sentence the owner asked for, whichever half wrote it.
  await expect(page.locator("#featured-toast-text"))
    .toContainText("Showing the Satellite/Constellation of the day");
  // AN ANNOUNCEMENT, NOT A DIALOG: it is inside a polite live region, it is
  // not a dialog, and it did not take the focus off the page on load.
  await expect(page.locator("#featured-toast-shell")).toHaveAttribute("role", "status");
  await expect(page.locator("#featured-toast-shell")).toHaveAttribute("aria-live", "polite");
  expect(await toast.getAttribute("role")).toBeNull();
  expect(await page.evaluate(() => document.activeElement?.id ?? "")).not.toBe("featured-toast-close");
  await page.screenshot({ path: `${SHOTS}/${testInfo.project.name}-toast-on-load.png` });

  // …and it does not sit on top of anything the reader needs. On a phone that
  // is the two doors and the legend; on a desktop it is the legend column.
  const box = await toast.boundingBox();
  expect(box).not.toBeNull();
  for (const selector of ["#mobile-panel-toggle", "#mobile-weather-toggle", "#map-key", "#satellite-legend"]) {
    const other = page.locator(selector);
    if (!(await other.isVisible())) continue;
    const rect = await other.boundingBox();
    if (rect === null) continue;
    const overlaps = box!.x < rect.x + rect.width && rect.x < box!.x + box!.width
      && box!.y < rect.y + rect.height && rect.y < box!.y + box!.height;
    expect(overlaps, `${selector} is covered by the constellation note`).toBe(false);
  }
});

test("goes on its own after ten seconds", async ({ page }, testInfo) => {
  testInfo.setTimeout(300_000);
  await load(page);
  const toast = page.locator("#featured-toast");
  await expect(toast).toBeVisible({ timeout: 90_000 });
  // Still there well inside the window, gone after it. Asserted from both
  // sides so a note that never appeared cannot pass as a note that expired.
  await expect(toast).toBeVisible({ timeout: 4_000 });
  await expect(toast).toBeHidden({ timeout: 15_000 });
});

test("closes on its X, and on a click anywhere else", async ({ page }, testInfo) => {
  testInfo.setTimeout(300_000);
  await load(page);
  const toast = page.locator("#featured-toast");
  await expect(toast).toBeVisible({ timeout: 90_000 });
  await page.locator("#featured-toast-close").click();
  await expect(toast).toBeHidden();

  await page.reload();
  await expect(page.locator("#visible-count")).toContainText("Selected", { timeout: 120_000 });
  await expect(toast).toBeVisible({ timeout: 90_000 });
  // Somewhere else entirely: the middle of the scene, well below the note.
  const scene = (await page.locator("#scene").boundingBox())!;
  await page.mouse.click(scene.x + scene.width / 2, scene.y + scene.height * 0.75);
  await expect(toast).toBeHidden();
  await page.screenshot({ path: `${SHOTS}/${testInfo.project.name}-toast-after-outside-click.png` });
});

test("a click inside it stops the clock for good", async ({ page }, testInfo) => {
  testInfo.setTimeout(300_000);
  await load(page);
  const toast = page.locator("#featured-toast");
  await expect(toast).toBeVisible({ timeout: 90_000 });
  // THE WHOLE POINT. A reader who has started reading must not have it taken
  // away mid-sentence, so this click cancels the ten seconds permanently.
  await page.locator("#featured-toast-text").click();
  await expect(toast).toHaveClass(/is-pinned/);
  await page.waitForTimeout(13_000);
  await expect(toast).toBeVisible({ timeout: 90_000 });
  await page.screenshot({ path: `${SHOTS}/${testInfo.project.name}-toast-pinned-past-ten-seconds.png` });

  // …and after that an outside click no longer closes it: only the X or
  // Escape does.
  const scene = (await page.locator("#scene").boundingBox())!;
  await page.mouse.click(scene.x + scene.width / 2, scene.y + scene.height * 0.75);
  await expect(toast).toBeVisible({ timeout: 90_000 });
  await page.keyboard.press("Escape");
  await expect(toast).toBeHidden();
});
