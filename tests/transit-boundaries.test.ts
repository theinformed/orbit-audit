/**
 * The areas-of-responsibility overlay.
 *
 * The point of these tests is not that the polygons are pretty. It is that the
 * overlay never asserts a boundary nobody published — every area either comes
 * from geometry the command published itself, or is drawn from prose with each
 * edge tagged for whether the source actually named a line.
 *
 * Two of these pin corrections that research forced, and they exist so the
 * errors cannot come back:
 *
 * 1. USINDOPACOM was drawn from a widely-repeated sentence that could not be
 *    sourced to any primary command page. The overlay was withdrawn.
 * 2. U.S. 5th Fleet was quoted with wording that appears in no capture of the
 *    command's own site.
 */

import { describe, expect, it } from "vitest";
import { AOR_BOUNDARIES } from "../src/data/aor-boundaries";
import { projectToMap, splitRingAtAntimeridian } from "../src/transit-map";
import { BOUNDARY_CHIP_LABEL_IDS, boundaryChipLabel } from "../src/transit-planner";
import aorReferenceData from "../data/aor_reference.json";

const reference = aorReferenceData as unknown as {
  combatantCommands: Array<{ id: string; drawable: boolean; statement: string; drawabilityNote: string }>;
  numberedFleets: Array<{ id: string; drawable: boolean; statement: string; drawabilityNote: string }>;
  boundaryOverlay: { publicationCadence: string; stability: string };
};

