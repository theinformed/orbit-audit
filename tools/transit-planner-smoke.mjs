/**
 * Drives tools/transit-planner-smoke.html in a real browser: mounts the planner,
 * runs a real solve, and exercises the waypoint dimming interaction.
 *
 * Usage:
 *   npx vite --host 127.0.0.1 --port 5178 &
 *   node tools/transit-planner-smoke.mjs
 */

import { chromium } from "@playwright/test";

const baseUrl = process.env.SMOKE_URL ?? "http://127.0.0.1:5178";
const audience = process.argv[2] === "gated" ? "gated" : "public";
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1500, height: 1000 } });

page.on("console", (message) => {
  if (message.type() === "error") console.error("[page]", message.text());
});
page.on("pageerror", (error) => console.error("[pageerror]", error.message));

await page.goto(`${baseUrl}/tools/transit-planner-smoke.html?audience=${audience}`, { waitUntil: "load" });
await page.waitForFunction(() => window.transitPlannerSmoke?.ready === true, null, { timeout: 240_000 });
const outcome = await page.evaluate(() => window.transitPlannerSmoke);
await page.screenshot({ path: `test-results/transit-planner-smoke-${audience}.png`, fullPage: true });
await browser.close();

if (outcome.error) {
  console.error("Planner threw on mount:\n" + outcome.error);
  process.exit(2);
}

for (const [name, value] of Object.entries(outcome.checks)) {
  console.log(`${name.padEnd(30)} ${value}`);
}

const mustBeTrue = [
  "disclosureRendered", "maskSliderPresent", "maskDefaultIsNotZero", "mapRendered",
  "aorReferenceRendered", "noBoundaryPolygonsBeforeToggle", "solveCompleted",
  "focusNoteShown", "rowsSurvivedDimming", "boundaryCitationShown",
  "indefiniteEdgeMarked", "elementAgeBannerShown",
  // 2026-08-19, the five faults.
  "disclosureIsFolded", "lessonIsFolded", "referenceIsFolded",
  "mapZoomChangesTheView", "zoomReadoutChanged", "zoomResets",
  "defaultPresetActive", "defaultRouteIsOverWater", "boundaryChipsNotHiddenInAFold",
  // Presentation differences: each must be true in exactly one build.
  ...(audience === "public"
    ? ["lessonShown", "gatedLinkShown"]
    : ["gatedDisclosureShown", "exportButtonPresent"]),
];
// And false in the other, or the two presentations have leaked into each other.
const mustBeFalse = audience === "public"
  ? ["gatedDisclosureShown", "exportButtonPresent"]
  : ["lessonShown", "gatedLinkShown"];
const failures = mustBeTrue.filter((name) => outcome.checks[name] !== true);
const emptyCounts = ["waypointCount", "needChips", "landDrawn", "routeDrawn", "coverageRows",
  "citationsShown", "boundaryButtonsPresent", "boundaryPolygonsAfterToggle", "elementAgeChips",
  "zoomControlsPresent", "presetChips", "definitionPopovers"]
  .filter((name) => !(Number(outcome.checks[name]) > 0));
const wronglyTrue = mustBeFalse.filter((name) => outcome.checks[name] === true);
if (wronglyTrue.length) {
  console.error(`\nFAILED: ${audience} build shows ${wronglyTrue.join(", ")} — presentations have leaked`);
  process.exit(1);
}

if (failures.length || emptyCounts.length) {
  console.error(`\nFAILED: ${[...failures, ...emptyCounts].join(", ")}`);
  process.exit(1);
}
/*
 * The text budget. The page opened with 1,394 words at rest on 2026-08-19 and
 * now opens with about a quarter of that; every word that went is inside a fold
 * on the same page. 500 is a ceiling with room to add a control caption, not a
 * target to creep toward.
 */
const RESTING_WORD_BUDGET = 500;
if (Number(outcome.checks.restingWords) > RESTING_WORD_BUDGET) {
  console.error(`\nFAILED: ${outcome.checks.restingWords} words at rest, over the ${RESTING_WORD_BUDGET} budget. `
    + "Fold it or move it to a Learn page; do not delete a source or a caveat to pass this.");
  process.exit(1);
}

if (!(Number(outcome.checks.dimmedAfterWaypointClick) > 0)) {
  console.error("\nFAILED: clicking a waypoint dimmed nothing — the interaction is not working");
  process.exit(1);
}
console.log("\nPlanner mounts, solves, and dims correctly.");
