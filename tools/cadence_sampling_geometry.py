#!/usr/bin/env python3
"""Sampling geometry pre-scan for T3. EPOCH TIMESTAMPS ONLY.

Reads no element value of any kind -- only norad, object_type and epoch_ms --
so nothing it prints can be a result about the estimand. Its single purpose is
to let the pre-registration DERIVE the alias structure and the resolvable
period band from the archive's real sampling pattern instead of guessing them.
"""
import json
import sqlite3
import sys

import numpy as np

DB = "/home/sdegan/space-orbit-history/orbit-history.sqlite3"
MOD = int(sys.argv[1]) if len(sys.argv) > 1 else 37
DAY = 86400000.0

db = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
db.execute("PRAGMA query_only=1")
db.execute("PRAGMA busy_timeout=600000")

types = dict(db.execute("SELECT norad, COALESCE(object_type,'(null)') FROM object"))
rows = db.execute(
    "SELECT norad, rows, min_epoch_ms, max_epoch_ms FROM object_rollup "
    "WHERE rows >= 200 AND (max_epoch_ms-min_epoch_ms) >= ?",
    (int(2 * 365.25 * DAY),),
).fetchall()

sample = [
    r for r in rows
    if r[0] % MOD == 0 and types.get(r[0]) in ("PAYLOAD", "DEBRIS", "ROCKET BODY")
]
print("sampled %d objects (norad %% %d == 0) of %d eligible"
      % (len(sample), MOD, len(rows)), file=sys.stderr)

buckets = {}
for norad, nrows, lo, hi in sample:
    cls = "payload" if types[norad] == "PAYLOAD" else "passive"
    ep = np.fromiter(
        (e for (e,) in db.execute(
            "SELECT epoch_ms FROM element_set WHERE norad=? ORDER BY epoch_ms", (norad,))),
        dtype=np.int64)
    if ep.size < 200:
        continue
    raw = np.diff(ep)
    d = raw.astype(np.float64) / DAY
    d = d[d > 0]
    if d.size < 50:
        continue
    b = buckets.setdefault(cls, {"n": 0, "spac": [], "nsamp": [], "base": [], "dupfrac": []})
    b["n"] += 1
    b["spac"].append(np.percentile(d, [5, 25, 50, 75, 95]))
    b["nsamp"].append(ep.size)
    b["base"].append((hi - lo) / DAY)
    b["dupfrac"].append(float(np.mean(raw == 0)))

out = {}
for cls, b in buckets.items():
    sp = np.array(b["spac"])
    out[cls] = {
        "objects": b["n"],
        "median_over_objects_of_within_object_spacing_percentiles_days": {
            k: round(float(np.median(sp[:, i])), 4)
            for i, k in enumerate(["p5", "p25", "p50", "p75", "p95"])},
        "across_object_spread_of_median_spacing_days": {
            "p10": round(float(np.percentile(sp[:, 2], 10)), 4),
            "p50": round(float(np.percentile(sp[:, 2], 50)), 4),
            "p90": round(float(np.percentile(sp[:, 2], 90)), 4)},
        "n_samples": {k: int(np.percentile(b["nsamp"], q))
                      for k, q in [("p10", 10), ("p50", 50), ("p90", 90)]},
        "baseline_days": {k: round(float(np.percentile(b["base"], q)), 1)
                          for k, q in [("p10", 10), ("p50", 50), ("p90", 90)]},
        "exact_duplicate_epoch_fraction_median": round(float(np.median(b["dupfrac"])), 6),
    }
print(json.dumps(out, indent=2, sort_keys=True))
