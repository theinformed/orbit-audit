#!/usr/bin/env python3
"""T13 -- the manoeuvre library: a versioned rule set that names what the
elements did across a detected burn.

Registration: docs/manoeuvre-library-preregistration-20260922.md (v1),
docs/manoeuvre-library-v2-preregistration-20260922.md (v2).
Design: docs/kinematic-reach-design-20260922.md section 5.

The whole instrument is threshold comparisons on element deltas. There is no
fitting, no training, no learned parameter, no weight and no tuned cut. Every
threshold in a rule set is a constant a committed registration already fixed,
or -- in v2's one case -- derived here by the arithmetic its registration
writes out, and it carries the file and symbol it came from in the rule table
itself, so the rule table's own checksum is the identity of the rule set.

TWO VERSIONS LIVE IN THIS FILE, and the version is never defaulted. v1 is the
frozen rule set of commit 343a112. v2 changes exactly one thing: the arm-G
inclination clause tests the NET change against a natural-motion prediction,
on a floor that grows with the burn's own differencing span, instead of the
raw difference against a fixed bar. Every call that assigns, tables or hashes
a rule set names its version, because a type read without its version is an
unversioned label (v1 registration section 7.2).

Three properties the tests hold this file to, because a comment is not a
capability:

  * EXACTLY ONE RULE. A type is assigned only when exactly one rule fires. Zero
    rules or two rules both give UNLABELLED, the second with the competing rule
    ids named. There is no tie-break and no default type anywhere in this file.
  * CAUSAL. A burn is typed from the element sets either side of it and from the
    object's own history STRICTLY BEFORE it. Nothing reads an element set later
    than the burn it types. The two types that need a later burn -- relocation
    and the transfer-leg run -- are episode records over already-typed burns and
    they never change a burn's type.
  * ELEMENT-ONLY INPUTS. The rule inputs are epoch, mean motion, eccentricity,
    inclination, right ascension of the ascending node, argument of perigee,
    mean anomaly, and the object's own earlier station segments and earlier
    flags. No registry code, no country, no operator, no name, no object type.
    Those are read by the controls, which are diagnostics on the rule set and
    are not rules.

Nothing here computes, stores or prints a figure in units of speed, of mass or
of what a burn consumed. Element units only.
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO / "tools") not in sys.path:
    sys.path.insert(0, str(_REPO / "tools"))

import proximity_geo as pg                      # noqa: E402
import proximity_plane as pp                    # noqa: E402
import stationkeeping_efficiency as se          # noqa: E402

LIBRARY_VERSIONS = ("v1", "v2")
REGISTRATIONS = {
    "v1": "docs/manoeuvre-library-preregistration-20260922.md",
    "v2": "docs/manoeuvre-library-v2-preregistration-20260922.md",
}


def _check_version(version):
    """No default. v1 registration section 7.2: a consumer that reads a type
    without pinning the version is reading an unversioned label."""
    if version not in LIBRARY_VERSIONS:
        raise ValueError(f"library version must be one of {LIBRARY_VERSIONS}")
    return version

# ==========================================================================
# Registration section 3 -- the registered floors. Every one of these is a
# constant another track fixed; the SOURCE string is part of the rule table's
# checksum, so a floor cannot be moved without changing the library's identity.
# ==========================================================================
FLOORS = {
    "burnFloorDegPerDay": {
        "value": pg.BURN_FLOOR_DEG_PER_DAY,
        "source": "tools/proximity_geo.py::BURN_FLOOR_DEG_PER_DAY (T8a prereg 5.5)",
    },
    "stationedBandDegPerDay": {
        "value": 6.0 * pg.X_PRIMARY_DEG / pg.D_PRIMARY_DAYS,
        "source": "tools/trigger_alarm.py::SLOT_DRIFT_FLOOR = 6 * X / D (T8d)",
    },
    "incBarDeg": {
        "value": 5.0 * 1.67e-4,
        "source": ("5 sigma_i on sigma_i = 1.67e-4 deg, docs/orbit-history-design.md "
                   "section 2 table, already floored at the 1e-4 deg publication quantum"),
    },
    "coLocationHalfWidthDeg": {
        "value": pg.X_PRIMARY_DEG,
        "source": "tools/proximity_geo.py::X_PRIMARY_DEG (T8a prereg 4)",
    },
    "relocationBarDeg": {
        "value": pg.X_FAR_DEG,
        "source": "tools/proximity_geo.py::X_FAR_DEG (T8a prereg 4)",
    },
    "stationHalfWidthDeg": {
        "value": pg.STATION_HALF_WIDTH_DEG,
        "source": "tools/proximity_geo.py::STATION_HALF_WIDTH_DEG (T8a prereg 5.3)",
    },
    "stationMinDays": {
        "value": pg.STATION_MIN_DAYS,
        "source": "tools/proximity_geo.py::STATION_MIN_DAYS (T8a prereg 5.3)",
    },
    "matchToleranceDays": {
        "value": pg.MAX_GAP_DAYS,
        "source": ("tools/proximity_geo.py::MAX_GAP_DAYS (T8a prereg 4); the same "
                   "value is T8d's MERGE_DAYS and CONFIRM_DAYS"),
    },
    "inTrackFloorKm": {
        "value": pp.DA_FLOOR_KM,
        "source": "tools/proximity_plane.py::DA_FLOOR_KM (T8b prereg 5.4)",
    },
    "planeFloorDeg": {
        "value": pp.I_FLOOR_DEG,
        "source": "tools/proximity_plane.py::I_FLOOR_DEG (T8b prereg 5.4)",
    },
    "campaignGapDays": {
        "value": pp.CAMPAIGN_MAX_GAP_DAYS,
        "source": "tools/proximity_plane.py::CAMPAIGN_MAX_GAP_DAYS (T8b prereg 5.5)",
    },
    "graveyardRaiseKm": {
        "value": 235.0,
        "source": "pipeline/orbit_events.py::GEO_GRAVEYARD_MINIMUM_RAISE_KM",
    },
    "geoSemiMajorAxisKm": {
        "value": 42164.0,
        "source": "pipeline/orbit_events.py::GEO_SEMI_MAJOR_AXIS_KM",
    },
    "terminalDecayPerigeeKm": {
        "value": 200.0,
        "source": "pipeline/orbit_events.py::TERMINAL_DECAY_PERIGEE_KM",
    },
}

# ==========================================================================
# v2 registration section 3 -- the two constants of the net-change floor.
# Neither is picked. The first is a MEASURED residual, the second is a
# MEASURED disagreement between a model and a calibration, and the floor is
# their quadrature sum with no multiple applied to either, because a multiple
# would be a pick and this archive's tails forbid a Gaussian one.
# ==========================================================================

# The pole-position residual of THIS SAME predictor over 948,942 quiet GEO
# arcs of median span 0.502 d. At that span the rotation's own error is
# negligible, so this is the differencing term at zero span: it already
# contains the fit scatter of both element sets and the periodic terms the
# secular model omits. Its own committed note calls it an upper bound.
POLE_RESIDUAL_DEG = 9.683819956551464e-4

# The pole speed at zero inclination, two ways. The model's is arithmetic on
# the Laplace constants; the calibration's is the median over the 33 objects
# that had stopped north-south keeping. They disagree, and the disagreement is
# the prediction's own uncertainty -- a RATE error, so it grows with the span.
MODEL_POLE_SPEED_DEG_PER_YEAR = (
    (360.0 / se.LAPLACE_PRECESSION_PERIOD_YR)
    * math.sin(math.radians(se.LAPLACE_TILT_DEG)))
CALIBRATED_POLE_SPEED_DEG_PER_YEAR = 0.7372991976588145

# The calibration medians themselves, used ONLY by the sensitivity arm of v2
# registration section 3. No rule reads them.
CALIBRATED_TILT_DEG = 6.747126521374816
CALIBRATED_PRECESSION_PERIOD_YR = 56.23362481563609
RATE_ERROR_DEG_PER_DAY = (
    abs(MODEL_POLE_SPEED_DEG_PER_YEAR - CALIBRATED_POLE_SPEED_DEG_PER_YEAR)
    / se.DAYS_PER_YEAR)

_NET_SOURCE = (
    "v2 prereg section 3, derived: hypot(poleResidualDeg, rateErrorDegPerDay "
    "* naturalSpanDays). poleResidualDeg 9.683819956551464e-4 deg is "
    "docs/stationkeeping-efficiency-20260922-receipt.json "
    "poleNoiseFloor.sigmaPoleDeg, measured on 948942 quiet GEO arcs. "
    "rateErrorDegPerDay is |modelPoleSpeedDegPerYear - "
    "laplaceCalibrationUnregistered.poleSpeedDegPerYear.median| / 365.25 from "
    "the same receipt, the model being (360 / "
    "stationkeeping_efficiency.LAPLACE_PRECESSION_PERIOD_YR) * "
    "sin(stationkeeping_efficiency.LAPLACE_TILT_DEG). No multiple is applied "
    "to either term")

# Captured BEFORE the v2 entries are added. A v1 artifact must carry the v1
# floor block and nothing else, or a v1 rerun would not reproduce the
# committed v1 artifact -- which is the whole point of keeping v1 runnable.
V1_FLOOR_NAMES = tuple(FLOORS)

FLOORS["netPoleResidualDeg"] = {"value": POLE_RESIDUAL_DEG,
                                "source": _NET_SOURCE}
FLOORS["netRateErrorDegPerDay"] = {"value": RATE_ERROR_DEG_PER_DAY,
                                   "source": _NET_SOURCE}
V2_FLOOR_NAMES = tuple(FLOORS)


def floors_for(version):
    names = V1_FLOOR_NAMES if _check_version(version) == "v1" else V2_FLOOR_NAMES
    return {k: FLOORS[k] for k in names}

BURN_FLOOR = FLOORS["burnFloorDegPerDay"]["value"]
STATIONED_BAND = FLOORS["stationedBandDegPerDay"]["value"]
INC_BAR_DEG = FLOORS["incBarDeg"]["value"]
CO_LOCATION_DEG = FLOORS["coLocationHalfWidthDeg"]["value"]
RELOCATION_BAR_DEG = FLOORS["relocationBarDeg"]["value"]
MATCH_TOLERANCE_DAYS = FLOORS["matchToleranceDays"]["value"]
IN_TRACK_FLOOR_KM = FLOORS["inTrackFloorKm"]["value"]
PLANE_FLOOR_DEG = FLOORS["planeFloorDeg"]["value"]
CAMPAIGN_GAP_DAYS = FLOORS["campaignGapDays"]["value"]
GRAVEYARD_RAISE_KM = FLOORS["graveyardRaiseKm"]["value"]
GEO_A_KM = FLOORS["geoSemiMajorAxisKm"]["value"]
DECAY_PERIGEE_KM = FLOORS["terminalDecayPerigeeKm"]["value"]

UNDERPOWERED_MIN = 20                 # registration section 8, Gate U
PARTITION_BAR = 0.05                  # registration section 8, Gate P
LEAK_RATIO_BAR = 0.10                 # registration section 8, Gate L (T8b Gate B)

UNLABELLED = "UNLABELLED"

# What a run of each version PUBLISHES. The v1 tuples are frozen: the burn
# record now carries the v2 net fields whatever version is running, and a v1
# run must not let them reach its ledger or its quantile block.
V1_REPORTED_DELTAS = ("deltaIncDeg", "deltaDriftDegPerDay", "deltaAKm",
                      "baselineSpanDays")
V2_REPORTED_DELTAS = ("deltaIncNetDeg", "deltaIncNetJ2Deg",
                      "deltaIncNetMeasuredModelDeg", "naturalSpanDays",
                      "netFloorDeg", "ratioNetOverRawAbs")
V1_LEDGER_DELTAS = ("deltaDriftDegPerDay", "deltaIncDeg", "deltaAKm",
                    "baselineSpanDays")
V2_LEDGER_DELTAS = ("deltaIncNetDeg", "naturalSpanDays", "netFloorDeg")

# v2 registration section 6.3: the three discriminations that must be
# published whatever they show. All three are computed in the same pass as
# the run, off the SAME burn records, so none of them is a second experiment.
#  1. the arm-G unlabelled fraction binned by the differencing span, under
#     both versions. v1's clause is measuring spacing, so v1's curve must
#     climb; if v2's climbs too, the change failed.
#  2. how much of the raw inclination change the prediction removes, as the
#     per-burn ratio |net| / |raw|. Near 1 means it removed nothing.
#  3. the arm-G type mix under the two model variants, so a v2 number that is
#     really a statement about a model choice says so.
SPAN_BIN_EDGES_DAYS = (0.0, 4.27, 9.99, 18.04, 29.92, 60.87, float("inf"))
PREDICTION_VARIANTS = {
    "asRegistered": "deltaIncNetDeg",
    "withJ2AddedOnTop": "deltaIncNetJ2Deg",
    "atTheCalibratedCircuit": "deltaIncNetMeasuredModelDeg",
}

# Label classes with no epoch: they support an object-level statement only
# (registration section 6.2).
OBJECT_LEVEL_LABEL_CLASSES = ("t10cEastWestObject", "t8bPlaneFlaggedObject")

# The element fields a rule is allowed to read. A test enforces this list by
# reading the source of every rule (registration section 7.3).
RULE_INPUT_FIELDS = (
    "epochMs", "driftBeforeDegPerDay", "driftAfterDegPerDay",
    "deltaDriftDegPerDay", "incBeforeDeg", "incAfterDeg", "deltaIncDeg",
    "lambdaAfterDeg", "aBeforeKm", "aAfterKm", "deltaAKm",
    "perigeeAltBeforeKm", "insideStationSegment", "priorStationHeld",
    "channel", "previousInTrackDeltaASign",
    # v2 only. Both are built from element sets that lie strictly before the
    # flag, plus the flag element set itself, so the causal discipline holds.
    "deltaIncNetDeg", "naturalSpanDays",
)


# ==========================================================================
# Registration section 4 -- the rule table
# ==========================================================================
class Rule:
    """One rule. `test` reads a burn record and returns True or False."""

    __slots__ = ("rid", "type_name", "arm", "clauses", "thresholds", "test",
                 "expected_label", "propulsive", "stage")

    def __init__(self, rid, type_name, arm, clauses, thresholds, test,
                 expected_label=None, propulsive=True, stage=1):
        self.rid = rid
        self.type_name = type_name
        self.arm = arm
        self.clauses = tuple(clauses)
        self.thresholds = tuple(thresholds)
        self.test = test
        self.expected_label = expected_label
        self.propulsive = propulsive
        self.stage = stage

    def as_dict(self):
        return {
            "id": self.rid,
            "type": self.type_name,
            "arm": self.arm,
            "clauses": list(self.clauses),
            "thresholds": [
                {"name": t, "value": FLOORS[t]["value"], "source": FLOORS[t]["source"]}
                for t in self.thresholds
            ],
            "expectedLabelClass": self.expected_label,
            "propulsive": self.propulsive,
            "stage": self.stage,
        }


def _finite(*vals):
    return all(v is not None and np.isfinite(v) for v in vals)


# ---- arm G, near-GEO -------------------------------------------------------
def _g_decaying(b):
    return _finite(b["perigeeAltBeforeKm"]) and b["perigeeAltBeforeKm"] < DECAY_PERIGEE_KM


def _g_graveyard(b):
    if not _finite(b["aBeforeKm"], b["aAfterKm"]):
        return False
    return ((b["aBeforeKm"] - GEO_A_KM) < GRAVEYARD_RAISE_KM
            <= (b["aAfterKm"] - GEO_A_KM))


def _g_drift_start(b):
    if not _finite(b["deltaDriftDegPerDay"], b["driftBeforeDegPerDay"],
                   b["driftAfterDegPerDay"], b["deltaIncDeg"]):
        return False
    return (abs(b["deltaDriftDegPerDay"]) >= BURN_FLOOR
            and abs(b["driftAfterDegPerDay"]) > STATIONED_BAND
            and abs(b["driftBeforeDegPerDay"]) <= STATIONED_BAND
            and abs(b["deltaIncDeg"]) < INC_BAR_DEG)


def _g_stop_geometry(b):
    if not _finite(b["driftBeforeDegPerDay"], b["driftAfterDegPerDay"]):
        return False
    return (abs(b["driftBeforeDegPerDay"]) > STATIONED_BAND
            and abs(b["driftAfterDegPerDay"]) <= STATIONED_BAND)


def _g_drift_stop(b):
    return _g_stop_geometry(b) and b["priorStationHeld"] is True


def _g_station_acquisition(b):
    return _g_stop_geometry(b) and b["priorStationHeld"] is False


def _g_east_west(b):
    if not _finite(b["deltaDriftDegPerDay"], b["driftBeforeDegPerDay"],
                   b["driftAfterDegPerDay"], b["deltaIncDeg"]):
        return False
    return (abs(b["deltaDriftDegPerDay"]) >= BURN_FLOOR
            and abs(b["driftBeforeDegPerDay"]) <= STATIONED_BAND
            and abs(b["driftAfterDegPerDay"]) <= STATIONED_BAND
            and bool(b["insideStationSegment"])
            and abs(b["deltaIncDeg"]) < INC_BAR_DEG)


def _g_north_south(b):
    if not _finite(b["deltaIncDeg"], b["deltaDriftDegPerDay"]):
        return False
    return (abs(b["deltaIncDeg"]) >= INC_BAR_DEG
            and abs(b["deltaDriftDegPerDay"]) < BURN_FLOOR)


# ---- arm G, v2: the net-change inclination clause --------------------------
def net_floor_deg(burn):
    """The v2 inclination floor for one burn, in degrees.

    Quadrature sum of the two errors that make the net change: the measured
    pole residual of this predictor at zero span, and the measured rate
    disagreement integrated over this burn's own natural span. Nothing is
    multiplied by anything. v2 registration section 3.

    A burn whose natural span is not finite has no prediction and therefore no
    floor; the rules below refuse it rather than substituting a constant.
    """
    span = burn.get("naturalSpanDays")
    if span is None or not np.isfinite(span):
        return None
    return float(math.hypot(POLE_RESIDUAL_DEG, RATE_ERROR_DEG_PER_DAY * span))


def _g_drift_start_v2(b):
    floor = net_floor_deg(b)
    if floor is None or not _finite(b["deltaDriftDegPerDay"],
                                    b["driftBeforeDegPerDay"],
                                    b["driftAfterDegPerDay"],
                                    b["deltaIncNetDeg"]):
        return False
    return (abs(b["deltaDriftDegPerDay"]) >= BURN_FLOOR
            and abs(b["driftAfterDegPerDay"]) > STATIONED_BAND
            and abs(b["driftBeforeDegPerDay"]) <= STATIONED_BAND
            and abs(b["deltaIncNetDeg"]) < floor)


def _g_east_west_v2(b):
    floor = net_floor_deg(b)
    if floor is None or not _finite(b["deltaDriftDegPerDay"],
                                    b["driftBeforeDegPerDay"],
                                    b["driftAfterDegPerDay"],
                                    b["deltaIncNetDeg"]):
        return False
    return (abs(b["deltaDriftDegPerDay"]) >= BURN_FLOOR
            and abs(b["driftBeforeDegPerDay"]) <= STATIONED_BAND
            and abs(b["driftAfterDegPerDay"]) <= STATIONED_BAND
            and bool(b["insideStationSegment"])
            and abs(b["deltaIncNetDeg"]) < floor)


def _g_north_south_v2(b):
    floor = net_floor_deg(b)
    if floor is None or not _finite(b["deltaIncNetDeg"],
                                    b["deltaDriftDegPerDay"]):
        return False
    return (abs(b["deltaIncNetDeg"]) >= floor
            and abs(b["deltaDriftDegPerDay"]) < BURN_FLOOR)


# ---- arm P, everything outside the near-GEO band ---------------------------
def _p_decaying(b):
    return _finite(b["perigeeAltBeforeKm"]) and b["perigeeAltBeforeKm"] < DECAY_PERIGEE_KM


def _p_inclination_adjust(b):
    if b["channel"] not in ("plane", "both"):
        return False
    if not _finite(b["deltaIncDeg"], b["deltaAKm"]):
        return False
    return abs(b["deltaIncDeg"]) >= PLANE_FLOOR_DEG and abs(b["deltaAKm"]) < IN_TRACK_FLOOR_KM


def _p_in_track_candidate(b):
    return (b["channel"] == "intrack" and _finite(b["deltaAKm"])
            and abs(b["deltaAKm"]) >= IN_TRACK_FLOOR_KM)


def _p_phasing(b):
    if not _p_in_track_candidate(b):
        return False
    prev = b["previousInTrackDeltaASign"]
    if prev is None or prev == 0:
        return False
    return prev != (1 if b["deltaAKm"] > 0 else -1)


def _p_orbit_raise(b):
    return _p_in_track_candidate(b) and b["deltaAKm"] > 0 and not _p_phasing(b)


def _p_orbit_lower(b):
    return _p_in_track_candidate(b) and b["deltaAKm"] < 0 and not _p_phasing(b)


RULES_V1 = (
    Rule("G6", "graveyard raise", "G",
         ["(a_before - 42164.0 km) < 235.0 km <= (a_after - 42164.0 km)"],
         ["graveyardRaiseKm", "geoSemiMajorAxisKm"], _g_graveyard, None,
         stage=0),
    Rule("G7", "decaying", "G",
         ["perigee altitude before the burn < 200.0 km"],
         ["terminalDecayPerigeeKm"], _g_decaying, None, propulsive=False,
         stage=0),
    Rule("G1", "drift start", "G",
         ["|delta drift| >= 0.010 deg/day",
          "|drift after| > 0.020 deg/day",
          "|drift before| <= 0.020 deg/day",
          "|delta inclination| < 8.35e-4 deg"],
         ["burnFloorDegPerDay", "stationedBandDegPerDay", "incBarDeg"],
         _g_drift_start, "t8aInitiatingFlag"),
    Rule("G2", "drift stop", "G",
         ["|drift before| > 0.020 deg/day",
          "|drift after| <= 0.020 deg/day",
          "an earlier station segment of this object has median longitude "
          "within 0.1 deg of the post-burn longitude"],
         ["stationedBandDegPerDay", "coLocationHalfWidthDeg",
          "stationHalfWidthDeg", "stationMinDays"],
         _g_drift_stop, "t8aArrival"),
    Rule("G3", "station acquisition", "G",
         ["|drift before| > 0.020 deg/day",
          "|drift after| <= 0.020 deg/day",
          "no earlier station segment of this object has median longitude "
          "within 0.1 deg of the post-burn longitude"],
         ["stationedBandDegPerDay", "coLocationHalfWidthDeg",
          "stationHalfWidthDeg", "stationMinDays"],
         _g_station_acquisition, "t10aPostTransferEndpoint"),
    Rule("G4", "east-west keeping", "G",
         ["|delta drift| >= 0.010 deg/day",
          "|drift before| <= 0.020 deg/day",
          "|drift after| <= 0.020 deg/day",
          "the burn epoch is inside a station segment",
          "|delta inclination| < 8.35e-4 deg"],
         ["burnFloorDegPerDay", "stationedBandDegPerDay", "incBarDeg",
          "stationHalfWidthDeg", "stationMinDays"],
         _g_east_west, "t10cEastWestObject"),
    Rule("G5", "north-south keeping", "G",
         ["|delta inclination| >= 8.35e-4 deg",
          "|delta drift| < 0.010 deg/day"],
         ["incBarDeg", "burnFloorDegPerDay"],
         _g_north_south, "t10bNorthSouth"),
    Rule("P1", "decaying", "P",
         ["perigee altitude before the burn < 200.0 km"],
         ["terminalDecayPerigeeKm"], _p_decaying, None, propulsive=False,
         stage=0),
    Rule("P2", "inclination adjust", "P",
         ["the plane channel fired at this epoch",
          "|delta inclination| >= 0.01 deg",
          "|delta semi-major axis| < 0.050 km"],
         ["planeFloorDeg", "inTrackFloorKm"],
         _p_inclination_adjust, "t8bPlaneFlaggedObject"),
    Rule("P3", "phasing", "P",
         ["the in-track channel fired and the plane channel did not",
          "|delta semi-major axis| >= 0.050 km",
          "the previous in-track flag within 180 d exists and has the "
          "opposite sign of delta semi-major axis"],
         ["inTrackFloorKm", "campaignGapDays"],
         _p_phasing, "t8bCampaignStart"),
    Rule("P4", "orbit raise", "P",
         ["the in-track channel fired and the plane channel did not",
          "delta semi-major axis >= +0.050 km",
          "the phasing rule does not hold"],
         ["inTrackFloorKm", "campaignGapDays"],
         _p_orbit_raise, "t10aTransferInterval"),
    Rule("P5", "orbit lower", "P",
         ["the in-track channel fired and the plane channel did not",
          "delta semi-major axis <= -0.050 km",
          "the phasing rule does not hold"],
         ["inTrackFloorKm", "campaignGapDays"],
         _p_orbit_lower, "t10aTransferInterval"),
)

# ==========================================================================
# v2 registration section 4 -- the v2 rule table. Built from v1's, replacing
# exactly the four entries the registration names and copying the other eight
# BY REFERENCE, so that byte-identity is a property of the construction and
# not something a later reader has to trust. Section 5's assertion checks it
# anyway, because a construction is not a proof.
# ==========================================================================
_NET_CLAUSE = (
    "hypot({!r} deg, {!r} deg/day * natural span days)".format(
        POLE_RESIDUAL_DEG, RATE_ERROR_DEG_PER_DAY))

_V2_REPLACEMENTS = {
    "G1": Rule("G1", "drift start", "G",
               ["|delta drift| >= 0.010 deg/day",
                "|drift after| > 0.020 deg/day",
                "|drift before| <= 0.020 deg/day",
                "|net delta inclination| < " + _NET_CLAUSE],
               ["burnFloorDegPerDay", "stationedBandDegPerDay",
                "netPoleResidualDeg", "netRateErrorDegPerDay"],
               _g_drift_start_v2, "t8aInitiatingFlag"),
    "G3": Rule("G3", "station acquisition", "G",
               ["|drift before| > 0.020 deg/day",
                "|drift after| <= 0.020 deg/day",
                "no earlier station segment of this object has median "
                "longitude within 0.1 deg of the post-burn longitude"],
               ["stationedBandDegPerDay", "coLocationHalfWidthDeg",
                "stationHalfWidthDeg", "stationMinDays"],
               _g_station_acquisition, "t8aArrival"),
    "G4": Rule("G4", "east-west keeping", "G",
               ["|delta drift| >= 0.010 deg/day",
                "|drift before| <= 0.020 deg/day",
                "|drift after| <= 0.020 deg/day",
                "the burn epoch is inside a station segment",
                "|net delta inclination| < " + _NET_CLAUSE],
               ["burnFloorDegPerDay", "stationedBandDegPerDay",
                "netPoleResidualDeg", "netRateErrorDegPerDay",
                "stationHalfWidthDeg", "stationMinDays"],
               _g_east_west_v2, "t10cEastWestObject"),
    "G5": Rule("G5", "north-south keeping", "G",
               ["|net delta inclination| >= " + _NET_CLAUSE,
                "|delta drift| < 0.010 deg/day"],
               ["netPoleResidualDeg", "netRateErrorDegPerDay",
                "burnFloorDegPerDay"],
               _g_north_south_v2, "t10bNorthSouth"),
}

RULES_V2 = tuple(_V2_REPLACEMENTS.get(r.rid, r) for r in RULES_V1)

RULE_SETS = {"v1": RULES_V1, "v2": RULES_V2}
RULES_BY_ID = {v: {r.rid: r for r in rules} for v, rules in RULE_SETS.items()}
ALL_RULE_FUNCTIONS = tuple(dict.fromkeys(
    r.test for rules in RULE_SETS.values() for r in rules))
EPISODE_TYPES = ("relocation", "transfer-leg run")

# The rule ids v2 changes, and the ids it leaves alone. Both halves are
# asserted: a version that changed a rule without changing its hash would be
# unversioned, and a version that changed a rule it said it would not is a
# different change from the one registered. v2 registration section 5.
V2_CHANGED_RULE_IDS = ("G1", "G3", "G4", "G5")
V2_UNCHANGED_RULE_IDS = ("G2", "G6", "G7", "P1", "P2", "P3", "P4", "P5")


def rules(version):
    return RULE_SETS[_check_version(version)]


def type_names(version):
    return tuple(dict.fromkeys(
        r.type_name for r in rules(version))) + (UNLABELLED,)


def rule_table(version):
    return [r.as_dict() for r in rules(version)]


def canonical_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def rules_sha256(version):
    return hashlib.sha256(canonical_json(rule_table(version))).hexdigest()


def per_rule_sha256(version):
    """The identity of each rule on its own, so that 'every other rule is
    byte-identical' can be checked by a reader rather than taken."""
    return {r.rid: hashlib.sha256(canonical_json(r.as_dict())).hexdigest()
            for r in rules(version)}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ==========================================================================
