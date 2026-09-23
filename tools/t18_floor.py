#!/usr/bin/env python3
"""T18 build step B4/B7: the cadence-only artefact floor, measured.

Registered in `docs/t18-preregistration-20260922.md` (2618343). This script
computes no estimand the registration did not fix in advance, and it applies
each screen exactly as written.

What it measures, in the order the registration puts them:

  E1   recall on the 1,134 mission-reported manoeuvres of ELEVEN GEODETIC AND
       ALTIMETRY SPACECRAFT, at the shipped detector's OWN false-flag rate of
       0.012642669007901668 flags per labelled-quiet window-day, with the
       shipped detector's OWN two-consecutive-same-sign confirmation rule.
       Arms A1 (any era) and A2 (at or after T_cut).
  E3   flag rate on the passive null and on objects that manoeuvre routinely,
       their ratio against the registered factor of 3.0, and the between-class
       dispersion across the committed sampling-geometry classes.
  G    the geometry probe: does the frozen embedding carry sampling class more
       strongly than behaviour class?
  G5   the leakage audit: the nearest-neighbour similarity distribution of test
       windows to training windows, PUBLISHED rather than asserted.

Nothing here is a census. The recall composition limits of registration 1.1
are carried into the output file so a reader of the JSON cannot lose them.

Usage:
  t18_floor.py --checkpoint <ckpt> --data-dir <dir> --out docs/t18-floor-20260922.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
TOOLS = Path(__file__).resolve().parent
for extra in (str(REPO), str(TOOLS)):
    if extra not in sys.path:
        sys.path.insert(0, extra)

import t18_data as td                                          # noqa: E402
import t18_model as tm                                         # noqa: E402
import proximity_plane as pp                                   # noqa: E402
from truthset_recall import (                                  # noqa: E402
    DA_BINS, SAT_NORAD, bin_of, bracketed_da_metres, load_labels, wilson,
)

BASELINE_JSON = REPO / "docs" / "t16b-truthset-recall-20260922.json"
PROPULSION = REPO / "data" / "propulsion-catalog-v1.json"

# registration 1: the operating point the learned threshold is swept to meet
BASELINE_FLAGS_PER_QUIET_WINDOW_DAY = 0.012642669007901668
BASELINE_RECALL = {"k": 90, "n": 1134, "recall": 0.07936507936507936,
                   "wilson95": [0.06501510889203253, 0.09655525523650489]}
E3_FALSE_ALARM_FRACTION = 0.01        # registration 3.4
E3_RATIO_SCREEN = 3.0                 # registration 3.4
MIN_CLASS_WINDOWS = 200               # registration 3.4
UNDERPOWERED_BELOW = 20               # registration 7, gate G7

COMPOSITION_LIMITS = [
    "The labels are ELEVEN GEODETIC AND ALTIMETRY SPACECRAFT, not "
    "constellations: CryoSat-2, Sentinel-3A, Sentinel-3B, Jason-1, Jason-2, "
    "Jason-3, SWOT, SARAL, HY-2A, TOPEX/Poseidon, Sentinel-6A.",
    "No figure here is 'the model's recall' without the qualifier: on this "
    "labelled set, these eleven geodetic and altimetry spacecraft, these burn "
    "sizes.",
    "Nothing here says anything about Starlink, about any constellation, or "
    "about any operator whose manoeuvre log is not public. A "
    "constellation-class labelled baseline remains UNMEASURED.",
    "Eleven cooperative, exceptionally well-tracked spacecraft are not a "
    "census. What makes them measurable makes them unrepresentative.",
    "Recall and precision measured on different populations do not compose.",
    "Every threshold here is a chosen screen, not a physical law.",
]


def wilson_or_none(k, n):
    return wilson(int(k), int(n)) if n else None


def cell(k, n):
    return {"k": int(k), "n": int(n),
            "rate": (k / n) if n else None,
            "wilson95": wilson_or_none(k, n)}


# --------------------------------------------------------------------------
# Populations
# --------------------------------------------------------------------------
def object_context(db, norads):
    """Regime, era and bus family per object.

    Ownership-blind: the bus family is a fact about the spacecraft, and it is
    read AFTER the embedding is frozen, to form an evaluation grouping only.
    No registry code, operator or country enters anything here.
    """
    bus = {}
    if PROPULSION.exists():
        for row in json.loads(PROPULSION.read_text())["objects"]:
            if row.get("norad") and row.get("bus"):
                bus[int(row["norad"])] = str(row["bus"])
    out = {}
    for norad in norads:
        got = db.execute(
            "SELECT mean_motion_q, eccentricity_q, epoch_ms FROM element_set "
            "WHERE norad=? ORDER BY epoch_ms LIMIT 1", (int(norad),)).fetchone()
        if not got:
            continue
        el = {"n_rev_day": np.asarray([got[0] / td.SCALE_MEAN_MOTION]),
              "ecc": np.asarray([got[1] / td.SCALE_ECCENTRICITY])}
        out[int(norad)] = {
            "regime": td.regime_of(el),
            "era": td.era_of(np.asarray([got[2]])),
            "bus": bus.get(int(norad)),
        }
    return out


def shipped_flags(db, norad):
    """The shipped detector's own flags, imported and called, never edited."""
    rows = db.execute(
        "SELECT epoch_ms, mean_motion_q, eccentricity_q, inclination_q, raan_q "
        "FROM element_set WHERE norad=? ORDER BY epoch_ms",
        (int(norad),)).fetchall()
    if len(rows) < pp.BURN_BASELINE_SAMPLES + 3:
        return None
    arr = np.asarray(rows, dtype=np.float64)
    el = {"epoch_ms": arr[:, 0].astype(np.int64),
          "n": arr[:, 1] / 1e8, "e": arr[:, 2] / 1e8,
          "inc": arr[:, 3] / 1e4, "raan": arr[:, 4] / 1e4}
    det = pp.detect_manoeuvres(el, 6.2747e-5, 0.6994)
    ep = el["epoch_ms"]
    intrack = ep[det["intrack"]] if det["intrack"].size else np.asarray([], dtype=np.int64)
    plane = ep[det["plane"]] if det["plane"].size else np.asarray([], dtype=np.int64)
    return np.union1d(intrack, plane)


