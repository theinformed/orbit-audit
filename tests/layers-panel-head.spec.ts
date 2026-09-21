import { expect, test, type Page } from "@playwright/test";

/**
 * THE FOLDED PANEL HAS TO SAY WHICH LAYERS IT HOLDS, AND AN OPENED CARD HAS TO
 * GET ROOM.
 *
 * Sean, 2026-08-26: "when we add a layer the layer browser window starts
 * collapsed. The window should at least start showing the collapsed layer - the
 * name of the layer - so that people can see what is being shown." And: "when I
 * expand the layer in the window, the window doesn't enlarge at all to show
 * enough. It needs to expand vertically and a bit horizontally."
 *
 * Both are geometry and text over a live globe, so they are checked here rather
 * than in a unit test: the ceiling is a CSS `min()` of three terms, one of which
 * is written from the live position of the LEGEND, and no unit test can see it.
 *
 * The folded state is reached the way a reader reaches it — the panel remembers
 * being folded (`space-explorer-data-explorer-collapsed-v2`), and the X sets
 * that flag, so any reader who has ever closed the panel opens folded from then
 * on. That is exactly the state Sean was in.
 */

async function ready(page: Page): Promise<void> {
  await expect(page.locator("#visible-count")).toContainText("Selected", { timeout: 120_000 });
}

/**
 * Opens or shuts the phone's control sheet. A no-op anywhere the rail is laid
 * out on the page, which is every viewport wider than 820 px.
 *
 * Needed because this file's first run failed all four of its phone cases in
 * the same place: on a phone every layer switch lives in a bottom sheet that
 * is SHUT on arrival, so the space-weather half of the rail is translated
 * off the bottom of the screen and Playwright retried the click 190 times
 * over four minutes reporting "element is outside of the viewport". Nothing
 * about the panel was wrong; the test simply never opened the drawer.
 */
async function setRail(page: Page, open: boolean): Promise<void> {
  const toggle = page.locator("#mobile-panel-toggle");
  if (!await toggle.isVisible()) return;
  const isOpen = await page.locator("#control-rail").evaluate((rail) => rail.classList.contains("is-open"));
  if (isOpen !== open) await toggle.click();
  await expect(page.locator("#control-rail")).toHaveClass(open ? /is-open/ : /^(?!.*is-open).*$/);
}

/**
 * Switches one layer on and waits for its switch to report itself on.
 *
 * NOT `.check()`, and not a Playwright handle held across the click. The rail
 * REBUILDS its layer controls when a layer changes, so the input node a
 * locator resolved a moment ago can be gone by the time the click lands --
 * "locator.scrollIntoViewIfNeeded: Element is not attached to the DOM",
 * observed on #layer-tec, and `.check()`'s own retry loop walks straight into
 * the same thing: it clicks, asserts `checked` early, gets false because it is
 * looking at a fresh node, and clicks again, which turns the layer back off.
 * That is how #layer-aurora and #layer-geospace burned five-minute timeouts.
 *
 * The site is not at fault, and this must not paper over one that would be:
 * probed directly, ONE click leaves #layer-geospace checked and it is still
 * checked six seconds later. So the element is re-resolved INSIDE the page on
 * the same tick it is used -- and hit-tested first, so a switch that is
 * genuinely covered by another panel still fails here rather than being
 * clicked through the thing covering it.
 */
async function switchLayerOn(page: Page, selector: string): Promise<void> {
  const reachable = await page.evaluate((sel) => {
    const element = document.querySelector(sel) as HTMLInputElement | null;
    if (!element) return "(missing)";
    element.scrollIntoView({ block: "center" });
    const box = element.getBoundingClientRect();
    const hit = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
    if (!hit) return "(nothing)";
    return hit === element || element.contains(hit) || hit.contains(element)
      ? "self"
      : `${hit.tagName}#${hit.id || "-"}`;
  }, selector);
  expect(reachable, `${selector} could not be reached to switch it on`).toBe("self");
  await page.evaluate((sel) => {
    const element = document.querySelector(sel) as HTMLInputElement | null;
    if (element && !element.checked) element.click();
  }, selector);
  await page.waitForFunction(
    (sel) => (document.querySelector(sel) as HTMLInputElement | null)?.checked === true,
    selector,
    { timeout: 120_000 },
  );
}

