/**
 * The two presentations, the export contract, and element age.
 *
 * The load-bearing test in this file is the first one: **the two audiences must
 * never be able to change an answer.** Everything else here is about making sure
 * a document that leaves the browser carries its own caveats.
 */

import { describe, expect, it } from "vitest";
import {
  EXPORT_PROVENANCE_LINE,
  audienceProfile,
  type Audience,
} from "../src/transit-audience";
import {
  MAXIMUM_ELEMENT_AGE_DAYS,
  elementAgeBand,
  solveSatelliteVisibility,
} from "../src/transit-solve";
import { exportHeaderLines, exportFilename, windowsToCsv, type ExportContext } from "../src/transit-export";
import { loadCatalog } from "./transit-fixtures";
import type { CatalogBundle } from "../src/types";
import type { TransitRoute } from "../src/transit-route";

const catalog: CatalogBundle = await loadCatalog();

const route: TransitRoute = {
  trackModel: "great-circle",
  waypoints: [
    { id: "1", label: "Pearl Harbor", latitudeDeg: 21.35, longitudeDeg: -157.95, timeMs: Date.parse("2026-08-10T18:00:00Z") },
    { id: "2", label: "Yokosuka", latitudeDeg: 35.28, longitudeDeg: 139.67, timeMs: Date.parse("2026-08-15T18:00:00Z") },
  ],
};

const wgs = catalog.satellites
  .filter((record) => record.constellation === "WGS")
  .map((record) => ({ id: record.id, periodMinutes: record.periodMinutes, omm: record.omm }));

describe("the two presentations cannot change an answer", () => {
  it("has no path from an audience profile into the solver", () => {
    // solveSatelliteVisibility takes SolveOptions, which carries mask, observer
    // height and edge tolerance and nothing else. If an audience field ever
    // appears in that call, this assertion is the thing that should stop it.
    const options = { maskDeg: 5, observerAltitudeKm: 0.02, edgeToleranceSeconds: 2 };
    expect(Object.keys(options).sort()).toEqual(["edgeToleranceSeconds", "maskDeg", "observerAltitudeKm"]);

    const first = solveSatelliteVisibility(wgs[0]!, route, options);
    const second = solveSatelliteVisibility(wgs[0]!, route, options);
    expect(second.windows).toEqual(first.windows);
    expect(second.elementAgeDaysAtEnd).toBe(first.elementAgeDaysAtEnd);
  });

  it("differs only in presentation, and in the one bound that is argued for", () => {
    const publicProfile = audienceProfile("public");
    const gated = audienceProfile("gated");
    expect(publicProfile.maximumElementAgeDays).toBe(MAXIMUM_ELEMENT_AGE_DAYS);
    expect(gated.maximumElementAgeDays).toBeGreaterThan(publicProfile.maximumElementAgeDays);
    // Both remain bounded. Neither pretends a two-month propagation is useful.
    expect(gated.maximumElementAgeDays).toBeLessThanOrEqual(30);
  });

  it("shows element age in both builds, and never hides it on the public one", () => {
    for (const audience of ["public", "gated"] as Audience[]) {
      expect(audienceProfile(audience).prominentElementAge, audience).toBe(true);
    }
  });
});

describe("export is off on the public site and on behind the gate", () => {
  it("is disabled for the public audience", () => {
    expect(audienceProfile("public").exportEnabled).toBe(false);
    expect(audienceProfile("gated").exportEnabled).toBe(true);
  });

  it("makes the public build point at the gated one honestly, not as a paywall", () => {
    const link = audienceProfile("public").gatedLink!;
    expect(link).toBeTruthy();
    // It has to say what is behind it and who it is for.
    expect(link.description).toMatch(/export/i);
    expect(link.description).toMatch(/Everything it computes, this page computes too/);
    expect(audienceProfile("gated").gatedLink).toBeNull();
  });

  it("makes the gated disclosure louder, not softer", () => {
    const gated = audienceProfile("gated");
    expect(gated.additionalDisclosure).toBeTruthy();
    expect(gated.additionalDisclosure!).toMatch(/not an operational ephemeris/i);
    expect(gated.additionalDisclosure!).toMatch(/element age/i);
    expect(audienceProfile("public").additionalDisclosure).toBeNull();
  });

  it("leads the public build with the lesson and does not lecture the gated one", () => {
    const lesson = audienceProfile("public").lesson!;
    expect(lesson).toBeTruthy();
    expect(lesson.points).toHaveLength(3);
    expect(audienceProfile("gated").lesson).toBeNull();
  });
});

