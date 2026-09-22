#!/usr/bin/env python3
"""Deterministic discovery of *curious* things in the orbital archive.

The requirement, stated plainly: look for interesting things in the archive,
check whether a publication already knows about them, and where none does, put
them on a page that says how curious they are -- behind a review step.

This module is the first of the four stages that answer it, and it is the only
one that decides whether something is worth looking at:

    1. **Detection — this file.** Code only. Five candidate classes, each with
       a stated threshold, each computed from data already on this disk.
    2. Literature check — ``pipeline/discovery_literature.py``.
    3. The review queue — ``pipeline/discovery_queue.py``.
    4. Human approval — a person, running a command. There is no fourth module,
       because there is nothing to automate.

**A language model never decides that something is interesting.** That is the
standing rule on this project ("the model decorates, never gates"), and it was
paid for: a model once wrote an all-clear health report over a hundred and five
real warnings. Nothing in this file calls a model, and nothing downstream may
let a model add, remove, or re-rank a candidate. What a model may do — later,
somewhere else — is help phrase a paragraph a human has already approved.

What "curious" is allowed to mean here
--------------------------------------
Every candidate is a **measured departure from a stated expectation**, and it
carries the measurement, the expectation, the margin, and a command that
reproduces it. A candidate with no number is a bug, not a finding. Five classes:

============================== ==============================================
class                          the departure
============================== ==============================================
``manoeuvre-out-of-family``    an object manoeuvred in a way its own class is
                               not published as doing, or spent more than its
                               class's published per-event ceiling
``correlated-shell-decay``     a whole altitude shell of passive objects
                               decayed together, faster or slower than the
                               archive's own baseline for that shell
``orbit-contradicts-catalog``  the object's own elements rule out the mission
                               its catalog label asserts
``delta-v-out-of-budget``      one interval's Delta-v exceeds the published
                               *annual* budget for that regime
``decay-rate-out-of-family``   this object's ballistic-coefficient-normalised
                               decay is far from the passive population's at
                               the same altitude, given the prevailing Kp
============================== ==============================================

Boundaries this module is built to respect
------------------------------------------
* **The eligibility gate of ``docs/mission-speculation-design.md`` Sections 1.3
  to 1.5 applies here unchanged.** An anomaly detector is exactly the kind of
  thing that drifts across that line, so ``opacity_denied()`` — the same
  function ``pipeline/orbit_events.py`` already uses — runs *before* a candidate
  record is built. A denied object produces **no candidate of any kind**: not a
  suppressed one, not a flagged one, not one with a "withheld" marker. The
  absence is silent, because a redaction badge is an assessment by implication
  and aggregated across a catalog it is worse than the thing it withholds.
* **No object-to-object association** (Section 1.6). Every candidate's subject
  is exactly one object, or one anonymous altitude shell described only by
  counts and medians. ``Candidate.subject`` cannot hold a list of objects and
  ``tests/test_discovery.py`` asserts it. The shell class is the one that looks
  closest to the line, and it is on the right side of it because it never names
  a member: ``population_decay()`` returns counts and medians, and there is no
  accessor anywhere that could grow a membership list.
* **No network.** Orbital data is read from the archive on ``/mnt/d`` and from
  the published catalog artifact. There is no fetch here at all — not to
  space-track, not to CelesTrak, not to a literature index. The literature step
  is a separate module, run separately, on purpose.
* **No publication path.** There is no function in this module or in
  ``pipeline/discovery_queue.py`` that writes into ``public/data/artifacts/`` or
  into ``manifest.json``. Publication is not disabled by a flag; it is absent.
  A test asserts the absence, because a flag can be flipped and a missing
  function cannot.

Degrading honestly while the archive is shallow
-----------------------------------------------
The archive began capturing on 2026-08-07 and it cannot be back-filled at our
published GP rate. Several of these detectors need weeks. Rather than return an
empty list — which reads as "nothing is interesting" — every detector that
cannot run yet returns a ``Deferral`` naming what it needs and when it becomes
available. The review page renders deferrals as visibly as candidates. "Not
enough history yet" has to look deliberate.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import re
import sqlite3
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from pipeline.orbit_events import (
    COHORT_PREFERRED,
    MINIMUM_USABLE_BSTAR,
    NON_PROPULSIVE_SIGNATURES,
    PASSIVE_TYPES,
    SIGNATURE_PROSE,
    TERMINAL_DECAY_PERIGEE_KM,
    Expectations,
    Interval,
    OrbitEvent,
    archive_maturity,
    detect_events,
    load_catalog,
    load_intervals,
    opacity_denied,
)
from pipeline.orbit_history import (
    archive_db_path,
    ORBIT_AVERAGING_MINIMUM,
    archive_root,
    epoch_ms_to_datetime,
    noise_floor_for,
    population_decay,
)

ROOT = Path(__file__).resolve().parents[1]

# Bumped whenever a threshold, an input, or a class definition changes. It is
# part of the deduplication key, so a threshold change deliberately re-opens
# every candidate for review rather than silently keeping the old verdicts.
DETECTOR_VERSION = "2026-08-07.1"

SCHEMA_VERSION = 1

# The closed enumeration. A candidate whose class is not in here is a hard
# error, not a pass-through — the same discipline the fact enumeration in
# `docs/mission-speculation-design.md` Section 2.1 uses, and for the same
# reason: a new class should arrive in a diff a reviewer sees.
CANDIDATE_CLASSES: frozenset[str] = frozenset(
    {
        "manoeuvre-out-of-family",
        "correlated-shell-decay",
        "orbit-contradicts-catalog",
        "delta-v-out-of-budget",
        "decay-rate-out-of-family",
    }
)

# ---------------------------------------------------------------------------
# Thresholds. Every one of them is here, named, with the reason attached.
# ---------------------------------------------------------------------------

# A manoeuvre only becomes a *curiosity* if the cohort screen actually ran on
# it. `orbit_events.detect_events` reports three confidence words, and only
# "candidate" means an anonymous population at the same altitude and
# inclination was compared over the same hours. The weaker two are honest
# labels on a measurement that has no control, and a measurement with no
# control is not evidence that something is unusual — it is evidence that
# something moved.
REQUIRED_EVENT_CONFIDENCE = "candidate"

# Expectation verdicts that make an event worth a human's attention. The two
# uninteresting verdicts are `expected-for-class` (the whole point of the
# expectations table) and `no-expectation` (we have not published a prior for
# this class, so we have nothing to be surprised against — surfacing those
# would fill the queue with our own coverage gaps).
CURIOUS_EXPECTATION_VERDICTS = frozenset({"unusual-for-class", "larger-than-typical"})

# `impossible-for-class` is deliberately NOT in that set, and the reason is the
# most important honesty decision in this file.
#
# A propulsive signature on a debris fragment or a spent stage is the most
# eye-catching thing this detector can produce, and it is **wrong by
# construction**: those objects have no propulsion. They are the free negative
# control (`docs/orbit-history-design.md` Section 3.7). Routing them into the
# review queue as curiosities would mean presenting our own measured error rate
# as a set of discoveries — which is precisely the failure this whole feature
# is built to prevent, in the one place it would be hardest to notice.
#
# So they go somewhere else: `Sweep.false_alarms`, rendered on the review page
# next to the candidates under a heading that says what they are. A queue that
# shows its own false-alarm rate beside its findings is more trustworthy than
# one that quietly filters them out, and it is the only number that tells a
# reviewer how much to believe the rest of the page.
FALSE_ALARM_VERDICT = "impossible-for-class"

# A per-object cadence is a property of one object's own time series. Below
# this many intervals there is no cadence, only a list of events, and calling a
# list of two events a "cadence departure" would be exactly the vibe this file
# exists to refuse. `orbit_events.archive_maturity` uses the same number.
CADENCE_MINIMUM_INTERVALS = 8

# Shell decay: how far a shell's median has to sit from the archive baseline
# for that shell before it is worth a look, in units of the combined standard
# error of the two medians. Three is chosen against the *population* standard
# error, which is a genuinely small number (design doc Section 5.6 estimates
# ~2.8% for a well-populated shell), not against the violently heavy-tailed
# single-object residual distribution where no threshold is meaningful.
SHELL_DEPARTURE_SIGMA = 3.0
SHELL_MINIMUM_OBJECTS = 20

# The shell detector needs a baseline window and a comparison window that do
# not overlap, and each needs to be long enough that the diurnal density cycle
# is integrated out rather than measured (design doc Section 5.4 — this is the
# trap that already ate a day of someone's work on this project).
SHELL_WINDOW_MINIMUM_DAYS = 1.0

# Decay-rate departure: the ratio of this object's B*-normalised decay to the
# passive population's median at the same altitude. A factor of two either way.
# Not a sigma, deliberately: `docs/orbit-history-design.md` Section 2.1 measured
# the fitted-element residual tails and found no usable decay, so a sigma
# threshold on a single object is not a probability statement. A factor of two
# in *drag* is a physical statement — it means this object is behaving as if it
# were flying through half or twice the air its neighbours are.
DECAY_RATIO_HIGH = 2.0
DECAY_RATIO_LOW = 0.5

# The physical factor above is necessary and **not sufficient**, and the reason
# is a measurement rather than a worry.
#
# Run over a 30-day window of the fifteen-year archive, the factor-of-two test
# alone flagged 88 of 797 usable passive intervals — **11%** — and the rate
# varied by an order of magnitude with altitude:
#
#     300-350 km   n=13   62% flagged      950-1000 km  n=20   20%
#     350-400 km   n=17   41%             1050-1100 km  n=13   23%
#     400-450 km   n=19   37%             1250-1300 km  n= 8   50%
#     550-950 km   n=40-154  3-8%         1350-1400 km  n= 8   38%
#
# Read that table as physics, not as noise. In the well-populated middle,
# where B* is a meaningful ballistic coefficient, the detector behaves exactly
# as the design predicted. At both ends it does not: down low the atmosphere is
# genuinely variable and the fits are chasing it, and up high drag is so weak
# that B* is fitted to almost nothing and the ratio is two small numbers
# divided by each other.
#
# A detector that flags one in ten of a *control* population is not finding
# anomalies, it is measuring the width of a distribution and calling it news.
# The fix is not to move the factor — that would be tuning a threshold until
# the answer looked right, which is the move this project has already refused
# once. The fix is to change the FORM of the test: an object must be a factor
# of two away in physical terms **and** lie outside its own shell's measured
# spread. The first condition keeps the claim physical; the second stops the
# claim being made where the population itself is that wide.
#
# Kappa 8 is the project's operating point everywhere else (orbit_events
# DEFAULT_KAPPA), used here against a robust MAD scale of the shell's own ratio
# distribution.
DECAY_SPREAD_KAPPA = 8.0

# Above this altitude the drag signal is too weak for a ratio of decay rates to
# mean anything, whatever B* says. `orbit_events.DRAG_MODEL_CEILING_KM` is
# 1400 km, which is the right ceiling for asking "is drag applicable at all";
# it is too generous for asking "is this object's drag unusual", and the
# 22-50% flag rates above 1050 km in the table are what that looks like.
DECAY_ALTITUDE_CEILING_KM = 1000.0

# How far the observed change in semi-major axis must exceed the *measured*
# catalogue fit scatter for its altitude band before a ratio built from it means
# anything. Without this, the detector divides one noise sample by another and
# reports the result to one decimal place: the first run produced ratios of 176
# and 1,331 this way, on objects that had barely moved. The factor of sqrt(2) at
# the call site is because two element sets each carry the scatter.
RESOLVABLE_DECAY_KAPPA = 8.0

# How much of the archive one sweep looks at, ending at the newest epoch held.
#
# Thirty days is chosen from the physics rather than from the clock: it is long
# enough for a geostationary east-west station-keeping cycle (one to four weeks)
# to show its cadence, long enough for the passive control to reach a few
# hundred intervals so the false-alarm rate becomes measurable, and short enough
# that every object in a cohort is being compared against the same weeks of
# space weather.
#
# It is also the guard against a real defect. The cohort screen compares an
# object against an anonymous population *over the same interval*. Sweeping the
# whole archive now that the 2004-2025 backfill has landed would place a 2009
# interval and a 2026 interval in the same shell, and the screen would compare
# an object against a population that was not there at the time. That is not a
# slow sweep, it is a wrong control, and it would produce confident nonsense.
DEFAULT_WINDOW_DAYS = 30.0

# Delta-v budgets in `data/orbit_manoeuvre_expectations.json` are published as
# prose figures ("40 to 51 m/s per year"). This parses the ones it can and
# skips the ones it cannot, rather than guessing at a number that will end up
# in a public claim.
_BUDGET_FIGURE = re.compile(
    r"(?P<low>\d+(?:\.\d+)?)\s*(?:to|-|–)\s*(?P<high>\d+(?:\.\d+)?)\s*m/s\s*per\s*(?P<period>year|day|manoeuvre|event)"
    r"|(?P<single>\d+(?:\.\d+)?)\s*m/s\s*per\s*(?P<single_period>year|day|manoeuvre|event)",
    re.IGNORECASE,
)

# Which budget applies to which regime. Read as data by a human, not inferred.
_BUDGET_REGIMES = {
    "geo-north-south": ("GEO", "near-GEO"),
    "geo-east-west": ("GEO", "near-GEO"),
    "geo-disposal": ("GEO", "near-GEO"),
    "leo-plane-change-vs-raise": ("LEO",),
}

# Fingerprint tolerances. The publish timer runs every five minutes over 8,000
# objects; an exact hash over drifting values re-fires forever and would drown
# the queue. This is the same lesson `pipeline/teaching_brief.py` records after
# a brief expired within one cycle of being written: tolerance bands, never
# rounded buckets, because a bucket has a boundary to cross and the data sits
# exactly on it.
_FINGERPRINT_TOLERANCE: dict[str, float] = {
    "deltaVMetresPerSecond": 0.05,
    "propulsiveDeltaAMetres": 25.0,
    "perigeeAltitudeKm": 5.0,
    "apogeeAltitudeKm": 5.0,
    "inclinationDeg": 0.05,
    "periodMinutes": 0.5,
    "medianDecayMetresPerDay": 5.0,
    "baselineDecayMetresPerDay": 5.0,
    "decayRatio": 0.1,
    "budgetMetresPerSecond": 0.5,
    "cohortMedian": 0.1,
}


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Subject:
    """What a candidate is about. Exactly one object, or one anonymous shell.

    ``kind`` is ``"object"`` or ``"shell"`` and nothing else. There is no
    ``kind == "pair"``, no list field, and no constructor that accepts more
    than one NORAD id. This is the structural half of the object-to-object
    exclusion in ``docs/mission-speculation-design.md`` Section 1.6: a shape
    that cannot hold two spacecraft cannot be made to relate two spacecraft by
    a later refactor, however well-intentioned.
    """

    kind: str
    norad: int | None = None
    name: str | None = None
    object_type: str | None = None
    perigee_band_km: tuple[float, float] | None = None

    def __post_init__(self) -> None:
        if self.kind not in ("object", "shell"):
            raise ValueError(f"unknown subject kind: {self.kind!r}")
        if self.kind == "object" and self.norad is None:
            raise ValueError("an object subject needs a NORAD id")
        if self.kind == "shell" and self.norad is not None:
            raise ValueError("a shell subject names no object, ever")

    @property
    def key(self) -> str:
        if self.kind == "object":
            return f"object:{self.norad}"
        band = self.perigee_band_km or (0.0, 0.0)
        return f"shell:{band[0]:.0f}-{band[1]:.0f}"

    def as_dict(self) -> dict[str, Any]:
        if self.kind == "object":
            return {
                "kind": "object",
                "noradId": self.norad,
                "name": self.name,
                "objectType": self.object_type,
            }
        return {
            "kind": "shell",
            "perigeeAltitudeKm": list(self.perigee_band_km or ()),
            "note": (
                "An anonymous altitude population. This record carries counts and "
                "medians and never a list of members."
            ),
        }


@dataclass(frozen=True)
class Candidate:
    """One measured departure, with everything needed to argue with it."""

    candidate_class: str
    subject: Subject
    headline: str
    measured: dict[str, float | int | None]
    expected: dict[str, Any]
    margin: str
    window: tuple[int, int]
    reproduce: dict[str, Any]
    alternatives: list[str]
    detector_version: str = DETECTOR_VERSION

    def __post_init__(self) -> None:
        if self.candidate_class not in CANDIDATE_CLASSES:
            raise ValueError(f"unknown candidate class: {self.candidate_class!r}")
        if not self.measured:
            raise ValueError("a candidate with no numbers is not a candidate")
        if not self.alternatives:
            raise ValueError(
                "every candidate must state at least one alternative explanation"
            )

    @property
    def fingerprint(self) -> str:
        """Identity of the *state* this candidate describes, within tolerance.

        Quantised, so ordinary element churn does not manufacture a new
        candidate every five minutes. Deliberately excludes the window
        timestamps: a candidate re-observed an hour later with the same numbers
        is the same finding, and re-queuing it would bury the review page.
        """
        reduced = {
            key: _quantise(_FINGERPRINT_TOLERANCE[key], value)
            if key in _FINGERPRINT_TOLERANCE
            else value
            for key, value in sorted(self.measured.items())
        }
        payload = {
            "class": self.candidate_class,
            "subject": self.subject.key,
            "measured": reduced,
            "detectorVersion": self.detector_version,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    @classmethod
    def from_dict(cls, record: dict[str, Any]) -> "Candidate":
        """Rebuild a candidate from a sweep artifact.

        The sweep became expensive once the archive went from an afternoon to
        fifteen years, so detection and queueing are no longer sensibly done in
        one process: a sweep is a durable artifact that can be reviewed, argued
        with, and *then* queued, possibly by a different person on a different
        day. This is the seam that makes that possible.

        It re-runs every constructor invariant — the closed class enumeration,
        the "numbers required" rule, the "alternative explanation required"
        rule, and the single-object subject shape — rather than trusting the
        file, because a sweep artifact is an ordinary file on disk that anybody
        could have edited between the two steps.
        """
        subject = record.get("subject") or {}
        if subject.get("kind") == "shell":
            band = subject.get("perigeeAltitudeKm") or []
            rebuilt = Subject(
                kind="shell",
                perigee_band_km=(float(band[0]), float(band[1])) if len(band) == 2 else None,
            )
        else:
            rebuilt = Subject(
                kind="object",
                norad=subject.get("noradId"),
                name=subject.get("name"),
                object_type=subject.get("objectType"),
            )
        window = record.get("observedWindow") or {}
        return cls(
            candidate_class=str(record.get("class")),
            subject=rebuilt,
            headline=str(record.get("headline") or ""),
            measured=dict(record.get("measured") or {}),
            expected=dict(record.get("expected") or {}),
            margin=str(record.get("margin") or ""),
            window=(
                (_epoch_ms(window.get("from")), _epoch_ms(window.get("to")))
                if window
                else (0, 0)
            ),
            reproduce=dict(record.get("reproduce") or {}),
            alternatives=list(record.get("alternativeExplanations") or []),
            detector_version=str(record.get("detectorVersion") or DETECTOR_VERSION),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "class": self.candidate_class,
            "subject": self.subject.as_dict(),
            "subjectKey": self.subject.key,
            "headline": self.headline,
            "measured": self.measured,
            "expected": self.expected,
            "margin": self.margin,
            # A candidate that is not about an interval has no window, and a
            # zero must never be rendered as 1970-01-01 — an epoch-zero leak is
            # exactly the kind of plausible-looking wrong number this project
            # has been bitten by before.
            "observedWindow": (
                None
                if self.window == (0, 0)
                else {"from": _iso(self.window[0]), "to": _iso(self.window[1])}
            ),
            "reproduce": self.reproduce,
            "alternativeExplanations": self.alternatives,
            "detectorVersion": self.detector_version,
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True)
class Deferral:
    """A detector that cannot run yet, and exactly what it is waiting for.

    This exists so the review page can distinguish "we looked and found
    nothing" from "we cannot look yet". Those are completely different
    statements and collapsing them into an empty list is dishonest.
    """

    candidate_class: str
    needs: str
    why: str
    have: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "class": self.candidate_class,
            "status": "not-yet-computable",
            "needs": self.needs,
            "why": self.why,
            "have": self.have,
        }


@dataclass
class Sweep:
    """The whole result of one detection pass."""

    generated_at: str
    detector_version: str
    candidates: list[Candidate]
    deferrals: list[Deferral]
    inputs: dict[str, Any]
    maturity: dict[str, Any]
    eligibility: dict[str, Any]
    false_alarms: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA_VERSION,
            "generatedAt": self.generated_at,
            "detectorVersion": self.detector_version,
            "inputs": self.inputs,
            "archiveMaturity": self.maturity,
            "eligibility": self.eligibility,
            "candidates": [candidate.as_dict() for candidate in self.candidates],
            "deferrals": [deferral.as_dict() for deferral in self.deferrals],
            "falseAlarms": {
                "note": (
                    "Propulsive signatures reported on objects that have no propulsion. These "
                    "are wrong by construction and they are the honest measure of how much to "
                    "believe the candidates above. They are never queued as findings."
                ),
                "count": len(self.false_alarms),
                "events": self.false_alarms,
            },
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _mad_sigma(values: Sequence[float]) -> float:
    """Robust 1-sigma from the median absolute deviation.

    Local rather than imported: `orbit_history._mad_sigma` is private, and a
    detector that depends on another module's private name breaks silently the
    day that module is tidied.
    """
    if len(values) < 3:
        return float("nan")
    centre = statistics.median(values)
    mad = statistics.median([abs(value - centre) for value in values])
    return 1.4826 * mad


def _quantise(step: float, value: Any) -> Any:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return value
    if value != value or step <= 0:  # NaN, or a nonsense step
        return value
    return round(round(float(value) / step) * step, 6)


def _iso(epoch_ms: int) -> str:
    return epoch_ms_to_datetime(epoch_ms).isoformat(timespec="seconds").replace("+00:00", "Z")


def _epoch_ms(value: Any) -> int:
    """Element epoch in milliseconds, or zero when it cannot be read.

    Zero is a sentinel the record renders as "no window", never as 1970. The
    conversion is here rather than inline so that the one place that produces a
    zero is the one place that has to be read alongside `Candidate.as_dict`.
    """
    if not isinstance(value, str) or not value:
        return 0
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return 0
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return int(parsed.timestamp() * 1000)


def _round(value: float | None, places: int) -> float | None:
    if value is None or value != value or value in (float("inf"), float("-inf")):
        return None
    return round(float(value), places)


def eligible(record: dict[str, Any] | None, name: str | None) -> bool:
    """True when this object may appear in the queue at all.

    Thin wrapper over ``pipeline.orbit_events.opacity_denied`` so that there is
    exactly one implementation of the gate on this project and a change to it
    reaches every consumer. Objects denied in the mission-speculation design
    are denied here, on identical terms, with no reference to nationality.

    Note the asymmetry with ``orbit_events``: there, a denied object still gets
    its physics rendered and only loses *purpose language*. Here the whole
    artifact is a claim that something is curious about a specific spacecraft,
    which is a claim about the spacecraft, so the gate removes the record
    entirely rather than trimming a field off it.
    """
    record = record or {}
    return not opacity_denied(
        name or record.get("name"),
        record.get("sector"),
        record.get("mission"),
        record.get("classificationConfidence"),
    )


def _reproduce(command: str, **inputs: Any) -> dict[str, Any]:
    return {
        "command": command,
        "inputs": inputs,
        "note": (
            "Runs against files already on this disk. Nothing in the detection "
            "stage makes a network request."
        ),
    }


def parse_budget(figure: str) -> dict[str, Any] | None:
    """Turn a published budget figure into a number, or refuse.

    ``"40 to 51 m/s per year"`` becomes an upper bound of 51 m/s per year.
    Anything this cannot parse returns ``None`` and the budget is skipped, on
    the principle that a made-up threshold is worse than a missing one — the
    figure ends up inside a public claim about how much an operator spent.
    """
    match = _BUDGET_FIGURE.search(figure or "")
    if match is None:
        return None
    if match.group("single") is not None:
        high = float(match.group("single"))
        low = high
        period = match.group("single_period").lower()
    else:
        low = float(match.group("low"))
        high = float(match.group("high"))
        period = match.group("period").lower()
    return {"lowMetresPerSecond": low, "highMetresPerSecond": high, "per": period}


# ---------------------------------------------------------------------------
# Detector 1 — a manoeuvre out of family for its own class of object
# ---------------------------------------------------------------------------
def detect_manoeuvre_out_of_family(
    events: Sequence[OrbitEvent],
    intervals: Sequence[Interval],
    catalog: dict[int, dict[str, Any]],
) -> tuple[list[Candidate], list[Deferral]]:
    """Objects whose manoeuvre is not what their published class ordinarily does.

    The expectation is not a threshold this file invented. It comes from
    ``data/orbit_manoeuvre_expectations.json``, which is hand-authored, cited
    and versioned, and ``orbit_events.score_against_expectation()`` has already
    compared the event against it. All this detector does is decide which of
    those verdicts is worth a human's time, and apply the eligibility gate.

    Two things it deliberately does *not* do. It does not surface
    ``no-expectation`` verdicts, because those are our coverage gaps rather
    than the sky's anomalies. And it does not call a run of two events a
    cadence — see the deferral below.
    """
    candidates: list[Candidate] = []
    per_object = _intervals_per_object(intervals)

    for event in events:
        if event.signature in NON_PROPULSIVE_SIGNATURES:
            continue
        if event.confidence != REQUIRED_EVENT_CONFIDENCE:
            continue
        verdict = event.expectation.get("verdict")
        if verdict not in CURIOUS_EXPECTATION_VERDICTS:
            continue
        record = catalog.get(event.norad, {})
        if not eligible(record, event.name):
            continue

        label, _ = SIGNATURE_PROSE.get(event.signature, (event.signature, ""))
        screened = [test for test in event.tests if test.tripped and test.cohort_screened]
        cohort_count = max((test.cohort_count for test in screened), default=0)
        cohort_z = max((abs(test.cohort_z or 0.0) for test in screened), default=0.0)

        candidates.append(
            Candidate(
                candidate_class="manoeuvre-out-of-family",
                subject=Subject(
                    kind="object",
                    norad=event.norad,
                    name=event.name,
                    object_type=event.object_type,
                ),
                headline=(
                    f"{event.name} shows a {label} that is not among the manoeuvres "
                    f"its class is published as performing."
                ),
                measured={
                    "deltaVMetresPerSecond": _round(event.delta_v.total, 4),
                    "propulsiveDeltaAMetres": _round(
                        event.delta_v.propulsive_delta_a_metres, 1
                    ),
                    "perigeeAltitudeKm": _round(event.perigee_altitude_km, 1),
                    "apogeeAltitudeKm": _round(event.apogee_altitude_km, 1),
                    "inclinationDeg": _round(event.inclination_deg, 4),
                    "cohortZ": _round(cohort_z, 2),
                    "cohortCount": cohort_count,
                    "spanDays": _round((event.end_ms - event.start_ms) / 86_400_000.0, 4),
                },
                expected={
                    "source": "data/orbit_manoeuvre_expectations.json",
                    "class": event.expectation.get("class"),
                    "verdict": verdict,
                    "reason": event.expectation.get("reason"),
                    "citations": event.expectation.get("citations", []),
                    "signature": event.signature,
                    "signatureLabel": label,
                },
                margin=(
                    f"{cohort_z:.1f} times the robust scale of an anonymous population of "
                    f"{cohort_count} objects at the same perigee altitude and inclination, "
                    f"measured over the same hours."
                ),
                window=(event.start_ms, event.end_ms),
                reproduce=_reproduce(
                    "python3 -m pipeline.discovery --sweep --only manoeuvre-out-of-family",
                    noradId=event.norad,
                    startAt=_iso(event.start_ms),
                    endAt=_iso(event.end_ms),
                    expectationsVersion=None,
                ),
                alternatives=[
                    "A catalogue re-fit after a tracking gap can move the fitted mean "
                    "elements without the spacecraft doing anything.",
                    "The expectations table may simply be incomplete for this class; an "
                    "unlisted ordinary manoeuvre reads as unusual.",
                    "A correlation error between two nearby catalogued objects can swap "
                    "element sets and produce a step neither object performed.",
                    "Unmodelled solar radiation pressure, which matters most for high "
                    "area-to-mass objects.",
                ],
            )
        )

    deferrals: list[Deferral] = []
    ready = sum(1 for count in per_object.values() if count >= CADENCE_MINIMUM_INTERVALS)
    if ready == 0:
        deferrals.append(
            Deferral(
                candidate_class="manoeuvre-out-of-family",
                needs=(
                    f"{CADENCE_MINIMUM_INTERVALS} or more element-set intervals for a single "
                    "object, typically three to five days of archive"
                ),
                why=(
                    "A *cadence* departure — this object corrects more or less often than its "
                    "class does — is a property of one object's own time series and cannot be "
                    "borrowed from the population. Until then this detector reports single "
                    "out-of-family events only, which is a weaker statement and is labelled as "
                    "one."
                ),
                have={
                    "objectsWithIntervals": len(per_object),
                    "objectsReadyForCadence": ready,
                    "maxIntervalsOnOneObject": max(per_object.values(), default=0),
                },
            )
        )
    return candidates, deferrals


def _intervals_per_object(intervals: Sequence[Interval]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for interval in intervals:
        counts[interval.norad] = counts.get(interval.norad, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Detector 2 — a whole altitude shell moving together
# ---------------------------------------------------------------------------
def detect_correlated_shell_decay(
    connection: sqlite3.Connection,
    *,
    baseline: tuple[int, int],
    comparison: tuple[int, int],
    shell_km: float = 50.0,
    min_objects: int = SHELL_MINIMUM_OBJECTS,
) -> tuple[list[Candidate], list[Deferral]]:
    """Shells whose passive population decayed together, against their own baseline.

    This is the one candidate class that is about a population rather than an
    object, and it is the strongest kind of evidence the archive can produce:
    a storm bends a whole shell at once, and a shell median over hundreds of
    independent passive tracers has a standard error of a couple of per cent
    where a single object's residual distribution has no usable tail at all.

    It is also the class that sits closest to the object-association boundary,
    so it is worth being explicit: the record carries an altitude band, an
    object count, a median and a standard error. It never carries a member
    list, and ``population_decay()`` has no accessor that could supply one.

    Restricted to DEBRIS and ROCKET BODY. Those cannot manoeuvre, so they are
    clean ballistic tracers of the density they fly through, and a manoeuvring
    payload cannot contaminate the very quantity being measured.
    """
    baseline_days = (baseline[1] - baseline[0]) / 86_400_000.0
    comparison_days = (comparison[1] - comparison[0]) / 86_400_000.0
    if baseline_days < SHELL_WINDOW_MINIMUM_DAYS or comparison_days < SHELL_WINDOW_MINIMUM_DAYS:
        return [], [
            Deferral(
                candidate_class="correlated-shell-decay",
                needs=(
                    f"two non-overlapping windows of at least {SHELL_WINDOW_MINIMUM_DAYS:g} day "
                    "each in the same archive"
                ),
                why=(
                    "Neutral density swings by about a factor of two between the day and night "
                    "sides. A comparison built from windows shorter than this measures the "
                    "diurnal cycle and reports it as a storm, which is a mistake this project "
                    "has already made once."
                ),
                have={
                    "baselineDays": round(baseline_days, 4),
                    "comparisonDays": round(comparison_days, 4),
                },
            )
        ]
    if baseline[1] > comparison[0]:
        raise ValueError("the baseline window must end before the comparison window begins")

    before = {
        tuple(row["perigeeAltitudeKm"]): row
        for row in population_decay(
            connection,
            start_ms=baseline[0],
            end_ms=baseline[1],
            shell_km=shell_km,
            min_objects=min_objects,
        )
    }
    after = {
        tuple(row["perigeeAltitudeKm"]): row
        for row in population_decay(
            connection,
            start_ms=comparison[0],
            end_ms=comparison[1],
            shell_km=shell_km,
            min_objects=min_objects,
        )
    }
    shared = sorted(set(before) & set(after))
    if not shared:
        return [], [
            Deferral(
                candidate_class="correlated-shell-decay",
                needs=(
                    f"at least one perigee shell holding {min_objects} distinct passive objects "
                    "in BOTH windows"
                ),
                why=(
                    "The comparison is per shell against that same shell's own earlier "
                    "behaviour. A shell present in only one window cannot be compared with "
                    "anything, and comparing different shells would measure the population mix "
                    "rather than the atmosphere."
                ),
                have={
                    "shellsInBaseline": len(before),
                    "shellsInComparison": len(after),
                    "shellsInBoth": 0,
                },
            )
        ]

    candidates: list[Candidate] = []
    for band in shared:
        base, comp = before[band], after[band]
        base_se = base.get("standardErrorMetresPerDay")
        comp_se = comp.get("standardErrorMetresPerDay")
        if base_se is None or comp_se is None:
            continue
        combined = math.hypot(base_se, comp_se)
        if combined <= 0:
            continue
        delta = comp["medianDecayMetresPerDay"] - base["medianDecayMetresPerDay"]
        sigma = abs(delta) / combined
        if sigma < SHELL_DEPARTURE_SIGMA:
            continue
        direction = "faster" if delta < 0 else "slower"
        ratio = (
            comp["medianDecayMetresPerDay"] / base["medianDecayMetresPerDay"]
            if base["medianDecayMetresPerDay"]
            else None
        )
        candidates.append(
            Candidate(
                candidate_class="correlated-shell-decay",
                subject=Subject(kind="shell", perigee_band_km=(band[0], band[1])),
                headline=(
                    f"Passive objects with perigee between {band[0]:.0f} and {band[1]:.0f} km "
                    f"decayed {direction} in the comparison window than they had been."
                ),
                measured={
                    "medianDecayMetresPerDay": _round(comp["medianDecayMetresPerDay"], 2),
                    "baselineDecayMetresPerDay": _round(base["medianDecayMetresPerDay"], 2),
                    "decayRatio": _round(ratio, 3),
                    "comparisonObjects": comp["objects"],
                    "baselineObjects": base["objects"],
                    "combinedStandardErrorMetresPerDay": _round(combined, 2),
                    "departureSigma": _round(sigma, 2),
                },
                expected={
                    "source": "the same shell's own decay in the baseline window",
                    "threshold": (
                        f"a departure of at least {SHELL_DEPARTURE_SIGMA:g} combined standard "
                        f"errors, over at least {min_objects} distinct passive objects"
                    ),
                    "physics": (
                        "Semi-major axis decay is linear in neutral density, so a shell-wide "
                        "change in decay rate IS a change in the density at that altitude. The "
                        "ballistic coefficient cancels because each object is compared against "
                        "its own shell's earlier behaviour."
                    ),
                },
                margin=f"{sigma:.1f} combined standard errors of the two shell medians.",
                window=(baseline[0], comparison[1]),
                reproduce=_reproduce(
                    "python3 -m pipeline.discovery --sweep --only correlated-shell-decay",
                    perigeeAltitudeKm=list(band),
                    baselineFrom=_iso(baseline[0]),
                    baselineTo=_iso(baseline[1]),
                    comparisonFrom=_iso(comparison[0]),
                    comparisonTo=_iso(comparison[1]),
                ),
                alternatives=[
                    "A change in which objects the catalogue tracked between the two windows "
                    "changes the population, not the atmosphere.",
                    "Element-set spacing is not uniform, so the two windows are not equally "
                    "weighted across objects.",
                    "Eccentric orbits sample a range of altitudes; binning on perigee is right "
                    "but not exact.",
                    "A catalogue-wide re-fit or process change at the tracking network moves "
                    "every object at once, which looks exactly like weather.",
                ],
            )
        )
    return candidates, []


# ---------------------------------------------------------------------------
# Detector 3 — the orbit contradicts the catalog label
# ---------------------------------------------------------------------------
def detect_orbit_contradicts_catalog(
    catalog_records: Iterable[dict[str, Any]],
) -> tuple[list[Candidate], list[Deferral]]:
    """Objects whose own elements rule out the mission their label asserts.

    The site already computes this and already publishes it, as
    ``contestedAttribution`` entries of kind ``orbit-inconsistent`` — see
    ``docs/catalog-accuracy-audit.md``. This detector does not recompute the
    rule; it reads the published annotation, which means the queue and the
    public card can never disagree about the same object.

    **This complements the card rather than duplicating it.** The card already
    renders the disagreement and is a finished statement that needs no review.
    What it does not do is ask the next question — *has anybody written this
    up?* — and that question is the whole reason this class is in the queue.
    For one of these objects the answer turns out to be yes, with a DOI, and
    the entry is worth having because it demonstrates the method rediscovering
    a published result from elements alone. For the others the answer is no,
    and the entry is worth having because a person now has to decide whether
    that means anything or whether the searches were simply poor.

    The eligibility gate matters more here than anywhere else in this file. A
    sentence of the form "the catalog says this is an imager and the orbit says
    it cannot be" is a claim about a specific spacecraft's purpose. Applied to
    an opaque military object it is a mission assessment, which is precisely
    what ``docs/mission-speculation-design.md`` exists to prevent. Denied
    objects therefore produce no candidate, and their absence is silent.
    """
    candidates: list[Candidate] = []
    for record in catalog_records:
        contested = record.get("contestedAttribution") or []
        entries = [
            entry
            for entry in contested
            if isinstance(entry, dict) and entry.get("kind") == "orbit-inconsistent"
        ]
        if not entries:
            continue
        if not eligible(record, record.get("name")):
            continue
        entry = entries[0]
        omm = record.get("omm") or {}
        # This candidate is a property of one element set rather than of an
        # interval, so the "window" is that element set's own epoch. Without
        # this the record would carry a zero and render as 1970.
        epoch_ms = _epoch_ms(omm.get("EPOCH"))
        candidates.append(
            Candidate(
                candidate_class="orbit-contradicts-catalog",
                subject=Subject(
                    kind="object",
                    norad=record.get("id"),
                    name=record.get("name"),
                    object_type=record.get("orbit"),
                ),
                headline=(
                    f"{record.get('name')} is catalogued as "
                    f"{record.get('mission')}, and its own orbit is not the geometry that "
                    f"mission ordinarily uses."
                ),
                measured={
                    "periodMinutes": _round(record.get("periodMinutes"), 2),
                    "perigeeAltitudeKm": _round(record.get("perigeeKm"), 1),
                    "apogeeAltitudeKm": _round(record.get("apogeeKm"), 1),
                    "inclinationDeg": _round(omm.get("INCLINATION"), 4),
                    "eccentricity": _round(omm.get("ECCENTRICITY"), 7),
                },
                expected={
                    "source": "pipeline/build_release.py orbit-vs-mission table, via the published catalog",
                    "catalogMission": record.get("mission"),
                    "catalogOrbit": record.get("orbit"),
                    "classificationBasis": record.get("classificationBasis"),
                    "classificationConfidence": record.get("classificationConfidence"),
                    "publishedAnnotation": entry,
                    "strength": entry.get("strength"),
                },
                margin=(
                    "This is a categorical contradiction rather than a statistical one: the "
                    "regime is computed from the elements and the mission is read from the "
                    "catalog, and the published rule table says the two do not go together."
                ),
                window=(epoch_ms, epoch_ms),
                reproduce=_reproduce(
                    "python3 -m pipeline.catalog_audit --json /tmp/audit.json",
                    noradId=record.get("id"),
                    check="regime-mission-contradiction",
                    catalogArtifact="see public/data/manifest.json -> catalog.path",
                ),
                alternatives=[
                    "The mission label may simply be wrong or over-broad; the registries "
                    "establish who registered an object and where it is, never what it is for.",
                    "A programme name can span several distinct missions flown in different "
                    "orbits, so the label may be right for the programme and wrong for this "
                    "flight.",
                    "The orbit-vs-mission rule is a statement about what is usual, and an "
                    "unusual-but-real design choice is exactly what a teaching site should "
                    "expect to find.",
                ],
            )
        )
    return candidates, []


# ---------------------------------------------------------------------------
# Detector 4 — Delta-v out of budget for the regime
# ---------------------------------------------------------------------------
def detect_delta_v_out_of_budget(
    events: Sequence[OrbitEvent],
    catalog: dict[int, dict[str, Any]],
    expectations: Expectations,
) -> tuple[list[Candidate], list[Deferral]]:
    """One interval that spends more than the regime's whole published budget.

    The comparison is deliberately unfair to the detector: a *single interval*
    of a few hours is compared against a published figure covering a *year*.
    Anything that clears that bar is spending at a rate no station-keeping
    budget can explain, which makes it worth a look without needing a tuned
    threshold at all.

    Budgets come from ``data/orbit_manoeuvre_expectations.json``, hand-authored
    with their derivations. Figures this cannot parse are skipped and named in
    the deferral rather than guessed at.
    """
    budgets: list[dict[str, Any]] = []
    unparsed: list[str] = []
    for entry in expectations.budgets:
        parsed = parse_budget(str(entry.get("figure", "")))
        if parsed is None:
            unparsed.append(str(entry.get("id")))
            continue
        budgets.append({**entry, "parsed": parsed})

    candidates: list[Candidate] = []
    for event in events:
        if event.signature in NON_PROPULSIVE_SIGNATURES:
            continue
        if event.confidence != REQUIRED_EVENT_CONFIDENCE:
            continue
        record = catalog.get(event.norad, {})
        if not eligible(record, event.name):
            continue
        for budget in budgets:
            regimes = _BUDGET_REGIMES.get(str(budget.get("id")), ())
            if event.regime not in regimes:
                continue
            if budget["parsed"]["per"] != "year":
                continue
            ceiling = budget["parsed"]["highMetresPerSecond"]
            if event.delta_v.total <= ceiling:
                continue
            span_days = (event.end_ms - event.start_ms) / 86_400_000.0
            candidates.append(
                Candidate(
                    candidate_class="delta-v-out-of-budget",
                    subject=Subject(
                        kind="object",
                        norad=event.norad,
                        name=event.name,
                        object_type=event.object_type,
                    ),
                    headline=(
                        f"{event.name} changed its orbit by at least "
                        f"{event.delta_v.total:.2f} m/s in {span_days:.2f} days, which is more "
                        f"than the published annual budget for {budget.get('label')}."
                    ),
                    measured={
                        "deltaVMetresPerSecond": _round(event.delta_v.total, 4),
                        "budgetMetresPerSecond": ceiling,
                        "spanDays": _round(span_days, 4),
                        "perigeeAltitudeKm": _round(event.perigee_altitude_km, 1),
                        "apogeeAltitudeKm": _round(event.apogee_altitude_km, 1),
                        "inclinationDeg": _round(event.inclination_deg, 4),
                    },
                    expected={
                        "source": "data/orbit_manoeuvre_expectations.json deltaVBudgets",
                        "budgetId": budget.get("id"),
                        "budgetLabel": budget.get("label"),
                        "figure": budget.get("figure"),
                        "derivation": budget.get("derivation"),
                        "kind": budget.get("kind"),
                        "regime": event.regime,
                    },
                    margin=(
                        f"{event.delta_v.total / ceiling:.1f} times the published annual figure, "
                        f"spent in {span_days:.2f} days. The Delta-v itself is a lower bound: it "
                        "is the cheapest manoeuvre consistent with the element change."
                    ),
                    window=(event.start_ms, event.end_ms),
                    reproduce=_reproduce(
                        "python3 -m pipeline.discovery --sweep --only delta-v-out-of-budget",
                        noradId=event.norad,
                        startAt=_iso(event.start_ms),
                        endAt=_iso(event.end_ms),
                        budgetId=budget.get("id"),
                        expectationsVersion=expectations.version,
                    ),
                    alternatives=[
                        "A single large manoeuvre is ordinary at some points in a mission — "
                        "orbit raising after launch, a relocation, or end-of-life disposal — and "
                        "comparing it to a station-keeping budget is the wrong comparison.",
                        "A catalogue re-fit or a correlation error can produce an element change "
                        "no propulsion caused, and the Delta-v is computed from the elements.",
                        "The budget figure is a published typical value, not a limit anyone "
                        "agreed to.",
                    ],
                )
            )
            break

    deferrals: list[Deferral] = []
    if unparsed:
        deferrals.append(
            Deferral(
                candidate_class="delta-v-out-of-budget",
                needs="a machine-readable figure for every published Delta-v budget",
                why=(
                    "These budgets are published as prose and this detector refuses to guess a "
                    "number that would end up inside a public claim about what an operator "
                    "spent. The unparsed budgets are simply not applied."
                ),
                have={"unparsedBudgetIds": sorted(unparsed)},
            )
        )
    return candidates, deferrals


# ---------------------------------------------------------------------------
# Detector 5 — decaying far faster or slower than its neighbourhood
# ---------------------------------------------------------------------------
def detect_decay_rate_out_of_family(
    intervals: Sequence[Interval],
    catalog: dict[int, dict[str, Any]],
    *,
    kp_max: float | None = None,
    shell_km: float = 50.0,
    min_cohort: int = COHORT_PREFERRED,
) -> tuple[list[Candidate], list[Deferral]]:
    """Passive objects flying as if through half or twice the air their neighbours are.

    The quantity is ``adot / B*``. From

        adot_drag = -(C_D A / m) rho sqrt(mu a)

    and the fact that the fitted B* term is proportional to ``C_D A / m``, the
    ratio ``adot / B*`` is very nearly a property of the *atmosphere* alone at a
    given altitude — shared by every object flying through it, whatever it is
    made of. ``pipeline/orbit_events.py`` measured this on the live archive:
    normalising by B* tightens the relative spread of a 50 km shell from 1.27 to
    0.14 at 750-800 km. So an object sitting a factor of two away from its
    shell's median is not a noisy measurement, it is a physical statement.

    The threshold is a *ratio*, not a sigma, on purpose. The fitted-element
    residual distribution has no usable tail decay (design doc Section 2.1), so
    a sigma on one object is not a probability. A factor of two in drag is.

    The prevailing Kp travels with every candidate, because "decaying unusually
    fast" during a geomagnetic storm and "decaying unusually fast" on a quiet
    day are different findings and only one of them is surprising.

    Four restrictions, and the first one is not a nicety
    ---------------------------------------------------
    1. **Passive objects only — debris and spent stages, on both sides.**
       ``adot/B*`` measures the atmosphere only for an object that is not
       thrusting. The first run of this detector, without this restriction,
       returned 176 candidates of which 168 were Starlink spacecraft: a
       constellation that raises and lowers its orbit continuously departs from
       a ballistic population by construction, and calling that "unusual decay"
       is calling propulsion weather. A manoeuvre is Detector 1's job. This one
       makes a statement about air, so it is restricted to objects that can only
       respond to air. **This does mean a genuinely odd payload decay is not
       reported here.** That is a stated limitation, not an oversight: without
       propulsion excluded, no drag claim about a payload is separable.
    2. **Orbit-averaged intervals only.** Neutral density swings by about a
       factor of two between the day and night sides, so a rate measured over a
       fraction of a revolution measures local solar time. Requiring at least
       ``ORBIT_AVERAGING_MINIMUM`` complete revolutions integrates it out. This
       is the trap that already cost this project a day of work.
    3. **The change must be resolvable.** The observed change in semi-major
       axis has to exceed the measured catalogue fit scatter for that altitude
       band by a comfortable factor, otherwise a ratio of two noise samples
       produces a spectacular number with no physics behind it. The unrestricted
       first run produced ratios of 1,331 and 176 this way.
    4. **A usable B*, away from both ends.** Below ``MINIMUM_USABLE_BSTAR`` the
       drag term was not really fitted and dividing by it invents a number;
       below ``TERMINAL_DECAY_PERIGEE_KM`` the object is re-entering and its
       fits are degrading faster than the arc; above
       ``DECAY_ALTITUDE_CEILING_KM`` drag is too weak for a ratio of decay
       rates to mean anything and B* is fitted to almost nothing.
    5. **A departure from the shell's own measured spread**, not only from a
       fixed factor -- see ``DECAY_SPREAD_KAPPA``, which records the 11%
       control-population flag rate that made it necessary.
    """
    usable = [
        interval
        for interval in intervals
        # Restriction 1: passive tracers only, subject and cohort alike.
        if interval.object_type in PASSIVE_TYPES
        # Restriction 4.
        and interval.bstar is not None
        and interval.bstar > MINIMUM_USABLE_BSTAR
        and TERMINAL_DECAY_PERIGEE_KM
        <= interval.perigee_altitude_km
        <= DECAY_ALTITUDE_CEILING_KM
        # Restriction 2.
        and interval.span_days * interval.mean_motion_rev_per_day >= ORBIT_AVERAGING_MINIMUM
        # Restriction 3.
        and abs(interval.delta_a_km) > RESOLVABLE_DECAY_KAPPA
        * noise_floor_for(interval.perigee_altitude_km)[0]
        * math.sqrt(2.0)
    ]
    shells: dict[int, list[tuple[Interval, float]]] = {}
    for interval in usable:
        normalised = (interval.delta_a_km / interval.span_days) / interval.bstar
        shells.setdefault(int(interval.perigee_altitude_km // shell_km), []).append(
            (interval, normalised)
        )

    candidates: list[Candidate] = []
    thin = 0
    for index, members in sorted(shells.items()):
        values = [value for _, value in members]
        if len(values) < min_cohort:
            thin += 1
            continue
        median = statistics.median(values)
        # The shell's own spread, robustly. MAD rather than a standard
        # deviation because one genuinely odd member would inflate a standard
        # deviation enough to hide itself -- the same reason `orbit_history`
        # uses MAD for its per-object scale.
        ratios = [value / median for value in values] if median else []
        spread = _mad_sigma(ratios)
        if median >= 0:
            # A shell whose passive median is not decaying gives nothing to
            # divide by; dividing by noise invents a ratio.
            continue
        band = (index * shell_km, (index + 1) * shell_km)
        for interval, value in members:
            ratio = value / median
            # Both conditions, and each does a different job. The factor keeps
            # the claim physical -- "as if through half or twice the air". The
            # spread test stops the claim being made in a shell whose own
            # population is that wide, which measurement showed is most of
            # them at the top and bottom of the altitude range.
            if DECAY_RATIO_LOW < ratio < DECAY_RATIO_HIGH:
                continue
            if spread != spread or spread <= 0:
                continue
            spread_sigma = abs(ratio - 1.0) / spread
            if spread_sigma < DECAY_SPREAD_KAPPA:
                continue
            record = catalog.get(interval.norad, {})
            if not eligible(record, interval.name):
                continue
            # A negative ratio means the semi-major axis ROSE while the shell
            # around it fell. Drag cannot do that, so calling it "slower decay"
            # would be wrong in kind rather than in degree, and the honest label
            # says what actually happened.
            direction = (
                "faster"
                if ratio >= DECAY_RATIO_HIGH
                else "in the opposite direction to"
                if ratio <= 0
                else "slower"
            )
            candidates.append(
                Candidate(
                    candidate_class="decay-rate-out-of-family",
                    subject=Subject(
                        kind="object",
                        norad=interval.norad,
                        name=interval.name,
                        object_type=interval.object_type,
                    ),
                    headline=(
                        f"{interval.name} changed altitude {abs(ratio):.1f} times "
                        f"{direction} the passive objects sharing its altitude, once each "
                        "object's own ballistic coefficient is divided out."
                        if ratio <= 0
                        else f"{interval.name} is losing altitude {ratio:.1f} times "
                        f"{direction} than the passive objects sharing its altitude, once "
                        "each object's own ballistic coefficient is divided out."
                    ),
                    measured={
                        "decayRatio": _round(ratio, 3),
                        "normalisedDecay": _round(value, 3),
                        "cohortMedian": _round(median, 3),
                        "cohortRatioSpread": _round(spread, 4),
                        "spreadSigma": _round(spread_sigma, 2),
                        "cohortCount": len(values),
                        "decayMetresPerDay": _round(
                            interval.delta_a_km / interval.span_days * 1000.0, 2
                        ),
                        "bstar": interval.bstar,
                        "perigeeAltitudeKm": _round(interval.perigee_altitude_km, 1),
                        "apogeeAltitudeKm": _round(interval.apogee_altitude_km, 1),
                        "inclinationDeg": _round(interval.inclination_deg, 4),
                        "spanDays": _round(interval.span_days, 4),
                        "kpMax": kp_max,
                    },
                    expected={
                        "source": "the median of the same quantity over this object's own perigee shell",
                        "quantity": "semi-major-axis decay rate divided by the fitted B* drag term",
                        "shellPerigeeAltitudeKm": list(band),
                        "threshold": (
                            f"a ratio at or above {DECAY_RATIO_HIGH:g} or at or below "
                            f"{DECAY_RATIO_LOW:g} -- the physical condition -- AND at least "
                            f"{DECAY_SPREAD_KAPPA:g} robust deviations from the same shell's "
                            f"own ratio spread, over a shell of at least {min_cohort} "
                            f"intervals below {DECAY_ALTITUDE_CEILING_KM:g} km. The factor "
                            "alone flagged 11% of the passive control population, which is a "
                            "distribution width rather than a set of anomalies."
                        ),
                        "physics": (
                            "Decay is linear in neutral density and B* is proportional to the "
                            "ballistic coefficient, so adot/B* is a property of the atmosphere "
                            "rather than of the spacecraft. Two objects at the same altitude "
                            "should agree on it whatever they are made of."
                        ),
                    },
                    margin=(
                        f"A factor of {ratio:.1f} against a shell median taken over "
                        f"{len(values)} intervals between {band[0]:.0f} and {band[1]:.0f} km "
                        f"of perigee altitude, and {spread_sigma:.1f} robust deviations "
                        "outside that shell's own spread of the same quantity."
                    ),
                    window=(interval.start_ms, interval.end_ms),
                    reproduce=_reproduce(
                        "python3 -m pipeline.discovery --sweep --only decay-rate-out-of-family",
                        noradId=interval.norad,
                        startAt=_iso(interval.start_ms),
                        endAt=_iso(interval.end_ms),
                        shellPerigeeAltitudeKm=list(band),
                    ),
                    alternatives=[
                        "B* is a fitted drag term, not a measured ballistic coefficient, and a "
                        "poorly conditioned fit produces a wrong ratio with no physical cause.",
                        "An object that manoeuvred during the interval has a change in "
                        "semi-major axis that drag did not cause.",
                        "An eccentric orbit samples a wide range of altitudes, so binning on "
                        "perigee places it in a shell it only visits briefly.",
                        "A tumbling or fragmenting object genuinely changes its own effective "
                        "area, so its ballistic coefficient is not the one that was fitted.",
                    ],
                )
            )

    deferrals: list[Deferral] = []
    if not candidates:
        # The funnel, not just the verdict. "Nothing found" and "nothing was
        # eligible to be found" look identical from the outside, and only the
        # counts tell a reviewer which one happened.
        passive = [i for i in intervals if i.object_type in PASSIVE_TYPES]
        with_bstar = [
            i
            for i in passive
            if i.bstar is not None
            and i.bstar > MINIMUM_USABLE_BSTAR
            and TERMINAL_DECAY_PERIGEE_KM <= i.perigee_altitude_km <= DECAY_ALTITUDE_CEILING_KM
        ]
        averaged = [
            i
            for i in with_bstar
            if i.span_days * i.mean_motion_rev_per_day >= ORBIT_AVERAGING_MINIMUM
        ]
        deferrals.append(
            Deferral(
                candidate_class="decay-rate-out-of-family",
                needs=(
                    f"element-set intervals long enough that the change in semi-major axis "
                    f"exceeds {RESOLVABLE_DECAY_KAPPA:g} times the measured fit scatter for its "
                    f"altitude band, with at least {min_cohort} of them inside one "
                    f"{shell_km:g} km perigee shell"
                ),
                why=(
                    "At the altitudes where the passive population lives, decay is metres per "
                    "day and the measured fit scatter is a fraction of a metre. Over the hours "
                    "this archive currently spans, most objects have not moved far enough for a "
                    "RATIO of two decay rates to mean anything — dividing one noise sample by "
                    "another produces a spectacular number and no physics. This resolves itself "
                    "with elapsed time and needs no new data source."
                ),
                have={
                    "intervals": len(intervals),
                    "passiveIntervals": len(passive),
                    "withUsableBstarAndAltitude": len(with_bstar),
                    "orbitAveraged": len(averaged),
                    "resolvableAgainstFitScatter": len(usable),
                    "shellsExamined": len(shells),
                    "shellsBelowCohortMinimum": thin,
                },
            )
        )
    return candidates, deferrals


# ---------------------------------------------------------------------------
# The sweep
# ---------------------------------------------------------------------------
def _kp_max(connection: sqlite3.Connection, start_ms: int, end_ms: int) -> float | None:
    try:
        row = connection.execute(
            "SELECT MAX(value) FROM geomagnetic WHERE index_name='kp' AND observed_ms BETWEEN ? AND ?",
            (start_ms, end_ms),
        ).fetchone()
    except sqlite3.Error:
        return None
    return None if row is None or row[0] is None else float(row[0])


ARCHIVE_NAME = "orbit-history.sqlite3"


def open_archive_readonly(path: Path | None = None) -> sqlite3.Connection:
    """Open the archive in a mode that cannot take a write lock.

    ``orbit_history.open_archive()`` opens read-write and runs the schema
    script, which takes a write lock on a database that other processes are
    writing to. The detection stage writes nothing, so holding a lock on it is
    pure downside — and it is not hypothetical: while this module was being
    built, the 2004-2025 bulk backfill running in another process failed with
    ``sqlite3.OperationalError: database is locked`` against exactly this
    contention. A reader that can stall a writer is a bug in the reader.

    ``mode=ro`` rather than ``immutable=1`` deliberately. ``immutable`` tells
    SQLite the file will not change, which is false while a backfill is
    importing and would let this process read a torn page and report the
    numbers from it with a straight face.
    """
    target = path if path is not None else archive_db_path()
    return sqlite3.connect(f"file:{target}?mode=ro", uri=True, timeout=60.0)


def archive_bounds(connection: sqlite3.Connection) -> tuple[int, int]:
    """Earliest and latest element epoch held, in milliseconds."""
    row = connection.execute("SELECT MIN(epoch_ms), MAX(epoch_ms) FROM element_set").fetchone()
    if not row or row[0] is None:
        return 0, 0
    return int(row[0]), int(row[1])


def sweep(
    connection: sqlite3.Connection,
    *,
    data_root: Path,
    only: str | None = None,
    now: dt.datetime | None = None,
    since_ms: int | None = None,
    until_ms: int | None = None,
    window_days: float | None = DEFAULT_WINDOW_DAYS,
) -> Sweep:
    """One detection pass over a bounded window. Pure with respect to the outside world.

    Reads the archive and the published catalog. Writes nothing, publishes
    nothing, and calls no model. The caller decides what to do with the result;
    the only sanctioned destination is the review queue.

    **The window is not optional, and this is a correctness property rather
    than a performance one.** The archive was hours deep when this module was
    written and is years deep now, because the 2004-2025 bulk backfill landed.
    An unbounded sweep materialises every consecutive element-set pair in the
    whole archive as a Python object before it tests any of them, which on the
    current archive does not finish. Worse, it would silently mix a 2009
    interval into a cohort screen against 2026 intervals — the screen's entire
    validity rests on the cohort being measured *over the same hours*, so an
    unbounded sweep does not merely run slowly, it produces a wrong control.

    So: ``window_days`` ending at the newest epoch held, by default. Pass
    ``since_ms``/``until_ms`` to sweep a specific historical episode instead —
    which is the interesting case now that the backfill exists, because the
    archive finally contains storms rather than a quiet afternoon.
    """
    reference = now or dt.datetime.now(dt.timezone.utc)
    catalog = load_catalog(data_root)
    catalog_records = _catalog_records(data_root)
    expectations = Expectations.load()

    # Which detectors actually need which inputs. Reading the archive is by far
    # the most expensive thing here — a windowed scan of a fifteen-year archive
    # on a v9fs mount is minutes — so `--only orbit-contradicts-catalog` must
    # not pay for it, and `--only correlated-shell-decay` must not pay for the
    # event pass on top.
    needs_intervals = only not in ("orbit-contradicts-catalog",) and not (
        only == "correlated-shell-decay" and since_ms and until_ms
    )
    needs_events = only is None or only in (
        "manoeuvre-out-of-family",
        "delta-v-out-of-budget",
    )

    earliest, latest = archive_bounds(connection) if needs_intervals else (0, 0)
    if needs_intervals and since_ms is None and until_ms is None and window_days:
        until_ms = latest
        since_ms = max(earliest, latest - int(window_days * 86_400_000))
    intervals = (
        load_intervals(connection, since_ms=since_ms, until_ms=until_ms)
        if needs_intervals
        else []
    )
    events = (
        detect_events(intervals, expectations=expectations, catalog=catalog)
        if needs_events
        else []
    )

    window = (
        min((interval.start_ms for interval in intervals), default=0),
        max((interval.end_ms for interval in intervals), default=0),
    )
    kp = _kp_max(connection, window[0], window[1]) if window[1] else None

    candidates: list[Candidate] = []
    deferrals: list[Deferral] = []

    def run(name: str, produced: tuple[list[Candidate], list[Deferral]]) -> None:
        if only and only != name:
            return
        candidates.extend(produced[0])
        deferrals.extend(produced[1])

    run(
        "manoeuvre-out-of-family",
        detect_manoeuvre_out_of_family(events, intervals, catalog),
    )
    run(
        "orbit-contradicts-catalog",
        detect_orbit_contradicts_catalog(catalog_records),
    )
    run(
        "delta-v-out-of-budget",
        detect_delta_v_out_of_budget(events, catalog, expectations),
    )
    run(
        "decay-rate-out-of-family",
        detect_decay_rate_out_of_family(intervals, catalog, kp_max=kp),
    )
    if not only or only == "correlated-shell-decay":
        # An explicit --since/--until is the whole point of a historical sweep:
        # "compare this storm week against the quiet weeks before it". Deriving
        # the split from the intervals that happened to load would silently
        # move the boundary somewhere else, so an explicit request wins.
        shell_window = (
            (since_ms, until_ms) if since_ms and until_ms else window
        )
        midpoint = shell_window[0] + (shell_window[1] - shell_window[0]) // 2
        shell_candidates, shell_deferrals = detect_correlated_shell_decay(
            connection,
            baseline=(shell_window[0], midpoint),
            comparison=(midpoint, shell_window[1]),
        )
        candidates.extend(shell_candidates)
        deferrals.extend(shell_deferrals)

    denied = sum(
        1
        for record in catalog_records
        if not eligible(record, record.get("name"))
    )
    false_alarms = [
        {
            "noradId": event.norad,
            "name": event.name,
            "objectType": event.object_type,
            "signature": event.signature,
            "confidence": event.confidence,
            "deltaVMetresPerSecond": _round(event.delta_v.total, 4),
            "startAt": _iso(event.start_ms),
            "endAt": _iso(event.end_ms),
            "why": event.expectation.get("reason"),
        }
        for event in events
        if event.expectation.get("verdict") == FALSE_ALARM_VERDICT
        and event.signature not in NON_PROPULSIVE_SIGNATURES
    ]
    return Sweep(
        generated_at=reference.isoformat(timespec="seconds").replace("+00:00", "Z"),
        detector_version=DETECTOR_VERSION,
        candidates=sorted(
            candidates,
            key=lambda candidate: (candidate.candidate_class, candidate.subject.key),
        ),
        deferrals=deferrals,
        inputs={
            "archive": str(archive_root()),
            "dataRoot": str(data_root),
            "archiveEarliestEpoch": _iso(earliest) if earliest else None,
            "archiveLatestEpoch": _iso(latest) if latest else None,
            "sweptFrom": _iso(since_ms) if since_ms else None,
            "sweptTo": _iso(until_ms) if until_ms else None,
            "windowDays": (
                round((until_ms - since_ms) / 86_400_000.0, 3)
                if since_ms and until_ms
                else None
            ),
            "coverageNote": (
                "One sweep looks at a bounded window ending at the newest epoch held. The "
                "cohort screen compares an object against the population measured over the "
                "same interval, so mixing epochs years apart would produce a control that "
                "was not there at the time. Sweep a historical episode explicitly with "
                "--since/--until rather than widening this."
            ),
            "intervals": len(intervals),
            "events": len(events),
            "catalogObjects": len(catalog_records),
            "expectationsVersion": expectations.version,
            "kpMaxOverWindow": kp,
            "windowFrom": _iso(window[0]) if window[1] else None,
            "windowTo": _iso(window[1]) if window[1] else None,
        },
        # `archive_maturity` counts whole tables, which is minutes on a
        # fifteen-year archive. A catalog-only sweep has no archive claim to
        # qualify, so it does not pay for one.
        maturity=(
            archive_maturity(connection, intervals)
            if needs_intervals
            else {"note": "not computed: this sweep read the catalog only, not the archive"}
        ),
        eligibility={
            "gate": "pipeline.orbit_events.opacity_denied",
            "policy": "docs/mission-speculation-design.md Sections 1.3 to 1.5",
            "catalogObjectsDenied": denied,
            "note": (
                "Denied objects produce no candidate of any kind and no marker of their "
                "absence. The count is published here, in an operator-only artifact that never "
                "reaches a visitor, because an operator needs to know the gate is running. It "
                "must not be rendered on any public surface: a visible redaction total is an "
                "assessment by implication."
            ),
        },
        false_alarms=false_alarms,
    )


def _catalog_records(data_root: Path) -> list[dict[str, Any]]:
    """Full catalog records, for the fields ``load_catalog()`` deliberately drops."""
    try:
        manifest = json.loads((data_root / "manifest.json").read_text())
        catalog = json.loads((data_root / manifest["catalog"]["path"]).read_text())
    except (OSError, KeyError, json.JSONDecodeError):
        return []
    records = catalog.get("satellites", [])
    return records if isinstance(records, list) else []


def _parse_day(value: str | None) -> int | None:
    if not value:
        return None
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return int(parsed.timestamp() * 1000)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministic anomaly sweep. Writes nothing.")
    parser.add_argument("--archive", type=Path, default=None)
    parser.add_argument("--data-root", type=Path, default=ROOT / "public" / "data")
    parser.add_argument("--sweep", action="store_true", help="run the sweep and print it")
    parser.add_argument(
        "--only",
        choices=sorted(CANDIDATE_CLASSES),
        default=None,
        help="run a single detector class",
    )
    parser.add_argument(
        "--window-days",
        type=float,
        default=DEFAULT_WINDOW_DAYS,
        help="how far back from the newest epoch held to sweep (default %(default)s)",
    )
    parser.add_argument("--since", default=None, help="sweep a historical episode: ISO start")
    parser.add_argument("--until", default=None, help="sweep a historical episode: ISO end")
    parser.add_argument("--bounds", action="store_true", help="print what the archive holds and stop")
    args = parser.parse_args(argv)

    connection = open_archive_readonly(args.archive)
    if args.bounds:
        earliest, latest = archive_bounds(connection)
        print(json.dumps({"earliest": _iso(earliest), "latest": _iso(latest)}, indent=2))
        return 0

    result = sweep(
        connection,
        data_root=args.data_root,
        only=args.only,
        since_ms=_parse_day(args.since),
        until_ms=_parse_day(args.until),
        window_days=args.window_days,
    )
    print(json.dumps(result.as_dict(), indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
