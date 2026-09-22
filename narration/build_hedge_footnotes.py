#!/usr/bin/env python3
"""Build the eight classification footnotes the satellite cards print.

WHAT THIS IS FOR. A spacecraft card's category label says what the object is for.
Where nobody has corroborated that label against the individual spacecraft, the label
is drawn dashed, dimmed and marked with an asterisk -- 1,559 of the 8,000 cards.  An
asterisk rather than a question mark, with its meaning written out in the card's details,
so that the caveat reads as a footnote a reader can follow rather than as doubt cast on
the card.

WHY IT RUNS HERE AND NOT IN THE BROWSER.  There are 1,559 marked cards and EIGHT reasons a
card is marked.  So this writes eight footnotes, once, at authoring time, and checks them
into the repository; the site ships the finished words and asks no model anything when a
reader opens a card.  A per-card call would be 1,559 chances to say something the facts do
not support, on a page a reader is waiting on, for eight distinct answers.

THE SPLIT.  Code owns the facts: `hedge-footnote-facts.json` holds, per kind, what the
label rests on and what nobody checked, both copied out of CLASSIFICATION_BASIS_EVIDENCE
and classificationChipEvidence in src/main.ts.  The free local 35B on bigmem owns only the
phrasing -- turning those two facts into the two sentences a person would actually say.
THE MODEL DECORATES; IT NEVER GATES.  With no --drafts, with bigmem down, with a refused
draft, every kind still gets a footnote: the deterministic composition of its own two
facts.  A card can never render with no explanation for its mark.

THE GATE THAT MATTERS.  A footnote that has stopped saying what has NOT been established
has failed, however well it reads.  `--drafts` output is re-checked HERE, against THIS
repository's facts file, because a gate that only runs on the machine that generated the
text protects the wrong file (the lesson layer-narration paid for).  Every refusal is
printed and the kind falls back to deterministic wording; one bad footnote never costs the
other seven.

    python3 narration/build_hedge_footnotes.py
    python3 narration/build_hedge_footnotes.py --drafts /tmp/hedge-drafts.json

The drafts file is the `items` array the house scaffold runner cached for the
`space-hedge-footnote` tool (VPS: state/brain-scaffold-notes.json).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
FACTS = ROOT / "narration" / "hedge-footnote-facts.json"
OUT = ROOT / "narration" / "hedge-footnotes.json"

# The SAME hedge list scaffold_lib.py's gate_no_hedging uses, and the same list the prompt
# prints for the model.  A gate the prompt never stated cannot be repaired against: three
# layer-narration runs were lost to exactly that mismatch, so these three lists are kept
# character-for-character equal on purpose.
HEDGES = re.compile(
    r"\b(might|maybe|perhaps|possibly|probably|seems?|appears?|suggests?|likely|"
    r"presumably|could be|i think|it looks like)\b",
    re.I,
)
# Talking the evidence DOWN is the same defect as talking it up.  An assessment named
# analysts reasoned out of an orbit is not a guess; a live run wrote "the current best
# guess" and it was refused for that reason, not for reading badly.
BANNED = ("as an AI", "i think", "*", "there is some uncertainty", "in summary",
          "it is important to note", "guess", "meaningless", "made up", "fabricat")
# The one rule this footnote exists for.  Every honest explanation of an uncorroborated
# label contains a negation, because the whole content of the mark is something that was
# NOT done.  A footnote with no negation in it has been polished into agreement.
NEGATION = re.compile(r"\b(not|no|nobody|none|never|nothing|without|lacked|lacks)\b", re.I)


def deterministic(kind: dict) -> str:
    """The sentence that ships when no model has run, or when its draft was refused.

    Two of the facts, in order, and nothing else.  It is stiffer than the model's version
    and it is exactly as honest, which is the whole design: the site is never wrong when
    bigmem is down, only plainer.

    THIS TEXT IS DELIBERATELY ABSENT FROM THE FACTS FILE THE MODEL IS SHOWN.  Handed its
    own fallback, a model returns it unchanged; the result passes every gate, because it is
    made of the facts, and ships marked as model-written while the model authored nothing.
    `_is_deterministic_restatement` below is the second half of that guard.
    """
    return f"{kind['what'].strip()} {kind['notChecked'].strip()}"


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _is_deterministic_restatement(text: str, kind: dict) -> bool:
    """Did the model hand the fallback back? Then it is deterministic, whatever wrote it.

    Provenance is a claim this file makes in its own `source` field, and a wrong one is a
    lie about who wrote the words rather than a wrong fact -- which no later gate can
    catch, because the text is perfect.
    """
    return _norm(text) == _norm(deterministic(kind))


def check(text: str, kind: dict) -> str | None:
    """→ the reason this draft may not ship, or None.  One question per line, in order."""
    body = (text or "").strip()
    if not body:
        return "empty"
    words = len(body.split())
    ceiling = int(kind["wordCeiling"])
    if words > ceiling:
        return f"{words} words, ceiling is {ceiling}"
    if not body.endswith("."):
        return "does not end in a full stop"
    if body.count(".") > 3:
        return f"{body.count('.')} sentences; two is the shape, three is the limit"
    hedge = HEDGES.search(body)
    if hedge:
        return f'hedging word "{hedge.group(0)}"'
    low = body.lower()
    for phrase in BANNED:
        if phrase.lower() in low:
            return f'banned phrase "{phrase}"'
    if not NEGATION.search(body):
        return "no negation in it -- it has stopped saying what was NOT established"
    if _is_deterministic_restatement(body, kind):
        return "the deterministic fallback handed back; not model-written"
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--drafts", type=pathlib.Path,
                    help="the scaffold runner's cached items for space-hedge-footnote")
    ap.add_argument("--out", type=pathlib.Path, default=OUT)
    args = ap.parse_args()

    facts = json.loads(FACTS.read_text())
    kinds = {row["key"]: row for row in facts["keys"]}

    drafts: dict[str, str] = {}
    if args.drafts:
        raw = json.loads(args.drafts.read_text())
        items = raw.get("items", raw) if isinstance(raw, dict) else raw
        for item in items:
            if isinstance(item, dict) and item.get("key"):
                drafts[item["key"]] = str(item.get("text") or "")
        unknown = sorted(set(drafts) - set(kinds))
        if unknown:
            print(f"  ! drafts name kinds this repo does not have: {', '.join(unknown)}")

    footnotes, model_written = {}, 0
    for key, kind in kinds.items():
        draft = drafts.get(key)
        if draft is None:
            footnotes[key] = {"text": deterministic(kind), "source": "deterministic"}
            print(f"  · {key:26s} deterministic (no draft offered)")
            continue
        reason = check(draft, kind)
        if reason:
            footnotes[key] = {"text": deterministic(kind), "source": "deterministic"}
            print(f"  ✗ {key:26s} REFUSED: {reason}")
            continue
        footnotes[key] = {"text": draft.strip(), "source": "local-35b"}
        model_written += 1
        print(f"  ✓ {key:26s} local-35b ({len(draft.split())} words)")

    payload = {
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": ("Built by narration/build_hedge_footnotes.py from narration/hedge-footnote-facts.json. "
                 "One footnote per KIND of uncorroborated label, never one per spacecraft. `source` says "
                 "who wrote each one: `local-35b` is the free home model's phrasing of this repo's own "
                 "facts, re-checked here before it was allowed in; `deterministic` is those facts composed "
                 "in code, which is what ships when no model has run or when its draft was refused. The "
                 "site reads this file at BUILD time and asks no model anything at request time."),
        "footnotes": footnotes,
    }
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    try:
        where = args.out.relative_to(ROOT)
    except ValueError:  # --out to a scratch path, which the negative-control run uses
        where = args.out
    print(f"\n  {model_written}/{len(kinds)} model-written -> {where}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
