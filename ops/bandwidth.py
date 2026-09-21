#!/usr/bin/env python3
"""How many bytes this site moves, on which leg, measured rather than assumed.

WHY THIS EXISTS
---------------
On 2026-08-08 the VPS disk hit 97%. The cause turned out to be a bandwidth
problem wearing a disk problem's clothes: the publisher was shipping 83 GB/day
of raw artifacts from bigmem to the VPS, 71% of it the 256 content-addressed
orbit-history shards, which were rebuilt hourly and therefore got a new
filename — and were shipped in full — every hour. Nobody knew, because nothing
counted.

The reason nobody could have known by looking is that neither machine's
interface totals are about this site. bigmem is Sean's personal PC and runs
ComfyUI, local language models and other agents; the VPS runs Bob's entire
OpenClaw stack. ``/proc/net/dev`` and plain ``vnstat`` on either box are
dominated by traffic that has nothing to do with the Space Environment
Explorer. Reading one of those totals and labelling it "the site" would be the
exact class of unearned number this project forbids.

So every number here comes from an instrument attached to the transfer itself:

===========================  =====================================================
Leg                          Instrument
===========================  =====================================================
bigmem egress -> VPS         ``rsync --stats`` and ``--out-format='XFER|%l|%b|%n'``
                             inside ``pipeline/publish_vps.sh``. ``%b`` is the
                             bytes rsync actually put on the socket for that
                             file, so the per-family split is measured and not
                             apportioned.
bigmem ingress <- upstream   the fetchers themselves, at the point where the
                             socket read returns, via ``record()``.
bigmem ingress <- VPS        the CelesTrak-mirror rsync PULL in the same script.
VPS ingress <- bigmem        two independent sources, deliberately: bigmem's own
                             rsync figure, and the WireGuard peer counter read
                             on the VPS. They are shown side by side and a
                             disagreement is printed, never reconciled.
VPS egress -> the public      Caddy's access log, if it is enabled. Until it is,
                             the origin nginx log gives an UPPER BOUND, because
                             Caddy compresses on the way out and nginx does not.
===========================  =====================================================

WIRE BYTES AND RAW BYTES ARE DIFFERENT NUMBERS AND MUST NEVER BE ADDED
----------------------------------------------------------------------
This trap has already cost this project one wrong answer. A first measurement
of a cold visit totalled decoded response bodies and reported 13.97 MB; the
real figure on the wire was 1.71 MB, because artifacts are served gzipped. A
fourfold overstatement of what hosting the site costs.

The same trap is on the publish leg: ``rsync -z`` compresses in flight, so a
byte count taken from file sizes on disk overstates it the same way. On
2026-08-08 the raw shards were 2.26 GB/h and the compressed transfer was
0.53 GB/h — a factor of four again.

So every record carries a ``basis``: ``wire`` (what crossed the socket, after
compression) or ``raw`` (before it). ``totals()`` refuses to mix them. A total
without a basis is meaningless and this module will not produce one.

WHAT AN ABSENT MEASUREMENT LOOKS LIKE
-------------------------------------
``LegTotal.bytes`` is ``None`` when no instrument reported at all, and that is
different from ``0``, which means an instrument reported and it reported
nothing moved. The page renders ``None`` as "not measured" and never as a
number. This is the same rule the watchdog uses for an unmeasurable hour, and
it is here for the same reason: a comfortable number over a blind spot is
worse than an obvious hole.

Coverage is tracked separately from the total. The ledger begins when the
tracker was installed, so a month-to-date figure early in a month is a
measurement of PART of the month. ``coverage()`` reports what fraction of the
elapsed period actually has records behind it, and the projection is computed
from the measured window rather than from the month-to-date, so installing the
tracker on the 8th does not make the month look three-quarters empty.

NOTHING HERE IS A JUDGEMENT
---------------------------
There is no model, no heuristic and no threshold that is not stated on the page
next to the number it governs. Every function in this module is arithmetic over
a list of records.
"""

from __future__ import annotations

import argparse
import calendar
import datetime as dt
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "runtime" / "bandwidth"
LEDGER = STATE_DIR / "ledger.jsonl"
WG_CURSOR = STATE_DIR / "wireguard-cursor.json"
NGINX_CURSOR = STATE_DIR / "nginx-egress-cursor.json"
ALLOWANCES = ROOT / "ops" / "allowances.json"

HOUR = 3600.0
DAY = 86400.0

SCHEMA_VERSION = 1

#: Keep the ledger bounded. At one record per artifact family per publish cycle
#: this is roughly a year of history; the trim keeps the newest half. The same
#: shape as ops/watchdog.SAMPLE_LIMIT, and for the same reason: an operations
#: file that grows without bound is itself the slow leak this page exists to
#: catch in other people's code.
LEDGER_LIMIT = 400_000

# ---------------------------------------------------------------------------
# The closed vocabularies. A record outside them is rejected at write time
# rather than quietly summed into the wrong column later.
# ---------------------------------------------------------------------------

#: bigmem sends to the VPS. This is the leg that crosses Sean's home
#: connection, and it is the one that was at 43% of his allowance.
BIGMEM_EGRESS = "bigmem-egress"
#: bigmem receives — from NOAA, space-track, and the CelesTrak mirror pull.
BIGMEM_INGRESS = "bigmem-ingress"
#: The same transfer as BIGMEM_EGRESS, counted at the far end. Kept as its own
#: leg on purpose: if the two disagree, something is moving that nobody
#: accounted for, and that is worth seeing rather than averaging away.
VPS_INGRESS = "vps-ingress"
#: The VPS serving the site to browsers. This is what an egress allowance bills.
VPS_EGRESS = "vps-egress"

LEGS = (BIGMEM_EGRESS, BIGMEM_INGRESS, VPS_INGRESS, VPS_EGRESS)

