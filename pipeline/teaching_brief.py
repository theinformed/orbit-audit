#!/usr/bin/env python3
"""Validity rules for the model-written "what does it all mean" brief.

The brief is the one place on the site where a language model writes prose that
a visitor reads. Everything about this module exists to keep that safe:

* the model never supplies a number — digits are rejected outright, so exact
  values only ever reach the visitor through the independently rendered
  observation cards;
* the brief is bound to the conditions it was written about, so a calm-day
  interpretation can never be shown over storm data; and
* the brief carries the time of the observations it describes, so the interface
  can say how old the interpretation is instead of implying it is current.

Why the binding is fuzzy rather than exact
------------------------------------------
The original contract hashed the whole fact packet, including every
``observedAt`` timestamp. Those timestamps change on every five-minute
publication, so the hash could never match twice: a brief was invalid within one
cycle of being written, and the site always fell back to the deterministic
sentence. Generating a brief takes about seventy seconds of local GPU time, so a
brief that expires in five minutes can never be worth writing.

The binding here is to the *physically meaningful* state instead: the brief
records the values it was written about, and stays valid while each one is still
within a tolerance chosen as "how far would this have to move before the sentence
a teacher writes changes?", plus a hard staleness bound. Conditions that have
materially changed invalidate the brief immediately; a quiet hour does not.

Tolerance bands rather than rounded buckets, because buckets are unstable exactly
where the data usually sits. Measured live: a brief was rejected because Kp moved
0.0 -> 1.0, Bt 2.5 -> 5.0 and wind speed 300 -> 250 in rounded terms, when the
underlying values had barely moved at all and had simply crossed a rounding
boundary. A tolerance band has no boundary to cross.

Why the tolerance is a WORD boundary rather than a distance
-----------------------------------------------------------
The symmetric tolerances that replaced the hash were still far too tight to
bind. Replayed over 253 real published fact packets spanning 25.9 hours on
2026-08-07/08, they invalidated the cached brief 122 times: 113 rewrites a day,
against 110 actually observed in the systemd journal over the same period. The
45-minute freshness allowance almost never got a say, because the fingerprint
had already failed.

The brief carries no numbers at all — the rules below reject digits and
spelled-out quantities outright. It says "quiet", "moderate", "elevated". So the
only change that can make it wrong is one that changes a WORD, and the tolerance
is now exactly that: the brief stays valid while each value is still inside the
same qualitative band it was written in.

Where the site itself defines those bands, they are quoted from it rather than
invented — ``deterministic_weather_brief`` in pipeline/build_release.py is the
site's own vocabulary for the same quantities, and the edges in ``_WORD_EDGES``
below are its numbers. Where the site defines no band, the quantity is either
excluded (with the reason recorded beside it) or given the coarsest banding the
prompt's word list can distinguish, and that choice is checked against measured
range rather than asserted.

Boundary stability is kept by widening the stored value's band by a margin on
each side, so a value sitting on an edge and jittering across it does not throw
away seventy seconds of GPU. The margin is derived, not typed: one tenth of the
narrowest finite band that quantity has.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from typing import Any

# A brief older than this is rejected no matter how well the conditions match.
# It is the real safety net: quantisation decides whether the interpretation
# still fits, this decides whether it is still worth showing at all.
MAX_BRIEF_AGE_MINUTES = 180

# The value at which the word changes, for every quantity the brief describes.
#
# The first three are QUOTED from deterministic_weather_brief() in
# pipeline/build_release.py, which is the site's own published vocabulary for
# exactly these quantities. If those thresholds move, these must move with them,
# and the test suite compares the two directly so they cannot drift apart.
#
#   speedKps  450 / 600   "relatively slow" / "moderate" / "fast"
#   bzGsmNt    -5 / +5    "southward enough to favor stronger dayside coupling"
#                         / "near neutral" / "northward"
#   kp          4 / 5     "below NOAA storm threshold" / "active but below" /
#                         "in NOAA geomagnetic-storm range"
#
# The last two have no published band anywhere in this repository. The prompt
# permits only low / moderate / elevated for them, so they get the coarsest
# two-edge banding that separates those three words, checked against measured
# range rather than asserted: across 253 real packets over 25.9 hours the field
# strength ran 2.2 to 18.8 nT and the density 2.8 to 30.5 cm^-3, so these edges
# put the tenth percentile in the low band, the median in the middle one and the
# ninetieth in the high one, which is what a three-word ladder is for.
_WORD_EDGES: dict[tuple[str, str], tuple[float, ...]] = {
    ("solarWind", "speedKps"): (450.0, 600.0),
    ("imf", "bzGsmNt"): (-5.0, 5.0),
    ("geomagnetic", "kp"): (4.0, 5.0),
    ("imf", "btNt"): (5.0, 15.0),
    ("solarWind", "densityCm3"): (5.0, 15.0),
}

#: How far outside its band a value may sit before the band is treated as left.
#: Expressed as a fraction of the narrowest finite band the quantity has, so it
#: is derived from the edges rather than typed in beside them. Without it a
#: value resting on an edge throws away seventy seconds of GPU every time it
#: jitters across — the same instability that the rounded-bucket contract had.
_EDGE_MARGIN_FRACTION = 0.1

# Timestamps are excluded from the binding entirely; staleness is enforced
# separately and explicitly. Everything else here is excluded because it cannot
# change a word in the brief, and each one was measured before it was dropped.
#
#   subsolarStandoffRe, flaringAlpha
#       Computed FROM the solar-wind pressure and IMF Bz already in the packet,
#       so they add churn without adding information.
#   caveat
#       PROSE, not a condition, and it is not even constant prose: the
#       solar-wind guard appends the two spacecraft readings that made it
#       withhold a value, so the sentence carries digits that change every
#       cycle. It invalidated four briefs in the 25.9-hour replay for a
#       disagreement between SOLAR1 at 278 km/s and IMAP at 285 km/s. The
#       validator still reads this field out of `facts` to reject a brief that
#       echoes it; that check is unaffected by dropping it from the binding.
#   dynamicPressureNpa
#       Density times speed squared. Both factors are banded above, so this is
#       already bound; including it binds the same physics twice and at a
#       tighter tolerance than either factor.
#   medianHmF2Km
#       Measured full range over the 25.9-hour replay: 2.9 km. It cannot reach a
#       word boundary. Every one of the 26 invalidations it caused was the value
#       being ABSENT for a cycle, not moving.
#   tecRange
#       A global min/max over the assimilated field. When the field is missing
#       the layer publishes [0, 1] rather than a gap, so this key encodes "the
#       upstream was absent" far more often than "the ionosphere changed" — 19
#       of 253 cycles. Excluding the observed range (46 to 65 TECU) it does not
#       move far enough to change a word either.
#
# MAX_BRIEF_AGE_MINUTES remains the backstop over all of them.
_EXCLUDED_KEYS = {
    "observedAt", "sourceSpacecraft", "subsolarStandoffRe", "flaringAlpha",
    "caveat", "dynamicPressureNpa", "medianHmF2Km", "tecRange",
}

# Banning digits alone is not enough. Asked for prose without numerals, the model
# spells the quantity out instead - "flow speeds below three hundred kilometers
# per second", "standoff exceeds twelve Earth radii" - which is still the model
# supplying a value. Observed on the second live run.
#
# "one" is deliberately absent: in this register it is nearly always an article
# or pronoun ("one of the", "a single one"), and a spelled "one hundred" is
# caught by "hundred" anyway.
_NUMBER_WORDS = frozenset(
    """two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen
    sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety
    hundred thousand million billion""".split()
)


def facts_snapshot(facts: dict[str, Any]) -> dict[str, Any]:
    """The state the interpretation depends on, at full precision."""
    reduced: dict[str, Any] = {}
    for section, values in sorted(facts.items()):
        if not isinstance(values, dict):
            reduced[section] = values
            continue
        kept: dict[str, Any] = {}
        for key, value in sorted(values.items()):
            if key in _EXCLUDED_KEYS:
                continue
            if key == "class" and isinstance(value, str) and value:
                # "B2.7" and "B4.1" are the same story; "B2.7" and "M1.2" are not.
                kept[key] = value[0].upper()
                continue
            kept[key] = value
        reduced[section] = kept
    return reduced


def edge_margin(edges: tuple[float, ...]) -> float:
    """A tenth of the narrowest finite band, or zero when every band is open.

    Derived rather than typed so the margin cannot fall out of step with the
    edges it protects. Two edges at 450 and 600 give a 150-wide middle band and
    a 15-unit margin; Kp's edges at 4 and 5 give 0.1.
    """
    widths = [high - low for low, high in zip(edges, edges[1:])]
    return min(widths) * _EDGE_MARGIN_FRACTION if widths else 0.0


def band_bounds(edges: tuple[float, ...], value: float) -> tuple[float, float]:
    """The half-open band ``value`` falls in, as (low, high).

    ``-inf`` and ``inf`` stand for the open ends. A value exactly on an edge
    belongs to the band above it, matching the ``>=`` comparisons in
    deterministic_weather_brief().
    """
    index = sum(1 for edge in edges if value >= edge)
    low = edges[index - 1] if index > 0 else float("-inf")
    high = edges[index] if index < len(edges) else float("inf")
    return low, high


def _values_agree(section: str, key: str, stored: Any, current: Any) -> bool:
    """True while the current value would still be described by the same word.

    An absent value on either side agrees. Absence is not a change of
    conditions, it is the loss of the evidence that could show one, and there is
    nothing honest to compare — the solar wind went missing for 16 of 253 cycles
    in the replay and the median F2 height for 19. Treating a gap as a material
    change spent GPU rewriting the brief about a fact packet that had less in it
    than the one before. MAX_BRIEF_AGE_MINUTES bounds how long a brief may
    outlive its evidence.
    """
    if stored is None or current is None:
        return True
    edges = _WORD_EDGES.get((section, key))
    if edges is None:
        return stored == current
    numeric = (int, float)
    if not isinstance(stored, numeric) or not isinstance(current, numeric):
        return stored == current
    if isinstance(stored, bool) or isinstance(current, bool):
        return stored == current
    low, high = band_bounds(edges, float(stored))
    margin = edge_margin(edges)
    return (low - margin) <= float(current) <= (high + margin)


def snapshot_still_describes(stored: Any, facts: dict[str, Any]) -> bool:
    """True while every tracked value is still within tolerance of the brief's."""
    if not isinstance(stored, dict):
        return False
    current = facts_snapshot(facts)
    if set(stored) != set(current):
        return False
    for section, values in current.items():
        held = stored.get(section)
        if not isinstance(values, dict):
            if held != values:
                return False
            continue
        if not isinstance(held, dict) or set(held) != set(values):
            return False
        for key, value in values.items():
            if not _values_agree(section, key, held[key], value):
                return False
    return True


