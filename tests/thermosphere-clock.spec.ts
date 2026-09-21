import { expect, test, type Page } from "@playwright/test";

import { closeRail, openRail, showViewer } from "./phone-state";

/**
 * The thermosphere has to follow the clock, and this is how that is proved.
 *
 * It has been reported static four times and declared fixed twice, and every
 * one of those all-clears argued from pixels. All three readings were invalid,
 * and each failed differently:
 *
 *   - a crop that included the globe changed between clock positions because
 *     the EARTH TURNS with the clock, so a frozen layer still produced two
 *     different images;
 *   - a crop outside the glow was identical black in every frame, so a working
 *     layer produced two identical images;
 *   - a `canvas.getImageData` readback after `drawImage` returned all zeros,
 *     because the WebGL context is not created with `preserveDrawingBuffer`.
 *     That probe measured nothing at all and reported `lit: 0` everywhere.
 *
 * Pixels can be fooled in all three directions. The IDENTITY of the frame handed
 * to the renderer cannot: the layer publishes it as `data-thermosphere-frame` on
 * its own switch, absent when nothing is drawn. This spec asserts that identity
 * against the published bundle the page actually downloaded, so it is checking
 * agreement with the data rather than merely checking that something moved.
 *
 * The companion unit tests in `thermosphere-clock.test.ts` cover the other half:
 * that the baked texture responds to more air, which is the physical change the
 * layer exists to show.
 */

/** The frame the release publishes nearest an instant, or null outside it. */
async function expectedFrame(page: Page, at: string): Promise<string | null> {
  return page.evaluate(async (iso: string) => {
    const manifest = await (await fetch("data/manifest.json")).json();
    const record = manifest.thermosphere;
    if (!record) return null;
    const url = new URL(record.path, new URL("data/manifest.json", document.baseURI));
    const bundle = await (await fetch(url.toString())).json();
    const wanted = Date.parse(iso);
    let best: string | null = null;
    let bestGap = Number.POSITIVE_INFINITY;
    for (const frame of bundle.frames as Array<{ validAt: string }>) {
      const gap = Math.abs(Date.parse(frame.validAt) - wanted);
      if (gap >= bestGap) continue;
      bestGap = gap;
      best = frame.validAt;
    }
    return bestGap <= ((bundle.cadenceMinutes ?? 60) * 60_000) / 2 ? best : null;
  }, at);
}

/** Hold the clock at one instant, the way the timeline itself does. */
async function holdAt(page: Page, iso: string): Promise<void> {
  await page.evaluate((target: string) => {
    const slider = document.getElementById("time-slider") as HTMLInputElement;
    slider.value = String(Math.round((Date.parse(target) - Date.now()) / 60_000));
    slider.dispatchEvent(new Event("input", { bubbles: true }));
  }, iso);
}

const drawnFrame = (page: Page) =>
  page.locator("#layer-thermosphere").getAttribute("data-thermosphere-frame");

