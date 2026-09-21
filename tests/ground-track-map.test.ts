import { describe, expect, it } from "vitest";
import {
  formatLatitudeLabel,
  formatLongitudeLabel,
  formatSpan,
  formatTimeEntry,
  formatUtcTick,
  graticuleLines,
  interpolateTrackAt,
  localZoneLabel,
  localZoneName,
  MAXIMUM_SPAN_MINUTES,
  parseSpanEntry,
  parseTimeEntry,
  parseTimeInput,
  plotRect,
  project,
  PROJECTION_NAME,
  PROJECTION_NOTE,
  splitTrackAtTime,
  trackTimeRange,
  groundTrackExtent,
  groundTrackAnnotation,
  normalizeGroundTrackPoints,
  normalizeLongitude,
  segmentGroundTrack,
  selectGlobalUtcTickPoints,
  selectUtcTickPoints,
  shouldShowCompactGeosynchronousInset,
  sampleTrackWindow,
  trackSampleCount,
  trackSpanOptions,
} from "../src/ground-track-map";

describe("ground-track longitude handling", () => {
  it("normalizes longitudes without changing valid positions", () => {
    expect(normalizeLongitude(45)).toBe(45);
    expect(normalizeLongitude(181)).toBe(-179);
    expect(normalizeLongitude(-181)).toBe(179);
    expect(normalizeLongitude(540)).toBe(-180);
  });

  it("splits an eastbound antimeridian crossing at both map edges", () => {
    const segments = segmentGroundTrack([
      { longitudeDeg: 179, latitudeDeg: 10, at: "2026-08-06T12:00:00Z" },
      { longitudeDeg: -179, latitudeDeg: 12, at: "2026-08-06T12:02:00Z" },
    ]);

    expect(segments).toHaveLength(2);
    expect(segments[0]?.at(-1)).toMatchObject({ longitudeDeg: 180, latitudeDeg: 11 });
    expect(segments[1]?.[0]).toMatchObject({ longitudeDeg: -180, latitudeDeg: 11 });
    expect(segments[0]?.at(-1)?.timeMs).toBe(Date.parse("2026-08-06T12:01:00Z"));
  });

  it("splits a westbound antimeridian crossing at both map edges", () => {
    const segments = segmentGroundTrack([
      { longitudeDeg: -179, latitudeDeg: -4, at: "2026-08-06T12:00:00Z" },
      { longitudeDeg: 179, latitudeDeg: -6, at: "2026-08-06T12:02:00Z" },
    ]);

    expect(segments).toHaveLength(2);
    expect(segments[0]?.at(-1)).toMatchObject({ longitudeDeg: -180, latitudeDeg: -5 });
    expect(segments[1]?.[0]).toMatchObject({ longitudeDeg: 180, latitudeDeg: -5 });
  });

  it("keeps an ordinary track in one segment", () => {
    const segments = segmentGroundTrack([
      { longitudeDeg: -30, latitudeDeg: 5, at: 0 },
      { longitudeDeg: 20, latitudeDeg: 8, at: 60_000 },
    ]);
    expect(segments).toHaveLength(1);
    expect(segments[0]).toHaveLength(2);
  });
});

