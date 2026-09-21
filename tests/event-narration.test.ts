import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import bedManifest from "../media/event-charts/narration/bed-manifest.json";
import script from "../narration/event-charts.json";
import events from "../data/events.json";
import {
  AnchorCurve,
  buildCurve,
  narrationBed,
  orbitDecayAnchors,
  type AnchorReplay,
  type BedScene,
} from "../src/event-narration";

/**
 * The narrated walkthrough over the Starlink chart, checked where it can be checked without
 * a browser: the bed that was stitched, the anchors derived from the shipped catalogue, and
 * the curve that joins them.
 *
 * The load-bearing one is THE SEPARATION TEST. Sean asked for a voice-over that walks a
 * reader through this chart, and the sentence the whole clip turns on is "watch the traces
 * separate". If the anchor for that line drifts off the hour the two families actually part
 * — because the catalogue republished, because someone retimed the bed, because an anchor
 * was edited by hand — the clip still plays, still sounds fine, and teaches the wrong thing.
 * Nothing about that failure is visible in a screenshot of a still frame. So the traces are
 * measured directly out of `data/events.json`, at the two ends of the window that line is
 * spoken over, and the gap between the families has to have opened across it.
 */

const SCENE = "starlink-2022-chart";
const PICTURE_LEAD_SECONDS = 0.2;

const bed = narrationBed(SCENE) as BedScene;

const replay = (events as { events: Array<Record<string, any>> }).events
  .find((event) => event.id === "starlink-2022")!.replay as AnchorReplay;

/** Perigee and apogee of one object at an arbitrary hour, or null if it is not on the plot. */
function altitudeAt(object: AnchorReplay["objects"][number], hour: number): [number, number] | null {
  const samples = object.samples;
  const first = samples[0];
  const last = samples[samples.length - 1];
  if (!first || !last || hour < first[0] || hour > last[0]) return null;
  for (let i = 1; i < samples.length; i += 1) {
    const b = samples[i]!;
    if (b[0] < hour) continue;
    const a = samples[i - 1]!;
    if (b[0] === a[0]) return [a[1], a[2]];
    const t = (hour - a[0]) / (b[0] - a[0]);
    return [a[1] + t * (b[1] - a[1]), a[2] + t * (b[2] - a[2])];
  }
  return null;
}

/** Median perigee across whichever objects of one outcome are on the plot at that hour. */
function medianPerigee(outcome: "lost" | "raised", hour: number): number | null {
  const values = replay.objects
    .filter((object) => object.outcome === outcome)
    .map((object) => altitudeAt(object, hour))
    .filter((pair): pair is [number, number] => pair !== null)
    .map((pair) => pair[0])
    .sort((a, b) => a - b);
  if (!values.length) return null;
  const middle = Math.floor(values.length / 2);
  return values.length % 2 ? values[middle]! : (values[middle - 1]! + values[middle]!) / 2;
}

describe("the stitched narration bed", () => {
  it("ships, and is just over the minute Sean asked for", () => {
    // "I think if we timed things correctly, I could have a voice over that walks users
    // through these" — and, explicitly, just over a minute rather than longer.
    expect(bed).toBeTruthy();
    expect(bed.ok).toBe(true);
    expect(bed.bedSeconds).toBeGreaterThan(60);
    expect(bed.bedSeconds).toBeLessThan(70);
  });

  it("has the mp3 it names", () => {
    const file = fileURLToPath(new URL(`../media/event-charts/narration/${bed.file}`, import.meta.url));
    expect(existsSync(file)).toBe(true);
  });

  it("puts every line where the filter graph said, measured off the delivered file", () => {
    // `measuredStartSeconds` was read back out of the mp3 with silencedetect. A bed whose
    // lines have drifted is a bed whose anchors are pointing at the wrong sentences.
    for (const line of bed.lines) {
      const expected = line.startSeconds;
      expect(Math.abs(line.measuredStartSeconds - expected)).toBeLessThanOrEqual(0.12);
    }
  });

  it("runs its lines in order, with a gap between each", () => {
    for (let i = 1; i < bed.lines.length; i += 1) {
      const previous = bed.lines[i - 1]!;
      const line = bed.lines[i]!;
      expect(line.startSeconds).toBeGreaterThan(previous.startSeconds + previous.audioSeconds);
    }
    const last = bed.lines[bed.lines.length - 1]!;
    expect(bed.bedSeconds).toBeGreaterThan(last.startSeconds + last.audioSeconds);
  });

  it("says exactly what the script says, word for word", () => {
    // The transcript on the page is rendered from the bed manifest. If the manifest could
    // drift from the script the audio was rendered from, the written record of a spoken
    // fact would stop matching the spoken one, which is the failure the transcript exists
    // to prevent.
    const written = new Map(script.lines.map((line) => [line.id, line.text]));
    expect(bed.lines).toHaveLength(script.lines.filter((line) => line.scene === SCENE).length);
    for (const line of bed.lines) {
      expect(line.text).toBe(written.get(line.id));
    }
  });
});

