"""Offline fixtures only. Never opens the operator's archive or network."""
import json
import contextlib
import dataclasses
import io
import pickle
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock

import numpy as np

from pipeline import orbit_campaigns as oc, orbit_columnar as col, orbit_history as oh


def fixture(path):
    db = sqlite3.connect(path)
    db.executescript(oh._SCHEMA)
    db.execute("PRAGMA journal_mode=WAL")
    return db


def insert(db, n, epoch, *, mm=1543210987, bstar=-123456789, inc=987654):
    db.execute("""INSERT INTO element_set
        (norad,epoch_ms,mean_motion_q,eccentricity_q,inclination_q,bstar_q,
         raan_q,arg_perigee_q,mean_anomaly_q,ingest_hour)
         VALUES (?,?,?,?,?,?,?,?,0,0)""", (n, epoch, mm, 99999999, inc, bstar, 3599999, 1234567))
    db.commit()


class ColumnarTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "source.sqlite3"
        self.root = Path(self.temp.name) / "columns"
        self.db = fixture(self.path)
        self.addCleanup(self.db.close)
        for n, epoch, bstar in [(10, 1700000000001, None), (10, 1700000000003, 0),
                                (20, 1700000000001, -123456789), (40, 1700000000002, 987654321)]:
            insert(self.db, n, epoch, bstar=bstar)

    def build(self, **kw):
        return col.build(self.root, archive=self.path, **kw)

    def stored(self, **kw):
        with col.open_store(self.root, archive=self.path) as s:
            return [(o.norad, list(o.rows())) for o in s.iter_objects(**kw)]

    def source(self, **kw):
        db = oc.open_archive_for_reading(self.path)
        try:
            return list(oc.stream_object_rows(db, **kw))
        finally:
            db.close()

    def test_exact_roundtrip_all_fields_and_null_zero_negative_bstar(self):
        self.build()
        self.assertEqual(self.stored(), self.source())
        with col.open_store(self.root, archive=self.path) as s:
            for name in col.FIELDS:
                self.assertEqual(s.arrays[name].dtype, np.dtype("int64" if name == "epoch_ms" else "float64"))
                self.assertFalse(s.arrays[name].flags.writeable)
            self.assertEqual(s.arrays["index"].dtype.itemsize, 12)
        self.assertTrue(col.verify(self.root, archive=self.path)["ok"])

    def test_float32_would_lose_mean_motion_and_all_quantised_fields_recover(self):
        self.assertNotEqual(round(float(np.float32(1543210987 / 1e8)) * 1e8), 1543210987)
        rng = np.random.default_rng(123)
        raw = np.zeros(20000, dtype=col.RAW_DTYPE)
        raw["epoch_ms"] = 1700000000001 + np.arange(len(raw))
        raw["valid"] = 1
        for name, high in [("mean_motion", 1800000000), ("eccentricity", 100000000),
                           ("inclination", 1800000), ("raan", 3600000), ("arg_perigee", 3600000),
                           ("bstar", 10**12)]:
            raw[name] = rng.integers(-high if name == "bstar" else 0, high, len(raw))
        columns = col._dequantise(raw)
        np.testing.assert_array_equal(columns["epoch_ms"], raw["epoch_ms"])
        for name, scale in zip(col.FIELDS[1:], col.SCALES[1:]):
            np.testing.assert_array_equal(np.rint(columns[name] * scale).astype(np.int64), raw[name])
            np.testing.assert_array_equal(columns[name], [int(v) / scale for v in raw[name]])

    def test_out_of_domain_quantisation_fails_before_promotion(self):
        self.db.execute("UPDATE element_set SET mean_motion_q=? WHERE norad=10", (2**53 + 1,))
        self.db.commit()
        with self.assertRaises(col.IntegrityError):
            self.build()
        self.assertFalse((self.root / "CURRENT").exists())

    def test_segmentation_chunk_offsets_and_filter_parity(self):
        self.build()
        self.assertEqual(self.stored(only=[10, 40], since_ms=1700000000002),
                         self.source(only=[10, 40], since_ms=1700000000002))
        with col.open_store(self.root, archive=self.path) as s:
            chunks = list(s.iter_chunks(objects_per_chunk=2))
            self.assertEqual(chunks[0][0]["offset"].tolist(), [0, 2])
            self.assertEqual(chunks[1][0]["offset"].tolist(), [0])
            for index, arrays in chunks:
                self.assertEqual(sum(index["length"]), len(arrays["epoch_ms"]))
                for array in arrays.values():
                    self.assertTrue(array.flags.c_contiguous)
                    self.assertTrue(np.shares_memory(array, s.arrays[next(n for n in col.FIELDS if arrays[n] is array)]))

    def test_backfill_same_count_edit_prune_and_new_object_detected(self):
        self.build()
        insert(self.db, 10, 1700000000002)
        self.db.execute("UPDATE element_set SET raan_q=raan_q+1 WHERE norad=20")
        self.db.execute("DELETE FROM element_set WHERE norad=40")
        self.db.commit()
        insert(self.db, 30, 1600000000000)
        with self.assertRaises(col.IntegrityError) as raised:
            col.verify(self.root, archive=self.path)
        self.assertEqual(raised.exception.changed_objects, [10, 20, 30, 40])
        with self.assertRaises(col.IntegrityError):
            self.stored()
        col.append(self.root, archive=self.path)
        self.assertEqual(self.stored(), self.source())
        self.assertFalse((self.root / "HALTED.json").exists())

    def test_append_dequantises_only_changed_object_and_is_idempotent(self):
        self.build()
        insert(self.db, 10, 1700086400000)
        with mock.patch.object(col, "_dequantise", wraps=col._dequantise) as dequantise:
            m = col.append(self.root, archive=self.path)
        self.assertEqual(m["maintenance"]["changed_objects"], [10])
        self.assertEqual(dequantise.call_count, 1)
        self.assertEqual(self.stored(), self.source())
        with mock.patch.object(col, "_dequantise", side_effect=AssertionError("unchanged object rebuilt")):
            col.append(self.root, archive=self.path)
        self.assertEqual(self.stored(), self.source())
        self.assertEqual(len(list(self.root.glob("gen-*"))), 1)

    def test_each_raw_field_mutation_including_null_is_detected(self):
        self.build()
        for field in ["mean_motion_q", "eccentricity_q", "inclination_q", "bstar_q", "raan_q", "arg_perigee_q", "epoch_ms"]:
            with self.subTest(field=field):
                self.db.execute(f"UPDATE element_set SET {field}=COALESCE({field},0)+1 WHERE norad=20")
                self.db.commit()
                with self.assertRaises(col.IntegrityError) as error:
                    col.verify(self.root, archive=self.path)
                self.assertEqual(error.exception.changed_objects, [20])
                col.append(self.root, archive=self.path)

    def test_source_commit_while_iteration_active_aborts_context(self):
        self.build()
        with self.assertRaises(col.SourceChanged):
            with col.open_store(self.root, archive=self.path) as s:
                first = next(s.iter_objects())
                self.assertEqual(first.norad, 10)
                insert(self.db, 10, 1700000000002)
        with self.assertRaises(col.SourceChanged):
            col.open_store(self.root, archive=self.path)

    def test_null_to_zero_is_a_content_change(self):
        self.build()
        self.db.execute("UPDATE element_set SET bstar_q=0 WHERE bstar_q IS NULL")
        self.db.commit()
        with self.assertRaises(col.IntegrityError) as error:
            col.verify(self.root, archive=self.path)
        self.assertEqual(error.exception.changed_objects, [10])

    def test_failed_promotion_keeps_previous_complete_generation(self):
        self.build()
        pointer = (self.root / "CURRENT").read_bytes()
        original = col.os.replace
        def fail_current(src, dst):
            if Path(dst).name == "CURRENT":
                raise OSError("injected interruption before atomic promotion")
            return original(src, dst)
        with mock.patch.object(col.os, "replace", side_effect=fail_current):
            with self.assertRaises(OSError):
                self.build()
        self.assertEqual((self.root / "CURRENT").read_bytes(), pointer)
        self.assertEqual(self.stored(), self.source())

    def test_commit_during_build_never_promotes_partial_scan(self):
        original = col._dequantise
        def change(raw):
            insert(self.db, 5, 1700000000000)
            return original(raw)
        with mock.patch.object(col, "_dequantise", side_effect=change):
            with self.assertRaises(col.SourceChanged):
                self.build()
        self.assertFalse((self.root / "CURRENT").exists())

    def test_rollup_and_cold_ledger_change_invalidates_even_without_row_change(self):
        self.build()
        self.db.execute("INSERT INTO pruned_month VALUES ('2020-01',1,1)")
        self.db.execute("INSERT INTO month_rollup VALUES ('2020-01',1,1,1)")
        self.db.execute("INSERT INTO cold_shard VALUES ('2020-01','offline',1,1,'abc',1,1)")
        self.db.commit()
        with self.assertRaises(col.SourceChanged):
            self.stored()
        result = col.verify(self.root, archive=self.path)
        self.assertTrue(result["needs_recertification"])
        col.append(self.root, archive=self.path)
        self.assertEqual(self.stored(), self.source())

    def test_column_corruption_halts_and_full_build_recovers(self):
        self.build()
        d, _ = col._generation(self.root)
        path = d / "mean_motion.bin"
        original = path.read_bytes()
        altered = bytearray(original)
        altered[0] ^= 1
        path.write_bytes(altered)
        with self.assertRaises(col.IntegrityError):
            self.stored()
        with self.assertRaises(col.IntegrityError):
            col.verify(self.root, archive=self.path)
        path.write_bytes(original)
        with self.assertRaises(col.IntegrityError):
            self.stored()  # restoring bytes cannot clear the sticky failure
        self.build()
        self.assertEqual(self.stored(), self.source())

    def test_index_and_manifest_corruption_refuse_to_open(self):
        self.build()
        d, _ = col._generation(self.root)
        (d / "index.bin").write_bytes(b"\0" * 36)
        with self.assertRaises(col.IntegrityError):
            self.stored()
        self.build()
        d, _ = col._generation(self.root)
        m = json.loads((d / "manifest.json").read_text())
        m["objects"][0]["length"] += 1
        (d / "manifest.json").write_text(json.dumps(m))
        with self.assertRaises(col.IntegrityError):
            self.stored()

    def test_scope_empty_and_last_object_deletion(self):
        self.build(only=[])
        self.assertEqual(self.stored(), [])
        self.build(only=[10])
        self.assertEqual([n for n, _ in self.stored()], [10])
        self.db.execute("DELETE FROM element_set WHERE norad=10")
        self.db.commit()
        col.append(self.root, archive=self.path)
        self.assertEqual(self.stored(), [])

    def test_overflow_and_storage_budget_leave_current_intact(self):
        self.build()
        pointer = (self.root / "CURRENT").read_bytes()
        with self.assertRaises(col.IntegrityError):
            col.append(self.root, archive=self.path, budget_bytes=1)
        self.assertEqual((self.root / "CURRENT").read_bytes(), pointer)
        self.build()
        with mock.patch.object(col, "MAX_ROWS", 3):
            with self.assertRaises(col.IntegrityError):
                self.build()
        self.assertEqual(self.stored(), self.source())

    def test_row_offset_overflow_is_checked_independently_of_norad(self):
        self.db.execute("DELETE FROM element_set")
        self.db.commit()
        for epoch in range(4):
            insert(self.db, 1, 1700000000000 + epoch)
        with mock.patch.object(col, "MAX_ROWS", 3):
            with self.assertRaisesRegex(col.IntegrityError, "index overflow"):
                self.build()
        self.assertFalse((self.root / "CURRENT").exists())

    def test_cleanup_dry_run_protects_current_and_unknown_directories(self):
        self.build()
        current, _ = col._generation(self.root)
        stale = self.root / ("gen-" + "a" * 32)
        stale.mkdir()
        (stale / "OWNER").write_text(col.OWNER)
        (stale / "epoch_ms.bin").write_bytes(b"123")
        other = self.root / "other-agent"
        other.mkdir()
        (other / "keep").write_text("owned by someone else")
        result = col.cleanup(self.root)
        self.assertEqual(result["paths"], [str(stale)])
        self.assertTrue(stale.exists())
        col.cleanup(self.root, apply=True)
        self.assertFalse(stale.exists())
        self.assertTrue(current.exists())
        self.assertTrue((other / "keep").exists())
        self.assertEqual(self.stored(), self.source())

    def test_reader_uses_approved_opener_and_missing_source_is_not_created(self):
        with mock.patch.object(oc, "open_archive_for_reading", wraps=oc.open_archive_for_reading) as opener:
            self.build()
        opener.assert_called_once_with(self.path.resolve())
        missing = Path(self.temp.name) / "absent.sqlite3"
        with self.assertRaises(FileNotFoundError):
            col.build(Path(self.temp.name) / "missing", archive=missing)
        self.assertFalse(missing.exists())

    def test_maintenance_build_append_corruption_and_missing_column(self):
        self.assertEqual(col.maintain(self.root, archive=self.path)["operation"], "build")
        self.assertEqual(col.maintain(self.root, archive=self.path)["operation"], "current")
        insert(self.db, 10, 1700000000100)
        self.assertEqual(col.maintain(self.root, archive=self.path)["operation"], "append")
        d, _ = col._generation(self.root)
        (d / "mean_motion.bin").write_bytes(b"broken")
        self.assertEqual(col.maintain(self.root, archive=self.path)["operation"], "build")
        d, _ = col._generation(self.root)
        (d / "raan.bin").unlink()
        insert(self.db, 20, 1700000000200)
        self.assertEqual(col.maintain(self.root, archive=self.path)["operation"], "build")
        self.assertEqual(self.stored(), self.source())

    def test_maintenance_budget_never_certifies_stale_or_partial_work(self):
        preview = col.maintain(self.root, archive=self.path, dry_run=True)
        self.assertEqual(preview["operation"], "build")
        self.assertFalse(self.root.exists())
        with self.assertRaises(col.BudgetExceeded):
            col.maintain(self.root, archive=self.path, seconds=0)
        self.assertFalse(self.root.exists())
        self.build()
        pointer = (self.root / "CURRENT").read_bytes()
        insert(self.db, 10, 1700000000100)
        self.assertEqual(col.maintain(self.root, archive=self.path, dry_run=True)["operation"], "append")
        self.assertEqual((self.root / "CURRENT").read_bytes(), pointer)
        with self.assertRaises(col.BudgetExceeded):
            col.maintain(self.root, archive=self.path, seconds=0)
        self.assertEqual((self.root / "CURRENT").read_bytes(), pointer)
        with self.assertRaises(col.SourceChanged):
            self.stored()
        # Exhaust in the middle of a write, not just the admission check.
        original = col._dequantise
        def expire(raw):
            value = original(raw)
            raise col.BudgetExceeded("injected mid-build deadline")
        with mock.patch.object(col, "_dequantise", expire):
            with self.assertRaises(col.BudgetExceeded):
                col.maintain(self.root, archive=self.path)
        self.assertEqual((self.root / "CURRENT").read_bytes(), pointer)
        self.assertEqual(len(list(self.root.glob("gen-*"))), 1)

    def test_bad_pointer_rebuild_removes_only_its_failed_staging(self):
        self.build()
        (self.root / "CURRENT").write_text("bad json")
        with mock.patch.object(col, "_dequantise", side_effect=col.BudgetExceeded("expired")):
            with self.assertRaises(col.BudgetExceeded):
                col.maintain(self.root, archive=self.path)
        self.assertEqual(len(list(self.root.glob("gen-*"))), 1)
        self.assertEqual(col.maintain(self.root, archive=self.path)["operation"], "build")
        self.assertEqual(self.stored(), self.source())


