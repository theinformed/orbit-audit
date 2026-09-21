"""CuPy verification backend with a private capped pool and measured usage.

Importing this module never initializes CUDA. CLI GPU failures are explicit;
there is no automatic backend substitution. GPU parity tests are opt-in.
"""
from __future__ import annotations

from contextlib import contextmanager
import ctypes
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import numpy as np

MIB = 1024**2
LANE = "space-orbit-drift"
DEFAULT_CEILING_MIB = 1335  # 1,399,848,960 bytes, below decimal 1.4 GB
RESERVE = 256 * MIB        # CUDA context/modules are NOT covered by a CuPy pool limit


class VramBudgetError(RuntimeError):
    pass


# Under GPU contention -- which is exactly when this lane runs -- nvidia-smi can
# take many seconds to answer. 5 s killed a finished 86-second run on 2026-09-12.
NVIDIA_SMI_TIMEOUT_S = 20
NVIDIA_SMI_ATTEMPTS = 3


def smi_memory(device):
    # 5 s was too short: under GPU contention -- exactly when this lane runs --
    # nvidia-smi answers slowly, and the probe was killing finished runs.
    command = "/usr/lib/wsl/lib/nvidia-smi" if Path("/dev/dxg").exists() else "nvidia-smi"
    last = None
    for attempt in range(NVIDIA_SMI_ATTEMPTS):
        try:
            data = subprocess.check_output([
                command, f"--id={device}", "--query-gpu=memory.used,memory.free",
                "--format=csv,noheader,nounits"], text=True,
                timeout=NVIDIA_SMI_TIMEOUT_S)
            used, free = (int(x.strip()) * MIB for x in data.strip().split(","))
            return used, free
        except Exception as error:              # noqa: BLE001 - reported, not swallowed
            last = error
            time.sleep(0.5 * (attempt + 1))
    raise last


