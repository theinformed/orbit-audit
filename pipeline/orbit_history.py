#!/usr/bin/env python3
"""Orbit history archive: keep every element set this installation ever sees.

WHY THIS EXISTS
---------------
`ingest/spacetrack_ingest.py` pulls the full GP set once an hour and
*overwrites* `runtime/spacetrack-mirror/gp-active.json`. Every hour that
passes without archiving is an hour of orbital history permanently lost, and
the hourly capture cannot be back-filled from the GP class: space-track's
published cadence for GP is one query per hour, and `gp_history` is rate
limited to one call per lifetime. So this module runs immediately after each
fetch and appends the new element sets to a durable archive.

space-track does, however, publish the whole history as yearly zip bundles on
a separate cloud share, and its documentation asks callers to use those rather
than the API for large date ranges. `pipeline/orbit_history_backfill.py` does
exactly that, into this module's schema, quantisation and retention machinery
unchanged. So the archive is no longer confined to what has been watched
since 2026-08-07 — but the *live* stream still has to be caught as it goes
past, which is what this file is for.

THIS MODULE MAKES NO NETWORK REQUESTS. It reads files that are already on
disk and writes a local archive. It must never grow a fetch. `tests/
test_orbit_history.py` asserts that no networking module is imported.

WHAT IS STORED, AND WHAT IS NOT
-------------------------------
We keep *derived, reduced* quantities: the mean elements, the drag terms and
the epoch, quantised to the precision the upstream data actually carries. We
deliberately do NOT store `TLE_LINE1/2`, `GP_ID` or `FILE`. Those are
verbatim upstream records, and mirroring them at scale would make this
installation look like a data clearinghouse, which USSPACECOM's blanket
redistribution approval does not cover. The elements themselves are basic SSA
data and travel with the citation carried by
`pipeline/build_release.py:source_citation()`.

STORAGE SHAPE
-------------
Everything lives on `/mnt/d`, the 3.7 TB spinning disk, not on the SSD. This
is a cold-storage workload that grows forever, and the SSD's remaining space
belongs to the model weights under /opt/ai/models.

Three tiers, all in one SQLite database plus a directory of shard files.
sqlite3 is in the standard library, which matters because this pipeline runs
on system python3 with no virtualenv and no pip.

  1. `element_set`  - every element set, full fidelity, retained for a bounded
     window (default 400 days). `WITHOUT ROWID`, clustered on
     (norad, epoch_ms). That clustering is the whole design: an object's
     history is physically contiguous, so "show me this satellite's orbit over
     time" is one sequential read, while "sweep the population for a storm
     signature" is a single ordered scan.

  2. `element_set_daily` - one element set per object per UTC day, the one
     nearest 12:00 UTC, kept forever. Multi-year decay plots need dense
     coverage in time, not dense coverage in element sets.

     The 3.4x saving this tier was designed around IS NOT AVAILABLE OVER
     BACK-FILLED HISTORY, and the difference decides whether the tier is worth
     having. 3.4x was measured against the hourly live capture, which sees the
     same element set again and again until it is re-fitted. The bulk bundles
     carry each fit once. Counted on 2023-06 of the real archive, 2026-08-08:
     1,075,921 element sets over 24,642 objects fold to 574,602 object-days, a
     ratio of 1.87. So decimating twenty-two years into tier 2 would leave
     about 125 M rows in the hot database out of 233 M - which is not a hot
     database. Tier 2 earns its keep over the live capture and does not earn it
     over the back-fill, and any retention policy that assumes otherwise will
     roll the archive and find it barely smaller.

  3. Cold shards - one file per UTC month, zig-zag varint delta-encoded
     against each object's previous row and zlib-compressed, kept forever.
     Full fidelity, so nothing is ever actually lost when tier 1 rolls off.
     Measured 2026-08-08 on 2023-06: 20.06 bytes per element set, against 62.9
     bytes per element set in tier 1. The whole 233 M-row back-fill is about
     4.7 GB of shards, against about 14.7 GB as SQLite.

WHAT COSTS WHAT, MEASURED
-------------------------
Everything here is timed on the live 55,151,708-row archive of 2026-08-08 (a
consistent copy of it, so the running import was not disturbed). The numbers
are the reason the summary tier below exists:

    COUNT(*) FROM element_set               121.9 s  ->  0.00 s
    archive_stats()                         117.3 s  ->  0.12 s
    orbit_release.coverage()                239.1 s  ->  0.18 s

The right-hand column is a read of `month_rollup` and `object_rollup`, and it
does not move when the archive grows: 85 month rows and 42,807 object rows
today, at most 264 and about 60,000 at the end of the back-fill. Seeding those
tables costs one paged pass, 257.8 s for 55.2 M rows, projected 1,090 s at
233 M - paid once per refresh rather than once per query, and paged, so no
single statement holds a lock for more than a page.

STILL PROPORTIONAL TO THE WHOLE ARCHIVE, ON PURPOSE OR NOT
----------------------------------------------------------
  * `export_month` and `decimate_day` each filter on `epoch_ms`, and there is
    no index on `epoch_ms` alone - the table is clustered on (norad, epoch_ms).
    So each is a full scan. Measured: exporting 2023-06, 1,075,921 rows, took
    136.0 s because it read all 55 M. Rolling the 85 months held today is
    therefore about 3.2 hours of scanning, and 264 months at 233 M rows is
    about 42 hours. Both should be one ordered pass instead, distributing rows
    into per-month spill files as they go - the stream is already in
    (norad, epoch_ms) order, which is the order the shards need. Not built.
  * `orbit_campaigns.scan_archive` reads every element set by design. It is the
    per-object detector, it is already paged, and it runs on the daily timer.

`PRAGMA journal_mode` DEPENDS ON THE FILESYSTEM, and `supports_wal()` decides.
On /mnt/d it is TRUNCATE, for the original reason: v9fs, and WAL needs a
shared-memory index that 9p does not coordinate reliably between processes;
measured there, TRUNCATE inserts 31,697 rows in 0.16 s, so there was nothing to
buy by risking it. Since 2026-09-08 the database lives on ext4 on the SSD, where
that objection does not apply and WAL is used instead -- because under the
rollback modes ANY reader blocks the writer, and an orphaned read cursor once
held this archive for five hours.

RETENTION IS NOT OPTIONAL
-------------------------
`roll()` decimates, exports, verifies, and only then prunes, in that order,
and refuses to prune a day it has not both decimated and written into a
verified shard. The retention window is passed in at the call site, the way
`deploy/prune_data.py` takes `--max-age-hours` from `pipeline/publish_vps.sh`,
so the policy is visible where it is applied rather than buried in here.

QUANTISATION
------------
Scales are chosen so the stored integer is *exact* for every value
space-track actually publishes (measured against the live 31,697-record
mirror), not merely close:

    mean motion       1e-8 rev/day      (upstream carries 8 decimals)
    eccentricity      1e-8              (8 decimals)
    inclination/RAAN/argp/M
                      1e-4 deg          (4 decimals)
    B*                1e-12 /earth-radii
    n-dot             1e-8 rev/day^2    (8 decimals)
    n-ddot            1e-13 rev/day^3   (13 decimals)
    epoch             1 ms              (TLE epoch resolution is 0.86 ms;
                                         the 0.5 ms rounding is 3.8 mm of
                                         along-track position at 7.5 km/s)
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import sqlite3
import statistics
import sys
import time
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence

ROOT = Path(__file__).resolve().parents[1]

SCHEMA_VERSION = 2
ARCHIVE_NAME = "orbit-history.sqlite3"

# The spinning disk, alongside the other cold artifacts this machine keeps
# (/mnt/d/space-ccmc-cache, /mnt/d/space-explorer). This is the COLD root and
# it stays where it is: bulk/ is 12 GB of TLE bundles kept forever and read a
# few times a year, and it has no business on the SSD.
DEFAULT_ROOT = Path("/mnt/d/space-orbit-history")
FALLBACK_ROOT = ROOT / "runtime" / "orbit-history"

# THE HOT DATABASE LIVES ON THE SSD.
#
# The rule above used to end "Never the SSD", and for the cold artifacts it
# still holds. The DATABASE is a different animal. A full sweep reads it in
# small random reads for hours: one measured sweep did 22.6 GB of reads over 15
# hours and made the machine unusable interactively, visible as the
# Windows/Linux bridge DLL pegging a core.
#
# /mnt/d is a 9p mount onto a Windows SPINNING disk. Measured the same day:
# 7 MB/s sequential, 2 ms per stat, and every single read crosses that bridge.
# Root is ext4 on the SSD with 429 GB free. 13 GB of hot database belongs there.
#
# TWO WINS, NOT ONE. The bridge leaves the hot path -- and on ext4 the archive
# can finally run in WAL mode, which 9p does not support. Under the old
# journal_mode=delete ANY reader blocks the writer, which has cost this project
# entire days; see the CONTENTION note below, most of which WAL retires.
DB_ROOT = Path("/home/sdegan/space-orbit-history")

# Written while the 13 GB copy is in flight and deleted when it has been
# verified. Its PRESENCE means the SSD copy is partial, so `archive_db_root()`
# must keep using the spinning disk. The move therefore takes effect the moment
# this file is removed, atomically, rather than at some point during a 40-minute
# copy -- and a copy that dies half way leaves the marker behind and changes
# nothing.
DB_MOVE_MARKER = "MOVE-IN-PROGRESS.txt"

# How long tier 1 keeps full-fidelity element sets. 400 days rather than 365
# so a year-long comparison never straddles the edge of the window.
DEFAULT_RETAIN_DAYS = 400

# A UTC day is left alone this long before being decimated into tier 2.
# Element sets do arrive with epochs a day or two in the past, and decimating
# a day while it can still gain members picks the wrong representative.
DECIMATION_SETTLE_DAYS = 2

# CONTENTION
# ----------
# One database, one rollback journal, three programs: the hourly capture
# (writer), the bulk back-fill (writer, hours at a time), and the hourly
# release rebuild (reader, tens of minutes). The next two constants are the
# whole of the arbitration between them, and both were set by measurement on
# 2026-08-08 against the live 46.8-million-row archive.
#
# The failure they exist to prevent, reproduced end to end that day:
#
#   1. `orbit-release` opened ONE cursor over `element_set` and iterated it for
#      32-45 minutes. An open cursor holds a SHARED lock for its whole life.
#   2. A writer wanting to commit takes RESERVED, then PENDING, then EXCLUSIVE.
#      It reached PENDING and stopped there, because PENDING waits for every
#      SHARED lock to drain and the release's would not drain for half an hour.
#   3. PENDING blocks *new* readers too. So the capture's very first statement -
#      `PRAGMA journal_mode`, which has to read page 1 - was refused, waited out
#      its 60-second timeout and died with `database is locked`.
#
# The capture is the process that must win. It takes 40-80 seconds and the data
# it writes is irreplaceable: `gp-active.json` is overwritten in place by the
# next fetch, so an hour the capture misses is an hour of orbital history that
# no later run can recover. The release is a derived rebuild of cache artifacts
# and loses nothing by being retried on the next tick.

# How long a writer waits for the lock before giving up. Sixty seconds was the
# old value and it was never capable of outlasting a reader that holds the
# archive for half an hour; the archive's own aggregate queries hold it for 103
# seconds, so even a release that never reached its main scan could starve it.
#
# Fifteen minutes is longer than every hold this module can still produce, and
# it has to stay below `spacetrack-ingest.service`'s TimeoutStartSec - raised
# to 1200 s in the same change - because a capture killed by systemd at the
# unit timeout dies without printing anything, and the whole point of waiting
# is to be able to say what happened if the wait fails. See
# `starved_capture_report`.
#
# Tunable with SPACE_EXPLORER_ORBIT_ARCHIVE_TIMEOUT_SECONDS.
DEFAULT_BUSY_TIMEOUT_SECONDS = 900.0

# How many element-set rows one read transaction may cover.
#
# A scan that pages by primary key and ends its transaction between pages gives
# a waiting writer a window every page. Chosen by measurement against the live
# 46.8 M-row archive on 2026-08-08, timing each page's
# `execute(...).fetchall()` - which is exactly the life of its SHARED lock:
#
#     page rows      median hold      throughput
#        50,000          0.14 s      347,000 rows/s
#       100,000          0.29 s      339,000 rows/s
#       250,000          0.90 s      (this default)
#       500,000          1.84 s      265,000 rows/s
#     1,000,000          3.68 s      266,000 rows/s
#
# The point of that table is the right-hand column: throughput is flat across a
# twentyfold range of page sizes, so the page size buys nothing and costs
# nothing in speed. It only decides how long the lock is held, which makes it a
# free choice of the smallest hold that is not silly. 250,000 rows is under a
# second, against the 32-45 MINUTES the single statement it replaces used to
# hold - and that single statement also held the lock through all of the
# caller's analysis, which this does not.
#
# Resuming a page is one descent of the primary-key b-tree of a WITHOUT ROWID
# table, not a re-scan; that is why the flat throughput is possible at all.
#
# Tunable with SPACE_EXPLORER_ORBIT_SCAN_PAGE_ROWS.
DEFAULT_SCAN_PAGE_ROWS = 250_000

# Above every epoch SQLite can hold, so `(norad, epoch_ms) > (n, this)` selects
# the first row of the object AFTER n. Used only to seed a resumed sweep.
_EPOCH_ABOVE_ALL = 9_223_372_036_854_775_807

# The six columns every whole-archive scan in this pipeline reads. Named once
# because `orbit_campaigns.stream_object_rows` and `orbit_events.load_intervals`
# are two scans of the same shape and must stay that way: they feed the two
# detectors whose agreement is the release's only cross-check.
SCAN_COLUMNS = (
    "norad, epoch_ms, mean_motion_q, eccentricity_q, inclination_q, bstar_q"
)

# Physical constants, WGS-72 as used by SGP4 - the elements are fitted with
# this gravity model, so deriving a semi-major axis with any other value of mu
# introduces a bias of tens of metres.
MU_WGS72 = 398600.8            # km^3/s^2
RE_WGS72 = 6378.135            # km
J2_WGS72 = 1.082616e-3

SCALE_MEAN_MOTION = 10**8      # rev/day
SCALE_ECCENTRICITY = 10**8
SCALE_ANGLE = 10**4            # degrees
SCALE_BSTAR = 10**12
SCALE_NDOT = 10**8
SCALE_NDDOT = 10**13

# The three drag columns are the only elements the formats leave unbounded, and
# they carry the largest quantisation scales. B* is an inverse-Earth-radii drag
# coefficient: a satellite in terminal decay reaches order 1e-2, and 1e3 is
# already a thousand times past anything the atmosphere can do. The same holds
# for the two mean-motion derivatives in rev/day^2 and rev/day^3.
#
# The ceiling is a physical statement, but it also closes a real hole. A garbled
# implied-decimal exponent in the bulk archive parses to something like 1e27;
# multiplied by SCALE_NDDOT that leaves the signed 64-bit range SQLite stores
# integers in, and `executemany` raises OverflowError in the middle of a batch.
# One such record in the 2005 bundle killed the whole 20-year backfill at 1.4
# million rows and did it identically on every relaunch.
MAX_DRAG_MAGNITUDE = 1.0e3


def drag_terms_in_range(*values: float | None) -> bool:
    """True when every supplied drag term is physically possible.

    Applied by both element sources so a record legal on one path cannot be
    illegal on the other. `None` is a missing value, not a bad one.
    """
    for value in values:
        if value is None:
            continue
        if not math.isfinite(value) or abs(value) > MAX_DRAG_MAGNITUDE:
            return False
    return True

_ELEMENT_COLUMNS = (
    "epoch_ms",
    "mean_motion_q",
    "eccentricity_q",
    "inclination_q",
    "raan_q",
    "arg_perigee_q",
    "mean_anomaly_q",
    "bstar_q",
    "ndot_q",
    "nddot_q",
    "rev_at_epoch",
)


def _now_ms() -> int:
    return int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)


class ArchiveError(RuntimeError):
    """Raised when the archive cannot be written or is internally inconsistent."""


class ArchiveBusy(ArchiveError):
    """Raised when the archive could not be locked before the timeout ran out.

    A distinct type because the operator response is different from every other
    ArchiveError. Nothing here is corrupt and nothing needs repairing: another
    process is simply holding the file, and the only question is what was lost
    while this one waited.
    """


# ---------------------------------------------------------------------------
# Contention
# ---------------------------------------------------------------------------
def busy_timeout_seconds() -> float:
    """How long to wait for the archive lock. See DEFAULT_BUSY_TIMEOUT_SECONDS."""
    override = os.environ.get("SPACE_EXPLORER_ORBIT_ARCHIVE_TIMEOUT_SECONDS")
    if not override:
        return DEFAULT_BUSY_TIMEOUT_SECONDS
    try:
        value = float(override)
    except ValueError:
        print(
            f"WARNING: SPACE_EXPLORER_ORBIT_ARCHIVE_TIMEOUT_SECONDS={override!r} is not a "
            f"number; using {DEFAULT_BUSY_TIMEOUT_SECONDS}",
            file=sys.stderr,
        )
        return DEFAULT_BUSY_TIMEOUT_SECONDS
    if value <= 0:
        print(
            f"WARNING: SPACE_EXPLORER_ORBIT_ARCHIVE_TIMEOUT_SECONDS={override!r} is not "
            f"positive; using {DEFAULT_BUSY_TIMEOUT_SECONDS}",
            file=sys.stderr,
        )
        return DEFAULT_BUSY_TIMEOUT_SECONDS
    return value


def scan_page_rows() -> int:
    """How many rows one read transaction may cover. See DEFAULT_SCAN_PAGE_ROWS."""
    override = os.environ.get("SPACE_EXPLORER_ORBIT_SCAN_PAGE_ROWS")
    if not override:
        return DEFAULT_SCAN_PAGE_ROWS
    try:
        value = int(override)
    except ValueError:
        value = 0
    if value <= 0:
        print(
            f"WARNING: SPACE_EXPLORER_ORBIT_SCAN_PAGE_ROWS={override!r} is not a positive "
            f"integer; using {DEFAULT_SCAN_PAGE_ROWS}",
            file=sys.stderr,
        )
        return DEFAULT_SCAN_PAGE_ROWS
    return value


def paged_element_sets(
    connection: sqlite3.Connection,
    *,
    only: Sequence[int] | None = None,
    page_rows: int | None = None,
    columns: str = SCAN_COLUMNS,
    start_after_norad: int | None = None,
) -> Iterator[tuple]:
    """Every `element_set` row in (norad, epoch_ms) order, in bounded transactions.

    Yields exactly what

        SELECT <SCAN_COLUMNS> FROM element_set ORDER BY norad, epoch_ms

    yields, and is a drop-in for it, but ends its read transaction every
    `page_rows` rows so a waiting writer gets a window. That is the difference
    between the hourly capture running and the hourly capture dying: see the
    CONTENTION note at the top of this module.

    WHY PAGING BY KEY IS SAFE HERE, WHICH IS NOT THE SAME AS "THE TABLE IS
    APPEND-ONLY"
    ---------------------------------------------------------------------------
    It is tempting to justify this by saying `element_set` is only ever appended
    to. That is **not true**, and the untrue version would be a dangerous thing
    to rely on: `prune_hot` runs `DELETE FROM element_set WHERE epoch_ms < ?`
    every time `roll()` retires a day out of tier 1.

    The property that actually holds, checked against every statement in this
    package that touches the table, is narrower and stronger:

      * `ingest_records`  - INSERT OR IGNORE            (adds keys)
      * `orbit_history_backfill._INSERT` - INSERT OR IGNORE   (adds keys)
      * `prune_hot`       - DELETE ... WHERE epoch_ms   (removes keys)
      * nothing, anywhere, UPDATEs a row.

    So a row's primary key is fixed for as long as the row exists. Key-set
    paging resumes at `WHERE (norad, epoch_ms) > (last seen)`, which means a row
    present for the whole scan is returned exactly once no matter what else was
    inserted or deleted meanwhile - unlike LIMIT/OFFSET paging, which a delete
    ahead of the cursor would make skip a row. Rows inserted behind the cursor
    are missed and rows inserted ahead of it are included; both are element sets
    that did not exist when the scan began, and the next hourly rebuild has
    them. What cannot happen is losing one that did.

    The scan is a walk of the primary-key b-tree of a WITHOUT ROWID table, so
    resuming a page is one index descent, not a re-scan.
    """
    limit = page_rows if page_rows is not None else scan_page_rows()
    if limit <= 0:
        raise ValueError("page_rows must be positive")
    # The cursor IS the first two columns, so a projection that dropped them
    # would page against values it never read. Cheaper to refuse than to debug.
    if not columns.replace(" ", "").startswith("norad,epoch_ms"):
        raise ValueError("columns must begin with 'norad, epoch_ms' - they are the paging cursor")

    if only:
        marks = ",".join("?" for _ in only)
        query = (
            f"SELECT {columns} FROM element_set "
            f"WHERE norad IN ({marks}) AND (norad, epoch_ms) > (?, ?) "
            "ORDER BY norad, epoch_ms LIMIT ?"
        )
        prefix: tuple = tuple(int(norad) for norad in only)
    else:
        query = (
            f"SELECT {columns} FROM element_set "
            "WHERE (norad, epoch_ms) > (?, ?) "
            "ORDER BY norad, epoch_ms LIMIT ?"
        )
        prefix = ()

    # Below every real key: norad is a positive catalogue number.
    #
    # `start_after_norad` seeds the cursor ABOVE every possible epoch of that
    # object instead, so the walk restarts at the next object. Resuming is one
    # descent of the primary-key b-tree, not a re-scan, which is the property
    # that lets an archive sweep stop on a wall-clock budget and continue in a
    # later run rather than being killed part-way and losing the work.
    if start_after_norad is None:
        cursor_norad, cursor_epoch = -1, -1
    else:
        cursor_norad, cursor_epoch = int(start_after_norad), _EPOCH_ABOVE_ALL
    while True:
        # fetchall, not iteration: the SHARED lock lives as long as the
        # statement, so the statement has to FINISH for the lock to drop. A
        # generator that yielded straight out of the cursor would hold the lock
        # across the caller's work as well, which is most of the run.
        page = connection.execute(
            query, prefix + (cursor_norad, cursor_epoch, limit)
        ).fetchall()
        if not page:
            return
        yield from page
        cursor_norad, cursor_epoch = page[-1][0], page[-1][1]
        if len(page) < limit:
            return


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
def archive_root() -> Path:
    """Where the archive lives. /mnt/d unless told otherwise.

    Falls back to the repository's runtime directory only when /mnt/d is not
    mounted - on a machine that is not bigmem, or during tests - and says so,
    because silently writing gigabytes to the SSD is exactly the mistake this
    function exists to prevent.
    """
    override = os.environ.get("SPACE_EXPLORER_ORBIT_HISTORY_ROOT")
    if override:
        return Path(override)
    if DEFAULT_ROOT.parent.is_dir():
        return DEFAULT_ROOT
    print(
        f"WARNING: {DEFAULT_ROOT.parent} is not mounted; "
        f"falling back to {FALLBACK_ROOT} on the system disk",
        file=sys.stderr,
    )
    return FALLBACK_ROOT


def archive_db_root() -> Path:
    """Where the HOT database lives, which is no longer where the cold tier lives.

    Falls back to the cold root whenever the SSD copy is absent or unverified,
    so this is safe to ship before, during and after the move, and safe on any
    machine that is not bigmem.
    """
    override = os.environ.get("SPACE_EXPLORER_ORBIT_DB_ROOT")
    if override:
        return Path(override)
    if (DB_ROOT / ARCHIVE_NAME).exists() and not (DB_ROOT / DB_MOVE_MARKER).exists():
        return DB_ROOT
    return archive_root()


def archive_db_path() -> Path:
    """The database file itself. Every reader and writer should come through here."""
    return archive_db_root() / ARCHIVE_NAME


# Filesystems on which WAL's shared-memory index is not coordinated between
# processes. 9p is the one that matters here (/mnt/d); the others are listed
# because the same objection applies and the archive could plausibly land on
# one during a recovery.
NO_WAL_FILESYSTEMS = {"9p", "v9fs", "nfs", "nfs4", "cifs", "smbfs", "fuseblk"}


def filesystem_type(path: Path) -> str | None:
    """The fstype of the mount `path` sits on, or None if it cannot be read.

    Longest-prefix match against /proc/mounts, because /mnt/d and / are both
    prefixes of a file under /mnt/d and only the longer one is the answer.
    """
    try:
        target = path.resolve()
        best, best_type = -1, None
        with open("/proc/mounts", encoding="utf-8") as handle:
            for line in handle:
                parts = line.split()
                if len(parts) < 3:
                    continue
                point = parts[1].replace("\\040", " ")
                if (str(target) == point or str(target).startswith(point.rstrip("/") + "/")) \
                        and len(point) > best:
                    best, best_type = len(point), parts[2]
        return best_type
    except OSError:
        return None


def supports_wal(path: Path) -> bool:
    """Whether WAL is safe on the filesystem holding `path`.

    Asked of the FILESYSTEM rather than of SQLite, deliberately. Setting
    `journal_mode=WAL` on 9p can appear to succeed and then fail later on the
    shared-memory index, so "the pragma returned wal" is not evidence that WAL
    works here -- it is the proxy signal, not the outcome.
    """
    kind = filesystem_type(path)
    if kind is None:
        return False           # unknown filesystem: keep the conservative mode
    return kind.lower() not in NO_WAL_FILESYSTEMS


def cold_root(root: Path | None = None) -> Path:
    return (root if root is not None else archive_root()) / "cold"


# ---------------------------------------------------------------------------
# Encoding
# ---------------------------------------------------------------------------
def quantise(value: float | str | None, scale: int) -> int | None:
    """Round a published element to its exact integer representation.

    Returns None for a missing value rather than substituting a zero: a
    missing B* and a B* of zero are different physical statements.
    """
    if value is None or value == "":
        return None
    return int(round(float(value) * scale))


def parse_epoch_ms(text: str) -> int:
    """space-track publishes a naive ISO-8601 timestamp that is always UTC."""
    stamp = dt.datetime.fromisoformat(text)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=dt.timezone.utc)
    return int(round(stamp.timestamp() * 1000))


def epoch_ms_to_datetime(epoch_ms: int) -> dt.datetime:
    return dt.datetime.fromtimestamp(epoch_ms / 1000.0, dt.timezone.utc)


@dataclass(frozen=True)
class ElementSet:
    """One archived element set, in engineering units."""

    norad: int
    epoch_ms: int
    mean_motion: float          # rev/day
    eccentricity: float
    inclination: float          # deg
    raan: float                 # deg
    arg_perigee: float          # deg
    mean_anomaly: float         # deg
    bstar: float | None
    ndot: float | None          # rev/day^2 (upstream reports n-dot/2)
    nddot: float | None
    rev_at_epoch: int | None

    @property
    def epoch(self) -> dt.datetime:
        return epoch_ms_to_datetime(self.epoch_ms)

    @property
    def semi_major_axis_km(self) -> float:
        return semi_major_axis_km(self.mean_motion)

    @property
    def perigee_altitude_km(self) -> float:
        return self.semi_major_axis_km * (1.0 - self.eccentricity) - RE_WGS72

    @property
    def apogee_altitude_km(self) -> float:
        return self.semi_major_axis_km * (1.0 + self.eccentricity) - RE_WGS72


def semi_major_axis_km(mean_motion_rev_per_day: float) -> float:
    """Kozai mean semi-major axis from the GP mean motion.

    This is *not* the osculating a, and it is not the Brouwer a either: the
    J2 short-period correction between them is very nearly constant for a
    given object, so it cancels in the first differences this module is built
    on. Never compare this number against an osculating a from an ephemeris.
    """
    n_rad_s = mean_motion_rev_per_day * 2.0 * math.pi / 86400.0
    if n_rad_s <= 0:
        raise ValueError("mean motion must be positive")
    return (MU_WGS72 / (n_rad_s * n_rad_s)) ** (1.0 / 3.0)


def j2_secular_rates(element: ElementSet) -> tuple[float, float]:
    """Secular nodal regression and apsidal precession from J2, deg/day.

    The detector subtracts these before looking at RAAN and argument of
    perigee. They are large - a 500 km sun-synchronous orbit regresses about
    1 deg/day - perfectly predictable, and emphatically not manoeuvres.
    """
    a = element.semi_major_axis_km
    e = element.eccentricity
    inc = math.radians(element.inclination)
    p = a * (1.0 - e * e)
    if p <= 0:
        raise ValueError("degenerate orbit")
    factor = J2_WGS72 * (RE_WGS72 / p) ** 2
    n_deg_day = element.mean_motion * 360.0
    raan_dot = -1.5 * n_deg_day * factor * math.cos(inc)
    argp_dot = 0.75 * n_deg_day * factor * (5.0 * math.cos(inc) ** 2 - 1.0)
    return raan_dot, argp_dot


def element_from_gp(record: dict) -> ElementSet | None:
    """Reduce one space-track GP/OMM record. Returns None if unusable."""
    try:
        norad = int(record["NORAD_CAT_ID"])
        epoch_ms = parse_epoch_ms(record["EPOCH"])
        mean_motion = float(record["MEAN_MOTION"])
        eccentricity = float(record["ECCENTRICITY"])
        inclination = float(record["INCLINATION"])
        raan = float(record["RA_OF_ASC_NODE"])
        arg_perigee = float(record["ARG_OF_PERICENTER"])
        mean_anomaly = float(record["MEAN_ANOMALY"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (0.0 < mean_motion < 20.0):
        return None
    if not (0.0 <= eccentricity < 1.0):
        return None
    if not (0.0 <= inclination <= 180.0):
        return None

    def optional(key: str) -> float | None:
        raw = record.get(key)
        if raw is None or raw == "":
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    rev = record.get("REV_AT_EPOCH")
    try:
        rev_at_epoch = int(rev) if rev not in (None, "") else None
    except (TypeError, ValueError):
        rev_at_epoch = None

    bstar = optional("BSTAR")
    ndot = optional("MEAN_MOTION_DOT")
    nddot = optional("MEAN_MOTION_DDOT")
    if not drag_terms_in_range(bstar, ndot, nddot):
        return None

    return ElementSet(
        norad=norad,
        epoch_ms=epoch_ms,
        mean_motion=mean_motion,
        eccentricity=eccentricity,
        inclination=inclination,
        raan=raan,
        arg_perigee=arg_perigee,
        mean_anomaly=mean_anomaly,
        bstar=bstar,
        ndot=ndot,
        nddot=nddot,
        rev_at_epoch=rev_at_epoch,
    )


def _row_from_element(element: ElementSet, ingest_hour: int) -> tuple:
    return (
        element.norad,
        element.epoch_ms,
        quantise(element.mean_motion, SCALE_MEAN_MOTION),
        quantise(element.eccentricity, SCALE_ECCENTRICITY),
        quantise(element.inclination, SCALE_ANGLE),
        quantise(element.raan, SCALE_ANGLE),
        quantise(element.arg_perigee, SCALE_ANGLE),
        quantise(element.mean_anomaly, SCALE_ANGLE),
        quantise(element.bstar, SCALE_BSTAR),
        quantise(element.ndot, SCALE_NDOT),
        quantise(element.nddot, SCALE_NDDOT),
        element.rev_at_epoch,
        ingest_hour,
    )


def _element_from_row(norad: int, row: Sequence) -> ElementSet:
    def unscale(value, scale):
        return None if value is None else value / scale

    return ElementSet(
        norad=norad,
        epoch_ms=row[0],
        mean_motion=row[1] / SCALE_MEAN_MOTION,
        eccentricity=row[2] / SCALE_ECCENTRICITY,
        inclination=row[3] / SCALE_ANGLE,
        raan=row[4] / SCALE_ANGLE,
        arg_perigee=row[5] / SCALE_ANGLE,
        mean_anomaly=row[6] / SCALE_ANGLE,
        bstar=unscale(row[7], SCALE_BSTAR),
        ndot=unscale(row[8], SCALE_NDOT),
        nddot=unscale(row[9], SCALE_NDDOT),
        rev_at_epoch=row[10],
    )


# ---------------------------------------------------------------------------
# Archive
# ---------------------------------------------------------------------------
_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS element_set (
    norad          INTEGER NOT NULL,
    epoch_ms       INTEGER NOT NULL,
    mean_motion_q  INTEGER NOT NULL,
    eccentricity_q INTEGER NOT NULL,
    inclination_q  INTEGER NOT NULL,
    raan_q         INTEGER NOT NULL,
    arg_perigee_q  INTEGER NOT NULL,
    mean_anomaly_q INTEGER NOT NULL,
    bstar_q        INTEGER,
    ndot_q         INTEGER,
    nddot_q        INTEGER,
    rev_at_epoch   INTEGER,
    ingest_hour    INTEGER NOT NULL,
    PRIMARY KEY (norad, epoch_ms)
) WITHOUT ROWID;

-- Tier 2: one element set per object per UTC day, kept forever. Same columns
-- as tier 1 plus the day it stands for, so a decade of decay can be plotted
-- without touching a cold shard.
CREATE TABLE IF NOT EXISTS element_set_daily (
    norad          INTEGER NOT NULL,
    day            INTEGER NOT NULL,   -- days since 1970-01-01 UTC
    epoch_ms       INTEGER NOT NULL,
    mean_motion_q  INTEGER NOT NULL,
    eccentricity_q INTEGER NOT NULL,
    inclination_q  INTEGER NOT NULL,
    raan_q         INTEGER NOT NULL,
    arg_perigee_q  INTEGER NOT NULL,
    mean_anomaly_q INTEGER NOT NULL,
    bstar_q        INTEGER,
    ndot_q         INTEGER,
    nddot_q        INTEGER,
    rev_at_epoch   INTEGER,
    PRIMARY KEY (norad, day)
) WITHOUT ROWID;

-- Which UTC days have been decimated into tier 2. A day is only safe to
-- prune once it appears here AND inside a verified cold shard.
CREATE TABLE IF NOT EXISTS decimated_day (
    day        INTEGER PRIMARY KEY,
    rows_in    INTEGER NOT NULL,
    rows_kept  INTEGER NOT NULL,
    done_ms    INTEGER NOT NULL
);

-- Cold shard ledger. `verified_ms` is set only after the shard has been read
-- back and compared row for row against the database it came from.
CREATE TABLE IF NOT EXISTS cold_shard (
    month       TEXT PRIMARY KEY,      -- YYYY-MM
    path        TEXT NOT NULL,
    rows        INTEGER NOT NULL,
    bytes       INTEGER NOT NULL,
    sha256      TEXT NOT NULL,
    exported_ms INTEGER NOT NULL,
    verified_ms INTEGER
);

-- Object facts change rarely; one row per object, refreshed when it moves.
CREATE TABLE IF NOT EXISTS object (
    norad        INTEGER PRIMARY KEY,
    name         TEXT,
    object_id    TEXT,
    object_type  TEXT,
    rcs_size     TEXT,
    country      TEXT,
    launch_date  TEXT,
    first_seen_ms INTEGER NOT NULL,
    last_seen_ms  INTEGER NOT NULL
);

-- One row per capture run, so gaps in the archive are provable rather than
-- inferred from missing data.
CREATE TABLE IF NOT EXISTS capture (
    captured_ms   INTEGER PRIMARY KEY,
    source        TEXT NOT NULL,
    source_mtime_ms INTEGER,
    records_read  INTEGER NOT NULL,
    elements_new  INTEGER NOT NULL,
    objects_seen  INTEGER NOT NULL,
    rejected      INTEGER NOT NULL
);

-- Maintained summaries, so the archive-wide questions stop being archive-wide
-- scans. `element_set` is WITHOUT ROWID, clustered on (norad, epoch_ms), and
-- there is no index on epoch_ms alone -- so MIN(epoch_ms), MAX(epoch_ms) and
-- COUNT(*) each read every page in the table. Measured on the 55,151,708-row
-- archive of 2026-08-08: COUNT(*) 121.9 s, `archive_stats` 117.3 s,
-- `orbit_release.coverage` 239.1 s. Those costs scale with the whole history,
-- which is exactly what the bulk back-fill is making bigger.
--
-- Both tables are keyed by something whose cardinality is bounded by the
-- catalogue rather than by time: about 40,000 objects, and twelve months a
-- year. That is the property that matters. Reading them is constant in the
-- number of element sets held, so a twenty-two-year archive answers these
-- questions as fast as a one-week one.
--
-- They are maintained transactionally by every insert path in this module, and
-- rebuilt from scratch by `refresh_summary()` after a prune or after a writer
-- that predates them has run. `summary_dirty` in `meta` says which.
CREATE TABLE IF NOT EXISTS month_rollup (
    month        TEXT PRIMARY KEY,      -- YYYY-MM, UTC, of the element set epoch
    rows         INTEGER NOT NULL,
    min_epoch_ms INTEGER NOT NULL,
    max_epoch_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS object_rollup (
    norad        INTEGER PRIMARY KEY,
    rows         INTEGER NOT NULL,
    min_epoch_ms INTEGER NOT NULL,
    max_epoch_ms INTEGER NOT NULL
);

-- Which months a prune has actually taken rows out of. A scalar high-water mark
-- cannot answer this: it says "everything before instant X is suspect", which
-- condemns every month before X including the ones that were never touched.
-- See `prune_hot` for the incident that made the difference matter.
CREATE TABLE IF NOT EXISTS pruned_month (
    month        TEXT PRIMARY KEY,
    rows_deleted INTEGER NOT NULL,
    pruned_ms    INTEGER NOT NULL
);

-- Geomagnetic context, archived from artifacts this pipeline already built.
-- Without this the orbit archive outlives the only geomagnetic time series
-- the site has, which is a rolling 24 hours.
CREATE TABLE IF NOT EXISTS geomagnetic (
    observed_ms INTEGER NOT NULL,
    index_name  TEXT NOT NULL,
    value       REAL NOT NULL,
    PRIMARY KEY (index_name, observed_ms)
) WITHOUT ROWID;
"""