def latest_observed_at(facts: dict[str, Any]) -> str | None:
    """The most recent observation time in the packet, for the "as of" stamp."""
    stamps: list[str] = []
    for values in facts.values():
        if isinstance(values, dict):
            observed = values.get("observedAt")
            if isinstance(observed, str) and observed:
                stamps.append(observed)
    return max(stamps) if stamps else None


def _parse_time(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


def brief_fingerprint(facts: dict[str, Any], sha256, canonical_json) -> str:
    """Identity of the conditions a brief was written about.

    Retained so a candidate can record what it saw; acceptance is decided by
    snapshot_still_describes, which tolerates ordinary drift.
    """
    return sha256(canonical_json(facts_snapshot(facts)))


def validate_candidate(
    candidate: Any,
    facts: dict[str, Any],
    sha256,
    canonical_json,
    now: dt.datetime | None = None,
) -> dict[str, str] | None:
    """Return a publishable brief, or None with the reason left to the caller.

    Rejection is always silent-but-safe: the caller falls back to the
    deterministic sentence, which is honest, just less interesting.
    """
    if not isinstance(candidate, dict):
        return None

    if not snapshot_still_describes(candidate.get("factsSnapshot"), facts):
        return None

    if candidate.get("reasoningUsed") is not True:
        return None

    text = candidate.get("text")
    caveat = candidate.get("caveat")
    if not isinstance(text, str) or not isinstance(caveat, str):
        return None
    if not (40 <= len(text) <= 850) or not (20 <= len(caveat) <= 240):
        return None

    # The model interprets; it never supplies a value. Exact numbers belong to
    # the independently rendered observation cards.
    if re.search(r"\d", text + caveat):
        return None
    if _spells_out_a_number(text) or _spells_out_a_number(caveat):
        return None

    # The caveat must describe THIS brief. A model that echoes a source model's
    # own caveat out of the fact packet produces a sentence that is true about
    # something else entirely - observed in the first live run, where the Shue
    # magnetopause caveat was returned verbatim as the brief's caveat.
    if _echoes_source_prose(caveat, facts):
        return None

    generated_at = _parse_time(candidate.get("generatedAt"))
    if generated_at is None:
        return None
    reference = now or dt.datetime.now(dt.timezone.utc)
    age_minutes = (reference - generated_at).total_seconds() / 60.0
    if age_minutes < -5 or age_minutes > MAX_BRIEF_AGE_MINUTES:
        return None

    brief: dict[str, str] = {
        "kind": "model-assisted",
        "text": text.strip(),
        "caveat": caveat.strip(),
        "generatedAt": candidate["generatedAt"],
    }
    observed = candidate.get("observationsAt") or latest_observed_at(facts)
    if isinstance(observed, str) and observed:
        brief["observationsAt"] = observed
    return brief


def _spells_out_a_number(prose: str) -> bool:
    """True when the prose states a quantity in words instead of digits."""
    return any(word in _NUMBER_WORDS for word in re.findall(r"[a-z]+", prose.lower()))


def _echoes_source_prose(caveat: str, facts: dict[str, Any]) -> bool:
    """True when the caveat is lifted from prose supplied in the fact packet."""
    normalised = " ".join(caveat.lower().split())
    for values in facts.values():
        if not isinstance(values, dict):
            continue
        for value in values.values():
            if not isinstance(value, str) or len(value) < 40:
                continue
            source = " ".join(value.lower().split())
            if source in normalised or normalised in source:
                return True
    return False


def load_candidate(path) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
