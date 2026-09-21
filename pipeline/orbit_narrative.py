#!/usr/bin/env python3
"""Prose for an orbit event: a complete deterministic version, and a gate for the model's.

The project's standing rule is that **the language model decorates and never
gates**. `pipeline/teaching_brief.py` established how that is enforced for the
space-weather brief, and this module applies the same contract to orbit events,
with three additions the orbit case needs.

**1. The deterministic version is the product, not the fallback.**
`describe()` writes a complete, publishable evidence card from the computed
numbers alone. It is what ships when the model is unreachable — which the
endpoint on bigmem often is — and a visitor cannot tell the difference except
by reading the honesty label. If the deterministic version were merely a stub,
the model would in practice be gating the feature, whatever the documentation
said.

**2. The model may only phrase a cause that code already put on the list.**
`candidate_causes()` returns a closed set of cause identifiers computed from the
elements, the object's class and the archived Kp. `validate_candidate()` rejects
any output that asserts a cause outside it. The model's entire job is to choose
among computed possibilities and write them in readable English — it may not
add one.

**3. The bright line from `docs/mission-speculation-design.md` is enforced here
in code, not in the prompt.**
"New tasking" as a *category of manoeuvre* is physics and is permitted for any
object. Asserting what a specific spacecraft was retasked *to do* is not, and
for an object that fails the opacity gate no purpose language is permitted at
all. A prompt is a request; `_asserts_a_mission()` is a rejection.

Numbers
-------
The model writes no digits and no spelled-out quantities, exactly as in
`teaching_brief.py`. This is more important here, not less: every figure on an
orbit card — the Delta-v, the residual, the drag share, the sigma — is computed,
and a model that restates one has introduced a second, unverified copy of a
number the visitor is being asked to trust.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from typing import Any, Sequence

MAX_NARRATIVE_AGE_MINUTES = 7 * 24 * 60
"""An orbit event does not change once it is in the past, unlike the weather.