def open_archive(path: Path | None = None) -> sqlite3.Connection:
    target = path if path is not None else archive_db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    # `isolation_level="IMMEDIATE"` is the whole reason the busy timeout works,
    # and its absence is why captures kept being lost with a nine-second wait
    # against a nine-hundred-second setting.
    #
    # Python's default is a DEFERRED transaction: the first statement takes a
    # SHARED read lock and the first write then tries to UPGRADE it to
    # RESERVED. SQLite does not run the busy handler for an upgrade -- it
    # returns SQLITE_BUSY immediately, because two readers both waiting to
    # upgrade would deadlock. So no timeout value could ever have helped; the
    # 05:00Z capture on 2026-08-09 died in nine seconds and said so.
    #
    # IMMEDIATE takes the write lock up front, before any read, which is a
    # plain acquisition the busy handler does honour. The cost is that the
    # capture now queues behind the backfill rather than failing fast, which is
    # the correct trade: an hour of orbital history cannot be re-fetched,
    # because the mirror file is overwritten in place.
    connection = sqlite3.connect(
        target, timeout=busy_timeout_seconds(), isolation_level="IMMEDIATE")
    # TRUNCATE, not WAL: /mnt/d is v9fs and WAL's shared-memory index is not
    # coordinated reliably across processes there. Measured cost of the safe
    # choice on this machine: 0.16 s versus 0.24 s for 31,697 inserts.
    #
    # Set unconditionally, and NOT guarded by first reading the current mode.
    # The guard looks like it would save an exclusive lock on the common path
    # and it saves nothing, for two measured reasons (2026-08-08, sqlite
    # 3.45.1, on /mnt/d):
    #
    #   * the rollback journal modes are a property of the CONNECTION, not of
    #     the file. A brand-new connection to this archive reports `delete`
    #     every time, so "already TRUNCATE" is never the case and the guard
    #     would fire on every open anyway.
    #   * `PRAGMA journal_mode=TRUNCATE` does not take a write lock. Run against
    #     a database another process was holding SHARED, it returned in 0.00 s.
    #     Both forms of the pragma need the same thing - a read of page 1 - and
    #     both are refused together when a writer is sitting at PENDING, which
    #     is exactly how this line came to be the one in the 10:19 traceback.
    #     It was the first statement to touch the file, not the expensive one.
    # WAL WHEN THE FILE IS LOCAL, TRUNCATE WHEN IT IS NOT.
    #
    # Everything argued above remains true of the 9p mount and stays in force
    # there. The archive now lives on ext4 on the SSD, where high-throughput
    # work belongs, and on a local filesystem WAL buys the one thing
    # TRUNCATE cannot: a reader that does not block the writer. Under the
    # rollback modes an orphaned read cursor held this archive for five hours
    # and cost a day.
    #
    # The filesystem is asked, not SQLite. `PRAGMA journal_mode=WAL` can report
    # success on 9p and then fail later on the shared-memory index, so the
    # pragma's own answer is a proxy signal rather than the outcome.
    if supports_wal(target):
        connection.execute("PRAGMA journal_mode=WAL")
        # Bound the WAL between checkpoints: ~8 MB at this page size.
        connection.execute("PRAGMA wal_autocheckpoint=2000")
    else:
        connection.execute("PRAGMA journal_mode=TRUNCATE")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.executescript(_SCHEMA)
    stored = connection.execute(
        "SELECT value FROM meta WHERE key='schema_version'"
    ).fetchone()
    if stored is None:
        connection.execute(
            "INSERT INTO meta(key, value) VALUES('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        # A database being created right now has no element sets, and empty
        # rollups describe an empty table exactly. So its summary is already
        # true and every insert from here maintains it. An archive that existed
        # before the rollups did reaches this branch with `stored` set, keeps
        # `summary_built_ms` absent, and is therefore treated as stale until
        # something has actually scanned it -- which is the correct answer for
        # the live archive on /mnt/d, whose bulk back-fill was written by a
        # version of this module that could not maintain what did not exist.
        _set_meta(connection, _SUMMARY_BUILT_KEY, str(_now_ms()))
        connection.commit()
    elif int(stored[0]) != SCHEMA_VERSION:
        connection.close()
        raise ArchiveError(
            f"{target} is schema v{stored[0]}, this code speaks v{SCHEMA_VERSION}"
        )
    return connection


@dataclass
class CaptureResult:
    records_read: int
    elements_new: int
    objects_seen: int
    rejected: int
    duplicates: int
    captured_ms: int

    def as_dict(self) -> dict:
        return {
            "recordsRead": self.records_read,
            "elementsNew": self.elements_new,
            "objectsSeen": self.objects_seen,
            "rejected": self.rejected,
            "duplicates": self.duplicates,
            "capturedAt": epoch_ms_to_datetime(self.captured_ms).isoformat(
                timespec="seconds"
            ).replace("+00:00", "Z"),
        }


def ingest_records(
    connection: sqlite3.Connection,
    records: Iterable[dict],
    *,
    source: str = "spacetrack:gp-active",
    captured_ms: int | None = None,
    source_mtime_ms: int | None = None,
) -> CaptureResult:
    """Append every element set not already archived. Idempotent.

    Running this twice on the same file adds nothing the second time: the
    primary key is (norad, epoch), and an element set is uniquely identified
    by its epoch. That is what makes it safe to attach to a timer that may
    fire while the mirror is unchanged.
    """
    now_ms = captured_ms if captured_ms is not None else _now_ms()
    ingest_hour = now_ms // 3_600_000

    rows: list[tuple] = []
    objects: dict[int, tuple] = {}
    read = 0
    rejected = 0
    for record in records:
        read += 1
        element = element_from_gp(record)
        if element is None:
            rejected += 1
            continue
        rows.append(_row_from_element(element, ingest_hour))
        objects[element.norad] = (
            element.norad,
            record.get("OBJECT_NAME"),
            record.get("OBJECT_ID"),
            record.get("OBJECT_TYPE"),
            record.get("RCS_SIZE"),
            record.get("COUNTRY_CODE"),
            record.get("LAUNCH_DATE"),
            now_ms,
            now_ms,
        )

    # Ask which keys are new BEFORE inserting them, so the summaries can be
    # moved by the same transaction that moves the table.
    by_month, by_object, expected = rollup_delta_for(connection, rows)
    before = connection.total_changes
    connection.executemany(
        "INSERT OR IGNORE INTO element_set VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows
    )
    inserted = connection.total_changes - before
    apply_rollup_delta(
        connection, by_month, by_object, inserted=inserted, expected=expected
    )

    connection.executemany(
        """
        INSERT INTO object VALUES (?,?,?,?,?,?,?,?,?)
        ON CONFLICT(norad) DO UPDATE SET
            name=excluded.name,
            object_id=excluded.object_id,
            object_type=excluded.object_type,
            rcs_size=excluded.rcs_size,
            country=excluded.country,
            launch_date=excluded.launch_date,
            last_seen_ms=excluded.last_seen_ms
        """,
        list(objects.values()),
    )

    result = CaptureResult(
        records_read=read,
        elements_new=inserted,
        objects_seen=len(objects),
        rejected=rejected,
        duplicates=len(rows) - inserted,
        captured_ms=now_ms,
    )
    connection.execute(
        "INSERT OR REPLACE INTO capture VALUES (?,?,?,?,?,?,?)",
        (
            now_ms,
            source,
            source_mtime_ms,
            read,
            inserted,
            len(objects),
            rejected,
        ),
    )
    connection.commit()
    return result


def capture_from_mirror(
    connection: sqlite3.Connection,
    mirror_path: Path,
    *,
    captured_ms: int | None = None,
) -> CaptureResult:
    """Read the on-disk GP mirror. Never fetches anything."""
    if not mirror_path.exists():
        raise ArchiveError(f"no GP mirror at {mirror_path}; nothing to archive")
    payload = json.loads(mirror_path.read_bytes())
    if not isinstance(payload, list) or not payload:
        raise ArchiveError(f"{mirror_path} is not a non-empty GP array")
    mtime_ms = int(mirror_path.stat().st_mtime * 1000)
    return ingest_records(
        connection,
        payload,
        source=f"spacetrack:{mirror_path.name}",
        captured_ms=captured_ms,
        source_mtime_ms=mtime_ms,
    )


def space_weather_artifact_from_manifest(data_root: Path) -> Path | None:
    """Resolve the current space-weather artifact through the published manifest.

    The artifacts are content-addressed, so their filenames change every build.
    A systemd unit cannot glob, and hard-coding a hash would break on the next
    publish; this reads `manifest.json` the same way `deploy/publish_data.py`
    does. Returns None rather than raising - a missing manifest must not stop
    the orbital capture, which is the part that cannot be back-filled.
    """
    manifest = data_root / "manifest.json"
    if not manifest.exists():
        return None
    try:
        document = json.loads(manifest.read_bytes())
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    # A manifest that is a list, a string, or null is malformed, not fatal.
    if not isinstance(document, dict):
        return None
    record = document.get("spaceWeather")
    if not isinstance(record, dict) or not isinstance(record.get("path"), str):
        return None
    candidate = data_root / record["path"]
    return candidate if candidate.exists() else None


def capture_geomagnetic(
    connection: sqlite3.Connection, space_weather_artifact: Path
) -> int:
    """Archive the Kp series out of an artifact this pipeline already wrote.

    The published `space-weather` artifact carries only a rolling 24-hour Kp
    window. An orbit archive that outlives its geomagnetic context cannot
    support the storm correlation, so we snapshot the window on every capture
    and let the primary key deduplicate the overlap.
    """
    if not space_weather_artifact.exists():
        return 0
    try:
        payload = json.loads(space_weather_artifact.read_bytes())
    except (OSError, json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    # `.get("geomagnetic", {})` returns None, not {}, when the key is present
    # with a JSON null - which raises on the next `.get`.
    geomagnetic = payload.get("geomagnetic")
    series = geomagnetic.get("series") if isinstance(geomagnetic, dict) else None
    if not isinstance(series, list):
        return 0
    rows = []
    for sample in series:
        if not isinstance(sample, dict):
            continue
        time_text, value = sample.get("time"), sample.get("value")
        if not isinstance(time_text, str) or not isinstance(value, (int, float)):
            continue
        try:
            rows.append((parse_epoch_ms(time_text.replace("Z", "+00:00")), "kp", float(value)))
        except ValueError:
            continue
    if not rows:
        return 0
    before = connection.total_changes
    connection.executemany("INSERT OR IGNORE INTO geomagnetic VALUES (?,?,?)", rows)
    connection.commit()
    return connection.total_changes - before


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------
def series(
    connection: sqlite3.Connection,
    norad: int,
    *,
    since_ms: int | None = None,
    until_ms: int | None = None,
) -> list[ElementSet]:
    query = (
        f"SELECT {', '.join(_ELEMENT_COLUMNS)} FROM element_set WHERE norad = ?"
    )
    params: list = [norad]
    if since_ms is not None:
        query += " AND epoch_ms >= ?"
        params.append(since_ms)
    if until_ms is not None:
        query += " AND epoch_ms <= ?"
        params.append(until_ms)
    query += " ORDER BY epoch_ms"
    return [
        _element_from_row(norad, row)
        for row in connection.execute(query, params)
    ]


def _iso_or_none(epoch_ms: int | None) -> str | None:
    """`if epoch_ms` would report 1970-01-01T00:00:00Z as "no data"."""
    return None if epoch_ms is None else epoch_ms_to_datetime(epoch_ms).isoformat()


# ---------------------------------------------------------------------------
# The maintained summaries
# ---------------------------------------------------------------------------
# WHY THESE EXIST
# ---------------
# Three questions used to read all 55 million rows to answer: how many element
# sets are held, what is the earliest epoch, what is the latest. None of them
# is a question ABOUT 55 million rows - each is a question about the shape of
# the archive, and the shape is small. `month_rollup` and `object_rollup` hold
# the shape, so the answers cost a read of a few hundred rows instead of a read
# of the whole disk.
#
# WHAT KEEPS THEM TRUE
# --------------------
# Every insert path in this package applies its own delta inside the same
# transaction as the insert, so there is no window in which the table and its
# summary disagree. What the delta cannot be is a guess: `INSERT OR IGNORE`
# silently drops the element sets already held, and counting the offered rows
# rather than the accepted ones would inflate the total by every duplicate the
# archive has ever been handed. `rollup_delta_for` therefore asks the database
# which offered keys are genuinely new, and `apply_rollup_delta` cross-checks
# that count against the connection's own `total_changes`. A mismatch raises
# rather than writing a number nobody would ever re-derive.
#
# WHAT BREAKS THEM
# ----------------
# A writer that predates this code - the bulk back-fill running on 2026-08-08
# had the old module in memory and could not maintain what did not yet exist -
# and `prune_hot`, which removes rows without being able to say cheaply which
# objects lost their earliest epoch. Both cases set `summary_dirty`, and a
# dirty summary is REFUSED rather than served: `archive_stats` falls back to
# the honest full scan and says so in `elementSetsSource`. Stale numbers that
# look fresh are how a published figure stops being worth anything.
_SUMMARY_DIRTY_KEY = "summary_dirty"
_SUMMARY_BUILT_KEY = "summary_built_ms"


def month_key(epoch_ms: int) -> str:
    """The UTC month an epoch falls in, as YYYY-MM."""
    stamp = epoch_ms_to_datetime(epoch_ms)
    return f"{stamp.year:04d}-{stamp.month:02d}"


def _set_meta(connection: sqlite3.Connection, key: str, value: str) -> None:
    connection.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def _get_meta(connection: sqlite3.Connection, key: str) -> str | None:
    try:
        row = connection.execute(
            "SELECT value FROM meta WHERE key = ?", (key,)
        ).fetchone()
    except sqlite3.OperationalError:
        # No `meta` table at all. Several callers assemble a minimal archive by
        # hand - the campaign scan tests do - and an archive with no meta table
        # has certainly never had a summary built. Reporting "no summary" sends
        # the caller to the full scan, which is slow and right; raising here
        # would break readers that never asked for the fast path.
        return None
    return row[0] if row else None


def mark_summary_dirty(connection: sqlite3.Connection, reason: str) -> None:
    """Record that the rollups no longer describe `element_set`.

    Takes a reason because "the summary is stale" is not actionable and "the
    summary is stale because a prune removed rows" is.
    """
    _set_meta(connection, _SUMMARY_DIRTY_KEY, reason)


def summary_is_dirty(connection: sqlite3.Connection) -> str | None:
    """The reason the summary cannot be trusted, or None if it can."""
    if _get_meta(connection, _SUMMARY_BUILT_KEY) is None:
        return "never built"
    return _get_meta(connection, _SUMMARY_DIRTY_KEY)


def rollup_delta_for(
    connection: sqlite3.Connection, offered: Sequence[tuple]
) -> tuple[dict[str, list[int]], dict[int, list[int]], int]:
    """Which of `offered` the archive does not already hold, folded by month and object.

    `offered` is the row tuples about to be handed to `INSERT OR IGNORE`; only
    the first two members, (norad, epoch_ms), are read. Must be called BEFORE
    the insert - afterwards every key is present and the delta is empty.

    Returns (by month, by object, new-row count), where each fold is
    [rows, min_epoch_ms, max_epoch_ms].
    """
    if not offered:
        return {}, {}, 0
    connection.execute(
        "CREATE TEMP TABLE IF NOT EXISTS offered_key ("
        "  norad INTEGER NOT NULL, epoch_ms INTEGER NOT NULL,"
        "  PRIMARY KEY (norad, epoch_ms)) WITHOUT ROWID"
    )
    connection.execute("DELETE FROM offered_key")
    # OR IGNORE: one batch may legitimately offer the same key twice, and the
    # archive would accept it once. The delta has to agree with that.
    connection.executemany(
        "INSERT OR IGNORE INTO offered_key VALUES (?,?)",
        [(row[0], row[1]) for row in offered],
    )
    novel = connection.execute(
        "SELECT o.norad, o.epoch_ms FROM offered_key o "
        "WHERE NOT EXISTS ("
        "  SELECT 1 FROM element_set e WHERE e.norad = o.norad AND e.epoch_ms = o.epoch_ms)"
    ).fetchall()
    by_month: dict[str, list[int]] = {}
    by_object: dict[int, list[int]] = {}
    for norad, epoch_ms in novel:
        for table, key in ((by_month, month_key(epoch_ms)), (by_object, norad)):
            fold = table.get(key)
            if fold is None:
                table[key] = [1, epoch_ms, epoch_ms]
            else:
                fold[0] += 1
                fold[1] = min(fold[1], epoch_ms)
                fold[2] = max(fold[2], epoch_ms)
    return by_month, by_object, len(novel)


def apply_rollup_delta(
    connection: sqlite3.Connection,
    by_month: dict[str, list[int]],
    by_object: dict[int, list[int]],
    *,
    inserted: int,
    expected: int,
) -> None:
    """Fold one insert's delta into the summaries, or refuse to.

    `inserted` is what the database says it accepted, `expected` is what
    `rollup_delta_for` predicted. They are the same number computed two ways,
    and if they ever disagree the summary would start drifting from the table
    silently -- so this raises instead. That is the whole guard.
    """
    if inserted != expected:
        raise ArchiveError(
            f"rollup delta predicted {expected} new element sets, the archive "
            f"accepted {inserted}; refusing to write a summary that already disagrees"
        )
    if not by_month:
        return
    connection.executemany(
        "INSERT INTO month_rollup(month, rows, min_epoch_ms, max_epoch_ms) VALUES (?,?,?,?) "
        "ON CONFLICT(month) DO UPDATE SET "
        "  rows = month_rollup.rows + excluded.rows,"
        "  min_epoch_ms = MIN(month_rollup.min_epoch_ms, excluded.min_epoch_ms),"
        "  max_epoch_ms = MAX(month_rollup.max_epoch_ms, excluded.max_epoch_ms)",
        [(month, fold[0], fold[1], fold[2]) for month, fold in by_month.items()],
    )
    connection.executemany(
        "INSERT INTO object_rollup(norad, rows, min_epoch_ms, max_epoch_ms) VALUES (?,?,?,?) "
        "ON CONFLICT(norad) DO UPDATE SET "
        "  rows = object_rollup.rows + excluded.rows,"
        "  min_epoch_ms = MIN(object_rollup.min_epoch_ms, excluded.min_epoch_ms),"
        "  max_epoch_ms = MAX(object_rollup.max_epoch_ms, excluded.max_epoch_ms)",
        [(norad, fold[0], fold[1], fold[2]) for norad, fold in by_object.items()],
    )


def refresh_summary(
    connection: sqlite3.Connection, *, page_rows: int | None = None
) -> dict:
    """Rebuild both rollups from `element_set` in one paged pass, and clear `dirty`.

    This is the only O(all rows) operation the summaries need, and it is paid
    once rather than once per query. It reads two columns instead of six and
    ends its read transaction every page, exactly like every other whole-archive
    scan here -- see `paged_element_sets` for why that is what keeps the hourly
    capture alive.

    The rollups are accumulated in memory first and swapped in at the end, so a
    pass that dies half way leaves the previous summary in place rather than a
    half-built one. The dirty flag is only cleared once the swap has committed.
    """
    started = time.time()
    by_month: dict[str, list[int]] = {}
    by_object: dict[int, list[int]] = {}
    total = 0
    for norad, epoch_ms in paged_element_sets(
        connection, page_rows=page_rows, columns="norad, epoch_ms"
    ):
        total += 1
        for table, key in ((by_month, month_key(epoch_ms)), (by_object, norad)):
            fold = table.get(key)
            if fold is None:
                table[key] = [1, epoch_ms, epoch_ms]
            else:
                fold[0] += 1
                fold[1] = min(fold[1], epoch_ms)
                fold[2] = max(fold[2], epoch_ms)

    connection.execute("DELETE FROM month_rollup")
    connection.execute("DELETE FROM object_rollup")
    connection.executemany(
        "INSERT INTO month_rollup(month, rows, min_epoch_ms, max_epoch_ms) VALUES (?,?,?,?)",
        [(month, f[0], f[1], f[2]) for month, f in by_month.items()],
    )
    connection.executemany(
        "INSERT INTO object_rollup(norad, rows, min_epoch_ms, max_epoch_ms) VALUES (?,?,?,?)",
        [(norad, f[0], f[1], f[2]) for norad, f in by_object.items()],
    )
    _set_meta(connection, _SUMMARY_BUILT_KEY, str(_now_ms()))
    connection.execute("DELETE FROM meta WHERE key = ?", (_SUMMARY_DIRTY_KEY,))
    connection.commit()
    return {
        "rows": total,
        "months": len(by_month),
        "objects": len(by_object),
        "seconds": round(time.time() - started, 3),
    }


def summary_totals(connection: sqlite3.Connection) -> tuple[int, int | None, int | None]:
    """(rows, earliest epoch, latest epoch) read from `month_rollup`.

    O(months): twelve rows a year, so 264 of them for the twenty-two years the
    bulk back-fill is importing. This is the read that replaces the full scan.
    """
    row = connection.execute(
        "SELECT COALESCE(SUM(rows), 0), MIN(min_epoch_ms), MAX(max_epoch_ms) FROM month_rollup"
    ).fetchone()
    return int(row[0]), row[1], row[2]


def busiest_norad(connection: sqlite3.Connection) -> int | None:
    """The object holding the most element sets, from `object_rollup`.

    O(objects): about 40,000 rows, against the `GROUP BY norad` over every
    element set that this replaces.
    """
    if summary_is_dirty(connection) is None:
        row = connection.execute(
            "SELECT norad FROM object_rollup ORDER BY rows DESC, norad ASC LIMIT 1"
        ).fetchone()
        if row:
            return int(row[0])
    # No trustworthy summary. Answer the question the slow way rather than
    # answering it wrongly: an empty rollup and an empty archive are different
    # things, and returning None for the first would quietly delete every gap
    # `_epoch_gaps` is supposed to find.
    row = connection.execute(
        "SELECT norad FROM element_set GROUP BY norad ORDER BY COUNT(*) DESC LIMIT 1"
    ).fetchone()
    return int(row[0]) if row else None


def archive_stats(connection: sqlite3.Connection, *, exact: bool = False) -> dict:
    """Shape of the archive. Reads the maintained summary unless it is dirty.

    `exact=True` forces the full scan. It exists for the one caller that needs
    the count as of this instant rather than as of the last summary write, and
    it is not the default because every caller in this pipeline reads only
    `earliestEpoch` and `latestEpoch` -- checked across `orbit_release`,
    `orbit_events` and `orbit_campaigns` on 2026-08-08 -- and none of them was
    worth 121.9 s of disk.

    `elementSetsSource` is part of the answer, not decoration: a number read
    from a summary and a number counted from the rows are different claims, and
    a consumer that cannot tell them apart will eventually publish the wrong one.
    """
    dirty = summary_is_dirty(connection)
    if exact or dirty:
        row = connection.execute(
            "SELECT COUNT(*), MIN(epoch_ms), MAX(epoch_ms) FROM element_set"
        ).fetchone()
        source = "scan"
    else:
        row = summary_totals(connection)
        source = "summary"
    objects = connection.execute("SELECT COUNT(*) FROM object").fetchone()[0]
    captures = connection.execute(
        "SELECT COUNT(*), MIN(captured_ms), MAX(captured_ms) FROM capture"
    ).fetchone()
    kp = connection.execute(
        "SELECT COUNT(*) FROM geomagnetic WHERE index_name='kp'"
    ).fetchone()[0]
    daily = connection.execute("SELECT COUNT(*) FROM element_set_daily").fetchone()[0]
    shards = connection.execute(
        "SELECT COUNT(*), COALESCE(SUM(rows),0), COALESCE(SUM(bytes),0) "
        "FROM cold_shard WHERE verified_ms IS NOT NULL"
    ).fetchone()
    return {
        "schemaVersion": SCHEMA_VERSION,
        "elementSets": row[0],
        "objects": objects,
        "earliestEpoch": _iso_or_none(row[1]),
        "latestEpoch": _iso_or_none(row[2]),
        "captures": captures[0],
        "firstCapture": _iso_or_none(captures[1]),
        "lastCapture": _iso_or_none(captures[2]),
        "kpSamples": kp,
        "dailySamples": daily,
        "coldShards": shards[0],
        "coldRows": shards[1],
        "coldBytes": shards[2],
        "elementSetsSource": source,
        "summaryStale": dirty,
    }


# ---------------------------------------------------------------------------
# Noise, and the detectors built on it
# ---------------------------------------------------------------------------
# Measured element-to-element scatter of the live catalogue, 2026-08-07, from
# 787 three-epoch triples: the middle element set is compared against the
# straight line through its neighbours, and the residual is divided by
# sqrt(1 + f^2 + (1-f)^2) to undo the interpolation's own error propagation.
# Keys are the upper bound of a perigee-altitude band, in km.
#
# These are floors, not estimates. An object whose own recent window happens
# to be unusually quiet would otherwise be handed a threshold of millimetres,
# and every subsequent element set would look like a burn. Sigma for
# inclination is at the 1e-4 deg quantisation limit in every band, which is
# to say the published inclination is rounded more coarsely than it is noisy.
CATALOGUE_NOISE_FLOOR: tuple[tuple[float, float, float, float], ...] = (
    #  perigee <=,  sigma_a km, sigma_e,  sigma_i deg
    (500.0,        1.67e-3,     1.3e-6,   1.0e-4),
    (800.0,        0.51e-3,     6.3e-7,   1.0e-4),
    (1500.0,       0.10e-3,     4.6e-7,   1.0e-4),
    (30000.0,      0.76e-3,     4.5e-7,   1.0e-4),
    (float("inf"), 12.44e-3,    1.1e-6,   1.7e-4),
)


def noise_floor_for(perigee_altitude_km: float) -> tuple[float, float, float]:
    """Measured (sigma_a km, sigma_e, sigma_i deg) for this altitude band.

    A NaN altitude gets the widest floor rather than an exception: refusing to
    judge is the right answer for an object whose elements are unusable.
    """
    if perigee_altitude_km != perigee_altitude_km:
        return CATALOGUE_NOISE_FLOOR[-1][1:]
    for upper, sigma_a, sigma_e, sigma_i in CATALOGUE_NOISE_FLOOR:
        if perigee_altitude_km <= upper:
            return sigma_a, sigma_e, sigma_i
    return CATALOGUE_NOISE_FLOOR[-1][1:]


def _floor_sigma(estimate: float, floor: float) -> float:
    """`max()` propagates NaN as the incumbent; this falls back to the floor."""
    return floor if estimate != estimate else max(estimate, floor)


def _mad_sigma(values: Sequence[float]) -> float:
    """Robust 1-sigma from the median absolute deviation.

    MAD rather than the standard deviation because a single manoeuvre in the
    window would inflate a standard deviation enough to hide itself.
    """
    if len(values) < 3:
        return float("nan")
    centre = statistics.median(values)
    mad = statistics.median([abs(v - centre) for v in values])
    return 1.4826 * mad


@dataclass(frozen=True)
class Rate:
    """One consecutive-pair difference, in per-day units."""

    start_ms: int
    end_ms: int
    span_days: float
    da_km_per_day: float
    de_per_day: float
    di_deg_per_day: float
    draan_resid_deg_per_day: float
    dargp_resid_deg_per_day: float
    a_start_km: float
    perigee_altitude_km: float


def rates(
    elements: Sequence[ElementSet],
    *,
    max_gap_days: float = 3.0,
    min_span_orbits: float = 0.0,
) -> list[Rate]:
    """First differences, with the J2 secular rates removed from RAAN and argp.

    Pairs separated by more than `max_gap_days` are dropped: across a long gap
    a step and a slow trend are not distinguishable, and reporting one as the
    other is exactly the failure mode this design is trying to avoid.

    `min_span_orbits` guards the opposite end, and it matters specifically for
    drag work. Neutral density swings by about a factor of two between the day
    and night sides, so a decay rate measured over a fraction of an orbit
    measures *local solar time*, not the atmosphere. Requiring the interval to
    span several complete revolutions makes each rate an orbit-averaged
    quantity. Manoeuvre detection deliberately leaves this at zero: a step is
    instantaneous and wants the shortest interval available.
    """
    out: list[Rate] = []
    for first, second in zip(elements, elements[1:]):
        span = (second.epoch_ms - first.epoch_ms) / 86_400_000.0
        if span <= 0 or span > max_gap_days:
            continue
        if min_span_orbits and span * first.mean_motion < min_span_orbits:
            continue
        raan_dot_j2, argp_dot_j2 = j2_secular_rates(first)
        draan = _wrap_deg(second.raan - first.raan) / span - raan_dot_j2
        dargp = _wrap_deg(second.arg_perigee - first.arg_perigee) / span - argp_dot_j2
        a0 = first.semi_major_axis_km
        out.append(
            Rate(
                start_ms=first.epoch_ms,
                end_ms=second.epoch_ms,
                span_days=span,
                da_km_per_day=(second.semi_major_axis_km - a0) / span,
                de_per_day=(second.eccentricity - first.eccentricity) / span,
                di_deg_per_day=(second.inclination - first.inclination) / span,
                draan_resid_deg_per_day=draan,
                dargp_resid_deg_per_day=dargp,
                a_start_km=a0,
                perigee_altitude_km=first.perigee_altitude_km,
            )
        )
    return out


def _wrap_deg(delta: float) -> float:
    """Fold an angle difference into (-180, 180]."""
    return (delta + 180.0) % 360.0 - 180.0


@dataclass(frozen=True)
class Event:
    kind: str                  # "manoeuvre-candidate" | "drag" | "station-keeping"
    start_ms: int
    end_ms: int
    evidence: dict
    confidence: str            # "candidate" always, until the FPR is measured


def noise_floor(rate_list: Sequence[Rate]) -> dict:
    """Per-object robust scatter of each differenced element.

    Measured on the live catalogue (787 three-epoch triples, 2026-08-07), the
    semi-major-axis scatter is 1.67 m below 500 km, 0.51 m from 500-800 km,
    0.10 m from 800-1500 km, 0.76 m in MEO and 12.44 m at GEO - the bands and
    values in `CATALOGUE_NOISE_FLOOR`, which is the authority. The distribution
    is strongly heavy-tailed, so a Gaussian threshold is meaningless and every
    detector here is calibrated on empirical quantiles instead.
    """
    if len(rate_list) < 8:
        return {"samples": len(rate_list), "sufficient": False}
    return {
        "samples": len(rate_list),
        "sufficient": True,
        "catalogueFloorMetres": (
            noise_floor_for(rate_list[-1].perigee_altitude_km)[0] * 1000.0
        ),
        "sigmaDaKmPerDay": _mad_sigma([r.da_km_per_day for r in rate_list]),
        "sigmaDePerDay": _mad_sigma([r.de_per_day for r in rate_list]),
        "sigmaDiDegPerDay": _mad_sigma([r.di_deg_per_day for r in rate_list]),
        "medianDaKmPerDay": statistics.median([r.da_km_per_day for r in rate_list]),
    }


def detect_manoeuvres(
    elements: Sequence[ElementSet],
    *,
    kappa: float = 8.0,
    min_samples: int = 8,
) -> list[Event]:
    """Step discontinuities in a, e or i, against the object's own scatter.

    `kappa` is a robust-sigma multiple, not a Gaussian confidence: with the
    measured heavy tails, kappa=8 corresponds to roughly the 99.5th
    percentile of the empirical residual distribution, not to 1e-15. The
    honest false-positive rate must be measured against the passive-object
    control population (see `false_positive_rate`), not assumed.

    Every candidate reports the neighbours it was NOT compared against; the
    cohort control lives in `screen_against_cohort` because it needs the
    whole archive, not one object.
    """
    rate_list = rates(elements)
    if len(rate_list) < min_samples:
        return []
    da = [r.da_km_per_day for r in rate_list]
    de = [r.de_per_day for r in rate_list]
    di = [r.di_deg_per_day for r in rate_list]
    events: list[Event] = []
    for index, rate in enumerate(rate_list):
        # Leave-one-out, so a large step cannot raise the bar it must clear.
        floor_a, floor_e, floor_i = noise_floor_for(rate.perigee_altitude_km)
        # The floors are absolute element scatter; a rate over a short span
        # divides that scatter by the span, so a six-hour gap has four times
        # the rate uncertainty of a one-day gap. Two element sets each carry
        # the scatter, hence the sqrt(2).
        spread = math.sqrt(2.0) / rate.span_days
        # `max` keeps NaN as the incumbent, so a short window would otherwise
        # silently disable the test rather than falling back to the floor.
        sigma_a = _floor_sigma(_mad_sigma(da[:index] + da[index + 1:]), floor_a * spread)
        sigma_e = _floor_sigma(_mad_sigma(de[:index] + de[index + 1:]), floor_e * spread)
        sigma_i = _floor_sigma(_mad_sigma(di[:index] + di[index + 1:]), floor_i * spread)
        centre_a = statistics.median(da[:index] + da[index + 1:])
        centre_e = statistics.median(de[:index] + de[index + 1:])
        centre_i = statistics.median(di[:index] + di[index + 1:])
        tripped = {}
        if sigma_a > 0 and abs(rate.da_km_per_day - centre_a) > kappa * sigma_a:
            tripped["semiMajorAxis"] = {
                "deltaMetres": (rate.da_km_per_day - centre_a) * rate.span_days * 1000.0,
                "sigmaMetres": sigma_a * rate.span_days * 1000.0,
                "z": (rate.da_km_per_day - centre_a) / sigma_a,
            }
        # Every element is tested against its own median rate, never against
        # zero. Eccentricity and inclination both drift secularly under
        # luni-solar perturbation - a GEO satellite's inclination walks about
        # 0.85 deg/year with nobody touching it - and testing those against
        # zero reports the drift itself as a burn on every single interval.
        if sigma_e > 0 and abs(rate.de_per_day - centre_e) > kappa * sigma_e:
            tripped["eccentricity"] = {
                "delta": (rate.de_per_day - centre_e) * rate.span_days,
                "z": (rate.de_per_day - centre_e) / sigma_e,
            }
        if sigma_i > 0 and abs(rate.di_deg_per_day - centre_i) > kappa * sigma_i:
            tripped["inclination"] = {
                "deltaDegrees": (rate.di_deg_per_day - centre_i) * rate.span_days,
                "z": (rate.di_deg_per_day - centre_i) / sigma_i,
            }
        if not tripped:
            continue
        events.append(
            Event(
                kind="manoeuvre-candidate",
                start_ms=rate.start_ms,
                end_ms=rate.end_ms,
                evidence={
                    "elements": tripped,
                    "spanDays": rate.span_days,
                    "kappa": kappa,
                    "deltaVEstimateMetresPerSecond": (
                        _delta_v_from_da(rate) if "semiMajorAxis" in tripped else None
                    ),
                    "cohortScreened": False,
                },
                confidence="candidate",
            )
        )
    return events


def _delta_v_from_da(rate: Rate) -> float:
    """Impulsive tangential dv that would produce this change in a.

    dv = n a / 2 * (da / a) for a near-circular orbit. Stated as an *upper
    bound on the smallest* manoeuvre consistent with the observation: any
    other thrust direction needs more.
    """
    a = rate.a_start_km
    n = math.sqrt(MU_WGS72 / a**3)          # rad/s
    da_km = rate.da_km_per_day * rate.span_days
    return 0.5 * n * da_km * 1000.0         # m/s


ORBIT_AVERAGING_MINIMUM = 3.0
"""Complete revolutions a decay-rate interval must span.

Below this, the number being reported is contaminated by the diurnal density
bulge rather than describing the thermosphere the object flew through.
"""


def detect_drag(
    elements: Sequence[ElementSet],
    *,
    min_samples: int = 10,
    significance: float = 3.0,
    min_span_orbits: float = ORBIT_AVERAGING_MINIMUM,
) -> list[Event]:
    """A sustained, negative, accelerating trend in semi-major axis.

    Drag is the only common perturbation that removes energy secularly, so a
    negative slope in a that is significant against the object's own scatter
    is the signature. Curvature - the decay accelerating as it goes - is what
    separates it from a slow sequence of retrograde burns.
    """
    rate_list = rates(elements, min_span_orbits=min_span_orbits)
    if len(rate_list) < min_samples:
        return []
    da = [r.da_km_per_day for r in rate_list]
    median_span = statistics.median([r.span_days for r in rate_list])
    floor_a, _, _ = noise_floor_for(rate_list[-1].perigee_altitude_km)
    sigma = _floor_sigma(_mad_sigma(da), floor_a * math.sqrt(2.0) / median_span)
    median = statistics.median(da)
    if not (sigma > 0) or median >= 0:
        return []
    standard_error = 1.2533 * sigma / math.sqrt(len(da))
    if abs(median) < significance * standard_error:
        return []
    first_half = statistics.median(da[: len(da) // 2])
    second_half = statistics.median(da[len(da) // 2:])
    return [
        Event(
            kind="drag",
            start_ms=rate_list[0].start_ms,
            end_ms=rate_list[-1].end_ms,
            evidence={
                "medianDecayMetresPerDay": median * 1000.0,
                "standardErrorMetresPerDay": standard_error * 1000.0,
                "accelerating": second_half < first_half,
                "firstHalfMetresPerDay": first_half * 1000.0,
                "secondHalfMetresPerDay": second_half * 1000.0,
                "perigeeAltitudeKm": rate_list[-1].perigee_altitude_km,
                "meanBstar": statistics.median(
                    [e.bstar for e in elements if e.bstar is not None] or [0.0]
                ),
                "samples": len(da),
            },
            confidence="candidate",
        )
    ]


def detect_station_keeping(
    elements: Sequence[ElementSet],
    *,
    min_events: int = 4,
    kappa: float = 6.0,
) -> list[Event]:
    """Small, repeated, roughly periodic corrections.

    GEO east-west keeping shows as recurring steps in semi-major axis with a
    cadence of days to weeks; north-south keeping shows as steps in
    inclination, typically much rarer and much larger. We report the cadence
    and its regularity, and require the intervals to be regular - a
    coefficient of variation below 0.6 - because that regularity is the whole
    discriminator against a run of unrelated manoeuvres.
    """
    steps = detect_manoeuvres(elements, kappa=kappa)
    if len(steps) < min_events:
        return []
    times = [(event.start_ms + event.end_ms) / 2.0 for event in steps]
    intervals = [
        (later - earlier) / 86_400_000.0 for earlier, later in zip(times, times[1:])
    ]
    if len(intervals) < 2:
        return []
    mean_interval = statistics.fmean(intervals)
    if mean_interval <= 0:
        return []
    cv = statistics.pstdev(intervals) / mean_interval
    if cv > 0.6:
        return []
    magnitudes = [
        abs(event.evidence["elements"].get("semiMajorAxis", {}).get("deltaMetres", 0.0))
        for event in steps
    ]
    return [
        Event(
            kind="station-keeping",
            start_ms=steps[0].start_ms,
            end_ms=steps[-1].end_ms,
            evidence={
                "correctionCount": len(steps),
                "meanIntervalDays": mean_interval,
                "intervalCoefficientOfVariation": cv,
                "medianStepMetres": statistics.median(magnitudes) if magnitudes else None,
                "meanMotionRevPerDay": statistics.median(
                    [e.mean_motion for e in elements]
                ),
            },
            confidence="candidate",
        )
    ]


def false_positive_rate(
    connection: sqlite3.Connection,
    *,
    kappa: float = 8.0,
    limit: int | None = None,
) -> dict:
    """Measure the manoeuvre detector's false-positive rate on passive objects.

    DEBRIS and ROCKET BODY objects cannot manoeuvre. Every manoeuvre the
    detector reports on one of them is, by construction, a false positive.
    The live catalogue carries 9,881 debris and 2,199 rocket bodies, so this
    control set is large, free, and contemporaneous - it measures the
    detector against the same fits, the same tracking outages and the same
    space weather as the payloads it is judging.

    This is the number that must be published beside any inference shown to a
    visitor, and it is the reason nothing here is labelled better than
    "candidate" until it has been run over a real archive.
    """
    query = (
        "SELECT norad FROM object WHERE object_type IN ('DEBRIS','ROCKET BODY') "
        "ORDER BY norad"
    )
    if limit and limit > 0:
        query += f" LIMIT {int(limit)}"
    flagged = 0
    intervals = 0
    objects = 0
    for (norad,) in connection.execute(query).fetchall():
        elements = series(connection, norad)
        pair_count = len(rates(elements))
        if pair_count < 8:
            continue
        objects += 1
        intervals += pair_count
        flagged += len(detect_manoeuvres(elements, kappa=kappa))
    return {
        "kappa": kappa,
        "controlObjects": objects,
        "controlIntervals": intervals,
        "falsePositives": flagged,
        "falsePositiveRatePerInterval": (flagged / intervals) if intervals else None,
        "note": (
            "Debris and spent stages cannot manoeuvre; any flag here is a false "
            "positive. Run this before showing manoeuvre inferences to visitors."
        ),
    }


# ---------------------------------------------------------------------------
# Population drag: the storm tie-in
# ---------------------------------------------------------------------------
def population_decay(
    connection: sqlite3.Connection,
    *,
    start_ms: int,
    end_ms: int,
    shell_km: float = 50.0,
    passive_only: bool = True,
    min_objects: int = 20,
    min_span_orbits: float = ORBIT_AVERAGING_MINIMUM,
) -> list[dict]:
    """Median decay rate per perigee-altitude shell over one interval.

    Binned on *perigee* altitude, not semi-major axis, because drag does its
    work at perigee. Restricted by default to passive objects - debris and
    spent stages - because a manoeuvring payload contaminates the very
    quantity being measured, and because a passive object is a clean
    ballistic tracer of the density it flies through.
    """
    types = ("DEBRIS", "ROCKET BODY")
    where = "WHERE object_type IN (?,?)" if passive_only else ""
    params = types if passive_only else ()
    buckets: dict[int, list[float]] = {}
    # Distinct objects, tracked separately from intervals. One object with
    # forty element sets is one tracer of the density, not forty, and gating
    # on interval count would let a handful of objects carry a whole shell.
    members: dict[int, set[int]] = {}
    for (norad,) in connection.execute(
        f"SELECT norad FROM object {where} ORDER BY norad", params
    ):
        elements = series(connection, norad, since_ms=start_ms, until_ms=end_ms)
        for rate in rates(elements, min_span_orbits=min_span_orbits):
            if rate.perigee_altitude_km < 150 or rate.perigee_altitude_km > 1400:
                continue
            index = int(rate.perigee_altitude_km // shell_km)
            buckets.setdefault(index, []).append(rate.da_km_per_day)
            members.setdefault(index, set()).add(norad)
    out = []
    for index in sorted(buckets):
        values = buckets[index]
        objects = len(members[index])
        if objects < min_objects:
            continue
        median = statistics.median(values)
        sigma = _mad_sigma(values)
        out.append(
            {
                "perigeeAltitudeKm": [index * shell_km, (index + 1) * shell_km],
                "objects": objects,
                "intervals": len(values),
                "medianDecayMetresPerDay": median * 1000.0,
                # Median standard error for a roughly symmetric distribution,
                # taken over independent objects rather than over intervals.
                "standardErrorMetresPerDay": (
                    1.2533 * sigma / math.sqrt(objects) * 1000.0
                    if sigma == sigma
                    else None
                ),
            }
        )
    return out


def _passive_norads(connection: sqlite3.Connection) -> list[int]:
    return [
        row[0]
        for row in connection.execute(
            "SELECT norad FROM object WHERE object_type IN ('DEBRIS','ROCKET BODY') "
            "ORDER BY norad"
        )
    ]


def _median_decay(
    connection: sqlite3.Connection,
    norad: int,
    start_ms: int,
    end_ms: int,
    min_span_orbits: float,
) -> tuple[float, float] | None:
    """(median da/dt in km/day, perigee altitude) over one window, or None."""
    rate_list = rates(
        series(connection, norad, since_ms=start_ms, until_ms=end_ms),
        min_span_orbits=min_span_orbits,
    )
    if len(rate_list) < 2:
        return None
    return (
        statistics.median([r.da_km_per_day for r in rate_list]),
        statistics.median([r.perigee_altitude_km for r in rate_list]),
    )


def density_enhancement(
    connection: sqlite3.Connection,
    *,
    quiet_start_ms: int,
    quiet_end_ms: int,
    storm_start_ms: int,
    storm_end_ms: int,
    shell_km: float = 50.0,
    min_objects: int = 20,
    min_span_orbits: float = ORBIT_AVERAGING_MINIMUM,
) -> list[dict]:
    """Thermospheric density ratio per altitude shell, measured with satellites.

    Because decay is linear in neutral density,

        adot = -(C_D A / m) rho sqrt(mu a)

    the ballistic coefficient cancels exactly in the ratio of one object's
    storm-time decay to its own quiet-time decay, and what is left is
    rho_storm / rho_quiet at that altitude. No accelerometer, no drag
    coefficient, no assumed area - only the element sets already archived.

    Ratios are formed **per object against its own baseline** and only then
    combined, never as a ratio of two population medians: a changing mix of
    objects between the two windows would otherwise be read as a change in
    the atmosphere.

    Restricted to passive objects. A manoeuvring payload contaminates exactly
    the quantity being measured, and a spent stage is a clean ballistic tracer.

    `pipeline/thermosphere.py:decay_rate_km_per_day()` is the forward version
    of the same physics - density in, decay rate out, same km/day sign
    convention - so a density from that model can be checked against the
    decay measured here, and vice versa.
    """
    ratios: dict[int, list[float]] = {}
    members: dict[int, set[int]] = {}
    for norad in _passive_norads(connection):
        quiet = _median_decay(
            connection, norad, quiet_start_ms, quiet_end_ms, min_span_orbits
        )
        storm = _median_decay(
            connection, norad, storm_start_ms, storm_end_ms, min_span_orbits
        )
        if quiet is None or storm is None:
            continue
        quiet_rate, perigee = quiet
        # A quiet baseline at or above zero is not a drag measurement; it is
        # noise or an unflagged manoeuvre, and dividing by it invents a ratio.
        if quiet_rate >= 0 or perigee < 150 or perigee > 1400:
            continue
        ratios.setdefault(int(perigee // shell_km), []).append(
            storm[0] / quiet_rate
        )
        members.setdefault(int(perigee // shell_km), set()).add(norad)

    out = []
    for index in sorted(ratios):
        values = ratios[index]
        objects = len(members[index])
        if objects < min_objects:
            continue
        sigma = _mad_sigma(values)
        out.append(
            {
                "perigeeAltitudeKm": [index * shell_km, (index + 1) * shell_km],
                "objects": objects,
                "densityRatio": statistics.median(values),
                "standardError": (
                    1.2533 * sigma / math.sqrt(objects) if sigma == sigma else None
                ),
                "note": (
                    "Ratio of storm-time to quiet-time orbital decay, per object "
                    "against its own baseline. The ballistic coefficient cancels, "
                    "so this is a measurement of neutral density enhancement."
                ),
            }
        )
    return out


def kp_series(
    connection: sqlite3.Connection, *, start_ms: int, end_ms: int
) -> list[tuple[int, float]]:
    return [
        (row[0], row[1])
        for row in connection.execute(
            "SELECT observed_ms, value FROM geomagnetic "
            "WHERE index_name='kp' AND observed_ms BETWEEN ? AND ? "
            "ORDER BY observed_ms",
            (start_ms, end_ms),
        )
    ]


# ---------------------------------------------------------------------------
# Cold shards: zig-zag varint deltas, one file per UTC month
# ---------------------------------------------------------------------------
def _zigzag(value: int) -> int:
    return (value << 1) ^ (value >> 63)


def _unzigzag(value: int) -> int:
    return (value >> 1) ^ -(value & 1)


def encode_varints(values: Iterable[int]) -> bytes:
    out = bytearray()
    for value in values:
        v = _zigzag(int(value))
        while True:
            byte = v & 0x7F
            v >>= 7
            if v:
                out.append(byte | 0x80)
            else:
                out.append(byte)
                break
    return bytes(out)


def decode_varints(data: bytes) -> Iterator[int]:
    shift = 0
    acc = 0
    for byte in data:
        acc |= (byte & 0x7F) << shift
        if byte & 0x80:
            shift += 7
            continue
        yield _unzigzag(acc)
        acc = 0
        shift = 0


_COLD_MAGIC = b"OHZ1"
_MISSING = -(2**62)   # sentinel for a NULL in an integer column


def encode_shard(rows: Sequence[tuple]) -> bytes:
    """Columnar, delta-against-the-object's-previous-row, varint, zlib.

    Rows must be ordered by (norad, epoch_ms). Delta encoding is applied
    within each object, which is where it pays: a LEO object's semi-major
    axis moves a few metres between element sets, so the quantised delta is a
    two-byte varint instead of a ten-digit absolute.
    """
    columns: list[list[int]] = [[] for _ in range(13)]
    previous: dict[int, tuple] = {}
    last_norad = 0
    for row in rows:
        norad = row[0]
        columns[0].append(norad - last_norad)
        last_norad = norad
        base = previous.get(norad)
        for position in range(1, 13):
            value = row[position]
            if value is None:
                columns[position].append(_MISSING)
                continue
            reference = 0
            if base is not None and base[position] is not None:
                reference = base[position]
            columns[position].append(value - reference)
        previous[norad] = row
    body = bytearray(_COLD_MAGIC)
    body += len(rows).to_bytes(4, "little")
    blocks = [encode_varints(column) for column in columns]
    for block in blocks:
        body += len(block).to_bytes(4, "little")
    for block in blocks:
        body += block
    return zlib.compress(bytes(body), 9)


def decode_shard(blob: bytes) -> list[tuple]:
    raw = zlib.decompress(blob)
    if raw[:4] != _COLD_MAGIC:
        raise ArchiveError("not an orbit-history cold shard")
    count = int.from_bytes(raw[4:8], "little")
    offset = 8
    lengths = []
    for _ in range(13):
        lengths.append(int.from_bytes(raw[offset:offset + 4], "little"))
        offset += 4
    columns = []
    for length in lengths:
        columns.append(list(decode_varints(raw[offset:offset + length])))
        offset += length
    rows: list[tuple] = []
    previous: dict[int, list] = {}
    norad = 0
    for index in range(count):
        norad += columns[0][index]
        base = previous.get(norad)
        row: list = [norad]
        for position in range(1, 13):
            delta = columns[position][index]
            if delta == _MISSING:
                row.append(None)
                continue
            reference = 0
            if base is not None and base[position] is not None:
                reference = base[position]
            row.append(reference + delta)
        previous[norad] = row
        rows.append(tuple(row))
    return rows


def month_bounds(year: int, month: int) -> tuple[int, int]:
    start = dt.datetime(year, month, 1, tzinfo=dt.timezone.utc)
    end = dt.datetime(
        year + (month // 12), (month % 12) + 1, 1, tzinfo=dt.timezone.utc
    )
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def export_month(
    connection: sqlite3.Connection,
    year: int,
    month: int,
    destination: Path,
    *,
    verify: bool = True,
) -> dict:
    """Write one immutable monthly cold shard, then read it back.

    Deletes nothing. `roll()` is what connects this to pruning, and it will
    not prune a month whose shard did not verify.
    """
    start_ms, end_ms = month_bounds(year, month)
    rows = list(
        connection.execute(
            f"SELECT norad, {', '.join(_ELEMENT_COLUMNS)}, ingest_hour "
            "FROM element_set WHERE epoch_ms >= ? AND epoch_ms < ? "
            "ORDER BY norad, epoch_ms",
            (start_ms, end_ms),
        )
    )
    existing = connection.execute(
        "SELECT verified_ms FROM cold_shard WHERE month = ?",
        (f"{year:04d}-{month:02d}",),
    ).fetchone()
    if existing and existing[0] is not None and not verify:
        raise ArchiveError(
            f"refusing to replace the verified shard for {year:04d}-{month:02d} "
            "with an unverified one"
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    blob = encode_shard(rows)
    temporary = destination.with_suffix(destination.suffix + ".next")
    temporary.write_bytes(blob)

    # Verify the temporary file, THEN swap. Verifying after the swap means a
    # corrupt encode has already destroyed the good shard by the time we find
    # out, while the ledger still describes the one that is gone.
    verified_ms = None
    if verify:
        if decode_shard(temporary.read_bytes()) != rows:
            temporary.unlink(missing_ok=True)
            raise ArchiveError(
                f"{destination} did not read back identically; the previous shard "
                "is untouched"
            )
        verified_ms = _now_ms()
    os.replace(temporary, destination)

    connection.execute(
        "INSERT OR REPLACE INTO cold_shard VALUES (?,?,?,?,?,?,?)",
        (
            f"{year:04d}-{month:02d}",
            str(destination),
            len(rows),
            len(blob),
            hashlib.sha256(blob).hexdigest(),
            _now_ms(),
            verified_ms,
        ),
    )
    connection.commit()
    return {
        "month": f"{year:04d}-{month:02d}",
        "path": str(destination),
        "rows": len(rows),
        "bytes": len(blob),
        "bytesPerRow": (len(blob) / len(rows)) if rows else None,
        "verified": verified_ms is not None,
    }


def shard_path(cold_directory: Path, year: int, month: int) -> Path:
    """Where the shard for one UTC month lives. One name, defined once.

    `export_month` and every reader have to agree on this, and they used to
    agree by both spelling the same f-string.
    """
    return cold_directory / f"orbit-history-{year:04d}-{month:02d}.ohz"


def read_cold_month(
    cold_directory: Path, year: int, month: int
) -> list[tuple] | None:
    """Every row of one cold month, or None if no shard was written for it.

    None and [] are different answers and the caller needs both: no shard means
    the archive cannot speak for that month, while an empty shard means it can
    and the month is genuinely empty. Collapsing them is how a gap becomes an
    assertion that nothing was in orbit.
    """
    path = shard_path(cold_directory, year, month)
    if not path.exists():
        return None
    return decode_shard(path.read_bytes())


def cold_series(
    cold_directory: Path,
    norad: int,
    *,
    start_ms: int,
    end_ms: int,
) -> list[ElementSet]:
    """One object's history from cold storage, across however many months it spans.

    This is the read that makes the hot/cold split invisible to a reader asking
    about 2009: tier 1 no longer holds it, and the answer still comes back. Only
    the months the window actually touches are opened, so the cost is set by the
    length of the question rather than by the size of the archive.
    """
    if end_ms < start_ms:
        return []
    found: list[ElementSet] = []
    stamp = epoch_ms_to_datetime(start_ms)
    year, month = stamp.year, stamp.month
    while True:
        bounds = month_bounds(year, month)
        if bounds[0] > end_ms:
            break
        rows = read_cold_month(cold_directory, year, month)
        if rows is not None:
            found.extend(
                _element_from_row(row[0], row[1:1 + len(_ELEMENT_COLUMNS)])
                for row in rows
                if row[0] == norad and start_ms <= row[1] <= end_ms
            )
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    found.sort(key=lambda element: element.epoch_ms)
    return found


def decimate_day(connection: sqlite3.Connection, day: int) -> dict:
    """Fold one UTC day of element sets into tier 2.

    The element set nearest 12:00 UTC is the one kept. Nearest-to-noon rather
    than first-of-day so the daily sample is not systematically biased towards
    whichever objects happen to be re-fitted just after midnight.
    """
    start_ms = day * 86_400_000
    end_ms = start_ms + 86_400_000
    noon = start_ms + 43_200_000
    columns = ", ".join(_ELEMENT_COLUMNS)
    rows = list(
        connection.execute(
            f"SELECT norad, {columns} FROM element_set "
            "WHERE epoch_ms >= ? AND epoch_ms < ? ORDER BY norad, epoch_ms",
            (start_ms, end_ms),
        )
    )
    best: dict[int, tuple] = {}
    for row in rows:
        norad = row[0]
        current = best.get(norad)
        if current is None or abs(row[1] - noon) < abs(current[1] - noon):
            best[norad] = row
    connection.executemany(
        "INSERT OR REPLACE INTO element_set_daily VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [(row[0], day) + tuple(row[1:]) for row in best.values()],
    )
    connection.execute(
        "INSERT OR REPLACE INTO decimated_day VALUES (?,?,?,?)",
        (day, len(rows), len(best), _now_ms()),
    )
    connection.commit()
    return {"day": day, "rowsIn": len(rows), "rowsKept": len(best)}


def daily_series(
    connection: sqlite3.Connection, norad: int, *, since_day: int | None = None
) -> list[ElementSet]:
    """Tier 2 read: one element set per object per day, for long baselines."""
    query = (
        f"SELECT {', '.join(_ELEMENT_COLUMNS)} FROM element_set_daily WHERE norad = ?"
    )
    params: list = [norad]
    if since_day is not None:
        query += " AND day >= ?"
        params.append(since_day)
    query += " ORDER BY day"
    return [_element_from_row(norad, row) for row in connection.execute(query, params)]


def pruned_before_ms(connection: sqlite3.Connection) -> int:
    """The high-water mark of everything ever deleted from tier 1.

    A row count cannot stand in for this. A month that was pruned and then
    received late element sets can climb back above its recorded shard row
    count, and re-exporting it would rewrite the shard from the surviving
    rows only - permanently losing the pruned ones from the one full-fidelity
    copy. The watermark is monotonic and cannot be fooled that way.
    """
    row = connection.execute(
        "SELECT value FROM meta WHERE key='pruned_before_ms'"
    ).fetchone()
    return int(row[0]) if row else 0


def prune_hot(connection: sqlite3.Connection, before_ms: int, *, force: bool = False) -> int:
    """Drop tier-1 element sets older than `before_ms`.

    Refuses unless every UTC day being deleted has been decimated into tier 2
    and is covered by a cold shard that read back identically. `force` exists
    for the one legitimate case - deliberately discarding data you have
    decided not to keep - and says so in its name.
    """
    if not force:
        unsafe = _undecimated_or_unshipped_days(connection, before_ms)
        if unsafe:
            raise ArchiveError(
                f"refusing to prune: {len(unsafe)} day(s) before "
                f"{epoch_ms_to_datetime(before_ms).date()} are not both decimated "
                f"and inside a verified cold shard (first: day {unsafe[0]}). "
                "Run roll() or export the month first."
            )
    # Which months are about to lose rows, recorded before the delete makes the
    # question unanswerable. `month_rollup` already knows, in O(months).
    losing = [
        (row[0], row[1])
        for row in connection.execute(
            "SELECT month, rows FROM month_rollup WHERE min_epoch_ms < ?", (before_ms,)
        )
    ]
    cursor = connection.execute(
        "DELETE FROM element_set WHERE epoch_ms < ?", (before_ms,)
    )
    deleted = cursor.rowcount

    # THE WATERMARK MOVES ONLY IF ROWS ACTUALLY LEFT.
    #
    # It used not to, and that is the bug this guard is named after. On
    # 2026-08-07 `roll()` called this with a 400-day cutoff against an archive
    # that then held only the previous day's live capture. Nothing was older
    # than the cutoff, the DELETE removed zero rows -- and the watermark was
    # advanced to 2025-07-03 anyway, because the write was unconditional. Every
    # month the bulk back-fill has imported since then begins before that
    # instant, so `roll()` has refused to export any of them to cold storage
    # ever since, and the cold directory still holds exactly one 10 KB shard.
    #
    # This is a defect class this codebase has produced before, not a one-off:
    # a guard that advances its state on a no-op. The state is meant to record
    # something that happened. If it did not happen, nothing may be recorded --
    # and `deleted == 0` is the whole test, because a DELETE that removed no
    # rows destroyed no history and therefore leaves nothing to protect.
    if deleted:
        connection.execute(
            "INSERT INTO meta(key, value) VALUES('pruned_before_ms', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = MAX(CAST(value AS INTEGER), ?)",
            (str(before_ms), before_ms),
        )
        connection.executemany(
            "INSERT INTO pruned_month(month, rows_deleted, pruned_ms) VALUES (?,?,?) "
            "ON CONFLICT(month) DO UPDATE SET "
            "  rows_deleted = pruned_month.rows_deleted + excluded.rows_deleted,"
            "  pruned_ms = excluded.pruned_ms",
            [(month, rows, _now_ms()) for month, rows in losing],
        )
        # A delete can raise an object's earliest epoch and lower a month's row
        # count, and there is no cheap way to say by how much per object. Rather
        # than write a summary that is nearly right, say it is stale: the next
        # `refresh_summary` makes it exact, and until then `archive_stats`
        # counts honestly.
        mark_summary_dirty(connection, f"prune removed {deleted} rows")
    connection.commit()
    return deleted


def _undecimated_or_unshipped_days(
    connection: sqlite3.Connection, before_ms: int
) -> list[int]:
    present = [
        row[0]
        for row in connection.execute(
            "SELECT DISTINCT epoch_ms / 86400000 FROM element_set WHERE epoch_ms < ?",
            (before_ms,),
        )
    ]
    decimated = {
        row[0] for row in connection.execute("SELECT day FROM decimated_day")
    }
    # Trusting the ledger alone authorises a delete against a shard that has
    # been moved, truncated or lost. Check the file, and its digest.
    shipped = set()
    for month, path, digest in connection.execute(
        "SELECT month, path, sha256 FROM cold_shard WHERE verified_ms IS NOT NULL"
    ):
        shard = Path(path)
        if not shard.exists():
            continue
        if hashlib.sha256(shard.read_bytes()).hexdigest() != digest:
            continue
        shipped.add(month)
    unsafe = []
    for day in sorted(present):
        stamp = epoch_ms_to_datetime(day * 86_400_000)
        if day not in decimated or f"{stamp.year:04d}-{stamp.month:02d}" not in shipped:
            unsafe.append(day)
    return unsafe


def roll(
    connection: sqlite3.Connection,
    *,
    retain_days: int,
    cold_directory: Path,
    now_ms: int | None = None,
) -> dict:
    """Decimate, export, verify, then prune - in that order, every time.

    `retain_days` is required and has no default here on purpose. The publish
    path passes it explicitly, the way `pipeline/publish_vps.sh` passes
    `--max-age-hours` to `deploy/prune_data.py`, so the retention policy is
    readable at the place it is applied.
    """
    now = now_ms if now_ms is not None else _now_ms()
    today = now // 86_400_000
    report: dict = {
        "retainDays": retain_days,
        "decimated": [],
        "exported": [],
        "skipped": [],
        "pruned": 0,
    }

    # 1. Decimate settled days. A day is left alone for SETTLE_DAYS because
    #    18 SPCS does publish element sets whose epoch is already a day or two
    #    old, and decimating too eagerly would pick the wrong representative.
    done = {
        row[0]: row[1]
        for row in connection.execute("SELECT day, rows_in FROM decimated_day")
    }
    # `day <= today - SETTLE`, so the newest day considered is exactly
    # DECIMATION_SETTLE_DAYS old rather than one more than that.
    settled_before = (today - DECIMATION_SETTLE_DAYS + 1) * 86_400_000
    for day, held in connection.execute(
        "SELECT epoch_ms / 86400000 AS d, COUNT(*) FROM element_set "
        "WHERE epoch_ms < ? GROUP BY d ORDER BY d",
        (settled_before,),
    ).fetchall():
        # Re-decimate a day that gained element sets after it was folded: the
        # late arrival may be the one nearest noon, and the module already
        # accepts that late arrivals happen.
        if done.get(day) != held:
            report["decimated"].append(decimate_day(connection, day))

    # 2. Export every complete month. A month whose shard already holds MORE
    #    rows than the database does has been partially pruned, and rewriting
    #    it would silently destroy the only full-fidelity copy. Skip, loudly.
    watermark = pruned_before_ms(connection)
    report["prunedBeforeMs"] = watermark
    # Asked per month, not against the scalar watermark. The hazard being
    # avoided is real -- re-exporting a month that has been partly pruned would
    # rewrite its shard from the surviving rows and lose the rest -- but the
    # watermark answers a much broader question than the hazard asks. It says
    # "everything before this instant is suspect", which condemns every month
    # earlier than the newest prune, including the twenty-two years of
    # back-filled history that no prune has ever touched. `pruned_month` records
    # only what was actually taken.
    pruned_months = {
        row[0] for row in connection.execute("SELECT month FROM pruned_month")
    }
    for year, month in _months_with_rows(connection, before_ms=now):
        label = f"{year:04d}-{month:02d}"
        start_ms, end_ms = month_bounds(year, month)
        if end_ms > now:
            continue                        # still filling up
        if label in pruned_months:
            report["skipped"].append(
                {
                    "month": label,
                    "reason": "rows have already been pruned out of this month; "
                    "rewriting its shard would lose them",
                    "prunedBeforeMs": watermark,
                }
            )
            continue
        destination = shard_path(cold_directory, year, month)
        report["exported"].append(export_month(connection, year, month, destination))

    # 3. Prune, which refuses anything not decimated and verified.
    cutoff = (today - retain_days) * 86_400_000
    if cutoff > 0:
        try:
            report["pruned"] = prune_hot(connection, cutoff)
        except ArchiveError as error:
            report["pruneSkipped"] = str(error)

    # 4. Leave the summary exact. A prune that removed rows marked it dirty, and
    #    a dirty summary sends every later `archive_stats` back to the full scan
    #    this whole tier exists to avoid. Rebuilding here means the O(all rows)
    #    pass happens once, on the daily timer, instead of on every read.
    if summary_is_dirty(connection) is not None:
        report["summaryRefresh"] = refresh_summary(connection)
    return report


def _months_with_rows(
    connection: sqlite3.Connection, *, before_ms: int
) -> list[tuple[int, int]]:
    """Which UTC months hold element sets, from the summary when it is trustworthy.

    The scan version reads every row to answer a question with 264 possible
    answers, which is the shape of problem `month_rollup` was added for. The
    scan is kept for the dirty case rather than deleted, because a wrong list
    here is a month that never reaches cold storage.
    """
    if summary_is_dirty(connection) is None:
        return sorted(
            (int(month[:4]), int(month[5:7]))
            for (month,) in connection.execute(
                "SELECT month FROM month_rollup WHERE min_epoch_ms < ?", (before_ms,)
            )
        )
    months = set()
    for (day,) in connection.execute(
        "SELECT DISTINCT epoch_ms / 86400000 FROM element_set WHERE epoch_ms < ?",
        (before_ms,),
    ):
        stamp = epoch_ms_to_datetime(day * 86_400_000)
        months.add((stamp.year, stamp.month))
    return sorted(months)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _default_mirror() -> Path:
    override = os.environ.get("SPACE_EXPLORER_SPACETRACK_MIRROR")
    base = Path(override) if override else ROOT / "runtime" / "spacetrack-mirror"
    return base / "gp-active.json"


def starved_capture_report(
    mirror_path: Path, *, waited_seconds: float, archive_path: Path
) -> str:
    """What a capture that could not get the lock has to say for itself.

    A bare `sqlite3.OperationalError: database is locked` traceback is the wrong
    report for this failure in the one way that matters: it reads like a
    transient database problem, and it is not. It is a permanent hole in the
    archive, and the operator needs to know which hour is missing before the
    next fetch overwrites the evidence.

    `gp-active.json` is rewritten in place by the next `spacetrack-ingest` run,
    so the element sets this capture failed to read cease to exist within the
    hour. There is no back-fill for them: space-track's yearly bundles are
    published a year in arrears, and `orbit_history_backfill` can only import
    what has been published.
    """
    try:
        mtime = dt.datetime.fromtimestamp(
            mirror_path.stat().st_mtime, dt.timezone.utc
        ).isoformat(timespec="seconds").replace("+00:00", "Z")
    except OSError:
        mtime = "unknown (the mirror could not be stat'd)"
    now = dt.datetime.now(dt.timezone.utc)
    hour = now.strftime("%Y-%m-%dT%H:00Z")
    return (
        f"THE {hour} CAPTURE WAS LOST. Waited {waited_seconds:.0f} s for a write lock on "
        f"{archive_path} and never got one, so nothing from the mirror was archived.\n"
        f"  mirror:            {mirror_path}\n"
        f"  mirror written at: {mtime}\n"
        "  recoverable:       NO. The next spacetrack-ingest run overwrites gp-active.json "
        "in place, and space-track publishes its yearly bundles a year in arrears, so no "
        "back-fill can supply this hour.\n"
        "  cause:             another process is holding the archive. In rollback-journal "
        "mode a long-lived READER blocks a writer from reaching EXCLUSIVE, and a writer "
        "waiting at PENDING blocks new readers in turn.\n"
        "  look at:           orbit-release.service (whole-archive scans) and any running "
        "pipeline.orbit_history_backfill (hours-long writer).\n"
        "  tunable:           SPACE_EXPLORER_ORBIT_ARCHIVE_TIMEOUT_SECONDS "
        f"(currently {busy_timeout_seconds():.0f} s), SPACE_EXPLORER_ORBIT_SCAN_PAGE_ROWS "
        f"(currently {scan_page_rows()})."
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Archive space-track GP element sets. Makes no network requests."
    )
    parser.add_argument("--archive", type=Path, default=None)
    parser.add_argument("--mirror", type=Path, default=None)
    parser.add_argument("--capture", action="store_true", help="append the current GP mirror")
    parser.add_argument(
        "--space-weather",
        type=Path,
        default=None,
        help="published space-weather artifact whose Kp window should be archived",
    )
    parser.add_argument(
        "--from-manifest",
        type=Path,
        default=None,
        metavar="DATA_ROOT",
        help="resolve the space-weather artifact through DATA_ROOT/manifest.json",
    )
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--series", type=int, metavar="NORAD")
    parser.add_argument("--detect", type=int, metavar="NORAD")
    parser.add_argument("--false-positive-rate", action="store_true")
    parser.add_argument("--fpr-limit", type=int, default=500)
    parser.add_argument("--export-month", metavar="YYYY-MM")
    parser.add_argument(
        "--roll",
        action="store_true",
        help="decimate complete days, export and verify complete months, then prune",
    )
    parser.add_argument(
        "--retain-days",
        type=int,
        default=DEFAULT_RETAIN_DAYS,
        help="how long tier 1 keeps full-fidelity element sets (default %(default)s)",
    )
    parser.add_argument("--cold-root", type=Path, default=None)
    parser.add_argument("--prune-before", metavar="YYYY-MM-DD")
    parser.add_argument(
        "--refresh-summary",
        action="store_true",
        help="rebuild month_rollup and object_rollup in one paged pass, so the "
        "archive-wide questions stop reading the archive",
    )
    args = parser.parse_args(argv)

    archive_path = args.archive or archive_db_path()
    mirror = args.mirror or _default_mirror()
    # Opening and capturing are both under the same guard: the lock can be lost
    # at the first statement of open_archive() - which is where the 10:19
    # failure landed - or at the commit inside ingest_records() an entire file
    # later. Both mean the same hour is gone, so both get the same report.
    started = time.monotonic()
    try:
        connection = open_archive(archive_path)
    except sqlite3.OperationalError as error:
        if args.capture:
            raise ArchiveBusy(
                starved_capture_report(
                    mirror,
                    waited_seconds=time.monotonic() - started,
                    archive_path=archive_path,
                )
            ) from error
        raise
    try:
        if args.capture:
            try:
                result = capture_from_mirror(connection, mirror)
            except sqlite3.OperationalError as error:
                raise ArchiveBusy(
                    starved_capture_report(
                        mirror,
                        waited_seconds=time.monotonic() - started,
                        archive_path=archive_path,
                    )
                ) from error
            payload = result.as_dict()
            weather = args.space_weather
            if weather is None and args.from_manifest:
                weather = space_weather_artifact_from_manifest(args.from_manifest)
                payload["spaceWeatherArtifact"] = str(weather) if weather else None
            if weather:
                payload["kpSamplesAdded"] = capture_geomagnetic(connection, weather)
            print(json.dumps(payload, indent=2))
        if args.status:
            print(json.dumps(archive_stats(connection), indent=2))
        if args.series is not None:
            for element in series(connection, args.series):
                print(
                    f"{element.epoch.isoformat()}  a={element.semi_major_axis_km:10.3f} km"
                    f"  e={element.eccentricity:.8f}  i={element.inclination:8.4f}"
                    f"  hp={element.perigee_altitude_km:9.3f} km"
                )
        if args.detect is not None:
            elements = series(connection, args.detect)
            events = (
                detect_manoeuvres(elements)
                + detect_drag(elements)
                + detect_station_keeping(elements)
            )
            print(
                json.dumps(
                    {
                        "norad": args.detect,
                        "elementSets": len(elements),
                        "noiseFloor": noise_floor(rates(elements)),
                        "events": [
                            {
                                "kind": event.kind,
                                "from": epoch_ms_to_datetime(event.start_ms).isoformat(),
                                "to": epoch_ms_to_datetime(event.end_ms).isoformat(),
                                "confidence": event.confidence,
                                "evidence": event.evidence,
                            }
                            for event in events
                        ],
                    },
                    indent=2,
                    default=str,
                )
            )
        if args.false_positive_rate:
            print(
                json.dumps(
                    false_positive_rate(connection, limit=args.fpr_limit), indent=2
                )
            )
        if args.refresh_summary:
            print(json.dumps(refresh_summary(connection), indent=2))
        cold = args.cold_root or cold_root(
            args.archive.parent if args.archive else None
        )
        if args.export_month:
            parts = args.export_month.split("-")
            if len(parts) != 2:
                raise SystemExit("--export-month takes YYYY-MM, not a date")
            year, month = (int(part) for part in parts)
            destination = shard_path(cold, year, month)
            print(json.dumps(export_month(connection, year, month, destination), indent=2))
        if args.roll:
            print(
                json.dumps(
                    roll(
                        connection,
                        retain_days=args.retain_days,
                        cold_directory=cold,
                    ),
                    indent=2,
                )
            )
        if args.prune_before:
            cutoff = dt.datetime.fromisoformat(args.prune_before).replace(
                tzinfo=dt.timezone.utc
            )
            removed = prune_hot(connection, int(cutoff.timestamp() * 1000))
            print(json.dumps({"removed": removed}, indent=2))
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    # ArchiveBusy carries a written report, not a diagnosis to be reconstructed
    # from a stack. Print the report and exit non-zero; systemd fails the unit
    # either way, and this is the difference between the journal saying which
    # hour was lost and the journal saying `sqlite3.OperationalError`. 75 is
    # EX_TEMPFAIL: the run failed for a reason that will not be there next hour.
    try:
        raise SystemExit(main())
    except ArchiveBusy as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(75)
