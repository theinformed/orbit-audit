import { expect, test } from "@playwright/test";

/**
 * The floating panels must not cover each other's controls.
 *
 * This exists because they did. On a 834 px tablet the rail takes 350 px, which
 * left the scene 484 px wide while the satellite stack and the Data Explorer
 * both kept their desktop widths. The stack ended up over 151 px of the
 * Explorer's head — its whole height — and since both are z-index 15 the stack
 * won on DOM order. With satellites selected, a tablet reader could not expand
 * the Data Explorer at all.
 *
 * The check is a hit test rather than a rectangle comparison, because a hit
 * test is what the browser actually does when it routes a click. Overlapping
 * boxes are allowed; an unreachable control is not.
 */

/** What would receive a click at the centre of this element? */
async function hitTarget(page: import("@playwright/test").Page, selector: string) {
  return page.evaluate((sel) => {
    const element = document.querySelector(sel);
    if (!element) return "(missing)";
    const box = element.getBoundingClientRect();
    const hit = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
    if (!hit) return "(nothing)";
    return hit === element || element.contains(hit) || hit.contains(element)
      ? "self"
      : `${hit.tagName}#${hit.id || "-"}.${String(hit.className).split(" ")[0] || "-"}`;
  }, selector);
}

test("the satellite stack never covers the Data Explorer's head", async ({ page }, testInfo) => {
  testInfo.setTimeout(300_000);
  // A phone stacks these deliberately as sheets, one at a time, and getting to
  // the Explorer there is governed by tests/phone-state.ts and proven in
  // browser.spec.ts. This is about the floating layout.
  test.skip(testInfo.project.name === "mobile", "a phone shows these as sheets, one at a time, by design");

  await page.addInitScript(() => localStorage.setItem("space-explorer-hide-welcome-v1", "1"));
  await page.goto("./");
  await expect(page.locator("#visible-count")).toContainText("Selected", { timeout: 120_000 });

  // Both panels on screen at once: a satellite selected AND a layer plotting.
  await page.locator("#satellite-search").fill("ISS");
  await page.locator("#search-results [role=option]").first().click();
  await expect(page.locator("#satellite-stack")).toBeVisible();

  await page.locator("#layer-thermosphere").check();
  await expect(page.locator("#data-viewer")).toBeVisible();

  expect(await hitTarget(page, "#data-viewer-head"), "the Explorer's head is covered").toBe("self");

  // ...and the same in reverse, so a fix that simply raised one panel over the
  // other does not pass: that would only move the defect.
  // The panel's grab surface is the CARD'S HEAD since 2026-08-28: the bar that
  // used to carry the selection count was the handle, and it went with the
  // count when the selection became one spacecraft at a time. Same question,
  // same failure mode - a panel you cannot grab is a panel you cannot move out
  // of the way - asked of the element that is now grabbed.
  expect(await hitTarget(page, "#satellite-stack .sat-card-head"), "the panel's drag handle is covered").toBe("self");

  // The head must also actually take the click, which is the behaviour a reader
  // depends on and the thing that timed out for fifteen minutes before the fix.
  const collapsed = await page.locator("#data-viewer").evaluate((el) => el.classList.contains("is-collapsed"));
  await page.locator("#data-viewer-head").click({ timeout: 15_000 });
  await expect(page.locator("#data-viewer")).toHaveClass(collapsed ? /^(?!.*is-collapsed).*$/ : /is-collapsed/);
});