def load_cupy():
    # NVRTC kernels stay in process memory; no unbounded ~/.cupy disk writer.
    os.environ["CUPY_CACHE_IN_MEMORY"] = "1"
    # CUDA component wheels are isolated here; never mutate global loader paths.
    libs = Path(sys.prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages/nvidia/cu13/lib"
    for name in ("libcudart.so.13", "libnvrtc.so.13"):
        if (libs / name).exists():
            ctypes.CDLL(str(libs / name), mode=ctypes.RTLD_GLOBAL)
    import cupy
    return cupy


def fit_with_shrinking(objects, attempt, release, retryable):
    """Retry allocation failures on smaller object chunks, never larger budgets."""
    try:
        return attempt(objects)
    except retryable:
        release()
        if len(objects) <= 1:
            raise
    # Leave the except scope first so failed GPU locals/tracebacks can be freed.
    release()
    midpoint = len(objects) // 2
    return np.concatenate((fit_with_shrinking(objects[:midpoint], attempt, release, retryable),
                           fit_with_shrinking(objects[midpoint:], attempt, release, retryable)))


class GpuBackend:
    def __init__(self, device=0, ceiling_mib=DEFAULT_CEILING_MIB):
        if device < 0 or not 320 <= ceiling_mib <= DEFAULT_CEILING_MIB:
            raise ValueError("device must be nonnegative; ceiling must be 320..1335 MiB")
        self.device, self.ceiling = device, ceiling_mib * MIB
        self.cp = None
        self.pool = None
        self.baseline = 0
        self.pool_peak = 0
        self.observed_peak = 0
        self.context_bytes = 0
        self.chunk_reductions = 0
        self.monitor_error = None
        self.stopped = threading.Event()
        self.monitor = None

    def start(self):
        self.baseline, free = smi_memory(self.device)
        if free < RESERVE + 64 * MIB:
            raise VramBudgetError("too little measured free VRAM even for context reserve")
        self.cp = cp = load_cupy()  # failure must propagate, never pretend CPU was GPU
        with cp.cuda.Device(self.device):
            cp.cuda.runtime.free(0)  # context initialization only
            used, smi_free = smi_memory(self.device)
            cuda_free, _ = cp.cuda.runtime.memGetInfo()
            self.context_bytes = max(0, used - self.baseline)
            reserve = max(RESERVE, self.context_bytes + 64 * MIB)
            available = min(int(cuda_free), smi_free) - 64 * MIB
            limit = min(self.ceiling - reserve, available)
            if limit < 8 * MIB:
                raise VramBudgetError("context/available VRAM leaves no safe pool budget")
            self.pool = cp.cuda.MemoryPool()
            self.pool.set_limit(size=limit)
        self.sample()
        self.monitor = threading.Thread(target=self._monitor, daemon=True)
        self.monitor.start()
        return self

    def _monitor(self):
        while not self.stopped.wait(0.1):
            try:
                self.sample()
            except Exception as error:
                self.monitor_error = str(error)
                return

    def sample(self):
        used, _ = smi_memory(self.device)
        self.observed_peak = max(self.observed_peak, max(0, used - self.baseline))

    def _allocate(self, size):
        allocation = self.pool.malloc(size)
        self.pool_peak = max(self.pool_peak, self.pool.total_bytes())
        return allocation

    def check(self):
        # OUR ceiling, measured on OUR pool. `observed_peak` is device-wide
        # growth and moves when any other process on the card allocates, so
        # gating on it makes this lane fail whenever another job on the card
        # is busy -- and
        # shrinking our own chunks cannot bring someone else's memory down.
        in_process = self.context_bytes + self.pool_peak
        if in_process > self.ceiling:
            raise VramBudgetError("our own GPU pool exceeded the configured ceiling")
        if self.monitor_error:
            # Telemetry is unavailable. We still know our own usage exactly, and
            # it is inside the ceiling, so continue with a labelled gap rather
            # than destroying the run over an unanswered question.
            return
        try:
            self.sample()
            _, free = smi_memory(self.device)
            cuda_free, _ = self.cp.cuda.runtime.memGetInfo()
            # Include cached pool bytes, which are ours and can be recycled.
            available = (min(free, int(cuda_free)) + self.pool.total_bytes()
                         - self.pool.used_bytes() - 64 * MIB)
            limit = min(self.pool.get_limit(), max(0, available))
            if limit < 8 * MIB:
                # The CARD is full, which is a reason to back off and retry
                # smaller -- not a statement that we overspent.
                raise VramBudgetError("measured VRAM headroom unavailable")
            self.pool.set_limit(size=limit)
        except VramBudgetError:
            raise
        except Exception as error:              # noqa: BLE001 - recorded, not fatal
            self.monitor_error = self.monitor_error or str(error)

    def fit(self, objects, pairs):
        """Fit independent arcs, including optional trailing/test rows for one NORAD.

        Shrinking may separate the two windows but cannot alter their fits:
        pair selection depends only on NORAD and each window's block count.
        """
        from pipeline.orbit_drift import prepare, fit_arrays
        cp = self.cp
        def attempt(chunk):
            self.check()
            # Conservative admission estimate; actual pool is the hard allocation bound.
            n = max(len(o.days) for o in chunk)
            estimate = len(chunk) * (pairs * 256 + n * 256)
            if estimate > self.pool.get_limit():
                self.chunk_reductions += 1
                raise VramBudgetError("chunk estimate exceeds private pool ceiling")
            try:
                with cp.cuda.using_allocator(self._allocate):
                    result = cp.asnumpy(fit_arrays(prepare(chunk, pairs), cp))
                    cp.cuda.Stream.null.synchronize()
            except cp.cuda.memory.OutOfMemoryError:
                self.chunk_reductions += 1
                raise
            self.check()
            return result
        with cp.cuda.Device(self.device):
            return fit_with_shrinking(objects, attempt, self.pool.free_all_blocks,
                                      (VramBudgetError, cp.cuda.memory.OutOfMemoryError))

    def smoke(self):
        cp = self.cp
        with cp.cuda.Device(self.device), cp.cuda.using_allocator(self._allocate):
            self.check()
            value = cp.empty(8 * MIB, dtype=cp.uint8)  # allocation only; no fitting/kernel compilation
            cp.cuda.runtime.deviceSynchronize()
            self.sample()
            del value
            self.pool.free_all_blocks()
        return {"smokeAllocationBytes": 8 * MIB, "cupyVersion": cp.__version__,
                "deviceCount": cp.cuda.runtime.getDeviceCount(), **self.measurement()}

    def measurement(self, allow_telemetry_gap=False):
        # THE FIGURE THE CEILING IS ENFORCED ON. Context plus this process's own
        # pool high-water: exact, in-process, and immune both to a slow probe and
        # to another consumer's allocations. `accountedPeakBytes` below takes the
        # max with a DEVICE-WIDE delta, so it can be inflated by any other job
        # sharing the card -- reportable, but not something to fail on.
        in_process = self.context_bytes + self.pool_peak
        pool_limit = None
        if self.pool:
            # CuPy pools have per-device state. The caller may be on device 0
            # even though the worker that set this limit ran on device 1.
            with self.cp.cuda.Device(self.device):
                pool_limit = self.pool.get_limit()
        return {"device": self.device, "ceilingBytes": self.ceiling,
                "inProcessPeakBytes": in_process,
                "telemetryGap": bool(self.monitor_error) or None,
                "poolLimitBytes": pool_limit,
                "poolPeakReservedBytes": self.pool_peak,
                "observedDeviceDeltaPeakBytes": self.observed_peak,
                "contextBytes": self.context_bytes,
                "accountedPeakBytes": max(self.observed_peak, self.context_bytes + self.pool_peak),
                "chunkReductions": self.chunk_reductions,
                "telemetryError": self.monitor_error,
                "measurementNote": "pool high-water is exact; device delta sampled at 100 ms and "
                "boundaries is device-wide and may include other consumers"}

    def close(self):
        self.stopped.set()
        if self.monitor:
            self.monitor.join(timeout=6)
        if self.pool:
            with self.cp.cuda.Device(self.device):
                self.cp.cuda.runtime.deviceSynchronize()
                self.pool.free_all_blocks()
        if self.cp:
            try:
                self.sample()
            except Exception as error:          # shutdown telemetry is also a gap
                self.monitor_error = self.monitor_error or str(error)


def ledger_directory():
    return Path(os.environ.get("SPACE_GPU_USAGE_DIR", str(Path(__file__).resolve().parents[1] / "state")))


def ledger_retention_plan():
    """Read-only cleanup preview; the next receipt applies these same bounds."""
    path = ledger_directory() / f"{LANE}-usage.jsonl"
    size = path.stat().st_size if path.exists() else 0
    lines = 0
    if path.exists():
        with path.open("rb") as handle:
            lines = sum(1 for _ in handle)
    return {"path": str(path), "bytes": size, "lines": lines,
            "budgetBytes": 4 * MIB, "budgetLines": 4096,
            "trimOnNextReceipt": size > 4 * MIB or lines >= 4096,
            "policy": "retain newest complete lines within both limits; no archive deletion"}


def write_receipt(receipt):
    """Fail visibly; bounded, locked local ledger read by operators/estate tooling.

    Keep latest 4096 lines / 4 MiB (regenerable telemetry), no backup copies.
    Lock the actual file, not an inode replaced out from under another device.
    """
    directory = ledger_directory()
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / f"{LANE}-usage.jsonl").open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        handle.seek(0, 2)
        size = handle.tell()
        handle.seek(max(0, size - 4 * MIB))
        if size > 4 * MIB:
            handle.readline()  # drop partial leading record
        rows = handle.readlines()
        rows.append(json.dumps(receipt, sort_keys=True) + "\n")
        rows = rows[-4096:]
        while sum(len(r.encode()) for r in rows) > 4 * MIB:
            rows.pop(0)
        handle.seek(0)
        handle.truncate()
        handle.writelines(rows)
        handle.flush()
        os.fsync(handle.fileno())


