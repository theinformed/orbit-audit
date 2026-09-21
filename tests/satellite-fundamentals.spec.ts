import { expect, test } from "@playwright/test";

/**
 * The satellite-fundamentals routes, in a real browser.
 *
 * The unit suite proves the markup is right. It cannot prove the buttons are
 * bound, and that is the exact failure this project has shipped before: a
 * module that compiled, passed its tests, and was not reachable from the page.
 * mountSatelliteFundamentals() runs after the start-up [data-view] sweep, so
 * the only way to know it ran is to click.
 *
 * Deliberately light on waiting for the globe: none of this needs WebGL, and
 * the box these run on renders WebGL in software.
 */

const CHAPTERS = ["link", "spectrum", "orbits", "manoeuvre", "spacecraft", "environment", "inference"];

async function openTrack(page: import("@playwright/test").Page) {
  // Suppress the first-visit welcome before anything loads.
  //
  // #welcome-dialog is a real modal <dialog>, so it intercepts every pointer
  // event on the page behind it and a click on a chapter door retries until
  // the test times out. tests/browser.spec.ts sets the same key for the same
  // reason; the dialog itself has its own test and does not need another.
  await page.addInitScript(() => localStorage.setItem("space-explorer-hide-welcome-v1", "1"));
  await page.goto("/");
  // RETRY THE CLICK, do not race the boot.
  //
  // The nav buttons are bound inside boot(), after the published data has
  // loaded. On a box at load 100 with software WebGL that can take far longer
  // than any fixed wait, and a click that lands before the binding does
  // nothing at all - which then reads as "the route is broken" when it is not.
  // So: click, look, click again. Eight attempts over two minutes is generous
  // enough for the slowest observed boot and still fails in bounded time.
  //
  // The button is display:none below 820px and is still the app's own entry
  // point; clicking it through the DOM is what the mobile doors do internally,
  // which keeps one code path for all three viewports.
  for (let attempt = 0; attempt < 8; attempt += 1) {
    await page.evaluate(() => (document.querySelector('[data-view="learn-orbits"]') as HTMLElement | null)?.click());
    const opened = await page.locator("#content-body .fundamentals-index")
      .waitFor({ state: "visible", timeout: 15_000 })
      .then(() => true)
      .catch(() => false);
    if (opened) return;
  }
  throw new Error("the Satellite fundamentals view never opened");
}

test("the fundamentals index opens with seven doors", async ({ page }) => {
  await openTrack(page);
  await expect(page.locator("[data-fundamentals-page]")).toHaveCount(CHAPTERS.length);
  for (const id of CHAPTERS) {
    await expect(page.locator(`[data-fundamentals-page="${id}"]`)).toHaveCount(1);
  }
  // The defect this page replaced must not be able to come back.
  await expect(page.locator("#content-body .diagram")).toHaveCount(0);
});

// ONE TEST PER CHAPTER, not one loop over six.
//
// The loop version opened all six inside a single 240 s budget and timed out on
// a box under load - which says nothing about whether any chapter is broken.
// Split, each one gets its own budget and a failure names the chapter.
for (const id of CHAPTERS) {
  test(`chapter ${id} opens, carries its sources, and can be left again`, async ({ page }) => {
    await openTrack(page);
    await page.locator(`[data-fundamentals-page="${id}"]`).first().click();
    await expect(page.locator("#content-body .fundamentals-page")).toBeVisible();
    await expect(page.locator("#content-body .fund-sources")).toBeVisible();
    await expect(page.locator("#content-body .fund-live").first()).toBeVisible();
    // Every chapter must draw at least one real figure where the glow box was.
    await expect(page.locator("#content-body .fund-figure svg").first()).toBeVisible();
    // Nothing may push the page sideways at any viewport. The figures keep a
    // 760 px floor below the narrow breakpoint and scroll inside their own box.
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
    expect(overflow, `${id} overflows horizontally`).toBe(false);
    await page.locator("[data-fundamentals-index]").first().click();
    await expect(page.locator("#content-body .fundamentals-index")).toBeVisible();
  });
}

test("a chapter's pager moves to the next chapter", async ({ page }) => {
  await openTrack(page);
  await page.locator('[data-fundamentals-page="link"]').first().click();
  await expect(page.locator("#content-body .fund-pager")).toBeVisible();
  await page.locator('.fund-pager [data-fundamentals-page="spectrum"]').click();
  await expect(page.locator("#content-body h1")).toContainText("Spectrum and the link budget");
});

test("a see-it-live door actually leaves for the explorer", async ({ page }) => {
  await openTrack(page);
  await page.locator('[data-fundamentals-page="orbits"]').first().click();
  await page.locator('.fund-live [data-fundamentals-goto="explore"]').first().click();
  // openContent("explore") closes the content view and hands the globe back.
  await expect(page.locator("#content-view")).toBeHidden();
});

test("a see-it-live door can also send the reader to another track", async ({ page }) => {
  await openTrack(page);
  await page.locator('[data-fundamentals-page="environment"]').first().click();
  await page.locator('.fund-live [data-fundamentals-goto="events"]').first().click();
  await expect(page.locator("#content-body")).toContainText(/historical events/i, { timeout: 30_000 });
});