LEG_WORDS = {
    BIGMEM_EGRESS: "bigmem → VPS (publish)",
    BIGMEM_INGRESS: "bigmem ← upstream and VPS (fetch)",
    VPS_INGRESS: "VPS ← bigmem (publish, counted at the VPS)",
    VPS_EGRESS: "VPS → the public internet (visitors)",
}

#: What crossed the socket, after any compression. The only figure an ISP or a
#: host meters.
WIRE = "wire"
#: What the bytes measured before compression. Useful for "how big is this
#: layer", useless for "what does it cost", and never added to a wire total.
RAW = "raw"

BASES = (WIRE, RAW)

#: Artifact families, derived from the filename prefix that
#: deploy/publish_data.py writes. ``orbit-history-000`` .. ``orbit-history-255``
#: collapse to one family, because 256 shards of one layer is one answer to
#: "which layer is eating the allowance", not 256.
ARTIFACT_FAMILIES = (
    "aurora",
    "catalog",
    "drap",
    "events",
    "geospace-model",
    "ionosphere-model",
    "land-110m",
    "orbit-drag",
    "orbit-events",
    "orbit-history",
    "provenance",
    "space-weather",
)

#: Not an artifact family: the bytes rsync spends on its own file list and
#: protocol framing. Measured as the residual between the run total and the sum
#: of the per-file figures, so the columns add up exactly rather than nearly.
PROTOCOL_FAMILY = "rsync-protocol"

#: Anything under artifacts/ whose prefix is not in ARTIFACT_FAMILIES. A new
#: layer lands here and is visible immediately rather than being silently
#: folded into a neighbour.
OTHER_FAMILY = "other"

#: The manifest, and the operations pages. Neither is an artifact family, and
#: both cross the same link, so they get their own rows rather than swelling
#: "other" into a bucket nobody can interpret.
MANIFEST_FAMILY = "manifest"
OPS_PAGES_FAMILY = "ops-pages"

#: Upstream sources, for the ingress leg.
UPSTREAM_FAMILIES = (
    "noaa-swpc",
    "noaa-nomads-swmf",
    "noaa-nomads-wam-ipe",
    "space-track",
    "space-track-bulk",
    "celestrak-mirror-pull",
    "natural-earth",
    "literature",
    "other-upstream",
)

FAMILIES = tuple(sorted(set(
    ARTIFACT_FAMILIES + UPSTREAM_FAMILIES
    + (PROTOCOL_FAMILY, OTHER_FAMILY, MANIFEST_FAMILY, OPS_PAGES_FAMILY, "site-total")
)))

_RECORD_FIELDS = frozenset({
    "schema", "at", "leg", "family", "bytes", "basis", "source", "run",
})

_SHARD = re.compile(r"^orbit-history-\d{3}$")
_HASHED = re.compile(r"^(?P<stem>.+?)-[0-9a-f]{8,}\.")


def family_of(filename: str) -> str:
    """The artifact family a published filename belongs to.

    Filenames are ``<family>-<content hash>.<ext>``. Splitting on the last
    hyphen before a hex run is the only rule here; anything that does not match
    is ``other`` rather than a guess.
    """
    name = filename.rsplit("/", 1)[-1]
    match = _HASHED.match(name)
    stem = match.group("stem") if match else name.split(".", 1)[0]
    if _SHARD.match(stem):
        return "orbit-history"
    if stem in ARTIFACT_FAMILIES:
        return stem
    return OTHER_FAMILY


# ---------------------------------------------------------------------------
# Writing. Append-only, one JSON object per line, validated before it lands.
# ---------------------------------------------------------------------------

def _validate(record: dict) -> dict:
    if set(record) != _RECORD_FIELDS:
        missing = sorted(_RECORD_FIELDS - set(record))
        extra = sorted(set(record) - _RECORD_FIELDS)
        raise ValueError(f"bandwidth record schema: missing={missing} extra={extra}")
    if record["leg"] not in LEGS:
        raise ValueError(f"unknown leg {record['leg']!r}; expected one of {LEGS}")
    if record["basis"] not in BASES:
        raise ValueError(f"unknown basis {record['basis']!r}; expected one of {BASES}")
    if record["family"] not in FAMILIES:
        raise ValueError(f"unknown family {record['family']!r}")
    if not isinstance(record["bytes"], int) or record["bytes"] < 0:
        raise ValueError(f"bytes must be a non-negative integer, got {record['bytes']!r}")
    if not record["source"]:
        raise ValueError("every record must name the instrument that measured it")
    return record


def record(*, leg: str, family: str, byte_count: int, basis: str, source: str,
           run: str, at: float | None = None, path: Path = LEDGER) -> dict:
    """Append one measurement.

    ``source`` is the instrument, in words, and is not optional: a byte total
    whose provenance is not written down is not evidence of anything, and this
    page's whole claim is that its numbers are attributable.
    """
    entry = _validate({
        "schema": SCHEMA_VERSION,
        "at": float(at if at is not None else _now()),
        "leg": leg,
        "family": family,
        "bytes": int(byte_count),
        "basis": basis,
        "source": source,
        "run": run,
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, sort_keys=True) + "\n"
    # One write() of one short line, opened O_APPEND: the kernel will not
    # interleave it with a concurrent publish cycle's write. Whole-file state
    # elsewhere in this repo uses temp-file-and-rename; that is the wrong tool
    # for an append-only log, where rename would race away another writer's
    # line entirely.
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)
    return entry


def _now() -> float:
    import time  # noqa: PLC0415 - keeps the module importable with a frozen clock in tests
    return time.time()


def trim(path: Path = LEDGER, limit: int = LEDGER_LIMIT) -> int:
    """Keep the ledger bounded. Returns how many lines were dropped."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return 0
    if len(lines) <= limit:
        return 0
    keep = lines[-(limit // 2):]
    temporary = path.with_suffix(path.suffix + ".next")
    temporary.write_text("\n".join(keep) + "\n", encoding="utf-8")
    temporary.replace(path)
    return len(lines) - len(keep)


def read(path: Path = LEDGER, *, since: float | None = None,
         until: float | None = None) -> list[dict]:
    """Every valid record in the window. A corrupt line is skipped, not fatal."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    out = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict) or "at" not in entry or "bytes" not in entry:
            continue
        if since is not None and entry["at"] < since:
            continue
        if until is not None and entry["at"] >= until:
            continue
        out.append(entry)
    return out


