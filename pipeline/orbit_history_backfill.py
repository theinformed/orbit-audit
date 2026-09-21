#!/usr/bin/env python3
"""Back-fill the orbit archive from space-track's sanctioned bulk-TLE share.

WHY THIS EXISTS, AND WHY IT IS NOT AN API CLIENT
------------------------------------------------
`pipeline/orbit_history.py` archives every element set this installation sees,
but it only sees them from the moment it started running (2026-08-07). Everything
before that is missing, including the May 2024 Gannon storm that several other
parts of this project are built around.

space-track publishes that history. Their documentation for the `gp_history`
API class rate-limits it to **1 / lifetime** and says, verbatim:

    "Do NOT use this class to retrieve current ephemerides; use the GP class.
     For queries of many objects or large date ranges, download TLEs bundled as
     zip files by year from our cloud storage site instead. Once you download an
     object's history, you need to store it on your own servers; do not download
     it again."

So this module does exactly what they ask. It **never touches the space-track
API**. It fetches from the Sync.com share they publish for this purpose, which
consumes no API rate limit at all, and it keeps what it downloads so a re-import
never needs a re-fetch. Sean holds the space-track account personally, as a
serving officer; a suspension is a trip through his chain of command, and that
constraint is what shapes every fetch decision below.

    NEVER add a request to space-track.org's API to this file.
    NEVER add a request to celestrak.org to this file.

ENTITY BOUNDARY
---------------
Identical to `ingest/spacetrack_ingest.py`, and for the same legal reason:
space-track material is fetched and held only on bigmem-PC, under Sean's
personal account. The VPS operates under a separate entity and must never hold
it. `enforce_entity_boundary()` runs before anything opens a socket or writes a
byte, and it refuses on any other host.

Redistribution of *derived* products (mean elements, with citation) is settled
and permitted. Acting as a clearinghouse for the raw bundles is not. The zips
stay on `/mnt/d` and are never published; only the reduced element sets that
`orbit_history` already stores ever reach the browser.

HOW THE FETCH WORKS
-------------------
The share is a Sync.com public link. Its file list and per-file download URL are
produced by client-side JavaScript holding the link key, so there is no REST
endpoint to call. `pipeline/orbit_history_bulk_signer.mjs` runs the real client
once per file and prints a signed URL; this module then transfers the bytes
itself. That split is deliberate: the signed URL is an ordinary HTTPS GET that
honours `Range`, so Python can resume a broken transfer at the byte, verify the
length and digest, and pace itself, none of which a browser download does well.

Downloads are sequential, with a pause between files, and a file already held
and verified is never fetched again.

...AND WHY THE IMPORT IS A SEPARATE COMMAND
-------------------------------------------
The fetch happens once. The import takes a double-digit number of hours on this
machine and *will* be interrupted - the first run died on a lock after fifteen
million rows. So `--import-held` imports bundles already on disk and makes no
network request of any kind: no share listing, no browser, nothing that could
be pointed at an upstream. Re-run it until every bundle reports
`already imported`; a bundle re-read inserts nothing, because (norad, epoch_ms)
is the primary key.

    python3 -m pipeline.orbit_history_backfill --import-held

The archive is shared with the hourly GP capture and lives on a v9fs mount,
where the journal mode `orbit_history` chose makes readers block writers. Both
directions of that are handled: the import waits half an hour for the lock
rather than dying (`tune_for_bulk`), and its batches are small enough that it
never holds the lock longer than the capture is willing to wait
(`IMPORT_BATCH_ROWS`).

STORAGE
-------
Everything on `/mnt/d` (3.3 TB free), never the SSD:

    /mnt/d/space-orbit-history/bulk/manifest.json   what we hold, and its state
    /mnt/d/space-orbit-history/bulk/tleYYYY.txt.zip the bundles, kept forever
    /mnt/d/space-orbit-history/orbit-history.sqlite3 the archive itself

Keeping the zips is the point: space-track's instruction is to store the history
yourself and not download it again, and a re-import must never become a re-fetch.

WHAT A BULK TLE IS, AND WHY IT IS NOT A GP RECORD
-------------------------------------------------
The archive stores GP-style mean elements. The bundles are classic two-line
elements, which are a *lossy rendering* of the same underlying fit:

    eccentricity  TLE carries 7 decimals, GP carries 8
    B*            TLE carries 5 significant figures, GP carries more
    epoch         TLE resolves 0.86 ms, GP publishes microseconds
    everything else round-trips exactly

`cross_check_live_capture()` measures those residuals against tonight's live GP
mirror rather than asserting them, because the same object at the same epoch
arriving from two sources is the only real proof the conversion is right.

THIS MODULE DOES NOT MODIFY `pipeline/orbit_history.py`. It uses that module's
schema, quantisation and cold-shard machinery unchanged.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import socket
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Iterator, Sequence

from pipeline import orbit_history as oh

ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# The boundary. Do not relax without Sean's explicit instruction.
# ---------------------------------------------------------------------------
SPACETRACK_HOST = "bigmem-PC"


def enforce_entity_boundary(host: str | None = None) -> None:
    """Refuse to run anywhere but bigmem-PC.

    Same guard, same wording and the same reason as
    `ingest/spacetrack_ingest.py`. space-track material is held only under
    Sean's personal identity, on his own machine. The VPS operates under the
    LLC and must never hold it, and a guard is the only form of that rule that
    cannot be forgotten.
    """
    current = host if host is not None else socket.gethostname()
    if current != SPACETRACK_HOST:
        raise SystemExit(
            f"REFUSING TO RUN on host {current!r}. space-track bulk history is "
            f"downloaded and held only on {SPACETRACK_HOST}, under Sean's personal "
            "account. The VPS operates under the LLC and must never hold it."
        )


# ---------------------------------------------------------------------------
# The share
# ---------------------------------------------------------------------------
# space-track's own published bulk-download location, linked from their API
# documentation as the thing to use *instead of* the gp_history class.
BULK_SHARE_URL = (
    "https://ln5.sync.com/dl/afd354190/c5cd2q72-a5qjzp4q-nbjdiqkr-cenajuqu"
)

SIGNER = Path(__file__).with_name("orbit_history_bulk_signer.mjs")

BULK_DIRNAME = "bulk"
MANIFEST_NAME = "manifest.json"

# Sequential, with a gap. Their instruction is to store the history rather than
# re-fetch it, so this runs once; there is no reason to be in a hurry.
POLITE_GAP_SECONDS = 5.0
DOWNLOAD_CHUNK = 1 << 20
DOWNLOAD_TIMEOUT = 300.0
MAX_ATTEMPTS_PER_FILE = 4

# How long an import batch waits for the write lock before giving up. See
# `tune_for_bulk` - this number is the difference between pausing and losing a
# run that is already hours old.
BUSY_TIMEOUT_MS = 30 * 60 * 1000

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "HeadlessChrome/151.0.7922.34 Safari/537.36"
)
"""The signed URL is bound to the requesting user agent as well as the IP.

Sending a different one gets a signature rejection, not a redirect, so this has
to match whatever the signer's browser announced. `mint_urls()` returns the live
value and `download_file()` prefers it; this constant is only the fallback.
"""

# 2024 first: it holds the May 2024 Gannon storm, which the drag, thermosphere
# and storm-teaching work in this project is built around. Then recent years
# backwards, because recency is what the browser will be asked for; then the
# deep history, which is the least urgent and by far the largest.
PRIORITY_YEARS: tuple[int, ...] = (2024, 2025, 2023, 2022, 2021, 2020, 2019) + tuple(
    range(2018, 2003, -1)
)


class BackfillError(RuntimeError):
    """Raised when a bundle cannot be fetched, verified, or read."""


def bulk_root(root: Path | None = None) -> Path:
    return (root if root is not None else oh.archive_root()) / BULK_DIRNAME


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------
def load_manifest(directory: Path) -> dict:
    path = directory / MANIFEST_NAME
    if not path.exists():
        return {"share": BULK_SHARE_URL, "files": {}}
    try:
        document = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError, ValueError):
        # A corrupt manifest must not authorise a re-download of 12 GB. Refuse
        # loudly and let a human look, rather than starting again from zero.
        raise BackfillError(
            f"{path} is unreadable. It records what has already been fetched and "
            "imported; fix or move it deliberately rather than letting this tool "
            "re-download everything."
        )
    if not isinstance(document, dict) or not isinstance(document.get("files"), dict):
        raise BackfillError(f"{path} is not a backfill manifest")
    document.setdefault("share", BULK_SHARE_URL)
    return document


def save_manifest(directory: Path, manifest: dict) -> None:
    """Write the manifest atomically. A torn manifest is a re-download."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / MANIFEST_NAME
    temporary = path.with_suffix(".json.next")
    temporary.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    os.replace(temporary, path)