# Registration section 4/5 -- assignment. Exactly one rule, or UNLABELLED.
# ==========================================================================
def fired_rules(burn, version, stage=None):
    arm = burn["arm"]
    return [r.rid for r in rules(version)
            if r.arm == arm and (stage is None or r.stage == stage)
            and r.test(burn)]


def assign_type(burn, version):
    """The registered two-stage evaluation of section 4.1 and 4.2.

    Stage 0 is a precedence the registration fixed before any number: G6 then
    G7 on arm G, P1 on arm P, each naming a condition on the orbit itself that
    the drift-rate and channel rules cannot see. The first stage-0 rule that
    fires assigns the type, and `alsoSatisfiedStage1` records whether a stage-1
    rule would have fired too, so nothing is hidden by the precedence.

    Stage 1 is the mutually exclusive set. Exactly one rule fires -> that type.
    Zero, or two or more -> UNLABELLED, with the reason and, when two or more
    fired, the competing rule ids. There is no tie-break at stage 1.
    """
    _check_version(version)
    for rule in rules(version):
        if rule.arm != burn["arm"] or rule.stage != 0:
            continue
        if rule.test(burn):
            return {"type": rule.type_name, "ruleId": rule.rid,
                    "competingRules": [], "reason": None,
                    "alsoSatisfiedStage1": bool(
                        fired_rules(burn, version, stage=1))}
    fired = fired_rules(burn, version, stage=1)
    if len(fired) == 1:
        rid = fired[0]
        return {"type": RULES_BY_ID[version][rid].type_name, "ruleId": rid,
                "competingRules": [], "reason": None,
                "alsoSatisfiedStage1": False}
    if not fired:
        return {"type": UNLABELLED, "ruleId": None, "competingRules": [],
                "reason": "no-rule", "alsoSatisfiedStage1": False}
    return {"type": UNLABELLED, "ruleId": None, "competingRules": fired,
            "reason": "multi-fire", "alsoSatisfiedStage1": False}


