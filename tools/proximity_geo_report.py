#!/usr/bin/env python3
"""T8a reporting: every number quoted in `docs/proximity-results-20260922.md`
that is not already in `docs/proximity-20260922-receipt.json`.

Descriptive only. It reads the committed event catalogue and the extract
cache, adds no threshold, and changes no registered verdict. It is committed
so that each figure in the results document is reproducible.

TWO DIAGNOSTICS IN AN EARLIER DRAFT OF THIS FILE WERE WRONG, and the
corrected versions are what section D runs. The originals are described in
the results document, because a selection flaw found by the author is still
a finding:

  * the "uncontrolled object" sample was selected as objects with NO
    drift-change flag. That selects STATION-KEPT satellites: their
    manoeuvres are below the registered 0.010 deg/day floor so they never
    flag, and their lambda_ddot is ~0 by construction. Corrected to objects
    with no stationed segment at all.
  * the lambda noise floor was pooled over every object including fast
    drifters, whose real acceleration enters the second difference and
    inflates it by two orders of magnitude (0.0219 deg against 0.0011 deg).
    Corrected to element sets inside stationed segments, which is the
    population the 0.1 deg estimand is about.

Usage: python3 tools/proximity_geo_report.py [--timelines]
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))
from tools import proximity_geo as pg  # noqa: E402

DATE = "20260922"
WANT_TIMELINES = "--timelines" in sys.argv


def wilson(k, n, z=1.959963984540054):
    """Wilson score interval. scipy is not installed on this host, which is
    why the receipt's Jeffreys field is null; Wilson needs no special
    functions and is reported in its place."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1.0 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


rows = [json.loads(l) for l in open(_REPO / f"docs/proximity-events-{DATE}.jsonl")]
prov, events = rows[0], rows[1:]
receipt = json.loads((_REPO / f"docs/proximity-{DATE}-receipt.json").read_text())

resolved = [e for e in events if e["attribution"] == "resolved"
            and e["approacherClass"] == "active"]
print(f"events total {len(events)}, active+resolved {len(resolved)}")


def pct(vals, name):
    a = np.asarray([v for v in vals if v is not None and np.isfinite(v)],
                   dtype=np.float64)
    if a.size == 0:
        print(f"{name}: none")
        return
    ps = {p: float(np.percentile(a, p)) for p in (5, 25, 50, 75, 95)}
    print(f"{name}: n={a.size} min={a.min():.4g} "
          + " ".join(f"p{p}={v:.4g}" for p, v in ps.items())
          + f" max={a.max():.4g} mean={a.mean():.4g}")


pct([e["loiterDays"] for e in resolved], "loiterDays")
pct([e["closestSeparationDeg"] for e in resolved], "closestSeparationDeg")
pct([e["closestSeparationKm"] for e in resolved], "closestSeparationKm")
pct([e["medianSeparationDeg"] for e in resolved], "medianSeparationDeg")
pct([e["transferDays"] for e in resolved], "transferDays")
pct([e["transferDriftDegPerDay"] for e in resolved], "transferDriftDegPerDay")
pct([e["approacherMotionDeg"] for e in resolved], "approacherMotionDeg")
pct([e["leadCausalDays"] for e in resolved], "leadCausalDays")
pct([e["leadFirstFlagDays"] for e in resolved], "leadFirstFlagDays(secondary)")

# histogram of lead time
leads = np.asarray([e["leadCausalDays"] for e in resolved
                    if e["leadCausalDays"] is not None])
if leads.size:
    edges = [-1e9, 0, 7, 14, 30, 60, 120, 180, 1e9]
    labels = ["<=0", "0-7", "7-14", "14-30", "30-60", "60-120", "120-180", ">180"]
    h, _ = np.histogram(leads, bins=edges)
    print("lead-time histogram (days):",
          ", ".join(f"{l}:{int(c)}" for l, c in zip(labels, h)))

# departures
dep = [e for e in resolved if e["departureMs"] is not None]
print(f"events with an observed departure: {len(dep)} of {len(resolved)}")
pct([(e["departureMs"] - e["arrivalMs"]) / 86400000.0 for e in dep],
    "arrival->departure days")

# metadata splits (structural only; no per-nation narrative)
same = sum(1 for e in resolved if e["sameCountry"])
print(f"same-registry pairs: {same} of {len(resolved)} "
      f"({100.0 * same / max(1, len(resolved)):.1f}%)")