# ---------------------------------------------------------------------------
# Arithmetic. Every function below is a sum, a ratio or a comparison.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LegTotal:
    """One leg's bytes over one window, on one basis.

    ``bytes is None`` means *no instrument reported*, which is not the same as
    zero. Nothing that renders this may substitute a number for None.
    """

    leg: str
    basis: str
    bytes: int | None
    records: int
    first_at: float | None
    last_at: float | None
    sources: tuple[str, ...] = ()

    @property
    def measured(self) -> bool:
        return self.records > 0

    @property
    def span_seconds(self) -> float | None:
        """How long the measurements themselves cover.

        One record covers no span, so this is None until there are two. A rate
        computed from a single observation is not a rate.
        """
        if self.first_at is None or self.last_at is None or self.records < 2:
            return None
        span = self.last_at - self.first_at
        return span if span > 0 else None


def totals(records: Iterable[dict], *, leg: str, basis: str) -> LegTotal:
    """Sum one leg on one basis. Refuses to mix wire and raw by construction."""
    if basis not in BASES:
        raise ValueError(f"unknown basis {basis!r}")
    selected = [r for r in records if r.get("leg") == leg and r.get("basis") == basis]
    if not selected:
        return LegTotal(leg=leg, basis=basis, bytes=None, records=0,
                        first_at=None, last_at=None)
    stamps = [r["at"] for r in selected]
    return LegTotal(
        leg=leg,
        basis=basis,
        bytes=sum(int(r["bytes"]) for r in selected),
        records=len(selected),
        first_at=min(stamps),
        last_at=max(stamps),
        sources=tuple(sorted({str(r.get("source", "?")) for r in selected})),
    )


def by_family(records: Iterable[dict], *, leg: str, basis: str) -> list[tuple[str, int, int]]:
    """``(family, bytes, record count)``, largest first.

    This breakdown is the entire point of the page. The orbit-history problem
    was findable only because the bytes could be attributed to a layer; a
    single grand total would have shown a big number and no lever.
    """
    buckets: dict[str, list[int]] = {}
    for entry in records:
        if entry.get("leg") != leg or entry.get("basis") != basis:
            continue
        slot = buckets.setdefault(str(entry.get("family", OTHER_FAMILY)), [0, 0])
        slot[0] += int(entry["bytes"])
        slot[1] += 1
    return sorted(((name, v[0], v[1]) for name, v in buckets.items()),
                  key=lambda row: -row[1])


def billing_period(now: float, *, start_day: int = 1) -> tuple[float, float]:
    """The billing month containing ``now``, in UTC, as (start, end) epochs.

    ``start_day`` is the day of the month the allowance resets. It defaults to
    1 — the calendar month — and the page states that this is an assumption
    until Sean confirms his ISP's actual reset day, because a cap measured over
    the wrong month is measured over the wrong month.
    """
    start_day = max(1, min(28, int(start_day)))
    moment = dt.datetime.fromtimestamp(now, dt.timezone.utc)
    if moment.day >= start_day:
        start = moment.replace(day=start_day, hour=0, minute=0, second=0, microsecond=0)
    else:
        previous_month = moment.replace(day=1) - dt.timedelta(days=1)
        start = previous_month.replace(day=start_day, hour=0, minute=0,
                                       second=0, microsecond=0)
    days_in_month = calendar.monthrange(start.year, start.month)[1]
    end = start + dt.timedelta(days=days_in_month)
    # A period that started on the 31st of a 31-day month must not land on the
    # 31st of a 30-day one; clamping start_day to 28 above makes that
    # impossible, and this assertion is what keeps it impossible if anyone
    # widens the clamp.
    assert end > start
    return start.timestamp(), end.timestamp()


@dataclass(frozen=True)
class Coverage:
    """How much of the elapsed period the ledger actually has records for."""

    period_start: float
    period_end: float
    now: float
    first_record_at: float | None

    @property
    def elapsed_seconds(self) -> float:
        return max(0.0, min(self.now, self.period_end) - self.period_start)

    @property
    def measured_seconds(self) -> float:
        if self.first_record_at is None:
            return 0.0
        return max(0.0, min(self.now, self.period_end) - max(self.first_record_at,
                                                             self.period_start))

    @property
    def fraction(self) -> float | None:
        if self.elapsed_seconds <= 0:
            return None
        return self.measured_seconds / self.elapsed_seconds

    @property
    def complete(self) -> bool:
        """True only if records exist from the first moment of the period.

        A one-minute tolerance, because the ledger's first line lands a moment
        after the period boundary in the month the tracker was installed and a
        month later than that it is genuinely complete.
        """
        fraction = self.fraction
        return fraction is not None and fraction >= 1 - (60 / max(1.0, self.elapsed_seconds))

    @property
    def remaining_seconds(self) -> float:
        return max(0.0, self.period_end - self.now)

    @property
    def remaining_days(self) -> float:
        return self.remaining_seconds / DAY


