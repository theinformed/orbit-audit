#!/usr/bin/env python3
"""
Assemble narration/layer-pages.json — the spoken script for the ten layer-page clips.

WHAT THIS IS FOR. Nine of the ten clips on Learn > Layers play silently. This turns the
words already printed beside each clip into the words spoken over it, and it is the LAST
step before tools/narrate.py spends anything: narrate.py renders whatever is in
layer-pages.json, so what this writes is what Sean's voice will say.

TWO SOURCES OF A LINE, AND THE FILE SAYS WHICH ONE IT GOT
---------------------------------------------------------
1. `--drafts <file>` — the free local 35B's draft, produced by the shared scaffold runner
   (manifest entry `space-layer-narration` in the OpenClaw workspace; the model never sees
   anything but layer-narration-facts.json). Every line is re-checked HERE against the
   same per-clip gate the runner ran, because a gate that only runs on the machine that
   generated the text is a gate that protects the wrong file.
2. No draft, or a draft that fails the gate — a deterministic line assembled from the
   clip's own `onScreen` and `doNotInfer` copy, and marked `"source": "deterministic"` in
   the output. The model decorates; it never gates. The site is never waiting on a model,
   and a clip whose model line was rejected still gets a voice.

Every entry carries `source`, so a reader of the script file can always see which lines a
model wrote and which the arithmetic did.

THE ONE CHECK THAT CANNOT BE DEFERRED is fit: a spoken line longer than the animation it
is spoken over cannot be repaired after the audio exists, so `wordBudget` is arithmetic on
the clip's own duration and is enforced on both paths.

    python3 narration/build_layer_script.py                     # deterministic only
    python3 narration/build_layer_script.py --drafts drafts.json
    python3 narration/build_layer_script.py --check             # verify, write nothing
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FACTS = HERE / "layer-narration-facts.json"
OUT = HERE / "layer-pages.json"

VOICE_ID = "9M1l09pkVunOZDmYq0Ms"
VOICE_NAME = "Myself (Sean, professional clone)"
MODEL_ID = "eleven_multilingual_v2"

sys.path.insert(0, str(HERE))


def _sentences(text: str) -> list:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9'’.-]+", text))


# Unit abbreviations and symbols read wrong, or not at all, in a speech synthesiser, so a
# deterministic line assembled out of PRINTED page copy has to be spoken-ified before it is
# spoken. Written-out words are the only safe form. This is a fixed table, not a guess:
# every entry is a unit that actually appears in layer-narration-facts.json.
SPEAKABLE = [
    (r"(\d)\s*x\s*10\^-(\d+)", r"\1 times ten to the minus \2"),
    (r"(\d)\s*x\s*10\^(\d+)", r"\1 times ten to the \2"),
    (r"kg m\^-3", "kilograms per cubic metre"),
    (r"cm\^-3", "per cubic centimetre"),
    (r"(?<![A-Za-z])km(?![A-Za-z])", "kilometres"),
    (r"(?<![A-Za-z])cm(?![A-Za-z])", "centimetres"),
    (r"(?<![A-Za-z])MHz(?![A-Za-z])", "megahertz"),
    (r"(?<![A-Za-z])GHz(?![A-Za-z])", "gigahertz"),
    (r"(?<![A-Za-z])keV(?![A-Za-z])", "kilo-electron-volts"),
    (r"(?<![A-Za-z])MeV(?![A-Za-z])", "mega-electron-volts"),
    (r"(?<![A-Za-z])nT(?![A-Za-z])", "nanotesla"),
    (r"(?<![A-Za-z])nPa(?![A-Za-z])", "nanopascals"),
    (r"(?<![A-Za-z])dB(?![A-Za-z])", "decibels"),
    (r"(?<![A-Za-z])pfu(?![A-Za-z])", "particle flux units"),
    (r"(?<![A-Za-z])TECU(?![A-Za-z])", "TEC units"),
    (r"(?<=\d)\s*x(?![A-Za-z])", " times"),
    (u"×", " times "),
    (u"°", " degrees"),
    (r"\s+", " "),
]


def speakable(text: str) -> str:
    for pattern, replacement in SPEAKABLE:
        text = re.sub(pattern, replacement, text)
    return text.strip()


def deterministic(clip: dict) -> str:
    """A line built only from this clip's own copy, inside its own word budget.

    `onScreen` is a description of the picture and `doNotInfer` is the misreading the page
    exists to prevent — which is exactly the pair a voice over a moving picture is for.
    Sentences are added while they fit and dropped whole when they do not, because half a
    spoken sentence is worse than one fewer.
    """
    budget = int(clip["wordBudget"])
    chosen: list = []
    for sentence in _sentences(speakable(clip["onScreen"])):
        if _words(" ".join(chosen + [sentence])) <= budget:
            chosen.append(sentence)
    tail = speakable(clip["doNotInfer"])
    if tail and _words(" ".join(chosen + [tail])) <= budget:
        chosen.append(tail)
    line = " ".join(chosen).strip()
    if line and line[-1] not in ".!?":
        line += "."
    return line


def gate(clip: dict, text: str) -> tuple:
    """The per-clip check, imported from the deployed validator so the two cannot drift.

    Falls back to a local copy of the same rules when the OpenClaw validator is not on this
    machine — the space repo lives on bigmem-PC and the runner lives on the VPS, and this
    script has to be runnable on either.
    """
    try:
        sys.path.insert(0, "/root/apps/openclaw")
        from scaffold_validators.space_layer_narration import check  # type: ignore
    except Exception:
        return _local_gate(clip, text)
    return check({"items": [{"id": clip["id"], "text": text}]},
                 {"carry": [clip]})


def _local_gate(clip: dict, text: str) -> tuple:
    budget = int(clip["wordBudget"])
    if not text.strip():
        return False, f"{clip['name']}: empty line"
    if text.strip()[-1] not in ".!?":
        return False, f"{clip['name']}: no terminal punctuation"
    n = _words(text)
    if n > budget:
        return False, f"{clip['name']}: {n} words over a budget of {budget}"
    if n < 12:
        return False, f"{clip['name']}: {n} words is not a narration line"
    if re.search(r"(?<![A-Za-z])(km|cm|MHz|keV|MeV|nT|nPa|dB|pfu|TECU)(?![A-Za-z])", text):
        return False, f"{clip['name']}: unspeakable unit abbreviation"
    return True, ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--drafts", type=Path, default=None,
                    help='scaffold-runner output: {"items":[{"id":...,"text":...}]}')
    ap.add_argument("--check", action="store_true", help="verify the existing file, write nothing")
    args = ap.parse_args()

    facts = json.loads(FACTS.read_text())
    clips = {c["id"]: c for c in facts["clips"]}

    if args.check:
        spec = json.loads(OUT.read_text())
        bad = 0
        for line in spec["lines"]:
            clip = clips.get(line.get("clip") or line["id"])
            if clip is None:
                print(f"  {line['id']}: no facts row (already-rendered line, not re-checked)")
                continue
            ok, reason = gate(clip, line["text"])
            budget = clip["wordBudget"]
            print(f"  {'ok  ' if ok else 'FAIL'} {line['id']:24s} "
                  f"{_words(line['text']):3d}/{budget} words  {line.get('source','?')}"
                  + ("" if ok else f"  — {reason}"))
            bad += 0 if ok else 1
        print(f"\n{len(spec['lines'])} lines, {bad} failing.")
        return 1 if bad else 0

    drafts = {}
    if args.drafts and args.drafts.is_file():
        raw = json.loads(args.drafts.read_text())
        for item in raw.get("items") or []:
            if item.get("id") and item.get("text"):
                drafts[item["id"]] = item["text"].strip()

    # The solar-wind line is already rendered and already muxed into solar-wind.mp4. It is
    # carried through untouched so the manifest hash stays stable and re-running narrate.py
    # never re-bills it.
    previous = {}
    if OUT.is_file():
        for line in json.loads(OUT.read_text()).get("lines", []):
            previous[line["id"]] = line

    lines, used_model, used_det = [], 0, 0
    for clip in facts["clips"]:
        cid = clip["id"]
        text, source = None, None
        if cid in drafts:
            ok, reason = gate(clip, drafts[cid])
            if ok:
                text, source = drafts[cid], "local-35b"
                used_model += 1
            else:
                print(f"  rejected model line for {cid}: {reason}", file=sys.stderr)
        if text is None:
            text = deterministic(clip)
            source = "deterministic"
            used_det += 1
            ok, reason = gate(clip, text)
            if not ok:
                print(f"  DETERMINISTIC LINE FAILS ITS OWN GATE for {cid}: {reason}",
                      file=sys.stderr)
                return 2
        lines.append({
            "id": f"layer-{cid}",
            "clip": cid,
            "source": source,
            "clipSeconds": clip["clipSeconds"],
            "wordBudget": clip["wordBudget"],
            "words": _words(text),
            "note": f"Spoken over the {clip['name']} clip on Learn > Layers. "
                    f"{'Drafted by the free local 35B and gated against this clip’s own page copy.' if source == 'local-35b' else 'Assembled from this clip’s own page copy — no model wrote this line.'}",
            "text": text,
        })

    for cid, line in previous.items():
        if cid.startswith("layer-"):
            continue
        lines.append(line)   # solar-wind-corona and anything else already rendered

    OUT.write_text(json.dumps({
        "name": "Layer-page clip narration",
        "voice_id": VOICE_ID,
        "voice_name": VOICE_NAME,
        "model_id": MODEL_ID,
        "note": "One spoken line per layer-page clip. `source` says whether the free local "
                "35B wrote it or whether it was assembled deterministically from the page "
                "copy; `wordBudget` is arithmetic on the clip's own duration, so no line "
                "can be spoken past the picture it describes. Facts: "
                "narration/layer-narration-facts.json.",
        "lines": lines,
    }, indent=1, ensure_ascii=False) + "\n")

    print(f"{len(lines)} lines written to {OUT}")
    print(f"  {used_model} from the local 35B, {used_det} deterministic")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