def sha256_of(path: Path, *, chunk: int = 1 << 22) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def file_is_held(directory: Path, manifest: dict, name: str) -> bool:
    """True when this bundle is already on disk, complete and digest-checked.

    The digest is not re-computed here - that would mean re-hashing 12 GB on
    every run. The size is checked against the disk, because a truncated file is
    the failure that actually happens; the digest was verified once, when the
    file was written, and is recorded so a later re-verification is possible.
    """
    record = manifest["files"].get(name)
    if not isinstance(record, dict) or not record.get("sha256"):
        return False
    path = directory / name
    if not path.exists():
        return False
    return path.stat().st_size == record.get("bytes")


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------
def mint_urls(names: Sequence[str], *, share: str = BULK_SHARE_URL) -> dict:
    """Ask the share's own web client for signed download URLs.

    Returns {"listing": [...], "urls": {name: {"url": ...}}, "userAgent": ...}.
    Raises rather than returning a partial result, because a silent miss here
    would look exactly like "the share no longer has that year".
    """
    if not SIGNER.exists():
        raise BackfillError(f"signer script missing: {SIGNER}")
    command = ["node", str(SIGNER), share, *names]
    try:
        finished = subprocess.run(
            command, capture_output=True, text=True, timeout=900, cwd=str(ROOT)
        )
    except FileNotFoundError as error:
        raise BackfillError(
            "node is required to mint a download URL from the share "
            "(the share is a Sync.com public link whose URLs are minted by its "
            "own client-side JavaScript)"
        ) from error
    except subprocess.TimeoutExpired as error:
        raise BackfillError("the share's web client did not respond in 900 s") from error
    if finished.returncode != 0:
        raise BackfillError(
            f"signer failed ({finished.returncode}): {finished.stderr.strip()[:500]}"
        )
    try:
        return json.loads(finished.stdout)
    except json.JSONDecodeError as error:
        raise BackfillError(
            f"signer produced no usable JSON: {finished.stdout[:300]!r}"
        ) from error


def _open_range(url: str, offset: int, user_agent: str):
    request = urllib.request.Request(url)
    request.add_header("User-Agent", user_agent)
    if offset:
        request.add_header("Range", f"bytes={offset}-")
    return urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT)


def download_file(
    name: str,
    *,
    directory: Path,
    expected_bytes: int | None = None,
    share: str = BULK_SHARE_URL,
    signed: dict | None = None,
    progress: Callable[[int, int | None], None] | None = None,
) -> dict:
    """Fetch one bundle, resuming a partial transfer rather than restarting.

    Idempotent by construction: a bundle already recorded in the manifest with a
    matching size on disk is never fetched again. space-track's instruction is
    explicit that the history is stored once and not re-downloaded, and this is
    where that promise is kept.
    """
    directory.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(directory)
    if file_is_held(directory, manifest, name):
        record = dict(manifest["files"][name])
        record["skipped"] = "already held"
        return record

    final = directory / name
    partial = directory / (name + ".part")
    user_agent = USER_AGENT
    last_error: str | None = None

    for attempt in range(1, MAX_ATTEMPTS_PER_FILE + 1):
        payload = signed if (signed and attempt == 1) else mint_urls([name], share=share)
        user_agent = payload.get("userAgent") or USER_AGENT
        entry = (payload.get("urls") or {}).get(name) or {}
        url = entry.get("url")
        if not url:
            raise BackfillError(
                f"the share did not offer {name}: {entry.get('error', 'no URL returned')}"
            )
        if expected_bytes is None:
            for row in payload.get("listing") or []:
                if row.get("name") == name and row.get("bytes"):
                    expected_bytes = int(row["bytes"])

        offset = partial.stat().st_size if partial.exists() else 0
        try:
            with _open_range(url, offset, user_agent) as response:
                # `getattr(x, "status", x.getcode())` would evaluate the default
                # eagerly and raise on any response object without getcode().
                status = getattr(response, "status", None)
                if status is None:
                    status = response.getcode()
                if offset and status != 206:
                    # The server ignored the Range header. Appending now would
                    # splice the whole file onto the tail of the part we already
                    # have, and the size check would not necessarily catch it.
                    partial.unlink(missing_ok=True)
                    offset = 0
                    raise BackfillError(
                        f"resume refused (HTTP {status} for a ranged request)"
                    )
                total = response.headers.get("Content-Range")
                if total and "/" in total:
                    declared = total.rsplit("/", 1)[-1]
                    if declared.isdigit():
                        expected_bytes = int(declared)
                elif response.headers.get("Content-Length") and not offset:
                    expected_bytes = int(response.headers["Content-Length"])
                with partial.open("ab" if offset else "wb") as handle:
                    received = offset
                    while True:
                        block = response.read(DOWNLOAD_CHUNK)
                        if not block:
                            break
                        handle.write(block)
                        received += len(block)
                        if progress is not None:
                            progress(received, expected_bytes)
        except (urllib.error.URLError, OSError, BackfillError) as error:
            last_error = f"{type(error).__name__}: {error}"
            # Keep the partial file. The next attempt resumes from it; that is
            # the whole reason it is written under a separate name.
            time.sleep(min(30.0, 3.0 * attempt))
            continue

        size = partial.stat().st_size
        if expected_bytes is not None and size != expected_bytes:
            last_error = f"short transfer: {size} of {expected_bytes} bytes"
            time.sleep(min(30.0, 3.0 * attempt))
            continue

        digest = sha256_of(partial)
        os.replace(partial, final)
        manifest = load_manifest(directory)
        manifest["files"][name] = {
            "url": share,
            "bytes": size,
            "sha256": digest,
            "downloadedAt": _now_iso(),
            "attempts": attempt,
        }
        save_manifest(directory, manifest)
        return manifest["files"][name]

    raise BackfillError(
        f"gave up on {name} after {MAX_ATTEMPTS_PER_FILE} attempts: {last_error}"
    )


def bundle_name_for_year(year: int, listing: Sequence[dict]) -> list[str]:
    """Every bundle covering `year`. 2004 is split into eight parts."""
    prefix = f"tle{year}"
    return sorted(
        row["name"]
        for row in listing
        if isinstance(row.get("name"), str) and row["name"].startswith(prefix)
    )


# ---------------------------------------------------------------------------
# TLE parsing
# ---------------------------------------------------------------------------
# Alpha-5: NORAD numbers past 99999 replace the leading digit with a letter,
# skipping I and O because they read as 1 and 0. The catalogue crossed 100000
# during the window these bundles cover, so a parser that assumes five digits
# silently drops the newest objects - which are exactly the ones a visitor is
# most likely to look up.
_ALPHA5 = "0123456789ABCDEFGHJKLMNPQRSTUVWXYZ"

# TLE epochs carry two-digit years. space-track's convention, and the one the
# SGP4 reference implementation uses: 57-99 is 19xx, 00-56 is 20xx. Sputnik
# launched in 1957, so nothing earlier can exist.
_YEAR_PIVOT = 57


class Rejection:
    """Why a record was not archived. Counted, never silently dropped."""

    SHORT_LINE = "short-line"
    BAD_PREFIX = "bad-prefix"
    CHECKSUM_1 = "checksum-line1"
    CHECKSUM_2 = "checksum-line2"
    SATNUM_MISMATCH = "satnum-mismatch"
    BAD_SATNUM = "bad-satnum"
    BAD_EPOCH = "bad-epoch"
    BAD_FIELD = "unparseable-field"
    OUT_OF_RANGE = "element-out-of-range"
    UNPAIRED = "unpaired-line"
    ANALYST = "analyst-object"
    # Not a rejection. Counted under `acceptedWithNote`: the early bundles
    # publish whole records with no checksum column, and accepting those
    # silently would be the wrong kind of quiet.
    NO_CHECKSUM_COLUMN = "accepted-without-checksum-column"


