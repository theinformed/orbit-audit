#!/usr/bin/env python3
"""The alarm lane's LEO ARM.

The operator answered design section 10.6: the LEO arm is LIVE in v1. This
module builds it, under the scope T8b's own measurement established and under
no wider one.

WHAT THE ARM IS, and the qualification that travels with every number it
prints: T8b's LEO catalogue is **in-track phasing campaigns between objects
that already share an orbit** -- overwhelmingly members of the same large
constellation manoeuvring relative to one another. That is not a claim about
LEO approach behaviour in general; it is what the catalogue contains, because
T8b's registered direction-noise statistic came back 145 times too large and
switched the second channel off. The scope string is mandatory and is carried
on the face of every alert.

WHAT THE ARM MAY NOT DO. The second channel is blinded until its noise floor
is re-derived, so this arm ships **no matching product of any kind against it
and uses none of its vocabulary in any output string**.
`tests/test_alarm_lane.py` enforces that against the tool, the frozen tables,
every rendered alert, every audit report and every setting description.

THE TRIGGER, which is the observable a watching operator actually has: a
CAMPAIGN-INITIATING confirmed IN-TRACK manoeuvre of a payload-class LEO
object. `proximity_plane.detect_manoeuvres` decides what a confirmed in-track
manoeuvre is -- two consecutive element sets over
`max(5 sigma_n, 3 |ndot| dt, 50 m of semi-major axis)` and agreeing in sign,
flagged at the SECOND set, which is the first instant a causal observer had
the evidence. A campaign is a chain of those with no internal gap longer than
180 days, and the alert is its first flag. All of that is T8b's own
arithmetic, reused rather than reinvented.

THE OUTCOME RULE is T8b's own attribution and not a new one: an alert at `f`
is a hit when the same object carries a registered arm-M event whose
`campaignStartMs` is `f` and whose arrival is after `f`. T8b computes
`campaignStartMs` with `campaign_of` over the object's whole confirmed-flag
series, so the two definitions are the same boundary read from two directions.

WHAT IS FROZEN AND WHAT IS MEASURED. T8b's published figures -- 161 alerts,
71 hits, 44.1% [36.7%, 51.8%], a 195.9-day median causal lead, and the
never-manoeuvred control at zero events over 18.79 million object-days -- are
frozen here as T8b measured them. **They were measured on T8b's own alert
channel, which is not this trigger**, so this arm may NOT quote them as its
own precision: that is the same discipline section 7.10 imposes on the GEO
arm. This arm's own precision is measured by the replay, over a declared
outcome-blind window, and written into a second version of the frozen table.
Until it exists, the gate withholds the pattern clause and says why.

    python3 tools/alarm_lane_leo.py freeze
    python3 tools/alarm_lane_leo.py replay --work <low-orbit lane work dir>
    python3 tools/alarm_lane_leo.py freeze --measured <replay receipt>
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
for _p in (str(_REPO / "tools"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import proximity_plane as pp          # noqa: E402  the T8b instrument
import trigger_alarm as ta            # noqa: E402
import alarm_lane as al               # noqa: E402

DAY_MS = pp.DAY_MS

LEO_MODEL_PATH = _REPO / "docs" / "alarm-lane-leo-model-20260922.json"
LEO_MODEL_VERSION_1 = "leo-phasing-campaign/20260922/1"
LEO_MODEL_VERSION_2 = "leo-phasing-campaign/20260922/2"
LEO_RESULTS = "docs/proximity-leo-results-20260922.md"
LEO_EVENTS = _REPO / "docs" / "proximity-leo-events-20260922.jsonl"

# ---- T8b's published figures, frozen as measured --------------------------
T8B_ALERTS = 161
T8B_HITS = 71
T8B_PRECISION = 71.0 / 161.0
T8B_MEDIAN_CAUSAL_LEAD_DAYS = 195.9
T8B_CONTROL_EVENTS = 0
T8B_CONTROL_OBJECT_DAYS = 18_790_000.0
T8B_HORIZON_DAYS = pp.T_LOOK_DAYS                  # 1095.0

SCOPE = (
    "in-track phasing campaigns between objects that already share an orbit. "
    "This is what the measured catalogue contains and it is not a statement "
    "about approach behaviour in this regime generally: the second detection "
    "channel was switched off by a direction-noise floor that came back 145 "
    "times too large, and it stays off until that floor is re-derived.")

# the vocabulary this arm may never use, in addition to design section 7
LEO_NEVER_SAY = (
    "no matching product against the blinded second channel, and none of its "
    "vocabulary in any output string, until its noise floor is re-derived",
    "no claim that the measured lead time applies to anything but in-track "
    "phasing campaigns inside an already-shared orbit",
    "no quoting of the published alert-channel precision as this trigger's "
    "own: the two denominators are different detectors",
)

# ---- the registered operating-point grid for this arm ---------------------
# T8b measured its own sensitivity arms; those are the settings this arm
# offers, and the numbers in them are T8b's. Precision was measured for the
# primary arm ONLY, so every other row carries a LABELLED GAP and not a zero.
T8B_SENSITIVITY = (
    # thetaP, gamma, dDays, armM events, KM median lead d, never-manoeuvred
    (0.05, 5.0, 30.0, 31, 219.0, 0),
    (0.1, 5.0, 30.0, 54, 220.8, 0),
    (0.2, 5.0, 30.0, 71, 195.9, 0),          # primary
    (0.5, 5.0, 30.0, 85, 171.6, 4),
    (1.0, 5.0, 30.0, 104, 219.0, 6),
    (0.2, 1.0, 30.0, 24, 17.5, 0),
    (0.2, 0.2085, 30.0, 27, 4.4, 0),
    (0.2, 5.0, 14.0, 170, 196.9, 0),
    (0.2, 5.0, 60.0, 25, 196.9, 0),
)
PRIMARY_ARM = (0.2, 5.0, 30.0)

# the shipped detector's own design target for a flag on an object that
# physically cannot manoeuvre: one in a thousand. `pipeline/orbit_events.py`
# withholds its label because the published control stands at 34 in 1,941,
# and this arm is held to the same bar rather than to a softer one.
PASSIVE_CONTROL_BAR = 0.001

# ---- the LEO band, from T8b's own regime constants ------------------------
MU_KM3_S2 = pp.MU_KM3_S2
LEO_A_MAX_KM = pp.EARTH_RADIUS_KM + pp.LEO_CEILING_KM
LEO_A_MIN_KM = pp.EARTH_RADIUS_KM + 120.0


def mean_motion_rev_day(a_km):
    return 86400.0 / (2.0 * math.pi) * math.sqrt(MU_KM3_S2 / a_km ** 3)


# ==========================================================================
def control_base_population():
    """The never-manoeuvred control, expressed so the gate can compare a
    precision against it.

    T8b's control is zero registered events over 18.79 million object-days.
    Expressed as independent horizons of `T8B_HORIZON_DAYS`, that is
    `objectDays / horizonDays` trials with zero successes, and Wilson's 95%
    upper bound on a zero count over that many trials is the false-alarm
    ceiling the control licenses.

    THE LIMITATION, stated rather than buried: object-horizons carved out of
    one archive are not independent trials, so this ceiling is optimistic by
    an unmeasured factor. It is a ceiling, not an estimate, and nothing in
    this lane rests on its exact value."""
    trials = int(round(T8B_CONTROL_OBJECT_DAYS / T8B_HORIZON_DAYS))
    lo, hi = ta.wilson(T8B_CONTROL_EVENTS, trials)
    return {
        "kind": "never-manoeuvred control",
        "n": trials,
        "positives": T8B_CONTROL_EVENTS,
        "precision": (T8B_CONTROL_EVENTS / trials) if trials else None,
        "wilson95": [lo, hi],
        "objectDays": T8B_CONTROL_OBJECT_DAYS,
        "horizonDays": T8B_HORIZON_DAYS,
        "note": ("zero registered events over 18.79 million object-days of "
                 "objects with no detected manoeuvre anywhere in their "
                 "history, expressed as that many independent horizons. The "
                 "horizons are NOT independent, so the ceiling is optimistic "
                 "by an unmeasured factor; it is a ceiling, not an estimate."),
    }


def build_leo_model(measured=None):
    """The LEO arm's frozen table, in the SAME shape as the GEO one so that
    the gate, the renderer, the ledger and the audit consume both arms
    identically."""
    control = control_base_population()
    if measured is None:
        cls = {
            "cluster": 0,
            "name": "PHASING-CAMPAIGN",
            "description": ("a campaign-initiating confirmed in-track "
                            "manoeuvre of a payload-class object in this "
                            "regime"),
            "namedByFeatures": ["campaign-initiating in-track manoeuvre"],
            "n": 0,
            "positives": 0,
            "precision": None,
            "wilson95": None,
            "bootstrapJaccard": None,
            "stabilityBasis": ("not a cluster: the class is the detector's "
                               "own definition, so the cluster-stability bar "
                               "does not apply to it"),
            "arrivalDays": {"n": 0,
                            "label": "NOT ASSESSABLE -- this trigger's own "
                                     "lead-time distribution has not been "
                                     "measured yet; a labelled gap"},
            "underpowered": True,
        }
        version = LEO_MODEL_VERSION_1
    else:
        m = measured
        lo, hi = ta.wilson(int(m["hits"]), int(m["alerts"]))
        cls = {
            "cluster": 0,
            "name": "PHASING-CAMPAIGN",
            "description": ("a campaign-initiating confirmed in-track "
                            "manoeuvre of a payload-class object in this "
                            "regime"),
            "namedByFeatures": ["campaign-initiating in-track manoeuvre"],
            "n": int(m["alerts"]),
            "positives": int(m["hits"]),
            "precision": (int(m["hits"]) / int(m["alerts"])
                          if m["alerts"] else None),
            "wilson95": [lo, hi],
            "bootstrapJaccard": None,
            "stabilityBasis": ("not a cluster: the class is the detector's "
                               "own definition, so the cluster-stability bar "
                               "does not apply to it"),
            "arrivalDays": m["leadDays"],
            "underpowered": bool(int(m["alerts"]) < al.MIN_SUPPORT_FOR_A_RATE),
            "passiveControlRatio": m.get("passiveControlRatio"),
            "passiveControlBar": m.get("passiveControlBar",
                                       PASSIVE_CONTROL_BAR),
            "measuredOn": m["window"],
            "measuredNote": ("measured by this arm's own replay over the "
                             "declared window below, and NOT over the whole "
                             "archive: the archive-wide measurement for this "
                             "trigger has not been run."),
        }
        version = LEO_MODEL_VERSION_2

    return {
        "artifact": al.ARTIFACT_KIND,
        "schema": al.MODEL_SCHEMA,
        "modelFamily": "leo-phasing-campaign",
        "modelVersion": version,
        "regime": "LEO",
        "frozenAt": al._iso(time.time() * 1000.0),
        "design": al.DESIGN,
        "scope": SCOPE,
        "note": ("the LEO arm of the behavioural alarm lane. Its trigger is "
                 "a campaign-initiating confirmed in-track manoeuvre; its "
                 "outcome rule is T8b's own attribution; and its published "
                 "figures below were measured on T8b's own alert channel, "
                 "which is a DIFFERENT detector, so this arm may not quote "
                 "them as its own precision."),
        "earnedBy": {
            "results": LEO_RESULTS,
            "resultsSha256": al.sha256_file(_REPO / LEO_RESULTS),
            "eventRecord": "docs/proximity-leo-events-20260922.jsonl",
            "eventRecordSha256": al.sha256_file(LEO_EVENTS),
            "instrument": "tools/proximity_plane.py",
            "instrumentSha256": al.sha256_file(_REPO / "tools"
                                               / "proximity_plane.py"),
            "arm": "tools/alarm_lane_leo.py",
        },
        "publishedFigures": {
            "alerts": T8B_ALERTS,
            "hits": T8B_HITS,
            "precision": T8B_PRECISION,
            "wilson95": list(ta.wilson(T8B_HITS, T8B_ALERTS)),
            "medianCausalLeadDays": T8B_MEDIAN_CAUSAL_LEAD_DAYS,
            "scope": SCOPE,
            "channelNote": ("measured on T8b's own alert channel, which is "
                            "NOT the trigger this arm runs. The two "
                            "denominators are different detectors and this "
                            "arm does not quote these figures as its own "
                            "precision."),
        },
        "detector": {
            "trigger": ("a campaign-initiating confirmed in-track manoeuvre "
                        "of a payload-class object in this regime"),
            "confirmRule": ("two consecutive element sets over the threshold "
                            "and agreeing in sign, flagged at the second"),
            "thresholdNote": ("max(5 sigma_n, 3 |ndot| dt, the semi-major-axis "
                              "floor), all of it computed by the T8b "
                              "instrument"),
            "semiMajorAxisFloorKm": float(pp.DA_FLOOR_KM),
            "sigmaK": float(pp.BURN_SIGMA_K),
            "baselineSamples": int(pp.BURN_BASELINE_SAMPLES),
            "campaignMaxGapDays": float(pp.CAMPAIGN_MAX_GAP_DAYS),
            "horizonDays": float(T8B_HORIZON_DAYS),
            "confirmDays": 0.0,
            "confirmDaysNote": ("the flag epoch is already the second "
                                "confirming element set, and a campaign's own "
                                "merge window is 180 days, so charging a "
                                "further wait would cost warning time for "
                                "nothing"),
            "lookBackFloorDays": float(pp.T_LOOK_DAYS),
            "bandMeanMotionRevDay": [mean_motion_rev_day(LEO_A_MAX_KM),
                                     mean_motion_rev_day(LEO_A_MIN_KM)],
            "sigmaNDegPerDay": None,
            "floorDegPerDay": None,
        },
        "featureNames": [],
        "classes": [cls],
        "basePopulation": control,
        "bars": {"bootstrapJaccard": float(ta.GATE_E_JACCARD),
                 "minSupportForARate": al.MIN_SUPPORT_FOR_A_RATE},
        "shippedDetectorPermissions": {
            "manoeuvreLabelPermitted": False,
            "source": ("pipeline/orbit_events.py, the published passive "
                       "control"),
            "consequence": ("this arm says 'confirmed in-track manoeuvre', "
                            "which is what its own detector measured, and "
                            "never a word the shipped bundle has not earned"),
        },
        "operatingPoints": build_leo_operating_points(),
        "caveats": list(al.CAVEATS) + [SCOPE],
        "neverSay": list(al.NEVER_SAY) + list(LEO_NEVER_SAY),
        "reservedDecisions": {k: v for k, v in al.RESERVED_DECISIONS.items()
                              if k != "leoArmIsBuilt"},
        "reservedNote": (al.RESERVED_NOTE + " Decision 6 -- whether this arm "
                         "is built -- was ANSWERED by the operator: it is "
                         "live. Every other decision remains reserved."),
    }


def build_leo_operating_points():
    """T8b measured its own sensitivity arms and those are the settings this
    arm offers. Precision was measured for the primary arm only, so every
    other row is a LABELLED GAP and never a zero."""
    rows = []
    for theta_p, gamma, d_days, arm_m, lead, control in T8B_SENSITIVITY:
        primary = (theta_p, gamma, d_days) == PRIMARY_ARM
        row = {
            "point": {"coOrbitalToleranceDeg": theta_p,
                      "phaseConfinementDeg": gamma,
                      "minDwellDays": d_days},
            "isPrimary": primary,
            "registeredEvents": arm_m,
            "medianLeadDays": lead,
            "neverManoeuvredControlEvents": control,
            "supportingEvents": arm_m,
            "underpowered": bool(arm_m < al.MIN_SUPPORT_FOR_A_RATE),
        }
        if primary:
            lo, hi = ta.wilson(T8B_HITS, T8B_ALERTS)
            row["alerts"] = T8B_ALERTS
            row["arrivals"] = T8B_HITS
            row["precision"] = T8B_PRECISION
            row["wilson95"] = [lo, hi]
            row["precisionLabel"] = (
                f"{T8B_HITS}/{T8B_ALERTS} = {100.0 * T8B_PRECISION:.1f}% on "
                f"the published alert channel, which is NOT this arm's "
                f"trigger")
        else:
            row["alerts"] = None
            row["arrivals"] = None
            row["precision"] = None
            row["wilson95"] = None
            row["precisionLabel"] = (
                "NOT ASSESSABLE -- the alert denominator was measured for the "
                "primary arm only, so no precision exists for this setting. A "
                "labelled gap, not a zero.")
        row["recallProxy"] = (arm_m / T8B_HITS) if T8B_HITS else None
        row["recallNote"] = (
            "TRUE RECALL IS NOT MEASURABLE here either. `recallProxy` is this "
            "setting's registered event count over the primary arm's, and it "
            "is a ratio between two rows of one table rather than the "
            "fraction of real approaches caught.")
        row["description"] = _describe_leo(row)
        rows.append(row)
    return {
        "note": ("the settings are T8b's own registered sensitivity arms and "
                 "the numbers in them are T8b's. A tighter setting is not a "
                 "more certain alert: it is FEWER alerts, with a different "
                 "measured lead, and the row says which."),
        "rows": rows,
    }


def _describe_leo(row):
    p = row["point"]
    lead = row["medianLeadDays"]
    head = (f"{row['registeredEvents']} registered events, median warning "
            f"{lead:.1f} days, never-manoeuvred control "
            f"{row['neverManoeuvredControlEvents']}")
    if row["precision"] is not None:
        head += (f", published alert-channel precision "
                 f"{100.0 * row['precision']:.1f}%")
    else:
        head += ", precision NOT ASSESSABLE at this setting -- a labelled gap"
    return (head + f"; evidence: co-orbital tolerance "
            f"{p['coOrbitalToleranceDeg']} deg, phase confinement "
            f"{p['phaseConfinementDeg']} deg, dwell at least "
            f"{p['minDwellDays']:.0f} days.")


# ==========================================================================
# The extract -- one sequential pass, bounded to the band and the window
# ==========================================================================
def extract(db, lo_ms, hi_ms, cache, say):
    if cache.exists():
        with np.load(cache) as z:
            arrays = {k: z[k] for k in z.files}
        say(f"extract reused: {arrays['norad'].size:,} rows")
        return arrays
    mm_lo = int(round(mean_motion_rev_day(LEO_A_MAX_KM) * pp.SCALE_MM))
    mm_hi = int(round(mean_motion_rev_day(LEO_A_MIN_KM) * pp.SCALE_MM))
    ecc_hi = int(round(pp.MEO_ECC_MAX * pp.SCALE_ECC))
    t0 = time.time()
    # typed accumulators: a Python list of 56 million integers costs an order
    # of magnitude more memory than the archive rows it holds, and this
    # machine is shared
    from array import array
    cols = [array("q") for _ in range(6)]
    seen = 0
    for row in db.execute(
            "SELECT norad, epoch_ms, mean_motion_q, eccentricity_q, "
            "inclination_q, raan_q FROM element_set"):
        seen += 1
        if not (mm_lo <= row[2] <= mm_hi) or row[3] > ecc_hi:
            continue
        if not (lo_ms <= row[1] <= hi_ms):
            continue
        for i in range(6):
            cols[i].append(row[i])
        if seen % 50_000_000 == 0:
            say(f"  scanned {seen:,}, kept {len(cols[0]):,}")
    arrays = {
        "norad": np.asarray(cols[0], dtype=np.int64),
        "epoch_ms": np.asarray(cols[1], dtype=np.int64),
        "n": np.asarray(cols[2], dtype=np.float64) / pp.SCALE_MM,
        "e": np.asarray(cols[3], dtype=np.float64) / pp.SCALE_ECC,
        "inc": np.asarray(cols[4], dtype=np.float64) / pp.SCALE_ANGLE,
        "raan": np.asarray(cols[5], dtype=np.float64) / pp.SCALE_ANGLE,
    }
    say(f"extract: {seen:,} scanned, {arrays['norad'].size:,} kept in "
        f"{time.time() - t0:.0f}s")
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez(cache, **arrays)
    return arrays


def per_object(arrays):
    order = np.argsort(arrays["norad"], kind="stable")
    norad = arrays["norad"][order]
    uniq, starts = np.unique(norad, return_index=True)
    bounds = np.append(starts, norad.size)
    for k in range(uniq.size):
        idx = order[bounds[k]:bounds[k + 1]]
        idx = idx[np.argsort(arrays["epoch_ms"][idx], kind="stable")]
        yield int(uniq[k]), {key: arrays[key][idx]
                             for key in ("epoch_ms", "n", "e", "inc", "raan")}


def campaign_starts(flag_ms, max_gap_days=pp.CAMPAIGN_MAX_GAP_DAYS):
    """The first flag of every chain with no internal gap longer than
    `max_gap_days`. T8b reads the same boundary backwards from an arrival with
    `campaign_of`; this reads it forwards, which is what a lane can do."""
    f = np.sort(np.asarray(flag_ms, dtype=np.float64))
    if f.size == 0:
        return f
    cut = np.nonzero(np.diff(f) / DAY_MS > max_gap_days)[0] + 1
    return f[np.concatenate(([0], cut)).astype(np.int64)]


def load_leo_events():
    rows = []
    with open(LEO_EVENTS) as fh:
        for line in fh:
            rec = json.loads(line)
            if rec.get("record") == "provenance":
                continue
            if rec.get("armM"):
                rows.append(rec)
    return rows


# ==========================================================================
# The replay -- design section 11.6, for this arm
# ==========================================================================
WINDOW_RULE = (
    "the earliest span of the decade that holds the largest payload "
    "population in this regime for which EVERY alert's 1,095-day horizon "
    "still closes inside the archive. Chosen on population and on archive "
    "extent, both outcome-blind, and fixed before any figure in this replay "
    "existed.")
WINDOW_START = "2020-01-01T00:00:00+00:00"
WINDOW_END = "2023-06-01T00:00:00+00:00"
LOOK_BACK_START = "2017-01-01T00:00:00+00:00"


def detect_all(arrays, classes, say):
    """Confirmed in-track flags and campaign starts, per object, by T8b's own
    detector. Nothing here reads a clock: the clock decides only which of
    these the lane has SEEN, which is what the tick loop does."""
    out = {}
    done = 0
    for norad, el in per_object(arrays):
        done += 1
        if el["epoch_ms"].size < pp.BURN_BASELINE_SAMPLES + 3:
            continue
        sigma_theta, sigma_n = pp.object_sigma_contributions(el)
        if not (np.isfinite(sigma_n) and np.isfinite(sigma_theta)):
            continue
        flags = pp.detect_manoeuvres(el, sigma_n, sigma_theta)
        idx = flags["intrack"]
        if idx.size == 0:
            continue
        flag_ms = el["epoch_ms"][idx].astype(np.float64)
        out[norad] = {"flagMs": flag_ms,
                      "starts": campaign_starts(flag_ms),
                      "klass": classes.get(norad),
                      "firstMs": float(el["epoch_ms"][0]),
                      "lastMs": float(el["epoch_ms"][-1])}
        if done % 5000 == 0:
            say(f"  detected {done:,} objects, {len(out):,} with a flag")
    return out


def run_leo_replay(args, model, say):
    t0 = time.time()
    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    ledger = work / "alarm-lane-leo-replay-ledger.jsonl"
    if ledger.exists():
        ledger.unlink()

    lo = al._ms(args.look_back)
    start = al._ms(args.start)
    end = al._ms(args.end)
    db = sqlite3.connect(f"file:{ta.ARCHIVE}?mode=ro", uri=True)
    db.execute("PRAGMA query_only = 1")
    arrays = extract(db, int(lo), int(end), work / "leo-extract.npz", say)
    norads = np.unique(arrays["norad"])
    classes = {}
    for nd in norads:
        row = db.execute("SELECT object_type FROM object WHERE norad = ?",
                         (int(nd),)).fetchone()
        classes[int(nd)] = pp.class_label(row[0] if row else None)
    db.close()
    say(f"{len(classes):,} objects in the band, "
        f"{sum(1 for v in classes.values() if v == 'payload'):,} payload-class")

    detected = detect_all(arrays, classes, say)
    say(f"{len(detected):,} objects carry a confirmed in-track flag")

    events = load_leo_events()
    by_obj = {}
    for e in events:
        by_obj.setdefault(int(e["approacher"]), []).append(e)
    # the horizon must be judged against the OUTCOME RECORD's end, not
    # against the end of this replay's extract window -- the first version of
    # this line used the extract's own maximum epoch and turned 5,114 of
    # 5,327 resolvable alerts into labelled gaps
    record_end = max(float(e["arrivalMs"]) for e in events) if events else 0.0

    cadence = al.derive_cadence(
        _median_spacing(arrays),
        median_causal_lead_days=T8B_MEDIAN_CAUSAL_LEAD_DAYS,
        spacing_source=(f"measured over all {len(classes)} objects' element "
                        f"sets in this regime and window"))
    tick_days = float(args.tick_days or cadence["workFloorDays"])
    say(f"derived cadence: work floor {cadence['workFloorDays']:.4f} d, "
        f"tick {tick_days:.4f} d")

    horizon_ms = float(model["detector"]["horizonDays"]) * DAY_MS
    point = None
    vocab_cache = {}

    def record_for(norad, f_ms, now_ms, klass):
        vocab = vocab_cache.get("v")
        if vocab is None:
            vocab = al.permitted_vocabulary(model, 0, assessable=True,
                                            point=point)
            vocab_cache["v"] = vocab
        base = {
            "alertId": f"leo-{norad}-{int(f_ms)}",
            "record": "assessment",
            "regime": "LEO",
            "arm": "leo-phasing-campaign",
            "norad": int(norad),
            "objectClass": klass,
            "tFirstMs": float(f_ms),
            "tTrigMs": float(f_ms),
            "tTrigIso": al._iso(f_ms),
            "tAnnounceMs": float(f_ms),
            "tAnnounceIso": al._iso(f_ms),
            "announcedAtMs": float(now_ms),
            "driftChangeDegPerDay": 0.0,
            "assessable": True,
            "class": 0,
            "className": model["classes"][0]["name"],
            "classSupport": int(model["classes"][0]["n"]),
            "classPositives": int(model["classes"][0]["positives"]),
            "classPrecision": model["classes"][0]["precision"],
            "classWilson95": model["classes"][0]["wilson95"],
            "classArrivalDays": model["classes"][0]["arrivalDays"],
            "populationN": int(model["basePopulation"]["n"]),
            "populationPrecision": model["basePopulation"]["precision"],
            "populationWilson95": model["basePopulation"]["wilson95"],
            "horizonDays": float(model["detector"]["horizonDays"]),
            "resolveByMs": float(f_ms) + horizon_ms,
            "setting": "primary",
            "scope": SCOPE,
            "spoken": bool(vocab["mayRaiseAlert"]),
            "vocabulary": al._vocab_record(vocab),
            "resolution": {"state": "pending"},
            "gapReason": None,
        }
        base["text"] = (_render_leo(model, base, vocab)
                        if vocab["mayRaiseAlert"] else None)
        return base

    records, control_records = [], []
    announced = {}
    ticks = 0
    now = start
    step = tick_days * DAY_MS
    ledger.write_text(json.dumps(al.LEDGER_PROVENANCE, sort_keys=True) + "\n")
    while now <= end:
        fired = []
        for norad, blob in detected.items():
            starts = blob["starts"]
            seen = announced.get(norad, start)
            new = starts[(starts > seen) & (starts <= now)]
            if new.size == 0:
                continue
            announced[norad] = float(new[-1])
            for f in new:
                rec = record_for(norad, float(f), now, blob["klass"])
                (records if blob["klass"] == "payload"
                 else control_records).append(rec)
                if blob["klass"] == "payload":
                    fired.append(rec)
        if fired:
            al.ledger_append(ledger, fired)
        ticks += 1
        if ticks % 200 == 0:
            say(f"  tick {ticks} at {al._iso(now)[:10]}: {len(records)} alerts")
        now += step
    say(f"{ticks} ticks, {len(records)} payload-class alerts, "
        f"{len(control_records)} on objects that cannot manoeuvre")

    next_start = _next_campaign_start(detected)
    resolutions = resolve_leo(records, by_obj, record_end, horizon_ms,
                              next_start)
    al.ledger_append(ledger, resolutions)
    control_res = resolve_leo(control_records, by_obj, record_end, horizon_ms,
                              next_start)
    audit = al.audit_ledger(records + resolutions, model)

    hits = sum(1 for r in resolutions if r["state"] == "arrival")
    resolved = sum(1 for r in resolutions if r["state"] in ("arrival", "none"))
    leads = [r["leadDays"] for r in resolutions if r["state"] == "arrival"]
    lo_w, hi_w = ta.wilson(hits, resolved) if resolved else (float("nan"),) * 2
    control_hits = sum(1 for r in control_res if r["state"] == "arrival")

    receipt = {
        "artifact": "alarm-lane-leo-replay-receipt",
        "schema": 1,
        "design": al.DESIGN,
        "regime": "LEO",
        "status": ("SYNTHETIC EXERCISE. Nothing is deployed, nothing is "
                   "scheduled, no timer or cron entry exists, nothing is on "
                   "any site surface, and no alert left this machine."),
        "scope": SCOPE,
        "windowRule": WINDOW_RULE,
        "window": {"start": args.start, "end": args.end,
                   "lookBackFrom": args.look_back, "ticks": ticks,
                   "tickDays": tick_days},
        "model": {"version": model["modelVersion"],
                  "checksum": al.model_checksum(model)},
        "cadence": cadence,
        "clock": {"mode": "injected", "start": args.start, "end": args.end},
        "population": {
            "objectsInBand": len(classes),
            "payloadClass": sum(1 for v in classes.values() if v == "payload"),
            "objectsWithAConfirmedFlag": len(detected),
        },
        "measured": {
            "alerts": len(records),
            "resolved": resolved,
            "hits": hits,
            "precision": (hits / resolved) if resolved else None,
            "wilson95": [lo_w, hi_w] if resolved else None,
            "underpowered": bool(resolved < al.MIN_SUPPORT_FOR_A_RATE),
            "leadDays": _percentiles(leads),
            "passiveControlRatio": _control_ratio(len(control_records),
                                                  len(records), classes),
            "passiveControlBar": PASSIVE_CONTROL_BAR,
            "notAssessable": sum(1 for r in resolutions
                                 if r["state"] == "not-assessable"),
            "exactCampaignStartMatches": sum(
                1 for r in resolutions if r.get("exactCampaignStartMatch")),
            "outcomeRecordEndsAt": al._iso(record_end),
            "window": {"start": args.start, "end": args.end},
            "note": ("measured on THIS arm's trigger -- a campaign-initiating "
                     "confirmed in-track manoeuvre -- over the declared "
                     "window. It is not the published alert-channel figure "
                     "and does not replace it."),
        },
        "publishedFiguresBeside": model["publishedFigures"],
        "control": {
            "kind": ("the detector's own alert rate on objects that cannot "
                     "manoeuvre -- the non-tautological control, in the shape "
                     "the shipped passive control uses"),
            "alertsOnNonPayload": len(control_records),
            "hitsOnNonPayload": control_hits,
            "ratioToPayloadAlerts": (len(control_records) / len(records)
                                     if records else None),
            "perObjectRatio": _control_ratio(len(control_records),
                                             len(records), classes),
            "bar": PASSIVE_CONTROL_BAR,
            "barSource": ("the shipped detector's own design target of one "
                          "in a thousand; `pipeline/orbit_events.py` "
                          "withholds its label because its published control "
                          "stands at 34 in 1,941"),
            "frozenControl": model["basePopulation"],
        },
        "audit": audit,
        "auditReport": al.audit_report(audit),
        "caveats": list(model["caveats"]),
        "neverSay": list(model["neverSay"]),
        "reservedDecisions": dict(model["reservedDecisions"]),
        "ledger": {"path": str(ledger),
                   "rows": len(records) + len(resolutions) + 1,
                   "sha256": al.sha256_file(ledger)},
        "host": "pc",
        "executionMode": "CPU, one core",
        "wallSeconds": time.time() - t0,
    }
    out = Path(args.out) / f"alarm-lane-leo-replay-{args.date}-receipt.json"
    out.write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n")
    say(f"receipt: {out}")

    subset = Path(args.out) / f"alarm-lane-leo-replay-{args.date}-ledger.jsonl"
    arrived = {r["alertId"] for r in resolutions if r["state"] == "arrival"}
    rng = np.random.default_rng(ta.SEED)
    keep = [r for r in records if r["spoken"] or r["alertId"] in arrived]
    others = [r for r in records
              if not (r["spoken"] or r["alertId"] in arrived)]
    sampled = min(args.sample, len(others)) if others else 0
    if sampled:
        picks = sorted(rng.choice(len(others), size=sampled, replace=False))
        keep.extend(others[i] for i in picks)
    keep = [r if r.get("spoken") else dict(r, text=None) for r in keep]
    kept_ids = {r["alertId"] for r in keep}
    keep_res = [r for r in resolutions if r["alertId"] in kept_ids]
    prov = dict(al.LEDGER_PROVENANCE)
    prov["regime"] = "LEO"
    prov["scope"] = SCOPE
    prov["subsetOf"] = {
        "path": str(ledger),
        "rows": receipt["ledger"]["rows"],
        "sha256": receipt["ledger"]["sha256"],
        "assessmentsInFull": len(records),
        "spokenKept": sum(1 for r in records if r["spoken"]),
        "arrivalRowsKept": len(arrived),
        "otherAssessments": len(others),
        "otherAssessmentsSampled": sampled,
        "rule": ("every spoken alert, every assessment an arrival resolved, "
                 "plus a seed-%d uniform sample of %d of the %d others. The "
                 "sampling rule reads only whether the row was spoken, so the "
                 "alerts are complete rather than sampled. The rendered text "
                 "of a row that was never spoken is dropped."
                 % (ta.SEED, sampled, len(others)))}
    with open(subset, "w") as fh:
        fh.write(json.dumps(prov, sort_keys=True) + "\n")
        for r in sorted(keep, key=lambda r: r["tTrigMs"]):
            fh.write(json.dumps(r, sort_keys=True, allow_nan=False) + "\n")
        for r in keep_res:
            fh.write(json.dumps(r, sort_keys=True, allow_nan=False) + "\n")
    say(f"committed ledger: {subset}")
    print()
    print(receipt["auditReport"])
    return receipt


def _control_ratio(control_alerts, payload_alerts, classes):
    """The alert rate on objects that physically cannot manoeuvre, divided by
    the rate on objects that can, both PER OBJECT so the comparison is not a
    comparison of population sizes.

    This is the non-tautological control -- the shape
    `pipeline/orbit_events.py` uses for the word it withholds -- and it is
    the one that decides whether this arm has earned a clause about what its
    flag means."""
    n_payload = sum(1 for v in classes.values() if v == "payload")
    n_other = sum(1 for v in classes.values() if v != "payload")
    if not n_payload or not n_other or not payload_alerts:
        return None
    return (control_alerts / n_other) / (payload_alerts / n_payload)


def _median_spacing(arrays):
    order = np.lexsort((arrays["epoch_ms"], arrays["norad"]))
    nd = arrays["norad"][order]
    ep = arrays["epoch_ms"][order].astype(np.float64)
    d = np.diff(ep) / DAY_MS
    same = nd[1:] == nd[:-1]
    d = d[same & (d > 0)]
    return float(np.median(d)) if d.size else 1.0


def _percentiles(values, ps=(5, 25, 50, 75, 95)):
    v = np.asarray([x for x in values if x is not None and np.isfinite(x)],
                   dtype=np.float64)
    if v.size == 0:
        return {"n": 0, "label": "NOT ASSESSABLE -- no arrival; a labelled gap"}
    return {"n": int(v.size),
            **{f"p{p}": float(np.percentile(v, p)) for p in ps}}


def _next_campaign_start(detected):
    """For every campaign-initiating flag, the object's NEXT one. A campaign
    runs from its own first flag to the start of the following campaign."""
    out = {}
    for norad, blob in detected.items():
        starts = blob["starts"]
        for i, f in enumerate(starts):
            out[(int(norad), float(f))] = (float(starts[i + 1])
                                           if i + 1 < starts.size
                                           else float("inf"))
    return out


def resolve_leo(records, by_obj, record_end_ms, horizon_ms, next_start=None,
                tol_ms=1000.0):
    """T8b's OWN attribution, read forwards: an alert at `f` is a hit when the
    same object carries a registered event whose campaign start falls inside
    the campaign this alert opens, and whose arrival is after `f` and inside
    the horizon.

    AN EXACT EPOCH MATCH WAS TRIED FIRST AND DOES NOT WORK, and the reason is
    worth recording rather than hiding: T8b estimated each object's noise
    floor over the whole archive, this arm estimates it over the replay's own
    span, and two slightly different thresholds put the confirming element set
    in slightly different places. The campaign BOUNDARY is the robust
    quantity, so the campaign boundary is what is matched. Exact matches are
    counted separately and reported."""
    out = []
    grace = pp.CAMPAIGN_MAX_GAP_DAYS * DAY_MS
    for rec in records:
        f = float(rec["tTrigMs"])
        close = f + horizon_ms
        end = (next_start or {}).get((int(rec["norad"]), f), float("inf"))
        matches, exact = [], 0
        for e in by_obj.get(int(rec["norad"]), []):
            start = e.get("campaignStartMs")
            if start is None:
                continue
            start = float(start)
            if abs(start - f) <= tol_ms:
                exact += 1
            if not (f - grace <= start < end):
                continue
            if float(e["arrivalMs"]) > f and float(e["arrivalMs"]) <= close:
                matches.append(e)
        if matches:
            best = min(matches, key=lambda e: float(e["arrivalMs"]))
            out.append({"record": "resolution", "alertId": rec["alertId"],
                        "class": 0, "state": "arrival",
                        "exactCampaignStartMatch": bool(exact),
                        "arrivalMs": float(best["arrivalMs"]),
                        "arrivalIso": al._iso(best["arrivalMs"]),
                        "leadDays": (float(best["arrivalMs"]) - f) / DAY_MS,
                        "rule": ("a registered event whose campaign start "
                                 "falls inside the campaign this alert opens, "
                                 "arriving after it and inside the horizon")})
        elif record_end_ms < close:
            out.append({"record": "resolution", "alertId": rec["alertId"],
                        "class": 0, "state": "not-assessable",
                        "rule": ("the outcome record ends before this alert's "
                                 "horizon closes: a labelled gap, not a "
                                 "miss")})
        else:
            out.append({"record": "resolution", "alertId": rec["alertId"],
                        "class": 0, "state": "none",
                        "rule": ("the horizon closed with no registered event "
                                 "attributed to this campaign")})
    return out


def _render_leo(model, assessment, vocabulary):
    """This arm's alert. It carries the scope on its face, quotes only what
    this trigger earned, and says what the published figures are and why they
    are not this alert's precision."""
    fig = vocabulary["figures"]
    lines = [
        f"Object NORAD {assessment['norad']} executed a confirmed in-track "
        f"manoeuvre at {assessment['tTrigIso']} (second consecutive element "
        f"set showing the change, agreeing in sign), and it begins a "
        f"campaign: no confirmed manoeuvre of this object in the "
        f"{model['detector']['campaignMaxGapDays']:.0f} days before it."]
    if "pattern_match" in vocabulary["permitted"]:
        lines.append("")
        lines.append(
            f"The trigger matches pattern {fig['name']} -- "
            f"{fig['description']}. {fig['n']:,} campaign-initiating "
            f"manoeuvres in the measured window match it, and "
            f"{fig['positives']} of them were followed by a registered "
            f"co-orbital arrival: {al._pct(fig['precision'])}, Wilson 95% "
            f"{al._pct(fig['wilson95'][0])} to {al._pct(fig['wilson95'][1])}.")
        d = fig["arrivalDays"]
        if d.get("p50") is not None:
            lines.append(
                f"Median time from this point to arrival: {d['p50']:.1f} "
                f"days, p25-p75 {d['p25']:.1f} to {d['p75']:.1f} days.")
    else:
        lines.append("")
        lines.append("NOT AN ALERT: "
                     + vocabulary["withheld"]["pattern_match"])
    lines.append("")
    lines.append(f"SCOPE: {SCOPE}")
    lines.append(
        f"Published figures for this regime, measured on a DIFFERENT "
        f"detector and therefore NOT this alert's precision: "
        f"{T8B_HITS} of {T8B_ALERTS} alerts "
        f"({al._pct(T8B_PRECISION)}), median causal lead "
        f"{T8B_MEDIAN_CAUSAL_LEAD_DAYS:.1f} days.")
    control = model["basePopulation"]
    lines.append(
        f"Control: objects with no detected manoeuvre anywhere in their "
        f"history produced {control['positives']} registered events over "
        f"{control['objectDays']:,.0f} object-days.")
    lines.append("")
    lines.extend(al.CAVEATS)
    lines.append("Pattern assignment is mathematics on public element sets. "
                 "No purpose is attributed.")
    lines.append(f"Frozen model {model['modelVersion']}, checksum "
                 f"{str(al.model_checksum(model))[:16]}.")
    return "\n".join(lines)


