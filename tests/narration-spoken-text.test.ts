/**
 * The rule that makes the pronunciation lane safe: WHAT IS SPOKEN IS NOT WHAT IS SHOWN.
 *
 * ElevenLabs says "Egan" as EGG-an on this voice, so the synthesiser is sent "Eagen"
 * instead. That respelling is a lie about the spelling of a real word, and it is only
 * acceptable because it never reaches a reader. The moment "Eagen" appears in a transcript,
 * a caption, or any page copy, this lane has stopped being a pronunciation fix and started
 * being a typo — and it is exactly the kind of typo nobody reports, because it is buried in
 * a collapsed transcript beside a video.
 *
 * So these tests hold three lines:
 *   1. No respelled form appears in anything a reader can see.
 *   2. Every rendered line whose displayed text contains a respelled term actually GOT the
 *      respelling — a lexicon entry that is never applied is a lexicon entry that lies.
 *   3. No script says a term the lexicon marks `unresolved`, i.e. one that nothing was ever
 *      made to pronounce correctly.
 */

import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import lexicon from "../narration/pronunciation-lexicon.json";
import eventManifest from "../media/narration/manifest.json";
import bedManifest from "../media/narration-layers/manifest.json";
import eventScript from "../narration/script.json";
import layerScript from "../narration/layer-pages.json";
import mechanismScript from "../narration/mechanisms.json";
import quebecScript from "../narration/quebec-mechanism.json";

type Term = {
  id: string;
  display: string;
  spoken: string | null;
  status: "plain-ok" | "respelled-proven" | "expansion" | "unresolved";
  expectedIpa: string;
  spokenWhy: string;
};

const terms = lexicon.terms as Term[];
const respelled = terms.filter((t) => t.status === "respelled-proven" && t.spoken);
const unresolved = terms.filter((t) => t.status === "unresolved");

/** Match a term as a whole word, the same way tools/narrate.py does. */
const pattern = (s: string) =>
  new RegExp(`(?<![A-Za-z0-9])${s.replace(/[.*+?^${}()|[\]\\/-]/g, "\\$&")}(?![A-Za-z0-9])`,
             /[A-Z]/.test(s) ? "" : "i");

const readerVisible: Array<[string, string]> = [
  ["event narration transcripts", eventManifest.lines.map((l: any) => l.text).join("\n")],
  ["layer bed transcripts", (bedManifest.clips as any[])
    .flatMap((c) => c.lines.map((l: any) => l.text)).join("\n")],
  ["mechanism transcripts", readFileSync(
    fileURLToPath(new URL("../src/mechanism-animations.ts", import.meta.url)), "utf8")],
  ["layer page copy", readFileSync(
    fileURLToPath(new URL("../src/layer-pages.ts", import.meta.url)), "utf8")],
  ["observed imagery captions", readFileSync(
    fileURLToPath(new URL("../src/observed-imagery.ts", import.meta.url)), "utf8")],
];

describe("a respelling never reaches a reader", () => {
  for (const term of respelled) {
    for (const [where, text] of readerVisible) {
      it(`${term.display}: "${term.spoken}" is absent from ${where}`, () => {
        expect(pattern(term.spoken as string).test(text)).toBe(false);
      });
    }
  }

  it("keeps the displayed text and the spoken text in separate manifest fields", () => {
    for (const line of eventManifest.lines as any[]) {
      if (line.spokenText) expect(line.spokenText).not.toBe(line.text);
      expect(typeof line.text).toBe("string");
      expect(line.text.length).toBeGreaterThan(0);
    }
  });
});

describe("a lexicon entry that is never applied would be a lie", () => {
  it("applies the respelling to every rendered line whose displayed text uses the term", () => {
    for (const line of eventManifest.lines as any[]) {
      for (const term of respelled) {
        if (!pattern(term.display).test(line.text)) continue;
        expect(line.spokenText, `${line.id} shows ${term.display} but was sent no respelling`)
          .toBeTruthy();
        expect(pattern(term.spoken as string).test(line.spokenText)).toBe(true);
      }
    }
  });
});

describe("a term nothing could fix is never spoken", () => {
  const scripts: Array<[string, { lines: Array<{ id: string; text: string }> }]> = [
    ["script.json", eventScript as any],
    ["layer-pages.json", layerScript as any],
    ["mechanisms.json", mechanismScript as any],
    ["quebec-mechanism.json", quebecScript as any],
  ];
  for (const [name, script] of scripts) {
    it(`${name} says none of them`, () => {
      for (const line of script.lines) {
        for (const term of unresolved) {
          expect(pattern(term.display).test(line.text),
            `${line.id} says ${term.display}, which has no working spoken form: ${term.spokenWhy}`)
            .toBe(false);
        }
      }
    });
  }
});

describe("the lexicon only holds defects somebody actually heard", () => {
  // This is the guard against the file refilling itself. It briefly held 59 entries, built
  // by auditing every term that LOOKED risky before anything had been heard wrong. Sean:
  // "I'm worried not many words need the phonetics spelled out like this, so we introduce
  // more error if we overdo it." A respelling is a permanent silent override on every future
  // render, so respelling a word the model already says correctly does not make it safer -
  // it manufactures a defect and hides it somewhere nobody re-listens.
  it("makes every entry cite the failure that justifies it", () => {
    for (const term of terms) {
      expect((term as any).heardFailure, `${term.id} has no heard failure behind it`)
        .toBeTruthy();
      expect((term as any).heardFailure.length).toBeGreaterThan(40);
    }
  });

  it("checks every fix inside a sentence someone would actually say", () => {
    // The same respelling behaves differently alone: "Eegan." on its own came back "E gun",
    // while the carrier sentence Sean ruled on is right. A bare-word check is what produced
    // the 57 speculative entries.
    for (const term of terms) {
      const carrier = (term as any).carrier as string;
      expect(carrier, `${term.id} has no carrier sentence`).toBeTruthy();
      expect(carrier).toContain(term.display);
      expect(carrier.trim().endsWith(".")).toBe(true);
    }
  });

  it("keeps the file small, and says so out loud", () => {
    expect((lexicon as any).theRuleThatGovernsThisFile.join(" ")).toContain("LIABILITY");
    expect(terms.length, "if this is growing, ask what was HEARD wrong").toBeLessThan(10);
  });
});

describe("the lexicon is honest about itself", () => {
  it("pins every proven form to one voice and one model", () => {
    expect(lexicon.voiceProvenOn.voice_id).toBeTruthy();
    expect(lexicon.voiceProvenOn.model_id).toBe("eleven_multilingual_v2");
  });

  it("gives every term a reason, and every changed term a measurement behind it", () => {
    for (const term of terms) {
      expect(term.spokenWhy.length, `${term.id} has no rationale`).toBeGreaterThan(20);
      expect(term.expectedIpa.length, `${term.id} has no target sound`).toBeGreaterThan(1);
      if (term.status === "respelled-proven") expect(term.spoken).toBeTruthy();
      if (term.status === "plain-ok") expect(term.spoken).toBeNull();
    }
  });
});
