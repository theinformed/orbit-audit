/// <reference types="vite/client" />
/**
 * The shape of the page: zoom, and how much prose it opens with.
 *
 * Sean, 2026-08-19, on the shipped Transit visibility page: "it has WAY too
 * much text. Fucking ridiculous. If the text is important, some of it needs to
 * be in popups for definitions, or in places we can collapse... The map isn't
 * zoomable. Why?"
 *
 * Measured before the change: 1,394 words rendered at rest on a 1440 px
 * viewport, and a map with a fixed viewBox and no zoom affordance of any kind.
 *
 * Two things are pinned here, in the only ways a DOM-less unit suite can pin
 * them. The runtime measurement — the actual word count of the mounted planner
 * and the actual transform on the world group — is in
 * `tools/transit-planner-smoke.ts`, which mounts the real component in a real
 * browser; this file pins the source-level decisions that produce it, so the
 * prose cannot quietly climb back out of its folds.
 *
 * NOTHING HERE WAS DELETED. Every sentence that left the resting page is inside
 * one of the three folds this file asserts, in the same file it was always in.
 */

import { describe, expect, it } from "vitest";
import plannerSource from "../src/transit-planner.ts?raw";
import { clampView, MAXIMUM_MAP_SCALE, MINIMUM_MAP_SCALE } from "../src/transit-map";
import { geostationaryReachDeg } from "../src/transit-planner";
import { audienceProfile } from "../src/transit-audience";

describe("the map can be zoomed", () => {
  it("has a scale range wide enough to check a leg against a coast", () => {
    expect(MINIMUM_MAP_SCALE).toBe(1);
    expect(MAXIMUM_MAP_SCALE).toBeGreaterThanOrEqual(8);
  });

  it("refuses a scale below the whole world and above the useful limit", () => {
    expect(clampView({ scale: 0.2, translateX: 0, translateY: 0 }, 1000, 500).scale).toBe(MINIMUM_MAP_SCALE);
    expect(clampView({ scale: 900, translateX: 0, translateY: 0 }, 1000, 500).scale).toBe(MAXIMUM_MAP_SCALE);
  });

  it("never lets the world be dragged off the frame", () => {
    // At 1x there is nowhere to pan to; at 4x the world may be pulled left and
    // up by three frame widths and no further, or the reader is looking at void.
    expect(clampView({ scale: 1, translateX: 300, translateY: -80 }, 1000, 500))
      .toEqual({ scale: 1, translateX: 0, translateY: 0 });
    expect(clampView({ scale: 4, translateX: -99_999, translateY: -99_999 }, 1000, 500))
      .toEqual({ scale: 4, translateX: -3000, translateY: -1500 });
    expect(clampView({ scale: 4, translateX: 50, translateY: 50 }, 1000, 500))
      .toEqual({ scale: 4, translateX: 0, translateY: 0 });
  });
});

describe("the mask's consequence is computed, not typed", () => {
  it("reproduces the three figures that used to be a paragraph", () => {
    // "At 0 degrees a geostationary satellite stays visible to 81.3 degrees of
    // arc away. At 5 that shrinks to 76.3, and at 10 to 71.4." Same numbers,
    // now read off the control the reader is holding.
    expect(geostationaryReachDeg(0)).toBeCloseTo(81.3, 1);
    expect(geostationaryReachDeg(5)).toBeCloseTo(76.3, 1);
    expect(geostationaryReachDeg(10)).toBeCloseTo(71.4, 1);
  });

  it("falls monotonically as the mask rises, which is the whole lesson", () => {
    for (let mask = 0; mask < 30; mask += 1) {
      expect(geostationaryReachDeg(mask + 1), String(mask)).toBeLessThan(geostationaryReachDeg(mask));
    }
  });
});

describe("prose is a cost", () => {
  it("folds the standing disclosure rather than deleting a word of it", () => {
    expect(plannerSource).toContain('<details class="transit-disclosure"');
    // Every clause that used to be open on the page is still in this file.
    for (const sentence of [
      "not an operational ephemeris",
      "manoeuvres are invisible to them",
      "terminal is certified, or whether a link would close",
      "Where the public record is silent, this planner is silent",
      "different answers to different",
      "read the source label on every row",
    ]) {
      expect(plannerSource, sentence).toContain(sentence);
    }
  });

  it("folds the lesson and keeps all three of its claims", () => {
    expect(plannerSource).toContain('<details class="transit-lesson"');
    const lesson = audienceProfile("public").lesson!;
    expect(lesson.points).toHaveLength(3);
    expect(lesson.points.map((point) => point.title)).toEqual([
      "Height sets how much of the Earth a satellite can see at once",
      "A satellite low on your horizon is not usable, and the mask is where you say so",
      "Latitude decides whether a geostationary satellite is any use at all",
    ]);
  });

  it("folds the fleet and combatant-command reference, sources intact", () => {
    expect(plannerSource).toContain('<details class="transit-block transit-reference-fold"');
    expect(plannerSource).toContain("The published wording, quoted");
    expect(plannerSource).toContain("whatIsNotDrawn");
  });

  it("puts definitions on the term instead of in a paragraph", () => {
    // Each of these replaced a hint paragraph that was open on the page.
    for (const label of [
      "Elevation mask",
      "Track",
      "Times in",
      "Entire transit",
      "Areas of responsibility",
      "Deliberately absent",
    ]) {
      expect(plannerSource, label).toContain(`term("${label}"`);
    }
    // The definition must be IN the element, not in a title attribute: a title
    // is unreachable by keyboard and silent to a screen reader.
    expect(plannerSource).toContain('class="transit-term-card" role="note"');
  });

  it("keeps the standfirst to one sentence", () => {
    const standfirst = audienceProfile("public").standfirst;
    expect(standfirst.split(/\s+/).length).toBeLessThanOrEqual(20);
  });
});
