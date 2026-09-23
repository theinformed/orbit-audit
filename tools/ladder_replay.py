#!/usr/bin/env python3
"""M3 -- the sequential precision ladder, calibrated on the archive.

The registration is `docs/m3-ladder-replay-preregistration-20260923.md`,
committed ALONE before this file existed; the ordering in `git log` is the
evidence. Nothing here changes a threshold, a stage rule, a horizon, a control
or a gate that document fixed.

WHAT THIS IS. The reach design asks whether the burns that FOLLOW a first
confirmed change carry information the first does not. The construction is a
ladder of measured precisions per stage, not a posterior: each rung is a k/n
over every historical sequence that reached it, with the same denominator
discipline the single-burn measurement already uses. This driver replays the
ladder over a historical window with an INJECTED CLOCK, at the derived cadence,
reusing the alarm lane's own machinery rather than building a second one.

WHAT IT CANNOT DO, said plainly: the frozen partition was fitted on the whole
1959-2026 primary arm, which CONTAINS the near-geosynchronous window, so every
precision measured here is IN SAMPLE for the taxonomy. And the recall of the
initiating flag is UNMEASURED: a sequence that never opened cannot be counted.

NOTHING IS SCHEDULED. No timer and no cron entry is installed by this module,
nothing it writes reaches any site surface, and no handle it opens is
writable.

    python3 tools/ladder_replay.py --arms geo,leo --out docs
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

import proximity_geo as pg            # noqa: E402
import proximity_plane as pp          # noqa: E402
import trigger_alarm as ta            # noqa: E402
import alarm_lane as al               # noqa: E402
import alarm_lane_leo as alleo        # noqa: E402

DAY_MS = pg.DAY_MS
REGISTRATION = "docs/m3-ladder-replay-preregistration-20260923.md"
DESIGN = "docs/kinematic-reach-design-20260922.md"
SEED = ta.SEED                                    # 20260922, registration 5(c)
SHUFFLE_DRAWS = 200                               # registration 5(c)
MIN_SUPPORT = al.MIN_SUPPORT_FOR_A_RATE           # 20, "UNDERPOWERED"

# -- registration section 3, the two horizons -------------------------------
GEO_H_R_DAYS = 20.0          # membership, the forward-error measurement's cut
GEO_H_R_SECOND_DAYS = 180.0  # the arm the committed operating table uses
GEO_H_O_DAYS = ta.H_DAYS     # 180.0, the outcome horizon, the lane's own
GEO_H_O_SENSITIVITY_DAYS = 90.0
LEO_H_R_DAYS = 90.0
LEO_H_R_SECOND_DAYS = 1095.0
LEO_H_O_DAYS = pp.T_LOOK_DAYS   # 1095.0

# -- registration section 2.3, the deceleration rule ------------------------
DECEL_SETS = 3                          # three element sets, two decreases
DECEL_START_FLOOR = ta.SLOT_DRIFT_FLOOR / 2.0   # 0.010 deg/day, the flag floor
LEO_DA_FLOOR_KM = 0.050                 # the in-track channel's own floor
LEO_PLANE_TOL_DEG = 0.2                 # T8b theta_p
LEO_STALE_DAYS = 5.0                    # an element set older than this is not
                                        # a current state; IMPLEMENTATION, and
                                        # it is declared in the results

# -- registration section 6.3: the sentence that travels with every GEO rung
GEO_LEAK = {
    "chains": 3812,
    "objectDays": 517391,
    "ratio": 0.288,
    "wilson95": [0.279, 0.298],
    "bar": 0.10,
    "source": "docs/geo-libration-epoch-control-results-20260922.md",
    "sentence": (
        "The GEO catalogues remain uncontrolled. This trigger fires 3,812 "
        "times inside 517,391 days of provably uncontrolled motion -- 0.288 "
        "[0.279, 0.298] of the rate it fires on objects that can manoeuvre, "
        "against a bar of 0.10. A rung precision measured here is a property "
        "of this detector on this catalogue, not a rate at which objects of a "
        "class do anything."),
}

IN_SAMPLE_NOTE = (
    "The frozen partition was fitted on the whole 1959-2026 primary arm, "
    "which contains this window, so every precision measured here is IN "
    "SAMPLE for the taxonomy.")

STRUCTURAL_CAVEATS = tuple(al.CAVEATS)

STAGES = ("S1", "S2", "S3", "S4")


def _iso(ms):
    return al._iso(ms)


def percentiles(values, ps=(5, 25, 50, 75, 95)):
    v = np.asarray([x for x in values if x is not None and np.isfinite(x)],
                   dtype=np.float64)
    if v.size == 0:
        return {"n": 0,
                "label": "NOT ASSESSABLE -- no values; a labelled gap, not a zero"}
    return {"n": int(v.size),
            **{f"p{p}": float(np.percentile(v, p)) for p in ps}}


def rate_row(k, n, label=""):
    """k/n with Wilson 95%, the power rule applied. A labelled gap is never a
    zero and fewer than twenty resolutions is UNDERPOWERED in those words."""
    if n == 0:
        return {"k": 0, "n": 0, "precision": None, "wilson95": [None, None],
                "underpowered": True,
                "label": ("NOT ASSESSABLE -- nothing of this kind has resolved; "
                          "a labelled gap, not a zero")}
    lo, hi = ta.wilson(k, n)
    row = {"k": int(k), "n": int(n), "precision": float(k) / float(n),
           "wilson95": [float(lo), float(hi)],
           "underpowered": bool(n < MIN_SUPPORT)}
    if row["underpowered"]:
        row["label"] = (f"UNDERPOWERED -- {k}/{n} resolved, below {MIN_SUPPORT}; "
                        f"the count is quoted and no rate is drawn from it")
    elif k == 0:
        # a MEASURED zero is not a labelled gap and not a rate: it is a
        # bound, and it is printed as one
        row["label"] = (f"0 of {n} resolved; nothing arrived, and the 95% "
                        f"upper bound is {100.0 * hi:.3f}%")
    else:
        row["label"] = f"{k}/{n} = {100.0 * k / n:.3f}%"
    if label:
        row["of"] = label
    return row


def km_median(durations, events, look_back_days=al.LOOK_BACK_FLOOR_DAYS):
    """Kaplan-Meier quantiles with the censoring reported. `durations` are days
    to arrival or to the censoring epoch; `events` is 1 for an arrival."""
    d = np.asarray(durations, dtype=np.float64)
    e = np.asarray(events, dtype=np.int64)
    ok = np.isfinite(d)
    d, e = d[ok], e[ok]
    if d.size == 0:
        return {"n": 0, "label": "NOT ASSESSABLE -- no episodes; a labelled gap"}
    order = np.argsort(d, kind="stable")
    d, e = d[order], e[order]
    n_at_risk = d.size
    surv = 1.0
    curve = []
    i = 0
    while i < d.size:
        j = i
        while j < d.size and d[j] == d[i]:
            j += 1
        deaths = int(e[i:j].sum())
        if deaths:
            surv *= (1.0 - deaths / float(n_at_risk))
            curve.append((float(d[i]), surv))
        n_at_risk -= (j - i)
        i = j

    def q(p):
        for t, s in curve:
            if s <= 1.0 - p:
                return float(t)
        return None

    return {"n": int(d.size), "events": int(e.sum()),
            "censored": int(d.size - e.sum()),
            "p25": q(0.25), "p50": q(0.50), "p75": q(0.75),
            "lookBackFloorDays": float(look_back_days),
            "label": ("Kaplan-Meier over every episode that reached the rung; "
                      "an unreached quantile is null, never the largest "
                      "observed time")}


# ==========================================================================
# The occupancy table, with the members it is made of
# ==========================================================================
class MemberSweep(ta.OccupancySweep):
    """`trigger_alarm.OccupancySweep`, which returns the occupied longitudes,
    plus the NORADs and drift rates behind them -- the ladder needs to know
    WHICH objects a set is made of and where each one will be when a stop is
    propagated. The state machine is the parent's: advanced only with element
    sets whose epoch is at or before the query, so the table can never contain
    the future. `at_members` reproduces `at` exactly on the same call and a
    test asserts it."""

    def at_members(self, t_ms, exclude_norad):
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
              & ((t_ms - self.cur_ep) <= ta.MERGE_DAYS * DAY_MS)
              & (self.first <= t_ms - ta.SLOT_MIN_HISTORY_DAYS * DAY_MS)
              & (np.abs(self.cur_drift) <= ta.SLOT_DRIFT_FLOOR))
        e = self.index.get(int(exclude_norad))
        if e is not None:
            ok[e] = False
        idx = np.where(ok)[0]
        lons = pg.wrap180(self.cur_lam[idx]
                          + self.cur_drift[idx] * (t_ms - self.cur_ep[idx]) / DAY_MS)
        return (self.norads[idx], lons, self.cur_inc[idx],
                self.cur_drift[idx], self.cur_ep[idx])


def propagate_decel(lam0_deg, drift0_deg_per_day, decel_deg_per_day2,
                    horizon_days, step_days=ta.PROP_STEP_DAYS):
    """The registration's section 2.3 stop: `trigger_alarm.propagate`'s RK4 on
    (lambda, lambda-dot) with a CONSTANT extra acceleration added to the
    tesseral term -- the deceleration the three newest element sets measure.
    With `decel = 0` this is `trigger_alarm.propagate` exactly, and a test
    asserts that identity rather than assuming it."""
    n = int(round(horizon_days / step_days))
    lam = np.empty(n + 1, dtype=np.float64)
    lam[0] = float(lam0_deg)
    x, v, h = float(lam0_deg), float(drift0_deg_per_day), float(step_days)
    c = float(decel_deg_per_day2)

    def acc(u):
        return ta._lam_ddot(u) + c

    for i in range(1, n + 1):
        k1x, k1v = v, acc(x)
        k2x, k2v = v + 0.5 * h * k1v, acc(x + 0.5 * h * k1x)
        k3x, k3v = v + 0.5 * h * k2v, acc(x + 0.5 * h * k2x)
        k4x, k4v = v + h * k3v, acc(x + h * k3x)
        x = x + (h / 6.0) * (k1x + 2.0 * k2x + 2.0 * k3x + k4x)
        v = v + (h / 6.0) * (k1v + 2.0 * k2v + 2.0 * k3v + k4v)
        lam[i] = x
    return lam


def decel_fit(epoch_ms, drift):
    """The registration's section 2.3 clauses 1-3 on the three newest element
    sets: decelerating across two successive sets, starting above the flag
    floor, with a least-squares zero-crossing ahead of the newest set.

    Returns `(slope_deg_per_day2, t_stop_ms)` or None."""
    if epoch_ms.size < DECEL_SETS:
        return None
    t = np.asarray(epoch_ms[-DECEL_SETS:], dtype=np.float64)
    d = np.asarray(drift[-DECEL_SETS:], dtype=np.float64)
    if not np.all(np.isfinite(d)):
        return None
    a = np.abs(d)
    if not np.all(np.diff(a) < 0.0):
        return None
    if a[0] < DECEL_START_FLOOR:
        return None
    days = (t - t[-1]) / DAY_MS
    slope, intercept = np.polyfit(days, d, 1)
    if slope == 0.0:
        return None
    t_zero_days = -intercept / slope
    if not (0.0 < t_zero_days):
        return None
    return float(slope), float(t[-1] + t_zero_days * DAY_MS)


# ==========================================================================
# THE GEO ARM
# ==========================================================================
def geo_triggers(source, flags, model, start_ms, end_ms, say):
    """Every confirmed flag chain whose announce falls inside the window, with
    its reachable set at both registered horizons. The occupancy table is
    advanced forward only, so the chains are processed in trigger order and
    the table can never contain the future."""
    classes = source.classes(sorted(source.series_by_norad))
    sweep = MemberSweep(source.series_by_norad)
    sigma_n = float(model["detector"]["sigmaNDegPerDay"])

    chains = []
    for norad, s in source.series_by_norad.items():
        if classes.get(int(norad)) != "active":
            continue
        flag_ms, sizes, bases = flags.flags(s, sigma_n, float(end_ms))
        for t_first, t_trig, stages, size, base in ta.chain_flags(
                flag_ms, sizes, bases):
            chains.append((float(t_trig), int(norad), float(t_first),
                           int(stages), float(size), float(base)))
    chains.sort(key=lambda r: (r[0], r[1]))
    say(f"[geo] {len(chains):,} confirmed flag chains on "
        f"{len(source.series_by_norad):,} watched objects")

    out = []
    feats, keep = [], []
    announce_lo = start_ms
    for t_trig, norad, t_first, stages, size, base in chains:
        trig = ta.Trigger(norad, t_first, t_trig, stages, size, base)
        if trig.tAnnounce < announce_lo or trig.tAnnounce > end_ms:
            # still advance the table so it stays in time order
            sweep.at_members(t_trig, norad)
            continue
        series = source.series(norad, t_trig)
        if series is None:
            continue
        view = ta.causal_view(series, t_trig)
        norads, lons, incs, drifts, eps = sweep.at_members(t_trig, norad)
        rec = {"norad": norad, "tFirstMs": t_first, "tTrigMs": t_trig,
               "tAnnounceMs": float(trig.tAnnounce),
               "stages": stages, "driftChange": size, "driftBase": base,
               "eligible": bool(trig.eligible)}
        gap = _geo_gap_reason(view, trig)
        if gap is not None:
            rec.update({"assessable": False, "gapReason": gap, "class": None})
            out.append(rec)
            continue
        k = int(view.epoch_ms.size - 1)
        lam_now, d_now = float(view.lam[k]), float(view.drift[k])
        rec.update({"assessable": True, "gapReason": None,
                    "lamDeg": lam_now, "driftDegPerDay": d_now,
                    "incDeg": float(view.inc[k]),
                    "stationedObjects": int(norads.size)})
        # ONE propagation. The second horizon's path CONTAINS the governing
        # one step for step -- the RK4 takes the same steps in the same order
        # -- so slicing it is the same arithmetic and not an approximation; a
        # test asserts the identity rather than assuming it.
        path180 = ta.propagate(lam_now, d_now,
                               horizon_days=GEO_H_R_SECOND_DAYS)
        n_gov = int(round(GEO_H_R_DAYS / ta.PROP_STEP_DAYS)) + 1
        for tag, hz, path in (("R", GEO_H_R_DAYS, path180[:n_gov]),
                              ("R2", GEO_H_R_SECOND_DAYS, path180)):
            reached, first_day, _fp, _tot = ta.slots_reached(path, lons)
            sel = np.where(reached)[0]
            d_inc = np.abs(incs[sel] - float(view.inc[k]))
            rec[tag] = {
                "horizonDays": float(hz),
                "members": norads[sel].astype(np.int32),
                "setSize": int(sel.size),
                "setSizePlaneCompatible": int((d_inc <= ta.PLANE_MATCH_DEG).sum()),
                "planeCompatibleMembers": norads[sel][
                    d_inc <= ta.PLANE_MATCH_DEG].astype(np.int32),
                "chanceMembership": (float(sel.size) / float(norads.size)
                                     if norads.size else None),
            }
            if tag == "R":
                rec[tag]["arrivalDays"] = [float(x) for x in first_day[sel]]
                # the member state the stop propagation of section 2.3 needs,
                # from the same causal snapshot and from nowhere later. Only
                # the governing set's members are kept: the set only ever
                # shrinks, so no later rung can need a state this omits.
                rec["_memberState"] = {
                    int(n): (float(lons[i]), float(drifts[i]), float(eps[i]))
                    for i, n in zip(sel, norads[sel])}
        # the trigger-time features the operating-point axes read
        f = ta.trigger_features(trig, view, (lons, incs))
        f.update({"cad_days_since_prev_trigger": float("nan"),
                  "miss_prev_trigger": 1.0, "cad_prior_triggers": 0.0,
                  "cad_prior_events": 0.0, "cad_prior_targets": 0.0})
        rec["fwdSlotsReached180"] = float(f.get("fwd_slots_reached") or 0.0)
        feats.append(f)
        keep.append(rec)
        out.append(rec)
    if feats:
        for rec, cluster in zip(keep, al.classify(feats, model)):
            rec["class"] = int(cluster)
            rec["className"] = al.model_class(model, int(cluster))["name"]
    say(f"[geo] {len(out):,} chains announced inside the window, "
        f"{len(keep):,} assessable")
    return out


def _geo_gap_reason(view, trig):
    """The lane's own labelled-gap rule, imported in substance from
    `alarm_lane.Sidecar._gap_reason` so the ladder's population is the
    population every frozen figure was measured on."""
    ep = np.asarray(view.epoch_ms, dtype=np.float64)
    if ep.size < pg.BURN_BASELINE_SAMPLES + 2:
        return "the look-back holds fewer element sets than the baseline window needs"
    if (float(ep[-1]) - float(ep[0])) / DAY_MS < pg.STATION_MIN_DAYS:
        return (f"the usable look-back is {(float(ep[-1]) - float(ep[0])) / DAY_MS:.1f} d, "
                f"shorter than the {pg.STATION_MIN_DAYS:.0f} d of history the slot "
                f"definition needs")
    window = ep[ep >= trig.tFirst - ta.MERGE_DAYS * DAY_MS]
    if window.size >= 2:
        worst = float(np.max(np.diff(window))) / DAY_MS
        if worst > ta.MERGE_DAYS:
            return (f"an element-set gap of {worst:.1f} d across the trigger, longer "
                    f"than the {ta.MERGE_DAYS:.0f} d merge window")
    if not trig.eligible:
        return ("the object was not at a slot when it moved: its baseline drift rate "
                "is outside the eligibility floor, so this trigger is outside the "
                "population every frozen figure was measured on")
    return None


def snap(t_ms, start_ms, tick_ms):
    """The first tick at or after `t_ms`. Every rung is spoken on a tick, so
    the cadence's own cost is charged to the ladder exactly as the lane
    charges it."""
    if t_ms <= start_ms:
        return float(start_ms)
    return float(start_ms + math.ceil((t_ms - start_ms) / tick_ms) * tick_ms)


def geo_episodes(triggers, source, events, start_ms, end_ms, tick_ms, say):
    """The state machine of registration section 2, per object. A rung is
    entered once per episode; an expiry is counted in every denominator of
    every rung the episode reached; nothing is deleted."""
    by_obj = {}
    for rec in triggers:
        by_obj.setdefault(int(rec["norad"]), []).append(rec)
    ev_by_obj = {}
    record_end = 0.0
    for e in events:
        ev_by_obj.setdefault(int(e["approacherNorad"]), []).append(e)
        record_end = max(record_end, float(e["arrivalMs"]))

    episodes = []
    for norad in sorted(by_obj):
        rows = sorted(by_obj[norad], key=lambda r: r["tTrigMs"])
        series = source.series_by_norad.get(int(norad))
        ep = None
        for rec in rows:
            if not rec.get("assessable"):
                episodes.append({"norad": norad, "notAssessable": True,
                                 "gapReason": rec["gapReason"],
                                 "tTrigMs": rec["tTrigMs"]})
                continue
            if ep is not None:
                # close the open episode at its own horizon before this one
                if rec["tAnnounceMs"] > ep["closeMs"]:
                    _geo_close(ep, series, tick_ms, start_ms)
                    episodes.append(ep)
                    ep = None
            if ep is None:
                ep = _geo_open(rec, tick_ms, start_ms)
                continue
            # --- a further confirmed change while the episode is open ------
            prev = ep["set"]
            new = set(int(x) for x in rec["R"]["members"])
            enlarging = (len(new) > len(prev)) or (not (prev & new))
            if enlarging:
                ep["closedBy"] = "reopened-at-S1"
                _geo_close(ep, series, tick_ms, start_ms)
                episodes.append(ep)
                ep = _geo_open(rec, tick_ms, start_ms)
                continue
            ep["set"] = prev & new
            ep["chains"].append((rec["tFirstMs"], rec["tTrigMs"]))
            ep["closeMs"] = max(ep["closeMs"],
                                rec["tTrigMs"] + GEO_H_O_DAYS * DAY_MS)
            if "S2" not in ep["rungs"]:
                ep["rungs"]["S2"] = {
                    "tTrigMs": rec["tTrigMs"],
                    "announceMs": snap(rec["tAnnounceMs"], start_ms, tick_ms),
                    "announceRuleMs": rec["tAnnounceMs"],
                    "setSize": len(ep["set"]),
                    "setSizePlaneCompatible": _plane_count(rec, ep["set"]),
                    "chanceMembership": rec["R"]["chanceMembership"],
                    "members": sorted(ep["set"]),
                    "setSizeSecondHorizon": len(
                        set(int(x) for x in rec["R2"]["members"])
                        & ep["setSecond"]),
                }
            ep["setSecond"] = ep["setSecond"] & set(
                int(x) for x in rec["R2"]["members"])
            ep["s2count"] += 1
        if ep is not None:
            _geo_close(ep, series, tick_ms, start_ms)
            episodes.append(ep)

    # --- the outcome, by the lane's own rule -------------------------------
    for ep in episodes:
        if ep.get("notAssessable"):
            continue
        _geo_outcome(ep, ev_by_obj.get(int(ep["norad"]), []), record_end)
    say(f"[geo] {len(episodes):,} episodes, "
        f"{sum(1 for e in episodes if not e.get('notAssessable')):,} assessable")
    return episodes, record_end


def _plane_count(rec, members):
    pc = {int(n) for n in rec["R"]["planeCompatibleMembers"]}
    return len(pc & set(members))


def _geo_open(rec, tick_ms, start_ms):
    members = set(int(x) for x in rec["R"]["members"])
    second = set(int(x) for x in rec["R2"]["members"])
    return {
        "norad": int(rec["norad"]),
        "class": rec.get("class"),
        "className": rec.get("className"),
        "openedMs": rec["tTrigMs"],
        "closeMs": rec["tTrigMs"] + GEO_H_O_DAYS * DAY_MS,
        "chains": [(rec["tFirstMs"], rec["tTrigMs"])],
        "set": set(members),
        "setSecond": set(second),
        "r1": sorted(members),
        "r1Empty": not members,
        "r1Second": sorted(second),
        "driftChange": rec["driftChange"],
        "fwdSlotsReached180": rec.get("fwdSlotsReached180"),
        "memberState": rec["_memberState"],
        "lamDeg": rec["lamDeg"], "driftDegPerDay": rec["driftDegPerDay"],
        "s2count": 0,
        "closedBy": None,
        "rungs": {"S1": {
            "tTrigMs": rec["tTrigMs"],
            "announceMs": snap(rec["tAnnounceMs"], start_ms, tick_ms),
            "announceRuleMs": rec["tAnnounceMs"],
            "setSize": rec["R"]["setSize"],
            "setSizePlaneCompatible": rec["R"]["setSizePlaneCompatible"],
            "setSizeSecondHorizon": rec["R2"]["setSize"],
            "chanceMembership": rec["R"]["chanceMembership"],
            "members": sorted(members),
        }},
    }


def _geo_close(ep, series, tick_ms, start_ms):
    """Scan for the S3 rung over the mover's own element sets while the episode
    is open, then close it. Reads only element sets at or before the epoch it
    evaluates."""
    ep.pop("_scanned", None)
    if series is not None and ep["set"]:
        lo = ep["rungs"].get("S2", ep["rungs"]["S1"])["tTrigMs"]
        hi = ep["closeMs"]
        idx = np.where((series.epoch_ms > lo) & (series.epoch_ms <= hi))[0]
        for j in idx:
            fit = decel_fit(series.epoch_ms[:j + 1], series.drift[:j + 1])
            if fit is None:
                continue
            slope, t_stop = fit
            dt_days = (t_stop - float(series.epoch_ms[j])) / DAY_MS
            if not (0.0 < dt_days <= GEO_H_R_DAYS):
                continue
            path = propagate_decel(float(series.lam[j]), float(series.drift[j]),
                                   slope, dt_days)
            lam_stop = float(path[-1])
            hits = []
            for m in sorted(ep["set"]):
                st = ep["memberState"].get(int(m))
                if st is None:
                    continue
                lon, drift_m, ep_m = st
                lon_at = pg.wrap180(lon + drift_m * (t_stop - ep_m) / DAY_MS)
                if abs(float(pg.wrap180(lam_stop - lon_at))) <= pg.X_PRIMARY_DEG:
                    hits.append(int(m))
            if len(hits) == 1:
                t_ann = float(series.epoch_ms[j])
                ep["rungs"]["S3"] = {
                    "tTrigMs": t_ann,
                    "announceMs": snap(t_ann, start_ms, tick_ms),
                    "announceRuleMs": t_ann,
                    "setSize": 1, "setSizePlaneCompatible": None,
                    "setSizeSecondHorizon": 1,
                    "chanceMembership": None,
                    "members": hits,
                    "stopLongitudeDeg": lam_stop,
                    "stopMs": float(t_stop),
                    "decelDegPerDay2": float(slope),
                }
                break
    ep.pop("memberState", None)
    ep["set"] = sorted(ep["set"])
    ep["setSecond"] = sorted(ep["setSecond"])


def _geo_outcome(ep, evs, record_end):
    """The lane's attribution rule, per rung: an event whose initiating flag
    lies inside one of this episode's chains, arriving after the rung's
    announce and inside that rung's own outcome horizon. An arrival before the
    announce warned nobody and is counted as a miss with the reason recorded."""
    matches = [e for e in evs
               if e.get("initiatingFlagMs") is not None
               and any(a <= float(e["initiatingFlagMs"]) <= b
                       for a, b in ep["chains"])]
    ep["attributedEvents"] = len(matches)
    best = min(matches, key=lambda e: float(e["arrivalMs"])) if matches else None
    ep["partnerNorad"] = int(best["targetNorad"]) if best else None
    ep["arrivalMs"] = float(best["arrivalMs"]) if best else None
    # the window-rule pair Gate T needs, over every event of this object
    ep["objectArrivalsMs"] = [float(e["arrivalMs"]) for e in evs]

    for stage, rung in ep["rungs"].items():
        close = float(rung["tTrigMs"]) + GEO_H_O_DAYS * DAY_MS
        after = [e for e in matches
                 if float(e["arrivalMs"]) > float(rung["announceMs"])
                 and float(e["arrivalMs"]) <= close]
        if after:
            b = min(after, key=lambda e: float(e["arrivalMs"]))
            rung["outcome"] = "arrival"
            rung["arrivalMs"] = float(b["arrivalMs"])
            rung["partnerNorad"] = int(b["targetNorad"])
            rung["leadDays"] = (float(b["arrivalMs"])
                                - float(rung["announceMs"])) / DAY_MS
            rung["leadFromRuleDays"] = (float(b["arrivalMs"])
                                        - float(rung["announceRuleMs"])) / DAY_MS
        elif record_end < close:
            rung["outcome"] = "not-assessable"
            rung["rule"] = ("the outcome record ends before this rung's horizon "
                            "closes: a labelled gap, not a miss")
        else:
            rung["outcome"] = "none"
            rung["arrivedBeforeAnnounce"] = bool(matches and not after)
            rung["censoredDays"] = GEO_H_O_DAYS
        rung["expired"] = rung["outcome"] == "none"
        rung["partnerInSet"] = (bool(ep["partnerNorad"] in rung["members"])
                                if ep["partnerNorad"] is not None else None)
    ep["deepestStage"] = _deepest(ep)
    if ep["arrivalMs"] is not None and any(
            ep["rungs"][s].get("outcome") == "arrival" for s in ep["rungs"]):
        ep["deepestStage"] = "S4"
    ep["partnerInR1"] = (bool(ep["partnerNorad"] in ep["r1"])
                         if ep["partnerNorad"] is not None else None)
    ep["partnerInR1SecondHorizon"] = (
        bool(ep["partnerNorad"] in ep["r1Second"])
        if ep["partnerNorad"] is not None else None)
    ep["partnerInR2"] = (
        bool(ep["partnerNorad"] in (ep["rungs"].get("S2") or {}).get("members", []))
        if ep["partnerNorad"] is not None and "S2" in ep["rungs"] else None)
    ep["earliestRungContainingPartner"] = None
    if ep["partnerNorad"] is not None:
        for stage in ("S1", "S2", "S3"):
            r = ep["rungs"].get(stage)
            if r and ep["partnerNorad"] in r["members"]:
                ep["earliestRungContainingPartner"] = stage
                break
    # time in stage
    order = [s for s in ("S1", "S2", "S3") if s in ep["rungs"]]
    for i, s in enumerate(order):
        nxt = (ep["rungs"][order[i + 1]]["announceMs"] if i + 1 < len(order)
               else ep["closeMs"])
        ep["rungs"][s]["daysInStage"] = (float(nxt)
                                         - float(ep["rungs"][s]["announceMs"])) / DAY_MS


def _deepest(ep):
    for s in ("S3", "S2", "S1"):
        if s in ep["rungs"]:
            return s
    return None


# ==========================================================================
# THE LEO ARM
# ==========================================================================
class PlaneSweep:
    """The same shape as the occupancy table, for the other regime: each
    object's newest inclination, right ascension and mean motion at or before
    the query, advanced forward only. The set is the objects whose orbit plane
    agrees with the mover's to theta_p -- the in-plane population the reach
    design names as this regime's reachable set."""

    def __init__(self, arrays):
        order = np.argsort(arrays["epoch_ms"], kind="stable")
        self.norads = np.unique(arrays["norad"]).astype(np.int64)
        self.index = {int(n): i for i, n in enumerate(self.norads)}
        self.ep = arrays["epoch_ms"][order].astype(np.float64)
        self.inc = arrays["inc"][order]
        self.raan = arrays["raan"][order]
        self.n = arrays["n"][order]
        self.source = np.asarray([self.index[int(x)]
                                  for x in arrays["norad"][order]], dtype=np.int64)
        m = self.norads.size
        self.cur_ep = np.full(m, -np.inf)
        self.cur_inc = np.full(m, np.nan)
        self.cur_raan = np.full(m, np.nan)
        self.cur_n = np.full(m, np.nan)
        self.pos = 0

    def at(self, t_ms, exclude_norad):
        j = int(np.searchsorted(self.ep, t_ms, side="right"))
        if j > self.pos:
            sl = slice(self.pos, j)
            who = self.source[sl]
            self.cur_ep[who] = self.ep[sl]
            self.cur_inc[who] = self.inc[sl]
            self.cur_raan[who] = self.raan[sl]
            self.cur_n[who] = self.n[sl]
            self.pos = j
        ok = (np.isfinite(self.cur_inc)
              & ((t_ms - self.cur_ep) <= LEO_STALE_DAYS * DAY_MS))
        e = self.index.get(int(exclude_norad))
        if e is not None:
            ok[e] = False
        idx = np.where(ok)[0]
        return idx

    def plane_set(self, t_ms, norad, tol_deg=LEO_PLANE_TOL_DEG):
        idx = self.at(t_ms, norad)
        me = self.index.get(int(norad))
        if me is None or not np.isfinite(self.cur_inc[me]) or idx.size == 0:
            return np.zeros(0, dtype=np.int64), 0
        i0 = math.radians(float(self.cur_inc[me]))
        o0 = math.radians(float(self.cur_raan[me]))
        i1 = np.radians(self.cur_inc[idx])
        o1 = np.radians(self.cur_raan[idx])
        cos_t = (math.cos(i0) * np.cos(i1)
                 + math.sin(i0) * np.sin(i1) * np.cos(o1 - o0))
        sep = np.degrees(np.arccos(np.clip(cos_t, -1.0, 1.0)))
        sel = idx[sep <= float(tol_deg)]
        return self.norads[sel], int(idx.size)

    def sma_km(self, norad):
        me = self.index.get(int(norad))
        if me is None or not np.isfinite(self.cur_n[me]):
            return None
        return float(alleo.MU_KM3_S2 ** (1.0 / 3.0)
                     / (2.0 * math.pi * float(self.cur_n[me]) / 86400.0) ** (2.0 / 3.0))


