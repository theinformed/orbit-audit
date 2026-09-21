/**
 * Measures a realistic transit solve against the real published catalog, using
 * the exact production solver (`src/transit-solve.ts`) that the worker calls.
 *
 * Run: npx tsx tools/transit-benchmark.ts   (or: npx vitest run tests/transit-solve.test.ts
 * for the assertion-bearing version). This file exists so the numbers in the
 * handoff can be regenerated rather than remembered.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { estimateEvaluations, solveSatelliteVisibility, type SolveSatelliteInput } from "../src/transit-solve";
import { buildLegs, type TransitRoute } from "../src/transit-route";
import { summarizeCoverage } from "../src/transit-visibility";
import type { CatalogBundle } from "../src/types";

const root = join(import.meta.dirname, "..");
const manifest = JSON.parse(readFileSync(join(root, "public/data/manifest.json"), "utf8"));
const catalog: CatalogBundle = JSON.parse(
  readFileSync(join(root, "public/data", manifest.catalog.path), "utf8"),
);

/** Pearl Harbor to Yokosuka: a real 7th Fleet transit, seven days at 18 knots. */
const route: TransitRoute = {
  trackModel: "great-circle",
  waypoints: [
    { id: "1", label: "Pearl Harbor", latitudeDeg: 21.35, longitudeDeg: -157.95, timeMs: Date.parse("2026-08-10T18:00:00Z") },
    { id: "2", label: "Midway", latitudeDeg: 28.2, longitudeDeg: -177.35, timeMs: Date.parse("2026-08-13T06:00:00Z") },
    { id: "3", label: "Yokosuka", latitudeDeg: 35.28, longitudeDeg: 139.67, timeMs: Date.parse("2026-08-17T18:00:00Z") },
  ],
};

const SATCOM_CONSTELLATIONS = new Set([
  "WGS", "AEHF", "MUOS", "UHF Follow-On (UFO)", "Inmarsat", "Iridium",
  "Intelsat", "SES", "O3b / mPOWER", "Eutelsat", "Globalstar",
  "Arctic Satellite Broadband Mission",
]);

function scenario(name: string, filter: (record: CatalogBundle["satellites"][number]) => boolean) {
  const satellites: SolveSatelliteInput[] = catalog.satellites
    .filter(filter)
    .map((record) => ({ id: record.id, periodMinutes: record.periodMinutes, omm: record.omm }));
  const durationSeconds = (route.waypoints.at(-1)!.timeMs - route.waypoints[0]!.timeMs) / 1000;
  const estimated = estimateEvaluations(satellites, durationSeconds);

  const startedAt = performance.now();
  let evaluations = 0;
  let windows = 0;
  const perSatellite = satellites.map((satellite) => {
    const result = solveSatelliteVisibility(satellite, route, {
      maskDeg: 5,
      observerAltitudeKm: 0.02,
      edgeToleranceSeconds: 2,
    });
    evaluations += result.evaluations;
    windows += result.windows.length;
    return result;
  });
  const elapsedMs = performance.now() - startedAt;

  const startMs = route.waypoints[0]!.timeMs;
  const endMs = route.waypoints.at(-1)!.timeMs;
  const allWindows = perSatellite.flatMap((result) => result.windows);
  const summary = summarizeCoverage(allWindows, startMs, endMs, 1000);

  console.log(`\n=== ${name} ===`);
  console.log(`satellites            ${satellites.length}`);
  console.log(`estimated evaluations ${estimated.toLocaleString()}`);
  console.log(`actual evaluations    ${evaluations.toLocaleString()}`);
  console.log(`elapsed               ${elapsedMs.toFixed(0)} ms`);
  console.log(`rate                  ${Math.round(evaluations / (elapsedMs / 1000)).toLocaleString()} evaluations/s`);
  console.log(`windows found         ${windows.toLocaleString()}`);
  console.log(`union coverage        ${(summary.coveredFraction * 100).toFixed(3)} %  continuous=${summary.continuous}`);
  return { satellites: satellites.length, evaluations, elapsedMs, windows };
}

console.log("Route:");
for (const leg of buildLegs(route)) {
  console.log(
    `  leg ${leg.index + 1}: ${leg.from.label} -> ${leg.to.label}  `
    + `${Math.round(leg.greatCircleKm).toLocaleString()} km  `
    + `${(leg.durationMs / 3_600_000).toFixed(1)} h  `
    + `${leg.speedKnots.toFixed(1)} kn  course ${leg.initialCourseDeg.toFixed(0)}`,
  );
}
const totalHours = (route.waypoints.at(-1)!.timeMs - route.waypoints[0]!.timeMs) / 3_600_000;
console.log(`  total: ${totalHours.toFixed(1)} h`);

scenario("Named SATCOM constellations (the planner's default set)", (record) =>
  record.constellation !== null && SATCOM_CONSTELLATIONS.has(record.constellation));
scenario("Military SATCOM only (WGS + AEHF + MUOS + UFO)", (record) =>
  record.constellation !== null && ["WGS", "AEHF", "MUOS", "UHF Follow-On (UFO)"].includes(record.constellation));
scenario("Every geostationary communications satellite in the catalog", (record) =>
  record.mission === "communications" && record.orbit === "GEO");
scenario("OneWeb, a low-orbit constellation at full size", (record) => record.constellation === "OneWeb");