describe("the anchors, derived from the shipped catalogue", () => {
  const anchors = orbitDecayAnchors(SCENE, replay)!;

  it("derives one for every line, in order", () => {
    expect(anchors).toHaveLength(bed.lines.length);
    anchors.forEach((anchor, index) => expect(anchor.line).toBe(bed.lines[index]!.id));
    for (let i = 1; i < anchors.length; i += 1) {
      expect(anchors[i]!.at).toBeGreaterThan(anchors[i - 1]!.at);
    }
  });

  it("opens on the window's own start", () => {
    expect(anchors[0]!.at).toBe(0);
  });

  it("puts the storm line on a G1 interval, on the day after the window opens", () => {
    const storm = anchors[2]!.at;
    expect(storm).toBeGreaterThanOrEqual(anchors[1]!.at);
    const index = replay.driver.hours.indexOf(storm);
    expect(index).toBeGreaterThanOrEqual(0);
    expect(replay.driver.kp[index]!).toBeGreaterThanOrEqual(5);
    // and it is the FIRST such interval after the day boundary, not merely one of them
    for (let i = 0; i < index; i += 1) {
      if (replay.driver.hours[i]! >= anchors[1]!.at) {
        expect(replay.driver.kp[i]!).toBeLessThan(5);
      }
    }
  });

  it("puts the mechanism line on the first element set the chart has", () => {
    const firsts = replay.objects.map((object) => object.samples[0]![0]);
    expect(anchors[3]!.at).toBe(Math.min(...firsts));
  });

  it("puts the reentry line on the last object the catalogue lost", () => {
    const lasts = replay.objects
      .filter((object) => object.outcome === "lost")
      .map((object) => object.samples[object.samples.length - 1]![0]);
    expect(anchors[5]!.at).toBe(Math.max(...lasts));
  });

  it('anchors "watch the traces separate" on the first frame both families are drawn', () => {
    const at = anchors[4]!.at;
    const drawn = (outcome: "lost" | "raised", hour: number) => replay.objects
      .some((object) => object.outcome === outcome && altitudeAt(object, hour) !== null);
    expect(drawn("raised", at)).toBe(true);
    expect(drawn("lost", at)).toBe(true);
    // and not one hour earlier
    expect(drawn("raised", at - 0.01) && drawn("lost", at - 0.01)).toBe(false);
  });

  it("separates the traces WHILE that line is being spoken", () => {
    // The whole clip turns on this. Line 05 runs for its own measured duration from its own
    // measured start; the picture leads the voice by a fixed fraction of a second. Take the
    // chart's hour at the first word and at the last, and the two families must be further
    // apart at the end than at the start — measured off the catalogue, not asserted.
    const anchorList = orbitDecayAnchors(SCENE, replay)!;
    const curve = buildCurve(bed, anchorList, 720)!;
    const line = bed.lines[4]!;
    const opens = curve.at(line.startSeconds);
    const closes = curve.at(line.startSeconds + line.audioSeconds);
    expect(opens).toBeGreaterThanOrEqual(anchorList[4]!.at);

    const gapAt = (hour: number) => {
      const raised = medianPerigee("raised", hour);
      const lost = medianPerigee("lost", hour);
      expect(raised).not.toBeNull();
      expect(lost).not.toBeNull();
      return raised! - lost!;
    };
    const before = gapAt(opens);
    const after = gapAt(closes);
    expect(before).toBeGreaterThan(0);
    // Not "a bit wider": the sentence lasts nine and a half seconds and the picture has to
    // do visible work across it.
    expect(after).toBeGreaterThan(before * 2);
  });
});

describe("the curve from audio seconds to chart hours", () => {
  const anchors = orbitDecayAnchors(SCENE, replay)!;
  const endsAt = 720;
  const curve = buildCurve(bed, anchors, endsAt)!;

  it("is built", () => {
    expect(curve).toBeInstanceOf(AnchorCurve);
  });

  it("passes through every anchor exactly, a beat ahead of the word", () => {
    // Line 01's anchor is the window's own origin and is the curve's first knot, so it is
    // met at t=0 rather than a fifth of a second before a sound that has not started.
    expect(curve.at(0)).toBeCloseTo(anchors[0]!.at, 6);
    for (let i = 1; i < anchors.length; i += 1) {
      const at = bed.lines[i]!.startSeconds - PICTURE_LEAD_SECONDS;
      expect(curve.at(at)).toBeCloseTo(anchors[i]!.at, 6);
    }
  });

  it("never runs the chart backwards, and never stands still", () => {
    let previous = -1;
    let stalls = 0;
    for (let t = 0; t <= bed.bedSeconds; t += 0.02) {
      const value = curve.at(t);
      expect(value).toBeGreaterThanOrEqual(previous);
      // A picture that does not move for a fifth of a second while a voice runs over it is
      // the dead air this whole timeline exists to avoid.
      if (t > 0 && value - previous < 1e-6) stalls += 1;
      previous = value;
    }
    expect(stalls).toBe(0);
  });

  it("starts at the top of the window and finishes on the chart's last frame", () => {
    expect(curve.at(0)).toBe(0);
    expect(curve.at(bed.bedSeconds)).toBeCloseTo(endsAt, 6);
    expect(curve.at(bed.bedSeconds + 5)).toBe(endsAt);
    expect(curve.at(-1)).toBe(0);
  });

  it("refuses an anchor list the chart cannot run forwards through", () => {
    const backwards = anchors.map((anchor, index) => (index === 4 ? { ...anchor, at: 10 } : anchor));
    expect(buildCurve(bed, backwards, endsAt)).toBeNull();
  });

  it("refuses a line the bed does not carry", () => {
    const missing = anchors.map((anchor, index) =>
      (index === 3 ? { ...anchor, line: "no-such-line" } : anchor));
    expect(buildCurve(bed, missing, endsAt)).toBeNull();
  });
});

describe("the bed manifest the page is built from", () => {
  it("names the tool that made it, and the voice", () => {
    expect(bedManifest.generator).toBe("tools/narrate_event_bed.py");
    expect(bedManifest.voice).toContain("9M1l09pkVunOZDmYq0Ms");
  });
});
