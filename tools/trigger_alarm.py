#!/usr/bin/env python3
"""T8d: the trigger-time predictor -- a taxonomy over what an alarm actually
possesses at the moment a drift-rate change is confirmed, and the per-object
predictor T8c's variance decomposition points at.

Every definition here is the one registered in
`docs/trigger-alarm-preregistration-20260922.md` and must not drift from it.
Section references below (prereg N) point at that document; where this module
makes an implementation choice the registration left open, the choice is
marked IMPL and justified in place.

The instrument is ownership-agnostic. Catalogue registry codes are carried on
no row this module writes and are read by no branch of it. Nothing here
computes a mass or any consumables figure, and nothing here emits a distance:
every separation is mean-longitude separation, a slot coordinate (T8a 1.1).

The geometry, the unwrap, the daily grid, the station segmentation and the
drift-change flags are IMPORTED from `tools/proximity_geo.py`; the transform,
the scaler, k-means, the silhouette, the bootstrap and the partition
comparisons are IMPORTED from `tools/alarm_pattern.py`. T8d adds no second
copy of any of them (prereg 2).

THE CAUSAL CONTRACT (prereg 12). `trigger_features` is handed a `CausalView`
-- a per-object element history truncated at `t_trig` -- and an occupancy
table computed from other objects' pre-trigger state. It can therefore not
read the future, and `tests/test_trigger_alarm.py` asserts it by extracting
the same vector from a truncated series and from a series whose post-trigger
elements have been replaced by garbage.

Stages
------
  triggers   the flag chains, their features and their outcomes (prereg 3, 4)
  analyze    the taxonomy (prereg 5), M1 (prereg 6), M2 (prereg 8), the gates
  all        both
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
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
for _p in (str(_REPO), str(_REPO / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import proximity_geo as pg            # noqa: E402  the T8a instrument
import alarm_pattern as ap            # noqa: E402  the T8c instrument

DAY_MS = pg.DAY_MS
SEED = 20260922                                     # prereg 2

REGISTRATION = "docs/trigger-alarm-preregistration-20260922.md"
EVENTS_PATH = _REPO / "docs" / "proximity-events-20260922.jsonl"
T8C_FEATURES_PATH = _REPO / "docs" / "alarm-pattern-features-20260922.jsonl"
# Installation-specific locations. Each is named by an environment variable
# and falls back to a placeholder that cannot resolve, so an unconfigured
# checkout fails with the name of the variable it needs instead of reading
# whatever happens to sit at somebody else's path.
ARCHIVE = Path(os.environ.get("ORBIT_ARCHIVE_DB",
                              "element-archive.not-configured.sqlite3"))
EXTRACT_DIR = _REPO / "runtime" / "proximity-geo"

# prereg 2 -- the cached T8a extract must reproduce these three numbers.
T8A_ROWS_SCANNED = 217_007_154
T8A_ROWS_KEPT = 11_626_494
T8A_OBJECTS_KEPT = 1_768

# prereg 3 -- the trigger
MERGE_DAYS = pg.MAX_GAP_DAYS                        # 5.0
CONFIRM_DAYS = MERGE_DAYS                           # 5.0, the announce delay
H_DAYS = pg.T_LOOK_DAYS                             # 180.0, the horizon
DWELL_DAYS = pg.D_PRIMARY_DAYS                      # 30.0
SLOT_DRIFT_FLOOR = 6.0 * pg.X_PRIMARY_DEG / pg.D_PRIMARY_DAYS   # 0.020 deg/day
SLOT_MATCH_DEG = pg.X_PRIMARY_DEG                   # 0.1
SLOT_MIN_HISTORY_DAYS = pg.STATION_MIN_DAYS         # 30.0
RAMP_LOOKBACK_DAYS = 30.0                           # prereg 4.2 feature 2
RAMP_FLOOR_DAYS = 0.5                               # prereg 4.2 feature 4
PLANE_MATCH_DEG = 0.5                               # prereg 4.6 feature 19

# prereg 4.6 -- the resonance propagation, from T8a's own constants
LAMBDA_DDOT = pg.LAMBDA_DDOT_MAX                    # ~1.70e-3 deg/day^2
LAMBDA_STABLE_DEG = 75.1                            # prereg 4.6 derivation
PROP_STEP_DAYS = 1.0

# DECLARED COMPUTE DEVIATIONS (results doc section 2). The registered
# protocol assumed a trigger population of the order of T8a's 1,483 alerts.
# The measured population is 226,422 flag chains, and two steps of the
# registered procedure do not scale to it:
#   D1a  `silhouette` materialises two n x n matrices: at n = 98,720 that is
#        2 x 78 GB. The mean silhouette is a sample statistic, so it is
#        evaluated on SUBSAMPLE_SILHOUETTE rows drawn with the registered
#        seed -- three independent draws, all three reported, so the reader
#        can see whether the chosen k depends on the draw.
#   D1b  leave-one-OBJECT-out needs one k-means refit per approacher. At the
#        measured 25 s per refit and 1,200 approachers that is 8.3 hours per
#        arm. It is replaced by GROUPED K-FOLD over approachers, which keeps
#        the object-disjointness that makes the estimate honest and trains on
#        95% of objects where leave-one-out trains on 99.9% -- strictly the
#        more conservative of the two. The LOO protocol is kept UNCHANGED
#        wherever it is affordable: M2-L, on T8c's 487 events, is leave-one-
#        object-out exactly as registered.
SUBSAMPLE_SILHOUETTE = 6000
SUBSAMPLE_DRAWS = 3
CV_FOLDS = 20

# prereg 5 / 9
K_RANGE = ap.K_RANGE                                # 2..10
STABILITY_DRAWS = ap.STABILITY_DRAWS                # 200
SKILL_BOOTSTRAP = ap.SKILL_BOOTSTRAP                # 2000

# prereg 8 -- the fixed combination rule
HYBRID_WEIGHT = 0.5
WEIGHT_CURVE = (0.0, 0.25, 0.5, 0.75, 1.0)
PRIOR_STRATA = ((1, 1), (2, 2), (3, 3), (4, 4), (5, 10 ** 9))

# prereg 11 -- the gates, as numbers
GATE_A_MIN_TRIGGERS = 200
GATE_A_MIN_POSITIVES = 50
GATE_D_MIN_CLASS = 20
GATE_E_JACCARD = 0.5
GATE_F_ARI = 0.5
GATE_G_BAR = 0.157                                  # T8c's own gate-P bar
GATE_W_DEG = 2.0
T8A_SKILL_LOITER = ap.T8A_SKILL_LOITER              # +0.137
MIN_STRATUM_PREDICTIONS = 20                        # prereg 8.4

# prereg 4 -- the feature table, in registration order: (name, log-transformed)
FEATURES = (
    ("init_drift_change_mag", True),
    ("init_ramp_days", True),
    ("init_stage_count", False),
    ("init_abruptness", True),
    ("trig_drift_abs", True),
    ("trig_drift_sign", False),
    ("trig_baseline_drift_abs", True),
    ("cad_days_since_prev_trigger", True),
    ("cad_prior_triggers", False),
    ("cad_prior_events", False),
    ("cad_prior_targets", False),
    ("ctx_libration_zone", False),
    ("ctx_nearest_occupied_deg", True),
    ("ctx_inclination_deg", True),
    ("fwd_path_length_deg", True),
    ("fwd_slots_reached", False),
    ("fwd_days_to_first_slot", True),
    ("fwd_first_slot_deg", True),
    ("fwd_plane_compatible_slots", False),
    ("miss_ramp", False),
    ("miss_prev_trigger", False),
    ("miss_fwd_slot", False),
)
FEATURE_NAMES = tuple(n for n, _ in FEATURES)
LOG_FEATURES = frozenset(n for n, lg in FEATURES if lg)
FORWARD_FEATURES = tuple(n for n in FEATURE_NAMES if n.startswith("fwd_"))

# prereg 4.8 -- names that may never be a column here
FORBIDDEN_PREFIXES = ("transit_", "arrival_", "dwell_", "departure_", "lead_")
FORBIDDEN_SUBSTRINGS = ("loiter", "closestseparation", "_km")


# ==========================================================================
# Loading -- prereg 2
# ==========================================================================
def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_cached_extract(db=None, extract_dir=EXTRACT_DIR):
    """prereg 2: reuse T8a's own 293.5 s pass, but only after asserting its
    three published numbers. If any disagrees the extract is recomputed from
    the archive by T8a's own `extract`, and the receipt records which path
    was taken."""
    npz = extract_dir / "near-geo.npz"
    meta_path = extract_dir / "extract-meta.json"
    if npz.exists() and meta_path.exists():
        meta = json.loads(meta_path.read_text())
        ok = (meta.get("rowsScanned") == T8A_ROWS_SCANNED
              and meta.get("rowsKept") == T8A_ROWS_KEPT
              and meta.get("objectsKept") == T8A_OBJECTS_KEPT)
        if ok:
            with np.load(npz) as z:
                arrays = {k: z[k] for k in z.files}
            meta["source"] = "cached T8a extract, three numbers asserted"
            meta["sha256"] = sha256_file(npz)
            return arrays, meta
    if db is None:
        raise SystemExit("cached extract absent or disagrees and no archive given")
    arrays, meta = pg.extract(db, extract_dir)
    meta["source"] = "recomputed from the archive"
    meta["sha256"] = sha256_file(npz)
    return arrays, meta


def load_events(path=EVENTS_PATH):
    """The committed T8a catalogue. The provenance record carries the sigma_n
    T8d must reuse rather than recalibrate (prereg 2)."""
    provenance, rows = None, []
    with open(path) as fh:
        for line in fh:
            rec = json.loads(line)
            if rec.get("record") == "provenance":
                provenance = rec
                continue
            rows.append(rec)
    return provenance, rows


def primary_arm(rows):
    """T8a's registered headline catalogue of 487 (prereg 2)."""
    return [e for e in rows
            if e.get("approacherClass") == "active"
            and e.get("attribution") == "resolved"]


def object_classes(db, norads):
    """prereg 1.2: `object_type` is read for T8a 3.2's active/passive class and
    for nothing else. No other catalogue column is read by this module."""
    out = {}
    for norad in norads:
        row = db.execute("SELECT object_type FROM object WHERE norad = ?",
                         (int(norad),)).fetchone()
        out[int(norad)] = pg.class_of(row[0] if row else None)
    return out