def sma_from_n(n_rev_day):
    w = 2.0 * math.pi * np.asarray(n_rev_day, dtype=np.float64) / 86400.0
    return (alleo.MU_KM3_S2 ** (1.0 / 3.0)) / np.power(w, 2.0 / 3.0)


def leo_run(args, say):
    """The other regime's ladder. Reuses the lane's own extract cache, its own
    detector and its own event record; nothing new is extracted and no new
    cache is written."""
    work = Path(args.leo_work)
    cache = work / "leo-extract.npz"
    if not cache.exists():
        say(f"[leo] NOT RUN -- the lane's extract cache {cache} is absent and "
            f"this replay writes no new extract")
        return None
    db = sqlite3.connect(f"file:{ta.ARCHIVE}?mode=ro", uri=True)
    db.execute("PRAGMA query_only = 1")
    arrays = alleo.extract(db, 0, 0, cache, say)
    norads = np.unique(arrays["norad"])
    classes = {}
    for nd in norads:
        row = db.execute("SELECT object_type FROM object WHERE norad = ?",
                         (int(nd),)).fetchone()
        classes[int(nd)] = pp.class_label(row[0] if row else None)
    db.close()

    start = al._ms(args.leo_start)
    end = al._ms(args.leo_end)
    spacing = alleo._median_spacing(arrays)
    cadence = al.derive_cadence(
        spacing, median_causal_lead_days=alleo.T8B_MEDIAN_CAUSAL_LEAD_DAYS,
        spacing_source=(f"measured over all {norads.size:,} objects' element "
                        f"sets in this regime and window"))
    tick_ms = float(cadence["workFloorDays"]) * DAY_MS
    say(f"[leo] derived cadence work floor {cadence['workFloorDays']:.7f} d")

    detected = alleo.detect_all(arrays, classes, say)
    sweep = PlaneSweep(arrays)
    events = [e for e in alleo.load_leo_events() if e.get("armM")]
    ev_by_obj = {}
    record_end = 0.0
    for e in events:
        ev_by_obj.setdefault(int(e["approacher"]), []).append(e)
        record_end = max(record_end, float(e["arrivalMs"]))

    # every trigger, in time order, so the plane table can never see the future
    fires = []
    for norad, d in detected.items():
        for f in d["starts"]:
            if start <= float(f) <= end:
                fires.append((float(f), int(norad)))
    fires.sort()
    say(f"[leo] {len(fires):,} campaign starts inside the window")

    a_all = sma_from_n(arrays["n"])
    by_obj_series = {}
    for nd, el in alleo.per_object(arrays):
        by_obj_series[int(nd)] = el

    episodes = []
    open_ep = {}
    for t_fire, norad in fires:
        members, n_band = sweep.plane_set(t_fire, norad)
        d = detected[norad]
        klass = "payload" if d["klass"] == "payload" else "control"
        ep = open_ep.get(norad)
        if ep is not None and t_fire > ep["closeMs"]:
            _leo_close(ep, by_obj_series.get(norad), episodes)
            ep = None
        mem = set(int(x) for x in members)
        if ep is None:
            ep = {
                "norad": norad, "regime": "LEO", "arm": klass,
                "class": 0, "className": "PHASING-CAMPAIGN",
                "openedMs": t_fire,
                "closeMs": t_fire + LEO_H_O_DAYS * DAY_MS,
                "chains": [(t_fire, t_fire)],
                "set": mem, "r1": sorted(mem),
                "bandObjects": n_band, "s2count": 0, "closedBy": None,
                "rungs": {"S1": {
                    "tTrigMs": t_fire,
                    "announceMs": snap(t_fire, start, tick_ms),
                    "announceRuleMs": t_fire,
                    "setSize": len(mem), "setSizePlaneCompatible": len(mem),
                    "setSizeSecondHorizon": len(mem),
                    "chanceMembership": (float(len(mem)) / float(n_band)
                                         if n_band else None),
                    "members": sorted(mem)}},
            }
            open_ep[norad] = ep
            continue
        enlarging = (len(mem) > len(ep["set"])) or (not (ep["set"] & mem))
        if enlarging:
            ep["closedBy"] = "reopened-at-S1"
            _leo_close(ep, by_obj_series.get(norad), episodes)
            open_ep.pop(norad, None)
            open_ep[norad] = {
                "norad": norad, "regime": "LEO", "arm": klass,
                "class": 0, "className": "PHASING-CAMPAIGN",
                "openedMs": t_fire,
                "closeMs": t_fire + LEO_H_O_DAYS * DAY_MS,
                "chains": [(t_fire, t_fire)],
                "set": mem, "r1": sorted(mem), "bandObjects": n_band,
                "s2count": 0, "closedBy": None,
                "rungs": {"S1": {
                    "tTrigMs": t_fire,
                    "announceMs": snap(t_fire, start, tick_ms),
                    "announceRuleMs": t_fire,
                    "setSize": len(mem), "setSizePlaneCompatible": len(mem),
                    "setSizeSecondHorizon": len(mem),
                    "chanceMembership": (float(len(mem)) / float(n_band)
                                         if n_band else None),
                    "members": sorted(mem)}},
            }
            continue
        ep["set"] = ep["set"] & mem
        ep["chains"].append((t_fire, t_fire))
        ep["closeMs"] = max(ep["closeMs"], t_fire + LEO_H_O_DAYS * DAY_MS)
        ep["s2count"] += 1
        if "S2" not in ep["rungs"]:
            ep["rungs"]["S2"] = {
                "tTrigMs": t_fire,
                "announceMs": snap(t_fire, start, tick_ms),
                "announceRuleMs": t_fire,
                "setSize": len(ep["set"]),
                "setSizePlaneCompatible": len(ep["set"]),
                "setSizeSecondHorizon": len(ep["set"]),
                "chanceMembership": (float(len(ep["set"])) / float(n_band)
                                     if n_band else None),
                "members": sorted(ep["set"])}
    for norad, ep in list(open_ep.items()):
        _leo_close(ep, by_obj_series.get(norad), episodes)

    for ep in episodes:
        _leo_outcome(ep, ev_by_obj.get(int(ep["norad"]), []), record_end)
    say(f"[leo] {len(episodes):,} episodes "
        f"({sum(1 for e in episodes if e['arm'] == 'payload'):,} payload, "
        f"{sum(1 for e in episodes if e['arm'] == 'control'):,} control)")
    return {"episodes": episodes, "cadence": cadence,
            "recordEnd": record_end, "window": {"start": args.leo_start,
                                                "end": args.leo_end},
            "population": {"objectsInBand": int(norads.size),
                           "objectsWithAConfirmedFlag": len(detected)}}