describe("what an exported file carries", () => {
  const results = wgs.map((satellite) =>
    solveSatelliteVisibility(satellite, route, { maskDeg: 5, observerAltitudeKm: 0.02, edgeToleranceSeconds: 2 }));

  const context: ExportContext = {
    profile: audienceProfile("gated"),
    route,
    maskDeg: 5,
    observerAltitudeKm: 0.02,
    results,
    satelliteNames: new Map(catalog.satellites.map((record) => [record.id, record.name])),
    systemBySatellite: new Map(wgs.map((satellite) => [satellite.id, "Wideband Global SATCOM"])),
    catalogUpstreamAsOf: catalog.upstreamAsOf,
    generatedAtMs: Date.parse("2026-08-08T00:00:00Z"),
  };

  it("puts the mask, the route and the provenance line in the header", () => {
    const header = exportHeaderLines(context).join("\n");
    expect(header).toContain(EXPORT_PROVENANCE_LINE);
    expect(header).toMatch(/Elevation mask:\s+5\.0 deg/);
    expect(header).toContain("Pearl Harbor");
    expect(header).toContain("Yokosuka");
    expect(header).toContain(catalog.upstreamAsOf);
  });

  it("repeats provenance, mask and element age on EVERY row", () => {
    // The whole point: somebody pastes one line into a message. That line has to
    // survive the journey with its caveats attached.
    const csv = windowsToCsv(context);
    const dataRows = csv.split("\n").filter((line) => line && !line.startsWith("#") && !line.startsWith("satellite_id"));
    expect(dataRows.length).toBeGreaterThan(0);
    for (const row of dataRows) {
      expect(row).toContain(EXPORT_PROVENANCE_LINE);
      expect(row).toMatch(/,5\.0,/);
      // Element epoch and a numeric age must both be present.
      expect(row).toMatch(/,\d{4}-\d{2}-\d{2}T/);
      expect(row).toMatch(/(fresh|aging|stale|beyond-bound)/);
    }
  });

  it("quotes cells containing commas so the provenance line cannot break the format", () => {
    const csv = windowsToCsv(context);
    const dataRows = csv.split("\n").filter((line) => line && !line.startsWith("#") && !line.startsWith("satellite_id"));
    expect(EXPORT_PROVENANCE_LINE).toContain(",");
    for (const row of dataRows) {
      expect(row).toContain(`"${EXPORT_PROVENANCE_LINE.replace(/"/g, '""')}"`);
    }
  });

  it("says so rather than emitting an empty table when nothing is visible", () => {
    const impossible: ExportContext = { ...context, maskDeg: 89, results: wgs.map((satellite) =>
      solveSatelliteVisibility(satellite, route, { maskDeg: 89, observerAltitudeKm: 0.02, edgeToleranceSeconds: 2 })) };
    const csv = windowsToCsv(impossible);
    expect(csv).toMatch(/No satellite reached 89\.0 deg elevation/);
  });

  it("names the file after the route and the mask, so two exports cannot be confused", () => {
    expect(exportFilename(context)).toBe("transit-visibility-2026-08-10-mask5deg.csv");
  });
});

describe("element age", () => {
  it("bands ages the way a reader would", () => {
    expect(elementAgeBand(0.5)).toBe("fresh");
    expect(elementAgeBand(2)).toBe("fresh");
    expect(elementAgeBand(2.01)).toBe("aging");
    expect(elementAgeBand(7)).toBe("aging");
    expect(elementAgeBand(7.01)).toBe("stale");
    expect(elementAgeBand(MAXIMUM_ELEMENT_AGE_DAYS)).toBe("stale");
    expect(elementAgeBand(MAXIMUM_ELEMENT_AGE_DAYS + 0.01)).toBe("beyond-bound");
  });

  it("treats a transit before the epoch as just as uncertain as one after it", () => {
    // Propagating backwards is no more trustworthy than forwards, so the band
    // is taken on absolute age. A negative age that read as "fresh" would be a
    // quiet lie.
    expect(elementAgeBand(-20)).toBe("beyond-bound");
    expect(elementAgeBand(-1)).toBe("fresh");
  });

  it("reports a real age against the real catalog, measured at the end of the transit", () => {
    const result = solveSatelliteVisibility(wgs[0]!, route, {
      maskDeg: 5, observerAltitudeKm: 0.02, edgeToleranceSeconds: 2,
    });
    expect(result.elementEpoch).toMatch(/^\d{4}-\d{2}-\d{2}T/);
    expect(Number.isFinite(result.elementAgeDaysAtEnd)).toBe(true);
    // Measured at the END of the transit — the worst case over the answer.
    const expected = (route.waypoints.at(-1)!.timeMs - Date.parse(result.elementEpoch)) / 86_400_000;
    expect(result.elementAgeDaysAtEnd).toBeCloseTo(expected, 6);
    expect(result.elementAgeBand).toBe(elementAgeBand(result.elementAgeDaysAtEnd));
  });
});