# ==========================================================================
# prereg 3 -- the trigger population
# ==========================================================================
class Trigger:
    """One maximal flag chain. `tFirst` opens it, `tTrig` closes it, and the
    alarm could speak at `tAnnounce = tTrig + CONFIRM_DAYS`."""

    __slots__ = ("norad", "tFirst", "tTrig", "stages", "driftChange",
                 "driftBase", "eligible")

    def __init__(self, norad, t_first, t_trig, stages, drift_change, drift_base):
        self.norad = int(norad)
        self.tFirst = float(t_first)
        self.tTrig = float(t_trig)
        self.stages = int(stages)
        self.driftChange = float(drift_change)
        self.driftBase = float(drift_base)
        self.eligible = bool(np.isfinite(drift_base)
                             and abs(drift_base) <= SLOT_DRIFT_FLOOR)

    @property
    def tAnnounce(self):
        return self.tTrig + CONFIRM_DAYS * DAY_MS


def flag_baselines(series, sigma_n):
    """The trailing-median baseline `drift_change_flags` already computes,
    returned alongside the flags so that prereg 4.1's `d_base` is READ from
    T8a's own array rather than recomputed differently here."""
    d = series.drift
    n = d.size
    w = pg.BURN_BASELINE_SAMPLES
    if n < w + 2:
        return (np.zeros(0, dtype=np.int64), np.zeros(0), np.zeros(0))
    base = np.full(n, np.nan)
    windows = np.lib.stride_tricks.sliding_window_view(d[:n - 1], w)
    base[w:] = np.median(windows[:n - w], axis=1)
    thresh = max(pg.BURN_SIGMA_K * sigma_n, pg.BURN_FLOOR_DEG_PER_DAY)
    dev = np.abs(d - base)
    hot = np.isfinite(dev) & (dev > thresh)
    confirmed = np.where(hot[:-1] & hot[1:])[0] + 1
    return (series.epoch_ms[confirmed],
            d[confirmed] - base[confirmed - 1],
            base[confirmed - 1])


def chain_flags(flag_ms, sizes, bases, merge_days=MERGE_DAYS):
    """prereg 3.1: consecutive flags separated by <= merge_days are ONE
    trigger. Returns (t_first, t_trig, stages, drift_change_at_last,
    drift_base_at_first)."""
    out = []
    if flag_ms.size == 0:
        return out
    start = 0
    for i in range(1, flag_ms.size + 1):
        if i == flag_ms.size or (flag_ms[i] - flag_ms[i - 1]) > merge_days * DAY_MS:
            out.append((float(flag_ms[start]), float(flag_ms[i - 1]),
                        i - start, float(sizes[i - 1]), float(bases[start])))
            start = i
    return out


def build_triggers(series_by_norad, classes, sigma_n):
    """prereg 3.1-3.3. Active-class approachers only."""
    triggers = []
    for norad in sorted(series_by_norad):
        if classes.get(norad) != "active":
            continue
        s = series_by_norad[norad]
        flags, sizes, bases = flag_baselines(s, sigma_n)
        for t_first, t_trig, stages, size, base in chain_flags(flags, sizes, bases):
            triggers.append(Trigger(norad, t_first, t_trig, stages, size, base))
    triggers.sort(key=lambda t: (t.tTrig, t.norad))
    return triggers


# ==========================================================================
# prereg 3.4 / 3.5 -- resolvability and the outcome
# ==========================================================================
def resolve_outcomes(triggers, events, series_by_norad):
    """O1 (primary) and O2 (secondary), attached to every trigger in place as
    a plain dict per trigger. No catalogue metadata column is read here."""
    by_obj = {}
    for e in events:
        by_obj.setdefault(int(e["approacherNorad"]), []).append(e)
    out = []
    for tr in triggers:
        s = series_by_norad[tr.norad]
        need = tr.tTrig + (H_DAYS + DWELL_DAYS) * DAY_MS
        resolvable = bool(s.epoch_ms.size and float(s.epoch_ms[-1]) >= need)
        evs = by_obj.get(tr.norad, [])
        # O1 -- T8a's own attribution: its initiating flag is inside the chain
        o1 = [e for e in evs
              if e.get("initiatingFlagMs") is not None
              and tr.tFirst <= float(e["initiatingFlagMs"]) <= tr.tTrig]
        # O2 -- the window rule
        o2 = [e for e in evs
              if (tr.tFirst - MERGE_DAYS * DAY_MS) <= float(e["transferStartMs"])
              <= (tr.tTrig + H_DAYS * DAY_MS)
              and float(e["arrivalMs"]) <= tr.tTrig + H_DAYS * DAY_MS]
        rec = {"resolvable": resolvable,
               "o1Matches": len(o1), "o2Matches": len(o2)}
        for tag, matched in (("o1", o1), ("o2", o2)):
            if matched:
                best = min(matched, key=lambda e: float(e["arrivalMs"]))
                d = (float(best["arrivalMs"]) - tr.tAnnounce) / DAY_MS
                rec[tag + "Positive"] = True
                rec[tag + "ArrivalDays"] = float(d)
                rec[tag + "TargetNorad"] = int(best["targetNorad"])
                rec[tag + "LoiterDays"] = float(best["loiterDays"])
            else:
                rec[tag + "Positive"] = False
                rec[tag + "ArrivalDays"] = None
                rec[tag + "TargetNorad"] = None
                rec[tag + "LoiterDays"] = None
        out.append(rec)
    return out


# ==========================================================================
# prereg 12 -- the causal contract
# ==========================================================================
class CausalView:
    """A per-object element history truncated at `t`. Construction is the
    ONLY place a full series is touched by the feature path; everything the
    extractor sees is already in the past."""

    __slots__ = ("norad", "epoch_ms", "lam", "lam_unwrapped", "drift", "inc", "t")

    def __init__(self, series, t_ms):
        k = int(np.searchsorted(series.epoch_ms, t_ms, side="right"))
        self.norad = int(series.norad)
        self.t = float(t_ms)
        self.epoch_ms = series.epoch_ms[:k]
        self.lam = series.lam[:k]
        self.lam_unwrapped = series.lam_unwrapped[:k]
        self.drift = series.drift[:k]
        self.inc = series.inc[:k]


def causal_view(series, t_ms):
    return CausalView(series, t_ms)


# ==========================================================================
# prereg 4.6 -- the forward propagation, derived in the registration
# ==========================================================================
def _lam_ddot(lam_deg):
    """dd(lambda)/dt^2 = -K sin(2(lambda - lambda_s)), K and lambda_s from
    T8a's own tesseral constants (prereg 4.6)."""
    return -LAMBDA_DDOT * np.sin(2.0 * np.radians(lam_deg - LAMBDA_STABLE_DEG))


def propagate(lam0_deg, drift0_deg_per_day, horizon_days=H_DAYS,
              step_days=PROP_STEP_DAYS):
    """RK4 on the pair (lambda, lambda-dot) over `horizon_days`. Returns the
    unwrapped lambda path sampled at every step boundary, including t=0.

    The propagation is what the object WOULD do if it does nothing further:
    no station-keeping, no second burn, no luni-solar or SRP correction. That
    is the quantity an alarm needs at trigger, and prereg 11's gate W measures
    its error against the archive rather than trusting it.
    """
    n = int(round(horizon_days / step_days))
    lam = np.empty(n + 1, dtype=np.float64)
    lam[0] = float(lam0_deg)
    x, v, h = float(lam0_deg), float(drift0_deg_per_day), float(step_days)
    for i in range(1, n + 1):
        k1x, k1v = v, _lam_ddot(x)
        k2x, k2v = v + 0.5 * h * k1v, _lam_ddot(x + 0.5 * h * k1x)
        k3x, k3v = v + 0.5 * h * k2v, _lam_ddot(x + 0.5 * h * k2x)
        k4x, k4v = v + h * k3v, _lam_ddot(x + h * k3x)
        x = x + (h / 6.0) * (k1x + 2.0 * k2x + 2.0 * k3x + k4x)
        v = v + (h / 6.0) * (k1v + 2.0 * k2v + 2.0 * k3v + k4v)
        lam[i] = x
    return lam


def slots_reached(path_deg, slot_lons_deg, step_days=PROP_STEP_DAYS,
                  tol_deg=SLOT_MATCH_DEG):
    """Which occupied slots the propagated path passes within `tol_deg` of,
    when the first pass happens, and how far along the path that is.

    IMPL: a 1-day sample of the path is NOT enough to detect a 0.1 deg window
    -- a 5 deg/day drifter steps over it. Each step is therefore treated as
    the straight segment it is and intersected EXACTLY with the periodic band
    {360 m + s +/- tol}: the segment [lo, hi] meets it iff an integer m lies
    in [(lo - s - tol)/360, (hi - s + tol)/360].
    """
    slots = np.asarray(slot_lons_deg, dtype=np.float64)
    n_slots = slots.size
    reached = np.zeros(n_slots, dtype=bool)
    first_day = np.full(n_slots, np.nan)
    first_path = np.full(n_slots, np.nan)
    if n_slots == 0 or path_deg.size < 2:
        return reached, first_day, first_path, 0.0
    seg_lo = np.minimum(path_deg[:-1], path_deg[1:])
    seg_hi = np.maximum(path_deg[:-1], path_deg[1:])
    cum = np.concatenate(([0.0], np.cumsum(np.abs(np.diff(path_deg)))))
    total = float(cum[-1])
    # IMPL: the whole-path band test first, so a slowly drifting object does
    # not pay for 180 segment tests against slots it can never reach. It is
    # the same arithmetic, applied once to [min(path), max(path)].
    whole_lo = np.ceil((float(path_deg.min()) - slots - tol_deg) / 360.0)
    whole_hi = np.floor((float(path_deg.max()) - slots + tol_deg) / 360.0)
    cand = np.where(whole_lo <= whole_hi)[0]
    if cand.size == 0:
        return reached, first_day, first_path, total
    for i in range(seg_lo.size):
        idx = cand[~reached[cand]]
        if idx.size == 0:
            break
        m_lo = np.ceil((seg_lo[i] - slots[idx] - tol_deg) / 360.0)
        m_hi = np.floor((seg_hi[i] - slots[idx] + tol_deg) / 360.0)
        hit = idx[m_lo <= m_hi]
        if hit.size == 0:
            continue
        u0, u1 = float(path_deg[i]), float(path_deg[i + 1])
        for j in hit:
            m = np.round((0.5 * (u0 + u1) - slots[j]) / 360.0)
            target = slots[j] + 360.0 * m
            tau = 0.0
            if u1 != u0:
                lo_t = (target - tol_deg - u0) / (u1 - u0)
                hi_t = (target + tol_deg - u0) / (u1 - u0)
                cands = [c for c in (lo_t, hi_t) if -1e-12 <= c <= 1.0 + 1e-12]
                tau = min(cands) if cands else 0.0
                tau = min(max(tau, 0.0), 1.0)
            reached[j] = True
            first_day[j] = (i + tau) * step_days
            first_path[j] = cum[i] + tau * abs(u1 - u0)
    return reached, first_day, first_path, total


