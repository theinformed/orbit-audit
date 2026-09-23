#!/usr/bin/env python3
"""The behavioural alarm lane -- the read-only sidecar.

This module builds items 3, 4 and 5 of `docs/alarm-lane-design-20260922.md`
section 11:

  3. a FROZEN ARTIFACT for the trigger-time taxonomy, its scaler constants and
     its outcome tables, VERSIONED and CHECKSUMMED so that a published
     precision figure names the model that earned it;
  4. the SIDECAR -- a timer-shaped job that reads the latest element sets,
     runs the trigger-time detector against the frozen artifact, keeps a state
     file and appends to an alert ledger, with the vocabulary gate of the
     design's section 6 implemented as A FUNCTION THAT RETURNS THE PERMITTED
     WORDS rather than as a convention;
  5. the LEDGER'S OWN AUDIT -- every alert, its class, its resolution and the
     running precision measured on THIS lane rather than borrowed from the
     offline run, with the two structural caveats of section 5.4 printed on
     every output.

NOTHING HERE IS SCHEDULED. This module installs no timer and no cron entry;
it writes nothing to `src/`, `data/` or `public/`; and no alert leaves the
machine, because whether one ever does is operator decision 5 of the design's
section 10 and is RESERVED, not taken. Every database handle opened here is
read-only (`mode=ro` plus `PRAGMA query_only = 1`) and there is no write path
into `orbit-release`, the catalogue shards or the publish gate.

The detector is not reinvented here. Every quantity is computed by the
instrument that measured it -- `proximity_geo` (T8a) for the element series,
the drift rate and the flag threshold, and `trigger_alarm` (T8d) for the flag
chain, the causal view, the forward propagation and the trigger-time feature
vector. This module adds a clock, a state file, a ledger, a gate and an audit.

Usage:

    python3 tools/alarm_lane.py freeze  --work <dir> [--out docs] [--date ...]
    python3 tools/alarm_lane.py run     [--now <iso>] [--state ...] [--ledger ...]
    python3 tools/alarm_lane.py resolve [--ledger ...]
    python3 tools/alarm_lane.py audit   [--ledger ...] [--json <path>]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
for _p in (str(_REPO / "tools"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import proximity_geo as pg            # noqa: E402  the T8a instrument
import alarm_pattern as ap            # noqa: E402  the T8c instrument
import trigger_alarm as ta            # noqa: E402  the T8d instrument

DAY_MS = pg.DAY_MS
DESIGN = "docs/alarm-lane-design-20260922.md"
REGISTRATION = ta.REGISTRATION
RESULTS = "docs/trigger-alarm-results-20260922.md"
RECEIPT = "docs/trigger-alarm-20260922-receipt.json"

ARTIFACT_KIND = "alarm-lane-frozen-model"
MODEL_SCHEMA = 1
MODEL_FAMILY = "trigger-time-taxonomy"
MODEL_VERSION = "trigger-time-taxonomy/20260922/1"

MODEL_PATH = _REPO / "docs" / "alarm-lane-model-20260922.json"
STATE_PATH = _REPO / "runtime" / "alarm-lane" / "alarm-lane-state.json"
LEDGER_PATH = _REPO / "runtime" / "alarm-lane" / "alarm-lane-ledger.jsonl"

# design 8.1 -- T8b's standing requirement, at GEO as well as in LEO. The lane
# reads the whole per-object history up to the clock, which is at least this
# and usually far more; the constant is the FLOOR the design requires, and the
# state file records which of the two the run actually had.
LOOK_BACK_FLOOR_DAYS = 1095.0

# design 5.2 -- a class below this many supporting events is UNDERPOWERED and
# no rate is drawn from it
MIN_SUPPORT_FOR_A_RATE = 20

# design 2.1 -- the timer grid the lane would ride, stated so the derivation
# of section 2.3 has something to divide into. It is NOT this lane's choice.
HOST_TIMER_PERIOD_HOURS = 2.0

# design 2.3 / T8a 5.5 -- the CITED inputs to the cadence derivation. They are
# inputs to `derive_cadence` and never a hard-coded period: the derived value
# is recomputed from them, and from the spacing the lane MEASURES on the
# element sets it actually read, every time the state file is written.
CITED_EPOCH_SPACING_DAYS = 0.865          # design 2.3, near-GEO median
CITED_CONFIRMING_ELEMENT_SETS = 2         # T8a 5.5, the confirmation rule
CITED_MEDIAN_CAUSAL_LEAD_DAYS = 36.1      # T8a, design 8

# design 5.4 -- printed on the face of every alert and every audit report,
# never linked
CAVEATS = (
    "Mean longitude is a slot coordinate, not a miss distance. Two objects "
    "sharing a mean longitude are routinely tens of kilometres apart, kept so "
    "by eccentricity- and inclination-vector separation this track does not "
    "model. This lane is not a conjunction warning and does not replace one.",
    "The catalogue is a lower bound, never a census. A transfer executed "
    "below 0.010 deg/day is invisible, and 33% of the catalogued events had "
    "no visible initiating change. Absence of an alert is not evidence of "
    "absence of an approach.",
)

# design 7 -- what the lane must NEVER say. Enforced by
# `tests/test_alarm_lane.py`, not merely written down here.
NEVER_SAY = (
    "no purpose, motive or mission, for an object or for anyone operating it",
    "no attribution of a purpose to an operator, a programme or a state",
    "no per-nation narrative, no country grouping, no registry-code "
    "aggregate; a registry code is metadata, no detector branch reads one, "
    "and whether one ever appears on a surface is a reserved decision",
    "no miss distance, no range, no conjunction probability, no collision "
    "risk",
    "no velocity-change figure, no consumable-remaining figure, no mass and "
    "no remaining-life estimate for any object",
    "no point forecast of dwell duration or of closest separation",
    "no 'first', no 'at catalogue scale', no 'validated' before the "
    "corresponding gate has run",
    "no claim that an individual event was deliberate",
    "no silent suppression of an alert that did not pan out",
    "no quoting of the relocation-alert precision, or of another arm's "
    "published alert-channel precision, as the precision of a trigger-time "
    "alert: both are measured on populations defined by what the object "
    "subsequently did, or by a different detector",
    "no sentence about an individual object's own history",
)

# design 7.10 -- the two figures a trigger-time alert may never carry, as the
# literal strings a rendered alert is checked against
FORBIDDEN_FIGURES = ("32.8", "44.1")

# design 10 -- reserved and NOT taken here. Every value is null; the lane
# refuses the corresponding behaviour rather than picking a default that would
# pre-empt the decision.
RESERVED_DECISIONS = {
    "publicationSurface": None,
    "framing": None,
    "registryCodesEverAppear": None,
    "objectNamesAppear": None,
    "notificationLeavesTheMachine": None,
    "leoArmIsBuilt": None,
    "ledgerRetention": None,
}
RESERVED_NOTE = (
    "design section 10: seven operator decisions, reserved and not taken. "
    "This lane implements none of them. It has no surface, sends nothing, "
    "reads no registry code, prints no object name, has no LEO arm, and "
    "deletes nothing.")


# ==========================================================================
# Small helpers
# ==========================================================================
def _iso(ms):
    return datetime.fromtimestamp(float(ms) / 1000.0, timezone.utc).isoformat()


def _ms(iso):
    text = str(iso).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return float(dt.timestamp() * 1000.0)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json(body):
    """The serialisation the checksum is taken over: sorted keys, no spaces,
    no NaN -- so the same model always hashes to the same value."""
    return json.dumps(body, sort_keys=True, separators=(",", ":"),
                      allow_nan=False, ensure_ascii=True)


def checksum_of(body):
    return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


def _pct(x):
    return f"{100.0 * float(x):.3f}%"


class FrozenModelError(Exception):
    """The frozen artifact is absent, malformed, or does not match its own
    checksum. The lane refuses to run rather than quote a precision figure
    that names a model it cannot prove it is using."""


# ==========================================================================
# design 11.3 -- THE FROZEN ARTIFACT
# ==========================================================================
def write_model(body, path):
    """`body` is everything the checksum covers; the file is the body plus the
    checksum, so a reader can recompute it from the file alone."""
    body = {k: v for k, v in dict(body).items() if k != "checksum"}
    digest = checksum_of(body)
    doc = dict(body)
    doc["checksum"] = digest
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    return digest


CURVE_KIND = "alarm-lane-operating-points"
CURVE_PATH = _REPO / "docs" / "alarm-lane-operating-points-20260922.json"


def load_model(path=MODEL_PATH, verify=True, kind=ARTIFACT_KIND):
    """Load a frozen artifact and prove it is the one it says it is."""
    path = Path(path)
    if not path.exists():
        raise FrozenModelError(f"the frozen artifact is absent: {path}")
    doc = json.loads(path.read_text())
    stated = doc.get("checksum")
    body = {k: v for k, v in doc.items() if k != "checksum"}
    actual = checksum_of(body)
    if verify:
        if stated != actual:
            raise FrozenModelError(
                "the frozen artifact does not match its own checksum: stated "
                f"{stated}, recomputed {actual}")
        if doc.get("artifact") != kind:
            raise FrozenModelError(f"not a {kind}: {doc.get('artifact')}")
        if int(doc.get("schema", -1)) != MODEL_SCHEMA:
            raise FrozenModelError(f"unsupported schema {doc.get('schema')}")
    doc["_bodyChecksum"] = actual
    return doc


def model_checksum(model):
    return model.get("checksum") or model.get("_bodyChecksum")


def model_scaler(model):
    """The frozen scaler, as the array dictionary `alarm_pattern` expects, so
    a live assignment runs through the SAME two functions the measurement ran
    through rather than through a second implementation that could drift."""
    s = model["scaler"]
    return {"median": np.asarray(s["median"], dtype=np.float64),
            "mean": np.asarray(s["mean"], dtype=np.float64),
            "sd": np.asarray(s["sd"], dtype=np.float64),
            "keep": np.asarray(s["keep"], dtype=bool)}


def model_centroids(model):
    return np.asarray(model["centroids"], dtype=np.float64)


def classify(features, model):
    """Assign trigger-time feature dictionaries to frozen classes. Nothing is
    fitted: the scaler constants and the centroids come from the frozen
    artifact and from nowhere else."""
    names = tuple(model["featureNames"])
    if not features:
        return np.zeros(0, dtype=np.int64)
    matrix = np.asarray([[f.get(n, float("nan")) for n in names] for f in features],
                        dtype=np.float64)
    x = ap.apply_scaler(ap.transform(matrix, names), model_scaler(model))
    return np.asarray(ap.assign(x, model_centroids(model)), dtype=np.int64)


def load_operating_points(path=CURVE_PATH, model=None):
    """The operating-point curve, checksummed like the model and REFUSED if
    it does not name the frozen model it was measured against. A precision
    figure must name the model that earned it, and a setting's precision is
    no different."""
    doc = load_model(path, kind=CURVE_KIND)
    if model is not None:
        earned = doc.get("earnedBy", {})
        if earned.get("modelChecksum") != model_checksum(model):
            raise FrozenModelError(
                "the operating-point curve was measured against a different "
                f"frozen model ({str(earned.get('modelVersion'))} / "
                f"{str(earned.get('modelChecksum'))[:16]})")
    return doc


def operating_setting(curve, name):
    for entry in curve["namedSettings"]:
        if entry["name"] == name:
            return entry
    raise FrozenModelError(
        f"the curve has no setting {name!r}; it has "
        + ", ".join(repr(e["name"]) for e in curve["namedSettings"]))


def setting_class_row(setting, cluster):
    if setting is None:
        return None
    for row in setting["classes"]:
        if int(row["class"]) == int(cluster):
            return row
    return None


def model_class(model, cluster):
    for row in model["classes"]:
        if int(row["cluster"]) == int(cluster):
            return row
    raise FrozenModelError(f"the frozen artifact has no class {cluster}")


# ==========================================================================
# design 6 -- THE VOCABULARY GATE, AS A FUNCTION THAT RETURNS THE WORDS
# ==========================================================================
# The permitted words themselves, one tuple per clause. The gate returns
# these; the renderer may use nothing else. `pipeline/orbit_events.py` gates
# the word "manoeuvre" in exactly this shape and this is a copy of it, not an
# improvement on it.
CLAUSE_WORDS = {
    "drift_change": ("executed a drift-rate change of", "deg/day",
                     "confirmed at", "second consecutive element set",
                     "announced at"),
    "pattern_match": ("the trigger matches pattern",),
    "prior_instances": ("of the",
                        "confirmed drift changes in the archive match it"),
    "outcome_distribution": ("the object arrived within 0.1 deg of another "
                             "satellite's mean longitude and stayed there for "
                             "at least 30 days in", "Wilson 95%",
                             "median time from this point to arrival",
                             "p25-p75"),
    "base_rate": ("base rate for a confirmed drift change of any kind",),
    "running_precision": ("alert class precision to date on this lane",),
    "labelled_gap": ("not assessable",),
    "caveats": CAVEATS,
    "provenance": ("pattern assignment is mathematics on public element sets. "
                   "No purpose is attributed.",),
}

WITHHELD_REASONS = {
    "object_history": (
        "WITHHELD -- the per-object predictor is worse than the population "
        "base rate at every prior-event count and no threshold exists "
        "(design 6, 7.11). The lane may rank on it internally; it may not say "
        "anything about it."),
    "manoeuvre": (
        "WITHHELD -- `manoeuvreLabelPermitted` is false in the shipped "
        "detector bundle: 34 flags in 1,941 intervals of objects that "
        "physically cannot manoeuvre, against a design target of one in a "
        "thousand. The lane may not invent a word the shipped detector has "
        "not earned, so it says 'drift-rate change'."),
    "approach": (
        "WITHHELD for an individual alert -- corroboration is informative in "
        "aggregate and not per row (design 6)."),
    "point_forecast": (
        "WITHHELD -- a distribution with its spread, always; never a point "
        "value of the dwell duration, of the closest separation or of the "
        "time to arrival (design 7.6)."),
    "borrowed_precision": (
        "WITHHELD -- the relocation-alert and plane-change precisions are "
        "measured on populations defined by what the object subsequently did; "
        "neither is available at trigger time (design 7.10)."),
}


def _lo(row):
    return float(row["wilson95"][0])


def _hi(row):
    return float(row["wilson95"][1])


def class_may_be_spoken(model, cluster, point=None):
    """design 6, as an arithmetic rule rather than a stored verdict.

    'matches pattern P' is permitted when the class is a REPRODUCIBLE cluster
    -- bootstrap Jaccard at or above the registered bar -- when the numbers
    being quoted rest on at least `MIN_SUPPORT_FOR_A_RATE` supporting events,
    so a rate may be drawn from them at all, and when the precision is
    SEPARATED ABOVE the base rate of the same population: the Wilson lower
    bound above the base population's Wilson upper bound.

    `point` is one class's row of an OPERATING-POINT setting. When it is
    given, the rule is applied to THAT SETTING'S OWN measured numbers and to
    the base rate at that setting's horizon, because a setting's alert quotes
    the setting's precision. When it is absent the class's whole-population
    numbers are used, which is the loosest setting.

    The third condition is what withholds the large class. That class is not
    unmeasured; it is measured at a rate that straddles the base rate, and an
    alert that fires on almost every confirmed drift change and is right about
    once in 1,300 is not a warning. Returning the reasons matters as much as
    returning the verdict, so both come back."""
    row = model_class(model, cluster)
    jaccard = row.get("bootstrapJaccard")
    bar = float(model["bars"]["bootstrapJaccard"])
    if point is None:
        quoted, base = row, model["basePopulation"]
        n = int(row["n"])
    else:
        quoted = point
        base = point.get("basePopulationAtThisHorizon") or model["basePopulation"]
        n = int(point.get("alerts") or 0)
    reasons = []
    basis = row.get("stabilityBasis")
    if jaccard is None and basis:
        # a class that is not a cluster -- one the detector's own definition
        # produces -- has no cluster-stability statistic, and requiring one
        # would be a bar it cannot be measured against. The exemption is
        # explicit in the artifact and is never inferred from a missing key.
        pass
    elif jaccard is None or not math.isfinite(float(jaccard)):
        reasons.append("the class has no measured bootstrap stability")
    elif float(jaccard) < bar:
        reasons.append(f"bootstrap Jaccard {float(jaccard):.3f} is below the "
                       f"registered {bar:.2f} bar, so it is not a class")
    if n < MIN_SUPPORT_FOR_A_RATE:
        reasons.append(f"{n} supporting events is below the "
                       f"{MIN_SUPPORT_FOR_A_RATE} a rate needs (design 5.2)")
    if quoted.get("precision") is None or quoted.get("wilson95") is None:
        reasons.append("there is no measured precision to quote")
    elif base.get("precision") is None or base.get("wilson95") is None:
        reasons.append("there is no base rate to compare against")
    ratio = row.get("passiveControlRatio")
    bar = row.get("passiveControlBar")
    if ratio is not None and bar is not None and float(ratio) > float(bar):
        # the shape `pipeline/orbit_events.py` already uses for the word it
        # withholds: a detector that flags objects which physically cannot
        # manoeuvre at anything like the rate it flags ones that can has not
        # earned a clause about what the flag means.
        reasons.append(
            f"its own passive control fires at {float(ratio):.3f} of the "
            f"rate it fires on objects that can manoeuvre, against a design "
            f"target of {float(bar)}; the detector has not earned a clause "
            f"about what its flag means")
    if quoted.get("precision") is None or quoted.get("wilson95") is None:
        pass
    elif float(quoted["wilson95"][0]) <= float(base["wilson95"][1]):
        reasons.append(
            f"its precision {_pct(quoted['precision'])} "
            f"[{_pct(quoted['wilson95'][0])}, {_pct(quoted['wilson95'][1])}] "
            f"is not separated above the base rate "
            f"{_pct(base['precision'])} [{_pct(base['wilson95'][0])}, "
            f"{_pct(base['wilson95'][1])}]; quoting it would be a labelled "
            f"gap dressed as a result")
    return (not reasons), tuple(reasons)


def _base_population(base):
    """The curve stores the base population as n/pos/precision/wilson95; the
    model stores it as n/positives/... One shape for the renderer."""
    out = dict(base)
    if "positives" not in out and "pos" in out:
        out["positives"] = out["pos"]
    return out


def alert_figures(model, cluster, point=None):
    """The numbers an alert of this class, at this setting, is allowed to
    quote -- and the population they were measured on. One place, so the
    renderer and the gate can never quote different ones."""
    row = model_class(model, cluster)
    if point is None:
        return {"settingName": "everything",
                "n": int(row["n"]), "positives": int(row["positives"]),
                "precision": row["precision"], "wilson95": row["wilson95"],
                "arrivalDays": row["arrivalDays"],
                "base": model["basePopulation"],
                "name": row["name"], "description": row["description"],
                "settingDescription": None}
    return {"settingName": point.get("settingName"),
            "n": int(point.get("alerts") or 0),
            "positives": int(point.get("arrivals") or 0),
            "precision": point.get("precision"),
            "wilson95": point.get("wilson95"),
            "arrivalDays": point.get("leadDays") or {},
            "base": _base_population(point.get("basePopulationAtThisHorizon")
                                 or model["basePopulation"]),
            "name": row["name"], "description": row["description"],
            "settingDescription": point.get("description")}


def permitted_vocabulary(model, cluster=None, assessable=True, gap_reason=None,
                         point=None, evidence_failures=()):
    """THE GATE. Returns the words the lane is permitted to use for this one
    assessment, the clauses it is refused and why, the list it may never say
    at all, and the labels it must carry. The renderer may use nothing this
    function did not return.

    `cluster is None` or `assessable is False` is a LABELLED GAP -- 'not
    assessable' -- and never a zero and never a blank (design 5.3).

    `point` is the operating-point setting's row for this class: the gate then
    judges, and the alert then quotes, THAT SETTING'S measured numbers.

    `evidence_failures` are the setting's thresholds this trigger did not
    meet. They are not a gap in the measurement -- the trigger is perfectly
    assessable -- they are a deliberate choice of operating point, and the
    record says so in those terms."""
    permitted = ["caveats"]
    words = list(CLAUSE_WORDS["caveats"])
    withheld = {}
    labels = []
    underpowered = False
    may_alert = False
    figures = None

    if not assessable or cluster is None:
        permitted.append("labelled_gap")
        words.extend(CLAUSE_WORDS["labelled_gap"])
        labels.append("NOT ASSESSABLE")
        withheld["pattern_match"] = (
            "WITHHELD -- "
            + (gap_reason or "the trigger could not be assessed")
            + " (design 5.3: a labelled gap, never a zero and never a blank)")
    else:
        figures = alert_figures(model, cluster, point)
        n = int(figures["n"])
        positives = int(figures["positives"])
        underpowered = bool(n < MIN_SUPPORT_FOR_A_RATE
                            or positives < MIN_SUPPORT_FOR_A_RATE)
        if underpowered:
            labels.append("UNDERPOWERED")
        for clause in ("drift_change", "base_rate", "provenance"):
            permitted.append(clause)
            words.extend(CLAUSE_WORDS[clause])

        if evidence_failures:
            speak, reasons = False, tuple(
                "below this setting's evidence: " + f for f in evidence_failures)
            labels.append("BELOW THIS SETTING'S EVIDENCE")
        else:
            speak, reasons = class_may_be_spoken(model, cluster, point)
        if speak:
            for clause in ("pattern_match", "prior_instances"):
                permitted.append(clause)
                words.extend(CLAUSE_WORDS[clause])
            may_alert = True
            if underpowered:
                withheld["outcome_distribution"] = (
                    f"WITHHELD as a rate -- {positives} supporting outcomes is "
                    f"below {MIN_SUPPORT_FOR_A_RATE}; the count and its "
                    f"interval are quoted and no rate is drawn from them "
                    f"(design 5.2)")
            else:
                for clause in ("outcome_distribution", "running_precision"):
                    permitted.append(clause)
                    words.extend(CLAUSE_WORDS[clause])
        else:
            withheld["pattern_match"] = "WITHHELD -- " + "; ".join(reasons)
            withheld["outcome_distribution"] = (
                "WITHHELD -- the class it would be conditioned on may not be "
                "spoken")
            if "BELOW THIS SETTING'S EVIDENCE" not in labels:
                labels.append("NOT AN ALERT")

    for clause, reason in WITHHELD_REASONS.items():
        withheld[clause] = reason

    return {
        "modelVersion": model["modelVersion"],
        "modelChecksum": model_checksum(model),
        "setting": None if figures is None else figures["settingName"],
        "class": None if cluster is None else int(cluster),
        "assessable": bool(assessable and cluster is not None),
        "permitted": tuple(permitted),
        "permittedWords": tuple(words),
        "withheld": dict(withheld),
        "neverSay": NEVER_SAY,
        "labels": tuple(labels),
        "underpowered": bool(underpowered),
        "mayRaiseAlert": bool(may_alert),
        "caveats": CAVEATS,
        "figures": figures,
        "supportingEvents": None if figures is None else int(figures["n"]),
        "supportingOutcomes": None if figures is None else int(figures["positives"]),
    }


def render_alert(model, assessment, vocabulary, to_date=None):
    """Compose the alert from the permitted clauses and nothing else.

    `to_date` is `(k, n)` measured on THIS lane's ledger (design 11.5); it is
    printed when it exists and labelled as a gap when it does not."""
    lines = []
    if not vocabulary["assessable"]:
        lines.append(
            f"Object NORAD {assessment['norad']}: NOT ASSESSABLE. "
            f"{assessment.get('gapReason') or 'the trigger could not be assessed'}. "
            f"This is a labelled gap, not a statement that nothing happened.")
        lines.append("")
        lines.extend(CAVEATS)
        return "\n".join(lines)

    fig = vocabulary["figures"]
    base = fig["base"]
    lines.append(
        f"Object NORAD {assessment['norad']} executed a drift-rate change of "
        f"{assessment['driftChangeDegPerDay']:+.4f} deg/day, confirmed at "
        f"{_iso(assessment['tTrigMs'])} (second consecutive element set "
        f"showing the change), and announced at "
        f"{_iso(assessment['tAnnounceMs'])} once the change had stopped.")

    if "pattern_match" in vocabulary["permitted"]:
        lines.append("")
        lines.append(
            f"The trigger matches pattern {fig['name']} -- "
            f"{fig['description']}. {fig['n']:,} of the {base['n']:,} "
            f"confirmed drift changes in the archive match it at evidence "
            f"setting '{fig['settingName']}'.")
        if "outcome_distribution" in vocabulary["permitted"]:
            d = fig["arrivalDays"]
            lines.append("")
            lines.append(
                f"In those {fig['n']:,}, the object arrived within 0.1 deg of "
                f"another satellite's mean longitude and stayed there for at "
                f"least 30 days in {fig['positives']} -- "
                f"{_pct(fig['precision'])}, Wilson 95% "
                f"{_pct(fig['wilson95'][0])} to {_pct(fig['wilson95'][1])}. "
                f"Median time from this point to arrival: {d['p50']:.1f} days, "
                f"p25-p75 {d['p25']:.1f} to {d['p75']:.1f} days.")
        else:
            lines.append(
                f"UNDERPOWERED: {fig['positives']} supporting outcomes, below "
                f"{MIN_SUPPORT_FOR_A_RATE}. The count is quoted and no rate is "
                f"drawn from it.")
    else:
        lines.append("")
        lines.append("NOT AN ALERT: " + vocabulary["withheld"]["pattern_match"])

    lines.append("")
    lines.append(
        f"Base rate for a confirmed drift change of any kind: "
        f"{_pct(base['precision'])} ({base['positives']} of {base['n']:,}), "
        f"Wilson 95% {_pct(base['wilson95'][0])} to "
        f"{_pct(base['wilson95'][1])}.")

    if "running_precision" in vocabulary["permitted"]:
        if to_date and int(to_date[1]) > 0:
            lines.append(
                f"Alert class precision to date on this lane: "
                f"{int(to_date[0])}/{int(to_date[1])} resolved.")
        else:
            lines.append(
                "Alert class precision to date on this lane: NOT ASSESSABLE "
                "-- no alert of this class has resolved yet. A labelled gap, "
                "not a zero.")

    if fig.get("settingDescription"):
        lines.append("")
        lines.append(f"Evidence setting '{fig['settingName']}': "
                     f"{fig['settingDescription']}")

    lines.append("")
    lines.extend(CAVEATS)
    lines.append("Pattern assignment is mathematics on public element sets. "
                 "No purpose is attributed.")
    lines.append(f"Frozen model {model['modelVersion']}, checksum "
                 f"{str(model_checksum(model))[:16]}.")
    return "\n".join(lines)


# ==========================================================================
# design 2.3 -- CADENCE, DERIVED AND NOT CHOSEN
# ==========================================================================
def derive_cadence(median_epoch_spacing_days,
                   confirming_element_sets=CITED_CONFIRMING_ELEMENT_SETS,
                   median_causal_lead_days=CITED_MEDIAN_CAUSAL_LEAD_DAYS,
                   host_timer_period_hours=HOST_TIMER_PERIOD_HOURS,
                   spacing_source="cited"):
    """The lane's period is DERIVED from three measured quantities; it is not
    a number somebody liked.

    The detector's own confirmation rule needs `confirming_element_sets`
    consecutive element sets showing the change, so a confirmable change
    cannot become visible sooner than that many median epoch spacings after it
    happens. Re-reading the archive more often than one median spacing
    therefore re-reads element sets that have not changed and cannot make any
    alert earlier: the WORK FLOOR is one median spacing.

    Against the median causal lead, a lane that waits one work floor spends
    `workFloorDays / medianCausalLeadDays` of its warning budget on latency; a
    lane that works on the host timer's own period spends less and buys
    nothing, because the element sets it re-reads have not changed.

    Everything in the returned record is arithmetic on the inputs, and the
    state file carries the record rather than a constant."""
    spacing = float(median_epoch_spacing_days)
    sets = int(confirming_element_sets)
    lead = float(median_causal_lead_days)
    host_days = float(host_timer_period_hours) / 24.0
    visibility = spacing * sets
    work_floor = spacing
    return {
        "inputs": {
            "medianEpochSpacingDays": spacing,
            "medianEpochSpacingSource": spacing_source,
            "confirmingElementSets": sets,
            "medianCausalLeadDays": lead,
            "hostTimerPeriodHours": float(host_timer_period_hours),
        },
        "derivation": [
            f"the confirmation rule needs {sets} consecutive element sets, so "
            f"a confirmable change becomes visible about {visibility:.3f} d "
            f"after it happens ({sets} x {spacing:.3f} d)",
            f"re-reading more often than one median spacing re-reads unchanged "
            f"element sets, so the work floor is {work_floor:.3f} d",
            f"against a median causal lead of {lead:.1f} d, one work floor of "
            f"latency is {100.0 * work_floor / lead:.1f}% of the warning "
            f"budget",
            f"the host timer's own period of {host_timer_period_hours:.1f} h "
            f"is {100.0 * host_days / lead:.1f}% of the same budget and buys "
            f"nothing, because the element sets it would re-read have not "
            f"changed",
            "so: fire on the host timer, and do work only when the object's "
            "newest element-set epoch has advanced",
        ],
        "confirmableVisibilityDays": visibility,
        "workFloorDays": work_floor,
        "workFloorHours": work_floor * 24.0,
        "latencyFractionOfLead": work_floor / lead,
        "hostTimerLatencyFractionOfLead": host_days / lead,
        "rule": ("fire on the host timer; do work only when the object's "
                 "newest element-set epoch has advanced"),
        "citation": f"{DESIGN} section 2.3; the confirmation rule is T8a 5.5",
        "parameter": "--cadence-hours",
    }


# ==========================================================================
# THE CLOCK -- injectable, because a lane that runs later is exercised now
# ==========================================================================
class Clock:
    """Wall clock, or an injected one. The sidecar reads the time from here
    and from nowhere else, so the synthetic exercise of design 11.6 drives the
    same code a live lane would run."""

    def __init__(self, now_ms=None):
        self.injected = now_ms is not None
        self._now = None if now_ms is None else float(now_ms)

    def now_ms(self):
        if self._now is not None:
            return float(self._now)
        return float(time.time() * 1000.0)

    def set(self, now_ms):
        if not self.injected:
            raise RuntimeError("only an injected clock may be set")
        self._now = float(now_ms)

    def record(self):
        return {"mode": "injected" if self.injected else "system",
                "nowMs": self.now_ms(), "nowIso": _iso(self.now_ms())}


# ==========================================================================
# ELEMENT SOURCES -- read-only, both of them
# ==========================================================================
class ArchiveSource:
    """The live path of design 2.2: one indexed read per watched object
    against `element_set`, whose PRIMARY KEY (norad, epoch_ms) WITHOUT ROWID
    makes the table its own index. The handle is opened `mode=ro` and set
    `query_only`, so this class cannot write to the archive by mistake.

    `object_type` is the only catalogue column read, and it is read only for
    the active/passive class the detector was measured on."""

    kind = "archive"

    def __init__(self, archive=ta.ARCHIVE):
        self.archive = Path(archive)
        self.db = sqlite3.connect(f"file:{self.archive}?mode=ro", uri=True)
        self.db.execute("PRAGMA query_only = 1")

    def close(self):
        self.db.close()

    def classes(self, norads):
        return ta.object_classes(self.db, sorted(int(n) for n in norads))

    def series(self, norad, upto_ms):
        rows = self.db.execute(
            "SELECT epoch_ms, mean_motion_q, eccentricity_q, inclination_q, "
            "raan_q, arg_perigee_q, mean_anomaly_q FROM element_set "
            "WHERE norad = ? AND epoch_ms <= ? ORDER BY epoch_ms",
            (int(norad), int(upto_ms))).fetchall()
        if len(rows) < 2:
            return None
        cols = list(zip(*rows))
        return pg.Series(int(norad),
                         np.asarray(cols[0], dtype=np.int64),
                         np.asarray(cols[1], dtype=np.float64) / pg.SCALE_MM,
                         np.asarray(cols[2], dtype=np.float64) / pg.SCALE_ECC,
                         np.asarray(cols[3], dtype=np.float64) / pg.SCALE_ANGLE,
                         np.asarray(cols[4], dtype=np.float64) / pg.SCALE_ANGLE,
                         np.asarray(cols[5], dtype=np.float64) / pg.SCALE_ANGLE,
                         np.asarray(cols[6], dtype=np.float64) / pg.SCALE_ANGLE)

    def watch_list(self):
        """The near-GEO watch, built from the cached extract when its three
        published numbers assert -- that population is exactly the one every
        figure in the frozen artifact was measured on."""
        arrays, meta = ta.load_cached_extract(self.db)
        norads = np.unique(arrays["norad"]).astype(np.int64)
        del arrays
        return [int(n) for n in norads], {
            "source": meta.get("source"),
            "objectsKept": int(meta.get("objectsKept", norads.size)),
            "sha256": meta.get("sha256")}


class ExtractSource:
    """The replay path: the same near-GEO element sets, already extracted, so
    a multi-year replay does not re-read 217 million archive rows once per
    simulated day. Memory-heavy by construction and therefore confined to the
    machine that holds the archive."""

    kind = "extract"

    def __init__(self, archive=ta.ARCHIVE, extract_dir=ta.EXTRACT_DIR):
        db = sqlite3.connect(f"file:{archive}?mode=ro", uri=True)
        db.execute("PRAGMA query_only = 1")
        arrays, self.meta = ta.load_cached_extract(db, extract_dir)
        self.series_by_norad = {s.norad: s for s in pg.build_series(arrays)}
        del arrays
        self._classes = ta.object_classes(db, sorted(self.series_by_norad))
        db.close()

    def close(self):
        pass

    def classes(self, norads):
        return {int(n): self._classes.get(int(n)) for n in norads}

    def watch_list(self):
        return sorted(self.series_by_norad), {
            "source": self.meta.get("source"),
            "objectsKept": int(self.meta.get("objectsKept", 0)),
            "sha256": self.meta.get("sha256")}

    def series(self, norad, upto_ms):
        s = self.series_by_norad.get(int(norad))
        if s is None:
            return None
        j = int(np.searchsorted(s.epoch_ms, upto_ms, side="right"))
        if j < 2:
            return None
        return TruncatedSeries(s, j)


class TruncatedSeries:
    """A window onto an already-built series, holding nothing at or after the
    cut. It carries the attribute names the detector reads and nothing else,
    so a feature path cannot reach past the clock through it."""

    __slots__ = ("norad", "epoch_ms", "lam", "lam_unwrapped", "drift", "inc",
                 "ecc", "grid_lo", "grid")

    def __init__(self, s, j):
        self.norad = int(s.norad)
        self.epoch_ms = s.epoch_ms[:j]
        self.lam = s.lam[:j]
        self.lam_unwrapped = s.lam_unwrapped[:j]
        self.drift = s.drift[:j]
        self.inc = s.inc[:j]
        self.ecc = s.ecc[:j]
        self.grid_lo = None
        self.grid = None


# ==========================================================================
# Flag computation, and the memo the replay uses
# ==========================================================================
class DirectFlags:
    """The live path: compute the flag chain from the truncated series the
    source just returned. This is `trigger_alarm.flag_baselines` and nothing
    else."""

    def flags(self, series, sigma_n, now_ms):
        return ta.flag_baselines(series, sigma_n)


class MemoisedFlags:
    """The replay path, and a memo that has to earn its place.

    `flag_baselines` confirms a flag at element set `i` from the trailing
    baseline over the ten sets before `i`, and from the departures at `i - 1`
    and `i` alone. A flag's existence therefore depends on no element set
    after it, and the flags of a series truncated at time `t` are exactly the
    flags of the whole series whose epoch is at most `t`. That identity is
    what makes computing each object's flags ONCE, from its whole history, and
    then cutting them at the clock legitimate rather than a leak --
    `tests/test_alarm_lane.py` asserts the identity on a fixture instead of
    assuming it, including against a series whose tail is replaced.

    It exists because a multi-year replay would otherwise recompute a
    ten-sample rolling median over every object's whole history on every
    simulated day, which costs more than everything else in the lane put
    together."""

    def __init__(self, full_series_by_norad):
        self.full = full_series_by_norad
        self.cache = {}

    def flags(self, series, sigma_n, now_ms):
        key = int(series.norad)
        if key not in self.cache:
            whole = self.full.get(key, series)
            self.cache[key] = ta.flag_baselines(whole, sigma_n)
        flag_ms, sizes, bases = self.cache[key]
        j = int(np.searchsorted(flag_ms, now_ms, side="right"))
        return flag_ms[:j], sizes[:j], bases[:j]


# ==========================================================================
# design 11.4 -- THE SIDECAR
# ==========================================================================
def _blank_state(model, cadence):
    return {
        "artifact": "alarm-lane-state",
        "schema": 1,
        "design": DESIGN,
        "model": {"version": model["modelVersion"],
                  "checksum": model_checksum(model),
                  "path": str(MODEL_PATH.relative_to(_REPO))},
        "cadence": cadence,
        "lookBackFloorDays": LOOK_BACK_FLOOR_DAYS,
        "lookBackPolicy": ("the whole per-object element history up to the "
                           "clock, which is at least the floor the design "
                           "requires"),
        "reservedDecisions": dict(RESERVED_DECISIONS),
        "reservedNote": RESERVED_NOTE,
        "runs": 0,
        "lastRunAtMs": None,
        "lastRunAtIso": None,
        "clock": None,
        "watch": None,
        "lastEpochMsByNorad": {},
        "lastAnnouncedMsByNorad": {},
        "counters": {"firings": 0, "objectsRead": 0,
                     "objectsSkippedNoAdvance": 0, "triggersAssessed": 0,
                     "alertsRaised": 0, "notAssessable": 0,
                     "withheldByClass": 0},
    }


def load_state(path, model, cadence):
    path = Path(path)
    if not path.exists():
        return _blank_state(model, cadence)
    state = json.loads(path.read_text())
    state["cadence"] = cadence
    frozen = model_checksum(model)
    if state.get("model", {}).get("checksum") not in (None, frozen):
        raise FrozenModelError(
            "the state file was written by a different frozen model "
            f"({state['model'].get('version')} / "
            f"{str(state['model'].get('checksum'))[:16]}). A precision figure "
            "must name the model that earned it, so the lane refuses to "
            "continue a ledger under a new model: start a new state file and "
            "a new ledger.")
    state["model"] = {"version": model["modelVersion"], "checksum": frozen,
                      "path": str(MODEL_PATH.relative_to(_REPO))}
    return state


def save_state(state, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(state, indent=1, sort_keys=True) + "\n")


LEDGER_PROVENANCE = {
    "record": "provenance",
    "artifact": "alarm-lane-ledger",
    "schema": 1,
    "design": DESIGN,
    "note": ("append-only. Every assessment is counted here, including the "
             "alerts that did not pan out (design 7.9). Nothing in this file "
             "is published, sent or surfaced."),
    "caveats": list(CAVEATS),
    "neverSay": list(NEVER_SAY),
    "reservedDecisions": dict(RESERVED_DECISIONS),
}


def ledger_append(path, records):
    if not records:
        return 0
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fresh = not Path(path).exists()
    with open(path, "a") as fh:
        if fresh:
            fh.write(json.dumps(LEDGER_PROVENANCE, sort_keys=True) + "\n")
        for rec in records:
            fh.write(json.dumps(rec, sort_keys=True, allow_nan=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return len(records)


def ledger_read(path):
    path = Path(path)
    if not path.exists():
        return []
    out = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def measured_epoch_spacing_days(series_list):
    """The median element-set spacing the lane ACTUALLY saw, so the cadence
    record in the state file is derived from this run's own data and not only
    from the cited figure."""
    gaps = []
    for s in series_list:
        if s is None or s.epoch_ms.size < 2:
            continue
        d = np.diff(np.asarray(s.epoch_ms, dtype=np.float64)) / DAY_MS
        d = d[np.isfinite(d) & (d > 0)]
        if d.size:
            gaps.append(d)
    if not gaps:
        return None
    return float(np.median(np.concatenate(gaps)))


class Sidecar:
    """One firing of the lane.

    Reads the watched objects' element sets up to the clock, skips the
    detector work for every object whose newest epoch has not advanced since
    the last firing (the derived cadence rule), chains the confirmed
    drift-rate flags, announces every chain whose announce time has arrived,
    classifies each announced chain against the FROZEN artifact, asks the
    vocabulary gate what may be said, and returns the records. It writes
    nothing anywhere: the caller appends them to the ledger."""

    def __init__(self, model, source, clock, state, events=None,
                 flags=None, occupancy=None, setting=None, tick_days=None):
        self.model = model
        # the OPERATING POINT this lane is running at. `None` is the loosest
        # one: no evidence threshold beyond the detector's own, and the
        # class's whole-population figures.
        self.setting = setting
        self.point = (setting or {}).get("point") or {}
        self.tick_days = float(tick_days) if tick_days else None
        self.source = source
        self.clock = clock
        self.state = state
        self.sigma_n = float(model["detector"]["sigmaNDegPerDay"])
        state.setdefault("pending", {})
        state.setdefault("setting", None)
        if setting is not None:
            state["setting"] = {"name": setting["name"],
                                "point": dict(setting["point"]),
                                "tradeoff": setting.get("tradeoff"),
                                "tickDays": self.tick_days}
        self.flags = flags or DirectFlags()
        self.occupancy = occupancy
        self.events = list(events or [])
        self._event_ends = {}
        for e in self.events:
            self._event_ends.setdefault(int(e["approacherNorad"]), []).append(
                (float(e["loiterEndMs"]), int(e["targetNorad"])))
        for v in self._event_ends.values():
            v.sort()
        self._watch = None
        self._classes = None
        # per-object flag chains, rebuilt only when the object's flag count
        # changes. A chain's membership depends on no element set after its
        # own last flag, so a chain once closed cannot change; re-chaining
        # every object on every firing would be the whole cost of the lane.
        self._chains = {}
        # the element-set spacing is measured once and then carried in the
        # state file; re-measuring it over every history on every firing
        # would cost more than the detector does
        self._measure_spacing = True

    # -- the watch ---------------------------------------------------------
    def watch(self):
        if self._watch is None:
            watch, meta = self.source.watch_list()
            self._watch = [int(n) for n in watch]
            self._classes = self.source.classes(self._watch)
            self.state["watch"] = dict(meta, n=len(self._watch))
        return self._watch

    # -- the cadence gate --------------------------------------------------
    def _advanced(self, norad, newest_ms):
        prev = self.state["lastEpochMsByNorad"].get(str(int(norad)))
        return prev is None or float(newest_ms) > float(prev)

    # -- the cadence block, causal by construction -------------------------
    def _cadence_features(self, norad, t_trig, prior_triggers, prev_trigger_ms):
        rows = [r for r in self._event_ends.get(int(norad), []) if r[0] < t_trig]
        return {
            "cad_days_since_prev_trigger": (
                float((t_trig - prev_trigger_ms) / DAY_MS)
                if prev_trigger_ms is not None else float("nan")),
            "miss_prev_trigger": float(prev_trigger_ms is None),
            "cad_prior_triggers": float(prior_triggers),
            "cad_prior_events": float(len(rows)),
            "cad_prior_targets": float(len({r[1] for r in rows})),
        }

    def fire(self):
        now = self.clock.now_ms()
        watch = self.watch()
        read = skipped = 0
        announced = []
        seen = []
        series_by_norad = {}
        need_series = self.occupancy is None
        need_spacing = self._measure_spacing
        for norad in watch:
            active = self._classes.get(int(norad)) == "active"
            if not (active or need_series or need_spacing):
                continue
            s = self.source.series(int(norad), now)
            if s is None or s.epoch_ms.size < 2:
                continue
            if need_series:
                # the occupancy table of the registered definition is built
                # from EVERY watched object's pre-clock state, whatever class
                # the object is
                series_by_norad[int(norad)] = s
            if need_spacing:
                seen.append(s)
            if not active:
                continue
            newest = float(s.epoch_ms[-1])
            key = str(int(norad))
            cached = self._chains.get(key)
            if self._advanced(norad, newest) or cached is None:
                # the DERIVED CADENCE RULE of design 2.3, and the only thing
                # it governs: the detector work. An object whose newest epoch
                # has not advanced cannot have gained a flag, so re-running
                # the baseline over its history would re-read element sets
                # that have not changed.
                read += 1
                self.state["lastEpochMsByNorad"][key] = newest
                flag_ms, sizes, bases = self.flags.flags(s, self.sigma_n, now)
                if cached is None or cached[0] != int(flag_ms.size):
                    chains = ta.chain_flags(flag_ms, sizes, bases)
                    cached = (int(flag_ms.size), chains,
                              np.asarray([c[1] for c in chains],
                                         dtype=np.float64))
                    self._chains[key] = cached
            else:
                # the announcement scan below still runs. A chain already
                # detected becomes announceable five days after it closed, and
                # making that wait on the object's NEXT element set would
                # charge the cadence gate for latency it does not cause.
                skipped += 1
            _n, chains, chain_trigs = cached
            last_announced = self.state["lastAnnouncedMsByNorad"].get(key)
            i = (0 if last_announced is None
                 else int(np.searchsorted(chain_trigs, float(last_announced),
                                          side="right")))
            newest_announced = last_announced
            while i < len(chains):
                t_first, t_trig, stages, size, base = chains[i]
                trig = ta.Trigger(norad, t_first, t_trig, stages, size, base)
                if trig.tAnnounce > now:
                    break
                announced.append((trig, s, i,
                                  chains[i - 1][1] if i > 0 else None))
                newest_announced = t_trig
                i += 1
            if newest_announced is not None:
                self.state["lastAnnouncedMsByNorad"][key] = newest_announced

        announced.sort(key=lambda r: (r[0].tTrig, r[0].norad))
        records = self._assess(announced, series_by_norad)

        spacing = measured_epoch_spacing_days(seen) if need_spacing else None
        if spacing is not None:
            self._measure_spacing = False
            self.state["cadence"] = derive_cadence(
                spacing,
                spacing_source=(f"measured on this firing over {len(seen)} "
                                f"watched objects' element sets"))
            self.state["cadence"]["citedComparison"] = {
                "medianEpochSpacingDays": CITED_EPOCH_SPACING_DAYS,
                "citation": f"{DESIGN} section 2.3"}
        c = self.state["counters"]
        c["firings"] += 1
        c["objectsRead"] += read
        c["objectsSkippedNoAdvance"] += skipped
        c["triggersAssessed"] += len(records)
        c["alertsRaised"] += sum(1 for r in records if r["spoken"])
        c["notAssessable"] += sum(1 for r in records if not r["assessable"])
        c["withheldByClass"] += sum(
            1 for r in records if r["assessable"] and not r["spoken"])
        self.state["runs"] += 1
        self.state["lastRunAtMs"] = now
        self.state["lastRunAtIso"] = _iso(now)
        self.state["clock"] = self.clock.record()
        return records

    def _evidence_failures(self, trig, features):
        """The operating point's thresholds this trigger does not meet. They
        are a choice of operating point, not a gap in the measurement."""
        out = []
        floor = self.point.get("minDriftChangeDegPerDay")
        if floor is not None and abs(float(trig.driftChange)) < float(floor):
            out.append(f"the drift-rate change is "
                       f"{abs(float(trig.driftChange)):.4f} deg/day, below "
                       f"this setting's {float(floor)} deg/day")
        slots = self.point.get("minSlotsReached")
        if slots is not None:
            have = float(features.get("fwd_slots_reached") or 0.0)
            if have < float(slots):
                out.append(f"the propagated path passes {have:.0f} occupied "
                           f"mean longitudes, below this setting's "
                           f"{float(slots):.0f}")
        return out

    def _persistence_ok(self, norad, t_check, series_by_norad):
        """Is the object still drifting at or above the detector's floor at
        `t_check`, judged on its newest element set at that moment? Reads
        nothing later than `t_check`."""
        s = series_by_norad.get(int(norad))
        if s is None:
            s = self.source.series(int(norad), t_check)
        if s is None or s.epoch_ms.size == 0:
            return None
        j = int(np.searchsorted(s.epoch_ms, t_check, side="right")) - 1
        if j < 0 or (t_check - float(s.epoch_ms[j])) > ta.MERGE_DAYS * DAY_MS:
            return None
        floor = float(self.model["detector"]["floorDegPerDay"])
        return bool(abs(float(s.drift[j])) >= floor)

    def _sweeps(self):
        return int(self.point.get("persistenceSweeps") or 1)

    def _assess(self, announced, series_by_norad):
        occupancy = self.occupancy
        if occupancy is None:
            if not series_by_norad:
                series_by_norad = {}
            occupancy = (ta.OccupancySweep(series_by_norad)
                         if series_by_norad else None)
        out, feats, keep = [], [], []
        for trig, series, prior, prev_ms in announced:
            view = ta.causal_view(series, trig.tTrig)
            gap = self._gap_reason(view, trig)
            if gap is not None:
                out.append(self._gap_record(trig, gap))
                continue
            if occupancy is None:
                out.append(self._gap_record(
                    trig, "no occupancy table could be built for this firing"))
                continue
            f = ta.trigger_features(trig, view,
                                    occupancy.at(trig.tTrig, trig.norad))
            f.update(self._cadence_features(trig.norad, trig.tTrig, prior,
                                            prev_ms))
            feats.append(f)
            keep.append((trig, f))
        if feats:
            for (trig, f), cluster in zip(keep, classify(feats, self.model)):
                out.append(self._record(trig, int(cluster), f,
                                        series_by_norad))
        out.extend(self._advance_pending(series_by_norad))
        out = [r for r in out if r is not None]
        out.sort(key=lambda r: (r["tTrigMs"], r["norad"]))
        return out

    def _advance_pending(self, series_by_norad):
        """design: a setting with `persistenceSweeps` above one waits for the
        object to still be drifting at the next firings. A trigger that stops
        drifting is WITHDRAWN and recorded as withdrawn -- never dropped in
        silence (design 7.9)."""
        now = self.clock.now_ms()
        out = []
        for alert_id, rec in list(self.state["pending"].items()):
            if float(rec["nextCheckMs"]) > now:
                continue
            ok = self._persistence_ok(rec["norad"], float(rec["nextCheckMs"]),
                                      series_by_norad)
            if ok is None:
                rec["checksMissing"] = int(rec.get("checksMissing", 0)) + 1
                ok = False
                reason = ("no element set within the merge window at the "
                          "persistence check, so the check could not be made")
            else:
                reason = ("the object was no longer drifting at or above the "
                          "detector's floor at the persistence check")
            if not ok:
                del self.state["pending"][alert_id]
                out.append(self._withdrawn(rec, reason))
                continue
            rec["checksPassed"] = int(rec["checksPassed"]) + 1
            if rec["checksPassed"] >= self._sweeps() - 1:
                del self.state["pending"][alert_id]
                out.append(self._speak(rec))
            else:
                rec["nextCheckMs"] = float(rec["nextCheckMs"]) + \
                    float(rec["tickMs"])
        return out

    def _gap_reason(self, view, trig):
        """design 5.3 -- an object with no usable look-back, or an
        element-set gap across the trigger longer than the merge window, is
        NOT ASSESSABLE. So is a trigger outside the population the frozen
        figures were measured on."""
        ep = np.asarray(view.epoch_ms, dtype=np.float64)
        if ep.size < pg.BURN_BASELINE_SAMPLES + 2:
            return ("the look-back holds fewer element sets than the baseline "
                    "window needs")
        if (float(ep[-1]) - float(ep[0])) / DAY_MS < pg.STATION_MIN_DAYS:
            return (f"the usable look-back is "
                    f"{(float(ep[-1]) - float(ep[0])) / DAY_MS:.1f} d, shorter "
                    f"than the {pg.STATION_MIN_DAYS:.0f} d of history the slot "
                    f"definition needs")
        window = ep[ep >= trig.tFirst - ta.MERGE_DAYS * DAY_MS]
        if window.size >= 2:
            worst = float(np.max(np.diff(window))) / DAY_MS
            if worst > ta.MERGE_DAYS:
                return (f"an element-set gap of {worst:.1f} d across the "
                        f"trigger, longer than the {ta.MERGE_DAYS:.0f} d merge "
                        f"window")
        if not trig.eligible:
            return ("the object was not at a slot when it moved: its baseline "
                    "drift rate is outside the eligibility floor, so this "
                    "trigger is outside the population every frozen figure "
                    "was measured on")
        return None

    def _base_record(self, trig):
        return {
            "alertId": uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"alarm-lane/{self.model['modelVersion']}/{trig.norad}/"
                f"{int(trig.tTrig)}").hex,
            "norad": int(trig.norad),
            "tFirstMs": float(trig.tFirst),
            "tTrigMs": float(trig.tTrig),
            "tTrigIso": _iso(trig.tTrig),
            "tAnnounceMs": float(trig.tAnnounce),
            "tAnnounceIso": _iso(trig.tAnnounce),
            "announcedAtMs": float(self.clock.now_ms()),
            "driftChangeDegPerDay": float(trig.driftChange),
            "baselineDriftDegPerDay": (float(trig.driftBase)
                                       if np.isfinite(trig.driftBase) else None),
            "stages": int(trig.stages),
            "eligible": bool(trig.eligible),
            "modelVersion": self.model["modelVersion"],
            "modelChecksum": model_checksum(self.model),
            "gapReason": None,
        }

    def _gap_record(self, trig, reason):
        vocab = permitted_vocabulary(self.model, None, assessable=False,
                                     gap_reason=reason)
        assessment = self._base_record(trig)
        assessment["gapReason"] = reason
        rec = dict(assessment)
        rec["record"] = "assessment"
        rec["assessable"] = False
        rec["class"] = None
        rec["spoken"] = False
        rec["vocabulary"] = _vocab_record(vocab)
        rec["text"] = render_alert(self.model, assessment, vocab)
        rec["resolution"] = {"state": "not-assessed"}
        rec["setting"] = (self.setting or {}).get("name", "everything")
        return rec

    def _record(self, trig, cluster, features, series_by_norad):
        base = self._base_record(trig)
        base["class"] = int(cluster)
        base["className"] = model_class(self.model, cluster)["name"]
        base["evidenceFailures"] = self._evidence_failures(trig, features)
        base["setting"] = (self.setting or {}).get("name", "everything")
        base["settingPoint"] = dict(self.point)
        sweeps = self._sweeps()
        if base["evidenceFailures"] or sweeps <= 1:
            return self._speak(base)
        # the setting waits. Nothing is spoken and nothing is ledgered until
        # the persistence checks have run, and a withdrawal is recorded.
        tick_ms = float(self.tick_days or
                        self.state["cadence"]["workFloorDays"]) * DAY_MS
        pending = dict(base)
        pending["checksPassed"] = 0
        pending["tickMs"] = tick_ms
        pending["nextCheckMs"] = float(trig.tAnnounce) + tick_ms
        pending["sweepsRequired"] = sweeps
        self.state["pending"][base["alertId"]] = pending
        return None

    def _speak(self, base):
        """Turn an assessment into its ledger record, at this operating
        point, with the gate's verdict attached."""
        cluster = int(base["class"])
        point = setting_class_row(self.setting, cluster)
        if point is not None:
            point = dict(point, settingName=self.setting["name"])
        vocab = permitted_vocabulary(
            self.model, cluster, assessable=True, point=point,
            evidence_failures=tuple(base.get("evidenceFailures") or ()))
        fig = vocab["figures"]
        rec = dict(base)
        rec["record"] = "assessment"
        rec["assessable"] = True
        rec["announcedAtMs"] = float(self.clock.now_ms())
        rec["classSupport"] = int(fig["n"])
        rec["classPositives"] = int(fig["positives"])
        rec["classPrecision"] = fig["precision"]
        rec["classWilson95"] = fig["wilson95"]
        rec["classArrivalDays"] = dict(fig["arrivalDays"])
        rec["populationN"] = int(fig["base"]["n"])
        rec["populationPrecision"] = fig["base"].get("precision")
        rec["populationWilson95"] = fig["base"].get("wilson95")
        rec["horizonDays"] = float(self.point.get("leadHorizonDays")
                                   or self.model["detector"]["horizonDays"])
        rec["resolveByMs"] = float(base["tTrigMs"]) + rec["horizonDays"] * DAY_MS
        rec["spoken"] = bool(vocab["mayRaiseAlert"])
        rec["vocabulary"] = _vocab_record(vocab)
        rec["resolution"] = {"state": "pending"}
        rec["text"] = (render_alert(self.model, base, vocab)
                       if vocab["mayRaiseAlert"] else None)
        for key in ("checksPassed", "tickMs", "nextCheckMs", "sweepsRequired",
                    "checksMissing"):
            rec.pop(key, None)
        if base.get("checksPassed") is not None:
            rec["persistence"] = {"sweepsRequired": base.get("sweepsRequired"),
                                  "checksPassed": base.get("checksPassed")}
        return rec

    def _withdrawn(self, pending, reason):
        """A trigger that failed a persistence check. It is RECORDED, because
        a lane that quietly forgets the alerts it nearly raised cannot be
        audited (design 7.9)."""
        rec = dict(pending)
        rec["record"] = "assessment"
        rec["assessable"] = True
        rec["spoken"] = False
        rec["withdrawn"] = True
        rec["withdrawnReason"] = reason
        rec["announcedAtMs"] = float(self.clock.now_ms())
        rec["resolution"] = {"state": "withdrawn"}
        rec["text"] = None
        rec["persistence"] = {"sweepsRequired": pending.get("sweepsRequired"),
                              "checksPassed": pending.get("checksPassed")}
        for key in ("checksPassed", "tickMs", "nextCheckMs", "sweepsRequired",
                    "checksMissing"):
            rec.pop(key, None)
        return rec


