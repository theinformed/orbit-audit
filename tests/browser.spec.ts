import { expect, test, type Page } from "@playwright/test";

import { featuredToday } from "./featured-today";
import { closeRail, openRail as phoneOpenRail, showLegend, showViewer } from "./phone-state";

/**
 * `data/featured-constellation.json` is written on the VPS by the scaffold lane
 * that composes the constellation-of-the-day sentence, straight into
 * `runtime/data/` and deliberately NOT into the manifest, so the artifact
 * pruner cannot reach it. It is therefore CORRECTLY absent from a local tree:
 * bigmem never produces it and `public/data` never carries it.
 *
 * The page already handles that — the fetch is wrapped and falls back to a
 * sentence built from the catalog — but the browser still logs the 404, and
 * three separate agents lost a debugging cycle each to the resulting red
 * before anyone wrote this down. The absence is the environment, not a defect.
 *
 * Scoped to that one path on purpose. Anything else that 404s is still a
 * failure, and the LIVE file is verified by fetching it from the deployed site,
 * not by this suite.
 */
function isVpsOnlyArtifact(text: string): boolean {
  return text.includes("featured-constellation.json");
}


/**
 * A layer's own settings, opened the way a reader opens them today.
 *
 * They used to be one click away: a caret on the layer's row in the rail. That
 * caret is GONE — 8c771ca took the evidence chips off the rail rows and made
 * the Data Explorer's card the only place a layer states what it is, and the
 * caret went with them. Nothing in `src/` or `index.html` carries
 * `data-layer-caret` any more, so every `[data-layer-caret=…]` this file used
 * to click was a locator that could never resolve. They were all downstream of
 * an earlier failure, which is the only reason it took this long to notice.
 *
 * The route now is three surfaces deep, and each step is a real reader action:
 * the Explorer expanded, then this layer's card (every card opens SHUT — they
 * are peers, there is no focused layer), then the card's own "Layer settings"
 * fold, which starts folded from the second layer onward. Each step asks the
 * page what state it is in rather than assuming, because the site itself
 * folds these surfaces in response to other actions.
 */
async function openLayerCard(page: Page, layer: string): Promise<void> {
  // On a phone the rail is a sheet over the globe: the Explorer is not
  // reachable underneath it.
  await closeRail(page);
  if (await page.locator("#data-viewer.is-collapsed").count()) {
    await page.locator("#data-viewer-head").click();
  }
  await expect(page.locator("#data-viewer")).not.toHaveClass(/is-collapsed/);
  const card = page.locator(`#data-viewer-cards [data-layer="${layer}"]`);
  await expect(card).toBeVisible();
  if (await card.evaluate((node) => node.classList.contains("is-collapsed"))) {
    await card.locator("[data-card-toggle]").click();
  }
  await expect(card).not.toHaveClass(/is-collapsed/);
  // A layer with nothing to set has this fold marked hidden rather than empty,
  // so ask before reaching for it.
  const controls = card.locator("[data-card-controls]");
  const hasControls = await controls.count() > 0
    && !await controls.evaluate((node) => node.hasAttribute("hidden"));
  if (hasControls && !await controls.evaluate((node) => node.hasAttribute("open"))) {
    await controls.locator("> summary").click();
    await expect(controls).toHaveAttribute("open", "");
  }
}

// 15 min: this walk drives every heavy layer; under SwiftShader the belt
// volume alone bakes for tens of seconds. Measured 5.6 min on a quiet bigmem,
// so a 6 min budget failed the moment anything else was running — and the
// symptom was a browser session killed mid-assertion, which reads like a
// product bug and is not one. The budget is a machine-speed allowance, not a
// performance assertion; the site's own speed is measured elsewhere.
/** Untick every ticked organization, one row at a time — which is what the
 *  reader now does with the "Clear this list" button gone. Each click goes
 *  through the real deselect path, so the assertions around it are testing the
 *  gesture Sean described rather than a shortcut. */
async function clearOwnerList(page: Page): Promise<void> {
  const ticked = page.locator("[data-owner]:checked");
  while (await ticked.count() > 0) await ticked.first().uncheck();
}