# ==========================================================================
# prereg 4 -- the trigger-time feature vector
# ==========================================================================
def trigger_features(trigger, view, occupancy, horizon_days=H_DAYS):
    """prereg 4. `view` is a CausalView truncated at `t_trig`; `occupancy` is
    the table of prereg 4.5 computed from other objects' pre-trigger state.
    Nothing else is read, so nothing after `t_trig` can enter a feature.

    `occupancy` is (lon_deg, inc_deg) arrays.
    """
    f = {n: float("nan") for n in FEATURE_NAMES}
    if view.epoch_ms.size == 0:
        return f
    t = trigger.tTrig
    k = int(view.epoch_ms.size - 1)                 # the confirming element set
    mag = abs(trigger.driftChange)
    base = trigger.driftBase

    # --- initiation block (prereg 4.2) ---------------------------------
    f["init_drift_change_mag"] = float(mag)
    f["init_stage_count"] = float(trigger.stages)
    ramp = float("nan")
    if np.isfinite(base) and mag > 0:
        lo = trigger.tFirst - RAMP_LOOKBACK_DAYS * DAY_MS
        win = (view.epoch_ms >= lo) & (view.epoch_ms <= t)
        quiet = win & (np.abs(view.drift - base) <= 0.1 * mag)
        if np.any(quiet):
            ramp = float((t - float(view.epoch_ms[np.where(quiet)[0][-1]])) / DAY_MS)
    f["init_ramp_days"] = ramp
    f["init_abruptness"] = (float(mag / max(ramp, RAMP_FLOOR_DAYS))
                            if np.isfinite(ramp) else float("nan"))

    # --- kinematic block (prereg 4.3) ----------------------------------
    d_now = float(view.drift[k])
    f["trig_drift_abs"] = abs(d_now)
    f["trig_drift_sign"] = float(np.sign(d_now))
    f["trig_baseline_drift_abs"] = abs(base) if np.isfinite(base) else float("nan")

    # --- context block (prereg 4.5) ------------------------------------
    lam_now = float(view.lam[k])
    f["ctx_libration_zone"] = float(bool(pg.in_libration_zone(
        lam_now, pg.X_PRIMARY_DEG, pg.D_PRIMARY_DAYS)))
    f["ctx_inclination_deg"] = float(view.inc[k])
    lons, incs = occupancy
    if lons.size:
        sep = np.abs(pg.wrap180(lons - lam_now))
        f["ctx_nearest_occupied_deg"] = float(np.min(sep))
    else:
        f["ctx_nearest_occupied_deg"] = float("nan")

    # --- forward geometry (prereg 4.6) ---------------------------------
    path = propagate(lam_now, d_now, horizon_days=horizon_days)
    reached, first_day, first_path, total = slots_reached(path, lons)
    f["fwd_path_length_deg"] = float(total)
    f["fwd_slots_reached"] = float(int(reached.sum()))
    if np.any(reached):
        j = int(np.nanargmin(np.where(reached, first_day, np.nan)))
        f["fwd_days_to_first_slot"] = float(first_day[j])
        f["fwd_first_slot_deg"] = float(first_path[j])
        d_inc = np.abs(incs[reached] - f["ctx_inclination_deg"])
        f["fwd_plane_compatible_slots"] = float(int((d_inc <= PLANE_MATCH_DEG).sum()))
    else:
        f["fwd_days_to_first_slot"] = float("nan")
        f["fwd_first_slot_deg"] = float("nan")
        f["fwd_plane_compatible_slots"] = 0.0

    # --- indicators (prereg 4.7) ---------------------------------------
    f["miss_ramp"] = float(not np.isfinite(f["init_ramp_days"]))
    f["miss_fwd_slot"] = float(not np.isfinite(f["fwd_days_to_first_slot"]))
    return f


def attach_cadence(triggers, features, events):
    """prereg 4.4 -- the cadence block, strictly before the trigger. An event
    is not KNOWN to have happened until its 30-day dwell has been observed,
    so `loiterEndMs` is the cut, never `arrivalMs`.

    `triggers` must be in time order; the caller sorts them.
    """
    ends = {}
    for e in events:
        ends.setdefault(int(e["approacherNorad"]), []).append(
            (float(e["loiterEndMs"]), int(e["targetNorad"])))
    for v in ends.values():
        v.sort()
    last_t, count = {}, {}
    for tr, f in zip(triggers, features):
        p = last_t.get(tr.norad)
        f["cad_days_since_prev_trigger"] = (float((tr.tTrig - p) / DAY_MS)
                                            if p is not None else float("nan"))
        f["miss_prev_trigger"] = float(p is None)
        f["cad_prior_triggers"] = float(count.get(tr.norad, 0))
        rows = [r for r in ends.get(tr.norad, []) if r[0] < tr.tTrig]
        f["cad_prior_events"] = float(len(rows))
        f["cad_prior_targets"] = float(len({r[1] for r in rows}))
        last_t[tr.norad] = tr.tTrig
        count[tr.norad] = count.get(tr.norad, 0) + 1
    return features


# ==========================================================================
# prereg 4.5 -- the occupancy sweep
# ==========================================================================
def occupancy_reference(series_by_norad, t_ms, exclude_norad):
    """The registered definition, written the slow obvious way. The sweep
    below must agree with it exactly; a test asserts it on a fixture."""
    lons, incs = [], []
    for norad, s in series_by_norad.items():
        if norad == exclude_norad or s.epoch_ms.size < 2:
            continue
        k = int(np.searchsorted(s.epoch_ms, t_ms, side="right")) - 1
        if k < 0:
            continue
        t_o = float(s.epoch_ms[k])
        if (t_ms - t_o) > MERGE_DAYS * DAY_MS:
            continue
        if float(s.epoch_ms[0]) > t_ms - SLOT_MIN_HISTORY_DAYS * DAY_MS:
            continue
        d_o = float(s.drift[k])
        if abs(d_o) > SLOT_DRIFT_FLOOR:
            continue
        lons.append(float(pg.wrap180(s.lam[k] + d_o * (t_ms - t_o) / DAY_MS)))
        incs.append(float(s.inc[k]))
    return np.asarray(lons), np.asarray(incs)


class OccupancySweep:
    """The same definition, computed once in time order. State is advanced
    only with element sets whose epoch is <= the query time, so the table can
    never contain the future."""

    def __init__(self, series_by_norad):
        self.norads = np.asarray(sorted(series_by_norad), dtype=np.int64)
        index = {int(n): i for i, n in enumerate(self.norads)}
        self.index = index
        n = self.norads.size
        epochs, lams, drifts, incs, sources = [], [], [], [], []
        first = np.full(n, np.inf)
        for norad, s in series_by_norad.items():
            i = index[int(norad)]
            if s.epoch_ms.size < 2:
                continue
            first[i] = float(s.epoch_ms[0])
            epochs.append(s.epoch_ms.astype(np.float64))
            lams.append(s.lam)
            drifts.append(s.drift)
            incs.append(s.inc)
            sources.append(np.full(s.epoch_ms.size, i, dtype=np.int64))
        ep = np.concatenate(epochs)
        order = np.argsort(ep, kind="stable")
        self.ep = ep[order]
        self.lam = np.concatenate(lams)[order]
        self.drift = np.concatenate(drifts)[order]
        self.inc = np.concatenate(incs)[order]
        self.source = np.concatenate(sources)[order]
        self.first = first
        self.cur_ep = np.full(n, -np.inf)
        self.cur_lam = np.full(n, np.nan)
        self.cur_drift = np.full(n, np.nan)
        self.cur_inc = np.full(n, np.nan)
        self.pos = 0

    def at(self, t_ms, exclude_norad):
        j = int(np.searchsorted(self.ep, t_ms, side="right"))
        if j > self.pos:
            sl = slice(self.pos, j)
            who = self.source[sl]
            self.cur_ep[who] = self.ep[sl]
            self.cur_lam[who] = self.lam[sl]
            self.cur_drift[who] = self.drift[sl]
            self.cur_inc[who] = self.inc[sl]
            self.pos = j
        ok = (np.isfinite(self.cur_lam)
              & ((t_ms - self.cur_ep) <= MERGE_DAYS * DAY_MS)
              & (self.first <= t_ms - SLOT_MIN_HISTORY_DAYS * DAY_MS)
              & (np.abs(self.cur_drift) <= SLOT_DRIFT_FLOOR))
        e = self.index.get(int(exclude_norad))
        if e is not None:
            ok[e] = False
        idx = np.where(ok)[0]
        lons = pg.wrap180(self.cur_lam[idx]
                          + self.cur_drift[idx] * (t_ms - self.cur_ep[idx]) / DAY_MS)
        return lons, self.cur_inc[idx]


