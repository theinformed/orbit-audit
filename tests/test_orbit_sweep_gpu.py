"""Offline wiring/failure controls plus opt-in real CUDA arithmetic fixtures."""
from dataclasses import asdict, replace
import contextlib
import io
import math
import os
import unittest
from unittest import mock

import numpy as np

from pipeline import orbit_campaigns as oc
from pipeline import orbit_sweep_gpu as gpu
from test_orbit_campaigns import series, intervals


def oracle(data, kappa):
    """CPU fixture backend only; exercises the verifier without requiring CUDA."""
    elements = oc.ELEMENTS
    blocks = {e: oc._blocks_for(data, e) for e in elements}
    bases = [{e: oc.baseline_at(blocks[e], i.mid_ms // int(oc.BLOCK_DAYS * 86400000))
              for e in elements} for i in data]
    import statistics
    perigee = statistics.median(i.perigee_altitude_km for i in data)
    floors = {e: oc._residual_floor(e, [abs(value - b[e].rate * i.span_days)
                                      for i, b in zip(data, bases)
                                      if (value := oc._observed(i, e)) is not None], perigee)
              for e in elements}
    tests = [[oc._self_channel(i, e, b[e], kappa=kappa * oc.NODE_CHANNEL_KAPPA_MULTIPLIER
                              if e == "raan" else kappa, own_floor=floors[e]) for e in elements]
             for i, b in zip(data, bases)]
    numeric = lambda field: np.array([[np.nan if t is None or getattr(t, field) is None
                                       else getattr(t, field) for t in row] for row in tests])
    persistence = np.array([[oc.step_persistence(data, bases, p, element=e)["persistent"]
                             for e in elements] for p in range(len(data))])
    uncorroborated = np.array([oc._inclination_uncorroborated(i, [
        replace(t, tripped=bool(t.tripped and persistence[p, c]))
        for c, t in enumerate(tests[p]) if t is not None]) for p, i in enumerate(data)])
    return gpu.Arithmetic(elements,
                          np.array([[[getattr(b[e], key) for key in
                                      ("rate", "scale", "blocks", "samples", "within", "between")]
                                     for e in elements] for b in bases]),
                          np.array([floors[e] for e in elements]),
                          numeric("delta"), numeric("floor_sigma"), numeric("floor_z"), numeric("cohort_z"),
                          np.array([[t is not None for t in row] for row in tests]),
                          np.array([[t is not None and t.tripped for t in row] for row in tests]),
                          persistence, uncorroborated)


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.data = intervals(series(steps={30: 1000}, spikes={60: 1000}))

    def test_default_never_imports_or_starts_cuda(self):
        with mock.patch.object(gpu, "load_cupy", side_effect=AssertionError("CUDA")):
            self.assertTrue(oc.detect_object_events(self.data))

    def test_unavailable_gpu_is_loud_cpu_fallback_not_agreement(self):
        expected = oc.detect_object_events(self.data)
        with mock.patch.object(gpu.Backend, "start", side_effect=RuntimeError("no card")), \
                contextlib.redirect_stderr(io.StringIO()) as log, gpu.Verification() as v:
            self.assertEqual(expected, oc.detect_object_events(self.data, gpu_verifier=v))
            self.assertEqual(v.report()["outcome"], "unverified")
            self.assertEqual(v.fallback_objects, 1)
        self.assertIn("EXPLICIT CPU FALLBACK", log.getvalue())

    def test_success_keeps_every_cpu_event_field(self):
        expected = oc.detect_object_events(self.data)
        with mock.patch.object(gpu.Backend, "start"), \
                mock.patch.object(gpu.Backend, "analyze", side_effect=oracle), gpu.Verification() as v:
            self.assertEqual([asdict(e) for e in expected],
                             [asdict(e) for e in oc.detect_object_events(self.data, gpu_verifier=v)])
            self.assertEqual(v.report()["outcome"], "agreement")
            self.assertGreater(v.threshold_flags, v.persistence_flags)
            self.assertGreater(v.persistence_flags, 0)

    def test_injected_threshold_flip_aborts_instead_of_falling_back(self):
        result = oracle(self.data, 8)
        result.tripped[0, 0] = ~result.tripped[0, 0]
        with mock.patch.object(gpu.Backend, "start"), \
                mock.patch.object(gpu.Backend, "analyze", return_value=result), gpu.Verification() as v:
            with self.assertRaisesRegex(gpu.AgreementError, "threshold flag"):
                oc.detect_object_events(self.data, gpu_verifier=v)
            self.assertEqual(v.fallback_objects, 0)

    def test_injected_persistence_flip_aborts(self):
        result = oracle(self.data, 8)
        p, c = np.argwhere(result.tripped)[0]
        result.persistent[p, c] = ~result.persistent[p, c]
        with mock.patch.object(gpu.Backend, "start"), \
                mock.patch.object(gpu.Backend, "analyze", return_value=result), gpu.Verification() as v:
            with self.assertRaisesRegex(gpu.AgreementError, "persistence flag"):
                oc.detect_object_events(self.data, gpu_verifier=v)

    def test_baseline_selection_has_zero_tolerance(self):
        v = gpu.Verification()
        with self.assertRaises(gpu.AgreementError):
            v.equal(1.0, math.nextafter(1.0, 2.0), "baseline")

    def test_signed_zero_selection_has_zero_tolerance(self):
        with self.assertRaises(gpu.AgreementError):
            gpu.Verification().equal(-0.0, 0.0, "median")

    def test_sweep_flag_wires_verifier_into_real_object_path(self):
        from test_orbit_parallel import ParallelSweepTests
        fixture = ParallelSweepTests()
        fixture.setUp()
        try:
            expected = oc.sweep_archive(fixture.db, workers=1, only=[1, 2])
            with mock.patch.object(gpu.Backend, "start"), \
                    mock.patch.object(gpu.Backend, "analyze", side_effect=oracle), \
                    contextlib.redirect_stderr(io.StringIO()) as log:
                actual = oc.sweep_archive(fixture.db, workers=12, only=[1, 2], gpu_verify_devices=(0, 1))
            self.assertEqual(asdict(expected.passed), asdict(actual.passed))
            self.assertIn('"outcome": "agreement"', log.getvalue())
        finally:
            fixture.doCleanups()

    def test_release_flag_is_forwarded(self):
        from pipeline import orbit_release
        import inspect
        # Exercise CLI parsing and forwarding without opening any real archive.
        self.assertIsNone(inspect.signature(orbit_release.build_cache).parameters["sweep_gpu_verify"].default)
        with mock.patch.object(orbit_release, "build_cache", return_value=(None, {})) as build, \
                mock.patch.object(oc, "open_archive_for_reading"), \
                contextlib.redirect_stdout(io.StringIO()):
            orbit_release.main(["--build-cache", "--sweep-gpu-verify", "0", "1", "--sweep-gpu-ceiling-mib", "512"])
        self.assertEqual(build.call_args.kwargs["sweep_gpu_verify"], (0, 1))
        self.assertEqual(build.call_args.kwargs["sweep_gpu_ceiling_mib"], 512)

    def test_release_rejects_unwired_or_invalid_gpu_flag_before_archive_access(self):
        from pipeline import orbit_release
        for args in (["--sweep-gpu-verify", "1"],
                     ["--build-cache", "--sweep-gpu-verify", "1", "1"],
                     ["--build-cache", "--sweep-gpu-verify", "1", "--sweep-gpu-ceiling-mib", "1400"]):
            with mock.patch.object(oc, "open_archive_for_reading", side_effect=AssertionError("archive accessed")), \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as result:
                orbit_release.main(args)
            self.assertEqual(result.exception.code, 2)

    def test_threshold_comparison_is_strict_at_kappa(self):
        i = self.data[0]
        b = oc.Baseline(0, 0, 3, 9)
        t = oc._self_channel(i, "semiMajorAxis", b, kappa=8)
        exact = abs(t.floor_z)
        self.assertFalse(oc._self_channel(i, "semiMajorAxis", b, kappa=exact).tripped)
        self.assertTrue(oc._self_channel(i, "semiMajorAxis", b, kappa=math.nextafter(exact, 0)).tripped)

    def test_two_cards_receive_disjoint_whole_objects(self):
        seen = {0: [], 1: []}
        def analyze(backend, data, kappa):
            seen[backend.device].append(data[0].norad)
            return oracle(data, kappa)
        with mock.patch.object(gpu.Backend, "start"), \
                mock.patch.object(gpu.Backend, "analyze", analyze), gpu.Verification((0, 1)) as v:
            for n in range(4):
                oc.detect_object_events([replace(i, norad=n) for i in self.data], gpu_verifier=v)
        self.assertEqual(seen, {0: [0, 2], 1: [1, 3]})

    def test_failed_object_is_explicitly_unverified(self):
        with mock.patch.object(gpu.Backend, "start"), \
                mock.patch.object(gpu.Backend, "analyze", side_effect=MemoryError("object too large")), \
                contextlib.redirect_stderr(io.StringIO()) as log, gpu.Verification() as v:
            self.assertTrue(oc.detect_object_events(self.data, gpu_verifier=v))
            self.assertEqual(v.fallback_objects, 1)
            self.assertEqual(v.report()["outcome"], "unverified")
        self.assertIn("object too large", log.getvalue())


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.data = intervals(series(steps={30: 1000}, spikes={60: 1000}))

    def test_gpu_result_used_without_cpu_arithmetic(self):
        expected = oc.detect_object_events(self.data)
        result = oracle(self.data, 8)
        with mock.patch.object(gpu.Backend, "start"), \
                mock.patch.object(gpu.Backend, "analyze", return_value=result), \
                mock.patch.object(oc, "baseline_at", side_effect=AssertionError("CPU baseline")), \
                mock.patch.object(oc, "_residual_floor", side_effect=AssertionError("CPU floor")), \
                mock.patch.object(oc, "_self_channel", side_effect=AssertionError("CPU channel")), \
                mock.patch.object(oc, "step_persistence", side_effect=AssertionError("CPU persistence")), \
                gpu.Execution() as executor:
            self.assertEqual(expected, oc.detect_object_events(self.data, gpu_executor=executor))
            self.assertEqual(executor.report()["outcome"], "gpu")
            # Change a GPU decision: the returned events must actually follow it.
            result.tripped[:] = False
            self.assertFalse(oc.detect_object_events(self.data, gpu_executor=executor))

    def test_every_failure_is_loud_and_returns_cpu_results(self):
        expected = oc.detect_object_events(self.data)
        for method, error in (("start", RuntimeError("CUDA unavailable")),
                              ("start", RuntimeError("device busy")),
                              ("analyze", gpu.VramBudgetError("private ceiling")),
                              ("analyze", MemoryError("allocation failed"))):
            with self.subTest(method=method, error=error), \
                    mock.patch.object(gpu.Backend, "start"), \
                    mock.patch.object(gpu.Backend, method, side_effect=error), \
                    contextlib.redirect_stderr(io.StringIO()) as log, gpu.Execution() as executor:
                self.assertEqual(expected, oc.detect_object_events(self.data, gpu_executor=executor))
                self.assertEqual(executor.report()["outcome"], "cpu-fallback")
                self.assertEqual(executor.report()["gpuObjects"], 0)
                self.assertEqual(executor.fallback_objects, 1)
            self.assertIn("EXPLICIT CPU FALLBACK", log.getvalue())
            self.assertIn(str(error), log.getvalue())

    def test_sweep_executes_gpu_and_preserves_accumulator(self):
        from test_orbit_parallel import ParallelSweepTests
        fixture = ParallelSweepTests()
        fixture.setUp()
        try:
            expected = oc.sweep_archive(fixture.db, workers=1, only=[1, 2])
            with mock.patch.object(gpu.Backend, "start"), \
                    mock.patch.object(gpu.Backend, "analyze", side_effect=oracle), \
                    contextlib.redirect_stderr(io.StringIO()) as log:
                actual = oc.sweep_archive(fixture.db, workers=12, only=[1, 2], gpu_devices=(0, 1))
            self.assertEqual(asdict(expected.passed), asdict(actual.passed))
            self.assertIn('"outcome": "gpu"', log.getvalue())
        finally:
            fixture.doCleanups()

    def test_release_flag_and_default(self):
        from pipeline import orbit_release
        import inspect
        self.assertIsNone(inspect.signature(orbit_release.build_cache).parameters["sweep_gpu"].default)
        with mock.patch.object(orbit_release, "build_cache", return_value=(None, {})) as build, \
                mock.patch.object(oc, "open_archive_for_reading"), \
                contextlib.redirect_stdout(io.StringIO()):
            orbit_release.main(["--build-cache", "--sweep-gpu", "1", "--sweep-gpu-ceiling-mib", "512"])
        self.assertEqual(build.call_args.kwargs["sweep_gpu"], (1,))
        self.assertIsNone(build.call_args.kwargs["sweep_gpu_verify"])

    def test_build_cache_forwards_execution_without_publication(self):
        from pipeline import orbit_release as release
        from pathlib import Path
        from test_orbit_parallel import ParallelSweepTests
        fixture = ParallelSweepTests()
        fixture.setUp()
        try:
            with mock.patch.object(release, "load_catalog", return_value=fixture.catalog), \
                    mock.patch.object(release, "_read_sweep_state", return_value=None), \
                    mock.patch.object(release, "_seconds_until_sweep_due", return_value=0), \
                    mock.patch.object(release, "_write_sweep_state"), \
                    mock.patch.object(oc, "sweep_archive", return_value=
                                      oc.SweepProgress(oc.ArchivePass(), 8, 8, 1)) as sweep:
                fragment, report = release.build_cache(Path(fixture.directory.name),
                    write_artifact=mock.Mock(side_effect=AssertionError("publication")),
                    connection=fixture.db, sweep_gpu=(1,), sweep_gpu_ceiling_mib=512)
            self.assertIsNone(fragment)
            self.assertFalse(report["published"])
            self.assertEqual(sweep.call_args.kwargs["gpu_devices"], (1,))
            self.assertEqual(sweep.call_args.kwargs["gpu_ceiling_mib"], 512)
        finally:
            fixture.doCleanups()

    def test_mutual_exclusion_and_invalid_devices_before_io(self):
        from pipeline import orbit_release
        for args in (["--build-cache", "--sweep-gpu", "1", "--sweep-gpu-verify", "0"],
                     ["--sweep-gpu", "1"], ["--build-cache", "--sweep-gpu", "-1"],
                     ["--build-cache", "--sweep-gpu", "1", "1"],
                     ["--build-cache", "--sweep-gpu", "0", "--sweep-gpu-ceiling-mib", "1400"]):
            with mock.patch.object(oc, "open_archive_for_reading", side_effect=AssertionError("I/O")), \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                orbit_release.main(args)
            self.assertEqual(error.exception.code, 2)
        with self.assertRaises(ValueError):
            oc.detect_object_events([], gpu_executor=object(), gpu_verifier=object())
        with self.assertRaises(ValueError):
            oc.sweep_archive(None, gpu_devices=(1,), gpu_verify_devices=(0,))
        with self.assertRaises(ValueError):
            orbit_release.build_cache(None, write_artifact=None, sweep_gpu=(1,), sweep_gpu_verify=(0,))


class BudgetTests(unittest.TestCase):
    def test_ceiling_is_below_decimal_1_point_4_gb(self):
        self.assertLessEqual(gpu.DEFAULT_CEILING_MIB * gpu.MIB, 1.4e9)
        for ceiling in (319, 1336, 1430):
            with self.assertRaises(ValueError):
                gpu.Backend(0, ceiling)

    def test_own_pool_enforced_without_device_wide_probe(self):
        backend = gpu.Backend(0, 320)
        backend.pool = mock.Mock()
        backend.pool.total_bytes.return_value = 65 * gpu.MIB
        with mock.patch.object(gpu, "smi_memory", side_effect=AssertionError("device probe")):
            with self.assertRaises(gpu.VramBudgetError):
                backend._allocate(1)
        backend.pool.total_bytes.return_value = gpu.MIB
        backend.pool_peak = 0
        backend._allocate(1)

    def test_telemetry_failure_is_gap_and_start_continues(self):
        cp = mock.MagicMock()
        with mock.patch.object(gpu, "smi_memory", side_effect=TimeoutError("fixture retries exhausted")), \
                mock.patch.object(gpu, "load_cupy", return_value=cp), \
                contextlib.redirect_stderr(io.StringIO()) as log:
            b = gpu.Backend(0, 512).start()
        self.assertTrue(b.telemetry_gaps)
        self.assertIsNotNone(b.pool)
        self.assertIn("TELEMETRY GAP", log.getvalue())


class PopulationTests(unittest.TestCase):
    def test_only_cannot_drop_missing_or_unusable_controls(self):
        from tools.verify_orbit_sweep_gpu import select
        from types import SimpleNamespace
        import sqlite3
        db = sqlite3.connect(":memory:")
        self.addCleanup(db.close)
        db.executescript("CREATE TABLE object(norad,name,object_type); "
                         "CREATE TABLE element_set(norad,epoch_ms,mean_motion_q);")
        db.execute("INSERT INTO object VALUES(1,'SPARSE','DEBRIS')")
        db.executemany("INSERT INTO element_set VALUES(1,?,100000000)",
                       [(j * 4 * 86400000,) for j in range(20)])
        args = SimpleNamespace(only=[1], start=0, end=100 * 86400000, min_rows=9,
                               max_rows=1000, objects=1, seed=42)
        with self.assertRaisesRegex(ValueError, "cannot shrink"):
            select(db, args)
        args.only = [2]
        with self.assertRaisesRegex(ValueError, "cannot shrink"):
            select(db, args)

    def test_auto_selection_requires_entire_requested_population(self):
        from tools.verify_orbit_sweep_gpu import select
        from types import SimpleNamespace
        import sqlite3
        db = sqlite3.connect(":memory:")
        self.addCleanup(db.close)
        db.executescript("CREATE TABLE object(norad,name,object_type); "
                         "CREATE TABLE element_set(norad,epoch_ms,mean_motion_q);")
        args = SimpleNamespace(only=None, start=0, end=100, min_rows=9,
                               max_rows=1000, objects=2, seed=42)
        with self.assertRaisesRegex(ValueError, "!= requested 2"):
            select(db, args)


@unittest.skipUnless(os.environ.get("ORBIT_SWEEP_GPU_TEST") == "1", "opt-in CUDA sweep fixtures")
class GpuTests(unittest.TestCase):
    def test_execution_real_events_and_no_cpu_arithmetic(self):
        data = intervals(series(steps={30: 1000}, spikes={60: 1000}))
        expected = oc.detect_object_events(data)
        with gpu.Execution((int(os.environ.get("ORBIT_SWEEP_GPU_DEVICE", "1")),), 320) as executor, \
                mock.patch.object(oc, "_self_channel", side_effect=AssertionError("CPU channel")), \
                mock.patch.object(oc, "baseline_at", side_effect=AssertionError("CPU baseline")), \
                mock.patch.object(oc, "step_persistence", side_effect=AssertionError("CPU persistence")):
            actual = oc.detect_object_events(data, gpu_executor=executor)
            self.assertEqual(executor.report()["outcome"], "gpu")
        self.assertEqual(expected, actual)

    def test_real_kernels_all_channels_and_detector_switches(self):
        base = intervals(series(steps={30: 1000}, spikes={60: 1000}))
        rng = np.random.default_rng(42)
        data = [replace(i, delta_raan_deg=0.01 + float(rng.normal(0, 0.002)),
                        delta_arg_perigee_deg=0.0, delta_e=float(rng.normal(0, 1e-6)),
                        delta_i_deg=float(rng.choice([0, 0.0001, -0.0001]))) for i in base]
        # Sparse missing measurements, gaps, even/odd ties, negative epochs, degenerate node.
        data = [replace(i, delta_raan_deg=None) if p % 19 == 0 else i for p, i in enumerate(data)]
        variants = [data, data[:10], data[:100] + data[130:],
                    [replace(i, inclination_deg=0.0) for i in data],
                    [replace(i, start_ms=i.start_ms-2_000_000_000_000,
                             end_ms=i.end_ms-2_000_000_000_000) for i in data]]
        with mock.patch.object(oc, "ELEMENTS", ("semiMajorAxis", "inclination", "eccentricity", "raan")), \
                mock.patch.object(oc, "INCLINATION_FLOOR_TAIL_AWARE", True), \
                gpu.Verification((int(os.environ.get("ORBIT_SWEEP_GPU_DEVICE", "1")),), 320) as v:
            for data in variants:
                expected = oc.detect_object_events(data)
                actual = oc.detect_object_events(data, gpu_verifier=v)
                self.assertEqual(expected, actual)
            self.assertEqual(v.report()["outcome"], "agreement")
            self.assertGreater(v.threshold_flags, 0)
            self.assertGreater(v.persistence_flags, 0)

    def test_even_odd_selection_and_signed_ties(self):
        b = gpu.Backend(int(os.environ.get("ORBIT_SWEEP_GPU_DEVICE", "1")), 320).start()
        import statistics
        try:
            with b.cp.cuda.Device(b.device), b.cp.cuda.using_allocator(b._allocate):
                for values in ([1, 3, 3, 8], [-0.0, 0.0, 1.0], [-8, -3, -3, 1, 8]):
                    actual = float(gpu.median(b.cp.asarray(values, dtype=float), b.cp))
                    expected = statistics.median(values)
                    self.assertEqual(actual, expected)
                    self.assertEqual(math.copysign(1, actual), math.copysign(1, expected))
        finally:
            b.close()


if __name__ == "__main__":
    unittest.main()