describe("ground-track labeling", () => {
  it("distinguishes one orbit from a geosynchronous analemma", () => {
    expect(groundTrackAnnotation({ kind: "orbital-period", periodMinutes: 93.8 }).label)
      .toBe("ONE ORBIT · 93.8 min");
    const geosynchronous = groundTrackAnnotation({ kind: "geosynchronous-analemma" });
    expect(geosynchronous.label).toBe("24-HOUR GEOSYNCHRONOUS GROUND TRACK");
    expect(geosynchronous.explanation).toContain("Inclination");
  });

  it("formats compact UTC labels", () => {
    expect(formatUtcTick(Date.parse("2026-08-06T19:47:30Z"))).toBe("08-06 19:47Z");
  });

  it("selects bounded, ordered tick samples including both endpoints", () => {
    const points = normalizeGroundTrackPoints(Array.from({ length: 11 }, (_, index) => ({
      longitudeDeg: index,
      latitudeDeg: index,
      at: index * 60_000,
    })));
    const ticks = selectUtcTickPoints(points, 4);
    expect(ticks).toHaveLength(4);
    expect(ticks[0]?.timeMs).toBe(0);
    expect(ticks.at(-1)?.timeMs).toBe(600_000);
    expect(ticks.map((point) => point.timeMs)).toEqual([...ticks.map((point) => point.timeMs)].sort((a, b) => a - b));
  });

  it("drops invalid samples before rendering", () => {
    const points = normalizeGroundTrackPoints([
      { longitudeDeg: 0, latitudeDeg: 0, at: "not-a-date" },
      { longitudeDeg: 12, latitudeDeg: 95, at: "2026-08-06T00:00:00Z" },
    ]);
    expect(points).toEqual([{ longitudeDeg: 12, latitudeDeg: 90, timeMs: Date.parse("2026-08-06T00:00:00Z") }]);
  });
});

describe("compact geosynchronous presentation", () => {
  const compactGeosynchronous = normalizeGroundTrackPoints(Array.from({ length: 25 }, (_, index) => {
    const phase = (index / 24) * Math.PI * 2;
    return {
      longitudeDeg: -75 + Math.sin(phase * 2) * 0.045,
      latitudeDeg: Math.sin(phase) * 2.35,
      at: Date.parse("2026-08-06T00:00:00Z") + index * 60 * 60_000,
    };
  }));

  it("detects a compact 24-hour trace but not an ordinary orbit or broad analemma", () => {
    expect(shouldShowCompactGeosynchronousInset(
      compactGeosynchronous,
      { kind: "geosynchronous-analemma", hours: 24 },
    )).toBe(true);
    expect(shouldShowCompactGeosynchronousInset(
      compactGeosynchronous,
      { kind: "orbital-period", periodMinutes: 1436 },
    )).toBe(false);

    const broadAnalemma = normalizeGroundTrackPoints(Array.from({ length: 25 }, (_, index) => {
      const phase = (index / 24) * Math.PI * 2;
      return {
        longitudeDeg: 20 + Math.sin(phase * 2) * 5,
        latitudeDeg: Math.sin(phase) * 10,
        at: index * 60 * 60_000,
      };
    }));
    expect(shouldShowCompactGeosynchronousInset(
      broadAnalemma,
      { kind: "geosynchronous-analemma", hours: 24 },
    )).toBe(false);
  });

  it("measures compact longitude extent correctly across the antimeridian", () => {
    const extent = groundTrackExtent(normalizeGroundTrackPoints([
      { longitudeDeg: 179.96, latitudeDeg: -2, at: 0 },
      { longitudeDeg: -179.99, latitudeDeg: 0, at: 1 },
      { longitudeDeg: 179.97, latitudeDeg: 2, at: 2 },
    ]));
    expect(extent?.longitudeSpanDeg).toBeCloseTo(0.05, 8);
    expect(extent?.latitudeSpanDeg).toBe(4);
    expect(Math.abs(extent?.centerLongitudeDeg ?? 0)).toBeGreaterThan(179.9);
  });

  it("suppresses colliding UTC labels on the global map", () => {
    expect(selectGlobalUtcTickPoints(compactGeosynchronous, 6)).toHaveLength(1);

    const broadTrack = normalizeGroundTrackPoints(Array.from({ length: 7 }, (_, index) => ({
      longitudeDeg: -150 + index * 50,
      latitudeDeg: -45 + index * 15,
      at: index * 60 * 60_000,
    })));
    expect(selectGlobalUtcTickPoints(broadTrack, 6).length).toBeGreaterThan(3);
  });
});