# ==========================================================================
# Arm G -- building the burn records from the cached near-GEO extract
# ==========================================================================
def _perigee_alt_km(a_km, ecc):
    return a_km * (1.0 - ecc) - pg.EARTH_RADIUS_KM


def _semi_major_km(mean_motion_rev_day):
    n_rad_s = 2.0 * math.pi * np.asarray(mean_motion_rev_day) / 86400.0
    return float((pg.MU_KM3_S2 / n_rad_s ** 2) ** (1.0 / 3.0))


def _a_from_drift_km(drift_deg_per_day):
    """Kepler's third law, exactly, from the drift the detector measured.

    ddot = 360 n - omega_E inverts to the object's own mean motion, and
    a = (mu / (2 pi n / 86400)^2)^(1/3). The repository also carries a
    LINEARISED offset (`proximity_geo.semi_major_offset_km`), whose own
    docstring says it is interpretive and never inside a detector decision --
    so it is not used here, where a rule reads the value.
    """
    n_rev_day = (float(drift_deg_per_day) + pg.OMEGA_E_DEG_PER_DAY) / 360.0
    return _semi_major_km(n_rev_day)


def trailing_baseline(values, window=pg.BURN_BASELINE_SAMPLES):
    """The registered detector's own trailing median, reproduced exactly as
    `proximity_geo.drift_change_flags` computes it: base[i] is the median of
    the `window` samples that END BEFORE i.

    This is load-bearing. The flag epoch is the SECOND confirming element set
    (T8a prereg 5.5), so the element set immediately before a flag is already
    on the far side of the change and the naive difference across it is near
    zero. The detector measures the change against this baseline, and so does
    the library, or the library would be typing a different quantity from the
    one that was detected.
    """
    v = np.asarray(values, dtype=np.float64)
    n = v.size
    base = np.full(n, np.nan)
    if n < window + 2:
        return base
    windows = np.lib.stride_tricks.sliding_window_view(v[:n - 1], window)
    base[window:] = np.median(windows[:n - window], axis=1)
    return base