@dataclass(frozen=True)
class Projection:
    """A month-end figure, and the window it was extrapolated from.

    Every field needed to say "this is a projection and here is what from" is
    on the object, so no caller can render the number without the caveat.
    """

    per_day: float
    period_total: float
    window_seconds: float
    window_bytes: int
    measured_to_date: int

    label = "projection"

    #: A month-end figure extrapolated from less than this is arithmetic over
    #: an unrepresentative sample, and it is worse than no figure because it
    #: looks like one. A full day is the shortest window that can contain the
    #: daily orbit-history rebuild -- the single largest thing this site ships,
    #: and the thing whose cadence the page exists to let Sean choose. A window
    #: that misses it understates the month; a short window that happens to
    #: catch it overstates it several-fold. Twelve minutes of measurement once
    #: projected this leg at 92% of the home allowance.
    minimum_window = DAY

    @property
    def reliable(self) -> bool:
        return self.window_seconds >= self.minimum_window

    def rate_sentence(self) -> str:
        return (f"measured at {self.per_day / 1e9:.2f} GB/day over "
                f"{self.window_seconds / 60:.0f} minutes of records")

    def sentence(self) -> str:
        if not self.reliable:
            return (f"{self.rate_sentence()} — too short to project a month. A month-end "
                    "figure needs at least a full day, because the daily orbit-history "
                    "rebuild is the largest single thing this site ships and a shorter "
                    "window either misses it entirely or is dominated by it.")
        return (f"projected from {self.window_seconds / DAY:.2f} days of measurement "
                f"at {self.per_day / 1e9:.2f} GB/day — a projection, not a measurement")


def project(total: LegTotal, coverage: Coverage) -> Projection | None:
    """Month-end from the measured window. None when there is nothing to project.

    The rate comes from the window that has records in it, NOT from the whole
    elapsed period. Dividing a part-month measurement by a whole part-month
    would report a rate the instruments never observed, and on the day the
    tracker is installed it would report roughly zero.
    """
    if total.bytes is None or not total.measured:
        return None
    window = coverage.measured_seconds
    if window <= 0:
        return None
    per_day = total.bytes / window * DAY
    already = total.bytes
    period_total = already + per_day * (coverage.remaining_seconds / DAY)
    return Projection(per_day=per_day, period_total=period_total,
                      window_seconds=window, window_bytes=total.bytes,
                      measured_to_date=already)


@dataclass(frozen=True)
class Disagreement:
    """Two independent measurements of the same leg, and the gap between them.

    Never reconciled, never averaged, and neither one is preferred. If bigmem
    thinks it sent 8 GB and the VPS thinks it received 12, something is moving
    over that link that nobody in this repository accounted for, and the useful
    output is the sentence saying so.
    """

    left_name: str
    left: int | None
    right_name: str
    right: int | None

    #: Below this the two are treated as agreeing. rsync counts its own
    #: protocol bytes; WireGuard counts those plus SSH framing, TCP/IP headers
    #: and the tunnel's own encapsulation, so the far end reading a few percent
    #: high is expected rather than surprising.
    tolerance = 0.15

    @property
    def comparable(self) -> bool:
        return self.left is not None and self.right is not None

    @property
    def delta(self) -> int | None:
        return None if not self.comparable else self.right - self.left

    @property
    def ratio(self) -> float | None:
        if not self.comparable or not self.left:
            return None
        return self.right / self.left

    @property
    def agrees(self) -> bool | None:
        ratio = self.ratio
        if ratio is None:
            return None
        return abs(ratio - 1.0) <= self.tolerance

    #: The window both instruments actually covered, so the sentence can say
    #: what was compared rather than implying it was the whole month.
    window: tuple[float, float] | None = None
    reason: str = ""

    def sentence(self) -> str:
        if self.reason:
            return self.reason
        if not self.comparable:
            missing = self.left_name if self.left is None else self.right_name
            return f"cannot be cross-checked: {missing} reported no measurement"
        ratio = self.ratio
        if ratio is None:
            return (f"{self.left_name} measured nothing, {self.right_name} measured "
                    f"{self.right:,} bytes")
        verdict = "agree" if self.agrees else "DISAGREE"
        window = ""
        if self.window:
            window = (f", over the {(self.window[1] - self.window[0]) / 60:.0f} minutes "
                      "both instruments covered")
        return (f"{self.left_name} {self.left:,} B vs {self.right_name} {self.right:,} B "
                f"— {ratio:.2f}×, they {verdict} "
                f"(tolerance ±{self.tolerance:.0%}){window}")


def cross_check(records: Sequence[dict]) -> Disagreement:
    """Compare the publish leg's two instruments over the window BOTH cover.

    This has to be an overlap, not a month-to-date against a month-to-date. The
    WireGuard counter only starts producing intervals once it has been sampled
    twice, and rsync starts recording the moment the publish script is updated;
    comparing the two running totals in the hours after installation shows a
    gap that is entirely an artefact of when each instrument woke up. A page
    that shouts DISAGREE on its first afternoon is a page nobody believes on
    the day it is right.

    The comparable window is between consecutive WireGuard samples. The first
    sample's own interval reaches back before the ledger, so it is excluded.
    Fewer than two samples is not a disagreement, it is not yet a comparison.
    """
    wg = sorted((r for r in records if r.get("leg") == VPS_INGRESS
                 and r.get("basis") == WIRE), key=lambda r: r["at"])
    left_name = "bigmem's rsync (--stats)"
    right_name = "the VPS's WireGuard counter"
    if len(wg) < 2:
        return Disagreement(left_name, None, right_name, None,
                            reason="not enough WireGuard samples yet to compare a common "
                                   "window — two consecutive samples are needed before "
                                   "either instrument has an interval the other also "
                                   "covers. This is not a disagreement.")
    start, end = wg[0]["at"], wg[-1]["at"]
    far = sum(int(r["bytes"]) for r in wg if start < r["at"] <= end)
    near = sum(int(r["bytes"]) for r in records
               if r.get("leg") == BIGMEM_EGRESS and r.get("basis") == WIRE
               and start < r["at"] <= end)
    return Disagreement(left_name, near, right_name, far, window=(start, end))


# ---------------------------------------------------------------------------
# Allowances. A number Sean gave from memory is not a measurement either, and
# this file is where that distinction is kept.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AllowanceWindow:
    bytes: int | None
    unlimited: bool
    effective_from: str | None
    confirmed: bool
    note: str

    @property
    def scheduled(self) -> bool:
        """An announced change with no date is not in force and never applies."""
        return self.effective_from is not None


