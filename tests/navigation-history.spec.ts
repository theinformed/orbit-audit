// Browser history, and the two blocks the event player was missing.
//
// Sean, 2026-09-03: "if I ve drilled down into a lesson and I want to go back,
// and I miss the back button at the top of the page and hit my browser s back
// button, it takes me out of the space site completely."
//
// Before that day this bundle contained no pushState, no popstate and no hash
// handling at all, so the whole visit was ONE history entry and Back always
// meant leave. These three cases are the contract that replaced it.
import { test, expect } from "@playwright/test";

async function dismissWelcome(page: any) {
  const welcome = page.locator("#welcome-dialog");
  if (await welcome.isVisible().catch(() => false)) {
    await welcome.locator(".dialog-close").click();
    await expect(welcome).toBeHidden();
  }
}

// 1. The synopsis and impacts blocks, reached by deep link (the only route to a
//    content view on a phone, where `.topnav` is display:none).
test("a deep link opens Historical events, with synopsis and impacts", async ({ page }) => {
  await page.goto("/#/events");
  await dismissWelcome(page);
  await expect(page.locator("#content-view")).toBeVisible();

  await page.locator('[data-replay-event="halloween-2003"]').click();
  const dialog = page.locator("#event-dialog");
  await expect(dialog).toBeVisible();

  const synopsis = dialog.locator(".event-synopsis");
  await expect(synopsis).toBeVisible();
  const impacts = dialog.locator(".event-impacts li");
  await expect(impacts.first()).toBeVisible();
  console.log("IMPACTS >>", await impacts.count(), "entries");

  const sy = await synopsis.boundingBox();
  const chart = await dialog.locator("[data-event-replay]").boundingBox();
  expect(sy!.y).toBeLessThan(chart!.y);
});

// 2. Sean's actual complaint: drill into a lesson, press the BROWSER back
//    button, and stay inside the site instead of leaving it.
test("browser Back returns to the lesson index instead of leaving the site", async ({ page }) => {
  await page.goto("/#/learn-orbits");
  await dismissWelcome(page);

  const chapter = page.locator("[data-fundamentals-page]").first();
  await expect(chapter).toBeVisible();
  await chapter.click();

  await expect(page).toHaveURL(/#\/learn-orbits\/.+/);
  const deep = page.url();
  console.log("IN LESSON  >>", deep);

  await page.goBack();
  await expect(page).toHaveURL(/#\/learn-orbits$/);
  console.log("AFTER BACK >>", page.url());
  await expect(page.locator("[data-fundamentals-page]").first()).toBeVisible();

  // and Forward must go back down again
  await page.goForward();
  await expect(page).toHaveURL(deep);
  console.log("AFTER FWD  >>", page.url());
});

// 3. The replay is a full-screen modal, so Back must close it rather than
//    stepping over it or leaving the site.
test("browser Back closes an open replay and stays on the grid", async ({ page }) => {
  await page.goto("/#/events");
  await dismissWelcome(page);

  await page.locator('[data-replay-event="quebec-1989"]').click();
  const dialog = page.locator("#event-dialog");
  await expect(dialog).toBeVisible();
  await expect(page).toHaveURL(/#\/events\/quebec-1989/);
  console.log("REPLAY OPEN >>", page.url());

  await page.goBack();
  await expect(dialog).toBeHidden();
  await expect(page).toHaveURL(/#\/events$/);
  console.log("AFTER BACK  >>", page.url());
  await expect(page.locator('[data-replay-event="quebec-1989"]')).toBeVisible();
});
