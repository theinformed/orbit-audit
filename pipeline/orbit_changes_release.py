#!/usr/bin/env python3
"""Build the artifacts the Orbit changes section fetches.

The section is a READER. Nothing here detects anything, classifies anything or
fits anything: every row it publishes is either copied out of a frozen record,
copied out of the shipped event bundle, or is arithmetic on the archive with the
registered instruments' own functions imported rather than re-derived
(`tools/proximity_geo.py` for the slot coordinate and the drift rate,
`tools/proximity_plane.py` for the phase angle). A second implementation of a
measured quantity is a second instrument, and this repository has learned what
that costs.

Five artifacts, split by how they are used:

| manifest field | prefix                      | content                        |
|----------------|-----------------------------|--------------------------------|
| `index`        | `orbit-changes-index`       | one slim row per change, all families |
| `belt`         | `geo-belt`                  | every near-belt object: slot coordinate, drift rate, stationed flag |
| `events`       | `orbit-changes-event-*`     | one file per change with a series behind it, fetched on open |
| `alerts`       | `orbit-alerts`              | the lane's spoken rows, or the labelled gap |
| `settings`     | `orbit-alert-settings`      | the operating points that have been counted |

**The archive is opened read-only and never written**: `mode=ro` on the URI and
`PRAGMA query_only`, so a mistake fails rather than mutates.

**Byte-stability is a property, not a hope.** Every output is a pure function of
its inputs, `generatedAt` included: it defaults to the event bundle's own
timestamp rather than to the clock, so two runs over the same inputs produce the
same bytes and therefore the same content-addressed names.

**What is not here, on purpose.** No registry code and no country, on any row of
any artifact (design row 10.3 is open, and an absent field cannot be printed by
accident). No velocity-change figure, though the shipped event bundle carries
one. No separation in kilometres, though the frozen belt record carries one: a
slot coordinate converted to kilometres reads as a distance between two objects,
which it is not. No plane-separation series for the low-orbit arm, which speaks
about phase inside a plane two objects already share and about nothing else.

Run it: `python3 -m pipeline.orbit_changes_release --build`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.orbit_history import (  # noqa: E402
    SCALE_ANGLE,
    SCALE_ECCENTRICITY,
    SCALE_MEAN_MOTION,
    archive_db_path,
    semi_major_axis_km,
)
from pipeline import orbit_episodes  # noqa: E402
from tools import proximity_geo as geo  # noqa: E402
from tools import proximity_plane as plane  # noqa: E402

SCHEMA = 1
DAY_MS = 86_400_000

FRAGMENT_PATH = ROOT / "pipeline" / ".cache" / "orbit-changes-manifest.json"
MANIFEST_KEY = "orbitChanges"

GEO_RECORD = ROOT / "docs" / "proximity-events-20260922.jsonl"
LEO_RECORD = ROOT / "docs" / "proximity-leo-events-20260922.jsonl"
TRIGGER_RESULTS = ROOT / "docs" / "trigger-alarm-results-20260922.md"
KINEMATIC_INPUTS = ROOT / "docs" / "kinematic-inputs-20260922.json"
TRUTHSET_GROWTH = ROOT / "docs" / "t16b-truthset-growth-20260922.json"
FROZEN_MODEL = ROOT / "docs" / "alarm-lane-model-20260922.json"
LEDGER_PATH = ROOT / "runtime" / "alarm-lane" / "alarm-lane-ledger.jsonl"

# THE REPLAY. No lane is running, so what the Alerts view reads is the lane's
# own synthetic exercise over the 2010s, produced with an injected clock. It is
# published as a replay and labelled as one in the artifact itself, not only on
# the page: `live` is false, `source` is the replay, and the exercise block
# carries the window and the receipt that earned it.
REPLAY_RECEIPT = ROOT / "docs" / "alarm-lane-replay-20260922-receipt.json"
REPLAY_LEDGERS = {
    "everything": ROOT / "docs" / "alarm-lane-replay-20260922-everything-ledger.jsonl",
    "high-confidence": ROOT / "docs" / "alarm-lane-replay-20260922-high-confidence-ledger.jsonl",
}
# The setting whose rows become the cards. It is the LOOSEST one the replay
# exercised, because the dial narrows it: a tighter setting's list has to be a
# subset of a looser one's, and reading each setting's own ledger would make
# four lists that nothing holds together.
LISTED_SETTING = "everything"
CURVE_PATH = ROOT / "docs" / "alarm-lane-operating-points-20260922.json"
LEO_MODEL = ROOT / "docs" / "alarm-lane-leo-model-20260922.json"
LEO_REPLAY_RECEIPT = ROOT / "docs" / "alarm-lane-leo-replay-20260922-receipt.json"
# How far either side of a trigger the archive is asked for the element set the
# reachable set is swept from. The near-belt median spacing is 0.76 d, so five
# days is several sets on both sides and still inside the change.
ANCHOR_WINDOW_DAYS = 5

# How much of each object's record travels with an event. The measured forward
# error is quoted at +30 d and the spoken class's arrival p95 is 90 d, so a
# window of 180 d either side holds the whole of what can be said plus the run-up
# that shows the change against what came before it.
SERIES_WINDOW_DAYS = 180
# The belt is a present-tense picture, so it is built from the newest element
# sets only. Ninety days is long enough to fit a drift rate through the
# catalogue's publication cadence and short enough that a retired object drops
# out of it.
BELT_WINDOW_DAYS = 90
BELT_MIN_SAMPLES = 6
# The registered ceiling on interpolating a fast angle (T8b prereg 5.1). A phase
# grid point without an element set this close on both sides is not published at
# all; it is a hole, and a hole draws as a break in the line.
FAST_ANGLE_MAX_GAP_DAYS = plane.FAST_ANGLE_MAX_GAP_DAYS
FORWARD_STEP_DAYS = 1.0

# Rounding, fixed here so that two runs agree to the last digit. The series
# carry one more place than the section prints, because a chart fits slopes
# through them and the printed value is the endpoint, not the fit.
LONGITUDE_PLACES = 3
DRIFT_PLACES = 5
KM_PLACES = 3
ANGLE_PLACES = 4


# ---------------------------------------------------------------------------
# Reading the frozen sources
# ---------------------------------------------------------------------------
def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def forward_error(inputs: dict[str, Any]) -> dict[str, Any]:
    """How wrong the forward path is, at every horizon it was measured at.

    M1 measured the error at ten horizons on the same method the +30 d figure
    used, and the registration then CUT THE DESIGN'S HORIZON on what it found:

    * membership of a reachable set is resolvable to **+20 days**, and the
      drawn path stops there -- beyond it the band is wider than the belt's own
      measured slot spacing, so a ribbon drawn onward covers several occupied
      longitudes and invites a reach the geometry cannot support;
    * an arrival time may be stated to co-location precision only to
      **+10 days**;
    * at **+180 days** the median error is 2.651 deg, which exceeds the 2.0 deg
      bar Gate W was registered against, so that horizon is unfit and is
      labelled rather than used.

    The band may still be DRAWN out to +180 d, because what it shows there is
    true and is the point: it grows past the objects it is drawn among. What
    may not be drawn there is the path.

    Every number is read from the artifact. Nothing here is typed, and the
    three horizons above are read from the results that decided them.
    """
    arm = inputs["M1"]["armA"]["byHorizon"]
    spacing = inputs["M1"]["slotSpacing"]
    published = inputs["M1"]["published30d"]
    reproduction = inputs["M1"]["gateK1Reproduction"]
    if not reproduction.get("passed"):
        raise SystemExit(
            "the measured forward-error table does not reproduce the published "
            "+30 d figure; the ribbon has no source"
        )
    return {
        "byHorizon": {
            days: {
                "n": row["n"],
                "p50Deg": round(row["p50"], 4),
                "p75Deg": round(row["p75"], 4),
                "p95Deg": round(row["p95"], 4),
            }
            for days, row in sorted(arm.items(), key=lambda pair: int(pair[0]))
        },
        # The design's original horizon, kept so a reader of the artifact can
        # see which figure the section used to draw and which it draws now.
        "publishedHorizonDays": 30,
        "publishedP50Deg": published["p50"],
        "membershipHorizonDays": 20,
        "precisionHorizonDays": 10,
        "unfitHorizonDays": 180,
        "unfitBarDeg": 2.0,
        "slotSpacingP50Deg": round(spacing["p50"], 4),
        "source": f"docs/{KINEMATIC_INPUTS.name}",
        "registration": inputs["M1"]["registration"],
    }


def low_orbit_error(growth: dict[str, Any]) -> dict[str, Any]:
    """How wrong a low-orbit forward path is, measured against precise orbits.

    T16b propagated catalogue element sets against three spacecraft whose true
    orbits are published to centimetres, and the along-track error it measured
    grows as the SQUARE of the time, not linearly: about half a kilometre at
    the epoch, 2 km at +3 d, 24 km at +14 d and some hundreds by +60 d.

    THAT MATTERS BECAUSE THE SECTION'S ORIGINAL RIBBON WOULD HAVE BEEN WRONG IN
    BOTH DIRECTIONS. Drawn from the element-set noise alone it is several times
    too WIDE in the days after a change and several times too NARROW three
    months out, which is the worst arrangement available: it overstates the
    uncertainty where a reader would act on it and understates it where they
    would not.

    THE CAVEAT TRAVELS WITH THE NUMBERS and is quoted from the results rather
    than paraphrased: these are three of the best-tracked spacecraft in orbit,
    and their error growth is a BEST CASE for a catalogue-typical object rather
    than a typical one. The per-object drag stratum of M2 still applies on top:
    a 90-day horizon is meaningful for well under two thirds of objects, and
    which ones is a property of their drag, so no regime-wide horizon is
    published here.
    """
    missions = growth["missions"]
    horizons = [str(day) for day in growth["horizonDays"]]
    combined: dict[str, Any] = {}
    for day in horizons:
        rows = [mission["horizons"][day] for mission in missions.values()
                if day in mission.get("horizons", {})]
        if not rows:
            continue
        # A RANGE ACROSS THE THREE SPACECRAFT, NOT A POOLED NUMBER.
        # Quantiles cannot be pooled: the median of three medians is not the
        # median of the three samples, and there is no way back to the
        # comparisons from the quantiles this artifact publishes. So what is
        # published is the lowest and the highest of the three, which is a
        # true statement about what was measured, and a per-spacecraft row
        # beside it so a reader can see which orbit gave which.
        combined[day] = {
            "n": sum(row["n"] for row in rows),
            "alongTrackKmP50Low": round(min(row["alongTrackKm"]["p50"] for row in rows), 3),
            "alongTrackKmP50High": round(max(row["alongTrackKm"]["p50"] for row in rows), 3),
            "alongTrackKmP95High": round(max(row["alongTrackKm"]["p95"] for row in rows), 3),
            "alongTrackPhaseDegP50High": round(
                max(row["alongTrackPhaseDeg"]["p50"] for row in rows), 5),
        }
    return {
        "byHorizon": combined,
        "missions": sorted(missions),
        "caveat": "measured on three best-tracked spacecraft; a best case for "
                  "catalogue-typical objects",
        "perObjectStratum": "M2: a 90-day horizon is meaningful for 58.2% of objects "
                            "and which ones is a property of their drag, so no "
                            "regime-wide horizon is published",
        "source": f"docs/{TRUTHSET_GROWTH.name}",
        "registration": growth["registration"],
    }


def gate_w_error(results_text: str) -> dict[str, Any]:
    """The measured forward error at +30 d, read from the results it was measured in.

    Typing these three numbers would make the ribbon a drawing of an assumption.
    They are anchored to the row that carries them, and this function raises if
    that row has moved, because a ribbon whose provenance has gone is worse than
    no ribbon.
    """
    flat = " ".join(results_text.split())
    row = re.search(
        r"at \+30 d \| \*\*([\d.]+)°\*\* \| ([\d.]+)° \| ([\d.]+)° \|", flat
    )
    support = re.search(r"Over the ([\d,]+) primary-arm triggers", flat)
    if row is None or support is None:
        raise SystemExit(
            "the measured forward-error row is no longer in "
            f"{TRIGGER_RESULTS.name}; the ribbon has no source"
        )
    return {
        "horizonDays": 30,
        "p50Deg": float(row.group(1)),
        "p75Deg": float(row.group(2)),
        "p95Deg": float(row.group(3)),
        "support": int(support.group(1).replace(",", "")),
        "source": f"docs/{TRIGGER_RESULTS.name}",
        "beyondHorizon": "not-measured",
    }


# ---------------------------------------------------------------------------
# The archive, read-only
# ---------------------------------------------------------------------------
def open_readonly(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.execute("PRAGMA query_only=ON")
    return connection


_ELEMENT_COLUMNS = (
    "epoch_ms, mean_motion_q, eccentricity_q, inclination_q, "
    "raan_q, arg_perigee_q, mean_anomaly_q"
)


def element_window(
    connection: sqlite3.Connection, norad: int, low_ms: int, high_ms: int
) -> dict[str, np.ndarray]:
    """One object's element sets in a time window, as unpacked arrays.

    The primary key is `(norad, epoch_ms)` on a `WITHOUT ROWID` table, so this is
    a key-range seek and not a scan: the whole belt costs a few seconds.
    """
    rows = connection.execute(
        f"SELECT {_ELEMENT_COLUMNS} FROM element_set "
        "WHERE norad = ? AND epoch_ms BETWEEN ? AND ? ORDER BY epoch_ms",
        (int(norad), int(low_ms), int(high_ms)),
    ).fetchall()
    if not rows:
        return {name: np.zeros(0) for name in
                ("epochMs", "meanMotion", "eccentricity", "inclination", "raan", "argPerigee", "meanAnomaly")}
    packed = np.asarray(rows, dtype=np.float64)
    return {
        "epochMs": packed[:, 0],
        "meanMotion": packed[:, 1] / SCALE_MEAN_MOTION,
        "eccentricity": packed[:, 2] / SCALE_ECCENTRICITY,
        "inclination": packed[:, 3] / SCALE_ANGLE,
        "raan": packed[:, 4] / SCALE_ANGLE,
        "argPerigee": packed[:, 5] / SCALE_ANGLE,
        "meanAnomaly": packed[:, 6] / SCALE_ANGLE,
    }


def daily_indices(epoch_ms: np.ndarray) -> np.ndarray:
    """One element set per UTC day: the last of that day, deterministically."""
    if epoch_ms.size == 0:
        return np.zeros(0, dtype=np.int64)
    day = np.floor(epoch_ms / DAY_MS).astype(np.int64)
    keep = np.ones(day.size, dtype=bool)
    keep[:-1] = day[:-1] != day[1:]
    return np.flatnonzero(keep)


def grid_series(
    values: np.ndarray, epoch_ms: np.ndarray, start_day: int, day_count: int
) -> list[float | None]:
    """Place one value on each day of a fixed grid, or a hole where there is none."""
    out: list[float | None] = [None] * day_count
    if epoch_ms.size == 0:
        return out
    day = np.floor(epoch_ms / DAY_MS).astype(np.int64) - start_day
    for index, slot in enumerate(day.tolist()):
        if 0 <= slot < day_count:
            out[slot] = float(values[index])
    return out


# ---------------------------------------------------------------------------
# The slot coordinate, the drift rate, and the forward path
# ---------------------------------------------------------------------------
def slot_coordinate(elements: dict[str, np.ndarray]) -> np.ndarray:
    return geo.mean_longitude_deg(
        elements["raan"], elements["argPerigee"], elements["meanAnomaly"], elements["epochMs"]
    )


def drift_rate(elements: dict[str, np.ndarray]) -> np.ndarray:
    return geo.drift_rate_deg_per_day(elements["meanMotion"])


def forward_path(
    lambda_deg: float,
    drift_deg_per_day: float,
    horizon_days: float,
    *,
    acceleration: float,
    stable_deg: float,
    step_days: float = FORWARD_STEP_DAYS,
) -> list[float]:
    """The resonance integration, RK4 at a one-day step.

    ``dlambda/dt = ddot`` and ``dddot/dt = -K sin 2(lambda - lambda_stable)``.
    The constants are the frozen bundle's own; nothing is fitted here. A
    straight line instead of this omits half K H squared, which at 180 days is
    27.5 degrees -- not a correction but a quantity the size of the signal.

    The returned list is the slot coordinate at day 0, 1, ... up to the horizon.
    It says where the coordinate would be if the object did nothing further, and
    it is not a position.
    """
    def slope(state: tuple[float, float]) -> tuple[float, float]:
        lam, ddot = state
        return ddot, -acceleration * math.sin(2.0 * math.radians(lam - stable_deg))

    lam, ddot = float(lambda_deg), float(drift_deg_per_day)
    out = [round(geo.wrap180(lam).item(), LONGITUDE_PLACES)]
    steps = int(round(horizon_days / step_days))
    for _ in range(steps):
        k1 = slope((lam, ddot))
        k2 = slope((lam + 0.5 * step_days * k1[0], ddot + 0.5 * step_days * k1[1]))
        k3 = slope((lam + 0.5 * step_days * k2[0], ddot + 0.5 * step_days * k2[1]))
        k4 = slope((lam + step_days * k3[0], ddot + step_days * k3[1]))
        lam += step_days / 6.0 * (k1[0] + 2.0 * k2[0] + 2.0 * k3[0] + k4[0])
        ddot += step_days / 6.0 * (k1[1] + 2.0 * k2[1] + 2.0 * k3[1] + k4[1])
        out.append(round(geo.wrap180(lam).item(), LONGITUDE_PLACES))
    return out


def fitted_drift(times_ms: np.ndarray, unwrapped_deg: np.ndarray) -> float | None:
    """Least squares slope of the unwrapped slot coordinate, degrees per day."""
    if times_ms.size < 2:
        return None
    days = (times_ms - times_ms[0]) / DAY_MS
    if float(days[-1] - days[0]) <= 0.0:
        return None
    slope, _ = np.polyfit(days, unwrapped_deg, 1)
    return float(slope)


# ---------------------------------------------------------------------------
# The belt
# ---------------------------------------------------------------------------
def belt(
    connection: sqlite3.Connection, *, now_ms: int, drift_floor: float
) -> dict[str, Any]:
    """Every near-belt object, its slot coordinate, its drift rate, stationed or not.

    The eligibility proxy is the lane's own: an object is STATIONED when the
    magnitude of its fitted drift rate is at or below the frozen bundle's slot
    floor. It is a description of the last ninety days of its elements and
    nothing else -- not a claim about what it is for, and not a claim about what
    it will do.
    """
    low_ms = now_ms - BELT_WINDOW_DAYS * DAY_MS
    candidates = [
        int(row[0])
        for row in connection.execute(
            "SELECT norad FROM object_rollup WHERE max_epoch_ms >= ? ORDER BY norad",
            (low_ms,),
        )
    ]
    floor = float(drift_floor)
    rows: list[dict[str, Any]] = []
    for norad in candidates:
        elements = element_window(connection, norad, low_ms, now_ms)
        if elements["epochMs"].size < BELT_MIN_SAMPLES:
            continue
        motion = elements["meanMotion"]
        if not (geo.MM_MIN_REV_DAY <= float(np.median(motion)) <= geo.MM_MAX_REV_DAY):
            continue
        if float(np.median(elements["eccentricity"])) > geo.ECC_MAX:
            continue
        if float(np.median(elements["inclination"])) > geo.INC_MAX_DEG:
            continue
        lam = slot_coordinate(elements)
        ddot = drift_rate(elements)
        unwrapped = geo.unwrap_longitude(lam, elements["epochMs"], ddot)
        fitted = fitted_drift(elements["epochMs"], unwrapped)
        if fitted is None:
            continue
        rows.append({
            "norad": norad,
            "longitudeDeg": round(float(lam[-1]), LONGITUDE_PLACES),
            "driftDegPerDay": round(fitted, DRIFT_PLACES),
            # The plane, so a reachable set can print how many of its members
            # share one with the mover. It is the object's own median over the
            # window and it is a fact about the elements, not a match with
            # anything: no candidate set anywhere in this section is BUILT by
            # comparing two planes.
            "inclinationDeg": round(float(np.median(elements["inclination"])), ANGLE_PLACES),
            "stationed": abs(fitted) <= floor,
            "lastEpochMs": int(elements["epochMs"][-1]),
            "samples": int(elements["epochMs"].size),
        })
    names = object_names(connection, [row["norad"] for row in rows])
    for row in rows:
        name = names.get(int(row["norad"]))
        if name:
            row["name"] = name
    rows.sort(key=lambda entry: (entry["longitudeDeg"], entry["norad"]))
    return {
        "schema": SCHEMA,
        "windowDays": BELT_WINDOW_DAYS,
        "stationedDriftFloorDegPerDay": floor,
        "objects": len(rows),
        "stationed": sum(1 for row in rows if row["stationed"]),
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# Event files
# ---------------------------------------------------------------------------
def _window_days(centre_ms: int) -> tuple[int, int, int, int]:
    start_day = int(math.floor(centre_ms / DAY_MS)) - SERIES_WINDOW_DAYS
    day_count = 2 * SERIES_WINDOW_DAYS + 1
    return start_day, day_count, start_day * DAY_MS, (start_day + day_count) * DAY_MS


def series_value_at(series: dict[str, Any], slot: int) -> tuple[int, float] | None:
    """The value at `slot`, or the nearest earlier one, with the slot it came from.

    A forward path has to start from a coordinate that was actually observed.
    Walking backwards rather than substituting the series' beginning keeps the
    anchor on the right side of the change.
    """
    values = series["values"]
    for index in range(min(slot, len(values) - 1), -1, -1):
        value = values[index]
        if value is not None:
            return index, float(value)
    return None


def slot_series(
    connection: sqlite3.Connection, norad: int, centre_ms: int
) -> dict[str, Any]:
    start_day, day_count, low_ms, high_ms = _window_days(centre_ms)
    elements = element_window(connection, norad, low_ms, high_ms)
    keep = daily_indices(elements["epochMs"])
    if keep.size == 0:
        return {"startMs": start_day * DAY_MS, "stepDays": 1.0, "values": [None] * day_count,
                "samples": 0}
    epochs = elements["epochMs"][keep]
    lam = slot_coordinate({key: value[keep] for key, value in elements.items()})
    return {
        "startMs": start_day * DAY_MS,
        "stepDays": 1.0,
        "values": [None if value is None else round(value, LONGITUDE_PLACES)
                   for value in grid_series(lam, epochs, start_day, day_count)],
        "samples": int(keep.size),
    }


def _advance_to(elements: dict[str, np.ndarray], index: int, target_ms: float) -> np.ndarray:
    """One object's position direction at `target_ms`, from the element set at `index`.

    Only the fast angle is advanced, by the object's own mean motion, and only
    across a gap the registration allows. The slow angles are the element set's
    own: over a day they move by far less than the phase angle this feeds.
    """
    days = (target_ms - elements["epochMs"][index]) / DAY_MS
    mean_anomaly = elements["meanAnomaly"][index] + 360.0 * elements["meanMotion"][index] * days
    true_anomaly = plane.true_anomaly_deg(mean_anomaly, elements["eccentricity"][index])
    return plane.position_unit_vector(
        elements["inclination"][index],
        elements["raan"][index],
        elements["argPerigee"][index],
        true_anomaly,
    )


def phase_series(
    connection: sqlite3.Connection, norad: int, partner: int, centre_ms: int
) -> dict[str, Any]:
    """The angle between two objects along their shared track, day by day.

    This is the phase the low-orbit study measured and the only thing this arm
    speaks about. There is no plane-separation series here and no plane product
    anywhere in this file: that channel was blinded and its noise floor has not
    been re-derived.
    """
    start_day, day_count, low_ms, high_ms = _window_days(centre_ms)
    span = FAST_ANGLE_MAX_GAP_DAYS * DAY_MS
    left = element_window(connection, norad, low_ms - span, high_ms + span)
    right = element_window(connection, partner, low_ms - span, high_ms + span)
    values: list[float | None] = [None] * day_count
    if left["epochMs"].size and right["epochMs"].size:
        for slot in range(day_count):
            target = (start_day + slot) * DAY_MS + DAY_MS // 2
            a = int(np.argmin(np.abs(left["epochMs"] - target)))
            b = int(np.argmin(np.abs(right["epochMs"] - target)))
            if abs(left["epochMs"][a] - target) > span or abs(right["epochMs"][b] - target) > span:
                continue
            angle = plane.track_angle_deg(_advance_to(left, a, target), _advance_to(right, b, target))
            values[slot] = round(float(angle), ANGLE_PLACES)
    return {
        "startMs": start_day * DAY_MS,
        "stepDays": 1.0,
        "values": values,
        "maxGapDays": FAST_ANGLE_MAX_GAP_DAYS,
        "samples": sum(1 for value in values if value is not None),
    }


def element_panels(
    connection: sqlite3.Connection, norad: int, centre_ms: int
) -> dict[str, Any]:
    """The element panels the history browser already draws, on one grid.

    Semi-major axis, inclination and eccentricity only. The perigee/apogee band
    the browser draws is exactly `a(1 -/+ e) - Re`, so shipping it as well would
    be shipping the same measurement twice and leaving open the question of
    which copy is right.
    """
    start_day, day_count, low_ms, high_ms = _window_days(centre_ms)
    elements = element_window(connection, norad, low_ms, high_ms)
    keep = daily_indices(elements["epochMs"])
    if keep.size == 0:
        def empty() -> list[float | None]:
            return [None] * day_count

        return {"startMs": start_day * DAY_MS, "stepDays": 1.0, "samples": 0,
                "earthRadiusKm": plane.EARTH_RADIUS_KM,
                "semiMajorAxisKm": empty(), "inclinationDeg": empty(),
                "eccentricity": empty()}
    epochs = elements["epochMs"][keep]
    axis = np.asarray([semi_major_axis_km(float(value)) for value in elements["meanMotion"][keep]])
    ecc = elements["eccentricity"][keep]
    inclination = elements["inclination"][keep]

    def place(values: np.ndarray, places: int) -> list[float | None]:
        return [None if value is None else round(value, places)
                for value in grid_series(values, epochs, start_day, day_count)]

    return {
        "startMs": start_day * DAY_MS,
        "stepDays": 1.0,
        "samples": int(keep.size),
        "earthRadiusKm": plane.EARTH_RADIUS_KM,
        "semiMajorAxisKm": place(axis, KM_PLACES),
        "inclinationDeg": place(inclination, ANGLE_PLACES),
        "eccentricity": place(ecc, 7),
    }


def element_state(row: Sequence[float] | None) -> dict[str, Any] | None:
    """One element set as the summary an episode row carries.

    Semi-major axis, inclination and eccentricity for every object, because
    those are what an element set is anywhere.

    THE SLOT COORDINATE AND THE DRIFT RATE TRAVEL ONLY FOR BELT OBJECTS, and
    that is the whole reason the fields are conditional. `lambda` is the
    coordinate of a stationary slot and `360 n - omega_E` is how fast an object
    walks along it; both are defined by synchronous motion. Carrying them for a
    low-orbit object publishes a drift rate of five thousand degrees a day and a
    mean longitude that means nothing, and a reader who saw one of those would
    be right to stop trusting the rest. Absent where they do not apply, and the
    surface draws a labelled gap.
    """
    if row is None:
        return None
    motion = row[1] / SCALE_MEAN_MOTION
    summary = {
        "epochMs": int(row[0]),
        "semiMajorAxisKm": round(semi_major_axis_km(motion), KM_PLACES),
        "inclinationDeg": round(row[3] / SCALE_ANGLE, ANGLE_PLACES),
        "eccentricity": round(row[2] / SCALE_ECCENTRICITY, 7),
    }
    if geo.MM_MIN_REV_DAY <= motion <= geo.MM_MAX_REV_DAY:
        elements = {
            "epochMs": np.asarray([row[0]], dtype=np.float64),
            "raan": np.asarray([row[4] / SCALE_ANGLE]),
            "argPerigee": np.asarray([row[5] / SCALE_ANGLE]),
            "meanAnomaly": np.asarray([row[6] / SCALE_ANGLE]),
        }
        summary["longitudeDeg"] = round(float(slot_coordinate(elements)[0]), LONGITUDE_PLACES)
        summary["driftDegPerDay"] = round(float(geo.drift_rate_deg_per_day(motion)), DRIFT_PLACES)
    return summary


def episode_bounds(
    connection: sqlite3.Connection, norad: int, start_ms: int, end_ms: int, *, now_ms: int
) -> dict[str, Any]:
    """An episode's opening and closing element state, and which state it is in.

    THE STATE IS READ FROM THE ARCHIVE, not assumed from the record. An episode
    whose closing element set is the newest one the archive holds for that
    object is still running as far as anything here can tell; one with element
    sets after it has settled into whatever it settled into; one with an opening
    and no closing has only been seen to start. `stateBasis` says which of those
    three sentences was true, so a later state machine can disagree with this
    one without having to guess what it meant.

    The type slot and the reading slot are declared and empty. There is no
    library to label a type from yet and nothing has been measured to read, and
    an absent field renders as a labelled gap rather than as a blank that could
    be mistaken for "none".
    """
    before = connection.execute(
        f"SELECT {_ELEMENT_COLUMNS} FROM element_set WHERE norad = ? AND epoch_ms <= ? "
        "ORDER BY epoch_ms DESC LIMIT 1",
        (int(norad), int(start_ms)),
    ).fetchone()
    after = connection.execute(
        f"SELECT {_ELEMENT_COLUMNS} FROM element_set WHERE norad = ? AND epoch_ms >= ? "
        "ORDER BY epoch_ms ASC LIMIT 1",
        (int(norad), int(end_ms)),
    ).fetchone()
    newest = connection.execute(
        "SELECT MAX(epoch_ms) FROM element_set WHERE norad = ?", (int(norad),)
    ).fetchone()
    newest_ms = int(newest[0]) if newest and newest[0] is not None else None

    if after is None:
        state, basis = ("initiated", "no element set has been published at or after the end of it")
    elif newest_ms is not None and int(after[0]) >= newest_ms:
        state, basis = ("in-progress", "its closing element set is the newest the archive holds for this object")
    else:
        state, basis = ("completed", "element sets published after it show where it settled")
    del now_ms
    return {
        "state": state,
        "stateBasis": basis,
        "initial": element_state(before),
        "current": element_state(after),
        "type": None,
        "typePrecision": None,
        "readingLines": None,
    }


def element_change(
    connection: sqlite3.Connection, norad: int, start_ms: int, end_ms: int
) -> dict[str, Any]:
    """What moved across one catalogued change: semi-major axis, inclination, drift.

    The element set last published before the change and the one next published
    after it. Nothing is interpolated into the gap, and where either side is
    missing the field is absent rather than zero.
    """
    before = connection.execute(
        f"SELECT {_ELEMENT_COLUMNS} FROM element_set WHERE norad = ? AND epoch_ms <= ? "
        "ORDER BY epoch_ms DESC LIMIT 1",
        (int(norad), int(start_ms)),
    ).fetchone()
    after = connection.execute(
        f"SELECT {_ELEMENT_COLUMNS} FROM element_set WHERE norad = ? AND epoch_ms >= ? "
        "ORDER BY epoch_ms ASC LIMIT 1",
        (int(norad), int(end_ms)),
    ).fetchone()
    if before is None or after is None:
        return {}
    motion_before = before[1] / SCALE_MEAN_MOTION
    motion_after = after[1] / SCALE_MEAN_MOTION
    return {
        "semiMajorAxisKm": round(
            semi_major_axis_km(motion_after) - semi_major_axis_km(motion_before), KM_PLACES
        ),
        "inclinationDeg": round((after[3] - before[3]) / SCALE_ANGLE, ANGLE_PLACES),
        "driftDegPerDay": round(
            float(geo.drift_rate_deg_per_day(motion_after) - geo.drift_rate_deg_per_day(motion_before)),
            DRIFT_PLACES,
        ),
        "observedFromMs": int(before[0]),
        "observedToMs": int(after[0]),
    }


# ---------------------------------------------------------------------------
# The labelled gaps
# ---------------------------------------------------------------------------
def _newest_epoch(connection: sqlite3.Connection, norad: int) -> int | None:
    """The newest element set the archive holds for one object."""
    row = connection.execute(
        "SELECT MAX(epoch_ms) FROM element_set WHERE norad = ?", (int(norad),)
    ).fetchone()
    return int(row[0]) if row and row[0] is not None else None


def _repo_relative(path: Path) -> str:
    """A path a reader can find, whether or not it is inside this repository."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _ledger_parts(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """A ledger file as its header, its assessments and its resolutions by alert.

    The lane writes one append-only file: a provenance line, then an assessment
    for every change it looked at, then a resolution for every alert whose
    horizon closed. The three are separated here and nothing is dropped -- the
    counts below are over the assessments, including the ones that were never
    spoken, which is the whole point of an append-only record.
    """
    rows = read_jsonl(path)
    header = rows[0] if rows and rows[0].get("record") == "provenance" else {}
    body = rows[1:] if header else rows
    assessments = [row for row in body if row.get("record") == "assessment"]
    resolutions = {row["alertId"]: row for row in body if row.get("record") == "resolution"}
    return header, assessments, resolutions


def _setting_counts(
    assessments: Sequence[dict[str, Any]], resolutions: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """What one setting's replay did, as counts and one measured precision.

    `runningPrecision` is THIS LANE'S OWN: the alerts it raised that ended in an
    attributed arrival, over the alerts it raised. It is not the frozen figure
    and it never replaces it -- the page prints the pair. When no alert of the
    class has resolved it is null, which the page renders as the labelled gap
    the lane's own text uses, never as a zero.
    """
    spoken = [row for row in assessments if row.get("spoken") is True]
    resolved = [resolutions[row["alertId"]] for row in spoken if row["alertId"] in resolutions]
    arrivals = [row for row in resolved if row.get("state") == "arrival"]
    closed = [row for row in resolved if row.get("state") in ("arrival", "none")]
    precision = (len(arrivals) / len(closed)) if closed else None
    return {
        "assessed": len(assessments),
        "notAssessable": sum(1 for row in assessments if row.get("assessable") is False),
        "withheld": sum(1 for row in assessments
                        if row.get("assessable") is not False and row.get("spoken") is not True),
        "raised": len(spoken),
        "resolved": len(closed),
        "arrivals": len(arrivals),
        "pending": len(spoken) - len(resolved),
        "runningPrecision": precision,
        "runningPositives": len(arrivals),
        "runningSupport": len(closed),
    }


def alert_anchor(
    connection: sqlite3.Connection, norad: int, trigger_ms: float
) -> dict[str, Any] | None:
    """Where the object was on the belt when its change was confirmed.

    The ledger carries the drift rate and how much of it the change was; it does
    not carry the slot coordinate, because the lane has no surface and needed
    none. A reachable set has to be swept from somewhere, so the coordinate is
    read back out of the archive at the trigger -- the element set at or just
    before it, or the nearest one after when the change opened a gap.

    The inclination travels with it so the set can say how many of its members
    share the mover's plane. Neither number is a new measurement: both are the
    archive's own element set, unpacked by the registered instrument.
    """
    span = ANCHOR_WINDOW_DAYS * DAY_MS
    elements = element_window(connection, norad, int(trigger_ms - span), int(trigger_ms + span))
    if elements["epochMs"].size == 0:
        return None
    before = np.flatnonzero(elements["epochMs"] <= trigger_ms)
    index = int(before[-1]) if before.size else 0
    lam = slot_coordinate(elements)
    return {
        "lambdaDeg": round(float(lam[index]), LONGITUDE_PLACES),
        "inclinationDeg": round(float(elements["inclination"][index]), ANGLE_PLACES),
        "epochMs": int(elements["epochMs"][index]),
    }


def _slim_alert(
    row: dict[str, Any],
    resolution: dict[str, Any] | None,
    anchor: dict[str, Any] | None,
    name: str | None,
) -> dict[str, Any]:
    """One spoken row, with what the page draws and nothing it does not.

    `text` travels VERBATIM. The page renders it as the alert's body and
    composes no sentence of its own, so the words a reader sees are the lane's
    own and are gated by the lane's own vocabulary.

    The class figures are NOT on the row: they are the same three numbers on
    every row of a class, and they travel once in `classFigures`. What is on the
    row is what differs between alerts, plus the evidence values the dial
    filters on -- the drift change, how many element sets it held for, the
    horizon -- so that the page's filter is arithmetic on ledger fields.
    """
    drift_change = row.get("driftChangeDegPerDay")
    baseline = row.get("baselineDriftDegPerDay")
    after = None
    if drift_change is not None and baseline is not None:
        after = round(float(baseline) + float(drift_change), DRIFT_PLACES)
    vocabulary = row.get("vocabulary") or {}
    return {
        "alertId": row["alertId"],
        "norad": int(row["norad"]),
        "name": name,
        "class": row.get("class"),
        "className": row.get("className"),
        "text": row.get("text"),
        "labels": list(vocabulary.get("labels") or []),
        "permitted": list(vocabulary.get("permitted") or []),
        "underpowered": bool(vocabulary.get("underpowered")),
        "driftChangeDegPerDay": drift_change,
        "baselineDriftDegPerDay": baseline,
        # The drift the object is left with, which is what a forward path is
        # swept at. It is the lane's own two fields added, not a second fit.
        "driftAfterDegPerDay": after,
        "stages": row.get("stages"),
        "horizonDays": row.get("horizonDays"),
        "tTrigMs": row.get("tTrigMs"),
        "tAnnounceMs": row.get("tAnnounceMs"),
        "resolveByMs": row.get("resolveByMs"),
        "settingPoint": row.get("settingPoint"),
        "anchor": anchor,
        "resolution": {
            "state": (resolution or {}).get("state", (row.get("resolution") or {}).get("state")),
            "arrivalMs": (resolution or {}).get("arrivalMs"),
            "leadDays": (resolution or {}).get("leadDays"),
            "rule": (resolution or {}).get("rule"),
        },
        "modelVersion": row.get("modelVersion"),
        "modelChecksum": row.get("modelChecksum"),
    }


def _class_figures(assessments: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """The per-class figures every card prints, carried once instead of per row."""
    figures: dict[str, Any] = {}
    for row in assessments:
        cluster = row.get("class")
        if cluster is None or str(cluster) in figures or row.get("classSupport") is None:
            continue
        figures[str(cluster)] = {
            "className": row.get("className"),
            "support": row.get("classSupport"),
            "positives": row.get("classPositives"),
            "precision": row.get("classPrecision"),
            "wilson95": row.get("classWilson95"),
            "arrivalDays": row.get("classArrivalDays"),
            "populationN": row.get("populationN"),
            "populationPrecision": row.get("populationPrecision"),
            "populationWilson95": row.get("populationWilson95"),
        }
    return figures


def leo_arm(leo_model: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    """The low-orbit arm: a WITHHELD gate, with the number that withheld it.

    The arm ran. It assessed 5,327 changes over its window and raised none,
    because its own control fires on objects that cannot move themselves at
    0.797 of the rate it fires on ones that can, against a design target of
    0.001. That is a measured reason and it is published as one: `available` is
    false, `raised` is a real count of zero next to a real count of assessments,
    and the page prints the reason rather than an empty list.
    """
    entry = leo_model["classes"][0]
    audit = receipt["audit"]
    return {
        "available": False,
        "gate": "withheld",
        "modelVersion": leo_model["modelVersion"],
        "modelChecksum": leo_model["checksum"],
        "assessed": int(audit["assessments"]),
        "raised": int(audit["alertsRaised"]),
        "passiveControlRatio": entry["passiveControlRatio"],
        "passiveControlBar": entry["passiveControlBar"],
        "window": dict(receipt["window"]),
        "receipt": f"docs/{LEO_REPLAY_RECEIPT.name}",
        "caveats": list(leo_model["caveats"]),
    }


def alerts_artifact(
    model: dict[str, Any],
    ledger_path: Path,
    *,
    connection: sqlite3.Connection | None = None,
    replay_ledgers: dict[str, Path] | None = None,
    replay_receipt: Path = REPLAY_RECEIPT,
    leo_model_path: Path = LEO_MODEL,
    leo_receipt_path: Path = LEO_REPLAY_RECEIPT,
) -> dict[str, Any]:
    """Every spoken row there is to read, and what kind of record it came from.

    THREE STATES, AND THE ARTIFACT SAYS WHICH. A live ledger, if the lane is
    running; otherwise the lane's own REPLAY over the 2010s, published with
    `live` false and its window and receipt attached, so a page cannot render
    it as live without deleting a field; otherwise the labelled gap.

    Never a zero and never an empty list rendered as one.
    """
    base: dict[str, Any] = {
        "schema": SCHEMA,
        "modelVersion": model["modelVersion"],
        "modelChecksum": model["checksum"],
        "caveats": list(model["caveats"]),
    }
    if leo_model_path.is_file() and leo_receipt_path.is_file():
        base["leo"] = leo_arm(json.loads(leo_model_path.read_text()),
                              json.loads(leo_receipt_path.read_text()))

    if ledger_path.is_file():
        header, assessments, resolutions = _ledger_parts(ledger_path)
        spoken = [row for row in assessments if row.get("spoken") is True]
        base.update({
            "available": True,
            "live": True,
            "source": "lane",
            "gap": None,
            "listedSetting": header.get("setting"),
            "settings": {str(header.get("setting")): _setting_counts(assessments, resolutions)},
            "counts": _setting_counts(assessments, resolutions),
            "classFigures": _class_figures(assessments),
            "alerts": [_slim_alert(row, resolutions.get(row["alertId"]),
                                   alert_anchor(connection, int(row["norad"]), row["tTrigMs"])
                                   if connection is not None and row.get("tTrigMs") else None,
                                   None)
                       for row in spoken],
        })
        return base

    candidates = REPLAY_LEDGERS if replay_ledgers is None else replay_ledgers
    ledgers = {name: path for name, path in candidates.items() if path.is_file()}
    if not ledgers or not replay_receipt.is_file():
        base.update({
            "available": False,
            "live": False,
            "source": None,
            "gap": "lane-not-running",
            "gapSource": _repo_relative(ledger_path),
            "alerts": None,
            "counts": None,
        })
        return base

    receipt = json.loads(replay_receipt.read_text())
    settings: dict[str, Any] = {}
    by_setting: dict[str, list[dict[str, Any]]] = {}
    listed_figures: dict[str, Any] = {}
    listed_name = LISTED_SETTING if LISTED_SETTING in ledgers else sorted(ledgers)[0]
    # One archive read per (object, trigger), shared across the settings that
    # spoke the same change: 125 of the two ledgers' rows are the same alert.
    anchors: dict[tuple[int, int], dict[str, Any] | None] = {}
    for name in sorted(ledgers):
        _header, assessments, resolutions = _ledger_parts(ledgers[name])
        settings[name] = _setting_counts(assessments, resolutions)
        if name == listed_name:
            listed_figures = _class_figures(assessments)
        # EACH SETTING'S LIST IS ITS OWN LEDGER'S. The page does not re-derive
        # one setting's alerts from another's: which changes a setting speaks
        # is the lane's answer, not the reader's, and a setting the replay did
        # not exercise gets a labelled gap rather than a filtered guess.
        spoken = [row for row in assessments if row.get("spoken") is True]
        names = (object_names(connection, [int(row["norad"]) for row in spoken])
                 if connection is not None else {})
        rows: list[dict[str, Any]] = []
        for row in spoken:
            norad = int(row["norad"])
            key = (norad, int(row["tTrigMs"] or 0))
            if connection is not None and row.get("tTrigMs") and key not in anchors:
                anchors[key] = alert_anchor(connection, norad, row["tTrigMs"])
            rows.append(_slim_alert(row, resolutions.get(row["alertId"]),
                                    anchors.get(key), names.get(norad)))
        rows.sort(key=lambda entry: (-(entry["tTrigMs"] or 0), entry["alertId"]))
        by_setting[name] = rows
    listed = by_setting.get(listed_name, [])

    base.update({
        "available": True,
        # NOT LIVE, and the field says so before any prose does.
        "live": False,
        "source": "replay",
        "gap": None,
        "exercise": {
            "status": receipt["status"],
            "window": {"startIso": receipt["clock"]["start"], "endIso": receipt["clock"]["end"]},
            "mode": receipt["clock"]["mode"],
            "settings": list(receipt["settingsExercised"]),
            "wallSeconds": receipt["wallSeconds"],
            "executionMode": receipt["executionMode"],
            "inSampleNote": receipt["inSampleNote"],
            "receipt": f"docs/{replay_receipt.name}",
            "ledgers": {name: f"docs/{path.name}" for name, path in sorted(ledgers.items())},
        },
        "listedSetting": listed_name,
        "settings": settings,
        "counts": settings[listed_name],
        "classFigures": listed_figures,
        "alerts": listed,
        # The other settings the replay exercised, each with its own rows. A
        # setting that is on the dial and not in here has measured numbers and
        # no list, and the page says which.
        "alertsBySetting": {name: rows for name, rows in by_setting.items()
                            if name != listed_name},
    })
    return base


def settings_artifact(model: dict[str, Any], curve_path: Path = CURVE_PATH) -> dict[str, Any]:
    """The dial's stops, each with the three numbers the curve counted for it.

    THE PAGE COMPUTES NO PRECISION. Every figure a stop prints is copied out of
    the operating-point table here: the measured precision and its interval, the
    median warning, the alerts a year, and the share of the loosest setting's
    arrivals the stop keeps. A stop the table did not count does not appear.

    A STOP IS OFFERED ONLY IF ITS ROW CAN BE JUDGED. Two things take a stop off
    the dial, and both are the table's own: `underpowered` (fewer alerts than
    the bar a rate may be quoted at), and a gate the curve itself refused, whose
    reason travels with the row. A stop that is not offered is still listed,
    with its reason, because a control that silently loses a segment teaches a
    reader that the ones left are the only ones there are.
    """
    curve = json.loads(curve_path.read_text())
    bar = int(model["bars"]["minSupportForARate"])
    spoken_name = next(entry["name"] for entry in model["classes"]
                       if entry["name"] == "WIDE-CROSSING")
    points: list[dict[str, Any]] = []
    for setting in curve["namedSettings"]:
        rows = {entry["className"]: entry for entry in setting["classes"]}
        row = rows.get(spoken_name)
        if row is None:
            continue
        offered = bool(row["mayBeSpoken"]) and not row["underpowered"] and row["alerts"] >= bar
        reason = None
        if row["underpowered"] or row["alerts"] < bar:
            reason = "underpowered"
        elif not row["mayBeSpoken"]:
            reason = "gated"
        withheld = [{
            "className": entry["className"],
            "alerts": entry["alerts"],
            "gateReasons": list(entry["gateReasons"]),
        } for entry in setting["classes"]
            if entry["className"] != spoken_name and not entry["mayBeSpoken"]]
        points.append({
            "stop": setting["name"],
            "point": dict(setting["point"]),
            "className": row["className"],
            "class": row["class"],
            "support": row["alerts"],
            "positives": row["arrivals"],
            "precision": row["precision"],
            "wilson95": list(row["wilson95"]),
            "leadDays": {key: row["leadDays"][key] for key in ("p5", "p25", "p50", "p75", "p95")},
            "alertsPerYear": row["alertsPerYear2010s"],
            "recallProxy": row["recallProxy"],
            "recallProxyNumerator": row["recallProxyNumerator"],
            "recallProxyDenominator": row["recallProxyDenominator"],
            "underpowered": bool(row["underpowered"]),
            "mayBeSpoken": bool(row["mayBeSpoken"]),
            "gateReasons": list(row["gateReasons"]),
            "offered": offered,
            "notOfferedReason": reason,
            "withheldClasses": withheld,
            "source": "operating-points",
        })
    return {
        "schema": SCHEMA,
        "modelVersion": model["modelVersion"],
        "modelChecksum": model["checksum"],
        "curveVersion": curve["curveVersion"],
        "curveChecksum": curve["checksum"],
        # The stop the lane speaks unaided: the loosest evidence cell, where the
        # class gate is the only thing filtering. It is first on the dial and it
        # is the default, so a reader who touches nothing sees what the lane
        # would actually have said.
        "defaultStop": points[0]["stop"] if points else None,
        "points": points,
        "replayAvailable": True,
        "gap": None,
        "gapFields": [],
        "minSupportForARate": bar,
        "tickDays": curve["tickDays"],
        "axes": list(curve["axes"]),
    }


# ---------------------------------------------------------------------------
# Assembling the release
# ---------------------------------------------------------------------------
def object_names(connection: sqlite3.Connection, norads: Iterable[int]) -> dict[int, str]:
    wanted = sorted({int(value) for value in norads})
    found: dict[int, str] = {}
    for start in range(0, len(wanted), 500):
        chunk = wanted[start:start + 500]
        marks = ",".join("?" * len(chunk))
        for norad, name in connection.execute(
            f"SELECT norad, name FROM object WHERE norad IN ({marks})", chunk
        ):
            if name:
                found[int(norad)] = str(name)
    return found


def _iso(ms: float | int | None) -> str | None:
    if ms is None:
        return None
    moment = dt.datetime.fromtimestamp(int(ms) / 1000.0, tz=dt.timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


def archive_present(connection: sqlite3.Connection, *, clock_ms: int | None = None) -> int:
    """The archive's present moment: its newest element set the clock has reached.

    AN ELEMENT SET MAY CARRY AN EPOCH THAT HAS NOT HAPPENED. A general-perturbations
    set is a fit with a reference time, and a small number of them are issued ahead
    of the moment they are published: ten of the 68,089 objects in this archive held
    one on 2026-09-22, the furthest 2026-09-26. `MAX(max_epoch_ms)` over the rollup
    therefore named a moment in the future, every episode still open took that moment
    as its `updatedMs` by construction, and `recordToMs` is the largest of those -- so
    the ledger's header read "Record to 24 Sep 2026" on 22 Sep 2026. A record cannot
    run past the moment it was built, and a header that says it does is wrong about
    the one thing it exists to say.

    The present is the newest epoch the archive holds that the clock has already
    reached. The forward-dated sets are not dropped and not corrected: they stay in
    the archive and every window that spans them still reads them. They simply do not
    get to decide what "now" is.

    The clock is injectable, and a release that needs two runs to agree byte for byte
    over a moving archive passes `--now-ms` instead, which is what that flag is for.
    """
    clock = (int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
             if clock_ms is None else int(clock_ms))
    newest = connection.execute(
        "SELECT MAX(max_epoch_ms) FROM object_rollup WHERE max_epoch_ms <= ?", (clock,)
    ).fetchone()[0]
    # An archive whose every epoch is ahead of the clock would be a parse fault
    # upstream rather than a record; the clock is then the only honest answer, and
    # it keeps the bound this function exists to enforce.
    return int(newest) if newest is not None else clock


def build(
    connection: sqlite3.Connection,
    data_root: Path,
    write_artifact: Callable[[Path, str, Any], tuple[str, str]],
    *,
    generated_at: str,
    events_bundle: dict[str, Any],
    geo_record: Sequence[dict[str, Any]],
    leo_record: Sequence[dict[str, Any]],
    model: dict[str, Any],
    measured_error: dict[str, Any],
    ledger_path: Path = LEDGER_PATH,
    curve_path: Path = CURVE_PATH,
    replay_ledgers: dict[str, Path] | None = None,
    replay_receipt: Path = REPLAY_RECEIPT,
    event_limit: int | None = None,
    now_ms: int | None = None,
) -> dict[str, Any]:
    """Every artifact, and the manifest fragment that names them."""
    if now_ms is None:
        now_ms = archive_present(connection)
    acceleration = float(model["detector"]["lambdaDdotDegPerDay2"])
    stable = float(model["detector"]["lambdaStableDeg"])
    horizon = float(
        next(entry for entry in model["classes"] if entry["name"] == "WIDE-CROSSING")
        ["arrivalDays"]["p95"]
    )

    registered_geo = [row for row in geo_record
                      if row.get("approacherClass") == "active" and row.get("attribution") == "resolved"]
    registered_leo = [row for row in leo_record if row.get("armM")]
    headline = list(events_bundle["events"])
    belt_bundle = belt(connection, now_ms=now_ms,
                       drift_floor=float(model["detector"]["slotDriftFloorDegPerDay"]))


    # -- the episodes ------------------------------------------------------
    # THE LEDGER'S ROWS. The steps above are what the instruments produce; an
    # episode is what a reader is shown, and the tracker is the one function
    # that turns the former into the latter. It is pure and `now_ms` is
    # injected, so the replay and the live product are the same code, and this
    # call is the live one.
    #
    # `sustained` is not passed, because no continuous-thrust verdict reaches
    # this bundle yet. That is a labelled gap on the page -- continuous
    # episodes are simply not opened -- and not a claim that none exist.
    episode_rows = orbit_episodes.episodes(
        now_ms=now_ms,
        catalogue_events=headline,
        geo_record=registered_geo,
        leo_record=registered_leo,
        elements=lambda norad, low, high: element_window(connection, norad, low, high),
        newest_epoch=lambda norad: _newest_epoch(connection, norad),
        class_figures=next(entry for entry in model["classes"] if entry["name"] == "WIDE-CROSSING"),
    )
    # Which episode a step belongs to, so the step's row can name it and the
    # step's series file can carry the whole record it is part of.
    episode_for_step: dict[str, dict[str, Any]] = {}
    for episode in episode_rows:
        for member in episode.get("steps", ()):
            key = member["key"] if isinstance(member, dict) else member
            episode_for_step[key] = episode

    rows: list[dict[str, Any]] = []
    event_files: list[dict[str, Any]] = []
    written = 0

    def publish_event(prefix: str, payload: dict[str, Any]) -> str | None:
        nonlocal written
        if event_limit is not None and written >= event_limit:
            return None
        path, digest = write_artifact(data_root, prefix, payload)
        event_files.append({"key": payload["key"], "path": path, "sha256": digest})
        written += 1
        return path

    # -- the belt record ----------------------------------------------------
    for record in registered_geo:
        norad = int(record["approacherNorad"])
        partner = int(record["targetNorad"])
        start_ms = int(record["transferStartMs"])
        key = f"geo|{norad}|{record['arrivalIso']}"
        series = slot_series(connection, norad, start_ms)
        partner_series = slot_series(connection, partner, start_ms)
        drift_after = record.get("transferDriftDegPerDay")
        anchor = series_value_at(series, SERIES_WINDOW_DAYS)
        payload = {
            "schema": SCHEMA,
            "key": key,
            "episode": episode_for_step.get(key),
            "family": "geoColocation",
            "regime": "GEO",
            "norad": norad,
            "name": record.get("approacherName"),
            "partnerNorad": partner,
            "partnerName": record.get("targetName"),
            "eventMs": start_ms,
            "arrivalMs": int(record["arrivalMs"]),
            "loiterEndMs": int(record["loiterEndMs"]) if record.get("loiterEndMs") else None,
            "departureMs": int(record["departureMs"]) if record.get("departureMs") else None,
            "series": series,
            "partnerSeries": partner_series,
            "facts": {
                "transferDriftDegPerDay": drift_after,
                "departureDriftDegPerDay": record.get("departureDriftDegPerDay"),
                "loiterLongitudeDeg": record.get("loiterLongitudeDeg"),
                "loiterDays": record.get("loiterDays"),
                "medianSeparationDeg": record.get("medianSeparationDeg"),
                "leadCausalDays": record.get("leadCausalDays"),
                "initiatingDriftChangeDegPerDay": record.get("initiatingDriftChangeDegPerDay"),
            },
            "measuredError": measured_error,
            "frozenRecord": f"docs/{GEO_RECORD.name}",
        }
        if anchor is not None and drift_after is not None:
            membership = float(measured_error.get("membershipHorizonDays", horizon))
            band_horizon = float(measured_error.get("unfitHorizonDays", horizon))
            payload["forward"] = {
                "anchor": "event",
                "fromMs": (series["startMs"] + anchor[0] * DAY_MS),
                "stepDays": FORWARD_STEP_DAYS,
                # THE PATH STOPS WHERE MEMBERSHIP IS RESOLVABLE. Beyond +20 d
                # the measured band is wider than the belt's own slot spacing,
                # so a line drawn onward reads as a reach the geometry does not
                # support.
                "horizonDays": membership,
                "values": forward_path(anchor[1], float(drift_after), membership,
                                       acceleration=acceleration, stable_deg=stable),
                # The band's centres continue to the last horizon that was
                # measured. They are NOT a path and the section does not draw
                # them as one: they place a ribbon whose whole point is that it
                # grows past the objects it is drawn among.
                "bandHorizonDays": band_horizon,
                "bandCentres": forward_path(anchor[1], float(drift_after), band_horizon,
                                            acceleration=acceleration, stable_deg=stable),
                "classArrivalP95Days": horizon,
                "accelerationDegPerDay2": acceleration,
                "stableLongitudeDeg": stable,
            }
        path = publish_event(f"orbit-changes-event-{norad}-{_slug(record['arrivalIso'])}", payload)
        closing = int(record.get("departureMs") or record.get("loiterEndMs") or record["arrivalMs"])
        rows.append({
            "key": key,
            "episodeId": key,
            **episode_bounds(connection, norad, start_ms, closing, now_ms=now_ms),
            "family": "geoColocation",
            "norad": norad,
            "name": record.get("approacherName"),
            "regime": "GEO",
            "startMs": start_ms,
            "endMs": int(record["arrivalMs"]),
            "signature": "slot-co-location",
            "changeValue": drift_after,
            "changeUnit": "degPerDay",
            "partnerNorad": partner,
            "partnerName": record.get("targetName"),
            "confidence": "candidate",
            "event": path,
        })

    # -- the phasing campaigns ---------------------------------------------
    for record in registered_leo:
        norad = int(record["approacher"])
        partner = int(record["target"])
        start_ms = int(record["campaignStartMs"])
        key = f"leo|{norad}|{_iso(record['arrivalMs'])}"
        payload = {
            "schema": SCHEMA,
            "key": key,
            "episode": episode_for_step.get(key),
            "family": "leoStation",
            "regime": "LEO",
            "norad": norad,
            "name": record.get("approacherName"),
            "partnerNorad": partner,
            "partnerName": record.get("targetName"),
            "eventMs": start_ms,
            "arrivalMs": int(record["arrivalMs"]),
            "endMs": int(record["endMs"]),
            "phase": phase_series(connection, norad, partner, start_ms),
            "elements": element_panels(connection, norad, start_ms),
            "facts": {
                "dwellDays": record.get("dwellDays"),
                "campaignDays": record.get("campaignDays"),
                "medianPhaseDeg": record.get("medianGammaDeg"),
                "closestPhaseDeg": record.get("closestGammaDeg"),
                "phaseRateMaxDegPerDay": record.get("phaseRateMaxDegPerDay"),
                "phaseRateFinalDegPerDay": record.get("phaseRateFinalDegPerDay"),
                "leadCausalDays": record.get("leadCausalDays"),
                "meanSemiMajorAxisKm": record.get("meanAKm"),
            },
            "frozenRecord": f"docs/{LEO_RECORD.name}",
        }
        path = publish_event(f"orbit-changes-event-{norad}-{_slug(_iso(record['arrivalMs']))}", payload)
        rows.append({
            "key": key,
            "episodeId": key,
            **episode_bounds(connection, norad, start_ms, int(record["endMs"]), now_ms=now_ms),
            "family": "leoStation",
            "norad": norad,
            "name": record.get("approacherName"),
            "regime": "LEO",
            "startMs": start_ms,
            "endMs": int(record["arrivalMs"]),
            "signature": "in-track-phasing",
            "changeValue": record.get("closestGammaDeg"),
            "changeUnit": "deg",
            "partnerNorad": partner,
            "partnerName": record.get("targetName"),
            "confidence": "candidate",
            "event": path,
        })

    # -- the catalogued changes --------------------------------------------
    belt_regimes = {"GEO", "near-GEO"}
    for record in headline:
        norad = int(record["norad"])
        start_ms = int(dt.datetime.strptime(record["startAt"], "%Y-%m-%dT%H:%M:%SZ")
                       .replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
        end_ms = int(dt.datetime.strptime(record["endAt"], "%Y-%m-%dT%H:%M:%SZ")
                     .replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
        change = element_change(connection, norad, start_ms, end_ms)
        path = None
        if record["regime"] in belt_regimes:
            payload = {
                "schema": SCHEMA,
                "key": record["eventKey"],
                "episode": episode_for_step.get(record["eventKey"]),
                "family": "catalogue",
                "regime": record["regime"],
                "norad": norad,
                "name": record.get("name"),
                "partnerNorad": None,
                "partnerName": None,
                "eventMs": start_ms,
                "arrivalMs": None,
                "series": slot_series(connection, norad, start_ms),
                "facts": {
                    "signature": record["signature"],
                    "signatureLabel": record["signatureLabel"],
                    "spanDays": record.get("spanDays"),
                    "expectationVerdict": record.get("expectationVerdict"),
                    "controlBasis": record.get("controlBasis"),
                    **change,
                },
                "measuredError": measured_error,
                "frozenRecord": "manifest.orbitEvents",
            }
            path = publish_event(f"orbit-changes-event-{norad}-{_slug(record['startAt'])}", payload)
        size, unit = _catalogue_size(record["signature"], change)
        rows.append({
            "key": record["eventKey"],
            "episodeId": record["eventKey"],
            **episode_bounds(connection, norad, start_ms, end_ms, now_ms=now_ms),
            "family": "catalogue",
            "norad": norad,
            "name": record.get("name"),
            "regime": record["regime"],
            "startMs": start_ms,
            "endMs": end_ms,
            "signature": record["signature"],
            "signatureLabel": record["signatureLabel"],
            "changeValue": size,
            "changeUnit": unit,
            "partnerNorad": None,
            "partnerName": None,
            "confidence": record.get("confidence", "candidate"),
            "event": path,
        })

    # A STEP THAT OPENED NO EPISODE KEEPS ITS PLACE AND ITS NULL.
    # Routine keeping is registered as something that must never open one, and
    # a sustained fall is what drag does, so both are detected steps with no
    # episode above them. Giving such a step its own key as an episode id would
    # invent a row; dropping it would lose a measurement. It gets `null`, and
    # the index counts them so the section can say how many there are.
    # A REGISTERED FAMILY'S EPISODE IS ITS OWN STEP, and the two carry the same
    # key by construction: a co-location or a phasing campaign is not a chain
    # of catalogued steps, it is one recorded thing, and the tracker lists no
    # members for it. So a step whose key IS an episode key belongs to it.
    episode_keys = {record["key"] for record in episode_rows}
    for step in rows:
        episode = episode_for_step.get(step["key"])
        if episode is None and step["key"] in episode_keys:
            step["episodeId"] = step["key"]
            continue
        step["episodeId"] = episode["key"] if episode else None
    rows.sort(key=lambda entry: (-entry["startMs"], entry["key"]))

    index = {
        "schema": SCHEMA,
        "generatedAt": generated_at,
        "modelVersion": model["modelVersion"],
        "modelChecksum": model["checksum"],
        "trackerVersion": (episode_rows[0]["versions"]["trackerVersion"] if episode_rows
                           else orbit_episodes.TRACKER_VERSION),
        "recordToMs": max((int(row["updatedMs"]) for row in episode_rows), default=None),
        # The state rates themselves -- how often a change that opens goes on to
        # settle, lapse or re-open -- have not been counted. M8 is owed, and
        # until it lands the page says so rather than implying the states are
        # as reliable as the elements behind them.
        "stateRatesMeasured": False,
        # Detected steps that opened no episode: routine keeping, which is
        # registered as something that must never open one, and sustained falls,
        # which are what drag does. Counted rather than dropped.
        "stepsWithoutEpisode": sum(1 for step in rows if step["episodeId"] is None),
        "manoeuvreLabelPermitted": events_bundle["labelPolicy"]["manoeuvreLabelPermitted"],
        "families": {
            "catalogue": {
                "rows": sum(1 for row in rows if row["family"] == "catalogue"),
                "frozen": False,
                "source": "manifest.orbitEvents",
                "generatedAt": events_bundle["generatedAt"],
            },
            "geoColocation": {
                "rows": len(registered_geo),
                "frozen": True,
                "source": f"docs/{GEO_RECORD.name}",
                "archiveToMs": max((int(row["arrivalMs"]) for row in registered_geo), default=None),
            },
            "leoStation": {
                "rows": len(registered_leo),
                "frozen": True,
                "source": f"docs/{LEO_RECORD.name}",
                "archiveToMs": max((int(row["arrivalMs"]) for row in registered_leo), default=None),
            },
        },
        "measuredError": measured_error,
        # The measured error growth for a LOW-ORBIT forward path, once rather
        # than in every one of the low-orbit series files. It is here so that
        # nothing re-derives it; the ribbon that draws it is not built yet, and
        # until it is, a low-orbit object page shows the phase record with no
        # forward band at all rather than one drawn from the element noise,
        # which T16b measured to be several times too wide in the days after a
        # change and several times too narrow three months out.
        "leoMeasuredError": low_orbit_error(json.loads(TRUTHSET_GROWTH.read_text())),
        "rows": [_ledger_row(record) for record in episode_rows],
        # THE STEPS, SLIM. What a step's own row carried -- its confidence, its
        # regime, its partner, its object's name -- is on the episode above it
        # and does not need saying twice; the full step record travels in the
        # series file. What stays is what the object page draws in the step
        # list and the path to the series behind it.
        "changes": [{
            "key": step["key"],
            "episodeId": step["episodeId"],
            "family": step["family"],
            "startMs": step["startMs"],
            "signature": step["signature"],
            "signatureLabel": step.get("signatureLabel"),
            "changeValue": step["changeValue"],
            "changeUnit": step["changeUnit"],
            "event": step["event"],
        } for step in rows],
        "versions": (episode_rows[0]["versions"] if episode_rows else {}),
    }

    index_path, index_digest = write_artifact(data_root, "orbit-changes-index", index)
    belt_path, belt_digest = write_artifact(data_root, "geo-belt", belt_bundle)
    alerts = alerts_artifact(model, ledger_path, connection=connection,
                             replay_ledgers=replay_ledgers, replay_receipt=replay_receipt)
    # The forward error travels with the alerts too, because the reachable set
    # is swept to the horizon the error measured and the Reach view may not be
    # made to fetch the whole index to learn what that horizon is.
    alerts["measuredError"] = measured_error
    alerts_path, alerts_digest = write_artifact(data_root, "orbit-alerts", alerts)
    settings = settings_artifact(model, curve_path)
    settings_path, settings_digest = write_artifact(data_root, "orbit-alert-settings", settings)

    return {
        "generatedAt": generated_at,
        "schema": SCHEMA,
        "modelVersion": model["modelVersion"],
        "trackerVersion": index["trackerVersion"],
        "index": {"path": index_path, "sha256": index_digest,
                  "rows": len(episode_rows), "changes": len(rows)},
        "belt": {"path": belt_path, "sha256": belt_digest, "objects": belt_bundle["objects"]},
        "alerts": {"path": alerts_path, "sha256": alerts_digest,
                   "available": alerts["available"], "live": alerts.get("live", False),
                   "source": alerts.get("source"), "gap": alerts["gap"],
                   "raised": (alerts.get("counts") or {}).get("raised")},
        "settings": {"path": settings_path, "sha256": settings_digest,
                     "points": len(settings["points"]), "gap": settings["gap"],
                     "offered": sum(1 for point in settings["points"] if point["offered"])},
        "events": event_files,
    }


def _row_state(state: dict[str, Any] | None) -> dict[str, Any] | None:
    """The part of an element state the ledger's delta line draws.

    The baseline's own scatter, its window and its eccentricity are part of the
    episode and travel in its series file. They are not on the row, because the
    row draws four numbers and carrying the other four cost 30 KB gz across
    1,992 episodes.
    """
    if not state:
        return None
    # No `epochMs`: the row already carries `onsetMs`, `updatedMs` and
    # `completedMs`, and a fourth timestamp per side cost 10 KB gz of an index
    # that is 1 KB over its budget without it.
    kept = ("semiMajorAxisKm", "inclinationDeg", "lambdaDeg", "driftDegPerDay")
    return {key: state[key] for key in kept if key in state and state[key] is not None}


def _ledger_row(record: dict[str, Any]) -> dict[str, Any]:
    """The slim row the ledger draws, from the full episode record.

    THE INDEX IS A LIST, NOT AN ARCHIVE. The full record -- its trend, its
    history, its reading with every clause's provenance, its versions -- is
    twelve times the size of what a row shows, and shipping all of it made the
    index 477 KB gz against a 250 KB budget. The row carries what is drawn and
    the key to fetch the rest, which is the same split the orbit history made
    when a year of evidence cards stopped fitting on a front page.

    `verdict` is the routine check's answer, and today it is unmeasured for
    every episode. It is on the row rather than only in the reading because the
    ledger filters on it, and a filter that has to fetch 1,992 files to run is
    not a filter.
    """
    reading = record.get("reading") or {}
    routine = reading.get("r2") or {}
    slots = routine.get("slots") or {}
    verdict = ("routine" if routine.get("filled") and "patternLabel" in slots
               else "notRoutine" if routine.get("filled") else "unmeasured")
    return {
        "key": record["key"],
        "norad": record["norad"],
        "name": record.get("name"),
        "regime": record["regime"],
        "kind": record["kind"],
        "state": record["state"],
        "closure": record["closure"],
        "reopened": record.get("reopened", 0),
        "stage": record.get("stage", "none"),
        "onsetMs": record.get("onsetMs"),
        "updatedMs": record["updatedMs"],
        "completedMs": record.get("completedMs"),
        "initial": _row_state(record.get("initial")),
        "current": _row_state(record.get("current")),
        "type": ((reading.get("r1") or {}).get("slots") or {}).get("typeLabel"),
        "verdict": verdict,
        "reading": None,
        # The member steps are NOT listed here. The episode's own key is on
        # every step in `changes`, so the object page joins the two, and the
        # keys are long enough that carrying them twice cost 24 KB gz of an
        # index with a 250 KB budget.
        "steps": None,
        "partnerNorad": record.get("partnerNorad"),
        "partnerName": record.get("partnerName"),
    }


def _catalogue_size(signature: str, change: dict[str, Any]) -> tuple[float | None, str | None]:
    """The one number that names a catalogued change, chosen by what moved."""
    if not change:
        return None, None
    if signature in ("inclination-change", "node-change"):
        return change["inclinationDeg"], "deg"
    if signature.startswith("geo-"):
        return change["driftDegPerDay"], "degPerDay"
    return change["semiMajorAxisKm"], "km"


def write_fragment(fragment: dict[str, Any], *, path: Path = FRAGMENT_PATH) -> None:
    """Record the fragment atomically, for the same reason the orbit release does.

    The five-minute publish cycle reads this while the build may be writing it,
    and a half-written file would drop the section for a cycle for no reason.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps({"generatedAt": fragment["generatedAt"], "manifest": {MANIFEST_KEY: fragment}},
                   indent=1, sort_keys=True)
    )
    temporary.replace(path)