@dataclass(frozen=True)
class Allowance:
    key: str
    label: str
    counts: str
    billing_start_day: int
    billing_day_confirmed: bool
    windows: tuple[AllowanceWindow, ...]
    source_note: str = ""
    announced: tuple[AllowanceWindow, ...] = field(default_factory=tuple)

    def at(self, when: float) -> AllowanceWindow | None:
        """The window in force at ``when``. None if nothing is in force yet."""
        moment = dt.datetime.fromtimestamp(when, dt.timezone.utc).date()
        chosen = None
        for window in self.windows:
            if not window.scheduled:
                continue
            starts = dt.date.fromisoformat(window.effective_from)
            if starts <= moment and (chosen is None or
                                     dt.date.fromisoformat(chosen.effective_from) <= starts):
                chosen = window
        return chosen


def _window(raw: dict) -> AllowanceWindow:
    return AllowanceWindow(
        bytes=None if raw.get("bytes") is None else int(raw["bytes"]),
        unlimited=bool(raw.get("unlimited", False)),
        effective_from=raw.get("effectiveFrom"),
        confirmed=bool(raw.get("confirmed", False)),
        note=str(raw.get("note", "")),
    )


def load_allowances(path: Path = ALLOWANCES) -> dict[str, Allowance]:
    """Read ops/allowances.json. A missing file yields nothing, never a default.

    There is deliberately no fallback constant. An allowance this code invented
    would be indistinguishable on the page from one Sean confirmed, and the
    whole point of the file is that the page can say which it is.
    """
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out: dict[str, Allowance] = {}
    for key, raw in (blob.get("allowances") or {}).items():
        windows = tuple(_window(w) for w in (raw.get("windows") or []))
        out[key] = Allowance(
            key=key,
            label=str(raw.get("label", key)),
            counts=str(raw.get("counts", "unstated")),
            billing_start_day=int(raw.get("billingStartDay", 1)),
            billing_day_confirmed=bool(raw.get("billingStartDayConfirmed", False)),
            windows=tuple(w for w in windows if w.scheduled),
            announced=tuple(w for w in windows if not w.scheduled),
            source_note=str(raw.get("sourceNote", "")),
        )
    return out


def share_of_allowance(byte_count: int | None, window: AllowanceWindow | None) -> float | None:
    """Fraction of the allowance used. None when either side is unknown."""
    if byte_count is None or window is None or window.unlimited or not window.bytes:
        return None
    return byte_count / window.bytes


# ---------------------------------------------------------------------------
# Instruments.
# ---------------------------------------------------------------------------

_STATS_SENT = re.compile(r"^Total bytes sent:\s*([\d,]+)", re.M)
_STATS_RECEIVED = re.compile(r"^Total bytes received:\s*([\d,]+)", re.M)
_XFER = re.compile(r"^XFER\|(\d+)\|(\d+)\|(.*)$", re.M)


def parse_rsync(text: str) -> dict:
    """Pull the measured figures out of one rsync run's output.

    Requires ``--stats`` and ``--out-format='XFER|%l|%b|%n'``. ``%l`` is the
    file's length; ``%b`` is the bytes rsync actually transferred for it, which
    with ``-z`` is the COMPRESSED figure and therefore the one that crossed the
    wire. ``Total bytes sent`` is the same measurement for the whole run and
    includes the file list and protocol chatter, so it is slightly larger than
    the sum of the per-file numbers; the difference is reported rather than
    discarded so the columns add up exactly.

    None for a figure the output did not contain — an rsync that died before
    printing its stats block has not transferred a known number of bytes, and
    the caller must not treat that as zero.
    """
    sent = _STATS_SENT.search(text)
    received = _STATS_RECEIVED.search(text)
    files: list[tuple[str, int, int]] = []
    for raw_length, raw_wire, name in _XFER.findall(text):
        files.append((name.strip(), int(raw_length), int(raw_wire)))
    per_file_wire = sum(wire for _, _, wire in files)
    total_sent = int(sent.group(1).replace(",", "")) if sent else None
    return {
        "totalSent": total_sent,
        "totalReceived": (int(received.group(1).replace(",", "")) if received else None),
        "files": files,
        "perFileWire": per_file_wire if files else 0,
        "perFileRaw": sum(length for _, length, _ in files),
        "overhead": (None if total_sent is None else max(0, total_sent - per_file_wire)),
    }


def record_rsync_push(text: str, *, run: str, path: Path = LEDGER,
                      at: float | None = None, force_family: str | None = None) -> dict:
    """Record one bigmem -> VPS rsync, split by artifact family.

    Writes wire bytes per family plus a ``rsync-protocol`` residual, so the
    family column sums exactly to ``Total bytes sent``. Also writes the raw
    per-family figures on the ``raw`` basis, because "how big is this layer"
    and "what does this layer cost" are both worth knowing and are different
    numbers.

    ``force_family`` is for transfers that are not artifacts at all — the
    operations pages, for instance, whose filenames carry no family prefix and
    would otherwise pile into ``other`` where nobody could tell them apart from
    a new layer that had appeared without anyone noticing.
    """
    parsed = parse_rsync(text)
    if parsed["totalSent"] is None:
        # No stats block: the run did not report, so nothing is recorded. A
        # zero here would read on the page as a publish that cost nothing.
        return {"recorded": 0, "reason": "rsync printed no --stats block", **parsed}
    wire: dict[str, int] = {}
    raw: dict[str, int] = {}
    for name, length, sent in parsed["files"]:
        family = force_family if force_family in FAMILIES else family_of(name)
        wire[family] = wire.get(family, 0) + sent
        raw[family] = raw.get(family, 0) + length
    if parsed["overhead"]:
        wire[PROTOCOL_FAMILY] = wire.get(PROTOCOL_FAMILY, 0) + parsed["overhead"]
    written = 0
    for family, count in sorted(wire.items()):
        record(leg=BIGMEM_EGRESS, family=family, byte_count=count, basis=WIRE,
               source="rsync --stats / --out-format %b", run=run, at=at, path=path)
        written += 1
    for family, count in sorted(raw.items()):
        record(leg=BIGMEM_EGRESS, family=family, byte_count=count, basis=RAW,
               source="rsync --out-format %l (file length on disk)", run=run,
               at=at, path=path)
        written += 1
    return {"recorded": written, **parsed}