lib = sum(1 for e in resolved if e["libration_zone"])
print(f"libration-zone events: {lib} of {len(resolved)}")
tgt_types = {}
for e in resolved:
    tgt_types[e["targetObjectType"]] = tgt_types.get(e["targetObjectType"], 0) + 1
print("target object types:", tgt_types)

# repeaters and their profile timelines
by = {}
for e in resolved:
    by.setdefault(e["approacherNorad"], []).append(e)
rep = sorted(((n, v) for n, v in by.items() if len(v) >= 2),
             key=lambda kv: -len(kv[1]))
print(f"\nrepeat approachers (>=2 events): {len(rep)}")
for n, v in rep[:25]:
    v.sort(key=lambda e: e["arrivalMs"])
    tg = {e["targetNorad"] for e in v}
    print(f"  {n} {v[0]['approacherName']!r} {v[0]['approacherCountry']} "
          f"events={len(v)} distinct targets={len(tg)} "
          f"loiter={[round(e['loiterDays']) for e in v]} "
          f"closest={[round(e['closestSeparationDeg'], 3) for e in v]} "
          f"lead={[None if e['leadCausalDays'] is None else round(e['leadCausalDays']) for e in v]}")

print("\n--- worked example timelines (top repeaters) ---")
if WANT_TIMELINES:
    for n, v in rep[:6]:
        print(f"\n### NORAD {n} — {v[0]['approacherName']} "
              f"({v[0]['approacherObjectId']}, {v[0]['approacherCountry']}, "
              f"launched {v[0]['approacherLaunchDate']})")
        for e in v:
            print(f"  flag {e['initiatingFlagIso']} "
                  f"(drift change {e['initiatingDriftChangeDegPerDay']}) -> "
                  f"transfer from {e['transferStartIso']} ({e['transferDays']:.0f} d, "
                  f"{e['transferDriftDegPerDay']:.4f} deg/day, "
                  f"{e['approacherMotionDeg']:.2f} deg) -> arrive "
                  f"{e['arrivalIso']} at {e['loiterLongitudeDeg']:.3f} deg "
                  f"near {e['targetNorad']} {e['targetName']} "
                  f"({e['targetObjectType']}, {e['targetCountry']}) -> loiter "
                  f"{e['loiterDays']:.0f} d, closest "
                  f"{e['closestSeparationDeg']:.4f} deg "
                  f"({e['closestSeparationKm']:.1f} km) -> depart "
                  f"{e['departureIso']}  [lead {e['leadCausalDays']} d]")



passive = [e for e in events if e["approacherClass"] == "passive"]
amb = [e for e in events if e["attribution"] == "ambiguous"]

print("=== event bookkeeping ===")
print(f"alert precision (events/alerts) Wilson95: {wilson(len(resolved), 1483)}")
print(f"raw {len(events)}  active-resolved {len(resolved)}  "
      f"passive {len(passive)}  ambiguous {len(amb)}")

# distinct arrivals: one approacher arriving once, however many co-located
# targets happen to share that longitude
arr = {}
for e in resolved:
    key = (e["approacherNorad"], round(e["arrivalMs"] / 86400000.0 / 30.0))
    arr.setdefault(key, []).append(e)
print(f"distinct (approacher, arrival month) arrivals: {len(arr)}")
multi = sum(1 for v in arr.values() if len({x['targetNorad'] for x in v}) > 1)
print(f"  of which arrivals with >1 co-located target: {multi}")
print(f"distinct approachers: {len({e['approacherNorad'] for e in resolved})}")
print(f"distinct targets: {len({e['targetNorad'] for e in resolved})}")

print("\n=== lead-time censoring ===")
leads = [e["leadCausalDays"] for e in resolved if e["leadCausalDays"] is not None]
first = [e["leadFirstFlagDays"] for e in resolved if e["leadFirstFlagDays"] is not None]
print(f"lead_causal >= 170 d (near the 180 d look-back wall): "
      f"{sum(1 for v in leads if v >= 170)} of {len(leads)}")
print(f"lead_first  >= 170 d: {sum(1 for v in first if v >= 170)} of {len(first)}")

print("\n=== the five passive-class events ===")
for e in passive:
    print(f"  {e['approacherNorad']} {e['approacherName']!r} "
          f"({e['approacherObjectType']}) -> {e['targetNorad']} {e['targetName']!r} "
          f"arrive {e['arrivalIso'][:10]} lon {e['loiterLongitudeDeg']:.2f} "
          f"loiter {e['loiterDays']:.0f} d closest {e['closestSeparationDeg']:.4f} "
          f"libration_zone={e['libration_zone']} "
          f"transfer_drift={e['transferDriftDegPerDay']:.4f}")

