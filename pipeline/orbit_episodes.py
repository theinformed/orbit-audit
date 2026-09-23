#!/usr/bin/env python3
"""Change episodes: a pure function of the archive up to an injected moment.

An episode is the unit the change ledger scrolls through. It OPENS when an
element set departs the object's own pre-change baseline beyond a registered
floor, it is IN PROGRESS while the elements are still trending, and it
COMPLETES when they have held still for a registered dwell. Routine keeping
never opens one. The design is `docs/change-ledger-and-reading-design-20260922.md`
section 1; every floor below is imported from the instrument that registered it
and none is re-typed here.

**THIS MODULE IS PURE, AND THAT IS THE WHOLE POINT.** It reads no clock, no
file, no database and no network; `now_ms`, the registered rows, the catalogue
events and two archive readers all arrive as arguments. Two consequences the
design asks for follow directly:

* the episode is recomputed from scratch on every release, so there is no state
  file, no concurrent-writer problem and no drift between what is stored and
  what the archive says;
* **the replay is this same function with an injected clock.** The synthetic
  exercise and the live product cannot diverge, because they are one call.

**One departure from design section 4.1, stated rather than smuggled.** That
section gives `reading` a `text` field per clause. This module emits SLOTS AND
GAPS ONLY and never a sentence. The templates live in
`src/orbit-changes-strings.ts`, which is generated from the frozen bundle and
scanned by `tests/orbit-changes-vocabulary.test.ts`; a clause whose prose was
composed in an artifact would reach a reader without ever passing that gate.
Slots in, template in the browser, gate over the template.

**What is not emitted, anywhere, on any record:** no country, no registry code
(section 10.3 is open and an absent field cannot be printed by accident), no
velocity-change figure, no separation in kilometres.

The rule and floor block is hashed at import into `TRACKER_VERSION`, so a
published state chip names the rules that produced it.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.orbit_campaigns import (  # noqa: E402
    BLOCK_DAYS,
    MAXIMUM_JOINABLE_GAP_DAYS,
    MINIMUM_BASELINE_BLOCKS,
    SUSTAINED_THRUST_KAPPA,
)
from pipeline.orbit_events import TERMINAL_DECAY_PERIGEE_KM  # noqa: E402
from pipeline.orbit_history import (  # noqa: E402
    RE_WGS72,
    semi_major_axis_km,
)
from tools import proximity_geo as pg  # noqa: E402
from tools.proximity_plane import CAMPAIGN_MAX_GAP_DAYS, DA_FLOOR_KM  # noqa: E402

DAY_MS = 86_400_000
EPISODE_SCHEMA = 1

# The stationed band. Six tenths of the slot tolerance over the dwell, which is
# how the alarm lane derives it; an object inside it is being held, one outside
# it is being carried somewhere.
SLOT_DRIFT_FLOOR_DEG_PER_DAY = 6.0 * pg.X_PRIMARY_DEG / pg.D_PRIMARY_DAYS

# ---------------------------------------------------------------------------
# The rules, in one literal block, hashed into the version a chip names.
#
# Every value is read from the module that registered it. The dictionary exists
# so that the hash covers the rules as a WHOLE: change a floor in its own
# module and the tracker version moves, which is what lets a reader tell a chip
# drawn under one set of rules from a chip drawn under another.
# ---------------------------------------------------------------------------
RULES: dict[str, Any] = {
    "designSection": "docs/change-ledger-and-reading-design-20260922.md section 1",
    "onset": {
        "nearGeoDepartureFloorDegPerDay": pg.BURN_FLOOR_DEG_PER_DAY,
        "nearGeoSigmaK": pg.BURN_SIGMA_K,
        "nearGeoBaselineSamples": pg.BURN_BASELINE_SAMPLES,
        "nearGeoConfirmingSamples": 2,
        "mergeDays": pg.MAX_GAP_DAYS,
        "campaignMaxGapDays": CAMPAIGN_MAX_GAP_DAYS,
    },
    "inProgress": {
        "nearGeoBandDegPerDay": SLOT_DRIFT_FLOOR_DEG_PER_DAY,
        "blockDays": BLOCK_DAYS,
        "blocks": MINIMUM_BASELINE_BLOCKS,
        "windowDays": BLOCK_DAYS * MINIMUM_BASELINE_BLOCKS,
        "evidenceKappa": SUSTAINED_THRUST_KAPPA,
        "materialityKm": DA_FLOOR_KM,
    },
    "completion": {
        "nearGeoStationHalfWidthDeg": pg.STATION_HALF_WIDTH_DEG,
        "nearGeoStationMinDays": pg.STATION_MIN_DAYS,
        "outsideStillBlocks": MINIMUM_BASELINE_BLOCKS,
    },
    "lapse": {
        "trackingGapDays": MAXIMUM_JOINABLE_GAP_DAYS,
        "terminalPerigeeKm": TERMINAL_DECAY_PERIGEE_KM,
    },
    "nearGeoBand": {
        "meanMotionRevPerDay": [pg.MM_MIN_REV_DAY, pg.MM_MAX_REV_DAY],
        "eccentricityMax": pg.ECC_MAX,
        "inclinationMaxDeg": pg.INC_MAX_DEG,
    },
    "notes": {
        "trackingGapConstant": (
            "the design cites DECLINE_AFTER_TRACKING_GAP for the three-day gap. That "
            "name is a BOOLEAN FLAG in pipeline/orbit_campaigns.py and is false today; "
            "the three days it gates live in MAXIMUM_JOINABLE_GAP_DAYS, which is what "
            "is imported here."
        ),
        "blockRateUnits": (
            "the trend test compares a RATE against the standard error OF THAT RATE, "
            "which is the shape orbit_campaigns.sustained_thrust already uses: block "
            "medians are per-day rates, the scale is 1.4826 x their MAD, and the "
            "standard error is that scale over the square root of the block count. "
            "Reading the design's 'slope' as a level rather than a rate would compare "
            "kilometres per day against kilometres."
        ),
        "nearGeoDepartureFloor": (
            "max(5 sigma, 0.010) is the registered threshold. The archive's measured "
            "sigma is 6.0385e-4 deg/day, so five of them is 3.02e-3 and the floor "
            "dominates at every sigma this archive has produced. A caller may pass the "
            "measured sigma; the threshold is computed from it either way."
        ),
    },
}

TRACKER_VERSION = hashlib.sha256(
    json.dumps(RULES, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()

NEAR_GEO_REGIMES = frozenset({"GEO", "near-GEO"})

# THE FROZEN RECORDS' OWN FIELD NAMES, confined to one place.
#
# T8a and T8b name the moving object of a pair with a word this section may not
# print. The word is theirs, it is a key in a file this module only reads, and
# renaming a key in someone else's frozen record is not available. Every read
# of it goes through this table, so the word appears in this module twice and
# never anywhere a reader could see it.
_MOVER = {"geo": "approacherNorad", "geoName": "approacherName",
          "leo": "approacher", "leoName": "approacherName"}

# Signatures that describe an orbit coming down under the atmosphere. A
# sustained fall is what drag does, so none of these opens an episode; the
# instrument that could tell a slow retrograde burn from the air declines to,
# and this module does not overrule it.
FALLING_SIGNATURES = frozenset({
    "drag-decay",
    "re-entry-decay",
    "drag-and-thrust-not-separable",
})

# Keeping signatures near the belt. These are the object holding its own slot,
# which is the baseline an episode departs FROM, so they never open one.
KEEPING_SIGNATURES = frozenset({
    "geo-east-west-keeping",
    "geo-north-south-keeping",
    "drag-make-up",
})


# ---------------------------------------------------------------------------
# Small numeric helpers
# ---------------------------------------------------------------------------
def _round(value: float | None, places: int) -> float | None:
    if value is None or not math.isfinite(float(value)):
        return None
    return round(float(value), places)


def _median(values: Sequence[float]) -> float:
    return float(statistics.median(values))


def _mad_scale(values: Sequence[float]) -> float:
    """The module's own robust scale: 1.4826 times the median absolute deviation."""
    if len(values) < 2:
        return 0.0
    middle = _median(values)
    return float(statistics.median([abs(value - middle) for value in values]) * 1.4826)