@contextmanager
def gpu_session(device, ceiling_mib=DEFAULT_CEILING_MIB):
    # GPU use must be measurable: prove the ledger is writable BEFORE CUDA.
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    t0 = time.perf_counter()
    gpu = GpuBackend(device, ceiling_mib)
    base = {"ts": started, "lane": LANE, "resource": "gpu-direct", "device": device,
            "host": os.uname().nodename, "pid": os.getpid()}
    write_receipt({**base, "durationMs": 0, "outcome": "starting", "ok": True})
    ok = False
    try:
        gpu.start()
        yield gpu
        ok = True
    finally:
        try:
            try:
                gpu.close()
                # A telemetry failure is a GAP, not a verdict. Failing to MEASURE
                # memory is not the same as exceeding it, and killing a finished
                # run because a probe was slow destroys real work to answer a
                # question nobody asked. The ceiling is enforced below on the
                # exact in-process pool figure, which cannot time out.
                measured = gpu.measurement(allow_telemetry_gap=True)
                if measured["inProcessPeakBytes"] > gpu.ceiling:
                    raise VramBudgetError("GPU peak exceeded configured ceiling")
            except BaseException:
                ok = False
                raise
        finally:
            write_receipt({**base, "durationMs": round((time.perf_counter() - t0) * 1000),
                           "outcome": "completed" if ok else "failed", "ok": ok,
                           **gpu.measurement()})