# ==========================================================================
# prereg 6.4 -- the propagator's own error. VALIDATION ONLY.
# ==========================================================================
def validate_propagator(triggers, series_by_norad, sigma_n, check_days=30.0):
    """Reads POST-TRIGGER element sets BY DESIGN, feeds no feature, and is
    called by no feature path (prereg 12). Named `validate_` so the test that
    asserts that separation can find it."""
    errs = []
    flags_cache = {}
    for tr in triggers:
        s = series_by_norad[tr.norad]
        if tr.norad not in flags_cache:
            flags_cache[tr.norad] = flag_baselines(s, sigma_n)[0]
        fl = flags_cache[tr.norad]
        t_end = tr.tTrig + check_days * DAY_MS
        if np.any((fl > tr.tTrig) & (fl <= t_end)):
            continue                       # it manoeuvred again; not a test
        k = int(np.searchsorted(s.epoch_ms, t_end, side="right")) - 1
        if k < 0 or abs(float(s.epoch_ms[k]) - t_end) > MERGE_DAYS * DAY_MS:
            continue
        j = int(np.searchsorted(s.epoch_ms, tr.tTrig, side="right")) - 1
        if j < 0:
            continue
        span = (float(s.epoch_ms[k]) - float(s.epoch_ms[j])) / DAY_MS
        if span <= 0:
            continue
        path = propagate(float(s.lam[j]), float(s.drift[j]), horizon_days=span)
        errs.append(abs(float(pg.wrap180(path[-1] - float(s.lam[k])))))
    errs = np.asarray(errs)
    if errs.size == 0:
        return {"n": 0, "note": "no trigger had a clean 30-day look-ahead"}
    return {"n": int(errs.size),
            **{f"p{p}": float(np.percentile(errs, p)) for p in (50, 75, 95)},
            "note": ("absolute mean-longitude error of the registered "
                     "propagation at +30 d, over triggers with no further "
                     "flag in that window")}


# ==========================================================================
# Statistics
# ==========================================================================
def wilson(k, n, z=1.959963984540054):
    """prereg 6.1 -- Wilson 95%, because scipy is absent on pc and T8a 4.1
    recorded the same substitution for its registered Jeffreys interval."""
    if n <= 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def brier_skill(y, p_model, p_base, groups, draws=SKILL_BOOTSTRAP, seed=SEED):
    """prereg 6.3 -- 1 - SSE(model)/SSE(base), bootstrapped over APPROACHERS
    by the same protocol `alarm_pattern.bootstrap_skill` uses for MAE."""
    y = np.asarray(y, dtype=np.float64)
    pm = np.asarray(p_model, dtype=np.float64)
    pb = np.asarray(p_base, dtype=np.float64)
    if y.size == 0:
        return {"n": 0, "skill": None}
    em = (y - pm) ** 2
    eb = (y - pb) ** 2
    if float(eb.mean()) <= 0:
        return {"n": int(y.size), "skill": None}
    lo, hi = ap.bootstrap_skill(em, eb, groups, draws=draws, seed=seed)
    return {"n": int(y.size), "skill": float(1.0 - em.mean() / eb.mean()),
            "brierModel": float(em.mean()), "brierBase": float(eb.mean()),
            "ci95": [lo, hi], "objects": int(len(set(map(int, groups)))),
            "positives": int(y.sum())}


