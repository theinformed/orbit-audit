#!/usr/bin/env python3
"""Which satellites are under-described, ranked by how much it matters.

Why this module exists
----------------------
On 2026-08-19 four agents took the catalog from "2,516 objects with no real
description" down to a number small enough to read out loud, and the objects
that survived the sweep were not the ones anyone predicted.  They were not
anonymous picosats.  They were PAZ (a Spanish X-band radar imaging satellite),
SUOMI100, the four-spacecraft German S-NET, EAGLET 1, YOUTHSAT -- documented
spacecraft that fell between the seams of four owner-partitioned work packages
(China / Russia-CIS / United States / rest of the world).

What is wanted is a tracker of which satellites are UNDER-described.  The word
that matters there is *under*.

A present/absent check is the easy half and the useless half.  It reports the
objects whose card openly says "we do not know", which are already the honest
ones.  It cannot see the far larger population whose card looks completely
fine: a paragraph of accurate family prose about Starlink, or OneWeb, or
Yaogan, attached to a spacecraft the paragraph never mentions and could not
distinguish from four thousand siblings.  That card is not wrong.  It is also
not about the object the reader clicked.

The bar this module grades against was set by the GPS work: every GPS card
names its own block, flight, SVN, PRN, orbital plane and slot.  That is what
"described" means on this site.  Ten dimensions below measure distance from
that bar, and every one of them is computed from the published artifact, so a
reviewer can disagree with a rule rather than having to re-derive a fact.

What this module is NOT
-----------------------
It is not ``catalog_audit.py`` and must not become it.  That module is a
*contradiction detector*: its contract is that it can prove a displayed claim
disagrees with authoritative registry data, and it deliberately cannot say
anything is right.  This module measures *sufficiency*, which is a different
question with a different answer shape -- an object can be perfectly
uncontradicted and still tell the reader nothing.  Folding sufficiency into a
contradiction detector would blunt the asymmetry that makes that module
trustworthy.  It does reuse its helpers, because the parsing of name rules out
of ``build_release.py`` is worth having once.

Every check is offline and deterministic except one.  Source liveness needs the
network, so it is opt-in (``--check-sources``), cached on disk with a long TTL,
rate-limited per host, and it reports a 403 as *unverifiable*, never as dead --
several publishers and every .mil host refuse automated clients, and a sibling
agent confirmed three such by hand.  A dead-link column that cries wolf is
worse than no column at all.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import datetime as dt
import html
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.catalog_audit import (  # noqa: E402
    extract_name_rule_fragments,
    fragment_matches_substring,
    fragment_matches_tokens,
    load_catalog,
    load_registry,
    name_tokens,
    resolve_catalog_path,
)

MAIN_TS = ROOT / "src" / "main.ts"
# The rotation moved out of main.ts on 2026-08-21 so a Playwright spec could
# import it: a spec cannot import main.ts at all, because its first line is
# `import "./styles.css"`, and the two specs that worked around that by
# hard-coding "GPS" expired at the next UTC midnight. main.ts re-exports every
# name, so nothing else changed — but this parser reads a literal, and a
# re-export is not one.
FEATURED_TS = ROOT / "src" / "featured-constellation.ts"
DEFAULT_HTML = ROOT / "public" / "data" / "review" / "satellite-coverage.html"
DEFAULT_JSON = ROOT / "public" / "data" / "review" / "satellite-coverage.json"


# ---------------------------------------------------------------------------
# The bar
# ---------------------------------------------------------------------------
# The three sentences build_release emits when it has nothing.  They are honest
# and they are exactly what the tracker exists to count, so they are read out
# of the generator rather than retyped here -- a retyped sentence is a dead
# rule waiting to happen, and this project has shipped six of those.
UNKNOWN_TEMPLATE_MARKERS: tuple[str, ...] = (
    "No public source names this spacecraft's payload",
    "The public catalog does not identify this spacecraft's payload",
    "The public catalog does not provide a verified mission description",
)

# The per-object tail build_release appends when it can say something specific
# about this registry record and nothing else.  Its presence means the sentence
# is at least partly about *this* object.
# RETIRED 2026-08-20. `REGISTRY_TAIL` was "This object's registry record:", the
# opening of a sentence build_release appended to 1,205 descriptions listing the
# object's altitude, period, launch date, launch group and registering state.
# That sentence was removed -- every fact in it is already a row in the
# Satellite Details grid on the same screen -- so the tracker no longer accepts
# it as a per-object anchor. Cards that qualified ONLY through it now grade
# `no-per-object-detail`, which is the honest reading: a family paragraph that
# names nothing about this particular spacecraft. Do not reinstate this as an
# anchor; reinstating it would mean the sentence is back on the cards.

# A classification basis that was corroborated against something outside the
# spacecraft's own name.  Anything else draws the "claimed, not corroborated"
# chip on the card, and the tracker should agree with the chip.
# The bases the FRONT END counts as corroborated -- read from src/main.ts, not
# decided here. `radio-licence` is in that set and is deliberately not in the
# pipeline's equivalent, which src/main.ts says in as many words.
CORROBORATED_BASES = frozenset({"norad-id", "exact-name", "web-corroborated", "radio-licence"})

# The bases that draw the card's "claimed, not corroborated" chip.
WEAK_BASES = frozenset({"name-pattern", "source-group", "unclassified"})

# The bases that corroborate nothing about the MISSION, which is the question a
# description exists to answer. `radio-licence` is here and not above on
# purpose: an ITU filing is genuinely strong evidence, tied to this object, and
# about its transmitter. PAZ is a Spanish X-band SAR imaging satellite and its
# licence says "Earth Exploration service", which is true, cited, corroborated
# and not what the spacecraft is for. That gap is the entire reason this
# tracker grades sufficiency separately from correctness.
MISSION_UNCORROBORATED_BASES = WEAK_BASES | frozenset({"radio-licence"})

# Language that concedes the site is not certain.  A card that hedges in prose
# while its chip says "high confidence" is telling the reader two things.  That
# contradiction is what drove the chip redesign after Tianmu-111.
HEDGES: tuple[str, ...] = (
    "assessed", "reportedly", "is believed", "believed to", "apparently",
    "widely reported", "has not confirmed", "does not say", "not been disclosed",
    "undisclosed", "no public source", "presumed", "thought to be",
    "announces these launches only",
)

# Below this, a description is one sentence.  Chosen from the catalog itself:
# the shared Starlink line is 137 characters and is the canonical example of a
# description that reads complete and says nothing per-object, so the floor sits
# just above it.  Sensitivity at other floors is reported, not hidden.
LENGTH_FLOOR = 160
LENGTH_FLOORS_REPORTED = (140, 160, 220, 300, 400)

# The owner partitions the 2026-08-19 sweep was split into.  Used only to
# attribute a cause, never to grade.
SWEPT_PARTITIONS: dict[str, frozenset[str]] = {
    "United States": frozenset({"US", "ISS"}),
    "China": frozenset({"PRC"}),
    "Russia / CIS": frozenset({"CIS"}),
}

# Missions a naval / METOC audience is paid to care about, and what that is
# worth in the ranking.  Grounded in the catalog's own `mission` vocabulary and
# in the display priority the site itself applies (see `density_rank`).
METOC_MISSION_WEIGHT: dict[str, int] = {
    "weather": 30,
    "missile-warning": 22,
    "navigation": 22,
    "signals-intelligence": 14,
    "human-spaceflight": 10,
    "earth-observation": 8,
    "communications": 4,
    "science": 4,
}


@dataclasses.dataclass(frozen=True)
class Dimension:
    key: str
    weight: int
    title: str
    why: str


DIMENSIONS: tuple[Dimension, ...] = (
    Dimension(
        "no-description", 100,
        "No description at all",
        "The card openly says the payload is unknown, and nothing else explains "
        "the gap. Honest, and the thing a reader came for is missing.",
    ),
    Dimension(
        "class-not-object", 60,
        "Describes the class, not the object",
        "purposeKind is 'class': the card explains what kind of thing this is, why "
        "nobody has published a mission for it, and how long its orbit will last. "
        "Correct and honestly labelled — a dispenser slot or a builder serial from "
        "a rideshare cohort. Listed apart from the other two so a sweep does not "
        "waste time hunting a mission that was never published.",
    ),
    Dimension(
        # Weighted level with `no-description`, not below it. The reader's
        # question goes equally unanswered, and unlike an honest apology this
        # card LOOKS answered: real prose, a real citation, a solid
        # 'corroborated' chip, and no caveat row. See the exemptions table for
        # the two carve-outs that make that happen.
        "licence-only", 100,
        "Radio licence stands in for the mission",
        "The description is about the spectrum the transmitter is licensed for, "
        "not about what the spacecraft does. PAZ is a Spanish X-band SAR imaging "
        "satellite and its card says 'ITU Earth Exploration service' — true, "
        "cited, corroborated, and not the mission. These are documented "
        "spacecraft, so unlike the class cards below they are fixable by reading.",
    ),
    Dimension(
        "dead-source", 80,
        "The citation no longer resolves",
        "A source URL that 404s is silent rot: the card still shows a citation "
        "and the citation is gone. A 403 is NOT counted here.",
    ),
    Dimension(
        "no-source", 60,
        "A claim with no citation",
        "The description asserts something and points at nothing.",
    ),
    Dimension(
        "no-per-object-detail", 40,
        "Family prose, nothing about THIS object",
        "The text is shared verbatim with at least one sibling and contains no "
        "anchor unique to this spacecraft. The GPS cards set the bar: block, "
        "flight, SVN, PRN, plane, slot.",
    ),
    Dimension(
        "never-names-itself", 15,
        "Names neither itself nor its family",
        "The text does not contain even the alphabetic stem of the object's name, "
        "and is shared with siblings. Graded only in combination, because on its "
        "own it fires on 9.6% of the catalog including cards that are plainly "
        "about their object — CALSPHERE 1's card opens 'A passive metal sphere'. "
        "A dimension that noisy would train a reader to ignore the column.",
    ),
    Dimension(
        "thin", 10,
        f"Shorter than {LENGTH_FLOOR} characters",
        "One sentence. Enough for a label, not for a teaching card.",
    ),
    Dimension(
        "weak-classification", 10,
        "Claimed, not corroborated",
        "classificationBasis is name-pattern, source-group or unclassified — the "
        "substring guess that put a NASA mission statement on SKYTERRA 1.",
    ),
    Dimension(
        "confidence-conflict", 50,
        "Confidence and evidence disagree",
        "High confidence on a weak basis, or high confidence over a contested "
        "attribution, or hedged prose under a high-confidence chip. Tianmu-111.",
    ),
    Dimension(
        "contested-attribution", 20,
        "Attribution is contested",
        "Someone disputes who this belongs to. Not a defect; a card that needs "
        "a human eye.",
    ),
)

DIMENSION_BY_KEY = {d.key: d for d in DIMENSIONS}


# ---------------------------------------------------------------------------
# Prominence, taken from the site rather than from an opinion
# ---------------------------------------------------------------------------


def featured_constellations(source: Path = FEATURED_TS) -> list[str]:
    """The rotation the site opens on, read out of the front end.

    Hardcoding this list here would let it drift silently the first time the
    rotation changed.  It is a plain array literal; parse it.
    """
    text = source.read_text(encoding="utf-8")
    match = re.search(
        r"FEATURED_CONSTELLATIONS\s*:\s*readonly\s+string\[\]\s*=\s*\[(.*?)\]",
        text, re.S,
    )
    if not match:
        raise RuntimeError(
            f"FEATURED_CONSTELLATIONS not found in {source}; the tracker's notion of "
            "prominence is the site's, so this is a hard failure rather than a default"
        )
    return re.findall(r'"([^"]+)"', match.group(1))


def density_rank(record: dict[str, Any]) -> int:
    """What the site draws first, reimplemented from `src/main.ts` densityRank.

    The default view draws at most 450 markers, chosen by this ordering.  An
    object inside that ceiling is one a visitor sees without asking, so an
    under-described card there costs more than the same card on an object
    nobody reaches.  `check_density_rank_matches_front_end` guards the copy.
    """
    if record.get("purposeKind") == "curated":
        return 0
    mission = record.get("mission")
    if mission in ("weather", "missile-warning", "human-spaceflight"):
        return 1
    if record.get("sector") == "military":
        return 2
    if mission in ("navigation", "science", "earth-observation"):
        return 3
    if record.get("constellation") is None:
        return 4
    return 6


def check_density_rank_matches_front_end(source: Path = MAIN_TS) -> list[str]:
    """Cheap anti-drift guard: every token this copy branches on must still
    appear inside the front end's own densityRank body."""
    text = source.read_text(encoding="utf-8")
    start = text.find("private densityRank(")
    if start < 0:
        return ["densityRank not found in src/main.ts"]
    body = text[start:start + 900]
    missing = [
        token for token in
        ("curated", "weather", "missile-warning", "human-spaceflight", "military",
         "navigation", "science", "earth-observation")
        if f'"{token}"' not in body
    ]
    return [f"densityRank drifted: {missing} no longer in the front end"] if missing else []