describe("equirectangular projection and graticule", () => {
  it("maps the world corners to the plot corners", () => {
    const topLeft = project(-180, 90, 960, 540);
    const bottomRight = project(180, -90, 960, 540);
    const centre = project(0, 0, 960, 540);
    expect(centre.x).toBeCloseTo((topLeft.x + bottomRight.x) / 2, 9);
    expect(centre.y).toBeCloseTo((topLeft.y + bottomRight.y) / 2, 9);
    // Linear in both axes: -90 deg is a quarter of the way across the world,
    // so it sits half way between the left edge and the prime meridian.
    expect(project(-90, 0, 960, 540).x - topLeft.x)
      .toBeCloseTo((centre.x - topLeft.x) / 2, 9);
    expect(project(0, 45, 960, 540).y - topLeft.y)
      .toBeCloseTo((centre.y - topLeft.y) / 2, 9);
  });

  it("keeps a degree of longitude the same size as a degree of latitude", () => {
    // On plate carree the two axes must share a scale, so the drawing
    // rectangle is 2:1 and centred, whatever box the caller gives it.
    for (const [width, height] of [[960, 594], [960, 540], [700, 900], [1400, 600]] as const) {
      const plot = plotRect(width, height);
      expect(`${width}x${height}: ${(plot.width / plot.height).toFixed(6)}`)
        .toBe(`${width}x${height}: 2.000000`);
      const degreesPerPixelX = 360 / plot.width;
      const degreesPerPixelY = 180 / plot.height;
      expect(degreesPerPixelX).toBeCloseTo(degreesPerPixelY, 9);
    }
  });

  it("names the projection so the distortion is not left implicit", () => {
    expect(PROJECTION_NAME.toLowerCase()).toContain("equirectangular");
    expect(PROJECTION_NOTE.toLowerCase()).toContain("exaggerated toward the poles");
  });

  it("draws a 30 degree graticule and marks the equator and prime meridian", () => {
    const lines = graticuleLines();
    const meridians = lines.filter((line) => line.kind === "meridian");
    const parallels = lines.filter((line) => line.kind === "parallel");
    expect(meridians.map((line) => line.degrees))
      .toEqual([-150, -120, -90, -60, -30, 0, 30, 60, 90, 120, 150]);
    expect(parallels.map((line) => line.degrees))
      .toEqual([-60, -30, 0, 30, 60]);

    const principal = lines.filter((line) => line.emphasis === "principal");
    expect(principal).toHaveLength(2);
    expect(principal.map((line) => line.kind).sort()).toEqual(["meridian", "parallel"]);
    expect(principal.every((line) => line.degrees === 0)).toBe(true);
  });

  it("labels degrees with a hemisphere, and zero and the antimeridian without one", () => {
    expect(formatLongitudeLabel(-120)).toBe("120°W");
    expect(formatLongitudeLabel(30)).toBe("30°E");
    expect(formatLongitudeLabel(0)).toBe("0°");
    expect(formatLongitudeLabel(180)).toBe("180°");
    expect(formatLongitudeLabel(-180)).toBe("180°");
    expect(formatLatitudeLabel(60)).toBe("60°N");
    expect(formatLatitudeLabel(-30)).toBe("30°S");
    expect(formatLatitudeLabel(0)).toBe("0°");
  });
});