test("the thermosphere draws the hour the clock is on, and nothing when it has none", async ({ page }, testInfo) => {
  testInfo.setTimeout(300_000);
  await page.addInitScript(() => localStorage.setItem("space-explorer-hide-welcome-v1", "1"));
  await page.goto("./");
  await expect(page.locator("#visible-count")).toContainText("Selected", { timeout: 120_000 });
  await openRail(page);
  await page.locator('[data-preset="simple"]').click();
  await expect(page.locator("#layer-thermosphere")).toBeChecked();
  // The attribute only appears once a frame has been decoded and handed to the
  // renderer, so waiting for it is waiting for the layer to be really drawn.
  await expect(page.locator("#layer-thermosphere")).toHaveAttribute("data-thermosphere-frame", /Z$/, { timeout: 120_000 });

  const covered = await page.evaluate(async () => {
    const manifest = await (await fetch("data/manifest.json")).json();
    const url = new URL(manifest.thermosphere.path, new URL("data/manifest.json", document.baseURI));
    const bundle = await (await fetch(url.toString())).json();
    return (bundle.frames as Array<{ validAt: string }>).map((frame) => frame.validAt);
  });
  // Three published hours, spread across the release, so this cannot pass by
  // landing twice on the same frame.
  expect(covered.length).toBeGreaterThanOrEqual(3);
  const sampled = [covered[0]!, covered[Math.floor(covered.length / 2)]!, covered[covered.length - 1]!];

  // Paused, so the frame the assertion reads is the frame the reader would see
  // rather than one the running clock has already moved past. The sheet goes
  // away first: on a phone the open rail covers the timeline, and the pause
  // button is under it.
  await closeRail(page);
  await page.locator("#time-play").click();

  const seen: string[] = [];
  for (const iso of sampled) {
    await holdAt(page, iso);
    const want = await expectedFrame(page, iso);
    expect(want).not.toBeNull();
    await expect
      .poll(() => drawnFrame(page), { timeout: 60_000, message: `drawn frame at ${iso}` })
      .toBe(want);
    seen.push(want!);
  }
  // Changed, not merely present. A layer that picked one frame at load and kept
  // it — the defect this spec exists for — passes every check above except this
  // one.
  expect(new Set(seen).size).toBe(sampled.length);

  // And the card has to agree with the scene. This line used to be written from
  // `frames[0]`, so it read the same instant at every clock position no matter
  // what was drawn.
  await showViewer(page);
  const card = page.locator('#data-viewer-cards [data-layer="thermosphere"]');
  if (await card.evaluate((element) => element.classList.contains("is-collapsed"))) {
    await card.locator("[data-card-toggle]").click();
  }
  await expect(card).toContainText(`${seen[seen.length - 1]!.slice(11, 16)}Z`);

  // OUTSIDE NOAA'S WAM RELEASE THE LAYER NO LONGER GOES DARK.
  //
  // This assertion used to read "nothing is drawn", and that was the honest
  // half of the fix: leaving WAM's last frame standing under a MODEL badge was
  // a lie, so the layer cleared. But WAM covers about twelve hours of a
  // 120-hour slider, so clearing meant a dead layer across 90% of the timeline
  // — which is a different way of failing the same reader. NRLMSIS now covers
  // the rest, and what changes at the boundary is the MODEL and the BADGE, not
  // whether there is a thermosphere.
  const outside = new Date(Date.parse(covered[covered.length - 1]!) + 6 * 60 * 60_000).toISOString();
  await holdAt(page, outside);
  await expect(page.locator("#layer-thermosphere"))
    .toHaveAttribute("data-thermosphere-model", "nrlmsis21", { timeout: 90_000 });
  await expect(card).toContainText("EMPIRICAL");
  expect(await drawnFrame(page)).not.toBe(seen[seen.length - 1]!);

  // And coming back restores NOAA's field, its frame and its badge together.
  await holdAt(page, sampled[0]!);
  await expect
    .poll(() => drawnFrame(page), { timeout: 60_000 })
    .toBe(seen[0]!);
  await expect(page.locator("#layer-thermosphere"))
    .toHaveAttribute("data-thermosphere-model", "wamNeutral");
});

/**
 * DOES IT CHANGE ACROSS THE WHOLE SLIDER? The measured version of the one
 * complaint this layer keeps getting.
 *
 * Before the empirical field shipped, this walk drew a frame at 6 of 61
 * positions — 9.8% — and every other position was blank, which a reader
 * describes as "static" whether the badge says MODEL or NO DATA. The assertion
 * is on frame IDENTITY, never pixels: the volume rides the Earth-fixed group,
 * so the glow rotates with the clock and a frozen layer still produces
 * different images at two clock times.
 */