async function switchOn(page: Page, ids: readonly string[]): Promise<void> {
  await setRail(page, true);
  for (const id of ids) await switchLayerOn(page, `#layer-${id}`);
  // ...and shut again, because the panel this file is about floats over the
  // globe and a sheet covering 72svh of the screen is not the state a reader
  // looks at it in. On a desktop this returns without touching anything.
  await setRail(page, false);
  await expect(page.locator("#data-viewer")).toBeVisible();
  await expect(page.locator("#data-viewer-cards > *")).toHaveCount(ids.length);
}

test("a folded panel names the layer it is holding", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("space-explorer-hide-welcome-v1", "1");
    localStorage.setItem("space-explorer-data-explorer-collapsed-v2", "1");
  });
  await page.goto("./");
  await ready(page);
  await switchOn(page, ["thermosphere"]);

  const panel = page.locator("#data-viewer");
  await expect(panel, "the reader's own folded choice must still be remembered").toHaveClass(/is-collapsed/);

  // The count Sean asked for five days earlier stays...
  await expect(page.locator("#data-viewer-title")).toHaveText(/1 Space Weather Layer$/);
  // ...and the NAME is the thing that was missing.
  const names = page.locator("#data-viewer-layers");
  await expect(names).toBeVisible();
  await expect(names).toHaveText("Thermosphere height");
  // Which is the same name its card carries, so folding does not rename it.
  await expect(page.locator('#data-viewer-cards [data-layer="thermosphere"] [data-card-name]'))
    .toHaveText("Thermosphere height");
});

test("a folded panel with several on lists them, and never hides that they exist", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("space-explorer-hide-welcome-v1", "1");
    localStorage.setItem("space-explorer-data-explorer-collapsed-v2", "1");
  });
  await page.goto("./");
  await ready(page);
  await switchOn(page, ["thermosphere", "aurora", "solar-wind"]);

  const names = page.locator("#data-viewer-layers");
  await expect(names).toBeVisible();
  const text = (await names.textContent()) ?? "";
  expect(text.split(" · ")).toHaveLength(3);
  // The line may ELLIPSE — a 216 px slot cannot hold three layer names — but
  // the count above it is what tells the reader how many there are, so nothing
  // is hidden by the truncation. That is the load-bearing part.
  await expect(page.locator("#data-viewer-title")).toHaveText(/^3 Space Weather Layers$/);
  // ...and the full list is reachable without unfolding, by pointer and by
  // screen reader both.
  await expect(page.locator("#data-viewer-head")).toHaveAttribute("title", new RegExp(text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  await expect(page.locator("#data-viewer")).toHaveAttribute("aria-label", /Thermosphere height/);
});

test("the names line stands down once the panel is open", async ({ page }) => {
  // The cards below then name every layer themselves, and this file has
  // already retired one reading printed ten pixels above the table it
  // summarised. Same rule.
  await page.addInitScript(() => localStorage.setItem("space-explorer-hide-welcome-v1", "1"));
  await page.goto("./");
  await ready(page);
  await switchOn(page, ["thermosphere"]);
  if (await page.locator("#data-viewer.is-collapsed").count()) {
    await page.locator("#data-viewer-head").click();
  }
  await expect(page.locator("#data-viewer")).not.toHaveClass(/is-collapsed/);
  await expect(page.locator("#data-viewer-layers")).toBeHidden();
});