describe("time selection along the track", () => {
  const start = Date.parse("2026-08-07T12:00:00Z");
  const track = normalizeGroundTrackPoints([
    { longitudeDeg: -10, latitudeDeg: 0, at: start },
    { longitudeDeg: 10, latitudeDeg: 20, at: start + 600_000 },
    { longitudeDeg: 30, latitudeDeg: 40, at: start + 1_200_000 },
  ]);

  it("reports the window the track actually covers", () => {
    expect(trackTimeRange(track)).toEqual({ startMs: start, endMs: start + 1_200_000 });
    expect(trackTimeRange([])).toBeNull();
  });

  it("is exact at the samples and linear between them", () => {
    expect(interpolateTrackAt(track, start)).toMatchObject({ longitudeDeg: -10, latitudeDeg: 0 });
    const midpoint = interpolateTrackAt(track, start + 300_000)!;
    expect(midpoint.longitudeDeg).toBeCloseTo(0, 9);
    expect(midpoint.latitudeDeg).toBeCloseTo(10, 9);
    expect(midpoint.timeMs).toBe(start + 300_000);
  });

  it("clamps outside the window instead of extrapolating off the map", () => {
    expect(interpolateTrackAt(track, start - 5_000_000)?.longitudeDeg).toBe(-10);
    expect(interpolateTrackAt(track, start + 5_000_000)?.longitudeDeg).toBe(30);
  });

  it("interpolates the short way across the antimeridian", () => {
    const seam = normalizeGroundTrackPoints([
      { longitudeDeg: 179, latitudeDeg: 0, at: 0 },
      { longitudeDeg: -179, latitudeDeg: 0, at: 1000 },
    ]);
    expect(interpolateTrackAt(seam, 500)?.longitudeDeg).toBe(-180);
  });

  it("splits the track at the selected time and shares one boundary point", () => {
    const { past, future } = splitTrackAtTime(track, start + 300_000);
    expect(past.at(-1)?.timeMs).toBe(start + 300_000);
    expect(future[0]?.timeMs).toBe(start + 300_000);
    expect(past.at(-1)?.longitudeDeg).toBeCloseTo(future[0]!.longitudeDeg, 9);
    expect(past).toHaveLength(2);
    expect(future).toHaveLength(3);
  });

  it("puts everything ahead when the selected time is before the track starts", () => {
    const { past, future } = splitTrackAtTime(track, start - 1);
    expect(past).toHaveLength(0);
    expect(future).toHaveLength(3);
  });
});

describe("typed time entry", () => {
  const reference = Date.parse("2026-08-07T19:38:15Z");

  it("reads the same format the readout prints, in UTC", () => {
    expect(formatTimeEntry(reference, "utc")).toBe("2026-08-07 19:38");
    expect(parseTimeEntry("2026-08-07 19:38", "utc")).toBe(Date.parse("2026-08-07T19:38:00Z"));
  });

  it("round-trips local time through the viewer's own offset", () => {
    const printed = formatTimeEntry(reference, "local");
    const parsed = parseTimeEntry(printed, "local");
    expect(parsed).not.toBeNull();
    // Same instant to the printed minute, whatever timezone the viewer is in.
    expect(Math.abs(parsed! - reference)).toBeLessThan(60_000);
    expect(formatTimeEntry(parsed!, "local")).toBe(printed);
  });

  it("does not confuse the two zones unless the viewer is on UTC", () => {
    const utc = parseTimeEntry("2026-08-07 19:38", "utc")!;
    const local = parseTimeEntry("2026-08-07 19:38", "local")!;
    expect(local - utc).toBe(new Date(utc).getTimezoneOffset() * 60_000);
  });

  it("is tolerant about separators, seconds and a trailing Z", () => {
    const target = Date.parse("2026-08-07T19:38:00Z");
    for (const text of [
      "2026-08-07 19:38",
      "2026-08-07T19:38",
      "2026-08-07T19:38Z",
      "2026-08-07 19:38:00",
      "  2026-08-07   19:38  ",
      "2026-8-7 19:38",
    ]) {
      expect(`${text} -> ${parseTimeEntry(text, "utc")}`).toBe(`${text} -> ${target}`);
    }
    expect(parseTimeEntry("19:38", "utc", reference)).toBe(target);
  });

  it("returns null rather than guessing when it cannot read the text", () => {
    // "tomorrow" used to belong on this list. It is now read on purpose; the
    // owner asked for words, so the words are in the grammar below.
    for (const text of ["", "garbage", "2026-02-31 10:00", "2026-08-07 25:00", "99:99", "orbit"]) {
      expect(`${text} -> ${parseTimeEntry(text, "utc", reference)}`).toBe(`${text} -> null`);
    }
  });

  it("labels the viewer's zone with an explicit UTC offset", () => {
    expect(localZoneLabel(new Date(reference))).toMatch(/UTC[+-]\d{2}:\d{2}/);
  });
});