def _vocab_record(vocab):
    """What the ledger keeps of the gate's verdict. The standing withheld list
    and the full word list live once, in the frozen artifact and in the
    ledger's provenance record; the row keeps the verdict and the reason this
    particular assessment was or was not spoken."""
    return {
        "setting": vocab.get("setting"),
        "permitted": list(vocab["permitted"]),
        "labels": list(vocab["labels"]),
        "underpowered": bool(vocab["underpowered"]),
        "mayRaiseAlert": bool(vocab["mayRaiseAlert"]),
        "patternClause": vocab["withheld"].get("pattern_match", "PERMITTED"),
    }


# ==========================================================================
# design 11.5 -- THE LEDGER'S OWN AUDIT
# ==========================================================================
def resolve_ledger(records, events, horizon_days=None):
    """Attach the outcome to every assessment whose horizon has closed, by the
    same rule the frozen precision was measured under: an arrival attributed
    to a flag inside this chain, arriving after the announce.

    Where the outcome record cannot speak -- because it ends before the
    alert's horizon does -- the resolution is a LABELLED GAP, never a miss and
    never a zero."""
    by_obj = {}
    record_end = 0.0
    for e in events:
        by_obj.setdefault(int(e["approacherNorad"]), []).append(e)
        record_end = max(record_end, float(e["arrivalMs"]))
    out = []
    for rec in records:
        if rec.get("record") != "assessment" or not rec.get("assessable"):
            continue
        if rec.get("withdrawn"):
            # it was never an alert: the operating point withdrew it before it
            # was spoken, and the withdrawal is already on the record
            continue
        h = float(horizon_days if horizon_days is not None
                  else rec.get("horizonDays", 180.0))
        close = float(rec["tTrigMs"]) + h * DAY_MS
        matches = [e for e in by_obj.get(int(rec["norad"]), [])
                   if e.get("initiatingFlagMs") is not None
                   and float(rec["tFirstMs"]) <= float(e["initiatingFlagMs"])
                   <= float(rec["tTrigMs"])]
        after = [e for e in matches
                 if float(e["arrivalMs"]) > float(rec["tAnnounceMs"])]
        if after:
            best = min(after, key=lambda e: float(e["arrivalMs"]))
            out.append({"record": "resolution", "alertId": rec["alertId"],
                        "class": rec.get("class"),
                        "state": "arrival",
                        "arrivalMs": float(best["arrivalMs"]),
                        "arrivalIso": _iso(best["arrivalMs"]),
                        "leadDays": (float(best["arrivalMs"])
                                     - float(rec["tAnnounceMs"])) / DAY_MS,
                        "rule": ("an attributed arrival after the announce, "
                                 "within the frozen horizon")})
        elif record_end < close:
            out.append({"record": "resolution", "alertId": rec["alertId"],
                        "class": rec.get("class"),
                        "state": "not-assessable",
                        "rule": ("the outcome record ends before this alert's "
                                 "horizon closes: a labelled gap, not a miss")})
        else:
            out.append({"record": "resolution", "alertId": rec["alertId"],
                        "class": rec.get("class"),
                        "state": "none",
                        "arrivedBeforeAnnounce": bool(matches and not after),
                        "rule": ("the horizon closed with no attributed "
                                 "arrival after the announce")})
    return out


