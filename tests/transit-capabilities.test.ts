/**
 * The capability table, and the end-to-end solve, against the real published
 * catalog.
 *
 * This project has shipped green tests over code that never ran. The defence
 * used here is that every test below drives the same functions the browser
 * drives - `solveSatelliteVisibility` is what the worker calls, `resolveSystems`
 * and `summarizeSystemCoverage` are what the panel calls - with the real
 * `data/satcom_capabilities.json` and the real published catalog artifact, not
 * fixtures shaped to agree with them.
 */

import { describe, expect, it } from "vitest";
import capabilityData from "../data/satcom_capabilities.json";
import {
  matchesSystem,
  resolveSystems,
  satellitesOverheadAt,
  summarizeSystemCoverage,
  systemsForNeed,
  systemsOverheadAt,
  validateDataset,
  type SatcomCapabilityDataset,
} from "../src/satcom-capabilities";
import { solveSatelliteVisibility, estimateEvaluations, visibleAtInstant } from "../src/transit-solve";
import { loadCatalog } from "./transit-fixtures";
import type { CatalogBundle, SatelliteRecord } from "../src/types";
import type { TransitRoute } from "../src/transit-route";
import type { Interval } from "../src/transit-visibility";

const dataset = capabilityData as unknown as SatcomCapabilityDataset;

const catalog: CatalogBundle = await loadCatalog();

/** Pearl Harbor to Yokosuka via Midway. Fixed times so the test is repeatable. */
const route: TransitRoute = {
  trackModel: "great-circle",
  waypoints: [
    { id: "1", label: "Pearl Harbor", latitudeDeg: 21.35, longitudeDeg: -157.95, timeMs: Date.parse("2026-08-10T18:00:00Z") },
    { id: "2", label: "Midway", latitudeDeg: 28.2, longitudeDeg: -177.35, timeMs: Date.parse("2026-08-13T06:00:00Z") },
    { id: "3", label: "Yokosuka", latitudeDeg: 35.28, longitudeDeg: 139.67, timeMs: Date.parse("2026-08-17T18:00:00Z") },
  ],
};
const startMs = route.waypoints[0]!.timeMs;
const endMs = route.waypoints.at(-1)!.timeMs;