describe("compact-track inset threshold", () => {
  // Shape of SKYTERRA 1's real 24-hour analemma, measured with the project's
  // own SGP4 path: 0.263 deg of longitude by 10.50 deg of latitude.
  const skyterraShaped = normalizeGroundTrackPoints(Array.from({ length: 97 }, (_, index) => {
    const phase = (index / 96) * Math.PI * 2;
    return {
      longitudeDeg: -101.33 + Math.sin(phase * 2) * 0.1315,
      latitudeDeg: Math.sin(phase) * 5.25,
      at: Date.parse("2026-08-07T07:38:00Z") + index * 15 * 60_000,
    };
  }));

  it("fires for a track that is a sliver on the global map even when it is tall", () => {
    const extent = groundTrackExtent(skyterraShaped)!;
    expect(extent.longitudeSpanDeg).toBeCloseTo(0.263, 2);
    expect(extent.latitudeSpanDeg).toBeCloseTo(10.5, 1);
    // Under one pixel wide at the default size: that is why the inset exists.
    const plotWidth = 960 - 44 - 18;
    expect((extent.longitudeSpanDeg / 360) * plotWidth).toBeLessThan(1);
    expect(shouldShowCompactGeosynchronousInset(
      skyterraShaped,
      { kind: "geosynchronous-analemma", hours: 24 },
    )).toBe(true);
  });

  it("still declines for an analemma that is already legible", () => {
    const broad = normalizeGroundTrackPoints(Array.from({ length: 25 }, (_, index) => {
      const phase = (index / 24) * Math.PI * 2;
      return {
        longitudeDeg: 20 + Math.sin(phase * 2) * 5,
        latitudeDeg: Math.sin(phase) * 10,
        at: index * 60 * 60_000,
      };
    }));
    expect(shouldShowCompactGeosynchronousInset(
      broad,
      { kind: "geosynchronous-analemma", hours: 24 },
    )).toBe(false);
  });
});

/**
 * The forgiving entry that replaced the two unexplained time boxes.
 *
 * The owner's complaint was precise: the boxes duplicated the slider, said
 * nothing about what they were for, and typing an arbitrary date into them did
 * nothing useful. These tests pin every format he named, plus the sentence the
 * control shows back, because a parser that reads "08/07" as the seventh of
 * August without saying so is a different kind of trap.
 */