def _leo_close(ep, el, episodes):
    """The S3 rung in this regime, in the coordinate this arm's element extract
    carries: the semi-major-axis offset from exactly one member closing
    monotonically across three element sets and reaching the in-track floor
    inside the set's horizon. DECLARED DEVIATION, registration section 9.1."""
    if el is not None and ep["set"]:
        a_mover = sma_from_n(el["n"])
        lo = ep["rungs"].get("S2", ep["rungs"]["S1"])["tTrigMs"]
        idx = np.where((el["epoch_ms"] > lo) & (el["epoch_ms"] <= ep["closeMs"]))[0]
        # the member's own semi-major axis is not carried per epoch here; the
        # closing quantity is the mover's own |da| against its value at the
        # rung, which is what the in-track channel measures
        if idx.size >= DECEL_SETS:
            base = float(a_mover[max(idx[0] - 1, 0)])
            for p in range(DECEL_SETS - 1, idx.size):
                w = idx[p - DECEL_SETS + 1:p + 1]
                da = np.abs(a_mover[w] - base)
                if not np.all(np.diff(da) < 0.0):
                    continue
                days = (el["epoch_ms"][w] - el["epoch_ms"][w[-1]]) / DAY_MS
                slope, inter = np.polyfit(days, da, 1)
                if slope >= 0.0:
                    continue
                t_hit = (LEO_DA_FLOOR_KM - inter) / slope
                if not (0.0 < t_hit <= LEO_H_R_DAYS):
                    continue
                if len(ep["set"]) != 1:
                    continue
                t_ann = float(el["epoch_ms"][w[-1]])
                ep["rungs"]["S3"] = {
                    "tTrigMs": t_ann, "announceMs": t_ann,
                    "announceRuleMs": t_ann,
                    "setSize": 1, "setSizePlaneCompatible": 1,
                    "setSizeSecondHorizon": 1, "chanceMembership": None,
                    "members": sorted(ep["set"]),
                    "daysToFloor": float(t_hit)}
                break
    ep["set"] = sorted(ep["set"])
    episodes.append(ep)


