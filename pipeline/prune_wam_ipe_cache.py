#!/usr/bin/env python3
"""Prune superseded WAM-IPE source files while protecting the current selection."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path

from .wam_ipe import (
    CYCLE,
    IPE05_FILE,
    IPE10_FILE,
    WAM_CACHE_RETENTION_HOURS,
    WFS_DAY,
    _parse_compact_time,
    _prune_cache,
    _select_frame_urls,
)


def _selected_cached_files(root: Path, now: dt.datetime) -> set[Path]:
    """Resolve the current keep-set from local files without contacting NOAA."""
    full_cycles = []
    peak_cycles = []
    for directory in root.glob("wfs.????????/??"):
        day_match = WFS_DAY.fullmatch(directory.parent.name)
        cycle_match = CYCLE.fullmatch(directory.name)
        if not day_match or not cycle_match:
            continue
        run_at = dt.datetime.strptime(
            day_match.group(1) + cycle_match.group(1), "%Y%m%d%H"
        ).replace(tzinfo=dt.timezone.utc)
        full_files = {}
        peak_files = {}
        for path in directory.glob("*.nc"):
            full_match = IPE10_FILE.fullmatch(path.name)
            peak_match = IPE05_FILE.fullmatch(path.name)
            if full_match and path.stat().st_size >= 20_000_000:
                full_files[_parse_compact_time(full_match.group(2))] = path
            elif peak_match and path.stat().st_size >= 50_000:
                peak_files[_parse_compact_time(peak_match.group(2))] = path
        if full_files:
            full_cycles.append((run_at, full_files))
        if peak_files:
            peak_cycles.append((run_at, peak_files))
    selected, _coverage = _select_frame_urls(now, full_cycles)
    peak_selected, _peak_coverage = _select_frame_urls(
        now,
        peak_cycles,
        source_cadence_minutes=5,
        published_cadence_minutes=5,
        product_label="cached ipe05 HmF2/NmF2",
    )
    return {
        Path(path)
        for _valid_at, _run_at, path in selected + peak_selected
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache_root", type=Path)
    parser.add_argument("--max-age-hours", type=float, default=WAM_CACHE_RETENTION_HOURS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = args.cache_root.resolve()
    os.environ["SPACE_EXPLORER_WAM_IPE_CACHE"] = str(root)
    now = dt.datetime.now(dt.timezone.utc)
    keep = _selected_cached_files(root, now)
    report = _prune_cache(
        keep,
        retention_hours=args.max_age_hours,
        dry_run=args.dry_run,
        now=now.timestamp(),
    )
    report.update(
        {
            "cacheRoot": str(root),
            "dryRun": args.dry_run,
            "retentionHours": args.max_age_hours,
            "protectedFiles": len(keep),
        }
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