def trailing_median_pole(inc, raan, epoch_ms, window=pg.BURN_BASELINE_SAMPLES):
    """The baseline POLE and the baseline EPOCH, v2 registration section 2.3.

    The vector form of the detector's own trailing-median statistic. `inc`
    alone already has one (`trailing_baseline`); the node wraps, so a median
    of the angle is not defined and the median is taken componentwise on the
    unit pole vector and renormalised -- a componentwise median of unit
    vectors is not itself a unit vector. The epoch median is taken over the
    SAME samples under the SAME convention, so the value statistic and the
    epoch statistic describe the same point.

    Returns (inc_base, raan_base, epoch_base), each NaN where the window is
    not yet full. Every sample read ends strictly before index i.
    """
    inc = np.asarray(inc, dtype=np.float64)
    raan = np.asarray(raan, dtype=np.float64)
    ep = np.asarray(epoch_ms, dtype=np.float64)
    n = inc.size
    out = (np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan))
    if n < window + 2:
        return out
    si = np.sin(np.radians(inc))
    ci = np.cos(np.radians(inc))
    sr = np.sin(np.radians(raan))
    cr = np.cos(np.radians(raan))
    comps = (si * sr, -si * cr, ci)
    med = []
    for c in comps:
        w = np.lib.stride_tricks.sliding_window_view(c[:n - 1], window)
        m = np.full(n, np.nan)
        m[window:] = np.median(w[:n - window], axis=1)
        med.append(m)
    we = np.lib.stride_tricks.sliding_window_view(ep[:n - 1], window)
    out[2][window:] = np.median(we[:n - window], axis=1)
    px, py, pz = med
    norm = np.sqrt(px * px + py * py + pz * pz)
    with np.errstate(divide="ignore", invalid="ignore"):
        px, py, pz = px / norm, py / norm, pz / norm
    out[0][:] = np.degrees(np.arctan2(np.hypot(px, py), pz))
    out[1][:] = np.degrees(np.arctan2(px, -py)) % 360.0
    out[0][norm == 0.0] = np.nan
    return out


def _natural_prediction(inc_base, raan_base, a_km, ecc, span_days,
                        include_j2=False):
    """The committed natural-motion propagator, called and not reimplemented.

    v2 registration section 2.1/2.2: the Laplace-plane rotation alone is the
    primary, because the 7.4 deg tilt is already the balance between the
    luni-solar torque and the oblateness, so adding the nodal regression on
    top would double-count it. `include_j2` is the companion that measures how
    large that choice is, and no rule reads it.
    """
    if not all(np.isfinite(v) for v in (inc_base, raan_base, a_km, ecc,
                                        span_days)):
        return float("nan")
    inc_pred, _, _ = se.propagate_natural(
        float(inc_base), float(raan_base), float(a_km), float(ecc),
        float(span_days), include_j2=include_j2)
    return float(inc_pred)


def _natural_prediction_at(inc_base, raan_base, span_days, tilt_deg,
                           period_yr):
    """The same rotation at a different circuit geometry, composed from the
    committed primitives rather than by overwriting the committed defaults,
    which are bound at definition and would silently ignore the change.

    Used only by the sensitivity arm. A test asserts that this form reproduces
    `_natural_prediction` exactly when handed the committed constants, so the
    sensitivity is a change of constants and not a change of model.
    """
    if not all(np.isfinite(v) for v in (inc_base, raan_base, span_days)):
        return float("nan")
    p = se.pole_vector(float(inc_base), float(raan_base))
    omega = se.LAPLACE_SENSE * 360.0 / (period_yr * se.DAYS_PER_YEAR)
    axis = se.laplace_pole(tilt_deg)
    moved = se.rotate_about(p, axis, omega * float(span_days))
    norm = math.sqrt(sum(c * c for c in moved))
    if norm == 0.0:
        return float("nan")
    inc_pred, _ = se.pole_to_elements(tuple(c / norm for c in moved))
    return float(inc_pred)


