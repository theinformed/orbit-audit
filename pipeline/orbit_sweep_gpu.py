"""Default-off sweep arithmetic execution and independent CPU verification.

Physics inputs (_observed and natural_floor) remain the canonical CPU functions.
All robust statistics, self-history residuals, z scores and forward persistence
are evaluated on device. Selections and flags must match exactly; only hypot
and its derived z score permit a small floating-point tolerance (see docs).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import sys
import time
import math

import numpy as np

import ctypes as _ctypes
import datetime as _dt
import glob as _glob
import json as _json
import os as _os
from pathlib import Path as _Path

from pipeline.orbit_drift_gpu import load_cupy, smi_memory, MIB, VramBudgetError

_ROOT = _Path(__file__).resolve().parents[1]
_USAGE_LEDGER = _ROOT / "state" / "space-orbit-sweep-gpu-usage.jsonl"


def _preload_nvrtc():
    """Load the venv's NVIDIA runtime libraries before cupy needs them.

    pip installs libnvrtc under site-packages/nvidia/*/lib, which is not on the
    loader path. Without this, RawKernel compilation fails at first use -- and
    under systemd there is no operator shell to have exported LD_LIBRARY_PATH.
    Best-effort by design: if the libraries are genuinely absent, load_cupy()
    fails loudly on its own and the sweep falls back to CPU, loudly.
    """
    for pattern in ("lib/python*/site-packages/nvidia/*/lib/libnvrtc.so*",
                    "lib/python*/site-packages/nvidia/*/lib/libcudart.so*"):
        for lib in sorted(_glob.glob(str(_ROOT / ".venv-gpu" / pattern))):
            try:
                _ctypes.CDLL(lib, mode=_ctypes.RTLD_GLOBAL)
            except OSError:
                pass


def _write_receipt(entry):
    """Append one usage record. GPU use must be measurable (estate rule);
    a ledger failure is reported but never kills the analysis itself."""
    try:
        _USAGE_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with open(_USAGE_LEDGER, "a", encoding="utf-8") as fh:
            fh.write(_json.dumps(entry, sort_keys=True) + "\n")
    except OSError as error:
        print(f"SWEEP GPU RECEIPT FAILED: {error}", file=sys.stderr)

DEFAULT_CEILING_MIB = 1335  # 1,399,848,960 bytes, below decimal 1.4 GB
CONTEXT_RESERVE = 256 * MIB
Z_ATOL = 1e-10
Z_RTOL = 2e-15


class AgreementError(AssertionError):
    pass


def median(values, cp):
    """Python statistics.median convention, including the even addition order."""
    ordered = cp.sort(values)
    n = len(ordered)
    return ordered[n // 2] if n % 2 else (ordered[n // 2 - 1] + ordered[n // 2]) / 2.0


PERSISTENCE_KERNEL = r'''
extern "C" __global__ void persist(
    const double* residual, const unsigned char* valid,
    const long long* start, const long long* end, int n, int channels,
    long long horizon, double gap, double fraction, unsigned char* out) {
    int t = blockDim.x * blockIdx.x + threadIdx.x;
    if (t >= n * channels) return;
    int p = t / channels, c = t % channels;
    out[t] = 0;
    if (!valid[t] || residual[t] == 0.0) return;
    double r = residual[t];
    if (p > 0 && start[p] - end[p-1] <= gap && valid[t-channels]) {
        double prev = residual[t-channels];
        if (prev * r < 0.0 && fabs(prev + r) < fraction * fabs(r)) return;
    }
    double running = r, lowest = fabs(r);
    long long previous_end = end[p];
    int checked = 0;
    for (int q=p+1; q<n; ++q) {
        int j = q * channels + c;
        if (start[q] - previous_end > gap || start[q] - end[p] > horizon || !valid[j]) break;
        running += residual[j];  // serial CPU order, NOT a parallel reduction
        double value = r > 0.0 ? running : -running;
        lowest = value < lowest ? value : lowest;
        ++checked;
        previous_end = end[q];
    }
    if (checked && previous_end - end[p] >= horizon)
        out[t] = lowest / fabs(r) >= fraction;
}
'''

BASELINE_KERNEL = r'''
__device__ void stable_sort(double* x, int n, int stride) {
    for (int j=1; j<n; ++j) {
        double value=x[j*stride]; int k=j;
        while (k && value < x[(k-1)*stride]) {x[k*stride]=x[(k-1)*stride]; --k;}
        x[k*stride]=value;
    }
}
__device__ double middle(double* x, int n, int stride) {
    return n % 2 ? x[(n/2)*stride] : (x[(n/2-1)*stride]+x[(n/2)*stride])/2.0;
}
extern "C" __global__ void blocks(
    const double* obs, const double* spans, const long long* order,
    const long long* offsets, int count, int channels, double* scratch, double* out) {
    int t=blockDim.x*blockIdx.x+threadIdx.x;
    if (t>=count*channels) return;
    int b=t/channels,c=t%channels,n=0;
    double* values=scratch+offsets[b]*channels+c;
    for(long long j=offsets[b];j<offsets[b+1];++j) {
        long long p=order[j]; double o=obs[p*channels+c];
        if (!isnan(o) && spans[p]>0) values[(n++)*channels]=o/spans[p];
    }
    double med=0,mad=0;
    if (n) {
        stable_sort(values,n,channels); med=middle(values,n,channels);
        for(int j=0;j<n;++j) values[j*channels]=fabs(values[j*channels]-med);
        stable_sort(values,n,channels); mad=middle(values,n,channels)*1.4826;
    }
    out[t*3]=med; out[t*3+1]=mad; out[t*3+2]=n;
}
extern "C" __global__ void baselines(
    const double* blocks, const long long* neighbors, int count, int channels,
    int width, double* out) {
    int t=blockDim.x*blockIdx.x+threadIdx.x;
    if(t>=count*channels) return;
    int b=t/channels,c=t%channels,n=0,samples=0;
    double medians[12],mads[12];
    for(int j=0;j<width;++j) {
        long long k=neighbors[b*width+j];
        if(k<0) continue;
        const double* block=blocks+(k*channels+c)*3;
        if(block[2]==0) continue;
        medians[n]=block[0]; mads[n]=block[1]; ++n; samples+=(int)block[2];
    }
    double rate=0,within=0,between=0;
    if(n) {
        stable_sort(medians,n,1); rate=middle(medians,n,1);
        stable_sort(mads,n,1); within=middle(mads,n,1);
        for(int j=0;j<n;++j) medians[j]=fabs(medians[j]-rate);
        stable_sort(medians,n,1); between=middle(medians,n,1)*1.4826;
    }
    out[t*6]=rate; out[t*6+1]=within>=between?within:between;
    out[t*6+2]=n; out[t*6+3]=samples; out[t*6+4]=within; out[t*6+5]=between;
}
'''


@dataclass
class Arithmetic:
    elements: tuple
    baselines: np.ndarray  # interval, element, rate/scale/blocks/samples/within/between
    own_floor: np.ndarray
    residual: np.ndarray
    sigma: np.ndarray
    z: np.ndarray
    self_z: np.ndarray
    valid: np.ndarray
    tripped: np.ndarray
    persistent: np.ndarray
    inclination_uncorroborated: np.ndarray

    def baseline_rows(self):
        """Decode device results; do not recompute baseline arithmetic on CPU."""
        from pipeline.orbit_campaigns import Baseline
        # All intervals in a block share the same device baseline. Reuse the
        # immutable values instead of allocating millions of identical objects.
        # Byte keys preserve signed zeros; numeric tuple keys would merge them.
        cache, rows = {}, []
        for row in self.baselines:
            key = row.tobytes()
            if key not in cache:
                cache[key] = {e: Baseline(float(v[0]), float(v[1]), int(v[2]), int(v[3]),
                                          float(v[4]), float(v[5]))
                              for e, v in zip(self.elements, row)}
            rows.append(cache[key])
        return rows

    def channel_tests(self, position, baselines):
        from pipeline.orbit_campaigns import ChannelTest
        return [ChannelTest(
            element=e, delta=float(self.residual[position, c]),
            floor_sigma=float(self.sigma[position, c]), floor_z=float(self.z[position, c]),
            cohort_z=None if math.isnan(self.self_z[position, c]) else float(self.self_z[position, c]),
            cohort_count=baselines[e].samples, cohort_screened=baselines[e].usable,
            tripped=bool(self.tripped[position, c]), basis="self-history")
            for c, e in enumerate(self.elements) if self.valid[position, c]]


def prepare(intervals, *, epoch_slices=None):
    from pipeline import orbit_campaigns as oc
    elements = oc.ELEMENTS
    observed = np.array([[oc._observed(i, e) for e in elements] for i in intervals], dtype=np.float64)
    floors = np.array([[oc.natural_floor(i, e) for e in elements] for i in intervals], dtype=np.float64)
    if epoch_slices is not None:
        starts, ends = epoch_slices["starts"], epoch_slices["ends"]
    else:
        starts = np.array([i.start_ms for i in intervals], dtype=np.int64)
        ends = np.array([i.end_ms for i in intervals], dtype=np.int64)
    indices = ((starts + ends) // 2) // int(oc.BLOCK_DAYS * 86400000)
    unique, inverse = np.unique(indices, return_inverse=True)
    lookup = {int(b): j for j, b in enumerate(unique)}
    neighbors = np.array([[lookup.get(int(b) + offset, -1)
                           for offset in range(-oc.BASELINE_BLOCKS, oc.BASELINE_BLOCKS + 1)
                           if offset] for b in unique], dtype=np.int64)
    if neighbors.shape[1] > 12:
        raise ValueError("GPU baseline kernel supports at most +/-6 blocks")
    order = np.argsort(inverse, kind="stable")
    offsets = np.concatenate(([0], np.cumsum(np.bincount(inverse)))).astype(np.int64)
    return (elements, observed, floors, starts, ends, inverse, neighbors,
            np.array([i.span_days for i in intervals]),
            np.array([i.perigee_altitude_km for i in intervals]), order, offsets,
            np.array([i.inclination_deg for i in intervals]))


def arithmetic(prepared, kappa, cp, kernels):
    from pipeline import orbit_campaigns as oc
    elements, observed, floors, starts, ends, inverse, neighbors, spans, perigees, order, offsets, inclinations = prepared
    obs, floors, starts, ends, groups, neighbors, spans, perigees, order, offsets = map(
        cp.asarray, (observed, floors, starts, ends, inverse, neighbors, spans, perigees, order, offsets))
    n, channels = obs.shape
    count = len(neighbors)
    own_floors = []
    valid = ~cp.isnan(obs)
    block_stats = cp.empty((count, channels, 3), dtype=cp.float64)
    scratch = cp.empty_like(obs)
    launch = (((count * channels + 127) // 128,), (128,))
    kernels["blocks"](*launch, (obs, spans, order, offsets, np.int32(count), np.int32(channels), scratch, block_stats))
    block_bases = cp.empty((count, channels, 6), dtype=cp.float64)
    kernels["baselines"](*launch, (block_stats, neighbors, np.int32(count), np.int32(channels),
                                 np.int32(neighbors.shape[1]), block_bases))
    bases = block_bases[groups]
    residual = obs - bases[:, :, 0] * spans[:, None]
    for c, element in enumerate(elements):
        residuals = cp.abs(residual[valid[:, c], c])
        own = median(residuals, cp) * 1.4826 if len(residuals) else cp.asarray(0.0)
        if oc.INCLINATION_FLOOR_TAIL_AWARE and element == "inclination" and len(residuals):
            # The floor table is a CPU policy lookup on an exactly selected GPU median.
            if oc.noise_floor_for(float(median(perigees, cp)))[2] <= oc.ANGLE_QUANTISATION_DEG:
                ordered = cp.sort(residuals)
                index = (len(ordered) - 1) * 0.95
                low, high = int(index), min(int(index) + 1, len(ordered) - 1)
                q95 = ordered[low] + (ordered[high] - ordered[low]) * (index - low)
                own = cp.maximum(own, q95 / 1.96)
        own_floors.append(own)
    own = cp.stack(own_floors)
    expected_sigma = bases[:, :, 1] * spans[:, None]
    sigma = cp.hypot(cp.maximum(floors, own[None, :]), expected_sigma)
    z = cp.where(sigma > 0, residual / sigma, 0.0)
    self_z = cp.where(expected_sigma > 0, residual / expected_sigma, cp.nan)
    thresholds = cp.asarray([kappa * oc.NODE_CHANNEL_KAPPA_MULTIPLIER if e == "raan" else kappa for e in elements])
    usable = (bases[:, :, 2] >= oc.MINIMUM_BASELINE_BLOCKS) & (bases[:, :, 3] >= oc.MINIMUM_BASELINE_INTERVALS)
    tripped = valid & usable & (cp.abs(z) > thresholds) & (cp.isnan(self_z) | (cp.abs(self_z) > thresholds))
    persistent = cp.zeros((n, channels), dtype=cp.uint8)
    kernels["persist"](((n * channels + 127) // 128,), (128,),
                       (residual, valid.view(cp.uint8), starts, ends, np.int32(n), np.int32(channels),
                        np.int64(oc.PERSISTENCE_HORIZON_DAYS * 86400000),
                        np.float64(oc.MAXIMUM_JOINABLE_GAP_DAYS * 86400000),
                        np.float64(oc.PERSISTENCE_FRACTION), persistent))
    # Keep raw threshold/persistence decisions for exact oracle comparison.
    # Corroboration is a separate decision using BOTH surviving energy trips;
    # a raw energy spike that failed persistence cannot rescue inclination.
    surviving = tripped & persistent.astype(cp.bool_)
    uncorroborated = cp.zeros(n, dtype=cp.bool_)
    if "inclination" in elements:
        energy = cp.zeros(n, dtype=cp.bool_)
        for element in ("semiMajorAxis", "eccentricity"):
            if element in elements:
                energy |= surviving[:, elements.index(element)]
        uncorroborated = (surviving[:, elements.index("inclination")] & ~energy
                         & (cp.asarray(inclinations) >= oc.INCLINATION_CORROBORATION_MIN_DEG))
    return Arithmetic(elements, *[cp.asnumpy(a) for a in
                      (bases, own, residual, sigma, z, self_z, valid, tripped, persistent, uncorroborated)])


class Backend:
    """One card, one nonblocking stream, private pool released after each object."""
    def __init__(self, device=0, ceiling_mib=DEFAULT_CEILING_MIB):
        if device < 0 or not 320 <= ceiling_mib <= DEFAULT_CEILING_MIB:
            raise ValueError("device >= 0 and ceiling 320..1335 MiB required")
        self.device, self.ceiling = device, ceiling_mib * MIB
        self.cp = self.pool = self.stream = self.kernel = None
        self.pool_peak = 0
        self.telemetry_gaps = []
        self.objects = self.intervals = 0
        self.wall_seconds = self.cpu_seconds = 0.0

    def start(self):
        _preload_nvrtc()
        self._started_iso = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
        self._started_clock = time.perf_counter()
        _write_receipt({"ts": self._started_iso, "lane": "space-orbit-sweep-gpu",
                        "resource": "gpu-direct", "device": self.device,
                        "host": _os.uname().nodename, "pid": _os.getpid(),
                        "outcome": "starting"})
        self.cp = cp = load_cupy()
        # Availability is admission only, never a device-used memory ceiling.
        try:
            _, free = smi_memory(self.device)
            if free < self.ceiling + 64 * MIB:
                raise VramBudgetError("insufficient measured admission headroom")
        except VramBudgetError:
            raise
        except Exception as error:
            self.telemetry_gaps.append(str(error))
            print(f"SWEEP GPU TELEMETRY GAP device={self.device}: {error}", file=sys.stderr)
        with cp.cuda.Device(self.device):
            self.stream = cp.cuda.Stream(non_blocking=True)
            self.pool = cp.cuda.MemoryPool()
            self.pool.set_limit(size=self.ceiling - CONTEXT_RESERVE)
            options = ("--fmad=false", "--prec-div=true", "--prec-sqrt=true")
            self.kernel = {name: cp.RawKernel(code, name, options=options)
                           for name, code in (("persist", PERSISTENCE_KERNEL), ("blocks", BASELINE_KERNEL),
                                              ("baselines", BASELINE_KERNEL))}
        return self

    def _allocate(self, size):
        result = self.pool.malloc(size)
        self.pool_peak = max(self.pool_peak, self.pool.total_bytes())
        if CONTEXT_RESERVE + self.pool_peak > self.ceiling:
            raise VramBudgetError("own context reserve + private pool high-water exceeds ceiling")
        return result

    def analyze(self, intervals, kappa, *, epoch_slices=None):
        wall, cpu = time.perf_counter(), time.thread_time()
        try:
            with self.cp.cuda.Device(self.device), self.stream, self.cp.cuda.using_allocator(self._allocate):
                result = arithmetic(prepare(intervals, epoch_slices=epoch_slices), kappa, self.cp, self.kernel)
                self.stream.synchronize()
            self.objects += 1
            self.intervals += len(intervals)
            return result
        finally:
            with self.cp.cuda.Device(self.device):
                self.stream.synchronize()
                self.pool.free_all_blocks()
            self.wall_seconds += time.perf_counter() - wall
            self.cpu_seconds += time.thread_time() - cpu

    def measurement(self):
        return dict(device=self.device, ceilingBytes=self.ceiling, poolPeakBytes=self.pool_peak,
                    contextReserveBytes=CONTEXT_RESERVE,
                    chargedPeakBytes=CONTEXT_RESERVE + self.pool_peak,
                    contextMeasurement="unavailable per process under WSL; conservative 256 MiB reserve",
                    telemetryGaps=self.telemetry_gaps, objects=self.objects, intervals=self.intervals,
                    wallSeconds=self.wall_seconds, cpuSeconds=self.cpu_seconds)

    def close(self):
        if self.pool:
            with self.cp.cuda.Device(self.device):
                self.stream.synchronize()
                self.pool.free_all_blocks()
        if getattr(self, "_started_iso", None):
            duration_ms = round((time.perf_counter() - self._started_clock) * 1000)
            _write_receipt({"ts": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
                            "lane": "space-orbit-sweep-gpu", "resource": "gpu-direct",
                            "device": self.device, "host": _os.uname().nodename,
                            "pid": _os.getpid(), "outcome": "completed",
                            "startedTs": self._started_iso, "durationMs": duration_ms,
                            **{k: v for k, v in self.measurement().items()
                               if k not in ("contextMeasurement",)}})
            self._started_iso = None


class Verification:
    """CPU owns results. A mismatch raises; unavailable GPU falls back LOUDLY."""
    def __init__(self, devices=(0,), ceiling_mib=DEFAULT_CEILING_MIB):
        if not devices or len(set(devices)) != len(devices) or len(devices) > 2:
            raise ValueError("choose one or two distinct GPU devices")
        self.backends = [Backend(d, ceiling_mib) for d in devices]
        self.executor = None
        self.objects = self.channels = self.threshold_flags = self.persistence_flags = 0
        self.disagreements = self.fallback_objects = 0
        self.corroboration_checks = self.inclination_abstentions = 0
        self.failures = []
        self.cpu_reference_seconds = 0.0
        self.max_z_error = 0.0

    def __enter__(self):
        available = []
        for backend in self.backends:
            try:
                backend.start()
                available.append(backend)
            except Exception as error:
                backend.close()
                self.fallback(f"device={backend.device}: {error}")
        self.backends = available
        self.executor = ThreadPoolExecutor(max_workers=max(1, len(available)))
        return self

    def fallback(self, reason):
        self.failures.append(str(reason))
        print(f"SWEEP GPU VERIFICATION UNAVAILABLE — EXPLICIT CPU FALLBACK: {reason}", file=sys.stderr, flush=True)

    def submit(self, intervals, kappa, *, epoch_slices=None):
        self.objects += 1
        if not self.backends:
            self.fallback_objects += 1
            return None
        backend = self.backends[(self.objects - 1) % len(self.backends)]
        options = {} if epoch_slices is None else {"epoch_slices": epoch_slices}
        return self.executor.submit(backend.analyze, intervals, kappa, **options)

    def resolve(self, future):
        if future is None:
            return None
        try:
            return future.result()
        except Exception as error:
            self.fallback_objects += 1
            self.fallback(error)
            return None

    def equal(self, a, b, label, *, approximate=False):
        if np.isscalar(a) and np.isscalar(b):
            okay = (math.isclose(a, b, rel_tol=Z_RTOL,
                                 abs_tol=Z_ATOL if label.endswith("z") else 0.0)
                    if approximate else a == b)
            okay = okay or (math.isnan(a) and math.isnan(b))
            if not approximate and a == 0 and b == 0:
                okay = math.copysign(1, a) == math.copysign(1, b)
        else:
            okay = np.allclose(a, b, rtol=Z_RTOL, atol=Z_ATOL if label.endswith("z") else 0.0,
                           equal_nan=True) if approximate else np.array_equal(a, b, equal_nan=True)
            if okay and not approximate:
                aa, bb = np.asarray(a), np.asarray(b)
                okay = np.array_equal(np.signbit(aa[aa == 0]), np.signbit(bb[bb == 0]))
        if not okay:
            self.disagreements += 1
            raise AgreementError(f"SWEEP GPU DISAGREEMENT {label}: CPU={a!r}, GPU={b!r}")

    def compare_baselines(self, result, baselines, floors, norad):
        if result is None:
            return
        actual = np.array([[[getattr(row[e], name) for name in
                            ("rate", "scale", "blocks", "samples", "within", "between")]
                           for e in result.elements] for row in baselines])
        self.equal(actual, result.baselines, f"{norad}: baselines")
        self.equal([floors[e] for e in result.elements], result.own_floor, f"{norad}: own floor")

    def compare_channels(self, result, tests, position, norad):
        if result is None:
            return
        by_element = {t.element: t for t in tests}
        for c, element in enumerate(result.elements):
            t = by_element.get(element)
            label = f"{norad}/{position}/{element}"
            self.equal(t is not None, result.valid[position, c], label + " measurable")
            if t is None:
                continue
            self.channels += 1
            self.equal(t.tripped, result.tripped[position, c], label + " threshold flag")
            self.threshold_flags += int(t.tripped)
            self.equal(t.delta, result.residual[position, c], label + " residual")
            self.equal(t.floor_sigma, result.sigma[position, c], label + " sigma", approximate=True)
            self.equal(t.floor_z, result.z[position, c], label + " z", approximate=True)
            self.max_z_error = max(self.max_z_error, abs(t.floor_z - result.z[position, c]))
            self.equal(np.nan if t.cohort_z is None else t.cohort_z,
                       result.self_z[position, c], label + " self z")

    def compare_persistence(self, result, position, element, persistent, norad):
        if result is not None:
            c = result.elements.index(element)
            self.equal(persistent, bool(result.persistent[position, c]),
                       f"{norad}/{position}/{element} persistence flag")
            self.persistence_flags += int(persistent)

    def compare_corroboration(self, result, position, uncorroborated, norad):
        if result is not None:
            self.equal(uncorroborated, bool(result.inclination_uncorroborated[position]),
                       f"{norad}/{position} inclination corroboration flag")
            self.corroboration_checks += 1
            self.inclination_abstentions += int(uncorroborated)

    def report(self):
        return dict(outcome="agreement" if not self.disagreements and not self.failures and self.channels else "unverified",
                    objects=self.objects, comparedChannels=self.channels, thresholdFlags=self.threshold_flags,
                    persistentFlags=self.persistence_flags, disagreements=self.disagreements,
                    corroborationChecks=self.corroboration_checks,
                    inclinationUncorroborated=self.inclination_abstentions,
                    fallbackObjects=self.fallback_objects, failures=self.failures,
                    maxAbsoluteZError=self.max_z_error, cpuReferenceSeconds=self.cpu_reference_seconds,
                    devices=[b.measurement() for b in self.backends])

    def __exit__(self, *exc):
        self.executor.shutdown(wait=True)
        for backend in self.backends:
            backend.close()


class Execution(Verification):
    """Use GPU arithmetic, or explicitly return None to request the CPU path.

    Shares device admission, private pools and object scheduling with verify.
    Never calls its comparison methods or claims verification agreement.
    """
    def fallback(self, reason):
        self.failures.append(str(reason))
        print(f"SWEEP GPU EXECUTION UNAVAILABLE — EXPLICIT CPU FALLBACK: {reason}",
              file=sys.stderr, flush=True)

    def analyze(self, intervals, kappa, *, epoch_slices=None):
        return self.resolve(self.submit(intervals, kappa, epoch_slices=epoch_slices))

    def report(self):
        completed = self.objects - self.fallback_objects
        return dict(mode="gpu-execution", outcome=("gpu" if completed and not self.failures
                    else "mixed" if completed else "cpu-fallback" if self.objects else "no-work"),
                    objects=self.objects, gpuObjects=completed, fallbackObjects=self.fallback_objects,
                    failures=self.failures, devices=[b.measurement() for b in self.backends])