def audit_ledger(records, model=None):
    """design 11.5 -- the running precision measured on THIS lane.

    Nothing here is borrowed from the offline run: every count comes from the
    ledger. The frozen figure is printed BESIDE it, labelled as the figure the
    model earned elsewhere, so that the two can never be confused."""
    resolutions = {r["alertId"]: r for r in records
                   if r.get("record") == "resolution"}
    alerts = [r for r in records if r.get("record") == "assessment"]
    spoken = [r for r in alerts if r.get("spoken")]

    by_class = {}
    for rec in alerts:
        key = rec.get("class")
        key = "not-assessable" if key is None else int(key)
        row = by_class.setdefault(key, {
            "class": key, "assessed": 0, "spoken": 0, "resolved": 0,
            "arrivals": 0, "none": 0, "notAssessable": 0, "pending": 0,
            "withdrawn": 0, "belowEvidence": 0, "leadDays": []})
        row["assessed"] += 1
        row["spoken"] += 1 if rec.get("spoken") else 0
        if rec.get("withdrawn"):
            row["withdrawn"] += 1
        if rec.get("evidenceFailures"):
            row["belowEvidence"] += 1
        res = resolutions.get(rec["alertId"]) or rec.get("resolution") \
            or {"state": "pending"}
        state = res.get("state", "pending")
        if state == "arrival":
            row["resolved"] += 1
            row["arrivals"] += 1
            if res.get("leadDays") is not None:
                row["leadDays"].append(float(res["leadDays"]))
        elif state == "none":
            row["resolved"] += 1
            row["none"] += 1
        elif state in ("not-assessable", "not-assessed", "withdrawn"):
            row["notAssessable"] += 1
        else:
            row["pending"] += 1

    rows = []
    for key in sorted(by_class, key=lambda k: (isinstance(k, str), str(k))):
        row = by_class[key]
        n, k = row["resolved"], row["arrivals"]
        lo, hi = ta.wilson(k, n) if n else (float("nan"), float("nan"))
        leads = sorted(row["leadDays"])
        row["precisionOnThisLane"] = (k / n) if n else None
        row["wilson95"] = [lo if n and math.isfinite(lo) else None,
                           hi if n and math.isfinite(hi) else None]
        row["underpowered"] = bool(n < MIN_SUPPORT_FOR_A_RATE)
        if n == 0:
            row["precisionLabel"] = ("NOT ASSESSABLE -- no assessment of this "
                                     "class has resolved yet; a labelled gap, "
                                     "not a zero")
        elif row["underpowered"]:
            row["precisionLabel"] = (
                f"UNDERPOWERED -- {k}/{n} resolved, below "
                f"{MIN_SUPPORT_FOR_A_RATE}; the count is quoted and no rate "
                f"is drawn from it")
        else:
            row["precisionLabel"] = f"{k}/{n} = {100.0 * k / n:.3f}%"
        row["leadDays"] = {
            "n": len(leads),
            "p25": float(np.percentile(leads, 25)) if leads else None,
            "p50": float(np.percentile(leads, 50)) if leads else None,
            "p75": float(np.percentile(leads, 75)) if leads else None,
            "min": leads[0] if leads else None,
            "max": leads[-1] if leads else None,
            "label": ("NOT ASSESSABLE -- no resolved arrival yet; a labelled "
                      "gap" if not leads else "measured on this lane"),
        }
        if model is not None and isinstance(key, int):
            frozen = model_class(model, key)
            row["frozenFigure"] = {
                "precision": frozen["precision"],
                "wilson95": frozen["wilson95"],
                "n": frozen["n"], "positives": frozen["positives"],
                "arrivalDaysP50": frozen["arrivalDays"].get("p50"),
                "label": ("the figure this model earned on the offline "
                          "population, printed beside the lane's own and "
                          "never in place of it")}
        rows.append(row)

    return {
        "artifact": "alarm-lane-ledger-audit",
        "schema": 1,
        "design": DESIGN,
        "modelVersion": None if model is None else model["modelVersion"],
        "modelChecksum": None if model is None else model_checksum(model),
        "setting": next((r.get("setting") for r in alerts
                         if r.get("setting")), "everything"),
        "assessments": len(alerts),
        "alertsRaised": len(spoken),
        "resolutions": len(resolutions),
        "classes": rows,
        "caveats": list(CAVEATS),
        "neverSay": list(NEVER_SAY),
        "reservedDecisions": dict(RESERVED_DECISIONS),
        "reservedNote": RESERVED_NOTE,
    }


