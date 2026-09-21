import type { Page } from "@playwright/test";

/**
 * Putting a phone screen into a known state.
 *
 * A phone shows this site through three collapsible surfaces, and each one is
 * closed or folded by default ON PURPOSE, so that the globe — the point of the
 * whole site — keeps a real share of a 390 px screen:
 *
 *   - the **rail** is a bottom sheet, `translateY(100%)` until `.is-open`;
 *   - the **Data Explorer** opens collapsed to its one-line head;
 *   - the **legend** opens folded to its title bar.
 *
 * They also interact. Opening the rail collapses the Explorer and vice versa
 * ("one sheet at a time", added after measurement showed the two together
 * covered the entire viewport). And the rail, when open, sits over the legend
 * at the foot of the screen.
 *
 * So a mobile test cannot open a surface once and assume it stays: it has to
 * re-assert the state it needs immediately before it needs it. That is what
 * these do. Every one is a no-op on desktop and tablet, where the mobile toggle
 * is not rendered at all, so they are safe to call unconditionally.
 *
 * (Some older tests carry their own local `openRail`; those work and are left
 * alone. New sites should use these.)
 */

const onPhone = (page: Page) => page.locator("#mobile-panel-toggle").isVisible();

/** The layer sheet up, so its presets, mode switch and layer toggles are reachable. */
export async function openRail(page: Page): Promise<void> {
  if (!await onPhone(page)) return;
  const open = await page.locator("#control-rail").evaluate((rail) => rail.classList.contains("is-open"));
  if (!open) await page.locator("#mobile-panel-toggle").click();
}

/** The layer sheet away, so what is underneath it can be reached. */
export async function closeRail(page: Page): Promise<void> {
  if (!await onPhone(page)) return;
  const open = await page.locator("#control-rail").evaluate((rail) => rail.classList.contains("is-open"));
  if (open) await page.locator("#mobile-panel-toggle").click();
}

/**
 * The legend readable: sheet out of the way first, because an open rail covers
 * the foot of the screen where the legend lives, and then unfolded.
 */
export async function showLegend(page: Page): Promise<void> {
  await closeRail(page);
  if (await page.locator("#map-key").evaluate((element) => element.classList.contains("is-collapsed"))) {
    await page.locator("#map-key-toggle").click();
  }
}

/** The Data Explorer expanded: sheet away, then unfolded from its head. */
export async function showViewer(page: Page): Promise<void> {
  await closeRail(page);
  if (await page.locator("#data-viewer").evaluate((el) => el.classList.contains("is-collapsed"))) {
    await page.locator("#data-viewer-head").click();
  }
}
