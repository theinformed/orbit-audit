#!/usr/bin/env python3
"""T18 data instrument: element-set histories turned into causal sequences,
and the leakage-proof split that decides which object may be seen where.

Registered in `docs/t18-preregistration-20260922.md`, committed alone at
2618343 before this file existed. Every constant below is that document's,
and a constant that drifts from it is a defect, not a tuning choice.

Three channel groups (registration 2.1):

  A  the physics residual -- set `i` propagated by SGP4 to `epoch_{i+1}` and
     differenced against set `i+1` at its own epoch, as six osculating-element
     deltas and three RTN position components. This is the TARGET.
  B  fit covariates: B*, ndot and the epoch-to-ingest latency.
  C  TIMING ONLY: the step spacing, its rolling median and scatter, the fit
     latency and the step's index inside its geometry window. Nothing about
     where the object is or what it did.

The cadence-only artefact floor reads group C and predicts group A. The full
model reads A, B and C. Same depth, same width, same heads -- a floor measured
with a different architecture would not be a floor.

The split is a pure function of (the registered rule, the seed, the `object`
table, the census). It is built once, checksummed, and never regenerated.

Usage:
  t18_data.py split   --out docs/t18-split-20260922.json
  t18_data.py extract --partition train --limit 2000 --out <dir>
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
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

# Installation-specific locations. Each is named by an environment variable
# and falls back to a placeholder that cannot resolve, so an unconfigured
# checkout fails with the name of the variable it needs instead of reading
# whatever happens to sit at somebody else's path.
ARCHIVE = Path(os.environ.get("ORBIT_ARCHIVE_DB",
                              "element-archive.not-configured.sqlite3"))
RUNG2_CLASSES = REPO / "docs" / "matched-filter-rung2-classes-20260922.json"

# --------------------------------------------------------------------------
# Registered constants (t18-preregistration-20260922.md)
# --------------------------------------------------------------------------
SEED = 20260922
SPLIT_SALT = "t18-20260922"
T_CUT_MS = 1704067200000              # 2024-01-01T00:00:00Z, registration 2.3

MIN_ELEMENT_SETS = 512                # registration 2.2
MIN_SPAN_DAYS = 720.0
MAX_SETS_PER_OBJECT = 4096
TRAIN_OBJECT_CAP = 2000
VALIDATION_OBJECT_CAP = 500
PASSIVE_OBJECT_CAP = 1000

BUCKETS = 10000
TRAIN_BUCKET_MAX = 6000               # [0, 6000)
VALIDATION_BUCKET_MAX = 8000          # [6000, 8000); test is [8000, 10000)

# registration 2.3: the split unit is the constellation group where catalogued
CONSTELLATION_PREFIXES = ("STARLINK-", "ONEWEB-", "IRIDIUM", "GLOBALSTAR",
                          "ORBCOMM", "PLANET", "FLOCK", "SPIRE", "LEMUR")
INCLINATION_GROUP_DEG = 0.5
RAAN_GROUP_DEG = 15.0

# registration 2.3: assigned to TEST by construction, whatever their hash.
# The eleven geodetic and altimetry spacecraft the truth set labels.
TRUTH_NORADS = {
    36508: "cryosat-2", 37781: "hy-2a", 26997: "jason-1", 33105: "jason-2",
    41240: "jason-3", 39086: "saral", 41335: "sentinel-3a",
    43437: "sentinel-3b", 46984: "sentinel-6a", 54754: "swot",
    22076: "topex-poseidon",
}

# archive quantisation (pipeline/orbit_history.py)
SCALE_MEAN_MOTION = 1e8
SCALE_ECCENTRICITY = 1e8
SCALE_ANGLE = 1e4
SCALE_BSTAR = 1e12
SCALE_NDOT = 1e8
SCALE_NDDOT = 1e13

DAY_MS = 86400000.0
MU_KM3_S2 = 398600.4418
TARGET_CHANNELS = ("dA_km", "dE", "dI_deg", "dRAAN_deg", "dARGP_deg",
                   "dM_deg", "dRadial_km", "dAlongTrack_km", "dCrossTrack_km")
CADENCE_CHANNELS = ("logDtDays", "rollingMedianLogDt", "rollingMadLogDt",
                    "log1pLatencyHours", "windowPositionFraction")
FIT_CHANNELS = ("bstar", "ndot", "log1pLatencyHours")
ROLLING_STEPS = 10


class SplitLeak(Exception):
    """Raised when a split violates a registered disjointness condition.

    These are not warnings. A leak that is logged and carried on with is a
    leak, so every validator here raises and the tests assert the raise on a
    case built to contain the bug.
    """


# --------------------------------------------------------------------------
# The split (registration 2.3)
# --------------------------------------------------------------------------
def constellation_prefix(name: str | None) -> str | None:
    if not name:
        return None
    upper = name.strip().upper()
    for prefix in CONSTELLATION_PREFIXES:
        if upper.startswith(prefix):
            return prefix
    return None


def split_unit(norad: int, name: str | None, inclination_deg: float | None,
               raan_deg: float | None) -> str:
    """The unit that moves between partitions as a whole.

    A Starlink sibling in the same plane shares a bus, an operations schedule
    and therefore effectively the object's own future, so object-level holdout
    is not holdout at all for them (design 2.4). The constellation name reaches
    the model HERE AND NOWHERE ELSE: it decides a partition and enters no input
    tensor, no grouping of any score and no output column (registration 2.1).
    """
    prefix = constellation_prefix(name)
    if prefix is None or inclination_deg is None or raan_deg is None:
        return f"norad:{int(norad)}"
    inc_bin = round(float(inclination_deg) / INCLINATION_GROUP_DEG)
    raan_bin = math.floor((float(raan_deg) % 360.0) / RAAN_GROUP_DEG)
    return f"group:{prefix}|{inc_bin}|{raan_bin}"


def split_bucket(unit: str) -> int:
    digest = hashlib.sha256(f"{SPLIT_SALT}:{unit}".encode()).hexdigest()
    return int(digest[:8], 16) % BUCKETS


def partition_of_bucket(bucket: int) -> str:
    if bucket < TRAIN_BUCKET_MAX:
        return "train"
    if bucket < VALIDATION_BUCKET_MAX:
        return "validation"
    return "test"


def partition_of(norad: int, unit: str) -> str:
    if int(norad) in TRUTH_NORADS:
        return "test"
    return partition_of_bucket(split_bucket(unit))


def validate_split(assignment: dict) -> None:
    """Every registered disjointness condition, each one raising.

    `assignment` maps `str(norad) -> {"unit", "partition", ...}`.
    """
    seen: dict[int, str] = {}
    unit_partition: dict[str, str] = {}
    for key, row in assignment.items():
        norad = int(key)
        partition = row["partition"]
        if partition not in ("train", "validation", "test"):
            raise SplitLeak(f"object {norad} carries an unknown partition {partition!r}")
        if norad in seen and seen[norad] != partition:
            raise SplitLeak(
                f"object {norad} appears in two partitions: "
                f"{seen[norad]} and {partition}")
        seen[norad] = partition
        unit = row["unit"]
        if unit in unit_partition and unit_partition[unit] != partition:
            raise SplitLeak(
                f"split unit {unit!r} spans two partitions: "
                f"{unit_partition[unit]} and {partition} (object {norad})")
        unit_partition[unit] = partition
    for norad in TRUTH_NORADS:
        row = assignment.get(str(norad))
        if row is not None and row["partition"] != "test":
            raise SplitLeak(
                f"truth spacecraft {norad} ({TRUTH_NORADS[norad]}) is in "
                f"{row['partition']}, not test")


def validate_no_future(partition: str, epoch_ms) -> None:
    """A training or validation sequence may not contain an epoch at or after
    `T_cut` (registration 2.3). The test partition may.
    """
    if partition == "test":
        return
    epochs = np.asarray(epoch_ms, dtype=np.int64)
    if epochs.size and int(epochs.max()) >= T_CUT_MS:
        offenders = int(np.count_nonzero(epochs >= T_CUT_MS))
        raise SplitLeak(
            f"{partition} sequence carries {offenders} element set(s) at or "
            f"after T_cut={T_CUT_MS}; the model may not see the test era")


def validate_pairwise(assignment_a: dict, assignment_b: dict,
                      name_a: str, name_b: str) -> None:
    """Two partitions built separately must share no object and no unit."""
    objects = set(assignment_a) & set(assignment_b)
    if objects:
        raise SplitLeak(
            f"{name_a} and {name_b} share {len(objects)} object(s), "
            f"first {sorted(objects)[:5]}")
    units_a = {row["unit"] for row in assignment_a.values()}
    units_b = {row["unit"] for row in assignment_b.values()}
    shared = units_a & units_b
    if shared:
        raise SplitLeak(
            f"{name_a} and {name_b} share {len(shared)} split unit(s), "
            f"first {sorted(shared)[:3]}")


def split_checksum(assignment: dict) -> str:
    """A checksum over the assignment alone, independent of dict ordering and
    of any timestamp, so two independent constructions are comparable."""
    payload = json.dumps(
        {k: [assignment[k]["unit"], assignment[k]["partition"]]
         for k in sorted(assignment, key=int)},
        separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


# --------------------------------------------------------------------------
# The sampling-geometry class, reused verbatim (registration 2.4)
# --------------------------------------------------------------------------
class Rung2Classes:
    """The committed 60-class assignment, applied -- never refitted.

    Refitting the cut points on T18's split would fit class definitions on test
    objects. The `edges` block and the `classes` map are read from the
    committed artifact and the merge ladder is walked exactly as it was built.
    """

    LADDER = ("g1g2g3g4", "g1g2g3", "g1g2", "g1")

    def __init__(self, edges: dict, classes: dict, source: str):
        self.edges = {k: list(v) for k, v in edges.items()}
        self.classes = set(classes)
        self.source = source

    @classmethod
    def load(cls, path: Path = RUNG2_CLASSES) -> "Rung2Classes":
        blob = json.loads(Path(path).read_text())
        return cls(blob["edges"], blob["classes"], str(path))

    @staticmethod
    def features(times_days: np.ndarray) -> dict[str, float] | None:
        """g1..g4 exactly as the Rung-2 pre-registration defines them."""
        t = np.asarray(times_days, dtype=np.float64)
        if t.size < 2:
            return None
        gaps = np.diff(t)
        if not np.all(gaps > 0):
            order = np.argsort(t, kind="stable")
            t = t[order]
            gaps = np.diff(t)
        median_gap = float(np.median(gaps))
        if not (median_gap > 0.0):
            return None
        span = float(t[-1] - t[0])
        if span <= 0.0:
            return None
        burdened = gaps[gaps > 3.0 * median_gap]
        return {
            "g1": math.log2(median_gap),
            "g2": math.log2(float(t.size)),
            "g3": float(gaps.max()),
            "g4": float(burdened.sum()) / span,
        }

    def _bin(self, key: str, value: float) -> int:
        edges = self.edges[key]
        index = 0
        for edge in edges:
            if value >= edge:
                index += 1
        return index

    def classify(self, times_days: np.ndarray) -> str | None:
        """The class key, or None when the window abstains.

        An abstaining window is counted and attributed and NEVER folded into a
        rate -- the discipline of matched-filter-rung2-results 2.2.
        """
        feats = self.features(times_days)
        if feats is None:
            return None
        bins = {k: self._bin(k, feats[k]) for k in ("g1", "g2", "g3", "g4")}
        candidates = (
            f"g1g2g3g4:{bins['g1']}-{bins['g2']}-{bins['g3']}-{bins['g4']}",
            f"g1g2g3:{bins['g1']}-{bins['g2']}-{bins['g3']}",
            f"g1g2:{bins['g1']}-{bins['g2']}",
            f"g1:{bins['g1']}",
        )
        for key in candidates:
            if key in self.classes:
                return key
        return None


# --------------------------------------------------------------------------
# Geometry windows (registration 2.4; cadence_core, unchanged)
# --------------------------------------------------------------------------
GEOMETRY_WINDOW_DAYS = 1080.0
GEOMETRY_STEP_DAYS = 360.0


def geometry_windows(times_days: np.ndarray) -> list[tuple[float, float]]:
    t = np.asarray(times_days, dtype=np.float64)
    if t.size == 0:
        return []
    span = float(t[-1] - t[0])
    out = []
    start = 0.0
    while start + GEOMETRY_WINDOW_DAYS <= span + 1e-9:
        out.append((start, start + GEOMETRY_WINDOW_DAYS))
        start += GEOMETRY_STEP_DAYS
    return out


# --------------------------------------------------------------------------
# Orbital mechanics: state from elements, elements from state
# --------------------------------------------------------------------------
def rv_to_osculating(r_km: np.ndarray, v_km_s: np.ndarray) -> dict[str, float]:
    """Classical osculating elements from a position and velocity.

    Derived from the two-body integrals, not quoted: the specific angular
    momentum h = r x v fixes the plane (i from h_z/|h|, RAAN from the node
    vector n = z x h); the eccentricity vector
    e = ((|v|^2 - mu/|r|) r - (r.v) v)/mu fixes the shape and the line of
    apsides; a comes from the vis-viva energy 1/a = 2/|r| - |v|^2/mu.
    Circular and equatorial cases are degenerate in argp and RAAN and are
    resolved by the standard substitutions, which is why the six returned
    numbers are only a coordinate choice for such an orbit.
    """
    r = np.asarray(r_km, dtype=np.float64)
    v = np.asarray(v_km_s, dtype=np.float64)
    r_mag = float(np.linalg.norm(r))
    v_mag = float(np.linalg.norm(v))
    if not (r_mag > 0.0 and np.isfinite(r_mag) and np.isfinite(v_mag)):
        return {}
    h = np.cross(r, v)
    h_mag = float(np.linalg.norm(h))
    if h_mag <= 0.0:
        return {}
    node = np.array([-h[1], h[0], 0.0])
    node_mag = float(np.linalg.norm(node))
    energy = 0.5 * v_mag * v_mag - MU_KM3_S2 / r_mag
    if abs(energy) < 1e-14:
        return {}
    a = -MU_KM3_S2 / (2.0 * energy)
    ecc_vec = ((v_mag * v_mag - MU_KM3_S2 / r_mag) * r
               - float(np.dot(r, v)) * v) / MU_KM3_S2
    ecc = float(np.linalg.norm(ecc_vec))
    inc = math.degrees(math.acos(max(-1.0, min(1.0, h[2] / h_mag))))
    if node_mag > 1e-12:
        raan = math.degrees(math.atan2(node[1], node[0])) % 360.0
    else:
        raan = 0.0
    if node_mag > 1e-12 and ecc > 1e-12:
        argp = math.degrees(math.acos(max(-1.0, min(
            1.0, float(np.dot(node, ecc_vec)) / (node_mag * ecc)))))
        if ecc_vec[2] < 0.0:
            argp = 360.0 - argp
    else:
        argp = 0.0
    if ecc > 1e-12:
        nu = math.degrees(math.acos(max(-1.0, min(
            1.0, float(np.dot(ecc_vec, r)) / (ecc * r_mag)))))
        if float(np.dot(r, v)) < 0.0:
            nu = 360.0 - nu
        nu_rad = math.radians(nu)
        if ecc < 1.0:
            ecc_anom = math.atan2(
                math.sqrt(max(0.0, 1.0 - ecc * ecc)) * math.sin(nu_rad),
                ecc + math.cos(nu_rad))
            mean_anom = math.degrees(ecc_anom - ecc * math.sin(ecc_anom)) % 360.0
        else:
            mean_anom = float("nan")
    else:
        arg_lat = math.degrees(math.atan2(
            float(np.dot(r, np.cross(h, node))) if node_mag > 1e-12 else r[1],
            float(np.dot(r, node)) if node_mag > 1e-12 else r[0]))
        mean_anom = arg_lat % 360.0
    return {"a_km": a, "ecc": ecc, "inc_deg": inc, "raan_deg": raan,
            "argp_deg": argp % 360.0, "m_deg": mean_anom}


def wrap180(degrees_in):
    return (np.asarray(degrees_in, dtype=np.float64) + 180.0) % 360.0 - 180.0


def rtn_components(r_ref: np.ndarray, v_ref: np.ndarray,
                   delta_r: np.ndarray) -> tuple[float, float, float]:
    """A position difference expressed in the reference state's own orbit frame.

    Radial along r-hat, cross-track along (r x v)-hat, along-track completing
    the right-handed triad. The along-track axis is not v-hat: for an eccentric
    orbit v-hat is not perpendicular to r-hat and the three numbers would not
    be a decomposition.
    """
    r_hat = r_ref / np.linalg.norm(r_ref)
    h = np.cross(r_ref, v_ref)
    c_hat = h / np.linalg.norm(h)
    t_hat = np.cross(c_hat, r_hat)
    return (float(np.dot(delta_r, r_hat)),
            float(np.dot(delta_r, t_hat)),
            float(np.dot(delta_r, c_hat)))


def _satrec(row, whichconst=None):
    from sgp4.api import Satrec, WGS72                        # noqa: PLC0415
    from sgp4.conveniences import jday_datetime               # noqa: PLC0415
    import datetime as _dt                                    # noqa: PLC0415

    epoch_ms = int(row["epoch_ms"])
    when = _dt.datetime.fromtimestamp(epoch_ms / 1000.0, _dt.timezone.utc)
    jd, fr = jday_datetime(when)
    # sgp4init takes the epoch as days since 1949-12-31 00:00 UT
    epoch_days = (jd - 2433281.5) + fr
    sat = Satrec()
    sat.sgp4init(
        whichconst or WGS72, "i", int(row["norad"]), epoch_days,
        float(row["bstar"]), float(row["ndot"]), float(row["nddot"]),
        float(row["ecc"]), math.radians(float(row["argp_deg"])),
        math.radians(float(row["inc_deg"])), math.radians(float(row["m_deg"])),
        float(row["n_rev_day"]) * 2.0 * math.pi / 1440.0,
        math.radians(float(row["raan_deg"])))
    return sat, jd, fr


def _jd_of(epoch_ms: int) -> tuple[float, float]:
    from sgp4.conveniences import jday_datetime               # noqa: PLC0415
    import datetime as _dt                                    # noqa: PLC0415
    when = _dt.datetime.fromtimestamp(int(epoch_ms) / 1000.0, _dt.timezone.utc)
    return jday_datetime(when)


# --------------------------------------------------------------------------
# Archive reading
# --------------------------------------------------------------------------
ELEMENT_SQL = (
    "SELECT epoch_ms, mean_motion_q, eccentricity_q, inclination_q, raan_q, "
    "arg_perigee_q, mean_anomaly_q, bstar_q, ndot_q, nddot_q, ingest_hour "
    "FROM element_set WHERE norad=? ORDER BY epoch_ms")


def open_archive(path: Path = ARCHIVE) -> sqlite3.Connection:
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    db.execute("PRAGMA query_only=1")
    return db


def load_elements(db: sqlite3.Connection, norad: int) -> dict | None:
    rows = db.execute(ELEMENT_SQL, (int(norad),)).fetchall()
    if not rows:
        return None
    arr = np.asarray([[c if c is not None else 0 for c in row] for row in rows],
                     dtype=np.float64)
    return {
        "norad": int(norad),
        "epoch_ms": arr[:, 0].astype(np.int64),
        "n_rev_day": arr[:, 1] / SCALE_MEAN_MOTION,
        "ecc": arr[:, 2] / SCALE_ECCENTRICITY,
        "inc_deg": arr[:, 3] / SCALE_ANGLE,
        "raan_deg": arr[:, 4] / SCALE_ANGLE,
        "argp_deg": arr[:, 5] / SCALE_ANGLE,
        "m_deg": arr[:, 6] / SCALE_ANGLE,
        "bstar": arr[:, 7] / SCALE_BSTAR,
        "ndot": arr[:, 8] / SCALE_NDOT,
        "nddot": arr[:, 9] / SCALE_NDDOT,
        "ingest_hour": arr[:, 10],
    }


def clip_history(el: dict, partition: str,
                 cap: int = MAX_SETS_PER_OBJECT) -> dict:
    """The registered per-object cap: the most recent contiguous run, ending
    before `T_cut` for train and validation (registration 2.2, 2.3)."""
    keep = np.ones(el["epoch_ms"].size, dtype=bool)
    if partition != "test":
        keep &= el["epoch_ms"] < T_CUT_MS
    index = np.nonzero(keep)[0]
    if index.size == 0:
        return {k: (v[:0] if isinstance(v, np.ndarray) else v)
                for k, v in el.items()}
    if index.size > cap:
        index = index[-cap:]
    out = {k: (v[index] if isinstance(v, np.ndarray) else v)
           for k, v in el.items()}
    return out


def regime_of(el: dict) -> str:
    """A coarse regime label for the composition report. Interpretive only --
    it is never an input channel."""
    n = float(np.median(el["n_rev_day"]))
    if not (n > 0):
        return "unknown"
    a = (MU_KM3_S2 / ((n * 2.0 * math.pi / 86400.0) ** 2)) ** (1.0 / 3.0)
    ecc = float(np.median(el["ecc"]))
    apogee = a * (1.0 + ecc) - 6378.137
    perigee = a * (1.0 - ecc) - 6378.137
    if apogee - perigee > 5000.0:
        return "HEO"
    if perigee < 2000.0:
        return "LEO"
    if 33000.0 < perigee < 39000.0:
        return "GEO"
    return "MEO"


def era_of(epoch_ms: np.ndarray) -> str:
    import datetime as _dt
    mid = int(np.median(epoch_ms))
    year = _dt.datetime.fromtimestamp(mid / 1000.0, _dt.timezone.utc).year
    return f"{(year // 10) * 10}s"


# --------------------------------------------------------------------------
# Channel construction
# --------------------------------------------------------------------------
def rolling_median_mad(values: np.ndarray, window: int = ROLLING_STEPS):
    """Causal rolling median and MAD over the PRECEDING `window` samples.

    Causal, not centred: a centred statistic at step k reads steps after k, and
    a detector that reads its own future is not a detector.
    """
    v = np.asarray(values, dtype=np.float64)
    n = v.size
    med = np.zeros(n, dtype=np.float64)
    mad = np.zeros(n, dtype=np.float64)
    for k in range(n):
        lo = max(0, k - window)
        chunk = v[lo:k] if k > lo else v[k:k + 1]
        m = float(np.median(chunk))
        med[k] = m
        mad[k] = float(np.median(np.abs(chunk - m)))
    return med, mad


def cadence_channels(epoch_ms: np.ndarray, ingest_hour: np.ndarray) -> np.ndarray:
    """Channel group C. Timing only -- registration 2.1.

    Nothing here is a function of where the object is or of what it did. The
    array is (steps, 5) aligned to the TARGET index, i.e. entry k describes the
    step from set k to set k+1.
    """
    epochs = np.asarray(epoch_ms, dtype=np.float64)
    dt_days = np.diff(epochs) / DAY_MS
    dt_days = np.maximum(dt_days, 1e-9)
    log_dt = np.log(dt_days)
    med, mad = rolling_median_mad(log_dt, ROLLING_STEPS)
    latency_h = np.asarray(ingest_hour, dtype=np.float64)[1:] - epochs[1:] / 3600000.0
    latency = np.log1p(np.maximum(latency_h, 0.0))
    t_days = (epochs - epochs[0]) / DAY_MS
    span = max(float(t_days[-1] - t_days[0]), 1e-9)
    position = ((t_days[1:] % GEOMETRY_WINDOW_DAYS) / GEOMETRY_WINDOW_DAYS
                if span > GEOMETRY_WINDOW_DAYS
                else t_days[1:] / max(span, 1e-9))
    return np.stack([log_dt, med, mad, latency, position], axis=1)


def fit_channels(el: dict) -> np.ndarray:
    """Channel group B, aligned to the target index."""
    epochs = el["epoch_ms"].astype(np.float64)
    latency_h = el["ingest_hour"][1:] - epochs[1:] / 3600000.0
    return np.stack([
        el["bstar"][1:],
        el["ndot"][1:],
        np.log1p(np.maximum(latency_h, 0.0)),
    ], axis=1)


def residual_channels(el: dict, say=None) -> tuple[np.ndarray, np.ndarray]:
    """Channel group A: the SGP4 residual, and a validity mask.

    Set `i` is propagated to `epoch_{i+1}` and differenced against set `i+1`
    evaluated at its own epoch. This is a difference between two FITS over
    different observation spans, not a physical acceleration: it carries fit
    noise and the archive's sampling geometry along with whatever the object
    did. That sentence is registered and is repeated wherever the channel is.
    """
    from sgp4.api import WGS72                                 # noqa: PLC0415

    count = el["epoch_ms"].size
    steps = max(count - 1, 0)
    out = np.zeros((steps, len(TARGET_CHANNELS)), dtype=np.float64)
    ok = np.zeros(steps, dtype=bool)
    if steps == 0:
        return out, ok

    sats = []
    jds = []
    for i in range(count):
        row = {k: (el[k][i] if isinstance(el[k], np.ndarray) else el[k])
               for k in ("epoch_ms", "n_rev_day", "ecc", "inc_deg", "raan_deg",
                         "argp_deg", "m_deg", "bstar", "ndot", "nddot")}
        row["norad"] = el["norad"]
        try:
            sat, jd, fr = _satrec(row, WGS72)
        except Exception:                                      # noqa: BLE001
            sats.append(None)
            jds.append((0.0, 0.0))
            continue
        sats.append(sat)
        jds.append((jd, fr))

    for k in range(steps):
        sat_a, sat_b = sats[k], sats[k + 1]
        if sat_a is None or sat_b is None:
            continue
        jd_b, fr_b = jds[k + 1]
        err_a, r_pred, v_pred = sat_a.sgp4(jd_b, fr_b)
        err_b, r_obs, v_obs = sat_b.sgp4(jd_b, fr_b)
        if err_a != 0 or err_b != 0:
            continue
        r_pred = np.asarray(r_pred, dtype=np.float64)
        r_obs = np.asarray(r_obs, dtype=np.float64)
        v_pred = np.asarray(v_pred, dtype=np.float64)
        v_obs = np.asarray(v_obs, dtype=np.float64)
        if not (np.all(np.isfinite(r_pred)) and np.all(np.isfinite(r_obs))):
            continue
        ea = rv_to_osculating(r_pred, v_pred)
        eb = rv_to_osculating(r_obs, v_obs)
        if not ea or not eb:
            continue
        radial, along, cross = rtn_components(r_pred, v_pred, r_obs - r_pred)
        values = (
            eb["a_km"] - ea["a_km"],
            eb["ecc"] - ea["ecc"],
            float(wrap180(eb["inc_deg"] - ea["inc_deg"])),
            float(wrap180(eb["raan_deg"] - ea["raan_deg"])),
            float(wrap180(eb["argp_deg"] - ea["argp_deg"])),
            float(wrap180(eb["m_deg"] - ea["m_deg"])),
            radial, along, cross,
        )
        if not all(math.isfinite(v) for v in values):
            continue
        out[k] = values
        ok[k] = True
    return out, ok


def build_sequence(el: dict, partition: str) -> dict:
    """The full per-object record: targets, both input groups, and the epochs.

    `validate_no_future` is called here rather than by the caller, so a
    training sequence carrying a test-era epoch cannot be built at all.
    """
    validate_no_future(partition, el["epoch_ms"])
    targets, ok = residual_channels(el)
    return {
        "norad": el["norad"],
        "epoch_ms": el["epoch_ms"][1:],
        "targets": targets,
        "valid": ok,
        "cadence": cadence_channels(el["epoch_ms"], el["ingest_hour"]),
        "fit": fit_channels(el),
    }


# --------------------------------------------------------------------------
# Split construction (CLI)
# --------------------------------------------------------------------------
def census_rows(db: sqlite3.Connection) -> list[tuple[int, int, int, int]]:
    """A DIRECT scan. The archive's object_rollup undercounts the row total by
    33,654,516 rows, so no T18 count is ever read from it (registration 1.2)."""
    return db.execute(
        "SELECT norad, COUNT(*), MIN(epoch_ms), MAX(epoch_ms) "
        "FROM element_set GROUP BY norad").fetchall()


def build_split(db: sqlite3.Connection, say=print) -> dict:
    rows = census_rows(db)
    say(f"census: {len(rows)} objects, {sum(r[1] for r in rows)} element sets")
    names = dict(db.execute("SELECT norad, name FROM object").fetchall())
    types = dict(db.execute("SELECT norad, object_type FROM object").fetchall())

    assignment: dict[str, dict] = {}
    admissible = 0
    for norad, count, first_ms, last_ms in rows:
        span_days = (last_ms - first_ms) / DAY_MS
        is_admissible = (count >= MIN_ELEMENT_SETS
                         and span_days >= MIN_SPAN_DAYS
                         and first_ms < T_CUT_MS)
        name = names.get(norad)
        prefix = constellation_prefix(name)
        inc = raan = None
        if prefix is not None:
            got = db.execute(
                "SELECT inclination_q, raan_q FROM element_set WHERE norad=? "
                "ORDER BY epoch_ms LIMIT 1", (norad,)).fetchone()
            if got:
                inc = got[0] / SCALE_ANGLE
                raan = got[1] / SCALE_ANGLE
        unit = split_unit(norad, name, inc, raan)
        assignment[str(norad)] = {
            "unit": unit,
            "partition": partition_of(norad, unit),
            "elementSets": int(count),
            "spanDays": round(span_days, 3),
            "admissible": bool(is_admissible),
            "objectType": types.get(norad),
            "truthSpacecraft": TRUTH_NORADS.get(norad),
        }
        admissible += int(is_admissible)
    validate_split(assignment)
    say(f"admissible: {admissible}")
    return {
        "registration": "docs/t18-preregistration-20260922.md",
        "registrationCommit": "2618343",
        "seed": SEED,
        "salt": SPLIT_SALT,
        "tCutMs": T_CUT_MS,
        "buckets": {"train": [0, TRAIN_BUCKET_MAX],
                    "validation": [TRAIN_BUCKET_MAX, VALIDATION_BUCKET_MAX],
                    "test": [VALIDATION_BUCKET_MAX, BUCKETS]},
        "admissibility": {"minElementSets": MIN_ELEMENT_SETS,
                          "minSpanDays": MIN_SPAN_DAYS,
                          "firstEpochBeforeTCut": True},
        "truthSpacecraftForcedToTest": {str(k): v for k, v in TRUTH_NORADS.items()},
        "objects": len(assignment),
        "admissibleObjects": admissible,
        "assignment": assignment,
    }


def partition_objects(split: dict, partition: str, limit: int | None = None,
                      require_admissible: bool = True,
                      object_types: tuple | None = None) -> list[int]:
    """Objects of a partition in seeded-hash order -- the cap of registration
    2.2 applied to a deterministic order, never to an arbitrary one."""
    rows = []
    for key, row in split["assignment"].items():
        if row["partition"] != partition:
            continue
        if require_admissible and not row["admissible"]:
            continue
        if object_types is not None and row.get("objectType") not in object_types:
            continue
        rows.append((split_bucket(row["unit"]), int(key)))
    rows.sort()
    out = [norad for _, norad in rows]
    return out if limit is None else out[:limit]


def extract(db: sqlite3.Connection, split: dict, partition: str,
            norads: list[int], out_path: Path, say=print,
            cap: int = MAX_SETS_PER_OBJECT) -> dict:
    classes = Rung2Classes.load()
    blocks = {}
    stats = {"objects": 0, "steps": 0, "validSteps": 0, "abstained": 0,
             "windows": 0, "byClass": {}, "byRegime": {}, "byEra": {}}
    started = time.time()
    for index, norad in enumerate(norads):
        el = load_elements(db, norad)
        if el is None:
            continue
        el = clip_history(el, partition, cap)
        if el["epoch_ms"].size < 64:
            continue
        seq = build_sequence(el, partition)
        t_days = (el["epoch_ms"] - el["epoch_ms"][0]) / DAY_MS
        window_class = []
        for lo, hi in geometry_windows(t_days):
            inside = (t_days >= lo) & (t_days < hi)
            key = classes.classify(t_days[inside])
            window_class.append([float(lo), float(hi), key or ""])
            stats["windows"] += 1
            if key is None:
                stats["abstained"] += 1
            else:
                stats["byClass"][key] = stats["byClass"].get(key, 0) + 1
        regime = regime_of(el)
        era = era_of(el["epoch_ms"])
        stats["byRegime"][regime] = stats["byRegime"].get(regime, 0) + 1
        stats["byEra"][era] = stats["byEra"].get(era, 0) + 1
        blocks[f"targets_{norad}"] = seq["targets"].astype(np.float32)
        blocks[f"valid_{norad}"] = seq["valid"]
        blocks[f"cadence_{norad}"] = seq["cadence"].astype(np.float32)
        blocks[f"fit_{norad}"] = seq["fit"].astype(np.float32)
        blocks[f"epoch_{norad}"] = seq["epoch_ms"]
        blocks[f"windows_{norad}"] = np.asarray(window_class, dtype=object)
        stats["objects"] += 1
        stats["steps"] += int(seq["targets"].shape[0])
        stats["validSteps"] += int(seq["valid"].sum())
        if (index + 1) % 100 == 0:
            say(f"  {index + 1}/{len(norads)} objects, "
                f"{stats['validSteps']} valid steps, "
                f"{time.time() - started:.0f}s")
    stats["elapsedS"] = time.time() - started
    stats["partition"] = partition
    stats["perObjectCap"] = cap
    stats["splitChecksum"] = split_checksum(split["assignment"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_path, **blocks,
                        _norads=np.asarray(sorted(blocks and
                                                  {int(k.split("_")[1])
                                                   for k in blocks} or []),
                                           dtype=np.int64))
    (out_path.parent / f"{out_path.stem}-stats.json").write_text(
        json.dumps(stats, indent=2, sort_keys=True) + "\n")
    say(f"-> {out_path} ({stats['objects']} objects, "
        f"{stats['validSteps']} valid steps, {stats['elapsedS']:.0f}s)")
    return stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("split")
    sp.add_argument("--out", type=Path,
                    default=REPO / "docs" / "t18-split-20260922.json")

    ex = sub.add_parser("extract")
    ex.add_argument("--split", type=Path,
                    default=REPO / "docs" / "t18-split-20260922.json")
    ex.add_argument("--partition", required=True,
                    choices=("train", "validation", "test"))
    ex.add_argument("--limit", type=int, default=None)
    ex.add_argument("--passive", action="store_true",
                    help="restrict to the passive class (DEBRIS, ROCKET BODY)")
    ex.add_argument("--norads", type=str, default=None,
                    help="comma-separated explicit object list")
    ex.add_argument("--out", type=Path, required=True)
    ex.add_argument("--cap", type=int, default=MAX_SETS_PER_OBJECT,
                    help="per-object element-set cap; 0 means no cap, which "
                         "is what the registration gives the evaluation "
                         "populations")

    args = ap.parse_args(argv)
    db = open_archive()

    if args.command == "split":
        split = build_split(db)
        checksum = split_checksum(split["assignment"])
        split["assignmentSha256"] = checksum
        args.out.write_text(json.dumps(split, separators=(",", ":"),
                                       sort_keys=True) + "\n")
        print(f"-> {args.out}\nassignment sha256 {checksum}")
        return 0

    split = json.loads(args.split.read_text())
    if args.norads:
        norads = [int(x) for x in args.norads.split(",") if x.strip()]
    else:
        types = ("DEBRIS", "ROCKET BODY") if args.passive else None
        norads = partition_objects(split, args.partition, args.limit,
                                   object_types=types)
    print(f"{args.partition}: {len(norads)} objects")
    cap = args.cap if args.cap > 0 else 10 ** 12
    extract(db, split, args.partition, norads, args.out, cap=cap)
    return 0


if __name__ == "__main__":
    sys.exit(main())