def record_rsync_pull(text: str, *, run: str, family: str = "celestrak-mirror-pull",
                      path: Path = LEDGER, at: float | None = None) -> dict:
    """Record one VPS -> bigmem rsync. This is bigmem INGRESS, not egress.

    The publish script pulls the CelesTrak mirror down from the VPS on every
    cycle; it runs over the same private link and costs the same home
    allowance, but in the other direction, and counting it as egress would
    inflate the number Sean is watching.
    """
    parsed = parse_rsync(text)
    if parsed["totalReceived"] is None:
        return {"recorded": 0, "reason": "rsync printed no --stats block", **parsed}
    record(leg=BIGMEM_INGRESS, family=family, byte_count=parsed["totalReceived"],
           basis=WIRE, source="rsync --stats: Total bytes received", run=run,
           at=at, path=path)
    return {"recorded": 1, **parsed}


_UPSTREAM_BY_HOST = (
    ("services.swpc.noaa.gov", "noaa-swpc"),
    ("swpc.noaa.gov", "noaa-swpc"),
    ("ncei.noaa.gov", "noaa-swpc"),
    ("archive.data.noaa.gov", "noaa-swpc"),
    ("nomads.ncep.noaa.gov/pub/data/nccf/com/swmf", "noaa-nomads-swmf"),
    ("nomads.ncep.noaa.gov/pub/data/nccf/com/wfs", "noaa-nomads-wam-ipe"),
    ("space-track.org", "space-track"),
    ("ln5.sync.com", "space-track-bulk"),
    ("celestrak.org", "celestrak-mirror-pull"),
    ("raw.githubusercontent.com", "natural-earth"),
    ("naturalearthdata.com", "natural-earth"),
    ("arxiv.org", "literature"),
    ("crossref.org", "literature"),
)


def upstream_family(url: str) -> str:
    """Which upstream a URL belongs to. Unrecognised hosts are named as such.

    A new upstream shows up in its own row as ``other-upstream`` rather than
    being folded into whichever family happened to be listed first, which is
    how an unnoticed new fetch stays unnoticed.
    """
    lowered = (url or "").lower()
    for marker, family in _UPSTREAM_BY_HOST:
        if marker in lowered:
            return family
    return "other-upstream"


def record_fetch(byte_count: int, *, family: str, source: str, run: str,
                 path: Path = LEDGER, at: float | None = None) -> None:
    """One upstream download, recorded where the socket read returned.

    Called from the fetchers. Deliberately swallows its own errors: a
    bandwidth ledger that can break a data pipeline is a worse problem than an
    unmeasured hour, and an unmeasured hour is exactly what this module knows
    how to display honestly.

    The basis is ``raw``. ``len(body)`` after urllib has decoded a gzipped
    response is the decompressed length, not what came off the socket, and
    labelling it ``wire`` would repeat the 13.97-vs-1.71 MB mistake in the
    other direction.
    """
    try:
        record(leg=BIGMEM_INGRESS, family=family, byte_count=int(byte_count),
               basis=RAW, source=source, run=run, at=at, path=path)
    except Exception:  # noqa: BLE001 - measurement must never break a fetch
        pass


