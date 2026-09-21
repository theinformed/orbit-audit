/**
 * THE RAIL, DRIVEN: that both halves of it are present at once, and the four
 * arrangements of the owner list.
 *
 * Green unit tests are not evidence that a page renders. Everything here is
 * asked of the real page, and the screenshots it leaves behind are the record
 * that somebody looked.
 */
import { expect, test, type Page } from "@playwright/test";

import { openRail } from "./phone-state";

const SHOTS = ".agent-scratch-railtoast/shots";

async function load(page: Page): Promise<void> {
  await page.addInitScript(() => {
    localStorage.setItem("space-explorer-hide-welcome-v1", "1");
    // The two sort toggles persist per browser, so every test starts from the
    // shipped default — ONCE. This script runs again on a reload, and wiping
    // the preference there would make the test that checks persistence pass
    // for the wrong reason and fail for the right one.
    if (sessionStorage.getItem("owner-sort-reset-v1") === null) {
      sessionStorage.setItem("owner-sort-reset-v1", "1");
      localStorage.removeItem("space-explorer-owner-sort-v1");
    }
  });
  await page.goto("./");
  await expect(page.locator("#visible-count")).toContainText("Selected", { timeout: 120_000 });
  await openRail(page);
  // The note over the globe is not what this file is about, and on a phone it
  // shares the top of the scene with the windows that open there.
  await page.locator("#featured-toast-close").click({ timeout: 15_000 }).catch(() => {});
}

/**
 * SUPERSEDED, 2026-08-28. This test drove the three Explorer Modes and asserted
 * which sections each of them hid: Satellites hid conditions and the layer
 * list, Space weather hid the catalog, Combined hid nothing. Sean retired the
 * whole idea - "get rid of the Explorer Mode and Satellite/Space Weather/
 * Combined stuff on the mobile and on desktop version" - so what it was
 * measuring no longer exists to be measured.
 *
 * What replaced it is the surviving half of the old Combined behaviour, and it
 * is a stronger claim than the one this test made: NOTHING in the rail hides
 * anything. The three sections are all in the document, all unhidden, at once.
 * Which of them is on SCREEN is the two-rail arrangement's business and is
 * pinned by tests/rail-chrome.test.ts, so it is deliberately not restated here.
 */
test("no section of the rail is hidden from another", async ({ page }, testInfo) => {
  testInfo.setTimeout(300_000);
  await load(page);
  const conditions = page.locator(".conditions-section");
  const layers = page.locator(".environment-section");
  const catalog = page.locator("#catalog-details");

  for (const [name, section] of [["conditions", conditions], ["layers", layers], ["catalog", catalog]] as const) {
    await expect(section, `${name} is attached`).toHaveCount(1);
    expect(await section.evaluate((node) => {
      for (let el: HTMLElement | null = node as HTMLElement; el; el = el.parentElement) {
        if (el.hasAttribute("hidden")) return el.className || el.tagName;
      }
      return null;
    }), `${name} is hidden by an ancestor`).toBeNull();
  }

  // And the control that used to do the hiding is not in the page at all.
  await expect(page.locator("[data-explorer-mode]")).toHaveCount(0);
  await expect(page.locator(".mode-section")).toHaveCount(0);
  await page.screenshot({ path: `${SHOTS}/${testInfo.project.name}-rail-no-modes.png` });
});

/** The owner fold, opened. */
async function openOwnerFacet(page: Page): Promise<void> {
  const fold = page.locator("#owner-section");
  if (!(await fold.evaluate((node) => (node as HTMLDetailsElement).open))) {
    await fold.locator("> summary").click();
  }
  await expect(page.locator("#owner-filters")).toBeVisible();
}

const checkedOwners = (page: Page) => page.locator("[data-owner]:checked").count();
const groups = (page: Page) => page.locator("#owner-filters > details.facet-group:not([hidden])");
/** Open groups anywhere in the tree — every one of them ships SHUT. */
const openGroups = (page: Page) => page.locator("#owner-filters details.facet-group[open]");

