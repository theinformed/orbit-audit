"""Offline release resumption: real shard reads, artifact bytes and SIGTERM."""

import collections
import contextlib
import datetime as dt
import gzip
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pipeline import orbit_campaigns as oc
from pipeline import orbit_history as oh
from pipeline import orbit_events as oe
from pipeline import orbit_release as release
from pipeline.orbit_tail import TailCheckpoint, TailPaused
from test_orbit_campaigns import intervals, series
from test_orbit_history import gp_record


class TailResumeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.connection = oh.open_archive(self.root / "fixture.sqlite3")
        self.addCleanup(self.connection.close)
        self.catalog = {1: {}, 257: {}, 2: {}, 255: {}, 511: {}}
        # Two NORADs share shard 1; shard 255 exercises the end; most are empty.
        for norad in self.catalog:
            oh.ingest_records(self.connection, [
                gp_record(norad, f"2026-08-0{day}T{hour:02d}:00:00", MEAN_MOTION=15.5 + day / 10000)
                for day in range(1, 4) for hour in (0, 6, 12, 18)
            ], captured_ms=1785801600000)
        # Nonempty evidence cards and neighbourhood markers, not just samples.
        self.scan = oc.ArchivePass(events=oc.detect_object_events(
            intervals(series(steps={45: 2000})), kappa=32))
        self.assertTrue(self.scan.events)
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(release, "load_catalog", return_value=self.catalog))
        self.stack.enter_context(mock.patch.object(release, "COHORT_DETECT_WORKERS", 1))
        self.stack.enter_context(mock.patch.object(release, "space_weather_gaps", return_value=[]))
        self.stack.enter_context(mock.patch.object(release, "_load_narratives", return_value={}))
        # Same generation time for the reference build; resume changes the wall clock.
        self.datetime = self.stack.enter_context(mock.patch.object(release.dt, "datetime", wraps=dt.datetime))
        self.datetime.now.return_value = dt.datetime(2026, 9, 11, tzinfo=dt.timezone.utc)

    @staticmethod
    def writer(root, prefix, value):
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        digest = hashlib.sha256(raw).hexdigest()
        relative = f"artifacts/{prefix}-{digest[:16]}.json"
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        path.with_suffix(".json.gz").write_bytes(gzip.compress(raw, mtime=0))
        return relative, digest

    @contextlib.contextmanager
    def run_paths(self, name):
        root = self.root / name
        root.mkdir(exist_ok=True)
        with (mock.patch.object(release, "SWEEP_STATE_PATH", root / "state.pickle"),
              mock.patch.object(release, "FRAGMENT_PATH", root / "manifest-fragment.json")):
            if not release.SWEEP_STATE_PATH.exists():
                release._write_sweep_state({
                    "version": 4, "kappa": 32.0, "catalogSize": len(self.catalog),
                    "startedAt": "2026-09-10T00:00:00Z", "resumeAfter": release.SWEPT_TO_END,
                    "passed": self.scan,
                })
            yield root

    def run_build(self, root, writer=None, budget=None, workers=1):
        return release.build_cache(root, connection=self.connection,
                                   write_artifact=writer or self.writer,
                                   budget_seconds=budget, tail_workers=workers, minimum_seconds_between_sweeps=0)

    def reference(self):
        with self.run_paths("reference") as root:
            fragment, report = self.run_build(root)
            self.assertEqual(report["status"], "swept")
            return fragment, {p.name: p.read_bytes() for p in (root / "artifacts").iterdir()}

    def test_sigterm_inside_writer_preserves_shard_and_matches_whole_bundle(self):
        expected, expected_bytes = self.reference()
        writes = collections.Counter()
        previous_handler = signal.getsignal(signal.SIGTERM)

        def interrupted_writer(root, prefix, value):
            writes[prefix] += 1
            result = self.writer(root, prefix, value)
            if prefix == "orbit-history-001":
                # Real OS signal in the vulnerable gap: bytes written but the
                # caller has not yet received the path/digest to checkpoint.
                os.kill(os.getpid(), signal.SIGTERM)
            return result

        with self.run_paths("resumed") as root:
            release.FRAGMENT_PATH.write_text("previous release")
            fragment, report = self.run_build(root, interrupted_writer)
            self.assertIsNone(fragment)
            self.assertEqual(report["lastStage"], "shard:001")
            self.assertFalse(report["published"])
            self.assertEqual(release.FRAGMENT_PATH.read_text(), "previous release")
            self.assertEqual(signal.getsignal(signal.SIGTERM), previous_handler)
            # Exercise pruner protection as well as restart protection.
            for path in (root / "artifacts").iterdir():
                path.unlink()
            self.datetime.now.return_value = dt.datetime(2026, 9, 12, tzinfo=dt.timezone.utc)
            with mock.patch.object(release, "read_series", wraps=release.read_series) as reads:
                fragment, report = self.run_build(root, interrupted_writer)
            for call in reads.call_args_list:
                self.assertTrue({1, 257}.isdisjoint(call.args[1]), "completed members were queried again")
            self.assertEqual(writes["orbit-history-001"], 1)
            self.assertEqual(fragment, expected)
            self.assertEqual({p.name: p.read_bytes() for p in (root / "artifacts").iterdir()}, expected_bytes)
            self.assertFalse(release.SWEEP_STATE_PATH.exists())
            self.assertFalse(release.SWEEP_STATE_PATH.with_suffix(".tail").exists())

    def test_tiny_budgets_converge_without_recomputing_any_completed_stage(self):
        expected, _ = self.reference()
        counts = collections.Counter()
        original = TailCheckpoint.step

        def count_step(tail, name, compute):
            def counted():
                counts[name] += 1
                return compute()
            return original(tail, name, counted)

        with self.run_paths("budgeted") as root:
            with mock.patch.object(TailCheckpoint, "step", count_step):
                for run in range(350):
                    fragment, report = self.run_build(root, budget=1e-9)
                    if fragment is not None:
                        break
                    self.assertEqual(report["status"], "checkpointed")
                    self.datetime.now.return_value = dt.datetime(2026, 9, 12, tzinfo=dt.timezone.utc)
                else:
                    self.fail("budgeted tail did not converge")
            self.assertEqual(fragment, expected)
            self.assertGreater(run, release.HISTORY_SHARDS)
            for name, count in counts.items():
                # Parent assembly can be reentered after a child yields. Its
                # expensive children and every (including empty) shard cannot.
                if name not in ("prepared", "prepared-streamed", "drag", "cohort-events"):
                    self.assertEqual(count, 1, name)

    def test_shard_local_reads_equal_the_original_all_series_partition(self):
        prepared = release._prepare_tail(self.connection, self.root, 32.0, {}, self.scan, release._uncached_step)
        _, _, wanted, marks, events, clusters = prepared
        whole_series = release.read_series(self.connection, wanted, marks)
        for index in range(release.HISTORY_SHARDS):
            shard = release._history_shard(self.connection, index, wanted, marks, events, clusters)
            members = {n: samples for n, samples in whole_series.items() if n % release.HISTORY_SHARDS == index}
            self.assertEqual(shard is None, not members)
            if shard:
                self.assertEqual([o["norad"] for o in shard["objects"]], sorted(members))
                for obj in shard["objects"]:
                    self.assertEqual(obj["samples"], members[obj["norad"]])

    def test_failed_fragment_write_retries_without_rebuilding_artifacts(self):
        with self.run_paths("fragment-failure") as root:
            with mock.patch.object(release, "write_fragment", side_effect=OSError("disk unavailable")):
                with self.assertRaisesRegex(OSError, "disk unavailable"):
                    self.run_build(root)
            with (mock.patch.object(release, "read_series", side_effect=AssertionError("repeat read")),
                  mock.patch.object(release, "_prepare_tail", side_effect=AssertionError("repeat prepare"))):
                fragment, report = self.run_build(root, mock.Mock(side_effect=AssertionError("repeat write")))
            self.assertIsNotNone(fragment)
            self.assertTrue(report["published"])

    def test_checkpoint_failure_cannot_be_swallowed_as_optional_missing_shells(self):
        original = TailCheckpoint.step

        def full_disk(tail, name, compute):
            if name == "shells":
                raise OSError("checkpoint disk full")
            return original(tail, name, compute)

        with self.run_paths("full-disk") as root:
            with mock.patch.object(TailCheckpoint, "step", full_disk):
                with self.assertRaisesRegex(OSError, "checkpoint disk full"):
                    self.run_build(root)
            self.assertFalse(release.FRAGMENT_PATH.exists())
            self.assertTrue(release.SWEEP_STATE_PATH.exists())

    def test_pool_matches_serial_json_gzip_events_drag_and_manifest(self):
        expected, expected_bytes = self.reference()
        with self.run_paths("parallel") as root:
            fragment, report = self.run_build(root, workers=3)
            self.assertTrue(report["published"])
            self.assertEqual(fragment, expected)
            self.assertEqual({p.name: p.read_bytes() for p in (root / "artifacts").iterdir()}, expected_bytes)

    def test_streamed_cards_match_original_in_memory_bundles(self):
        shards, events, drag = release.build_bundles(
            self.connection, self.root, scan=self.scan, narratives={})
        with self.run_paths("streamed") as root:
            fragment, _ = self.run_build(root, workers=2)
            expected = {f"orbit-history-{shard['shard']:03d}": shard for shard in shards}
            expected.update({"orbit-events": events, "orbit-drag": drag})
            for prefix, bundle in expected.items():
                path, digest = self.writer(self.root / "original", prefix, bundle)
                self.assertEqual((root / path).read_bytes(), (self.root / "original" / path).read_bytes())
                self.assertEqual((root / path).with_suffix(".json.gz").read_bytes(),
                                 (self.root / "original" / path).with_suffix(".json.gz").read_bytes())

    def test_covariate_transfer_disclosure_survives_into_the_bundle(self):
        """docs/paperb-results-20260920.md's registered transfer finding must
        reach the published orbit-events bundle inside controls.selfHistory,
        unchanged, alongside every other control field."""
        _shards, events, _drag = release.build_bundles(
            self.connection, self.root, scan=self.scan, narratives={})
        self_history = events["controls"]["selfHistory"]
        transfer = self_history["covariateTransfer"]
        self.assertEqual(transfer, {
            "measured": "2026-09-20",
            "rawFloorPer1000": 0.163,
            "payloadReweightedPer1000": 0.335,
            "honestTierPer1000": 0.224,
            "honestTierCI": [0.154, 1.846],
            "compositeMatchedSeparation": 8.83,
            "compositeNote": (
                "raw-floor separation 18.191x divided by the registered reweighting "
                "factor 2.0591; the sensitivity variant (48 cells) gives 13.77x; "
                "see Phase 3"
            ),
            "verdict": (
                "registered transfer test failed; pooled floor may understate the "
                "payload-covariate floor; see Phase 3"
            ),
            "reference": "docs/paperb-*-20260920",
        })
        self.assertIn("covariateTransfer", self_history["note"])
        # Disclosure only: it must not move the gate.
        self.assertIn("sufficientToLabel", self_history)
        self.assertIn("manoeuvreLabelPermitted", events["labelPolicy"])

    def test_parallel_stop_drains_and_resume_never_rewrites_banked_shards(self):
        expected, expected_bytes = self.reference()
        original = TailCheckpoint.save
        for mode in ("deadline", "sigterm"):
            sent = False
            def stop(tail, name, value, **kwargs):
                nonlocal sent
                result = original(tail, name, value, **kwargs)
                if name.startswith("shard:") and not sent:
                    sent = True
                    if mode == "deadline":
                        tail.deadline = 0
                    else:
                        os.kill(os.getpid(), signal.SIGTERM)
                return result

            with self.subTest(mode=mode), self.run_paths(mode) as root:
                release.FRAGMENT_PATH.write_text("previous release")
                with mock.patch.object(TailCheckpoint, "save", stop):
                    fragment, report = self.run_build(root, tracking_writer, workers=3)
                self.assertIsNone(fragment)
                self.assertEqual(report["shardsDone"], 3)
                self.assertFalse(report["published"])
                self.assertEqual(release.FRAGMENT_PATH.read_text(), "previous release")
                before = collections.Counter((root / "writes").read_text().splitlines())
                for p in (root / "artifacts").iterdir():
                    p.unlink()
                self.datetime.now.return_value = dt.datetime(2026, 9, 12, tzinfo=dt.timezone.utc)
                fragment, report = self.run_build(root, tracking_writer, workers=2)
                after = collections.Counter((root / "writes").read_text().splitlines())
                for prefix in before:
                    self.assertEqual(after[prefix], before[prefix], prefix)
                self.assertEqual(fragment, expected)
                self.assertEqual({p.name: p.read_bytes() for p in (root / "artifacts").iterdir()}, expected_bytes)
                self.datetime.now.return_value = dt.datetime(2026, 9, 11, tzinfo=dt.timezone.utc)

    def test_legacy_prepared_and_banked_shards_survive_additive_projection(self):
        expected, expected_bytes = self.reference()
        prepared = release._prepare_tail(self.connection, self.root, 32.0, {}, self.scan, release._uncached_step)
        with self.run_paths("legacy") as root:
            state = release._read_sweep_state(self_history_kappa=32, catalog_size=len(self.catalog))
            state["tailId"] = "old-tail"
            release._write_sweep_state(state)
            with TailCheckpoint(release.SWEEP_STATE_PATH.with_suffix(".tail"), "old-tail", root, None) as tail:
                tail.step("prepared", lambda: prepared)
                tail.step("narratives", lambda: {"legacy": "frozen"})
                release._write_tail_shards(self.connection, prepared, tail, root, tracking_writer, 1, indices=[0, 1])
                saved = tail.db.execute("SELECT name,value FROM stage ORDER BY name").fetchall()
                release._prepared_tail(self.connection, root, 32, self.scan, tail)
                for name, raw in saved:
                    self.assertEqual(tail.db.execute("SELECT value FROM stage WHERE name=?", (name,)).fetchone()[0], raw)
            fragment, report = self.run_build(root, tracking_writer, workers=3)
            self.assertEqual(collections.Counter((root / "writes").read_text().splitlines())["orbit-history-001"], 1)
            self.assertEqual(fragment, expected)
            self.assertEqual({p.name: p.read_bytes() for p in (root / "artifacts").iterdir()}, expected_bytes)

    def test_a_second_run_is_refused_rather_than_sharing_one_stage_store(self):
        """Two runs in one tail is the 2026-09-20 outage, not a slow build.

        The 14:30 slice and an operator's forced run were both inside this
        tail; each checked `has()` for a `cohort-range:` stage the other then
        inserted, and `UNIQUE constraint failed: stage.name` killed them both.
        A second run must decline at the door, having read nothing and written
        nothing, and must leave the first run's work entirely alone.
        """
        expected, _ = self.reference()
        with self.run_paths("concurrent") as root:
            before = release.SWEEP_STATE_PATH.read_bytes()
            # A real second process: POSIX record locks do not conflict with
            # the holder's own, so this cannot be faked inside this one.
            holder = subprocess.Popen(
                [sys.executable, "-c", LOCK_HOLDER,
                 str(release.SWEEP_STATE_PATH.with_suffix(".lock"))],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, start_new_session=True)
            try:
                self.assertEqual(holder.stdout.readline(), b"locked\n")
                with mock.patch.object(release, "_prepare_tail",
                                       side_effect=AssertionError("read the archive anyway")):
                    fragment, report = self.run_build(root)
                self.assertIsNone(fragment)
                self.assertEqual(report["status"], "busy")
                self.assertFalse(report["published"])
                self.assertEqual(report["heldBy"], str(holder.pid))
                # Nothing of the running sweep was touched, and nothing shipped.
                self.assertEqual(release.SWEEP_STATE_PATH.read_bytes(), before)
                self.assertIsNone(TailCheckpoint.status(
                    release.SWEEP_STATE_PATH.with_suffix(".tail")))
                self.assertFalse(release.FRAGMENT_PATH.exists())
            finally:
                holder.stdin.close()
                self.assertEqual(holder.wait(timeout=30), 0)
                holder.stdout.close()
            # Refusal is free: the very next run publishes the same bundle.
            fragment, report = self.run_build(root)
            self.assertEqual(report["status"], "swept")
            self.assertEqual(fragment, expected)

    def test_a_finished_tail_never_lends_its_stages_to_the_next_sweep(self):
        """`tailId` covers the other half: a NEW sweep starts from nothing.

        The publish clears the sweep state before the private workspace, so a
        machine that dies between the two leaves a finished tail's stages on
        disk. Those stages describe data the next sweep has re-read; adopting
        one would publish a mixture nobody could defend.
        """
        expected, expected_bytes = self.reference()
        with self.run_paths("next-sweep") as root:
            # Inside the patched paths: the production workspace is not ours.
            tail_root = release.SWEEP_STATE_PATH.with_suffix(".tail")
            fragment, report = self.run_build(root)
            self.assertTrue(report["published"])
            self.assertFalse(tail_root.exists())
            # Survive the publish exactly as a kill between the two clears would.
            with TailCheckpoint(tail_root, "finished-tail", root, None) as stale:
                stale.step("cohort-range:0", lambda: ["not an event"])
                stale.step("narratives", lambda: {"stale": "frozen"})
                stale.step("shard:000", lambda: None)
            release._write_sweep_state({
                "version": release.SWEEP_STATE_VERSION, "kappa": 32.0,
                "catalogSize": len(self.catalog), "startedAt": "2026-09-13T00:00:00Z",
                "resumeAfter": release.SWEPT_TO_END, "passed": self.scan,
            })
            for path in (root / "artifacts").iterdir():
                path.unlink()
            fragment, report = self.run_build(root)
            # A reused `cohort-range:` stage cannot reach the same bundle, and
            # the banked shard:000 would have shipped as an absent shard.
            self.assertEqual(report["status"], "swept")
            self.assertEqual(fragment, expected)
            self.assertEqual({p.name: p.read_bytes() for p in (root / "artifacts").iterdir()},
                             expected_bytes)
            self.assertFalse(tail_root.exists())

    def test_worker_failure_banks_other_completed_shards_without_publishing(self):
        with self.run_paths("worker-failure") as root:
            with self.assertRaisesRegex(OSError, "worker write failed"):
                self.run_build(root, failing_writer, workers=3)
            self.assertFalse(release.FRAGMENT_PATH.exists())
            self.assertTrue(release.SWEEP_STATE_PATH.exists())
            self.assertGreater(TailCheckpoint.status(release.SWEEP_STATE_PATH.with_suffix(".tail"))["shardsDone"], 0)
            fragment, report = self.run_build(root, workers=2)
            self.assertTrue(report["published"])