def block_rates(epoch_ms: np.ndarray, values: np.ndarray) -> dict[int, float]:
    """Median per-day rate of change in each five-day block of one object's history.

    The same estimator `orbit_campaigns._blocks_for` uses, over the same block
    width, applied to raw element sets instead of pre-built intervals: each
    consecutive pair gives a rate, rates are grouped by the block their midpoint
    falls in, and the block's value is the median of them.
    """
    grouped: dict[int, list[float]] = {}
    width = int(BLOCK_DAYS * DAY_MS)
    for index in range(1, epoch_ms.size):
        span_ms = float(epoch_ms[index] - epoch_ms[index - 1])
        if span_ms <= 0:
            continue
        rate = float(values[index] - values[index - 1]) / (span_ms / DAY_MS)
        middle_ms = 0.5 * (float(epoch_ms[index]) + float(epoch_ms[index - 1]))
        grouped.setdefault(int(middle_ms // width), []).append(rate)
    return {index: _median(rates) for index, rates in grouped.items()}


# ---------------------------------------------------------------------------
# The two trend tests of design section 1.3
# ---------------------------------------------------------------------------
def geo_trend(drift: np.ndarray, flag_ms: np.ndarray, at_ms: int) -> dict[str, Any]:
    """Near the belt: is the object still being carried somewhere?

    Trending when the newest fitted drift rate is outside the stationed band,
    or when a confirmed departure arrived inside the merge window ending at
    `at_ms`. Both are the alarm lane's own tests, at its own floors.
    """
    latest = float(drift[-1]) if drift.size else float("nan")
    recent = bool(
        flag_ms.size
        and float(flag_ms[-1]) >= at_ms - pg.MAX_GAP_DAYS * DAY_MS
        and float(flag_ms[-1]) <= at_ms
    )
    outside = bool(math.isfinite(latest) and abs(latest) > SLOT_DRIFT_FLOOR_DEG_PER_DAY)
    return {
        "slope": _round(latest, 6),
        "slopeSe": None,
        "windowDays": pg.MAX_GAP_DAYS,
        "trending": outside or recent,
        "test": "geo-band",
    }


def block_slope_trend(epoch_ms: np.ndarray, axis_km: np.ndarray, at_ms: int) -> dict[str, Any]:
    """Outside the belt: is the semi-major axis still moving, materially?

    Two bars, both of which must clear, in the shape the continuous-thrust
    instrument already uses. The evidence bar is the trailing blocks' median
    rate against the standard error of that rate; the materiality bar is that
    the rate, carried over the window, moves the axis by at least the
    registered in-track floor. A rate inside its own block-to-block scatter is
    not a trend, and a real but negligible one is not a change.
    """
    window_days = BLOCK_DAYS * MINIMUM_BASELINE_BLOCKS
    low = at_ms - window_days * DAY_MS
    inside = (epoch_ms >= low) & (epoch_ms <= at_ms)
    if int(np.count_nonzero(inside)) < 2:
        return {"slope": None, "slopeSe": None, "windowDays": window_days,
                "trending": False, "test": "block-slope"}
    rates = block_rates(epoch_ms[inside], axis_km[inside])
    if len(rates) < 2:
        only = next(iter(rates.values()), None)
        return {"slope": _round(only, 6), "slopeSe": None, "windowDays": window_days,
                "trending": False, "test": "block-slope"}
    medians = list(rates.values())
    rate = _median(medians)
    scale = _mad_scale(medians)
    standard_error = scale / math.sqrt(len(medians)) if scale > 0 else 0.0
    evidence = standard_error == 0.0 or abs(rate) > SUSTAINED_THRUST_KAPPA * standard_error
    material = abs(rate) * window_days >= DA_FLOOR_KM
    return {
        "slope": _round(rate, 6),
        "slopeSe": _round(standard_error, 6),
        "windowDays": window_days,
        "trending": bool(evidence and material),
        "test": "block-slope",
    }


# ---------------------------------------------------------------------------
# Near-belt series helpers, built on the registered instrument
# ---------------------------------------------------------------------------
def _series(arrays: dict[str, np.ndarray], norad: int) -> Any | None:
    if arrays["epochMs"].size < 2:
        return None
    return pg.Series(
        norad,
        np.asarray(arrays["epochMs"], dtype=np.float64),
        np.asarray(arrays["meanMotion"], dtype=np.float64),
        np.asarray(arrays["eccentricity"], dtype=np.float64),
        np.asarray(arrays["inclination"], dtype=np.float64),
        np.asarray(arrays["raan"], dtype=np.float64),
        np.asarray(arrays["argPerigee"], dtype=np.float64),
        np.asarray(arrays["meanAnomaly"], dtype=np.float64),
    )


def _attach_grid(series: Any) -> Any:
    """Give one object the daily grid `station_segments` reads.

    `build_daily_grid` places a whole population on one shared origin; an
    episode is about one object, so the grid is built on that object's own span
    with the instrument's own interpolation and its own refusal across gaps.
    """
    low = int(series.epoch_ms[0] // DAY_MS)
    high = int(series.epoch_ms[-1] // DAY_MS)
    days = np.arange(low, high + 1, dtype=np.int64)
    targets = days.astype(np.float64) * DAY_MS + 0.5 * DAY_MS
    series.grid_lo = low
    series.grid = pg.interpolate(series.epoch_ms, series.lam_unwrapped, targets)
    return series


def _station_after(series: Any, onset_ms: int) -> tuple[int, int] | None:
    """The earliest new station after onset, as (start, the moment its dwell elapses).

    THE EPISODE COMPLETES WHEN THE DWELL HAS RUN, NOT WHEN THE STATION ENDS.
    Returning the segment's far edge would mean an object that settles into its
    new slot and stays there is never recorded as having settled -- the longer
    it holds, the longer the ledger says it is still moving -- which is the
    rule inverted. The registered dwell is thirty days, and thirty days after
    the station forms is the moment a causal reader could say it had formed.
    """
    if series.grid is None:
        return None
    for start, end in pg.station_segments(series):
        start_ms = (series.grid_lo + start) * DAY_MS
        end_ms = (series.grid_lo + end + 1) * DAY_MS
        if start_ms > onset_ms:
            return int(start_ms), int(min(end_ms, start_ms + pg.STATION_MIN_DAYS * DAY_MS))
    return None


def _geo_flags(series: Any, sigma_n: float) -> tuple[np.ndarray, np.ndarray]:
    return pg.drift_change_flags(series, sigma_n)


# ---------------------------------------------------------------------------
# Element-state summaries
# ---------------------------------------------------------------------------
def _geo_state(series: Any, low_ms: float, high_ms: float) -> dict[str, Any] | None:
    inside = (series.epoch_ms >= low_ms) & (series.epoch_ms <= high_ms)
    if not bool(np.any(inside)):
        return None
    lam = series.lam[inside]
    drift = series.drift[inside]
    return {
        "epochMs": int(series.epoch_ms[inside][-1]),
        "lambdaDeg": _round(float(np.median(lam)), 3),
        "driftDegPerDay": _round(float(np.median(drift)), 5),
        "scatter": _round(_mad_scale([float(value) for value in drift]), 6),
        "windowDays": _round((high_ms - low_ms) / DAY_MS, 2),
    }


def _outside_state(
    epoch_ms: np.ndarray, axis_km: np.ndarray, inclination: np.ndarray,
    low_ms: float, high_ms: float,
) -> dict[str, Any] | None:
    inside = (epoch_ms >= low_ms) & (epoch_ms <= high_ms)
    if not bool(np.any(inside)):
        return None
    axis = axis_km[inside]
    return {
        "epochMs": int(epoch_ms[inside][-1]),
        "semiMajorAxisKm": _round(float(np.median(axis)), 4),
        "inclinationDeg": _round(float(np.median(inclination[inside])), 5),
        "scatter": _round(_mad_scale([float(value) for value in axis]), 5),
        "windowDays": _round((high_ms - low_ms) / DAY_MS, 2),
    }


# ---------------------------------------------------------------------------
# The reading: slots and gaps, never a sentence
# ---------------------------------------------------------------------------
def _gap(reason: str, owed: str) -> dict[str, Any]:
    return {"filled": False, "slots": None, "gap": {"reason": reason, "owed": owed},
            "earnedBy": None}


def _reading(
    *, near_geo: bool, stage: str, class_figures: Mapping[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """Every clause of the reading, as slots or as a labelled gap.

    Today only R3 can carry a number, and only at stage S1 for a near-belt
    episode of the class the frozen bundle speaks. Everything else names the
    measurement it is waiting on. No clause is ever an empty string, because a
    blank and a gap read the same and mean different things.
    """
    reading = {
        "r1": _gap("the type library's agreement table has not been measured", "M4"),
        "r2": _gap("the routine check has not been measured for this class", "M5"),
        "r3": _gap("no number until the replay", "M3"),
        "r4": {"filled": True, "slots": None, "gap": None,
               "earnedBy": {"artifact": "src/orbit-changes-strings.ts",
                            "version": None, "checksum": None}},
    }
    if near_geo and stage == "S1" and class_figures:
        reading["r3"] = {
            "filled": True,
            "slots": {
                "stage": "S1",
                "k": class_figures.get("k"),
                "n": class_figures.get("n"),
                "precisionPercent": class_figures.get("precisionPercent"),
                "wilsonLo": class_figures.get("wilsonLo"),
                "wilsonHi": class_figures.get("wilsonHi"),
                "setSize": None,
                "setSizePlaneCompatible": None,
                "horizonDays": class_figures.get("horizonDays"),
            },
            "gap": None,
            "earnedBy": {
                "artifact": class_figures.get("artifact"),
                "version": class_figures.get("version"),
                "checksum": class_figures.get("checksum"),
            },
        }
    return reading


# ---------------------------------------------------------------------------
# Record assembly
# ---------------------------------------------------------------------------
def _record(**fields: Any) -> dict[str, Any]:
    base = {
        "key": None, "norad": None, "name": None, "regime": None, "kind": None,
        "state": None, "closure": "open", "reopened": 0, "stage": "none",
        "onsetMs": None, "updatedMs": None, "completedMs": None,
        "initial": None, "current": None,
        "partnerNorad": None, "partnerName": None,
        "steps": [], "trend": None, "history": [], "reading": None,
        "versions": {"episodeSchema": EPISODE_SCHEMA, "trackerVersion": TRACKER_VERSION},
    }
    base.update(fields)
    return base


def _history(entries: Sequence[tuple[int, str, str]]) -> list[dict[str, Any]]:
    return [{"ms": int(ms), "state": state, "stage": stage} for ms, state, stage in entries]


def _iso_ms(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_epoch(text: str | None) -> int | None:
    """An ISO instant from the shipped bundle, in milliseconds."""
    if not text:
        return None
    import datetime as dt

    try:
        moment = dt.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None
    return int(moment.replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


# ---------------------------------------------------------------------------
# The function
# ---------------------------------------------------------------------------
def episodes(
    *,
    now_ms: int,
    catalogue_events: Sequence[dict[str, Any]],
    geo_record: Sequence[dict[str, Any]],
    leo_record: Sequence[dict[str, Any]],
    elements: Callable[[int, int, int], dict[str, np.ndarray]],
    newest_epoch: Callable[[int], int | None],
    sustained: Mapping[int, bool] | None = None,
    sigma_n_deg_per_day: float | None = None,
    class_figures: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Every change episode the archive supports as of `now_ms`.

    `elements(norad, low_ms, high_ms)` returns the array bundle
    `pipeline.orbit_changes_release.element_window` produces; `newest_epoch`
    returns the newest element-set epoch the archive holds for an object, or
    None. Neither is called for a moment after `now_ms`: the caller is trusted
    to bound its reader, and every window this module asks for is clipped to
    `now_ms` so that a replay at an earlier clock cannot see the future.

    `sustained` is the continuous-thrust verdict per object, computed by the
    caller from the instrument that registered it. Absent, continuous episodes
    are simply not opened -- a labelled gap on the page, never a false negative
    presented as a measurement.
    """
    sigma = pg.BURN_FLOOR_DEG_PER_DAY / pg.BURN_SIGMA_K if sigma_n_deg_per_day is None \
        else float(sigma_n_deg_per_day)
    sustained = dict(sustained or {})
    records: list[dict[str, Any]] = []
    claimed: dict[int, list[tuple[int, int]]] = {}

    def claim(norad: int, low: int, high: int) -> None:
        claimed.setdefault(int(norad), []).append((int(low), int(high)))

    def is_claimed(norad: int, at_ms: int) -> bool:
        return any(low <= at_ms <= high for low, high in claimed.get(int(norad), ()))

    # -- catalogue events, grouped per object into chains -------------------
    steps_by_object: dict[int, list[dict[str, Any]]] = {}
    for event in catalogue_events:
        onset = _parse_epoch(event.get("startAt"))
        if onset is None or onset > now_ms:
            continue
        steps_by_object.setdefault(int(event["norad"]), []).append({
            "key": event.get("eventKey"),
            "epochMs": onset,
            "endMs": _parse_epoch(event.get("endAt")) or onset,
            "signature": event.get("signature"),
            "signatureLabel": event.get("signatureLabel"),
            "regime": event.get("regime"),
            "name": event.get("name"),
        })
    for rows in steps_by_object.values():
        rows.sort(key=lambda row: row["epochMs"])

    # -- the registered records become completed episodes -------------------
    for row in geo_record:
        arrival = _iso_ms(row.get("arrivalMs"))
        if arrival is None or arrival > now_ms:
            continue
        norad = int(row[_MOVER["geo"]])
        onset = _iso_ms(row.get("initiatingFlagMs")) or _iso_ms(row.get("transferStartMs"))
        # WHEN THE RECORD SAYS IT SETTLED, NOT WHEN YOU LOOKED. Clamping the
        # closing moment to `now_ms` published a completion dated the day of
        # the run, and moved it every time the clock did: measured over the
        # injected-clock exercise, 70 of 311 episodes completed as of 2019 had
        # a different completion date as of 2022, all of them sitting exactly
        # on the earlier clock. An episode that had arrived but not yet
        # departed as of the clock is IN PROGRESS, which is what it was.
        closing = (_iso_ms(row.get("departureMs")) or _iso_ms(row.get("loiterEndMs"))
                   or arrival)
        settled = closing <= now_ms
        observed_onset = row.get("initiatingFlagMs") is not None
        claim(norad, onset or arrival, closing)
        members = [
            {"key": step["key"], "epochMs": step["epochMs"], "delta": None}
            for step in steps_by_object.get(norad, ())
            if (onset or arrival) <= step["epochMs"] <= closing
        ]
        records.append(_record(
            key=f"geo|{norad}|{row.get('arrivalIso')}",
            norad=norad,
            name=row.get(_MOVER["geoName"]),
            regime="GEO",
            kind="impulsive" if observed_onset else "not-observed-onset",
            state="COMPLETED" if settled else "IN PROGRESS",
            closure="settled" if settled else "open",
            stage="S1",
            onsetMs=onset,
            updatedMs=closing if settled else int(now_ms),
            completedMs=closing if settled else None,
            partnerNorad=int(row["targetNorad"]),
            partnerName=row.get("targetName"),
            initial=None if not observed_onset else {
                "epochMs": onset,
                "lambdaDeg": None,
                "driftDegPerDay": _round(row.get("initiatingDriftChangeDegPerDay"), 5),
                "scatter": None,
                "windowDays": None,
            },
            current={
                "epochMs": closing if settled else int(now_ms),
                "lambdaDeg": _round(row.get("loiterLongitudeDeg"), 3),
                "driftDegPerDay": _round(row.get("departureDriftDegPerDay"), 5) if settled else None,
                "scatter": None,
                "windowDays": _round(row.get("loiterDays"), 2) if settled else None,
            },
            steps=members,
            trend={"slope": None, "slopeSe": None, "windowDays": None,
                   "trending": False, "test": "geo-band"},
            history=_history([(onset or closing, "INITIATED", "S1")]
                             + ([(closing, "COMPLETED", "S1")] if settled else [])),
            reading=_reading(near_geo=True, stage="S1", class_figures=class_figures),
        ))

    for row in leo_record:
        arrival = _iso_ms(row.get("arrivalMs"))
        if arrival is None or arrival > now_ms:
            continue
        norad = int(row[_MOVER["leo"]])
        onset = _iso_ms(row.get("initiatingConfirmMs")) or _iso_ms(row.get("campaignStartMs"))
        closing = _iso_ms(row.get("endMs")) or arrival
        settled = closing <= now_ms
        claim(norad, onset or arrival, closing)
        members = [
            {"key": step["key"], "epochMs": step["epochMs"], "delta": None}
            for step in steps_by_object.get(norad, ())
            if (onset or arrival) <= step["epochMs"] <= closing
        ]
        records.append(_record(
            key=f"leo|{norad}|{arrival}",
            norad=norad,
            name=row.get(_MOVER["leoName"]),
            regime="LEO",
            kind="campaign",
            state="COMPLETED" if settled else "IN PROGRESS",
            closure="settled" if settled else "open",
            stage="none",
            onsetMs=onset,
            updatedMs=closing if settled else int(now_ms),
            completedMs=closing if settled else None,
            partnerNorad=int(row["target"]),
            partnerName=row.get("targetName"),
            initial=None,
            current=None,
            steps=members,
            trend={"slope": None, "slopeSe": None, "windowDays": None,
                   "trending": False, "test": "block-slope"},
            history=_history([(onset or closing, "INITIATED", "none")]
                             + ([(closing, "COMPLETED", "none")] if settled else [])),
            reading=_reading(near_geo=False, stage="none", class_figures=None),
        ))

    # -- the remaining chains ------------------------------------------------
    for norad, rows in sorted(steps_by_object.items()):
        chains: list[list[dict[str, Any]]] = []
        for step in rows:
            if is_claimed(norad, step["epochMs"]):
                continue
            if (chains
                    and step["epochMs"] - chains[-1][-1]["epochMs"]
                    <= CAMPAIGN_MAX_GAP_DAYS * DAY_MS):
                chains[-1].append(step)
            else:
                chains.append([step])
        for chain in chains:
            record = _episode_from_chain(
                norad=norad, chain=chain, now_ms=now_ms, elements=elements,
                newest_epoch=newest_epoch, sigma=sigma, class_figures=class_figures,
            )
            if record is not None:
                records.append(record)

    # -- objects under a continuous rise with no step chain ------------------
    for norad, under_thrust in sorted(sustained.items()):
        if not under_thrust or steps_by_object.get(int(norad)):
            continue
        record = _continuous_episode(
            norad=int(norad), now_ms=now_ms, elements=elements,
            newest_epoch=newest_epoch, class_figures=class_figures,
        )
        if record is not None:
            records.append(record)

    records.sort(key=lambda entry: (-(entry["updatedMs"] or 0), str(entry["key"])))
    return records


def _episode_from_chain(
    *, norad: int, chain: Sequence[dict[str, Any]], now_ms: int,
    elements: Callable[[int, int, int], dict[str, np.ndarray]],
    newest_epoch: Callable[[int], int | None],
    sigma: float, class_figures: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """One chain of catalogue steps, as an episode with a state.

    Returns None when the chain is something that must not open one: keeping
    near the belt, or an orbit coming down under the atmosphere.
    """
    opening = chain[0]
    regime = opening.get("regime") or ""
    signatures = {step.get("signature") for step in chain}
    near_geo = regime in NEAR_GEO_REGIMES

    if signatures and signatures <= FALLING_SIGNATURES:
        return None
    if near_geo and signatures and signatures <= KEEPING_SIGNATURES:
        return None

    onset_ms = int(opening["epochMs"])
    baseline_days = pg.STATION_MIN_DAYS if near_geo else BLOCK_DAYS * MINIMUM_BASELINE_BLOCKS
    low_ms = int(onset_ms - baseline_days * DAY_MS)
    arrays = elements(norad, low_ms, int(now_ms))
    if arrays["epochMs"].size < 2:
        return None

    kind = "campaign" if len(chain) > 1 else "impulsive"
    steps = [{"key": step["key"], "epochMs": step["epochMs"], "delta": None} for step in chain]

    if near_geo:
        series = _attach_grid(_series(arrays, norad))
        if series is None:
            return None
        initial = _geo_state(series, low_ms, onset_ms)
        flag_ms, _ = _geo_flags(series, sigma)
        # A chain whose whole span stays inside the stationed band is the
        # object holding its slot, which is the baseline an episode departs
        # from rather than an episode.
        inside = (series.epoch_ms >= onset_ms)
        if bool(np.any(inside)) and float(np.max(np.abs(series.drift[inside]))) \
                <= SLOT_DRIFT_FLOOR_DEG_PER_DAY and not signatures - KEEPING_SIGNATURES:
            return None
        station = _station_after(series, onset_ms)
        settled_ms = int(station[1]) if station is not None and station[1] <= now_ms else None
        reopened = _steps_after(chain, settled_ms)
        # AN EPISODE IS JUDGED AT ITS OWN MOMENT, NOT AT THE PRESENT ONE.
        # Reading the trend from the newest element set in the whole window
        # meant a change that settled in 2010 was reported as still moving in
        # 2022 because the object was moving in 2022 -- for a different reason,
        # in a later episode. Measured over the injected-clock exercise, that
        # moved 17 of 311 episodes out of COMPLETED between two clocks. Once an
        # episode has settled, the moment that decides its state is the moment
        # it settled; only an open one is judged at `now_ms`.
        judged_ms = settled_ms if (settled_ms is not None and not reopened) else int(now_ms)
        span = inside & (series.epoch_ms <= judged_ms)
        trend = geo_trend(series.drift[span] if bool(np.any(span)) else series.drift,
                          flag_ms[flag_ms <= judged_ms] if flag_ms.size else flag_ms,
                          judged_ms)
        if trend["trending"] or reopened:
            state, completed = "IN PROGRESS", None
            current = _geo_state(series, float(series.epoch_ms[-1]) - DAY_MS,
                                 float(series.epoch_ms[-1]))
        elif settled_ms is not None and station is not None:
            state, completed = "COMPLETED", settled_ms
            current = _geo_state(series, station[0], settled_ms)
        else:
            state, completed = "INITIATED", None
            current = _geo_state(series, onset_ms, min(now_ms, onset_ms + DAY_MS))
        stage = "S1"
    else:
        epoch_ms = np.asarray(arrays["epochMs"], dtype=np.float64)
        axis_km = np.asarray(
            [semi_major_axis_km(float(value)) for value in arrays["meanMotion"]],
            dtype=np.float64,
        )
        inclination = np.asarray(arrays["inclination"], dtype=np.float64)
        initial = _outside_state(epoch_ms, axis_km, inclination, low_ms, onset_ms)
        still_since = _still_since(epoch_ms, axis_km, onset_ms, int(now_ms))
        reopened = _steps_after(chain, still_since)
        # The same rule outside the belt: a settled episode is judged at the
        # moment its dwell elapsed, so a later clock cannot re-open it with
        # activity that belongs to a later episode.
        judged_ms = int(still_since) if (still_since is not None and not reopened) else int(now_ms)
        trend = block_slope_trend(epoch_ms, axis_km, judged_ms)
        if trend["trending"] or reopened:
            state, completed = "IN PROGRESS", None
        elif still_since is not None:
            state, completed = "COMPLETED", int(still_since)
        else:
            state, completed = "INITIATED", None
        window_end = float(completed if completed is not None else min(now_ms, epoch_ms[-1]))
        current = _outside_state(
            epoch_ms, axis_km, inclination,
            window_end - BLOCK_DAYS * MINIMUM_BASELINE_BLOCKS * DAY_MS, window_end,
        )
        stage = "none"

    updated = int(min(now_ms, float(arrays["epochMs"][-1])))
    reopened = int(reopened)
    closure, state = _closure(
        norad=norad, state=state, updated_ms=updated, now_ms=int(now_ms),
        newest_epoch=newest_epoch, arrays=arrays,
    )
    return _record(
        key=f"cat|{norad}|{opening['key']}",
        norad=norad,
        name=opening.get("name"),
        regime=regime,
        kind=kind,
        state=state,
        closure=closure,
        reopened=reopened,
        stage=stage,
        onsetMs=onset_ms,
        updatedMs=updated,
        completedMs=completed,
        initial=initial,
        current=current,
        steps=steps,
        trend=trend,
        history=_history(
            [(onset_ms, "INITIATED", stage)]
            + ([(completed, "COMPLETED", stage)] if completed is not None else [])
        ),
        reading=_reading(near_geo=near_geo, stage=stage, class_figures=class_figures),
    )


def _steps_after(chain: Sequence[dict[str, Any]], settled_ms: int | None) -> int:
    """How many steps of this chain arrived after it had already settled.

    A step inside the campaign window re-opens the SAME episode rather than
    opening another: a staged transfer that coasts between burns can let the
    dwell elapse, and two episodes for one journey is a count nobody can use
    and a false completion nobody can see. The count is published, because it
    is the false-completion rate the design asks to be measured rather than
    assumed away.
    """
    if settled_ms is None:
        return 0
    return sum(1 for step in chain if int(step["epochMs"]) > int(settled_ms))


def _still_since(
    epoch_ms: np.ndarray, axis_km: np.ndarray, onset_ms: int, now_ms: int
) -> int | None:
    """The moment the trend test has returned still for three whole blocks.

    Walked forward from onset rather than tested once at the end, because the
    episode completes when the dwell elapses and not when someone looks.
    """
    window_ms = int(BLOCK_DAYS * MINIMUM_BASELINE_BLOCKS * DAY_MS)
    step_ms = int(BLOCK_DAYS * DAY_MS)
    gap_ms = int(MAXIMUM_JOINABLE_GAP_DAYS * DAY_MS)
    at = int(onset_ms) + window_ms
    while at <= now_ms:
        # THE DWELL ONLY RUNS WHILE THE OBJECT IS STILL BEING TRACKED. An
        # object that stopped being catalogued mid-episode has a window full of
        # nothing, and "no element set moved" is not the same sentence as "the
        # elements held still". Without this the dwell elapses on an empty
        # window and a lapse is published as a completion, which is the false
        # completion the design refuses.
        seen = epoch_ms[epoch_ms <= at]
        if seen.size == 0 or float(seen[-1]) < at - gap_ms:
            return None
        if not block_slope_trend(epoch_ms, axis_km, at)["trending"]:
            return at
        at += step_ms
    return None


def _closure(
    *, norad: int, state: str, updated_ms: int, now_ms: int,
    newest_epoch: Callable[[int], int | None], arrays: dict[str, np.ndarray],
) -> tuple[str, str]:
    """Open, settled, or lapsed -- and a lapse never promotes a state.

    An object that stopped being tracked before its episode completed has an
    episode nobody can finish. It keeps the state it reached and is marked, so
    that a reader is told tracking ended rather than left to read a stalled
    chip as a measurement.
    """
    if state == "COMPLETED":
        return "settled", state
    newest = newest_epoch(norad)
    gap_ms = MAXIMUM_JOINABLE_GAP_DAYS * DAY_MS
    if newest is None or now_ms - min(int(newest), updated_ms) >= gap_ms:
        return "lapsed", state
    axis = np.asarray(
        [semi_major_axis_km(float(value)) for value in arrays["meanMotion"]],
        dtype=np.float64,
    )
    eccentricity = np.asarray(arrays["eccentricity"], dtype=np.float64)
    perigee = axis * (1.0 - eccentricity) - RE_WGS72
    if perigee.size and float(perigee[-1]) < TERMINAL_DECAY_PERIGEE_KM:
        return "lapsed", state
    return "open", state


def _continuous_episode(
    *, norad: int, now_ms: int,
    elements: Callable[[int, int, int], dict[str, np.ndarray]],
    newest_epoch: Callable[[int], int | None],
    class_figures: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """An object climbing without a step to open on.

    The onset the instrument gives is the start of the window it judged, so the
    episode opens there and stays IN PROGRESS for as long as the climb lasts,
    with `current` advancing at every element set.
    """
    window_days = BLOCK_DAYS * MINIMUM_BASELINE_BLOCKS * 2
    low_ms = int(now_ms - window_days * DAY_MS)
    arrays = elements(norad, low_ms, int(now_ms))
    if arrays["epochMs"].size < 2:
        return None
    epoch_ms = np.asarray(arrays["epochMs"], dtype=np.float64)
    axis_km = np.asarray(
        [semi_major_axis_km(float(value)) for value in arrays["meanMotion"]],
        dtype=np.float64,
    )
    inclination = np.asarray(arrays["inclination"], dtype=np.float64)
    trend = block_slope_trend(epoch_ms, axis_km, int(now_ms))
    onset_ms = int(epoch_ms[0])
    updated = int(min(now_ms, epoch_ms[-1]))
    closure, state = _closure(
        norad=norad, state="IN PROGRESS" if trend["trending"] else "INITIATED",
        updated_ms=updated, now_ms=int(now_ms), newest_epoch=newest_epoch, arrays=arrays,
    )
    return _record(
        key=f"cont|{norad}|{onset_ms}",
        norad=norad,
        name=None,
        regime="LEO",
        kind="continuous",
        state=state,
        closure=closure,
        stage="none",
        onsetMs=onset_ms,
        updatedMs=updated,
        completedMs=None,
        initial=_outside_state(epoch_ms, axis_km, inclination, epoch_ms[0],
                               epoch_ms[0] + BLOCK_DAYS * DAY_MS),
        current=_outside_state(epoch_ms, axis_km, inclination,
                               updated - BLOCK_DAYS * DAY_MS, updated),
        steps=[],
        trend=trend,
        history=_history([(onset_ms, "INITIATED", "none")]),
        reading=_reading(near_geo=False, stage="none", class_figures=class_figures),
    )