print("\n=== slow-transfer population (the suspected uncontrolled class) ===")
slow = [e for e in resolved if e["transferDriftDegPerDay"] < 0.025]
print(f"active-resolved events whose transfer drift < 0.025 deg/day: "
      f"{len(slow)} of {len(resolved)}")
print(f"  of those, in the libration zone: {sum(1 for e in slow if e['libration_zone'])}")
byobj = {}
for e in slow:
    byobj.setdefault((e["approacherNorad"], e["approacherName"]), 0)
    byobj[(e["approacherNorad"], e["approacherName"])] += 1
print("  top slow-transfer approachers:",
      sorted(byobj.items(), key=lambda kv: -kv[1])[:12])
old = [e for e in slow if e["approacherLaunchDate"] and e["approacherLaunchDate"] < "1995"]
print(f"  slow-transfer events by objects launched before 1995: {len(old)}")



print("=== loiter-duration shape, active vs passive ===")
for name, ev in (("active", resolved), ("passive", passive)):
    l = np.asarray([e["loiterDays"] for e in ev])
    print(f"  {name}: n={l.size} median={np.median(l):.1f} "
          f">=45d {int((l >= 45).sum())} ({100*(l>=45).mean():.0f}%) "
          f">=60d {int((l >= 60).sum())} ({100*(l>=60).mean():.0f}%) "
          f">=120d {int((l >= 120).sum())} ({100*(l>=120).mean():.0f}%)")

print("\n=== flag-corroborated partition (post-registration, labelled) ===")
corr = [e for e in resolved if e["initiatingFlagMs"] is not None]
uncorr = [e for e in resolved if e["initiatingFlagMs"] is None]
for name, ev in (("with an observed drift-change flag", corr),
                 ("with no flag in the 180 d look-back", uncorr)):
    if not ev:
        continue
    l = np.asarray([e["loiterDays"] for e in ev])
    d = np.asarray([e["transferDriftDegPerDay"] for e in ev])
    pre95 = sum(1 for e in ev if e["approacherLaunchDate"]
                and e["approacherLaunchDate"] < "1995")
    lib = sum(1 for e in ev if e["libration_zone"])
    print(f"  {name}: n={len(ev)} "
          f"median loiter={np.median(l):.0f} d, median transfer drift="
          f"{np.median(d):.4f} deg/day, pre-1995 approachers={pre95}, "
          f"libration-zone={lib}, "
          f"distinct approachers={len({e['approacherNorad'] for e in ev})}")
print(f"  passive-class events with a flag: "
      f"{sum(1 for e in passive if e['initiatingFlagMs'] is not None)} of {len(passive)}")

# repetition on the corroborated subset
by = {}
for e in corr:
    by.setdefault(e["approacherNorad"], []).append(e)
rep = {n: v for n, v in by.items() if len(v) >= 2}
print(f"  corroborated repeat approachers (>=2): {len(rep)}; "
      f"multi-target: {sum(1 for v in rep.values() if len({x['targetNorad'] for x in v}) >= 2)}")

with np.load(_REPO / "runtime/proximity-geo/near-geo.npz") as z:
    arrays = {k: z[k] for k in z.files}
series = pg.build_series(arrays)
pg.build_daily_grid(series)
segs = {s.norad: pg.station_segments(s) for s in series}

print("\n=== (b) lambda scatter INSIDE stationed segments ===")
sig = []
for s in series:
    for i0, i1 in segs[s.norad][:2]:
        t0 = (s.grid_lo + i0) * pg.DAY_MS
        t1 = (s.grid_lo + i1 + 1) * pg.DAY_MS
        k0, k1 = np.searchsorted(s.epoch_ms, [t0, t1])
        if k1 - k0 < 100:
            continue
        lam = s.lam_unwrapped[k0:k1]
        t = s.epoch_ms[k0:k1] / pg.DAY_MS
        dt = np.diff(t)
        ok = (dt[:-1] > 0.05) & (dt[:-1] < 2.0) & (dt[1:] > 0.05) & (dt[1:] < 2.0)
        if ok.sum() < 50:
            continue
        d2 = (lam[2:] - 2 * lam[1:-1] + lam[:-2])[ok]
        sig.append(float(np.median(np.abs(d2 - np.median(d2)))
                         * 1.4826 / np.sqrt(6.0)))
