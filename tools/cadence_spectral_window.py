#!/usr/bin/env python3
"""Spectral window of the archive's epoch pattern. EPOCH TIMESTAMPS ONLY.

W(f) = |sum_j exp(-2 pi i f t_j)|^2 / N^2 carries the alias structure of an
irregularly sampled series: every peak of W away from f=0 is a frequency at
which a true signal can be counterfeited by the sampling. This reads no
element value, so it is sampling geometry and not a result.
"""
import json
import sqlite3
import sys

import numpy as np

DB = "/home/sdegan/space-orbit-history/orbit-history.sqlite3"
MOD = int(sys.argv[1]) if len(sys.argv) > 1 else 397
MAXN = 3000
DAY = 86400000.0

db = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
db.execute("PRAGMA query_only=1")
db.execute("PRAGMA busy_timeout=600000")

types = dict(db.execute("SELECT norad, COALESCE(object_type,'(null)') FROM object"))
rows = db.execute(
    "SELECT norad FROM object_rollup WHERE rows >= 200 AND (max_epoch_ms-min_epoch_ms) >= ?",
    (int(2 * 365.25 * DAY),)).fetchall()
sample = [n for (n,) in rows
          if n % MOD == 0 and types.get(n) in ("PAYLOAD", "DEBRIS", "ROCKET BODY")]
print("window sample: %d objects" % len(sample), file=sys.stderr)

# Alias-relevant band: 0.02 c/d (50 d) out to 4 c/d (6 h), the band in which
# the sampling itself has structure. Resolution 5e-4 c/d.
freq = np.arange(0.02, 4.0, 5e-4)

acc = {}
for norad in sample:
    cls = "payload" if types[norad] == "PAYLOAD" else "passive"
    ep = np.fromiter((e for (e,) in db.execute(
        "SELECT epoch_ms FROM element_set WHERE norad=? ORDER BY epoch_ms", (norad,))),
        dtype=np.int64)
    if ep.size < 200:
        continue
    t = ep[-MAXN:].astype(np.float64) / DAY
    t -= t[0]
    phase = np.exp(-2j * np.pi * np.outer(t, freq))
    w = np.abs(phase.sum(axis=0)) ** 2 / t.size ** 2
    a = acc.setdefault(cls, [0, np.zeros_like(freq)])
    a[0] += 1
    a[1] += w

out = {}
for cls, (n, w) in acc.items():
    w = w / n
    order = np.argsort(w)[::-1]
    peaks = []
    taken = []
    for i in order:
        f = freq[i]
        if any(abs(f - g) < 0.02 for g in taken):
            continue
        taken.append(f)
        peaks.append({"freq_cycles_per_day": round(float(f), 4),
                      "period_days": round(float(1.0 / f), 4),
                      "mean_window_power": float("%.5g" % w[i])})
        if len(peaks) >= 12:
            break
    out[cls] = {"objects": n, "max_samples_used": MAXN,
                "median_window_power_in_band": float("%.5g" % np.median(w)),
                "top_window_peaks": peaks}
print(json.dumps(out, indent=2, sort_keys=True))