def geo_burns(series, sigma_n, segs, grid_base_day):
    """Every confirmed drift-change flag of the registered GEO detector on one
    object, as a burn record. Causal in two places: the deltas are measured
    against the detector's own trailing baseline, which lies entirely before
    the flag, and `priorStationHeld` reads only station segments that END
    before the flag epoch.

    `grid_base_day` is the daily grid's own origin, the first return value of
    `proximity_geo.build_daily_grid`. A segment's grid offsets are relative to
    it, and an epoch built without it is off by the age of the archive.
    """
    flag_ms, _ = pg.drift_change_flags(series, sigma_n)
    if flag_ms.size == 0:
        return []
    base_d = trailing_baseline(series.drift)
    base_i = trailing_baseline(series.inc)
    pole_i, pole_raan, pole_epoch = trailing_median_pole(
        series.inc, series.raan, series.epoch_ms)
    idx = np.searchsorted(series.epoch_ms, flag_ms)
    seg_lon = []
    for i0, i1 in segs:
        lon = float(pg.wrap180(np.median(series.grid[i0:i1 + 1])))
        end_ms = (grid_base_day + series.grid_lo + i1 + 1) * pg.DAY_MS
        start_ms = (grid_base_day + series.grid_lo + i0) * pg.DAY_MS
        seg_lon.append((start_ms, end_ms, lon))
    out = []
    for k in idx:
        k = int(k)
        if k <= 0 or k >= series.epoch_ms.size:
            continue
        d_before = float(base_d[k - 1])
        i_before = float(base_i[k - 1])
        if not (np.isfinite(d_before) and np.isfinite(i_before)):
            continue
        t = float(series.epoch_ms[k])
        d_after = float(series.drift[k])
        a_before = _a_from_drift_km(d_before)
        a_after = _a_from_drift_km(d_after)
        lam_after = float(pg.wrap180(series.lam[k]))
        inc_now = float(series.inc[k])
        ecc_before = float(series.ecc[k - 1])
        # Index k - 1, not k: the pole baseline must be taken over the SAME
        # ten element sets the drift and inclination baselines above are taken
        # over, or the prediction would start from a different window from the
        # one the detector's own statistic used.
        pi_b = float(pole_i[k - 1])
        pr_b = float(pole_raan[k - 1])
        span_nat = (float((t - pole_epoch[k - 1]) / pg.DAY_MS)
                    if np.isfinite(pole_epoch[k - 1]) else float("nan"))
        inc_pred = _natural_prediction(pi_b, pr_b, a_before, ecc_before,
                                       span_nat)
        inc_pred_j2 = _natural_prediction(pi_b, pr_b, a_before, ecc_before,
                                          span_nat, include_j2=True)
        inc_pred_cal = _natural_prediction_at(
            pi_b, pr_b, span_nat, CALIBRATED_TILT_DEG,
            CALIBRATED_PRECESSION_PERIOD_YR)
        # STRICTLY earlier: a segment that merely starts later, at the same
        # longitude, is the future and may not be read to type the present.
        prior = any(end <= t and abs(pg.wrap180(lon - lam_after)) <= CO_LOCATION_DEG
                    for start, end, lon in seg_lon)
        inside = any(start <= t <= end for start, end, lon in seg_lon)
        out.append({
            "norad": series.norad, "arm": "G", "epochMs": t,
            "driftBeforeDegPerDay": d_before,
            "driftAfterDegPerDay": d_after,
            "deltaDriftDegPerDay": d_after - d_before,
            "incBeforeDeg": i_before,
            "incAfterDeg": float(series.inc[k]),
            "deltaIncDeg": float(series.inc[k]) - i_before,
            "lambdaAfterDeg": lam_after,
            "aBeforeKm": a_before, "aAfterKm": a_after,
            "deltaAKm": a_after - a_before,
            "perigeeAltBeforeKm": _perigee_alt_km(a_before, float(series.ecc[k - 1])),
            "insideStationSegment": inside,
            "priorStationHeld": prior,
            "channel": "drift",
            "previousInTrackDeltaASign": None,
            "incBaselinePoleDeg": pi_b,
            "raanBaselinePoleDeg": pr_b,
            "naturalSpanDays": span_nat,
            "incPredictedDeg": inc_pred,
            "deltaIncNetDeg": (inc_now - inc_pred
                               if np.isfinite(inc_pred) else float("nan")),
            "netFloorDeg": (float(math.hypot(
                POLE_RESIDUAL_DEG, RATE_ERROR_DEG_PER_DAY * span_nat))
                if np.isfinite(span_nat) else float("nan")),
            "deltaIncNetJ2Deg": (inc_now - inc_pred_j2
                                 if np.isfinite(inc_pred_j2) else float("nan")),
            "deltaIncNetMeasuredModelDeg": (
                inc_now - inc_pred_cal if np.isfinite(inc_pred_cal)
                else float("nan")),
            "baselineSpanDays": float(
                (series.epoch_ms[k]
                 - series.epoch_ms[max(0, k - 1 - pg.BURN_BASELINE_SAMPLES)])
                / pg.DAY_MS),
        })
    return out


# ==========================================================================
# Arm P -- burn records at the committed T8b flag epochs
# ==========================================================================
def _in_near_geo_band(n_rev_day, ecc, inc_deg):
    """T8a prereg 3.1. The arm-G detector owns these element sets."""
    return (pg.MM_MIN_REV_DAY <= n_rev_day <= pg.MM_MAX_REV_DAY
            and ecc < pg.ECC_MAX and inc_deg < pg.INC_MAX_DEG)