describe("forgiving time entry", () => {
  const reference = Date.parse("2026-08-07T19:38:15Z");
  const target = Date.parse("2026-08-07T19:38:00Z");

  it("reads every written form the owner asked for, in UTC", () => {
    for (const text of [
      "2026-08-07 19:38",
      "2026-08-07T19:38Z",
      "2026-08-07t19:38",
      "2026-08-07 19:38:00",
      "2026/08/07 19:38",
      "19:38",
      "7:38 pm",
      "7:38pm",
      "08/07 7:38 pm",
      "08/07/2026 19:38",
      "7 aug 2026 19:38",
      "aug 7 19:38",
      "August 7, 2026 7:38 PM",
      "2026-08-07 19:38 utc",
      "2026-08-07T19:38:00.000Z",
    ]) {
      expect(`${text} -> ${parseTimeInput(text, "utc", reference)?.timeMs}`).toBe(`${text} -> ${target}`);
    }
  });

  it("reads the day words, alone and with a time", () => {
    expect(parseTimeInput("now", "utc", reference)?.timeMs).toBe(reference);
    // Bare "yesterday" keeps the clock time already on screen, so the window
    // lands on the same moment a day earlier rather than on midnight.
    expect(parseTimeInput("yesterday", "utc", reference)?.timeMs)
      .toBe(Date.parse("2026-08-06T19:38:00Z"));
    expect(parseTimeInput("tomorrow", "utc", reference)?.timeMs)
      .toBe(Date.parse("2026-08-08T19:38:00Z"));
    expect(parseTimeInput("today 06:15", "utc", reference)?.timeMs)
      .toBe(Date.parse("2026-08-07T06:15:00Z"));
    expect(parseTimeInput("yesterday at 6:15 am", "utc", reference)?.timeMs)
      .toBe(Date.parse("2026-08-06T06:15:00Z"));
  });

  it("reads relative offsets from the time on screen", () => {
    expect(parseTimeInput("+90m", "utc", reference)?.timeMs).toBe(reference + 90 * 60_000);
    expect(parseTimeInput("-2h", "utc", reference)?.timeMs).toBe(reference - 2 * 3_600_000);
    expect(parseTimeInput("3 hours ago", "utc", reference)?.timeMs).toBe(reference - 3 * 3_600_000);
    expect(parseTimeInput("in 45 min", "utc", reference)?.timeMs).toBe(reference + 45 * 60_000);
    expect(parseTimeInput("-1d", "utc", reference)?.timeMs).toBe(reference - 86_400_000);
  });

  it("gets midnight and noon right on a 12-hour clock", () => {
    expect(parseTimeInput("12:00 am", "utc", reference)?.timeMs).toBe(Date.parse("2026-08-07T00:00:00Z"));
    expect(parseTimeInput("12:00 pm", "utc", reference)?.timeMs).toBe(Date.parse("2026-08-07T12:00:00Z"));
    expect(parseTimeInput("12:30 am", "utc", reference)?.timeMs).toBe(Date.parse("2026-08-07T00:30:00Z"));
    expect(parseTimeInput("13:00 pm", "utc", reference)).toBeNull();
  });

  it("lets the text override the selected zone, and says which zone it used", () => {
    // Local is selected, but the text says Zulu: Zulu wins, and the sentence
    // records that the zone came from the text rather than from the selector.
    const zulu = parseTimeInput("2026-08-07 19:38Z", "local", reference)!;
    expect(zulu.timeMs).toBe(target);
    expect(zulu.zone).toBe("utc");
    expect(zulu.assumedZone).toBe(false);
    expect(zulu.reading).toContain("zone taken from what you typed");

    const offset = parseTimeInput("2026-08-07T15:38-04:00", "utc", reference)!;
    expect(offset.timeMs).toBe(target);
    expect(offset.zone).toBe("offset");
    expect(offset.zoneLabel).toBe("UTC-04:00");

    const selected = parseTimeInput("2026-08-07 19:38", "local", reference)!;
    expect(selected.zone).toBe("local");
    expect(selected.assumedZone).toBe(true);
    expect(selected.timeMs - target).toBe(new Date(target).getTimezoneOffset() * 60_000);
  });

  it("names both zones in the sentence it shows back", () => {
    const parsed = parseTimeInput("2026-08-07 19:38", "utc", reference)!;
    expect(parsed.reading).toContain("2026-08-07 19:38Z");
    expect(parsed.reading).toContain(formatTimeEntry(target, "local"));
    expect(parsed.reading).toContain(localZoneName() || "UTC");
  });

  it("says out loud when it filled in the date for you", () => {
    const bare = parseTimeInput("19:38", "utc", reference)!;
    expect(bare.assumedDate).toBe(true);
    expect(bare.reading).toContain("date taken from the window on screen");

    const dated = parseTimeInput("2026-08-07 19:38", "utc", reference)!;
    expect(dated.assumedDate).toBe(false);
    expect(dated.reading).not.toContain("date taken from");
  });

  it("says out loud that a slashed date was read month-first", () => {
    const parsed = parseTimeInput("08/07 7:38 pm", "utc", reference)!;
    expect(parsed.timeMs).toBe(target);
    expect(parsed.reading).toContain("month/day");
    // The other reading of the same text is a different day, which is exactly
    // why it has to be stated.
    expect(parseTimeInput("07/08 7:38 pm", "utc", reference)!.timeMs)
      .toBe(Date.parse("2026-07-08T19:38:00Z"));
  });

  it("still refuses what it genuinely cannot read", () => {
    for (const text of [
      "", "   ", "garbage", "later", "99:99", "2026-02-31 10:00",
      "2026-08-07 25:00", "13:61", "19", "1938", "next tuesday",
    ]) {
      expect(`${text} -> ${parseTimeInput(text, "utc", reference)}`).toBe(`${text} -> null`);
    }
  });
});

