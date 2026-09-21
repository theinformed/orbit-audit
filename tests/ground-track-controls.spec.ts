import { expect, test } from "@playwright/test";

/**
 * The ground-track window controls, driven the way a visitor drives them.
 *
 * The unit tests hold the geometry and the grammar. This holds the thing the
 * owner actually complained about: that the controls under the map did not say
 * what they were for, and that typing a date into them changed nothing useful.
 * It runs against the shipped module with a real SGP4 propagator behind it, so
 * a change that leaves the parser correct but the wiring dead is caught here.
 */
const harness = "http://127.0.0.1:4174/tests/ground-track-controls.harness.html";

test.describe.configure({ mode: "serial" });

test.beforeEach(async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(harness);
  await page.waitForFunction(() => (window as any).groundTrackHarnessReady === true);
  expect(errors).toEqual([]);
});

async function mount(page: import("@playwright/test").Page, name: string, at = "2026-08-07T23:54:00Z", mask = 0) {
  await page.evaluate(
    ([caseName, iso, minimumElevation]) =>
      (window as any).groundTrackHarness.mount(caseName, iso, minimumElevation),
    [name, at, mask] as const,
  );
  await expect(page.locator(".gtm-figure svg")).toBeVisible();
}

test.describe("track length", () => {
  test("offers whole orbits and a day, and redraws the window on click", async ({ page }) => {
    await mount(page, "leo");
    const buttons = page.locator(".gtm-span-buttons button");
    await expect(buttons).toHaveCount(4);
    await expect(buttons.nth(0)).toContainText("1 orbit");
    await expect(buttons.nth(3)).toContainText("24 hours");
    // The default is what it always was: one orbital period, already lit.
    await expect(buttons.nth(0)).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator(".gtm-timeline")).toContainText("94.8 min");

    await buttons.nth(1).click();
    await expect(buttons.nth(1)).toHaveAttribute("aria-pressed", "true");
    await expect(buttons.nth(0)).toHaveAttribute("aria-pressed", "false");
    await expect(page.locator(".gtm-timeline")).toContainText("4.7 h");
    await expect(page.locator(".gtm-figure svg")).toContainText("3 ORBITS");

    await buttons.nth(3).click();
    await expect(page.locator(".gtm-figure svg")).toContainText("24 HOURS");
    await expect(page.locator(".gtm-timeline")).toContainText("24 h");
  });

  test("hands a caller a caption sentence that follows the window", async ({ page }) => {
    await mount(page, "leo");
    // Untouched, the sentence is the one the dialog always showed, plus the
    // window's own bounds — so wiring it to the lead line regresses nothing.
    expect(await page.evaluate(() => (window as any).groundTrackHarness.windowDescription()))
      .toContain("One 94.8-minute orbital period projected onto the rotating Earth");

    await page.locator(".gtm-span-buttons button").nth(1).click();
    const changed = await page.evaluate(() => (window as any).groundTrackHarness.windowDescription());
    expect(changed).toContain("Showing 3 orbits");
    expect(changed).toContain("4.7 h of ground track");
  });

  test("does not offer a geostationary spacecraft the same window twice", async ({ page }) => {
    await mount(page, "geo");
    const buttons = page.locator(".gtm-span-buttons button");
    await expect(buttons).toHaveCount(3);
    await expect(buttons.nth(0)).toContainText("1 orbit · 24 h");
    await expect(buttons.nth(0)).toContainText("1 orbit is 24 hours for this spacecraft");
    // One button, not two: no separate "24 hours" that would draw the same track.
    await expect(page.locator(".gtm-span-buttons button b"))
      .toHaveText(["1 orbit · 24 h", "3 orbits", "6 orbits"]);
  });
});