The staleness bound is a week rather than three hours, and it exists to catch a
narrative written against an evidence sheet that has since been recomputed --
after a cohort screen was added, say, or the false-alarm rate moved -- not to
catch conditions drifting.
"""

_NUMBER_WORDS = frozenset(
    """two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen
    sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety
    hundred thousand million billion dozen""".split()
)

# Hedges. At least one must be present: an inference from public elements is
# never a statement of fact about what an operator did, and the difference has
# to be visible in the sentence rather than only in a label beside it.
_HEDGES = (
    "consistent with",
    "the evidence",
    "we infer",
    "appears",
    "suggests",
    "would be",
    "could be",
    "may ",
    "might ",
    "likely",
    "probably",
    "cannot be distinguished",
    "one explanation",
    "typical of",
    "characteristic of",
)

# Words that turn an inference into a claim. "Confirmed" is banned outright by
# `docs/orbit-history-design.md` Section 4.3; the rest are the ways a model
# reaches the same place without the word.
_FORBIDDEN = (
    "confirmed",
    "confirms",
    "definitely",
    "certainly",
    "undoubtedly",
    "proves",
    "proven",
    "we know that",
    "in fact",
    "clearly shows",
    "must have",
    "was ordered",
    "was commanded",
    "operators decided",
    "ground control",
    "will re-enter",
    "will reenter",
    "is expected to re-enter",
    "predicted to re-enter",
)

# Mission assertions. The grammatical test in the design document -- does the
# sentence have a specific spacecraft as its subject and a mission as its
# predicate -- is not mechanically checkable, so this is the conservative
# proxy: the vocabulary of mission assessment does not appear at all.
_MISSION_TERMS = (
    "spy",
    "espionage",
    "reconnaissance",
    "surveillance",
    "intelligence",
    "signals intelligence",
    "sigint",
    "elint",
    "imint",
    "early warning",
    "missile warning",
    "inspector",
    "inspection satellite",
    "rendezvous",
    "proximity operations",
    "co-orbital",
    "shadowing",
    "stalking",
    "target",
    "targeting",
    "adversary",
    "military mission",
    "classified mission",
    "secret",
    "covert",
    "eavesdrop",
    "intercept",
)

# Relational language. `docs/mission-speculation-design.md` Section 1.6 excludes
# object-to-object association structurally -- no such evidence is ever computed
# -- so a model cannot be repeating an input when it uses these. It would be
# inventing one.
_RELATIONAL_TERMS = (
    "another satellite",
    "other satellite",
    "nearby satellite",
    "companion",
    "in tandem",
    "working with",
    "alongside another",
    "same plane as",
    "co-planar with",
    "close approach to",
    "approaching the",
    "trailing the",
    "following the",
    "paired with",
    "escort",
)


# ---------------------------------------------------------------------------
# Candidate causes: computed, closed, and the model's whole permitted vocabulary
# ---------------------------------------------------------------------------
CAUSE_VOCABULARY: dict[str, dict[str, str]] = {
    "drag-make-up": {
        "label": "making up altitude lost to atmospheric drag",
        "detail": (
            "Every object in low Earth orbit is slowly falling. An operator who wants to stay "
            "at a chosen altitude has to put back what the atmosphere takes out, and the higher "
            "the air density the more often that has to happen."
        ),
    },
    "storm-driven-drag": {
        "label": "making up altitude lost during a period of raised geomagnetic activity",
        "detail": (
            "Geomagnetic activity heats the thermosphere, which expands, which raises the density "
            "at a fixed altitude. Objects then decay faster, all of them at once, and operators "
            "who hold an altitude have to burn more often to keep it."
        ),
    },
    "constellation-slot-maintenance": {
        "label": "holding a position within a constellation's own geometry",
        "detail": (
            "A large constellation assigns each spacecraft an altitude and a phase, and small "
            "in-plane corrections are how a spacecraft is kept in the slot it was given. This is "
            "a statement about the published design of the constellation, not about which "
            "spacecraft is near which."
        ),
    },
    "orbit-raising-campaign": {
        "label": "climbing towards an operational altitude",
        "detail": (
            "A newly launched spacecraft is usually delivered below where it will work and climbs "
            "the rest of the way itself. With electric propulsion the climb takes weeks or months "
            "and appears as a steady trend rather than a step."
        ),
    },
    "orbit-lowering-campaign": {
        "label": "descending under propulsion",
        "detail": (
            "A sustained, deliberate descent. At end of life an operator may lower the orbit to "
            "shorten how long the object remains in orbit, rather than leaving it to decay on its "
            "own over decades."
        ),
    },
    "disposal": {
        "label": "moving out of a useful orbit at end of life",
        "detail": (
            "Disposal guidelines ask operators to clear the orbits other spacecraft use, either by "
            "lowering into the atmosphere or, at geostationary altitude, by raising above the ring."
        ),
    },
    "geo-longitude-control": {
        "label": "holding an assigned geostationary longitude",
        "detail": (
            "The Earth's equator is slightly elliptical, so a geostationary satellite drifts "
            "towards one of two stable longitudes unless it is corrected. Holding a slot means "
            "small tangential burns every few weeks."
        ),
    },
    "geo-inclination-control": {
        "label": "holding the orbit plane near the equator",
        "detail": (
            "Solar and lunar gravity tip a geostationary orbit's plane away from the equator by "
            "roughly three quarters of a degree a year. Correcting it is a plane change, which is "
            "why it dominates a geostationary satellite's propellant budget."
        ),
    },
    "sun-synchronous-maintenance": {
        "label": "holding the local solar time of the orbit",
        "detail": (
            "A sun-synchronous orbit's whole value is that every pass happens at the same local "
            "solar time, which requires a particular relationship between altitude and "
            "inclination. Holding it means correcting both."
        ),
    },
    "collision-avoidance": {
        "label": "a collision-avoidance manoeuvre",
        "detail": (
            "Operators are notified of close approaches and routinely move out of the way. These "
            "manoeuvres are small, unscheduled, and usually reversed a day or two later. This site "
            "does not identify what an object might have been avoiding, and cannot."
        ),
    },
    "mission-change": {
        "label": "a change in the orbit the operator wants the spacecraft to be in",
        "detail": (
            "Some manoeuvres are not maintenance. A change of inclination in particular costs so "
            "much more per unit than any in-plane correction that it is not something an operator "
            "does to keep a spacecraft where it already was. What the new orbit is FOR is not "
            "something orbital elements can answer, and this site does not guess."
        ),
    },
    "fit-artefact": {
        "label": "an artefact of how the orbit was fitted rather than a real change",
        "detail": (
            "These are fitted mean elements published every few hours, not measurements of where "
            "the spacecraft is. A gap in tracking, a change in the fitting process, or a mix-up "
            "between two objects in similar orbits can all move the published elements without "
            "anything moving in orbit."
        ),
    },
}

# Which causes each signature may offer. Closed, and read by both the
# deterministic writer and the validator, so the two can never disagree about
# what was on the table.
_SIGNATURE_CAUSES: dict[str, tuple[str, ...]] = {
    "along-track-raise": (
        "drag-make-up",
        "constellation-slot-maintenance",
        "orbit-raising-campaign",
        "collision-avoidance",
        "fit-artefact",
    ),
    "drag-make-up": ("drag-make-up", "constellation-slot-maintenance", "fit-artefact"),
    "along-track-lower": (
        "orbit-lowering-campaign",
        "constellation-slot-maintenance",
        "collision-avoidance",
        "disposal",
        "fit-artefact",
    ),
    "deorbit-lowering": ("disposal", "orbit-lowering-campaign", "fit-artefact"),
    "orbit-raising": ("orbit-raising-campaign", "fit-artefact"),
    "orbit-lowering": ("orbit-lowering-campaign", "disposal", "fit-artefact"),
    "inclination-change": ("mission-change", "sun-synchronous-maintenance", "fit-artefact"),
    "geo-east-west-keeping": ("geo-longitude-control", "collision-avoidance", "fit-artefact"),
    "geo-north-south-keeping": ("geo-inclination-control", "fit-artefact"),
    "geo-graveyard-raise": ("disposal", "fit-artefact"),
    "drag-decay": (),
    "re-entry-decay": (),
    "drag-and-thrust-not-separable": ("fit-artefact",),
    "unclassified-change": ("fit-artefact",),
}


def candidate_causes(event: dict[str, Any]) -> list[str]:
    """The closed list of causes this event is permitted to be attributed to.

    Deterministic, and computed from the event record alone. Conditions are
    applied so that a cause which cannot apply is not offered: sun-synchronous
    maintenance is only on the list for an orbit that is actually
    sun-synchronous, and a storm explanation is only on the list when the
    archive actually recorded raised geomagnetic activity over the interval.
    """
    causes = list(_SIGNATURE_CAUSES.get(event.get("signature", ""), ("fit-artefact",)))

    if "sun-synchronous-maintenance" in causes and not event.get("sunSynchronous"):
        causes.remove("sun-synchronous-maintenance")

    if "constellation-slot-maintenance" in causes and not event.get("constellation"):
        causes.remove("constellation-slot-maintenance")

    kp = (event.get("spaceWeather") or {}).get("kpMax")
    regime = event.get("regime")
    if (
        "drag-make-up" in causes
        and regime == "LEO"
        and isinstance(kp, (int, float))
        and kp >= 4.0
    ):
        causes.insert(causes.index("drag-make-up"), "storm-driven-drag")

    # An event on an object that cannot manoeuvre has exactly one honest
    # explanation, and it is not a manoeuvre.
    if (event.get("expectation") or {}).get("verdict") == "impossible-for-class":
        return ["fit-artefact"]
    return causes


# ---------------------------------------------------------------------------
# The deterministic card
# ---------------------------------------------------------------------------
def describe(event: dict[str, Any], controls: dict[str, Any]) -> dict[str, Any]:
    """A complete, publishable evidence card, written from the numbers alone.

    This is what a visitor sees when the model is unreachable, and it has to be
    good enough that they are not being short-changed. It follows the wording
    rules in `docs/orbit-history-design.md` Section 4.3 exactly: every inference
    carries its evidence, its noise floor, its control, at least one alternative
    explanation, and the measured false-alarm position; the word "confirmed"
    never appears; and no operator is named as having done anything.
    """
    signature = event.get("signature", "unclassified-change")
    label = event.get("signatureLabel", signature)
    delta_v = (event.get("deltaV") or {}).get("totalMetresPerSecond")
    drag = event.get("drag") or {}
    tests = [t for t in (event.get("tests") or []) if t.get("tripped")]
    causes = candidate_causes(event)

    observation = _observation_sentence(event, tests, drag)
    cost = _cost_sentence(event, delta_v)
    control = _control_sentence(event, tests)
    alternatives = _alternatives_sentence(causes, event)
    honesty = _honesty_sentence(controls, event)

    return {
        "kind": "deterministic",
        "headline": _headline(event, label),
        "observation": observation,
        "cost": cost,
        "control": control,
        "candidateCauses": [
            {"id": cause, **CAUSE_VOCABULARY[cause]} for cause in causes
        ],
        "alternatives": alternatives,
        "honesty": honesty,
        "footer": (
            "We infer this from public orbital elements. We are not told what any operator did, "
            "and this site never claims to be. These are fitted mean elements published every few "
            "hours, not measurements of where the spacecraft is; what we can see is how the fit "
            "moved."
        ),
    }


def _headline(event: dict[str, Any], label: str) -> str:
    if event.get("signature") in ("drag-decay", "re-entry-decay"):
        return f"{label.capitalize()} — no propulsion needed to explain this"
    if event.get("signature") == "drag-and-thrust-not-separable":
        return "Orbit lost energy — cause not separable"
    return f"{label.capitalize()} — inferred, not confirmed"


def _observation_sentence(event: dict[str, Any], tests: Sequence[dict], drag: dict) -> str:
    parts: list[str] = []
    for test in tests:
        element = test.get("element")
        delta = test.get("delta")
        sigma = test.get("floorSigma")
        if element == "semiMajorAxis":
            parts.append(
                f"the semi-major axis moved {_metres(delta)} beyond what could happen on its own, "
                f"against a floor of {_metres(sigma, signed=False)}"
            )
        elif element == "inclination":
            parts.append(
                f"the inclination moved {_degrees(delta)}, against a floor of {_degrees(sigma, signed=False)}"
            )
        elif element == "eccentricity":
            parts.append(f"the eccentricity moved {delta:.2e}")
    if not parts:
        return (
            "Nothing in this interval cleared the bar that separates a real change from the "
            "catalogue's own fit noise."
        )
    sentence = "Between the two element sets, " + "; and ".join(parts) + "."
    if drag.get("applicable"):
        sentence += (
            f" Atmospheric drag on a body of this ballistic coefficient accounts for "
            f"{_metres(drag.get('predictedDeltaAMetres'))} of the change in semi-major axis, "
            f"give or take {_metres(drag.get('predictedSigmaMetres'), signed=False)}; that has been subtracted "
            "before anything below is claimed."
        )
    else:
        reason = drag.get("reason")
        if reason == "cohort-too-small":
            sentence += (
                " There were not enough comparable objects at this altitude over these hours to "
                "predict how much of the change drag accounts for."
            )
        elif reason == "above-drag-regime":
            sentence += " At this altitude atmospheric drag is not a meaningful part of the story."
    return sentence


def _cost_sentence(event: dict[str, Any], delta_v: float | None) -> str:
    if not isinstance(delta_v, (int, float)) or delta_v <= 0:
        return ""
    components = event.get("deltaV") or {}
    plane = components.get("planeChangeMetresPerSecond") or 0.0
    sentence = (
        f"If a propulsion system produced this, the cheapest way to do it costs at least "
        f"{_speed(delta_v)}. That is a lower bound: a burn in any other direction, or at any "
        "other point in the orbit, costs more."
    )
    if plane > 0 and plane >= 0.5 * float(delta_v):
        sentence += (
            " Most of that is the plane change, and plane changes are the expensive kind. At this "
            "altitude, rotating the orbit by one degree costs roughly two hundred and forty times "
            "as much as raising it by one kilometre — which is why an inclination change is "
            "evidence of a decision rather than of maintenance."
        )
    return sentence


def _control_sentence(event: dict[str, Any], tests: Sequence[dict]) -> str:
    screened = [t for t in tests if t.get("cohortZ") is not None]
    if not screened:
        return (
            "There were not enough objects at the same altitude and inclination over the same "
            "hours to check whether the whole neighbourhood moved together. Without that check, "
            "this measurement cannot be separated from something that acted on every object in the "
            "shell at once — a geomagnetic storm, or a change in how the catalogue itself is "
            "fitted."
        )
    best = max(screened, key=lambda t: abs(t.get("cohortZ") or 0.0))
    count = best.get("cohortCount") or 0
    return (
        f"Compared against {count} other objects within twenty-five kilometres of the same altitude "
        "and two degrees of the same inclination over the same hours, this object stands out by "
        f"about {abs(best.get('cohortZ') or 0):.0f} times the spread of that group. Drag and "
        "geomagnetic heating act on a whole shell at once; whatever this was did not."
        + (
            ""
            if best.get("cohortScreened")
            else " That group is small enough that its own spread is poorly determined, so treat "
            "the comparison as indicative rather than settled."
        )
    )


def _alternatives_sentence(causes: Sequence[str], event: dict[str, Any]) -> str:
    if not causes:
        return ""
    alternatives = [CAUSE_VOCABULARY[c]["label"] for c in causes if c != "fit-artefact"]
    text = ""
    if alternatives:
        text = "What could produce this signature: " + "; ".join(alternatives) + ". "
    return text + (
        "It could also be an artefact of the fit rather than a real change — a re-fit after a "
        "gap in tracking, or a correlation error between two objects in similar orbits."
    )


# Which detector judged this event, in the reader's words rather than the
# pipeline's. `controlBasis` is set on every published record, and every
# false-alarm figure quoted in the sentence below belongs to ONE of these two
# instruments -- they have separate blanks, separate kappas and separate
# verdicts. A card that quotes a rate without saying whose it is asks the
# reader to trust a number whose provenance has been withheld, which is the
# opposite of what this card is for.
CONTROL_BASIS_PROSE: dict[str, str] = {
    "self-history": "the detector that judges each object against its own past",
    "cohort": (
        "the detector that judges each object against its neighbours at the same "
        "altitude and inclination"
    ),
}


def _detector_phrase(event: dict[str, Any]) -> str:
    """Name the instrument, or say plainly that the record does not name it."""
    described = CONTROL_BASIS_PROSE.get(event.get("controlBasis"))
    if described is None:
        return "the detector that judged this event"
    stratum = event.get("controlStratum")
    if isinstance(stratum, dict):
        return (f"{described}, using the {stratum['era']} / {stratum['band']} km "
                "perigee control — the one that judged this event —")
    return f"{described} — the one that found this event —"


def _honesty_sentence(controls: dict[str, Any], event: dict[str, Any]) -> str:
    passive = (controls or {}).get("passiveControl") or {}
    flags = passive.get("flags")
    intervals = passive.get("intervals")
    significance = (controls or {}).get("excessSignificance") or {}
    if not intervals:
        return (
            "This is a candidate. The false-alarm rate for this detector has not been measured "
            "yet, so no stronger word is available and none is used."
        )
    bound = (passive.get("interval95") or [None, None])[1]
    permitted = bool(
        event.get(
            "manoeuvreLabelPermitted",
            (controls or {}).get("sufficientToLabel", False),
        )
    )
    passive_object = (
        event.get("objectType") in ("DEBRIS", "ROCKET BODY")
        or (event.get("expectation") or {}).get("verdict") == "impossible-for-class"
    )
    sentence = (
        (
            # NOT "by construction". The physics is certain -- a fragment has no
            # engine -- but the premise is a CATALOGUE FIELD, and a catalogue
            # entry can be wrong or stale. The claim is stated at the strength
            # of its warrant; the refusal it licenses stays absolute.
            "The catalogue lists this object as debris or a spent rocket stage, a class "
            "with no propulsion, so on the strength of that classification this flag is a "
            "false alarm rather than a manoeuvre. "
            if passive_object
            else (
                "This is a manoeuvre inferred from public elements, not a confirmed cause. "
                if permitted
                else "This is a candidate. "
            )
        )
        + f"Over the same period {_detector_phrase(event)} flagged {flags} interval"
        f"{'' if flags == 1 else 's'} out of {intervals} on objects that physically cannot "
        "manoeuvre — debris and spent rocket stages — so flags like this one are wrong at least "
        f"that often"
    )
    if isinstance(bound, (int, float)):
        sentence += f", and the data cannot rule out a rate as high as {bound * 100:.3f} per cent"
    sentence += ". "
    if passive_object:
        sentence += (
            "That classification is the catalogue's, not a measurement made here: a fragment "
            "cannot burn, but an entry can be wrong or out of date, and that is the one way "
            "this could be a real change rather than a false alarm. It makes no difference to "
            "the word used — a passing population-level control can never lend the word "
            "manoeuvre to an individual flag on an object the catalogue says has no engine."
        )
    elif permitted:
        sentence += (
            "The upper bound on that false-alarm rate is below the design target, and payloads "
            "are flagged significantly more often than objects without propulsion. That earns "
            "the word manoeuvre for this detector; the cause and the Δv remain inferences."
        )
    elif isinstance(event.get("controlStratum"), dict):
        sentence += (controls.get("blockingReason") or
                     "not calibrated: the matched control has not established separation")
        sentence += ". This event remains a candidate; its Δv is a lower bound."
    elif controls.get("excessSignificant") is False:
        z = significance.get("z")
        if isinstance(z, (int, float)) and z < 0:
            sentence += (
                "The observed flag rate on payloads is lower than on objects that cannot "
                "manoeuvre, so the required positive separation is absent"
            )
        elif isinstance(z, (int, float)) and z > 0:
            sentence += (
                "The flag rate on payloads is higher than on objects that cannot manoeuvre, "
                "but with this much archive the difference is not yet statistically significant"
            )
        else:
            sentence += "Payloads have not been shown to flag more often than passive objects"
        if isinstance(z, (int, float)):
            sentence += f" (about {abs(z):.1f} standard errors)"
        sentence += (
            ". Until it is, this site shows you the measurement and declines to call it a "
            "manoeuvre."
        )
    elif controls.get("excessSignificant") is True:
        sentence += (
            "Payloads are flagged more often, but this detector's passive upper bound has not "
            "cleared the design target. Until it does, this site shows the measurement and keeps "
            "the event labelled candidate."
        )
    else:
        sentence += (
            "The payload comparison has not established the additional separation required by "
            "the label policy, so this event remains a candidate."
        )
    return sentence


def _metres(value: Any, signed: bool = True) -> str:
    """A length, in the unit that makes it readable.

    `signed` is False for a noise floor or an uncertainty, where a leading plus
    sign reads as a direction the quantity does not have.
    """
    if not isinstance(value, (int, float)):
        return "an unknown amount"
    shown = value if signed else abs(value)
    sign = "+" if signed else ""
    magnitude = abs(value)
    if magnitude >= 1000:
        return f"{shown / 1000:{sign}.3f} km"
    if magnitude >= 1:
        return f"{shown:{sign}.1f} m"
    return f"{shown * 100:{sign}.1f} cm"


def _degrees(value: Any, signed: bool = True) -> str:
    if not isinstance(value, (int, float)):
        return "an unknown amount"
    return f"{value:+.5f}°" if signed else f"{abs(value):.5f}°"


def _speed(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "an unknown amount"
    if abs(value) < 0.01:
        return f"{value * 1000:.1f} mm/s"
    if abs(value) < 1.0:
        return f"{value * 100:.1f} cm/s"
    return f"{value:.2f} m/s"


# ---------------------------------------------------------------------------
# The evidence sheet handed to the model
# ---------------------------------------------------------------------------
def evidence_sheet(event: dict[str, Any], controls: dict[str, Any]) -> dict[str, Any]:
    """Exactly what the model is allowed to see. Structured, bounded, no free rein.

    Note what is absent and why: no other object appears anywhere in it, no
    catalog is reachable from it, and for an object that failed the opacity
    gate the mission and sector fields are omitted entirely rather than sent
    with a "do not mention this" instruction. A field that is not in the prompt
    cannot be leaked by a model that ignores an instruction.
    """
    permitted = bool(event.get("purposeLanguagePermitted", False))
    sheet: dict[str, Any] = {
        "signature": event.get("signature"),
        "signatureLabel": event.get("signatureLabel"),
        "signatureExplanation": event.get("signatureExplanation"),
        "regime": event.get("regime"),
        "perigeeAltitudeKm": event.get("perigeeAltitudeKm"),
        "apogeeAltitudeKm": event.get("apogeeAltitudeKm"),
        "inclinationDeg": event.get("inclinationDeg"),
        "spanDays": event.get("spanDays"),
        "deltaV": event.get("deltaV"),
        "drag": event.get("drag"),
        "elementTests": event.get("tests"),
        "expectationVerdict": (event.get("expectation") or {}).get("verdict"),
        "expectationReason": (event.get("expectation") or {}).get("reason"),
        "concurrentKpMax": (event.get("spaceWeather") or {}).get("kpMax"),
        "candidateCauses": [
            {"id": cause, **CAUSE_VOCABULARY[cause]} for cause in candidate_causes(event)
        ],
        "falseAlarmControl": {
            # Which instrument's blank this is. The two detectors measure
            # different things and their rates are not interchangeable, so the
            # sheet says whose these numbers are rather than leaving the model
            # to assume there is only one detector.
            "basis": event.get("controlBasis"),
            "stratum": event.get("controlStratum", "not published"),
            "passiveFlags": (controls.get("passiveControl") or {}).get("flags"),
            "passiveIntervals": (controls.get("passiveControl") or {}).get("intervals"),
            "excessSignificant": controls.get("excessSignificant"),
        },
        "purposeLanguagePermitted": permitted,
    }
    if permitted:
        sheet["objectClass"] = (event.get("expectation") or {}).get("class")
        sheet["mission"] = (event.get("catalog") or {}).get("mission")
        sheet["constellation"] = event.get("constellation")
    return sheet


SYSTEM_PROMPT = (
    "You write one short paragraph explaining a change in a satellite's orbit, for readers who "
    "know orbital mechanics. Everything you need is in the evidence sheet, and you must use only "
    "it.\n"
    "RULES, all of which are checked by code after you answer:\n"
    "1. State NO quantities. No digits, and do not spell numbers out as words either. Every number "
    "is rendered separately and exactly; if you restate one you create a second copy that may not "
    "match.\n"
    "2. You may only attribute the change to a cause that appears in candidateCauses. You may say "
    "which of them you think most likely and why, given the evidence sheet. You may not add a "
    "cause of your own. Write the cause in natural English -- never paste the identifier or the "
    "label verbatim into a sentence, which produces phrasing like 'consistent with a descending "
    "under propulsion'.\n"
    "3. Hedge. This is an inference from public orbital elements, not a report of what an operator "
    "did. Use phrasing such as 'consistent with', 'the evidence suggests', 'we infer'. Never use "
    "'confirmed', 'proves', or 'certainly'.\n"
    "4. Never name or allude to any other spacecraft, and never suggest this object is operating "
    "with, near, or in relation to another. You have not been given any such information.\n"
    "5. Never state or guess what the spacecraft is for, what it observes, who operates it, or "
    "what it was tasked to do. Naming a CATEGORY of manoeuvre is fine and is physics. Naming a "
    "mission is not.\n"
    "6. Do not forecast. Never say when anything will re-enter.\n"
    "Return JSON with exactly two strings: text, between forty and seven hundred characters, and "
    "caveat, one sentence under two hundred characters describing the limits of your own reading."
)


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------
def validate_candidate(
    candidate: Any,
    event: dict[str, Any],
    now: dt.datetime | None = None,
) -> dict[str, str] | None:
    """Return a publishable narrative, or None and let the caller fall back.

    Rejection is silent and safe: `describe()` has already produced a complete
    card, so a rejected model output costs the visitor nothing except a less
    fluent paragraph. That asymmetry is the reason the rules below can be as
    strict as they are.
    """
    if not isinstance(candidate, dict):
        return None
    text = candidate.get("text")
    caveat = candidate.get("caveat")
    if not isinstance(text, str) or not isinstance(caveat, str):
        return None
    if not (40 <= len(text) <= 700) or not (20 <= len(caveat) <= 200):
        return None

    combined = f"{text}\n{caveat}"
    lowered = combined.lower()

    # The event this was written about must be the event being rendered.
    if candidate.get("eventKey") != event_key(event):
        return None

    # No numbers, in digits or in words.
    if re.search(r"\d", combined):
        return None
    if any(word in _NUMBER_WORDS for word in re.findall(r"[a-z]+", lowered)):
        return None

    if any(term in lowered for term in _FORBIDDEN):
        return None
    if any(term in lowered for term in _RELATIONAL_TERMS):
        return None
    if not any(hedge in lowered for hedge in _HEDGES):
        return None

    if _asserts_a_mission(lowered, event):
        return None
    if _asserts_an_uncomputed_cause(lowered, event):
        return None
    if _contradicts_the_numbers(lowered, event):
        return None
    if _echoes_source_prose(caveat, event):
        return None

    generated_at = _parse_time(candidate.get("generatedAt"))
    if generated_at is None:
        return None
    reference = now or dt.datetime.now(dt.timezone.utc)
    age_minutes = (reference - generated_at).total_seconds() / 60.0
    if age_minutes < -5 or age_minutes > MAX_NARRATIVE_AGE_MINUTES:
        return None

    return {
        "kind": "model-assisted",
        "text": text.strip(),
        "caveat": caveat.strip(),
        "generatedAt": candidate["generatedAt"],
    }


def event_key(event: dict[str, Any]) -> str:
    """Identity of the evidence a narrative was written about.

    Deliberately coarse: the object, the interval, and the signature. A
    narrative written about a raise must not survive that raise being
    reclassified, but it should survive the Delta-v moving in the fourth
    decimal place when the cohort gains a member. This is the same lesson as
    the fingerprint in `teaching_brief.py`, where hashing every timestamp made
    a brief invalid within one publish cycle of being written.
    """
    return "|".join(
        str(event.get(field))
        for field in ("norad", "startAt", "endAt", "signature")
    )


def _asserts_a_mission(lowered: str, event: dict[str, Any]) -> bool:
    """True when the prose says what the spacecraft is FOR.

    For an object that failed the opacity gate this is an outright ban. For
    every other object it is still a ban, because the mission of a spacecraft
    is not something an orbit change can establish -- the catalog may say it,
    and the catalog renders it separately, but this paragraph is about a
    manoeuvre.
    """
    return any(term in lowered for term in _MISSION_TERMS)


def _asserts_an_uncomputed_cause(lowered: str, event: dict[str, Any]) -> bool:
    """True when the prose reaches for a cause that was not on the computed list.

    Implemented as an exclusion rather than an inclusion: every cause in the
    closed vocabulary that was NOT offered for this event has a set of marker
    phrases, and any of them appearing is a rejection. An inclusion test -- does
    the text mention an allowed cause -- would pass prose that mentioned an
    allowed cause and then added a forbidden one.
    """
    allowed = set(candidate_causes(event))
    for cause, markers in _CAUSE_MARKERS.items():
        if cause in allowed:
            continue
        if any(marker in lowered for marker in markers):
            return True
    return False


_CAUSE_MARKERS: dict[str, tuple[str, ...]] = {
    "drag-make-up": ("drag make-up", "makes up for drag", "lost to drag", "reboost"),
    "storm-driven-drag": ("geomagnetic storm", "storm-time", "solar storm", "space weather event"),
    "constellation-slot-maintenance": ("slot", "constellation geometry", "phasing"),
    "orbit-raising-campaign": ("raising campaign", "climbing to its operational", "orbit raising"),
    "orbit-lowering-campaign": ("lowering campaign", "controlled descent"),
    "disposal": ("disposal", "graveyard", "end of life", "end-of-life", "deorbit"),
    "geo-longitude-control": ("longitude control", "east-west station", "east-west keeping"),
    "geo-inclination-control": ("north-south station", "north-south keeping", "inclination control"),
    "sun-synchronous-maintenance": ("sun-synchronous", "local solar time", "local time of"),
    "collision-avoidance": ("collision avoidance", "conjunction", "avoid a collision", "close approach"),
    "mission-change": ("new tasking", "retasked", "retasking", "mission change", "change of mission"),
    "fit-artefact": (),
}


def _contradicts_the_numbers(lowered: str, event: dict[str, Any]) -> bool:
    """True when the prose says the opposite of what was computed.

    Only directional claims are checkable without letting numbers back in, and
    those are the ones a model actually gets wrong: it reads a negative
    Delta-v and writes "raised its orbit".
    """
    delta_a = (event.get("drag") or {}).get("propulsiveDeltaAMetres")
    if isinstance(delta_a, (int, float)) and delta_a != 0:
        rose = delta_a > 0
        claims_rise = any(
            phrase in lowered
            for phrase in ("raised", "raising", "higher orbit", "boosted", "climbed", "ascend")
        )
        claims_fall = any(
            phrase in lowered
            for phrase in ("lowered", "lowering", "lower orbit", "descended", "dropped", "fell")
        )
        if rose and claims_fall and not claims_rise:
            return True
        if not rose and claims_rise and not claims_fall:
            return True

    if event.get("signature") in ("drag-decay", "re-entry-decay"):
        if any(word in lowered for word in ("burn", "thruster", "manoeuvre", "maneuver", "propulsion")):
            # These signatures assert explicitly that no propulsion is needed.
            if "no " not in lowered and "not " not in lowered and "without" not in lowered:
                return True
    return False


def _echoes_source_prose(caveat: str, event: dict[str, Any]) -> bool:
    """True when the caveat is lifted from prose supplied in the evidence sheet.

    The same failure `teaching_brief.py` observed live: asked for a caveat about
    its own reading, a model returns a caveat that was in its input, which is a
    true sentence about something else. Here the input carries a `detail` string
    for every candidate cause and an `expectationReason`, and any of them could
    be echoed.
    """
    normalised = " ".join(caveat.lower().split())
    sources: list[str] = []
    expectation = event.get("expectation") or {}
    if isinstance(expectation.get("reason"), str):
        sources.append(expectation["reason"])
    for cause in candidate_causes(event):
        sources.append(CAUSE_VOCABULARY[cause]["detail"])
        sources.append(CAUSE_VOCABULARY[cause]["label"])
    explanation = event.get("signatureExplanation")
    if isinstance(explanation, str):
        sources.append(explanation)
    for source in sources:
        if len(source) < 40:
            continue
        flattened = " ".join(source.lower().split())
        if flattened in normalised or normalised in flattened:
            return True
    return False


def _parse_time(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


def load_candidates(path) -> dict[str, Any]:
    """Cached narratives keyed by `event_key`, or an empty mapping."""
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}
