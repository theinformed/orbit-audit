import { describe, expect, it } from "vitest";

import { formatTime, zoneDescription, zoneLetter } from "../src/transit-planner-data";
import { TRANSIT_PRESETS } from "../src/transit-presets";
import { audienceProfile } from "../src/transit-audience";
import { geostationaryReachDeg } from "../src/transit-planner";
import { footprintAngularRadius } from "../src/orbit";

/**
 * These are CLAIM tests. Each one recomputes a number the page prints from the
 * code that produces it, or checks a convention against its own definition.
 * None of them assert that anything rendered.
 *
 * The zone-letter block exists because there was no test here at all, and the
 * function shipped for months with its sign inverted and a letter missing —
 * the class of defect a rendering test cannot see, on a Navy tool where a
 * reader knows the answer by heart.
 */
describe("ship's zone time", () => {
  /**
   * Zone description is the number of hours to ADD to zone time to get UTC.
   * West longitude is positive, east negative.
   */
  it("signs the zone description the way a ship does", () => {
    // Rounding a negative-zero longitude gives -0, which is 0 for every purpose
    // this value has; compare numerically rather than by Object.is.
    expect(zoneDescription(0)).toBeCloseTo(0, 10);
    expect(zoneDescription(-75)).toBe(5);
    expect(zoneDescription(139.95)).toBe(-9);
    expect(zoneDescription(-158.05)).toBe(11);
    expect(zoneDescription(180)).toBe(12);
  });

  /**
   * The letters are named by UTC OFFSET, which is the negative of the zone
   * description. Z is UTC; J is the one letter skipped; O is NOT skipped — it
   * is UTC-2.
   */
  it("names the zone by its UTC offset, not by its zone description", () => {
    expect(zoneLetter(0)).toBe("Z");
    expect(zoneLetter(-1)).toBe("A");   // UTC+1, Alfa
    expect(zoneLetter(-9)).toBe("I");   // UTC+9, India: Japan
    expect(zoneLetter(-12)).toBe("M");  // UTC+12, Mike
    expect(zoneLetter(1)).toBe("N");    // UTC-1, November
    expect(zoneLetter(2)).toBe("O");    // UTC-2, Oscar
    expect(zoneLetter(5)).toBe("R");    // UTC-5, Romeo
    expect(zoneLetter(11)).toBe("X");   // UTC-11, X-ray
    expect(zoneLetter(12)).toBe("Y");   // UTC-12, Yankee
  });

  it("never uses J, and uses every other letter exactly once", () => {
    const letters = [];
    for (let zone = -12; zone <= 12; zone += 1) letters.push(zoneLetter(zone));
    expect(letters).not.toContain("J");
    expect(new Set(letters).size).toBe(25);
  });

  /** The clock and the letter have to describe the same instant. */
  it("prints a clock that matches the letter it stamps", () => {
    // 2026-06-21T00:00Z at 139.95 E is 09:00 on the 21st, zone India.
    const at = Date.parse("2026-06-21T00:00:00Z");
    expect(formatTime(at, "zone", 139.95)).toBe("2026-06-21 09:00I");
    // The same instant at 75 W is 19:00 on the 20th, zone Romeo.
    expect(formatTime(at, "zone", -75)).toBe("2026-06-20 19:00R");
  });
});

describe("the lesson's numbers are the tool's numbers", () => {
  const lesson = audienceProfile("public").lesson!;
  const body = lesson.points.map((point) => point.body).join(" ");

  it("quotes the geostationary reach the mask control computes", () => {
    expect(body).toContain(`${geostationaryReachDeg(0).toFixed(1)}\u00b0 of arc away at 0\u00b0`);
    expect(body).toContain(`${geostationaryReachDeg(5).toFixed(1)}\u00b0 at 5\u00b0`);
    expect(body).toContain(`${geostationaryReachDeg(10).toFixed(1)}\u00b0 at 10\u00b0`);
  });

  /**
   * Raising the mask by one degree costs almost exactly one degree of arc,
   * which is 60 nautical miles of reach — not the 550 the copy claimed until
   * 2026-09-08, which was out by nearly a factor of ten and contradicted the
   * three reach figures in its own sentence.
   */
  it("costs a degree of arc per degree of mask, and says so", () => {
    const lostPerDegree = geostationaryReachDeg(0) - geostationaryReachDeg(1);
    expect(lostPerDegree).toBeGreaterThan(0.99);
    expect(lostPerDegree).toBeLessThan(1.0);
    expect(Math.round(lostPerDegree * 60)).toBe(60);
    expect(body).toContain("60 nautical miles of reach");
    expect(body).not.toContain("550 nautical miles");
  });

  /**
   * A geostationary satellite sees 42% of the surface at the geometric
   * horizon. The copy said "nearly a third", which is the figure for a
   * ten-degree mask, and understating it undercuts the very point the
   * sentence is making about why a handful of them is enough.
   */
  it("states the geostationary surface fraction the geometry gives", () => {
    const capFraction = (1 - Math.cos(footprintAngularRadius(35_786, 0))) / 2;
    expect(Math.round(capFraction * 100)).toBe(42);
    expect(body).toContain("42% of the planet");
  });

  /** 400 km reaches 2,200 km, which is a fifth of the way to the pole. */
  it("states the low-orbit reach as a reach, not as a diameter", () => {
    const reachDeg = (footprintAngularRadius(400, 0) * 180) / Math.PI;
    expect(Math.round((reachDeg * 111.195) / 100) * 100).toBe(2200);
    expect(Math.round((reachDeg / 90) * 100)).toBe(22);
    expect(body).toContain("reaches about 2,200 km in every direction");
  });
});

describe("preset notes describe what the tool will actually show", () => {
  /**
   * The Keflavik run's note claimed geostationary coverage "runs out" at
   * 64 N. It does not: on the meridian a geostationary satellite is still
   * about 18 degrees up there, so at the planner's default 5 degree mask every
   * geostationary system covers that transit and the note contradicted the
   * answer beside it.
   */
  it("does not claim geostationary coverage ends at 64 N", () => {
    const keflavik = TRANSIT_PRESETS.find((preset) => preset.id === "norfolk-keflavik")!;
    const arrival = keflavik.waypoints.at(-1)!;
    const centralAngleDeg = Math.abs(arrival.latitudeDeg);
    // Same spherical relation the footprint uses: a satellite is above the
    // mask while the central angle is inside footprintAngularRadius.
    const reachAtDefaultMaskDeg = (footprintAngularRadius(35_786, 5) * 180) / Math.PI;
    expect(centralAngleDeg).toBeLessThan(reachAtDefaultMaskDeg);
    expect(keflavik.note).not.toContain("runs out");
    expect(keflavik.note).toContain("18 degrees");
  });
});
