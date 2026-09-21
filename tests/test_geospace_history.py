from __future__ import annotations

import base64
import datetime as dt
import json
import struct
import tempfile
import unittest
from pathlib import Path

from pipeline.geospace_history import (
    CADENCE_LADDER_MINUTES,
    MAX_PUBLISHED_ARCHIVE_FRAMES,
    archived_frame,
    cached_source_frames,
    load_snapshot_frames,
    merge_frames,
    on_cadence,
    prune_snapshots,
    published_cadence_minutes,
    radiation_fingerprint,
    snapshot_frames,
    snapshot_times,
    valid_frame,
)


POINT_COUNT = 4
PITCH_COUNT = 2
ENERGIES = [1.0, 2.5]


def encoded(count: int, fill: int = 7) -> str:
    return base64.b64encode(struct.pack(f"<{count}H", *([fill] * count))).decode("ascii")


def radiation_definition() -> dict[str, object]:
    return {
        "count": POINT_COUNT,
        "gridShape": {"radialCount": 2, "magneticLocalTimeCount": 2},
        "energiesKev": list(ENERGIES),
        "pitchCoordinatesSin": [0.5, 1.0],
        "pitchAnglesDegrees": [30.0, 90.0],
        "pitchResolvedOrdering": "equatorial-point-major, pitch-index-minor",
        "innerBoundaryRe": 1.5,
        "encoding": {"scale": "log10", "minimum": -2.0, "maximum": 9.0},
    }


def belt_payload() -> dict[str, object]:
    return {
        "coordinatesU16": encoded(POINT_COUNT * 2),
        "electronFluxU16": {str(energy): encoded(POINT_COUNT) for energy in ENERGIES},
        "pitchResolvedElectronFluxU16": {
            str(energy): encoded(POINT_COUNT * PITCH_COUNT) for energy in ENERGIES
        },
    }


def frame(valid_at: str, *, run_at: str = "2026-08-07T12:00:00Z") -> dict[str, object]:
    """A complete frame, shaped exactly like `pipeline/swmf.py` emits one."""
    return {
        "validAt": valid_at,
        "leadMinutes": 20,
        "runAt": run_at,
        "planes": {
            "equatorial": {"fieldsU16": {"density": encoded(8)}, "fieldMasksU8": {"density": encoded(4)}},
            "meridional": {"fieldsU16": {"density": encoded(8)}, "fieldMasksU8": {"density": encoded(4)}},
        },
        "structures": {
            "equatorial": {"bowShockRadiusU16": encoded(4)},
            "meridional": {"bowShockRadiusU16": encoded(4)},
        },
        "radiationBelt": belt_payload(),
    }


def bundle(valid_times: list[str]) -> dict[str, object]:
    return {
        "schema": 1,
        "planes": {
            "equatorial": {"count": 4, "coordinatesI16": encoded(8), "boundsRe": [-55, 25, -35, 35]},
            "meridional": {"count": 4, "coordinatesI16": encoded(8), "boundsRe": [-55, 25, -35, 35]},
        },
        "radiationBelt": radiation_definition(),
        "frames": [frame(valid_at) for valid_at in valid_times],
    }