def audit_report(audit):
    """The printed form. Both structural caveats appear on it, always."""
    out = ["ALARM LANE -- LEDGER AUDIT",
           f"model {audit['modelVersion']} checksum "
           f"{str(audit['modelChecksum'])[:16]}",
           f"operating point: {audit.get('setting')}",
           f"{audit['assessments']} assessments, {audit['alertsRaised']} "
           f"alerts raised, {audit['resolutions']} resolutions folded in", ""]
    for row in audit["classes"]:
        out.append(f"  class {row['class']}: assessed {row['assessed']}, "
                   f"spoken {row['spoken']}, resolved {row['resolved']} "
                   f"(arrivals {row['arrivals']}, none {row['none']}, "
                   f"not assessable {row['notAssessable']}, "
                   f"pending {row['pending']}, "
                   f"withdrawn {row.get('withdrawn', 0)}, "
                   f"below this setting's evidence "
                   f"{row.get('belowEvidence', 0)})")
        out.append(f"      precision on this lane: {row['precisionLabel']}")
        if row["wilson95"][0] is not None:
            out.append(f"      Wilson 95%: {_pct(row['wilson95'][0])} to "
                       f"{_pct(row['wilson95'][1])}")
        lead = row["leadDays"]
        out.append("      lead days: " + (
            f"n={lead['n']} p25 {lead['p25']:.1f} p50 {lead['p50']:.1f} "
            f"p75 {lead['p75']:.1f}" if lead["n"] else lead["label"]))
        frozen = row.get("frozenFigure")
        if frozen:
            if frozen.get("precision") is None:
                out.append("      frozen figure: NOT ASSESSABLE -- this arm's "
                           "own trigger has no measured precision yet; a "
                           "labelled gap, not a zero")
            else:
                lead = frozen.get("arrivalDaysP50")
                out.append(
                    f"      frozen figure (earned offline, beside and not "
                    f"instead): {frozen['positives']}/{frozen['n']} = "
                    f"{_pct(frozen['precision'])}, median lead "
                    + (f"{lead:.1f} d" if lead is not None
                       else "NOT ASSESSABLE"))
        out.append("")
    out.append("CAVEATS, printed and not linked:")
    out.extend(f"  - {c}" for c in audit["caveats"])
    out.append("")
    out.append("RESERVED OPERATOR DECISIONS, none taken: "
               + ", ".join(sorted(audit["reservedDecisions"])))
    return "\n".join(out)