describe("the capability dataset", () => {
  it("is internally consistent", () => {
    expect(validateDataset(dataset)).toEqual([]);
  });

  it("gives every service a real citation, never a bare assertion", () => {
    for (const system of dataset.systems) {
      for (const service of system.services) {
        expect(service.source, `${system.systemId}/${service.needId}`).toMatch(/^https?:\/\//);
        // Plain http is permitted only where the host is gone and an archived
        // capture stands in for it — see validateDataset for why.
        if (service.source.startsWith("http://")) {
          expect(service.archiveSource, `${system.systemId}/${service.needId}`).toBeTruthy();
        }
        expect(service.sourceName.length).toBeGreaterThan(3);
        expect(["us-government", "allied-government", "operator", "prime-contractor"])
          .toContain(service.sourceKind);
      }
    }
  });

  it("records what is missing instead of quietly omitting it", () => {
    // The gap list is the honest half of this table. If it is ever empty while
    // the systems list is short, somebody has deleted the evidence of a gap.
    expect(dataset.unsourced.length).toBeGreaterThan(0);
    for (const entry of dataset.unsourced) {
      expect(entry.reason.length).toBeGreaterThan(60);
    }
  });

  it("does not claim a band for a system whose source never named one", () => {
    // O3b mPOWER is the row where the operator describes the orbit but never
    // writes "O3b mPOWER" and "Ka-band" in one sentence, and CBSP is a
    // procurement programme rather than a band. Neither may carry a band need,
    // and both must say why in the caveat.
    const bandNeeds = new Set([
      "uhf-satcom", "l-band-mobile", "shf-satcom", "ku-band", "ka-wideband", "ehf-protected",
    ]);
    for (const systemId of ["o3b-mpower", "cbsp"]) {
      const system = dataset.systems.find((candidate) => candidate.systemId === systemId)!;
      expect(system, systemId).toBeDefined();
      expect(system.caveat, systemId).not.toBeNull();
      for (const service of system.services) {
        expect(bandNeeds.has(service.needId), `${systemId} claims band need ${service.needId}`).toBe(false);
      }
    }
  });

  it("flags a citation whose current official page no longer carries the fact", () => {
    // Research found band and host detail present in older official captures and
    // removed from today's equivalents. Where that is why an older capture is
    // cited, the row has to say so - otherwise the citation quietly implies the
    // owner still stands behind it.
    const superseded = dataset.systems.filter((system) => system.supersededNote);
    expect(superseded.length).toBeGreaterThan(0);
    for (const system of superseded) {
      expect(system.supersededNote!.length).toBeGreaterThan(60);
      // A superseded citation must carry an archive link, or it cannot be checked.
      expect(system.services.some((service) => service.archiveSource), system.systemId).toBe(true);
    }
    expect(superseded.map((system) => system.systemId)).toContain("gbs");
  });

  it("keeps an archived capture wherever a live government page refuses to be read", () => {
    // Every .mil or .gov citation here was taken from an Internet Archive
    // capture, because those hosts refuse automated requests. Without the
    // capture recorded, the quotation is unverifiable by the next reader.
    for (const system of dataset.systems) {
      for (const service of system.services) {
        const isBlockedGovHost = /^https?:\/\/[^/]*\.(mil|gao\.gov|doncio\.navy\.mil)/.test(service.source)
          || /af\.mil|spaceforce\.mil|afspc|peoc3t/.test(service.source);
        if (isBlockedGovHost) {
          expect(service.archiveSource, `${system.systemId}/${service.needId} has no archived capture`)
            .toBeTruthy();
        }
      }
    }
  });
});

describe("matching systems to the real published catalog", () => {
  const resolved = resolveSystems(dataset, catalog.satellites);

  it("resolves the named military constellations to real spacecraft", () => {
    const counts = new Map(resolved.map((entry) => [entry.system.systemId, entry.satellites.length]));
    expect(counts.get("muos")).toBe(5);
    expect(counts.get("wgs")).toBe(10);
    expect(counts.get("aehf")).toBe(6);
    expect(counts.get("asbm")).toBe(2);
  });

  it("resolves GBS through the hosted-payload record rather than a second copy of it", () => {
    // The satellites GBS uses are never listed in satcom_capabilities.json. They
    // come from data/programme_participation.json by way of the catalog's own
    // `programmes[]` field, which is what keeps the two datasets from diverging.
    const gbs = resolved.find((entry) => entry.system.systemId === "gbs")!;
    expect(gbs.system.match).toEqual({ kind: "programme", programmeId: "gbs" });
    expect(gbs.satellites.length).toBeGreaterThan(0);
    for (const satellite of gbs.satellites) {
      expect((satellite.programmes ?? []).some((p) => p.programmeId === "gbs")).toBe(true);
    }
    // It should reach across two different programmes' spacecraft, which is the
    // whole point of a hosted payload.
    const constellations = new Set(gbs.satellites.map((satellite) => satellite.constellation));
    expect(constellations.size).toBeGreaterThan(1);
  });

  it("resolves CBSP to no spacecraft, on purpose", () => {
    const cbsp = resolved.find((entry) => entry.system.systemId === "cbsp")!;
    expect(cbsp.satellites).toHaveLength(0);
    expect(cbsp.system.caveat).toMatch(/no spacecraft/i);
  });

  it("matches only on fields the upstream catalog already carries", () => {
    // No name patterns, no orbit tests, no inference. Every match kind here must
    // be one of the three that read a source-backed field.
    for (const system of dataset.systems) {
      expect(["constellation", "programme", "norad"]).toContain(system.match.kind);
    }
  });

  it("never matches a satellite to a system by anything about a different satellite", () => {
    // A structural check for docs/mission-speculation-design.md section 1.6: a
    // match must depend only on the record being tested. Shuffling the rest of
    // the catalog cannot change any individual verdict.
    const sample = catalog.satellites.slice(0, 400);
    const shuffled = [...sample].reverse();
    for (const system of dataset.systems) {
      const a = sample.filter((record) => matchesSystem(record, system.match)).map((record) => record.id).sort();
      const b = shuffled.filter((record) => matchesSystem(record, system.match)).map((record) => record.id).sort();
      expect(b).toEqual(a);
    }
  });

  it("filters by need without losing systems that serve more than one", () => {
    const wideband = systemsForNeed(resolved, "shf-satcom").map((entry) => entry.system.systemId);
    const ka = systemsForNeed(resolved, "ka-wideband").map((entry) => entry.system.systemId);
    expect(wideband).toContain("wgs");
    expect(ka).toContain("wgs");
    expect(systemsForNeed(resolved, "ehf-protected").map((entry) => entry.system.systemId)).toContain("aehf");
    expect(systemsForNeed(resolved, "uhf-satcom").map((entry) => entry.system.systemId)).toContain("muos");
    expect(systemsForNeed(resolved, "no-such-need")).toHaveLength(0);
  });
});

describe("coverage semantics", () => {
  const resolved = resolveSystems(dataset, catalog.satellites);

  it("takes the union across a constellation, not the intersection", () => {
    // Two satellites of one system, each covering half the transit with no
    // overlap, cover the whole transit between them. An intersection would say
    // zero, and that is the mistake this function exists to not make.
    const wgs = resolved.find((entry) => entry.system.systemId === "wgs")!;
    const [first, second] = wgs.satellites;
    const windows = new Map<number, Interval[]>([
      [first!.id, [{ startMs, endMs: startMs + (endMs - startMs) / 2 }]],
      [second!.id, [{ startMs: startMs + (endMs - startMs) / 2, endMs }]],
    ]);
    const coverage = summarizeSystemCoverage([wgs], windows, startMs, endMs, 1000);
    expect(coverage[0]!.verdict).toBe("entire-transit");
    expect(coverage[0]!.summary.coveredFraction).toBeCloseTo(1, 9);
    expect(coverage[0]!.solvedSatelliteIds).toHaveLength(2);
    expect(coverage[0]!.unsolvedSatelliteIds.length).toBe(wgs.satellites.length - 2);
  });

  it("calls a real hole partial, and reports its length", () => {
    const wgs = resolved.find((entry) => entry.system.systemId === "wgs")!;
    const quarter = (endMs - startMs) / 4;
    const windows = new Map<number, Interval[]>([
      [wgs.satellites[0]!.id, [
        { startMs, endMs: startMs + quarter },
        { startMs: startMs + 3 * quarter, endMs },
      ]],
    ]);
    const coverage = summarizeSystemCoverage([wgs], windows, startMs, endMs, 1000);
    expect(coverage[0]!.verdict).toBe("partial");
    expect(coverage[0]!.summary.coveredFraction).toBeCloseTo(0.5, 6);
    expect(coverage[0]!.summary.longestGapMs).toBeCloseTo(2 * quarter, -3);
  });

  it("reports not-computed rather than none when nothing was solved", () => {
    const cbsp = resolved.find((entry) => entry.system.systemId === "cbsp")!;
    const coverage = summarizeSystemCoverage([cbsp], new Map(), startMs, endMs);
    expect(coverage[0]!.verdict).toBe("not-computed");
    expect(coverage[0]!.summary.coveredFraction).toBe(0);
  });

  it("distinguishes a system that was solved and never seen from one that was not solved", () => {
    const aehf = resolved.find((entry) => entry.system.systemId === "aehf")!;
    const solvedButBlind = new Map<number, Interval[]>(
      aehf.satellites.map((satellite) => [satellite.id, []]),
    );
    expect(summarizeSystemCoverage([aehf], solvedButBlind, startMs, endMs)[0]!.verdict).toBe("none");
    expect(summarizeSystemCoverage([aehf], new Map(), startMs, endMs)[0]!.verdict).toBe("not-computed");
  });
});

describe("the waypoint dimming interaction", () => {
  const resolved = resolveSystems(dataset, catalog.satellites);
  const wgs = resolved.find((entry) => entry.system.systemId === "wgs")!;
  const aehf = resolved.find((entry) => entry.system.systemId === "aehf")!;
  const middleMs = route.waypoints[1]!.timeMs;

  const windows = new Map<number, Interval[]>([
    // WGS is overhead at the middle waypoint; AEHF is not.
    [wgs.satellites[0]!.id, [{ startMs, endMs }]],
    [aehf.satellites[0]!.id, [{ startMs, endMs: middleMs - 3_600_000 }]],
  ]);

  it("names exactly the systems with something overhead at that instant", () => {
    const overhead = systemsOverheadAt([wgs, aehf], windows, middleMs);
    expect(overhead.has("wgs")).toBe(true);
    expect(overhead.has("aehf")).toBe(false);
  });

  it("still lists the system that is not overhead, because that is the answer", () => {
    // The panel dims rather than removes. Both systems must remain in the
    // coverage output at the focused instant; only the highlight changes.
    const coverage = summarizeSystemCoverage([wgs, aehf], windows, startMs, endMs, 1000);
    expect(coverage.map((entry) => entry.systemId).sort()).toEqual(["aehf", "wgs"]);
  });

  it("counts the individual spacecraft overhead, not just the system", () => {
    expect(satellitesOverheadAt(wgs, windows, middleMs)).toEqual([wgs.satellites[0]!.id]);
    expect(satellitesOverheadAt(aehf, windows, middleMs)).toEqual([]);
    expect(satellitesOverheadAt(aehf, windows, startMs + 60_000)).toEqual([aehf.satellites[0]!.id]);
  });
});

describe("end to end, through the same solver the worker calls", () => {
  const resolved = resolveSystems(dataset, catalog.satellites);
  const wgs = resolved.find((entry) => entry.system.systemId === "wgs")!;
  const inputs = wgs.satellites.map((record: SatelliteRecord) => ({
    id: record.id,
    periodMinutes: record.periodMinutes,
    omm: record.omm,
  }));

  it("finds windows for a real geosynchronous constellation over a real transit", () => {
    const results = inputs.map((satellite) =>
      solveSatelliteVisibility(satellite, route, { maskDeg: 5, observerAltitudeKm: 0.02, edgeToleranceSeconds: 2 }));
    expect(results).toHaveLength(10);
    expect(results.every((result) => result.propagationFailures === 0)).toBe(true);

    const withWindows = results.filter((result) => result.windows.length > 0);
    expect(withWindows.length).toBeGreaterThan(0);

    for (const result of results) {
      // Geosynchronous: sampled every 300 s, and any window must sit inside the
      // transit and run forwards.
      expect(result.gridStepSeconds).toBe(300);
      for (const window of result.windows) {
        expect(window.endMs).toBeGreaterThan(window.startMs);
        expect(window.startMs).toBeGreaterThanOrEqual(startMs - 1);
        expect(window.endMs).toBeLessThanOrEqual(endMs + 1);
        expect(window.peakElevationDeg).toBeGreaterThanOrEqual(5);
        expect(window.peakRangeKm).toBeGreaterThan(30_000);
        expect(window.peakRangeKm).toBeLessThan(45_000);
      }
    }
  });

  it("gives strictly less coverage as the mask rises — the control has to bite", () => {
    const totals = [0, 5, 10, 20].map((maskDeg) => {
      const windows = new Map<number, Interval[]>();
      for (const satellite of inputs) {
        const result = solveSatelliteVisibility(satellite, route, {
          maskDeg, observerAltitudeKm: 0.02, edgeToleranceSeconds: 5,
        });
        windows.set(result.satelliteId, result.windows.map((w) => ({ startMs: w.startMs, endMs: w.endMs })));
      }
      const coverage = summarizeSystemCoverage([wgs], windows, startMs, endMs, 1000)[0]!;
      return { maskDeg, seconds: [...windows.values()].flat().reduce((sum, w) => sum + (w.endMs - w.startMs), 0) / 1000, coverage };
    });

    for (let index = 1; index < totals.length; index += 1) {
      expect(totals[index]!.seconds, `mask ${totals[index]!.maskDeg}`)
        .toBeLessThan(totals[index - 1]!.seconds);
    }
    // And it must actually matter, not shave a rounding error off.
    expect(totals[0]!.seconds - totals.at(-1)!.seconds).toBeGreaterThan(3600);
  });

  it("agrees with the cheap instantaneous path used by the globe and the dimming", () => {
    // Two independent code paths answer "is this satellite up right now": the
    // window solve, and `visibleAtInstant`. If they disagree, the map shows one
    // thing and the list says another - which is exactly the bug a user reports
    // as "it's lying to me".
    const maskDeg = 5;
    const windows = new Map<number, Interval[]>();
    for (const satellite of inputs) {
      const result = solveSatelliteVisibility(satellite, route, {
        maskDeg, observerAltitudeKm: 0.02, edgeToleranceSeconds: 1,
      });
      windows.set(result.satelliteId, result.windows.map((w) => ({ startMs: w.startMs, endMs: w.endMs })));
    }

    const probeTimes = [0.1, 0.3, 0.5, 0.7, 0.9].map((f) => startMs + (endMs - startMs) * f);
    for (const timeMs of probeTimes) {
      const observer = positionOnRoute(timeMs);
      const instant = new Set(visibleAtInstant(
        inputs, observer.latitudeDeg, observer.longitudeDeg, 0.02, timeMs, maskDeg,
      ).map((entry) => entry.satelliteId));
      const fromWindows = new Set(
        [...windows.entries()]
          .filter(([, list]) => list.some((w) => timeMs >= w.startMs && timeMs <= w.endMs))
          .map(([id]) => id),
      );
      expect([...instant].sort(), `at ${new Date(timeMs).toISOString()}`)
        .toEqual([...fromWindows].sort());
    }
  });

  it("estimates its own cost within a few percent of what it then spends", () => {
    const durationSeconds = (endMs - startMs) / 1000;
    const estimate = estimateEvaluations(inputs, durationSeconds);
    let actual = 0;
    for (const satellite of inputs) {
      actual += solveSatelliteVisibility(satellite, route, {
        maskDeg: 5, observerAltitudeKm: 0.02, edgeToleranceSeconds: 2,
      }).evaluations;
    }
    // The estimate excludes edge refinement, so it must be a slight undercount -
    // never an overcount, or the budget gate would let through a solve it
    // promised would be cheap.
    expect(actual).toBeGreaterThanOrEqual(estimate);
    expect(actual / estimate).toBeLessThan(1.15);
  });
});

/** Route position, duplicated from the module under test only for probe times. */
function positionOnRoute(timeMs: number) {
  const waypoints = route.waypoints;
  let index = 0;
  for (let candidate = 0; candidate < waypoints.length - 1; candidate += 1) {
    if (timeMs <= waypoints[candidate + 1]!.timeMs) { index = candidate; break; }
    index = candidate;
  }
  const from = waypoints[index]!;
  const to = waypoints[index + 1]!;
  const fraction = (timeMs - from.timeMs) / (to.timeMs - from.timeMs);
  const DEG = Math.PI / 180;
  const lat1 = from.latitudeDeg * DEG;
  const lat2 = to.latitudeDeg * DEG;
  const lon1 = from.longitudeDeg * DEG;
  const lon2 = to.longitudeDeg * DEG;
  const angle = 2 * Math.asin(Math.sqrt(
    Math.sin((lat2 - lat1) / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin((lon2 - lon1) / 2) ** 2,
  ));
  const a = Math.sin((1 - fraction) * angle) / Math.sin(angle);
  const b = Math.sin(fraction * angle) / Math.sin(angle);
  const x = a * Math.cos(lat1) * Math.cos(lon1) + b * Math.cos(lat2) * Math.cos(lon2);
  const y = a * Math.cos(lat1) * Math.sin(lon1) + b * Math.cos(lat2) * Math.sin(lon2);
  const z = a * Math.sin(lat1) + b * Math.sin(lat2);
  return {
    latitudeDeg: Math.atan2(z, Math.hypot(x, y)) / DEG,
    longitudeDeg: Math.atan2(y, x) / DEG,
  };
}