# ---------------------------------------------------------------------------
# What the front end already forgives
# ---------------------------------------------------------------------------
# A completeness check whose exemptions nobody can list is not a check. The
# site has two, both deliberate, both defensible, and together they are why the
# 38 SatNOGS radio-licence cards were invisible: `hasPublishedDescription()`
# matches on content and their opening is not in its list, so they count as
# described; and the front end's own CORROBORATED_BASES includes
# `radio-licence`, so their chip reads corroborated. A reader gets a card with
# a corroborated chip, no "no published description" caveat, and prose whose
# first sentence is "The public catalog does not identify this spacecraft's
# payload."
#
# These are read out of src/main.ts rather than restated here, so the page
# cannot quietly disagree with the code it is describing.


def _ts_string_array(source: str, name: str) -> list[str]:
    match = re.search(rf"{name}\s*=\s*\[(.*?)\]", source, re.S)
    return re.findall(r'"((?:[^"\\]|\\.)*)"', match.group(1)) if match else []


def _ts_record_keys(source: str, name: str) -> list[str]:
    """The keys of a `Record<string, string>` literal in the site's source."""
    match = re.search(rf"{name}[^=]*=\s*\{{(.*?)\n\}};", source, re.S)
    return re.findall(r'"([^"]+)":', match.group(1)) if match else []


def _ts_string_set(source: str, name: str) -> list[str]:
    match = re.search(rf"{name}\s*=\s*new Set\(\[(.*?)\]\)", source, re.S)
    return re.findall(r'"([^"]+)"', match.group(1)) if match else []


def front_end_exemptions(catalog: dict[str, Any],
                         source: Path = MAIN_TS) -> list[dict[str, Any]]:
    """Every carve-out the site applies, with what each one currently lets past."""
    text = source.read_text(encoding="utf-8")
    records = catalog["satellites"]
    rows: list[dict[str, Any]] = []

    prefixes = _ts_string_array(text, "TEMPLATE_PURPOSE_PREFIXES")
    for prefix in prefixes:
        rows.append({
            "where": "hasPublishedDescription() / TEMPLATE_PURPOSE_PREFIXES",
            "rule": f"an opening of {prefix!r} means 'no published description'",
            "objects": sum(1 for r in records
                           if str(r.get("purpose") or "").startswith(prefix)),
            "effect": "the card drops its Satellite Background section and gains a "
                      "'No published source names this object's payload' row",
        })

    described_anyway = [
        r for r in records
        if is_unknown_template(r)
        and not any(str(r.get("purpose") or "").startswith(prefix) for prefix in prefixes)
    ]
    rows.append({
        "where": "hasPublishedDescription() — the gap between its list and ours",
        "rule": "an opening this tracker reads as 'we do not know' that the front "
                "end's prefix list does not cover",
        "objects": len(described_anyway),
        "effect": "the card counts as DESCRIBED and shows no caveat row, while its "
                  "first sentence says the payload is not identified",
    })

    # The fleet carve-out, read out of the site rather than restated here. It is
    # the largest exemption on this page by two orders of magnitude, so it is
    # listed with the others rather than being the one nobody can see.
    for kind in _ts_record_keys(text, "MISSION_CORROBORATION_EVIDENCE"):
        rows.append({
            "where": "src/main.ts MISSION_CORROBORATION_EVIDENCE",
            "rule": f"missionCorroboration {kind!r} draws a solid 'corroborated' chip "
                    "whatever the basis says",
            "objects": sum(1 for r in records if r.get("missionCorroboration") == kind),
            "effect": "the card states a mission class its own fleet agrees with, and does "
                      "not mark it claimed; the object's individual identity is still "
                      "unestablished and the chip does not speak to it",
        })

    front = set(_ts_string_set(text, "CORROBORATED_BASES"))
    if front:
        # Only the bases the site calls corroborated that corroborate nothing
        # about the mission -- today that is exactly `radio-licence`.
        for basis in sorted(front & MISSION_UNCORROBORATED_BASES):
            rows.append({
                "where": "src/main.ts CORROBORATED_BASES",
                "rule": f"basis {basis!r} draws a solid 'corroborated' chip",
                "objects": sum(1 for r in records
                               if r.get("classificationBasis") == basis),
                "effect": "true about the transmitter, and the chip is read as being "
                          "about the mission; the pipeline's own table omits this basis",
            })
    return rows


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------