# --------------------------------------------------------------------------
# E1
# --------------------------------------------------------------------------
def sweep_threshold(scored, stable_by_sat, target_rate, say=print):
    """The registered tie-break: the SMALLEST threshold whose false-flag rate
    on the labelled-quiet windows does not exceed the baseline's."""
    pool = np.concatenate([row["dA"][row["valid"]] for row in scored.values()
                           if row["valid"].any()])
    grid = np.unique(np.percentile(pool, np.linspace(50.0, 99.999, 900)))
    curve = []
    chosen = None
    for tau in grid:
        flags_in_quiet = 0
        quiet_days = 0.0
        for sat, row in scored.items():
            flags = tm.confirmed_flags(row["dA"], row["sign"], row["epoch_ms"],
                                       row["valid"], float(tau))
            for win in stable_by_sat.get(sat, []):
                flags_in_quiet += int(np.count_nonzero(
                    (flags >= win["startMs"]) & (flags <= win["endMs"])))
        for sat in scored:
            for win in stable_by_sat.get(sat, []):
                quiet_days += (win["endMs"] - win["startMs"]) / td.DAY_MS
        rate = flags_in_quiet / quiet_days if quiet_days else None
        curve.append({"threshold": float(tau), "flagsInQuiet": flags_in_quiet,
                      "quietWindowDays": quiet_days,
                      "flagsPerQuietWindowDay": rate})
        if rate is not None and rate <= target_rate and chosen is None:
            chosen = curve[-1]
        if chosen is not None and flags_in_quiet == 0:
            break
    if chosen is None:
        say("NO THRESHOLD reaches the baseline's false-flag rate without "
            "driving the flag count to zero; no recall is quoted")
    return chosen, curve