def _record_paths(record: dict[str, Any]) -> list[str]:
    """Every artifact path a fragment record names, at any depth it uses."""
    paths: list[str] = []
    for key in ("index", "belt", "alerts", "settings"):
        entry = record.get(key)
        if isinstance(entry, dict) and isinstance(entry.get("path"), str):
            paths.append(entry["path"])
    for entry in record.get("events", []) or []:
        if isinstance(entry, dict) and isinstance(entry.get("path"), str):
            paths.append(entry["path"])
    return paths


def usable_record(data_root: Path, record: Any) -> dict[str, Any] | None:
    """A record only counts if every file it names is still on disk.

    The shared reader in `orbit_release` understands a single `path` record and
    a list of shards, and this one is neither: four named artifacts plus a list
    of per-change files. A fragment naming a file the pruner has since removed
    would put a 404 in a visitor's browser rather than an error in the pipeline,
    which is the failure this project has learned to fear most, so the check
    lives with the shape that needs it.
    """
    if not isinstance(record, dict):
        return None
    paths = _record_paths(record)
    if not paths or len(paths) < 4:
        return None
    if any(not (data_root / relative).is_file() for relative in paths):
        return None
    return record


def publish(data_root: Path, *, fragment_path: Path | None = None) -> dict[str, Any]:
    """The manifest record for this section, read from the offline build.

    **This function does not touch the archive.** It is called inside the
    five-minute publish cycle, and everything expensive already happened in
    `build`. Like the orbit release it names, it degrades to whatever the
    previous manifest named rather than dropping the key: a section that
    disappears for a cycle is worse than one that is a few hours old, and the
    artifacts are content-addressed, so an old name is still an honest one.
    """
    # Resolved at the call rather than bound to the signature, so that a caller
    # which repoints the module constant -- a check running against a scratch
    # data root, so that it cannot reach a live publish cycle -- gets the path
    # it set rather than the one that existed when this file was imported.
    path = fragment_path or FRAGMENT_PATH
    try:
        payload = json.loads(path.read_text())
        record = usable_record(data_root, payload.get("manifest", {}).get(MANIFEST_KEY))
    except (OSError, json.JSONDecodeError, AttributeError):
        record = None
    if record is None:
        try:
            manifest = json.loads((data_root / "manifest.json").read_text())
        except (OSError, json.JSONDecodeError):
            return {}
        record = usable_record(data_root, manifest.get(MANIFEST_KEY))
    return {MANIFEST_KEY: record} if record is not None else {}


