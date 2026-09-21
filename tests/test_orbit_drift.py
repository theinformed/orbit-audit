"""Offline regression tests. Real CUDA fits require ORBIT_DRIFT_GPU_TEST=1."""
import contextlib
from dataclasses import replace
import io
import json
import math
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock

import numpy as np

from pipeline import orbit_drift as drift
from pipeline import orbit_drift_gpu as gpu
from pipeline import orbit_history as history


IN_GATE = {"inGate": True, "regime": "drag regime"}


def fixture(objects=20, days=120):
    db = sqlite3.connect(":memory:")
    db.executescript("""
        CREATE TABLE object(norad INTEGER PRIMARY KEY, object_type TEXT);
        CREATE TABLE element_set(norad INTEGER,epoch_ms INTEGER,mean_motion_q INTEGER,
          eccentricity_q INTEGER,inclination_q INTEGER,bstar_q INTEGER,PRIMARY KEY(norad,epoch_ms)) WITHOUT ROWID;
    """)
    for norad in range(1, objects + 1):
        db.execute("INSERT INTO object VALUES (?,?)", (norad, "PAYLOAD" if norad == objects else "DEBRIS"))
        bstar = float(np.geomspace(1e-6, 4e-4, objects)[(norad * 7 + objects // 2) % objects])
        for day in range(days):
            # Atmospheric trend shared by the entire cohort, with gentle curvature.
            axis = 6800 - 100 * bstar * (day + .0005 * day**2)
            if norad == objects:
                axis += .05 * max(0, day - 60)  # injected sustained drift
            for fit in range(3):
                # A single awful fit every ninth day must be rejected by the daily median.
                a = axis + (5 if fit == 2 and day % 9 == 0 else 0)
                mm = math.sqrt(history.MU_WGS72 / a**3) * 86400 / (2 * math.pi)
                db.execute("INSERT INTO element_set VALUES (?,?,?,?,?,?)", (
                    norad, day * drift.DAY_MS + fit * 1000, round(mm * 1e8), 100000, 510000, round(bstar * history.SCALE_BSTAR)))
    return db


def execute(db, chunk=4, cfg=None, **kwargs):
    output = io.StringIO()
    metrics = drift.run(db, output, cfg or drift.Config(0, 120, split_day=60), chunk_size=chunk, **kwargs)
    return output.getvalue(), metrics


class DriftTests(unittest.TestCase):
    def setUp(self):
        self.db = fixture()
        self.addCleanup(self.db.close)

    def test_byte_identical_runs_and_chunks(self):
        first, _ = execute(self.db, 1)
        for chunk in (1, 3, 20, 32):
            self.assertEqual(first.encode(), execute(self.db, chunk)[0].encode())

    def test_detects_injected_drift_not_pure_drag_and_measures_controls(self):
        raw, _ = execute(self.db)
        rows = [json.loads(x) for x in raw.splitlines()]
        objects = [r for r in rows if r["kind"] == "object"]
        for obj in objects[:-1]:
            self.assertFalse(any(c["flag"] for c in obj["channels"]), obj)
        self.assertTrue(objects[-1]["channels"][0]["flag"])
        self.assertGreater(objects[-1]["channels"][0]["departureLowerBound"], 1)
        controls = rows[-1]
        self.assertEqual(controls["passive"]["flags"], 0)
        self.assertEqual(controls["passive"]["objects"], 19)  # in-gate test fits only
        self.assertEqual(controls["payload"]["flags"], 1)
        self.assertGreater(controls["passive"]["jeffreys95"][1], 0)
        self.assertFalse(controls["sufficientToLabel"])
        self.assertTrue(objects[-1]["geometry"]["inGate"])

    def test_object_segmentation_and_fit_padding(self):
        a = drift.Blocks(42, "DEBRIS", np.arange(120.),
                         np.column_stack([np.arange(120.) * 2, np.zeros(120), np.ones(120)]), (0, 0), 120)
        b = drift.Blocks(77, "PAYLOAD", np.arange(73.),
                         np.column_stack([1e6 - np.arange(73.) * 37, np.ones(73), np.zeros(73)]), (0, 0), 73)
        together = drift.fit_cpu([a, b], 4000)
        np.testing.assert_array_equal(together[0], drift.fit_cpu([a], 4000)[0])
        np.testing.assert_array_equal(together[1], drift.fit_cpu([b], 4000)[0])
        self.assertEqual(together[0, 0, 0], 2)
        self.assertEqual(together[1, 0, 0], -37)

    def test_daily_reduction_crosses_pages_without_bleeding(self):
        a = drift.daily_blocks(self.db, 1, replace(drift.Config(0, 120), page_rows=2))
        b = drift.daily_blocks(self.db, 1, drift.Config(0, 120))
        self.assertEqual(a.raw_rows, 360)
        np.testing.assert_array_equal(a.values, b.values)
        self.assertAlmostEqual(a.values[0, 0], 6800, places=5)
        self.assertEqual(len(a.days), 120)

    def test_no_cohort_required_but_restricted_acceptance_labelled(self):
        rows = [json.loads(x) for x in execute(self.db, only=[1, 20])[0].splitlines()]
        self.assertFalse(rows[1]["channels"][0]["flag"])
        self.assertTrue(rows[2]["channels"][0]["flag"])
        self.assertEqual(rows[-1]["passive"]["objects"], 1)
        self.assertEqual(rows[-1]["objectsWithGap"], 0)
        self.assertIn("restricted population", rows[-1]["acceptance"])

    def test_short_coverage_excluded_from_control(self):
        self.db.execute("DELETE FROM element_set WHERE norad=1 AND epoch_ms>=?", (70 * drift.DAY_MS,))
        rows = [json.loads(x) for x in execute(self.db)[0].splitlines()]
        self.assertIn("coverage", rows[1]["channels"][0]["gap"])
        self.assertIsNone(rows[1]["channels"][0]["flag"])
        self.assertEqual(rows[-1]["passive"]["objects"], 18)

    def test_bands_are_diagnostics_and_never_gate_flags(self):
        self.db.execute("UPDATE element_set SET inclination_q=700000 WHERE norad=20")
        rows = [json.loads(x) for x in execute(self.db)[0].splitlines()]
        self.assertTrue(rows[-2]["channels"][0]["flag"])
        self.assertNotEqual(rows[1]["band"], rows[-2]["band"])

    def test_sampling_is_per_norad_bounded_and_nondegenerate(self):
        a, b = drift.pair_indices(17, 3660, 4000)
        self.assertEqual(len(a), 4000)
        self.assertTrue(np.all(a < b))
        np.testing.assert_array_equal(a, drift.pair_indices(17, 3660, 4000)[0])
        self.assertFalse(np.array_equal(a, drift.pair_indices(18, 3660, 4000)[0]))
        a, b = drift.pair_indices(1, 5, 4000)
        self.assertEqual(len(set(zip(a, b))), 10)

    def test_raw_row_budget_fails_visibly(self):
        with self.assertRaisesRegex(ValueError, "budget"):
            drift.daily_blocks(self.db, 1, replace(drift.Config(0, 120), max_fits_per_day=2))

    def test_window_is_half_open(self):
        blocks = drift.daily_blocks(self.db, 1, drift.Config(10, 90))
        self.assertEqual((blocks.days[0], blocks.days[-1]), (10, 89))

    def test_two_device_dispatch_preserves_control_population_and_bytes(self):
        class OracleBackend:
            def __init__(self, device):
                self.device, self.seen = device, []
            def fit(self, objects, pairs):
                self.seen.extend(o.norad for o in objects)
                return drift.fit_cpu(objects, pairs)
        backends = [OracleBackend(0), OracleBackend(1)]
        expected = execute(self.db)[0]
        actual = execute(self.db, backends=backends)[0]
        self.assertEqual(expected.encode(), actual.encode())
        self.assertTrue(all(b.seen for b in backends))
        self.assertFalse(set(backends[0].seen) & set(backends[1].seen))
        self.assertEqual(sorted(backends[0].seen + backends[1].seen), sorted(list(range(1, 21)) * 2))

    def test_private_scratch_removed_after_failure(self):
        class BrokenOutput:
            def write(self, value):
                raise OSError("fixture")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(OSError):
                drift.run(self.db, BrokenOutput(), drift.Config(0, 120, split_day=60), scratch_dir=directory)
            self.assertEqual(list(Path(directory).iterdir()), [])


class BudgetTests(unittest.TestCase):
    def test_wsl_admission_uses_lower_free_measurement(self):
        for cuda_free, smi_free in ((15000, 700), (700, 15000)):
            cp = mock.MagicMock()
            cp.cuda.runtime.memGetInfo.return_value = (cuda_free * gpu.MIB, 16376 * gpu.MIB)
            instance = gpu.GpuBackend(0, gpu.DEFAULT_CEILING_MIB)
            with mock.patch.object(gpu, "load_cupy", return_value=cp), \
                    mock.patch.object(gpu, "smi_memory", return_value=(100 * gpu.MIB, smi_free * gpu.MIB)), \
                    mock.patch.object(gpu.threading, "Thread"):
                instance.start()
            cp.cuda.MemoryPool.return_value.set_limit.assert_called_once_with(size=636 * gpu.MIB)

    def test_smoke_dry_run_cannot_initialize_cuda(self):
        with mock.patch.object(gpu, "load_cupy", side_effect=AssertionError("CUDA accessed")), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(drift.main(["--smoke", "--dry-run"]), 0)
        self.assertFalse(json.loads(output.getvalue())["cudaAccess"])

    def test_registry_declares_real_gpu_resource_and_existing_callers(self):
        root = Path(__file__).resolve().parents[1]
        row = json.loads((root / "ops/orbit-drift-gpu-consumer.json").read_text())
        self.assertEqual(row["resource"], ["gpu-direct"])
        self.assertEqual(row["invocation"], "on-demand")
        self.assertEqual(row["usageLedger"]["kind"], "bigmem-local")
        import re
        for evidence in row["callerEvidence"]:
            path = root / evidence["target"].split("space-teaching-aid/", 1)[1]
            self.assertRegex(path.read_text(), re.compile(evidence["pattern"]))

    def test_shrink_retries_without_altering_objects(self):
        attempts = []
        def attempt(objects):
            attempts.append(len(objects))
            if len(objects) > 2:
                raise gpu.VramBudgetError("fixture ceiling")
            return np.array(objects)
        release = mock.Mock()
        result = gpu.fit_with_shrinking(list(range(9)), attempt, release, (gpu.VramBudgetError,))
        np.testing.assert_array_equal(result, np.arange(9))
        self.assertGreater(release.call_count, 0)
        self.assertIn(2, attempts)

    def test_single_object_oom_is_not_silently_cpu(self):
        with self.assertRaises(gpu.VramBudgetError):
            gpu.fit_with_shrinking([1], mock.Mock(side_effect=gpu.VramBudgetError()),
                                    mock.Mock(), (gpu.VramBudgetError,))

    def test_ceiling_cannot_exceed_one_point_four_decimal_gb(self):
        self.assertLess(gpu.DEFAULT_CEILING_MIB * gpu.MIB, 1.4e9)
        with self.assertRaises(ValueError):
            gpu.GpuBackend(0, 1536)

    def test_runtime_telemetry_failure_is_labelled_gap(self):
        backend = gpu.GpuBackend()
        backend.pool = mock.MagicMock()
        backend.cp = mock.MagicMock()
        backend.context_bytes = 240 * gpu.MIB
        backend.pool_peak = 12 * gpu.MIB
        with mock.patch.object(backend, 'sample', side_effect=TimeoutError('fixture telemetry')):
            backend.check()
        self.assertTrue(backend.measurement()['telemetryGap'])
        self.assertIn('fixture telemetry', backend.measurement()['telemetryError'])
        self.assertEqual(backend.measurement()['inProcessPeakBytes'], 252 * gpu.MIB)

    def test_nvrtc_preloaded_in_process_and_no_disk_kernel_cache(self):
        fake_cupy = mock.MagicMock()
        with mock.patch.object(gpu.Path, 'exists', return_value=True), \
                mock.patch.object(gpu.ctypes, 'CDLL') as loader, \
                mock.patch.dict('sys.modules', cupy=fake_cupy), mock.patch.dict(os.environ):
            self.assertIs(gpu.load_cupy(), fake_cupy)
            self.assertEqual(os.environ['CUPY_CACHE_IN_MEMORY'], '1')
        self.assertEqual([Path(call.args[0]).name for call in loader.call_args_list],
                         ['libcudart.so.13', 'libnvrtc.so.13'])
        self.assertTrue(all(call.kwargs['mode'] == gpu.ctypes.RTLD_GLOBAL for call in loader.call_args_list))

    def test_failed_gpu_start_has_timed_receipt(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(os.environ, SPACE_GPU_USAGE_DIR=directory):
            with mock.patch.object(gpu.GpuBackend, "start", side_effect=RuntimeError("device unavailable")):
                with self.assertRaisesRegex(RuntimeError, "unavailable"):
                    with gpu.gpu_session(0):
                        self.fail("must not run")
            receipt = json.loads((Path(directory) / f"{gpu.LANE}-usage.jsonl").read_text().splitlines()[-1])
            self.assertFalse(receipt["ok"])
            self.assertIn("ts", receipt)
            self.assertIn("durationMs", receipt)
            self.assertEqual(receipt["resource"], "gpu-direct")

    def test_ledger_retains_bounded_newest_rows(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(os.environ, SPACE_GPU_USAGE_DIR=directory):
            path = Path(directory) / f"{gpu.LANE}-usage.jsonl"
            path.write_text('"old"\n' * 5000)
            gpu.write_receipt({"new": True})
            rows = path.read_text().splitlines()
            self.assertEqual(len(rows), 4096)
            self.assertEqual(json.loads(rows[-1]), {"new": True})


@unittest.skipUnless(os.environ.get("ORBIT_DRIFT_GPU_TEST") == "1",
                     "CUDA fit authorization required; allocation smoke is separate")
class GpuParityTests(unittest.TestCase):
    def test_gpu_equals_cpu_fixture_and_gpu_chunks(self):
        # Float64 tolerance: rtol 1e-10, atol 1e-10 in each element's native units.
        with contextlib.closing(fixture()) as db, gpu.gpu_session(int(os.environ.get("ORBIT_DRIFT_GPU_DEVICE", "0")), 512) as backend:
            objects = [drift.daily_blocks(db, n, drift.Config(0, 120)) for n in (1, 7, 20)]
            cpu = drift.fit_cpu(objects, 4000)
            actual = backend.fit(objects, 4000)
            np.testing.assert_allclose(actual, cpu, rtol=1e-10, atol=1e-10)
            single = np.concatenate([backend.fit([o], 4000) for o in objects])
            np.testing.assert_array_equal(actual, single)
            self.assertLessEqual(backend.measurement()["inProcessPeakBytes"], backend.ceiling)
            # Exercise both five-day windows and the complete v4 control output.
            expected = execute(db, chunk=3)[0]
            self.assertEqual(expected, execute(db, chunk=3, backends=[backend])[0])
            self.assertEqual(expected, execute(db, chunk=20, backends=[backend])[0])
            # Variable one/two-window batches must also match on real CUDA.
            db.execute('DELETE FROM element_set WHERE norad=20 AND epoch_ms<60*86400000')
            db.execute('DELETE FROM element_set WHERE norad=1 AND epoch_ms>=60*86400000')
            expected = execute(db, chunk=1)[0]
            self.assertEqual(expected, execute(db, chunk=7, backends=[backend])[0])
            self.assertLessEqual(backend.measurement()["inProcessPeakBytes"], backend.ceiling)



def atmosphere_fixture(inject=False, cadence=1, missing=False):
    db = sqlite3.connect(':memory:')
    db.executescript('CREATE TABLE object(norad INTEGER PRIMARY KEY,object_type TEXT); CREATE TABLE element_set(norad INTEGER,epoch_ms INTEGER,mean_motion_q INTEGER,eccentricity_q INTEGER,inclination_q INTEGER,bstar_q INTEGER,PRIMARY KEY(norad,epoch_ms)) WITHOUT ROWID;')
    for n in range(1, 41):
        b = np.geomspace(1e-6, 1e-3, 40)[(n * 17) % 40]
        db.execute('INSERT INTO object VALUES (?,?)', (n, 'PAYLOAD' if n % 2 else 'DEBRIS'))
        for day in range(0, 120, cadence):
            # Thrust exceeds the strongest drag: the injection must RAISE, not merely slow decay.
            axis = 6800 - 100 * b * (min(day, 60) + 1.4 * max(0, day - 60)) + (0.2 * max(0, day-60) if inject and n == 21 else 0)
            for fit in range(3):
                a = axis + (5 if fit == 2 and day % 9 == 0 else 0)
                mm = math.sqrt(history.MU_WGS72/a**3)*86400/(2*math.pi)
                db.execute('INSERT INTO element_set VALUES (?,?,?,?,?,?)',(n, day*drift.DAY_MS+fit*1000,round(mm*1e8),100000,510000,None if missing else round(b*history.SCALE_BSTAR)))
    return db

class SelfTrailingTests(unittest.TestCase):
    def test_varied_drag_only_population_no_flags(self):
        with contextlib.closing(atmosphere_fixture()) as db:
            raw, metrics=execute(db)
            rows=[json.loads(r) for r in raw.splitlines()]
            self.assertEqual(metrics['fittedObjects'],40)
            controlled=[r['channels'][0] for r in rows[1:-1] if r['channels'][0]['flag'] is not None]
            self.assertGreaterEqual(len(controlled),36)
            self.assertTrue(all(c['flag'] is False for c in controlled))
            self.assertTrue(all(c['z'] < 0 for c in controlled))
            self.assertTrue(all('predictedSlopePerDay' not in c for c in controlled))
            self.assertTrue(all(r['channels'][1]['flag'] is None for r in rows[1:-1]))
    def test_injected_and_chunk_determinism(self):
        with contextlib.closing(atmosphere_fixture(inject=True)) as db:
            raw,_=execute(db,chunk=3)
            self.assertEqual(raw, execute(db,chunk=32)[0])
            rows=[json.loads(r) for r in raw.splitlines()]
            self.assertTrue(next(r for r in rows[1:-1] if r['norad']==21)['channels'][0]['flag'])
            self.assertEqual(rows[-1]['passive']['flags'],0)
            self.assertEqual(rows[-1]['payload']['flags'],1)
    def test_sparse_cadence_gets_fit(self):
        with contextlib.closing(atmosphere_fixture(cadence=4)) as db:
            raw,metrics=execute(db)
            self.assertEqual(metrics['fittedObjects'],40)
            row=json.loads(raw.splitlines()[1])
            self.assertEqual(row['blockCount'],24)
            self.assertEqual(row['occupiedDayCount'],30)
    def test_missing_and_garbage_bstar_have_no_effect(self):
        with contextlib.closing(atmosphere_fixture()) as db:
            expected = execute(db)[0]
            db.execute('UPDATE element_set SET bstar_q=NULL')
            self.assertEqual(expected, execute(db)[0])
            db.execute("UPDATE element_set SET bstar_q=CASE WHEN norad%2=0 THEN 999999999999 ELSE 'garbage' END")
            self.assertEqual(expected, execute(db)[0])
            db.execute('ALTER TABLE element_set DROP COLUMN bstar_q')
            self.assertEqual(expected, execute(db)[0])

    def test_trailing_absence_and_preexisting_raising_do_not_suppress(self):
        with contextlib.closing(atmosphere_fixture(inject=True)) as db:
            db.execute('DELETE FROM element_set WHERE norad=21 AND epoch_ms<60*86400000')
            rows = [json.loads(x) for x in execute(db)[0].splitlines()]
            obj = next(r for r in rows[1:-1] if r['norad'] == 21)
            self.assertTrue(obj['channels'][0]['flag'])
            self.assertIsNone(obj['channels'][0]['windows']['trailing'])
            self.assertIsNotNone(obj['trailingGap'])
            self.assertEqual(rows[-1]['payload']['flags'], 1)
        cfg = drift.Config(0, 366)
        for trailing in (None, [.02, 0, .0001, 240], [-1, 100, 1, 240]):
            score = drift.score_axis([trailing, [.02, 0, .0001, 115]], IN_GATE, cfg)
            self.assertTrue(score['flag'])

    def test_shutdown_telemetry_gap(self):
        backend=gpu.GpuBackend()
        backend.cp=mock.MagicMock()
        with mock.patch.object(backend,'sample',side_effect=TimeoutError('probe')):
            backend.close()
        self.assertTrue(backend.measurement()['telemetryGap'])
    def test_inprocess_ceiling_ignores_device_growth(self):
        b=gpu.GpuBackend()
        b.context_bytes=240*gpu.MIB
        b.pool_peak=32*gpu.MIB
        b.observed_peak=8*1024**3
        b.monitor_error='probe'
        b.check()
        self.assertEqual(b.measurement()['inProcessPeakBytes'],272*gpu.MIB)
        b.pool_peak=b.ceiling
        with self.assertRaises(gpu.VramBudgetError):
            b.check()




class V4SyntheticTests(unittest.TestCase):
    def test_drag_slowdown_raising_and_negative_labels(self):
        cfg = drift.Config(0, 366)
        for test, positive, negative in ((-.14, False, True), (-.04, False, True),
                                         (.02, True, False), (-.3, False, True)):
            score = drift.score_axis([[-.1, 0, .0001, 240], [test, 0, .0001, 115]], IN_GATE, cfg)
            self.assertEqual(score['flag'], positive)
            self.assertEqual(score['negativeSide'], negative)
        self.assertIn('diagnostic only', score['label'])

    def test_out_of_gate_sustained_raising_recorded_never_flagged(self):
        cfg = drift.Config(0, 366)
        for perigee, ecc, label in ((1000, .01, 'SRP-regime rise'),
                                    (35786, .001, 'GEO libration'), (1500, .4, 'HEO lunisolar')):
            obj = drift.Blocks(1, 'DEBRIS', np.array([300.]), np.zeros((1, 3)), (0, 0), 1,
                               geometry=np.array([[perigee, ecc]]))
            geometry = drift.regime_geometry(obj, cfg)
            score = drift.score_axis([None, [.02, 0, .0001, 115]], geometry, cfg)
            self.assertFalse(score['flag'])
            self.assertTrue(score['outOfGateRaising'])
            self.assertEqual(score['label'], label)
            self.assertTrue(score['reportable'])

    def test_scale_is_own_test_scatter_with_quantisation_floor(self):
        cfg = drift.Config(0, 366)
        for scatter, scale in ((0, .001 / 115), (.01, .01 / 115)):
            test = [.001, scatter, scale, 115]
            a = drift.score_axis([[-1, 999, 99, 240], test], IN_GATE, cfg)
            b = drift.score_axis([None, test], IN_GATE, cfg)
            self.assertEqual(a['comparisonScalePerDay'], scale)
            self.assertEqual(a['z'], b['z'])
            self.assertEqual(a['z'], test[0] / scale)
        edge = drift.score_axis([None, [5 * .001 / 100, 0, .00001, 100]], IN_GATE, cfg)
        self.assertTrue(edge['flag'])

    def test_split_precedes_block_reduction_and_coverage_checks_both_windows(self):
        cfg = drift.Config(0, 120, split_day=63)
        obj = drift.Blocks(12, 'DEBRIS', np.arange(120.),
                           np.column_stack([np.arange(120.), np.zeros((120, 2))]), (1, 1), 120)
        trailing = drift.temporal_blocks(obj, cfg, 0, 63)
        test = drift.temporal_blocks(obj, cfg, 63, 120)
        self.assertLess(trailing.days[-1], 63)
        self.assertGreaterEqual(test.days[0], 63)
        self.assertEqual(trailing.occupied_days + test.occupied_days, 120)
        self.assertEqual(drift.Config(19723, 20089).split_day, 19967)  # 2024-09-01
        with self.assertRaises(ValueError):
            drift.Config(0, 120, split_day=120)

    def test_other_objects_cannot_change_score_and_other_elements_cannot_flag(self):
        with contextlib.closing(atmosphere_fixture(inject=True)) as db:
            db.execute('UPDATE element_set SET inclination_q=inclination_q+epoch_ms/86400000, '
                       'eccentricity_q=eccentricity_q+epoch_ms/86400000 WHERE norad=21')
            before = next(json.loads(r)['channels'] for r in execute(db)[0].splitlines()
                          if json.loads(r).get('norad') == 21)
            db.execute('DELETE FROM element_set WHERE norad!=21')
            rows = [json.loads(r) for r in execute(db)[0].splitlines()]
            self.assertEqual(before, rows[1]['channels'])
            self.assertTrue(all(c['flag'] is None for c in before[1:]))

    def test_continuous_stationkeeping_blind_spot(self):
        score = drift.score_axis([[0, 0, .0001, 240], [0, 0, .0001, 115]],
                                 IN_GATE, drift.Config(0, 366))
        self.assertFalse(score['flag'])
        self.assertFalse(score['reportable'])

    def test_exact_upper_bound_and_bound_aware_separation(self):
        cfg = drift.Config(0, 366)
        result = drift.control_summary({'passive': [3829, 0, 0], 'payload': [1000, 20, 0]},
                                       {'passive': 3829 * 100, 'payload': 100000}, cfg)
        upper = 1 - .05 ** (1 / 3829)
        self.assertAlmostEqual(result['passive']['upper95'], upper)
        self.assertLess(upper, .001)
        self.assertTrue(result['passiveBoundMeetsTarget'])
        self.assertAlmostEqual(result['separation'], .02 / upper)
        self.assertIsNone(result['pointSeparation'])
        self.assertIsNone(drift.binomial_upper95(0, 0))
        self.assertEqual(drift.binomial_upper95(3, 3), 1)
        self.assertAlmostEqual(drift.binomial_upper95(1, 2), math.sqrt(.95))
        small = drift.control_summary({'passive': [10, 0, 0], 'payload': [10, 0, 0]},
                                      {'passive': 100, 'payload': 100}, cfg)
        self.assertFalse(small['passiveBoundMeetsTarget'])


class RegimeIntegrationTests(unittest.TestCase):
    def test_raw_gate_cannot_be_hidden_by_daily_median(self):
        with contextlib.closing(fixture()) as db:
            # One high fit: median stays low, raw perigee maximum crosses 800.
            mm = math.sqrt(history.MU_WGS72 / 7500**3) * 86400 / (2 * math.pi)
            db.execute('UPDATE element_set SET mean_motion_q=? WHERE norad=20 AND epoch_ms=?',
                       (round(mm * 1e8), 90 * drift.DAY_MS))
            rows = [json.loads(x) for x in execute(db)[0].splitlines()]
            obj = rows[-2]
            self.assertFalse(obj['geometry']['inGate'])
            self.assertGreater(obj['geometry']['maxPerigeeKm'], 800)
            self.assertFalse(obj['channels'][0]['flag'])
            self.assertTrue(obj['channels'][0]['outOfGateRaising'])
            self.assertEqual(rows[-1]['payload']['objects'], 0)
            self.assertEqual(rows[-1]['outOfGate']['payload']['raising'], 1)

    def test_strict_boundaries_and_trailing_geometry_excluded(self):
        cfg = drift.Config(0, 120, split_day=60)
        for perigee, ecc, expected in ((799.999, .04999, True), (800, .001, False),
                                       (500, .05, False), (801, .051, False)):
            daily = drift.Blocks(1, 'PAYLOAD', np.array([0., 90.]), np.zeros((2, 3)), (0, 0), 2,
                                 geometry=np.array([[40000, .5], [perigee, ecc]]))
            self.assertEqual(drift.regime_geometry(daily, cfg)['inGate'], expected)

    def test_no_test_data_is_gap_even_with_trailing_fit(self):
        with contextlib.closing(fixture()) as db:
            db.execute('DELETE FROM element_set WHERE norad=20 AND epoch_ms>=60*86400000')
            obj = json.loads(execute(db)[0].splitlines()[-2])
            self.assertIsNone(obj['channels'][0]['flag'])
            self.assertIsNone(obj['channels'][0]['windows']['test'])
            self.assertIsNotNone(obj['channels'][0]['windows']['trailing'])
            self.assertIsNone(obj['geometry']['inGate'])

    def test_mixed_window_availability_is_chunk_and_device_independent(self):
        with contextlib.closing(fixture()) as db:
            db.execute('DELETE FROM element_set WHERE norad=20 AND epoch_ms<60*86400000')
            db.execute('DELETE FROM element_set WHERE norad=1 AND epoch_ms>=60*86400000')
            class Oracle:
                def __init__(self, device): self.device = device
                def fit(self, objects, pairs): return drift.fit_cpu(objects, pairs)
            expected = execute(db, chunk=1)[0]
            self.assertEqual(expected, execute(db, chunk=7, backends=[Oracle(0), Oracle(1)])[0])
            self.assertEqual(expected, execute(db, chunk=32)[0])



class PublicationTests(unittest.TestCase):
    def bundle(self):
        with contextlib.closing(fixture()) as db:
            report, _ = execute(db)
        return drift.publication_bundle(io.StringIO(report), "2026-09-12T00:00:00Z")

    def test_nightly_window_is_120_complete_days_with_optional_240_day_context(self):
        cfg = drift.nightly_config(drift.dt.date(2026, 9, 12))
        self.assertEqual((cfg.start_day, cfg.split_day, cfg.end_day), (20348, 20588, 20708))
        self.assertEqual((cfg.block_days, cfg.min_blocks, cfg.min_coverage, cfg.threshold), (5, 12, .8, 5))

    def test_gate_requires_both_bounds_on_own_population(self):
        cfg = drift.Config(0, 120, split_day=60)
        def control(n, payload):
            return drift.control_summary({"passive": [n, 0, 0], "payload": [1000, payload, 0]},
                                         {"passive": n * 100, "payload": 100000}, cfg)
        self.assertFalse(control(100, 900)["sufficientToLabel"])  # separation alone is insufficient
        self.assertFalse(control(4107, 7)["sufficientToLabel"])  # bound passes, separation <10
        self.assertTrue(control(4107, 8)["sufficientToLabel"])
        self.assertIsNone(control(4107, 8)["blockingReason"])
        self.assertFalse(control(0, 0)["sufficientToLabel"])
        with mock.patch.object(drift, "binomial_upper95", return_value=.001):
            self.assertFalse(control(4107, 10)["sufficientToLabel"])  # strict bound
        with mock.patch.object(drift, "binomial_upper95", return_value=.0005):
            self.assertTrue(control(4107, 5)["sufficientToLabel"])  # inclusive separation

    def test_website_suppresses_flags_but_preserves_detections_and_gaps(self):
        b = self.bundle()
        self.assertEqual(b["controls"]["payload"]["flags"], 1)
        self.assertTrue(b["objects"][-1]["raising"])
        self.assertFalse(any(o["flag"] for o in b["objects"]))
        self.assertIsNotNone(b["labelPolicy"]["blockingReason"])
        self.assertGreater(b["objects"][-1]["slopeMetresPerDay"], 40)
        self.assertLess(b["objects"][-1]["slopeMetresPerDay"], 50)
        with self.assertRaisesRegex(ValueError, "incomplete"):
            drift.publication_bundle(io.StringIO('{"kind":"method"}\n'), "date")

    def test_allowed_flags_are_payload_only_and_never_above_gate(self):
        with contextlib.closing(fixture()) as db:
            report, _ = execute(db)
        rows = [json.loads(line) for line in report.splitlines()]
        control = rows[-1]
        control.update(sufficientToLabel=True, blockingReason=None, separation=10)
        control["passive"]["upper95"] = .0005
        def published():
            return drift.publication_bundle(map(drift.canonical, rows), "date")
        self.assertTrue(published()["objects"][-1]["flag"])
        rows[-2]["objectType"] = "UNKNOWN"
        self.assertFalse(published()["objects"][-1]["flag"])
        rows[-2]["objectType"] = "PAYLOAD"
        rows[-2]["geometry"]["inGate"] = False
        self.assertFalse(published()["objects"][-1]["flag"])
        rows[0]["restrictedPopulation"] = True
        self.assertFalse(published()["labelPolicy"]["propulsionLabelPermitted"])

    def test_content_address_fragment_merge_and_last_good_fallback(self):
        from pipeline import orbit_release as release
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = root / "data"
            fragment = root / "pipeline/.cache/orbit-drift-manifest.json"
            b = self.bundle()
            result = drift.publish_cache(b, data, fragment)
            record = result["orbitDrift"]
            import hashlib
            self.assertEqual(hashlib.sha256((data / record["path"]).read_bytes()).hexdigest(), record["sha256"])
            self.assertTrue((data / (record["path"] + ".gz")).is_file())
            step = root / "step.json"
            step.write_text(drift.canonical({"manifest": {"orbitEvents": record}}))
            with mock.patch.object(release, "ROOT", root), mock.patch.object(release, "FRAGMENT_PATH", step):
                merged = release.publish(data)
                self.assertEqual(set(merged), {"orbitEvents", "orbitDrift"})
                (data / "manifest.json").write_text(drift.canonical(merged))
                from deploy import publish_data
                staging = root / "staged"
                with mock.patch("sys.argv", ["publish_data", str(data), str(staging)]):
                    self.assertEqual(publish_data.main(), 0)
                self.assertEqual((staging / record["path"]).read_bytes(), (data / record["path"]).read_bytes())
                self.assertTrue((staging / (record["path"] + ".gz")).is_file())
                for malformed in ('{"manifest":{"orbitDrift":{"path":"gone.json"}}}', "[]", "null", "{"):
                    fragment.write_text(malformed)
                    self.assertEqual(release.publish(data), merged)
                step.unlink()
                self.assertEqual(release.publish(data), merged)
            fragment.write_text(drift.canonical({"manifest": result}))
            old_fragment = fragment.read_bytes()
            before = (data / "manifest.json").read_bytes()
            with mock.patch("pipeline.build_release.write_artifact", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    drift.publish_cache(b, data, fragment)
            self.assertEqual((data / "manifest.json").read_bytes(), before)
            self.assertEqual(fragment.read_bytes(), old_fragment)
            with mock.patch("pipeline.build_release.atomic_write", side_effect=OSError("fragment write failed")):
                with self.assertRaises(OSError):
                    drift.publish_cache(b, data, fragment)
            self.assertEqual(fragment.read_bytes(), old_fragment)

    def test_retention_preserves_live_and_pending_and_has_safe_dry_run(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            artifact_dir = root / "artifacts"
            artifact_dir.mkdir()
            paths = [artifact_dir / f"orbit-drift-{i}.json" for i in range(3)]
            for path in paths:
                path.write_text("{}")
                os.utime(path, (1, 1))
            (root / "manifest.json").write_text(drift.canonical({"orbitDrift": {"path": "artifacts/" + paths[0].name}}))
            fragment = root / "fragment.json"
            fragment.write_text(drift.canonical({"manifest": {"orbitDrift": {"path": "artifacts/" + paths[1].name}}}))
            plan = drift.retention_plan(root, fragment)
            self.assertEqual(plan["remove"], [str(paths[2])])
            self.assertTrue(all(p.exists() for p in paths))
            fragment.write_text("broken")
            with self.assertRaises(json.JSONDecodeError):
                drift.retention_plan(root, fragment)
            self.assertTrue(all(p.exists() for p in paths))

    def test_scheduled_defaults_point_to_the_publishers_data_root(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(drift.main(["--build-cache", "--dry-run"]), 0)
        plan = json.loads(output.getvalue())
        self.assertEqual(plan["dataRoot"], str(drift.ROOT / "public/data"))
        self.assertEqual(plan["fragment"], str(drift.DRIFT_FRAGMENT_PATH))

    def test_build_cache_cannot_publish_a_restricted_or_custom_window(self):
        for args in (("--only", "20"), ("--limit", "1"), ("--start", "2024-01-01"), ("--split", "2024-09-01")):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                drift.main(["--build-cache", "--dry-run", *args])


if __name__ == "__main__":
    unittest.main()
