#!/usr/bin/env python3
"""Bound the disposable NOAA SWMF download cache on bigmem-PC.

Historical teaching bundles are immutable artifacts elsewhere. This directory is
only a retry/cache layer for recent operational GM and RBE source files.
"""

from __future__ import annotations

import argparse
import re
import time
from pathlib import Path


DAY = re.compile(r"\d{8}")
# mag_grid joined this cache on 2026-08-08. Left out, its ~774 KB per frame
# would have accumulated on /mnt/d forever at roughly 56 MB a day, because
# anything this pattern does not name is never a candidate for deletion.
MODEL_FILE = re.compile(
    r"(?:[yz]0_\d{8}T\d{4}_\d{8}T\d{6}|mag_grid_\d{8}T\d{4}_\d{8}T\d{6}\.txt|\d{8}_\d{6}_e\.fls)"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache_root", type=Path)
    parser.add_argument("--max-age-hours", type=float, default=96)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = args.cache_root.resolve()
    if (
        root.name != "swmf-cache"
        or root.parent.name != "space-explorer"
        or not root.is_dir()
        or root.is_symlink()
        or args.max_age_hours < 24
    ):
        raise RuntimeError(f"refusing unsafe SWMF cache root or retention: {root}")

    cutoff = time.time() - args.max_age_hours * 3600
    removed_count = 0
    removed_bytes = 0
    for day in root.iterdir():
        if not day.is_dir() or day.is_symlink() or DAY.fullmatch(day.name) is None:
            continue
        for path in day.iterdir():
            if not path.is_file() or path.is_symlink() or MODEL_FILE.fullmatch(path.name) is None:
                continue
            stat = path.stat()
            if stat.st_mtime >= cutoff:
                continue
            removed_count += 1
            removed_bytes += stat.st_size
            if not args.dry_run:
                path.unlink()
        if not args.dry_run and not any(day.iterdir()):
            day.rmdir()

    action = "would prune" if args.dry_run else "pruned"
    print(f"{action} {removed_count} cached NOAA model files ({removed_bytes} bytes) from {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