test("the thermosphere covers the whole timeline, and says which model drew each hour", async ({ page }, testInfo) => {
  testInfo.setTimeout(300_000);
  await page.addInitScript(() => localStorage.setItem("space-explorer-hide-welcome-v1", "1"));
  await page.goto("./");
  await expect(page.locator("#visible-count")).toContainText("Selected", { timeout: 120_000 });
  await openRail(page);
  await page.locator('[data-preset="simple"]').click();
  await expect(page.locator("#layer-thermosphere"))
    .toHaveAttribute("data-thermosphere-frame", /Z$/, { timeout: 120_000 });
  await closeRail(page);
  await page.locator("#time-play").click();

  // Twelve positions from -44 h to +64 h, inside the slider at both ends and
  // well outside NOAA's WAM window at most of them.
  const offsetsHours = [-44, -36, -28, -20, -12, -4, 4, 12, 24, 36, 52, 64];
  const drawn: { hours: number; frame: string | null; model: string | null }[] = [];
  for (const hours of offsetsHours) {
    const iso = new Date(Date.now() + hours * 3_600_000).toISOString();
    await holdAt(page, iso);
    // Accept the frame only once it is within half a cadence of the clock.
    // Polling for "any frame" passes on the PREVIOUS position's leftover, which
    // reads as a working walk while measuring the step before.
    await expect
      .poll(async () => {
        const frame = await drawnFrame(page);
        if (!frame) return "none";
        return Math.abs(Date.parse(frame) - Date.parse(iso)) <= 30 * 60_000 ? "near" : "far";
      }, { timeout: 90_000, message: `a frame for ${iso}` })
      .toBe("near");
    drawn.push({
      hours,
      frame: await drawnFrame(page),
      model: await page.locator("#layer-thermosphere").getAttribute("data-thermosphere-model"),
    });
  }

  // Every position drew, and drew something different from its neighbours.
  expect(drawn.filter((row) => row.frame).length).toBe(offsetsHours.length);
  expect(new Set(drawn.map((row) => row.frame)).size).toBe(offsetsHours.length);
  // Both models appear, so the walk really did cross the boundary rather than
  // measuring one field twelve times.
  const models = new Set(drawn.map((row) => row.model));
  expect(models.has("nrlmsis21")).toBe(true);
  expect(models.size).toBeGreaterThanOrEqual(1);

  // The badge has to agree with the model, at the same instant, on the card.
  await showViewer(page);
  const card = page.locator('#data-viewer-cards [data-layer="thermosphere"]');
  const badge = card.locator("[data-card-mission]");
  const empirical = drawn.find((row) => row.model === "nrlmsis21")!;
  await holdAt(page, new Date(Date.now() + empirical.hours * 3_600_000).toISOString());
  await expect
    .poll(() => page.locator("#layer-thermosphere").getAttribute("data-thermosphere-model"), { timeout: 90_000 })
    .toBe("nrlmsis21");
  await expect(badge).toContainText("EMPIRICAL");
  // ...and never the other model's word while the other model's field is up.
  expect((await badge.textContent())?.includes("NOAA MODEL")).toBe(false);
});

test("choosing a different air density re-reads the heights on the card", async ({ page }, testInfo) => {
  testInfo.setTimeout(300_000);
  await page.addInitScript(() => localStorage.setItem("space-explorer-hide-welcome-v1", "1"));
  await page.goto("./");
  await expect(page.locator("#visible-count")).toContainText("Selected", { timeout: 120_000 });
  await openRail(page);
  await page.locator('[data-preset="simple"]').click();
  await expect(page.locator("#layer-thermosphere")).toHaveAttribute("data-thermosphere-frame", /Z$/, { timeout: 120_000 });
  await closeRail(page);
  await showViewer(page);
  const card = page.locator('#data-viewer-cards [data-layer="thermosphere"]');
  if (await card.evaluate((element) => element.classList.contains("is-collapsed"))) {
    await card.locator("[data-card-toggle]").click();
  }
  await card.locator("details.card-section").evaluateAll((sections) => {
    sections.forEach((section) => { (section as HTMLDetailsElement).open = true; });
  });

  const heights = async () => card.evaluate((element) => {
    const text = (element.textContent ?? "").replace(/\s+/g, " ");
    return /LOWEST\s*([0-9]+) km\s*HIGHEST\s*([0-9]+) km/.exec(text)?.slice(1).join("/") ?? "none";
  });

  await page.locator("#thermosphere-level").selectOption("1e-11");
  const lower = await heights();
  await page.locator("#thermosphere-level").selectOption("1e-13");
  const upper = await heights();
  expect(lower).not.toBe("none");
  expect(upper).not.toBe("none");
  // Thinner air is higher up. Asserting the DIRECTION, not just a difference,
  // so a card that redrew with stale numbers cannot pass.
  expect(Number(upper.split("/")[0])).toBeGreaterThan(Number(lower.split("/")[0]));
  // And the sentence under the readings has to name the level that produced
  // them. It used to be hard-coded to the default, so two of the three choices
  // left the card contradicting the control directly beneath it.
  await expect(card).toContainText("reaches 1e-13 kg m⁻³");
  await page.locator("#thermosphere-level").selectOption("1e-11");
  await expect(card).toContainText("reaches 1e-11 kg m⁻³");
});