def tle_checksum(line: str) -> int:
    """Modulo-10 sum of the first 68 columns; every minus sign counts as 1."""
    total = 0
    for character in line[:68]:
        if character.isdigit():
            total += ord(character) - 48
        elif character == "-":
            total += 1
    return total % 10


def fix_checksum(line: str) -> str:
    """Return `line` with column 69 set to the checksum its body implies.

    Used to rebuild a line after editing it - in tests, and when reconstructing
    the checksum column an analyst record was published without.
    """
    body = line[:68].ljust(68)
    return body + str(tle_checksum(body))


def normalise_line(raw: str) -> str:
    """Strip the line ending, and the trailing backslash the bundles carry.

    Every line 1 in these bundles ends with a literal backslash, making it 70
    columns instead of 69. A parser that validates the length, or that reads the
    checksum from the last character, rejects one hundred percent of the file -
    and a backfill that rejects everything looks, from the outside, exactly like
    a backfill that found nothing.
    """
    line = raw.rstrip("\r\n")
    while line.endswith("\\"):
        line = line[:-1]
    return line.rstrip()


def decode_satnum(field_text: str) -> int | None:
    """Five-column catalogue number, Alpha-5 aware.

    The bundles are not consistent about padding. Most records zero-pad
    (`00005`), but a substantial minority space-pad (`    5`) - including
    VANGUARD 1, the object this project pins its semi-major-axis test against.
    A parser that assumes five digits drops them, and drops them so quietly that
    the only symptom is a famous satellite with a hole in its history.
    """
    text = field_text.strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    index = _ALPHA5.find(text[0].upper())
    if index < 10:
        # Below 10 means the leading character was a digit, which `isdigit()`
        # already handled, or was not found at all - I and O among them.
        return None
    rest = text[1:]
    if len(rest) != 4 or not rest.isdigit():
        return None
    return index * 10000 + int(rest)


# Analyst objects. space-track publishes uncorrelated tracks in this band, and
# **the numbers are recycled**: 81134 is not one object across the years, it is
# whatever track happened to hold that slot. Archiving them under
# (norad, epoch_ms) would splice unrelated debris into a single "history", and
# the manoeuvre detector would then report the splice as a very large burn.
#
# They are also absent from the live GP feed, so nothing would ever give them a
# name, a type or a decay date. They are excluded deliberately, counted, and
# reported - not silently dropped.
ANALYST_RANGE = (80000, 89999)


def is_analyst(norad: int) -> bool:
    return ANALYST_RANGE[0] <= norad <= ANALYST_RANGE[1]


def decode_implied_decimal(field_text: str) -> float | None:
    """Decode TLE's exponent-with-assumed-leading-decimal fields.

    ` 17439-2` is 0.17439e-2, `-21183-6` is -0.21183e-6, ` 00000-0` is zero.
    """
    text = field_text.strip()
    if not text:
        return None
    sign = 1.0
    if text[0] in "+-":
        sign = -1.0 if text[0] == "-" else 1.0
        text = text[1:]
    if not text:
        return None
    if len(text) > 2 and text[-2] in "+-":
        mantissa, exponent_text = text[:-2], text[-2:]
    else:
        mantissa, exponent_text = text, "0"
    if not mantissa.isdigit():
        return None
    try:
        exponent = int(exponent_text)
    except ValueError:
        return None
    return sign * float("0." + mantissa) * (10.0 ** exponent)