test("the owner list arranges four ways and never changes what is ticked", async ({ page }, testInfo) => {
  testInfo.setTimeout(600_000);
  await load(page);
  await openOwnerFacet(page);
  const byNumber = page.locator("#owner-sort-count");
  const alphabetically = page.locator("#owner-sort-alpha");
  const summary = page.locator("#owner-facet-state");

  // A selection to protect across every regroup below. The featured
  // constellation has already ticked its own owners, so this is a real
  // selection rather than an empty one.
  const ticked = await checkedOwners(page);
  expect(ticked).toBeGreaterThan(0);
  const summaryText = await summary.textContent();

  // ---- NEITHER: the flat list, unchanged -------------------------------
  await expect(groups(page)).toHaveCount(0);
  await expect(page.locator("#owner-filters > label").first()).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/${testInfo.project.name}-owners-flat.png` });

  // ---- ALPHABETICALLY: A–Z, every group shut ---------------------------
  await alphabetically.click();
  await expect(alphabetically).toHaveAttribute("aria-pressed", "true");
  const letters = await groups(page).locator("> summary > span").allTextContents();
  expect(letters.length).toBeGreaterThan(5);
  expect(letters).toEqual([...letters].filter((l) => l !== "#").sort().concat(letters.includes("#") ? ["#"] : []));
  await expect(openGroups(page)).toHaveCount(0);
  expect(await checkedOwners(page)).toBe(ticked);
  await expect(summary).toHaveText(summaryText!);
  await page.screenshot({ path: `${SHOTS}/${testInfo.project.name}-owners-alphabetical.png` });

  // …and a group opens, with its members inside and its count on the header.
  const firstLetter = groups(page).first();
  await firstLetter.locator("summary").click();
  await expect(firstLetter).toHaveAttribute("open", "");
  const shownRows = await firstLetter.locator(".facet-group-grid > label:visible").count();
  expect(shownRows).toBeGreaterThan(0);
  const headline = await firstLetter.locator("> summary > .facet-group-count").textContent();
  expect(Number((headline ?? "").replace(/[^0-9]/g, ""))).toBe(shownRows);
  await page.screenshot({ path: `${SHOTS}/${testInfo.project.name}-owners-alphabetical-expanded.png` });
  await firstLetter.locator("summary").click();

  // ---- BY NUMBER: count bands, largest first, all shut -----------------
  await alphabetically.click();
  await byNumber.click();
  await expect(byNumber).toHaveAttribute("aria-pressed", "true");
  await expect(alphabetically).toHaveAttribute("aria-pressed", "false");
  const bands = await groups(page).locator("> summary > span").allTextContents();
  expect(bands.length).toBeGreaterThan(1);
  expect(bands[0]).toBe("1000+");
  // Descending, and no band is drawn empty.
  const ladder = ["1000+", "500–999", "100–499", "50–99", "25–49", "10–24", "5–9", "2–4", "1"];
  expect(bands).toEqual(ladder.filter((label) => bands.includes(label)));
  const counts = await groups(page).locator("> summary > .facet-group-count").allTextContents();
  counts.forEach((count) => expect(Number(count.replace(/[^0-9]/g, ""))).toBeGreaterThan(0));
  await expect(openGroups(page)).toHaveCount(0);
  expect(await checkedOwners(page)).toBe(ticked);
  await page.screenshot({ path: `${SHOTS}/${testInfo.project.name}-owners-by-number.png` });

  // ---- BOTH: bands at the top, A–Z inside each -------------------------
  await alphabetically.click();
  await expect(byNumber).toHaveAttribute("aria-pressed", "true");
  await expect(alphabetically).toHaveAttribute("aria-pressed", "true");
  const topBand = groups(page).first();
  await expect(topBand.locator("> summary > span")).toHaveText("1000+");
  await expect(topBand.locator("> details.facet-group")).not.toHaveCount(0);
  await expect(openGroups(page)).toHaveCount(0);
  expect(await checkedOwners(page)).toBe(ticked);
  await page.screenshot({ path: `${SHOTS}/${testInfo.project.name}-owners-both.png` });

  // SORTING NEVER TICKS OR UNTICKS. The two selection buttons that used to be
  // pressed here are gone (2026-08-28) — the arrangement toggles Sean asked to
  // keep are the only buttons left in this list, and this is the assertion
  // that they arrange and nothing more.
  expect(await checkedOwners(page)).toBe(ticked);
  await page.locator("#owner-sort-count").click();
  expect(await checkedOwners(page)).toBe(ticked);
  await page.locator("#owner-sort-alpha").click();
  expect(await checkedOwners(page)).toBe(ticked);
});

test("the owner search reaches into a shut group and puts the folds back", async ({ page }, testInfo) => {
  testInfo.setTimeout(600_000);
  await load(page);
  await openOwnerFacet(page);
  await page.locator("#owner-sort-alpha").click();
  await expect(groups(page).first()).toBeVisible();
  await expect(openGroups(page)).toHaveCount(0);

  // A query REVEALS its matches rather than leaving them behind a shut header,
  // and every group with nothing in it goes away.
  await page.locator("#owner-search").fill("iridium");
  await expect(page.locator("#owner-filters label:visible").first()).toContainText(/iridium/i);
  const visible = await page.locator("#owner-filters label:visible").allTextContents();
  expect(visible.length).toBeGreaterThan(0);
  visible.forEach((text) => expect(text.toLowerCase()).toContain("iridium"));
  const shown = await groups(page).count();
  expect(shown).toBeGreaterThan(0);
  await expect(page.locator("#owner-filters details.facet-group:not([hidden])[open]")).toHaveCount(shown);

  // Nothing at all is still an honest, spelt-out state.
  await page.locator("#owner-search").fill("zzzzzzzz");
  await expect(page.locator("#owner-facet-empty")).toBeVisible();
  await expect(groups(page)).toHaveCount(0);

  // Clearing it puts the reader's own folds back rather than shutting or
  // opening everything.
  await page.locator("#owner-search").fill("");
  await expect(page.locator("#owner-facet-empty")).toBeHidden();
  await expect(openGroups(page)).toHaveCount(0);
  expect(await groups(page).count()).toBeGreaterThan(5);
});

test("the sort toggles survive a reload", async ({ page }, testInfo) => {
  testInfo.setTimeout(600_000);
  await load(page);
  await openOwnerFacet(page);
  await page.locator("#owner-sort-count").click();
  await expect(page.locator("#owner-sort-count")).toHaveAttribute("aria-pressed", "true");

  await page.reload();
  await expect(page.locator("#visible-count")).toContainText("Selected", { timeout: 120_000 });
  await openRail(page);
  await openOwnerFacet(page);
  await expect(page.locator("#owner-sort-count")).toHaveAttribute("aria-pressed", "true");
  await expect(groups(page).first().locator("> summary > span")).toHaveText("1000+");
});