class SweepColumnarTests(unittest.TestCase):
    def setUp(self):
        from test_orbit_parallel import ParallelSweepTests
        self.fixture = ParallelSweepTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.db, self.path = self.fixture.db, self.fixture.path
        self.root = self.path.parent / "columns"
        self.members = [1, 2, 5, 40, 41]
        self.options = dict(self.fixture.options, only=self.members, workers=1)
        col.build(self.root, archive=self.path, only=self.members)

    def sweep(self, **kw):
        options = dict(self.options, columnar_root=self.root, **kw)
        return oc.sweep_archive(self.db, **options)

    def test_real_serial_and_pool_paths_never_call_sqlite_row_reader(self):
        # Several jobs per worker, exercising retained mappings across ranges.
        self.options["only"] = list(range(1, 42))
        col.build(self.root, archive=self.path)
        expected = oc.sweep_archive(self.db, columnar_root=False, **self.options)
        with mock.patch.object(oc, "stream_object_rows", side_effect=AssertionError("SQLite rows")):
            actual = self.sweep()
        self.assertEqual(dataclasses.asdict(actual.passed), dataclasses.asdict(expected.passed))
        self.options["workers"] = 2
        self.assertEqual(self.sweep().passed, expected.passed)
        self.assertTrue(actual.passed.events)
        self.assertGreater(actual.passed.passive_intervals, 0)

    def test_default_release_call_uses_verified_store_even_with_spent_budget(self):
        with mock.patch.object(col, "DEFAULT_ROOT", self.root), \
                mock.patch.object(oc, "archive_db_path", return_value=self.path), \
                mock.patch.object(oc, "stream_object_rows", side_effect=AssertionError("SQLite rows")):
            actual = oc.sweep_archive(self.db, deadline=0, **self.options)
        self.assertEqual(actual.objects_this_run, 1)
        self.assertEqual(actual.resume_after, self.members[0])

    def test_maintenance_gets_only_five_percent_of_remaining_slice(self):
        import time
        with mock.patch.object(col, "maintain", wraps=col.maintain) as maintenance:
            self.sweep(deadline=time.time() + 10)
        self.assertGreater(maintenance.call_args.kwargs["seconds"], 0)
        self.assertLessEqual(maintenance.call_args.kwargs["seconds"], 0.5)

    def test_gpu_epoch_slices_reach_backend_through_real_sweep(self):
        from pipeline import orbit_sweep_gpu as gpu
        from test_orbit_sweep_gpu import oracle
        received = []
        def backend(data, kappa, *, epoch_slices):
            received.append(epoch_slices)
            prepared = gpu.prepare(data, epoch_slices=epoch_slices)
            np.testing.assert_array_equal(prepared[3], [i.start_ms for i in data])
            np.testing.assert_array_equal(prepared[4], [i.end_ms for i in data])
            return oracle(data, kappa)
        with mock.patch.object(gpu.Backend, "start"), \
                mock.patch.object(gpu.Backend, "analyze", side_effect=backend):
            actual = self.sweep(gpu_devices=(1,))
        self.assertEqual(len(received), actual.passed.objects_with_baseline)
        self.assertTrue(received)

    def test_subset_filters_since_resume_empty_and_unknown(self):
        for overrides in (dict(only=[41, 5, 5, 2], start_after=2),
                          dict(since_ms=1354320000000 + 60 * 86400000),
                          dict(start_after=999999)):
            options = dict(self.options, **overrides)
            expected = oc.sweep_archive(self.db, columnar_root=False, **options)
            actual = oc.sweep_archive(self.db, columnar_root=self.root, **options)
            self.assertEqual(actual.passed, expected.passed)

    def test_expired_slice_resumes_old_checkpoint_with_exact_day_sums(self):
        expected = oc.sweep_archive(self.db, columnar_root=False, **self.options).passed
        first = oc.sweep_archive(self.db, columnar_root=False, deadline=0, **self.options)
        del first.passed.payload_breakdown  # emulate an older checkpoint
        into = pickle.loads(pickle.dumps(first.passed))
        original = into.objects_scanned
        final = self.sweep(into=into, start_after=first.resume_after)
        self.assertIs(final.passed, into)
        self.assertGreater(into.objects_scanned, original)
        # First object is DEBRIS; the old checkpoint's payload breakdown was empty.
        self.assertEqual(final.passed, expected)

    def test_absent_corrupt_and_out_of_scope_fallback_are_loud_once(self):
        expected = oc.sweep_archive(self.db, columnar_root=False, **self.options).passed
        d, _ = col._generation(self.root)
        for action in (lambda: (self.root / "CURRENT").unlink(),
                       lambda: (d / "mean_motion.bin").write_bytes(b"bad"),
                       lambda: col.build(self.root, archive=self.path, only=[1])):
            col.build(self.root, archive=self.path, only=self.members)
            d, _ = col._generation(self.root)
            action()
            log = io.StringIO()
            with contextlib.redirect_stderr(log):
                actual = self.sweep(columnar_seconds=0)
            self.assertEqual(actual.passed, expected)
            self.assertEqual(log.getvalue().count("SWEEP COLUMNAR FALLBACK:"), 1)

    def test_exit_failure_discards_slice_before_merging_existing_checkpoint(self):
        first = oc.sweep_archive(self.db, columnar_root=False, deadline=0, **self.options)
        expected = oc.sweep_archive(self.db, columnar_root=False, **self.options).passed
        original = col.Store.__exit__
        exits = 0
        def fail_last(store, *args):
            nonlocal exits
            exits += 1
            original(store, *args)
            if exits == 2:  # maintain's current check succeeds, consumer exit fails
                raise col.IntegrityError("injected exit failure")
        with mock.patch.object(col.Store, "__exit__", fail_last), contextlib.redirect_stderr(io.StringIO()) as log:
            actual = self.sweep(into=first.passed, start_after=first.resume_after)
        self.assertEqual(actual.passed, expected)
        self.assertEqual(log.getvalue().count("SWEEP COLUMNAR FALLBACK:"), 1)

    def test_concurrent_source_change_retries_entire_slice(self):
        iterator = col.Store.iter_objects
        def changing(store, **kw):
            for index, obj in enumerate(iterator(store, **kw)):
                yield obj
                if index == 0:
                    self.db.execute("UPDATE element_set SET inclination_q=inclination_q+1 WHERE norad=2")
                    self.db.commit()
        with mock.patch.object(col.Store, "iter_objects", changing), contextlib.redirect_stderr(io.StringIO()) as log:
            actual = self.sweep()
        expected = oc.sweep_archive(self.db, columnar_root=False, **self.options)
        self.assertEqual(actual.passed, expected.passed)
        self.assertEqual(log.getvalue().count("SWEEP COLUMNAR FALLBACK:"), 1)

    def test_temp_shadow_and_uncommitted_data_use_caller_connection(self):
        self.db.execute("CREATE TEMP VIEW element_set AS SELECT * FROM main.element_set WHERE norad=2")
        with mock.patch.object(col, "maintain", side_effect=AssertionError("wrong connection")):
            actual = self.sweep()
        self.assertEqual(actual.objects_this_run, 1)
        self.db.execute("DROP VIEW temp.element_set")
        self.db.execute("DELETE FROM element_set WHERE norad=2")
        with mock.patch.object(col, "maintain", side_effect=AssertionError("uncommitted inputs")):
            actual = self.sweep()
        self.assertEqual(actual.objects_this_run, len(self.members) - 1)

    def test_gpu_prepare_borrows_contiguous_epochs_and_gathers_rejected_pairs(self):
        from pipeline import orbit_sweep_gpu as gpu
        with col.open_store(self.root, archive=self.path) as store:
            for obj in store.iter_objects(only=[1, 5]):
                epochs = {}
                actual = oc.intervals_from_rows(obj.norad, "test", "PAYLOAD", obj, epoch_slices=epochs)
                expected = oc.intervals_from_rows(obj.norad, "test", "PAYLOAD", list(obj.rows()))
                self.assertEqual(actual, expected)
                a, b = gpu.prepare(actual, epoch_slices=epochs), gpu.prepare(expected)
                for left, right in zip(a[1:], b[1:]):
                    np.testing.assert_array_equal(left, right)
                self.assertEqual(np.shares_memory(a[3], obj.columns["epoch_ms"]), obj.norad == 1)


if __name__ == "__main__":
    unittest.main()
