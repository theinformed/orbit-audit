#!/usr/bin/env python3
"""T3 step 4: the peak-frequency line profile, and the derivations that read it.

**THIS IS DESCRIPTIVE, NOT A REGISTERED TEST.**
`docs/cadence-preregistration-20260921.md` registers a per-object significance
verdict (E1/E3) and a cadence distribution by regime and operator (E4). It does
not register a search for spectral lines in the pooled peak-frequency
distribution, and nothing this module prints carries a p-value or contributes
to a gate. It exists because the registered per-object test returned a null and
a null is worth nothing without a diagnosis: this module measures WHERE in the
band the periodogram peaks actually land, for the payload class and for the
free passive control side by side, so that the null can be explained rather
than merely reported.

Read every "excess" below as a ratio to a LOCAL background, never as evidence.
Two things about the grid make a naive reading wrong, and both are handled here:

* the frequency grid is uniform in FREQUENCY, so a fixed number of grid steps
  spans a period width that grows as P^2. Three steps is +/-0.11 d at a period
  of 14 days and +/-18.5 d at 182 days. A "line test" at long period is
  therefore not a line test at all, and the printed core half-width says so at
  every target.
* the peak distribution is nowhere near uniform over the grid, so a
  uniform-over-the-band expectation manufactures excess wherever the background
  is merely high. The expectation used here is a local annulus in frequency.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from tools import cadence_core as core  # noqa: E402
from tools.cadence_measure import CHANNELS  # noqa: E402

CORE_STEPS, GAP_STEPS, OUTER_STEPS = 3, 8, 40

# Natural periodicities the pre-registration's section 6.5 derived or cited, so
# that a line landing on one is recognised instead of being called a discovery.
NATURAL = (
    ("solar rotation (synodic Carrington)", 27.2753),
    ("sidereal month", 27.3217),
    ("anomalistic month", 27.5546),
    ("synodic month", 29.5306),
    ("half sidereal month", 13.6609),
    ("half synodic month", 14.7653),
    ("81-day F10.7 mean", 81.0),
    ("thermospheric semiannual", 182.6),
)
CONTROLS = (("control 21 d", 21.0), ("control 40 d", 40.0), ("control 70 d", 70.0))

MU_KM3_S2, EARTH_RADIUS_KM, J2 = core.MU_KM3_S2, core.EARTH_RADIUS_KM, 1.08263e-3
J22, GEO_RADIUS_KM = 1.8154e-6, 42164.2


def nodal_rate_deg_day(a_km: float, incl_deg: float, ecc: float = 0.0) -> float:
    """J2 nodal regression: dOmega/dt = -(3/2) J2 (Re/p)^2 n cos i."""
    p = a_km * (1.0 - ecc * ecc)
    n = math.sqrt(MU_KM3_S2 / a_km ** 3)
    return math.degrees(-1.5 * J2 * (EARTH_RADIUS_KM / p) ** 2 * n * math.cos(math.radians(incl_deg))) * 86400.0


def beta_period_days(a_km: float, incl_deg: float, ecc: float = 0.0) -> float:
    """Period of the orbit plane's geometry against the mean Sun (+0.9856 deg/day)."""
    return 360.0 / (abs(nodal_rate_deg_day(a_km, incl_deg, ecc)) + 0.9856)


def geo_longitude_acceleration_deg_day2() -> float:
    """Amplitude of d2(lambda)/dt2 = -18 n^2 J22 (Re/a)^2 sin(2(lam - lam22))."""
    n = 2.0 * math.pi / 86164.0905
    amplitude = 18.0 * n * n * J22 * (EARTH_RADIUS_KM / GEO_RADIUS_KM) ** 2
    return math.degrees(amplitude) * 86400.0 ** 2


def east_west_deadband_deg(period_days: float, acceleration_fraction: float = 1.0) -> float:
    """Deadband half-width implied by a one-sided parabolic drift cycle of `period_days`.

    Place the satellite at one edge with an initial drift rate, let the
    triaxial acceleration A carry it across the full deadband 2*dlam and back:
    the parabola's excursion from its vertex is (1/2) A (T/2)^2 = 2*dlam, so
    T = 4*sqrt(dlam/A) and dlam = A T^2 / 16.
    """
    return geo_longitude_acceleration_deg_day2() * acceleration_fraction * period_days ** 2 / 16.0


def load(artifacts: Path, shards, results_jsonl: Path, channel: str):
    tables = [np.load(p) for p in shards]
    data = {k: np.concatenate([t[k] for t in tables]) for k in tables[0].files}
    keep = data["channel"] == CHANNELS.index(channel)
    data = {k: v[keep] for k, v in data.items()}
    index = json.loads((artifacts / "index.json").read_text())
    meta = {int(o["norad"]): o for o in index["objects"]}
    rows = {r["norad"]: r for r in
            (json.loads(line) for line in open(results_jsonl))}
    klass = np.array([meta[int(n)]["class"] for n in data["norad"]])
    return data, klass, rows


def local_excess(freqs: np.ndarray, target_days: float, df: float):
    f0 = 1.0 / target_days
    delta = np.abs(freqs - f0) / df
    core_count = int(np.sum(delta <= CORE_STEPS))
    ring_count = int(np.sum((delta > GAP_STEPS) & (delta <= OUTER_STEPS)))
    core_width = 2 * CORE_STEPS + 1
    ring_width = 2 * (OUTER_STEPS - GAP_STEPS)
    expected = ring_count * core_width / ring_width
    return {"corePeaks": core_count,
            "coreHalfWidthDays": target_days ** 2 * df * CORE_STEPS,
            "localExpected": expected,
            "excess": (core_count / expected) if expected > 0 else None}