def _designator_tokens(name: str) -> list[str]:
    """The parts of a name that could tell two siblings apart."""
    return [
        token for token in re.split(r"[^A-Z0-9\-]+", name.upper())
        if token and any(character.isdigit() for character in token)
    ]


def has_per_object_anchor(record: dict[str, Any]) -> bool:
    """Does the description say anything only true of THIS object?

    Two ways to qualify, in descending order of how much they prove:
      * the object's own name appears in the text;
      * a digit-bearing token from the name appears in the text (STARLINK-1012
        -> "1012"), which is how the GPS cards carry SVN and PRN.

    There was a third until 2026-08-20: an appended registry read-out. It is
    gone from the cards, so it is gone from here -- see the note by the retired
    `REGISTRY_TAIL` constant above.
    """
    text = str(record.get("purpose") or "")
    upper = text.upper()
    bare = record["name"].upper().split("(")[0].strip()
    if bare and bare in upper:
        return True
    return any(token in upper for token in _designator_tokens(record["name"]))


def name_stem(name: str) -> str:
    """The alphabetic head of a name: STARLINK-1012 -> STARLINK, S-NET B -> S."""
    parts = re.split(r"[^A-Za-z]+", name.strip())
    return (parts[0] if parts else "").upper()


def names_its_family(record: dict[str, Any]) -> bool:
    stem = name_stem(record["name"])
    return not stem or stem in str(record.get("purpose") or "").upper()


def is_unknown_template(record: dict[str, Any]) -> bool:
    text = str(record.get("purpose") or "")
    return any(text.startswith(marker) for marker in UNKNOWN_TEMPLATE_MARKERS)


def hedges_in(text: str) -> list[str]:
    lowered = text.lower()
    return [hedge for hedge in HEDGES if hedge in lowered]


