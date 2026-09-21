/**
 * Smoke test harness: mounts the real planner, solves a real route, exercises
 * the waypoint dimming interaction, and reports what it found.
 *
 * Drive it with tools/transit-planner-smoke.mjs.
 */

import { TransitPlanner } from "../src/transit-planner";
import type { CatalogBundle, ReleaseManifest } from "../src/types";
import type { LandGeoJson } from "../src/globe";

declare global {
  interface Window {
    transitPlannerSmoke?: {
      ready: boolean;
      error?: string;
      checks: Record<string, boolean | number | string>;
    };
  }
}

async function main() {
  const manifest: ReleaseManifest = await (await fetch("/public/data/manifest.json")).json();
  const [catalog, land] = await Promise.all([
    fetch(`/public/data/${manifest.catalog.path}`).then((response) => response.json()) as Promise<CatalogBundle>,
    fetch(`/public/data/${manifest.land.path}`).then((response) => response.json()) as Promise<LandGeoJson>,
  ]);

  const audience = new URLSearchParams(location.search).get("audience") === "gated" ? "gated" : "public";
  const host = document.getElementById("host")!;
  const planner = new TransitPlanner({ container: host, catalog, land, audience });
  void planner;

  const checks: Record<string, boolean | number | string> = {};
  const query = (selector: string) => host.querySelector(selector);

  /*
   * TEXT AT REST, measured first, before anything is clicked or unfolded.
   *
   * Sean, 2026-08-19: "it has WAY too much text. Fucking ridiculous." The page
   * opened with 1,394 words above and around the tool. Prose is a cost, and the
   * only version of that rule a test can hold is a budget on what a reader is
   * shown before they ask for more. Every one of those words still exists —
   * inside the disclosure fold, the lesson fold and the reference fold — so
   * this number going up means something was un-folded, not that something was
   * written.
   */
  const restingText = (host as HTMLElement).innerText ?? "";
  checks.restingWords = restingText.trim().split(/\s+/).filter(Boolean).length;
  checks.disclosureIsFolded = query(".transit-disclosure")?.tagName === "DETAILS";
  checks.lessonIsFolded = !query(".transit-lesson") || query(".transit-lesson")?.tagName === "DETAILS";
  checks.referenceIsFolded = query(".transit-reference-fold")?.tagName === "DETAILS";
  checks.definitionPopovers = host.querySelectorAll(".transit-term-card").length;

  /*
   * ZOOM. "The map isn't zoomable. Why?" — it had no affordance at all.
   */
  checks.zoomControlsPresent = host.querySelectorAll("[data-map-zoom]").length;
  const worldGroup = host.querySelector('[data-layer="world"]');
  const transformAtRest = worldGroup?.getAttribute("transform") ?? "";
  host.querySelector<HTMLButtonElement>('[data-map-zoom="in"]')?.click();
  const transformZoomed = worldGroup?.getAttribute("transform") ?? "";
  checks.mapZoomChangesTheView = transformAtRest !== transformZoomed && transformZoomed.includes("scale");
  checks.zoomReadoutChanged = (host.querySelector("[data-map-scale]")?.textContent ?? "") !== "1.0\u00d7";
  host.querySelector<HTMLButtonElement>('[data-map-zoom="reset"]')?.click();
  checks.zoomResets = (worldGroup?.getAttribute("transform") ?? "") === transformAtRest;

  /*
   * ROUTE PRESETS, and the land check on the shipped default.
   */
  checks.presetChips = host.querySelectorAll("[data-route-preset]").length;
  checks.defaultPresetActive = Boolean(host.querySelector("[data-route-preset].is-active"));
  checks.defaultRouteIsOverWater = !host.querySelector(".transit-land-warning");

  /*
   * The AOR overlay has to be FINDABLE. It used to be five chips inside a shut
   * <details>, which is why Sean asked for overlays that were already built.
   */
  const picker = host.querySelector(".transit-boundary-picker");
  checks.boundaryChipsNotHiddenInAFold = Boolean(picker) && !picker!.closest("details");

  checks.disclosureRendered = Boolean(query(".transit-disclosure"));
  checks.maskSliderPresent = Boolean(query("[data-mask-slider]"));
  checks.maskDefaultIsNotZero = (query("[data-mask-slider]") as HTMLInputElement | null)?.value !== "0";
  checks.waypointCount = host.querySelectorAll("[data-waypoint]").length;
  checks.needChips = host.querySelectorAll("[data-need]").length;
  checks.mapRendered = Boolean(query(".transit-map-svg"));
  checks.landDrawn = host.querySelectorAll('[data-layer="static"] path').length;
  checks.routeDrawn = host.querySelectorAll('[data-layer="route"] path').length;
  checks.aorReferenceRendered = Boolean(query(".transit-reasons"));
  checks.audience = audience;
  checks.lessonShown = Boolean(query(".transit-lesson"));
  checks.gatedLinkShown = Boolean(query(".transit-gated-link"));
  checks.gatedDisclosureShown = Boolean(query(".transit-disclosure-gated"));
  checks.noBoundaryPolygonsBeforeToggle = host.querySelectorAll('[data-layer="boundaries"] path').length === 0;

  // Turn on a published boundary and confirm it draws with its citation.
  const boundaryButton = host.querySelector<HTMLButtonElement>('[data-boundary="c7f"]');
  boundaryButton?.click();
  host.querySelector<HTMLButtonElement>('[data-boundary="usafricom"]')?.click();
  host.querySelector<HTMLButtonElement>('[data-boundary="useucom"]')?.click();
  checks.selfPublishedGeometryNoted = Boolean(host.querySelector(".transit-boundary-geometry"));
  checks.boundaryButtonsPresent = host.querySelectorAll("[data-boundary]").length;
  checks.boundaryPolygonsAfterToggle = host.querySelectorAll('[data-layer="boundaries"] path').length;
  checks.boundaryCitationShown = Boolean(host.querySelector(".transit-boundary-cite blockquote"));
  checks.indefiniteEdgeMarked = Boolean(host.querySelector(".transit-boundary-cite em"));

  // Narrow to a small need so the solve is quick, then run it.
  const ehfChip = [...host.querySelectorAll<HTMLButtonElement>("[data-need]")]
    .find((button) => button.dataset.need === "ehf-protected");
  ehfChip?.click();
  (host.querySelector("[data-run-solve]") as HTMLButtonElement | null)?.click();

  const solved = await new Promise<boolean>((resolve) => {
    const deadline = Date.now() + 120_000;
    const poll = () => {
      const status = host.querySelector("[data-solve-status]")?.textContent ?? "";
      if (/Solved \d+ satellites/.test(status)) return resolve(true);
      if (Date.now() > deadline) return resolve(false);
      setTimeout(poll, 250);
    };
    poll();
  });
  checks.solveCompleted = solved;
  checks.solveStatus = host.querySelector("[data-solve-status]")?.textContent?.trim() ?? "";
  checks.coverageRows = host.querySelectorAll(".transit-coverage-row").length;
  checks.citationsShown = host.querySelectorAll(".transit-citations li").length;

  // The interaction Sean asked for: click a waypoint, and rows with nothing
  // overhead there must dim while the rest stay in normal weight.
  const beforeDimmed = host.querySelectorAll(".transit-coverage-row.is-dimmed").length;
  (host.querySelector("[data-waypoint]") as HTMLElement | null)?.click();
  const afterRows = host.querySelectorAll(".transit-coverage-row").length;
  const afterDimmed = host.querySelectorAll(".transit-coverage-row.is-dimmed").length;
  checks.dimmedBeforeWaypointClick = beforeDimmed;
  checks.rowsAfterWaypointClick = afterRows;
  checks.dimmedAfterWaypointClick = afterDimmed;
  checks.focusNoteShown = Boolean(host.querySelector(".transit-focus-note"));
  checks.elementAgeBannerShown = Boolean(host.querySelector(".transit-age-banner"));
  checks.elementAgeChips = host.querySelectorAll(".transit-age-chip").length;
  checks.exportButtonPresent = Boolean(host.querySelector("[data-export-csv]"));
  // Dimming must not remove rows: the count has to survive the click.
  checks.rowsSurvivedDimming = afterRows === Number(checks.coverageRows);

  window.transitPlannerSmoke = { ready: true, checks };
  console.table(checks);
}

main().catch((error) => {
  window.transitPlannerSmoke = { ready: true, error: `${error}\n${(error as Error)?.stack ?? ""}`, checks: {} };
  console.error(error);
});