def decode_epoch_ms(year_text: str, day_text: str) -> int | None:
    """`YYDDD.DDDDDDDD` to milliseconds since the epoch, UTC."""
    try:
        two_digit = int(year_text)
        day_of_year = float(day_text)
    except ValueError:
        return None
    if not (0 <= two_digit <= 99):
        return None
    year = 1900 + two_digit if two_digit >= _YEAR_PIVOT else 2000 + two_digit
    # Day-of-year is 1-based and fractional. 366.x is legal in a leap year and
    # 367.x is not; rather than re-deriving the calendar, let timedelta place it
    # and check the year afterwards.
    if not (1.0 <= day_of_year < 367.0):
        return None
    stamp = dt.datetime(year, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(
        days=day_of_year - 1.0
    )
    if stamp.year != year:
        return None
    return int(round(stamp.timestamp() * 1000))


@dataclass
class RejectionLog:
    """Counts by reason, plus one worked example of each, for the report."""

    counts: dict[str, int] = field(default_factory=dict)
    examples: dict[str, str] = field(default_factory=dict)
    notes: dict[str, int] = field(default_factory=dict)

    def add(self, reason: str, evidence: str = "") -> None:
        self.counts[reason] = self.counts.get(reason, 0) + 1
        if reason not in self.examples and evidence:
            self.examples[reason] = evidence[:80]

    def note(self, reason: str, evidence: str = "") -> None:
        """Count a record that was ACCEPTED but is worth knowing about.

        Kept apart from `counts` so it can never be read as a rejection. It
        exists for one case so far: records the bundles publish with no
        checksum column at all, which are accepted on other evidence and must
        not be accepted silently.
        """
        self.notes[reason] = self.notes.get(reason, 0) + 1
        if reason not in self.examples and evidence:
            self.examples[reason] = evidence[:80]

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    def merge(self, other: "RejectionLog") -> None:
        for reason, count in other.counts.items():
            self.counts[reason] = self.counts.get(reason, 0) + count
        for reason, count in other.notes.items():
            self.notes[reason] = self.notes.get(reason, 0) + count
        for reason, evidence in other.examples.items():
            self.examples.setdefault(reason, evidence)

    def as_dict(self) -> dict:
        return {
            "total": self.total,
            "byReason": dict(sorted(self.counts.items())),
            "acceptedWithNote": dict(sorted(self.notes.items())),
            "examples": self.examples,
        }


def parse_tle_pair(
    line1: str,
    line2: str,
    *,
    log: RejectionLog | None = None,
    validate_checksum: bool = True,
    exclude_analyst: bool = True,
) -> oh.ElementSet | None:
    """One TLE pair to one `orbit_history.ElementSet`, or None with a reason.

    The range guards are deliberately the same ones `orbit_history.
    element_from_gp()` applies, so a record the live path would refuse is
    refused here too and the two sources cannot disagree about what is archivable.

    The order of the checks matters. The catalogue number is read *before* the
    checksum is required, because analyst records in these bundles are 68
    columns wide with no checksum at all; testing the length first would file
    every one of them under "short line" and hide what they actually are.
    """
    reject = log.add if log is not None else (lambda *_: None)
    first = normalise_line(line1)
    second = normalise_line(line2)

    # 68 columns is a complete element set with the checksum column absent,
    # which is how the analyst records are published. Anything shorter is junk.
    if len(first) < 68 or len(second) < 68:
        reject(Rejection.SHORT_LINE, first or second)
        return None
    if first[0] != "1" or second[0] != "2":
        reject(Rejection.BAD_PREFIX, first)
        return None

    norad = decode_satnum(first[2:7])
    if norad is None:
        reject(Rejection.BAD_SATNUM, first)
        return None
    if decode_satnum(second[2:7]) != norad:
        # Two lines from different objects mean the file is misaligned, and
        # blending them would invent an orbit that never existed.
        reject(Rejection.SATNUM_MISMATCH, first)
        return None
    analyst = is_analyst(norad)
    if analyst and exclude_analyst:
        reject(Rejection.ANALYST, first)
        return None

    # THE EARLY BUNDLES PUBLISH WHOLE RECORDS WITH NO CHECKSUM COLUMN.
    #
    # §3.4 of docs/orbit-history-backfill.md concluded, from tle2024, that a
    # 68-column line is an analyst record. That is true of tle2024 and false of
    # the deep history. From roughly 7% of the way into `tle2004_1of8.txt.zip`
    # onward, *ordinary catalogued objects* - the ISS, Hubble, Vanguard 1 -
    # are published 68 columns wide on BOTH lines, with `+` signs written out
    # and the fields zero-padded, and no checksum anywhere. Measured: 1,723,295
    # of that bundle's 1,816,163 records, 95% of the file.
    #
    # Refusing them is not caution, it is silent destruction of a quarter of
    # the archive - 2004 and 2005 together are ~56 million records - and it
    # fails in exactly the shape §3.1 warns about: a backfill that rejects
    # almost everything is indistinguishable from a backfill that found almost
    # nothing.
    #
    # The columns are otherwise standard, verified against known orbits at
    # 2001 epochs: ISS 51.6384 deg / 15.578 rev per day, Vanguard 1 34.2555 deg
    # / e=0.1854, Hubble 28.4676 deg. So the rule is UNIFORMITY, not length: a
    # record whose two lines are both 68 columns is a checksum-free record and
    # is accepted on its other evidence - the catalogue numbers on the two
    # lines must agree, the epoch must be a real date, and every element must
    # pass the same range guards the live path applies. A 68-column line paired
    # with a 69-column one is a *truncation*, and stays rejected.
    #
    # Accepted is not the same as unremarkable, so each one is counted under
    # `acceptedWithNote`. Nothing about this archive should be silent.
    uniformly_unchecksummed = len(first) == 68 and len(second) == 68

    def checksum_ok(line: str) -> bool:
        """Present and correct, or legitimately absent for this record."""
        if len(line) < 69:
            return analyst or uniformly_unchecksummed
        if not validate_checksum:
            return True
        return line[68].isdigit() and tle_checksum(line) == int(line[68])

    if not checksum_ok(first):
        reject(
            Rejection.SHORT_LINE if len(first) < 69 else Rejection.CHECKSUM_1, first
        )
        return None
    if not checksum_ok(second):
        reject(
            Rejection.SHORT_LINE if len(second) < 69 else Rejection.CHECKSUM_2, second
        )
        return None
    if uniformly_unchecksummed and not analyst and log is not None:
        log.note(Rejection.NO_CHECKSUM_COLUMN, first)

    epoch_ms = decode_epoch_ms(first[18:20], first[20:32])
    if epoch_ms is None:
        reject(Rejection.BAD_EPOCH, first)
        return None

    try:
        ndot = float(first[33:43].replace(" ", "") or "0")
    except ValueError:
        reject(Rejection.BAD_FIELD, first)
        return None
    nddot = decode_implied_decimal(first[44:52])
    bstar = decode_implied_decimal(first[53:61])

    try:
        inclination = float(second[8:16])
        raan = float(second[17:25])
        eccentricity = float("0." + second[26:33].strip())
        arg_perigee = float(second[34:42])
        mean_anomaly = float(second[43:51])
        mean_motion = float(second[52:63])
    except ValueError:
        reject(Rejection.BAD_FIELD, second)
        return None

    rev_text = second[63:68].strip()
    try:
        rev_at_epoch = int(rev_text) if rev_text else None
    except ValueError:
        rev_at_epoch = None

    # Exactly `element_from_gp`'s guards.
    if not (0.0 < mean_motion < 20.0):
        reject(Rejection.OUT_OF_RANGE, second)
        return None
    if not (0.0 <= eccentricity < 1.0):
        reject(Rejection.OUT_OF_RANGE, second)
        return None
    if not (0.0 <= inclination <= 180.0):
        reject(Rejection.OUT_OF_RANGE, second)
        return None
    # Same ceiling the live GP path applies. A garbled exponent in the drag
    # columns is the one bad value big enough to break the archive rather than
    # just pollute it - see MAX_DRAG_MAGNITUDE.
    if not oh.drag_terms_in_range(bstar, ndot, nddot):
        reject(Rejection.OUT_OF_RANGE, first)
        return None

    return oh.ElementSet(
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


def iter_tle_pairs(lines: Iterable[str]) -> Iterator[tuple[str, str]]:
    """Pair consecutive `1 `/`2 ` lines, skipping name lines and blanks.

    Yields the pair even when the second line is wrong, so the caller counts it
    as a rejection rather than never seeing it.
    """
    pending: str | None = None
    for raw in lines:
        line = normalise_line(raw)
        if not line:
            continue
        if line.startswith("1 "):
            pending = line
            continue
        if line.startswith("2 "):
            if pending is not None:
                yield pending, line
                pending = None
            else:
                yield "", line
            continue
        # A `0 NAME` header, or anything else: not an element line.
        pending = None


def iter_elements_from_zip(
    path: Path, *, log: RejectionLog
) -> Iterator[oh.ElementSet]:
    """Stream every element set out of one bundle. Never loads it all."""
    with zipfile.ZipFile(path) as archive:
        members = [m for m in archive.infolist() if not m.is_dir()]
        if not members:
            raise BackfillError(f"{path} contains no members")
        for member in members:
            with archive.open(member) as handle:
                text = (line.decode("ascii", "replace") for line in handle)
                for first, second in iter_tle_pairs(text):
                    if not first:
                        log.add(Rejection.UNPAIRED, second)
                        continue
                    element = parse_tle_pair(first, second, log=log)
                    if element is not None:
                        yield element


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------
# Rows are sorted inside each batch before insertion. `element_set` is
# WITHOUT ROWID and clustered on (norad, epoch_ms), so unsorted inserts scatter
# writes across the whole B-tree; the bundles are in fit order, not catalogue
# order. Sorting a bounded batch buys most of the locality without ever holding
# a whole year - 17 million rows - in memory at once.
#
# THE CEILING IS NOT MEMORY, IT IS HOW LONG THE WRITE LOCK IS HELD. The archive
# is a rollback-journal database shared with the hourly GP capture, so a batch
# holds the write lock for as long as it takes to insert - and `open_archive`
# gave the capture a 60-second busy timeout when this was sized. Measured here,
# an insert runs at roughly 8-15 k rows/s, which puts a 500,000-row batch at
# 35-60 s of lock: near enough to that timeout to cost a live hour of data.
# 100,000 rows is about 10 s, comfortably inside it, and still sorts to good
# locality. The capture now waits 900 s
# (`orbit_history.DEFAULT_BUSY_TIMEOUT_SECONDS`), so the margin is far wider
# than it was; the batch size is left where it is because the number that
# actually justifies it is the 10 s of lock, not the timeout it fits inside.
#
# In this journal mode readers block writers too, so a long scan by anything
# else on the machine stalls the import. That is what the bulk busy timeout is
# for; the import waits rather than dying, which is the right way round.
IMPORT_BATCH_ROWS = 100_000

# How long to stand back after each commit so another writer can have the file.
#
# THIS IS NOT POLITENESS. Measured on 2026-08-08: an 80-minute import of
# tle2024, with 100,000-row batches, caused `spacetrack-ingest.service` to fail
# TWICE with `sqlite3.OperationalError: database is locked` - once inside
# `ingest_records`, once inside `open_archive`'s `PRAGMA journal_mode=TRUNCATE`.
# Two hourly captures of live GP elements were lost and can never be recovered,
# because space-track publishes GP for the present moment and nothing back-fills
# it.
#
# Small batches were not enough on their own. Back-to-back batches never left a
# window the capture's busy timeout could sit out; the writer has to actually
# stop. The capture inserts 31,697 rows in 0.16 s, so a few seconds of genuine
# idle is ample, and at ~10 s of work per batch this costs about a third of the
# import's throughput - against an import that is already measured in days and a
# loss that is permanent.
#
# Two things in the paragraph above were true when it was written on 2026-08-08
# and are not now, and both made the problem look smaller than it was:
#
#   * the capture's busy timeout was 60 s. It is
#     `orbit_history.DEFAULT_BUSY_TIMEOUT_SECONDS`, 900 s, since the same day.
#   * the unit ran the capture as `ExecStartPost=-`, so a failure was swallowed
#     and the service still reported "Deactivated successfully". The `-` is
#     gone; a starved capture now fails the unit and prints
#     `orbit_history.starved_capture_report`.
#
# The yield is kept regardless. This import is the writer that can hold the file
# for hours, and standing back is cheaper here than anywhere else.
BATCH_YIELD_SECONDS = 4.0

# ...and a REAL pause, periodically, because four seconds turned out not to be
# a window at all.
#
# 2026-08-09T05:00Z, with the 4 s yield already in place, the hourly capture
# still died: "Waited 9 s for a write lock ... and never got one." Nine seconds,
# not the 900 it was configured to wait - so it was not simply losing a race, it
# was being refused without waiting. That is the signature of a LOCK UPGRADE:
# a connection that reads first and then writes asks SQLite to promote a shared
# lock to an exclusive one, and SQLite answers SQLITE_BUSY *immediately* on an
# upgrade instead of running the busy handler, because waiting could deadlock.
# A busy timeout cannot help a reader-turned-writer, however long it is set.
#
# Fixing that properly belongs on the capture's side (take the write lock up
# front with BEGIN IMMEDIATE, where the handler does apply) and lives in
# pipeline/orbit_history.py. What this module can do is stop presenting a
# moving target: at ~77 s per batch, a 4 s gap means the file is busy 95% of the
# time and the capture has to be lucky. So every few batches the import stops
# properly - long enough that an hourly job cannot miss it, and cheap because
# the import is unattended and already measured in days.
LONG_YIELD_EVERY_BATCHES = 6
LONG_YIELD_SECONDS = 90.0

_INSERT = "INSERT OR IGNORE INTO element_set VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"


def _row_for(element: oh.ElementSet, ingest_hour: int) -> tuple:
    """Quantise exactly as `orbit_history` does. Same scales, same schema."""
    return (
        element.norad,
        element.epoch_ms,
        oh.quantise(element.mean_motion, oh.SCALE_MEAN_MOTION),
        oh.quantise(element.eccentricity, oh.SCALE_ECCENTRICITY),
        oh.quantise(element.inclination, oh.SCALE_ANGLE),
        oh.quantise(element.raan, oh.SCALE_ANGLE),
        oh.quantise(element.arg_perigee, oh.SCALE_ANGLE),
        oh.quantise(element.mean_anomaly, oh.SCALE_ANGLE),
        oh.quantise(element.bstar, oh.SCALE_BSTAR),
        oh.quantise(element.ndot, oh.SCALE_NDOT),
        oh.quantise(element.nddot, oh.SCALE_NDDOT),
        element.rev_at_epoch,
        ingest_hour,
    )


@dataclass
class ImportResult:
    bundle: str
    records_read: int
    elements_new: int
    duplicates: int
    objects_seen: int
    rejections: RejectionLog
    earliest_ms: int | None
    latest_ms: int | None
    seconds: float

    def as_dict(self) -> dict:
        return {
            "bundle": self.bundle,
            "recordsRead": self.records_read,
            "elementsNew": self.elements_new,
            "duplicates": self.duplicates,
            "objectsSeen": self.objects_seen,
            "rejected": self.rejections.as_dict(),
            "earliestEpoch": oh._iso_or_none(self.earliest_ms),
            "latestEpoch": oh._iso_or_none(self.latest_ms),
            "seconds": round(self.seconds, 1),
        }


def import_bundle(
    connection: sqlite3.Connection,
    path: Path,
    *,
    captured_ms: int | None = None,
    batch_rows: int = IMPORT_BATCH_ROWS,
    on_batch: Callable[[int, int], None] | None = None,
    yield_seconds: float = BATCH_YIELD_SECONDS,
    long_yield_every: int = LONG_YIELD_EVERY_BATCHES,
    long_yield_seconds: float = LONG_YIELD_SECONDS,
) -> ImportResult:
    """Archive every element set in one bundle. Idempotent.

    Deduplication is the archive's own: `element_set`'s primary key is
    (norad, epoch_ms), so re-importing a bundle inserts nothing the second time.
    That is the same property the hourly capture relies on, exercised here at a
    scale it has never seen - which is worth verifying rather than assuming, and
    `--verify-dedupe` does exactly that.

    It sleeps `yield_seconds` after every commit, and that sleep is not
    politeness - see BATCH_YIELD_SECONDS. Without it this function silently
    destroys the hourly capture it shares the file with.
    """
    started = time.time()
    now_ms = captured_ms if captured_ms is not None else oh._now_ms()
    ingest_hour = now_ms // 3_600_000
    log = RejectionLog()

    rows: list[tuple] = []
    objects: dict[int, list[int]] = {}
    read = 0
    inserted = 0
    offered = 0
    earliest: int | None = None
    latest: int | None = None

    batches = 0

    def flush() -> None:
        nonlocal rows, inserted, offered, batches
        if not rows:
            return
        if yield_seconds > 0 and batches:
            # Stand back BEFORE taking the write lock again, so the hourly
            # capture has an interval in which the file is genuinely free. See
            # BATCH_YIELD_SECONDS. Waiting here rather than after the commit
            # means the pause is the window another writer needs, and means a
            # single-batch import - every test, and any small bundle - never
            # waits at all.
            long_pause = (
                long_yield_seconds > 0
                and long_yield_every > 0
                and batches % long_yield_every == 0
            )
            time.sleep(long_yield_seconds if long_pause else yield_seconds)
        batches += 1
        rows.sort(key=lambda row: (row[0], row[1]))
        # Same transaction as the insert, so the summary can never describe a
        # batch the table does not hold, or vice versa. See the summary section
        # of `pipeline/orbit_history.py` for why the delta is asked for rather
        # than counted from the offered rows.
        by_month, by_object, expected = oh.rollup_delta_for(connection, rows)
        before = connection.total_changes
        connection.executemany(_INSERT, rows)
        added = connection.total_changes - before
        oh.apply_rollup_delta(
            connection, by_month, by_object, inserted=added, expected=expected
        )
        inserted += added
        offered += len(rows)
        connection.commit()
        if on_batch is not None:
            on_batch(offered, inserted)
        rows = []

    for element in iter_elements_from_zip(path, log=log):
        read += 1
        rows.append(_row_for(element, ingest_hour))
        span = objects.get(element.norad)
        if span is None:
            objects[element.norad] = [element.epoch_ms, element.epoch_ms]
        else:
            if element.epoch_ms < span[0]:
                span[0] = element.epoch_ms
            if element.epoch_ms > span[1]:
                span[1] = element.epoch_ms
        if earliest is None or element.epoch_ms < earliest:
            earliest = element.epoch_ms
        if latest is None or element.epoch_ms > latest:
            latest = element.epoch_ms
        if len(rows) >= batch_rows:
            flush()
    flush()

    _record_objects(connection, objects, now_ms)

    connection.execute(
        "INSERT OR REPLACE INTO capture VALUES (?,?,?,?,?,?,?)",
        (
            now_ms,
            f"spacetrack:bulk:{path.name}",
            int(path.stat().st_mtime * 1000) if path.exists() else None,
            read,
            inserted,
            len(objects),
            log.total,
        ),
    )
    connection.commit()

    return ImportResult(
        bundle=path.name,
        records_read=read,
        elements_new=inserted,
        duplicates=offered - inserted,
        objects_seen=len(objects),
        rejections=log,
        earliest_ms=earliest,
        latest_ms=latest,
        seconds=time.time() - started,
    )


def _record_objects(
    connection: sqlite3.Connection, objects: dict[int, list[int]], now_ms: int
) -> None:
    """Add objects we had never seen, and widen `first_seen_ms` backwards.

    Deliberately additive. The bundles carry no names, types, countries or RCS
    sizes - only catalogue numbers - so overwriting the `object` row of anything
    the live capture already knows would erase the identity the browser needs.
    New rows get NULL metadata, which the next hourly capture fills in for
    anything still on orbit; objects that decayed before 2026 keep a NULL name,
    which is the truth rather than a guess.
    """
    if not objects:
        return
    connection.executemany(
        "INSERT OR IGNORE INTO object "
        "(norad, name, object_id, object_type, rcs_size, country, launch_date, "
        " first_seen_ms, last_seen_ms) "
        "VALUES (?,NULL,NULL,NULL,NULL,NULL,NULL,?,?)",
        [(norad, span[0], span[1]) for norad, span in objects.items()],
    )
    connection.executemany(
        "UPDATE object SET first_seen_ms = ? WHERE norad = ? AND first_seen_ms > ?",
        [(span[0], norad, span[0]) for norad, span in objects.items()],
    )
    connection.commit()


def tune_for_bulk(connection: sqlite3.Connection, *, cache_mib: int = 512) -> None:
    """Give the archive enough page cache to absorb a bulk insert.

    Nothing here changes durability semantics beyond what `open_archive`
    already chose (TRUNCATE journal, synchronous=NORMAL). It only stops a
    million-row insert from evicting its own index pages on every batch.

    THE BUSY TIMEOUT IS NOT OPTIONAL. The archive is a single file shared with
    the hourly GP capture, and on this machine it lives on a v9fs mount where a
    half-million-row commit can hold the write lock for minutes. `open_archive`
    asks for 60 s, which is the right number for a 31,000-row capture and far
    too small for a bulk import: the first run of this backfill died with
    `sqlite3.OperationalError: database is locked` part-way through 2024,
    having already committed fifteen million rows, because the capture happened
    to be writing when a batch wanted the lock. Waiting is always cheaper than
    losing the run, so this waits half an hour before giving up.
    """
    connection.execute(f"PRAGMA cache_size=-{int(cache_mib) * 1024}")
    connection.execute("PRAGMA temp_store=FILE")
    connection.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")


# ---------------------------------------------------------------------------
# The cross-check: same object, same epoch, two sources
# ---------------------------------------------------------------------------
_CROSS_CHECK_FIELDS = (
    ("meanMotion", "MEAN_MOTION", "mean_motion", "rev/day"),
    ("eccentricity", "ECCENTRICITY", "eccentricity", ""),
    ("inclination", "INCLINATION", "inclination", "deg"),
    ("raan", "RA_OF_ASC_NODE", "raan", "deg"),
    ("argPerigee", "ARG_OF_PERICENTER", "arg_perigee", "deg"),
    ("meanAnomaly", "MEAN_ANOMALY", "mean_anomaly", "deg"),
    ("bstar", "BSTAR", "bstar", "1/earth-radii"),
    ("ndot", "MEAN_MOTION_DOT", "ndot", "rev/day^2"),
)


def cross_check_live_capture(mirror_path: Path, *, limit: int | None = None) -> dict:
    """Prove the TLE conversion against space-track's own GP elements.

    Every record in the live GP mirror carries both the reduced elements
    (`MEAN_MOTION`, `ECCENTRICITY`, ...) **and** the two-line rendering of the
    same fit (`TLE_LINE1`, `TLE_LINE2`). Feeding the TLE lines through this
    module's parser and comparing the result against the GP fields of the *same
    record* is the same object at the same epoch from two independent
    representations - which is exactly the check that proves a bulk import is
    reading the bundles correctly, and it can be run tonight without waiting for
    an epoch that appears in both the bundles and the archive.

    Reads a file already on disk. Makes no network request.
    """
    if not mirror_path.exists():
        raise BackfillError(f"no GP mirror at {mirror_path}")
    payload = json.loads(mirror_path.read_bytes())
    if not isinstance(payload, list) or not payload:
        raise BackfillError(f"{mirror_path} is not a non-empty GP array")

    residuals: dict[str, list[float]] = {name: [] for name, _, _, _ in _CROSS_CHECK_FIELDS}
    epoch_residual_ms: list[float] = []
    quantised_disagreements: dict[str, int] = {}
    compared = 0
    unusable = 0
    missing_lines = 0

    for record in payload:
        if limit is not None and compared >= limit:
            break
        line1, line2 = record.get("TLE_LINE1"), record.get("TLE_LINE2")
        if not isinstance(line1, str) or not isinstance(line2, str):
            missing_lines += 1
            continue
        from_tle = parse_tle_pair(line1, line2)
        from_gp = oh.element_from_gp(record)
        if from_tle is None or from_gp is None:
            unusable += 1
            continue
        if from_tle.norad != from_gp.norad:
            unusable += 1
            continue
        compared += 1
        epoch_residual_ms.append(float(from_tle.epoch_ms - from_gp.epoch_ms))
        for name, _, attribute, _unit in _CROSS_CHECK_FIELDS:
            a = getattr(from_tle, attribute)
            b = getattr(from_gp, attribute)
            if a is None or b is None:
                continue
            residuals[name].append(abs(a - b))
        # The number that actually matters is not the float residual but
        # whether the two sources land on the same stored integer. Anything
        # that disagrees there is a row the archive would hold twice over.
        for index, name in enumerate(
            ("meanMotion", "eccentricity", "inclination", "raan", "argPerigee",
             "meanAnomaly", "bstar", "ndot")
        ):
            scale = (
                oh.SCALE_MEAN_MOTION, oh.SCALE_ECCENTRICITY, oh.SCALE_ANGLE,
                oh.SCALE_ANGLE, oh.SCALE_ANGLE, oh.SCALE_ANGLE, oh.SCALE_BSTAR,
                oh.SCALE_NDOT,
            )[index]
            attribute = _CROSS_CHECK_FIELDS[index][2]
            a, b = getattr(from_tle, attribute), getattr(from_gp, attribute)
            if a is None or b is None:
                continue
            if oh.quantise(a, scale) != oh.quantise(b, scale):
                quantised_disagreements[name] = quantised_disagreements.get(name, 0) + 1

    def summarise(values: Sequence[float]) -> dict:
        if not values:
            return {"n": 0}
        ordered = sorted(values)
        return {
            "n": len(ordered),
            "median": ordered[len(ordered) // 2],
            "p99": ordered[min(len(ordered) - 1, int(0.99 * len(ordered)))],
            "max": ordered[-1],
        }

    return {
        "source": str(mirror_path),
        "recordsCompared": compared,
        "recordsWithoutTleLines": missing_lines,
        "recordsUnusable": unusable,
        "epochResidualMs": summarise([abs(v) for v in epoch_residual_ms]),
        "elementResiduals": {
            name: summarise(values) for name, values in residuals.items()
        },
        "quantisedDisagreements": quantised_disagreements,
        "note": (
            "TLE is a lossy rendering of the same fit: eccentricity carries 7 "
            "decimals against GP's 8, and B* five significant figures against "
            "GP's fourteen. Residuals at those quanta are expected and are the "
            "proof the conversion is right; anything larger is not."
        ),
    }


def cross_check_archive_overlap(
    connection: sqlite3.Connection, path: Path, *, limit: int = 400
) -> dict:
    """Compare bundle records against archive rows at the identical epoch.

    Only finds anything where a bundle's coverage overlaps what the live capture
    already holds. When it does not - the bundles stop in 2025 and the archive
    starts in 2026 - it says so, rather than reporting a vacuous pass.
    """
    matches = 0
    scanned = 0
    disagreements: list[dict] = []
    log = RejectionLog()
    for element in iter_elements_from_zip(path, log=log):
        scanned += 1
        row = connection.execute(
            f"SELECT {', '.join(oh._ELEMENT_COLUMNS)} FROM element_set "
            "WHERE norad = ? AND epoch_ms = ?",
            (element.norad, element.epoch_ms),
        ).fetchone()
        if row is None:
            continue
        matches += 1
        archived = oh._element_from_row(element.norad, row)
        for _name, _gp, attribute, _unit in _CROSS_CHECK_FIELDS:
            a, b = getattr(element, attribute), getattr(archived, attribute)
            if a is None or b is None:
                continue
            if abs(a - b) > 1e-6 * max(1.0, abs(b)):
                disagreements.append(
                    {
                        "norad": element.norad,
                        "epoch": oh.epoch_ms_to_datetime(element.epoch_ms).isoformat(),
                        "field": attribute,
                        "bundle": a,
                        "archive": b,
                    }
                )
        if matches >= limit:
            break
    return {
        "bundle": path.name,
        "recordsScanned": scanned,
        "epochsAlsoInArchive": matches,
        "disagreements": disagreements[:20],
        "note": (
            "No overlap is the expected result while the bundles end in 2025 and "
            "the live archive begins in 2026. Zero matches is not a pass."
        )
        if matches == 0
        else "",
    }


def verify_dedupe_at_scale(connection: sqlite3.Connection) -> dict:
    """Check that (NORAD_CAT_ID, EPOCH) really is unique at this row count.

    The archive leans entirely on that key. It is cheap to assert on 32,000 rows
    and worth proving on a hundred million, because a duplicate epoch carrying
    two different element sets would silently become a manoeuvre.
    """
    total = connection.execute("SELECT COUNT(*) FROM element_set").fetchone()[0]
    distinct = connection.execute(
        "SELECT COUNT(*) FROM (SELECT 1 FROM element_set GROUP BY norad, epoch_ms)"
    ).fetchone()[0]
    return {
        "rows": total,
        "distinctNoradEpoch": distinct,
        "duplicateKeys": total - distinct,
        "holds": total == distinct,
    }


# ---------------------------------------------------------------------------
# Consolidation: tier 2 and the cold shards, using orbit_history unchanged
# ---------------------------------------------------------------------------
def consolidate(
    connection: sqlite3.Connection,
    *,
    cold_directory: Path,
    start_ms: int,
    end_ms: int,
) -> dict:
    """Decimate every backfilled day and export every backfilled month.

    Deliberately does NOT prune. `orbit_history.roll()` refuses to re-export a
    month whose start predates `meta.pruned_before_ms`, which means pruning
    part-way through a backfill would permanently strand every year imported
    afterwards: the shard for 2004 would never be written, and tier 1 would
    later drop those rows with nothing holding them. Export first, everything,
    then let the operator prune once - the ordering is the whole safety property.
    """
    days = [
        row[0]
        for row in connection.execute(
            "SELECT DISTINCT epoch_ms / 86400000 FROM element_set "
            "WHERE epoch_ms >= ? AND epoch_ms < ? ORDER BY 1",
            (start_ms, end_ms),
        )
    ]
    report: dict = {"days": len(days), "decimated": 0, "exported": [], "pruned": False}
    for day in days:
        oh.decimate_day(connection, day)
        report["decimated"] += 1

    months = sorted(
        {
            (
                oh.epoch_ms_to_datetime(day * 86_400_000).year,
                oh.epoch_ms_to_datetime(day * 86_400_000).month,
            )
            for day in days
        }
    )
    watermark = oh.pruned_before_ms(connection)
    for year, month in months:
        label = f"{year:04d}-{month:02d}"
        month_start, _ = oh.month_bounds(year, month)
        if month_start < watermark:
            report["exported"].append(
                {"month": label, "skipped": "predates the prune watermark"}
            )
            continue
        destination = cold_directory / f"orbit-history-{label}.ohz"
        report["exported"].append(
            oh.export_month(connection, year, month, destination)
        )
    return report


# ---------------------------------------------------------------------------
# Storage arithmetic, in real bytes
# ---------------------------------------------------------------------------
# Measured on this archive, recorded in docs/orbit-history-design.md 1.5.
BYTES_PER_HOT_ROW = 62.9
BYTES_PER_COLD_ROW = 22.36


def storage_projection(
    rows_by_year: dict[int, int], *, retain_days: int = oh.DEFAULT_RETAIN_DAYS
) -> dict:
    """What the backfill actually costs, at the archive's measured per-row size.

    `rows_by_year` is measured, not modelled: it is the row count each bundle
    contributed. The point of reporting it this way is that the design's
    retention plan was sized against 25,227 element sets a day from the hourly
    capture, and the bundles carry every fit space-track ever published, which
    is a different number entirely.
    """
    total_rows = sum(rows_by_year.values())
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=retain_days)
    # Years wholly older than the cutoff cannot contribute a single row to
    # tier 1 after a roll. The cutoff year itself is partial, so counting it in
    # full is an upper bound - which is the safe direction for a storage number.
    inside_upper_bound = sum(
        count for year, count in rows_by_year.items() if year >= cutoff.year
    )
    return {
        "rowsImported": total_rows,
        "rowsByYear": dict(sorted(rows_by_year.items())),
        "hotBytesIfNeverRolled": int(total_rows * BYTES_PER_HOT_ROW),
        "coldBytesAfterRolling": int(total_rows * BYTES_PER_COLD_ROW),
        "retainDays": retain_days,
        "retentionCutoff": cutoff.date().isoformat(),
        "hotRowsStillInsideWindowUpperBound": inside_upper_bound,
        "hotBytesAfterRollingUpperBound": int(
            inside_upper_bound * BYTES_PER_HOT_ROW
        ),
        "note": (
            "'hotBytesIfNeverRolled' is what the backfill costs if nobody runs "
            "orbit_history --roll, and is the number that says whether the "
            "rolling design still holds. After a roll, tier 1 keeps only the "
            f"{retain_days}-day window (cutoff {cutoff.date().isoformat()}) and "
            "everything older lives in the cold shards at the measured cold "
            "rate. The 'inside window' figure counts the cutoff year in full, "
            "so it is an upper bound."
        ),
    }


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
def run_backfill(
    *,
    years: Sequence[int],
    directory: Path,
    connection: sqlite3.Connection | None,
    share: str = BULK_SHARE_URL,
    download_only: bool = False,
    verbose: bool = True,
) -> dict:
    """Fetch, then import, one year at a time, in the order given."""
    listing_payload = mint_urls([], share=share)
    listing = listing_payload.get("listing") or []
    if not listing:
        raise BackfillError("the share returned an empty listing")
    report: dict = {"share": share, "bundles": [], "imports": [], "rowsByYear": {}}

    for year in years:
        names = bundle_name_for_year(year, listing)
        if not names:
            report["bundles"].append({"year": year, "error": "no bundle on the share"})
            continue
        year_rows = 0
        for name in names:
            expected = next(
                (row.get("bytes") for row in listing if row.get("name") == name), None
            )
            manifest = load_manifest(directory)
            if file_is_held(directory, manifest, name):
                if verbose:
                    print(f"  {name}: already held", flush=True)
            else:
                if verbose:
                    size = f"{expected:,} bytes" if expected else "unknown size"
                    print(f"  {name}: fetching {size}", flush=True)
                download_file(
                    name, directory=directory, expected_bytes=expected, share=share
                )
                time.sleep(POLITE_GAP_SECONDS)
            record = load_manifest(directory)["files"][name]
            report["bundles"].append({"year": year, "name": name, **record})

            if download_only or connection is None:
                continue
            manifest = load_manifest(directory)
            state = (manifest["files"].get(name) or {}).get("import")
            if isinstance(state, dict) and state.get("state") == "done":
                if verbose:
                    print(f"  {name}: already imported", flush=True)
                year_rows += int(state.get("elementsNew") or 0)
                continue
            result = import_bundle(connection, directory / name)
            report["imports"].append(result.as_dict())
            year_rows += result.elements_new
            manifest = load_manifest(directory)
            manifest["files"][name]["import"] = {
                "state": "done",
                "at": _now_iso(),
                **result.as_dict(),
            }
            save_manifest(directory, manifest)
            if verbose:
                print(json.dumps(result.as_dict(), indent=2), flush=True)
        report["rowsByYear"][year] = year_rows
    return report


def held_bundles_for_year(directory: Path, manifest: dict, year: int) -> list[str]:
    """Every bundle for `year` that is already on disk and digest-recorded.

    The offline twin of `bundle_name_for_year`. It reads the manifest instead
    of the share, which matters because the share's listing is only obtainable
    by driving a browser: once the bytes are held, asking the share what it has
    is a network round trip that can only tell us something we already know.
    """
    prefix = f"tle{year}"
    return sorted(
        name
        for name in manifest["files"]
        if name.startswith(prefix) and file_is_held(directory, manifest, name)
    )


# A lock error must pause this job, not end it.
#
# 2026-08-09T06:22Z: the import died on `database is locked` inside
# executemany, thirty-two minutes into a run, with a busy timeout of thirty
# MINUTES set and verified. It had not been waiting - it was refused
# immediately, which a busy handler cannot help with. The likely source is
# another connection calling `PRAGMA journal_mode=TRUNCATE`, which every
# `open_archive` does unconditionally and which needs exclusive access; an
# active writer gets bounced rather than queued.
#
# Whatever the cause, the response is the same. This job runs unattended for
# days beside an hourly capture, a publish cycle and whatever else is on the
# machine, and re-reading a bundle is free of effect because (norad, epoch_ms)
# is the primary key. So a lock is a reason to wait and start the bundle again,
# and only a persistent one is a reason to stop.
LOCK_RETRY_ATTEMPTS = 12
LOCK_RETRY_PAUSE_SECONDS = 120.0


def _is_lock_error(error: BaseException) -> bool:
    return "locked" in str(error).lower() or "busy" in str(error).lower()


def _import_with_lock_retry(
    connection: sqlite3.Connection,
    path: Path,
    *,
    on_batch: Callable[[int, int], None] | None = None,
    verbose: bool = True,
    attempts: int = LOCK_RETRY_ATTEMPTS,
    pause_seconds: float = LOCK_RETRY_PAUSE_SECONDS,
) -> ImportResult:
    for attempt in range(1, attempts + 1):
        try:
            return import_bundle(connection, path, on_batch=on_batch)
        except sqlite3.OperationalError as error:
            if not _is_lock_error(error) or attempt == attempts:
                raise
            if verbose:
                print(
                    f"  {path.name}: {error} - waiting {pause_seconds:.0f}s and "
                    f"starting the bundle again (attempt {attempt} of {attempts}); "
                    "rows already committed are kept",
                    flush=True,
                )
            time.sleep(pause_seconds)
    raise AssertionError("unreachable")


def import_held_years(
    *,
    years: Sequence[int],
    directory: Path,
    connection: sqlite3.Connection,
    verbose: bool = True,
    force: bool = False,
) -> dict:
    """Import bundles already on disk. Makes no network request of any kind.

    This is the half of the backfill that survives a session ending. The fetch
    is done once and the bytes are kept forever, exactly as space-track asks;
    everything after that is local work that may take days on this hardware and
    will be interrupted. So:

    * a bundle whose manifest records `import.state == "done"` is skipped, which
      makes a re-run cheap;
    * a bundle interrupted part-way is simply re-read, because `element_set`'s
      primary key is (norad, epoch_ms) and `INSERT OR IGNORE` makes a second
      pass free of effect - re-reading a bundle costs time, never correctness;
    * the manifest is written after every bundle, so the next run starts where
      this one stopped rather than where it began.

    `force` re-imports a bundle already marked done, which is how you verify
    that a bundle really did finish: a completed bundle re-imported reports
    every record as a duplicate and inserts nothing.
    """
    report: dict = {"imports": [], "skipped": [], "missing": [], "rowsByYear": {}}
    for year in years:
        manifest = load_manifest(directory)
        names = held_bundles_for_year(directory, manifest, year)
        if not names:
            report["missing"].append(year)
            if verbose:
                print(f"{year}: no bundle held on disk - fetch it first", flush=True)
            continue
        year_rows = 0
        for name in names:
            manifest = load_manifest(directory)
            state = (manifest["files"].get(name) or {}).get("import")
            if not force and isinstance(state, dict) and state.get("state") == "done":
                if verbose:
                    print(f"{name}: already imported", flush=True)
                report["skipped"].append(name)
                year_rows += int(state.get("elementsNew") or 0)
                continue

            started = time.time()

            def progress(offered: int, inserted: int, _name: str = name) -> None:
                if not verbose:
                    return
                elapsed = max(time.time() - started, 1e-6)
                print(
                    f"  {_name}: {offered:,} offered, {inserted:,} new, "
                    f"{offered / elapsed:,.0f} rows/s",
                    flush=True,
                )

            result = _import_with_lock_retry(
                connection, directory / name, on_batch=progress, verbose=verbose
            )
            report["imports"].append(result.as_dict())
            year_rows += result.elements_new
            manifest = load_manifest(directory)
            manifest["files"][name]["import"] = {
                "state": "done",
                "at": _now_iso(),
                **result.as_dict(),
            }
            save_manifest(directory, manifest)
            if verbose:
                print(json.dumps(result.as_dict(), indent=2), flush=True)
        report["rowsByYear"][year] = year_rows
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Back-fill the orbit archive from space-track's sanctioned bulk-TLE "
            "share. Never queries the space-track API."
        )
    )
    parser.add_argument("--archive", type=Path, default=None)
    parser.add_argument("--bulk-root", type=Path, default=None)
    parser.add_argument("--cold-root", type=Path, default=None)
    parser.add_argument(
        "--years",
        default=None,
        help="comma-separated years; default is the priority order "
        "(2024 first, for the Gannon storm, then recent years backwards)",
    )
    parser.add_argument("--list", action="store_true", help="enumerate the share")
    parser.add_argument("--download-only", action="store_true")
    parser.add_argument(
        "--import-held",
        action="store_true",
        help="import bundles already on disk and make no network request at "
        "all: no share listing, no browser. This is the resumable half of the "
        "backfill and the one to use once the 12 GB has been fetched.",
    )
    parser.add_argument(
        "--force-reimport",
        action="store_true",
        help="with --import-held, re-read a bundle already marked done. A "
        "finished bundle re-imported inserts nothing, which is how you prove "
        "it finished.",
    )
    parser.add_argument("--import-file", type=Path, default=None)
    parser.add_argument(
        "--cross-check",
        action="store_true",
        help="parse the live GP mirror's own TLE lines and compare against its "
        "GP elements: same object, same epoch, two representations",
    )
    parser.add_argument("--cross-check-bundle", type=Path, default=None)
    parser.add_argument("--verify-dedupe", action="store_true")
    parser.add_argument("--consolidate", metavar="YYYY", default=None)
    parser.add_argument("--storage-report", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args(argv)

    enforce_entity_boundary()

    directory = args.bulk_root or bulk_root()
    directory.mkdir(parents=True, exist_ok=True)

    if args.list:
        payload = mint_urls([], share=BULK_SHARE_URL)
        rows = payload.get("listing") or []
        total = sum(row.get("bytes") or 0 for row in rows)
        print(json.dumps({"files": len(rows), "totalBytes": total, "listing": rows}, indent=2))
        return 0

    if args.status:
        manifest = load_manifest(directory)
        held = {
            name: {
                "bytes": record.get("bytes"),
                "imported": (record.get("import") or {}).get("state"),
                "rows": (record.get("import") or {}).get("elementsNew"),
            }
            for name, record in sorted(manifest["files"].items())
        }
        print(json.dumps({"directory": str(directory), "held": held}, indent=2))
        return 0

    if args.cross_check:
        mirror = ROOT / "runtime" / "spacetrack-mirror" / "gp-active.json"
        print(json.dumps(cross_check_live_capture(mirror), indent=2))
        return 0

    connection = oh.open_archive(args.archive)
    tune_for_bulk(connection)
    cold = args.cold_root or oh.cold_root(args.archive.parent if args.archive else None)
    try:
        if args.import_file is not None:
            result = import_bundle(connection, args.import_file)
            print(json.dumps(result.as_dict(), indent=2))
            return 0
        if args.cross_check_bundle is not None:
            print(
                json.dumps(
                    cross_check_archive_overlap(connection, args.cross_check_bundle),
                    indent=2,
                )
            )
            return 0
        if args.verify_dedupe:
            print(json.dumps(verify_dedupe_at_scale(connection), indent=2))
            return 0
        if args.consolidate:
            year = int(args.consolidate)
            start_ms, _ = oh.month_bounds(year, 1)
            _, end_ms = oh.month_bounds(year, 12)
            print(
                json.dumps(
                    consolidate(
                        connection,
                        cold_directory=cold,
                        start_ms=start_ms,
                        end_ms=end_ms,
                    ),
                    indent=2,
                    default=str,
                )
            )
            return 0
        if args.storage_report:
            manifest = load_manifest(directory)
            rows_by_year: dict[int, int] = {}
            read_by_year: dict[int, int] = {}
            for name, record in manifest["files"].items():
                state = record.get("import") or {}
                if state.get("state") != "done":
                    continue
                try:
                    year = int(name[3:7])
                except ValueError:
                    continue
                rows_by_year[year] = rows_by_year.get(year, 0) + int(
                    state.get("elementsNew") or 0
                )
                read_by_year[year] = read_by_year.get(year, 0) + int(
                    state.get("recordsRead") or 0
                )
            report = storage_projection(rows_by_year)
            # `elementsNew` is what the FINAL pass inserted, not what the bundle
            # contributes. A bundle imported once reports the two as the same
            # thing; a bundle finished after an interruption does not, and the
            # difference is not small - tle2024 resumed on 2026-08-08 inserted
            # 516,270 rows into an archive that already held 15,445,194 of its
            # 15,961,464. Reporting 516,270 as "what 2024 costs" would be wrong
            # by a factor of thirty, so both numbers are printed and the
            # ambiguous one is named.
            report["rowsByYearCaveat"] = (
                "rowsByYear counts rows inserted by the pass that COMPLETED "
                "each bundle. Where an import was interrupted and resumed, the "
                "earlier passes' rows are not counted here and the true cost "
                "is larger - bounded above by recordsReadByYear. For the "
                "archive's actual size, measure the file."
            )
            report["recordsReadByYear"] = dict(sorted(read_by_year.items()))
            print(json.dumps(report, indent=2))
            return 0

        years = (
            [int(part) for part in args.years.split(",") if part.strip()]
            if args.years
            else list(PRIORITY_YEARS)
        )
        if args.import_held:
            print(
                json.dumps(
                    import_held_years(
                        years=years,
                        directory=directory,
                        connection=connection,
                        force=args.force_reimport,
                    ),
                    indent=2,
                )
            )
            return 0
        report = run_backfill(
            years=years,
            directory=directory,
            connection=None if args.download_only else connection,
            download_only=args.download_only,
        )
        print(json.dumps(report, indent=2))
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