def measure_e1(scored, labels, stable_by_sat, elements, floors, threshold,
               arm_name, min_event_ms=None):
    by_sat = {}
    for lab in labels:
        if min_event_ms is not None and lab["eventMs"] < min_event_ms:
            continue
        by_sat.setdefault(lab["sat"], []).append(lab)

    overall = {"k": 0, "n": 0, "notEvaluable": 0}
    by_bin, by_floor, by_sat_cell = {}, {}, {}
    campaign = {"k": 0, "n": 0}
    placebo = {"k": 0, "n": 0}
    flags_by_sat = {}
    for sat, row in scored.items():
        flags_by_sat[sat] = tm.confirmed_flags(
            row["dA"], row["sign"], row["epoch_ms"], row["valid"], threshold)

    for sat, sat_labels in by_sat.items():
        if sat not in scored:
            overall["notEvaluable"] += len(sat_labels)
            continue
        flags = flags_by_sat[sat]
        ep = scored[sat]["epoch_ms"]
        starts = campaign_starts(flags)
        el = elements[sat]
        for lab in sat_labels:
            lo, hi = lab["windowStartMs"], lab["windowEndMs"]
            if ep.size < pp.BURN_BASELINE_SAMPLES + 3 or ep[0] > lo or ep[-1] < hi:
                overall["notEvaluable"] += 1
                continue
            hit = bool(np.any((flags >= lo) & (flags <= hi)))
            overall["n"] += 1
            overall["k"] += int(hit)
            campaign["n"] += 1
            campaign["k"] += int(np.any((starts >= lo) & (starts <= hi)))
            cellv = by_sat_cell.setdefault(sat, {"k": 0, "n": 0})
            cellv["n"] += 1
            cellv["k"] += int(hit)
            da = bracketed_da_metres(el, lo, hi)
            cellv = by_bin.setdefault(bin_of(da, DA_BINS), {"k": 0, "n": 0})
            cellv["n"] += 1
            cellv["k"] += int(hit)
            side = ("unknown" if da is None
                    else "aboveFloor" if da >= floors[sat] else "belowFloor")
            cellv = by_floor.setdefault(side, {"k": 0, "n": 0})
            cellv["n"] += 1
            cellv["k"] += int(hit)
            # POST-REGISTRATION control, labelled as such here and in the
            # results: T16b added the same one for the same reason -- without
            # it a single-digit recall cannot be told from the background
            # density of flags on an object that is flagged often.
            for shift in (-90.0, -60.0, -30.0, 30.0, 60.0, 90.0):
                plo = lo + shift * td.DAY_MS
                phi = hi + shift * td.DAY_MS
                if plo < ep[0] or phi > ep[-1]:
                    continue
                if any(abs(plo - other["eventMs"]) < 2.0 * td.DAY_MS
                       for other in sat_labels):
                    continue
                placebo["n"] += 1
                placebo["k"] += int(np.any((flags >= plo) & (flags <= phi)))

    quiet_flags = 0
    quiet_days = 0.0
    quiet_windows_hit = 0
    quiet_windows = 0
    for sat in scored:
        for win in stable_by_sat.get(sat, []):
            if min_event_ms is not None and win["endMs"] < min_event_ms:
                continue
            quiet_windows += 1
            quiet_days += (win["endMs"] - win["startMs"]) / td.DAY_MS
            k = int(np.count_nonzero((flags_by_sat[sat] >= win["startMs"])
                                     & (flags_by_sat[sat] <= win["endMs"])))
            quiet_flags += k
            quiet_windows_hit += int(k > 0)

    return {
        "arm": arm_name,
        "threshold": float(threshold),
        "overall": {**cell(overall["k"], overall["n"]),
                    "notEvaluable": overall["notEvaluable"]},
        "campaignLevel": cell(campaign["k"], campaign["n"]),
        "placeboControlPostRegistration": cell(placebo["k"], placebo["n"]),
        "byDaBin": {k: cell(v["k"], v["n"]) for k, v in sorted(by_bin.items())},
        "byFloor": {k: cell(v["k"], v["n"]) for k, v in sorted(by_floor.items())},
        "bySpacecraft": {k: cell(v["k"], v["n"])
                         for k, v in sorted(by_sat_cell.items())},
        "falseFlags": {
            "quietWindows": quiet_windows,
            "quietWindowDays": quiet_days,
            "flagsInQuietWindows": quiet_flags,
            "quietWindowsWithAtLeastOneFlag": quiet_windows_hit,
            "flagsPerQuietWindowDay": (quiet_flags / quiet_days) if quiet_days else None,
            "note": "an UPPER bound on false flags: MAD-LEO's quiet windows "
                    "are mined from an element-set archive, not declared quiet "
                    "by an operator",
        },
        "totalFlags": int(sum(f.size for f in flags_by_sat.values())),
    }