def run(artifacts: Path, shards, results_jsonl: Path, out: Path, channel: str) -> dict:
    data, klass, rows = load(artifacts, shards, results_jsonl, channel)
    freqs = data["freqCyclesPerDay"].astype(np.float64)
    df = 1.0 / (core.OVERSAMPLE * core.WINDOW_DAYS)

    profile = {}
    for cls in ("payload", "passive"):
        mask = klass == cls
        entry = {"windows": int(mask.sum()), "targets": {}}
        for name, target in NATURAL + CONTROLS:
            entry["targets"][name] = dict(local_excess(freqs[mask], target, df),
                                          periodDays=target)
        periods = 1.0 / freqs[mask]
        edges = [2, 10, 20, 30, 45, 60, 90, 120, 150, 175, 190, 205, 220.001]
        hist, _ = np.histogram(periods, bins=edges)
        entry["periodHistogramShare"] = {
            f"{edges[i]}-{edges[i + 1]}": round(float(hist[i] / hist.sum()), 4)
            for i in range(len(edges) - 1)}
        profile[cls] = entry

    # Sweep for narrow excesses that the payload class carries and the control does not.
    payload_mask = klass == "payload"
    passive_mask = klass == "passive"
    found = []
    for period in np.arange(3.0, 200.0, 0.25):
        p_stat = local_excess(freqs[payload_mask], float(period), df)
        if not p_stat["excess"] or p_stat["localExpected"] < 30:
            continue
        q_stat = local_excess(freqs[passive_mask], float(period), df)
        found.append((p_stat["excess"], float(period), p_stat, q_stat))
    found.sort(reverse=True)
    lines, seen = [], []
    for excess_value, period, p_stat, q_stat in found:
        if any(abs(period - q) < 0.05 * period for q in seen):
            continue
        seen.append(period)
        carriers = _carriers(data, klass, rows, period, df)
        lines.append({"periodDays": period, "payload": p_stat, "passive": q_stat,
                      "payloadOverPassiveExcess":
                          (p_stat["excess"] / q_stat["excess"]) if q_stat["excess"] else None,
                      **carriers})
        if len(lines) >= 12:
            break

    derivations = {
        "geoLongitudeAccelerationDegPerDay2": geo_longitude_acceleration_deg_day2(),
        "eastWestDeadbandDeg": {
            str(t): {"atMaxAcceleration": east_west_deadband_deg(t, 1.0),
                     "atHalfMaxAcceleration": east_west_deadband_deg(t, 0.5)}
            for t in (12.5, 14.0, 21.0, 30.0)},
        "cosmosShellBetaPeriodDays": {
            str(alt): {"betaPeriod": beta_period_days(EARTH_RADIUS_KM + alt, 74.0),
                       "halfBetaPeriod": beta_period_days(EARTH_RADIUS_KM + alt, 74.0) / 2.0}
            for alt in (1368, 1400, 1426, 1463)},
        "leo500km53degBetaPeriodDays": beta_period_days(EARTH_RADIUS_KM + 500.0, 53.0),
    }

    receipt = {"channel": channel,
               "registration": "docs/cadence-preregistration-20260921.md",
               "status": "DESCRIPTIVE DIAGNOSTIC -- not a registered test, no p-values",
               "gridResolutionCyclesPerDay": df,
               "coreSteps": CORE_STEPS, "backgroundAnnulusSteps": [GAP_STEPS, OUTER_STEPS],
               "profile": profile, "payloadOnlyLineSweep": lines,
               "derivations": derivations}
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True))
    return receipt


def _carriers(data, klass, rows, period, df):
    f0 = 1.0 / period
    sel = (np.abs(data["freqCyclesPerDay"].astype(np.float64) - f0) <= CORE_STEPS * df) \
        & (klass == "payload")
    norads = [int(n) for n in data["norad"][sel]]
    objects = sorted(set(norads))
    counts = Counter(norads)
    top = []
    for norad, count in counts.most_common(8):
        r = rows[norad]
        top.append({"norad": norad, "name": r["name"], "objectType": r["objectType"],
                    "regime": r["regime"], "windowsOnLine": count,
                    "windowsTotal": r["windows"],
                    "medianPerigeeKm": r["medianPerigeeKm"],
                    "medianInclinationDeg": r["medianInclinationDeg"],
                    "medianEccentricity": r["medianEccentricity"]})
    return {"payloadObjectsOnLine": len(objects),
            "regimeCounts": dict(Counter(rows[n]["regime"] for n in objects).most_common()),
            "operatorCounts": dict(Counter(rows[n]["operator"] for n in objects).most_common(6)),
            "topCarriers": top}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", required=True, type=Path)
    parser.add_argument("--shards", required=True, nargs="+", type=Path)
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--channel", default="mean_motion")
    args = parser.parse_args()
    receipt = run(args.artifacts, args.shards, args.results, args.out, args.channel)
    print(json.dumps({k: receipt[k] for k in ("profile", "derivations")},
                     indent=2, sort_keys=True)[:4000])
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
