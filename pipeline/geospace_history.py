#!/usr/bin/env python3
"""Accumulate NOAA operational SWMF/RBE geospace frames on bigmem and publish a
browser-selectable time sequence.

Why this file exists
--------------------
`pipeline/swmf.py` reduces whatever NOAA's *current* operational run exposes.
That is a six-frame, roughly 100-minute window, so a visitor who scrubbed the
site's time slider back even two hours correctly met ``NO DATA · BEFORE
COVERAGE``. Aurora and D-RAP already avoid that by snapshotting every exact
upstream frame on bigmem and republishing the accumulated sequence; this module
gives the geospace family the same treatment, following
``pipeline/aurora_history.py`` deliberately rather than inventing a second
pattern:

* one immutable JSON document per exact model valid time under
  ``/mnt/d/space-explorer/environment-history/geospace``;
* frames are only ever *reduced from data already fetched* - this module never
  performs a network request of any kind, so it cannot add load upstream;
* a genuinely missing time stays missing. Nothing here holds a stale frame,
  interpolates across a gap, or synthesises a frame that NOAA did not publish.

What is published, and why it is smaller than what is archived
--------------------------------------------------------------
A full geospace frame is about 434 KB gzipped, and roughly 70% of that is the
BATS-R-US cut-plane field data for the ``layer-geospace`` checkbox, which is
``hidden`` in ``index.html`` and enabled by no preset. Publishing 48 hours of
complete frames would mean an 8+ MB download for a layer nobody can switch on.

So the archive on disk keeps the **complete** frame (planes included, for the
phase-two volume work and for any future decision to un-hide the cut layer),
while the published sequence carries, for archived times, only the parts the
public site actually draws:

* ``radiationBelt`` - the visible layer, and
* ``structures``   - the model-derived boundary/streamline profiles, which also
  carry the frame valid time the radiation-belt legend reports.

The live NOAA window is published unchanged, complete with planes.

Published cadence
-----------------
The published archive is thinned onto a fixed UTC grid so the artifact stays a
bounded download. The cadence is the finest one on ``CADENCE_LADDER_MINUTES``
that keeps the archived frame count at or under ``MAX_PUBLISHED_ARCHIVE_FRAMES``
across the covered window, so a young archive is published at NOAA's native
20-minute cadence and a full 48-hour archive is published two-hourly. A uniform
cadence matters for more than tidiness: the browser refuses to bridge a gap
wider than 2.5x the sequence's median spacing, so a mixed dense/sparse sequence
would manufacture ``NO DATA`` holes in the middle of times we actually hold.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import datetime as dt
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Iterable


SNAPSHOT_SCHEMA = "noaa-swmf-geospace-snapshot.v1"
SNAPSHOT_NAME = re.compile(r"geospace-(\d{8})(\d{6})\.json")

# The site's time scrubber spans -48 h to +72 h. This is the backwards half.
PUBLISHED_HISTORY_HOURS = 48.0
# Bounds the on-demand download. 24 archived frames is roughly 3 MB gzipped on
# top of the live window; see the module docstring for the size accounting.
MAX_PUBLISHED_ARCHIVE_FRAMES = 24
# Every entry divides a UTC day exactly, so the published slots repeat daily and
# the artifact does not churn between five-minute publish cycles.
CADENCE_LADDER_MINUTES = (20, 40, 60, 120)
# Comfortably longer than the published window, so widening the window later
# does not require waiting for the archive to refill. About 280 MB on /mnt/d.
SNAPSHOT_RETENTION_HOURS = 96.0

# Keys of a reduced frame that an archived (non-live) frame publishes.
ARCHIVED_FRAME_KEYS = ("validAt", "leadMinutes", "runAt", "structures", "radiationBelt")


class GeospaceHistoryError(ValueError):
    """Raised when an archived geospace frame cannot be trusted or replayed."""


def utc_iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_utc(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a UTC offset")
    return parsed.astimezone(dt.timezone.utc)


def radiation_fingerprint(bundle: dict[str, Any]) -> dict[str, Any]:
    """Describe the RBE grid an archived frame must match to be replayable.

    NOAA can change the coupled RBE grid between runs. The browser decodes every
    frame against one bundle-level definition, so an archived frame from a
    different grid would be silently misdecoded rather than rejected. This is the
    check that stops that.
    """
    definition = bundle.get("radiationBelt")
    if not isinstance(definition, dict):
        raise GeospaceHistoryError("geospace bundle has no radiation-belt definition")
    try:
        return {
            "count": int(definition["count"]),
            "gridShape": dict(definition["gridShape"]),
            "energiesKev": [float(value) for value in definition["energiesKev"]],
            "pitchCoordinatesSin": [float(value) for value in definition["pitchCoordinatesSin"]],
            "innerBoundaryRe": float(definition["innerBoundaryRe"]),
            "encoding": dict(definition["encoding"]),
        }
    except (KeyError, TypeError, ValueError) as error:
        raise GeospaceHistoryError("geospace radiation-belt definition is malformed") from error


def plane_fingerprint(bundle: dict[str, Any]) -> dict[str, str]:
    """Digest the adaptive-grid coordinates so a future publisher can tell
    whether an archived frame's cut planes are still decodable against the
    current bundle. Only recorded; the published archive omits planes today."""
    planes = bundle.get("planes")
    if not isinstance(planes, dict):
        return {}
    digests: dict[str, str] = {}
    for name, plane in planes.items():
        encoded = plane.get("coordinatesI16") if isinstance(plane, dict) else None
        if isinstance(encoded, str):
            digests[str(name)] = hashlib.sha256(encoded.encode("ascii")).hexdigest()
    return digests


def snapshot_label(valid_at: str) -> str:
    digits = re.sub(r"[^0-9]", "", valid_at)
    if len(digits) < 14:
        raise GeospaceHistoryError(f"geospace valid time is not a full timestamp: {valid_at!r}")
    return digits[:14]


def snapshot_frames(snapshot_root: Path, bundle: dict[str, Any]) -> list[Path]:
    """Persist every exact frame of one live bundle, newest NOAA run winning.

    An existing snapshot is left alone unless the incoming frame comes from a
    later NOAA cycle, which is the same "latest run for this valid time" rule
    `pipeline/swmf.py` already applies when it selects source files. That keeps
    the HDD write volume proportional to genuinely new content rather than to
    the five-minute publish cadence.
    """
    frames = bundle.get("frames")
    if not isinstance(frames, list) or not frames:
        raise GeospaceHistoryError("geospace bundle contains no frame to snapshot")
    radiation = radiation_fingerprint(bundle)
    planes = plane_fingerprint(bundle)
    written: list[Path] = []
    for frame in frames:
        if not isinstance(frame, dict) or not isinstance(frame.get("validAt"), str):
            continue
        path = snapshot_root / f"geospace-{snapshot_label(frame['validAt'])}.json"
        if not _supersedes(path, frame):
            continue
        document = {
            "schemaVersion": SNAPSHOT_SCHEMA,
            "radiationBelt": radiation,
            "planeCoordinateDigests": planes,
            "frame": frame,
        }
        _atomic_write(path, json.dumps(document, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        written.append(path)
    return written


def prune_snapshots(snapshot_root: Path, *, older_than: dt.datetime) -> int:
    """Bound the archive. Only deletes files this module could have written."""
    if snapshot_root.name != "geospace" or not snapshot_root.is_dir() or snapshot_root.is_symlink():
        return 0
    removed = 0
    for path in snapshot_root.iterdir():
        if not path.is_file() or path.is_symlink():
            continue
        valid_at = _label_time(path.name)
        if valid_at is None or valid_at >= older_than.astimezone(dt.timezone.utc):
            continue
        with contextlib.suppress(OSError):
            path.unlink()
            removed += 1
    return removed


def published_cadence_minutes(
    snapshot_times: Iterable[dt.datetime],
    *,
    start: dt.datetime,
    end: dt.datetime,
) -> int:
    """Pick the finest fixed-grid cadence that fits the published frame budget."""
    covered = [time for time in snapshot_times if start <= time < end]
    if not covered:
        return CADENCE_LADDER_MINUTES[0]
    span_minutes = (end - min(covered)).total_seconds() / 60
    for cadence in CADENCE_LADDER_MINUTES:
        if span_minutes / cadence <= MAX_PUBLISHED_ARCHIVE_FRAMES:
            return cadence
    return CADENCE_LADDER_MINUTES[-1]


def on_cadence(valid_at: dt.datetime, cadence_minutes: int) -> bool:
    """True when a valid time lands on the fixed UTC grid for this cadence."""
    return int(valid_at.timestamp()) % (cadence_minutes * 60) == 0


def load_snapshot_frames(
    snapshot_root: Path,
    *,
    start: dt.datetime,
    end: dt.datetime,
    cadence_minutes: int,
    radiation: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return archived frames on the cadence grid, reduced to what the site draws.

    Candidate files are filtered by their filename timestamp before anything is
    read, because a full geospace snapshot is about a megabyte and the publisher
    runs every five minutes.
    """
    if not snapshot_root.is_dir():
        return []
    start = start.astimezone(dt.timezone.utc)
    end = end.astimezone(dt.timezone.utc)
    frames: dict[str, dict[str, Any]] = {}
    for path in sorted(snapshot_root.glob("geospace-*.json")):
        valid_at = _label_time(path.name)
        if valid_at is None or valid_at < start or valid_at >= end:
            continue
        if not on_cadence(valid_at, cadence_minutes):
            continue
        try:
            document = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(document, dict) or document.get("radiationBelt") != radiation:
            continue
        frame = document.get("frame")
        if not isinstance(frame, dict) or frame.get("validAt") != utc_iso(valid_at):
            continue
        reduced = archived_frame(frame)
        if reduced is not None and valid_frame(reduced, radiation):
            frames[reduced["validAt"]] = reduced
    ordered = [frames[key] for key in sorted(frames, key=parse_utc)]
    return ordered[-MAX_PUBLISHED_ARCHIVE_FRAMES:]


