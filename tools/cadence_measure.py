#!/usr/bin/env python3
"""T3 step 2: batched GPU generalised Lomb-Scargle over the extracted histories.

Reads only the artifacts `tools/cadence_extract.py` wrote -- it never touches
the archive, so it cannot contend with the running Phase 3 readers -- builds
the registered windows, detrends them, and evaluates the registered frequency
grid on every window of every object in one batched pass.

The arithmetic is `tools/cadence_core.py`, which is array-module agnostic; this
program's only job is to choose CuPy over NumPy, to pack ragged windows into
rectangular batches, and to write the per-window table. The identical code path
runs on CPU in the tests.

CUDA_VISIBLE_DEVICES arrives from `gpu-run` as a GPU **UUID** and is never
parsed as an integer here or anywhere else; the granted card is always CUDA
device 0 inside the process, which is what CuPy's default device already is.
No device-wide VRAM query is made and nothing is gated on one.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from tools import cadence_core as core  # noqa: E402

CHANNELS = ("mean_motion", "inclination", "eccentricity")
CHANNEL_ID = {name: index for index, name in enumerate(CHANNELS)}
# Archive quantum per channel, for the registered "not constant" admissibility
# test (prereg 5.3(4)). Each is 1/SCALE for that element in orbit_history.
CHANNEL_QUANTUM = {"mean_motion": 1e-8, "inclination": 1e-4, "eccentricity": 1e-8}

FREQ_CHUNK = 128
ELEMENT_BUDGET = 2.0e7      # per (B, Npad, FREQ_CHUNK) buffer; four are live


def _array_module(force_cpu: bool):
    """NumPy or CuPy. The CuPy path borrows this repository's existing loader.

    `pipeline.orbit_drift_gpu.load_cupy` already knows that this venv's CUDA
    component wheels put libnvrtc and libcudart under `site-packages/nvidia`,
    which is not on the loader path, and already sets CUPY_CACHE_IN_MEMORY so
    no unbounded kernel cache is written to disk. Re-deriving that here would
    be a second copy of a fact that has already been learned once.
    """
    if force_cpu:
        return np, False
    from pipeline.orbit_drift_gpu import load_cupy  # noqa: PLC0415
    return load_cupy(), True


PAD_MULTIPLE = 512


def _pad_bucket(n: int) -> int:
    """Round the row width up to a multiple of PAD_MULTIPLE.

    Powers of two would waste up to half a batch on padding. That costs time,
    and it also costs precision: `gls_power` recovers the masked column sums by
    subtracting the padded rows' known constant contribution, so the smaller
    the padding the less cancellation there is to survive.
    """
    return int(-(-n // PAD_MULTIPLE) * PAD_MULTIPLE)


class _Batcher:
    """Packs ragged windows into rectangular batches of like sample count."""

    def __init__(self, xp, freqs_device, on_result, chunk=FREQ_CHUNK):
        self.xp = xp
        self.freqs = freqs_device
        self.on_result = on_result
        self.chunk = chunk
        self.buckets: dict[int, list] = {}
        self.batches = 0
        self.windows = 0

    def _capacity(self, padded: int) -> int:
        return max(1, int(ELEMENT_BUDGET // (padded * self.chunk)))

    def add(self, meta, times, values):
        padded = _pad_bucket(times.size)
        pending = self.buckets.setdefault(padded, [])
        pending.append((meta, times, values))
        if len(pending) >= self._capacity(padded):
            self._flush(padded)

    def flush_all(self):
        for padded in list(self.buckets):
            self._flush(padded)

    def _flush(self, padded):
        pending = self.buckets.pop(padded, None)
        if not pending:
            return
        xp = self.xp
        batch = len(pending)
        times = np.zeros((batch, padded), dtype=np.float32)
        values = np.zeros((batch, padded), dtype=np.float32)
        mask = np.zeros((batch, padded), dtype=np.float32)
        for row, (_meta, t, v) in enumerate(pending):
            times[row, : t.size] = t
            values[row, : v.size] = v
            mask[row, : t.size] = 1.0
        t_d = xp.asarray(times)
        v_d = xp.asarray(values)
        m_d = xp.asarray(mask)
        # Detrending already happened on the host, in float64 (see
        # `_detrend_and_normalise`), so the device only evaluates the grid.
        power = core.gls_power(t_d, v_d, m_d, self.freqs, xp, chunk=self.chunk)
        best = power.argmax(axis=1)
        pmax = power[xp.arange(batch), best]
        # Second-highest peak at least one resolution element away, so the
        # registered harmonic-ambiguity flag can be evaluated downstream.
        pmax_host = np.asarray(xp.asnumpy(pmax) if hasattr(xp, "asnumpy") else pmax)
        best_host = np.asarray(xp.asnumpy(best) if hasattr(xp, "asnumpy") else best)
        power_host = np.asarray(xp.asnumpy(power) if hasattr(xp, "asnumpy") else power)
        self.batches += 1
        self.windows += batch
        for row, (meta, _t, _v) in enumerate(pending):
            self.on_result(meta, float(pmax_host[row]), int(best_host[row]), power_host[row])


def _median_spacing(epochs_ms: np.ndarray) -> float:
    return float(np.median(np.diff(epochs_ms)) / core.DAY_MS)


def _detrend_and_normalise(times: np.ndarray, values: np.ndarray) -> np.ndarray:
    """The registered cubic detrend (prereg 5.2), then unit RMS, in float64.

    Done on the host and in float64 deliberately, on both counts:

    * Mean motion is about 14 rev/day and a station-keeping signature can be of
      order 1e-6 rev/day. float32 resolves 1.7e-6 at 14.0, so casting the raw
      series to float32 would quantise the signal away before the periodogram
      ever saw it. `tests/test_orbit_cadence.py` asserts that failure mode
      directly.
    * The detrend needs a small linear solve, and this environment's CuPy wheel
      set ships neither cuBLAS nor cuSOLVER. The device does the one thing it
      is actually needed for -- the grid evaluation, which is the whole cost --
      and nothing else.

    Lomb-Scargle power is a variance FRACTION, so it is invariant to both the
    additive offset and the multiplicative scale removed here; normalising
    changes no registered quantity and buys back the entire float32 mantissa
    for the part of the series that carries information.
    """
    t = np.asarray(times, dtype=np.float64)[None, :]
    v = np.asarray(values, dtype=np.float64)[None, :]
    m = np.ones_like(t)
    residual = core.detrend_batch(t, v, m, np)[0]
    scale = float(np.sqrt((residual * residual).mean()))
    if not np.isfinite(scale) or scale <= 0.0:
        return np.zeros(residual.size, dtype=np.float32)
    return (residual / scale).astype(np.float32)


def run(art: Path, out: Path, shard: int, shards: int, channels, force_cpu: bool,
        limit: int | None = None) -> dict:
    index = json.loads((art / "index.json").read_text())
    objects = index["objects"]
    lengths = np.array([o["length"] for o in objects], dtype=np.int64)
    total_rows = int(lengths.sum())

    memmaps = {
        "epoch_ms": np.memmap(art / "epoch_ms.bin", dtype="<i8", mode="r", shape=(total_rows,)),
        "mean_motion": np.memmap(art / "mean_motion.bin", dtype="<f8", mode="r", shape=(total_rows,)),
        "inclination": np.memmap(art / "inclination.bin", dtype="<f4", mode="r", shape=(total_rows,)),
        "eccentricity": np.memmap(art / "eccentricity.bin", dtype="<f8", mode="r", shape=(total_rows,)),
    }

    xp, on_gpu = _array_module(force_cpu)
    freqs = core.frequency_grid()
    freqs_device = xp.asarray(freqs.astype(np.float32))

    rows = {name: [] for name in (
        "norad", "window", "channel", "n", "tStartMs", "medianSpacingDays",
        "perigeeKm", "inclinationDeg", "eccentricity", "pmax", "freqCyclesPerDay",
        "secondPeakRatio", "secondPeakFreq")}
    rejects = {}

    def on_result(meta, pmax, best_index, spectrum):
        f_star = float(freqs[best_index])
        # Registered harmonic-ambiguity input (prereg 2.1): the strongest peak
        # separated from f* by more than 3 resolution elements.
        guard = 3
        masked = spectrum.copy()
        lo = max(0, best_index - guard)
        masked[lo: best_index + guard + 1] = -1.0
        second = int(masked.argmax())
        rows["norad"].append(meta["norad"])
        rows["window"].append(meta["window"])
        rows["channel"].append(meta["channel"])
        rows["n"].append(meta["n"])
        rows["tStartMs"].append(meta["tStartMs"])
        rows["medianSpacingDays"].append(meta["medianSpacingDays"])
        rows["perigeeKm"].append(meta["perigeeKm"])
        rows["inclinationDeg"].append(meta["inclinationDeg"])
        rows["eccentricity"].append(meta["eccentricity"])
        rows["pmax"].append(pmax)
        rows["freqCyclesPerDay"].append(f_star)
        rows["secondPeakRatio"].append(float(masked[second] / pmax) if pmax > 0 else 0.0)
        rows["secondPeakFreq"].append(float(freqs[second]))

    batcher = _Batcher(xp, freqs_device, on_result)
    started = time.monotonic()
    considered = 0
    admitted = 0
    processed = 0
    for position, obj in enumerate(objects):
        if position % shards != shard:
            continue
        if limit and processed >= limit:
            break
        processed += 1
        lo = obj["offset"]
        hi = lo + obj["length"]
        epochs = np.asarray(memmaps["epoch_ms"][lo:hi])
        t0 = epochs[0]
        days = (epochs - t0) / core.DAY_MS
        for window_index, (start, end) in enumerate(
                core.window_bounds(obj["firstEpochMs"], obj["lastEpochMs"])):
            sel = np.searchsorted(days, [start, end])
            piece = slice(int(sel[0]), int(sel[1]))
            times = days[piece] - start
            considered += 1
            primary = np.asarray(memmaps["mean_motion"][lo + piece.start: lo + piece.stop])
            ok, reason = core.window_admissible(times, primary)
            if not ok:
                rejects[reason] = rejects.get(reason, 0) + 1
                continue
            admitted += 1
            ecc = np.asarray(memmaps["eccentricity"][lo + piece.start: lo + piece.stop])
            inc = np.asarray(memmaps["inclination"][lo + piece.start: lo + piece.stop])
            mm_median = float(np.median(primary))
            ecc_median = float(np.median(ecc))
            meta_base = {
                "norad": obj["norad"], "window": window_index, "n": int(times.size),
                "tStartMs": int(t0 + start * core.DAY_MS),
                "medianSpacingDays": _median_spacing(epochs[piece]),
                "perigeeKm": core.perigee_km(mm_median, ecc_median),
                "inclinationDeg": float(np.median(inc)),
                "eccentricity": ecc_median,
            }
            series = {"mean_motion": primary, "inclination": inc.astype(np.float64),
                      "eccentricity": ecc}
            for channel in channels:
                values = series[channel]
                if float(values.max() - values.min()) <= CHANNEL_QUANTUM[channel]:
                    rejects[f"constant:{channel}"] = rejects.get(f"constant:{channel}", 0) + 1
                    continue
                meta = dict(meta_base, channel=CHANNEL_ID[channel])
                batcher.add(meta, times.astype(np.float32),
                            _detrend_and_normalise(times, values))
        if position % 2000 == 0:
            print(f"  object {position}/{len(objects)} shard {shard}: "
                  f"{batcher.windows:,} window-channels, "
                  f"{time.monotonic() - started:.0f}s", file=sys.stderr, flush=True)

    batcher.flush_all()
    elapsed = time.monotonic() - started

    dtypes = {"norad": "<i4", "window": "<i2", "channel": "u1", "n": "<i4",
              "tStartMs": "<i8", "medianSpacingDays": "<f4", "perigeeKm": "<f4",
              "inclinationDeg": "<f4", "eccentricity": "<f8", "pmax": "<f4",
              "freqCyclesPerDay": "<f4", "secondPeakRatio": "<f4",
              "secondPeakFreq": "<f4"}
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, **{k: np.asarray(v, dtype=dtypes[k]) for k, v in rows.items()})

    peak_mib = None
    if on_gpu:
        # Estate rule: unmeasured GPU use is a defect. Report what this job
        # actually held, so the next --estimate-mib is evidence and not a guess.
        peak_mib = round(xp.get_default_memory_pool().used_bytes() / (1024 ** 2), 1)
        peak_total_mib = round(xp.get_default_memory_pool().total_bytes() / (1024 ** 2), 1)
    summary = {"shard": shard, "shards": shards, "objects": processed,
               "windowsConsidered": considered, "windowsAdmitted": admitted,
               "windowChannelsEvaluated": batcher.windows, "batches": batcher.batches,
               "rejects": rejects, "seconds": round(elapsed, 1),
               "device": "gpu" if on_gpu else "cpu",
               "cudaVisibleDevices": os.environ.get("CUDA_VISIBLE_DEVICES", ""),
               "gpuBrokerRequestId": os.environ.get("GPU_BROKER_REQUEST_ID", ""),
               "frequencies": int(freqs.size), "channels": list(channels),
               "peakPoolMib": peak_total_mib if on_gpu else None,
               "residentPoolMib": peak_mib}
    Path(str(out) + ".summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--shards", type=int, default=1)
    parser.add_argument("--channels", default="mean_motion",
                        help="comma-separated; primary is mean_motion (prereg 3.2)")
    parser.add_argument("--cpu", action="store_true", help="NumPy instead of CuPy")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    channels = tuple(c.strip() for c in args.channels.split(",") if c.strip())
    unknown = set(channels) - set(CHANNELS)
    if unknown:
        raise SystemExit(f"unknown channel(s): {sorted(unknown)}")

    summary = run(args.artifacts, args.out, args.shard, args.shards, channels,
                  args.cpu, limit=args.limit)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