test.describe("the window editor", () => {
  test("is closed until it is opened, and holds one time field, not two", async ({ page }) => {
    await mount(page, "leo");
    const editor = page.locator("[id^=gtm-window-editor]");
    await expect(editor).toBeHidden();
    // The old design's two always-present boxes are gone: with the editor shut
    // there is no typing surface competing with the slider at all.
    await expect(page.locator(".gtm-timeline input[type=text]:visible")).toHaveCount(0);

    await page.locator(".gtm-window-open").click();
    await expect(editor).toBeVisible();
    await expect(editor.locator("input[type=text]")).toHaveCount(2);
    await expect(editor).toContainText("Centre the window on");
    await expect(editor).toContainText("Span of track to draw");
    // Both zones remain available and are clearly distinguished.
    await expect(editor.locator("input[type=radio]")).toHaveCount(2);
    await expect(editor).toContainText("UTC");
    await expect(editor).toContainText("Local —");
  });

  test("moves the window to yesterday instead of showing nothing useful", async ({ page }) => {
    await mount(page, "leo");
    await page.locator(".gtm-window-open").click();
    const editor = page.locator("[id^=gtm-window-editor]");
    const timeField = editor.locator("input[type=text]").first();
    await timeField.fill("yesterday");
    // It says how it read the text before anything is committed.
    await expect(editor).toContainText("Read as 2026-08-06");

    await editor.getByRole("button", { name: "Draw this window" }).click();
    await expect(editor).toBeHidden();
    // The drawn track really is a day earlier — the whole point of the fix.
    await expect(page.locator(".gtm-timeline")).toContainText("08-06");
    const selected = await page.evaluate(() => (window as any).groundTrackHarness.selectedTimeIso());
    expect(selected.slice(0, 10)).toBe("2026-08-06");
  });

  test("reads a date, a bare clock time and an offset, saying which zone each was", async ({ page }) => {
    await mount(page, "leo");
    await page.locator(".gtm-window-open").click();
    const editor = page.locator("[id^=gtm-window-editor]");
    const timeField = editor.locator("input[type=text]").first();

    await timeField.fill("2026-08-07 06:30");
    await expect(editor).toContainText("Read as 2026-08-07 06:30Z");
    await expect(editor).toContainText("read as UTC");

    await timeField.fill("06:30");
    await expect(editor).toContainText("date taken from the window on screen");

    await timeField.fill("08/07 7:38 pm");
    await expect(editor).toContainText("month/day");
    await expect(editor).toContainText("2026-08-07 19:38Z");

    await timeField.fill("2026-08-07T15:38-04:00");
    await expect(editor).toContainText("2026-08-07 19:38Z");
    await expect(editor).toContainText("zone taken from what you typed");

    // Switching the selector to local re-reads the same text in that zone.
    await editor.locator("input[type=radio]").nth(1).check();
    await timeField.fill("2026-08-07 06:30");
    await expect(editor).toContainText("read in ");
  });

  test("says so in place when the text is unreadable, and does not move", async ({ page }) => {
    await mount(page, "leo");
    const before = await page.evaluate(() => (window as any).groundTrackHarness.selectedTimeIso());
    await page.locator(".gtm-window-open").click();
    const editor = page.locator("[id^=gtm-window-editor]");
    await editor.locator("input[type=text]").first().fill("sometime last tuesday");
    await expect(editor).toContainText("Not readable yet");
    await editor.getByRole("button", { name: "Draw this window" }).click();
    // Still open, still says what it could not read, and nothing jumped.
    await expect(editor).toBeVisible();
    await expect(page.locator(".gtm-timeline")).toContainText("Could not read");
    expect(await page.evaluate(() => (window as any).groundTrackHarness.selectedTimeIso())).toBe(before);
  });

  test("takes a hand-typed span in orbits", async ({ page }) => {
    await mount(page, "leo");
    await page.locator(".gtm-window-open").click();
    const editor = page.locator("[id^=gtm-window-editor]");
    const spanField = editor.locator("input[type=text]").nth(1);
    await spanField.fill("4 orbits");
    await expect(editor).toContainText("Reads as 6.3 h");
    await editor.getByRole("button", { name: "Draw this window" }).click();
    await expect(page.locator(".gtm-timeline")).toContainText("6.3 h");
    await expect(page.locator(".gtm-figure svg")).toContainText("6.3 H");
  });
});

test.describe("the coverage footprint", () => {
  test("shades the ground the spacecraft can see, using the globe's mask", async ({ page }) => {
    await mount(page, "leo", "2026-08-07T23:54:00Z", 5);
    const toggle = page.locator(".gtm-footprint-toggle input");
    await expect(page.locator(".gtm-footprint-toggle")).toContainText("5° mask");
    await expect(page.locator(".gtm-figure svg path[fill='#f5c96a']")).toHaveCount(0);

    await toggle.check();
    const shapes = page.locator(".gtm-figure svg path[fill='#f5c96a']");
    await expect(shapes).not.toHaveCount(0);
    await expect(page.locator(".gtm-figure svg")).toContainText("In view now");
    // No NaN reaches the path data: an SVG path carrying one draws nothing.
    for (const value of await shapes.evaluateAll((paths) => paths.map((path) => path.getAttribute("d") ?? ""))) {
      expect(value).not.toContain("NaN");
    }
  });

  test("holds together over the pole and over the antimeridian", async ({ page }) => {
    await mount(page, "polar");
    await page.locator(".gtm-footprint-toggle input").check();
    const svg = page.locator(".gtm-figure svg");
    const slider = page.locator(".gtm-slider");
    const minimum = Number(await slider.getAttribute("min"));
    const maximum = Number(await slider.getAttribute("max"));

    // Walk the whole orbit: a near-polar pass crosses both traps.
    let sawFootprint = 0;
    for (let step = 0; step <= 12; step += 1) {
      // Set the value directly rather than through fill(), which rejects any
      // value off the range input's own step grid.
      await slider.evaluate((element, value) => {
        (element as HTMLInputElement).value = String(value);
        element.dispatchEvent(new Event("input", { bubbles: true }));
      }, Math.round(minimum + ((maximum - minimum) * step) / 12));
      const paths = await svg.locator("path[fill='#f5c96a']")
        .evaluateAll((elements) => elements.map((element) => element.getAttribute("d") ?? ""));
      for (const value of paths) {
        expect(value).not.toContain("NaN");
        expect(value).not.toContain("Infinity");
      }
      if (paths.length > 0) sawFootprint += 1;
    }
    expect(sawFootprint).toBe(13);
  });
});

test.describe("without a propagator", () => {
  test("hides the controls it cannot honour and says plainly what it can't do", async ({ page }) => {
    await page.evaluate(() =>
      (window as any).groundTrackHarness.mountWithoutPropagator("leo", "2026-08-07T23:54:00Z"));
    await expect(page.locator(".gtm-figure svg")).toBeVisible();
    // No dead span buttons and no dead footprint toggle.
    await expect(page.locator(".gtm-span-buttons button")).toHaveCount(0);
    await expect(page.locator(".gtm-footprint-toggle")).toBeHidden();

    await page.locator(".gtm-window-open").click();
    const editor = page.locator("[id^=gtm-window-editor]");
    await expect(editor).toContainText("fixed window");
    await editor.locator("input[type=text]").first().fill("yesterday");
    await editor.getByRole("button", { name: "Draw this window" }).click();
    // It never silently jumps: it names the window it does cover.
    await expect(page.locator(".gtm-timeline")).toContainText("outside the window this map covers");
  });
});