# ==========================================================================
# `freeze` -- build the frozen artifact from the measured trigger table
# ==========================================================================
def name_and_description(receipt_row):
    """The class's name is a position in a feature space -- not a behaviour,
    not a purpose, not an actor. It is derived from whether the class
    centroid sits above the population on the features that name it."""
    centroid = receipt_row.get("centroidVsPopulation") or {}
    above = []
    for name in ("trig_drift_abs", "fwd_path_length_deg", "fwd_slots_reached",
                 "init_drift_change_mag"):
        pair = centroid.get(name)
        if pair and pair[0] is not None and pair[1] is not None:
            above.append(float(pair[0]) > float(pair[1]))
    if above and all(above):
        return ("WIDE-CROSSING",
                "a large drift change leaving a trajectory that would cross "
                "many occupied mean longitudes")
    return ("RESIDUAL", "every other confirmed drift change")


def build_frozen_model(args):
    import pickle
    t0 = time.time()

    def say(m):
        print(f"  [{time.time() - t0:7.1f}s] {m}", flush=True)

    receipt_path = _REPO / RECEIPT
    receipt = json.loads(receipt_path.read_text())

    cache = Path(args.work) / "t8d-triggers.pkl"
    if not cache.exists():
        raise SystemExit(f"the measured trigger table is absent: {cache}")
    with open(cache, "rb") as fh:
        blob = pickle.load(fh)
    bundle = blob["bundle"]
    say(f"trigger table loaded, feature path {blob['featurePathSha256'][:12]}")

    triggers, feats, outs = (bundle["triggers"], bundle["features"],
                             bundle["outcomes"])
    idx_pri = [i for i in range(len(triggers))
               if outs[i]["resolvable"] and triggers[i].eligible]
    if len(idx_pri) != int(receipt["population"]["primaryArm"]):
        raise SystemExit(f"the primary arm is {len(idx_pri)}, the receipt says "
                         f"{receipt['population']['primaryArm']}; not freezing")
    say(f"primary arm {len(idx_pri):,} triggers")

    sub_feats = [feats[i] for i in idx_pri]
    sub_outs = [outs[i] for i in idx_pri]
    matrix = ta.feature_matrix(sub_feats)
    raw = ap.transform(matrix, ta.FEATURE_NAMES)
    scaler = ap.fold_scaler(raw)
    x = ap.apply_scaler(raw, scaler)
    k = int(receipt["kChosen"])
    say(f"fitting the frozen partition at k={k} on {x.shape[0]:,} x "
        f"{x.shape[1]} ...")
    labels, centres, inertia = ap.kmeans(x, k, seed=ta.SEED)
    sizes = [int((labels == c).sum()) for c in range(k)]
    say(f"sizes {sizes}, receipt {receipt['clusterSizes']}")
    if sizes != list(receipt["clusterSizes"]):
        raise SystemExit("the refit does not reproduce the measured partition; "
                         "refusing to freeze a model that did not earn the "
                         "published figures")
    if not np.array_equal(np.asarray(ap.assign(x, centres)),
                          np.asarray(labels)):
        raise SystemExit("the frozen constants do not reproduce their own "
                         "labels; not freezing")

    y = np.asarray([1.0 if (o["o1Positive"] and o["o1ArrivalDays"] is not None
                            and o["o1ArrivalDays"] > 0) else 0.0
                    for o in sub_outs])
    classes = []
    for c in range(k):
        m = labels == c
        n = int(m.sum())
        pos = int(y[m].sum())
        ref = next((r for r in receipt["classes"] if int(r["cluster"]) == c),
                   None)
        if ref is None or int(ref["n"]) != n or int(ref["positives"]) != pos:
            raise SystemExit(f"class {c}: refit {n}/{pos} disagrees with the "
                             f"receipt; not freezing")
        name, description = name_and_description(ref)
        lo, hi = ta.wilson(pos, n)
        classes.append({
            "cluster": c, "name": name, "description": description,
            "namedByFeatures": list(ref["namedBy"]),
            "n": n, "positives": pos, "precision": pos / n,
            "wilson95": [lo, hi],
            "bootstrapJaccard": float(receipt["stabilityJaccard"][c]),
            "arrivalDays": dict(ref["arrivalDays"]),
            "underpowered": bool(n < MIN_SUPPORT_FOR_A_RATE),
        })
    if sum(1 for r in classes if r["name"] == "WIDE-CROSSING") != 1:
        raise SystemExit("exactly one class must carry the wide-crossing name")

    pa = receipt["precision"]["primaryArm"]
    base_lo, base_hi = ta.wilson(int(pa["o1PositivesArrivalAfterAnnounce"]),
                                 int(pa["n"]))
    body = {
        "artifact": ARTIFACT_KIND,
        "schema": MODEL_SCHEMA,
        "modelFamily": MODEL_FAMILY,
        "modelVersion": MODEL_VERSION,
        "frozenAt": _iso(time.time() * 1000.0),
        "design": DESIGN,
        "note": (
            "The taxonomy, the scaler constants and the outcome tables are "
            "FROZEN here and are not re-fitted at run time. A lane that "
            "re-fitted its partition on each firing would have a pattern "
            "vocabulary that drifted silently, and every precision figure it "
            "published would be about a model that no longer existed. The "
            "version and the checksum are what let a published figure name "
            "the model that earned it."),
        "earnedBy": {
            "registration": REGISTRATION,
            "registrationSha256": sha256_file(_REPO / REGISTRATION),
            "results": RESULTS,
            "resultsSha256": sha256_file(_REPO / RESULTS),
            "receipt": RECEIPT,
            "receiptSha256": sha256_file(receipt_path),
            "instrument": "tools/trigger_alarm.py",
            "instrumentSha256": sha256_file(_REPO / "tools" / "trigger_alarm.py"),
            "featurePathSha256": blob["featurePathSha256"],
            "eventRecord": "docs/proximity-events-20260922.jsonl",
            "eventRecordSha256": sha256_file(ta.EVENTS_PATH),
            "extract": {kk: bundle["extractMeta"].get(kk)
                        for kk in ("rowsScanned", "rowsKept", "objectsKept",
                                   "sha256")},
        },
        "detector": {
            "sigmaNDegPerDay": float(bundle["sigma_n"]),
            "thresholdDegPerDay": max(pg.BURN_SIGMA_K * float(bundle["sigma_n"]),
                                      pg.BURN_FLOOR_DEG_PER_DAY),
            "baselineSamples": int(pg.BURN_BASELINE_SAMPLES),
            "sigmaK": float(pg.BURN_SIGMA_K),
            "floorDegPerDay": float(pg.BURN_FLOOR_DEG_PER_DAY),
            "mergeDays": float(ta.MERGE_DAYS),
            "confirmDays": float(ta.CONFIRM_DAYS),
            "horizonDays": float(ta.H_DAYS),
            "dwellDays": float(ta.DWELL_DAYS),
            "slotDriftFloorDegPerDay": float(ta.SLOT_DRIFT_FLOOR),
            "slotMatchDeg": float(ta.SLOT_MATCH_DEG),
            "slotMinHistoryDays": float(ta.SLOT_MIN_HISTORY_DAYS),
            "rampLookBackDays": float(ta.RAMP_LOOKBACK_DAYS),
            "rampFloorDays": float(ta.RAMP_FLOOR_DAYS),
            "planeMatchDeg": float(ta.PLANE_MATCH_DEG),
            "lambdaDdotDegPerDay2": float(ta.LAMBDA_DDOT),
            "lambdaStableDeg": float(ta.LAMBDA_STABLE_DEG),
            "propagationStepDays": float(ta.PROP_STEP_DAYS),
            "lookBackFloorDays": LOOK_BACK_FLOOR_DAYS,
        },
        "featureNames": list(ta.FEATURE_NAMES),
        "logFeatures": sorted(ta.LOG_FEATURES),
        "logEpsilon": float(ap.LOG_EPS),
        "seed": int(ta.SEED),
        "partition": {
            "k": k, "nInit": int(ap.N_INIT), "maxIter": int(ap.MAX_ITER),
            "tol": float(ap.TOL), "inertia": float(inertia),
            "criterion": ("maximum mean silhouette over k in 2..10, ties "
                          "toward the smaller k"),
            "silhouette": float([r["silhouette"] for r in receipt["kSweep"]
                                 if int(r["k"]) == k][0]),
        },
        "scaler": {
            "median": [float(v) for v in scaler["median"]],
            "mean": [float(v) for v in scaler["mean"]],
            "sd": [float(v) for v in scaler["sd"]],
            "keep": [bool(v) for v in scaler["keep"]],
            "note": ("medians impute, then centre and scale; columns with zero "
                     "spread are dropped by `keep`. Applied by the same two "
                     "functions the measurement used."),
        },
        "centroids": [[float(v) for v in row] for row in centres],
        "classes": classes,
        "basePopulation": {
            "n": int(pa["n"]),
            "positives": int(pa["o1PositivesArrivalAfterAnnounce"]),
            "precision": float(pa["o1PrecisionDpositive"]),
            "wilson95": [base_lo, base_hi],
            "arrivalDays": dict(pa["arrivalDays"]),
            "note": ("every confirmed drift change in the primary arm. This is "
                     "the denominator an alarm actually faces, and it is not "
                     "the relocation-alert denominator, which requires a large "
                     "relocation to have ALREADY HAPPENED: at trigger time no "
                     "such population exists."),
        },
        "bars": {
            "bootstrapJaccard": float(ta.GATE_E_JACCARD),
            "minSupportForARate": MIN_SUPPORT_FOR_A_RATE,
        },
        "shippedDetectorPermissions": {
            "manoeuvreLabelPermitted": False,
            "source": ("pipeline/orbit_events.py, the published passive "
                       "control: 34 flags in 1,941 intervals of objects that "
                       "physically cannot manoeuvre, against a design target "
                       "of one in a thousand"),
            "consequence": ("the lane says 'drift-rate change', because that "
                            "is what was measured"),
        },
        "caveats": list(CAVEATS),
        "neverSay": list(NEVER_SAY),
        "reservedDecisions": dict(RESERVED_DECISIONS),
        "reservedNote": RESERVED_NOTE,
    }
    out = Path(args.out) / f"alarm-lane-model-{args.date}.json"
    digest = write_model(body, out)
    say(f"frozen: {out}")
    say(f"checksum {digest}")

    reloaded = load_model(out)
    if not np.array_equal(classify(sub_feats[:5000], reloaded),
                          np.asarray(labels[:5000])):
        raise SystemExit("the written artifact does not reproduce the labels "
                         "it was built from")
    say("the written artifact reproduces its own labels on a 5,000-row check")
    return digest