def _leo_outcome(ep, evs, record_end):
    grace = pp.CAMPAIGN_MAX_GAP_DAYS * DAY_MS
    lo = ep["chains"][0][0] - grace
    hi = ep["closeMs"]
    matches = [e for e in evs
               if e.get("campaignStartMs") is not None
               and lo <= float(e["campaignStartMs"]) <= hi]
    ep["attributedEvents"] = len(matches)
    best = min(matches, key=lambda e: float(e["arrivalMs"])) if matches else None
    ep["partnerNorad"] = int(best["target"]) if best else None
    ep["arrivalMs"] = float(best["arrivalMs"]) if best else None
    ep["objectArrivalsMs"] = [float(e["arrivalMs"]) for e in evs]
    for stage, rung in ep["rungs"].items():
        close = float(rung["tTrigMs"]) + LEO_H_O_DAYS * DAY_MS
        after = [e for e in matches
                 if float(e["arrivalMs"]) > float(rung["announceMs"])
                 and float(e["arrivalMs"]) <= close]
        if after:
            b = min(after, key=lambda e: float(e["arrivalMs"]))
            rung["outcome"] = "arrival"
            rung["arrivalMs"] = float(b["arrivalMs"])
            rung["partnerNorad"] = int(b["target"])
            rung["leadDays"] = (float(b["arrivalMs"])
                                - float(rung["announceMs"])) / DAY_MS
        elif record_end < close:
            rung["outcome"] = "not-assessable"
            rung["rule"] = ("the outcome record ends before this rung's horizon "
                            "closes: a labelled gap, not a miss")
        else:
            rung["outcome"] = "none"
            rung["arrivedBeforeAnnounce"] = bool(matches and not after)
            rung["censoredDays"] = LEO_H_O_DAYS
        rung["expired"] = rung["outcome"] == "none"
        rung["partnerInSet"] = (bool(ep["partnerNorad"] in rung["members"])
                                if ep["partnerNorad"] is not None else None)
    ep["deepestStage"] = _deepest(ep)
    if ep["arrivalMs"] is not None and any(
            ep["rungs"][s].get("outcome") == "arrival" for s in ep["rungs"]):
        ep["deepestStage"] = "S4"
    ep["partnerInR1"] = (bool(ep["partnerNorad"] in ep["r1"])
                         if ep["partnerNorad"] is not None else None)
    ep["partnerInR1SecondHorizon"] = ep["partnerInR1"]
    ep["partnerInR2"] = (
        bool(ep["partnerNorad"] in (ep["rungs"].get("S2") or {}).get("members", []))
        if ep["partnerNorad"] is not None and "S2" in ep["rungs"] else None)
    ep["earliestRungContainingPartner"] = None
    if ep["partnerNorad"] is not None:
        for stage in ("S1", "S2", "S3"):
            r = ep["rungs"].get(stage)
            if r and ep["partnerNorad"] in r["members"]:
                ep["earliestRungContainingPartner"] = stage
                break
    order = [s for s in ("S1", "S2", "S3") if s in ep["rungs"]]
    for i, s in enumerate(order):
        nxt = (ep["rungs"][order[i + 1]]["announceMs"] if i + 1 < len(order)
               else ep["closeMs"])
        ep["rungs"][s]["daysInStage"] = (float(nxt)
                                         - float(ep["rungs"][s]["announceMs"])) / DAY_MS