def archived_frame(frame: dict[str, Any]) -> dict[str, Any] | None:
    """Reduce a complete archived frame to the published archive payload.

    ``planes`` is emitted as an empty object rather than dropped. The browser's
    cut-plane builder indexes ``frame.planes[plane]`` without a guard on
    ``frame.planes`` itself, so an absent key would throw and take the visible
    radiation-belt layer down with it; an empty object takes the existing
    "this plane has no field data" path and draws nothing, which is the honest
    outcome. Verified against `src/geospace-runtime.ts`.
    """
    reduced = {key: frame[key] for key in ARCHIVED_FRAME_KEYS if key in frame}
    if not {"validAt", "runAt", "radiationBelt"}.issubset(reduced):
        return None
    reduced["planes"] = {}
    return reduced


def valid_frame(frame: Any, radiation: dict[str, Any]) -> bool:
    """Structurally verify one frame against the bundle's RBE definition."""
    if not isinstance(frame, dict):
        return False
    belt = frame.get("radiationBelt")
    if not isinstance(belt, dict):
        return False
    count = radiation["count"]
    pitch_count = len(radiation["pitchCoordinatesSin"])
    energies = {str(round(value, 3)) for value in radiation["energiesKev"]}
    try:
        parse_utc(str(frame["validAt"]))
        parse_utc(str(frame["runAt"]))
        float(frame.get("leadMinutes", 0))
        if len(_decode(belt["coordinatesU16"])) != count * 2 * 2:
            return False
        for key, expected in (("electronFluxU16", count), ("pitchResolvedElectronFluxU16", count * pitch_count)):
            channels = belt[key]
            if not isinstance(channels, dict) or set(channels) != energies:
                return False
            if any(len(_decode(value)) != expected * 2 for value in channels.values()):
                return False
    except (KeyError, TypeError, ValueError):
        return False
    return True