# Holds the sweep lock from another process until its stdin closes.
LOCK_HOLDER = """
import fcntl, sys
handle = open(sys.argv[1], "a+")
fcntl.lockf(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
handle.truncate(0)
handle.write(str(__import__("os").getpid()) + "\\n")
handle.flush()
sys.stdout.write("locked\\n")
sys.stdout.flush()
sys.stdin.read()
"""


def tracking_writer(root, prefix, value):
    with (root / "writes").open("a") as handle:
        handle.write(prefix + "\n")
    return TailResumeTests.writer(root, prefix, value)


def failing_writer(root, prefix, value):
    if prefix == "orbit-history-001":
        raise OSError("worker write failed")
    return TailResumeTests.writer(root, prefix, value)


class TailCheckpointTests(unittest.TestCase):
    def test_artifact_budget_and_missing_pin_fail_without_publishing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, digest = TailResumeTests.writer(root, "orbit-history-001", {"objects": []})
            with TailCheckpoint(root / "tail", "first", root, None) as tail:
                with mock.patch.object(tail, "ARTIFACT_BYTES", 1):
                    with self.assertRaisesRegex(RuntimeError, "retention budget"):
                        tail.pin(path, digest)
                self.assertEqual(list((root / "tail/artifacts").iterdir()), [])
                with self.assertRaisesRegex(FileNotFoundError, "missing checkpoint"):
                    tail.restore([{"path": path, "sha256": digest}], verify=False)

    def test_cohort_chunks_resume_in_order_using_the_whole_reference_population(self):
        observed = intervals(series(days=520))  # >2048 targets; no archive I/O
        whole = oe.detect_events(observed)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calls = []
            detect_one = oe._detect_one

            def tracked(interval, index, **kwargs):
                calls.append(interval.start_ms)
                self.assertEqual(len(index._intervals), len(observed))
                return detect_one(interval, index, **kwargs)

            with mock.patch.object(oe, "_detect_one", tracked):
                # Freeze expectations, then stop at the first completed batch.
                with TailCheckpoint(root / "tail", "cohort", root, None) as tail:
                    tail.step("cohort-expectations", oe.Expectations.load)
                    tail.deadline = 0
                    with self.assertRaises(TailPaused):
                        oe.detect_events(observed, checkpoint=tail.step)
                self.assertEqual(len(calls), 2048)
                with TailCheckpoint(root / "tail", "cohort", root, None) as tail:
                    resumed = oe.detect_events(observed, checkpoint=tail.step)
            self.assertEqual(calls, [i.start_ms for i in observed])
            self.assertEqual([e.as_dict() for e in resumed], [e.as_dict() for e in whole])

    def test_cohort_pool_exits_with_inherited_cooperative_term_handler(self):
        # Isolate and time-bound the formerly hanging Pool.__exit__ case.
        code = """
import signal, time
from pipeline.orbit_events import _cohort_pool
signal.signal(signal.SIGTERM, signal.SIG_IGN)
with _cohort_pool(2) as pool:
    assert pool.map(abs, [-1, -2]) == [1, 2]
    time.sleep(.1)  # workers are idle, waiting for their next task
"""
        process = subprocess.Popen([sys.executable, "-c", code], start_new_session=True)
        try:
            self.assertEqual(process.wait(timeout=15), 0)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()

    def test_parallel_checkpointed_cohort_equals_ordinary_detector(self):
        observed = intervals(series(days=12))
        whole = oe.detect_events(observed)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (TailCheckpoint(root / "tail", "cohort", root, None) as tail,
                  mock.patch.object(oe, "COHORT_PARALLEL_MINIMUM_INTERVALS", 1)):
                result = oe.detect_events(observed, workers=2, checkpoint=tail.step)
            self.assertEqual([e.as_dict() for e in result], [e.as_dict() for e in whole])

    def test_status_is_read_only_and_supersession_deletes_only_private_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with TailCheckpoint(root / "tail", "first", root, None) as tail:
                tail.step("shard:000", lambda: None)
            before = (root / "tail/stages.sqlite3").stat().st_mtime_ns
            self.assertEqual(TailCheckpoint.status(root / "tail")["shardsDone"], 1)
            self.assertEqual((root / "tail/stages.sqlite3").stat().st_mtime_ns, before)
            with TailCheckpoint(root / "tail", "second", root, None) as tail:
                self.assertEqual(tail.values("shard:"), [])

    def test_exception_never_marks_an_unfinished_stage_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with TailCheckpoint(root / "tail", "first", root, None) as tail:
                with self.assertRaisesRegex(ValueError, "unfinished"):
                    tail.step("broken", mock.Mock(side_effect=ValueError("unfinished")))
                self.assertEqual(tail.values("broken"), [])
                self.assertEqual(tail.step("broken", lambda: 42), 42)