# ==========================================================================
# THE ESTIMANDS
# ==========================================================================
def rung_tables(episodes, regime, by_class=True):
    """E1, E2, E3, E5 per rung and per class, and the pooled rows."""
    out = []
    keys = [("pooled", None)]
    if by_class:
        seen = sorted({e.get("class") for e in episodes
                       if e.get("class") is not None})
        keys += [(f"class-{c}", c) for c in seen]
    for name, cls in keys:
        pool = [e for e in episodes
                if not e.get("notAssessable")
                and (cls is None or e.get("class") == cls)]
        prev_precision = None
        for stage in ("S1", "S2", "S3"):
            reached = [e for e in pool if stage in e["rungs"]]
            resolved = [e for e in reached
                        if e["rungs"][stage]["outcome"] in ("arrival", "none")]
            arrivals = [e for e in reached
                        if e["rungs"][stage]["outcome"] == "arrival"]
            gaps = [e for e in reached
                    if e["rungs"][stage]["outcome"] == "not-assessable"]
            e1 = rate_row(len(arrivals), len(resolved),
                          "episodes that reached this rung and resolved")
            hit_sets = [e["rungs"][stage]["setSize"] for e in arrivals]
            miss_sets = [e["rungs"][stage]["setSize"] for e in resolved
                         if e["rungs"][stage]["outcome"] == "none"]
            durations, evflag = [], []
            for e in reached:
                r = e["rungs"][stage]
                if r["outcome"] == "arrival":
                    durations.append(r["leadDays"])
                    evflag.append(1)
                elif r["outcome"] == "none":
                    durations.append(float(r.get("censoredDays") or 0.0))
                    evflag.append(0)
            row = {
                "regime": regime, "population": name, "class": cls,
                "stage": stage,
                "reached": len(reached),
                "resolved": len(resolved),
                "notAssessable": len(gaps),
                "precision": e1,
                "separatedAbovePreviousRung": (
                    None if (prev_precision is None or e1["precision"] is None)
                    else bool(e1["wilson95"][0] > prev_precision)),
                "previousRungPointPrecision": prev_precision,
                "setSize": percentiles(
                    [e["rungs"][stage]["setSize"] for e in reached]),
                "setSizePlaneCompatible": percentiles(
                    [e["rungs"][stage].get("setSizePlaneCompatible")
                     for e in reached]),
                "setSizeSecondHorizon": percentiles(
                    [e["rungs"][stage].get("setSizeSecondHorizon")
                     for e in reached]),
                "setSizeIfArrived": percentiles(hit_sets),
                "setSizeIfNot": percentiles(miss_sets),
                "chanceMembership": percentiles(
                    [e["rungs"][stage].get("chanceMembership") for e in reached]),
                "leadDaysKM": km_median(durations, evflag),
                "leadDaysRaw": percentiles(
                    [e["rungs"][stage]["leadDays"] for e in arrivals]),
                "announcementLagDays": percentiles(
                    [(e["rungs"][stage]["announceMs"]
                      - e["rungs"][stage]["announceRuleMs"]) / DAY_MS
                     for e in reached]),
                "daysInStage": percentiles(
                    [e["rungs"][stage].get("daysInStage") for e in reached]),
                "expiry": rate_row(
                    sum(1 for e in resolved
                        if e["rungs"][stage]["outcome"] == "none"),
                    len(resolved), "episodes that reached this rung and resolved"),
                "closedByEnlargingBurn": sum(
                    1 for e in reached if e.get("closedBy") == "reopened-at-S1"),
                "arrivedBeforeAnnounce": sum(
                    1 for e in reached
                    if e["rungs"][stage].get("arrivedBeforeAnnounce")),
            }
            if e1["precision"] is not None and not e1["underpowered"]:
                prev_precision = e1["precision"]
            out.append(row)
    return out