def plane_burns(el, intrack_ms, plane_ms):
    """Burn records for one object at the committed T8b flag epochs.

    The in-track delta is the DETECTOR'S OWN statistic, converted to
    kilometres of semi-major axis, not the one-step difference between the two
    element sets either side of the flag. `proximity_plane` flags on the
    residual of mean motion from a robust local fit over the preceding ten
    samples, and its flag epoch is the SECOND confirming set, so a one-step
    difference measures a different quantity from the one that was detected --
    the same defect the arm-G burn builder had, in the other channel. The
    conversion is Kepler's third law differentiated: a = (mu/(2 pi n/86400)^2)
    ^(1/3) gives da/dn = -2a / (3n), so da = -(2a / 3n) dn.

    Returns (records, missing_epochs) -- a flag epoch absent from the element
    cache is counted, never dropped silently (registration section 2).
    """
    ep = el["epoch_ms"]
    n, e, inc, raan = el["n"], el["e"], el["inc"], el["raan"]
    a = pp.semi_major_axis_km(n)
    t_days = ep / pp.DAY_MS
    res_n = pp.rolling_theil_sen_residual(t_days, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        d_a_series = -(2.0 * a / (3.0 * n)) * res_n
    om_pred = pp.j2_nodal_rate_deg_per_day(pp.centred_median(a, 5),
                                           pp.centred_median(e, 5),
                                           pp.centred_median(inc, 5))
    inc_base = trailing_baseline(inc)
    intrack = set(int(x) for x in intrack_ms)
    plane = set(int(x) for x in plane_ms)
    allflags = sorted(intrack | plane)
    pos = {}
    missing = 0
    for ms in allflags:
        j = int(np.searchsorted(ep, ms))
        if j >= ep.size or int(ep[j]) != ms or j == 0:
            missing += 1
            continue
        pos[ms] = j
    out = []
    prev_sign = None
    prev_t = None
    for ms in allflags:
        j = pos.get(ms)
        if j is None:
            continue
        in_i = ms in intrack
        in_p = ms in plane
        channel = "both" if (in_i and in_p) else ("intrack" if in_i else "plane")
        a_after = float(a[j])
        d_a = float(d_a_series[j])
        if not np.isfinite(d_a):
            d_a = 0.0
        a_before = a_after - d_a
        i_base = float(inc_base[j])
        i_before = i_base if np.isfinite(i_base) else float(inc[j - 1])
        d_inc = float(inc[j]) - i_before
        dt = float(t_days[j] - t_days[j - 1])
        d_om_res = float(pp.wrap180(raan[j] - raan[j - 1])
                         - 0.5 * (om_pred[j] + om_pred[j - 1]) * dt)
        near_geo = _in_near_geo_band(float(n[j - 1]), float(e[j - 1]),
                                     float(inc[j - 1]))
        sign_for_prev = prev_sign
        if prev_t is not None and (t_days[j] - prev_t) > CAMPAIGN_GAP_DAYS:
            sign_for_prev = None
        out.append({
            "norad": int(el["norad"]), "arm": "G-domain" if near_geo else "P",
            "epochMs": float(ms),
            "driftBeforeDegPerDay": None, "driftAfterDegPerDay": None,
            "deltaDriftDegPerDay": None,
            "incBeforeDeg": i_before, "incAfterDeg": float(inc[j]),
            "deltaIncDeg": d_inc,
            "lambdaAfterDeg": None,
            "aBeforeKm": a_before, "aAfterKm": a_after, "deltaAKm": d_a,
            "perigeeAltBeforeKm": _perigee_alt_km(a_before, float(e[j - 1])),
            "insideStationSegment": False, "priorStationHeld": None,
            "channel": channel,
            "previousInTrackDeltaASign": sign_for_prev,
            "deltaNodeResidualDeg": d_om_res,
            "baselineSpanDays": float(
                (ep[j] - ep[max(0, j - 1 - pp.BURN_BASELINE_SAMPLES)])
                / pp.DAY_MS),
        })
        if in_i and abs(d_a) >= IN_TRACK_FLOOR_KM:
            prev_sign = 1 if d_a > 0 else -1
            prev_t = float(t_days[j])
    return out, missing


# ==========================================================================
# Registration section 4.3 -- the episode types
# ==========================================================================
def relocation_episodes(typed_burns_for_object, seg_lookup):
    """E1. A drift start and the first following stop, where the station
    segment before the start and the one after the stop differ by >= 2.0 deg."""
    out = []
    starts = [b for b in typed_burns_for_object if b["type"] == "drift start"]
    stops = [b for b in typed_burns_for_object
             if b["type"] in ("drift stop", "station acquisition")]
    stop_ms = [b["epochMs"] for b in stops]
    for s in starts:
        j = bisect.bisect_right(stop_ms, s["epochMs"])
        if j >= len(stops):
            continue
        stop = stops[j]
        lon_before = seg_lookup(s["epochMs"], before=True)
        lon_after = seg_lookup(stop["epochMs"], before=False)
        if lon_before is None or lon_after is None:
            continue
        net = abs(float(pg.wrap180(lon_after - lon_before)))
        if net >= RELOCATION_BAR_DEG:
            out.append({"episode": "relocation", "norad": s["norad"],
                        "startMs": s["epochMs"], "stopMs": stop["epochMs"],
                        "stopType": stop["type"], "netChangeDeg": net})
    return out


def transfer_leg_runs(typed_burns_for_object):
    """E2. A maximal run of >= 2 consecutive same-direction in-plane burns
    within the campaign gap, with no intervening plane or phasing burn."""
    out = []
    run = []
    for b in typed_burns_for_object:
        t = b["type"]
        if t in ("orbit raise", "orbit lower"):
            if run and (b["type"] != run[-1]["type"]
                        or (b["epochMs"] - run[-1]["epochMs"])
                        / pp.DAY_MS > CAMPAIGN_GAP_DAYS):
                if len(run) >= 2:
                    out.append(_run_record(run))
                run = []
            run.append(b)
        elif t in ("inclination adjust", "phasing"):
            if len(run) >= 2:
                out.append(_run_record(run))
            run = []
    if len(run) >= 2:
        out.append(_run_record(run))
    return out


def _run_record(run):
    return {"episode": "transfer-leg run", "norad": run[0]["norad"],
            "direction": run[0]["type"], "burns": len(run),
            "startMs": run[0]["epochMs"], "endMs": run[-1]["epochMs"],
            "cumulativeDeltaAKm": float(sum(b["deltaAKm"] for b in run))}


# ==========================================================================
# Registration section 6 -- agreement
# ==========================================================================
def wilson(k, n, z=1.959963984540054):
    if n <= 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1.0 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


class LabelIndex:
    """Per-object sorted label epochs and windows, matched within the
    registered tolerance (section 6.3)."""

    def __init__(self, tolerance_days=MATCH_TOLERANCE_DAYS):
        self.tol_ms = tolerance_days * pg.DAY_MS
        self.by_object = {}

    def add(self, norad, label_class, start_ms, end_ms=None):
        self.by_object.setdefault(int(norad), []).append(
            (float(start_ms), float(end_ms if end_ms is not None else start_ms),
             label_class))

    def freeze(self):
        for k in self.by_object:
            self.by_object[k].sort()

    def nearest(self, norad, t_ms):
        """(label_class, distance_ms, contested) or None. A linear scan: a
        single object carries a handful of labels, and a clever index here
        would be a second place for the tolerance to live."""
        rows = self.by_object.get(int(norad))
        if not rows:
            return None
        best = None
        hits = 0
        for start, end, cls in rows:
            if t_ms < start - self.tol_ms or t_ms > end + self.tol_ms:
                continue
            d = 0.0 if start <= t_ms <= end else min(abs(t_ms - start),
                                                     abs(t_ms - end))
            hits += 1
            if best is None or d < best[1]:
                best = (cls, d)
        if best is None:
            return None
        return (best[0], best[1], hits > 1)


def load_labels(repo=_REPO):
    """Every committed label set of registration section 6.2 that carries an
    epoch. Object-level label sets are returned separately."""
    idx = LabelIndex()
    counts = {}
    objects = {}

    def bump(cls, n=1):
        counts[cls] = counts.get(cls, 0) + n

    p = repo / "docs" / "proximity-events-20260922.jsonl"
    for line in p.open():
        d = json.loads(line)
        if d.get("record") == "provenance":
            continue
        if d.get("initiatingFlagMs") is not None:
            idx.add(d["approacherNorad"], "t8aInitiatingFlag", d["initiatingFlagMs"])
            bump("t8aInitiatingFlag")
        if d.get("arrivalMs") is not None:
            idx.add(d["approacherNorad"], "t8aArrival", d["arrivalMs"])
            bump("t8aArrival")

    p = repo / "docs" / "transfer-loss-20260922.jsonl"
    for line in p.open():
        d = json.loads(line)
        if "norad" not in d:
            continue
        for iv in d.get("intervals", []):
            s = _parse_iso(iv.get("startAt"))
            e = _parse_iso(iv.get("endAt"))
            if s is None:
                continue
            idx.add(d["norad"], "t10aTransferInterval", s, e)
            bump("t10aTransferInterval")
        pe = _parse_iso(d.get("phaseEnd"))
        if pe is not None:
            idx.add(d["norad"], "t10aPostTransferEndpoint", pe)
            bump("t10aPostTransferEndpoint")

    p = repo / "docs" / "stationkeeping-ns-20260922.jsonl"
    for line in p.open():
        d = json.loads(line)
        if "_provenance" in d:
            continue
        s = _parse_iso(d.get("startAt"))
        e = _parse_iso(d.get("endAt"))
        if s is None:
            continue
        idx.add(d["norad"], "t10bNorthSouth", s, e)
        bump("t10bNorthSouth")

    p = repo / "docs" / "proximity-leo-events-20260922.jsonl"
    for line in p.open():
        d = json.loads(line)
        if not d.get("armM"):
            continue
        cs = d.get("campaignStartMs")
        if cs is None:
            continue
        idx.add(d["approacher"], "t8bCampaignStart", cs)
        bump("t8bCampaignStart")

    idx.freeze()

    ew = set()
    p = repo / "docs" / "stationkeeping-ew-20260922.jsonl"
    for line in p.open():
        d = json.loads(line)
        if "_provenance" in d:
            continue
        ew.add(int(d["norad"]))
    objects["t10cEastWestObject"] = ew

    return idx, counts, objects


def external_events(repo=_REPO):
    """The 34 hand-cited operator and agency events of
    `data/orbit_manoeuvre_truth.json`. Registration section 6.1: they are
    scorable for DETECTION and never for type -- all twelve objects are low
    Earth orbit and the vocabulary is operational, not kinematic. Returned as
    a list of (norad, epoch_ms, published_kind); the published kind is carried
    so the table can be read, and it enters no rule and no matrix."""
    path = repo / "data" / "orbit_manoeuvre_truth.json"
    if not path.exists():
        return []
    raw = json.loads(path.read_text())
    out = []
    for ev in raw.get("events", []):
        ms = _parse_iso(ev.get("occurredAt"))
        if ms is None or ev.get("norad") is None:
            continue
        out.append({"norad": int(ev["norad"]), "epochMs": ms,
                    "publishedKind": ev.get("type"),
                    "dateExactness": ev.get("dateExactness")})
    return out


def external_check(events, seen_by_object, tolerance_days=MATCH_TOLERANCE_DAYS):
    """For each published event: was a burn detected inside the tolerance, and
    what did the library type it. A listed table, never a precision."""
    tol = tolerance_days * pg.DAY_MS
    rows = []
    for ev in events:
        burns = seen_by_object.get(ev["norad"], [])
        near = [b for b in burns if abs(b[0] - ev["epochMs"]) <= tol]
        near.sort(key=lambda b: abs(b[0] - ev["epochMs"]))
        rows.append({
            "norad": ev["norad"], "publishedAtMs": ev["epochMs"],
            "publishedKind": ev["publishedKind"],
            "dateExactness": ev["dateExactness"],
            "burnsWithinTolerance": len(near),
            "nearestType": near[0][1] if near else None,
            "nearestOffsetDays": (abs(near[0][0] - ev["epochMs"]) / pg.DAY_MS
                                  if near else None),
        })
    return rows


def _parse_iso(value):
    if not value:
        return None
    import datetime as _dt
    v = value.replace("Z", "+00:00")
    try:
        return _dt.datetime.fromisoformat(v).timestamp() * 1000.0
    except ValueError:
        return None


def confusion(typed, idx):
    """(type x label class) counts, plus unmatched counts, both marginals."""
    matrix = {}
    unmatched = {}
    contested = 0
    for b in typed:
        t = b["type"]
        m = idx.nearest(b["norad"], b["epochMs"])
        if m is None:
            unmatched[t] = unmatched.get(t, 0) + 1
            continue
        cls, _, ct = m
        contested += 1 if ct else 0
        matrix.setdefault(t, {})
        matrix[t][cls] = matrix[t].get(cls, 0) + 1
    return matrix, unmatched, contested


def per_type_precision(matrix, version):
    out = {}
    expected = {}
    for r in rules(version):
        if r.expected_label:
            expected[r.type_name] = r.expected_label
    for t, row in matrix.items():
        n = sum(row.values())
        exp = expected.get(t)
        if exp in OBJECT_LEVEL_LABEL_CLASSES:
            # registration section 6.2: an object-level label supports only an
            # object-level statement. Scoring it at burn level would print a
            # zero where there is a gap.
            out[t] = {"expectedLabelClass": exp, "matched": n,
                      "agreeing": None, "forwardAgreement": None,
                      "wilson95": None,
                      "mostFrequentLabelClass": (max(row.items(),
                                                     key=lambda kv: kv[1])[0]
                                                 if row else None),
                      "underpowered": n < UNDERPOWERED_MIN,
                      "gateF": False,
                      "note": ("expected label class is object-level; the "
                               "burn-level cell is a labelled gap, not a zero")}
            continue
        k = row.get(exp, 0) if exp else 0
        lo, hi = wilson(k, n)
        best = max(row.items(), key=lambda kv: kv[1])[0] if row else None
        out[t] = {
            "expectedLabelClass": exp,
            "matched": n,
            "agreeing": k,
            "forwardAgreement": (k / n) if n else float("nan"),
            "wilson95": [lo, hi],
            "mostFrequentLabelClass": best,
            "underpowered": n < UNDERPOWERED_MIN,
            "gateF": bool(exp and best is not None and best != exp),
        }
    return out


# ==========================================================================
# Registration section 6.5 -- the controls. These read objectType. No rule
# does; this is the only place in the file where a catalogue field appears,
# and it is a diagnostic ON the rule set, not a rule.
# ==========================================================================
def load_object_types(path):
    """{norad: objectType or None} from the committed T8b object metadata.
    Country, name and object id are present in that file and are NOT read."""
    raw = json.loads(Path(path).read_text())
    return {int(k): (v.get("objectType") or None) for k, v in raw.items()}


def control_class(object_type):
    """T8a prereg 3.2's split, by the catalogue's own object type."""
    if object_type is None:
        return "unknown"
    return "active" if object_type.upper() == "PAYLOAD" else "passive"


# ==========================================================================
# The run
# ==========================================================================
class Tally:
    """Streaming counters. Nothing holds three million burn records in memory:
    each object is typed, counted, written and dropped."""

    def __init__(self):
        self.by_arm = {}
        self.types = {}
        self.matrix = {}
        self.unmatched = {}
        self.reasons = {}
        self.competing = {}
        self.control = {}
        self.episodes = {}
        self.contested = 0
        self.multi_fire = 0
        self.burns = 0
        self.missing_flag_epochs = 0
        self.geo_domain_from_plane_detector = 0
        self.stage0_also_stage1 = 0
        self.no_rule_breakdown = {}
        self.object_level = {}
        self.object_level_base = {}
        self.external_watch = {}
        self.external_norads = set()
        self.dist = {}
        self.span_bins = {}
        self.variant_types = {}

    def add(self, burn, klass, match, version):
        arm = burn["arm"]
        t = burn["type"]
        self.burns += 1
        self.by_arm[arm] = self.by_arm.get(arm, 0) + 1
        self.types.setdefault(arm, {})
        self.types[arm][t] = self.types[arm].get(t, 0) + 1
        if burn["norad"] in self.external_norads:
            self.external_watch.setdefault(burn["norad"], []).append(
                (burn["epochMs"], burn["type"]))
        if burn.get("alsoSatisfiedStage1"):
            self.stage0_also_stage1 += 1
        if t == UNLABELLED:
            r = burn["reason"]
            self.reasons[r] = self.reasons.get(r, 0) + 1
            if r == "no-rule":
                key = no_rule_reason(burn, version)
                self.no_rule_breakdown[key] = self.no_rule_breakdown.get(key, 0) + 1
            if r == "multi-fire":
                self.multi_fire += 1
                key = "+".join(burn["competingRules"])
                self.competing[key] = self.competing.get(key, 0) + 1
        # The BURN RECORD is version-independent: the same burn, two rule
        # sets. What is SERIALISED is not. A v1 artifact carries the v1
        # blocks and nothing else, or a v1 rerun could not reproduce the
        # committed v1 artifact -- v2 registration section 8.2.
        for key in V1_REPORTED_DELTAS + (
                V2_REPORTED_DELTAS if version != "v1" else ()):
            v = burn.get(key)
            if v is not None and np.isfinite(v):
                self.dist.setdefault(arm + ":" + key, []).append(abs(float(v)))
        self.control.setdefault(t, {})
        self.control[t][klass] = self.control[t].get(klass, 0) + 1
        if match is None:
            self.unmatched[t] = self.unmatched.get(t, 0) + 1
        else:
            cls, _, ct = match
            self.contested += 1 if ct else 0
            self.matrix.setdefault(t, {})
            self.matrix[t][cls] = self.matrix[t].get(cls, 0) + 1

    def add_discriminations(self, burn):
        """v2 registration section 6.3, arm G only. Reads the burn already
        typed; assigns nothing and changes no count above."""
        span = burn.get("baselineSpanDays")
        if span is not None and np.isfinite(span):
            for j in range(len(SPAN_BIN_EDGES_DAYS) - 1):
                if SPAN_BIN_EDGES_DAYS[j] <= span < SPAN_BIN_EDGES_DAYS[j + 1]:
                    key = f"{SPAN_BIN_EDGES_DAYS[j]:g}-{SPAN_BIN_EDGES_DAYS[j + 1]:g}"
                    row = self.span_bins.setdefault(key, {})
                    for v, t in (("v1", burn["typeUnderV1"]),
                                 ("v2", burn["type"])):
                        cell = row.setdefault(v, [0, 0])
                        cell[0] += 1
                        cell[1] += 1 if t == UNLABELLED else 0
                    break
        for name, t in burn["typeUnderVariant"].items():
            row = self.variant_types.setdefault(name, {})
            row[t] = row.get(t, 0) + 1
        row = self.variant_types.setdefault("v1RuleSet", {})
        row[burn["typeUnderV1"]] = row.get(burn["typeUnderV1"], 0) + 1

    def add_episode(self, kind):
        self.episodes[kind] = self.episodes.get(kind, 0) + 1


def no_rule_reason(burn, version):
    """Which channel state left this burn outside every rule. Descriptive
    only: it assigns nothing and it is not a rule.

    Under v2 the inclination channel named here is the NET one, tested against
    that burn's own floor, because naming the raw channel would report a
    reason no v2 rule consulted.
    """
    _check_version(version)
    if burn["arm"] == "G":
        d = burn["deltaDriftDegPerDay"]
        b = burn["driftBeforeDegPerDay"]
        a = burn["driftAfterDegPerDay"]
        if version == "v1":
            di = burn["deltaIncDeg"]
            bar = INC_BAR_DEG
        else:
            di = burn.get("deltaIncNetDeg")
            bar = net_floor_deg(burn)
        if d is None or di is None or bar is None:
            return "G:non-finite"
        drift_moved = abs(d) >= BURN_FLOOR
        inc_moved = abs(di) >= bar
        if drift_moved and inc_moved:
            return "G:both-channels-moved"
        if inc_moved and not drift_moved:
            return "G:inclination-only-but-a-rule-claimed-it"
        if drift_moved and abs(b) <= STATIONED_BAND and abs(a) <= STATIONED_BAND:
            return "G:inside-the-band-but-outside-a-station-segment"
        if drift_moved:
            return "G:drift-moved-outside-every-band-case"
        return "G:below-the-drift-floor-and-the-inclination-bar"
    ch = burn["channel"]
    da = burn["deltaAKm"]
    di = burn["deltaIncDeg"]
    if ch == "both":
        return "P:both-channels-fired"
    if ch == "plane":
        if di is not None and abs(di) < PLANE_FLOOR_DEG:
            return "P:plane-flag-with-no-inclination-change-node-dominant"
        if da is not None and abs(da) >= IN_TRACK_FLOOR_KM:
            return "P:plane-flag-with-a-semi-major-axis-change"
        return "P:plane-flag-outside-the-rule"
    if da is not None and abs(da) < IN_TRACK_FLOOR_KM:
        return "P:in-track-flag-below-the-in-track-floor"
    return "P:in-track-flag-outside-the-rule"


def _discriminations(burn):
    """The v1 type and the two variant types for one already-built arm-G burn
    record. Same record, different clause input -- nothing is re-detected and
    nothing is re-measured."""
    out = {"typeUnderV1": assign_type(burn, "v1")["type"],
           "typeUnderVariant": {}}
    for name, field in PREDICTION_VARIANTS.items():
        rec = dict(burn)
        rec["deltaIncNetDeg"] = burn.get(field)
        out["typeUnderVariant"][name] = assign_type(rec, "v2")["type"]
    raw = burn.get("deltaIncDeg")
    net = burn.get("deltaIncNetDeg")
    if (raw is not None and net is not None and np.isfinite(raw)
            and np.isfinite(net) and abs(raw) > 0.0):
        out["ratioNetOverRawAbs"] = abs(net) / abs(raw)
    return out


def _type_and_record(burn, idx, tally, types_by_norad, ledger, version,
                     object_label_sets=None):
    burn.update(assign_type(burn, version))
    if version != "v1" and burn["arm"] == "G":
        burn.update(_discriminations(burn))
    klass = control_class(types_by_norad.get(burn["norad"]))
    match = idx.nearest(burn["norad"], burn["epochMs"])
    tally.add(burn, klass, match, version)
    if "typeUnderVariant" in burn:
        tally.add_discriminations(burn)
    if object_label_sets:
        for name, members in object_label_sets.items():
            inside = burn["norad"] in members
            tally.object_level.setdefault(name, {}).setdefault(burn["type"],
                                                               [0, 0])
            row = tally.object_level[name][burn["type"]]
            row[0] += 1
            row[1] += 1 if inside else 0
            base = tally.object_level_base.setdefault(name, [0, 0])
            base[0] += 1
            base[1] += 1 if inside else 0
    if ledger is not None:
        row = {k: burn[k] for k in ("norad", "arm", "epochMs", "type", "ruleId",
                                    "reason", "competingRules", "channel")}
        for k in V1_LEDGER_DELTAS + (
                V2_LEDGER_DELTAS if version != "v1" else ()):
            if burn.get(k) is not None:
                row[k] = round(float(burn[k]), 9)
        row["matchedLabelClass"] = match[0] if match else None
        ledger.write(json.dumps(row, separators=(",", ":")) + "\n")


def run_arm_g(npz_path, idx, tally, object_types, ledger, sigma_n, version,
              object_label_sets=None, progress_every=200):
    arrays = dict(np.load(npz_path))
    series_list = pg.build_series(arrays)
    del arrays
    grid_base_day, _ = pg.build_daily_grid(series_list)
    for i, s in enumerate(series_list):
        segs = pg.station_segments(s)
        burns = geo_burns(s, sigma_n, segs, grid_base_day)
        if not burns:
            continue
        for b in burns:
            _type_and_record(b, idx, tally, object_types, ledger, version,
                             object_label_sets)
        seg_rows = []
        for i0, i1 in segs:
            seg_rows.append(((grid_base_day + s.grid_lo + i0) * pg.DAY_MS,
                             (grid_base_day + s.grid_lo + i1 + 1) * pg.DAY_MS,
                             float(pg.wrap180(np.median(s.grid[i0:i1 + 1])))))

        def seg_lookup(t_ms, before, rows=seg_rows):
            if before:
                cand = [r for r in rows if r[1] <= t_ms]
                return cand[-1][2] if cand else None
            cand = [r for r in rows if r[0] >= t_ms]
            return cand[0][2] if cand else None

        for ep in relocation_episodes(burns, seg_lookup):
            tally.add_episode(ep["episode"])
        if progress_every and (i + 1) % progress_every == 0:
            print(f"  arm G {i + 1}/{len(series_list)} objects, "
                  f"{tally.burns} burns", flush=True)
    return len(series_list)


def run_arm_p(work_dir, flags_npz, idx, tally, object_types, ledger, version,
              object_label_sets=None, progress_every=5000):
    cache = pp.Cache(work_dir).open()
    z = np.load(flags_npz, allow_pickle=True)
    norads = [int(x) for x in z["norad"]]
    intrack = z["intrack"]
    plane = z["plane"]
    done = 0
    for k, nd in enumerate(norads):
        it = json.loads(str(intrack[k]))
        pl = json.loads(str(plane[k]))
        if not it and not pl:
            continue
        el = cache.elements(nd)
        if el is None:
            tally.missing_flag_epochs += len(it) + len(pl)
            continue
        el = dict(el)
        el["norad"] = nd
        burns, missing = plane_burns(el, it, pl)
        tally.missing_flag_epochs += missing
        kept = []
        for b in burns:
            if b["arm"] == "G-domain":
                tally.geo_domain_from_plane_detector += 1
                continue
            _type_and_record(b, idx, tally, object_types, ledger, version,
                             object_label_sets)
            kept.append(b)
        for ep in transfer_leg_runs(kept):
            tally.add_episode(ep["episode"])
        done += 1
        if progress_every and done % progress_every == 0:
            print(f"  arm P {done} objects with flags, {tally.burns} burns",
                  flush=True)
    return done


def build_artifact(tally, label_counts, inputs, wall_seconds, version):
    _check_version(version)
    matrix = tally.matrix
    per_type = per_type_precision(matrix, version)
    arms = {}
    for arm, counts in tally.types.items():
        total = sum(counts.values())
        arms[arm] = {
            "burns": total,
            "unlabelled": counts.get(UNLABELLED, 0),
            "unlabelledFraction": counts.get(UNLABELLED, 0) / total if total else float("nan"),
            "byType": dict(sorted(counts.items())),
        }
    total_burns = tally.burns
    unlab = sum(c.get(UNLABELLED, 0) for c in tally.types.values())
    multi_fraction = tally.multi_fire / total_burns if total_burns else float("nan")
    gates = {
        "gateP_partition": {
            "multiFireFraction": multi_fraction,
            "bar": PARTITION_BAR,
            "fired": bool(multi_fraction > PARTITION_BAR),
        },
        "gateU_underpowered": sorted(t for t, v in per_type.items() if v["underpowered"]),
        "gateF_falsification": sorted(t for t, v in per_type.items() if v["gateF"]),
        "gateN_unlabelledFraction": unlab / total_burns if total_burns else float("nan"),
    }
    leak = {}
    for t, byclass in tally.control.items():
        n = sum(byclass.values())
        passive = byclass.get("passive", 0)
        leak[t] = {"total": n, "passive": passive, "active": byclass.get("active", 0),
                   "unknown": byclass.get("unknown", 0),
                   "passiveFraction": passive / n if n else float("nan")}
    gates["gateL_leak"] = {
        "bar": LEAK_RATIO_BAR,
        "byType": leak,
        "firedFor": sorted(t for t, v in leak.items()
                           if RULES_BY_ID[version].get(
                               _rule_of_type(t, version), None) is not None
                           and _propulsive(t, version)
                           and v["total"] >= UNDERPOWERED_MIN
                           and v["passiveFraction"] > LEAK_RATIO_BAR),
    }
    art = {
        "libraryVersion": version,
        "registration": REGISTRATIONS[version],
        "note": ("Agreement between rule sets, not accuracy. Every label class "
                 "in the matrix is another instrument's output on the same "
                 "element sets, not ground truth. Read the floors before any "
                 "figure: every threshold is a screen, not a law."),
        "rules": rule_table(version),
        "rulesSha256": rules_sha256(version),
        "floors": floors_for(version),
        "episodeTypes": list(EPISODE_TYPES),
        "inputs": inputs,
        "population": {
            "burns": total_burns,
            "byArm": arms,
            "missingFlagEpochs": tally.missing_flag_epochs,
            "planeDetectorBurnsInsideArmGBand": tally.geo_domain_from_plane_detector,
            "stage0AssignmentsThatAlsoSatisfiedAStage1Rule": tally.stage0_also_stage1,
        },
        "labelCounts": label_counts,
        "confusion": {t: dict(sorted(row.items())) for t, row in sorted(matrix.items())},
        "unmatchedByType": dict(sorted(tally.unmatched.items())),
        "contestedMatches": tally.contested,
        "unlabelledReasons": dict(sorted(tally.reasons.items())),
        "competingRuleCombinations": dict(sorted(tally.competing.items())),
        "perTypePrecision": per_type,
        "episodes": dict(sorted(tally.episodes.items())),
        "controls": leak,
        "noRuleBreakdown": dict(sorted(tally.no_rule_breakdown.items())),
        "deltaQuantiles": {
            name: {f"p{q}": float(np.percentile(vals, q))
                   for q in (5, 25, 50, 75, 95)}
            for name, vals in sorted(tally.dist.items()) if vals
        },
        "objectLevelAgreement": {
            name: {
                "baseRate": (tally.object_level_base[name][1]
                             / tally.object_level_base[name][0]
                             if tally.object_level_base[name][0] else float("nan")),
                "burns": tally.object_level_base[name][0],
                "byType": {t: {"burns": v[0], "onALabelledObject": v[1],
                               "fraction": (v[1] / v[0]) if v[0] else float("nan")}
                           for t, v in sorted(rows.items())},
            }
            for name, rows in sorted(tally.object_level.items())
        },
        "externalPublishedEventCheck": external_check(
            external_events(), tally.external_watch),
        "gates": gates,
        "wallSeconds": wall_seconds,
    }
    if version != "v1":
        # v1's artifact schema is frozen: a v1 rerun must reproduce it field
        # for field, so nothing may be added to it after the fact.
        art["perRuleSha256"] = per_rule_sha256(version)
        art["byteIdenticalToV1"] = {
            rid: (per_rule_sha256(version)[rid] == per_rule_sha256("v1")[rid])
            for rid in per_rule_sha256(version)}
        art["v1RulesSha256"] = rules_sha256("v1")
        art["discriminations"] = {
            "note": ("v2 registration section 6.3. Computed in the same pass, "
                     "off the same burn records. Published whatever they "
                     "show. The variant mixes are a sensitivity on a model "
                     "choice, not a second answer."),
            "armGUnlabelledBySpanBin": {
                b: {v: {"burns": c[0], "unlabelled": c[1],
                        "unlabelledFraction": (c[1] / c[0]) if c[0] else None}
                    for v, c in sorted(row.items())}
                for b, row in sorted(tally.span_bins.items(),
                                     key=lambda kv: float(kv[0].split("-")[0]))},
            "armGTypeMixByPrediction": {
                k: dict(sorted(v.items()))
                for k, v in sorted(tally.variant_types.items())},
        }
    art["artifactSha256"] = hashlib.sha256(canonical_json(art)).hexdigest()
    return art


def _rule_of_type(type_name, version):
    for r in rules(version):
        if r.type_name == type_name:
            return r.rid
    return None


def _propulsive(type_name, version):
    for r in rules(version):
        if r.type_name == type_name:
            return r.propulsive
    return False


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--library-version", required=True,
                    choices=LIBRARY_VERSIONS,
                    help="never defaulted: a type without its version is an "
                         "unversioned label")
    ap.add_argument("--stage", default="all", choices=("geo", "plane", "all"))
    ap.add_argument("--geo-extract", type=Path,
                    default=_REPO / "runtime" / "proximity-geo" / "near-geo.npz")
    ap.add_argument("--plane-work", type=Path, required=True,
                    help="element-set column cache for the plane stage")
    ap.add_argument("--flags", type=Path, required=True,
                    help="detect-flags.npz from the plane detector")
    ap.add_argument("--object-meta", type=Path, required=True,
                    help="object-meta.json from the plane detector")
    ap.add_argument("--sigma-drift", type=float, default=6.038533519066339e-4)
    ap.add_argument("--out", type=Path, required=True,
                    help="directory the library artifacts are written to")
    args = ap.parse_args(argv)
    version = _check_version(args.library_version)
    args.out.mkdir(parents=True, exist_ok=True)

    started = time.time()
    idx, label_counts, object_labels = load_labels()
    object_types = load_object_types(args.object_meta)
    tally = Tally()
    tally.external_norads = {e["norad"] for e in external_events()}
    if args.flags.exists():
        z = np.load(args.flags, allow_pickle=True)
        object_labels["t8bPlaneFlaggedObject"] = {
            int(nd) for nd, pl in zip(z["norad"], z["plane"])
            if json.loads(str(pl))}
        del z
    ledger_path = args.out / f"manoeuvre-library-ledger-{version}.jsonl"
    inputs = {}
    with ledger_path.open("w") as ledger:
        if args.stage in ("geo", "all"):
            print("arm G ...", flush=True)
            n = run_arm_g(args.geo_extract, idx, tally, object_types, ledger,
                          args.sigma_drift, version, object_labels)
            inputs["geoExtract"] = {"path": str(args.geo_extract),
                                    "sha256": sha256_file(args.geo_extract),
                                    "objects": n}
        if args.stage in ("plane", "all"):
            print("arm P ...", flush=True)
            n = run_arm_p(args.plane_work, args.flags, idx, tally,
                          object_types, ledger, version, object_labels)
            inputs["planeFlags"] = {"path": str(args.flags),
                                    "sha256": sha256_file(args.flags),
                                    "objectsWithFlags": n}
            inputs["planeElementCache"] = json.loads(
                (args.plane_work / "extract-meta.json").read_text())
    for name in ("proximity-events-20260922.jsonl", "transfer-loss-20260922.jsonl",
                 "stationkeeping-ns-20260922.jsonl", "stationkeeping-ew-20260922.jsonl",
                 "proximity-leo-events-20260922.jsonl"):
        inputs[name] = sha256_file(_REPO / "docs" / name)
    inputs["toolSha256"] = sha256_file(Path(__file__))
    inputs["ledgerSha256"] = sha256_file(ledger_path)
    inputs["objectLevelLabelSets"] = {k: len(v) for k, v in object_labels.items()}

    art = build_artifact(tally, label_counts, inputs, time.time() - started,
                         version)
    out = args.out / f"manoeuvre-library-{version}.json"
    out.write_text(json.dumps(art, indent=1, ensure_ascii=False))
    print(json.dumps({k: art[k] for k in
                      ("libraryVersion", "rulesSha256", "artifactSha256",
                       "population", "perTypePrecision", "gates")},
                     indent=1)[:6000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