def auc(y, p):
    """Secondary, governs nothing (prereg 6.3)."""
    y = np.asarray(y, dtype=np.float64)
    p = np.asarray(p, dtype=np.float64)
    pos, neg = y == 1, y == 0
    if not pos.any() or not neg.any():
        return float("nan")
    order = np.argsort(p, kind="stable")
    ranks = np.empty(p.size, dtype=np.float64)
    sp = p[order]
    i = 0
    while i < sp.size:
        j = i
        while j + 1 < sp.size and sp[j + 1] == sp[i]:
            j += 1
        ranks[order[i:j + 1]] = 0.5 * (i + j) + 1.0
        i = j + 1
    n1, n0 = float(pos.sum()), float(neg.sum())
    return float((ranks[pos].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def cohens_kappa(a, b):
    a = np.asarray(a, dtype=bool)
    b = np.asarray(b, dtype=bool)
    n = a.size
    if n == 0:
        return float("nan")
    po = float((a == b).mean())
    pe = float(a.mean() * b.mean() + (1 - a.mean()) * (1 - b.mean()))
    return float((po - pe) / (1 - pe)) if pe < 1 else float("nan")


def percentiles(values, ps=(5, 25, 50, 75, 95)):
    v = np.asarray([x for x in values if x is not None and np.isfinite(x)],
                   dtype=np.float64)
    if v.size == 0:
        return {"n": 0}
    return {"n": int(v.size), **{f"p{p}": float(np.percentile(v, p)) for p in ps}}


# ==========================================================================
# prereg 5 -- the taxonomy, and prereg 6.3 -- skill_A
# ==========================================================================
def feature_matrix(features, names=FEATURE_NAMES):
    return np.asarray([[f.get(n, float("nan")) for n in names] for f in features],
                      dtype=np.float64)


def choose_k_by_silhouette(matrix, names, k_range=K_RANGE, seed=SEED,
                           subsample=SUBSAMPLE_SILHOUETTE,
                           draws=SUBSAMPLE_DRAWS):
    """prereg 5 -- T8c's criterion (max mean silhouette, ties toward the
    smaller k), computed with T8c's own `kmeans` and `silhouette`.

    DEVIATION D1a: the k-means is fit on EVERY row, as registered; only the
    silhouette is EVALUATED on `subsample` rows, because `ap.silhouette`
    materialises two n x n matrices. `draws` independent subsamples are
    reported, and the chosen k is the one the FIRST draw selects -- fixed
    here so the choice cannot be made after seeing the other two.
    """
    raw = ap.transform(matrix, names)
    sc = ap.fold_scaler(raw)
    x = ap.apply_scaler(raw, sc)
    n = x.shape[0]
    rng = np.random.default_rng(seed)
    if subsample and n > subsample:
        picks = [rng.choice(n, size=subsample, replace=False) for _ in range(draws)]
    else:
        picks = [np.arange(n)]
    rows = []
    fits = {}
    for k in k_range:
        t0 = time.time()
        labels, centres, inertia = ap.kmeans(x, k, seed=seed)
        fits[k] = (labels, centres)
        sils = [float(ap.silhouette(x[p], labels[p])) for p in picks]
        rows.append({"k": int(k), "silhouette": sils[0],
                     "silhouetteDraws": sils, "inertia": float(inertia),
                     "sizes": [int(np.count_nonzero(labels == c)) for c in range(k)],
                     "seconds": float(time.time() - t0)})
        print(f"    k={k}: silhouette {sils[0]:+.4f} "
              f"(draws {['%+.4f' % v for v in sils]}) in {rows[-1]['seconds']:.1f}s",
              flush=True)
    best = max(r["silhouette"] for r in rows)
    chosen = min(r["k"] for r in rows if r["silhouette"] > best - 1e-6)
    labels, centres = fits[chosen]
    return int(chosen), labels, centres, x, rows, sc


def fold_assignments(matrix, names, objects, k, seed=SEED, n_folds=CV_FOLDS):
    """prereg 6.3, with DEVIATION D1b.

    Object-disjoint cross-validation: the approachers are partitioned into
    `n_folds` groups with the registered seed, each fold's scaler, imputation
    medians and k-means are fit on the OTHER folds' rows, and the held-out
    rows are assigned to the fold's centroids BY THEIR OWN FEATURES -- which
    is what an alarm does, since at trigger time there is no modal class of
    the object's other events to borrow.

    `n_folds = 0` means one fold per approacher, i.e. the registered
    leave-one-object-out, and is what the affordable arms use.
    """
    raw = ap.transform(matrix, names)
    objects = np.asarray(objects)
    uniq = np.unique(objects)
    if n_folds and n_folds < uniq.size:
        rng = np.random.default_rng(seed)
        shuffled = rng.permutation(uniq)
        groups = np.array_split(shuffled, n_folds)
    else:
        groups = [np.array([o]) for o in uniq]
    assigned = np.full(objects.size, -1, dtype=np.int64)
    folds = {}
    for f, group in enumerate(groups):
        out_mask = np.isin(objects, group)
        train = np.where(~out_mask)[0]
        held = np.where(out_mask)[0]
        if train.size < k + 1 or held.size == 0:
            continue
        sc = ap.fold_scaler(raw[train])
        x_tr = ap.apply_scaler(raw[train], sc)
        labels_tr, centres, _ = ap.kmeans(x_tr, k, seed=seed)
        assigned[held] = ap.assign(ap.apply_scaler(raw[held], sc), centres)
        folds[f] = {"train": train, "labelsTrain": labels_tr, "held": held,
                    "objects": group.tolist()}
        print(f"    fold {f + 1}/{len(groups)}: {train.size} train, "
              f"{held.size} held", flush=True)
    return assigned, folds


# ==========================================================================
# prereg 6 -- M1
# ==========================================================================
def describe_classes(features, labels, outcomes, k):
    """prereg 5/6: size, centroid in ORIGINAL units beside the population
    median, the five most deviant standardised features, precision with its
    Wilson interval, and the arrival-time distribution."""
    matrix = feature_matrix(features)
    raw = ap.transform(matrix, FEATURE_NAMES)
    sc = ap.fold_scaler(raw)
    x = ap.apply_scaler(raw, sc)
    keep = sc["keep"]
    kept_names = [FEATURE_NAMES[j] for j in np.where(keep)[0]]
    out = []
    for c in range(k):
        m = labels == c
        n = int(m.sum())
        centroid = {}
        for j, name in enumerate(FEATURE_NAMES):
            col = matrix[m, j]
            col = col[np.isfinite(col)]
            allcol = matrix[:, j]
            allcol = allcol[np.isfinite(allcol)]
            centroid[name] = [float(np.median(col)) if col.size else None,
                              float(np.median(allcol)) if allcol.size else None]
        dev = np.abs(x[m].mean(axis=0)) if n else np.zeros(x.shape[1])
        top = [kept_names[j] for j in np.argsort(-dev)[:5]] if n else []
        pos = [o for o, mm in zip(outcomes, m) if mm and o["o1Positive"]
               and o["o1ArrivalDays"] is not None and o["o1ArrivalDays"] > 0]
        kpos = len(pos)
        lo, hi = wilson(kpos, n)
        out.append({
            "cluster": c, "n": n, "positives": kpos,
            "precision": (kpos / n) if n else None,
            "wilson95": [lo, hi],
            "underpowered": bool(n < GATE_D_MIN_CLASS),
            "arrivalDays": percentiles([p["o1ArrivalDays"] for p in pos]),
            "namedBy": top,
            "centroidVsPopulation": centroid,
        })
    return out


def skill_arrival(labels_assigned, folds, objects, y, k):
    """prereg 6.3 -- skill_A. Object-disjoint folds (D1b); the held-out
    trigger is assigned by its OWN features; the prediction is the assigned
    class's positive rate among that fold's TRAINING rows, and the reference
    is that fold's own base rate."""
    y = np.asarray(y, dtype=np.float64)
    objects = np.asarray(objects)
    ys, pm, pb, grp = [], [], [], []
    empty = 0
    for fold in folds.values():
        train, labels_tr, held = fold["train"], fold["labelsTrain"], fold["held"]
        base = float(y[train].mean())
        rate = np.full(k, np.nan)
        for c in range(k):
            pool = y[train][labels_tr == c]
            if pool.size:
                rate[c] = float(pool.mean())
        for i in held:
            c = int(labels_assigned[i])
            if c < 0 or not np.isfinite(rate[c]):
                empty += 1
                continue
            ys.append(float(y[i]))
            pm.append(float(rate[c]))
            pb.append(base)
            grp.append(int(objects[i]))
    res = brier_skill(ys, pm, pb, grp)
    res["auc"] = auc(ys, pm) if ys else float("nan")
    res["emptyTrainingClass"] = int(empty)
    return res


# ==========================================================================
# prereg 8 -- M2
# ==========================================================================
def m2_arrival(triggers, outcomes, labels_assigned, folds, objects, y, k):
    """prereg 8.1 -- baseline / P1 per-object / P2 per-class / P3 hybrid,
    leave-one-OBJECT-out, Brier skill score against the training base rate.

    Two definitions of the object's history are computed. `registered` is the
    registration's literal words -- every strictly earlier trigger of that
    object whose outcome is resolvable. `causal` additionally requires that
    the earlier trigger had RESOLVED (its own H + D window closed) before this
    trigger fired, which is what an alarm would actually know. The registered
    one is the headline; the difference is reported.
    """
    y = np.asarray(y, dtype=np.float64)
    objects = np.asarray(objects)
    n = y.size
    order = np.argsort([t.tTrig for t in triggers], kind="stable")
    hist = {"registered": (np.zeros(n), np.zeros(n)),
            "causal": (np.zeros(n), np.zeros(n))}
    seen = {}
    for i in order:
        norad = int(objects[i])
        rows = seen.setdefault(norad, [])
        for mode in ("registered", "causal"):
            if mode == "registered":
                usable = rows
            else:
                cut = triggers[i].tTrig
                usable = [r for r in rows
                          if r[0] + (H_DAYS + DWELL_DAYS) * DAY_MS <= cut]
            hist[mode][0][i] = len(usable)
            hist[mode][1][i] = sum(r[1] for r in usable)
        rows.append((triggers[i].tTrig, float(y[i])))
    out = {}
    for mode in ("registered", "causal"):
        counts, positives = hist[mode]
        arms = {}
        for name in ("P1_own", "P2_class", "P3_hybrid"):
            ys, pm, pb, grp, strata = [], [], [], [], []
            for fold in folds.values():
                train, labels_tr = fold["train"], fold["labelsTrain"]
                base = float(y[train].mean())
                rate = np.full(k, np.nan)
                for c in range(k):
                    pool = y[train][labels_tr == c]
                    if pool.size:
                        rate[c] = float(pool.mean())
                for i in fold["held"]:
                    if counts[i] < 1:
                        continue
                    p1 = (positives[i] + 1.0) / (counts[i] + 2.0)
                    c = int(labels_assigned[i])
                    p2 = float(rate[c]) if (c >= 0 and np.isfinite(rate[c])) else base
                    p = {"P1_own": p1, "P2_class": p2,
                         "P3_hybrid": HYBRID_WEIGHT * p2
                                      + (1.0 - HYBRID_WEIGHT) * p1}[name]
                    ys.append(float(y[i]))
                    pm.append(p)
                    pb.append(base)
                    grp.append(int(objects[i]))
                    strata.append(int(counts[i]))
            res = brier_skill(ys, pm, pb, grp)
            res["auc"] = auc(ys, pm) if ys else float("nan")
            if name == "P1_own":
                res["byPriorCount"] = _stratify(ys, pm, pb, grp, strata)
            arms[name] = res
        out[mode] = arms
    out["priorCountHistogram"] = {
        str(int(v)): int(c) for v, c in
        zip(*np.unique(hist["registered"][0], return_counts=True))}
    return out


def _stratify(ys, pm, pb, grp, strata):
    """prereg 8.4 -- the skill within each prior-count stratum, with its n."""
    ys = np.asarray(ys); pm = np.asarray(pm); pb = np.asarray(pb)
    grp = np.asarray(grp); strata = np.asarray(strata)
    rows = []
    for lo, hi in PRIOR_STRATA:
        m = (strata >= lo) & (strata <= hi)
        label = f"{lo}" if lo == hi else f">={lo}"
        if not np.any(m):
            rows.append({"priorCount": label, "n": 0, "skill": None})
            continue
        res = brier_skill(ys[m], pm[m], pb[m], grp[m])
        res["priorCount"] = label
        rows.append(res)
    return rows


def hybrid_mae_skill(values, folds, objects, labels_assigned, k, weight,
                     prior_only=False):
    """prereg 8.2/8.3 -- OWN, CLS and the w-weighted blend in LOG space, the
    T8a/T8c MAE protocol so the number is comparable to +0.137.

    `folds` is `alarm_pattern.fold_models`' output; `values` is already
    log-transformed with NaN where the outcome is missing.
    """
    objects = np.asarray(objects)
    vals = np.asarray(values, dtype=np.float64)
    finite = vals[np.isfinite(vals)]
    if finite.size < 3:
        return {"n": 0, "skill": None}
    pop_median = float(np.median(finite))
    own_e, cls_e, hyb_e, pop_e, grp = [], [], [], [], []
    for norad, fold in folds.items():
        held = fold["held"]
        if held.size < 2:
            continue
        order = sorted(range(held.size), key=lambda j: labels_assigned["order"][held[j]])
        train_vals = vals[fold["train"]]
        for pos, j in enumerate(order):
            i = int(held[j])
            if not np.isfinite(vals[i]):
                continue
            peers = ([order[p] for p in range(pos)] if prior_only
                     else [order[p] for p in range(len(order)) if p != pos])
            own_vals = [vals[int(held[p])] for p in peers]
            own_vals = [v for v in own_vals if np.isfinite(v)]
            if not own_vals:
                continue
            peer_lab = [int(fold["labelsHeld"][p]) for p in peers]
            counts = np.bincount(peer_lab, minlength=k)
            top = int(counts.max())
            tied = [c for c in range(k) if counts[c] == top]
            if len(tied) == 1:
                cluster = tied[0]
            else:
                mean_vec = fold["xHeld"][peers].mean(axis=0)
                cluster = tied[int(np.argmin(
                    [float(np.sum((mean_vec - fold["centres"][c]) ** 2))
                     for c in tied]))]
            pool = train_vals[fold["labelsTrain"] == cluster]
            pool = pool[np.isfinite(pool)]
            if pool.size == 0:
                continue
            own = float(np.median(own_vals))
            cls = float(np.median(pool))
            own_e.append(abs(vals[i] - own))
            cls_e.append(abs(vals[i] - cls))
            hyb_e.append(abs(vals[i] - (weight * cls + (1.0 - weight) * own)))
            pop_e.append(abs(vals[i] - pop_median))
            grp.append(int(norad))
    if not own_e:
        return {"n": 0, "skill": None}

    def pack(err, label):
        lo, hi = ap.bootstrap_skill(err, pop_e, grp)
        return {"label": label, "n": len(err),
                "skill": float(1.0 - np.mean(err) / np.mean(pop_e)),
                "maeModelLog": float(np.mean(err)),
                "maePopulationLog": float(np.mean(pop_e)),
                "ci95": [lo, hi], "objects": int(len(set(grp)))}
    return {"OWN": pack(own_e, "the object's own other events"),
            "CLS": pack(cls_e, "the modal class of the object's other events"),
            "HYB": pack(hyb_e, f"{weight:g} CLS + {1 - weight:g} OWN, log space"),
            "weight": weight}


# ==========================================================================
def _gate_b(classes):
    """prereg 11 gate B: do the classes separate precision at all?"""
    powered = [c for c in classes if not c["underpowered"] and c["precision"] is not None]
    if len(powered) < 2:
        return True, None, None
    spread = max(c["precision"] for c in powered) - min(c["precision"] for c in powered)
    widest = max(c["wilson95"][1] - c["wilson95"][0] for c in powered)
    return bool(spread <= widest), float(spread), float(widest)


def _finite(x):
    return x if (x is not None and np.isfinite(x)) else None


def _iso(ms):
    return datetime.fromtimestamp(float(ms) / 1000.0, timezone.utc).isoformat()


# ==========================================================================
def build_trigger_table(args):
    """Stage `triggers` -- prereg 3 and 4, end to end."""
    t0 = time.time()
    say = lambda m: print(f"  [{time.time() - t0:7.1f}s] {m}", flush=True)
    db = sqlite3.connect(f"file:{ARCHIVE}?mode=ro", uri=True)
    db.execute("PRAGMA query_only = 1")
    arrays, emeta = load_cached_extract(db)
    say(f"extract loaded: {emeta['rowsKept']:,} rows, {emeta['objectsKept']} objects")
    series = pg.build_series(arrays)
    del arrays
    by_norad = {s.norad: s for s in series}
    say(f"{len(by_norad)} element histories built")
    classes = object_classes(db, sorted(by_norad))
    db.close()
    say(f"{sum(1 for c in classes.values() if c == 'active')} active-class objects")
    provenance, rows = load_events()
    events = primary_arm(rows)
    sigma_n = float(provenance["sigma_n_deg_per_day"])
    load_s = time.time() - t0

    t1 = time.time()
    triggers = build_triggers(by_norad, classes, sigma_n)
    say(f"{len(triggers)} triggers, "
        f"{sum(1 for t in triggers if t.eligible)} eligible")
    outcomes = resolve_outcomes(triggers, events, by_norad)
    say(f"{sum(1 for o in outcomes if o['resolvable'])} resolvable, "
        f"{sum(1 for o in outcomes if o['o1Positive'])} O1-positive")
    trig_s = time.time() - t1

    t2 = time.time()
    sweep = OccupancySweep(by_norad)
    say("occupancy sweep indexed")
    feats = []
    for n, tr in enumerate(triggers):
        occ = sweep.at(tr.tTrig, tr.norad)
        feats.append(trigger_features(tr, causal_view(by_norad[tr.norad], tr.tTrig), occ))
        if n and n % 2000 == 0:
            say(f"features {n}/{len(triggers)}")
    attach_cadence(triggers, feats, events)
    feat_s = time.time() - t2
    say(f"features done in {feat_s:.1f}s")

    t3 = time.time()
    seg_agreement = station_proxy_audit(triggers, by_norad)
    say(f"station-proxy audit done ({time.time() - t3:.1f}s)")
    prop = validate_propagator(triggers, by_norad, sigma_n)
    say(f"propagator validation done, median error "
        f"{prop.get('p50')} deg over n={prop.get('n')}")
    audit_s = time.time() - t3

    return {
        "triggers": triggers, "features": feats, "outcomes": outcomes,
        "events": events, "classes": classes,
        "sigma_n": sigma_n, "extractMeta": emeta,
        "stationProxy": seg_agreement, "propagator": prop,
        "seconds": {"load": load_s, "triggers": trig_s, "features": feat_s,
                    "audits": audit_s},
    }


FEATURE_PATH_FUNCTIONS = (
    "load_cached_extract", "flag_baselines", "chain_flags", "build_triggers",
    "resolve_outcomes", "CausalView", "causal_view", "_lam_ddot", "propagate",
    "slots_reached", "trigger_features", "attach_cadence",
    "occupancy_reference", "OccupancySweep", "validate_propagator",
    "station_proxy_audit", "build_trigger_table")


def feature_path_sha256():
    """The hash of the code that PRODUCES the trigger table. The cache is
    valid iff this is unchanged, so editing the analysis cannot silently
    reuse a table built by a different extractor -- and editing the
    extractor cannot silently reuse a stale one."""
    import inspect
    h = hashlib.sha256()
    for name in FEATURE_PATH_FUNCTIONS:
        h.update(inspect.getsource(globals()[name]).encode())
    return h.hexdigest()


def cache_path(args):
    return Path(args.work) / "t8d-triggers.pkl"


def build_or_load(args):
    """The trigger stage is minutes of element arithmetic; cache it so the
    analysis can be re-run without repeating it. The cache is keyed on the
    tool's own sha256, so a changed instrument can never be analysed against
    a stale table."""
    import pickle
    path = cache_path(args)
    me = feature_path_sha256()
    if path.exists() and not args.rebuild:
        with open(path, "rb") as fh:
            blob = pickle.load(fh)
        if blob.get("featurePathSha256") == me:
            print(f"  reusing the cached trigger table ({path}), "
                  f"feature path {me[:12]}", flush=True)
            bundle = blob["bundle"]
            bundle["featurePathSha256"] = me
            return bundle
        print("  the cache was built by a different feature path; rebuilding",
              flush=True)
    bundle = build_trigger_table(args)
    bundle["featurePathSha256"] = me
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh:
        pickle.dump({"featurePathSha256": me, "bundle": bundle}, fh)
    return bundle


def station_proxy_audit(triggers, series_by_norad):
    """prereg 3.3 -- the causal eligibility proxy against T8a's own
    (non-causal) `station_segments`. A finding, not a correction."""
    cells = {"bothStationed": 0, "proxyOnly": 0, "segmentOnly": 0, "neither": 0}
    proxy, truth = [], []
    cache = {}
    for tr in triggers:
        s = series_by_norad[tr.norad]
        if tr.norad not in cache:
            g = ap.attach_grid(s)
            cache[tr.norad] = pg.station_segments(g)
        segs = cache[tr.norad]
        day = int(tr.tTrig // int(DAY_MS)) - int(s.grid_lo)
        in_seg = any(i0 <= day <= i1 for i0, i1 in segs)
        proxy.append(bool(tr.eligible))
        truth.append(bool(in_seg))
        if tr.eligible and in_seg:
            cells["bothStationed"] += 1
        elif tr.eligible:
            cells["proxyOnly"] += 1
        elif in_seg:
            cells["segmentOnly"] += 1
        else:
            cells["neither"] += 1
    cells["kappa"] = cohens_kappa(proxy, truth)
    cells["note"] = ("T8a's station_segments is computed on a daily grid "
                     "interpolated from element sets on BOTH sides of the "
                     "trigger and is therefore not available to an alarm; the "
                     "proxy of prereg 3.3 is. This table is the disagreement, "
                     "reported and repairing nothing.")
    return cells


def analyze(bundle):
    """Stage `analyze` -- prereg 5, 6, 8, 11."""
    triggers = bundle["triggers"]
    feats = bundle["features"]
    outs = bundle["outcomes"]
    events = bundle["events"]

    idx_all = list(range(len(triggers)))
    idx_res = [i for i in idx_all if outs[i]["resolvable"]]
    idx_pri = [i for i in idx_res if triggers[i].eligible]

    result = {
        "schema": 1, "registration": REGISTRATION,
        "featureNames": list(FEATURE_NAMES),
        "population": {
            "triggers": len(triggers),
            "approachers": len({t.norad for t in triggers}),
            "eligible": int(sum(1 for t in triggers if t.eligible)),
            "resolvable": len(idx_res),
            "primaryArm": len(idx_pri),
            "primaryApproachers": len({triggers[i].norad for i in idx_pri}),
            "unresolvableNotAssessable": len(idx_all) - len(idx_res),
        },
        "stationProxy": bundle["stationProxy"],
        "propagator": bundle["propagator"],
    }

    def _counts(idx):
        o1 = [outs[i] for i in idx]
        pos = [o for o in o1 if o["o1Positive"]]
        pos_pos = [o for o in pos if o["o1ArrivalDays"] is not None
                   and o["o1ArrivalDays"] > 0]
        o2pos = [o for o in o1 if o["o2Positive"]]
        k, n = len(pos_pos), len(idx)
        lo, hi = wilson(k, n)
        k_all, _ = len(pos), n
        lo_a, hi_a = wilson(k_all, n)
        lo2, hi2 = wilson(len(o2pos), n)
        return {
            "n": n,
            "o1PositivesArrivalAfterAnnounce": k,
            "o1PrecisionDpositive": (k / n) if n else None,
            "wilson95": [lo, hi],
            "o1PositivesAll": k_all,
            "o1PrecisionAll": (k_all / n) if n else None,
            "wilson95All": [lo_a, hi_a],
            "arrivedBeforeAnnounce": k_all - k,
            "o2Positives": len(o2pos),
            "o2Precision": (len(o2pos) / n) if n else None,
            "o2Wilson95": [lo2, hi2],
            "arrivalDays": percentiles([o["o1ArrivalDays"] for o in pos_pos]),
        }

    result["precision"] = {"primaryArm": _counts(idx_pri),
                           "allResolvableTriggers": _counts(idx_res)}
    result["precisionNote"] = (
        "prereg 3.6: this denominator is the FLAG CHAIN, which is what an "
        "alarm sees. T8a's 32.8% has a different denominator -- 1,483 "
        "relocation alerts, each a >=2 deg segment-to-segment move containing "
        "a flag. The two numbers are NOT comparable.")

    # ---- prereg 5: the taxonomy -----------------------------------------
    sub_feats = [feats[i] for i in idx_pri]
    sub_outs = [outs[i] for i in idx_pri]
    sub_objs = np.asarray([triggers[i].norad for i in idx_pri], dtype=np.int64)
    matrix = feature_matrix(sub_feats)
    result["missingFraction"] = {n: float(np.mean(~np.isfinite(matrix[:, j])))
                                 for j, n in enumerate(FEATURE_NAMES)}
    print(f"  clustering {matrix.shape[0]} primary-arm triggers ...", flush=True)
    t_k = time.time()
    k, labels, _centres, _x, sweep, _sc = choose_k_by_silhouette(matrix, FEATURE_NAMES)
    print(f"  k={k} chosen in {time.time() - t_k:.1f}s", flush=True)
    result["kSweep"], result["kChosen"] = sweep, int(k)
    result["clusterSizes"] = [int((labels == c).sum()) for c in range(k)]
    t_s = time.time()
    _bl, jaccard = ap.bootstrap_stability(matrix, FEATURE_NAMES, sub_objs, k)
    print(f"  stability in {time.time() - t_s:.1f}s", flush=True)
    result["stabilityJaccard"] = jaccard
    y = np.asarray([1.0 if (o["o1Positive"] and o["o1ArrivalDays"] is not None
                            and o["o1ArrivalDays"] > 0) else 0.0
                    for o in sub_outs])
    result["classes"] = describe_classes(sub_feats, labels, sub_outs, k)
    cadence_split = np.asarray([1 if f["cad_prior_triggers"] >= 1 else 0
                                for f in sub_feats])
    result["ariCadenceSplit"] = ap.adjusted_rand(labels, cadence_split)
    result["eta2Arrival"] = ap.eta_squared(y, labels)

    # ---- prereg 6.3: skill_A --------------------------------------------
    t0 = time.time()
    n_obj = int(np.unique(sub_objs).size)
    n_folds = CV_FOLDS if n_obj > CV_FOLDS else 0
    print(f"  object-disjoint folds over {n_obj} approachers "
          f"({n_folds or n_obj} folds) ...", flush=True)
    assigned, folds = fold_assignments(matrix, FEATURE_NAMES, sub_objs, k,
                                       n_folds=n_folds)
    result["foldSeconds"] = time.time() - t0
    result["foldProtocol"] = {
        "folds": len(folds), "approachers": n_obj,
        "leaveOneObjectOut": bool(n_folds == 0),
        "deviation": ("D1b -- grouped K-fold over approachers instead of "
                      "leave-one-object-out; see the results document") if n_folds
                     else "as registered: leave-one-object-out"}
    print(f"  folds in {result['foldSeconds']:.1f}s", flush=True)
    result["skill_A"] = skill_arrival(assigned, folds, sub_objs, y, k)
    print(f"  skill_A = {result['skill_A'].get('skill')}", flush=True)

    # gate W: if the propagator is unfit, refit without the forward block
    prop_p50 = bundle["propagator"].get("p50")
    gate_w = bool(prop_p50 is not None and prop_p50 > GATE_W_DEG)
    print("  the same measurement without the forward-geometry block ...",
          flush=True)
    reduced_names = tuple(n for n in FEATURE_NAMES if not n.startswith("fwd_"))
    ridx = [FEATURE_NAMES.index(n) for n in reduced_names]
    rassigned, rfolds = fold_assignments(matrix[:, ridx], reduced_names,
                                         sub_objs, k, n_folds=n_folds)
    result["withoutForwardBlock"] = {
        "kUsed": int(k),
        "skill_A": skill_arrival(rassigned, rfolds, sub_objs, y, k),
        "note": ("the same measurement with features 15-19 removed and the "
                 "SAME k, so a reader can see what the forward-geometry "
                 "block buys; the k sweep is not repeated, which is stated "
                 "rather than hidden"),
    }

    # ---- prereg 8.1: M2-A, the out-of-sample arm -------------------------
    print("  M2-A ...", flush=True)
    result["M2_A_arrival"] = m2_arrival(
        [triggers[i] for i in idx_pri], sub_outs, assigned, folds,
        sub_objs, y, k)

    # ---- prereg 8.3: M2-D, days to arrival ------------------------------
    print("  M2-D ...", flush=True)
    result["M2_D_days"] = m2_days(sub_feats, sub_outs, sub_objs, assigned, folds)

    # ---- prereg 8.2: M2-L, loiter on T8c's committed table ---------------
    print("  M2-L on T8c's committed table ...", flush=True)
    result["M2_L_loiter"] = m2_loiter()

    # ---- POST-REGISTRATION diagnostic, labelled as such ------------------
    result["postRegistration"] = {
        "POST_REGISTRATION": True,
        "note": ("Added at measurement time in the manner of T8a 7.4, T8b 7.3 "
                 "and T8c 6. These are not registered estimands, they change "
                 "no verdict, and no gate reads them."),
        "precisionByFeatureDecile": {
            name: decile_precision(sub_feats, y, name)
            for name in ("trig_drift_abs", "fwd_slots_reached",
                         "init_drift_change_mag", "ctx_nearest_occupied_deg",
                         "fwd_days_to_first_slot")},
        "causalRelocationScreen": causal_relocation_screen(
            sub_feats, sub_outs, y),
    }

    # ---- prereg 11: the gates -------------------------------------------
    gate_b, spread, widest = _gate_b(result["classes"])
    sa = result["skill_A"]
    sa_lo = (sa.get("ci95") or [None, None])[0]
    hyb = (result["M2_L_loiter"].get("registered_causal", {})
           .get("HYB", {}).get("skill"))
    strata = (result["M2_A_arrival"]["registered"]["P1_own"]
              .get("byPriorCount", []))
    threshold = None
    for row in strata:
        lo = (row.get("ci95") or [None, None])[0]
        if (lo is not None and lo > 0 and row.get("n", 0) >= MIN_STRATUM_PREDICTIONS):
            threshold = row["priorCount"]
            break
    result["priorEventThreshold"] = threshold
    result["gates"] = {
        "A": bool(len(idx_pri) < GATE_A_MIN_TRIGGERS
                  or result["precision"]["primaryArm"]
                  ["o1PositivesArrivalAfterAnnounce"] < GATE_A_MIN_POSITIVES),
        "B": bool(gate_b),
        "C": bool(sa_lo is None or sa_lo <= 0.0),
        "D": bool(min(result["clusterSizes"]) < GATE_D_MIN_CLASS),
        "E": bool(float(np.median(jaccard)) < GATE_E_JACCARD),
        "F": bool(result["ariCadenceSplit"] >= GATE_F_ARI),
        "G": bool(hyb is None or hyb <= GATE_G_BAR),
        "H": bool(threshold is None),
        "W": gate_w,
        "L": False,
    }
    result["gateDetail"] = {
        "B_precisionSpread": spread, "B_widestWilsonWidth": widest,
        "C_skillALowerBound": sa_lo,
        "G_hybridSkill": hyb, "G_bar": GATE_G_BAR,
        "W_propagatorMedianDeg": prop_p50, "W_bar": GATE_W_DEG,
        "L_note": ("gate L is the leakage audit and is discharged by "
                   "tests/test_trigger_alarm.py, which must pass before this "
                   "run is reportable"),
    }
    return result, labels, idx_pri, sub_objs, y


def decile_precision(features, y, name):
    """POST-REGISTRATION. The precision of a ONE-FEATURE screen, by decile.
    A taxonomy that cannot beat a single ordered feature is not earning its
    twenty-two dimensions, and this is the cheapest way to see it."""
    v = np.asarray([f.get(name, np.nan) for f in features], dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    ok = np.isfinite(v)
    if ok.sum() < 100:
        return {"n": int(ok.sum()), "note": "too few finite values"}
    edges = np.percentile(v[ok], np.arange(0, 101, 10))
    rows = []
    for i in range(10):
        lo, hi = edges[i], edges[i + 1]
        m = ok & (v >= lo) & ((v <= hi) if i == 9 else (v < hi))
        n = int(m.sum())
        kpos = int(y[m].sum())
        wl, wh = wilson(kpos, n)
        rows.append({"decile": i + 1, "lo": float(lo), "hi": float(hi),
                     "n": n, "positives": kpos,
                     "precision": (kpos / n) if n else None,
                     "wilson95": [wl, wh]})
    return {"feature": name, "nFinite": int(ok.sum()),
            "nMissing": int((~ok).sum()), "deciles": rows}


def causal_relocation_screen(features, outcomes, y):
    """POST-REGISTRATION. T8a's alert required a >= X_FAR = 2 deg relocation
    to have HAPPENED -- a fact only available afterwards. The causal analogue
    of that requirement, available AT TRIGGER, is that the post-burn drift
    rate could cover 2 deg inside the registered 180-day horizon:

        |ddot| >= X_FAR / H = 2.0 / 180.0 = 0.01111 deg/day

    This is a screen, not a law, and it is derived from two constants T8a
    already registered rather than tuned. Reported because the gap between
    226,422 flag chains and T8a's 1,483 relocation alerts is the single
    biggest thing T8d found, and this is the cheapest honest bridge across
    it.
    """
    bar = pg.X_FAR_DEG / H_DAYS
    v = np.asarray([f.get("trig_drift_abs", np.nan) for f in features])
    y = np.asarray(y, dtype=np.float64)
    m = np.isfinite(v) & (v >= bar)
    n, kpos = int(m.sum()), int(y[m].sum())
    lo, hi = wilson(kpos, n)
    days = [o["o1ArrivalDays"] for o, keep in zip(outcomes, m)
            if keep and o["o1Positive"] and o["o1ArrivalDays"] is not None
            and o["o1ArrivalDays"] > 0]
    return {"barDegPerDay": float(bar), "n": n, "positives": kpos,
            "precision": (kpos / n) if n else None, "wilson95": [lo, hi],
            "arrivalDays": percentiles(days),
            "excluded": int((~m).sum()),
            "positivesExcluded": int(y[~m].sum())}


def m2_days(sub_feats, sub_outs, sub_objs, assigned, folds):
    """prereg 8.3 -- log days-to-arrival for positive triggers, OWN vs CLS vs
    the 0.5/0.5 hybrid, leave-one-OBJECT-out against the population median."""
    idx = [i for i, o in enumerate(sub_outs)
           if o["o1Positive"] and o["o1ArrivalDays"] is not None
           and o["o1ArrivalDays"] > 0]
    if len(idx) < 10:
        return {"n": len(idx), "skill": None,
                "note": "fewer than 10 positives; not computed"}
    vals = {i: math.log(sub_outs[i]["o1ArrivalDays"]) for i in idx}
    pop = float(np.median(list(vals.values())))
    by_obj = {}
    for i in idx:
        by_obj.setdefault(int(sub_objs[i]), []).append(i)
    bags = {"OWN": [], "CLS": [], "HYB": []}
    pop_e, grp = [], []
    for fold in folds.values():
        train, labels_tr = fold["train"], fold["labelsTrain"]
        # the class pools, taken from this fold's TRAINING rows only
        tr_pos = [p for p, j in enumerate(train.tolist()) if j in vals]
        pools = {}
        for p in tr_pos:
            pools.setdefault(int(labels_tr[p]), []).append(vals[int(train[p])])
        held_objs = {int(sub_objs[i]) for i in fold["held"]}
        for norad in held_objs:
            mine = [i for i in by_obj.get(int(norad), []) if i in set(fold["held"].tolist())]
            if len(mine) < 2:
                continue
            for i in mine:
                others = [vals[j] for j in mine if j != i]
                if not others:
                    continue
                c = int(assigned[i])
                pool = pools.get(c)
                if not pool:
                    continue
                own = float(np.median(others))
                cls = float(np.median(pool))
                bags["OWN"].append(abs(vals[i] - own))
                bags["CLS"].append(abs(vals[i] - cls))
                bags["HYB"].append(abs(vals[i] - (HYBRID_WEIGHT * cls
                                                  + (1 - HYBRID_WEIGHT) * own)))
                pop_e.append(abs(vals[i] - pop))
                grp.append(int(norad))
    if not pop_e:
        return {"n": 0, "skill": None, "note": "no object had two positives"}
    out = {"populationDays": percentiles([sub_outs[i]["o1ArrivalDays"] for i in idx])}
    for name, err in bags.items():
        lo, hi = ap.bootstrap_skill(err, pop_e, grp)
        out[name] = {"n": len(err),
                     "skill": float(1.0 - np.mean(err) / np.mean(pop_e)),
                     "maeModelLog": float(np.mean(err)),
                     "maePopulationLog": float(np.mean(pop_e)),
                     "ci95": [lo, hi], "objects": int(len(set(grp)))}
    return out


def m2_loiter():
    """prereg 8.2 -- the registered re-test of T8c's D2 on T8c's committed
    487-event table.

    DECLARED IN THE REGISTRATION AND REPEATED HERE: this arm is NOT out of
    sample. D2 was computed on this same table and generated this hypothesis.
    What is new is that the rule, the weight, the protocol and the bar were
    fixed before the run. The arm that can generalise is M2-A.
    """
    provenance, rows = None, []
    with open(T8C_FEATURES_PATH) as fh:
        for line in fh:
            rec = json.loads(line)
            if rec.get("record") == "provenance":
                provenance = rec
                continue
            rows.append(rec)
    rows.sort(key=lambda r: (r["approacherNorad"], r["arrivalIso"], r["targetNorad"]))
    objects = np.asarray([r["approacherNorad"] for r in rows], dtype=np.int64)
    full = np.asarray([[r.get(n, float("nan")) for n in ap.FEATURE_NAMES]
                       for r in rows], dtype=np.float64)
    vals = np.asarray([math.log(r["loiterDays"]) if r["loiterDays"] > 0 else np.nan
                       for r in rows])
    order_key = {i: rows[i]["arrivalIso"] for i in range(len(rows))}
    holder = {"order": [order_key[i] for i in range(len(rows))]}
    out = {"n": len(rows), "kFull": provenance["kChosen"],
           "kCausal": provenance["causalKChosen"],
           "notOutOfSample": True,
           "note": ("prereg 8.2: D2 was computed on this same table, so a "
                    "number near +0.206 here confirms nothing about "
                    "generalisation. M2-A is the arm that can.")}
    # the registered headline: T8c's CAUSAL taxonomy
    cidx = [ap.FEATURE_NAMES.index(n) for n in ap.CAUSAL_FEATURES]
    ck = int(provenance["causalKChosen"])
    cfolds = ap.fold_models(full[:, cidx], ap.CAUSAL_FEATURES, objects, ck)
    out["registered_causal"] = hybrid_mae_skill(vals, cfolds, objects, holder,
                                                ck, HYBRID_WEIGHT)
    out["weightCurve_causal"] = {
        f"w={w:g}": hybrid_mae_skill(vals, cfolds, objects, holder, ck, w)["HYB"]
        for w in WEIGHT_CURVE}
    # reported beside it: D2's own setup, the FULL 37-feature taxonomy
    k = int(provenance["kChosen"])
    folds = ap.fold_models(full, ap.FEATURE_NAMES, objects, k)
    out["reported_fullTaxonomy"] = hybrid_mae_skill(vals, folds, objects, holder,
                                                    k, HYBRID_WEIGHT)
    # prereg 8.4 -- the prior-event stratification for the loiter arm
    out["byPriorCount_causal"] = _loiter_strata(vals, cfolds, objects, holder, ck)
    return out


def _loiter_strata(vals, folds, objects, holder, k):
    """prereg 8.4 for M2-L: the OWN predictor's skill by the number of the
    object's strictly prior events."""
    rows = []
    for lo, hi in PRIOR_STRATA:
        own_e, pop_e, grp = [], [], []
        finite = vals[np.isfinite(vals)]
        pop_median = float(np.median(finite))
        for norad, fold in folds.items():
            held = fold["held"]
            if held.size < 2:
                continue
            order = sorted(range(held.size), key=lambda j: holder["order"][held[j]])
            for pos, j in enumerate(order):
                i = int(held[j])
                if not np.isfinite(vals[i]):
                    continue
                n_prior = pos
                if not (lo <= n_prior <= hi):
                    continue
                peers = [vals[int(held[p])] for p in order[:pos]]
                peers = [v for v in peers if np.isfinite(v)]
                if not peers:
                    continue
                own_e.append(abs(vals[i] - float(np.median(peers))))
                pop_e.append(abs(vals[i] - pop_median))
                grp.append(int(norad))
        label = f"{lo}" if lo == hi else f">={lo}"
        if not own_e:
            rows.append({"priorCount": label, "n": 0, "skill": None})
            continue
        ci = ap.bootstrap_skill(own_e, pop_e, grp)
        rows.append({"priorCount": label, "n": len(own_e),
                     "skill": float(1.0 - np.mean(own_e) / np.mean(pop_e)),
                     "ci95": list(ci), "objects": int(len(set(grp)))})
    return rows


TABLE_SAMPLE = 5000            # rows of the committed subset beyond the positives


def _table_row(i, tr, f, o, cluster):
    """One row: the NORAD, the trigger's three epochs, the registered
    features, the class and the outcome -- and no catalogue metadata column
    of any kind. Floats are written to 10 significant digits, which is more
    than the element sets carry."""
    def r(v):
        if v is None or not np.isfinite(v):
            return None
        return float(f"{float(v):.10g}")
    row = {"approacherNorad": tr.norad,
           "tFirstIso": _iso(tr.tFirst), "tTrigIso": _iso(tr.tTrig),
           "tAnnounceIso": _iso(tr.tAnnounce),
           "eligible": bool(tr.eligible),
           "resolvable": bool(o["resolvable"]),
           "cluster": cluster}
    row.update({n: r(f.get(n)) for n in FEATURE_NAMES})
    row.update({"o1Positive": o["o1Positive"],
                "o1ArrivalDays": r(o["o1ArrivalDays"]),
                "o1TargetNorad": o["o1TargetNorad"],
                "o2Positive": o["o2Positive"],
                "o2ArrivalDays": r(o["o2ArrivalDays"])})
    return row


def write_tables(args, bundle, result, labels, idx_pri):
    """The full per-trigger table beside the run, and a BOUNDED subset beside
    the receipt.

    The full table is 226,422 rows and 241 MB. This repository is a
    teaching-aid source tree, not an archive, so what is COMMITTED is:

        every row positive under O1 or O2 (either arm), plus a uniform
        random sample of TABLE_SAMPLE of the remaining rows, drawn with
        `np.random.default_rng(20260922)`

    and the full table's row count and sha256 are recorded here so that the
    committed subset can be checked against it. The sampling rule reads no
    feature and no class -- only the outcome, which is what makes the
    positives complete rather than sampled.
    """
    triggers, feats, outs = bundle["triggers"], bundle["features"], bundle["outcomes"]
    cluster_of = {int(i): int(labels[p]) for p, i in enumerate(idx_pri)}
    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    full = work / f"trigger-alarm-triggers-{args.date}-FULL.jsonl"
    prov = {
        "schema": 1, "record": "provenance", "study": "T8d trigger-time predictor",
        "registration": REGISTRATION,
        "note": ("One row per flag chain of prereg 3.1. Every feature is a "
                 "function of element sets with epoch <= tTrig (prereg 12). "
                 "`cluster` is the prereg 5 taxonomy and is present only on "
                 "primary-arm resolvable rows. Separations are MEAN LONGITUDE "
                 "separations, slot coordinates -- not miss distances "
                 "(T8a 1.1). No catalogue metadata column is carried on any "
                 "row."),
        "kChosen": result["kChosen"], "triggerCount": len(triggers)}
    with open(full, "w") as fh:
        fh.write(json.dumps(dict(prov, subset=False)) + "\n")
        for i, (tr, f, o) in enumerate(zip(triggers, feats, outs)):
            fh.write(json.dumps(_table_row(i, tr, f, o, cluster_of.get(i))) + "\n")
    full_sha = sha256_file(full)

    keep = [i for i, o in enumerate(outs) if o["o1Positive"] or o["o2Positive"]]
    rest = np.setdiff1d(np.arange(len(triggers)), np.asarray(keep, dtype=np.int64))
    rng = np.random.default_rng(SEED)
    take = rng.choice(rest, size=min(TABLE_SAMPLE, rest.size), replace=False)
    chosen = sorted(set(keep) | set(int(v) for v in take))
    args.out.mkdir(parents=True, exist_ok=True)
    subset = args.out / f"trigger-alarm-triggers-{args.date}.jsonl"
    meta = dict(prov, subset=True, subsetRows=len(chosen),
                subsetPositives=len(keep), subsetSampledOthers=int(take.size),
                subsetRule=("every O1- or O2-positive row, plus a uniform "
                            "random sample of the rest, seed 20260922"),
                fullTableRows=len(triggers), fullTableSha256=full_sha,
                fullTablePath=str(full), fullTableBytes=full.stat().st_size)
    with open(subset, "w") as fh:
        fh.write(json.dumps(meta) + "\n")
        for i in chosen:
            fh.write(json.dumps(
                _table_row(i, triggers[i], feats[i], outs[i],
                           cluster_of.get(i))) + "\n")
    meta["subsetSha256"] = sha256_file(subset)
    print(f"  tables: full {len(triggers)} rows -> {full} ({full_sha[:12]}); "
          f"committed subset {len(chosen)} rows", flush=True)
    return meta


# ==========================================================================
def main(argv=None):
    parser = argparse.ArgumentParser(description="T8d trigger-time predictor")
    parser.add_argument("--out", type=Path, default=_REPO / "docs")
    parser.add_argument("--date", default="20260922")
    parser.add_argument("--stage", choices=("triggers", "all"), default="all")
    parser.add_argument("--work", type=Path, required=True,
                        help="working directory for the cached trigger population")
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args(argv)
    started, cpu0 = time.time(), time.process_time()

    print("T8d: building the trigger population ...", flush=True)
    bundle = build_or_load(args)
    print(f"  {len(bundle['triggers'])} triggers "
          f"({sum(1 for t in bundle['triggers'] if t.eligible)} eligible) in "
          f"{bundle['seconds']['triggers'] + bundle['seconds']['features']:.1f}s",
          flush=True)
    if args.stage == "triggers":
        return bundle

    print("T8d: taxonomy, M1, M2 ...", flush=True)
    result, labels, idx_pri, sub_objs, y = analyze(bundle)
    wall = time.time() - started

    result.update({
        "measuredAt": datetime.now(timezone.utc).isoformat(),
        "host": os.uname().nodename, "executionMode": "cpu",
        "wallSeconds": wall, "cpuSeconds": time.process_time() - cpu0,
        "gpuConsidered": bool(wall > 600.0),
        "sigma_n_deg_per_day": bundle["sigma_n"],
        "extract": bundle["extractMeta"],
        "seconds": bundle["seconds"],
        "sourceSha256": {
            "tools/trigger_alarm.py": sha256_file(Path(__file__)),
            "tools/alarm_pattern.py": sha256_file(_REPO / "tools" / "alarm_pattern.py"),
            "tools/proximity_geo.py": sha256_file(_REPO / "tools" / "proximity_geo.py"),
            "docs/proximity-events-20260922.jsonl": sha256_file(EVENTS_PATH),
            "docs/alarm-pattern-features-20260922.jsonl": sha256_file(T8C_FEATURES_PATH),
            REGISTRATION: sha256_file(_REPO / REGISTRATION)},
    })

    table_meta = write_tables(args, bundle, result, labels, idx_pri)
    result["triggerTable"] = table_meta

    args.out.mkdir(parents=True, exist_ok=True)
    receipt = args.out / f"trigger-alarm-{args.date}-receipt.json"
    receipt.write_text(json.dumps(result, indent=1, default=float))

    fired = [g for g, v in result["gates"].items() if v]
    print(f"  k={result['kChosen']}  primary arm={result['population']['primaryArm']}"
          f"  precision={result['precision']['primaryArm']['o1PrecisionDpositive']}"
          f"  skill_A={result['skill_A'].get('skill')}", flush=True)
    print(f"  gates FIRED: {fired or 'none'}   wall {wall:.1f}s", flush=True)
    return result


if __name__ == "__main__":
    main()