# ==========================================================================
# CLI
# ==========================================================================
def load_event_record():
    _prov, rows = ta.load_events()
    return ta.primary_arm(rows)


def cmd_run(args):
    model = load_model(args.model)
    clock = Clock(_ms(args.now) if args.now else None)
    cadence = derive_cadence(CITED_EPOCH_SPACING_DAYS,
                             spacing_source=f"cited, {DESIGN} section 2.3")
    if args.cadence_hours is not None:
        cadence["override"] = {
            "workFloorHours": float(args.cadence_hours),
            "why": ("supplied on the command line; the derivation above is "
                    "what the lane uses otherwise")}
    setting = None
    if args.setting:
        setting = operating_setting(load_operating_points(args.curve, model),
                                    args.setting)
    state = load_state(args.state, model, cadence)
    source = ExtractSource() if args.source == "extract" else ArchiveSource()
    try:
        car = Sidecar(model, source, clock, state, events=load_event_record(),
                      setting=setting,
                      tick_days=cadence["workFloorDays"])
        if args.warm_start_at is not None and not state["lastAnnouncedMsByNorad"]:
            # A lane started cold would announce every chain in the archive on
            # its first firing -- fifty years of them, at once. Warm-starting
            # declares that everything which closed before this instant was
            # already announced. It is recorded in the state file, because a
            # ledger that silently begins mid-history is not auditable.
            warm = float(_ms(args.warm_start_at))
            state["lastAnnouncedMsByNorad"] = {
                str(int(n)): warm for n in car.watch()}
            state["warmStart"] = {
                "at": args.warm_start_at, "atMs": warm,
                "why": ("every chain that closed before this instant is "
                        "treated as already announced; nothing before it "
                        "enters the ledger")}
        records = car.fire()
    finally:
        source.close()
    raised = sum(1 for r in records if r["spoken"])
    ledger_append(args.ledger,
                  [{"record": "run", "atMs": clock.now_ms(),
                    "atIso": _iso(clock.now_ms()), "clock": clock.record(),
                    "modelVersion": model["modelVersion"],
                    "modelChecksum": model_checksum(model),
                    "assessed": len(records), "raised": raised}] + records)
    save_state(state, args.state)
    print(f"assessed {len(records)}, raised {raised}")
    for rec in records:
        if rec["spoken"]:
            print()
            print(rec["text"])
    return 0