def post_hoc_non_empty_set(episodes, regime):
    """POST-HOC AND NOT REGISTERED, and labelled so wherever it appears.

    The set-enlarging predicate of the registration degenerates when the
    governing set is EMPTY: an empty set intersects nothing, so every later
    burn is "set-enlarging" and the episode reopens instead of advancing. S2
    is therefore reachable only for episodes whose first burn reached at least
    one station, and that is already a discriminating condition. This table
    exists so a reader can see whether S2's separation is the SECOND BURN
    speaking or the NON-EMPTY SET speaking; it was computed after the
    registered numbers existed and it changes no rule, threshold or gate."""
    pool = [e for e in episodes if not e.get("notAssessable")]
    nonempty = [e for e in pool if not e.get("r1Empty")]
    rows = []
    for name, sub in (("S1, every episode", pool),
                      ("S1, episodes whose first burn reached a station",
                       nonempty),
                      ("S1, episodes whose first burn reached nothing",
                       [e for e in pool if e.get("r1Empty")])):
        resolved = [e for e in sub
                    if e["rungs"]["S1"]["outcome"] in ("arrival", "none")]
        k = sum(1 for e in resolved
                if e["rungs"]["S1"]["outcome"] == "arrival")
        rows.append({"population": name, "precision": rate_row(k, len(resolved))})
    reached_s2 = [e for e in pool if "S2" in e["rungs"]]
    return {
        "regime": regime,
        "label": ("POST-HOC, NOT REGISTERED -- computed after the registered "
                  "numbers existed, changing no rule, threshold or gate"),
        "emptySetEpisodes": sum(1 for e in pool if e.get("r1Empty")),
        "episodes": len(pool),
        "s2ReachableOnlyFromANonEmptySet": all(
            not e.get("r1Empty") for e in reached_s2),
        "rows": rows,
    }


def recall_of_the_set(episodes, regime):
    """E4. Over every episode whose outcome record attributes an arrival: was
    the eventual partner inside the set when the rung opened?"""
    arrived = [e for e in episodes
               if not e.get("notAssessable") and e.get("partnerNorad") is not None]
    in_r1 = [e for e in arrived if e.get("partnerInR1")]
    in_r1b = [e for e in arrived if e.get("partnerInR1SecondHorizon")]
    with_s2 = [e for e in arrived if "S2" in e.get("rungs", {})]
    in_r2 = [e for e in with_s2 if e.get("partnerInR2")]
    earliest = {}
    for e in arrived:
        k = e.get("earliestRungContainingPartner") or "never"
        earliest[k] = earliest.get(k, 0) + 1
    return {
        "regime": regime,
        "s4EventsWithAnEpisode": len(arrived),
        "partnerInR1": rate_row(len(in_r1), len(arrived),
                                "S4 events with an episode, governing horizon"),
        "partnerInR1SecondHorizon": rate_row(
            len(in_r1b), len(arrived),
            "S4 events with an episode, the second horizon arm"),
        "partnerInR2": rate_row(len(in_r2), len(with_s2),
                                "S4 events whose episode reached S2"),
        "earliestRungContainingPartner": earliest,
        "note": ("this is the recall of the SET given an episode. The recall of "
                 "the DETECTOR is UNMEASURED: a sequence with no visible "
                 "initiating change never opens an episode and cannot be "
                 "counted here."),
    }


def gate_t(episodes, regime, horizon_days, window_start_ms, window_end_ms,
           draws=SHUFFLE_DRAWS, seed=SEED):
    """Registration 5(c). The flag-attribution rule cannot survive a
    displacement of the arrival epochs, so both arms use the WINDOW rule: an
    episode is a hit if an arrival of the same object falls inside the rung's
    own window."""
    rng = np.random.default_rng(seed)
    # THE SHUFFLE UNIVERSE. "Wrapped inside the replay window" is undefined for
    # an arrival that was never in it, and wrapping one in would manufacture
    # hits the real arm cannot have. The universe is therefore the interval a
    # rung of this replay can possibly reach -- the window plus one outcome
    # horizon -- and BOTH arms are restricted to it, so the two are measured on
    # the same population.
    u_lo = float(window_start_ms)
    u_hi = float(window_end_ms) + horizon_days * DAY_MS
    span = u_hi - u_lo
    rows = []
    real_by_stage = {}
    for e in episodes:
        if e.get("notAssessable"):
            continue
        arrivals = [a for a in (e.get("objectArrivalsMs") or [])
                    if u_lo <= a <= u_hi]
        for stage, rung in e["rungs"].items():
            ann = float(rung["announceMs"])
            close = float(rung["tTrigMs"]) + horizon_days * DAY_MS
            real_by_stage.setdefault(stage, []).append(
                (ann, close, arrivals))
    for stage in ("S1", "S2", "S3"):
        rows_stage = real_by_stage.get(stage) or []
        if not rows_stage:
            continue
        real_k = sum(1 for ann, close, arr in rows_stage
                     if any(ann < a <= close for a in arr))
        shuffled = []
        for _ in range(draws):
            delta = float(rng.uniform(-0.5 * span, 0.5 * span))
            k = 0
            for ann, close, arr in rows_stage:
                hit = False
                for a in arr:
                    b = u_lo + ((a + delta - u_lo) % span)
                    if ann < b <= close:
                        hit = True
                        break
                if hit:
                    k += 1
            shuffled.append(k / float(len(rows_stage)))
        s = np.asarray(shuffled, dtype=np.float64)
        real = real_k / float(len(rows_stage))
        rows.append({
            "regime": regime, "stage": stage, "n": len(rows_stage),
            "realWindowRulePrecision": real,
            "realWindowRule": rate_row(real_k, len(rows_stage)),
            "shuffledMean": float(s.mean()),
            "shuffledP5": float(np.percentile(s, 5)),
            "shuffledP95": float(np.percentile(s, 95)),
            "draws": int(draws), "seed": int(seed),
            "separated": bool(real > float(np.percentile(s, 95))
                              or real < float(np.percentile(s, 5))),
            "universe": {"fromIso": _iso(u_lo), "toIso": _iso(u_hi)},
            "note": ("both arms use the window rule, and both are restricted "
                     "to the same universe -- the replay window plus one "
                     "outcome horizon. The flag-attribution rule of the "
                     "headline cannot survive a time shuffle, and that is why "
                     "this pair exists"),
        })
    return rows


