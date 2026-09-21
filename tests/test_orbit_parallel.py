"""Offline, real-process parity and bounded/resumable sweep regressions."""

import dataclasses
import os
import pickle
import signal
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pipeline import orbit_campaigns as oc
from pipeline import orbit_release as release
from test_orbit_campaigns import series, BASE_MS, DAY_MS


class ParallelSweepTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "fixture.sqlite3"
        db = sqlite3.connect(self.path)
        self.addCleanup(db.close)
        db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE object (norad INTEGER PRIMARY KEY, name TEXT, object_type TEXT);
            CREATE TABLE element_set (
                norad INTEGER, epoch_ms INTEGER, mean_motion_q INTEGER,
                eccentricity_q INTEGER, inclination_q INTEGER, bstar_q INTEGER,
                raan_q INTEGER, arg_perigee_q INTEGER,
                PRIMARY KEY (norad, epoch_ms)) WITHOUT ROWID;
        """)
        self.catalog = {n: {} for n in range(1, 42)}
        for n in self.catalog:
            kind = ("PAYLOAD", "DEBRIS", "ROCKET BODY", "UNKNOWN")[n % 4]
            db.execute("INSERT INTO object VALUES (?, ?, ?)", (n, f"OBJECT {n}", kind))
            rows = series(days=100 + n / 3, cadence_hours=5.23,
                          a_km=oc.RE_WGS72 + (501, 810, 2000)[n % 3],
                          steps={40: 5000, 80: -3000})
            if n == 5:
                rows = [r for r in series(steps={45.25: 2000})
                        if not BASE_MS + 40 * DAY_MS < r[0] < BASE_MS + 45 * DAY_MS]
            # Every object crosses an era edge; some also cross a band edge.
            offset = (1354320000000 if n % 2 else 1606780800000) - BASE_MS
            if n == 41:  # insufficient baseline
                rows = rows[:3]
            for i, (epoch, mm, ecc, inc, bstar) in enumerate(rows):
                if n % 5 == 0 and n != 5 and 200 < i < 240:
                    continue  # tracking gap
                db.execute("INSERT INTO element_set VALUES (?,?,?,?,?,?,0,0)",
                           (n, epoch + offset, int(mm * 1e8), int(ecc * 1e8),
                            int(inc * 1e4), int(bstar * 1e12)))
        # Histories must survive missing metadata; empty metadata isn't scanned.
        db.execute("DELETE FROM object WHERE norad=40")
        db.execute("INSERT INTO object VALUES (99, 'EMPTY', 'DEBRIS')")
        db.commit()
        self.db = db
        self.options = dict(catalog=self.catalog, keep_summaries_for=set(range(1, 38)))

    def assertPassEqual(self, actual, expected):
        # Includes EVERY dataclass field, nested stratum, breakdown bucket,
        # event/test field, exact floating-point day total, and list order.
        self.assertEqual(dataclasses.asdict(actual), dataclasses.asdict(expected))

    def test_real_pool_matches_serial_every_field(self):
        serial = oc.sweep_archive(self.db, workers=1, **self.options)
        self.assertEqual(serial.passed.objects_scanned, 41)
        self.assertEqual(serial.passed.objects_with_baseline, 40)
        self.assertTrue(serial.passed.events)
        self.assertTrue(serial.passed.passive_breakdown)
        self.assertTrue(serial.passed.payload_breakdown)
        self.assertGreater(len(serial.passed.strata), 3)
        for workers in (2, 3):
            with self.subTest(workers=workers):
                parallel = oc.sweep_archive(self.db, workers=workers, **self.options)
                self.assertTrue(parallel.complete)
                self.assertEqual(parallel.objects_this_run, 41)
                self.assertPassEqual(parallel.passed, serial.passed)

    def test_real_pool_filters_only_since_and_resume(self):
        options = dict(self.options, only=[40, 21, 7, 3, 7, 99], start_after=3,
                       since_ms=1606780800000 + 20 * DAY_MS)
        self.assertPassEqual(oc.sweep_archive(self.db, workers=2, **options).passed,
                             oc.sweep_archive(self.db, workers=1, **options).passed)

    def test_spawn_preserves_enabled_detector_flags(self):
        with mock.patch.object(oc, "DECLINE_AFTER_TRACKING_GAP", True):
            serial = oc.sweep_archive(self.db, only=[5], workers=1, **self.options).passed
            parallel = oc.sweep_archive(self.db, only=[5], workers=2, **self.options).passed
        self.assertGreater(serial.tracking_gap_drops, 0)
        self.assertPassEqual(parallel, serial)

    def test_budget_at_end_still_yields_before_entering_tail(self):
        with mock.patch.object(oc.time, "time", side_effect=[0, 0] + [2] * 100):
            first = oc.sweep_archive(self.db, only=[1, 2], workers=2, deadline=1,
                                     **self.options)
        self.assertFalse(first.complete)
        self.assertEqual(first.resume_after, 2)
        final = oc.sweep_archive(self.db, only=[1, 2], workers=2, into=first.passed,
                                 start_after=2, **self.options)
        self.assertTrue(final.complete)
        self.assertEqual(final.objects_this_run, 0)

    def test_deadline_drains_bounded_prefix_then_resumes_exactly(self):
        # The clock advances only in the parent; real workers finish their
        # bounded ranges. Resume with a different pool size after pickling.
        expected = oc.sweep_archive(self.db, workers=1, **self.options).passed
        with mock.patch.object(oc.time, "time", side_effect=[0, 0] + [2] * 100):
            first = oc.sweep_archive(self.db, workers=2, deadline=1, **self.options)
        self.assertFalse(first.complete)
        self.assertEqual(first.resume_after, 2 * oc.SWEEP_SHARD_OBJECTS)
        self.assertEqual(first.objects_this_run, first.resume_after)
        into = pickle.loads(pickle.dumps(first.passed))
        final = oc.sweep_archive(self.db, workers=3, into=into,
                                 start_after=first.resume_after, **self.options)
        self.assertTrue(final.complete)
        self.assertPassEqual(final.passed, expected)

    def test_sigterm_drains_prefix_and_restores_handler(self):
        expected = oc.sweep_archive(self.db, workers=1, **self.options).passed
        original = oc.ArchivePass.merge
        sent = False

        def merge(target, partial):
            nonlocal sent
            if not sent:
                sent = True
                os.kill(os.getpid(), signal.SIGTERM)
            original(target, partial)

        handler = signal.getsignal(signal.SIGTERM)
        with mock.patch.object(oc.ArchivePass, "merge", merge):
            first = oc.sweep_archive(self.db, workers=2, **self.options)
        self.assertEqual(signal.getsignal(signal.SIGTERM), handler)
        self.assertFalse(first.complete)
        self.assertEqual(first.resume_after, 2 * oc.SWEEP_SHARD_OBJECTS)
        final = oc.sweep_archive(self.db, workers=2, into=first.passed,
                                 start_after=first.resume_after, **self.options)
        self.assertPassEqual(final.passed, expected)

    def test_expired_budget_makes_one_object_progress(self):
        result = oc.sweep_archive(self.db, workers=3, deadline=0, **self.options)
        self.assertFalse(result.complete)
        self.assertEqual(result.objects_this_run, 1)
        self.assertEqual(result.resume_after, 1)

    def test_existing_accumulator_never_crosses_worker_pipe(self):
        class ParentOnly:
            def __reduce__(self):
                raise AssertionError("the accumulated checkpoint was sent to a worker")

        sentinel = ParentOnly()
        into = oc.ArchivePass(events=[sentinel], objects_scanned=68654)
        result = oc.sweep_archive(self.db, only=[1, 2], workers=2, into=into,
                                  **self.options)
        self.assertIs(result.passed, into)
        self.assertIs(result.passed.events[0], sentinel)
        self.assertEqual(result.passed.objects_scanned, 68656)

    def test_worker_failure_propagates_and_leaves_handler_usable(self):
        handler = signal.getsignal(signal.SIGTERM)
        with mock.patch.object(oc, "_sweep_range", int):
            with self.assertRaises(TypeError):
                oc.sweep_archive(self.db, workers=2, **self.options)
        self.assertEqual(signal.getsignal(signal.SIGTERM), handler)

    def test_release_passes_worker_override_to_sweep(self):
        # Stop at the checkpoint boundary, before any tail/publication work.
        with mock.patch.object(release, "load_catalog", return_value=self.catalog), \
                mock.patch.object(release, "_read_sweep_state", return_value=None), \
                mock.patch.object(release, "_seconds_until_sweep_due", return_value=0), \
                mock.patch.object(release, "_write_sweep_state") as save, \
                mock.patch.object(release.orbit_campaigns, "sweep_archive", return_value=
                                  oc.SweepProgress(oc.ArchivePass(), 8, 8, 1)) as sweep:
            fragment, report = release.build_cache(Path(self.directory.name),
                                                   write_artifact=mock.Mock(),
                                                   connection=self.db, sweep_workers=3)
        self.assertIsNone(fragment)
        self.assertFalse(report["published"])
        self.assertEqual(sweep.call_args.kwargs["workers"], 3)
        self.assertEqual(save.call_args.args[0]["resumeAfter"], 8)


class MergeTests(unittest.TestCase):
    def test_all_integer_counters_add_including_gap_drops(self):
        partial = oc.ArchivePass()
        names = [f.name for f in dataclasses.fields(partial)
                 if type(getattr(partial, f.name)) is int]
        for name in names:
            setattr(partial, name, 17)
        merged = oc.ArchivePass()
        merged.merge(partial)
        merged.merge(partial)
        for name in names:
            self.assertEqual(getattr(merged, name), 34, name)

    def test_merge_replays_float_additions_instead_of_shard_totals(self):
        days = [1e16, 1., 1., 0.1, 0.2, 0.3]
        serial = oc.ArchivePass()
        merged = oc.ArchivePass()
        for day in days:
            serial.note("DEBRIS", 2, 1, day)
        for chunk in (days[:1], days[1:]):
            partial = oc.ArchivePass()
            for day in chunk:
                partial.note("DEBRIS", 2, 1, day)
            merged.merge(partial)
        self.assertEqual(merged, serial)

    def test_optional_catalogue_counter_and_nested_breakdowns(self):
        target = oc.ArchivePass()
        target.merge(oc.ArchivePass())
        self.assertIsNone(target.catalogue_geo_north_south_events)
        for count in (0, 2, 3):
            target.merge(oc.ArchivePass(
                catalogue_geo_north_south_events=count,
                strata={("2021+", "0-500"): oc.ArchivePass(
                    payload_breakdown={"channel": {"a": count}})},
            ))
        target.merge(oc.ArchivePass())
        self.assertEqual(target.catalogue_geo_north_south_events, 5)
        self.assertEqual(target.strata[("2021+", "0-500")].payload_breakdown,
                         {"channel": {"a": 5}})

    def test_old_checkpoint_retains_68654_objects_and_day_prefix(self):
        old = oc.ArchivePass(objects_scanned=68654, passive_objects=50000,
                             passive_object_days=123456.789)
        del old._day_terms
        del old.passive_breakdown
        old = pickle.loads(pickle.dumps(old))
        partial = oc.ArchivePass(objects_scanned=1)
        partial.note("DEBRIS", 2, 0, 0.1234567)
        old.merge(partial)
        self.assertEqual(old.objects_scanned, 68655)
        self.assertEqual(old.passive_objects, 50001)
        self.assertEqual(old.passive_object_days, 123456.789 + 0.1234567)
        self.assertEqual(old.passive_breakdown, {})

    def test_default_and_override_leave_headroom(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(oc.os, "cpu_count", return_value=16):
            self.assertEqual(oc.sweep_worker_count(), 12)
            with mock.patch.object(oc.os, "cpu_count", return_value=2):
                self.assertEqual(oc.sweep_worker_count(), 1)
            os.environ["SPACE_EXPLORER_ORBIT_SWEEP_WORKERS"] = "3"
            self.assertEqual(oc.sweep_worker_count(), 3)
            os.environ["SPACE_EXPLORER_ORBIT_SWEEP_WORKERS"] = "0"
            with self.assertRaises(ValueError):
                oc.sweep_worker_count()


if __name__ == "__main__":
    unittest.main()
