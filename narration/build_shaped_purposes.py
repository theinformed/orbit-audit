#!/usr/bin/env python3
"""Shape the long satellite descriptions to the published format, without losing a word of them.

WHAT THIS IS FOR.  Every one of the 8,000 spacecraft cards carries a background
description, and 7,933 of them carry a Source link to where it was researched.  The corpus
is real: 1,311 cited override entries, 1.2 MB.  The defect is SHAPE.  The published length
runs from a median of 137 characters to a maximum of 2,425, none of the texts contains a
paragraph break, and `main.ts` prints `purpose` as one textContent node -- so 835 objects
open onto a single unbroken wall.  The published format is:

    at most 2 paragraphs, and at most a few lines per paragraph. A card with only 1
    paragraph may run longer, to a maximum of about 6-8 lines. Nothing crowded.

WHY A MODEL IS ALLOWED NEAR THIS, WHEN THE STUDY SAYS NO MODEL WRITES SITE PROSE.  Because
this is not writing.  The text already exists and is already cited, so the honesty question
is CONTAINMENT rather than truth: does every number, every name and every hedge in the
shortened version come from the long version it was made out of?  That question is
answerable in code, exactly, per object -- which is what `check()` below does, and it is
the whole reason this lane is buildable.  A GENERATION lane over the same cards would have
none of those tests, because there would be nothing to contain the output against.  DO NOT
REUSE THIS LANE FOR GENERATION.

NOTHING RESEARCHED IS DELETED.  The shaped paragraphs are what the card opens with; the
full published text stays in the record and the card keeps it one disclosure away.  A
shaping that fails any check below is DROPPED and that object ships its original text,
unchanged, exactly as it does today.  THE MODEL DECORATES, IT NEVER GATES: bigmem down, the
kill switch, the quiet window, a refused draft and an empty drafts file all produce the
site as it is now, only unshaped.

    python3 narration/build_shaped_purposes.py --emit-facts
    python3 narration/build_shaped_purposes.py --drafts /path/to/drafts.json

The drafts file is the `items` array the house scaffold runner cached for the
`space-purpose-shape` tool (VPS: state/brain-scaffold-notes.json).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
from collections import Counter
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
FACTS = ROOT / "narration" / "purpose-shape-facts.json"
OUT = ROOT / "narration" / "shaped-purposes.json"

# ---------------------------------------------------------------------------
# THE FORMAT, MEASURED.  Not adjectives, and not the 55-60 characters a line was
# guessed to be.
#
# The format: at most 2 paragraphs, at most a few lines per paragraph, and a single
# paragraph may run longer to a maximum of about 6-8 lines. Nothing crowded.
#
# MEASURED ON THE REAL CARD, not assumed.  The satellite card's description column
# is 280.5 px wide at a 1440 px viewport, set in 11.6 px Inter on an 18.56 px line
# box (`.satellite-purpose`, src/styles.css:1444).  ASBM-1's 2,425-character
# description wraps to 53 line boxes there -- a MEDIAN OF 46 CHARACTERS PER LINE,
# range 35 to 54.  Every number below is that 46 times a count of stated lines, and
# raising the allowance is a one-line change to LINE_CHARS' multipliers.
#
# The ceiling is on the WHOLE section, both paragraphs together, because that is
# what a reader actually meets: two four-line paragraphs and one eight-line
# paragraph are the same amount of card, and the format states one number for both.
# ---------------------------------------------------------------------------
LINE_CHARS = 46
SECTION_LINES = 8               # "a max of maybe 6-8 lines"
# 5, not 4. "A few lines per paragraph" does not name a number;
# the number the format DOES give -- six to eight lines -- is on the section, and with two paragraphs
# the section ceiling binds long before either paragraph can run away. Four lines refused
# honest 186- and 195-character paragraphs inside a 368-character total, which is a derived
# number overruling the stated one. What this ceiling is actually for is stopping ONE
# paragraph swallowing the whole allowance and leaving a two-line stub beside it.
PARAGRAPH_LINES = 5             # "max just a few lines per paragraph"
SECTION_MAX = LINE_CHARS * SECTION_LINES        # 368
PARAGRAPH_MAX = LINE_CHARS * PARAGRAPH_LINES    # 184
# Below this a "shaping" has thrown the description away rather than shortened it.
# 3 lines: the shortest thing on the site that still reads as a description.
SECTION_MIN = LINE_CHARS * 3                    # 138

# THE SAME CEILING, IN THE UNIT THE MODEL CAN ACTUALLY COUNT.
#
# The first live run (2026-08-27) returned four shortenings that were complete, correctly
# contained, and 550 to 613 characters long against a 368 ceiling -- and the one guided
# repair, shown "613 characters, the ceiling is 368", came back over as well. A model does
# not count characters. It counts words and it counts sentences. So the ASK is stated in
# words and sentences and the CHECK stays on characters, which is the unit the card is
# actually measured in. Restructuring the ask rather than re-rejecting the answer is what
# deterministic-scaffolding.md calls rung 1; a gate that just keeps refusing is rung 3 in a
# rung-1 costume. 6.1 characters per word including its space is measured on this corpus.
# 6.6 is measured on these 139 descriptions (median 6.39, p90 6.97 characters per word
# including its space); the first model answers came back denser still, at 7.35. The
# advertised word ceiling is therefore conservative, and every REFUSAL states the real
# character count with the number of words to cut computed from that answer's OWN density --
# an earlier version said "26 words, the ceiling is 30" about a paragraph it had just
# refused, which is not a sentence anybody can act on.
CHARS_PER_WORD = 6.6
SECTION_WORDS = int(SECTION_MAX / CHARS_PER_WORD)          # 55
SECTION_WORD_AIM = int(SECTION_WORDS * 0.85)               # 46
PARAGRAPH_WORDS = int(PARAGRAPH_MAX / CHARS_PER_WORD)      # 27


def words_over(text: str, ceiling: int) -> int:
    """How many words to cut, at the density of THIS answer. Never zero when it is over."""
    words = max(len(text.split()), 1)
    return max(1, round((len(text) - ceiling) / (len(text) / words)))

# Only texts longer than this are shaped at all.  835 objects / 139 distinct texts sit
# above it, and it is the number the study measured the problem at.
SHAPE_ABOVE = 800

# ---------------------------------------------------------------------------
# THE HEDGE VOCABULARY.  Two different failures, one list.
#
#   dropping one is a FABRICATION: a trim that turns "reportedly manoeuvred" into
#   "manoeuvred" has upgraded an attributed report into an established fact, and every
#   word of it is shorter and cleaner and wrong.
#
#   adding one is the OPPOSITE failure, and this site has already paid for it: a live
#   run of space-hedge-footnote wrote "the current best guess" for a label that named
#   analysts had reasoned out of an orbit.  Talking evidence DOWN misdescribes it just
#   as badly as talking it up.
#
# So the test runs in both directions and is a CLASS test, not a word test: the shaped
# text must be hedged if and only if its own source was.  A word test would refuse an
# honest trim that dropped the one sentence a hedge happened to sit in.
# ---------------------------------------------------------------------------
HEDGE = re.compile(
    r"\b(reportedly|allegedly|apparently|assess\w+|presum\w+|purported\w*|"
    r"ostensibly|unconfirmed|uncorroborated|unverified|undisclosed|unclear|"
    r"believed|thought to|understood to|said to|described as|claims?|claimed|"
    r"probabl\w+|possibly|likely|may be|may have|may not|might|appears?|appeared|seems?|seemed|"
    r"suggests?|suggested|not (?:been )?(?:independently )?(?:verified|confirmed|"
    r"corroborated|established|disclosed|published|named|identified)|"
    r"no public|not known|unknown|question mark|has not stated|does not state|"
    r"speculat\w+|attributes?|attributed|attribution|according to|analysts|"
    r"open sources?|open-source|credited with|characteri[sz]e\w*|"
    r"remains? unsourced|no source|without a source)\b",
    re.I,
)
# TWO WORDS WERE TAKEN OUT OF THIS PATTERN AFTER THE FIRST LIVE RUN, and both were the same
# defect -- a deterministic word list standing in for a judgment about meaning, which is the
# brittleness deterministic-scaffolding.md §2b warns about arriving on schedule:
#   "possibl\w+" matched "the communications architecture that makes them POSSIBLE", an
#   adjective about capability rather than a qualifier on a claim. It marked ASBM-1's fully
#   sourced description as hedged, and every honest shortening of it was then refused for
#   stating the facts as plainly as the description itself does.
#   "may " matched "30 MAY 2025". The month. It marked all three GPS descriptions hedged.
# Only the auxiliary forms qualify a claim: "may be", "may have", "may not".

# House AI-tells and shapes that have no business in a reference description.  Kept in
# step with the same list in narration/build_hedge_footnotes.py and in the prompt the
# model is shown -- a gate the prompt never stated is one a repair loop converges on
# blindly, which is how space-hedge-footnote lost six of eight outputs while logging
# ok:true.
BANNED = (
    "as an ai", "i think", "in summary", "in conclusion", "it is important to note",
    "it's important to note", "importantly", "notably,", "overall,", "this satellite is a",
    "let's", "we will", "you can see", "in this description", "the text says",
    "the description", "based on the provided", "the source states", "**", "##", " - ",
)

# A designator is a name whichever case it is in: TJS-3, COSMOS 2504, USA 309, Kosmos,
# Nivelir, Yaogan.  Everything matched here must be in the source text it was made from.
TOKEN = re.compile(r"[A-Za-z][A-Za-z'’\-]*")
NUMBER = re.compile(r"\d[\d,.]*")
SENTENCE_START = re.compile(r"(?:^|[.!?]\s+|[—–:;]\s+)$")

# Capitalised words that begin a sentence are not evidence of a name, and a handful of
# ordinary words are capitalised mid-sentence for reasons that have nothing to do with
# naming anything.  Everything else capitalised mid-sentence is treated as a name.
CASE_EXEMPT = {"I", "A", "An", "The", "It", "Its", "This", "That", "They", "Their"}

# A DEMONYM BUILT FROM A COUNTRY THE DESCRIPTION ALREADY NAMES IS NOT AN INVENTED FACT.
# The name test asks whether a name was invented, and "Chinese" where the description says
# "China" invents nothing -- it is the adjective form of a fact already there. Refusing it
# was the name gate testing MORPHOLOGY rather than containment, and it cost real answers on
# Yaogan and Yunyao. The map is explicit and closed on purpose: it can turn a country in the
# description into its adjective and nothing else, so it cannot admit a country that is not
# there. Anything outside this list is still refused.
DEMONYM = {
    "chinese": "china", "russian": "russia", "american": "america", "japanese": "japan",
    "indian": "india", "european": "europe", "norwegian": "norway", "german": "germany",
    "french": "france", "british": "britain", "italian": "italy", "spanish": "spain",
    "korean": "korea", "israeli": "israel", "canadian": "canada", "brazilian": "brazil",
    "turkish": "turkey", "iranian": "iran", "australian": "australia", "swedish": "sweden",
    "argentine": "argentina", "mexican": "mexico", "thai": "thailand", "emirati": "emirates",
    "saudi": "saudi", "egyptian": "egypt", "pakistani": "pakistan", "indonesian": "indonesia",
    "vietnamese": "vietnam", "singaporean": "singapore", "taiwanese": "taiwan",
}



def _norm_number(raw: str) -> str:
    return raw.replace(",", "").rstrip(".")


def numbers_of(text: str) -> list:
    return [_norm_number(m) for m in NUMBER.findall(text or "")]


def names_of(text: str) -> list:
    """Capitalised tokens that are not sentence-initial, plus every ALL-CAPS token.

    The sentence-initial exemption is what stops "The" and "Its" being read as names; the
    ALL-CAPS clause is what stops a designator being missed because it opened a sentence.
    """
    out, body = [], text or ""
    for match in TOKEN.finditer(body):
        word = match.group(0)
        if len(word) < 2:
            continue
        if word.isupper():
            out.append(word)
            continue
        if not word[0].isupper():
            continue
        if word in CASE_EXEMPT and SENTENCE_START.search(body[: match.start()][-3:] or "^"):
            continue
        before = body[: match.start()]
        if not before.strip() or SENTENCE_START.search(before[-3:]):
            continue  # sentence-initial: capitalisation says nothing
        out.append(word)
    return out


def paragraphs_of(item: dict) -> list:
    first = (item.get("first") or "").strip()
    second = (item.get("second") or "").strip()
    return [p for p in (first, second) if p]


def text_key(purpose: str) -> str:
    """The identity of a description, so 4,648 identical Starlink sentences are one job."""
    return hashlib.sha256((purpose or "").strip().encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# THE CHECK.  Per object, against ITS OWN source text -- never against the pool.
#
# Every generic gate the scaffold runner offers reasons about the whole answer against
# the whole facts blob: "is this number anywhere in the six descriptions I was given",
# not "is it in the description THIS paragraph was made from".  Six long, similar
# spacecraft descriptions in one call is exactly the gap that matters, because the
# borrowed fact is the one that reads best.
# ---------------------------------------------------------------------------
def check(item: dict, row: dict) -> str | None:
    """→ the reason this shaping may not ship, or None.  One question per line, in order."""
    paras = paragraphs_of(item)
    source = row["text"]
    if not paras:
        return "empty"
    if len(paras) > 2:
        return f"{len(paras)} paragraphs; the maximum is 2"
    whole = " ".join(paras)

    # 1. LENGTH -- the format rule, in characters, against the measured card.
    if len(whole) > SECTION_MAX:
        return (f"{len(whole)} characters over both paragraphs; the ceiling is {SECTION_MAX}. "
                f"Cut about {words_over(whole, SECTION_MAX)} words -- take out a whole idea, "
                "do not compress every sentence")
    if len(paras) == 2 and max(len(p) for p in paras) > PARAGRAPH_MAX:
        worst = max(paras, key=len)
        return (f"one paragraph runs {len(worst)} characters; with two paragraphs neither may "
                f"pass {PARAGRAPH_MAX}. Cut about {words_over(worst, PARAGRAPH_MAX)} words from "
                "it, or write a single paragraph instead")
    if len(whole) < SECTION_MIN:
        return f"{len(whole)} characters; below {SECTION_MIN} this is a deletion, not a trim"
    if len(whole) >= len(source):
        return "not shorter than the description it was made from"

    # 2. NUMBERS -- every one must come out of THIS object's own description.  A model
    #    that writes "launched in 2019" where the source said 2018 fails here mechanically,
    #    and so does one that borrows the neighbouring spacecraft's apogee.
    # THE HAYSTACK IS THE DESCRIPTION, PLUS THE SPACECRAFT'S OWN NAME WHEN -- AND ONLY WHEN
    # -- THIS DESCRIPTION BELONGS TO ONE SPACECRAFT.
    #
    # 58 of the 139 long descriptions are printed on more than one object (up to 126), which
    # is the whole reason the corpus is 139 texts and not 835. A shortening that opens
    # "ASBM-1 is an Arctic Satellite Broadband Mission spacecraft" is then printed verbatim
    # on ASBM-2's card, naming the wrong satellite -- and it passes every containment test,
    # because "ASBM-1" is genuinely in the description. The first live run wrote exactly
    # that. So: one owner, the name is legitimate material and is allowed in; more than one
    # owner, no member may be named at all and the shortening says "this spacecraft".
    shared = row.get("doNotName") or []
    if shared:
        for name in shared:
            if re.search(rf"\b{re.escape(name.split(' (')[0])}\b", whole):
                return (f"this description is printed on {row.get('printedOn')} spacecraft, so "
                        f'naming "{name}" would put the wrong name on the others. Say "this '
                        'spacecraft" instead')
    if row.get("spacecraft"):
        source = f"{source} {row['spacecraft']}"

    allowed = set(numbers_of(source))
    for value in numbers_of(whole):
        if value not in allowed:
            return (f'the number "{value}" is not in this description. Use only numbers that '
                    "appear in it, or none at all")

    # 3. NAMES -- same test on names and designators.  An invented programme name is the
    #    most persuasive kind of wrong, because it reads exactly like the real ones.
    # Containment is tested against the SOURCE TEXT ITSELF, case-sensitively and on word
    # boundaries -- never against names_of(source). names_of() skips a sentence-initial
    # capital because capitalisation there says nothing about naming, so a description whose
    # sentence happens to START "Space Norway put ..." would otherwise refuse an honest
    # shortening that says "flown by Space Norway" in the middle of one.
    for name in names_of(whole):
        if re.search(rf"\b{re.escape(name)}\b", source):
            continue
        # Possessives and the adjective form are the SAME NAME. "China's" against a
        # description that says "Chinese", and "Chinese" against one that says "China",
        # invent nothing; refusing them was the test asking about spelling rather than about
        # containment, and it cost real answers on Yunyao and Yaogan.
        bare = re.sub(r"[\u2019']s$", "", name)
        if bare != name and re.search(rf"\b{re.escape(bare)}\b", source):
            continue
        root = DEMONYM.get(bare.lower())
        if root and re.search(rf"\b{root}", source, re.I):
            continue
        if bare.lower() in DEMONYM.values() and any(
                d for d, c in DEMONYM.items()
                if c == bare.lower() and re.search(rf"\b{d}", source, re.I)):
            continue
        return (f'"{name}" does not appear in this description. Every name in your version '
                "must be one this description already uses")

    # 4. HEDGING, BOTH WAYS -- see HEDGE above.  This is the check that makes a trim
    #    honest rather than merely short.
    source_hedged = bool(HEDGE.search(source))
    shaped_hedged = bool(HEDGE.search(whole))
    if source_hedged and not shaped_hedged:
        return ("this description attributes or qualifies its claim and your version states it "
                "flatly. Keep the wording that says who reported it or that it is not confirmed")
    if shaped_hedged and not source_hedged:
        return ("your version hedges a claim this description states plainly. Say it as plainly "
                "as the description does")

    # 5. SHAPE AND REGISTER.
    low = whole.lower()
    for phrase in BANNED:
        if phrase in low:
            return f'remove "{phrase.strip()}"'
    if not whole.rstrip().endswith((".", "!", "?", '"', "”")):
        return "does not end in a full stop"
    if '"' in whole or "“" in whole:
        quoted = re.findall(r"[“\"]([^”\"]{2,})[”\"]", whole)
        for q in quoted:
            if q.strip() not in source:
                return f'you put "{q.strip()}" in quotation marks; those words are not in the description'
    return None


def deterministic(row: dict) -> None:
    """There is no deterministic composition here, and that is the design.

    build_hedge_footnotes.py can compose a flat fallback because it owns the facts a
    footnote is made of.  A description is PROSE SOMEBODY RESEARCHED, and the only honest
    machine shortening of it is the first sentences that fit -- which cuts mid-argument and
    reads worse than the wall it replaced.  So a refused shaping ships NOTHING, the record
    keeps its original `purpose`, and the card renders exactly as it does today.
    """
    return None


# ---------------------------------------------------------------------------


def load_catalog(path: pathlib.Path) -> list:
    payload = json.loads(path.read_text())
    return payload["satellites"]


def build_rows(satellites: list) -> list:
    """One row per DISTINCT long description -- 139 of them behind 835 objects."""
    groups: dict[str, dict] = {}
    for sat in satellites:
        purpose = (sat.get("purpose") or "").strip()
        if len(purpose) <= SHAPE_ABOVE:
            continue
        key = text_key(purpose)
        entry = groups.setdefault(key, {"key": key, "text": purpose, "members": 0,
                                        "examples": []})
        entry["members"] += 1
        entry["examples"].append(sat.get("name"))
    rows = sorted(groups.values(), key=lambda r: (-len(r["text"]), r["key"]))
    for row in rows:
        # `id` is what the runner's `openIdsHash` cache key is built from, so a batch that
        # holds a different set of descriptions is a different cache entry and cannot be
        # skipped as "fresh" against another batch's answer.
        row["id"] = row["key"]
        row["chars"] = len(row["text"])
        row["example"] = row["examples"][0]
        # THE EXACT QUALIFIERS, not just a boolean. The first live wave refused batch after
        # batch for "your version states it flatly" while the model had no way to see WHICH
        # words it was supposed to keep -- a gate the prompt could not act on, which is the
        # failure deterministic-scaffolding.md §2c calls a rung-3 refusal wearing a rung-1
        # costume. Handing over the words turns it into something a model can do.
        row["qualifiers"] = sorted({m.group(0).lower() for m in HEDGE.finditer(row["text"])})
        row["hedged"] = bool(row["qualifiers"])
        row["printedOn"] = row["members"]
        row["spacecraft"] = row["examples"][0] if row["members"] == 1 else None
        # The FULL list, so the repository-side check can refuse a name on any of the 126
        # cards a description is printed on. emit_facts() ships the model a dozen of them --
        # enough to make the rule concrete, and the rule itself is "name none of them".
        row["doNotName"] = None if row["members"] == 1 else list(row["examples"])
        row["wordAim"] = SECTION_WORD_AIM
        row["wordCeiling"] = SECTION_WORDS
        row["wordCeilingPerParagraph"] = PARAGRAPH_WORDS
        row["maxChars"] = SECTION_MAX
        row["maxParagraphChars"] = PARAGRAPH_MAX
        row["minChars"] = SECTION_MIN
        del row["examples"]
    return rows


# ---------------------------------------------------------------------------
# WHY THIS SHIPS IN BATCHES, AND WHY THE BATCH SIZE IS SMALL.
#
# The house scaffold runner shows a `draft` stage ONE carry pool, capped at
# `groupBy.caps.charsPerGroup`, and `_carry` stops adding rows at the cap without
# saying so. 139 descriptions averaging 1,200 characters is 167 KB; every row past
# the cap would be invisible to the model AND invisible in the ledger -- the exact
# shape of the space-hedge-footnote failure, where an unstated ceiling wrote six of
# eight outputs out of existence while the run reported ok:true.
#
# So the batching is done HERE, where it is visible: each batch is its own source
# file, its own run, its own cache entry and its own row in the ledger, and
# `--drafts` refuses to finish quietly when a batch never came back (see `missing`).
# BATCH_CHARS is set so a batch's carry pool is comfortably inside charsPerGroup even
# if every row in it is the 2,425-character worst case.
# ---------------------------------------------------------------------------
BATCH_ROWS = 8
BATCH_CHARS = 11_000


def batches_of(rows: list) -> list:
    out, current, used = [], [], 0
    for row in rows:
        size = row["chars"] + 200          # the carried fields around the text
        if current and (len(current) >= BATCH_ROWS or used + size > BATCH_CHARS):
            out.append(current)
            current, used = [], 0
        current.append(row)
        used += size
    if current:
        out.append(current)
    return out


def emit_facts(rows: list, out_path: pathlib.Path = None, batch: int = None) -> None:
    all_rows = rows
    rows = [dict(r) for r in rows]
    for row in rows:
        if row.get("doNotName"):
            row["doNotName"] = row["doNotName"][:12]
    if batch is not None:
        groups = batches_of(rows)
        if not 0 <= batch < len(groups):
            raise SystemExit(f"batch {batch} out of range; there are {len(groups)}")
        rows = groups[batch]
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "what": ("One entry per DISTINCT satellite description longer than "
                 f"{SHAPE_ABOVE} characters in the published catalogue. Mirrored to the VPS as "
                 "infrastructure/scaffold-sources/space-purpose-shape-facts.json for the "
                 "`space-purpose-shape` scaffold tool; refresh it before forcing a run."),
        "format": {
            "lineChars": LINE_CHARS,
            "sectionMax": SECTION_MAX,
            "paragraphMax": PARAGRAPH_MAX,
            "sectionMin": SECTION_MIN,
            "measuredOn": ("the satellite card's .satellite-purpose column, 280.5 px wide at a "
                           "1440 px viewport, 11.6 px Inter on an 18.56 px line box; ASBM-1's "
                           "2,425 characters wrap to 53 lines there, median 46 per line"),
        },
        "batch": batch,
        "batchCount": len(batches_of(all_rows)),
        "distinctTexts": len(rows),
        "objectsCovered": sum(r["members"] for r in rows),
        "rows": rows,
    }
    target = out_path or FACTS
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n")
    where = target if not str(target).startswith(str(ROOT)) else target.relative_to(ROOT)
    print(f"wrote {where}: {len(rows)} distinct descriptions, "
          f"{payload['objectsCovered']} objects"
          + (f" (batch {batch} of {payload['batchCount']})" if batch is not None else ""))


def apply_drafts(rows: list, drafts: list) -> dict:
    by_key = {row["key"]: row for row in rows}
    accepted, refusals = {}, []
    seen = Counter()
    for item in drafts:
        key = item.get("key") or item.get("id")
        row = by_key.get(key)
        if row is None:
            refusals.append((key or "?", "no such description in this repository's catalogue"))
            continue
        seen[key] += 1
        if seen[key] > 1:
            refusals.append((key, "answered twice; the second answer is discarded"))
            continue
        reason = check(item, row)
        if reason:
            refusals.append((key, f'{row["example"]}: {reason}'))
            continue
        paras = paragraphs_of(item)
        accepted[key] = {
            "paragraphs": paras,
            "chars": sum(len(p) for p in paras),
            "sourceChars": row["chars"],
            "members": row["members"],
            "example": row["example"],
            "by": "model",
        }
    missing = [r["key"] for r in rows if r["key"] not in seen]
    return {"accepted": accepted, "refusals": refusals, "missing": missing}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", default=None,
                        help="published catalogue artifact; default: the one manifest.json names")
    parser.add_argument("--emit-facts", action="store_true")
    parser.add_argument("--out", default=None, help="where --emit-facts writes")
    parser.add_argument("--batch", type=int, default=None,
                        help="emit only this batch (0-based); see batches_of()")
    parser.add_argument("--batch-count", action="store_true",
                        help="print how many batches the descriptions divide into, and exit")
    parser.add_argument("--drafts", nargs="*", default=None,
                        help="one or more cached `items` arrays, or directories of them")
    args = parser.parse_args(argv)

    if args.catalog:
        catalog = pathlib.Path(args.catalog)
    else:
        manifest = json.loads((ROOT / "public/data/manifest.json").read_text())
        catalog = ROOT / "public/data" / manifest["catalog"]["path"]
    rows = build_rows(load_catalog(catalog))

    if args.batch_count:
        print(len(batches_of(rows)))
        return 0
    if args.emit_facts:
        emit_facts(rows, pathlib.Path(args.out) if args.out else None, args.batch)
        return 0

    drafts, files = [], []
    for name in args.drafts or []:
        path = pathlib.Path(name)
        files.extend(sorted(path.glob("*.json")) if path.is_dir() else [path])
    for path in files:
        raw = json.loads(path.read_text())
        drafts.extend(raw.get("items") if isinstance(raw, dict) else raw)
    if files:
        print(f"read {len(drafts)} drafts from {len(files)} file(s)")

    result = apply_drafts(rows, drafts or [])
    for key, reason in result["refusals"]:
        print(f"REFUSED {key}: {reason}", file=sys.stderr)
    if result["missing"]:
        print(f"NOT SHAPED ({len(result['missing'])} descriptions had no draft): "
              f"{', '.join(result['missing'][:6])}"
              f"{' …' if len(result['missing']) > 6 else ''}", file=sys.stderr)

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "what": ("Two-paragraph openings for the long satellite descriptions, keyed by the "
                 "sha256 prefix of the published description they were made from. A card whose "
                 "description is not in here renders it exactly as it always has."),
        "format": {"lineChars": LINE_CHARS, "sectionMax": SECTION_MAX,
                   "paragraphMax": PARAGRAPH_MAX, "sectionMin": SECTION_MIN},
        "shapeAbove": SHAPE_ABOVE,
        "distinctTexts": len(rows),
        "objectsInScope": sum(r["members"] for r in rows),
        "shaped": len(result["accepted"]),
        "objectsShaped": sum(v["members"] for v in result["accepted"].values()),
        "refused": [{"key": k, "why": w} for k, w in result["refusals"]],
        "notShaped": result["missing"],
        "entries": result["accepted"],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {payload['shaped']}/{len(rows)} descriptions shaped, "
          f"{payload['objectsShaped']}/{payload['objectsInScope']} objects; "
          f"{len(result['refusals'])} refused")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