/**
 * How much track to draw. The default stays exactly what it was; these pin the
 * options offered around it, and the geosynchronous case where "one orbit" and
 * "24 hours" are the same window and must not become two buttons.
 */
describe("track length options", () => {
  it("offers orbits and a day for a low Earth orbit", () => {
    const options = trackSpanOptions(94.8);
    expect(options.map((option) => option.id)).toEqual(["orbits-1", "orbits-3", "orbits-6", "hours-24"]);
    expect(options[0]).toMatchObject({ label: "1 orbit", detail: "94.8 min" });
    expect(options[1]).toMatchObject({ label: "3 orbits", detail: "4.7 h" });
    // A day is 15.2 of this spacecraft's orbits; saying so is the teaching part.
    expect(options[3]!.detail).toBe("15.2 orbits");
  });

  it("merges one orbit with 24 hours for a geosynchronous spacecraft", () => {
    const options = trackSpanOptions(1436);
    const minutes = options.map((option) => option.minutes);
    // No two buttons within two percent of each other: no degenerate control.
    for (let index = 1; index < minutes.length; index += 1) {
      expect(minutes[index]! / minutes[index - 1]!).toBeGreaterThan(1.02);
    }
    expect(options.some((option) => option.id === "hours-24")).toBe(false);
    expect(options[0]!.id).toBe("orbits-1");
    expect(options[0]!.label).toBe("1 orbit · 24 h");
    expect(options[0]!.detail).toBe("1 orbit is 24 hours for this spacecraft");
    expect(options.map((option) => option.label)).toEqual(["1 orbit · 24 h", "3 orbits", "6 orbits"]);
  });

  it("keeps a Molniya's half-day orbit and a day as separate windows", () => {
    const options = trackSpanOptions(717.8);
    expect(options.map((option) => option.id)).toEqual(["orbits-1", "hours-24", "orbits-3", "orbits-6"]);
    expect(options.every((option) => option.minutes <= MAXIMUM_SPAN_MINUTES)).toBe(true);
  });

  it("falls back to plain hours when the period is unknown", () => {
    for (const period of [null, undefined, 0, Number.NaN]) {
      expect(trackSpanOptions(period).map((option) => option.id)).toEqual(["hours-3", "hours-6", "hours-24"]);
    }
  });

  it("reads a hand-typed span forgivingly, and refuses the rest", () => {
    expect(parseSpanEntry("90 min", 94.8)).toBe(90);
    expect(parseSpanEntry("90", 94.8)).toBe(90);
    expect(parseSpanEntry("1.5h", 94.8)).toBe(90);
    expect(parseSpanEntry("6 hours", 94.8)).toBe(360);
    expect(parseSpanEntry("2 days", 94.8)).toBe(2880);
    expect(parseSpanEntry("3 orbits", 94.8)).toBeCloseTo(284.4, 9);
    expect(parseSpanEntry("2 rev", 94.8)).toBeCloseTo(189.6, 9);
    // Orbits mean nothing without a period, and nothing may exceed the cap.
    expect(parseSpanEntry("3 orbits", null)).toBeNull();
    expect(parseSpanEntry("9000 orbits", 94.8)).toBeNull();
    expect(parseSpanEntry("30 days", 94.8)).toBeNull();
    expect(parseSpanEntry("0", 94.8)).toBeNull();
    expect(parseSpanEntry("soon", 94.8)).toBeNull();
    expect(parseSpanEntry("", 94.8)).toBeNull();
  });

  it("sizes a span the way a reader would say it", () => {
    expect(formatSpan(94.8)).toBe("94.8 min");
    expect(formatSpan(60)).toBe("60 min");
    expect(formatSpan(284.4)).toBe("4.7 h");
    expect(formatSpan(1440)).toBe("24 h");
    expect(formatSpan(4320)).toBe("3 d");
  });
});

/**
 * Re-sampling the window. This is the code path that makes "if I put yesterday
 * in there right now nothing useful shows up" impossible: the drawn track is
 * generated around whatever centre the viewer chose, not around now.
 */
