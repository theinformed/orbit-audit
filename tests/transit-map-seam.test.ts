/**
 * The antimeridian seam, and the lines it drew across the map.
 *
 * Sean, on the shipped page: "what is going on with the weird lines at the top
 * and bottom? Are you not able to draw fleet or COCOM overlays correctly?"
 *
 * Two defects, one seam:
 *
 * 1. `normalizeLongitudeDeg(180)` is `-180`, which is right on a sphere and
 *    wrong on a plate carrée sheet where the antimeridian is BOTH edges. Every
 *    projected point went through it, so the +180 vertices `splitAtAntimeridian`
 *    inserts at a date-line crossing landed on the WESTERN edge and the segment
 *    reaching them was drawn straight back across the whole map. Measured on
 *    the built page: a full-width band through Wrangel Island at 71 N and
 *    another through Fiji at 17 S — the only two Natural Earth 1:110m land
 *    polygons that straddle the line — the Pacific transit drawn across Africa
 *    and Asia, and the U.S. 7th Fleet area drawn inside out over the Atlantic.
 * 2. A ring split at the seam became two open subpaths, and SVG closes each one
 *    with a straight chord back to its own first point. Across Russia that
 *    chord was a diagonal band from central Siberia to the Bering Strait.
 *
 * These tests work in the two coordinate systems the bug lived between, so they
 * fail if either half is reintroduced.
 */

import { describe, expect, it } from "vitest";
import {
  projectToMap,
  projectionLongitudeDeg,
  splitAtAntimeridian,
  splitRingAtAntimeridian,
  unprojectFromMap,
} from "../src/transit-map";
import { normalizeLongitudeDeg } from "../src/transit-route";

const WIDTH = 1000;
const HEIGHT = 500;
const LEFT_EDGE = 10;
const RIGHT_EDGE = 990;

describe("the two edges of the sheet are not the same point", () => {
  it("keeps +180 on the east edge and -180 on the west edge", () => {
    // The whole bug in one pair of assertions.
    expect(normalizeLongitudeDeg(180)).toBe(-180);
    expect(projectionLongitudeDeg(180)).toBe(180);
    expect(projectionLongitudeDeg(-180)).toBe(-180);
    expect(projectToMap(180, 0, WIDTH, HEIGHT).x).toBeCloseTo(RIGHT_EDGE, 6);
    expect(projectToMap(-180, 0, WIDTH, HEIGHT).x).toBeCloseTo(LEFT_EDGE, 6);
  });

  it("still wraps anything genuinely outside the range", () => {
    expect(projectionLongitudeDeg(190)).toBeCloseTo(-170, 9);
    expect(projectionLongitudeDeg(-190)).toBeCloseTo(170, 9);
    expect(projectToMap(190, 0, WIDTH, HEIGHT).x)
      .toBeCloseTo(projectToMap(-170, 0, WIDTH, HEIGHT).x, 9);
  });

  it("changes nothing anywhere else on the map", () => {
    for (let longitude = -179; longitude <= 179; longitude += 7) {
      expect(projectionLongitudeDeg(longitude), String(longitude)).toBe(longitude);
      const projected = projectToMap(longitude, 12, WIDTH, HEIGHT);
      expect(unprojectFromMap(projected.x, projected.y, WIDTH, HEIGHT).longitudeDeg)
        .toBeCloseTo(longitude, 9);
    }
  });
});

describe("a path crossing the date line", () => {
  /** Every drawn x, in order, for a lon/lat path. */
  const drawnX = (points: Array<[number, number]>) =>
    splitAtAntimeridian(points).map((piece) =>
      piece.map(([longitude]) => projectToMap(longitude, 0, WIDTH, HEIGHT).x));

  it("ends one piece on the east edge and starts the next on the west edge", () => {
    // Westbound across the line, as the Pearl Harbor transit is.
    const pieces = drawnX([[178, 30], [-178, 32]]);
    expect(pieces).toHaveLength(2);
    expect(pieces[0]!.at(-1)!).toBeCloseTo(RIGHT_EDGE, 6);
    expect(pieces[1]![0]!).toBeCloseTo(LEFT_EDGE, 6);
  });

  it("and the other way round for an eastbound crossing", () => {
    const pieces = drawnX([[-178, 30], [178, 32]]);
    expect(pieces).toHaveLength(2);
    expect(pieces[0]!.at(-1)!).toBeCloseTo(LEFT_EDGE, 6);
    expect(pieces[1]![0]!).toBeCloseTo(RIGHT_EDGE, 6);
  });

  it("never draws a piece that spans the whole sheet", () => {
    // This is the shape of the defect: one drawn segment running from one edge
    // to the other. No piece of a short crossing may be wider than the small
    // number of degrees it actually covers.
    for (const path of [
      [[176, 71.4], [-176, 71.3]] as Array<[number, number]>,
      [[178.6, -16.5], [-179.9, -16.6]] as Array<[number, number]>,
      [[170, 40], [-170, 45], [-160, 50]] as Array<[number, number]>,
    ]) {
      for (const piece of drawnX(path)) {
        const span = Math.max(...piece) - Math.min(...piece);
        expect(span, JSON.stringify(path)).toBeLessThan(WIDTH / 4);
      }
    }
  });
});