def record_wireguard(rx_bytes: int | None, *, peer: str, run: str,
                     cursor: Path = WG_CURSOR, path: Path = LEDGER,
                     at: float | None = None) -> dict:
    """Turn the VPS's WireGuard peer counter into a delta, and record it.

    ``wg show wg0 transfer`` is a counter since the interface came up, so it is
    a DELTA source and never a total. Two things must not happen:

    * A restart resets it to zero. Recording the new low value as a delta would
      subtract traffic that really happened. On a decrease, the cursor is
      re-based and nothing is recorded for that interval, which is honest: the
      bytes between the last sample and the restart are genuinely lost.
    * The first sample has no predecessor, so it establishes the cursor and
      records nothing. A tracker that counted a lifetime counter as one
      interval's traffic would report the machine's whole uptime as today.
    """
    now = float(at if at is not None else _now())
    if rx_bytes is None:
        return {"recorded": 0, "reason": "the VPS did not report a WireGuard counter"}
    previous = None
    try:
        previous = json.loads(cursor.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = None
    outcome = {"recorded": 0, "reason": "first sample; cursor established"}
    if previous and previous.get("peer") == peer and isinstance(previous.get("rx"), int):
        delta = rx_bytes - previous["rx"]
        if delta < 0:
            outcome = {"recorded": 0, "reason": "counter reset (interface restarted); re-based"}
        elif delta == 0:
            outcome = {"recorded": 0, "reason": "no change since the last sample"}
        else:
            record(leg=VPS_INGRESS, family="site-total", byte_count=delta, basis=WIRE,
                   source="wg show wg0 transfer (peer counter delta)", run=run,
                   at=now, path=path)
            outcome = {"recorded": 1, "bytes": delta,
                       "since": previous.get("at"), "reason": "delta recorded"}
    cursor.parent.mkdir(parents=True, exist_ok=True)
    temporary = cursor.with_suffix(".next")
    temporary.write_text(json.dumps({"peer": peer, "rx": int(rx_bytes), "at": now},
                                    indent=2) + "\n", encoding="utf-8")
    temporary.replace(cursor)
    return outcome


def record_origin_egress(byte_count: int | None, requests: int | None, *, run: str,
                         cursor: Path = NGINX_CURSOR, path: Path = LEDGER,
                         at: float | None = None) -> dict:
    """Record the origin nginx byte total as an UPPER BOUND on public egress.

    nginx sits behind Caddy. Caddy strips ``Accept-Encoding`` on the way in and
    compresses on the way out, so nginx's ``$body_bytes_sent`` is the
    UNCOMPRESSED size of what it handed Caddy, and the bytes that actually left
    the VPS are smaller — measured at roughly 1.71 MB wire against 13.97 MB
    decoded for one cold visit, so the overstatement is around eightfold.

    It is still worth recording, because an upper bound is a real fact and it
    can only ever make the allowance look tighter than it is. It is written on
    the ``raw`` basis so it can never be summed into a wire total, and the page
    labels it as a ceiling. The exact figure needs Caddy's access log, which is
    not currently enabled; see the hand-over notes.
    """
    now = float(at if at is not None else _now())
    if byte_count is None:
        return {"recorded": 0, "reason": "the VPS did not report an origin byte total"}
    previous = None
    try:
        previous = json.loads(cursor.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = None
    outcome = {"recorded": 0, "reason": "first sample; cursor established"}
    if previous and isinstance(previous.get("bytes"), int):
        delta = byte_count - previous["bytes"]
        if delta < 0:
            outcome = {"recorded": 0, "reason": "log rotated or container restarted; re-based"}
        elif delta == 0:
            outcome = {"recorded": 0, "reason": "no change since the last sample"}
        else:
            record(leg=VPS_EGRESS, family="site-total", byte_count=delta, basis=RAW,
                   source="nginx $body_bytes_sent at the origin (UPPER BOUND: "
                          "Caddy compresses downstream of this)",
                   run=run, at=now, path=path)
            outcome = {"recorded": 1, "bytes": delta, "reason": "delta recorded"}
    cursor.parent.mkdir(parents=True, exist_ok=True)
    temporary = cursor.with_suffix(".next")
    temporary.write_text(json.dumps({"bytes": int(byte_count), "requests": requests,
                                     "at": now}, indent=2) + "\n", encoding="utf-8")
    temporary.replace(cursor)
    return outcome


# ---------------------------------------------------------------------------
# What one orbit-history rebuild costs. The number that makes the cadence
# control an informed choice rather than a guess.
# ---------------------------------------------------------------------------

#: Measured by hand on 2026-08-08, before this tracker existed, and recorded in
#: deploy/systemd/orbit-release.timer's comment block: 2.26 GB of raw shards per
#: rebuild, 0.53 GB once rsync had compressed them. Used ONLY until the ledger
#: has observed a rebuild of its own, and always labelled with its provenance,
#: because a hand measurement from a different day is a weaker claim than one
#: this page took itself.
HAND_MEASURED_REBUILD_WIRE = 530_000_000
HAND_MEASURED_REBUILD_NOTE = (
    "measured by hand on 2026-08-08, before this tracker existed "
    "(2.26 GB raw, 0.53 GB compressed) — not measured by this page"
)

#: A rebuild ships its shards inside one or two consecutive publish cycles, and
#: the next rebuild is at least an hour away at the fastest cadence on offer.
#: An hour of silence is therefore the boundary between one rebuild and the
#: next, and it is stated on the page next to the number it produces.
BURST_GAP_SECONDS = 3600.0


def bursts(records: Iterable[dict], *, leg: str, basis: str, family: str,
           gap: float = BURST_GAP_SECONDS) -> list[dict]:
    """Group one family's records into transfer episodes separated by silence."""
    selected = sorted(
        (r for r in records
         if r.get("leg") == leg and r.get("basis") == basis and r.get("family") == family),
        key=lambda r: r["at"],
    )
    out: list[dict] = []
    for entry in selected:
        if out and entry["at"] - out[-1]["end"] <= gap:
            out[-1]["end"] = entry["at"]
            out[-1]["bytes"] += int(entry["bytes"])
            out[-1]["records"] += 1
        else:
            out.append({"start": entry["at"], "end": entry["at"],
                        "bytes": int(entry["bytes"]), "records": 1})
    return out


def rebuild_cost(records: Iterable[dict], now: float | None = None) -> dict:
    """Wire bytes one orbit-history rebuild puts on the link.

    Prefers this page's own measurement and falls back to the hand measurement
    only when it has never seen a complete rebuild. ``measured`` says which,
    and the page prints that word rather than hiding the difference.
    """
    moment = float(now if now is not None else _now())
    episodes = bursts(records, leg=BIGMEM_EGRESS, basis=WIRE, family="orbit-history")
    # An episode is complete once it has been quiet for a full gap. Testing
    # that directly, rather than always discarding the newest, is what lets a
    # single finished rebuild count -- and a rebuild is a daily event at the
    # default cadence, so "wait for the second one" would have meant a day of
    # showing a hand measurement over one this page had already taken.
    usable = [e for e in episodes if moment - e["end"] > BURST_GAP_SECONDS]
    if usable:
        total = sum(e["bytes"] for e in usable)
        return {"bytes": total / len(usable), "episodes": len(usable), "measured": True,
                "note": f"mean of {len(usable)} complete rebuild(s) this page measured, "
                        f"grouped by {BURST_GAP_SECONDS / 60:.0f} minutes of silence "
                        "and counted only once quiet that long"}
    return {"bytes": float(HAND_MEASURED_REBUILD_WIRE), "episodes": 0, "measured": False,
            "note": HAND_MEASURED_REBUILD_NOTE}


# ---------------------------------------------------------------------------
# The one function the page and --json both call.
# ---------------------------------------------------------------------------

def summarise(now: float, *, path: Path = LEDGER,
              allowances_path: Path = ALLOWANCES) -> dict:
    """Everything the page needs, as plain data. No colours, no words of praise."""
    allowances = load_allowances(allowances_path)
    home = allowances.get("home")
    vps = allowances.get("vps")
    start_day = home.billing_start_day if home else 1
    period_start, period_end = billing_period(now, start_day=start_day)
    records = read(path, since=period_start, until=period_end)
    everything = read(path)
    first_ever = min((r["at"] for r in everything), default=None)
    coverage = Coverage(period_start=period_start, period_end=period_end, now=now,
                        first_record_at=first_ever)

    legs = {}
    for leg in LEGS:
        for basis in BASES:
            legs[f"{leg}/{basis}"] = totals(records, leg=leg, basis=basis)

    return {
        "now": now,
        "periodStart": period_start,
        "periodEnd": period_end,
        "billingStartDay": start_day,
        "billingDayConfirmed": bool(home and home.billing_day_confirmed),
        "coverage": coverage,
        "legs": legs,
        "families": {
            f"{BIGMEM_EGRESS}/{WIRE}": by_family(records, leg=BIGMEM_EGRESS, basis=WIRE),
            f"{BIGMEM_EGRESS}/{RAW}": by_family(records, leg=BIGMEM_EGRESS, basis=RAW),
            f"{BIGMEM_INGRESS}/{RAW}": by_family(records, leg=BIGMEM_INGRESS, basis=RAW),
            f"{BIGMEM_INGRESS}/{WIRE}": by_family(records, leg=BIGMEM_INGRESS, basis=WIRE),
        },
        "projections": {key: project(total, coverage) for key, total in legs.items()},
        "crossCheck": cross_check(records),
        "allowances": allowances,
        "homeWindow": home.at(now) if home else None,
        "vpsWindow": vps.at(now) if vps else None,
        "rebuildCost": rebuild_cost(everything, now),
        "visit": read_visit(),
        "ledgerPath": str(path),
        "ledgerRecords": len(everything),
    }


#: One cold visit's cost, written by tools/measure-visit-payload.mjs. Kept out
#: of the ledger because it is not traffic that happened -- it is a measurement
#: of what one visit WOULD cost, taken deliberately by driving a browser at the
#: live site, and mixing it into a period total would count a synthetic visit
#: as real traffic.
VISIT_PATH = STATE_DIR / "visit-payload.json"


def read_visit(path: Path = VISIT_PATH) -> dict | None:
    """The last measured per-visit payload, or None if nobody has measured one."""
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(blob, dict) or not isinstance(blob.get("wireBytes"), (int, float)):
        return None
    return blob


def visits_supported(window: AllowanceWindow | None, visit: dict | None) -> float | None:
    """How many cold visits an egress allowance covers. None if either is unknown."""
    if visit is None or window is None or window.unlimited or not window.bytes:
        return None
    wire = float(visit["wireBytes"])
    if wire <= 0:
        return None
    return window.bytes / wire


# ---------------------------------------------------------------------------
# CLI. Used by pipeline/publish_vps.sh and by hand.
# ---------------------------------------------------------------------------

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measured bandwidth ledger.")
    sub = parser.add_subparsers(dest="command", required=True)

    push = sub.add_parser("rsync-push", help="record a bigmem -> VPS rsync from its output")
    push.add_argument("--run", required=True)
    push.add_argument("--file", type=Path, default=None,
                      help="rsync output to read (default: stdin)")
    push.add_argument("--force-family", default=None, choices=sorted(FAMILIES),
                      help="for transfers whose filenames carry no family prefix")

    size = sub.add_parser("file-size", help="record a transfer measured only by file size")
    size.add_argument("--path", type=Path, required=True)
    size.add_argument("--leg", required=True, choices=sorted(LEGS))
    size.add_argument("--family", required=True, choices=sorted(FAMILIES))
    size.add_argument("--run", required=True)
    size.add_argument("--source", required=True)

    pull = sub.add_parser("rsync-pull", help="record a VPS -> bigmem rsync from its output")
    pull.add_argument("--run", required=True)
    pull.add_argument("--family", default="celestrak-mirror-pull")
    pull.add_argument("--file", type=Path, default=None)

    fetch = sub.add_parser("fetch", help="record one upstream download")
    fetch.add_argument("--bytes", type=int, required=True)
    fetch.add_argument("--family", required=True, choices=sorted(UPSTREAM_FAMILIES))
    fetch.add_argument("--source", required=True)
    fetch.add_argument("--run", required=True)

    sub.add_parser("trim", help="bound the ledger")

    show = sub.add_parser("show", help="print the month-to-date summary as JSON")
    show.add_argument("--ledger", type=Path, default=LEDGER)

    args = parser.parse_args(argv)

    if args.command in {"rsync-push", "rsync-pull"}:
        text = args.file.read_text(encoding="utf-8") if args.file else sys.stdin.read()
        if args.command == "rsync-push":
            result = record_rsync_push(text, run=args.run, force_family=args.force_family)
        else:
            result = record_rsync_pull(text, run=args.run, family=args.family)
        detail = result.get("reason", "")
        print(f"bandwidth: {result['recorded']} record(s) from {args.run}"
              + (f" ({detail})" if detail else ""))
        trim()
        return 0

    if args.command == "file-size":
        # For a leg whose transport does not report what it moved -- scp, for
        # one. The file's length is a real measurement, but it is the RAW
        # length, so it is recorded on the raw basis and can never be summed
        # into a wire total by accident.
        try:
            count = args.path.stat().st_size
        except OSError as error:
            print(f"bandwidth: {args.path} could not be measured ({error}); "
                  "nothing recorded")
            return 0
        record(leg=args.leg, family=args.family, byte_count=count, basis=RAW,
               source=args.source, run=args.run)
        print(f"bandwidth: {count:,} raw bytes recorded for {args.family}")
        return 0

    if args.command == "fetch":
        record_fetch(args.bytes, family=args.family, source=args.source, run=args.run)
        return 0

    if args.command == "trim":
        print(f"bandwidth: dropped {trim()} ledger line(s)")
        return 0

    if args.command == "show":
        state = summarise(_now(), path=args.ledger)
        print(json.dumps({
            "periodStart": state["periodStart"],
            "periodEnd": state["periodEnd"],
            "ledgerRecords": state["ledgerRecords"],
            "legs": {key: {"bytes": total.bytes, "records": total.records,
                           "sources": list(total.sources)}
                     for key, total in state["legs"].items()},
            "families": {key: [[name, count, hits] for name, count, hits in rows]
                         for key, rows in state["families"].items()},
            "crossCheck": state["crossCheck"].sentence(),
        }, indent=2))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
