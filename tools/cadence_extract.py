#!/usr/bin/env python3
"""T3 step 1: stream the element histories T3 needs out of the archive, once.

Read-only, `PRAGMA query_only=1`, `nice`/idle-I/O at the caller, one pass in
NORAD order so the clustered `element_set` table is read sequentially. Writes
four flat binaries plus a JSON index; nothing here computes a periodogram, a
threshold or a result.

Registered population and screens: `docs/cadence-preregistration-20260921.md`
sections 3.1 and 5.3. Both are applied here identically to both classes, and
every object that fails a screen is counted and reported rather than dropped
in silence.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from pipeline import orbit_campaigns, orbit_history  # noqa: E402
from tools.cadence_core import (  # noqa: E402
    DAY_MS, PASSIVE_TYPES, WINDOW_DAYS, split_half,
)

MIN_ROWS = 200                       # prereg 3.1
MIN_BASELINE_DAYS = 2 * 365.25       # prereg 3.1


def _classes(db: sqlite3.Connection) -> dict[int, tuple[str, str, str]]:
    """norad -> (object_type, class, name), payload and passive only."""
    out = {}
    passive = {t.upper() for t in PASSIVE_TYPES}
    for norad, name, object_type in db.execute(
            "SELECT norad, name, object_type FROM object"):
        if object_type is None:
            continue
        upper = object_type.upper()
        if upper == "PAYLOAD":
            out[int(norad)] = (object_type, "payload", name or "")
        elif upper in passive:
            out[int(norad)] = (object_type, "passive", name or "")
    return out


def extract(db: sqlite3.Connection, out_dir: Path, limit: int | None = None,
            modulus: int = 1, progress_every: int = 500) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    classes = _classes(db)

    screened = db.execute(
        "SELECT norad, rows, min_epoch_ms, max_epoch_ms FROM object_rollup "
        "WHERE rows >= ? AND (max_epoch_ms - min_epoch_ms) >= ? ORDER BY norad",
        (MIN_ROWS, int(MIN_BASELINE_DAYS * DAY_MS))).fetchall()

    census = {"object_rollup_rows": len(screened), "kept": 0,
              "excluded_unlabelled": 0, "excluded_short_baseline_for_one_window": 0,
              "by_class": {"payload": 0, "passive": 0}}

    wanted = []
    for norad, rows, lo, hi in screened:
        norad = int(norad)
        if modulus > 1 and norad % modulus != 0:
            continue
        if norad not in classes:
            census["excluded_unlabelled"] += 1
            continue
        if (hi - lo) / DAY_MS < WINDOW_DAYS:
            census["excluded_short_baseline_for_one_window"] += 1
            continue
        wanted.append((norad, int(rows), int(lo), int(hi)))
    if limit:
        wanted = wanted[:limit]

    handles = {name: open(out_dir / f"{name}.bin", "wb")
               for name in ("epoch_ms", "mean_motion", "inclination", "eccentricity")}
    index = []
    offset = 0
    started = time.monotonic()
    for position, (norad, _rows, _lo, _hi) in enumerate(wanted):
        cursor = db.execute(
            "SELECT epoch_ms, mean_motion_q, inclination_q, eccentricity_q "
            "FROM element_set WHERE norad = ? ORDER BY epoch_ms", (norad,))
        block = np.array(cursor.fetchall(), dtype=np.int64)
        if block.size == 0 or block.shape[0] < MIN_ROWS:
            continue
        # Epochs are the PRIMARY KEY's second column, so they are already
        # unique and ascending; assert rather than assume, because a silent
        # unsorted series would corrupt every window boundary downstream.
        epochs = block[:, 0]
        if np.any(np.diff(epochs) <= 0):
            raise RuntimeError(f"NORAD {norad}: epochs not strictly ascending")

        mean_motion = block[:, 1].astype(np.float64) / orbit_history.SCALE_MEAN_MOTION
        inclination = (block[:, 2].astype(np.float64) / orbit_history.SCALE_ANGLE).astype(np.float32)
        eccentricity = block[:, 3].astype(np.float64) / orbit_history.SCALE_ECCENTRICITY

        handles["epoch_ms"].write(epochs.astype("<i8").tobytes())
        handles["mean_motion"].write(mean_motion.astype("<f8").tobytes())
        handles["inclination"].write(inclination.astype("<f4").tobytes())
        handles["eccentricity"].write(eccentricity.astype("<f8").tobytes())

        object_type, klass, name = classes[norad]
        index.append({"norad": norad, "offset": offset, "length": int(epochs.size),
                      "objectType": object_type, "class": klass, "name": name,
                      "half": split_half(norad) if klass == "passive" else None,
                      "firstEpochMs": int(epochs[0]), "lastEpochMs": int(epochs[-1])})
        offset += int(epochs.size)
        census["kept"] += 1
        census["by_class"][klass] += 1
        if progress_every and position % progress_every == 0:
            rate = (position + 1) / max(time.monotonic() - started, 1e-9)
            print(f"  {position + 1}/{len(wanted)} objects, {offset:,} rows, "
                  f"{rate:.1f} obj/s", file=sys.stderr, flush=True)

    for handle in handles.values():
        handle.flush()
        handle.close()
    census["element_sets"] = offset
    census["seconds"] = round(time.monotonic() - started, 1)
    (out_dir / "index.json").write_text(json.dumps(
        {"census": census, "objects": index}, separators=(",", ":")))
    return census


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--archive", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--modulus", type=int, default=1,
                        help="systematic subsample norad %% modulus == 0, for a smoke run")
    args = parser.parse_args()

    path = args.archive or orbit_history.archive_db_path()
    db = orbit_campaigns.open_archive_for_reading(path)
    db.execute("PRAGMA query_only=1")
    try:
        census = extract(db, args.out, limit=args.limit, modulus=args.modulus)
    finally:
        db.close()
    print(json.dumps(census, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
