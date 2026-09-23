#!/usr/bin/env python3
"""T16b measurement (A): how fast a propagated element set goes wrong, against
a precise orbit.

Registered in docs/t16b-truthset-preregistration-20260922.md. Nothing here may
be changed to chase a number; deviations are written into the results document
under their own heading.

What it does, per spacecraft:

  1. takes the FIRST archive element set of each UTC day inside the registered
     epoch window;
  2. propagates it with the programme's own SGP4 (tools/truthset_sgp4.mjs) to
     epoch + {0, 1, 3, 7, 14, 30, 60, 90} days;
  3. rotates TEME -> PEF at UT1 and PEF -> ITRF with polar motion;
  4. differences against the precise orbit at the truth product's own nearest
     sample, and resolves the difference into radial / along-track /
     cross-track components and an along-track phase angle;
  5. reports quantiles per horizon, the horizon at which the median along-track
     error crosses the co-orbital station threshold T8b uses, and the same
     table over the subset of intervals containing no labelled manoeuvre.

Usage:
  truthset_growth.py --out docs/t16b-truthset-growth-20260922.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import truthset_truth as tt                                     # noqa: E402

REPO = Path(__file__).resolve().parents[1]
# Installation-specific locations. Each is named by an environment variable
# and falls back to a placeholder that cannot resolve, so an unconfigured
# checkout fails with the name of the variable it needs instead of reading
# whatever happens to sit at somebody else's path.
TRUTH_ROOT = Path(os.environ.get("ORBIT_TRUTHSET_ROOT",
                                 "truthset.not-configured"))
ARCHIVE = Path(os.environ.get("ORBIT_ARCHIVE_DB",
                              "element-archive.not-configured.sqlite3"))
BRIDGE = Path(__file__).resolve().parent / "truthset_sgp4.mjs"
NODE = Path(os.environ.get("ORBIT_NODE", "") or shutil.which("node") or "node")

# --- the registration's own constants --------------------------------------
EPOCH_START = "2023-01-01"
EPOCH_END = "2023-10-03"
TRUTH_START = "2023-01-01"
TRUTH_END = "2024-01-01"
HORIZON_DAYS = (0, 1, 3, 7, 14, 30, 60, 90)

# T8b's co-orbital station thresholds, in degrees of relative along-track
# phase: the primary arm and the tightest registered arm. Screens, not laws.
GAMMA_PRIMARY_DEG = 5.0
GAMMA_TIGHT_DEG = 0.2085

# MAD-LEO's own screen for "a plausible unreported orbit change", reused here
# only to count steps in the truth product itself.
A_STEP_SCREEN_M = 20.0

# gate A1 bars, by product sampling
OFFSET_BAR_S = {"eof": 5.0, "sp3": 30.0}
OFFSET_BAR_FRACTION = 0.01
MIN_N_PER_ROW = 30

# the archive's own quantisation scales (pipeline/orbit_history.py)
SCALE_MEAN_MOTION = 10 ** 8
SCALE_ECCENTRICITY = 10 ** 8
SCALE_ANGLE = 10 ** 4
SCALE_BSTAR = 10 ** 12
SCALE_NDOT = 10 ** 8
SCALE_NDDOT = 10 ** 13

DAY_MS = 86400000

MISSIONS = {
    "sentinel-1a": {
        "norad": 39634, "kind": "eof", "dir": "eof/s1a",
        "product": "Copernicus AUX_POEORB (Earth Explorer XML), EARTH_FIXED, UTC, 10 s",
        "ids": None, "idsCode": None,
    },
    "sentinel-3a": {
        "norad": 41335, "kind": "sp3", "dir": "sp3/s3a",
        "product": "CNES/SSALTO POE SP3-c version 30 (POE-G), ITRF, TAI, 60 s",
        "ids": "ids/s3aman.txt", "idsCode": "SEN3A",
    },
    "sentinel-3b": {
        "norad": 43437, "kind": "sp3", "dir": "sp3/s3b",
        "product": "CNES/SSALTO POE SP3-c version 30 (POE-G), ITRF, TAI, 60 s",
        "ids": "ids/s3bman.txt", "idsCode": "SEN3B",
    },
}


def iso_ms(text: str) -> int:
    return int(dt.datetime.fromisoformat(text).replace(
        tzinfo=dt.timezone.utc).timestamp() * 1000)


def ms_iso(ms: int) -> str:
    return dt.datetime.fromtimestamp(ms / 1000.0, dt.timezone.utc).isoformat(
        timespec="milliseconds").replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# the archive
# ---------------------------------------------------------------------------
def daily_first_element_sets(norad: int, lo_ms: int, hi_ms: int):
    """The first element set of each UTC day in [lo, hi), as OMM dictionaries."""
    db = sqlite3.connect(f"file:{ARCHIVE}?mode=ro", uri=True)
    rows = db.execute(
        "SELECT epoch_ms, mean_motion_q, eccentricity_q, inclination_q, raan_q, "
        "arg_perigee_q, mean_anomaly_q, bstar_q, ndot_q, nddot_q "
        "FROM element_set WHERE norad=? AND epoch_ms>=? AND epoch_ms<? "
        "ORDER BY epoch_ms", (norad, lo_ms, hi_ms)).fetchall()
    db.close()
    seen = set()
    out = []
    for row in rows:
        day = row[0] // DAY_MS
        if day in seen:
            continue
        seen.add(day)
        out.append({
            "epochMs": int(row[0]),
            "omm": {
                "NORAD_CAT_ID": norad,
                "EPOCH": ms_iso(int(row[0])).replace("Z", ""),
                "MEAN_MOTION": row[1] / SCALE_MEAN_MOTION,
                "ECCENTRICITY": row[2] / SCALE_ECCENTRICITY,
                "INCLINATION": row[3] / SCALE_ANGLE,
                "RA_OF_ASC_NODE": row[4] / SCALE_ANGLE,
                "ARG_OF_PERICENTER": row[5] / SCALE_ANGLE,
                "MEAN_ANOMALY": row[6] / SCALE_ANGLE,
                "BSTAR": 0.0 if row[7] is None else row[7] / SCALE_BSTAR,
                "MEAN_MOTION_DOT": 0.0 if row[8] is None else row[8] / SCALE_NDOT,
                "MEAN_MOTION_DDOT": 0.0 if row[9] is None else row[9] / SCALE_NDDOT,
            },
        })
    return out


# ---------------------------------------------------------------------------
# labelled manoeuvres (IDS/DORIS mission-reported histories)
# ---------------------------------------------------------------------------
def parse_ids_manoeuvres(path: Path, code: str):
    """Mission-reported manoeuvre start epochs, in UTC milliseconds.

    Record layout, from the files themselves: a spacecraft code, the reported
    operation start as year / day-of-year / hour / minute, the same for the
    end, a mission record code, the impulse count, and then one block per
    impulse. The operation start is taken as the event epoch here; the
    per-impulse epochs inside the record are minutes away and the use of this
    list -- excluding intervals that contain a manoeuvre -- does not resolve
    minutes.
    """
    out = []
    for line in path.read_text(errors="replace").splitlines():
        parts = line.split()
        if len(parts) < 10 or parts[0] != code:
            continue
        try:
            year, doy, hh, mm = (int(parts[1]), int(parts[2]),
                                 int(parts[3]), int(parts[4]))
            when = (dt.datetime(year, 1, 1, tzinfo=dt.timezone.utc)
                    + dt.timedelta(days=doy - 1, hours=hh, minutes=mm))
        except (ValueError, OverflowError):
            continue
        out.append(int(when.timestamp() * 1000))
    return sorted(out)


# ---------------------------------------------------------------------------
# the propagator bridge
# ---------------------------------------------------------------------------
def run_propagator(jobs):
    payload = json.dumps({"jobs": jobs})
    proc = subprocess.run([str(NODE), str(BRIDGE)], input=payload.encode(),
                          capture_output=True, cwd=str(REPO))
    if proc.returncode != 0:
        raise RuntimeError(f"propagator failed: {proc.stderr.decode()[:2000]}")
    return json.loads(proc.stdout.decode())["results"]


# ---------------------------------------------------------------------------
# statistics
# ---------------------------------------------------------------------------
def quantiles(values):
    if values.size == 0:
        return None
    q = np.percentile(values, [25, 50, 75, 95])
    return {"n": int(values.size), "p25": float(q[0]), "p50": float(q[1]),
            "p75": float(q[2]), "p95": float(q[3])}


def crossing_horizon(medians_deg, horizons, bar_deg):
    """The horizon at which the median first exceeds `bar_deg`.

    Linear interpolation of log(median) against log(horizon) between the two
    bracketing measured horizons, as registered. Never extrapolated: outside
    the measured range the answer is a sentence, not a number.
    """
    pairs = [(h, m) for h, m in zip(horizons, medians_deg)
             if h > 0 and m is not None and m > 0]
    if not pairs:
        return {"crossed": False,
                "note": "no usable median at any measured horizon"}
    if pairs[0][1] > bar_deg:
        return {"crossed": True, "beforeFirstHorizon": True,
                "note": f"already above the threshold at +{pairs[0][0]} d, "
                        f"the shortest measured horizon"}
    for (h0, m0), (h1, m1) in zip(pairs, pairs[1:]):
        if m1 > bar_deg >= m0:
            lm0, lm1 = math.log(m0), math.log(m1)
            lh0, lh1 = math.log(h0), math.log(h1)
            frac = (math.log(bar_deg) - lm0) / (lm1 - lm0)
            return {"crossed": True,
                    "horizonDays": float(math.exp(lh0 + frac * (lh1 - lh0))),
                    "bracket": [h0, h1]}
    return {"crossed": False,
            "note": f"not reached within the measured horizons "
                    f"(median {pairs[-1][1]:.4g} deg at +{pairs[-1][0]} d, "
                    f"threshold {bar_deg} deg); no extrapolation is given"}


# ---------------------------------------------------------------------------
def truth_cache(name: str, spec: dict, say):
    cache = TRUTH_ROOT / f"cache-{name}.npz"
    if cache.exists():
        z = np.load(cache)
        return z["t"], z["pos"], z["vel"]
    src = TRUTH_ROOT / spec["dir"]
    paths = sorted(p for p in src.iterdir() if p.is_file())
    say(f"  parsing {len(paths)} {spec['kind']} files for {name}")
    t, pos, vel = tt.load_truth(paths, spec["kind"])
    np.savez(cache, t=t, pos=pos, vel=vel)
    return t, pos, vel


def product_properties(name: str, spec: dict):
    """Properties measured from the fetched files, not quoted from docs."""
    man = TRUTH_ROOT / ("manifest-s1.json" if spec["kind"] == "eof"
                        else f"manifest-{spec['dir'].split('/')[-1]}.json")
    if not man.exists():
        return {"note": "no manifest"}
    rows = json.loads(man.read_text())["files"]
    out = {"files": len(rows),
           "bytes": sum(r["bytes"] for r in rows)}
    lat = [r["latencyDays"] for r in rows if "latencyDays" in r]
    if lat:
        lat = np.asarray(lat)
        out["latencyDays"] = {"p5": float(np.percentile(lat, 5)),
                              "p50": float(np.median(lat)),
                              "p95": float(np.percentile(lat, 95))}
    spans = [(r.get("arcStart"), r.get("arcEnd")) for r in rows
             if r.get("arcStart")]
    if spans:
        lens = [(dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days
                for a, b in spans]
        out["arcLengthDays"] = {"min": int(min(lens)), "median": float(np.median(lens)),
                                "max": int(max(lens))}
    return out


def truth_step_days(t_ms, pos, vel):
    """Days on which the truth product's own daily-mean semi-major axis steps
    by more than the 20 m screen. A screen, not a detection claim."""
    a = tt.semi_major_axis_m(pos, vel)
    day = t_ms // DAY_MS
    uniq, inverse = np.unique(day, return_inverse=True)
    sums = np.bincount(inverse, weights=a)
    counts = np.bincount(inverse)
    mean_a = sums / counts
    steps = np.abs(np.diff(mean_a))
    contiguous = np.diff(uniq) == 1
    usable = steps[contiguous]
    flagged = usable > A_STEP_SCREEN_M
    out = {"days": int(uniq.size),
           "stepDaysAboveScreen": int(flagged.sum()),
           "screenMetres": A_STEP_SCREEN_M,
           "medianStepMetres": float(np.median(usable)) if usable.size else None,
           "p95StepMetres": float(np.percentile(usable, 95)) if usable.size else None}
    # POST-REGISTRATION DIAGNOSTIC, labelled as such. The registered 20 m
    # screen is MAD-LEO's, and it was defined on a TLE bracket across a 30 h
    # window, not on the day-to-day step of a daily-mean OSCULATING semi-major
    # axis, which carries the J2 short-period and eccentricity-cycle variation
    # as well. An outlier rule on the same series is reported beside it so the
    # difference between "a step" and "an unusual step" is visible.
    if usable.size:
        med = float(np.median(usable))
        mad = float(np.median(np.abs(usable - med))) * 1.4826
        bar = med + 5.0 * mad
        out["outlierRule"] = {
            "barMetres": bar,
            "daysAboveBar": int((usable > bar).sum()),
            "note": "post-registration diagnostic: median + 5 x MAD of the "
                    "day-to-day step of the truth's own daily-mean osculating "
                    "semi-major axis",
        }
    return out


def measure(name: str, spec: dict, eop: tt.EarthOrientation, say):
    t_truth, pos_truth, vel_truth = truth_cache(name, spec, say)
    say(f"  truth: {t_truth.size} samples "
        f"{ms_iso(int(t_truth[0]))} .. {ms_iso(int(t_truth[-1]))}")

    sets = daily_first_element_sets(spec["norad"], iso_ms(EPOCH_START),
                                    iso_ms(EPOCH_END))
    say(f"  archive: {len(sets)} daily element sets in the epoch window")

    manoeuvres = []
    if spec["ids"]:
        manoeuvres = parse_ids_manoeuvres(TRUTH_ROOT / spec["ids"], spec["idsCode"])
    man_arr = np.asarray(manoeuvres, dtype=np.int64)

    # --- build the comparison instants -------------------------------------
    jobs = []
    plan = []                      # (epochMs, horizon, targetMs, truthIndex)
    bar = OFFSET_BAR_S[spec["kind"]]
    dropped = 0
    for i, es in enumerate(sets):
        samples = []
        for h in HORIZON_DAYS:
            want = es["epochMs"] + h * DAY_MS
            k = int(np.searchsorted(t_truth, want))
            cand = [j for j in (k - 1, k) if 0 <= j < t_truth.size]
            if not cand:
                dropped += 1
                continue
            j = min(cand, key=lambda idx: abs(int(t_truth[idx]) - want))
            offset_s = abs(int(t_truth[j]) - want) / 1000.0
            if offset_s > bar:
                dropped += 1
                continue
            t_ms = int(t_truth[j])
            plan.append((es["epochMs"], h, t_ms, j, offset_s))
            samples.append({"t": t_ms, "gmstMs": t_ms})
        if samples:
            jobs.append({"id": i, "omm": es["omm"], "samples": samples})

    # UT1 correction for the whole batch at once
    all_t = np.asarray([p[2] for p in plan], dtype=np.int64)
    xp, yp, dut1 = eop.at_ms(all_t)
    eop_by_t = {int(t): (float(a), float(b), float(c))
                for t, a, b, c in zip(all_t.tolist(), xp, yp, dut1)}
    for job in jobs:
        for sample in job["samples"]:
            sample["gmstMs"] = sample["t"] + eop_by_t[sample["t"]][2] * 1000.0

    say(f"  propagating {sum(len(j['samples']) for j in jobs)} instants "
        f"({dropped} dropped by the offset bar)")
    results = run_propagator(jobs)

    got = {}
    failures = 0
    for row in results:
        if not row.get("ok"):
            failures += 1
            continue
        got[(row["id"], row["t"])] = row["pef"]

    # --- resolve every comparison ------------------------------------------
    by_horizon = {h: {"along": [], "cross": [], "radial": [], "phase": [],
                      "alongFree": [], "phaseFree": [], "offsets": [],
                      "alongSigned": []}
                  for h in HORIZON_DAYS}
    id_of_epoch = {es["epochMs"]: i for i, es in enumerate(sets)}

    for epoch_ms, h, t_ms, j, offset_s in plan:
        key = (id_of_epoch[epoch_ms], t_ms)
        pef = got.get(key)
        if pef is None:
            continue
        xp_i, yp_i, _ = eop_by_t[t_ms]
        r_prop = tt.pef_to_itrf(np.asarray(pef) * 1000.0, xp_i, yp_i)
        r_truth = pos_truth[j]
        v_truth = vel_truth[j]
        radial, along, cross = tt.rtn_basis(r_truth, v_truth)
        delta = r_prop - r_truth
        d_r = float(np.dot(delta, radial))
        d_t = float(np.dot(delta, along))
        d_c = float(np.dot(delta, cross))
        rmag = float(np.linalg.norm(r_truth))
        bucket = by_horizon[h]
        bucket["radial"].append(abs(d_r) / 1000.0)
        bucket["along"].append(abs(d_t) / 1000.0)
        bucket["alongSigned"].append(d_t / 1000.0)
        bucket["cross"].append(abs(d_c) / 1000.0)
        bucket["phase"].append(abs(d_t) / rmag * 180.0 / math.pi)
        bucket["offsets"].append(offset_s)
        if man_arr.size and h > 0:
            inside = np.count_nonzero((man_arr > epoch_ms) & (man_arr < t_ms))
        else:
            inside = 0
        if man_arr.size and inside == 0:
            bucket["alongFree"].append(abs(d_t) / 1000.0)
            bucket["phaseFree"].append(abs(d_t) / rmag * 180.0 / math.pi)

    rows = {}
    medians_deg = []
    medians_deg_free = []
    for h in HORIZON_DAYS:
        b = by_horizon[h]
        arr = {k: np.asarray(v, dtype=np.float64) for k, v in b.items()}
        row = {
            "horizonDays": h,
            "n": int(arr["along"].size),
            "radialKm": quantiles(arr["radial"]),
            "alongTrackKm": quantiles(arr["along"]),
            "crossTrackKm": quantiles(arr["cross"]),
            "alongTrackPhaseDeg": quantiles(arr["phase"]),
            # signed, because a residual that is a BIAS at epoch and a
            # residual that is scatter are different objects, and gate A4
            # cannot be read without knowing which one the +0 d row is
            "alongTrackSignedKm": quantiles(arr["alongSigned"]),
            "maxTruthOffsetSeconds": float(arr["offsets"].max()) if arr["offsets"].size else None,
            "manoeuvreFree": {
                "alongTrackKm": quantiles(arr["alongFree"]),
                "alongTrackPhaseDeg": quantiles(arr["phaseFree"]),
            } if man_arr.size else None,
            "belowMinimumN": bool(arr["along"].size < MIN_N_PER_ROW),
        }
        rows[str(h)] = row
        medians_deg.append(row["alongTrackPhaseDeg"]["p50"]
                           if row["alongTrackPhaseDeg"] else None)
        free = row["manoeuvreFree"]["alongTrackPhaseDeg"] if row["manoeuvreFree"] else None
        medians_deg_free.append(free["p50"] if free else None)

    mean_radius_km = float(np.mean(np.linalg.norm(pos_truth[::997], axis=1)) / 1000.0)
    horizons = list(HORIZON_DAYS)
    out = {
        "mission": name,
        "norad": spec["norad"],
        "truthProduct": spec["product"],
        "truthProductMeasured": product_properties(name, spec),
        "epochWindow": [EPOCH_START, EPOCH_END],
        "truthWindow": [TRUTH_START, TRUTH_END],
        "elementSets": len(sets),
        "comparisonsPlanned": len(plan),
        "comparisonsDropped": dropped,
        "propagatorFailures": failures,
        "meanRadiusKm": mean_radius_km,
        "horizons": rows,
        "labelledManoeuvresInTruthWindow": int(np.count_nonzero(
            (man_arr >= iso_ms(TRUTH_START)) & (man_arr < iso_ms(TRUTH_END)))) if man_arr.size else None,
        "labelSource": spec["ids"],
        "truthStepScreen": truth_step_days(t_truth, pos_truth, vel_truth),
        "stationThreshold": {
            "gammaPrimaryDeg": GAMMA_PRIMARY_DEG,
            "gammaPrimaryKm": GAMMA_PRIMARY_DEG * math.pi / 180.0 * mean_radius_km,
            "gammaTightDeg": GAMMA_TIGHT_DEG,
            "gammaTightKm": GAMMA_TIGHT_DEG * math.pi / 180.0 * mean_radius_km,
        },
        "crossing": {
            "primary": crossing_horizon(medians_deg, horizons, GAMMA_PRIMARY_DEG),
            "tight": crossing_horizon(medians_deg, horizons, GAMMA_TIGHT_DEG),
            "primaryManoeuvreFree": crossing_horizon(medians_deg_free, horizons,
                                                     GAMMA_PRIMARY_DEG) if man_arr.size else None,
            "tightManoeuvreFree": crossing_horizon(medians_deg_free, horizons,
                                                   GAMMA_TIGHT_DEG) if man_arr.size else None,
        },
    }

    # --- gates --------------------------------------------------------------
    planned = len(plan) + dropped
    out["gates"] = {
        "A1_offsetBar": {
            "barSeconds": bar,
            "droppedFraction": dropped / planned if planned else 0.0,
            "fires": bool(planned and dropped / planned > OFFSET_BAR_FRACTION),
        },
        "A2_rowCounts": {
            "minimumN": MIN_N_PER_ROW,
            "rowsBelow": [h for h in HORIZON_DAYS if rows[str(h)]["belowMinimumN"]],
        },
        "A4_zeroHorizon": {
            "alongTrackKm": rows["0"]["alongTrackKm"],
            "note": "the instrument's own floor: the element set differenced "
                    "against the truth at its own epoch",
        },
    }
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path,
                    default=REPO / "docs" / "t16b-truthset-growth-20260922.json")
    ap.add_argument("--mission", action="append",
                    help="restrict to one mission (repeatable)")
    args = ap.parse_args(argv)

    def say(msg):
        print(msg, flush=True)

    eop = tt.EarthOrientation(TRUTH_ROOT / "eop" / "finals2000A.all")
    names = args.mission or list(MISSIONS)
    out = {"registration": "docs/t16b-truthset-preregistration-20260922.md",
           "generatedUtc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "horizonDays": list(HORIZON_DAYS),
           "missions": {}}
    for name in names:
        say(f"{name}:")
        out["missions"][name] = measure(name, MISSIONS[name], eop, say)
    args.out.write_text(json.dumps(out, indent=2) + "\n")
    say(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
