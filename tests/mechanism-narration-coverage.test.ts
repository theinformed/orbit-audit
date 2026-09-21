/**
 * The mechanism lane's coverage guard.
 *
 * On 2026-08-26 Sean reported his voice missing from these clips: "one where my
 * voice doesn't start until half way through. It is bad." Nothing was broken.
 * Every line was exactly where its manifest said, every `fits` was true, and
 * docs called the lane complete. The lane was built on a rule that said the
 * voice must never read the caption and that the rest was silence on purpose,
 * and following it produced fifteen lines for seventy-nine caption beats:
 * 18-37% of each clip had a voice on it, and three of the six stayed silent
 * past their halfway mark.
 *
 * The rule is retired. These tests exist so it cannot come back by accident,
 * because the failure it produces is invisible to every other check on this
 * site - the files are valid, the alignment arithmetic is right, and the page
 * plays them without an error. The only thing wrong is that nobody is talking.
 *
 * Quebec is the yardstick, being the clip Sean singled out as the one that
 * works: 0.00 s onset, 76.9% speech, worst internal gap 2.11 s.
 *
 * These read the muxer's own alignment report rather than probing media, so
 * they run in the normal suite. The delivered audio is measured separately by
 * tools/narration-coverage.py and tools/mechanism-animations/check_alignment.py.
 */

import { describe, expect, it } from "vitest";
import alignment from "../tools/mechanism-animations/narration-alignment.json";
import script from "../narration/mechanisms.json";
import { MECHANISM_ANIMATIONS, mechanismNarration } from "../src/mechanism-animations";

type Placed = {
  id: string;
  startSeconds: number;
  audioSeconds: number;
  nextLineSeconds: number;
  slackSeconds: number;
  fits: boolean;
};
type Clip = { stem: string; scene: string; videoSeconds: number; lines: Placed[] };

const clips = alignment as unknown as Clip[];

// A reader who hears nothing for this long at the start of a clip concludes the
// audio is broken. The measured onsets that produced Sean's complaint were 11.6
// to 40.8 s; the rebuilt clips open at 0.35-0.44 s.
const MAX_OPENING_SILENCE_SECONDS = 1.5;

// Quebec runs at 0.769. Below this a clip reads as sparsely narrated rather than
// narrated, and the six clips that drew the complaint were at 0.183 to 0.365.
const MIN_SPEECH_FRACTION = 0.6;

describe("mechanism narration coverage", () => {
  it("covers all six clips", () => {
    expect(clips.map((c) => c.stem).sort()).toEqual([
      "chapman-layer", "dayside-reconnection", "drag-orbit-decay",
      "eccentric-dipole-saa", "hf-skip-blackout", "trapped-motion",
    ]);
  });

  it.each(clips.map((c) => [c.stem, c] as const))(
    "%s starts talking within the first seconds",
    (_stem, clip) => {
      const first = Math.min(...clip.lines.map((l) => l.startSeconds));
      expect(first).toBeLessThanOrEqual(MAX_OPENING_SILENCE_SECONDS);
    },
  );

  it.each(clips.map((c) => [c.stem, c] as const))(
    "%s has a voice on it for most of its length",
    (_stem, clip) => {
      const talking = clip.lines.reduce((a, l) => a + l.audioSeconds, 0);
      expect(talking / clip.videoSeconds).toBeGreaterThanOrEqual(MIN_SPEECH_FRACTION);
    },
  );

  it.each(clips.map((c) => [c.stem, c] as const))(
    "%s never has two lines talking at once",
    (_stem, clip) => {
      for (const line of clip.lines) {
        expect(line.fits, `${line.id} overruns by ${-line.slackSeconds}s`).toBe(true);
        expect(line.slackSeconds).toBeGreaterThanOrEqual(-0.05);
      }
    },
  );

  it.each(clips.map((c) => [c.stem, c] as const))(
    "%s stops talking before the picture ends",
    (_stem, clip) => {
      for (const line of clip.lines) {
        expect(line.startSeconds + line.audioSeconds).toBeLessThanOrEqual(clip.videoSeconds + 0.05);
      }
    },
  );

  it("keeps the retired silence rule recorded, so it is not reinstated by accident", () => {
    // Deleting the rule without recording why is how it comes back: the next
    // person to read the config sees a lane with no stated policy and invents
    // the tidy-sounding one that caused this.
    const retired = (script as { retiredRule?: Record<string, string> }).retiredRule;
    expect(retired, "narration/mechanisms.json must keep retiredRule").toBeTruthy();
    expect(retired?.rule).toMatch(/silence on purpose/i);
    expect(retired?.doNotReinstate).toBeTruthy();
    expect(retired?.captionsStay).toBeTruthy();
  });

  it("has an opening line placed by explicit time on every clip", () => {
    // The first caption on these six lands 6.1-10.3 s in, so an anchored line
    // can never open a clip. Losing the `at` placement silently reintroduces
    // the opening silence.
    const lines = (script as { lines: { id: string; scene: string; at?: number }[] }).lines;
    for (const clip of clips) {
      const opener = lines.find((l) => l.scene === clip.scene && typeof l.at === "number");
      expect(opener, `${clip.stem} has no explicitly timed opening line`).toBeTruthy();
      expect(opener!.at!).toBeLessThanOrEqual(MAX_OPENING_SILENCE_SECONDS);
    }
  });
});

describe("the transcript a deaf reader gets", () => {
  /**
   * The transcript used to be a hand-copied duplicate of the spoken lines. When
   * the clips went from fifteen lines to forty-four the copy stayed at fifteen,
   * so a reader who cannot hear was silently given a third of the content while
   * the page still looked correct. It is derived now, and these hold it there.
   */
  it.each(clips.map((c) => [c.stem, c] as const))(
    "%s prints every line the clip speaks",
    (stem, clip) => {
      expect(mechanismNarration(stem)).toHaveLength(clip.lines.length);
    },
  );

  it("prints the same words that were sent to the synthesiser", () => {
    const byId = new Map(
      (script as { lines: { id: string; text: string }[] }).lines.map((l) => [l.id, l.text]),
    );
    for (const clip of clips) {
      const printed = mechanismNarration(clip.stem);
      clip.lines.forEach((placed, i) => {
        expect(printed[i]).toBe(byId.get(placed.id));
      });
    }
  });

  it("prints them in the order they are spoken", () => {
    for (const clip of clips) {
      const starts = clip.lines.map((l) => l.startSeconds);
      expect([...starts].sort((a, b) => a - b)).toEqual(starts);
    }
  });

  it("gives every clip on the page a transcript", () => {
    for (const m of MECHANISM_ANIMATIONS) {
      expect(mechanismNarration(m.stem).length, `${m.stem} has no transcript`).toBeGreaterThan(0);
    }
  });
});