def resolve_events_bundle(data_root: Path, override: Path | None) -> dict[str, Any]:
    if override is not None:
        return json.loads(override.read_text())
    manifest = json.loads((data_root / "manifest.json").read_text())
    record = manifest.get("orbitEvents")
    if not isinstance(record, dict) or "path" not in record:
        raise SystemExit("the manifest names no event bundle to read")
    return json.loads((data_root / record["path"]).read_text())


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT / "public" / "data")
    parser.add_argument("--archive", type=Path, default=None)
    parser.add_argument("--events-bundle", type=Path, default=None)
    parser.add_argument("--generated-at", default=None,
                        help="fix the timestamp; the default is the event bundle's own, which "
                             "is what makes two runs over the same inputs byte-identical")
    parser.add_argument("--event-limit", type=int, default=None,
                        help="stop after this many event files; for measuring, not for a release")
    parser.add_argument("--now-ms", type=int, default=None,
                        help="fix the belt's present moment; the default is the archive's newest "
                             "element set THAT THE CLOCK HAS REACHED, which is what a release "
                             "wants and what makes a byte-stability check over a moving archive "
                             "need this flag")
    parser.add_argument("--build", action="store_true", help="write the artifacts and the fragment")
    args = parser.parse_args(argv)

    connection = open_readonly(args.archive or archive_db_path())
    events_bundle = resolve_events_bundle(args.data_root, args.events_bundle)
    model = json.loads(FROZEN_MODEL.read_text())
    measured_error = forward_error(json.loads(KINEMATIC_INPUTS.read_text()))

    from pipeline.build_release import write_artifact

    fragment = build(
        connection,
        args.data_root,
        write_artifact,
        generated_at=args.generated_at or events_bundle["generatedAt"],
        events_bundle=events_bundle,
        geo_record=read_jsonl(GEO_RECORD),
        leo_record=read_jsonl(LEO_RECORD),
        model=model,
        measured_error=measured_error,
        event_limit=args.event_limit,
        now_ms=args.now_ms,
    )
    connection.close()

    if args.build:
        write_fragment(fragment)
    print(json.dumps({key: value for key, value in fragment.items() if key != "events"}, indent=1))
    print(f"event files: {len(fragment['events'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