def t13_control(episodes, ledger_path):
    """Control (b). Join each episode's opening burn to the committed v2
    manoeuvre-library ledger by (norad, epochMs). The committed ledger is a
    SUBSET, and the joined n is printed on every row."""
    path = Path(ledger_path)
    if not path.exists():
        return {"label": ("NOT ASSESSABLE -- the library ledger is absent; a "
                          "labelled gap, not a zero")}
    by_key, prov = {}, None
    with open(path) as fh:
        for line in fh:
            rec = json.loads(line)
            if rec.get("record") == "provenance":
                prov = rec
                continue
            by_key[(int(rec["norad"]), int(round(float(rec["epochMs"]))))] = \
                rec.get("type")
    rows = {}
    joined = 0
    for e in episodes:
        if e.get("notAssessable"):
            continue
        t = None
        for a, b in (e["chains"][:1] or []):
            for cand in (int(round(b)), int(round(a))):
                t = by_key.get((int(e["norad"]), cand))
                if t is not None:
                    break
        if t is None:
            continue
        joined += 1
        row = rows.setdefault(t, {"type": t, "episodes": 0,
                                  "S2": 0, "S3": 0, "S4": 0})
        row["episodes"] += 1
        for stage in ("S2", "S3"):
            if stage in e["rungs"]:
                row[stage] += 1
        if e.get("deepestStage") == "S4":
            row["S4"] += 1
    for row in rows.values():
        for stage in ("S2", "S3", "S4"):
            row[stage + "Rate"] = rate_row(row[stage], row["episodes"],
                                           "joined episodes of this type")
    return {
        "joinedEpisodes": joined,
        "types": sorted(rows.values(), key=lambda r: -r["episodes"]),
        "libraryVersion": (prov or {}).get("libraryVersion"),
        "rulesSha256": (prov or {}).get("rulesSha256"),
        "subsetNote": (
            f"the committed ledger is a SUBSET -- "
            f"{(prov or {}).get('subsetRows')} rows of "
            f"{(prov or {}).get('fullTableRows')} -- so the joined population "
            f"is a sample of the ladder's episodes and every row prints its "
            f"own n. A type with fewer than 20 joined episodes is UNDERPOWERED "
            f"and lends its name to nothing. No type is re-implemented here: an "
            f"unjoined episode's type is a labelled gap, never an inferred "
            f"label."),
    }


def operating_point_rows(episodes, curve):
    """Registration 6.2 -- the dial gains `stage` as a fourth axis, by
    post-filtering episodes on each named setting's evidence axes at S1. Every
    row is measured at persistenceSweeps = 1 and says so."""
    rows = []
    for setting in curve.get("namedSettings", []):
        point = setting.get("point") or {}
        floor = point.get("minDriftChangeDegPerDay")
        slots = point.get("minSlotsReached")
        keep = []
        for e in episodes:
            if e.get("notAssessable"):
                continue
            if floor is not None and abs(float(e.get("driftChange") or 0.0)) < float(floor):
                continue
            if slots is not None and float(e.get("fwdSlotsReached180") or 0.0) < float(slots):
                continue
            keep.append(e)
        for row in rung_tables(keep, "GEO"):
            rows.append(dict(
                row, setting=setting.get("name"), point=dict(point),
                persistenceNote=(
                    "measured at persistenceSweeps = 1 for every setting; the "
                    "persistence axis changes announce timing and is not "
                    "re-measured here"),
                leakNote=GEO_LEAK["sentence"]))
    return rows


def _reach_leak(control, payload):
    """Per rung, the share of CONTROL episodes that reach it divided by the
    share of payload episodes that reach it. A rung reached by an object that
    cannot burn is a leak, and this is its size."""
    out = []
    for stage in ("S1", "S2", "S3"):
        c = sum(1 for e in control if stage in e["rungs"])
        p = sum(1 for e in payload if stage in e["rungs"])
        rc = (c / len(control)) if control else None
        rp = (p / len(payload)) if payload else None
        out.append({
            "stage": stage,
            "controlEpisodesReaching": c, "controlShare": rc,
            "payloadEpisodesReaching": p, "payloadShare": rp,
            "leakRatio": (rc / rp) if (rc is not None and rp) else None,
            "bar": 0.10,
            "note": ("the share of episodes on objects the catalogue does not "
                     "class as payloads that reach this rung, over the same "
                     "share on objects that can manoeuvre"),
        })
    return out


def verdict(rows, regime):
    """The registration's own words. Exactly one of YES, NO, UNDERPOWERED."""
    pooled = {r["stage"]: r for r in rows
              if r["population"] == "pooled" and r["regime"] == regime}
    s1 = pooled.get("S1")
    if s1 is None or s1["precision"]["precision"] is None:
        return "UNDERPOWERED", "no S1 rung resolved in this regime"
    for stage in ("S2", "S3"):
        r = pooled.get(stage)
        if r is None:
            continue
        if r["precision"]["n"] < MIN_SUPPORT:
            continue
        if r["precision"]["wilson95"][0] is None:
            continue
        if r["precision"]["wilson95"][0] > s1["precision"]["precision"]:
            return "YES", (f"{stage} Wilson lower bound "
                           f"{r['precision']['wilson95'][0]:.5f} exceeds S1's "
                           f"point precision {s1['precision']['precision']:.5f} "
                           f"on n = {r['precision']['n']}")
    powered = [pooled[s] for s in ("S2", "S3")
               if s in pooled and pooled[s]["precision"]["n"] >= MIN_SUPPORT]
    if not powered:
        return "UNDERPOWERED", ("no rung above S1 reached twenty resolved "
                                "episodes in this regime")
    return "NO", ("every powered rung above S1 has a Wilson lower bound at or "
                  "below S1's point precision")