test("loads the verified bundle and supports the primary teaching flow", async ({ page }, testInfo) => {
  testInfo.setTimeout(900_000);
  await page.addInitScript(() => localStorage.setItem("space-explorer-hide-welcome-v1", "1"));
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("./");
  const startupTimeout = testInfo.project.name === "mobile" ? 120_000 : 90_000;
  await expect(page.locator("#visible-count")).toContainText("Selected", { timeout: startupTimeout });
  await expect(page.locator("#scene canvas")).toBeVisible();
  await expect(page.locator("#data-status")).not.toContainText("unavailable");

  // THE SITE OPENS ON THE FEATURED CONSTELLATION, and on nothing else. Sean:
  // "We should be starting with a satellite or constellation of the day. I say
  // we start with GPS. Have that shown when you load the page." No layers, no
  // key cards, and — this is the separate half — no orbit band lit, because
  // showing GPS is a selection, not a filter the reader applied. The full
  // state model is driven through its transitions in its own test below.
  await expect(page.locator("#visible-count")).toHaveText(/^[1-9][0-9,]* Selected$/);
  await expect(page.locator("#key-cards .key-card")).toHaveCount(0);
  await expect(page.locator("#filter-status")).toBeHidden();
  // …and it SAYS so, over the globe, in the popup that replaced the rail's
  // `Today:` line. Never a hard-coded fleet name: the rotation advances one
  // entry per UTC day, and "GPS" was true here for exactly one day before this
  // assertion started failing on every project every day. The expected name is
  // asked of the rotation itself. The popup's own behaviour — ten seconds, the
  // X, the outside click, the click inside that stops the clock — is driven in
  // `featured-toast.spec.ts`.
  //
  // THE TEXT, NOT THE VISIBILITY, and with a real timeout. The note is
  // scheduled 400 ms after the catalog is applied and after a fetch that may
  // 404; under SwiftShader the main thread is still building the scene for
  // tens of seconds after `#visible-count` lands, so a 5-second default here
  // was asserting that this machine is fast. Whether the note is ON SCREEN,
  // for how long, and what closes it is `featured-toast.spec.ts`'s subject and
  // is driven there. What this flow needs to know is that the site opened on
  // today's fleet and said so.
  await expect(page.locator("#featured-toast-text"))
    .toContainText(await featuredToday(page), { timeout: 90_000 });
  // The colour key answers a drawn population, so it is on screen with one.
  // Assert the flag AND, where the phone stylesheet does not drop the key
  // outright, that the flag actually reaches the screen: `legend.hidden` had
  // been set for months while `.legend { display: flex }` beat the UA sheet's
  // `[hidden] { display: none }`, so the property alone proves nothing.
  await expect(page.locator("#satellite-legend")).toHaveJSProperty("hidden", false);
  if (testInfo.project.name !== "mobile") await expect(page.locator("#satellite-legend")).toBeVisible();

  // TAKING THE WHOLE CATALOG. The orbit band is the scope control; "All" is a
  // reader choosing every band, which is a different state from the unset band
  // the site opened on. Everything below this line measures a full catalog.
  if (testInfo.project.name === "mobile") {
    await phoneOpenRail(page);
    await expect(page.locator("#control-rail")).toHaveClass(/is-open/);
  }
  await page.locator('[data-orbit="all"]').click();
  await expect(page.locator("#visible-count")).toHaveText(/^[1-9][0-9,]* Selected$/);
  await expect(page.locator("#satellite-legend")).toHaveJSProperty("hidden", false);
  if (testInfo.project.name !== "mobile") await expect(page.locator("#satellite-legend")).toBeVisible();
  // The rendering ceiling outlived the control that used to set it: 450 on a
  // desktop, 220 at 820 px or narrower.
  const askedCount = Number((await page.locator("#visible-count").textContent() ?? "").replace(/[^0-9]/g, ""));
  expect(askedCount).toBe(testInfo.project.name === "mobile" ? 220 : 450);
  // Off the rail again, so the phone's bottom sheet is not over the globe when
  // the display panel opens on top of it.
  await closeRail(page);

  await page.locator("#display-settings-toggle").click();
  await expect(page.locator("#display-settings")).toBeVisible();
  await page.locator('[data-rendering-profile="efficient"]').click();
  await expect(page.locator("#display-profile-status")).toContainText("ADAPTIVE 30 FPS");
  await page.locator('[data-motion-rate="20"]').click();
  await expect(page.locator("#display-profile-status")).toContainText("20 FPS");
  await page.locator('[data-marker-size="large"]').click();
  await expect(page.locator('[data-marker-size="large"]')).toHaveClass(/is-active/);
  await page.locator('[data-color-mode="constellation"]').click();
  await expect(page.locator("#satellite-legend")).toHaveAttribute("aria-label", "Satellite constellation colors");
  await expect(page.locator("#satellite-legend span")).toHaveCount(testInfo.project.name === "mobile" ? 5 : 8);
  await page.locator('[data-color-mode="country"]').click();
  await expect(page.locator("#satellite-legend")).toHaveAttribute("aria-label", "Satellite country colors");
  await page.locator('[data-color-mode="mission"]').click();
  await expect(page.locator("#satellite-legend")).toHaveAttribute("aria-label", "Satellite mission colors");
  await page.locator("#display-settings-close").click();
  await expect(page.locator("#display-settings")).toBeHidden();

  if (testInfo.project.name === "mobile") {
    await phoneOpenRail(page);
    await expect(page.locator("#control-rail")).toHaveClass(/is-open/);
  }

  await page.locator('[data-orbit="GEO"]').click();
  await expect(page.locator("#geo-subfilter")).toHaveAttribute("aria-hidden", "false");
  await expect(page.locator('[data-geo-type="geostationary"]')).toBeEnabled();
  await page.locator('[data-geo-type="geostationary"]').click();
  await expect(page.locator('[data-geo-type="geostationary"]')).toHaveClass(/is-active/);
  await page.locator('[data-orbit="all"]').click();
  await expect(page.locator("#geo-subfilter")).toHaveAttribute("aria-hidden", "true");

  // THE THREE LISTS ARE LINKED (2026-08-28). The per-list Select all / Clear
  // this list buttons this block used to press are gone with the wrapper fold;
  // one tick fills the other two lists with everything that goes with it, an
  // untick takes exactly one value away, and Clear on the catalog heading is
  // the only control that empties anything wholesale.
  await page.locator('[data-orbit="all"]').click();
  await page.locator("#catalog-clear").click();
  await expect(page.locator("#visible-count")).toHaveText("0 Selected");
  await page.locator('[data-mission-facet][value="navigation"]').check();
  await expect(page.locator("#visible-count")).toHaveText(/^[1-9][0-9,]* Selected$/);
  // The link opened the fleet list and ticked the fleets navigation flies, so
  // the fill is visible rather than only arithmetic.
  await expect(page.locator("#constellation-section")).toHaveAttribute("open", "");
  await expect(page.locator('[data-constellation="GPS"]')).toBeChecked();
  // An untick STICKS: nothing is re-added, in any list.
  await page.locator('[data-constellation="GPS"]').uncheck();
  await expect(page.locator('[data-constellation="GPS"]')).not.toBeChecked();
  await expect(page.locator('[data-mission-facet][value="navigation"]')).toBeChecked();
  // Clear empties every list and the globe with it.
  await page.locator("#catalog-clear").click();
  await expect(page.locator('[data-mission-facet]:checked')).toHaveCount(0);
  await expect(page.locator('[data-constellation]:checked')).toHaveCount(0);
  await expect(page.locator('[data-owner]:checked')).toHaveCount(0);
  await expect(page.locator("#visible-count")).toHaveText("0 Selected");
  // "only Starlink" is now one plain tick, because a tick links.
  await page.locator('[data-constellation="Starlink"]').check();
  await expect(page.locator('[data-mission-facet][value="commercial-satcom"]')).toBeChecked();
  await expect(page.locator('[data-owner="SpaceX"]')).toBeChecked();
  await expect(page.locator("#visible-count")).toHaveText(/^[1-9][0-9,]* Selected$/);

  await page.locator("#satellite-search").focus();
  await expect(page.locator(".search-result")).toHaveCount(80);
  await page.locator("#search-results").evaluate((element) => { element.scrollTop = element.scrollHeight; });
  await expect.poll(() => page.locator(".search-result").count()).toBeGreaterThan(80);
  await page.locator("#satellite-search").fill("A");
  await expect(page.locator(".search-result").first().locator("strong")).toHaveText(/^A/i);
  await page.locator("#satellite-search").fill("HST");
  await expect(page.locator(".search-result")).toHaveCount(1);
  await page.locator(".search-result").click();
  await expect(page.locator("#satellite-stack")).toBeVisible();
  await expect(page.locator(".satellite-map-label--selected")).toBeVisible();
  await expect(page.locator(".sat-card.is-active [data-card-name]")).toContainText("HST");
  await expect(page.locator(".sat-card.is-active [data-card-ephemeris]")).toContainText("CelesTrak OMM");
  // The 2D map is reachable in ONE click again. It spent a day behind a
  // "Ground Data" fold that shipped shut and whose only universal content was
  // this button; on 2026-08-21 the fold was removed and the button became the
  // first of Satellite Details' two full-width actions, directly above the OMM
  // download. Satellite Details ships OPEN, so nothing has to be unfolded
  // first - and that is asserted, because a regression here would put the map
  // back behind a disclosure without failing anything else.
  await expect(page.locator('.sat-card.is-active [data-card-section="ground"]')).toHaveCount(0);
  await expect(page.locator('.sat-card.is-active [data-card-section="details"]')).toHaveAttribute("open", "");
  await expect(page.locator(".sat-card.is-active [data-card-ground-track]")).toBeVisible();
  // The orbit archive is a full-width box again, between the fact grid and the
  // 2-D map, wearing the same box as the two actions under it (Sean,
  // 2026-08-27: "right between the grid of values and the 2d ground track
  // box"). It spent 2026-08-21 to 08-27 as a cell of the fact grid; that is
  // what this used to assert, and the cell cost the grid its shape.
  //
  // What did NOT change is the honesty contract, so that is what is checked:
  // the archive is never fetched to draw a card, so the box says nothing about
  // a count in the ordinary case and one of three fixed sentences otherwise,
  // and the accessible name always states which of the four it is.
  const orbitHistory = page.locator(".sat-card.is-active [data-card-orbit-history]");
  await expect(page.locator(".sat-card.is-active [data-card-orbit-history-cell]")).toHaveCount(0);
  await expect(orbitHistory).toBeVisible();
  await expect(orbitHistory).toHaveText(/^Open orbit history( — (server offline|could not be read|no stored elements|[\d,]+ element sets?))? →$/);
  await expect(orbitHistory).toHaveAttribute(
    "aria-label",
    /^Open orbit history — (History not loaded|Archive server offline|History unavailable|No stored elements|[\d,]+ element sets? on file)$/,
  );
  // The three actions are one set, in Sean's order, and the archive leads.
  await expect(page.locator(".sat-card.is-active .card-actions > button:not([hidden])"))
    .toHaveText([/^Open orbit history/, /^Open 2D ground-track map/, /^Download OMM/]);
  await page.locator(".sat-card.is-active [data-card-ground-track]").click();
  await expect(page.locator("#ground-track-dialog")).toBeVisible();
  await expect(page.locator("#ground-track-dialog svg")).toHaveAttribute("role", "img");
  await expect(page.locator("#ground-track-dialog")).toContainText("ONE ORBIT");
  await page.locator("#ground-track-dialog .primary-button").click();
  await expect(page.locator("#ground-track-dialog")).toBeHidden();
  // Pause the simulation before reading a screen position off it. What follows
  // captures the marker's pixel coordinate, dismisses the card, and then hovers
  // that coordinate — and HST does not wait for any of that. It moves about
  // 3.5 px per 1.6 s of wall clock at this zoom, and under software WebGL the
  // steps in between take seconds, so on a slow or busy machine the pointer
  // arrives where the satellite USED to be and the hover label is empty. That
  // is a race in the test, not a defect in the hover: the same stale coordinate
  // identifies HST correctly when the gap is short. Freezing time removes the
  // race without weakening what is being checked — that hovering a marker names
  // the satellite under it.
  await page.locator("#time-play").click();
  // Paused from the live clock reads "Play simulation"; only a paused TIMED
  // PLAYBACK says "Resume". Both show the play glyph, which is the state this
  // needs, so the glyph is what it asserts.
  await expect(page.locator("#time-play")).toHaveText("▶");
  const selectedMarker = await page.locator(".satellite-map-label--selected").evaluate((label) => ({
    x: Number.parseFloat((label as HTMLElement).style.left),
    y: Number.parseFloat((label as HTMLElement).style.top),
  }));
  const sceneBounds = await page.locator("#scene").boundingBox();
  expect(sceneBounds).not.toBeNull();
  await page.locator(".sat-card.is-active [data-card-remove]").click();
  await expect(page.locator("#satellite-stack")).toBeHidden();
  await page.mouse.move(sceneBounds!.x + selectedMarker.x, sceneBounds!.y + selectedMarker.y);
  await expect(page.locator(".satellite-map-label--hover")).toBeVisible();
  await expect(page.locator(".satellite-map-label--hover")).toContainText("HST");
  await page.mouse.click(sceneBounds!.x + selectedMarker.x, sceneBounds!.y + selectedMarker.y);
  await expect(page.locator("#satellite-stack")).toBeVisible();
  await expect(page.locator(".sat-card.is-active [data-card-name]")).toContainText("HST");

  // Hand the clock back before the timeline steps below, which are about time
  // moving and must not inherit a paused simulation from the hover check.
  await page.locator("#time-play").click();
  await expect(page.locator("#time-play")).toHaveText("Ⅱ");
  await expect(page.locator("#time-play")).toHaveAttribute("aria-label", "Pause simulation");

  await page.locator("#time-slider").evaluate((element) => {
    const slider = element as HTMLInputElement;
    slider.value = "1440";
    slider.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await expect(page.locator("#sim-label")).toContainText("+1440 MIN");
  await expect(page.locator(".satellite-map-label--selected")).toBeVisible();
  await page.waitForTimeout(600);
  await expect(page.locator(".satellite-map-label--selected")).toBeVisible();
  if (await page.locator("#time-now").isVisible()) await page.locator("#time-now").click();
  else await page.evaluate(() => document.querySelector<HTMLButtonElement>("#time-now")?.click());
  await expect(page.locator("#sim-label")).toHaveText("LIVE");

  await page.locator("#time-playback-toggle").click();
  await expect(page.locator("#time-playback-settings")).toBeVisible();
  await page.locator("#time-playback-duration").selectOption("30");
  const playbackStart = await page.locator("#sim-time").textContent();
  await page.locator("#time-playback-start").click();
  await expect(page.locator("#sim-label")).toContainText("PLAYING 30M");
  await page.waitForTimeout(900);
  await expect(page.locator("#sim-time")).not.toHaveText(playbackStart ?? "");
  await page.locator("#time-play").click();
  await expect(page.locator("#sim-label")).toHaveText("PAUSED");
  if (await page.locator("#time-now").isVisible()) await page.locator("#time-now").click();
  else await page.evaluate(() => document.querySelector<HTMLButtonElement>("#time-now")?.click());
  await expect(page.locator("#sim-label")).toHaveText("LIVE");

  await page.evaluate(() => {
    Object.defineProperty(document, "hidden", { configurable: true, value: true });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  const beforeHidden = await page.locator("#sim-time").textContent();
  await page.waitForTimeout(1_300);
  await expect(page.locator("#sim-time")).toHaveText(beforeHidden ?? "");
  await page.evaluate(() => {
    Object.defineProperty(document, "hidden", { configurable: true, value: false });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await expect(page.locator("#sim-time")).not.toHaveText(beforeHidden ?? "", { timeout: 3_000 });
  await expect(page.locator("#sim-label")).toHaveText("LIVE");

  if (testInfo.project.name === "mobile") {
    await expect(page.locator("#control-rail")).not.toHaveClass(/is-open/);
    await page.locator("#mobile-panel-toggle").click();
  }
  await expect(page.locator(".environment-section")).toBeVisible();
  // The mode brings the CONTROL SURFACE, not a field. `setMode` used to apply
  // a preset on the way into Space weather, so the thermosphere was already on
  // by the time this line ran and every step below inherited it. Nothing draws
  // until the reader asks now, so ask the way the rail offers — press Simple —
  // and prove the mode switch on its own drew nothing first.
  await expect(page.locator("#layer-thermosphere")).not.toBeChecked();
  await expect(page.locator("#key-cards .key-card")).toHaveCount(0);
  await expect(page.locator("#data-viewer")).toBeHidden();
  await page.locator('[data-preset="simple"]').click();
  await expect(page.locator("#layer-thermosphere")).toBeChecked();
  await expect(page.locator('[data-layer-panel="thermosphere"]')).toHaveClass(/is-visible/);
  await expect(page.locator("#thermosphere-subcontrols")).toHaveAttribute("aria-hidden", "false");
  // Three surfaces, three jobs. The rail is a control surface. The legend in
  // the lower-right corner carries a colour ramp and its units, and nothing
  // else. Every other thing the layer says is in the data viewer, which is off
  // until it is switched on.
  const key = (layer: string) => page.locator(`#key-cards [data-layer="${layer}"]`);
  const viewer = (layer: string) => page.locator(`#data-viewer-cards [data-layer="${layer}"]`);
  await expect(key("thermosphere")).toContainText("Thermosphere height", { timeout: 60_000 });
  await expect(key("thermosphere")).toContainText("km");
  // EXPANDED on a clean profile, which is what this test runs on. It opened
  // folded until 8c771ca took the evidence chips off the rail rows and made
  // this panel the only place a layer states its evidence class, at which
  // point a panel that opened folded would let a reader draw a MODEL layer and
  // never be told it is one. The storage key went to v2 in the same change so
  // a remembered "collapsed" could not reintroduce that.
  //
  // A phone is the one exception, and only while the layer sheet is over the
  // globe: one surface at a time, folded by the sheet and given back when the
  // sheet closes. The sheet was opened a few lines above, so that is the state
  // this line is reached in.
  await expect(page.locator("#data-viewer")).toBeVisible();
  if (testInfo.project.name === "mobile") await expect(page.locator("#data-viewer")).toHaveClass(/is-collapsed/);
  else await expect(page.locator("#data-viewer")).not.toHaveClass(/is-collapsed/);
  // Either way the map key never carries readings; that is the Explorer's job.
  await expect(key("thermosphere")).not.toContainText("LOWEST");
  // And collapsed, this layer's own setting is nowhere in the rail either: it
  // moved into the card the viewer builds. Reaching it before that card
  // exists is exactly the failure this ordering guards.
  await expect(page.locator("#control-rail #thermosphere-level")).toHaveCount(0);
  // A satellite was selected above, so on a phone the stack is showing and the
  // Explorer has moved down under the open rail sheet, which outranks it. Put
  // the sheet away before reaching for the Explorer's head.
  await showViewer(page);
  await expect(page.locator("#data-viewer")).not.toHaveClass(/is-collapsed/);
  // The panel is open; this layer's card inside it is not. Cards open shut.
  await openLayerCard(page, "thermosphere");
  await expect(page.locator("#data-viewer #thermosphere-level")).toBeVisible();
  await page.locator("#thermosphere-level").selectOption("1e-12");
  await expect(viewer("thermosphere")).toContainText("LOWEST");
  await expect(viewer("thermosphere")).toContainText("HIGHEST");
  await expect(viewer("thermosphere")).toContainText("SPREAD");
  // Simple at first: the readings are open and the rest is folded until asked
  // for, exactly as a satellite card behaves.
  await expect(viewer("thermosphere").locator('[data-card-section="readings"]')).toHaveAttribute("open", "");
  await expect(viewer("thermosphere").locator('[data-card-section="provenance"]')).not.toHaveAttribute("open", "");
  // On a phone the rail is a sheet over the globe, and with the full layer
  // list it now reaches far enough down to intercept clicks on the viewer's
  // cards. The viewer is only reachable with the sheet closed — the same
  // deliberate small-screen arrangement the later steps already honour.
  const railOverViewer = testInfo.project.name === "mobile"
    && await page.locator("#control-rail").evaluate((rail) => rail.classList.contains("is-open"));
  if (railOverViewer) await page.locator("#mobile-panel-toggle").click();
  await viewer("thermosphere").locator('[data-card-section="provenance"] summary').click();
  await expect(viewer("thermosphere")).toContainText("WAM");
  if (railOverViewer) await page.locator("#mobile-panel-toggle").click();
  // Every value has exactly one home: the same colour ramp appearing in the
  // rail as well is what crowded the panel.
  await expect(page.locator(".environment-section .key-card-scale")).toHaveCount(0);
  await expect(page.locator("#data-viewer .key-card-scale")).toHaveCount(0);

  await page.locator("#time-slider").evaluate((element) => {
    const slider = element as HTMLInputElement;
    slider.value = slider.max;
    slider.dispatchEvent(new Event("input", { bubbles: true }));
  });
  // A layer with nothing to draw keeps the legend's shape — name, bar, units —
  // and says so where the units go, rather than growing a paragraph. The
  // sentence explaining it is in the data viewer and on the row's tooltip.
  // The "nothing to draw" rules are proved on aurora further down: they are
  // layer-agnostic, and the layer they used to be demonstrated on — the
  // ionospheric peak surfaces — moved to the learning pages on 2026-08-18.

  if (await page.locator("#time-now").isVisible()) await page.locator("#time-now").click();
  else await page.evaluate(() => document.querySelector<HTMLButtonElement>("#time-now")?.click());
  // Every layer toggle lives in the rail, and the rail is a sheet a phone
  // keeps shut. Ask for it before reaching for one, every time — a shut sheet
  // is translated off screen, where a click can never land no matter how long
  // Playwright waits for it.
  await phoneOpenRail(page);
  await page.locator("#layer-tec").check();
  await expect(key("tec")).toContainText("TECU");

  // A layer row in the rail is its toggle and nothing else now. Everything the
  // layer SAYS, and every setting it carries, is in its card in the Data
  // Explorer — which is where the rest of this section drives them from.
  const thermosphereCard = page.locator('#data-viewer-cards [data-layer="thermosphere"]');
  await expect(thermosphereCard).toBeVisible();
  await expect(page.locator("#control-rail [data-layer-caret]")).toHaveCount(0);
  // On a phone the rail is a sheet over the globe, so the rail and the window
  // it opens are never both reachable at once, and the steps below alternate
  // between them. This used to capture "is the rail open?" once and invert it
  // at each switch, which cannot work: the site itself shuts the sheet when a
  // satellite is picked, when a nav button is used and when the Explorer
  // expands, so the captured value goes stale and every later flip is backwards.
  // Ask for the surface each step needs instead.
  await closeRail(page);
  // The X closes by turning every active layer off through its real checkbox
  // — "stop plotting" — so the explorer disappears as a consequence, not by a
  // separate hide step, and the layers it was showing are provably unchecked.
  await page.locator("#data-viewer-close").click();
  await expect(page.locator("#data-viewer")).toBeHidden();
  await phoneOpenRail(page);
  await expect(page.locator("#layer-thermosphere")).not.toBeChecked();
  await expect(page.locator("#layer-tec")).not.toBeChecked();
  // With every layer off, the card goes with it — a card only exists for a
  // layer that is on. Switch the thermosphere back on to bring the panel back.
  await expect(thermosphereCard).toBeHidden();
  await page.locator("#layer-thermosphere").check();
  await expect(page.locator("#data-viewer")).toBeVisible();
  await expect(page.locator("#data-viewer")).toHaveClass(/is-collapsed/);
  await openLayerCard(page, "thermosphere");
  await expect(page.locator("#data-viewer #thermosphere-level")).toBeVisible();
  // Back to the rail for the advanced group and the layers below it.
  await phoneOpenRail(page);
  // A layer with nothing to set gets no settings fold at all rather than one
  // that opens an empty box.
  await expect(page.locator('#data-viewer-cards [data-layer="tec"] [data-card-controls]')).toBeHidden();

  const advancedEnvironment = page.locator("details.advanced-environment-details");
  await advancedEnvironment.locator("> summary").click();
  await expect(page.locator("#layer-drap")).not.toBeChecked();
  await page.locator("#layer-drap").check();
  await page.evaluate(async () => {
    const manifest = await fetch("data/manifest.json").then((response) => response.json()) as { drap?: { validTo: string } };
    if (!manifest.drap) return;
    const slider = document.querySelector<HTMLInputElement>("#time-slider");
    if (!slider) return;
    slider.value = String(Math.ceil((Date.parse(manifest.drap.validTo) - Date.now()) / 60_000));
    slider.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await expect(key("drap")).toContainText("D-region HF absorption");
  await expect(key("drap")).toContainText("1 dB HAF");
  await expect(viewer("drap")).toContainText("5 MHz @ MAP MAX");
  await expect(viewer("drap")).toContainText("Published coverage");
  await expect(viewer("drap")).toContainText("Source");

  await phoneOpenRail(page);
  await page.locator("#layer-aurora").check();
  await page.evaluate(async () => {
    const manifest = await fetch("data/manifest.json").then((response) => response.json()) as { aurora?: { validTo: string } };
    if (!manifest.aurora) return;
    const slider = document.querySelector<HTMLInputElement>("#time-slider");
    if (!slider) return;
    slider.value = String(Math.ceil((Date.parse(manifest.aurora.validTo) - Date.now()) / 60_000));
    slider.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await expect(key("aurora")).toContainText("OVATION");
  await expect(key("aurora")).toContainText("BOTH HEMISPHERES");
  await expect(viewer("aurora")).toContainText("not an energy-flux field");
  await expect(viewer("aurora")).toContainText("Observed at");
  await expect(viewer("aurora")).toContainText("Published coverage");
  await expect(page.locator("#aurora-subcontrols")).toHaveAttribute("aria-hidden", "false");
  await expect(page.locator("#aurora-note")).toContainText("hemispheres", { ignoreCase: true });
  await expect(page.locator("[data-aurora-hemisphere]")).toHaveCount(0);

  // Past the end of NOAA's published OVATION forecast, not before its start.
  // The slider's floor is 48 h back and this release's aurora history runs 48 h
  // and change, so "go to the floor" sat exactly on the boundary and resolved
  // or did not depending on the second the test ran. The forecast end is an
  // hour out and the slider reaches 72 h, so the top of the range is always
  // outside it.
  await page.locator("#time-slider").evaluate((element) => {
    const slider = element as HTMLInputElement;
    slider.value = slider.max;
    slider.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await expect(key("aurora")).toContainText("NO DATA AT THIS TIME");
  await expect(key("aurora")).toHaveAttribute("title", /No aurora/);
  // Three words in the legend; the reasoning behind them in the viewer.
  //
  // Past the END of coverage, which is what the slider was just pushed to.
  // 2b0ce05 split this notice in two because only one of the two situations is
  // anybody's fault: scrolled past the end says the record stops and the next
  // frame has not arrived, scrolled before the START says the archive does not
  // go back that far ("Rather than draw a NEARBY frame"). This test set up the
  // first and went on asserting the second's wording.
  await expect(viewer("aurora")).toContainText("the next frame has not arrived yet");
  await expect(viewer("aurora")).toContainText("Rather than draw the last one and call it now");
  // A layer with nothing to draw keeps the legend's shape — name, bar, units —
  // and says so where the units go, rather than growing a paragraph. Then it
  // offers the way out: one click to the nearest time that does have data.
  await expect(key("aurora")).not.toContainText("BEFORE COVERAGE");
  await expect(key("aurora").locator(".key-card-scale")).toHaveCount(1);
  await showLegend(page);
  await expect(key("aurora").locator(".key-card-jump")).toBeVisible();
  await key("aurora").locator(".key-card-jump").click();
  await expect(key("aurora").locator(".key-card-jump")).toHaveCount(0);
  if (await page.locator("#time-now").isVisible()) await page.locator("#time-now").click();
  else await page.evaluate(() => document.querySelector<HTMLButtonElement>("#time-now")?.click());
  if (testInfo.project.name === "desktop") {
    await page.locator("#layer-radiation").check();
    // The layer opens on the omnidirectional integration since 2026-08-08;
    // "mapped bounce shell" was the single-channel era's key title.
    await expect(key("radiation")).toContainText(/omnidirectional mapped volume|No rbe electron belt/, { timeout: 30_000 });
    // Radiation's own controls are in the data viewer now, behind the button on
    // its row; open it before driving them. Everything below drives the real
    // controls, so it also proves they survived the move out of the rail with
    // their bindings intact.
    await openLayerCard(page, "radiation");
    await expect(page.locator("#control-rail #radiation-pitch-select")).toHaveCount(0);
    await expect(page.locator("#data-viewer #radiation-pitch-select")).toBeVisible();
    await expect(page.locator("#radiation-pitch-select")).toBeEnabled();
    expect(await page.locator("#radiation-pitch-select option").count()).toBeGreaterThan(1);
    await expect(page.locator('[data-radiation-view="dipoleMapped3d"]')).toHaveClass(/is-active/);
    // The layer must open on the omnidirectional integration with every
    // published ENERGY folded in: one volume from every locally trapped pitch
    // channel, across the whole 88 keV - 2.32 MeV band. Ten stacked
    // translucent shells buried the belts, one 81.2 degree channel was a
    // 13.9:1 flat annulus, and opening on a single energy meant the two belts
    // only appeared once a visitor found the energy control.
    await expect(page.locator('[data-radiation-energy="-1"]')).toHaveClass(/is-active/);
    await expect(page.locator('[data-radiation-energy="1345.7"]')).not.toHaveClass(/is-active/);
    await expect(viewer("radiation")).toContainText(/OMNIDIRECTIONAL · \d+ OF \d+ PUBLISHED CHANNELS/);
    await expect(viewer("radiation")).not.toContainText(/ALL \d+\/\d+ PUBLISHED/);
    // ...and the stack must still be reachable, and must say so when chosen.
    await page.locator("#radiation-pitch-select").selectOption("-1");
    await expect(viewer("radiation")).toContainText(/ALL \d+\/\d+ PUBLISHED/, { timeout: 30_000 });
    const trappedChannel = await page.locator("#radiation-pitch-select option").evaluateAll((options) => {
      const published = options
        .map((option) => Number((option as HTMLOptionElement).value))
        .filter((value) => value >= 0);
      return String(Math.max(...published));
    });
    await page.locator("#radiation-pitch-select").selectOption(trappedChannel);
    await expect(viewer("radiation")).toContainText(/1 OF \d+ PUBLISHED CHANNELS/);
    await page.locator('[data-radiation-view="nativeEquatorial"]').click();
    await expect(key("radiation")).toContainText("RBE equatorial electron flux");
    await page.locator('[data-radiation-view="dipoleMapped3d"]').click();
    // A specific trapped channel is selected above, so the mapped view names
    // itself by what it is drawing — one bounce shell — rather than by the
    // omnidirectional integration it opens on. The label this asserted before
    // is `RADIATION_BELT_VIEWS.dipoleMapped3d.label`, which geospace-runtime
    // only uses when no pitch presentation is active; the omnidirectional-belts
    // work made that branch unreachable here and this assertion was left behind.
    await expect(viewer("radiation")).toContainText("SINGLE-PITCH-CHANNEL DIPOLE-MAPPED BOUNCE SHELL");
    await page.locator("#time-slider").evaluate((element) => {
      const slider = element as HTMLInputElement;
      slider.value = slider.max;
      slider.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await expect(key("radiation")).toContainText("NO DATA AT THIS TIME");
    await expect(key("radiation")).toHaveAttribute("title", /No rbe electron belt/);
    await expect(key("radiation")).not.toContainText("HIDDEN");
    if (await page.locator("#time-now").isVisible()) await page.locator("#time-now").click();
    else await page.evaluate(() => document.querySelector<HTMLButtonElement>("#time-now")?.click());
  }
  // The measured drivers are a reading, so they are the data viewer's first
  // card and they collapse the way every other card on this site collapses.
  // On a phone the rail is a sheet over the globe, so the viewer is only
  // reachable with the sheet closed — the deliberate small-screen arrangement.
  const railOverKey = await page.locator("#control-rail").evaluate((rail) => rail.classList.contains("is-open"));
  if (railOverKey) await page.locator("#mobile-panel-toggle").click();
  // The selected satellite's card is its own bottom sheet on a phone and sits
  // over the key; the conditions card is only reachable with it closed. The
  // panel-level Clear this used to press is gone - one spacecraft at a time,
  // so the card's own X is the whole of that gesture.
  const cardX = page.locator("#satellite-stack-cards .sat-card [data-card-remove]").first();
  if (testInfo.project.name === "mobile" && await cardX.isVisible()) await cardX.click();
  // On the desktop, five stacked key cards from the sections above push the
  // conditions card up under the sticky top bar, where clicks land on the nav
  // instead. Switch the finished layers off first — which is what a reader
  // does too, and what the legend's whole grows-only-with-layers design is
  // for. Ionosphere stays: the card under test should not be the only one.
  if (testInfo.project.name === "desktop") {
    for (const id of ["layer-radiation", "layer-drap", "layer-aurora", "layer-tec"]) {
      const box = page.locator(`#${id}`);
      if (await box.isChecked()) await box.uncheck();
    }
  }
  // "Conditions right now" is a RAIL FOLD now, not a card over the globe.
  // 2ee0ce8 moved it there and the NOAA scales moved inside it, because "what
  // is the storm level" and "what are the drivers" are the same question asked
  // twice. `#key-conditions`, the Data Explorer card this used to drive, and
  // `#key-conditions-toggle`, its dismiss, are both gone from the document —
  // so this drove two locators that could never resolve.
  await phoneOpenRail(page);
  const conditions = page.locator("#conditions-details");
  await expect(conditions).toBeVisible();
  // SHUT on arrival, alone among the rail's folds, and for the reason the
  // rail's own rule gives: it is the one readout in a column of controls, and
  // the pass that moved it here existed to get the controls above the fold.
  // Nothing it holds is on screen until it is opened.
  await expect(conditions).not.toHaveAttribute("open", "");
  await expect(page.locator("#weather-readout")).toBeHidden();
  // The one-line summary is the fold's CLOSED state, so it is readable with
  // the fold shut and stands down when the table it substitutes for is on
  // screen. It used to be asserted the other way round here, which was an
  // accurate reading of a backwards page: the line lived in the details BODY,
  // so the fold hid it exactly when it was the only reading left and showed it
  // ten pixels above the same four numbers when the table was open. It sits in
  // the <summary> now, which is the part of a <details> that survives folding.
  const summaryLine = page.locator("#key-conditions-summary");
  await expect(summaryLine).toBeVisible();
  await expect(summaryLine).toContainText("km/s");
  await conditions.locator("> summary").click();
  await expect(summaryLine).toBeHidden();
  // "Measured drivers" is a disclosure INSIDE that fold, and it ships OPEN —
  // the fold is the thing that ships shut, not the table inside it. Driven
  // both ways, because a disclosure that only opens is half a control.
  const drivers = page.locator('#conditions-details [data-card-section="conditions"]');
  await expect(drivers).toHaveAttribute("open", "");
  await expect(page.locator("#weather-readout")).toBeVisible();
  await drivers.locator("> summary").click();
  await expect(page.locator("#weather-readout")).toBeHidden();
  await drivers.locator("> summary").click();
  await expect(page.locator("#weather-readout")).toBeVisible();
  // The legend used to carry a second copy of the Explorer's dismiss at its
  // foot, which is what made the two read as one tall panel.
  await expect(page.locator("#map-key-data")).toHaveCount(0);
  // The X turns every still-active layer off — the thermosphere at minimum — so the
  // panel disappears as a consequence, and there is nothing left plotting.
  // On a phone the rail sheet is over the Explorer after the fold above.
  await showViewer(page);
  await page.locator("#data-viewer-close").click();
  await expect(page.locator("#data-viewer")).toBeHidden();
  await expect(page.locator("#layer-thermosphere")).not.toBeChecked();
  if (railOverKey) await page.locator("#mobile-panel-toggle").click();
  // ...and the way it comes back: there is no switch for it any more, only
  // switching a layer back on, in the rail above the layers.
  //
  // On a phone the rail is a slide-up panel, and when it is closed it is not
  // scrolled out of the way — it is TRANSLATED below the viewport
  // (translateY(395px) on a 664px screen). Its contents keep real boxes, so
  // Playwright calls the input "visible, enabled and stable" and then reports
  // it "outside of the viewport" forever, because scrollIntoView has nothing to
  // scroll: the ancestor is displaced, not overflowing. The click retries until
  // the test times out.
  //
  // `railOverKey` above reopens the panel only on the path that closed it, so
  // the other path reaches here with the rail shut. Asking the toggle what
  // state it is in is what makes this hold on both paths, and on desktop, where
  // the toggle is not rendered at all.
  const panelToggle = page.locator("#mobile-panel-toggle");
  if (await panelToggle.isVisible() && (await panelToggle.getAttribute("aria-expanded")) === "false") {
    await panelToggle.click();
  }
  // Fail on the real condition rather than on a click timeout 15 minutes later.
  await expect(page.locator("#layer-thermosphere")).toBeInViewport();
  await page.locator("#layer-thermosphere").check();
  await expect(page.locator("#data-viewer")).toBeVisible();
  await expect(page.locator("#swpc-summary")).toBeVisible();
  // NOAA's operational material moved out of a modal and onto its own page on
  // 2026-08-14: the rail button is the door to "Current conditions" now, the
  // three panels are MOVED onto that page rather than copied, and every one of
  // them is shown at once because a page has no reason to hide two thirds of
  // the answer behind tabs. The dialog it used to open is retired.
  await page.locator("#swpc-outlook-open").click();
  await expect(page.locator("#now-kp-chart")).toBeVisible();
  await expect(page.locator("#now-swpc-mount .swpc-panel")).toHaveCount(3);
  await expect(page.locator("#swpc-current-grid .swpc-condition-card")).toHaveCount(3);
  await expect(page.locator("#swpc-day-grid .swpc-day-card")).toHaveCount(3);
  await expect(page.locator("#swpc-rationales article")).toHaveCount(3);
  await expect(page.locator("#swpc-kp-days .swpc-kp-day")).not.toHaveCount(0);
  // The Kp series is the page's anchor: seven days observed and three
  // forecast, with the forecast bars drawn differently from the measurements.
  await expect(page.locator("#now-kp-chart .now-kp-bar")).not.toHaveCount(0);
  await expect(page.locator("#now-kp-chart .now-kp-bar.is-predicted")).not.toHaveCount(0);
  await expect(page.locator("#now-kp-chart .now-kp-boundary")).toHaveCount(1);
  // The top nav is not drawn on a phone from 2026-08-20 - the row it had is two
  // doors into the control sheet now - so the way back to the explorer is the
  // router, the same guarded shape the events and lessons tests already use.
  if (await page.locator("#mobile-panel-toggle").isVisible()) {
    await page.evaluate(() => document.querySelector<HTMLButtonElement>('[data-view="explore"]')?.click());
  } else {
    await page.locator('[data-view="explore"]').click();
  }
  // The router HIDES the content view rather than emptying it, so the chart
  // stays in the document and simply stops being on screen.
  await expect(page.locator("#content-view")).toBeHidden();
  await expect(page.locator("#now-kp-chart")).toBeHidden();
  // ...and the NOAA panels went home, so exactly one of each still exists.
  await expect(page.locator("#swpc-panel-conditions")).toHaveCount(1);
  // This link lives in the rail, and the nav click just above shut the sheet.
  await phoneOpenRail(page);
  await page.locator(".method-link").click();
  await expect(page.locator("#environment-methods-title")).toContainText("How every live layer is made");
  expect(await page.locator(".method-card").count()).toBeGreaterThanOrEqual(10);
  // Renamed when the cusped boundaries shipped: the method card now covers
  // all three fitted surfaces, with Shue's formula still inside it.
  const magnetopauseMethod = page.locator(".method-card").filter({ hasText: "Magnetopause and exterior cusp" });
  await magnetopauseMethod.locator("summary").click();
  await expect(magnetopauseMethod).toContainText("r(θ)");
  const radiationMethod = page.locator(".method-card").filter({ hasText: "RBE radiation environment" });
  await radiationMethod.locator("summary").click();
  await expect(radiationMethod).toContainText("51 radial × 48 magnetic-local-time");
  const hasHorizontalOverflow = await page.locator("#content-view").evaluate((element) => element.scrollWidth > element.clientWidth + 1);
  expect(hasHorizontalOverflow).toBe(false);
  expect(errors).toEqual([]);
});

/**
 * Sean: "if they close it with the X in the right hand side of it, all the
 * toggles go off." `groundField` ("Ground magnetic perturbation") has a real
 * rail toggle and plots real data, but it earns no card in the Data Explorer
 * — the panel's card/legend list (`layerOrder`) leaves it out on purpose,
 * because it has nothing to show there. A screenshot with it switched on
 * alongside the Full preset caught the regression this guards: closing left
 * it lit while every other toggle went dark, because the close handler had
 * been reading the narrower list too.
 */
test("the X turns off every real layer toggle, including ones with no card of their own", async ({ page }, testInfo) => {
  await page.addInitScript(() => localStorage.setItem("space-explorer-hide-welcome-v1", "1"));
  await page.goto("./");
  const startupTimeout = testInfo.project.name === "mobile" ? 120_000 : 90_000;
  await expect(page.locator("#visible-count")).toContainText("Selected", { timeout: startupTimeout });
  const openRail = async () => {
    if (await page.locator("#mobile-panel-toggle").isVisible()
      && !await page.locator("#control-rail").evaluate((rail) => rail.classList.contains("is-open"))) {
      await page.locator("#mobile-panel-toggle").click();
    }
  };
  await openRail();
  await page.locator("details.advanced-environment-details > summary").click();
  await page.locator("#layer-groundField").check();
  await expect(page.locator("#layer-groundField")).toBeChecked();
  await expect(page.locator("#data-viewer")).toBeVisible();
  // The close button lives over the globe, not in the rail; on the phone
  // sheet layout the rail has to fold away to reach it.
  if (await page.locator("#control-rail").evaluate((rail) => rail.classList.contains("is-open"))) {
    await page.locator("#mobile-panel-toggle").click();
  }
  await page.locator("#data-viewer-close").click();
  await expect(page.locator("#data-viewer")).toBeHidden();
  await openRail();
  await expect(page.locator("#layer-groundField")).not.toBeChecked();
});

test("presents Sean's first-visit welcome and full project credit", async ({ page }, testInfo) => {
  await page.addInitScript(() => {
    localStorage.removeItem("space-explorer-hide-welcome-v1");
    sessionStorage.removeItem("space-explorer-welcome-seen-v1");
  });
  await page.goto("./");
  const startupTimeout = testInfo.project.name === "mobile" ? 120_000 : 90_000;
  await expect(page.locator("#welcome-dialog")).toBeVisible({ timeout: startupTimeout });
  await expect(page.locator("#welcome-dialog")).toContainText("LT Sean Egan, PhD, USN");
  await expect(page.locator("#welcome-dialog")).toContainText("AG1 Derek Conklin");
  await page.locator("#welcome-about").click();
  await expect(page.locator("#about-dialog")).toBeVisible();
  // 2026-08: the About panel credits both creators on their own lines, Derek
  // first, and no longer publishes an email address — Sean built the site
  // feedback box precisely so no mailto sits on a public page (see
  // feedbackButton() in src/orbit-history-browser.ts). Feedback now goes
  // through the data-informed-feedback button.
  await expect(page.locator("#about-dialog")).toContainText("AG1 Derek Conklin, USN");
  await expect(page.locator("#about-dialog")).toContainText("LT Sean Egan, PhD, USN");
  await expect(page.locator('#about-dialog a[href^="mailto:"]')).toHaveCount(0);
  await expect(page.locator("#about-feedback")).toBeVisible();
});

/**
 * Every event on this page is a measured replay now, so this walks the replay.
 *
 * 27b27d4 gave gannon-2024, halloween-2003 and quebec-1989 real data replays,
 * and `eventPlayer()` branches on that: an event this project holds
 * measurements for gets `eventReplayBody`, an event it does not gets the
 * milestone stepper. Every event carries a `replay` today, so the stepper —
 * and with it `[data-event-title]` and `[data-event-timeline]`, which this
 * test used to drive — renders for none of them. Nothing is broken on the
 * page. Driven at 1440x900 and 390x844 to be sure of that before touching
 * anything: Gannon opens on its title, its Swarm-C vs WAM-IPE density chart,
 * its 400 km global ratio field and its SuperMAG driver strip, with a clean
 * console and no thrown exception on mount.
 *
 * The assertions below are the replay's own contract, which every view
 * shares: `[data-replay-clock]`, `[data-replay-range]`, `[data-replay-play]`
 * and the `[data-readout]` cells the drawing updates. A replay opens on its
 * FINAL frame, so a visitor who never presses Play still sees the whole
 * result; scrubbing BACK is therefore what proves the picture is driven by the
 * scrubber rather than printed once and left there.
 */
test("opens a historical replay and advances its causal timeline", async ({ page }, testInfo) => {
  await page.addInitScript(() => localStorage.setItem("space-explorer-hide-welcome-v1", "1"));
  await page.goto("./");
  const startupTimeout = testInfo.project.name === "mobile" ? 120_000 : 90_000;
  await expect(page.locator("#visible-count")).toContainText("Selected", { timeout: startupTimeout });
  if (await page.locator("#mobile-panel-toggle").isVisible()) {
    await page.evaluate(() => document.querySelector<HTMLButtonElement>('[data-view="events"]')?.click());
  } else {
    await page.locator('[data-view="events"]').click();
  }
  // Not a magic number. The count the page must draw is the count the
  // artifact declares, so this reads it off the manifest the browser was just
  // handed. Written as `toHaveCount(4)` it silently expired the first time an
  // event was added -- and it expired in the WORST possible way, because the
  // data publishes on its own five-minute timer while the frontend ships in an
  // image, so the number changed under a tree whose code had not.
  const declaredEvents = await page.evaluate(async () => {
    const response = await fetch("data/manifest.json", { cache: "no-store" });
    return (await response.json()).events.count as number;
  });
  expect(declaredEvents).toBeGreaterThanOrEqual(4);
  await expect(page.locator(".event-card")).toHaveCount(declaredEvents);
  /*
   * IT OPENS ON TOP, AND THE PAGE DOES NOT MOVE.
   *
   * Sean, 2026-08-21: "when you click to open the event, it looks like it opens
   * all events and scrolls the page through all of them to the correct one ...
   * This isn't good the way it is." Only one event was ever open; the player
   * was a panel ABOVE the grid and openEventPlayer() smooth-scrolled to it, so
   * the whole grid slid past the reader on the way to it. It is a modal
   * <dialog> now and nothing scrolls.
   *
   * Driven on the LAST card, because that is the worst case: it is the one
   * furthest from where the old panel sat, so it is the one whose reader
   * travelled the whole grid.
   *
   * The baseline is read AFTER scrolling that card into view. Playwright's own
   * click() scrolls its target into view first, and measuring before that would
   * be measuring the test harness rather than the page — it is how this
   * assertion failed the first time it ran, at 2424 -> 692 on a phone.
   *
   * `:modal` is the assertion worth making rather than `[open]`: it is true
   * only for showModal(), which is what buys the top layer, the inert page
   * behind, the focus trap and Escape. A dialog merely shown with show() would
   * satisfy [open] and give none of it.
   */
  const shell = page.locator("#content-view");
  const lastCard = page.locator(".event-card").last().locator("[data-replay-event]");
  const lastId = await lastCard.getAttribute("data-replay-event");
  await lastCard.scrollIntoViewIfNeeded();
  const scrollBefore = await shell.evaluate((el) => el.scrollTop);
  await lastCard.click();
  await expect(page.locator("#event-dialog")).toBeVisible();
  expect(await page.evaluate(() => document.getElementById("event-dialog")?.matches(":modal"))).toBe(true);
  expect(await shell.evaluate((el) => el.scrollTop)).toBe(scrollBefore);

  /*
   * AND IT CLOSES CLEANLY.
   *
   * Escape, because that is the way out a reader reaches for and the one a
   * hand-rolled overlay always forgets. Three things have to be true
   * afterwards: the reader is exactly where they were, focus is back on the
   * card they clicked rather than lost to the top of the document, and NOTHING
   * IS STILL RUNNING. Every replay drives itself with window.setInterval and
   * there are six of them on this page; one left ticking behind a closed panel
   * is a phone battery spent on a picture nobody can see. The empty player is
   * the proof: the handler that empties it is the same handler that destroys
   * the replay and clears its interval.
   */
  await page.keyboard.press("Escape");
  await expect(page.locator("#event-dialog")).toBeHidden();
  expect(await shell.evaluate((el) => el.scrollTop)).toBe(scrollBefore);
  await expect(page.locator("#event-player")).toBeEmpty();
  expect(await page.evaluate(() => (document.activeElement as HTMLElement | null)?.dataset?.replayEvent))
    .toBe(lastId);

  await page.locator('[data-replay-event="gannon-2024"]').click();
  await expect(page.locator("#event-player")).toBeVisible();
  // The visitor is told which event they opened.
  await expect(page.locator("#event-player .event-player-head h2")).toContainText("Gannon");

  const clock = page.locator("#event-player [data-replay-clock]");
  const measured = page.locator('#event-player [data-readout="measured"]');
  // Opens on the last frame — 13 May, after the storm — with a real Swarm-C
  // density ratio on the readout rather than the "—" the markup ships.
  await expect(clock).toContainText("2024-May-13");
  await expect(measured).toHaveText(/^×\d/);
  const atEnd = (await measured.textContent()) ?? "";

  // Scrub back to the start of the window. The clock and the measured density
  // must both follow the scrubber; that is the whole claim of the replay.
  await page.locator("#event-player [data-replay-range]").fill("0");
  await expect(clock).toContainText("2024-May-08");
  await expect(measured).not.toHaveText(atEnd);

  await expect(page.locator("#event-player [data-replay-play]")).toBeVisible();

  // The labelled button is the other way out of the dialog, and it has to take
  // the same path as Escape — including emptying the player, which is what
  // stops the clock.
  await page.locator("#event-player [data-close-event]").click();
  await expect(page.locator("#event-dialog")).toBeHidden();
  await expect(page.locator("#event-player")).toBeEmpty();
});

/**
 * Three surfaces, three jobs — proved by driving them, not by looking for their
 * ids.
 *
 * Sean: "if someone toggles something on, all you see initially is just the
 * legend change with that layers scale showing up… And if they have the data
 * viewer toggled on, a window pops up… nothing would appear in the right hand
 * panel except the layers and the NOAA data that we have always had there."
 *
 * Six features on this project have shipped unreachable behind green tests that
 * asked whether code existed. Every assertion below reads the running page: the
 * counts change, the boxes have positions, the panels have visibility.
 */
test("keeps the legend, the data viewer and the rail three separate things", async ({ page }, testInfo) => {
  // Same marathon-under-software-WebGL budget as the primary teaching flow.
  testInfo.setTimeout(900_000);
  await page.addInitScript(() => {
    localStorage.setItem("space-explorer-hide-welcome-v1", "1");
    // Both remembered preferences pinned, so this measures the design rather
    // than whatever a previous run left behind.
    //
    // The Explorer key is v2. It was v1 here for months after 8c771ca renamed
    // it — deliberately, so that a stored "collapsed" from before that change
    // could not survive it — and a seed written to a key nothing reads is a
    // seed that does nothing: every `is-collapsed` expectation below was
    // riding on the shipped default instead, which 8c771ca had just inverted.
    // A folded Explorer is the state this test needs, because (d) proves that
    // a click on its head EXPANDS it, and that click cannot mean anything
    // against a panel that was already open.
    localStorage.setItem("space-explorer-data-explorer-collapsed-v2", "1");
    localStorage.setItem("space-explorer-map-key-collapsed-v1", "0");
  });
  const errors: string[] = [];
  page.on("console", (message) => { if (message.type() === "error" && !isVpsOnlyArtifact(message.text())) errors.push(message.text()); });
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("./");
  const startupTimeout = testInfo.project.name === "mobile" ? 120_000 : 90_000;
  await expect(page.locator("#visible-count")).toContainText("Selected", { timeout: startupTimeout });

  const desktop = testInfo.project.name === "desktop";
  const openRail = async () => {
    if (await page.locator("#mobile-panel-toggle").isVisible()
      && !await page.locator("#control-rail").evaluate((rail) => rail.classList.contains("is-open"))) {
      await page.locator("#mobile-panel-toggle").click();
    }
  };

  // (a) First visit, Satellites mode: nothing is plotting, so the explorer has
  // no reason to exist yet. There is no switch for it any more.
  await expect(page.locator("#data-viewer")).toBeHidden();
  await expect(page.locator("#data-viewer-toggle")).toHaveCount(0);
  await openRail();
  await expect(page.locator(".environment-section")).toBeVisible();
  // CHANGING MODE DRAWS NOTHING. `setMode` used to call
  // `applyLayerPreset(this.currentPreset)` on the way into Space weather,
  // which is how the thermosphere came to be on before anyone asked for it; a
  // preset is something the reader CHOOSES, and until they do, no preset
  // button reads as selected either. What arrives with the mode is the control
  // surface — the layer list, the preset row, and the count that says nought.
  await expect(page.locator("#active-layer-count")).toHaveText("0 on");
  await expect(page.locator("[data-preset].is-active")).toHaveCount(0);
  await expect(page.locator("#layer-thermosphere")).not.toBeChecked();
  await expect(page.locator("#key-cards .key-card")).toHaveCount(0);
  await expect(page.locator("#data-viewer")).toBeHidden();

  // Press Simple, and the preset does the thing the mode switch stopped doing:
  // the thermosphere arrives, and the explorer appears on its own alongside
  // it — folded, because this profile folded it and nothing has asked it to
  // open.
  await openRail();
  await page.locator('[data-preset="simple"]').click();
  await expect(page.locator('[data-preset="simple"]')).toHaveClass(/is-active/);
  await expect(page.locator("#layer-thermosphere")).toBeChecked();
  await expect(page.locator("#active-layer-count")).toHaveText("1 on");
  await expect(page.locator("#key-cards .key-card")).toHaveCount(1, { timeout: 60_000 });
  await expect(page.locator("#data-viewer")).toBeVisible();
  await expect(page.locator("#data-viewer")).toHaveClass(/is-collapsed/);

  // (b) One layer on: the legend grows and the explorer appears alongside it
  // — collapsed, because the whole point of this redesign is that switching a
  // layer on changes the legend and reveals a one-line head, not a window.
  await openRail();
  for (const id of ["layer-thermosphere", "layer-tec", "layer-aurora"]) {
    const box = page.locator(`#${id}`);
    if (await box.isChecked()) await box.uncheck();
  }
  await expect(page.locator("#key-cards .key-card")).toHaveCount(0, { timeout: 60_000 });
  // No layer at all: the explorer is gone outright, not merely collapsed.
  await expect(page.locator("#data-viewer")).toBeHidden();
  await page.locator("#layer-aurora").check();
  await expect(page.locator("#key-cards .key-card")).toHaveCount(1, { timeout: 60_000 });
  // Present, collapsed, and no other panel opened itself on the way.
  await expect(page.locator("#data-viewer")).toBeVisible();
  await expect(page.locator("#data-viewer")).toHaveClass(/is-collapsed/);
  await expect(page.locator("#display-settings")).toBeHidden();
  await expect(page.locator("#storm-dropdown")).toBeHidden();
  await page.locator("#layer-tec").check();
  await expect(page.locator("#key-cards .key-card")).toHaveCount(2, { timeout: 60_000 });
  await expect(page.locator("#data-viewer")).toBeVisible();
  await expect(page.locator("#data-viewer")).toHaveClass(/is-collapsed/);

  // (c) The legend entry is the colour bar, the name and the units. Nothing
  //     else — no badge, no validity, no sentence.
  //
  // Assert it at a time the release covers. When a layer has nothing to draw at
  // the selected moment the site adds a fourth child on purpose — a button
  // offering to move the clock to a time that does have data — so measuring the
  // row against a stale release measures the affordance rather than the rule.
  // This test used to depend on how long ago the release was built: aurora
  // coverage ran out and the row grew to four children, identically at
  // 6ecd07b, before any of this branch's work.
  await page.evaluate(async () => {
    const manifest = await fetch("data/manifest.json").then((response) => response.json()) as {
      aurora?: { validFrom?: string; validTo?: string };
    };
    const validTo = manifest.aurora?.validTo;
    if (!validTo) return;
    const slider = document.querySelector<HTMLInputElement>("#time-slider");
    if (!slider) return;
    // Half an hour inside the published end, so the frame is unambiguous.
    const target = Date.parse(validTo) - 30 * 60_000;
    slider.value = String(Math.round((target - Date.now()) / 60_000));
    slider.dispatchEvent(new Event("input", { bubbles: true }));
  });
  const auroraRow = page.locator('#key-cards [data-layer="aurora"]');
  await expect(auroraRow).not.toContainText("NO DATA AT THIS TIME", { timeout: 60_000 });
  await expect(auroraRow).toContainText("Aurora viewing probability");
  await expect(auroraRow.locator(".key-card-scale")).toHaveCount(1);
  await expect(auroraRow.locator(".key-card-title")).toHaveCount(1);
  await expect(auroraRow.locator(".key-card-values")).toHaveCount(1);
  // Three children at most — title, bar, values — and no prose in any of them.
  const rowShape = await auroraRow.evaluate((row) => ({
    children: row.childElementCount,
    longest: Math.max(...[...row.children].map((child) => (child.textContent ?? "").trim().length)),
  }));
  expect(rowShape.children).toBeLessThanOrEqual(3);
  expect(rowShape.longest).toBeLessThan(90);
  await expect(auroraRow).not.toContainText("FORECAST");
  await expect(auroraRow).not.toContainText("Valid at");
  await expect(auroraRow).not.toContainText("NOAA OVATION 30");
  // Every row that can appear has the same shape, whatever the layer.
  const shapes = await page.locator("#key-cards .key-card").evaluateAll((rows) => rows.map((row) => [...row.children].map((child) => child.className.split(" ")[0]).join("|")));
  expect(new Set(shapes).size).toBe(1);

  // (d) The data viewer is a window of its own, in the top-right. It is
  // already present and collapsed from (b); clicking its head expands it —
  // the same click that would have collapsed it again is what a drag with no
  // real movement resolves to, pinned separately below.
  await openRail();
  await page.locator("#data-viewer-head").click();
  await expect(page.locator("#data-viewer")).toBeVisible();
  await expect(page.locator("#data-viewer")).not.toHaveClass(/is-collapsed/);
  if (desktop) {
    const geometry = await page.evaluate(() => {
      const scene = document.querySelector(".scene-shell")!.getBoundingClientRect();
      const viewer = document.getElementById("data-viewer")!.getBoundingClientRect();
      const legend = document.getElementById("map-key")!.getBoundingClientRect();
      return {
        rightHalf: viewer.left > scene.left + scene.width / 2,
        topHalf: viewer.top < scene.top + scene.height / 2,
        clearOfLegend: viewer.bottom <= legend.top || viewer.top >= legend.bottom
          || viewer.right <= legend.left || viewer.left >= legend.right,
        insideScene: viewer.right <= scene.right + 1 && viewer.bottom <= scene.bottom + 1,
      };
    });
    expect(geometry.rightHalf, "the data viewer is not in the right half of the scene").toBe(true);
    expect(geometry.topHalf, "the data viewer is not in the top half of the scene").toBe(true);
    expect(geometry.clearOfLegend, "the data viewer overlaps the legend").toBe(true);
    expect(geometry.insideScene, "the data viewer hangs outside the scene").toBe(true);

    // Sean: "I can't scroll or resize or move it? That is a problem." Drag the
    // head and prove the panel actually moved — not merely that a handler is
    // attached, but that its on-screen position changed by roughly the drag
    // distance.
    const before = (await page.locator("#data-viewer").boundingBox())!;
    const handle = page.locator("#data-viewer-head");
    const handleBox = (await handle.boundingBox())!;
    await page.mouse.move(handleBox.x + handleBox.width / 2, handleBox.y + handleBox.height / 2);
    await page.mouse.down();
    await page.mouse.move(handleBox.x - 120, handleBox.y + 90, { steps: 12 });
    await page.mouse.up();
    const after = (await page.locator("#data-viewer").boundingBox())!;
    expect(Math.hypot(after.x - before.x, after.y - before.y), "dragging the head did not move the panel").toBeGreaterThan(50);
    // A drag is not a click: the panel must still be expanded, not folded.
    await expect(page.locator("#data-viewer")).not.toHaveClass(/is-collapsed/);
  }
  // It is the readings, not the legend: everything the legend refuses to carry
  // — validity, provenance, the derived numbers — is in here.
  await expect(page.locator('#data-viewer-cards [data-layer="aurora"]')).toContainText("Published coverage");
  await expect(page.locator('#data-viewer-cards [data-layer="aurora"]')).toContainText("Valid at");

  // (e) The rail carries the layers and the NOAA block, and nothing that
  //     reports a value.
  //
  // 2ee0ce8 moved the NOAA block inside "Conditions right now", and that fold
  // is the one in this rail that ships SHUT — it is the single readout in a
  // column of controls, and the pass that moved it existed to get the controls
  // above the fold. So the block is reached the way a reader reaches it rather
  // than expected to be on screen already.
  await openRail();
  await expect(page.locator("#swpc-summary")).toBeHidden();
  await page.locator("#conditions-details > summary").click();
  await expect(page.locator("#swpc-summary")).toBeVisible();
  // No layer's readings and no storm panel in the rail — with ONE exception,
  // named rather than waved through. Sean asked for the NOAA block back in the
  // rail himself ("the SWPC 'card' that was in the rail previously. It looked
  // good. We can just have it be under 'space weather' as a separate,
  // collapsable entry"), and 2ee0ce8 put it and the drivers inside "Conditions
  // right now", shut. Anything on this list OUTSIDE that fold is a value that
  // has escaped back into the column of controls.
  const railHasReadouts = await page.evaluate(() => {
    const rail = document.getElementById("control-rail")!;
    const conditionsFold = document.getElementById("conditions-details");
    return ["key-cards", "data-viewer-cards", "weather-readout", "key-conditions", "storm-panel"]
      .filter((id) => {
        const node = rail.querySelector(`#${id}`);
        return node !== null && !(conditionsFold?.contains(node) ?? false);
      });
  });
  expect(railHasReadouts).toEqual([]);
  // ...and the one exception really is inside that fold, so "allowed" cannot
  // quietly become "anywhere in the rail".
  await expect(page.locator("#conditions-details #weather-readout")).toHaveCount(1);

  // Sean: "The last screenshot shows a ton of nested data and selection options
  // within the right-hand panel - not what I asked for. That should all be in
  // the data viewer." Measured on the running page with every layer switched
  // on, which is the only state in which the old nesting appeared.
  // The Data Explorer was expanded above, which closes the phone sheet
  // ("one sheet at a time"), so the rail has to be re-opened before its
  // own controls can be reached again.
  await openRail();
  await page.locator('[data-preset="full"]').click();
  await expect(page.locator("#key-cards .key-card")).not.toHaveCount(0);

  // Sean: "it can collapse into one row" and, expanded, dig as deep as he
  // wants — with every layer on there is more in the panel than its bounded
  // height can hold, so it has to scroll rather than clip or grow unbounded.
  // Opening the rail above closed the Data Explorer on a phone, and this
  // assertion is about the Explorer. Put the screen back the way the assertion
  // assumes: sheet away, Explorer expanded. Both are no-ops on desktop.
  if (await page.locator("#mobile-panel-toggle").isVisible()
    && await page.locator("#control-rail").evaluate((rail) => rail.classList.contains("is-open"))) {
    await page.locator("#mobile-panel-toggle").click();
  }
  if (await page.locator("#data-viewer").evaluate((el) => el.classList.contains("is-collapsed"))) {
    await page.locator("#data-viewer-head").click();
  }
  // 2 min, and it is a machine-speed allowance rather than a performance
  // assertion — the same kind as this file's 15 min walk budget. Full switches
  // seven layers on at once and the radiation volume alone bakes for tens of
  // seconds under SwiftShader; the cards are built empty and GROW as each
  // artifact lands, so what is being waited for is the content arriving, not
  // the layout deciding. Measured on the built page at 1440x900 with all seven
  // in: 485 px of cards in a 393 px body. At 20 s on a busy bigmem the cards
  // were all present and still short of the box, and the click that expands
  // the panel had itself taken 30 s to land.
  await expect
    .poll(() => page.locator("#data-viewer-body").evaluate((el) => el.scrollHeight > el.clientHeight + 4), { timeout: 120_000 })
    .toBe(true);

  // No value with two homes: with the solar-wind and photon layers on (Full
  // switched them on above), their own cards carry V/Bz and CLASS/FLUX in
  // more detail, so the header's duplicate rows for the same numbers fold
  // away — driven live, not merely present with `hidden` written by hand.
  // Read the `hidden` property directly rather than Playwright's `toBeVisible`,
  // which also depends on whether "Measured drivers" happens to be open — a
  // separate, independently-toggled disclosure this check has no business
  // depending on.
  const driverVisibility = await page.evaluate(() => {
    const hiddenOf = (selector: string) => document.querySelector<HTMLElement>(selector)?.hidden;
    return {
      solarWind: hiddenOf('#weather-readout [data-drivers-dedupe="solarWind"]'),
      photons: hiddenOf('#weather-readout [data-drivers-dedupe="photons"]'),
      ionosphere: hiddenOf('#weather-readout [data-drivers-dedupe="ionosphere"]'),
      kp: [...document.querySelectorAll<HTMLElement>("#weather-readout article")]
        .find((article) => article.textContent?.includes("Planetary Kp"))?.hidden,
    };
  });
  expect(driverVisibility.solarWind).toBe(true);
  // The X-ray chip STAYS under Full, and the reason is the rule working rather
  // than failing: `photons` is deliberately in no preset (bb9fd2c) — the X-ray
  // visual is one scalar and a contrast, and it is only worth drawing beside
  // the wind and the boundary — so Full leaves it off, no photon card exists,
  // and the header is the only home that number has. The comment above this
  // block said "with the solar-wind and photon layers on (Full switched them
  // on above)", which stopped being true when the presets did.
  expect(driverVisibility.photons).toBe(false);
  // So prove the photon half of the rule properly, by switching the layer on.
  // Its checkbox is a hidden input on purpose — the walkthrough drives it and
  // no rail row does — so it is dispatched rather than clicked.
  await page.locator("#layer-photons").dispatchEvent("click");
  await expect(page.locator('#data-viewer-cards [data-layer="photons"]')).toHaveCount(1, { timeout: 60_000 });
  await expect
    .poll(() => page.locator('#weather-readout [data-drivers-dedupe="photons"]').evaluate((el: HTMLElement) => el.hidden), { timeout: 30_000 })
    .toBe(true);
  await page.locator("#layer-photons").dispatchEvent("click");
  await expect(page.locator('#data-viewer-cards [data-layer="photons"]')).toHaveCount(0, { timeout: 60_000 });
  // ...and the row comes back when the card that restated it goes, because a
  // number that is folded away with nothing left showing it is a number lost.
  await expect
    .poll(() => page.locator('#weather-readout [data-drivers-dedupe="photons"]').evaluate((el: HTMLElement) => el.hidden), { timeout: 30_000 })
    .toBe(false);
  // The F2 peak chip now STAYS. The rule is "fold the header row away when a
  // layer card restates the same number", and since the ionospheric peak
  // surfaces moved to the learning pages on 2026-08-18 there is no such card
  // any more — so the header is the only place that number appears, and hiding
  // it would lose it. The chip is fed by the same WAM-IPE column the probe
  // reads; retiring the LAYER did not retire the measurement.
  expect(driverVisibility.ionosphere).toBe(false);
  // Kp has no layer card restating it, so it stays.
  expect(driverVisibility.kp).toBe(false);

  const duplicateStats = await page.evaluate(() => {
    const headerLabels = [...document.querySelectorAll("#weather-readout article:not([hidden]) > span")]
      .map((node) => node.textContent?.trim())
      .filter((text): text is string => Boolean(text));
    const cardLabels = [...document.querySelectorAll("#data-viewer-cards .fact-grid span")]
      .map((node) => node.textContent?.trim())
      .filter((text): text is string => Boolean(text));
    return headerLabels.filter((label) => cardLabels.includes(label));
  });
  expect(duplicateStats, "a header row survives alongside the same label in a layer card").toEqual([]);

  const railStrays = await page.evaluate(() => {
    const rail = document.getElementById("control-rail")!;
    return [...rail.querySelectorAll("[data-layer-panel], select, fieldset.segmented")]
      // The two the rail is allowed: the layer preset, and the orbit-class
      // filters in the satellites half. (`.mode-section` was a third until
      // 2026-08-28; Explorer Mode is retired and its fieldset with it.)
      .filter((node) => !node.closest(".search-section, [data-mode-panel='satellites']")
        && !node.classList.contains("layer-presets"))
      .map((node) => node.className || node.tagName.toLowerCase());
  });
  expect(railStrays, "a per-layer setting is back in the rail").toEqual([]);

  // Every control that moved, resolved in its new home AND driven, because a
  // control that is merely present would pass a screenshot review and fail a
  // reader. This is the failure mode this project keeps shipping: the node is
  // there, the listener is not.
  // The empirical-boundary annotation and its cut-open toggle live in the
  // plasma-field layer's card now, behind that card's own settings fold.
  await openLayerCard(page, "geospace");
  const cut = page.locator("#data-viewer #magnetopause-cut");
  await expect(cut).toBeVisible();
  await cut.check();
  await expect(cut).toBeChecked();
  // Its handler switches the globe to the cross-section presentation, which is
  // a different thing from the checkbox remembering it was clicked.
  await expect(page.locator('#key-cards [data-layer="geospace"]')).toContainText(/Magnetosphere/i);
  await cut.uncheck();

  await openLayerCard(page, "thermosphere");
  const surface = page.locator("#data-viewer #thermosphere-level");
  await expect(surface).toBeVisible();
  await surface.selectOption("1e-13");
  await expect(surface).toHaveValue("1e-13");
  // The handler re-renders the layer, so the viewer's own readings change: a
  // thinner air density is reached higher up, so the surface moves.
  await expect(page.locator('#data-viewer-cards [data-layer="thermosphere"]')).toContainText("LOWEST");
  await surface.selectOption("1e-12");

  if (desktop) {
    await openLayerCard(page, "radiation");
    for (const control of ["#radiation-pitch-select", '[data-radiation-energy="452.75"]', '[data-radiation-view="nativeEquatorial"]']) {
      await expect(page.locator(`#data-viewer ${control}`), `${control} is not in the data viewer`).toHaveCount(1);
    }
    await page.locator('[data-radiation-energy="452.75"]').click();
    await expect(page.locator('[data-radiation-energy="452.75"]')).toHaveClass(/is-active/);
    await expect(page.locator('[data-radiation-energy="-1"]')).not.toHaveClass(/is-active/);
    // The card's ENERGY reading is written from the renderer's own metadata for
    // the frame it just drew, so this proves the click reached the globe rather
    // than only repainting the button.
    await expect(page.locator('#data-viewer-cards [data-layer="radiation"]')).toContainText("453 keV", { timeout: 30_000 });
    // ...and back to the opening view, which is every energy at once.
    await page.locator('[data-radiation-energy="-1"]').click();
    await expect(page.locator('#data-viewer-cards [data-layer="radiation"]'))
      .toContainText("ALL ENERGIES (COMBINED)", { timeout: 30_000 });
  }
  await openRail();
  await page.locator('[data-preset="simple"]').click();

  // The walkthrough's rail door is below every layer toggle and is no longer
  // the largest thing in the column.
  await expect(page.locator("#energy-chain-open")).toHaveCount(1);
  const doorPlacement = await page.evaluate(() => {
    const door = document.getElementById("energy-chain-open");
    const preset = document.querySelector(".layer-presets");
    const rows = [...document.querySelectorAll<HTMLElement>("#layer-list .layer-control")];
    if (!door || !preset || rows.length === 0) return null;
    return {
      belowEveryToggle: rows.every((row) => (door.compareDocumentPosition(row) & Node.DOCUMENT_POSITION_PRECEDING) !== 0),
      belowThePreset: (door.compareDocumentPosition(preset) & Node.DOCUMENT_POSITION_PRECEDING) !== 0,
      shorterThanALayerRow: door.getBoundingClientRect().height <= rows[0]!.getBoundingClientRect().height,
    };
  });
  expect(doorPlacement?.belowEveryToggle, "the walkthrough door is not below the layer toggles").toBe(true);
  expect(doorPlacement?.belowThePreset).toBe(true);
  expect(doorPlacement?.shorterThanALayerRow, "the walkthrough door is still taller than a layer row").toBe(true);

  // The second door — the one a reader arrives at from the lessons — still
  // exists and still starts the walkthrough. It is the natural way in, so a
  // merge that broke it would matter more than the rail shortcut.
  if (await page.locator("#mobile-panel-toggle").isVisible()) {
    await page.evaluate(() => document.querySelector<HTMLButtonElement>('[data-view="learn-weather"]')?.click());
  } else {
    await page.locator('[data-view="learn-weather"]').click();
  }
  await expect(page.locator("#energy-chain-open-learn")).toBeVisible();
  await page.locator("#energy-chain-open-learn").click();
  await expect(page.locator("#energy-chain-panel")).toBeVisible({ timeout: 60_000 });
  await page.locator("#energy-chain-panel .chain-walk__close").click();
  await expect(page.locator("#energy-chain-panel")).toBeHidden();

  expect(errors).toEqual([]);
});

/**
 * Which satellites are plotted. Sean asked for the selector the rail already
 * uses for All / LEO / MEO / GEO / HEO instead of a switch with a paragraph
 * under it, and the one risk in that swap is inverting the meaning — so this
 * counts markers on the globe rather than reading the control back.
 */
test("asks which satellites to plot with the site's segmented selector", async ({ page }, testInfo) => {
  await page.addInitScript(() => localStorage.setItem("space-explorer-hide-welcome-v1", "1"));
  const errors: string[] = [];
  page.on("console", (message) => { if (message.type() === "error" && !isVpsOnlyArtifact(message.text())) errors.push(message.text()); });
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("./");
  const startupTimeout = testInfo.project.name === "mobile" ? 120_000 : 90_000;
  await expect(page.locator("#visible-count")).toContainText("Selected", { timeout: startupTimeout });
  if (await page.locator("#mobile-panel-toggle").isVisible()) await page.locator("#mobile-panel-toggle").click();

  // The search matches on the start of a name, and no object in this catalog is
  // named "GPS" — they are NAVSTARs. A query that matched nothing would have
  // failed here as a timeout with no explanation.
  await page.locator("#satellite-search").fill("NOAA 20");
  await expect(page.locator("#search-results [role=option]").first()).toBeVisible();
  await page.locator("#search-results [role=option]").first().click();
  await expect(page.locator("#satellite-stack")).toBeVisible();

  // TAKE THE WHOLE CATALOG BEFORE COUNTING ANYTHING. Selected/All only means
  // something against a POPULATION: if the opened spacecraft were the only
  // thing drawn, both positions of the control would plot the same one marker
  // and an inverted control would read as correct. 17aa11f stopped the site
  // drawing a population nobody asked for, which is what took this test's
  // `withAll` from 450 to 1 and made the check below vacuous.
  //
  // What the globe holds BEFORE this ask is the scope/facet state model's own
  // business — the band is single-select and survives Clear, unset is not the
  // same as All, and the featured constellation draws with no band lit — and it
  // is pinned by that model's test, not restated here.
  await phoneOpenRail(page);
  await page.locator('[data-orbit="all"]').click();
  await expect(page.locator("#visible-count")).toHaveText(/^[1-9][0-9,]* Selected$/);

  // EVERY CONTROL THIS TEST USED TO DRIVE IS DELETED, and the assertions are
  // inverted rather than dropped, because the failure this test now guards is
  // one of them coming back. Sean, 2026-08-28: "one at a time. that lets you
  // get rid of the 'x # satellites selected' line at the top with the X, as
  // well as the View Selected, View All, Clear Selected line. you'll just have
  // the card for the satellite."
  await expect(page.locator("#satellite-solo")).toHaveCount(0);
  await expect(page.locator(".stack-isolate")).toHaveCount(0);
  await expect(page.locator(".stack-scope")).toHaveCount(0);
  await expect(page.locator("[data-satellite-scope]")).toHaveCount(0);
  await expect(page.locator("#satellite-stack-clear")).toHaveCount(0);
  await expect(page.locator("#satellite-stack-count")).toHaveCount(0);
  await expect(page.locator("#satellite-stack-close")).toHaveCount(0);

  const shown = async () => Number((await page.locator("#visible-count").textContent() ?? "0").replace(/[^0-9]/g, ""));
  const withAll = await shown();
  expect(withAll).toBeGreaterThan(1);

  // WHAT REPLACED THE SCOPE CONTROL is that there is nothing to scope: opening
  // a second spacecraft REPLACES the first rather than adding to a list, and
  // the whole catalog stays drawn around it.
  await expect(page.locator("#satellite-stack-cards .sat-card")).toHaveCount(1);
  await page.locator("#satellite-search").fill("HST");
  await expect(page.locator("#search-results [role=option]").first()).toBeVisible();
  await page.locator("#search-results [role=option]").first().click();
  await expect(page.locator("#satellite-stack-cards .sat-card")).toHaveCount(1);
  await expect(page.locator("#satellite-stack-cards [data-card-name]")).toContainText("HST");
  expect(await shown()).toBe(withAll);

  // The card's X drops the drawn geometry and closes the panel, and it is the
  // only control that does: the panel-level X went with the count.
  await page.locator("#satellite-stack-cards .sat-card [data-card-remove]").click();
  await expect(page.locator("#satellite-stack")).toBeHidden();
  await expect(page.locator(".satellite-map-label--selected.is-visible")).toHaveCount(0);
  expect(errors).toEqual([]);
});

/**
 * Favorites, end to end, in a real browser — the only place the two claims
 * that matter can actually be tested: that the star writes to this machine's
 * localStorage, and that a full page reload brings the list back.
 */
test("keeps starred satellites in this browser across a reload", async ({ page }, testInfo) => {
  await page.addInitScript(() => localStorage.setItem("space-explorer-hide-welcome-v1", "1"));
  const errors: string[] = [];
  page.on("console", (message) => { if (message.type() === "error" && !isVpsOnlyArtifact(message.text())) errors.push(message.text()); });
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("./");
  const startupTimeout = testInfo.project.name === "mobile" ? 120_000 : 90_000;
  await expect(page.locator("#visible-count")).toContainText("Selected", { timeout: startupTimeout });
  if (await page.locator("#mobile-panel-toggle").isVisible()) await page.locator("#mobile-panel-toggle").click();
  const openRail = async () => {
    if (await page.locator("#mobile-panel-toggle").isVisible()
      && !await page.locator("#control-rail").evaluate((rail) => rail.classList.contains("is-open"))) {
      await page.locator("#mobile-panel-toggle").click();
    }
  };

  /**
   * The favourites section folds shut by default. That was deliberate: empty,
   * it was five lines of explanation about a list with nothing in it, sitting
   * above the catalog in the mode where a reader came to find a satellite. The
   * COUNT stays on the summary row, because whether anything is starred is the
   * one fact worth seeing while it is closed.
   *
   * So the count assertions below run against the closed section on purpose,
   * and every assertion about the list itself opens it first.
   */
  const openFavorites = async () => {
    const details = page.locator("#favorites-details");
    if (!await details.evaluate((node) => (node as HTMLDetailsElement).open)) {
      await details.locator("summary").click();
    }
  };

  // Closed, the section still reports the one fact it must: nothing starred.
  await expect(page.locator("#favorites-count")).toHaveText("0 of 200");
  await expect(page.locator("#favorites-empty")).toBeHidden();

  // Empty state: the section is there, it says what it is for, and it says
  // where the list lives.
  await openFavorites();
  await expect(page.locator("#favorites-empty")).toBeVisible();
  await expect(page.locator(".favorites-note")).toContainText("Stored only in this browser");
  await expect(page.locator("#favorites-list .search-result-row")).toHaveCount(0);

  // Star from the search results — one of the two places a satellite is
  // presented on its own.
  await page.locator("#satellite-search").fill("NOAA 20");
  const firstResult = page.locator("#search-results .search-result-row").first();
  await expect(firstResult).toBeVisible();
  const starredName = await firstResult.locator("strong").textContent();
  await firstResult.locator(".favorite-star").click();
  await expect(firstResult.locator(".favorite-star")).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("#favorites-count")).toHaveText("1 of 200");
  await expect(page.locator("#favorites-empty")).toBeHidden();
  await expect(page.locator("#favorites-list .search-result-row")).toHaveCount(1);
  await expect(page.locator("#favorites-list strong").first()).toHaveText(starredName!);

  // It is a NORAD number on disk, not a name and not a position in the list.
  const stored = await page.evaluate(() => localStorage.getItem("space-explorer-favorites-v1"));
  expect(stored).toBeTruthy();
  const parsed = JSON.parse(stored!) as { schema: number; ids: number[] };
  expect(parsed.schema).toBe(1);
  expect(parsed.ids).toHaveLength(1);
  expect(Number.isInteger(parsed.ids[0])).toBe(true);
  expect(stored).not.toContain(starredName!);

  // Star a second one from the satellite's own card.
  await page.locator("#search-results .search-result").first().click();
  await expect(page.locator("#satellite-stack")).toBeVisible();
  const cardStar = page.locator(".sat-card.is-active [data-card-favorite]");
  await expect(cardStar).toHaveAttribute("aria-pressed", "true");
  // Selecting a satellite closes the phone sheet, so the search field and
  // its results are off screen again by now.
  await openRail();
  await page.locator("#satellite-search").fill("HST");
  await page.locator("#search-results .search-result").first().click();
  await expect(page.locator(".sat-card.is-active [data-card-name]")).toContainText("HST");
  await page.locator(".sat-card.is-active [data-card-favorite]").click();
  await expect(page.locator("#favorites-count")).toHaveText("2 of 200");

  // The reload. Nothing here is server-side, so this is the whole persistence
  // claim: same machine, same browser, new page.
  await page.reload();
  await expect(page.locator("#visible-count")).toContainText("Selected", { timeout: startupTimeout });
  if (await page.locator("#mobile-panel-toggle").isVisible()) await page.locator("#mobile-panel-toggle").click();
  await expect(page.locator("#favorites-count")).toHaveText("2 of 200");
  await openFavorites();
  await expect(page.locator("#favorites-list .search-result-row")).toHaveCount(2);
  await expect(page.locator("#favorites-list strong")).toContainText(["HST", starredName!]);

  // Selecting from favorites behaves exactly like selecting from search.
  await openRail();
  await openFavorites();
  await page.locator("#favorites-list .search-result").first().click();
  await expect(page.locator("#satellite-stack")).toBeVisible();
  await expect(page.locator(".sat-card.is-active [data-card-name]")).toContainText("HST");
  await expect(page.locator(".sat-card.is-active [data-card-ephemeris]")).toContainText("CelesTrak OMM");

  // Unstarring from the card removes the row, and the two surfaces agree.
  await page.locator(".sat-card.is-active [data-card-favorite]").click();
  await expect(page.locator("#favorites-count")).toHaveText("1 of 200");
  await expect(page.locator("#favorites-list .search-result-row")).toHaveCount(1);
  await expect(page.locator(".sat-card.is-active [data-card-favorite]")).toHaveAttribute("aria-pressed", "false");
  await openFavorites();

  // A favorite whose object this release no longer publishes is kept, greyed,
  // and labelled rather than dropped on the floor.
  await page.evaluate(() => localStorage.setItem(
    "space-explorer-favorites-v1",
    JSON.stringify({ schema: 1, ids: [20580, 99999] }),
  ));
  await page.reload();
  await expect(page.locator("#visible-count")).toContainText("Selected", { timeout: startupTimeout });
  if (await page.locator("#mobile-panel-toggle").isVisible()) await page.locator("#mobile-panel-toggle").click();
  await openFavorites();
  await expect(page.locator("#favorites-list .search-result-row")).toHaveCount(2);
  const missingRow = page.locator("#favorites-list .favorites-row-missing");
  await expect(missingRow).toHaveCount(1);
  await expect(missingRow).toContainText("NORAD 99999");
  await expect(missingRow).toContainText("Not in this release's catalog");
  await expect(missingRow.locator(".search-result")).toBeDisabled();
  await missingRow.locator(".favorite-star").click();
  await expect(page.locator("#favorites-count")).toHaveText("1 of 200");

  // Garbage in the key must degrade to an empty list, not to a broken page.
  await page.evaluate(() => localStorage.setItem("space-explorer-favorites-v1", '{"schema":1,"ids":[2058'));
  await page.reload();
  await expect(page.locator("#visible-count")).toContainText("Selected", { timeout: startupTimeout });
  if (await page.locator("#mobile-panel-toggle").isVisible()) await page.locator("#mobile-panel-toggle").click();
  await expect(page.locator("#favorites-count")).toHaveText("0 of 200");
  await openFavorites();
  await expect(page.locator("#favorites-empty")).toBeVisible();
  expect(errors).toEqual([]);
});

/**
 * A key card's controls must survive long enough to be clicked.
 *
 * The cards were rebuilt on every environment update — 4.3 DOM replacements a
 * second, measured on the live site — and a control replaced every ~230 ms
 * cannot be clicked at all: the pointer press and release land on two
 * different nodes, so the browser produces no click event. That silently
 * disabled the "Go to <time> UTC" button on every no-data card, which is the
 * one control a visitor needs at exactly the moment a layer has nothing to
 * show. The handler was always correct; it simply never received the event.
 *
 * This asserts the property that makes the control usable rather than the
 * implementation that provides it: the node under the visitor's pointer stays
 * put while nothing about the card's content has changed.
 */
test("key cards are not rebuilt underneath the visitor's pointer", async ({ page }, testInfo) => {
  testInfo.setTimeout(300_000);
  await page.addInitScript(() => localStorage.setItem("space-explorer-hide-welcome-v1", "1"));
  await page.goto("./");
  await expect(page.locator("#visible-count")).toContainText("Selected", { timeout: 90_000 });
  // On a phone the rail is a bottom sheet that ships closed, so the mode switch
  // and the layer checkboxes below are off screen until it is opened. A no-op
  // on desktop and tablet, where the toggle is not rendered.
  if (await page.locator("#mobile-panel-toggle").isVisible()
    && !await page.locator("#control-rail").evaluate((rail) => rail.classList.contains("is-open"))) {
    await page.locator("#mobile-panel-toggle").click();
  }
  await page.locator("#layer-thermosphere").check();
  // The legend lives at the foot of the screen, under the sheet that was just
  // opened to reach the layer toggles, and a phone folds it by default.
  await showLegend(page);
  const card = page.locator("#key-cards .key-card").first();
  await expect(card).toBeVisible({ timeout: 120_000 });
  // Let the layer settle so genuine content changes are not counted as churn.
  await page.waitForTimeout(4_000);

  const replacements = await page.evaluate(() => new Promise<number>((resolve) => {
    let added = 0;
    const observer = new MutationObserver((records) => {
      for (const record of records) if (record.addedNodes.length) added += 1;
    });
    observer.observe(document.querySelector("#key-cards")!, { childList: true, subtree: true });
    setTimeout(() => { observer.disconnect(); resolve(added); }, 4_000);
  }));
  // A settled card whose readings have not changed should not be rebuilt at
  // all; the allowance is for a real datum arriving mid-window.
  expect(replacements, `key cards were rebuilt ${replacements} times in 4 s while settled`).toBeLessThanOrEqual(2);
});


/**
 * THE FILTER STATE MODEL, DRIVEN THROUGH ITS TRANSITIONS.
 *
 * Four separate complaints from Sean landed on this one rail, and every one of
 * them was the same defect wearing a different coat: the controls held a copy
 * of the state instead of rendering it, so they drifted, and each place they
 * drifted grew an affordance to rescue the reader from the drift.
 *
 *   "all the filters are selected. That is odd - we're not showing anything so
 *    why are they selected?"
 *   "Duh. I cleared everything. Why am I getting an error."
 *   "Stop that shit. You keep adding a feature there. None of those orbits
 *    should be selected when you come to the site. Even All shouldn't be
 *    selected… why is this so hard?"
 *   "But you'll have to make sure that constellation updates the
 *    owner/organization, constellation/fleet, and mission boxes correctly.
 *    I think they're the problem. They need to auto update with changes."
 *
 * And the model he then specified: "All/LEO/MEO/GEO/HEO are just buttons to
 * show all satellites in that category… That is like a controller - it is like
 * a top level… If I clear all, LEO still stays selected because when I go
 * select things, I only want things to show that are LEO."
 *
 * So this is a SEQUENCE, not a screenshot. Drift is the failure mode, and
 * drift only shows itself across transitions — a single load state agreed with
 * itself for months while the second click pulled it apart.
 */
test("the orbit band scopes, the facets follow it, and clearing never touches it", async ({ page }, testInfo) => {
  testInfo.setTimeout(300_000);
  await page.addInitScript(() => localStorage.setItem("space-explorer-hide-welcome-v1", "1"));
  await page.goto("./");
  const startupTimeout = testInfo.project.name === "mobile" ? 120_000 : 90_000;
  await expect(page.locator("#visible-count")).toContainText("Selected", { timeout: startupTimeout });
  if (testInfo.project.name === "mobile") await phoneOpenRail(page);

  const shown = async () => Number((await page.locator("#visible-count").textContent() ?? "").replace(/[^0-9]/g, ""));
  const checked = (facet: string) => page.locator(`[data-${facet}]:checked`).count();
  /** Only the rows the live band actually offers. An option the reader cannot
   *  see must not be counted as one they have. */
  const offered = (facet: string) => page.locator(`[data-${facet}]`).evaluateAll(
    (nodes) => nodes.filter((node) => node.closest("label")?.dataset.scope !== "out").length,
  );
  const litBands = () => page.locator("[data-orbit].is-active").count();
  /** Every affordance this rail is not allowed to grow back. */
  const rescueAffordances = async () => page.locator("#control-rail button").evaluateAll(
    (nodes) => nodes
      .filter((node) => !(node as HTMLElement).hidden && (node as HTMLElement).offsetParent !== null)
      .map((node) => (node.textContent ?? "").trim())
      .filter((text) => /show (every|all)|again|restore|reset|bring back/i.test(text)),
  );

  // ---- 1. LOAD ---------------------------------------------------------
  // GPS drawn, no band lit, and all three boxes describing GPS rather than
  // describing the catalog.
  expect(await shown()).toBeGreaterThan(0);
  // Asked of the rotation, not written down. On a phone the sheet has already
  // been opened by the time this runs, and opening it is a click outside the
  // popup, which takes the popup down — so this reads the text rather than the
  // visibility. What is drawn is the assertion; where the note is showing is
  // `featured-toast.spec.ts`'s business.
  await expect(page.locator("#featured-toast-text"))
    .toContainText(await featuredToday(page), { timeout: 90_000 });
  expect(await litBands()).toBe(0);
  await expect(page.locator("#constellation-facet-state")).not.toHaveText("all");
  expect(await checked("constellation")).toBe(1);
  // ASKED OF THE ROTATION, NOT WRITTEN DOWN. These three lines named GPS,
  // Navigation and the U.S. Space Force until 2026-08-27, when the rotation
  // reached Starlink and they failed on a page that was working perfectly —
  // the same expiry this file's own header warns about two hundred lines up.
  // What is actually being asserted is that the featured fleet arrives as a
  // facet selection and that healing has filled the other two boxes to match
  // it, and that holds for whichever fleet today is.
  const featuredFleet = await featuredToday(page);
  await expect(page.locator(`[data-constellation="${featuredFleet}"]`)).toBeChecked();
  expect(await checked("mission-facet")).toBeGreaterThan(0);
  expect(await checked("owner")).toBeGreaterThan(0);
  // Nothing is being explained and nothing is offering a way out of a state
  // the reader chose by arriving.
  await expect(page.locator("#filter-status")).toBeHidden();
  expect(await rescueAffordances()).toEqual([]);

  // ---- 2. THE BAND SCOPES ----------------------------------------------
  await page.locator('[data-orbit="LEO"]').click();
  expect(await litBands()).toBe(1);
  await expect(page.locator('[data-orbit="LEO"]')).toHaveClass(/is-active/);
  const leoShown = await shown();
  expect(leoShown).toBeGreaterThan(0);
  // The facets re-derived from the band: GPS is MEO-only, so it is no longer
  // on offer at all, and the owner and mission lists shrank with it.
  const leoConstellations = await offered("constellation");
  const leoOwners = await offered("owner");
  expect(await page.locator('[data-constellation="GPS"]').evaluate(
    (node) => node.closest("label")?.dataset.scope,
  )).toBe("out");
  await expect(page.locator('[data-constellation="GPS"]')).not.toBeChecked();
  // …and "all" on a chip means all of LEO, not all of the catalog.
  await expect(page.locator("#constellation-facet-state")).toHaveText("all");
  expect(await checked("constellation")).toBe(leoConstellations);

  // ---- 3. A PEER FACET NARROWS, THE OTHERS STILL DESCRIBE THE BAND ------
  await page.locator("#owner-section").locator("summary").click();
  await clearOwnerList(page);
  await page.locator('[data-owner="SpaceX"]').check();
  expect(await shown()).toBeGreaterThan(0);
  expect(await shown()).toBeLessThan(leoShown);
  // No hierarchy: narrowing the owner box did not shrink what the other two
  // boxes offer, because they are peers scoped by the band and by nothing else.
  expect(await offered("constellation")).toBe(leoConstellations);
  expect(await offered("owner")).toBe(leoOwners);
  expect(await litBands()).toBe(1);

  // ---- 4. CLEAR LEAVES THE BAND — AND THE OTHER TWO BOXES — STANDING ---
  // The assertion Sean described in words: "If I clear all, LEO still stays
  // selected because when I go select things, I only want things to show that
  // are LEO."
  //
  // CHANGED 2026-08-27. This used to also assert that clearing the OWNER box
  // emptied the mission and constellation boxes with it. That cascade is the
  // defect Sean reported next: he pressed Clear all in one box twice, meaning
  // "empty this box so I can pick one value out of it", and got a blank screen
  // and three empty boxes both times. The button empties its own list now, and
  // the globe still goes to zero because the facets AND together — which is
  // what makes the next tick an intersection rather than a fresh start.
  const missionTicksBefore = await checked("mission");
  const fleetTicksBefore = await checked("constellation");
  await clearOwnerList(page);
  expect(await shown()).toBe(0);
  expect(await checked("owner")).toBe(0);
  expect(await checked("mission")).toBe(missionTicksBefore);
  expect(await checked("constellation")).toBe(fleetTicksBefore);
  await expect(page.locator('[data-orbit="LEO"]')).toHaveClass(/is-active/);
  expect(await litBands()).toBe(1);
  // Silence. No error, no warning, no offer to put it back.
  await expect(page.locator("#filter-status")).toBeHidden();
  await expect(page.locator("#featured-toast")).toBeHidden();
  expect(await rescueAffordances()).toEqual([]);
  // And the band still means something: picking back up inside it stays in it.
  await page.locator('[data-owner="SpaceX"]').check();
  expect(await shown()).toBeGreaterThan(0);
  await expect(page.locator('[data-orbit="LEO"]')).toHaveClass(/is-active/);

  // ---- 5. ALL IS EVERY BAND --------------------------------------------
  await page.locator('[data-orbit="all"]').click();
  await expect(page.locator('[data-orbit="all"]')).toHaveClass(/is-active/);
  expect(await offered("constellation")).toBeGreaterThan(leoConstellations);
  expect(await offered("owner")).toBeGreaterThan(leoOwners);
  await expect(page.locator('[data-constellation="GPS"]')).toBeChecked();

  // ---- 6. UNSET IS NOT ALL ---------------------------------------------
  // Two states, kept two states. Clicking the live band again puts the scope
  // back to "no band chosen", which is what the site opens on and is the only
  // state in which no button is lit.
  await page.locator('[data-orbit="all"]').click();
  expect(await litBands()).toBe(0);
  await expect(page.locator('[data-orbit="all"]')).not.toHaveClass(/is-active/);
  expect(await offered("constellation")).toBeGreaterThan(leoConstellations);
  expect(await rescueAffordances()).toEqual([]);
});
