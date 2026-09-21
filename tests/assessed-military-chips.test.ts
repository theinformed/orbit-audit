import { describe, expect, it } from "vitest";

import {
  classificationBasisEvidence,
  classificationChipEvidence,
  missionFacet,
  satelliteChips,
} from "../src/main";

/**
 * ASSESSED IS NOT DOCUMENTED, AND THE CHIP HAS TO SHOW IT.
 *
 * The owner filtered the catalog by MILSATCOM and got 101 objects, 93 of them
 * American and none of them Chinese or Russian, and asked whether we know of no
 * PLA military communications satellites. We do — Shentong-2 flies as
 * "CHINASAT 2A", Blagovest and Garpun as "COSMOS 25nn" — and the pipeline now
 * publishes them. What it must never do is publish them as if they were as well
 * established as Skynet, which has a gov.uk page behind it. Nobody prints a
 * fact sheet for Shentong-2; what exists is Gunter Krebs and the China Space
 * Report reading the same evidence the same way.
 *
 * `classificationBasis: "assessed"` is that distinction, and this file pins the
 * two halves of it: the chip must draw CLAIMED, and the sentence must say why.
 */
describe("the assessed evidence class", () => {
  it("draws as claimed, never as corroborated", () => {
    // The single assertion this whole change rests on. If "assessed" ever
    // joins CORROBORATED_BASES, a Chinese spacecraft whose operator has never
    // said what it does starts looking exactly like a Space Force fact sheet.
    expect(classificationChipEvidence("assessed")).toBe("claimed");
  });

  it("still outranks a bare name match in what it TELLS the reader", () => {
    const assessed = classificationBasisEvidence("assessed");
    expect(assessed).toMatch(/independent analysts/i);
    expect(assessed).toMatch(/No operator or government has published/i);
    // ...and it is a different sentence from the name-pattern one, so a reader
    // comparing two claimed chips can still tell them apart.
    expect(assessed).not.toBe(classificationBasisEvidence("name-pattern"));
  });

  it("marks both chips on an assessed MILSATCOM card as claimed", () => {
    const chinasat2a = { mission: "communications", facet: "milsatcom", sector: "military", basis: "assessed" };
    const chips = satelliteChips(chinasat2a);
    expect(chips).toHaveLength(1);
    expect(chips[0]!.label).toBe("MILSATCOM");
    expect(chips[0]!.evidence).toBe("claimed");
    expect(chips[0]!.why).toMatch(/independent analysts/i);
  });

  it("leaves a documented allied programme corroborated", () => {
    // Skynet 5A, after the entry moved from a name prefix onto catalog numbers.
    const skynet = { mission: "communications", facet: "milsatcom", sector: "military", basis: "norad-id" };
    expect(satelliteChips(skynet)[0]!.evidence).toBe("corroborated");
  });
});

/**
 * THE TJS CASE, WHICH IS WHY THE CHIP GUARD READS THE FACET.
 *
 * China announces the 25 Tongxin Jishu Shiyan spacecraft as communications-
 * technology experiments; independent analysts read individual flights as
 * signals intelligence or missile early warning. Both readings are military and
 * they disagree about the mission, so the catalog records `mission: "other"`
 * with `sector: "military"` — the OTHER MILITARY facet — and claims no mission.
 *
 * `satelliteChips` used to suppress the category chip whenever `mission` was
 * "other", which drew those cards NO chips at all and threw away the one fact
 * the site had about them. The rule it wanted was about the facet: "Other /
 * unverified" is a chip saying nothing, "Other military" is not.
 */
describe("a military object with no established mission", () => {
  const tjs = { mission: "other", facet: missionFacet({ mission: "other", sector: "military" } as never), sector: "military", basis: "assessed" };

  it("is filed under OTHER MILITARY, not under MILSATCOM", () => {
    expect(tjs.facet).toBe("military-other");
  });

  it("still gets a chip, because the sector is a fact even where the mission is not", () => {
    const chips = satelliteChips(tjs);
    expect(chips.map((chip) => chip.label)).toEqual(["Other military"]);
    expect(chips[0]!.evidence).toBe("claimed");
  });

  it("draws nothing at all when the sector is unknown too", () => {
    expect(satelliteChips({ mission: "other", facet: "other", sector: "unknown", basis: "unclassified" })).toHaveLength(0);
  });
});