# ==========================================================================
def write_subset(episodes, out_path, date, regime, sample, seed=SEED):
    """Every episode that reached S2 or above, every episode an arrival
    resolved, plus a seeded uniform sample of at most `sample` of the rest."""
    rng = np.random.default_rng(seed)
    keep, others = [], []
    for e in episodes:
        if e.get("notAssessable"):
            others.append(e)
        elif ("S2" in e.get("rungs", {}) or "S3" in e.get("rungs", {})
                or e.get("arrivalMs") is not None):
            keep.append(e)
        else:
            others.append(e)
    n = min(int(sample), len(others))
    if n:
        picks = sorted(rng.choice(len(others), size=n, replace=False))
        keep.extend(others[i] for i in picks)
    prov = {
        "record": "provenance", "schema": 1,
        "artifact": "m3-ladder-episodes", "registration": REGISTRATION,
        "regime": regime,
        "caveats": list(STRUCTURAL_CAVEATS),
        "inSampleNote": IN_SAMPLE_NOTE,
        "subset": True, "subsetRows": len(keep),
        "fullRows": len(episodes), "otherEpisodes": len(others),
        "otherEpisodesSampled": n, "seed": int(seed),
        "droppedFields": ["r1", "r1Second", "set", "setSecond",
                          "memberState", "objectArrivalsMs"],
        "droppedFieldsNote": (
            "`r1` duplicates `rungs.S1.members`; the second horizon's member "
            "list is carried as `setSizeSecondHorizon` and "
            "`partnerInR1SecondHorizon`; the rest are working state."),
        "rule": ("every episode that reached S2 or above, every episode an "
                 "arrival resolved, plus a seeded uniform sample of the rest. "
                 "The sampling rule reads only the rung reached and whether an "
                 "arrival resolved, so the rungs above S1 are complete rather "
                 "than sampled."),
    }
    with open(out_path, "w") as fh:
        fh.write(json.dumps(prov, sort_keys=True) + "\n")
        for e in sorted(keep, key=lambda r: (r.get("openedMs") or 0.0,
                                             r.get("norad") or 0)):
            # the member lists are kept ONCE, on the rung that drew them.
            # `r1` duplicates `rungs.S1.members`, and the second horizon's
            # list runs to hundreds of entries whose only use here is its
            # size and whether it held the partner -- both of which are
            # already carried as `setSizeSecondHorizon` and
            # `partnerInR1SecondHorizon`. This repository is a teaching-aid
            # source tree, not an archive.
            row = {k: v for k, v in e.items()
                   if k not in ("memberState", "objectArrivalsMs",
                                "r1", "r1Second", "set", "setSecond")}
            fh.write(json.dumps(row, sort_keys=True, allow_nan=False,
                                default=float) + "\n")
    return out_path


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--arms", default="geo,leo")
    p.add_argument("--out", default=str(_REPO / "docs"))
    p.add_argument("--date", default="20260923")
    p.add_argument("--start", default="2010-01-01T00:00:00+00:00")
    p.add_argument("--end", default="2020-01-01T00:00:00+00:00")
    p.add_argument("--leo-start", default=alleo.WINDOW_START)
    p.add_argument("--leo-end", default=alleo.WINDOW_END)
    p.add_argument("--leo-work", required=True,
                   help="the low-orbit lane's working directory")
    p.add_argument("--tick-days", type=float, default=None)
    p.add_argument("--sample", type=int, default=1000)
    p.add_argument("--library",
                   default=str(_REPO / "docs"
                               / "manoeuvre-library-ledger-v2-20260922.jsonl"))
    args = p.parse_args(argv)

    t0 = time.time()

    def say(m):
        print(f"  [{time.time() - t0:8.1f}s] {m}", flush=True)

    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "artifact": "m3-ladder", "schema": 1,
        "registration": REGISTRATION, "design": DESIGN,
        "status": ("SYNTHETIC EXERCISE with an INJECTED CLOCK. Nothing is "
                   "deployed, nothing is scheduled, no timer or cron entry "
                   "exists, and nothing here is on any site surface."),
        "caveats": list(STRUCTURAL_CAVEATS),
        "inSampleNote": IN_SAMPLE_NOTE,
        "horizons": {
            "geoSetHorizonDays": GEO_H_R_DAYS,
            "geoSetHorizonSecondArmDays": GEO_H_R_SECOND_DAYS,
            "geoOutcomeHorizonDays": GEO_H_O_DAYS,
            "leoSetHorizonDays": LEO_H_R_DAYS,
            "leoOutcomeHorizonDays": LEO_H_O_DAYS,
            "note": ("the set's horizon is the one the forward-error "
                     "measurement leaves resolvable; the outcome horizon is "
                     "the lane's own, so a rung precision can be compared with "
                     "the single-burn figure it has to beat"),
        },
        "geoLeak": dict(GEO_LEAK),
        "arms": {},
        "host": "pc", "executionMode": "CPU, one core",
    }

    if "geo" in arms:
        model = al.load_model()
        curve = al.load_operating_points(al.CURVE_PATH, model)
        source = al.ExtractSource()
        say(f"[geo] {len(source.series_by_norad):,} element histories in memory")
        flags = al.MemoisedFlags(source.series_by_norad)
        events = al.load_event_record()
        spacing = al.measured_epoch_spacing_days(
            list(source.series_by_norad.values()))
        cadence = al.derive_cadence(
            spacing, spacing_source=(f"measured over all "
                                     f"{len(source.series_by_norad)} watched "
                                     f"objects' element sets"))
        tick = float(args.tick_days or cadence["workFloorDays"])
        cadence["replayTickDays"] = tick
        say(f"[geo] derived cadence work floor {cadence['workFloorDays']:.7f} d")
        start, end = al._ms(args.start), al._ms(args.end)
        trigs = geo_triggers(source, flags, model, start, end, say)
        episodes, record_end = geo_episodes(trigs, source, events, start, end,
                                            tick * DAY_MS, say)
        rows = rung_tables(episodes, "GEO")
        v, why = verdict(rows, "GEO")
        result["arms"]["GEO"] = {
            "window": {"start": args.start, "end": args.end},
            "windowRule": ("the decade with the most confirmed drift changes "
                           "(71,661 of 226,422 flag chains), chosen on alert "
                           "volume, which is outcome-blind"),
            "cadence": cadence,
            "model": {"version": model["modelVersion"],
                      "checksum": al.model_checksum(model)},
            "clock": {"mode": "injected", "start": args.start,
                      "end": args.end},
            "episodes": len(episodes),
            "notAssessable": sum(1 for e in episodes if e.get("notAssessable")),
            "outcomeRecordEndsAt": _iso(record_end),
            "rungs": rows,
            "recallOfTheSet": recall_of_the_set(episodes, "GEO"),
            "postHocNonEmptySet": post_hoc_non_empty_set(episodes, "GEO"),
            "gateT": gate_t(episodes, "GEO", GEO_H_O_DAYS, start, end),
            "controlA": {
                "exists": False,
                "label": ("control (a) DOES NOT EXIST at this regime, in those "
                          "words; the measurement it would need is still owed"),
                "leak": dict(GEO_LEAK)},
            "controlB": t13_control(episodes, args.library),
            "operatingPointRows": operating_point_rows(episodes, curve),
            "verdict": v, "verdictBasis": why,
        }
        write_subset(episodes,
                     out_dir / f"m3-ladder-episodes-geo-{args.date}.jsonl",
                     args.date, "GEO", args.sample)
        say(f"[geo] VERDICT {v}: {why}")
        source.close()

    if "leo" in arms:
        leo = leo_run(args, say)
        if leo is not None:
            payload = [e for e in leo["episodes"] if e["arm"] == "payload"]
            control = [e for e in leo["episodes"] if e["arm"] == "control"]
            rows = rung_tables(payload, "LEO", by_class=False)
            crows = rung_tables(control, "LEO", by_class=False)
            v, why = verdict(rows, "LEO")
            result["arms"]["LEO"] = {
                "window": leo["window"],
                "windowRule": alleo.WINDOW_RULE,
                "cadence": leo["cadence"],
                "clock": {"mode": "injected", **leo["window"]},
                "population": leo["population"],
                "episodes": len(payload),
                "outcomeRecordEndsAt": _iso(leo["recordEnd"]),
                "rungs": rows,
                "recallOfTheSet": recall_of_the_set(payload, "LEO"),
                "gateT": gate_t(payload, "LEO", LEO_H_O_DAYS,
                                al._ms(leo["window"]["start"]),
                                al._ms(leo["window"]["end"])),
                "controlA": {
                    "exists": True,
                    "circular": True,
                    "label": (
                        "the never-manoeuvred class is defined by the ABSENCE "
                        "of a flag from the very detector that defines S1, so "
                        "its zero at every rung is a tautology and is reported "
                        "as a tautology and not as evidence"),
                    "registeredFigure": {
                        "objects": 3011, "events": 0,
                        "objectDays": 18792698,
                        "source": "docs/proximity-leo-results-20260922.md"}},
                "controlAPrime": {
                    "episodes": len(control),
                    "rungs": crows,
                    "rungReachLeak": _reach_leak(control, payload),
                    "label": ("the substantive leak control: objects the "
                              "catalogue does not class as payloads, run "
                              "through the same ladder"),
                    "laneRatio": 0.7971470058543085, "laneBar": 0.001},
                "verdict": v, "verdictBasis": why,
            }
            write_subset(leo["episodes"],
                         out_dir / f"m3-ladder-episodes-leo-{args.date}.jsonl",
                         args.date, "LEO", args.sample)
            say(f"[leo] VERDICT {v}: {why}")

    # --- gate S, on the governing arm, per regime --------------------------
    for regime, arm in result["arms"].items():
        rec = arm["recallOfTheSet"]["partnerInR1"]
        arm["gateS"] = {
            "fires": (None if rec["precision"] is None
                      else bool(rec["precision"] < 0.5)),
            "partnerInR1": rec,
            "rule": ("if the eventual partner is absent from R1 in more than "
                     "half of S4 events, the reachable-set definition is wrong "
                     "and the layer is withheld entirely"),
        }
    result["wallSeconds"] = time.time() - t0
    out = out_dir / f"m3-ladder-{args.date}.json"
    out.write_text(json.dumps(result, indent=1, sort_keys=True,
                              default=float) + "\n")
    say(f"artifact: {out}")

    receipt = {
        "artifact": "m3-ladder-receipt", "schema": 1,
        "registration": REGISTRATION, "design": DESIGN,
        "status": result["status"],
        "measuredAt": _iso(time.time() * 1000.0),
        "host": "pc", "executionMode": "CPU, one core",
        "wallSeconds": result["wallSeconds"],
        "inputs": {name: al.sha256_file(_REPO / name)
                   for name in ("docs/proximity-events-20260922.jsonl",
                                "docs/proximity-leo-events-20260922.jsonl",
                                "docs/alarm-lane-model-20260922.json",
                                "docs/alarm-lane-operating-points-20260922.json",
                                "docs/alarm-lane-leo-model-20260922.json",
                                "docs/manoeuvre-library-ledger-v2-20260922.jsonl",
                                "tools/ladder_replay.py",
                                "tools/trigger_alarm.py", "tools/alarm_lane.py",
                                "tools/alarm_lane_leo.py")
                   if (_REPO / name).exists()},
        "verdicts": {r: a["verdict"] for r, a in result["arms"].items()},
        "caveats": list(STRUCTURAL_CAVEATS),
        "geoLeak": dict(GEO_LEAK),
    }
    (out_dir / f"m3-ladder-{args.date}-receipt.json").write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n")
    say(f"receipt: {out_dir / f'm3-ladder-{args.date}-receipt.json'}")
    for regime, arm in result["arms"].items():
        print()
        print(f"{regime}: does the ladder earn a rung above S1 -- "
              f"{arm['verdict']}")
        print(f"  {arm['verdictBasis']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
