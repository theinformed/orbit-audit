#!/usr/bin/env python3
"""Generate the Orbit changes section's string table from the frozen model.

The section has no vocabulary of its own. Every word it can put on a screen is
written here, or is copied out of the frozen detector bundle
(`docs/alarm-lane-model-20260922.json`), and `src/orbit-changes-strings.ts` is
the only file in the section allowed to hold one. The rendering code reads the
table; it never writes a sentence.

Three things are generated rather than typed, because typing them is how a
published figure stops naming the model that earned it:

* the withheld-term list, each term tied to the clause of the frozen bundle
  that licenses withholding it (this file refuses to run if a licensing clause
  is no longer in the bundle);
* the two structural caveats and the framing block, copied byte for byte out of
  the bundle and out of the section design, and checked against them here;
* every figure in the precision block -- support, positives, precision, its
  interval, the base rate, the lead distribution -- arithmetic on the bundle's
  own numbers and on nothing else.

Run: `python3 -m tools.orbit_changes_strings` (writes the module), or with
`--check` to fail when the committed module is not what this file produces.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "docs" / "alarm-lane-model-20260922.json"
DESIGN_PATH = ROOT / "docs" / "orbits-section-design-20260922.md"
OUTPUT_PATH = ROOT / "src" / "orbit-changes-strings.ts"
# The low-orbit arm's numbers have no entry in the frozen bundle, because the
# bundle is the belt detector's. They come from that study's own frozen record
# and its results, and are read here rather than typed, for the same reason.
LEO_EVENTS_PATH = ROOT / "docs" / "proximity-leo-events-20260922.jsonl"
LEO_RESULTS_PATH = ROOT / "docs" / "proximity-leo-results-20260922.md"
# The operating-point curve, the low-orbit arm's frozen model and the two
# replay receipts. The dial's finding, the low-orbit gap and the exercise
# label are all MEASURED sentences, so they are read from the artifacts that
# measured them rather than typed here.
CURVE_PATH = ROOT / "docs" / "alarm-lane-operating-points-20260922.json"
LEO_MODEL_PATH = ROOT / "docs" / "alarm-lane-leo-model-20260922.json"
REPLAY_RECEIPT_PATH = ROOT / "docs" / "alarm-lane-replay-20260922-receipt.json"
LEO_RECEIPT_PATH = ROOT / "docs" / "alarm-lane-leo-replay-20260922-receipt.json"

# The class the belt lane speaks. Everything the dial prints is that class's
# row of the curve; the other class is withheld at every setting the gate
# refuses it, and the curve carries the refusal's reason with it.
SPOKEN_CLASS = "WIDE-CROSSING"

# ---------------------------------------------------------------------------
# The withheld terms, and what licenses each one.
#
# The left column is the term the section may not print. The right column is a
# fragment that must still be present in the frozen bundle's `neverSay` list or
# in the section design, so that a term cannot outlive its reason: change the
# bundle and this generator stops, rather than shipping a rule nothing backs.
#
# Two deliberate omissions, both because a bare word would catch ordinary
# English and teach the reader nothing:
#   * "range" -- the timeline filters by a date range.
#   * "registry" -- decision 10.3 keeps registry codes off every alert, list,
#     filter and aggregate, which is a property of the DATA, enforced by
#     `tests/test_orbit_changes_release.py` asserting no such field is
#     published, not a property of the prose.
# ---------------------------------------------------------------------------
TERM_LICENCE: tuple[tuple[str, str], ...] = (
    ("manoeuvre", "the words *manoeuvre*, *approach*"),
    ("maneuver", "the words *manoeuvre*, *approach*"),
    ("approach", "the words *manoeuvre*, *approach*"),
    ("threat", "*threat*"),
    ("inspect", "*inspect*"),
    ("hostile", "*hostile*"),
    ("adversary", "*adversary*"),
    ("shadow", "*shadow*"),
    ("stalk", "*stalk*"),
    ("intent", "*intent*"),
    ("purpose", "no purpose, motive or mission"),
    ("motive", "no purpose, motive or mission"),
    ("mission", "no purpose, motive or mission"),
    ("fuel", "*fuel*"),
    ("propellant", "no velocity-change figure"),
    ("deliberate", "no claim that an individual event was deliberate"),
    ("validated", "no 'validated' before the corresponding gate has run"),
    ("first", "no 'first', no 'at catalogue scale'"),
    ("miss distance", "no miss distance"),
    ("conjunction probability", "no conjunction probability"),
    ("collision risk", "no collision risk"),
    ("velocity change", "no velocity-change figure"),
    ("delta-v", "no velocity-change figure"),
    ("remaining life", "no mass and no remaining-life estimate"),
    ("at catalogue scale", "no 'at catalogue scale'"),
    ("per-nation", "no per-nation narrative"),
    ("country grouping", "no country grouping"),
)

# ---------------------------------------------------------------------------
# The second gate: phrasings that would say a setting makes an alert SURER.
#
# The withheld list above is about subject matter. This one is about a single
# false sentence the dial invites, and the measurement is what forbids it: on
# the curve's own numbers the tighter named settings do NOT reach a higher
# precision than the loosest one (3.410% -> 3.208% -> 2.681% -> 2.725%), so a
# page that let a reader infer otherwise would be contradicted by the table it
# is printing. Every phrasing below is banned outright, and the one sentence
# that DENIES the claim is fenced in the generated module so the gate can scan
# everything else.
# ---------------------------------------------------------------------------
CERTAINTY_PHRASES: tuple[str, ...] = (
    "more certain",
    "most certain",
    "more certainty",
    "greater certainty",
    "higher certainty",
    "increases certainty",
    "more confident",
    "greater confidence",
    "higher confidence",
    "more sure",
    "surer",
    "more reliable",
    "more accurate",
    "more precise",
    "more trustworthy",
    "safer bet",
    "better odds",
)

# The framing block, quoted from the section design paragraph that licenses it.
# It is a denial of three things, so it necessarily contains one of the terms
# above; that is why the denial block is fenced off in the generated module and
# checked here instead.
NOT_THIS = (
    "Ownership-agnostic arithmetic on public element sets. It attributes no "
    "purpose to anyone. It is not a conjunction service and does not replace one."
)

# The denial the dial owes, and the only string in the section licensed to
# contain a banned phrasing, because it refuses it by naming it.
DIAL_DENIAL = (
    "A setting changes which alerts are shown. It does not make any one of them "
    "more certain, and the measured table beside it is why."
)


def _round(value: float, places: int) -> str:
    return f"{value:.{places}f}"


def _percent(fraction: float, places: int = 1) -> str:
    return _round(fraction * 100.0, places)


def _ts(value: object, indent: int = 0) -> str:
    """Emit a value as TypeScript source, deterministically."""
    pad = " " * indent
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return json.dumps(value)
    if isinstance(value, (list, tuple)):
        if not value:
            return "[]"
        items = ",\n".join(f"{pad}  {_ts(item, indent + 2)}" for item in value)
        return "[\n" + items + f",\n{pad}]"
    if isinstance(value, dict):
        if not value:
            return "{}"
        rows = []
        for key, item in value.items():
            name = key if key.isidentifier() else json.dumps(key)
            rows.append(f"{pad}  {name}: {_ts(item, indent + 2)}")
        return "{\n" + ",\n".join(rows) + f",\n{pad}}}"
    raise TypeError(f"cannot emit {type(value)!r}")


def _flat(text: str) -> str:
    """One line, single-spaced: the design wraps its prose, the quote does not."""
    return " ".join(text.split())


def _leo_figures() -> dict[str, object]:
    """The low-orbit arm's measured numbers, from its own frozen record.

    The registered catalogue is arm M -- the phase arm with corroboration -- and
    the support, the lead distribution and the alert denominator are read from
    three places that have to agree: the record file itself, the precision row
    of the results, and the control paragraph. A disagreement stops this
    generator rather than publishing a figure whose sources differ.
    """
    rows = [json.loads(line) for line in LEO_EVENTS_PATH.read_text().splitlines() if line.strip()]
    registered = [row for row in rows if row.get("armM")]
    leads = [row["leadCausalDays"] for row in registered if row.get("leadCausalDays") is not None]
    if not registered or len(leads) != len(registered):
        raise SystemExit("the low-orbit record has no complete lead distribution")

    results = _flat(LEO_RESULTS_PATH.read_text())
    precision_row = re.search(
        r"\| Alerts ending in a registered arm-M event \| (\d+) / (\d+) = \*\*([\d.]+)%\*\* "
        r"\| \[([\d.]+)%, ([\d.]+)%\] \|",
        results,
    )
    if precision_row is None:
        raise SystemExit("the low-orbit precision row is no longer in the results")
    positives, alerts = int(precision_row.group(1)), int(precision_row.group(2))
    if positives != len(registered):
        raise SystemExit(
            f"the low-orbit record holds {len(registered)} registered events and the "
            f"results row counts {positives}"
        )

    control = re.search(r"exactly zero events across ([\d.]+) million object-days", results)
    if control is None:
        raise SystemExit("the low-orbit control paragraph is no longer in the results")

    return {
        "leoSupport": positives,
        "leoAlerts": alerts,
        "leoPrecisionPercent": _round(positives / alerts * 100.0, 1),
        "leoWilsonLowPercent": precision_row.group(4),
        "leoWilsonHighPercent": precision_row.group(5),
        "leoLeadMedianDays": _round(statistics.median(leads), 1),
        "leoControlEvents": 0,
        "leoControlObjectDaysMillions": control.group(1),
    }


def _curve_rows(curve: dict) -> dict[str, dict]:
    """The spoken class's row of each named setting, keyed by the setting's name."""
    rows: dict[str, dict] = {}
    for setting in curve["namedSettings"]:
        for entry in setting["classes"]:
            if entry["className"] == SPOKEN_CLASS:
                rows[setting["name"]] = entry
    missing = [setting["name"] for setting in curve["namedSettings"] if setting["name"] not in rows]
    if missing:
        raise SystemExit(f"the curve has no {SPOKEN_CLASS} row at {', '.join(missing)}")
    return rows


def _dial_finding(curve: dict) -> str:
    """THE MEASURED FINDING, printed rather than the trade-off a reader expects.

    The curve swept four named settings and the precision did not climb with
    them. That is the sentence the page owes: it is counted, it is on the same
    table the stops are read from, and without it a segmented control that goes
    from *everything* to *very high* says the opposite by its shape alone.
    """
    rows = _curve_rows(curve)
    order = [setting["name"] for setting in curve["namedSettings"]]
    loosest = rows[order[0]]
    if any(rows[name]["precision"] > loosest["precision"] for name in order[1:]):
        # If a future curve ever measures a tighter setting ABOVE the loosest,
        # this sentence stops being true and this generator stops rather than
        # publishing it.
        raise SystemExit(
            "a tighter named setting now measures above the loosest one; the dial's "
            "finding sentence is no longer what the table says"
        )
    parts = ", ".join(
        f"{_percent(rows[name]['precision'], 3)}% {'at the loosest setting' if index == 0 else name.replace('-', ' ')}"
        for index, name in enumerate(order)
    )
    return (
        f"Tightening the setting did not raise the measured precision: {parts}. "
        f"What tightening changes is how many alerts are shown, and how late they come."
    )


def _exercise_body(receipt: dict) -> str:
    """What the reader is looking at: a replay, on an injected clock, not a lane."""
    clock = receipt["clock"]
    start = clock["start"][:10]
    end = clock["end"][:10]
    minutes = receipt["wallSeconds"] / 60.0
    settings = ", ".join(str(name).replace("-", " ") for name in receipt["settingsExercised"])
    return (
        f"No lane is running. Every alert on this page was produced by replaying the "
        f"frozen detector over the archive from {start} to {end} on an injected clock, "
        f"at two evidence settings ({settings}), on one processor core in "
        f"{minutes:.0f} minutes. Nothing was sent anywhere, nothing is scheduled, and "
        f"no line here is a statement about what is happening today."
    )


def _leo_gap(leo_model: dict, receipt: dict) -> str:
    """Why the low-orbit arm raises nothing, in the numbers that withheld it."""
    entry = leo_model["classes"][0]
    ratio = entry["passiveControlRatio"]
    bar = entry["passiveControlBar"]
    audit = receipt["audit"]
    window = receipt["window"]
    return (
        f"Low orbit raises no alert, and none was dropped quietly: over the window from "
        f"{window['start'][:10]} to {window['end'][:10]} the arm assessed "
        f"{audit['assessments']:,} changes and raised {audit['alertsRaised']}. Its own "
        f"control fires on objects that are not payloads at {ratio:.3f} of the rate it "
        f"fires on payloads, against a design target of {bar:g}, so its flag has not "
        f"earned a clause about what it means. A withheld gate, not an absence of change."
    )


def _verify_licences(model: dict, design: str) -> None:
    never_say = "\n".join(model["neverSay"])
    for term, licence in TERM_LICENCE:
        if licence not in never_say and licence not in _flat(design):
            raise SystemExit(
                f"the licence for withholding {term!r} is no longer in the frozen "
                f"bundle or in the section design: {licence!r}"
            )
    if NOT_THIS not in _flat(design):
        raise SystemExit("the framing block is not quoted verbatim in the section design")


def build(model: dict, design: str, curve: dict, leo_model: dict,
          receipt: dict, leo_receipt: dict) -> str:
    _verify_licences(model, design)

    detector = model["detector"]
    base = model["basePopulation"]
    classes = {entry["name"]: entry for entry in model["classes"]}
    spoken = classes["WIDE-CROSSING"]          # the one class the lane speaks unaided
    arrivals = spoken["arrivalDays"]

    slot_deg = _round(detector["slotMatchDeg"], 1)
    dwell_days = f"{int(detector['dwellDays'])}"
    precision = _percent(spoken["precision"])
    wilson_low = _percent(spoken["wilson95"][0])
    wilson_high = _percent(spoken["wilson95"][1])
    # The base rate is the one figure carried to two decimals: at one it reads
    # 0.1%, and the whole point of printing it beside 3.4% is the size of the
    # step between them.
    base_rate = _percent(base["precision"], 2)

    reach_sentence = (
        f"Of {spoken['n']:,} confirmed drift changes matching this pattern, "
        f"{spoken['positives']} ended within {slot_deg}° of any satellite's mean "
        f"longitude for {dwell_days} days or more — {precision}%, Wilson 95% "
        f"{wilson_low}–{wilson_high}%. That figure is for any satellite. No figure "
        f"exists for a particular one. Base rate for a drift change of any kind: "
        f"{base_rate}%."
    )

    leo = _leo_figures()
    leo_sentence = (
        f"Of {leo['leoAlerts']} alerts raised across the whole archive, "
        f"{leo['leoSupport']} ended in a campaign that closed to a shared phase — "
        f"{leo['leoPrecisionPercent']}%, Wilson 95% {leo['leoWilsonLowPercent']}–"
        f"{leo['leoWilsonHighPercent']}%, at a median {leo['leoLeadMedianDays']} days "
        f"between the campaign's confirmed start and the arrival. The control built for "
        f"this population returned {leo['leoControlEvents']} events in "
        f"{leo['leoControlObjectDaysMillions']} million object-days."
    )

    figures = {
        "modelVersion": model["modelVersion"],
        "modelChecksum": model["checksum"],
        "spokenClass": spoken["name"],
        "spokenClassDescription": spoken["description"],
        "support": spoken["n"],
        "positives": spoken["positives"],
        "precisionPercent": precision,
        "wilsonLowPercent": wilson_low,
        "wilsonHighPercent": wilson_high,
        "basePopulation": base["n"],
        "basePositives": base["positives"],
        "basePrecisionPercent": base_rate,
        "leadMedianDays": _round(arrivals["p50"], 1),
        "leadP25Days": _round(arrivals["p25"], 1),
        "leadP75Days": _round(arrivals["p75"], 1),
        "leadP95Days": _round(arrivals["p95"], 1),
        "slotMatchDeg": slot_deg,
        "dwellDays": dwell_days,
        "stationedDriftDegPerDay": _round(detector["slotDriftFloorDegPerDay"], 3),
        "resonanceStableDeg": _round(detector["lambdaStableDeg"], 1),
        "resonanceAccelDegPerDay2": detector["lambdaDdotDegPerDay2"],
        "resonanceStepDays": detector["propagationStepDays"],
        **leo,
    }

    strings = {
        "rail": {
            "label": "Orbit changes",
            "mobileLabel": "Changes",
        },
        "section": {
            "kicker": "ORBIT CHANGE RECORD",
            "title": "Orbit changes",
            "standfirst": (
                "A public record of element-set changes: what changed, by how much, "
                "and how often the same arithmetic has ended beside another satellite."
            ),
            "notThisHeading": "What this is not",
        },
        "views": {
            "ledger": "Ledger",
            "object": "Object",
            "reach": "Reach",
            "alerts": "Alerts",
        },
        "families": {
            "catalogue": "Catalogue change",
            "geoColocation": "Slot co-location",
            "leoStation": "Co-orbital station",
            "confirmed": "Confirmed drift change",
        },
        # What opened the episode. Not a type -- the type is the library's job
        # and the library has not been measured -- but what shape of change the
        # instruments saw.
        "kinds": {
            "impulsive": "Step change",
            "campaign": "Staged campaign",
            "continuous": "Continuous change",
            "not-observed-onset": "Opening not observed",
        },
        "regimes": {
            "LEO": "LEO",
            "MEO": "MEO",
            "GEO": "GEO",
            "HEO": "HEO",
        },
        "stamps": {
            "candidate": "CANDIDATE",
            "notAssessable": "NOT ASSESSABLE",
            "underpowered": "UNDERPOWERED",
            "notAnAlert": "NOT AN ALERT",
            "archiveToDate": "ARCHIVE TO",
            # The type slot's empty state. It is a stamp rather than a dash
            # because "we have not labelled this" and "this has no type" are
            # different sentences and a blank cell says the second one.
            "unlabelled": "UNLABELLED",
            "notLabelled": "NOT LABELLED",
            "trackingEnded": "TRACKING ENDED",
            "declared": "DECLARED",
            "reopened": "RE-OPENED",
        },
        # The three states an episode can be in. Read from the archive, not
        # assumed: the row carries the sentence that decided which.
        "states": {
            "initiated": "INITIATED",
            "in-progress": "IN PROGRESS",
            "completed": "COMPLETED",
        },
        "labels": {
            "date": "Date",
            "object": "Object",
            "regime": "Regime",
            "change": "Change",
            "size": "Size",
            "family": "Family",
            "norad": "NORAD",
            "lastElementSet": "Last element set",
            "partner": "Partner object",
            "driftRate": "Drift rate",
            "meanLongitude": "Mean longitude",
            "daysToReach": "Days to reach",
            "search": "Find an object",
            "dateRange": "Date range",
            "eventsPerWeek": "Changes per week",
            "leoCampaign": "in-track phasing campaign",
            "driftChange": "drift-rate change",
            "size": "Size",
            "moved": "Moved",
            "type": "Type",
            "state": "State",
            "stationed": "Stationed on the belt",
            "filters": "Narrow the record",
            "any": "Any",
            "clear": "Clear",
            "episodes": "changes",
            "ledger": "Ledger",
            "closure": "Closure",
            "reading": "The reading",
            "onset": "Opened",
            "updated": "Last element set",
            "settled": "Settled",
            "steps": "Steps in this change",
            "recordTo": "Record to",
            "openedNothing": "Steps that opened no change",
            "kind": "Kind",
            "verdict": "Routine check",
            "ofRecord": "of",
            "shownOf": "drawn of",
            "readingNotMeasured": (
                "No reading has been measured for any change in this record yet, "
                "so every reading slot is empty rather than blank."
            ),
        },
        "units": {
            "degPerDay": "°/day",
            "deg": "°",
            "km": "km",
            "days": "d",
            "year": "year",
        },
        "object": {
            "forwardPathClaim": (
                "The forward path is where the mean longitude would be if the object "
                "did nothing further."
            ),
            "forwardPathLimit": (
                "It is not a position, and it says nothing at all past the measured "
                "horizon."
            ),
            "ribbonLabel": "Measured error, growing with the horizon",
            "ribbonGap": "Error not measured beyond 30 days",
            "pathStops": "The path stops at +{membershipDays} days",
            "bandGrows": (
                "The band is measured out to +{unfitDays} days and the path is not, "
                "because membership of a reachable set was measured to be resolvable "
                "only to +{membershipDays} days and an arrival time only to "
                "+{precisionDays}. By +{unfitDays} days the band's median half-width "
                "is {unfitMedian}\u00b0, wider than the {spacing}\u00b0 that separates "
                "adjacent occupied longitudes on this belt and past the {unfitBar}\u00b0 "
                "bar its gate was set against, so it covers several stations at once "
                "and no line is drawn through it."
            ),
            "occupiedBandLabel": "Mean longitudes held by stationed objects",
            "phasePanelLabel": "Relative phase to the partner object",
        },
        "reach": {
            "heading": "Reachable set",
            "sentence": reach_sentence,
            "candidateNote": (
                "These are the stationed objects the drift can reach inside the "
                "window, in order of days to reach. Nothing here is ranked."
            ),
            "dialNote": "Tighter settings show fewer candidates and give later warning.",
            "leoGap": (
                "Same-plane reach is not measured for live objects. Historical "
                "phasing campaigns: see the event."
            ),
            # ------------------------------------------------------------------
            # THE REACHABLE SET, drawn for one alert at one evidence setting.
            #
            # The set is geometry on two published files -- the alert's slot
            # coordinate and drift rate, and the belt record -- and the page
            # does that geometry itself because it draws the path from wherever
            # the reader has put the dial. No precision is computed anywhere:
            # every k/n on this view is copied from the operating-point row of
            # the setting the reader chose.
            # ------------------------------------------------------------------
            "candidatesHeading": "The stationed objects on the path",
            "beltNote": (
                "The set is drawn against the belt record as it stands today, not "
                "as it stood during the replay window. Which objects hold which "
                "longitudes has moved since."
            ),
            "notRaisedHeading": "Not raised at this setting",
            "notRaisedDrift": (
                "The drift change is {driftChange} and this setting's floor is "
                "{floor} °/day."
            ),
            "notRaisedSlots": (
                "The path passes {slots} occupied longitudes inside the window and "
                "this setting asks for {minSlots}."
            ),
            "emptySet": (
                "No stationed object holds a longitude on this path inside the "
                "window. The path is drawn; the set is empty and says so."
            ),
            "arrivalWindowGap": "arrival window not stated beyond +{precisionDays} days",
            "arrivalWindowUnderADay": "\u00b1 under a day",
            "pathHorizon": "Path drawn to +{membershipDays} days",
            "daysToReach": "Days to reach",
            "arrivalWindow": "Arrival window",
            "planeCompatible": "In a compatible plane",
            "noAlertSelected": (
                "Open an alert from the Alerts view to see the objects its path "
                "reaches."
            ),
        },
        # --------------------------------------------------------------------
        # THE EVIDENCE SETTING (design 3.5).
        #
        # A segmented control over the settings the replay counted, and beside
        # each one its three measured numbers. The control's SHAPE argues that
        # the right-hand end is better, so the finding below it -- measured on
        # the same table -- is printed on the face of the dial and not in a
        # disclosure: the tighter settings did not reach a higher precision.
        # --------------------------------------------------------------------
        "dial": {
            "heading": "Evidence setting",
            "finding": _dial_finding(curve),
            "precision": "Measured precision",
            "lead": "Median warning",
            "alertsPerYear": "Alerts a year",
            "recall": "Arrivals kept, of the loosest setting's",
            "evidence": "What this setting asks for",
            "interval": "95% interval",
            "notOffered": (
                "Not offered: the replay counted fewer than {minSupport} alerts at "
                "this setting, so it has no figure a reader could judge."
            ),
            "withheldAtThisSetting": (
                "Withheld at this setting: {reason}."
            ),
            "sourceNote": (
                "Every figure on this dial is copied from the operating-point table "
                "{curveVersion}, counted on the same archive the model was frozen "
                "on. Nothing on this page counts anything."
            ),
            "alertsAtThisSetting": "Alerts in the replay at this setting",
            "evidenceLine": (
                "drift change at or above {drift} °/day · at least {slots} occupied "
                "longitudes on the path · still drifting at {sweeps} consecutive "
                "element sets · arrival counted within {horizon} days"
            ),
            "noListHeading": "This setting has no list",
            "noListBody": (
                "The exercise ran at two of the four settings. This one's numbers are "
                "measured and are on the dial above; which changes it would have "
                "spoken was not recorded, and it is not worked out from another "
                "setting's answer."
            ),
            "stops": {
                "everything": "Everything",
                "balanced": "Balanced",
                "high-confidence": "High confidence",
                "very-high": "Very high",
            },
        },
        "leo": {
            "heading": "In-track phasing campaigns",
            "sentence": leo_sentence,
            "label": "in-track phasing campaign",
            "phaseOnly": (
                "This lane speaks about phase inside a plane two objects already "
                "share. It does not match one object's plane to another's, in either "
                "direction, and it draws no candidate set from a plane."
            ),
            "partnerHeading": "The partner object",
            "closureLabel": "Phase closure",
        },
        "alerts": {
            "heading": "Spoken alerts",
            "accountingHeading": "This month, counted",
            "triggersAssessed": "Changes assessed",
            "withheld": "Withheld",
            "notAssessable": "Not assessable",
            "raised": "Alerts raised",
            "resolved": "Resolved",
            "expired": "Expired",
            "pending": "Pending",
            "runningPrecision": "Running precision",
            "modelFooter": "Model",
            # ----------------------------------------------------------------
            # THE REPLAY, LABELLED AS ONE EVERYWHERE IT APPEARS.
            #
            # These alerts are a synthetic exercise over the 2010s and the page
            # says so on the panel, on the stamp of every card and in the model
            # footer. A reader who lands on one card and reads nothing else
            # must still not be able to mistake it for something live.
            # ----------------------------------------------------------------
            "exerciseStamp": "REPLAY OF 2010-2020",
            "accountingReplayHeading": "Over the replay window, counted",
            "exerciseHeading": "A replay of the 2010s, not a running lane",
            "exerciseBody": _exercise_body(receipt),
            "exerciseWindow": "Replay window",
            "exerciseReceipt": "Receipt",
            "cardDriftChange": "Drift-rate change",
            "cardConfirmed": "Confirmed",
            "cardAnnounced": "Announced",
            "cardHorizon": "Horizon closes",
            "cardOutcome": "Outcome",
            "cardHeld": "Element sets the change held for",
            "outcomeArrival": "arrived and stayed",
            "outcomeNone": "the horizon closed with no attributed arrival",
            "outcomePending": "open; the horizon has not closed",
            "onThisLane": "On this lane",
            "frozenFigure": "Frozen figure",
            "precisionPairNote": (
                "Left: what this lane's own alerts of this class did, counted as they "
                "resolved. Right: what the frozen model measured before the lane ran. "
                "Beside each other, never in place of each other. The alert's own text "
                "quotes the left-hand figure as it stood when the alert was spoken, "
                "which for an early one is the labelled gap it was then."
            ),
            "runningPrecisionGap": "no alert of this class has resolved yet",
            "withheldHeading": "Assessed and not spoken",
            "withheldNote": (
                "These are counts. A change the lane does not speak gets no card: at "
                "that precision a card would be a labelled gap dressed as a result."
            ),
            "leoHeading": "Low orbit",
            "leoGap": _leo_gap(leo_model, leo_receipt),
            "leoAssessed": "Changes assessed",
            "leoRaised": "Alerts raised",
            "leoWindow": "Exercise window",
            "cardsShown": "alerts drawn",
        },
        "gaps": {
            "laneNotRunning": "The alert lane is not yet running",
            "laneNotRunningBody": (
                "Nothing has been recorded to read here. When the lane runs, every "
                "line it writes appears on this page, including the ones that expire "
                "unresolved."
            ),
            "settingsNotMeasured": "Only the measured settings are offered",
            "settingsNotMeasuredBody": (
                "A setting is shown when the replay has counted it. The two counted "
                "today are the whole population and the one class the lane speaks."
            ),
            "archiveOffline": "Archive server offline",
            "noRows": "No change in this window",
            "stateRatesNotMeasured": "State rates not yet measured",
            "stateRatesNotMeasuredBody": (
                "How often a change that opens goes on to settle, lapse or re-open "
                "has not been counted yet. The states below are what the elements "
                "show; how reliable the states themselves are is a separate "
                "measurement and it is owed."
            ),
            "noRowsBody": (
                "The record holds nothing matching what is set above. Widen the "
                "range or clear the filters to see it all again."
            ),
        },
        # ------------------------------------------------------------------
        # THE READING (ledger design section 2.1).
        #
        # These are TEMPLATES, not prose: each one is a fixed string with named
        # slots, and every slot is filled from a measured field of an episode
        # record. Nothing composes a sentence, which is what makes the
        # vocabulary gate sufficient -- it scans these, and there is nothing
        # else to scan.
        #
        # A clause whose measurement does not exist prints its `gap` string and
        # names the measurement it is owed. Today that is all of them except R3
        # at stage S1 for a class-1 near-belt episode, whose figures are in the
        # frozen bundle and are generated below.
        # ------------------------------------------------------------------
        "reading": {
            "r1": {
                "measured": (
                    "Type: {typeLabel}. Agreement with the {labelClass} record: "
                    "{agreementPercent}% of {typeSupport} matched changes "
                    "(library {libraryVersion})."
                ),
                "underpowered": (
                    "Type: {typeLabel}. Fewer than {minSupport} matched changes; "
                    "no agreement figure."
                ),
                "gap": (
                    "Type: not yet labelled. The library's agreement table has not "
                    "been measured."
                ),
                "owed": "M4",
            },
            "r2": {
                "routine": "Consistent with {patternLabel}, seen {patternCount} times in {classLabel}.",
                "declared": (
                    " An operator-published planned change covers this epoch "
                    "({declaredSource}, published {declaredDate})."
                ),
                "notRoutine": (
                    "Not consistent with any routine pattern of {classLabel}: "
                    "{featureLabel} is {featureValue}, outside the class range "
                    "{classP5}\u2013{classP95}. Routine objects of this class exceed "
                    "this deviation {falseAlarmPercent}% of the time."
                ),
                "gap": "Routine check: not yet measured for {classLabel}.",
                "owed": "M5",
            },
            "r3": {
                "measured": (
                    "Reaches the stations of {setSize} catalogued objects within "
                    "{horizonDays} days ({setSizePlaneCompatible} in a compatible "
                    "plane). Stage {stage}: {k} of {n} changes of this class at this "
                    "stage ended within {slotMatchDeg}\u00b0 of any satellite's station "
                    "for {dwellDays} days or more \u2014 {precisionPercent}% (95% interval "
                    "{wilsonLo}\u2013{wilsonHi}%). No figure exists for any particular "
                    "satellite."
                ),
                "gap": (
                    "Reaches the stations of {setSize} catalogued objects within "
                    "{horizonDays} days ({setSizePlaneCompatible} in a compatible "
                    "plane). Stage {stage}: no number until the replay."
                ),
                "leoInPlane": (
                    "Shares a plane with {setSize} catalogued objects; phase inside "
                    "that plane is reachable within {horizonDays} days. Cross-plane "
                    "reach is not computed."
                ),
                "owed": "M3",
            },
            # R4 is the denial, and it is the fenced block below rather than a
            # template: NOT_THIS and both structural caveats, byte for byte.
            "r4": {"source": "NOT_THIS and STRUCTURAL_CAVEATS"},
            # The slots R3 can fill today, from the frozen bundle. Stage S1 of a
            # near-belt class-1 episode and nothing else.
            "r3S1": {
                "stage": "S1",
                "k": spoken["positives"],
                "n": spoken["n"],
                "precisionPercent": precision,
                "wilsonLo": wilson_low,
                "wilsonHi": wilson_high,
                "slotMatchDeg": slot_deg,
                "dwellDays": dwell_days,
            },
        },
        "headline": {
            "template": "{typeLabel} \u2014 {verdictWord}",
            "routine": "routine for its class",
            "notRoutine": "not routine",
            "unmeasured": "routine check not yet measured",
            "unlabelledType": "Change of an unlabelled type",
        },
        "delta": {
            "belt": (
                "drift {initialDrift} \u2192 {currentDrift} \u00b0/day \u00b7 "
                "longitude {initialLon} \u2192 {currentLon}"
            ),
            "elsewhere": "semi-major axis {initialA} \u2192 {currentA} km ({deltaA})",
            "inclination": "inclination {initialI} \u2192 {currentI}\u00b0",
            "belowFloor": "below the floor",
            "driftOnly": "drift {initialDrift} \u2192 {currentDrift} \u00b0/day",
            "notObserved": "not observed",
        },
        "aggregate": {
            "chanceHeading": "Against chance",
            "chanceSentence": (
                "Relocations across this belt end beside another satellite 2.2 times "
                "less often than chance would put them there."
            ),
        },
    }

    lines = [
        "/* GENERATED FILE — DO NOT EDIT BY HAND.",
        " *",
        " * Written by `python3 -m tools.orbit_changes_strings` from the frozen",
        " * detector bundle and the section design. Every word the Orbit changes",
        " * section can put on a screen is in this file: the rendering modules read",
        " * it and compose no sentence of their own.",
        " *",
        f" * Model: {model['modelVersion']}",
        f" * Bundle checksum: {model['checksum']}",
        " *",
        " * `tests/orbit-changes-vocabulary.test.ts` regenerates nothing; it reads",
        " * the bundle itself and refuses this file if a figure, a caveat or the",
        " * framing block has drifted away from the frozen source, and it refuses",
        " * any section module that prints a withheld term.",
        " */",
        "",
        f"export const MODEL_VERSION = {_ts(model['modelVersion'])};",
        f"export const MODEL_CHECKSUM = {_ts(model['checksum'])};",
        "",
        "/* The terms no string in this section may contain. The fenced block is",
        "   DATA: it is the only place in the section where these words are allowed",
        "   to appear, and the gate test strips the fence before it scans. */",
        "/* @vocabulary-data-begin withheld */",
        f"export const NEVER_SAY_TERMS: readonly string[] = {_ts([term for term, _ in TERM_LICENCE])};",
        "/* @vocabulary-data-end withheld */",
        "",
        "/* @vocabulary-data-begin certainty */",
        "/* The phrasings that would tell a reader a tighter setting makes an alert",
        "   surer. The curve measured the opposite, so this is a gate rather than a",
        "   style rule, and the one sentence that DENIES the claim is fenced here",
        "   with the list, because it necessarily contains the phrasing it refuses. */",
        f"export const CERTAINTY_PHRASES: readonly string[] = {_ts(list(CERTAINTY_PHRASES))};",
        f"export const DIAL_DENIAL = {_ts(DIAL_DENIAL)};",
        "/* @vocabulary-data-end certainty */",
        "",
        "/* Denials, and the only strings exempt from the scan above, because each",
        "   one refuses something by naming it. Both caveats are copied byte for byte",
        "   out of the frozen bundle; the framing block is quoted from the section",
        "   design. The gate test compares all three against those sources. */",
        "/* @vocabulary-data-begin denials */",
        f"export const STRUCTURAL_CAVEATS: readonly string[] = {_ts(list(model['caveats']))};",
        f"export const NOT_THIS = {_ts(NOT_THIS)};",
        "/* @vocabulary-data-end denials */",
        "",
        "/* Every figure below is arithmetic on the frozen bundle. Percentages carry",
        "   one decimal, except the base rate, which carries two because at one it",
        "   reads 0.1% and the step between it and the spoken class is the point.",
        "   Lead days carry one decimal, as a distribution and never as a point. */",
        f"export const CLASS_FIGURES = {_ts(figures)} as const;",
        "",
        f"export const SECTION_STRINGS = {_ts(strings)} as const;",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="fail if the committed module differs from this file's output")
    args = parser.parse_args(argv)

    model = json.loads(MODEL_PATH.read_text())
    design = DESIGN_PATH.read_text()
    source = build(
        model,
        design,
        json.loads(CURVE_PATH.read_text()),
        json.loads(LEO_MODEL_PATH.read_text()),
        json.loads(REPLAY_RECEIPT_PATH.read_text()),
        json.loads(LEO_RECEIPT_PATH.read_text()),
    )

    if args.check:
        current = OUTPUT_PATH.read_text() if OUTPUT_PATH.exists() else ""
        if current != source:
            print(f"{OUTPUT_PATH} is not what tools/orbit_changes_strings.py produces")
            return 1
        print(f"{OUTPUT_PATH} matches the frozen bundle")
        return 0

    OUTPUT_PATH.write_text(source)
    print(f"wrote {OUTPUT_PATH} ({len(source)} bytes) from {MODEL_PATH.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