test("opening a layer's card makes the panel bigger, and never with an inline height", async ({ page }, testInfo) => {
  testInfo.setTimeout(300_000);
  // A phone runs this too. It was skipped outright at first, for a reason that
  // only ever applied to the WIDTH — the phone strip is pinned to both edges,
  // so it cannot widen and is not asked to — and skipping the whole case left
  // the one screen Sean actually reads this on unmeasured. The height rule is
  // the phone's own (46% -> 60% of the scene) and is checked here like any
  // other.
  const widens = testInfo.project.name !== "mobile";

  await page.addInitScript(() => localStorage.setItem("space-explorer-hide-welcome-v1", "1"));
  await page.goto("./");
  await ready(page);
  await switchOn(page, ["thermosphere"]);
  if (await page.locator("#data-viewer.is-collapsed").count()) {
    await page.locator("#data-viewer-head").click();
  }
  const panel = page.locator("#data-viewer");
  await expect(panel).not.toHaveClass(/is-collapsed/);

  const box = async () => panel.evaluate((node) => {
    const rect = node.getBoundingClientRect();
    return {
      width: Math.round(rect.width),
      height: Math.round(rect.height),
      bottom: Math.round(rect.bottom),
      inlineHeight: (node as HTMLElement).style.height,
      body: (() => {
        const body = document.getElementById("data-viewer-body")!;
        return { scroll: body.scrollHeight, client: body.clientHeight };
      })(),
    };
  });

  const shut = await box();
  await page.locator('#data-viewer-cards [data-layer="thermosphere"] [data-card-toggle]').click();
  await expect(page.locator('#data-viewer-cards [data-layer="thermosphere"]')).not.toHaveClass(/is-collapsed/);
  const open = await box();

  // Vertically, and "a bit" horizontally, which is what was asked for.
  expect(open.height, "the panel did not grow when the card was opened").toBeGreaterThan(shut.height);
  if (widens) {
    expect(open.width, "the panel did not widen when the card was opened").toBeGreaterThan(shut.width);
    // ...and the opened card actually FITS, which is the whole complaint. On
    // the shipped build this card wanted 519 px in a 394 px body.
    expect(open.body.scroll, "the opened card still does not fit").toBeLessThanOrEqual(open.body.client + 8);
  } else {
    // A 390 px strip is already as wide as the scene lets it be.
    expect(open.width, "the phone strip changed width, which it has no room to do").toBe(shut.width);
    // FITTING is not promised on a phone and must not be claimed: an 844 px
    // screen cannot hold every card whole, and a rule that tried would push
    // the panel over the timeline. What is promised is that opening the card
    // buys real room — measured at 241 -> 451 px on an iPhone 13, which is the
    // 46% -> 60% step — and that the panel still ends inside the window, which
    // the bound below checks.
    expect(open.height - shut.height, "opening the card on a phone bought less than 100 px").toBeGreaterThan(100);
  }

  // THE DEFECT THAT MUST NOT COME BACK. A reader-dragged size used to be
  // restored as an inline `height`, which is a floor as well as a ceiling and
  // propped a one-card panel open at 432 px. Every rule here is a max-height.
  expect(shut.inlineHeight, "an inline height came back on the folded-card panel").toBe("");
  expect(open.inlineHeight, "an inline height came back on the opened-card panel").toBe("");

  // Bounded to the scene, still: the panel must not run off the window, and it
  // must not cover the legend's own head, which is the one control that would
  // make room for it.
  expect(open.bottom).toBeLessThanOrEqual(page.viewportSize()!.height);
  const legendToggle = await page.evaluate(() => {
    const element = document.querySelector("#map-key-toggle");
    if (!element) return "(missing)";
    const rect = element.getBoundingClientRect();
    const hit = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
    if (!hit) return "(nothing)";
    return hit === element || element.contains(hit) || hit.contains(element) ? "self" : `${hit.tagName}#${hit.id || "-"}`;
  });
  expect(legendToggle, "the grown panel covered the legend's fold toggle").toBe("self");
});

test("an eight-layer panel with a card open still fits the window", async ({ page }, testInfo) => {
  testInfo.setTimeout(300_000);
  await page.addInitScript(() => localStorage.setItem("space-explorer-hide-welcome-v1", "1"));
  await page.goto("./");
  await ready(page);
  await switchOn(page, ["thermosphere", "ionosphere", "tec", "aurora", "geospace", "ring-current", "solar-wind", "radiation"]);
  if (await page.locator("#data-viewer.is-collapsed").count()) {
    await page.locator("#data-viewer-head").click();
  }
  await page.locator("#data-viewer-cards [data-card-toggle]").first().click();
  const rect = await page.locator("#data-viewer").evaluate((node) => {
    const box = node.getBoundingClientRect();
    return { top: Math.round(box.top), bottom: Math.round(box.bottom), inlineHeight: (node as HTMLElement).style.height };
  });
  expect(rect.top).toBeGreaterThanOrEqual(0);
  expect(rect.bottom).toBeLessThanOrEqual(page.viewportSize()!.height);
  expect(rect.inlineHeight).toBe("");
});