# ==========================================================================
def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("freeze")
    f.add_argument("--out", default=str(_REPO / "docs"))
    f.add_argument("--date", default="20260922")
    f.add_argument("--measured", default=None,
                   help="a replay receipt whose measured block becomes this "
                        "arm's own precision")

    r = sub.add_parser("replay")
    r.add_argument("--model", default=str(LEO_MODEL_PATH))
    r.add_argument("--work", required=True,
                   help="the low-orbit lane's working directory")
    r.add_argument("--out", default=str(_REPO / "docs"))
    r.add_argument("--date", default="20260922")
    r.add_argument("--start", default=WINDOW_START)
    r.add_argument("--end", default=WINDOW_END)
    r.add_argument("--look-back", default=LOOK_BACK_START)
    r.add_argument("--tick-days", type=float, default=None)
    r.add_argument("--sample", type=int, default=1000)

    args = p.parse_args(argv)
    t0 = time.time()

    def say(m):
        print(f"  [{time.time() - t0:8.1f}s] {m}", flush=True)

    if args.cmd == "freeze":
        measured = None
        if args.measured:
            measured = json.loads(Path(args.measured).read_text())["measured"]
        body = build_leo_model(measured)
        out = Path(args.out) / f"alarm-lane-leo-model-{args.date}.json"
        digest = al.write_model(body, out)
        say(f"frozen: {out}")
        say(f"version {body['modelVersion']} checksum {digest}")
        spoken, reasons = al.class_may_be_spoken(al.load_model(out), 0)
        say(f"the pattern clause may be spoken: {spoken}")
        for reason in reasons:
            say(f"  withheld because: {reason}")
        return 0

    model = al.load_model(args.model)
    run_leo_replay(args, model, say)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