describe("a shape whose published limit IS the date line", () => {
  it("stays in one piece and stays on the east edge", () => {
    // The U.S. 7th Fleet box: 68 E to the International Date Line. Its eastern
    // edge is a column of +180 vertices, and the splitter used to normalise
    // each of them to -180 and then "fix" the 248-degree jump it had just
    // invented, cutting the box into pieces that spanned the whole map.
    const box: Array<[number, number]> = [
      [68, 50], [180, 50], [180, -60], [68, -60], [68, 50],
    ];
    const pieces = splitAtAntimeridian(box);
    expect(pieces).toHaveLength(1);
    const drawn = pieces[0]!.map(([longitude]) => projectToMap(longitude, 0, WIDTH, HEIGHT).x);
    expect(Math.min(...drawn)).toBeGreaterThan(WIDTH / 2);
    expect(Math.max(...drawn)).toBeCloseTo(RIGHT_EDGE, 6);
  });

  it("still splits a shape that genuinely runs past the line", () => {
    const across: Array<[number, number]> = [[170, 10], [-170, 10], [-170, -10], [170, -10], [170, 10]];
    expect(splitAtAntimeridian(across).length).toBeGreaterThan(1);
  });
});

describe("a filled ring crossing the date line", () => {
  /**
   * Wrangel Island in miniature: a closed ring straddling the line, wound so it
   * starts and ends on the eastern side.
   */
  const ring: Array<[number, number]> = [
    [178, 71], [179.5, 71.2], [-179, 71.3], [-177, 71.1],
    [-177, 70.8], [-179, 70.7], [179.5, 70.6], [178, 70.8], [178, 71],
  ];

  it("comes back as two pieces, each with both ends on the same edge", () => {
    const pieces = splitRingAtAntimeridian(ring);
    expect(pieces).toHaveLength(2);
    for (const piece of pieces) {
      const first = projectToMap(piece[0]![0], piece[0]![1], WIDTH, HEIGHT).x;
      const last = projectToMap(piece.at(-1)![0], piece.at(-1)![1], WIDTH, HEIGHT).x;
      // Both ends on the same edge is what makes the implicit closing line run
      // ALONG the edge instead of as a chord through the middle of the map.
      expect(Math.abs(first - last), JSON.stringify(piece)).toBeLessThan(1e-6);
      expect([LEFT_EDGE, RIGHT_EDGE].some((edge) => Math.abs(first - edge) < 1e-6)).toBe(true);
    }
  });

  it("joins the head and the tail, because a ring's end is its own beginning", () => {
    // splitAtAntimeridian alone gives THREE pieces for this ring: up to the
    // first crossing, the far side, and back from the second crossing. Two of
    // those are the same piece of land.
    expect(splitAtAntimeridian(ring)).toHaveLength(3);
    expect(splitRingAtAntimeridian(ring)).toHaveLength(2);
  });

  it("leaves an open path alone", () => {
    const open: Array<[number, number]> = [[170, 10], [178, 11], [-178, 12], [-170, 13]];
    expect(splitRingAtAntimeridian(open)).toEqual(splitAtAntimeridian(open));
  });

  it("leaves a ring that never crosses the line alone", () => {
    const inland: Array<[number, number]> = [[10, 10], [20, 10], [20, 20], [10, 20], [10, 10]];
    expect(splitRingAtAntimeridian(inland)).toHaveLength(1);
    expect(splitRingAtAntimeridian(inland)[0]).toHaveLength(inland.length);
  });
});
