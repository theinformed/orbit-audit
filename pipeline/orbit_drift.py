"""V4 sustained orbit-raising lane: nightly offline build and manual verification.

z = test slope / (max(own test robust scatter, 0.001 km) / observed test span),
threshold 5 unchanged. Every raw element set in the TEST window must have
perigee <800 km and eccentricity <0.05 to flag. Maxima (before daily medians)
make regime crossings conservative and auditable. No drag model, prediction,
cohort requirement or trailing-window requirement. Other elements and optional
two-window slope changes are recorded diagnostics only; B* is never read.

Interpretation: sustained orbit-raising in the drag regime -- propulsion by
elimination. This is a physical interpretation, not independent ground truth.
Blind spots: station-keeping, lowering (drag-ambiguous), everything above the
gate, GEO relocations (future channel), and arcs failing test-window coverage.
Out-of-gate labels name ambiguous perturbation regimes, not proven causes.
z is a robust standardized score, not a Gaussian significance probability;
departureLowerBound is descriptive, not a confidence interval or delta-v.

The two windows retain five-day medians and deterministic Theil-Sen arithmetic.
The nightly publication contract and retention are in docs/orbit-drift.md.
Historical acceptance below is evidence only, never the nightly label policy.

Measured 2026-09-12 UTC, full catalogue, 2024-01-01 / 2024-09-01 / 2025-01-01:
PASSIVE: 0/4107 in-gate raising flags; exact one-sided 95% upper bound
0.7291550923 per 1000, below the 1/1000 design target. PAYLOAD: 56/7059
(7.933135005 per 1000), versus v3's 2 in-gate raisers: 28x more catches.
Bound-aware separation 10.87990071x = payload point rate / passive upper bound;
not a joint confidence bound on the ratio. Threshold 5 was not tuned.

Payload constellation/name families: Starlink 51, Omni 2 (OMNI-L1/L2), Umbra 1
(UMBRA-07), Zhixing 1 (ZHIXING-2A), Geesat 1 (GEESAT 3-03). Starlink is a known
orbit-raising fleet; membership is not independent truth for each 2024 campaign.
47/51 Starlink catches lack qualifying trailing fits; of the other 4, v3 had
2 cohort gaps and 2 subthreshold scores. Overall 49/56 payload catches lack trailing fits. Both v3 raisers survive.
Three UNKNOWN-type objects also flag; excluded from passive/payload rates.
Out-of-gate recorded rises: passive 106 (17 SRP, 28 GEO, 61 HEO); payload 175
(50 SRP, 92 GEO, 33 HEO); none flag. These labels are ambiguity bins, not causes.

68657 catalogue objects; 23971 test-fitted, 13554 fitted in-gate (including unknown
object types), 44686 test gaps. 2654 additional test fits versus v3. 15940097 raw
rows, 1844008 temporal blocks. GPU 1 pipeline 2341.33 s; in-process peak 262539264
bytes (250.377 MiB), ceiling 1399848960 bytes (<1.4 GB); no telemetry gap or chunk
reduction. Device-wide delta reached 11259609088 bytes from shared-card activity;
it did not govern our ceiling. Completed usage receipt retained in the ledger.
41/41 tests pass, including real GPU parity with optional windows. 64 real CPU
reference objects match GPU fits exactly. Independent raw geometry checks passed
for all 59 catches plus those 64 reference objects; counts/scores/days audited.

Evidence: /tmp/drift-v4-full-2024.jsonl (104763717 bytes), SHA-256
00f17ce50a5076233baf867373f68fb0511a134a37f5adfba73d99a7c0dd4a89.
Readable report, catch identities, counts, audit scripts and receipts/metrics:
/tmp/drift-v4-work/. This same 2024 archive motivated the gate: independent-year
validation, per-object propulsion truth, campaign timing and raising-population
recall remain unproven. Binomial bounds assume independent trials; shared debris
families/element errors can violate that assumption. Short campaigns may be
missed by the long-window fit. No deploys or release-timer changes.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
import datetime as dt
import itertools
import json
import math
from pathlib import Path
import sqlite3
import sys
import tempfile
import time

import numpy as np

from pipeline import orbit_campaigns, orbit_history
from pipeline.orbit_events import PASSIVE_TYPES, _jeffreys_interval, _regularised_incomplete_beta

DAY_MS = 86_400_000
ELEMENTS = ("semiMajorAxisKm", "eccentricity", "inclinationDeg")
QUANTA = (0.001, 1e-8, 1e-4)


@dataclass(frozen=True)
class Config:
    start_day: int
    end_day: int                    # exclusive, UTC aligned
    split_day: int | None = None     # default: two thirds trailing, one third test
    pairs: int = 4000
    min_blocks: int = 12             # at least 60 days at the five-day convention
    block_days: int = 5
    min_coverage: float = 0.8
    altitude_band_km: float = 50.0   # perigee, where drag acts
    inclination_band_deg: float = 4.0
    threshold: float = 5.0
    page_rows: int = 4096
    max_fits_per_day: int = 4096
    scratch_bytes: int = 512 * 1024**2

    def __post_init__(self):
        if not 2 <= self.end_day - self.start_day <= 3660:
            raise ValueError("window must contain 2..3660 UTC days")
        if not 1 <= self.pairs <= 16000 or not 2 <= self.min_blocks <= 3660:
            raise ValueError("invalid pair/block budget")
        if not 0 < self.min_coverage <= 1:
            raise ValueError("invalid control coverage")
        if not 1 <= self.block_days <= 30:
            raise ValueError("invalid block size")
        if self.split_day is None:
            object.__setattr__(self, "split_day", self.start_day + 2 * (self.end_day - self.start_day) // 3)
        if not self.start_day < self.split_day < self.end_day:
            raise ValueError("split must be strictly inside the window")
        if not all(math.isfinite(x) and x > 0 for x in (
            self.altitude_band_km, self.inclination_band_deg, self.threshold)):
            raise ValueError("bands and threshold must be finite and positive")
        if not 1 <= self.page_rows <= 65536 or not 1 <= self.max_fits_per_day <= 65536:
            raise ValueError("invalid raw-row budget")
        if self.scratch_bytes < 1024**2:
            raise ValueError("scratch budget must be at least 1 MiB")


@dataclass
class Blocks:
    norad: int
    object_type: str
    days: np.ndarray
    values: np.ndarray              # days x elements, float64
    band: tuple[int, int]
    raw_rows: int
    occupied_days: int = 0
    geometry: np.ndarray | None = None  # daily raw maxima: perigee km, eccentricity


def object_ids(db, only=None):
    """Keyset seek: no DISTINCT scan over the entire elements archive."""
    if only is not None:
        yield from sorted(set(only))
        return
    after = -1
    while True:
        row = db.execute("SELECT norad FROM element_set WHERE norad>? ORDER BY norad LIMIT 1",
                         (after,)).fetchone()
        if row is None:
            return
        after = row[0]
        yield after


def daily_blocks(db, norad, cfg):
    """Page one object's raw fits; retain at most one day before reducing it.

    Each query ends before analysis. No persistent archive read transaction;
    future appends outside the explicit window do not change its membership.
    Tier-2 representatives are deliberately not passed off as raw-day medians.
    """
    fact = db.execute("SELECT object_type FROM object WHERE norad=?", (norad,)).fetchone()
    object_type = (fact[0] or "UNKNOWN").upper() if fact else "UNKNOWN"
    after = cfg.start_day * DAY_MS - 1
    days, values, geometry, current, fits, raw_rows = [], [], [], None, [], 0

    def flush():
        if fits:
            days.append(current)
            raw = np.asarray(fits, dtype=np.float64)
            values.append(np.median(raw, axis=0))
            geometry.append((float(np.max(raw[:, 0] * (1 - raw[:, 1]) - orbit_history.RE_WGS72)),
                             float(np.max(raw[:, 1]))))

    while True:
        rows = db.execute(
            "SELECT epoch_ms,mean_motion_q,eccentricity_q,inclination_q FROM element_set "
            "WHERE norad=? AND epoch_ms>? AND epoch_ms<? ORDER BY epoch_ms LIMIT ?",
            (norad, after, cfg.end_day * DAY_MS, cfg.page_rows)).fetchall()
        if not rows:
            break
        for epoch, mm, ecc, inc in rows:
            day = epoch // DAY_MS
            if day != current:
                flush()
                current, fits = day, []
            if len(fits) >= cfg.max_fits_per_day:
                raise ValueError(f"NORAD {norad}: raw fits/day exceed bounded reduction budget")
            if mm <= 0 or not 0 <= ecc < 100000000 or not 0 <= inc <= 1800000:
                raise ValueError(f"NORAD {norad}: invalid orbital element")
            fits.append((orbit_history.semi_major_axis_km(mm / 1e8), ecc / 1e8, inc / 1e4))
            raw_rows += 1
        after = rows[-1][0]
    flush()
    if not days:
        return None
    vals = np.asarray(values)
    altitude = np.median(vals[:, 0] * (1 - vals[:, 1]) - orbit_history.RE_WGS72)
    inclination = np.median(vals[:, 2])
    return Blocks(norad, object_type, np.asarray(days, dtype=np.float64), vals,
                  (math.floor(altitude / cfg.altitude_band_km),
                   math.floor(inclination / cfg.inclination_band_deg)), raw_rows,
                  len(days), np.asarray(geometry))


def temporal_blocks(obj, cfg, start_day=None, end_day=None):
    """Equal weight per occupied UTC day, then per window-aligned five-day block.

    Actual median observation time is retained: sparse blocks are not assigned
    fictional regular timestamps. Empty blocks never become observations.
    """
    if obj is None:
        return None
    start_day = cfg.start_day if start_day is None else start_day
    end_day = cfg.end_day if end_day is None else end_day
    selected = (obj.days >= start_day) & (obj.days < end_day)
    days, vals = obj.days[selected], obj.values[selected]
    bins = ((days - start_day) // cfg.block_days).astype(int)
    times, values = [], []
    for block in np.unique(bins):
        mask = bins == block
        times.append(float(np.median(days[mask])))
        values.append(np.median(vals[mask], axis=0))
    return Blocks(obj.norad, obj.object_type, np.asarray(times), np.asarray(values).reshape(-1, 3),
                  obj.band, obj.raw_rows, len(days))


def coverage_gap(obj, start, end, cfg):
    count = len(obj.days) if obj else 0
    window = end - start
    if count < cfg.min_blocks:
        return "insufficient temporal blocks/coverage"
    if (count / math.ceil(window / cfg.block_days) < cfg.min_coverage or
            obj.days[0] > start + (1 - cfg.min_coverage) * window / 2 or
            obj.days[-1] < end - 1 - (1 - cfg.min_coverage) * window / 2):
        return "insufficient coverage of the common window"
    return None


def pair_indices(norad, count, target):
    """Uniform unordered pairs, sampled with replacement in O(target) memory.

    Per-NORAD PCG64, shared indices for every element and backend. Exhaustive
    enumeration only when the total pair count is already <= the budget.
    """
    total = count * (count - 1) // 2
    if total <= target:
        return np.triu_indices(count, 1)
    rng = np.random.Generator(np.random.PCG64(int(norad)))
    a = rng.integers(0, count, target)
    b = rng.integers(0, count - 1, target)
    b += b >= a
    return np.minimum(a, b), np.maximum(a, b)


def prepare(objects, pairs):
    """Independent object rows; padding only on the day/pair axes."""
    n = max(len(o.days) for o in objects)
    k = min(pairs, n * (n - 1) // 2)
    t = np.full((len(objects), n), np.nan)
    y = np.full((len(objects), 3, n), np.nan)
    left = np.zeros((len(objects), k), dtype=np.int64)
    right = left.copy()
    valid = np.zeros((len(objects), k), dtype=bool)
    for row, obj in enumerate(objects):
        m = len(obj.days)
        t[row, :m] = obj.days - obj.days[0]
        # Center before transfer: prevents intercept magnitude changing precision.
        y[row, :, :m] = (obj.values - obj.values[0]).T
        a, b = pair_indices(obj.norad, m, pairs)
        left[row, :len(a)], right[row, :len(b)] = a, b
        valid[row, :len(a)] = True
    return t, y, left, right, valid


def fit_arrays(arrays, xp=np):
    """Identical float64 operations, axis order and medians for both backends."""
    t, y, a, b, valid = (xp.asarray(x) for x in arrays)
    rows = xp.arange(t.shape[0])[:, None]
    delta = xp.where(valid, t[rows, b] - t[rows, a], 1.0)
    slopes = (xp.take_along_axis(y, b[:, None, :], axis=2)
              - xp.take_along_axis(y, a[:, None, :], axis=2)) / delta[:, None, :]
    slopes = xp.where(valid[:, None, :], slopes, xp.nan)
    slope = xp.nanmedian(slopes, axis=2)
    residual = y - slope[:, :, None] * t[:, None, :]
    intercept = xp.nanmedian(residual, axis=2)
    scatter = 1.4826 * xp.nanmedian(xp.abs(residual - intercept[:, :, None]), axis=2)
    return xp.stack((slope, scatter), axis=2)


def fit_cpu(objects, pairs):
    return fit_arrays(prepare(objects, pairs))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def regime_geometry(daily, cfg):
    """Gate raw extrema within the test window, before either median reduction."""
    result = {"inGate": None, "regime": None, "maxPerigeeKm": None,
              "maxEccentricity": None, "basis": "every raw test-window element set"}
    if daily is None:
        return result
    selected = (daily.days >= cfg.split_day) & (daily.days < cfg.end_day)
    if not np.any(selected):
        return result
    if daily.geometry is None:
        raise ValueError("raw geometry required for regime gate")
    perigee, ecc = (float(x) for x in np.max(daily.geometry[selected], axis=0))
    in_gate = perigee < 800 and ecc < .05
    # Diagnostic names describe ambiguity; they do not attribute the rise.
    regime = ("drag regime" if in_gate else "HEO lunisolar" if ecc >= .05 else
              "GEO libration" if 30000 <= perigee <= 40000 else "SRP-regime rise")
    return {**result, "inGate": in_gate, "regime": regime,
            "maxPerigeeKm": perigee, "maxEccentricity": ecc}


def score_axis(fit, geometry, cfg):
    """Optional trailing row, test row: (slope, scatter, floor, span).

    Only the object's test slope and test scatter/resolution scale can flag.
    Trailing slope/change never enters the score; negative slope is diagnostic.
    """
    trailing, test = fit
    result = {"regime": geometry["regime"], "gap": None, "flag": None,
              "negativeSide": None, "z": None, "reportable": None}
    if test is None or geometry["inGate"] is None:
        return {**result, "gap": "test fit or regime geometry unavailable"}
    scale = max(QUANTA[0], test[1]) / test[3]
    z = test[0] / scale
    raising, negative = z >= cfg.threshold, z <= -cfg.threshold
    flag = raising and geometry["inGate"]
    label = ("sustained orbit-raising in the drag regime -- propulsion by elimination" if flag else
             geometry["regime"] if raising else
             "lowering; drag-ambiguous, diagnostic only" if negative else "no resolved raising")
    result.update(z=z, flag=flag, negativeSide=negative, label=label,
                  reportable=raising or negative, raising=raising,
                  outOfGateRaising=raising and not geometry["inGate"],
                  comparisonScalePerDay=scale,
                  slopeChangePerDay=test[0] - trailing[0] if trailing else None,
                  departureLowerBound=max(0, test[0] - cfg.threshold * scale) * test[3])
    return result


def binomial_upper95(flags, n):
    """Exact one-sided Clopper-Pearson 95% upper bound; no zero-count shortcut to zero."""
    if not n:
        return None
    if flags == 0:
        return -math.expm1(math.log(.05) / n)
    if flags == n:
        return 1.0
    low, high = 0., 1.
    for _ in range(100):
        mid = (low + high) / 2
        if _regularised_incomplete_beta(flags + 1, n - flags, mid) < .95:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def control_summary(counts, days, cfg):
    result = {}
    for name in ("passive", "payload"):
        n, flags, negative = counts[name]
        result[name] = {
            "objects": n, "objectWindows": n, "flags": flags, "flaggedObjects": flags,
            "ratePerObjectWindow": flags / n if n else None,
            "negativeSideObjects": negative, "negativeSideRate": negative / n if n else None,
            "jeffreys95": list(_jeffreys_interval(flags, n)),
            "upper95": binomial_upper95(flags, n),
            "objectDays": days[name],
            "ratePerObjectYear": flags * 365.25 / days[name] if days[name] else None,
        }
    passive = result["passive"]["ratePerObjectWindow"]
    upper = result["passive"]["upper95"]
    payload = result["payload"]["ratePerObjectWindow"]
    separation = payload / upper if upper is not None and payload is not None else None
    return {"basis": "test-window semi-major-axis raising inside raw-element regime gate",
            "threshold": cfg.threshold, **result,
            "separation": separation,
            "separationExceedsOne": separation > 1 if separation is not None else None,
            "pointSeparation": payload / passive if passive and payload is not None else None,
            "separationNote": "payload observed rate / passive one-sided exact 95% upper bound; "
                              "bound-aware comparison, not a joint confidence bound on the ratio",
            "designTarget": .001,
            "passiveBoundMeetsTarget": upper < .001 if upper is not None else None,
            "sufficientToLabel": upper is not None and upper < .001 and separation is not None and separation >= 10,
            "blockingReason": (None if upper is not None and upper < .001 and separation is not None and separation >= 10
                               else "requires passive exact 95% upper bound < 1/1000 and bound-aware separation >= 10x"),
            "note": "One test object-window per object; only fitted in-gate objects in rate denominators. "
                    "Gaps excluded; out-of-gate rises diagnostic only. upper95 is one-sided exact binomial; "
                    "Jeffreys intervals also retained. Population dependence may limit binomial coverage. "
                    "Annualized flags are descriptive, not independent events."}


def run(db, out, cfg, *, chunk_size=32, only=None, limit=None, backends=(), scratch_dir=None):
    """Stream deterministic science JSONL; execution metrics are returned separately.

    One or two backend instances, each owning its device. Work futures never
    exceed device count, and emit in NORAD order regardless of completion order.
    Each test fit is sufficient; a qualifying trailing fit is optional context.
    """
    if not 1 <= chunk_size <= 256 or (limit is not None and limit < 1):
        raise ValueError("chunk_size must be 1..256; limit must be positive")
    if len(backends) > 2 or len({b.device for b in backends}) != len(backends):
        raise ValueError("use one or two distinct devices")
    start = time.perf_counter()
    metrics = {"objects": 0, "fittedObjects": 0, "rawRows": 0, "blocks": 0}
    windows = ((cfg.start_day, cfg.split_day), (cfg.split_day, cfg.end_day))
    with tempfile.TemporaryDirectory(prefix="orbit-drift-", dir=scratch_dir) as temp:
        stage = sqlite3.connect(str(Path(temp) / "fits.sqlite3"))
        try:
            stage.execute("PRAGMA cache_size=-4096")
            stage.execute("PRAGMA temp_store=FILE")
            stage.execute("PRAGMA journal_mode=OFF")  # regenerable private scratch only
            stage.execute(f"PRAGMA max_page_count={cfg.scratch_bytes // 4096}")
            stage.executescript("""
                CREATE TABLE object(norad INTEGER PRIMARY KEY,kind TEXT,blocks INTEGER,
                  first REAL,last REAL,alt INTEGER,inc INTEGER,gap TEXT,occupied_days INTEGER,
                  trailing_blocks INTEGER,test_blocks INTEGER,geometry TEXT,trailing_gap TEXT,test_days INTEGER);
                CREATE TABLE fit(norad INTEGER,element INTEGER,window INTEGER,slope REAL,scatter REAL,
                  floor REAL,span REAL,PRIMARY KEY(norad,element,window));
                CREATE INDEX bands ON object(alt,inc,kind);
            """)

            def chunks():
                chunk = []
                for norad in itertools.islice(object_ids(db, only), limit):
                    daily = daily_blocks(db, norad, cfg)
                    objects = [temporal_blocks(daily, cfg, a, b) for a, b in windows]
                    metrics["objects"] += 1
                    sizes = [len(o.days) if o else 0 for o in objects]
                    window_gaps = [coverage_gap(obj, a, b, cfg) for obj, (a, b) in zip(objects, windows)]
                    gap = window_gaps[1]
                    fact = None if daily else db.execute(
                        "SELECT object_type FROM object WHERE norad=?", (norad,)).fetchone()
                    kind = daily.object_type if daily else (fact[0] or "UNKNOWN").upper() if fact else "UNKNOWN"
                    stage.execute("INSERT INTO object VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                        norad, kind, sum(sizes),
                        float(daily.days[0]) if daily else None, float(daily.days[-1]) if daily else None,
                        daily.band[0] if daily else None, daily.band[1] if daily else None, gap,
                        daily.occupied_days if daily else 0, *sizes,
                        canonical(regime_geometry(daily, cfg)), window_gaps[0],
                        objects[1].occupied_days if objects[1] else 0))
                    if daily:
                        metrics["rawRows"] += daily.raw_rows
                        metrics["blocks"] += sum(sizes)
                    eligible = [(w, obj) for w, obj in enumerate(objects) if window_gaps[w] is None]
                    if gap is None:
                        metrics["fittedObjects"] += 1
                    if eligible:
                        chunk.append(eligible)
                    if len(chunk) == chunk_size:
                        yield chunk
                        chunk = []
                if chunk:
                    yield chunk

            def flattened(chunk):
                return [obj for arcs in chunk for _, obj in arcs]

            def save(chunk, fits):
                for (w, obj), fitted in zip(itertools.chain.from_iterable(chunk), fits):
                    span = float(obj.days[-1] - obj.days[0])
                    for element, (slope, scatter) in enumerate(fitted):
                        if not math.isfinite(slope) or not math.isfinite(scatter):
                            raise ValueError("nonfinite trend fit")
                        floor = max(QUANTA[element], float(scatter)) / span
                        stage.execute("INSERT INTO fit VALUES (?,?,?,?,?,?,?)", (
                            obj.norad, element, w, float(slope), float(scatter), floor, span))

            if backends:
                with ThreadPoolExecutor(max_workers=len(backends)) as pool:
                    source = iter(chunks())
                    while True:
                        pending = []
                        for backend in backends:
                            chunk = next(source, None)
                            if chunk is not None:
                                pending.append((chunk, pool.submit(backend.fit, flattened(chunk), cfg.pairs)))
                        if not pending:
                            break
                        for chunk, future in pending:
                            save(chunk, future.result())
            else:
                for chunk in chunks():
                    save(chunk, fit_cpu(flattened(chunk), cfg.pairs))
            stage.commit()
            out.write(canonical({"kind": "method", "version": 4, "config": asdict(cfg),
                                 "elements": ELEMENTS, "scope": "full-catalogue control; restricted runs cannot authorize labels",
                                 "activeElements": [ELEMENTS[0]], "windows": windows,
                                 "restrictedPopulation": only is not None or limit is not None,
                                 "gate": {"perigeeKmBelow": 800, "eccentricityBelow": .05,
                                          "basis": "every raw test-window element set"},
                                 "interpretation": "sustained orbit-raising in the drag regime -- propulsion by elimination",
                                 "blindSpots": ["station-keeping", "lowering (drag-ambiguous)",
                                                "everything above the gate", "GEO relocations (future channel)",
                                                "insufficient test-window coverage"],
                                 "note": "No drag model or prediction. Trailing fits optional diagnostics. "
                                         "Out-of-gate labels describe ambiguity, not demonstrated causes. "
                                         "z is not a Gaussian probability; attribution remains unproven."}) + "\n")
            counts = {name: [0, 0, 0] for name in ("passive", "payload")}
            days = {name: 0 for name in counts}
            out_of_gate = {name: {"objects": 0, "raising": 0, "byLabel": {}} for name in counts}
            gaps = 0
            in_gate = 0
            for row in stage.execute("SELECT * FROM object ORDER BY norad"):
                (norad, kind, blocks, first, last, alt, inc, gap, occupied_days,
                 tr_count, te_count, geometry, trailing_gap, test_days) = row
                geometry = json.loads(geometry)
                channels = []
                for element, name in enumerate(ELEMENTS):
                    fit = {w: values for w, *values in stage.execute(
                        "SELECT window,slope,scatter,floor,span FROM fit WHERE norad=? AND element=? ORDER BY window",
                        (norad, element))}
                    trailing, test = fit.get(0), fit.get(1)
                    channel = {"element": name, "slopePerDay": test[0] if test else None,
                               "robustScatter": test[1] if test else None, "z": None,
                               "flag": None, "negativeSide": None, "gap": gap}
                    channel["windows"] = {label: dict(zip(
                        ("slopePerDay", "robustScatter", "slopeFloorPerDay", "spanDays"), fit[w]))
                        if w in fit else None for w, label in enumerate(("trailing", "test"))}
                    if element != 0:
                        channel.update(label="recorded only", gap="diagnostic only: no validated natural-perturbation control",
                                       slopeChangePerDay=test[0] - trailing[0] if test and trailing else None)
                    elif test:
                        channel.update(score_axis([trailing, test], geometry, cfg))
                    channels.append(channel)
                group = "passive" if kind in PASSIVE_TYPES else "payload" if kind == "PAYLOAD" else None
                channel = channels[0]
                tested = channel["flag"] is not None
                if not tested:
                    gaps += 1
                elif geometry["inGate"]:
                    in_gate += 1
                    if group:
                        counts[group][0] += 1
                        counts[group][1] += int(channel["flag"])
                        counts[group][2] += int(channel["negativeSide"])
                        days[group] += test_days
                elif group:
                    tally = out_of_gate[group]
                    tally["objects"] += 1
                    tally["raising"] += int(channel["raising"])
                    if channel["raising"]:
                        label = channel["label"]
                        tally["byLabel"][label] = tally["byLabel"].get(label, 0) + 1
                out.write(canonical({"kind": "object", "norad": norad, "objectType": kind,
                                     "windowDays": [cfg.start_day, cfg.end_day], "blockCount": blocks,
                                     "windowBlockCounts": [tr_count, te_count],
                                     "occupiedDayCount": occupied_days, "testOccupiedDayCount": test_days,
                                     "observedDays": [first, last], "band": [alt, inc],
                                     "geometry": geometry, "trailingGap": trailing_gap,
                                     "channels": channels}) + "\n")
            controls = control_summary(counts, days, cfg)
            controls["objectsWithGap"] = gaps
            total = metrics["objects"]
            tested = total - gaps
            controls["population"] = {
                "objects": total, "trendFittedObjects": metrics["fittedObjects"],
                "trendFittedFraction": metrics["fittedObjects"] / total if total else None,
                "controlledObjects": in_gate, "controlledFraction": in_gate / total if total else None,
                "outOfGateFittedObjects": tested - in_gate,
                "objectsWithWindowData": stage.execute("SELECT count(*) FROM object WHERE blocks>0").fetchone()[0],
            }
            for group in counts:
                kinds = tuple(sorted(PASSIVE_TYPES)) if group == "passive" else ("PAYLOAD",)
                placeholders = ",".join("?" for _ in kinds)
                population, present, fitted = stage.execute(
                    f"SELECT count(*),coalesce(sum(blocks>0),0),coalesce(sum(gap IS NULL),0) "
                    f"FROM object WHERE kind IN ({placeholders})", kinds).fetchone()
                controls[group].update(populationObjects=population, objectsWithWindowData=present,
                                       trendFittedObjects=fitted,
                                       trendFittedFraction=fitted / population if population else None,
                                       controlledFraction=counts[group][0] / population if population else None)
            controls["restrictedPopulation"] = only is not None or limit is not None
            if controls["restrictedPopulation"]:
                controls.update(sufficientToLabel=False, blockingReason="restricted population; full-catalogue control required")
            controls["acceptance"] = ("restricted population; full-population acceptance unmeasured"
                                      if controls["restrictedPopulation"] else
                                      "passive-bound and bound-aware separation controls passed; attribution unproven"
                                      if controls["sufficientToLabel"] else
                                      "controls failed or unmeasurable")
            controls["outOfGate"] = out_of_gate
            out.write(canonical({"kind": "controls", **controls}) + "\n")
        finally:
            stage.close()
    metrics["durationSeconds"] = time.perf_counter() - start
    return metrics


ROOT = Path(__file__).resolve().parents[1]
DRIFT_FRAGMENT_PATH = ROOT / "pipeline/.cache/orbit-drift-manifest.json"
ARTIFACT_BUDGET = 32 * 1024**2


def nightly_config(end=None):
    """120 complete UTC test days: 24 five-day blocks, >=80% coverage.

    Long enough to measure sustained climbs rather than adjacent-fit steps.
    The preceding 240 days are optional context, never a flag requirement.
    This changes the 2024 acceptance windows: every run earns its own gate.
    """
    end = end or dt.datetime.now(dt.timezone.utc).date()
    day = (end - dt.date(1970, 1, 1)).days
    return Config(day - 360, day, split_day=day - 120)


def publication_bundle(report, generated_at):
    """Compact website records; raw detections remain in controls, not public flags."""
    objects, method, controls = [], None, None
    for line in report:
        row = json.loads(line)
        if controls is not None:
            raise ValueError("records after final control")
        if row["kind"] == "method":
            method = row
        elif row["kind"] == "controls":
            controls = row
        elif row["kind"] == "object":
            c = row["channels"][0]
            fit = c["windows"]["test"]
            objects.append({"norad": row["norad"], "objectType": row["objectType"],
                            "gap": c["gap"], "inGate": row["geometry"]["inGate"],
                            "regime": row["geometry"]["regime"], "raising": c.get("raising", False),
                            "slopeMetresPerDay": c["slopePerDay"] * 1000 if fit else None,
                            "spanDays": fit["spanDays"] if fit else None})
    if method is None or controls is None:
        raise ValueError("incomplete drift report")
    upper, separation = controls["passive"]["upper95"], controls["separation"]
    permitted = (method["version"] == 4 and not method["restrictedPopulation"]
                 and not controls["restrictedPopulation"] and controls["sufficientToLabel"]
                 and upper is not None and upper < .001 and separation is not None and separation >= 10)
    policy = {"propulsionLabelPermitted": bool(permitted),
              "blockingReason": None if permitted else controls["blockingReason"] or "control gate closed",
              "passiveUpperBoundTarget": .001, "minimumSeparation": 10,
              "warrant": "drag-regime exclusion plus this window's passive control; cause remains an inference"}
    for obj in objects:
        obj["flag"] = bool(permitted and obj["raising"] and obj["inGate"] and obj["objectType"] == "PAYLOAD" and not obj["gap"])
    return {"schema": 1, "version": 4, "generatedAt": generated_at,
            "method": method, "controls": controls, "labelPolicy": policy, "objects": objects}


def retention_plan(data_root, fragment_path):
    """Only this lane's superseded files; current published/pending references survive.

    72h browser grace, <=16 files / 256 MiB including gzip. Refuse admission
    if preserved files leave less than two 32 MiB artifact slots; never evict live data.
    """
    keep = set()
    for path in (data_root / "manifest.json", fragment_path):
        if path.exists():
            payload = json.loads(path.read_text())  # malformed reference => no deletion
            record = payload.get("manifest", payload).get("orbitDrift", {})
            if record.get("path"):
                keep.add((data_root / record["path"]).resolve())
                keep.add((data_root / (record["path"] + ".gz")).resolve())
    files = list((data_root / "artifacts").glob("orbit-drift-*.json*"))
    remove = [p for p in files if p.resolve() not in keep and p.stat().st_mtime < time.time() - 72 * 3600]
    retained = [p for p in files if p not in remove]
    return {"remove": [str(p) for p in remove], "retainedBytes": sum(p.stat().st_size for p in retained),
            "retainedFiles": len(retained), "budgetBytes": 256 * 1024**2, "budgetFiles": 16}


def publish_cache(bundle, data_root, fragment_path):
    from pipeline.build_release import write_artifact, atomic_write
    if len(canonical(bundle).encode()) > ARTIFACT_BUDGET:
        raise ValueError("website drift artifact exceeds 32 MiB")
    plan = retention_plan(data_root, fragment_path)
    if plan["retainedBytes"] + 2 * ARTIFACT_BUDGET > plan["budgetBytes"] or plan["retainedFiles"] + 2 > plan["budgetFiles"]:
        raise ValueError("drift retention budget full; preserved references cannot be evicted")
    for path in plan["remove"]:
        Path(path).unlink()
    relative, digest = write_artifact(data_root, "orbit-drift", bundle)
    fragment = {"orbitDrift": {"path": relative, "sha256": digest,
                               "generatedAt": bundle["generatedAt"], "objects": len(bundle["objects"])}}
    atomic_write(fragment_path, canonical({"manifest": fragment, "generatedAt": bundle["generatedAt"]}).encode())
    return fragment


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", help="UTC YYYY-MM-DD, inclusive")
    parser.add_argument("--end", help="UTC YYYY-MM-DD, exclusive")
    parser.add_argument("--split", help="UTC test start; default two thirds through window")
    parser.add_argument("--backend", choices=("cpu", "gpu"), default="cpu")
    parser.add_argument("--devices", default="0", help="one device or two distinct indices, e.g. 0,1")
    parser.add_argument("--vram-ceiling-mib", type=int, default=1335)
    parser.add_argument("--chunk-size", type=int, default=32)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--only", help="comma-separated NORADs; controls limited to this population")
    parser.add_argument("--output", type=Path, help="new JSONL file; refuses to overwrite")
    parser.add_argument("--smoke", action="store_true", help="8 MiB allocation only; no archive or fit")
    parser.add_argument("--dry-run", action="store_true", help="show bounds; no archive or CUDA access")
    parser.add_argument("--ledger-retention-dry-run", action="store_true",
                        help="read-only receipt-retention preview; no archive/CUDA")
    parser.add_argument("--build-cache", action="store_true", help="nightly full-catalogue config; publish artifact and fragment")
    parser.add_argument("--data-root", type=Path, default=ROOT / "public" / "data")
    parser.add_argument("--fragment-path", type=Path, default=DRIFT_FRAGMENT_PATH)
    parser.add_argument("--retention-dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.retention_dry_run:
        print(canonical(retention_plan(args.data_root, args.fragment_path)))
        return 0
    if args.build_cache and (args.start or args.split or args.only or args.limit or args.output or args.smoke):
        parser.error("--build-cache fixes the full catalogue and window; only --end may pin the UTC date")
    from pipeline.orbit_drift_gpu import gpu_session
    if args.ledger_retention_dry_run:
        from pipeline.orbit_drift_gpu import ledger_retention_plan
        print(canonical(ledger_retention_plan()))
        return 0
    if args.smoke:
        if args.dry_run:
            print(canonical({"smokeAllocationBytes": 8 * 1024**2,
                             "vramCeilingBytes": args.vram_ceiling_mib * 1024**2,
                             "device": int(args.devices), "cudaAccess": False}))
            return 0
        with gpu_session(int(args.devices), args.vram_ceiling_mib) as gpu:
            print(canonical(gpu.smoke()))
        return 0
    if args.build_cache:
        cfg = nightly_config(dt.date.fromisoformat(args.end) if args.end else None)
    else:
        if not args.start or not args.end:
            parser.error("--start and --end are required")
        epoch = dt.date(1970, 1, 1)
        cfg = Config((dt.date.fromisoformat(args.start) - epoch).days,
                     (dt.date.fromisoformat(args.end) - epoch).days,
                     split_day=(dt.date.fromisoformat(args.split) - epoch).days if args.split else None)
    devices = [int(x) for x in args.devices.split(",")]
    if len(devices) not in (1, 2) or len(set(devices)) != len(devices):
        parser.error("choose one or two distinct devices")
    if args.dry_run:
        print(canonical({"config": asdict(cfg), "backend": args.backend, "devices": devices,
                         "buildCache": args.build_cache, "dataRoot": str(args.data_root), "fragment": str(args.fragment_path),
                         "artifactBudgetBytes": ARTIFACT_BUDGET,
                         "vramCeilingBytesPerDevice": args.vram_ceiling_mib * 1024**2,
                         "chunkSize": args.chunk_size, "archive": str(orbit_history.archive_db_path()),
                         "outputBudgetBytes": 256 * 1024**2, "scratchBudgetBytes": cfg.scratch_bytes,
                         "cleanup": "private scratch deleted on exit; output is current until operator removes it"}))
        return 0
    if not args.output and not args.build_cache:
        parser.error("--output required")
    path = orbit_history.archive_db_path()
    if not path.is_file():
        raise FileNotFoundError(path)  # never invoke opener's create-on-missing fallback
    only = [int(x) for x in args.only.split(",")] if args.only else None
    import contextlib
    with contextlib.ExitStack() as stack:
        backends = [stack.enter_context(gpu_session(d, args.vram_ceiling_mib))
                    for d in devices] if args.backend == "gpu" else []
        db = stack.enter_context(contextlib.closing(orbit_campaigns.open_archive_for_reading(path)))
        out = stack.enter_context(tempfile.TemporaryFile(mode="w+", encoding="utf-8") if args.build_cache
                                  else args.output.open("x", encoding="utf-8"))
        class BoundedWriter:
            size = 0
            def write(self, text):
                self.size += len(text.encode("utf-8"))
                if self.size > 256 * 1024**2:
                    raise ValueError("output exceeds 256 MiB budget")
                out.write(text)
        metrics = run(db, BoundedWriter(), cfg, chunk_size=args.chunk_size, only=only,
                      limit=args.limit, backends=backends)
        if args.build_cache:
            out.seek(0)
            bundle = publication_bundle(out, dt.datetime.now(dt.timezone.utc).isoformat())
            metrics["controls"] = bundle["controls"]
            metrics["labelPolicy"] = bundle["labelPolicy"]
            # Finish GPU telemetry/cleanup before naming a release. A failed GPU
            # session must never leave an apparently successful new fragment.
        metrics["backend"] = args.backend
        metrics["gpu"] = [b.measurement() for b in backends]
    if args.build_cache:
        metrics["manifest"] = publish_cache(bundle, args.data_root, args.fragment_path)
    print(canonical(metrics), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