describe("sampling an arbitrary window", () => {
  // A real, if simple, sub-satellite motion: one revolution per period with the
  // Earth turning underneath. No mock — the function under test calls it.
  const period = 94.8;
  const epoch = Date.parse("2026-08-07T19:38:00Z");
  const sampler = (time: Date) => {
    const minutes = (time.getTime() - epoch) / 60_000;
    return {
      longitudeDeg: normalizeLongitude(minutes * (360 / period) - minutes * (360 / 1436)),
      latitudeDeg: 51.6 * Math.sin((minutes / period) * Math.PI * 2),
      altitudeKm: 420,
    };
  };

  it("centres the window on the requested time and covers exactly the span", () => {
    const centre = Date.parse("2026-08-06T19:38:00Z");
    const points = sampleTrackWindow(sampler, centre, 3 * period);
    const range = trackTimeRange(normalizeGroundTrackPoints(points))!;
    expect((range.endMs - range.startMs) / 60_000).toBeCloseTo(3 * period, 6);
    expect((range.startMs + range.endMs) / 2).toBe(centre);
    // Yesterday really is yesterday: nothing here is anchored to now.
    expect(range.endMs).toBeLessThan(Date.parse("2026-08-07T00:00:00Z"));
  });

  it("keeps sample spacing fine enough to draw, and bounded enough to compute", () => {
    expect(trackSampleCount(94.8)).toBe(240);
    expect(trackSampleCount(1440)).toBe(2000);
    expect(trackSampleCount(MAXIMUM_SPAN_MINUTES)).toBe(2000);
    for (const span of [94.8, 284.4, 1440, MAXIMUM_SPAN_MINUTES]) {
      const points = sampleTrackWindow(sampler, epoch, span);
      expect(points.length).toBe(trackSampleCount(span) + 1);
    }
  });

  it("clamps a span past the cap rather than propagating forever", () => {
    const points = sampleTrackWindow(sampler, epoch, 10 * MAXIMUM_SPAN_MINUTES);
    const range = trackTimeRange(normalizeGroundTrackPoints(points))!;
    expect((range.endMs - range.startMs) / 60_000).toBeCloseTo(MAXIMUM_SPAN_MINUTES, 6);
  });

  it("labels a chosen window without pretending it is still one orbit", () => {
    const annotation = groundTrackAnnotation({ kind: "custom-span", minutes: 284.4, label: "3 orbits" });
    expect(annotation.label).toBe("3 ORBITS · 4.7 h");
    expect(annotation.explanation).toContain("rotating Earth");
    const geosynchronous = groundTrackAnnotation({
      kind: "custom-span", minutes: 1436, label: "1 orbit · 24 h", geosynchronous: true,
    });
    expect(geosynchronous.explanation).toContain("Inclination");
    // The compact inset still fires for a geosynchronous window the viewer chose.
    const compact = normalizeGroundTrackPoints(Array.from({ length: 25 }, (_, index) => ({
      longitudeDeg: -75 + Math.sin((index / 24) * Math.PI * 4) * 0.045,
      latitudeDeg: Math.sin((index / 24) * Math.PI * 2) * 2.35,
      at: index * 60 * 60_000,
    })));
    expect(shouldShowCompactGeosynchronousInset(compact, {
      kind: "custom-span", minutes: 1436, geosynchronous: true,
    })).toBe(true);
    expect(shouldShowCompactGeosynchronousInset(compact, { kind: "custom-span", minutes: 1436 })).toBe(false);
  });
});

describe("what the day words claim", () => {
  const reference = Date.parse("2026-08-07T19:38:15Z");

  it("does not claim it invented a date when the word supplied one", () => {
    const bare = parseTimeInput("yesterday", "utc", reference)!;
    expect(bare.assumedDate).toBe(false);
    expect(bare.reading).not.toContain("date taken from");
    expect(bare.reading).toContain("at the clock time already shown");

    const withTime = parseTimeInput("yesterday 18:00", "utc", reference)!;
    expect(withTime.assumedDate).toBe(false);
    expect(withTime.reading).not.toContain("clock time already shown");
  });
});