describe("what is drawn", () => {
  it("draws only areas the reference file marks drawable, and all of them", () => {
    const drawn = new Set(AOR_BOUNDARIES.map((boundary) => boundary.id));
    const expected = new Set([
      ...reference.combatantCommands.filter((entry) => entry.drawable).map((entry) => entry.id),
      ...reference.numberedFleets.filter((entry) => entry.drawable).map((entry) => entry.id),
    ]);
    expect([...drawn].sort()).toEqual([...expected].sort());
  });

  it("gives every area a citation and real geometry", () => {
    expect(AOR_BOUNDARIES.length).toBeGreaterThan(0);
    for (const boundary of AOR_BOUNDARIES) {
      expect(boundary.source, boundary.id).toMatch(/^https?:\/\//);
      expect(boundary.statement.length, boundary.id).toBeGreaterThan(40);
      expect(boundary.rings.length, boundary.id).toBeGreaterThan(0);
      for (const ring of boundary.rings) {
        expect(ring.length, boundary.id).toBeGreaterThanOrEqual(4);
        for (const [longitude, latitude] of ring) {
          expect(Math.abs(longitude)).toBeLessThanOrEqual(180.001);
          expect(Math.abs(latitude)).toBeLessThanOrEqual(90.001);
        }
      }
    }
  });

  it("tags every edge of every prose extent, and tags nothing on a country selection", () => {
    for (const boundary of AOR_BOUNDARIES) {
      if (boundary.kind === "numbered-fleet") {
        expect(boundary.edges, boundary.id).toBeTruthy();
        expect(Object.keys(boundary.edges!).sort()).toEqual(["east", "north", "south", "west"]);
        for (const [side, edge] of Object.entries(boundary.edges!)) {
          expect(["published", "published-numeric", "indefinite"], `${boundary.id}.${side}`)
            .toContain(edge.kind);
          expect(edge.note.length, `${boundary.id}.${side}`).toBeGreaterThan(20);
        }
      } else {
        // A country selection has no edges of its own: its boundary is the
        // outline of the states the command assigned to it.
        expect(boundary.edges, boundary.id).toBeNull();
      }
    }
  });
});

describe("provenance", () => {
  it("records where a command published its own geometry", () => {
    const selfPublished = AOR_BOUNDARIES.filter((boundary) => boundary.geometrySource);
    expect(selfPublished.map((boundary) => boundary.id).sort()).toEqual(["usafricom", "useucom"]);
    for (const boundary of selfPublished) {
      expect(boundary.geometrySource!).toMatch(/^https:\/\/www\.(africom|eucom)\.mil\//);
      expect(boundary.caveat, boundary.id).toBeTruthy();
    }
  });

  it("keeps the one numeric coordinate the Navy has ever published", () => {
    // U.S. 7th Fleet's 2013 fact sheet: "from the International Date Line to the
    // 68th meridian east". No other fleet boundary has ever been published as a
    // coordinate, so if this tag disappears something has been flattened.
    const seventh = AOR_BOUNDARIES.find((boundary) => boundary.id === "c7f")!;
    expect(seventh.edges!.west!.kind).toBe("published-numeric");
    expect(seventh.edges!.west!.note).toContain("68th meridian east");
    const longitudes = seventh.rings.flat().map(([longitude]) => longitude);
    expect(Math.min(...longitudes)).toBeCloseTo(68, 5);
    expect(Math.max(...longitudes)).toBeCloseTo(180, 5);
  });

  it("still marks 7th Fleet's north and south open, because landmarks are not lines", () => {
    const seventh = AOR_BOUNDARIES.find((boundary) => boundary.id === "c7f")!;
    expect(seventh.edges!.north!.kind).toBe("indefinite");
    expect(seventh.edges!.south!.kind).toBe("indefinite");
  });

  it("excluded Israel from the European command overlay, and framed it as an assignment change", () => {
    // EUCOM's map file carries the GEOMETRY, which did not move; its live
    // country-list page carries the ASSIGNMENTS, and Israel's moved to CENTCOM
    // on 15 January 2021. Those are different kinds of change on different
    // timescales, and the caveat must not describe them as sources in conflict.
    const eucom = AOR_BOUNDARIES.find((boundary) => boundary.id === "useucom")!;
    expect(eucom.caveat!).toMatch(/Israel/);
    expect(eucom.caveat!).toMatch(/Central Command/);
    expect(eucom.caveat!).toMatch(/15 January 2021/);
    expect(eucom.caveat!).toMatch(/not in\s+conflict/);
    expect(eucom.caveat!).not.toMatch(/stale|disagree|contradict/i);
    // Israel sits near 35E/31N. No ring may enclose that area.
    const nearIsrael = eucom.rings.flat().filter(([longitude, latitude]) =>
      Math.abs(longitude - 35) < 1.5 && Math.abs(latitude - 31.5) < 1.5);
    expect(nearIsrael).toHaveLength(0);
  });
});

describe("corrections that must not come back", () => {
  it("does not draw USINDOPACOM from an unattributed sentence", () => {
    // The phrasing "from the waters off the west coast of the U.S. to the
    // western border of India, and from Antarctica to the North Pole" is
    // repeated everywhere and could not be sourced to any primary command page.
    // An overlay was built on it and then withdrawn.
    expect(AOR_BOUNDARIES.find((boundary) => boundary.id.startsWith("usindopacom"))).toBeUndefined();
    const entry = reference.combatantCommands.find((command) => command.id === "usindopacom")!;
    expect(entry.drawable).toBe(false);
    expect(entry.statement).not.toMatch(/western border of India/);
    expect(entry.drawabilityNote).toMatch(/could not be sourced/i);
  });

  it("quotes 5th Fleet as its own command actually publishes it", () => {
    const entry = reference.numberedFleets.find((fleet) => fleet.id === "c5f")!;
    // The replaced string. It is widely repeated and appears in no capture of
    // the command's own site.
    expect(entry.statement).not.toMatch(/North Arabian Sea/);
    expect(entry.statement).toMatch(/Strait of Hormuz/);
    expect(entry.statement).toMatch(/parts of the Indian Ocean/);
    const fleet = AOR_BOUNDARIES.find((boundary) => boundary.id === "c5f")!;
    expect(fleet.edges!.east!.kind).toBe("indefinite");
  });

  it("names the Defense Planning Guidance as the annual vehicle, and keeps the UCP fact separate", () => {
    const cadence = reference.boundaryOverlay.publicationCadence;
    expect(cadence).toMatch(/Defense Planning Guidance/);
    expect(cadence).toMatch(/not a public document/i);
    expect(cadence).toMatch(/10 U\.S\.C\. 161\(b\)\(1\)/);
    // The absence of an annual published map is a classification fact about the
    // vehicle, NOT evidence that the public record has drifted.
    expect(cadence).toMatch(/not evidence that the public record has drifted/i);
  });

  it("reads the age of a published map as stability rather than staleness", () => {
    const stability = reference.boundaryOverlay.stability;
    // The distinction that makes the whole thing coherent.
    expect(stability).toMatch(/GEOGRAPHIC BOUNDARIES/);
    expect(stability).toMatch(/COUNTRY ASSIGNMENTS/);
    // Both verified changes are assignment moves, not line moves.
    expect(stability).toMatch(/15 January 2021/);
    expect(stability).toMatch(/17 June 2025/);
    expect(stability).toMatch(/Neither redrew a line/);
    // Age is evidence FOR the data.
    expect(stability).toMatch(/evidence\s+that the lines have held/);
    // And no invented date: Sean offered "pre-2017" as recollection, not citation.
    expect(stability).toMatch(/no\s+public source was found that states one/);
    expect(stability).not.toMatch(/2017/);
  });

  it("attributes the 6th Fleet area to the command that publishes it", () => {
    const entry = reference.numberedFleets.find((fleet) => fleet.id === "c6f")!;
    expect(entry.drawabilityNote).toMatch(/NAVEUR-NAVAF/);
    const fleet = AOR_BOUNDARIES.find((boundary) => boundary.id === "c6f")!;
    expect(fleet.name).toMatch(/Naval Forces Europe-Africa/);
  });

  it("keeps 3rd Fleet undrawn, and records that the boundary was removed rather than never stated", () => {
    expect(AOR_BOUNDARIES.find((boundary) => boundary.id === "c3f")).toBeUndefined();
    const entry = reference.numberedFleets.find((fleet) => fleet.id === "c3f")!;
    expect(entry.drawabilityNote).toMatch(/removed rather than never stated/);
    expect(entry.drawabilityNote).toMatch(/no published Date Line exception/i);
  });
});

/**
 * WHERE the area is drawn, and not only whose sentence it came from.
 *
 * Everything above this point checks provenance, and all of it passed while the
 * U.S. 7th Fleet area was being drawn over the Atlantic Ocean. Its published
 * eastern limit is the International Date Line; the +180 vertex projected onto
 * the WESTERN edge of the map (see `projectionLongitudeDeg`), and the box turned
 * inside out. A correctly cited area in the wrong ocean is worse than no area at
 * all on a Navy tool, so the drawn extent is pinned here too.
 */
describe("where each area is actually drawn", () => {
  const WIDTH = 1000;
  const HEIGHT = 500;
  const x = (longitudeDeg: number) => projectToMap(longitudeDeg, 0, WIDTH, HEIGHT).x;

  it("puts 7th Fleet between the 68th meridian east and the Date Line, and nowhere else", () => {
    const seventh = AOR_BOUNDARIES.find((boundary) => boundary.id === "c7f")!;
    const drawn = seventh.rings.flat().map(([longitude]) => x(longitude));
    expect(Math.min(...drawn)).toBeCloseTo(x(68), 6);
    expect(Math.max(...drawn)).toBeCloseTo(x(180), 6);
    // The western Pacific half of the sheet. Nothing may be drawn in the
    // Atlantic, which is where this area used to appear.
    expect(Math.min(...drawn)).toBeGreaterThan(WIDTH / 2);
  });

  it("draws every area inside the box its own coordinates describe", () => {
    for (const boundary of AOR_BOUNDARIES) {
      const longitudes = boundary.rings.flat().map(([longitude]) => longitude);
      const drawn = longitudes.map(x);
      expect(Math.min(...drawn), boundary.id).toBeCloseTo(x(Math.min(...longitudes)), 6);
      expect(Math.max(...drawn), boundary.id).toBeCloseTo(x(Math.max(...longitudes)), 6);
    }
  });

  it("splits a ring that touches the Date Line into pieces that close on one edge", () => {
    // A filled ring cut at the seam has to have both ends of each piece on the
    // same map edge, or SVG closes it with a chord across the middle of the map.
    for (const boundary of AOR_BOUNDARIES) {
      for (const ring of boundary.rings) {
        for (const piece of splitRingAtAntimeridian(ring)) {
          const first = x(piece[0]![0]);
          const last = x(piece.at(-1)![0]);
          if (splitRingAtAntimeridian(ring).length === 1) continue;
          expect(Math.abs(first - last), boundary.id).toBeLessThan(1e-6);
        }
      }
    }
  });

  it("gives every area a label short enough to be a chip", () => {
    for (const boundary of AOR_BOUNDARIES) {
      const label = boundaryChipLabel(boundary);
      expect(BOUNDARY_CHIP_LABEL_IDS, `${boundary.id} has no short label`).toContain(boundary.id);
      expect(label.length, boundary.id).toBeLessThanOrEqual(12);
    }
  });
});