def cmd_resolve(args):
    records = ledger_read(args.ledger)
    known = {r["alertId"] for r in records if r.get("record") == "resolution"}
    fresh = [r for r in resolve_ledger(records, load_event_record())
             if r["alertId"] not in known]
    ledger_append(args.ledger, fresh)
    print(f"{len(fresh)} resolutions appended")
    return 0


def cmd_audit(args):
    model = None
    try:
        model = load_model(args.model)
    except FrozenModelError as exc:
        print(f"NOTE: {exc}")
    audit = audit_ledger(ledger_read(args.ledger), model)
    print(audit_report(audit))
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(
            json.dumps(audit, indent=1, sort_keys=True) + "\n")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("freeze", help="build the frozen artifact")
    f.add_argument("--work", required=True,
                   help="the trigger-time predictor's working directory")
    f.add_argument("--out", default=str(_REPO / "docs"))
    f.add_argument("--date", default="20260922")

    r = sub.add_parser("run", help="one firing of the sidecar")
    r.add_argument("--model", default=str(MODEL_PATH))
    r.add_argument("--state", default=str(STATE_PATH))
    r.add_argument("--ledger", default=str(LEDGER_PATH))
    r.add_argument("--now", default=None, help="inject the clock (ISO 8601)")
    r.add_argument("--cadence-hours", type=float, default=None)
    r.add_argument("--source", choices=("archive", "extract"), default="archive")
    r.add_argument("--curve", default=str(CURVE_PATH))
    r.add_argument("--setting", default=None,
                   help="a named operating point from the curve; absent means "
                        "the loosest one")
    r.add_argument("--warm-start-at", default=None,
                   help="treat every chain that closed before this instant "
                        "(ISO 8601) as already announced")

    rs = sub.add_parser("resolve", help="fold outcomes into the ledger")
    rs.add_argument("--ledger", default=str(LEDGER_PATH))

    a = sub.add_parser("audit", help="the ledger's own audit")
    a.add_argument("--model", default=str(MODEL_PATH))
    a.add_argument("--ledger", default=str(LEDGER_PATH))
    a.add_argument("--json", default=None)

    args = p.parse_args(argv)
    if args.cmd == "freeze":
        build_frozen_model(args)
        return 0
    if args.cmd == "run":
        return cmd_run(args)
    if args.cmd == "resolve":
        return cmd_resolve(args)
    if args.cmd == "audit":
        return cmd_audit(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