def campaign_starts(flag_ms):
    if flag_ms.size == 0:
        return np.asarray([], dtype=np.int64)
    flags = np.sort(flag_ms)
    gaps = np.diff(flags) / td.DAY_MS > pp.CAMPAIGN_MAX_GAP_DAYS
    return flags[np.concatenate(([True], gaps))]


# --------------------------------------------------------------------------
# E3
# --------------------------------------------------------------------------
def window_of(t_days, windows):
    for lo, hi, key in windows:
        if float(lo) <= t_days < float(hi):
            return str(key)
    return ""


def class_rates(corpus, scored, threshold, shipped=None):
    """Confirmed-flag rate per sampling-geometry class, and the p90/p10
    dispersion across classes carrying at least the registered exposure."""
    per_class = {}
    total_flags = 0
    total_days = 0.0
    shipped_per_class = {}
    for norad in corpus.norads:
        row = scored.get(norad)
        if row is None:
            continue
        flags = tm.confirmed_flags(row["dA"], row["sign"], row["epoch_ms"],
                                   row["valid"], threshold)
        epochs = row["epoch_ms"].astype(np.float64)
        if epochs.size == 0:
            continue
        origin = epochs[0]
        total_flags += int(flags.size)
        for lo, hi, key in corpus.windows[norad]:
            lo, hi, key = float(lo), float(hi), str(key)
            if not key:
                key = "__abstained__"
            wlo = origin + lo * td.DAY_MS
            whi = origin + hi * td.DAY_MS
            inside = (epochs >= wlo) & (epochs < whi)
            if not inside.any():
                continue
            days = (hi - lo)
            block = per_class.setdefault(key, {"windows": 0, "days": 0.0,
                                               "flags": 0, "objects": set()})
            block["windows"] += 1
            block["days"] += days
            block["flags"] += int(np.count_nonzero((flags >= wlo) & (flags < whi)))
            block["objects"].add(int(norad))
            total_days += days
            if shipped is not None and norad in shipped:
                s = shipped[norad]
                sb = shipped_per_class.setdefault(key, {"days": 0.0, "flags": 0})
                sb["days"] += days
                sb["flags"] += int(np.count_nonzero((s >= wlo) & (s < whi)))

    def dispersion(store, key_days="days", key_flags="flags", gate=None):
        rates = []
        for key, block in store.items():
            if key == "__abstained__":
                continue
            if gate is not None and gate.get(key, {}).get("windows", 0) < MIN_CLASS_WINDOWS:
                continue
            if block[key_days] > 0:
                rates.append(block[key_flags] / block[key_days])
        if len(rates) < 3:
            return {"measured": False,
                    "reason": f"only {len(rates)} class(es) carry the "
                              f"registered exposure of {MIN_CLASS_WINDOWS} "
                              f"windows; UNMEASURED, never zero",
                    "classes": len(rates)}
        p10, p90 = np.percentile(rates, [10.0, 90.0])
        return {"measured": True, "classes": len(rates),
                "p10": float(p10), "p90": float(p90),
                "p90OverP10": (float(p90 / p10) if p10 > 0 else None),
                "p10IsZero": bool(p10 <= 0.0)}

    out = {
        "totalFlags": total_flags,
        "totalWindowDays": total_days,
        "flagsPerWindowDay": (total_flags / total_days) if total_days else None,
        "classes": {k: {"windows": v["windows"], "windowDays": v["days"],
                        "flags": v["flags"], "objects": len(v["objects"]),
                        "flagsPerWindowDay": (v["flags"] / v["days"]) if v["days"] else None,
                        "underpowered": len(v["objects"]) < UNDERPOWERED_BELOW}
                    for k, v in sorted(per_class.items())},
        "dispersion": dispersion(per_class, gate=per_class),
    }
    if shipped is not None:
        out["shippedDetectorDispersion"] = dispersion(
            shipped_per_class, gate=per_class)
    return out


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--device", default="cpu")
    args = ap.parse_args(argv)

    say = print
    model, meta = tm.load_checkpoint(args.checkpoint)
    db = td.open_archive()
    labels, stable = load_labels()
    stable_by_sat = {}
    for win in stable:
        stable_by_sat.setdefault(win["sat"], []).append(win)

    out = {
        "registration": "docs/t18-preregistration-20260922.md",
        "registrationCommit": "2618343",
        "generatedUtc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "variant": meta["variant"],
        "modelVersion": f"t18-learned-model/20260922/{meta['variant']}",
        "checkpoint": str(args.checkpoint),
        "checkpointSha256": meta.get("checkpointSha256"),
        "modelMeta": {k: meta[k] for k in
                      ("seed", "parameters", "steps", "peakMiB", "claimMiB",
                       "durationS", "device", "stepRateMark", "coTenanted",
                       "bestValidationNll", "learnedDegreesOfFreedom",
                       "startedUtc")},
        "compositionLimits": COMPOSITION_LIMITS,
        "baseline": {
            "instrument": "tools/proximity_plane.detect_manoeuvres, shipped "
                          "settings, imported and called, never edited",
            "source": "docs/t16b-truthset-recall-20260922.json arms.pooled."
                      "windows.madleoEventWindow",
            "recall": BASELINE_RECALL,
            "flagsPerQuietWindowDay": BASELINE_FLAGS_PER_QUIET_WINDOW_DAY,
            "byDaBin": {"<20 m": [6, 576], "20-50 m": [2, 342],
                        "50-100 m": [1, 53], "100-200 m": [10, 27],
                        "200-500 m": [21, 36], ">=500 m": [50, 100]},
            "byFloor": {"aboveFloor": [81, 157], "belowFloor": [9, 977]},
        },
    }

    # ---- E1 ---------------------------------------------------------------
    truth_corpus = tm.Corpus(args.data_dir / "test-truth.npz")
    truth_scored_raw = tm.score_corpus(model, meta, truth_corpus, args.device)
    norad_to_sat = {v: k for k, v in SAT_NORAD.items()}
    scored = {norad_to_sat[n]: row for n, row in truth_scored_raw.items()
              if n in norad_to_sat}
    say(f"scored {len(scored)} truth spacecraft")

    baseline_blob = json.loads(BASELINE_JSON.read_text())
    per_sat_baseline = baseline_blob["arms"]["pooled"]["perSpacecraft"]
    floors = {sat: per_sat_baseline[sat]["floor"]["minDetectableDaMetres"]
              for sat in per_sat_baseline}

    elements = {}
    for sat, norad in SAT_NORAD.items():
        rows = db.execute(
            "SELECT epoch_ms, mean_motion_q FROM element_set WHERE norad=? "
            "ORDER BY epoch_ms", (norad,)).fetchall()
        arr = np.asarray(rows, dtype=np.float64)
        elements[sat] = {"epoch_ms": arr[:, 0].astype(np.int64),
                         "n": arr[:, 1] / 1e8}

    chosen, curve = sweep_threshold(scored, stable_by_sat,
                                    BASELINE_FLAGS_PER_QUIET_WINDOW_DAY, say)
    if chosen is None:
        out["E1"] = {"measured": False,
                     "reason": "no threshold meets the baseline's false-flag "
                               "rate without driving the flag count to zero; "
                               "no recall is quoted"}
    else:
        tau = chosen["threshold"]
        say(f"matched threshold {tau:.4f} at "
            f"{chosen['flagsPerQuietWindowDay']:.6f} flags/quiet-window-day")
        out["E1"] = {
            "measured": True,
            "matchedOperatingPoint": chosen,
            "A1_unseenObjectAnyEra": measure_e1(
                scored, labels, stable_by_sat, elements, floors, tau, "A1"),
            "A2_unseenObjectUnseenEra": measure_e1(
                scored, labels, stable_by_sat, elements, floors, tau, "A2",
                min_event_ms=td.T_CUT_MS),
            "sweep": curve[::max(1, len(curve) // 120)],
        }
        lower = out["E1"]["A1_unseenObjectAnyEra"]["overall"]["wilson95"]
        out["E1"]["screenE1"] = {
            "screen": "the learned model's recall Wilson lower bound must "
                      "exceed the shipped detector's Wilson upper bound of "
                      "9.656% at the matched false-flag rate",
            "learnedLower": (lower[0] * 100.0) if lower else None,
            "baselineUpper": BASELINE_RECALL["wilson95"][1] * 100.0,
            "clears": bool(lower and lower[0] > BASELINE_RECALL["wilson95"][1]),
        }

    # ---- E3 ---------------------------------------------------------------
    passive = tm.Corpus(args.data_dir / "test-passive.npz")
    routine = tm.Corpus(args.data_dir / "test-routine.npz")
    passive_scored = tm.score_corpus(model, meta, passive, args.device)
    routine_scored = tm.score_corpus(model, meta, routine, args.device)
    pool = np.concatenate([r["dA"][r["valid"]] for r in passive_scored.values()
                           if r["valid"].any()])
    tau_e3 = float(np.percentile(pool, 100.0 * (1.0 - E3_FALSE_ALARM_FRACTION)))
    say(f"E3 threshold fixed on the passive null at {tau_e3:.4f} "
        f"({E3_FALSE_ALARM_FRACTION:.0%} of scored steps)")

    shipped_passive = {n: shipped_flags(db, n) for n in passive.norads}
    shipped_passive = {k: v for k, v in shipped_passive.items() if v is not None}
    passive_rates = class_rates(passive, passive_scored, tau_e3, shipped_passive)
    routine_rates = class_rates(routine, routine_scored, tau_e3)
    ratio = (routine_rates["flagsPerWindowDay"] / passive_rates["flagsPerWindowDay"]
             if passive_rates["flagsPerWindowDay"] else None)
    out["E3"] = {
        "thresholdFixedOnPassiveNull": tau_e3,
        "registeredFalseAlarmFraction": E3_FALSE_ALARM_FRACTION,
        "passiveNull": {"objects": len(passive_scored), **passive_rates},
        "routineOperations": {"objects": len(routine_scored),
                              "source": "docs/t10b-drift-control-20260922.jsonl "
                                        "north-south keepers, test partition, "
                                        "admissible",
                              **routine_rates},
        "ratio": ratio,
        "screenE3": {
            "screen": f"the routine-keeper flag rate may not exceed the "
                      f"passive null's by more than {E3_RATIO_SCREEN}",
            "fires": bool(ratio is not None and ratio > E3_RATIO_SCREEN),
            "underpoweredNote": "a population below 20 supporting objects is "
                                "UNDERPOWERED and lends its name to nothing",
        },
    }
    if not routine_scored:
        out["E3"]["routineOperations"]["measured"] = False
        out["E3"]["routineOperations"]["reason"] = (
            "no routine keeper survived the partition and admissibility rule; "
            "UNMEASURED, never zero")

    # ---- G: the geometry probe -------------------------------------------
    train_corpus = tm.Corpus(args.data_dir / "train.npz")
    test_corpus = tm.Corpus(args.data_dir / "test-general.npz")
    train_rows = tm.window_embeddings(model, meta, train_corpus, args.device)
    test_rows = tm.window_embeddings(model, meta, test_corpus, args.device)
    context = object_context(db, sorted({r["norad"] for r in train_rows}
                                        | {r["norad"] for r in test_rows}))
    for row in train_rows + test_rows:
        ctx = context.get(row["norad"])
        if ctx is None:
            row["behaviourClass"] = ""
            continue
        # registration 3.6 fallback: the T13 v1 library is not committed, so
        # the behaviour target is the T14 class baseline alone. Recorded.
        row["behaviourClass"] = (f"{ctx['regime']}|{ctx['era']}|{ctx['bus']}"
                                 if ctx["bus"] else
                                 f"{ctx['regime']}|{ctx['era']}")
    sampling = tm.normalised_probe(train_rows, test_rows, "samplingClass")
    behaviour = tm.normalised_probe(train_rows, test_rows, "behaviourClass")
    out["G_geometryProbe"] = {
        "trainWindows": len(train_rows),
        "testWindows": len(test_rows),
        "behaviourTarget": "the T14 class baseline (regime x era x bus family "
                           "where catalogued), because the T13 v1 library is "
                           "not committed; registration 3.6's registered "
                           "fallback, recorded here, and the gate is re-run on "
                           "T13 types when they land",
        "samplingProbe": sampling,
        "behaviourProbe": behaviour,
        "verdict": tm.gate_g(sampling, behaviour),
    }

    # ---- G5: the leakage audit, published rather than asserted ------------
    if train_rows and test_rows:
        train_emb = np.stack([r["embedding"] for r in train_rows])
        test_emb = np.stack([r["embedding"] for r in test_rows])
        rng = np.random.default_rng(td.SEED)
        sample = test_emb[rng.choice(test_emb.shape[0],
                                     size=min(2000, test_emb.shape[0]),
                                     replace=False)]
        nearest = (sample @ train_emb.T).max(axis=1)
        # The within-training comparison must exclude each window's similarity
        # to ITSELF, which is 1 by construction. Masking the leading diagonal
        # of a SAMPLED block masks the wrong entries and publishes a reference
        # distribution that is all ones; the row's own index is masked here.
        idx = rng.choice(train_emb.shape[0],
                         size=min(2000, train_emb.shape[0]), replace=False)
        sims = train_emb[idx] @ train_emb.T
        sims[np.arange(idx.size), idx] = -np.inf
        within = sims.max(axis=1)
        out["G5_leakageAudit"] = {
            "statistic": "cosine similarity of a test window's frozen "
                         "embedding to its nearest training window",
            "testToTrain": {q: float(np.percentile(nearest, q))
                            for q in (5, 25, 50, 75, 95, 99)},
            "trainToTrain": {q: float(np.percentile(within, q))
                             for q in (5, 25, 50, 75, 95, 99)},
            "note": "the distribution is published; it is not asserted to "
                    "show the split worked",
        }

    # ---- the ingest-latency hazard, measured rather than assumed ----------
    lat = []
    ep = []
    for norad in train_corpus.norads[:200]:
        cad = train_corpus.cadence[norad]
        lat.append(cad[:, 3])
        ep.append(train_corpus.epoch[norad].astype(np.float64))
    if lat:
        lat = np.concatenate(lat)
        ep = np.concatenate(ep)
        keep = np.isfinite(lat) & np.isfinite(ep)
        corr = float(np.corrcoef(lat[keep], ep[keep])[0, 1])
        out["ingestLatencyHazard"] = {
            "pearsonWithEpoch": corr,
            "note": "the archive was back-filled, so `ingest_hour` on a "
                    "historical row is the back-fill time and the latency "
                    "channel is close to a clock. It is a registered input and "
                    "is kept, but a cadence-only model can read absolute era "
                    "from it, and any era-shaped result must be read with this "
                    "number beside it.",
        }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=1, sort_keys=True,
                                   default=float) + "\n")
    say(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