def utc(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


class SnapshotTests(unittest.TestCase):
    def test_writes_one_file_per_exact_valid_time(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "geospace"
            written = snapshot_frames(root, bundle(["2026-08-07T22:00:00Z", "2026-08-07T22:20:00Z"]))
            self.assertEqual(
                sorted(path.name for path in written),
                ["geospace-20260807220000.json", "geospace-20260807222000.json"],
            )
            document = json.loads(written[0].read_text())
            self.assertEqual(document["radiationBelt"], radiation_fingerprint(bundle([])))
            # The archive keeps the complete frame, cut planes included, even
            # though the published sequence withholds them.
            self.assertIn("planes", document["frame"])
            self.assertEqual(set(document["planeCoordinateDigests"]), {"equatorial", "meridional"})

    def test_keeps_the_newest_noaa_run_and_leaves_older_reissues_alone(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "geospace"
            first = bundle(["2026-08-07T22:00:00Z"])
            snapshot_frames(root, first)
            path = root / "geospace-20260807220000.json"

            stale = bundle(["2026-08-07T22:00:00Z"])
            stale["frames"][0]["runAt"] = "2026-08-07T06:00:00Z"
            stale["frames"][0]["leadMinutes"] = 960
            self.assertEqual(snapshot_frames(root, stale), [])
            self.assertEqual(json.loads(path.read_text())["frame"]["leadMinutes"], 20)

            newer = bundle(["2026-08-07T22:00:00Z"])
            newer["frames"][0]["runAt"] = "2026-08-07T21:00:00Z"
            newer["frames"][0]["leadMinutes"] = 60
            self.assertEqual(len(snapshot_frames(root, newer)), 1)
            self.assertEqual(json.loads(path.read_text())["frame"]["leadMinutes"], 60)


class PublishedArchiveTests(unittest.TestCase):
    def archive(self, root: Path, valid_times: list[str]) -> None:
        snapshot_frames(root, bundle(valid_times))

    def test_publishes_only_cadence_grid_frames_inside_the_window(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "geospace"
            self.archive(root, [
                "2026-08-07T20:00:00Z",
                "2026-08-07T20:20:00Z",
                "2026-08-07T20:40:00Z",
                "2026-08-07T21:00:00Z",
            ])
            published = load_snapshot_frames(
                root,
                start=utc("2026-08-07T00:00:00Z"),
                end=utc("2026-08-07T22:00:00Z"),
                cadence_minutes=60,
                radiation=radiation_fingerprint(bundle([])),
            )
            self.assertEqual(
                [item["validAt"] for item in published],
                ["2026-08-07T20:00:00Z", "2026-08-07T21:00:00Z"],
            )

    def test_archived_frames_drop_planes_but_keep_the_frame_time_carrier(self) -> None:
        """The radiation-belt legend reports the valid time of the structure
        frame. Dropping `structures` to save bytes would silently blank the one
        label that tells a visitor which model time they are looking at."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "geospace"
            self.archive(root, ["2026-08-07T20:00:00Z"])
            published = load_snapshot_frames(
                root,
                start=utc("2026-08-07T00:00:00Z"),
                end=utc("2026-08-07T22:00:00Z"),
                cadence_minutes=20,
                radiation=radiation_fingerprint(bundle([])),
            )
            self.assertEqual(len(published), 1)
            # Empty, not absent: src/geospace-runtime.ts reads frame.planes[plane]
            # without guarding frame.planes, so a missing key would throw and take
            # the visible radiation-belt layer down with the hidden cut layer.
            self.assertEqual(published[0]["planes"], {})
            self.assertIn("structures", published[0])
            self.assertIn("radiationBelt", published[0])
            self.assertEqual(published[0]["validAt"], "2026-08-07T20:00:00Z")
            self.assertEqual(published[0]["runAt"], "2026-08-07T12:00:00Z")

    def test_refuses_frames_recorded_against_a_different_rbe_grid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "geospace"
            regridded = bundle(["2026-08-07T20:00:00Z"])
            regridded["radiationBelt"]["energiesKev"] = [1.0, 9.9]
            snapshot_frames(root, regridded)
            published = load_snapshot_frames(
                root,
                start=utc("2026-08-07T00:00:00Z"),
                end=utc("2026-08-07T22:00:00Z"),
                cadence_minutes=20,
                radiation=radiation_fingerprint(bundle([])),
            )
            self.assertEqual(published, [])

    def test_refuses_a_frame_whose_flux_payload_is_the_wrong_length(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "geospace"
            self.archive(root, ["2026-08-07T20:00:00Z"])
            path = root / "geospace-20260807200000.json"
            document = json.loads(path.read_text())
            document["frame"]["radiationBelt"]["pitchResolvedElectronFluxU16"]["1.0"] = encoded(3)
            path.write_text(json.dumps(document))
            self.assertEqual(
                load_snapshot_frames(
                    root,
                    start=utc("2026-08-07T00:00:00Z"),
                    end=utc("2026-08-07T22:00:00Z"),
                    cadence_minutes=20,
                    radiation=radiation_fingerprint(bundle([])),
                ),
                [],
            )

    def test_a_missing_slot_stays_missing_rather_than_borrowing_a_neighbour(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "geospace"
            self.archive(root, ["2026-08-07T18:00:00Z", "2026-08-07T20:00:00Z"])
            published = load_snapshot_frames(
                root,
                start=utc("2026-08-07T00:00:00Z"),
                end=utc("2026-08-07T22:00:00Z"),
                cadence_minutes=60,
                radiation=radiation_fingerprint(bundle([])),
            )
            self.assertEqual(
                [item["validAt"] for item in published],
                ["2026-08-07T18:00:00Z", "2026-08-07T20:00:00Z"],
            )

    def test_never_publishes_more_than_the_frame_budget(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "geospace"
            base = utc("2026-08-06T00:00:00Z")
            self.archive(root, [
                (base + dt.timedelta(minutes=20 * step)).isoformat().replace("+00:00", "Z")
                for step in range(150)
            ])
            published = load_snapshot_frames(
                root,
                start=base,
                end=base + dt.timedelta(hours=50),
                cadence_minutes=20,
                radiation=radiation_fingerprint(bundle([])),
            )
            self.assertEqual(len(published), MAX_PUBLISHED_ARCHIVE_FRAMES)


class CadenceTests(unittest.TestCase):
    def times(self, hours: float) -> list[dt.datetime]:
        end = utc("2026-08-07T22:00:00Z")
        count = int(hours * 3) + 1
        return [end - dt.timedelta(minutes=20 * step) for step in range(count)]

    def test_young_archive_publishes_at_the_native_cadence(self) -> None:
        end = utc("2026-08-07T22:00:00Z")
        self.assertEqual(
            published_cadence_minutes(self.times(4), start=end - dt.timedelta(hours=48), end=end),
            20,
        )

    def test_full_archive_coarsens_to_stay_inside_the_frame_budget(self) -> None:
        end = utc("2026-08-07T22:00:00Z")
        self.assertEqual(
            published_cadence_minutes(self.times(48), start=end - dt.timedelta(hours=48), end=end),
            120,
        )

    def test_every_ladder_step_keeps_the_archive_inside_the_frame_budget(self) -> None:
        end = utc("2026-08-07T22:00:00Z")
        for hours in (2, 6, 8, 9, 16, 17, 24, 25, 36, 48):
            with self.subTest(hours=hours):
                cadence = published_cadence_minutes(
                    self.times(hours), start=end - dt.timedelta(hours=48), end=end
                )
                self.assertIn(cadence, CADENCE_LADDER_MINUTES)
                self.assertLessEqual(hours * 60 / cadence, MAX_PUBLISHED_ARCHIVE_FRAMES)

    def test_the_published_sequence_never_manufactures_a_bridging_gap(self) -> None:
        """The browser refuses to bridge a gap wider than 2.5x the median frame
        spacing and reports NO DATA instead. A published sequence must therefore
        never contain a gap that its own median cannot justify, or scrubbing to
        a time we actually hold would show nothing."""
        end = utc("2026-08-07T22:00:00Z")
        live = [end + dt.timedelta(minutes=20 * step) for step in range(-2, 4)]
        for hours in (2, 6, 8, 9, 16, 17, 24, 25, 36, 48):
            with self.subTest(hours=hours):
                stored = self.times(hours)
                archive_end = min(live)
                cadence = published_cadence_minutes(
                    stored, start=end - dt.timedelta(hours=48), end=archive_end
                )
                archived = [
                    time for time in sorted(stored)
                    if time < archive_end and on_cadence(time, cadence)
                ][-MAX_PUBLISHED_ARCHIVE_FRAMES:]
                sequence = archived + live
                gaps = sorted(
                    (later - earlier).total_seconds() / 60
                    for earlier, later in zip(sequence, sequence[1:])
                )
                self.assertTrue(gaps)
                median = gaps[len(gaps) // 2]
                self.assertLessEqual(max(gaps), median * 2.5)

    def test_cadence_grid_is_anchored_to_absolute_utc(self) -> None:
        self.assertTrue(on_cadence(utc("2026-08-07T22:00:00Z"), 120))
        self.assertFalse(on_cadence(utc("2026-08-07T21:00:00Z"), 120))
        self.assertTrue(on_cadence(utc("2026-08-07T21:00:00Z"), 60))
        self.assertTrue(on_cadence(utc("2026-08-07T21:20:00Z"), 20))
        self.assertFalse(on_cadence(utc("2026-08-07T21:10:00Z"), 20))


class MergeAndRetentionTests(unittest.TestCase):
    def test_the_complete_live_frame_wins_a_shared_valid_time(self) -> None:
        live = frame("2026-08-07T22:00:00Z")
        archived = archived_frame(frame("2026-08-07T22:00:00Z"))
        merged = merge_frames([archived, archived_frame(frame("2026-08-07T20:00:00Z"))], [live])
        self.assertEqual([item["validAt"] for item in merged], [
            "2026-08-07T20:00:00Z",
            "2026-08-07T22:00:00Z",
        ])
        self.assertNotEqual(merged[1]["planes"], {})
        self.assertEqual(merged[0]["planes"], {})

    def test_prune_removes_only_old_snapshots_it_could_have_written(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "geospace"
            snapshot_frames(root, bundle(["2026-08-05T00:00:00Z", "2026-08-07T20:00:00Z"]))
            foreign = root / "notes.txt"
            foreign.write_text("not mine")
            removed = prune_snapshots(root, older_than=utc("2026-08-06T00:00:00Z"))
            self.assertEqual(removed, 1)
            self.assertTrue(foreign.exists())
            self.assertEqual(
                [time.isoformat() for time in snapshot_times(root)],
                ["2026-08-07T20:00:00+00:00"],
            )

    def test_prune_refuses_a_directory_that_is_not_the_geospace_archive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "aurora"
            snapshot_frames(root, bundle(["2026-08-05T00:00:00Z"]))
            self.assertEqual(prune_snapshots(root, older_than=utc("2026-08-06T00:00:00Z")), 0)
            self.assertEqual(len(list(root.iterdir())), 1)

    def test_valid_frame_rejects_an_unknown_energy_channel_set(self) -> None:
        candidate = archived_frame(frame("2026-08-07T20:00:00Z"))
        candidate["radiationBelt"]["electronFluxU16"] = {"1.0": encoded(POINT_COUNT)}
        self.assertFalse(valid_frame(candidate, radiation_fingerprint(bundle([]))))


class CachedSourceTests(unittest.TestCase):
    def test_pairs_only_complete_triples_and_prefers_the_newest_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            day = cache / "20260807"
            day.mkdir()
            for name in (
                "y0_20260807T1200_20260807T200000",
                "z0_20260807T1200_20260807T200000",
                "z0_20260807T1800_20260807T200000",
                "20260807_200000_e.fls",
                "y0_20260807T1200_20260807T202000",
            ):
                (day / name).write_bytes(b"x")
            found = cached_source_frames(cache)
            self.assertEqual([time.isoformat() for time in found], ["2026-08-07T20:00:00+00:00"])
            entry = next(iter(found.values()))
            self.assertEqual(entry["runAt"], utc("2026-08-07T18:00:00Z"))
            self.assertEqual(entry["planes"]["equatorial"].name, "z0_20260807T1800_20260807T200000")


class ReleaseBundleTests(unittest.TestCase):
    """Exercise the real publish path, with the one NOAA call stubbed out.

    This project has already shipped bugs with green tests over a production
    path the tests never executed, so the helpers above are not enough on their
    own: `build_geospace_release_bundle` itself has to run.
    """

    def build(self, root: Path, *, retrieved_at: dt.datetime, live: list[str]):
        from pipeline import build_release

        # The publish path now reduces the ground magnetic perturbation from the
        # same run, so the stub returns the pair the real reducer returns. None
        # for the ground bundle is the honest case where mag_grid was unusable,
        # and asserting the geospace bundle still comes back is the point.
        original = build_release.build_geospace_and_ground_bundles
        build_release.build_geospace_and_ground_bundles = lambda now=None: (bundle(live), None)
        try:
            geospace, ground = build_release.build_geospace_release_bundle(root, retrieved_at=retrieved_at)
            self.assertIsNone(ground)
            return geospace
        finally:
            build_release.build_geospace_and_ground_bundles = original

    def live_window(self, anchor: dt.datetime) -> list[str]:
        return [
            (anchor + dt.timedelta(minutes=20 * step)).isoformat().replace("+00:00", "Z")
            for step in range(6)
        ]

    def test_first_run_publishes_only_the_live_window_and_says_so(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "geospace"
            retrieved_at = utc("2026-08-07T23:05:00Z")
            anchor = utc("2026-08-07T22:00:00Z")
            result = self.build(root, retrieved_at=retrieved_at, live=self.live_window(anchor))
            self.assertEqual(len(result["frames"]), 6)
            self.assertEqual(result["history"]["archivedFrameCount"], 0)
            self.assertFalse(result["time"]["coverageComplete"])
            self.assertEqual(
                result["time"]["noDataIntervals"][0]["reason"], "before-bigmem-accumulation"
            )
            # The live window is now on disk for the next cycle.
            self.assertEqual(len(snapshot_times(root)), 6)

    def test_a_later_run_republishes_the_archived_window_as_one_sequence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "geospace"
            anchor = utc("2026-08-07T00:00:00Z")
            # Twelve consecutive operational windows, twenty minutes apart.
            for step in range(12):
                moment = anchor + dt.timedelta(minutes=20 * step)
                self.build(
                    root,
                    retrieved_at=moment + dt.timedelta(minutes=65),
                    live=self.live_window(moment),
                )
            final = self.build(
                root,
                retrieved_at=anchor + dt.timedelta(minutes=20 * 11, hours=1),
                live=self.live_window(anchor + dt.timedelta(minutes=20 * 11)),
            )
            self.assertGreater(len(final["frames"]), 6)
            self.assertGreater(final["history"]["archivedFrameCount"], 0)
            self.assertEqual(final["history"]["liveFrameCount"], 6)
            # Widened coverage: the sequence now starts before the live window.
            self.assertLess(
                utc(final["time"]["availableFrom"]),
                utc(final["frames"][-6]["validAt"]),
            )
            times = [utc(item["validAt"]) for item in final["frames"]]
            self.assertEqual(times, sorted(set(times)))
            # Archived frames withhold the hidden cut planes; live frames keep them.
            self.assertTrue(all(item["planes"] for item in final["frames"][-6:]))
            self.assertTrue(all(item["planes"] == {} for item in final["frames"][:-6]))
            self.assertTrue(all("radiationBelt" in item for item in final["frames"]))
            self.assertEqual(final["history"]["archivedFrameOmits"], ["planes"])

    def test_an_unusable_archive_still_publishes_the_live_window(self) -> None:
        """A full or unmounted /mnt/d must not cost the site a geospace layer
        whose live NOAA reduction already succeeded."""
        with tempfile.TemporaryDirectory() as directory:
            blocked = Path(directory) / "not-a-directory"
            blocked.write_text("this is a file, so the archive cannot be written here")
            result = self.build(
                blocked / "geospace",
                retrieved_at=utc("2026-08-07T23:05:00Z"),
                live=self.live_window(utc("2026-08-07T22:00:00Z")),
            )
            self.assertEqual(len(result["frames"]), 6)
            self.assertEqual(result["history"]["archivedFrameCount"], 0)
            self.assertFalse(result["time"]["coverageComplete"])

    def test_coverage_reports_a_real_hole_instead_of_smoothing_over_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "geospace"
            anchor = utc("2026-08-07T00:00:00Z")
            for step in list(range(6)) + list(range(12, 18)):
                moment = anchor + dt.timedelta(minutes=20 * step)
                self.build(
                    root,
                    retrieved_at=moment + dt.timedelta(minutes=65),
                    live=self.live_window(moment),
                )
            final = self.build(
                root,
                retrieved_at=anchor + dt.timedelta(minutes=20 * 17, hours=1),
                live=self.live_window(anchor + dt.timedelta(minutes=20 * 17)),
            )
            self.assertFalse(final["time"]["coverageComplete"])
            self.assertTrue(
                any(item["reason"] == "snapshot-gap" for item in final["time"]["noDataIntervals"]),
                final["time"]["noDataIntervals"],
            )


if __name__ == "__main__":
    unittest.main()
