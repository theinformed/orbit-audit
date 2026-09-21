/**
 * The narration lane's own regression tests.
 *
 * These check the two things that cannot be fixed after the fact and the one thing a
 * reader would never find out about on their own:
 *
 *   1. FIT. A spoken line longer than the beat it is spoken over is wrong the moment the
 *      audio exists, and no amount of page work repairs it. The budget is arithmetic on
 *      the clip's own duration, so it is checkable here without touching a media file.
 *   2. ALIGNMENT. The bed manifest carries an onset measured off the delivered mp3 with
 *      silencedetect, not a number the builder asserted. If that measurement ever drifts
 *      from the mark, this fails.
 *   3. THE TRANSCRIPT SAYS WHAT THE VOICE SAYS. The page prints the transcript from the
 *      manifest and the audio was rendered from the script; if the two ever disagree, a
 *      deaf reader is being given different words from a hearing one, silently. That is
 *      exactly the class of defect nobody reports.
 */

import { describe, expect, it } from "vitest";
import bedManifest from "../media/narration-layers/manifest.json";
import script from "../narration/layer-pages.json";
import facts from "../narration/layer-narration-facts.json";
import { narratedClips } from "../src/layer-narration";

type ScriptLine = { id: string; clip?: string; text: string; words?: number; wordBudget?: number };

const scriptLines = script.lines as ScriptLine[];
const byId = new Map(scriptLines.map((line) => [line.id, line]));

/** The same count tools/narrate.py and the scaffold validator use. */
const wordCount = (text: string) => (text.match(/[A-Za-z0-9'’.-]+/g) ?? []).length;

describe("layer-page narration script", () => {
  it("gives every silent layer clip a line", () => {
    for (const clip of facts.clips) {
      expect(byId.has(`layer-${clip.id}`), `no narration line for ${clip.id}`).toBe(true);
    }
  });

  it("keeps every line inside the word budget its own clip's length allows", () => {
    for (const clip of facts.clips) {
      const line = byId.get(`layer-${clip.id}`)!;
      expect(wordCount(line.text), `${clip.id} is over budget`).toBeLessThanOrEqual(clip.wordBudget);
    }
  });

  it("computes the budget from the clip, so a longer clip can never get a shorter line", () => {
    for (const clip of facts.clips) {
      const expected = Math.min(60, Math.floor((clip.clipSeconds - 2.5) * 2.9));
      expect(clip.wordBudget, `${clip.id} budget does not match the stated rule`).toBe(expected);
    }
  });

  it("says of every line whether a model wrote it or the page copy did", () => {
    for (const line of scriptLines) {
      if (!line.clip) continue;
      expect(["local-35b", "deterministic"]).toContain(
        (line as ScriptLine & { source?: string }).source,
      );
    }
  });

  it("writes units out in words, because this text goes into a speech synthesiser", () => {
    // "km" is read "kay em" by some voices and skipped by others; an exponent is simply
    // lost. This is a mispronunciation check, not a style one.
    const unspeakable = /(?<![A-Za-z])(km|cm|MHz|GHz|keV|MeV|nT|nPa|pfu|TECU|dB)(?![A-Za-z])/;
    for (const line of scriptLines) {
      expect(unspeakable.test(line.text), `${line.id} carries an unspeakable abbreviation`).toBe(false);
    }
  });
});

describe("layer-page narration audio", () => {
  const beds = bedManifest.clips as Array<{
    clip: string;
    videoSeconds: number;
    bedSeconds: number;
    bedMatchesVideo: boolean;
    allOnTime: boolean;
    worstOffsetSeconds: number;
    offsetToleranceSeconds: number;
    lines: Array<{
      id: string;
      text: string;
      beatStartSeconds: number;
      audioSeconds: number;
      overrunSeconds: number;
      fits: boolean;
      leadInSeconds: number;
      expectedVoiceAtSeconds: number;
      measuredStartSeconds: number;
      measuredOffsetSeconds: number;
      rawOffsetSeconds: number;
    }>;
  }>;

  it("has at least one bed, or the page shows a control with nothing behind it", () => {
    expect(beds.length).toBeGreaterThan(0);
    expect(narratedClips()).toEqual(beds.map((bed) => bed.clip).sort());
  });

  it("makes every bed exactly as long as the clip it is played against", () => {
    for (const bed of beds) {
      expect(bed.bedMatchesVideo, `${bed.clip} bed is not the length of its clip`).toBe(true);
      expect(Math.abs(bed.bedSeconds - bed.videoSeconds)).toBeLessThanOrEqual(0.25);
    }
  });

  it("never lets a line run past the beat it describes", () => {
    for (const bed of beds) {
      for (const line of bed.lines) {
        expect(line.fits, `${line.id} overruns its beat by ${line.overrunSeconds}s`).toBe(true);
        expect(line.overrunSeconds).toBeLessThanOrEqual(0);
      }
    }
  });

  it("starts every line where its mark says, measured off the delivered file", () => {
    for (const bed of beds) {
      expect(bed.allOnTime, `${bed.clip} has a line off its beat`).toBe(true);
      expect(Math.abs(bed.worstOffsetSeconds)).toBeLessThanOrEqual(bed.offsetToleranceSeconds);
      for (const line of bed.lines) {
        // Against the mark PLUS that line's own attack. A line whose first syllable is a
        // soft consonant opens with up to a tenth of a second under the noise floor; that
        // is the recording, not the placement, and it is measured out of the source file
        // rather than waved away. The raw figure is asserted too, so the correction can
        // never quietly grow to cover a real drift.
        expect(Math.abs(line.measuredStartSeconds - line.expectedVoiceAtSeconds))
          .toBeLessThanOrEqual(bed.offsetToleranceSeconds);
        expect(line.expectedVoiceAtSeconds)
          .toBeCloseTo(line.beatStartSeconds + line.leadInSeconds, 3);
        expect(Math.abs(line.rawOffsetSeconds)).toBeLessThanOrEqual(0.25);
      }
    }
  });

  it("prints a transcript of the words that were actually rendered", () => {
    for (const bed of beds) {
      for (const line of bed.lines) {
        expect(byId.get(line.id)?.text, `${line.id} transcript has drifted from the script`)
          .toBe(line.text);
      }
    }
  });
});