sig = np.asarray(sig)
print(f"  n={sig.size} segments; per-element-set sigma_lambda: "
      f"p5={np.percentile(sig,5):.5f} p25={np.percentile(sig,25):.5f} "
      f"median={np.median(sig):.5f} p75={np.percentile(sig,75):.5f} "
      f"p95={np.percentile(sig,95):.5f} deg")
print(f"  median = {np.median(sig)*pg.KM_PER_DEG_GEO:.2f} km; "
      f"X_primary / median = {0.1/np.median(sig):.0f}x; "
      f"X_primary / p95 = {0.1/np.percentile(sig,95):.1f}x")

print("\n=== (a) empirical lambda_ddot for objects that never station-keep ===")
obs, pred, lons = [], [], []
n_obj = 0
for s in series:
    if segs[s.norad]:
        continue                      # has at least one stationed segment
    if s.epoch_ms.size < 400:
        continue
    span = float(np.nanmax(s.grid) - np.nanmin(s.grid)) if np.isfinite(s.grid).any() else 0.0
    if span < 5.0:
        continue
    n_obj += 1
    t = s.epoch_ms / pg.DAY_MS
    for a in range(0, s.epoch_ms.size - 200, 400):
        b = a + 200
        if not (60.0 < t[b - 1] - t[a] < 400.0):
            continue
        tt = t[a:b] - t[a]
        c = np.polyfit(tt, s.lam_unwrapped[a:b], 2)
        lam_mid = float(pg.wrap180(np.median(s.lam_unwrapped[a:b])))
        best = min(pg.STABLE_LONGITUDES_DEG,
                   key=lambda st: abs(float(pg.wrap180(lam_mid - st))))
        delta = float(pg.wrap180(lam_mid - best))
        obs.append(2.0 * c[0])
        pred.append(-pg.LAMBDA_DDOT_MAX * np.sin(np.radians(2.0 * delta)))
        lons.append(lam_mid)
obs = np.asarray(obs); pred = np.asarray(pred)
print(f"  {n_obj} never-stationed objects, {obs.size} 200-sample windows")
if obs.size > 20:
    keep = np.abs(pred) > 2e-4
    print(f"  windows with |predicted| > 2e-4: {int(keep.sum())}")
    if keep.sum() > 10:
        r = obs[keep] / pred[keep]
        print(f"  observed/predicted: p10={np.percentile(r,10):.2f} "
              f"median={np.median(r):.2f} p90={np.percentile(r,90):.2f}")
    print(f"  |observed| median = {np.median(np.abs(obs)):.6f} deg/day^2, "
          f"p90 = {np.percentile(np.abs(obs),90):.6f}; "
          f"derived max = {pg.LAMBDA_DDOT_MAX:.6f}")
    print(f"  correlation(observed, predicted) = "
          f"{float(np.corrcoef(obs, pred)[0,1]):.3f}")

print("\n=== dwell bound, checked directly on the uncontrolled events ===")
# For each passive-class event and each slow-transfer active event, the prereg
# 2.6 bound says max dwell = sqrt(2X / (K |sin 2 delta|)).
def bound(lon):
    best = min(pg.STABLE_LONGITUDES_DEG,
               key=lambda st: abs(float(pg.wrap180(lon - st))))
    d = float(pg.wrap180(lon - best))
    s = abs(np.sin(np.radians(2.0 * d)))
    return float("inf") if s < 1e-6 else float(np.sqrt(0.2 / (pg.LAMBDA_DDOT_MAX * s)))
viol = 0
for e in passive:
    b = bound(e["loiterLongitudeDeg"])
    flag = "VIOLATES" if e["loiterDays"] > b else "ok"
    if e["loiterDays"] > b:
        viol += 1
    print(f"  passive {e['approacherNorad']} lon {e['loiterLongitudeDeg']:.2f}: "
          f"loiter {e['loiterDays']:.0f} d vs bound {b:.1f} d -> {flag}")
slow = [e for e in resolved if e["transferDriftDegPerDay"] < 0.025]
sv = sum(1 for e in slow if e["loiterDays"] > bound(e["loiterLongitudeDeg"]))
print(f"  slow-transfer active events exceeding their own dwell bound: "
      f"{sv} of {len(slow)}")