def merge_frames(
    archived: Iterable[dict[str, Any]],
    live: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """One frame per valid time, with the complete live frame always winning."""
    merged: dict[str, dict[str, Any]] = {}
    for frame in archived:
        merged[frame["validAt"]] = frame
    for frame in live:
        merged[frame["validAt"]] = frame
    return [merged[key] for key in sorted(merged, key=parse_utc)]


def history_metadata(
    *,
    cadence_minutes: int,
    archived_count: int,
    live_count: int,
    retained_snapshots: int,
) -> dict[str, Any]:
    """Say plainly what each published frame does and does not carry."""
    return {
        "method": (
            "exact NOAA operational SWMF/RBE frames reduced once when they are current and "
            "archived on bigmem; nothing is refetched, reconstructed, or interpolated"
        ),
        "publishedCadenceMinutes": cadence_minutes,
        "sourceCadenceMinutes": 20,
        "archivedFrameCount": archived_count,
        "liveFrameCount": live_count,
        "retainedSnapshotCount": retained_snapshots,
        "snapshotRetentionHours": SNAPSHOT_RETENTION_HOURS,
        "archivedFramePayload": sorted(ARCHIVED_FRAME_KEYS),
        "archivedFrameOmits": ["planes"],
        "archivedFrameEmptyPlanes": (
            "Archived frames carry an empty planes object, not cut-plane field data. "
            "It is present only because the browser indexes into it unguarded."
        ),
        "archivedFrameOmissionReason": (
            "The BATS-R-US cut-plane fields are about 70% of a frame and feed only the hidden "
            "layer-geospace control. Complete frames including planes are retained on bigmem; "
            "they are withheld from the published archive to keep this an on-demand download "
            "rather than an 8 MB one."
        ),
        "cadenceReason": (
            "The published archive is thinned onto a fixed UTC grid to bound the download. "
            "The cadence is uniform across the window on purpose: the browser will not bridge "
            "a gap wider than 2.5x the median frame spacing, so a mixed dense/sparse sequence "
            "would report no data at times that are actually held."
        ),
        "notUsed": "temporal interpolation, stale-frame holding, or any reconstruction of a time NOAA did not publish",
    }


CACHE_PLANE_NAME = re.compile(r"(y0|z0)_(\d{8}T\d{4})_(\d{8}T\d{6})")
CACHE_RADIATION_NAME = re.compile(r"(\d{8}_\d{6})_e\.fls")
CACHE_PLANE_ROLES = {"z0": "equatorial", "y0": "meridional"}


def cached_source_frames(cache_root: Path) -> dict[dt.datetime, dict[str, Any]]:
    """Index complete NOAA source triples already sitting in the download cache.

    `pipeline/swmf.py` keeps every GM cut and RBE file it downloads under
    /mnt/d for up to 96 hours so a retry never refetches. Those bytes are a
    lawful, already-paid-for backfill source: replaying them costs NOAA nothing.
    A valid time is usable only when both cut planes and the RBE solution are
    present, and the newest NOAA cycle wins, exactly as the live selector does.
    """
    planes: dict[dt.datetime, dict[str, tuple[str, Path]]] = {}
    radiation: dict[dt.datetime, Path] = {}
    if not cache_root.is_dir():
        return {}
    for day in sorted(cache_root.iterdir()):
        if not day.is_dir() or day.is_symlink():
            continue
        for path in sorted(day.iterdir()):
            if not path.is_file() or path.is_symlink():
                continue
            plane_match = CACHE_PLANE_NAME.fullmatch(path.name)
            if plane_match:
                upstream, cycle, valid_text = plane_match.groups()
                valid_at = _cache_time(valid_text)
                previous = planes.setdefault(valid_at, {}).get(upstream)
                if previous is None or cycle > previous[0]:
                    planes[valid_at][upstream] = (cycle, path)
                continue
            radiation_match = CACHE_RADIATION_NAME.fullmatch(path.name)
            if radiation_match:
                radiation[_cache_time(radiation_match.group(1).replace("_", "T"))] = path
    complete: dict[dt.datetime, dict[str, Any]] = {}
    for valid_at, found in planes.items():
        if set(found) != set(CACHE_PLANE_ROLES) or valid_at not in radiation:
            continue
        complete[valid_at] = {
            "runAt": _cache_time(max(cycle for cycle, _ in found.values()) + "00"),
            "planes": {CACHE_PLANE_ROLES[key]: path for key, (_, path) in found.items()},
            "radiation": radiation[valid_at],
        }
    return dict(sorted(complete.items()))


def backfill_from_cache(
    snapshot_root: Path,
    cache_root: Path,
    *,
    limit: int | None = None,
    verbose: bool = False,
) -> tuple[int, int]:
    """Reduce cached NOAA source files into archive snapshots. Never fetches."""
    from pipeline.swmf import RADIATION_ENCODING, reduce_local_frame

    written = 0
    skipped = 0
    for valid_at, sources in cached_source_frames(cache_root).items():
        if limit is not None and written >= limit:
            break
        path = snapshot_root / f"geospace-{valid_at.strftime('%Y%m%d%H%M%S')}.json"
        if path.exists():
            skipped += 1
            continue
        try:
            reduced = reduce_local_frame(
                valid_at=valid_at,
                run_at=sources["runAt"],
                plane_bodies={name: file.read_bytes() for name, file in sources["planes"].items()},
                radiation_body=sources["radiation"].read_bytes(),
            )
        except Exception as error:  # noqa: BLE001 - one bad cached file must not stop the rest
            skipped += 1
            if verbose:
                print(f"skipped {valid_at:%Y-%m-%dT%H:%M:%S}Z: {error}")
            continue
        radiation = reduced["radiation"]
        document = {
            "schemaVersion": SNAPSHOT_SCHEMA,
            "radiationBelt": {
                "count": radiation["count"],
                "gridShape": radiation["gridShape"],
                "energiesKev": radiation["energiesKev"],
                "pitchCoordinatesSin": radiation["pitchCoordinatesSin"],
                "innerBoundaryRe": radiation["innerBoundaryRe"],
                "encoding": dict(RADIATION_ENCODING),
            },
            "planeCoordinateDigests": {
                name: hashlib.sha256(plane["coordinatesI16"].encode("ascii")).hexdigest()
                for name, plane in reduced["planes"].items()
            },
            "frame": reduced["frame"],
        }
        _atomic_write(path, json.dumps(document, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        written += 1
        if verbose:
            print(f"archived {valid_at:%Y-%m-%dT%H:%M:%S}Z")
    return written, skipped


def _cache_time(value: str) -> dt.datetime:
    return dt.datetime.strptime(value.replace("_", "T"), "%Y%m%dT%H%M%S").replace(tzinfo=dt.timezone.utc)


def _supersedes(path: Path, frame: dict[str, Any]) -> bool:
    """True when this frame should replace (or create) the snapshot on disk."""
    if not path.exists():
        return True
    try:
        existing = json.loads(path.read_text())["frame"]
        return parse_utc(str(frame["runAt"])) > parse_utc(str(existing["runAt"]))
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        # An unreadable or malformed snapshot is worth replacing with a good one.
        return True


def _label_time(name: str) -> dt.datetime | None:
    match = SNAPSHOT_NAME.fullmatch(name)
    if not match:
        return None
    try:
        return dt.datetime.strptime(match.group(1) + match.group(2), "%Y%m%d%H%M%S").replace(
            tzinfo=dt.timezone.utc
        )
    except ValueError:
        return None


def snapshot_times(snapshot_root: Path) -> list[dt.datetime]:
    if not snapshot_root.is_dir():
        return []
    times = [_label_time(path.name) for path in snapshot_root.glob("geospace-*.json")]
    return sorted(time for time in times if time is not None)


def _decode(value: Any) -> bytes:
    if not isinstance(value, str):
        raise TypeError("expected base64 text")
    return base64.b64decode(value, validate=True)


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)


def main() -> int:
    """Offline maintenance for the archive. No subcommand here touches a network."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--snapshot-root",
        type=Path,
        default=Path("/mnt/d/space-explorer/environment-history/geospace"),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status", help="report what the archive currently covers")
    prune = subparsers.add_parser("prune", help="delete snapshots older than the retention horizon")
    prune.add_argument("--retention-hours", type=float, default=SNAPSHOT_RETENTION_HOURS)
    backfill = subparsers.add_parser(
        "backfill",
        help="reduce NOAA source files already in the bigmem download cache (offline)",
    )
    backfill.add_argument("--cache-root", type=Path, default=Path("/mnt/d/space-explorer/swmf-cache"))
    backfill.add_argument("--limit", type=int)
    backfill.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if args.command == "backfill":
        written, skipped = backfill_from_cache(
            args.snapshot_root,
            args.cache_root,
            limit=args.limit,
            verbose=not args.quiet,
        )
        print(f"archived {written} cached geospace frame(s); skipped {skipped}")
        return 0

    times = snapshot_times(args.snapshot_root)
    if args.command == "prune":
        cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=args.retention_hours)
        print(f"pruned {prune_snapshots(args.snapshot_root, older_than=cutoff)} geospace snapshots")
        return 0

    if not times:
        print(f"no geospace snapshots under {args.snapshot_root}")
        return 0
    now = dt.datetime.now(dt.timezone.utc)
    start = now - dt.timedelta(hours=PUBLISHED_HISTORY_HOURS)
    cadence = published_cadence_minutes(times, start=start, end=now)
    on_grid = [time for time in times if time >= start and on_cadence(time, cadence)]
    print(
        f"{len(times)} snapshots, {utc_iso(times[0])} to {utc_iso(times[-1])}; "
        f"published cadence {cadence} min gives {len(on_grid)} archived frame(s) "
        f"inside the {PUBLISHED_HISTORY_HOURS:g}-hour window"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