def grade_record(
    record: dict[str, Any],
    shared_counts: collections.Counter,
    liveness: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Every dimension this object fails, with the evidence for each."""
    gaps: list[dict[str, Any]] = []
    text = str(record.get("purpose") or "")
    source = str(record.get("purposeSource") or "")
    basis = str(record.get("classificationBasis") or "")
    confidence = str(record.get("classificationConfidence") or "")
    # Published beside the basis, never instead of it. Where a fleet vouched for
    # this object's mission class the card draws a SOLID chip, so the sentence
    # this tracker prints about that card has to say so too — a page that
    # describes the site wrongly is the defect it exists to catch.
    corroboration = str(record.get("missionCorroboration") or "")

    def add(key: str, detail: str, **evidence: Any) -> None:
        gaps.append({"dimension": key, "detail": detail, "evidence": evidence})

    # Three disjoint answers to "why does this card not describe the object",
    # because merging them hides which sweep would fix which.
    if basis == "radio-licence":
        service = re.search(r"ITU (\w[\w \-]*?) service", text)
        add("licence-only",
            "the description is about the spectrum this object's transmitter is "
            "licensed for, not about what the spacecraft does",
            ituService=service.group(1) if service else None)
    elif record.get("purposeKind") == "class":
        add("class-not-object",
            "the card describes the class of object rather than this spacecraft, "
            "and says so",
            opening=text[:90])
    elif is_unknown_template(record):
        add("no-description",
            "the description is the generator's own 'we do not know' sentence",
            opening=text[:90])

    if not source.startswith("http"):
        add("no-source", "no citation on a card that asserts a purpose",
            purposeSource=record.get("purposeSource"))
    else:
        verdict = liveness.get(source)
        if verdict and (
            verdict.get("state") == "dead"
            or (verdict.get("state") == "dns-failure"
                and verdict.get("strikes", 0) >= DNS_STRIKES_FOR_DEAD)
        ):
            add("dead-source",
                f"the citation returned {verdict.get('status')} when last checked"
                + (f" on {verdict.get('strikes')} separate runs"
                   if verdict.get("state") == "dns-failure" else ""),
                url=source, status=verdict.get("status"), checkedAt=verdict.get("checkedAt"))

    shared_by = shared_counts[text]
    if shared_by > 1 and not has_per_object_anchor(record):
        add("no-per-object-detail",
            f"this exact text is on {shared_by:,} objects and names nothing "
            "that distinguishes this one",
            sharedBy=shared_by)

    if shared_by > 1 and not names_its_family(record):
        add("never-names-itself",
            "the text names neither this object nor the alphabetic stem of its name, "
            f"and {shared_by:,} objects carry it",
            stem=name_stem(record["name"]))

    if len(text) < LENGTH_FLOOR:
        add("thin", f"{len(text)} characters", length=len(text))

    if basis in WEAK_BASES and corroboration:
        add("weak-classification",
            f"classified by {basis}; the MISSION CLASS is corroborated by this object's "
            f"own fleet ({corroboration}), so the card draws a solid chip, but nothing has "
            "been checked against this spacecraft and which unit of the fleet it is "
            "remains unestablished",
            basis=basis, missionCorroboration=corroboration)
    elif basis in WEAK_BASES:
        add("weak-classification",
            f"classified by {basis}, which the card labels 'claimed, not corroborated'",
            basis=basis)
    elif basis == "radio-licence":
        add("weak-classification",
            "classified from an ITU spectrum filing, which corroborates what the "
            "transmitter is licensed for and nothing about the mission; the front "
            "end counts this basis as corroborated and the pipeline does not",
            basis=basis, frontEndCallsItCorroborated=True)

    conflicts: list[str] = []
    if confidence == "high" and basis in WEAK_BASES:
        conflicts.append(f"confidence 'high' resting on basis {basis!r}")
    if confidence == "high" and record.get("contestedAttribution"):
        conflicts.append("confidence 'high' over a contested attribution")
    found_hedges = hedges_in(text)
    if confidence == "high" and found_hedges:
        conflicts.append(f"confidence 'high' over hedged prose {found_hedges}")
    if conflicts:
        add("confidence-conflict", "; ".join(conflicts),
            basis=basis, confidence=confidence, hedges=found_hedges)

    if record.get("contestedAttribution"):
        add("contested-attribution", "attribution is disputed",
            note=str(record.get("contestedAttribution"))[:200])

    return gaps


# ---------------------------------------------------------------------------
# Cause attribution -- "why is this one still like this?"
# ---------------------------------------------------------------------------


def catalog_as_of(catalog: dict[str, Any]) -> dt.date:
    stamp = str(catalog.get("upstreamAsOf") or "")
    try:
        return dt.datetime.fromisoformat(stamp.replace("Z", "+00:00")).date()
    except ValueError:
        return dt.date.today()


def attribute_cause(record: dict[str, Any], gaps: Sequence[dict[str, Any]],
                    as_of: dt.date) -> str:
    """One plain-English reason, chosen so the reasons name real work packages."""
    keys = {gap["dimension"] for gap in gaps}
    owner = str(record.get("ownerCode") or "")
    swept = any(owner in codes for codes in SWEPT_PARTITIONS.values())

    launched = str(record.get("launchDate") or "")
    recent = False
    try:
        recent = (as_of - dt.date.fromisoformat(launched)).days <= 240
    except ValueError:
        pass

    if "licence-only" in keys:
        # Corrected 2026-08-20: these are not a gap between the four owner
        # partitions. They are the SatNOGS radio-licence lane's own output --
        # documented spacecraft to which a lane attached a spectrum filing in
        # place of a mission. A lane producing weak prose is a different and
        # more tractable cause than a seam, and it is fixed by changing the
        # lane, not by sweeping an owner.
        return "the radio-licence lane wrote a spectrum filing in place of a mission"
    if "class-not-object" in keys:
        return "honestly unknown: a rideshare dispenser slot or builder serial"
    if keys & {"no-description", "no-source"}:
        if recent:
            return "launched too recently for any sweep to have reached it"
        if not swept:
            return "fell between the owner partitions (not US, China or Russia/CIS)"
        return f"inside the {owner} partition that was swept, and still unwritten"
    if "dead-source" in keys:
        return "the citation rotted after it was written"
    if "no-per-object-detail" in keys:
        constellation = record.get("constellation")
        if constellation:
            return f"{constellation} has family prose and no per-object writing"
        return "shares a template with unrelated objects and has no per-object writing"
    if keys & {"confidence-conflict", "contested-attribution"}:
        return "the evidence and the confidence chip disagree"
    if "weak-classification" in keys:
        return "classified from its name alone and never corroborated"
    return "minor shortfall only"


# ---------------------------------------------------------------------------
# Importance -- what to fix FIRST
# ---------------------------------------------------------------------------


def importance(record: dict[str, Any], featured: Sequence[str],
               group_size: int) -> tuple[int, list[str]]:
    """A score, and the plain reasons that produced it.

    Nothing here is an opinion about spacecraft.  Every term is either the
    site's own display priority, the catalog's own mission vocabulary, or a
    count of objects that share the defect.
    """
    score = 0
    reasons: list[str] = []

    if record.get("constellation") in featured:
        score += 40
        reasons.append(f"{record['constellation']} is in the site's featured rotation")

    rank = density_rank(record)
    if rank <= 3:
        bump = (4 - rank) * 8
        score += bump
        reasons.append(f"the site draws it in the default view (density rank {rank})")

    mission = str(record.get("mission") or "")
    weight = METOC_MISSION_WEIGHT.get(mission, 0)
    if weight:
        score += weight
        reasons.append(f"{mission} matters to a METOC / naval reader")
    if record.get("sector") == "military":
        score += 12
        reasons.append("military sector")
    if record.get("programmes"):
        score += 10
        reasons.append("attached to a programme the site documents")

    if group_size > 1:
        # Capped at the value a 200-object group earns. Uncapped, Starlink's
        # 4,660 identical cards outrank everything on the site for ever, and
        # they are also the one group whose per-object detail would come from
        # the launch group and orbital shell rather than from anyone writing
        # 4,660 paragraphs. The cap keeps a real signal from becoming a rut.
        bump = min(30, int(round(14 * math.log10(group_size))))
        score += bump
        reasons.append(f"the same gap covers {group_size:,} objects")

    epoch = str((record.get("omm") or {}).get("EPOCH") or "")
    if not epoch:
        score -= 20
        reasons.append("no current element set, so it is not on the globe")

    return score, reasons


def gap_weight(gaps: Sequence[dict[str, Any]]) -> int:
    return sum(DIMENSION_BY_KEY[gap["dimension"]].weight for gap in gaps)


# ---------------------------------------------------------------------------
# Dead classification rules -- the same failure class, at repo level
# ---------------------------------------------------------------------------


def dead_name_rules(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    """Classification fragments in build_release.py that reach nothing.

    Six of these have shipped dead on this project, which is the coverage
    question asked from the other end: a rule that matches nothing is a
    description no reader will ever see.

    Two different answers, kept apart on purpose.  A fragment that matches no
    object among the published 8,000 but does match a registry name is not
    dead -- the selection simply did not pick that object up, which is a much
    smaller thing.  Only a fragment that matches nothing in either place is
    reported as dead, so this never contradicts the release guard.
    """
    catalog_names = [record["name"] for record in catalog["satellites"]]
    registry = load_registry()
    registry_names = sorted({
        str(row.get("SATNAME") or row.get("OBJECT_NAME") or "").strip()
        for row in list(registry.spacetrack_satcat.values())
        + list(registry.celestrak_satcat.values())
    } - {""})

    def hits(names: Sequence[str], fragment: str) -> int:
        return sum(
            1 for name in names
            if fragment_matches_tokens(fragment, name_tokens(name))
            or fragment_matches_substring(fragment, name)
        )

    out: list[dict[str, Any]] = []
    for constellation, fragments in extract_name_rule_fragments().items():
        for fragment in fragments:
            in_catalog = hits(catalog_names, fragment)
            if in_catalog:
                continue
            in_registry = hits(registry_names, fragment) if registry_names else None
            if in_registry:
                continue
            out.append({
                "constellation": constellation,
                "fragment": fragment,
                "registryChecked": bool(registry_names),
            })
    return out


# ---------------------------------------------------------------------------
# Source liveness -- the only part of this module that touches the network
# ---------------------------------------------------------------------------
# Written to the house rules in RUNBOOK.md and docs/OPEN-WORK.md section 0:
# one request at a time, a User-Agent naming a person who can be complained to,
# a hard interval floor, and a STOP on anything unexpected rather than a retry.
# CelesTrak is never contacted from here under any circumstance -- that is a
# legal boundary, not a courtesy one, and this lane has no reason to want it.

#: Named so a webmaster reading their logs can tell who this is and complain to
#: a person rather than to a firewall. This project was banned by CelesTrak once.
USER_AGENT = (
    "space-teaching-aid-coverage/1.0 "
    "(Space Environment Explorer, a Navy Space Cadre teaching site; "
    "checking that our own citations still resolve; contact sdegan@gmail.com)"
)

#: The same courtesy floor the SatNOGS lane uses, applied PER HOST: these are a
#: thousand unrelated publishers and making starlink.com wait for esa.int would
#: lengthen the sweep without making it kinder to anyone.
MIN_REQUEST_INTERVAL_S = 1.2

#: And a global floor on top of it, because a per-host limit alone permits two
#: hundred simultaneous strangers being contacted inside a second. That is not
#: rude to any one of them and it is exactly the shape of traffic that makes a
#: shared host's operator reach for a firewall rule.
MIN_GLOBAL_INTERVAL_S = 0.3

#: A citation that resolved is not going to stop resolving this week, and a
#: sweep that costs a thousand requests every build would simply be turned off.
LIVENESS_MAX_AGE_S = 30 * 24 * 3600
#: A dead one is re-checked sooner, because "we fixed it" is the outcome we want.
DEAD_RECHECK_MAX_AGE_S = 7 * 24 * 3600

#: Never more than this many URLs in one run, so an accidental cron loop cannot
#: turn into a thousand-request burst against a thousand strangers.
DEFAULT_URL_BUDGET = 250

LIVENESS_CACHE_DIR = ROOT / "pipeline" / ".cache" / "coverage-liveness"
LIVENESS_CACHE_FILE = LIVENESS_CACHE_DIR / "liveness.json"

DISABLE_LIVENESS = os.environ.get("SPACE_EXPLORER_DISABLE_COVERAGE_LIVENESS") == "1"


class LivenessRefused(RuntimeError):
    """The default transport refuses to touch the network without --check-sources."""


_LAST_REQUEST_AT: dict[str, float] = {}
_LAST_REQUEST_ANY = 0.0


def _throttle(host: str, sleep=time.sleep) -> None:
    global _LAST_REQUEST_ANY
    now = time.monotonic()
    wait = max(
        MIN_REQUEST_INTERVAL_S - (now - _LAST_REQUEST_AT.get(host, 0.0)),
        MIN_GLOBAL_INTERVAL_S - (now - _LAST_REQUEST_ANY),
    )
    if wait > 0:
        sleep(wait)
    _LAST_REQUEST_AT[host] = _LAST_REQUEST_ANY = time.monotonic()


def offline_probe(url: str) -> dict[str, Any]:
    """The default. Refuses, loudly, the way discovery_literature does."""
    raise LivenessRefused(
        f"refusing to fetch {url}: source liveness does not touch the network "
        "unless --check-sources is passed explicitly"
    )


def urllib_probe(url: str, timeout: int = 20, *, opener=None, sleep=time.sleep) -> dict[str, Any]:
    """One citation, classified into exactly three outcomes.

    * ``live``          -- it answered, at all, with something that is not a
                           404 or a 410.
    * ``dead``          -- 404 or 410, or the host does not resolve.  Only these
                           are reported as rot.
    * ``unverifiable``  -- 403, 401, 429, a timeout, a TLS failure.  A sibling
                           agent confirmed by hand that three publishers and
                           every .mil host in the catalog refuse automated
                           clients outright.  **A 403 is not a dead link.**
                           Saying so would put a false accusation next to a
                           perfectly good citation, and the tracker would stop
                           being believed the first time someone checked.

    HEAD first because it costs the publisher no body.  Some servers answer 405
    or 501 to a HEAD they would have served; those fall back to a GET asking for
    the first two kilobytes only.
    """
    host = urllib.parse.urlsplit(url).netloc
    _throttle(host, sleep=sleep)
    open_url = opener or urllib.request.urlopen

    def attempt(method: str, headers: dict[str, str]) -> dict[str, Any]:
        request = urllib.request.Request(url, method=method, headers={
            "User-Agent": USER_AGENT, **headers,
        })
        with open_url(request, timeout=timeout) as response:
            return {"state": "live", "status": response.status, "method": method}

    try:
        try:
            return attempt("HEAD", {})
        except urllib.error.HTTPError as error:
            if error.code not in (405, 501, 403):
                raise
            # 403 to a HEAD is often a WAF that would have served a GET.
            _throttle(host, sleep=sleep)
            return attempt("GET", {"Range": "bytes=0-2047"})
    except urllib.error.HTTPError as error:
        if error.code in (404, 410):
            return {"state": "dead", "status": error.code}
        return {"state": "unverifiable", "status": error.code,
                "note": "the host refused an automated client; NOT a dead link"}
    except urllib.error.URLError as error:
        reason = str(getattr(error, "reason", error))
        if "Name or service not known" in reason or "nodename nor servname" in reason:
            # A name that does not resolve is usually a domain that lapsed, and
            # it is occasionally this machine's resolver having a bad second.
            # `refresh_liveness` will not let it count as dead until a second,
            # separate run has seen the same thing -- an accusation against
            # someone's citation should not rest on one DNS packet.
            return {"state": "dns-failure", "status": "dns", "note": reason[:120]}
        return {"state": "unverifiable", "status": "network", "note": reason[:120]}
    except (TimeoutError, OSError) as error:
        return {"state": "unverifiable", "status": "timeout", "note": str(error)[:120]}


def load_liveness_cache(path: Path = LIVENESS_CACHE_FILE) -> dict[str, dict[str, Any]]:
    try:
        cache = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {url: _normalise_verdict(verdict) for url, verdict in cache.items()}


def _normalise_verdict(verdict: dict[str, Any]) -> dict[str, Any]:
    """Downgrade a verdict written before the two-strike rule existed.

    The first sweep of this lane recorded a name that would not resolve as
    ``dead`` outright.  That is one DNS packet's worth of evidence for calling
    somebody's citation rotten, which is not enough, and the entries are still
    on disk.  Rather than a one-off migration script that would have to be
    remembered, the downgrade happens on load: it is idempotent, and any cache
    written by an older copy of this module heals the first time a newer one
    reads it.
    """
    if verdict.get("state") == "dead" and verdict.get("status") == "dns" \
            and "strikes" not in verdict:
        healed = dict(verdict)
        healed["state"] = "dns-failure"
        healed["strikes"] = 1
        healed["note"] = "recorded before the two-strike rule; awaiting a second opinion"
        return healed
    return verdict


def save_liveness_cache(cache: dict[str, dict[str, Any]],
                        path: Path = LIVENESS_CACHE_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(cache, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


#: A name that does not resolve must be seen on this many separate runs before
#: the tracker will call the citation dead. An HTTP 404 needs only one, because
#: the server itself answered the question.
DNS_STRIKES_FOR_DEAD = 2

#: Write the cache to disk this often during a sweep, so an interruption costs
#: at most this many requests rather than the whole run.
CHECKPOINT_EVERY = 25


def _cache_is_fresh(entry: dict[str, Any], now: float) -> bool:
    checked = entry.get("checkedAtEpoch")
    if not isinstance(checked, (int, float)):
        return False
    if entry.get("state") == "dns-failure" and entry.get("strikes", 0) < DNS_STRIKES_FOR_DEAD:
        return False  # unconfirmed; re-check it on the next run rather than trusting it
    limit = (DEAD_RECHECK_MAX_AGE_S
             if entry.get("state") in ("dead", "dns-failure")
             else LIVENESS_MAX_AGE_S)
    return (now - checked) < limit


def refresh_liveness(
    urls: Sequence[str],
    *,
    probe=offline_probe,
    budget: int = DEFAULT_URL_BUDGET,
    cache_path: Path = LIVENESS_CACHE_FILE,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Check the citations whose cached verdict has expired, oldest first.

    Every outcome is cached, including the failures -- a 404 is a *result*.
    Without that the next run re-asks a stranger's server the same question it
    has already answered, which is precisely the behaviour that got this
    project's address into CelesTrak's firewall.
    """
    cache = load_liveness_cache(cache_path)
    now = time.time()
    stale = [url for url in urls if not _cache_is_fresh(cache.get(url, {}), now)]
    stale.sort(key=lambda url: cache.get(url, {}).get("checkedAtEpoch", 0.0))
    attempted = stale[:budget]

    checked = 0
    for url in attempted:
        try:
            verdict = probe(url)
        except LivenessRefused:
            raise
        except Exception as error:  # a probe must never take the build down
            verdict = {"state": "unverifiable", "status": "error", "note": str(error)[:120]}
        if verdict.get("state") == "dns-failure":
            verdict["strikes"] = int(cache.get(url, {}).get("strikes", 0)) + 1
        verdict["checkedAtEpoch"] = time.time()
        verdict["checkedAt"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        cache[url] = verdict
        checked += 1
        # Checkpoint. A full sweep is a thousand requests over twenty minutes,
        # and a version that only saved at the end threw all of it away on any
        # interruption -- then asked a thousand strangers the same questions
        # again on the next run, which is the discourtesy this lane is built to
        # avoid.
        if checked % CHECKPOINT_EVERY == 0:
            save_liveness_cache(cache, cache_path)

    save_liveness_cache(cache, cache_path)
    coverage = {
        "distinctUrls": len(urls),
        "cached": sum(1 for url in urls if url in cache),
        "checkedThisRun": checked,
        "staleRemaining": max(0, len(stale) - checked),
        "budget": budget,
        "states": dict(collections.Counter(
            cache[url]["state"] for url in urls if url in cache
        )),
    }
    return cache, coverage


# ---------------------------------------------------------------------------
# Assembling the report
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class Graded:
    record: dict[str, Any]
    gaps: list[dict[str, Any]]
    cause: str
    score: int
    importance: int
    reasons: list[str]

    @property
    def keys(self) -> set[str]:
        return {gap["dimension"] for gap in self.gaps}

    def as_dict(self) -> dict[str, Any]:
        return {
            "noradId": self.record["id"],
            "name": self.record["name"],
            "ownerCode": self.record.get("ownerCode"),
            "orbit": self.record.get("orbit"),
            "mission": self.record.get("mission"),
            "constellation": self.record.get("constellation"),
            "purposeSource": self.record.get("purposeSource"),
            "classificationBasis": self.record.get("classificationBasis"),
            "missionCorroboration": self.record.get("missionCorroboration"),
            "classificationConfidence": self.record.get("classificationConfidence"),
            "descriptionLength": len(str(self.record.get("purpose") or "")),
            "gaps": self.gaps,
            "cause": self.cause,
            "tier": tier_of(self),
            "importance": self.importance,
            "importanceReasons": self.reasons,
            "score": self.score,
        }


def grade_catalog(
    catalog: dict[str, Any],
    liveness: dict[str, dict[str, Any]] | None = None,
) -> list[Graded]:
    records = catalog["satellites"]
    liveness = liveness or {}
    shared_counts = collections.Counter(str(r.get("purpose") or "") for r in records)
    featured = featured_constellations()
    as_of = catalog_as_of(catalog)

    # How many objects share this object's *defect*, not merely its text: the
    # unit of work is "write per-object detail for OneWeb", not "edit one row".
    graded_raw: list[tuple[dict[str, Any], list[dict[str, Any]]]] = [
        (record, grade_record(record, shared_counts, liveness)) for record in records
    ]
    group_size: collections.Counter = collections.Counter()
    for record, gaps in graded_raw:
        group_size[work_unit(record, gaps)] += 1

    out: list[Graded] = []
    for record, gaps in graded_raw:
        if not gaps:
            continue
        unit = work_unit(record, gaps)
        weight, reasons = importance(record, featured, group_size[unit])
        out.append(Graded(
            record=record,
            gaps=gaps,
            cause=attribute_cause(record, gaps, as_of),
            importance=weight,
            reasons=reasons,
            # The defect's own weight, amplified by how much this object
            # matters. Both halves are shown on the page, so a reader who
            # disagrees with the ranking can see which half they disagree with.
            score=int(round(gap_weight(gaps) * (1 + weight / 100.0))),
        ))
    out.sort(key=lambda g: (-g.score, g.record["id"]))
    return out


def work_unit(record: dict[str, Any], gaps: Sequence[dict[str, Any]]) -> tuple:
    """The thing a person would actually sit down and fix in one go.

    The first version keyed everything on constellation-or-owner, and that was
    wrong for the two defects that are not about a spacecraft at all:

    * A dead citation is fixed by finding ONE new URL.  Eighteen dead links
      cover a hundred-odd cards, so the unit is the URL -- "www.wmo-sat.info
      /oscar/.../gaofen, cited by 32 objects" is a job; "owner:PRC, 32 objects"
      is a filing cabinet.
    * The SatNOGS radio-licence cards are one lane's output, not nineteen
      owners' problems.  Keying them by owner split a single job into nineteen
      fragments of two, and buried all of them.
    """
    keys = tuple(sorted(gap["dimension"] for gap in gaps))
    by_dimension = {gap["dimension"]: gap for gap in gaps}

    dead = by_dimension.get("dead-source")
    if dead:
        return ("citation " + str(dead["evidence"].get("url")), ("dead-source",))
    if "licence-only" in by_dimension:
        return ("the SatNOGS radio-licence lane", ("licence-only",))
    if "class-not-object" in by_dimension:
        return ("rideshare class cards", ("class-not-object",))
    return (record.get("constellation") or f"owner:{record.get('ownerCode')}", keys)


#: The dimensions that mean "the card does not answer the question the reader
#: clicked for". Everything else means "the card answers it, weakly".
MISSING_DIMENSIONS = frozenset({
    "no-description", "licence-only", "class-not-object", "no-source", "dead-source",
})


def tier_of(entry: "Graded") -> str:
    return "missing" if entry.keys & MISSING_DIMENSIONS else "generic"


def top_objects(graded: Sequence[Graded], limit: int = 20,
                per_unit: int = 2) -> list[Graded]:
    """The ranked table: half from each tier, capped per work unit.

    One global ordering was tried first and it was a lie in both directions.
    It filled twenty rows with cubesats that have no description at all, which
    is a true statement about severity and a useless worklist -- and it buried
    every MUOS, WGS, GOES and DMSP card, which are the ones a METOC reader
    actually opens and which say nothing about the individual spacecraft.
    Burying those is the exact failure this tracker was built after.

    So the tiers are ranked separately and shown together.  Within a tier the
    score orders honestly; across tiers it would be pretending that a national
    radar-imaging satellite and a 1U cubesat are commensurable, and the
    catalog carries nothing that would justify that claim -- PAZ and MARMOTSAT
    have identical `sector`, `sourceGroups` and `programmes` fields.

    The per-work-unit cap stops one constellation wearing twenty hats.
    """
    picked: list[Graded] = []
    for tier in ("missing", "generic"):
        quota = limit // 2
        members = [entry for entry in graded if tier_of(entry) == tier]
        seen: collections.Counter = collections.Counter()
        chosen: list[Graded] = []
        # First pass respects the cap. Second pass fills whatever the cap left
        # empty, because a tier that is genuinely one owner's problem should
        # still fill its half rather than showing two rows and a gap.
        for allow in (per_unit, quota):
            for entry in members:
                if len(chosen) >= quota:
                    break
                if entry in chosen:
                    continue
                unit = work_unit(entry.record, entry.gaps)
                if seen[unit] >= allow:
                    continue
                seen[unit] += 1
                chosen.append(entry)
        picked.extend(chosen)
    return picked


def work_items(graded: Sequence[Graded], limit: int = 40) -> list[dict[str, Any]]:
    """The same findings grouped into jobs, biggest job first."""
    groups: dict[tuple, list[Graded]] = collections.defaultdict(list)
    for entry in graded:
        groups[work_unit(entry.record, entry.gaps)].append(entry)
    rows = []
    for (label, keys), members in groups.items():
        members.sort(key=lambda g: -g.score)
        rows.append({
            "group": label,
            "dimensions": list(keys),
            "objects": len(members),
            "topScore": members[0].score,
            "totalScore": sum(m.score for m in members),
            "cause": members[0].cause,
            "examples": [m.record["name"] for m in members[:6]],
        })
    rows.sort(key=lambda row: (-row["totalScore"], row["group"]))
    return rows[:limit]


def summarise(catalog: dict[str, Any], graded: Sequence[Graded],
              liveness_coverage: dict[str, Any],
              dead_rules: Sequence[dict[str, Any]]) -> dict[str, Any]:
    records = catalog["satellites"]
    total = len(records)
    by_dimension = collections.Counter()
    for entry in graded:
        by_dimension.update(entry.keys)

    lengths = [len(str(r.get("purpose") or "")) for r in records]
    return {
        "generatedAt": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "catalogObjects": total,
        "totalAvailable": catalog.get("totalAvailable"),
        "taxonomyVersion": catalog.get("taxonomyVersion"),
        "upstreamAsOf": catalog.get("upstreamAsOf"),
        "objectsWithAnyGap": len(graded),
        "objectsClean": total - len(graded),
        "byDimension": {
            dimension.key: {
                "objects": by_dimension.get(dimension.key, 0),
                "percent": round(100.0 * by_dimension.get(dimension.key, 0) / total, 2),
                "title": dimension.title,
                "why": dimension.why,
                "weight": dimension.weight,
            }
            for dimension in DIMENSIONS
        },
        "byCause": dict(collections.Counter(entry.cause for entry in graded).most_common()),
        "lengthSensitivity": {
            str(floor): sum(1 for length in lengths if length < floor)
            for floor in LENGTH_FLOORS_REPORTED
        },
        "distinctDescriptions": len({str(r.get("purpose") or "") for r in records}),
        # Reported, not graded: on its own this fires on cards that are plainly
        # about their object, so it is context for a reader rather than a defect.
        "descriptionsMissingNameStem": sum(1 for r in records if not names_its_family(r)),
        "sourceLiveness": liveness_coverage,
        "deadNameRules": list(dead_rules),
        "frontEndExemptions": front_end_exemptions(catalog),
        "drift": check_density_rank_matches_front_end(),
    }


# ---------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------
# Modelled on pipeline/discovery_page.py: a complete document, inline CSS, and
# NO <script> of any kind. The nginx catch-all sends `script-src 'self'` with
# no 'unsafe-inline', so an inline script would be silently blocked and the
# page would look broken to the one person allowed to read it. Progressive
# disclosure is <details>/<summary>, which needs no JavaScript at all.

BANNER = "OPERATOR ONLY — NOT PUBLISHED. Internal quality tracking for the satellite catalog."

LEDE = (
    "Which satellite cards are under-described, and which one to fix next. "
    "\"Missing\" is the easy half: the far larger number below is cards that "
    "look finished while saying nothing about the object the reader clicked."
)

_STYLE = """
:root{color-scheme:light dark;--bg:#fbfbfc;--fg:#16181d;--dim:#5d6470;--line:#d9dde4;
  --card:#fff;--bad:#a3241d;--warn:#8a5a06;--ok:#1d6b3f;--accent:#1c4f8a}
@media (prefers-color-scheme:dark){:root{--bg:#101216;--fg:#e6e8ec;--dim:#9aa2b1;
  --line:#2b3037;--card:#171a20;--bad:#f0857c;--warn:#e3b357;--ok:#68d295;--accent:#7db4f0}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
  font:15px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:1180px;margin:0 auto;padding:1.4rem 1.1rem 4rem}
h1{font-size:1.5rem;margin:.2rem 0 .3rem}
h2{font-size:1.05rem;margin:2rem 0 .3rem;padding-top:.9rem;border-top:1px solid var(--line)}
p{margin:.45rem 0}
.lede{color:var(--dim);max-width:62ch}
.banner{background:var(--bad);color:#fff;padding:.45rem .8rem;border-radius:.35rem;
  font-weight:650;font-size:.82rem;letter-spacing:.02em}
.scoreboard{display:flex;flex-wrap:wrap;gap:.6rem;margin:.9rem 0}
.scoreboard div{border:1px solid var(--line);border-radius:.4rem;padding:.45rem .75rem;
  background:var(--card);font-size:.82rem;color:var(--dim);min-width:8.5rem}
.scoreboard b{font-size:1.35rem;display:block;color:var(--fg);
  font-variant-numeric:tabular-nums}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:.86rem;margin:.5rem 0}
th,td{text-align:left;padding:.35rem .7rem .35rem 0;vertical-align:top;
  border-bottom:1px solid var(--line)}
th{color:var(--dim);font-weight:600;white-space:nowrap;font-size:.74rem;
  text-transform:uppercase;letter-spacing:.04em}
td.num{font-variant-numeric:tabular-nums;white-space:nowrap}
td.why{color:var(--dim);font-size:.8rem}
.bar{display:inline-block;height:.55rem;background:var(--accent);border-radius:2px;
  vertical-align:middle;margin-right:.4rem;min-width:2px}
.tag{display:inline-block;border:1px solid var(--line);border-radius:.75rem;
  padding:0 .5rem;font-size:.72rem;color:var(--dim);margin:0 .25rem .2rem 0;
  white-space:nowrap}
.tag.hot{border-color:var(--bad);color:var(--bad)}
details{border:1px solid var(--line);border-radius:.4rem;background:var(--card);
  padding:.4rem .7rem;margin:.5rem 0}
summary{cursor:pointer;font-weight:600;font-size:.85rem}
details p{font-size:.85rem;color:var(--dim)}
code{font-size:.82em;background:color-mix(in srgb,var(--fg) 8%,transparent);
  padding:0 .25em;border-radius:3px}
.foot{color:var(--dim);font-size:.78rem;margin-top:2rem}
"""


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _table(rows: Sequence[tuple[str, Any]]) -> str:
    body = "".join(
        f"<tr><th>{_e(label)}</th><td>{_e(value)}</td></tr>"
        for label, value in rows if value is not None
    )
    return f"<table>{body}</table>" if body else ""


def _bar(value: int, largest: int, width: int = 130) -> str:
    if largest <= 0:
        return ""
    pixels = max(2, int(round(width * value / largest)))
    return f'<span class="bar" style="width:{pixels}px"></span>'


def render(summary: dict[str, Any], graded: Sequence[Graded]) -> str:
    top = top_objects(graded, limit=20)
    jobs = work_items(graded, limit=30)

    dimension_rows = ""
    largest = max((entry["objects"] for entry in summary["byDimension"].values()), default=0)
    for dimension in DIMENSIONS:
        cell = summary["byDimension"][dimension.key]
        dimension_rows += (
            f"<tr><td><b>{_e(dimension.title)}</b><br>"
            f"<code>{_e(dimension.key)}</code></td>"
            f"<td class='num'>{_bar(cell['objects'], largest)}{cell['objects']:,}</td>"
            f"<td class='num'>{cell['percent']:.2f}%</td>"
            f"<td class='why'>{_e(dimension.why)}</td></tr>"
        )

    object_rows = ""
    for position, entry in enumerate(top, start=1):
        tags = "".join(
            f"<span class='tag hot'>{_e(DIMENSION_BY_KEY[key].title)}</span>"
            for key in sorted(entry.keys)
        )
        object_rows += (
            f"<tr><td class='num'>{position}</td>"
            f"<td><b>{_e(entry.record['name'])}</b><br>"
            f"<span class='why'>NORAD {entry.record['id']} · "
            f"{_e(entry.record.get('ownerCode'))} · {_e(entry.record.get('orbit'))} · "
            f"{_e(entry.record.get('mission'))}</span></td>"
            f"<td class='num'>{entry.score:,}</td>"
            f"<td>{tags}</td>"
            f"<td class='why'>{_e('; '.join(entry.reasons))}</td>"
            f"<td class='why'>{_e(entry.cause)}</td></tr>"
        )

    job_rows = ""
    for position, job in enumerate(jobs, start=1):
        job_rows += (
            f"<tr><td class='num'>{position}</td>"
            f"<td><b>{_e(job['group'])}</b><br>"
            f"<span class='why'>{_e(', '.join(job['examples']))}</span></td>"
            f"<td class='num'>{job['objects']:,}</td>"
            f"<td>{''.join(f'<span class=tag>{_e(DIMENSION_BY_KEY[k].title)}</span>' for k in job['dimensions'])}</td>"
            f"<td class='why'>{_e(job['cause'])}</td></tr>"
        )

    cause_rows = "".join(
        f"<tr><td>{_e(cause)}</td><td class='num'>{count:,}</td></tr>"
        for cause, count in summary["byCause"].items()
    )

    liveness = summary["sourceLiveness"]
    liveness_note = (
        "Never run. Pass <code>--check-sources</code> to start the polite, cached sweep."
        if not liveness.get("cached") else
        f"{liveness.get('cached', 0):,} of {liveness.get('distinctUrls', 0):,} distinct "
        f"citations have a cached verdict; {liveness.get('checkedThisRun', 0):,} were "
        f"checked on this run; {liveness.get('staleRemaining', 0):,} still stale. "
        f"States: {liveness.get('states')}."
    )

    dead_rules = summary["deadNameRules"]
    dead_rule_rows = "".join(
        f"<tr><td>{_e(rule['constellation'])}</td><td><code>{_e(rule['fragment'])}</code></td></tr>"
        for rule in dead_rules
    ) or "<tr><td colspan=2>None. Every classification fragment matches at least one object.</td></tr>"

    exemption_rows = "".join(
        f"<tr><td class='why'><code>{_e(row['where'])}</code></td>"
        f"<td>{_e(row['rule'])}</td>"
        f"<td class='num'>{row['objects']:,}</td>"
        f"<td class='why'>{_e(row['effect'])}</td></tr>"
        for row in summary.get("frontEndExemptions", [])
    ) or "<tr><td colspan=4>None found.</td></tr>"

    sensitivity = " · ".join(
        f"&lt;{floor}: {count:,}" for floor, count in summary["lengthSensitivity"].items()
    )
    drift = summary["drift"]
    drift_block = (
        f"<p class='lede'><b>Ranking drift:</b> {_e('; '.join(drift))}</p>" if drift else ""
    )

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex, nofollow, noarchive">
<title>Satellite description coverage — operator only</title>
<style>{_STYLE}</style>
</head><body><main>
<div class="banner">{_e(BANNER)}</div>
<h1>Which satellites are under-described</h1>
<p class="lede">{_e(LEDE)}</p>
{drift_block}

<div class="scoreboard">
<div><b>{summary['catalogObjects']:,}</b>objects in the catalog</div>
<div><b>{summary['objectsWithAnyGap']:,}</b>with at least one gap</div>
<div><b>{summary['objectsClean']:,}</b>clean on every dimension</div>
<div><b>{summary['byDimension']['no-description']['objects']:,}</b>no description at all</div>
<div><b>{summary['byDimension']['no-per-object-detail']['objects']:,}</b>family prose only</div>
<div><b>{summary['distinctDescriptions']:,}</b>distinct descriptions</div>
</div>

<h2>Every dimension, and where the catalog stands on it</h2>
<div class="scroll"><table>
<thead><tr><th>Dimension</th><th>Objects</th><th>Share</th><th>Why it counts as under-described</th></tr></thead>
<tbody>{dimension_rows}</tbody></table></div>
<p class="why">Length sensitivity — objects shorter than: {sensitivity}. The graded floor
is {LENGTH_FLOOR} characters, chosen because the shared Starlink line is 137.</p>

<h2>Fix these next</h2>
<p class="lede">Ranked by the weight of the gaps found times how much the object
matters — the site's own featured rotation and default-draw ordering, the mission's
relevance to a METOC or naval reader, and how many objects share the same defect.
At most two rows per job, so the table spans separate work rather than repeating
one constellation twenty times.</p>
<div class="scroll"><table>
<thead><tr><th>#</th><th>Object</th><th>Score</th><th>Gaps</th><th>Why it ranks here</th><th>Likely cause</th></tr></thead>
<tbody>{object_rows}</tbody></table></div>

<h2>The same findings as jobs</h2>
<p class="lede">One row is one sitting: a constellation or an owner group sharing
the same set of gaps. This is the list to work from.</p>
<div class="scroll"><table>
<thead><tr><th>#</th><th>Job</th><th>Objects</th><th>Gaps</th><th>Likely cause</th></tr></thead>
<tbody>{job_rows}</tbody></table></div>

<h2>Why the gaps are still there</h2>
<div class="scroll"><table>
<thead><tr><th>Cause</th><th>Objects</th></tr></thead>
<tbody>{cause_rows}</tbody></table></div>

<h2>Citations that no longer resolve</h2>
<p class="lede">{liveness_note}</p>
<details><summary>How this is checked, and why a 403 is not reported as dead</summary>
<p>One request at a time per host with a 1.2-second floor, a User-Agent naming a
contact, HEAD before GET, and no retries — the house rules in
<code>docs/OPEN-WORK.md</code> §0. Verdicts are cached for 30 days (7 for a dead
one, because "we fixed it" is the outcome we want to see), so a build does not
re-ask a stranger's server a question it already answered.</p>
<p>Only 404, 410 and a name that does not resolve count as dead. A 403 or 401 is
recorded as <b>unverifiable</b>: several publishers and every .mil host in this
catalog refuse automated clients outright, and a tracker that called those dead
would be making a false accusation next to a perfectly good citation.</p>
</details>

<h2>What the site already forgives</h2>
<p class="lede">A completeness check whose exemptions nobody can list is not a
check. These are read out of <code>src/main.ts</code> on every run, so this
table cannot quietly disagree with the code it describes.</p>
<div class="scroll"><table>
<thead><tr><th>Where</th><th>Rule</th><th>Objects</th><th>What it lets past</th></tr></thead>
<tbody>{exemption_rows}</tbody></table></div>

<h2>Classification rules that match nothing</h2>
<p class="lede">The same failure class from the other end: a rule in
<code>build_release.py</code> that no object matches is a description nobody
will ever see. Six of these have shipped on this project.</p>
<div class="scroll"><table>
<thead><tr><th>Constellation</th><th>Fragment</th></tr></thead>
<tbody>{dead_rule_rows}</tbody></table></div>

<h2>Provenance</h2>
{_table([
    ("Generated", summary["generatedAt"]),
    ("Catalog objects", f"{summary['catalogObjects']:,} of {summary['totalAvailable']:,} available"),
    ("Taxonomy version", summary["taxonomyVersion"]),
    ("Upstream as of", summary["upstreamAsOf"]),
])}
<p class="foot">Written by <code>pipeline/coverage_tracker.py</code> into
<code>public/data/review/</code>, the tree the publish gate structurally cannot
stage into the public site. It reaches the VPS only through
<code>publish_vps.sh</code>'s ops-pages rsync and is served only behind Caddy
<code>forward_auth</code> at <code>/space/ops/</code>. Nothing in the front end
links to it, and a test asserts that stays true.</p>
</main></body></html>
"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rank the catalog's under-described satellites.")
    parser.add_argument("--catalog", type=Path, default=None, help="published catalog artifact")
    parser.add_argument("--html", type=Path, default=DEFAULT_HTML, help="operator page to write")
    parser.add_argument("--json", dest="json_out", type=Path, default=DEFAULT_JSON,
                        help="machine-readable report to write")
    parser.add_argument("--check-sources", action="store_true",
                        help="check citation liveness over the network (polite, cached, budgeted)")
    parser.add_argument("--url-budget", type=int, default=DEFAULT_URL_BUDGET,
                        help="most URLs to check in one run")
    parser.add_argument("--top", type=int, default=20, help="rows in the ranked object table")
    parser.add_argument("--full-json", action="store_true",
                        help="include every graded object (9 MB); the default carries the "
                             "ranked rows, the jobs, and every object in the missing tier")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    for destination in (args.html, args.json_out):
        if destination and destination.resolve().parent.name == "artifacts":
            raise SystemExit(
                "refusing to write into artifacts/: that directory is the publish "
                "allowlist's source, and this report is deliberately never published."
            )

    catalog_path = resolve_catalog_path(args.catalog)
    catalog = load_catalog(catalog_path)

    urls = sorted({
        str(record.get("purposeSource"))
        for record in catalog["satellites"]
        if str(record.get("purposeSource") or "").startswith("http")
    })
    if args.check_sources and DISABLE_LIVENESS:
        print("NOTE: SPACE_EXPLORER_DISABLE_COVERAGE_LIVENESS=1; not touching the network")
    probe = urllib_probe if (args.check_sources and not DISABLE_LIVENESS) else offline_probe
    liveness, coverage = refresh_liveness(
        urls,
        probe=probe,
        budget=args.url_budget if args.check_sources else 0,
    )

    graded = grade_catalog(catalog, liveness)
    summary = summarise(catalog, graded, coverage, dead_name_rules(catalog))

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps({
            "summary": summary,
            "topObjects": [entry.as_dict() for entry in top_objects(graded, limit=args.top)],
            "workItems": work_items(graded, limit=60),
            "objects": [
                entry.as_dict() for entry in graded
                if args.full_json or tier_of(entry) == "missing"
            ],
            "objectsTruncated": not args.full_json,
        }, indent=1) + "\n", encoding="utf-8")

    if args.html:
        args.html.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.html.with_suffix(args.html.suffix + ".next")
        temporary.write_text(render(summary, graded), encoding="utf-8")
        temporary.replace(args.html)

    if not args.quiet:
        print(f"catalog: {catalog_path}")
        print(json.dumps({
            key: summary[key] for key in
            ("catalogObjects", "objectsWithAnyGap", "objectsClean", "byCause",
             "lengthSensitivity", "sourceLiveness", "drift")
        }, indent=2))
        print("\nby dimension:")
        for dimension in DIMENSIONS:
            cell = summary["byDimension"][dimension.key]
            print(f"  {dimension.key:24s} {cell['objects']:6,d}  {cell['percent']:6.2f}%  {dimension.title}")
        print(f"\ndead classification rules: {len(summary['deadNameRules'])}")
        if args.html:
            print(f"wrote {args.html} ({args.html.stat().st_size:,} bytes, not published to /space/)")
        if args.json_out:
            print(f"wrote {args.json_out} ({args.json_out.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
