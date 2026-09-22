#!/usr/bin/env python3
"""Turn the orbit archive into the three artifacts the browser fetches.

Three, split by how they are used rather than by what they contain, because
that is what keeps the page load small (`docs/orbit-history-design.md` Section
4.5):

| manifest key   | prefix              | content                                    |
|----------------|---------------------|--------------------------------------------|
| `orbitHistory` | `orbit-history-NNN` | 256 shards of per-object series, `norad % 256` |
| `orbitEvents`  | `orbit-events`      | the cross-catalogue headline list, the controls and the per-object rows |
| `orbitDrag`    | `orbit-drag`        | population shells, density ratios, Kp, controls |

The split matters. A year of every catalogued object's daily elements is tens of
megabytes; sharding by `norad % 256` means opening one satellite's history costs
about a hundred kilobytes rather than the whole archive.

**Events live in the shards too, and that is a correction.** This module was
written when the archive was hours old and events were rare enough that the
whole catalogue's list was one small file. A year of archive produces tens of
thousands, each carrying a full evidence card, which is tens of megabytes on the
front page. So the full record for an object's changes travels in that object's
shard -- which the detail view is already fetching to draw the plot, so the
evidence costs no extra request -- and the events bundle carries the bounded
headline list the population views rank on, plus the controls and the per-object
summary rows.

The detector sweep and release tail both checkpoint across runs. History
series are read by indexed NORAD queries, one shard at a time; completing a
shard commits its artifact paths and digests before checking the run budget.

Nothing here makes a network request.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import json
import multiprocessing
import os
import signal
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
import pickle
import resource
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Sequence

from pipeline.orbit_campaigns import repeat_clusters
from pipeline.orbit_events import (
    GroundTruth,
    Interval,
    SCHEMA_VERSION,
    archive_maturity,
    control_rates,
    detect_events,
    kp_context,
    load_catalog,
    load_intervals,
    observation_span_days,
    score_against_ground_truth,
    separation_verdict,
    space_weather_gaps,
    sun_synchronous,
    summarise_objects,
    _parse_iso_ms,
)
from pipeline.orbit_history import (
    RE_WGS72,
    archive_stats,
    busiest_norad,
    density_enhancement,
    epoch_ms_to_datetime,
    kp_series,
    open_archive,
    population_decay,
    semi_major_axis_km,
)
from pipeline.orbit_narrative import describe, event_key, validate_candidate
from pipeline import orbit_campaigns
from pipeline.orbit_tail import TailCheckpoint, TailEvents, TailPaused

ROOT = Path(__file__).resolve().parents[1]
NARRATIVE_CACHE = ROOT / "pipeline" / ".cache" / "qwen-orbit-narratives.json"

HISTORY_SHARDS = 256

# The archive holds every catalogued object; the browser shows the curated
# teaching catalog. Shipping history for all 31,697 would quadruple the payload
# to serve objects the interface has no card for. Objects that produced an event
# are always included even if the catalog omits them, because an event with no
# plot behind it is worse than no event.
INCLUDE_ALL_WITH_EVENTS = True

# The plot grid. A year of archive at the catalogue's own publication rate is
# five hundred to a thousand element sets per object; a strip chart a few
# hundred pixels wide can resolve nothing like that many, and shipping them all
# cost 9.3 GB in the pipeline and tens of megabytes on the wire. Twelve hours
# gives roughly seven hundred points a year, which is still more than the plot
# can draw and cheap enough to ship.
SERIES_GRID_HOURS = 12.0

# Samples this close to a detected event escape the grid entirely. A three
# kilometre step that happened between two grid points would otherwise be drawn
# as a ramp across half a day, which is a picture of the sampling rather than a
# picture of the burn.
EVENT_DETAIL_HOURS = 36.0

# How much of the archive the cohort detector looks at. It exists to judge an
# object against its *neighbours at the same moment*, which needs many objects
# over a few days rather than one object over a year, so a short window loses it
# nothing -- and a long one costs a Python object per consecutive pair in the
# whole archive, which is precisely the 9.3 GB mistake. Longitudinal work is
# `pipeline/orbit_campaigns.py`, which streams.
COHORT_WINDOW_DAYS = 7.0
# Bounded deliberately. Restoring the real seven-day window made the cohort
# exact but left its single-process walk too close to the release tail's
# deadline. Two fork workers share the read-mostly interval index and preserve
# output order; using every core would compete with ingestion and the site.
COHORT_DETECT_WORKERS = 2

# These are two different instruments with two different passive controls.
# The cohort operating point was measured at eight and must not move when the
# archive-wide self-history lane is calibrated. The latter's complete control
# was rerun at 32 after the lower values failed or left too little margin.
COHORT_KAPPA = 8.0
DEFAULT_SELF_HISTORY_KAPPA = 32.0

# The window the population decay shells and the storm density ratio are
# measured over. Thirty days: long enough to hold a quiet spell and a disturbed
# one, short enough that the thermosphere it averages is one thermosphere.
POPULATION_WINDOW_DAYS = 30.0

# How many events the cross-catalogue headline list carries. A year of archive
# produces tens of thousands, each with a full evidence card; shipped as one
# artifact that is tens of megabytes on the front page. Per-object records live
# in the object's own history shard, which the detail view fetches anyway, so
# this cap hides nothing -- it only decides what the POPULATION views can rank
# without a second request.
MAX_HEADLINE_EVENTS = 1500


def iso(epoch_ms: int) -> str:
    return epoch_ms_to_datetime(epoch_ms).isoformat(timespec="seconds").replace("+00:00", "Z")


def observed_archive_end_ms(stats: dict[str, Any], *, now_ms: int | None = None) -> int:
    """Newest observed time, without mistaking a fitted epoch for capture time."""
    latest_ms = _parse_iso_ms(stats.get("latestEpoch")) or 0
    captured_ms = _parse_iso_ms(stats.get("lastCapture"))
    if captured_ms is not None:
        return captured_ms
    if now_ms is None:
        now_ms = int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
    return min(latest_ms, now_ms) if latest_ms else now_ms


def cohort_window_bounds(
    stats: dict[str, Any], *, now_ms: int | None = None
) -> tuple[int, int]:
    """The recent, observed-time window used by the cohort detector.

    Element epochs are not an observation clock. Space-Track occasionally
    publishes fitted epochs several days ahead of the capture that delivered
    them; anchoring on ``latestEpoch`` therefore collapsed a nominal seven-day
    control to a few hours. The capture ledger records when the source was
    actually observed and is the right end of a same-time population window.

    Archives without a capture ledger are supported for tests and imported
    fixtures. There the newest element epoch is capped at wall-clock time so a
    forward-dated fit still cannot move the window into the future.
    """
    end_ms = observed_archive_end_ms(stats, now_ms=now_ms)
    start_ms = end_ms - int(COHORT_WINDOW_DAYS * 86_400_000)
    return start_ms, end_ms


# ---------------------------------------------------------------------------
# Per-object series
# ---------------------------------------------------------------------------
def read_series(
    connection: sqlite3.Connection,
    wanted: set[int],
    events_at: dict[int, Sequence[int]] | None = None,
) -> dict[int, list[dict[str, Any]]]:
    """Every element set for the wanted objects, in one ordered scan per tier.

    Reads the daily tier first (settled days, kept forever) and then the hot
    tier (recent days at full cadence), merging on epoch. Both are needed and
    neither alone is right: the daily tier is empty for the days that have not
    settled yet, which on a young archive is *all* of them, and the hot tier is
    pruned after the retention window.

    Duplicate epochs across the two tiers deduplicate on `epoch_ms`, because the
    daily tier's rows are literally copies of hot-tier rows.
    **Decimated as it is read, never after.** The first version of this
    function absorbed every element set for every wanted object into a
    dictionary of dictionaries and sorted at the end. On the archive it was
    written against — a few thousand element sets — that was free. After the
    2004-2025 backfill it was one of the two structures that put the publish
    step at 9.3 GB resident, alongside `load_intervals`.

    Two bounds now apply, and both are applied *while streaming*, so the peak
    is one object's worth of samples rather than the catalogue's:

    * **A uniform time grid.** One sample per `SERIES_GRID_HOURS`, which over a
      year of archive is a couple of hundred points — more than a plot a few
      hundred pixels wide can resolve, and enough that the eye sees the shape.
    * **Event neighbourhoods survive it.** A step of three kilometres that
      happens between two grid points would otherwise be drawn as a ramp across
      three days. Samples within `EVENT_DETAIL_HOURS` of a detected event are
      kept at full cadence, so the one part of the curve a visitor came to look
      at is the one part that is not decimated.

    `events_at` therefore has to be known before the series is read, which is
    why `build_bundles` detects first and reads second.
    """
    grid_ms = int(SERIES_GRID_HOURS * 3_600_000)
    detail_ms = int(EVENT_DETAIL_HOURS * 3_600_000)
    events_at = events_at or {}
    out: dict[int, list[dict[str, Any]]] = {}

    def sample(epoch_ms: int, mm: float, ecc: float, inc: float,
               bstar: float | None, tier: str) -> dict[str, Any]:
        a = semi_major_axis_km(mm)
        return {
            "t": epoch_ms,
            "perigeeKm": round(a * (1.0 - ecc) - RE_WGS72, 3),
            "apogeeKm": round(a * (1.0 + ecc) - RE_WGS72, 3),
            "semiMajorAxisKm": round(a, 4),
            "inclinationDeg": round(inc, 4),
            "eccentricity": round(ecc, 8),
            "bstar": bstar,
            "tier": tier,
        }

    def flush(norad: int, rows: list[tuple[int, float, float, float, float | None, str]]) -> None:
        if not rows:
            return
        marks = events_at.get(norad, ())
        # Merge with whatever an earlier tier's sweep already kept, so the two
        # tiers combine rather than the second replacing the first.
        merged = {entry["t"]: entry for entry in out.get(norad, ())}
        for epoch_ms, mm, ecc, inc, bstar, tier in rows:
            merged.setdefault(epoch_ms, sample(epoch_ms, mm, ecc, inc, bstar, tier))
        # **The grid is anchored to absolute time, not to the previous sample
        # kept.** A running "has it been twelve hours since the last one I
        # kept" test makes the whole retained series depend on where the walk
        # started, so one element set arriving an hour early reshuffles every
        # sample after it — the artifact's content changes when the data has
        # not, all 256 shards get new content-addressed filenames every publish
        # cycle, and 72 MB an hour is written and shipped for nothing. That is
        # the self-invalidating cache key `docs/OPEN-WORK.md` lists as one of
        # this codebase's four defect classes.
        #
        # Bucketed on `epoch // grid`, the first sample in each bucket is
        # selected no matter what arrives later, so a shard changes only when it
        # genuinely gains or loses a point.
        kept: list[dict[str, Any]] = []
        claimed: set[int] = set()
        for epoch_ms in sorted(merged):
            if any(abs(epoch_ms - mark) <= detail_ms for mark in marks):
                kept.append(merged[epoch_ms])
                continue
            bucket = epoch_ms // grid_ms
            if bucket in claimed:
                continue
            claimed.add(bucket)
            kept.append(merged[epoch_ms])
        # An event neighbourhood can put a sample in a bucket a grid pick also
        # claimed; dedupe on epoch so the series never carries one twice.
        seen: set[int] = set()
        kept = [s for s in kept if not (s["t"] in seen or seen.add(s["t"]))]
        kept.sort(key=lambda entry: entry["t"])
        if kept:
            out[norad] = kept

    # ONE QUERY PER WANTED OBJECT, NOT ONE SWEEP PER TIER -- BECAUSE THE
    # MEASUREMENT THAT CHOSE THE SWEEP EXPIRED
    # -----------------------------------------------------------------------
    # This was `SELECT ... FROM <table> ORDER BY norad, epoch_ms`, with the
    # unwanted objects dropped in Python, and the comment here justified it with
    # a measurement taken on 2026-08-08: a full ordered sweep of the daily tier
    # cost 0.030 s while four thousand per-object queries cost 6.18 s. On that
    # archive the sweep really was cheaper, by two orders of magnitude.
    #
    # That archive held 55.2 M rows and fitted in the page cache. The 2004-2025
    # back-fill has since taken `element_set` to 181.3 M rows and 13.75 GB,
    # which does not fit, and `/mnt/d` is WSL drvfs 9p with `msize=65536`:
    # SQLite reads 4 KiB pages and each one is a 9p round trip. Re-measured cold
    # against the live archive on 2026-08-18:
    #
    #     ordered sweep of element_set      7,557 rows/s -> 6 h 40 m for 181.3 M
    #     rows belonging to `wanted`        16.6 M rows  -> 9.17 % of the table
    #
    # The sweep now reads about eleven rows for every one it keeps, at the
    # slowest access pattern this storage has. The catalogue is 8,000 objects
    # and the table is `WITHOUT ROWID` on `(norad, epoch_ms)`, so `WHERE
    # norad = ?` is one descent of the primary-key b-tree followed by a
    # sequential walk of exactly that object's rows: the same physical reads the
    # sweep was making, minus the 90.8 % of it that was thrown away.
    #
    # It also ends a defect that is not about speed. The sweep was a SINGLE
    # unpaged statement, so it held a SHARED lock on the archive for its whole
    # duration -- hours -- and in rollback-journal mode a SHARED lock is exactly
    # what stops the hourly capture reaching EXCLUSIVE. That is the starvation
    # `orbit_history.paged_element_sets` was written to fix in the OTHER pass of
    # this same build, on 2026-08-08; this pass never got the fix. One statement
    # per object holds the lock for one object.
    #
    # The per-object results are identical to the sweep's, and the tier
    # precedence is preserved: `full` is read before `daily` for each object,
    # and `flush` merges with `setdefault`, so a `daily` row never displaces the
    # `full` row for the same epoch.
    for norad in sorted(wanted):
        for tier, table in (("full", "element_set"), ("daily", "element_set_daily")):
            rows: list[tuple[int, float, float, float, float | None, str]] = []
            for epoch_ms, mm_q, ecc_q, inc_q, bstar_q in connection.execute(
                f"SELECT epoch_ms, mean_motion_q, eccentricity_q, inclination_q, bstar_q "
                f"FROM {table} WHERE norad = ? ORDER BY epoch_ms",
                (norad,),
            ):
                if mm_q <= 0:
                    continue
                rows.append(
                    (
                        epoch_ms,
                        mm_q / 1e8,
                        ecc_q / 1e8,
                        inc_q / 1e4,
                        None if bstar_q is None else bstar_q / 1e12,
                        tier,
                    )
                )
            flush(norad, rows)
    return {norad: samples for norad, samples in out.items()}


# ---------------------------------------------------------------------------
# Coverage honesty
# ---------------------------------------------------------------------------
ARCHIVE_BEGINS_MS = None  # resolved from the capture ledger, never hard-coded


def _epoch_gaps(
    connection: sqlite3.Connection, *, minimum_days: float
) -> list[tuple[int, int]]:
    """Stretches the archive holds nothing in, found from the data itself.

    Asked of one busy object rather than of the whole table, and that choice is
    the interesting part. A gap "in the archive" cannot be found by looking for
    days with no rows at all: the catalogue contains dead objects whose last
    element set is from the 1970s, so *somebody* has an epoch almost everywhere
    and the whole-table view shows no gap where there plainly is one. The ISS is
    fitted several times a day whenever it is being tracked at all, so a month
    with no ISS element set is a month the archive does not hold.

    The busy object is found from `object_rollup`, which is one row per object,
    rather than by grouping every element set in the archive by `norad`. Those
    two return the same catalogue number; one of them reads 40,000 rows and the
    other read 55 million.
    """
    reference = busiest_norad(connection)
    if reference is None:
        return []
    # One object's history is physically contiguous -- `element_set` is
    # clustered on (norad, epoch_ms) -- so this is a single range read of the
    # primary-key b-tree, not a scan.
    epochs = [
        row[0]
        for row in connection.execute(
            "SELECT epoch_ms FROM element_set WHERE norad = ? ORDER BY epoch_ms", (reference,)
        )
    ]
    threshold = minimum_days * 86_400_000
    return [
        (earlier, later)
        for earlier, later in zip(epochs, epochs[1:])
        if later - earlier > threshold
    ]



# What a headline row needs to be ranked, searched and clicked -- and nothing
# more. The full record, with its evidence card, channel tests, drag prediction
# and narrative, is in the object's shard, which the detail view fetches the
# moment somebody clicks. Shipping the full record here as well put 1.48 MB
# gzipped in front of every visitor before the globe had drawn.
_HEADLINE_FIELDS = (
    "norad", "name", "objectType", "startAt", "endAt", "spanDays",
    "signature", "signatureLabel", "confidence", "regime",
    "perigeeAltitudeKm", "apogeeAltitudeKm", "inclinationDeg",
    "sunSynchronous", "constellation", "eventKey", "purposeLanguagePermitted",
    "controlBasis", "controlStratum", "manoeuvreLabelPermitted",
)


def _slim(record: dict[str, Any]) -> dict[str, Any]:
    """A headline row: enough to rank and to click, never the whole evidence."""
    out = {field: record[field] for field in _HEADLINE_FIELDS if field in record}
    out["deltaVMetresPerSecond"] = record["deltaV"]["totalMetresPerSecond"]
    # Two things survive the diet because a row is misleading without them: the
    # verdict against the object's class, which is what "unusual" means on this
    # page, and whether an operator independently published this change, which
    # is the only claim here that rests on somebody else's evidence.
    out["expectationVerdict"] = (record.get("expectation") or {}).get("verdict")
    out["groundTruth"] = record.get("groundTruth")
    return out


def select_headline_events(
    records: Sequence[dict[str, Any]], cap: int = MAX_HEADLINE_EVENTS
) -> list[dict[str, Any]]:
    """The bounded cross-catalogue list the population views rank on.

    A year of archive produces tens of thousands of events, each carrying a full
    evidence card. Shipped as one artifact that is tens of megabytes on the front
    page, which would make this feature slower than the globe it hangs off. The
    per-object records travel in the object's own history shard instead, so this
    cap hides nothing -- it decides only what can be ranked without a second
    request.

    **The selection is deliberately not "the biggest N".** Taken naively that
    returns several hundred Starlinks and hides every other object in the
    catalogue, which is the opposite of what a population view is for. So:

    1. the largest change on *every* object that had one, so no object that did
       anything is invisible;
    2. every change an operator independently published, whatever its size --
       it is the one thing on the page that can be checked against somebody
       else, and dropping a small one for being small would drop the evidence
       that the detector works;
    3. the remainder by size, until the cap.
    """
    best_per_object: dict[int, dict[str, Any]] = {}
    for record in records:
        norad = record["norad"]
        cost = record["deltaV"]["totalMetresPerSecond"] or 0.0
        best = best_per_object.get(norad)
        if best is None or cost > (best["deltaV"]["totalMetresPerSecond"] or 0.0):
            best_per_object[norad] = record

    headline: list[dict[str, Any]] = []
    chosen: set[int] = set()

    def take(record: dict[str, Any]) -> None:
        if id(record) not in chosen:
            headline.append(record)
            chosen.add(id(record))

    for record in sorted(
        best_per_object.values(), key=lambda r: -(r["deltaV"]["totalMetresPerSecond"] or 0.0)
    ):
        take(record)
    for record in records:
        if record.get("groundTruth"):
            take(record)
    for record in sorted(records, key=lambda r: -(r["deltaV"]["totalMetresPerSecond"] or 0.0)):
        if len(headline) >= cap:
            break
        take(record)
    headline.sort(key=lambda r: -(r["deltaV"]["totalMetresPerSecond"] or 0.0))
    return headline[:cap]


def _control_basis(record: dict[str, Any]) -> str:
    return next(
        (test.get("basis") for test in record.get("tests", []) if test.get("tripped")),
        "cohort",
    )


def _self_history_separation(self_controls: dict[str, Any]) -> dict[str, Any]:
    """The effect-size half of the label gate, applied to the self-history lane.

    `orbit_campaigns.control_rates_by_object` publishes both Jeffreys intervals
    but decides `sufficientToLabel` from the passive upper bound and a p-value.
    At 89 million control intervals a p-value is not a separation -- the pooled
    z is 459, and the same test passes at a rate ratio of 1.001 -- so the
    requirement that the payload rate stand clear of the false-alarm floor is
    applied here, where the self-history control is reshaped into the
    vocabulary the card and the gate actually read.

    The predicate itself is `orbit_events.separation_verdict`, shared with the
    cohort lane, so "separated" means one thing on this site rather than one
    thing per detector.
    """
    passive = (self_controls.get("passive") or {}).get("jeffreys95") or [None, None]
    payload = (self_controls.get("payload") or {}).get("jeffreys95") or [None, None]
    return separation_verdict(
        passive[1] if len(passive) > 1 else None,
        payload[0] if payload else None,
    )


def _controls_for(
    record: dict[str, Any],
    cohort_controls: dict[str, Any],
    self_controls: dict[str, Any],
    *, matched_stratum: dict[str, str] | str | None = None,
) -> dict[str, Any]:
    """The control measurement that judged this event, in the card's vocabulary.

    Two detectors run, they have separately measured false-alarm rates, and a
    card must quote its own. The self-history control is reshaped into the key
    names `orbit_narrative` already reads rather than teaching the narrative
    module about a second shape: the card's wording is under a lot of scrutiny
    and the fewer branches in it the better.
    """
    basis = _control_basis(record)
    if basis != "self-history":
        return cohort_controls
    stratum: dict[str, str] | str | None = None
    if orbit_campaigns.MATCHED_CONTROL_STRATA_ENABLED:
        stratum = matched_stratum if matched_stratum is not None else orbit_campaigns.control_stratum(
            _parse_iso_ms(record.get("startAt")), record.get("perigeeAltitudeKm"))
        if isinstance(stratum, dict):
            self_controls = (self_controls.get("strata") or {}).get(stratum["era"], {}).get(
                stratum["band"], {})
        else:
            self_controls = {}
        if not self_controls:
            self_controls = {"sufficientToLabel": False, "blockingReason":
                             "not calibrated: matched stratum has not been measured"}
    passive = self_controls.get("passive") or {}
    payload = self_controls.get("payload") or {}
    separation = self_controls.get("separation") or {}
    p_value = separation.get("approximatePValue")
    z_value = separation.get("z")
    # Both halves of the gate, not one: the bound on the false-alarm rate that
    # the campaign scan measured, AND the effect size between the two rates.
    separated = _self_history_separation(self_controls)
    sufficient = bool(self_controls.get("sufficientToLabel")) and separated["meets"]
    blocking = self_controls.get("blockingReason") or (
        None if sufficient else separated["gap"]
    )
    return {
        "controlStratum": stratum or "not enabled: matched-control flag is disabled",
        "kappa": self_controls.get("kappa"),
        "passiveControl": {
            "flags": passive.get("flags"),
            "intervals": passive.get("intervals"),
            "rate": passive.get("ratePerInterval"),
            "interval95": passive.get("jeffreys95"),
        },
        "payloadPopulation": {
            "flags": payload.get("flags"),
            "intervals": payload.get("intervals"),
            "rate": payload.get("ratePerInterval"),
            "interval95": payload.get("jeffreys95"),
        },
        "excessSignificance": separation,
        "excessRate": separation.get("ratio"),
        "sufficientToLabel": sufficient,
        "excessSignificant": (
            z_value is not None
            and z_value > 0
            and p_value is not None
            and p_value < 0.01
        ),
        "rateSeparation": separated,
        "designTarget": self_controls.get("targetRatePerInterval"),
        "note": self_controls.get("note"),
        "blockingReason": blocking,
    }


def _event_label_permitted(
    record: dict[str, Any], event_controls: dict[str, Any]
) -> bool:
    """Only a payload may inherit a detector's earned manoeuvre vocabulary."""
    return (
        record.get("objectType") == "PAYLOAD"
        and record.get("signature") != "thrust-excess"
        and bool(event_controls.get("sufficientToLabel"))
    )


def _label_policy(
    cohort_controls: dict[str, Any], self_controls: dict[str, Any]
) -> dict[str, Any]:
    """Conservative bundle compatibility plus permission for each detector."""
    cohort_permitted = bool(cohort_controls.get("sufficientToLabel"))
    # The cohort lane carries the separation requirement inside
    # `orbit_events.control_rates`; the self-history lane's controls come from
    # the campaign scan, so the same requirement is applied to them here.
    self_separated = _self_history_separation(self_controls)
    self_permitted = bool(self_controls.get("sufficientToLabel")) and self_separated["meets"]
    by_stratum = {}
    if orbit_campaigns.MATCHED_CONTROL_STRATA_ENABLED:
        for era in orbit_campaigns.CONTROL_ERAS:
            by_stratum[era] = {}
            for band in orbit_campaigns.CONTROL_BANDS:
                measured = (self_controls.get("strata") or {}).get(era, {}).get(band, {})
                permitted = (bool(measured.get("sufficientToLabel"))
                             and _self_history_separation(measured)["meets"])
                by_stratum[era][band] = {
                    "manoeuvreLabelPermitted": permitted,
                    "gap": None if permitted else measured.get("blockingReason") or
                           "not calibrated: stratum has not been measured",
                }
        self_permitted = all(item["manoeuvreLabelPermitted"]
                             for bands in by_stratum.values() for item in bands.values())
    any_permitted = cohort_permitted or self_permitted or any(
        item["manoeuvreLabelPermitted"] for bands in by_stratum.values() for item in bands.values())
    # This compatibility bit can only describe the WHOLE bundle. Keep it shut
    # unless both instruments pass; new records carry their own permission.
    # An older consumer that knows only this bit must fail conservatively rather
    # than borrow the self-history control for a cohort-only event.
    all_permitted = cohort_permitted and self_permitted
    if cohort_permitted != self_permitted:
        calibrated = "self-history" if self_permitted else "cohort"
        uncalibrated = "cohort" if self_permitted else "self-history"
        uncalibrated_reason = (
            cohort_controls.get("blockingReason")
            if self_permitted
            else (self_controls.get("blockingReason") or self_separated["gap"])
        )
        reason = (
            f"The {calibrated} detector is calibrated. Events judged only by the "
            f"{uncalibrated} detector remain candidates: {uncalibrated_reason}"
        )
    elif all_permitted:
        reason = None
    else:
        reason = (
            self_controls.get("blockingReason")
            or self_separated["gap"]
            or cohort_controls.get("blockingReason")
        )
    if by_stratum and not all_permitted:
        reason = ("Calibration is specific to each event's era and perigee band. "
                  "Uncalibrated strata remain candidates; each card quotes the control that judged it.")
        if not cohort_permitted:
            reason += " Cohort-only events remain candidates."
    return {
        # The top-level compatibility bit means every lane earned the word.
        # Each event carries its own permission, because the controls measure
        # different instruments and are not interchangeable.
        "manoeuvreLabelPermitted": all_permitted,
        "byBasis": {
            "cohort": cohort_permitted,
            "selfHistory": self_permitted,
            **({"byStratum": by_stratum} if by_stratum else {}),
        },
        "reason": reason,
        "wording": (
            "An event is called a manoeuvre only when the passive control for the detector "
            "that judged it bounds false alarms below the design target. Its cost remains a "
            "lower bound and its cause remains an inference."
            if any_permitted
            else "Until the false-alarm rate is bounded below the design target, no event is "
                 "called a manoeuvre. The measurement, the cost, the control and the "
                 "alternatives all ship; the word does not."
        ),
    }


def coverage(connection: sqlite3.Connection) -> dict[str, Any]:
    """When the archive can and cannot speak, in the vocabulary the site uses.

    Reuses the environment layers' idea exactly: a `noDataIntervals` list with a
    machine-readable reason, so the interface renders a deliberate gap rather
    than a line drawn through nothing. `before-bigmem-accumulation` for
    everything before the first capture; `snapshot-gap` for a capture that did
    not happen when it should have.

    **Never interpolate across a gap**, and never let a line segment imply data
    between two points three days apart. The consumer is given the points and
    the gaps; drawing is its problem, and it has what it needs to draw honestly.
    """
    captures = [
        row[0] for row in connection.execute("SELECT captured_ms FROM capture ORDER BY captured_ms")
    ]
    stats = archive_stats(connection)
    gaps: list[dict[str, Any]] = []
    if captures:
        # The boundary is the earliest EPOCH held, not the first capture. One
        # snapshot of the catalogue already contains element sets several days
        # old, so the archive genuinely knows about orbits before it started
        # running. Drawing the no-data boundary at the first capture would mark
        # real, held data as missing -- and it did: the largest event in the
        # first run spanned two days that this function called empty.
        earliest_epoch_ms = _parse_iso_ms(stats["earliestEpoch"])
        boundary = min(captures[0], earliest_epoch_ms) if earliest_epoch_ms else captures[0]
        gaps.append(
            {
                "from": "1957-10-04T00:00:00Z",
                "to": iso(boundary),
                "reason": "before-bigmem-accumulation",
                "note": (
                    "Nothing before this point is held. What the archive does hold is whatever "
                    "the hourly capture has seen since it started, plus whatever the bulk "
                    "back-fill has imported from space-track's published yearly bundles."
                ),
            }
        )
        # The hole between the end of the bulk bundles and the start of live
        # capture. It needs its own reason code, and the browser needs to know
        # it is a different KIND of absence from "before the archive existed":
        # the archive holds data on both sides of it, so a line drawn across it
        # would look continuous and would be an invention. The gap is found from
        # the element sets themselves rather than hard-coded to a date, because
        # the back-fill imports year by year and the hole shrinks as it goes.
        for earlier, later in _epoch_gaps(connection, minimum_days=30.0):
            gaps.append(
                {
                    "from": iso(earlier),
                    "to": iso(later),
                    "reason": "between-backfill-and-live-capture",
                    "note": (
                        "The archive holds element sets on both sides of this gap and none inside "
                        "it: the bulk bundles end before live capture began. Nothing is "
                        "interpolated across it, no cadence is measured across it, and an "
                        "operator-published manoeuvre inside it is recorded as unscorable rather "
                        "than as one the detector missed."
                    ),
                }
            )
        # The ingest cadence is hourly; anything over two hours is a missed one.
        for earlier, later in zip(captures, captures[1:]):
            if later - earlier > 2 * 3_600_000:
                gaps.append(
                    {
                        "from": iso(earlier),
                        "to": iso(later),
                        "reason": "snapshot-gap",
                        "note": "No capture ran in this window, so any element set published inside it was missed.",
                    }
                )
    return {
        "capturedFrom": iso(captures[0]) if captures else None,
        "capturedTo": iso(captures[-1]) if captures else None,
        "captureCount": len(captures),
        "earliestEpoch": stats["earliestEpoch"],
        "latestEpoch": stats["latestEpoch"],
        "noDataIntervals": gaps,
        "interpolationPolicy": "never-across-a-gap",
        "framing": (
            "These are fitted mean elements published every few hours, not measurements of where "
            "a satellite is. What this archive can show you is how the fit moved."
        ),
    }


# ---------------------------------------------------------------------------
# The three bundles
# ---------------------------------------------------------------------------
def _uncached_step(name, compute):
    return compute()


def _generation_time():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def build_bundles(
    connection: sqlite3.Connection,
    data_root: Path,
    *,
    self_history_kappa: float = DEFAULT_SELF_HISTORY_KAPPA,
    narratives: dict[str, Any] | None = None,
    on_shard: Callable[[dict[str, Any]], Any] | None = None,
    scan: orbit_campaigns.ArchivePass | None = None,
    step: Callable = _uncached_step,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """Build the same bundles with or without durable stage checkpoints."""
    prepared = step("prepared", lambda: _prepare_tail(
        connection, data_root, self_history_kappa, narratives, scan, step))
    events_bundle, stats, wanted, events_at, events_by_object, clusters_by_object = prepared
    shards = []

    def build_shard(index):
        shard = _history_shard(connection, index, wanted, events_at,
                               events_by_object, clusters_by_object)
        if shard is not None:
            if on_shard is None:
                shards.append(shard)
            else:
                return on_shard(shard)
        return None  # Empty shards are completed work too.

    for index in range(HISTORY_SHARDS):
        step(f"shard:{index:03d}", lambda: build_shard(index))
    drag_bundle = step("drag", lambda: _build_drag(connection, stats, events_bundle, step))
    return shards, events_bundle, drag_bundle


def _prepare_tail(connection, data_root, self_history_kappa, narratives, scan, step):
    generated_at = step("generated-at", _generation_time)
    catalog = step("catalog", lambda: load_catalog(data_root))
    stats = step("stats", lambda: archive_stats(connection))

    # --- the two detectors, and why neither alone is enough ----------------
    # `orbit_campaigns` streams the whole archive one object at a time and
    # judges each object against its own history. That is the detector the
    # cadence questions need -- a cadence is a property of one object -- and it is the
    # only one that can be run over twenty-two years without materialising
    # them.
    # `scan` is injected by `build_cache`, which now runs the pass itself so it
    # can bound it on a wall-clock budget and resume it across runs. When it is
    # not injected -- `--dry-run`, and the tests -- the whole pass runs here, as
    # it always did.
    if scan is None:
        scan = orbit_campaigns.scan_archive(
            connection,
            kappa=self_history_kappa,
            catalog=catalog,
            keep_summaries_for=set(catalog),
        )
    # The cohort detector still runs, over a short recent window, because it
    # answers a question self-history cannot: an object with no history at all
    # -- a new launch, or anything the archive has only just met -- has no
    # baseline to depart from, and its neighbours at the same altitude are the
    # only control available on its first day.
    window_start_ms, window_end_ms = step("window", lambda: cohort_window_bounds(
        stats, now_ms=_parse_iso_ms(generated_at)))
    recent = step("recent", lambda: load_intervals(
        connection, since_ms=window_start_ms, until_ms=window_end_ms
    ))
    cohort_events = step("cohort-events", lambda: detect_events(
        recent, kappa=COHORT_KAPPA, catalog=catalog, workers=COHORT_DETECT_WORKERS,
        checkpoint=None if step is _uncached_step else step,
    ))
    controls = step("cohort-controls", lambda: control_rates(recent, cohort_events, kappa=COHORT_KAPPA))
    self_controls = step("self-controls", lambda: orbit_campaigns.control_rates_by_object(
        scan, kappa=self_history_kappa
    ))
    controls["selfHistory"] = self_controls
    controls["cohortWindowDays"] = COHORT_WINDOW_DAYS
    controls["cohortWindowFrom"] = iso(window_start_ms)
    controls["cohortWindowTo"] = iso(window_end_ms)
    controls["cohortWindowAnchor"] = (
        "capture-ledger"
        if _parse_iso_ms(stats.get("lastCapture")) is not None
        else "wall-clock-capped-element-epoch"
    )

    # One event list, deduplicated on the interval it was found in. When both
    # detectors see the same interval the self-history one wins: its expectation
    # was measured from this object rather than from its neighbours, so its
    # residual -- and therefore its Delta-v -- is the better number.
    events = list(scan.events)
    seen = {(event.norad, event.start_ms, event.end_ms) for event in events}
    for event in cohort_events:
        if (event.norad, event.start_ms, event.end_ms) not in seen:
            events.append(event)

    truth = step("truth", GroundTruth.load)
    coverage_by_norad = {
        row["norad"]: [
            (_parse_iso_ms(run["fromAt"]), _parse_iso_ms(run["toAt"]))
            for run in row["observationRuns"]
        ]
        for row in scan.summaries
    }
    ground_truth = step("ground-truth", lambda: orbit_campaigns.score_ground_truth_with_coverage(
        events, truth, coverage_by_norad
    ))
    matched_by_norad = {
        (match.get("norad"), match.get("detectedStartAt")): match
        for match in ground_truth.get("matches", [])
    }

    maturity = step("maturity", lambda: orbit_campaigns.archive_maturity_from_scan(connection, scan, self_controls))
    cover = step("coverage", lambda: coverage(connection))
    narratives = narratives or {}

    # --- events -----------------------------------------------------------
    def event_record(event):
        record = event.as_dict()
        record["sunSynchronous"] = sun_synchronous(
            record["perigeeAltitudeKm"] + RE_WGS72, 0.0, record["inclinationDeg"]
        )
        record["constellation"] = event.catalog.get("constellation")
        record["kpMax"] = kp_context(connection, event.start_ms, event.end_ms)
        record["spaceWeather"]["kpMax"] = record["kpMax"]
        record["groundTruth"] = matched_by_norad.get((event.norad, record["startAt"]))
        # The card quotes the control that actually judged THIS event. Quoting
        # the cohort's false-alarm rate under an event the self-history detector
        # found would be citing a measurement of a different instrument, and it
        # is exactly the sort of quiet inconsistency that makes a number
        # untrustworthy.
        # as_dict rounds perigee to 0.1 km. Match the original measurement,
        # as ArchivePass.note does, or an edge can silently change strata.
        event_controls = _controls_for(
            record, controls, self_controls,
            matched_stratum=orbit_campaigns.control_stratum(event.start_ms, event.perigee_altitude_km),
        )
        record["controlBasis"] = _control_basis(record)
        record["controlStratum"] = event_controls.get("controlStratum") or (
            "not applicable: cohort-only events have no calibrated matched stratum"
            if record["controlBasis"] == "cohort" else
            "not enabled: matched-control flag is disabled")
        # The two detectors have independent blanks. A calibrated self-history
        # lane must not lend its word to a new-object event found only by the
        # cohort lane (or vice versa), so permission travels with the event.
        record["manoeuvreLabelPermitted"] = _event_label_permitted(
            record, event_controls
        )
        record["card"] = describe(record, event_controls)
        key = event_key(record)
        record["eventKey"] = key
        accepted = validate_candidate(narratives.get(key), record)
        if accepted is not None:
            record["narrative"] = accepted
        return record


    checkpoint = getattr(step, "__self__", None)
    disk_cards = isinstance(checkpoint, TailCheckpoint)
    records: list[dict[str, Any]] = []
    if disk_cards:
        TailEvents.put(checkpoint.db, [])
    for offset in range(0, len(events), 128):
        batch = step(f"cards:{offset}", lambda: [
            event_record(event) for event in events[offset:offset + 128]
        ])
        if disk_cards:
            TailEvents.put(checkpoint.db, [
                {**r, "deltaVMetresPerSecond": r["deltaV"]["totalMetresPerSecond"]}
                for r in batch], offset)
            # Selection needs cost, NORAD, truth and the slim published fields;
            # retaining full cards/narratives here used to scale with ALL events.
            records.extend({**_slim(r), "deltaV": r["deltaV"],
                            "expectation": {"verdict": (r.get("expectation") or {}).get("verdict")}}
                           for r in batch)
        else:
            records.extend(batch)

    headline = [_slim(record) for record in select_headline_events(records)]

    label_policy = _label_policy(controls, self_controls)
    events_bundle = {
        "schema": SCHEMA_VERSION,
        "generatedAt": generated_at,
        "kappa": COHORT_KAPPA,
        "coverage": cover,
        "controls": controls,
        "groundTruth": ground_truth,
        "events": headline,
        "eventsPublished": {
            "inThisBundle": len(headline),
            "total": len(records),
            "rule": (
                "The population views need one list of the notable changes across the whole "
                "catalogue; a per-object view needs that object's changes and fetches them with "
                "the object's history shard, which it is already fetching. So this list is the "
                "largest change on every object that had one, plus the largest remaining changes "
                "and every change an operator independently published, up to "
                f"{MAX_HEADLINE_EVENTS}. Nothing is hidden: every event is in its object's shard."
            ),
        },
        # The per-object rows come from the streaming pass, which has seen the
        # whole archive. `summarise_objects` is still exported by
        # `orbit_events` for the cohort-only case and is what the unit tests
        # exercise, but it takes a list of every interval and so cannot be the
        # thing that runs here.
        "objects": scan.summaries,
        "maturity": maturity,
        "labelPolicy": label_policy,
    }

    # --- history shards ---------------------------------------------------
    wanted = set(catalog)
    if INCLUDE_ALL_WITH_EVENTS:
        wanted |= {event.norad for event in events}
    events_at: dict[int, list[int]] = {}
    for event in events:
        events_at.setdefault(event.norad, []).extend((event.start_ms, event.end_ms))
    # The shard carries the FULL record — evidence card, channel tests, drag
    # prediction, expectation, narrative — not a marker. The detail view already
    # fetches the shard to draw the plot, so the evidence costs no extra request,
    # and a visitor who opens an object gets the same depth on every one of its
    # changes rather than only on whichever ones were large enough to make a
    # catalogue-wide list. That is the whole reason the headline list above can
    # be capped without hiding anything.
    # The typed events are still in scope here, which is what the clustering
    # needs -- it reads `delta_v.total` and `start_ms` off the object, not the
    # serialised record.
    typed_by_object: dict[int, list[Any]] = {}
    for event in events:
        typed_by_object.setdefault(event.norad, []).append(event)
    clusters_by_object: dict[int, list[dict[str, Any]]] = {}
    for norad, group in typed_by_object.items():
        found = repeat_clusters(group)
        if found:
            clusters_by_object[norad] = found

    if disk_cards:
        return (events_bundle, stats, wanted, events_at, TailEvents(checkpoint.root), clusters_by_object)

    events_by_object: dict[int, list[dict[str, Any]]] = {}
    for record in records:
        events_by_object.setdefault(record["norad"], []).append(
            # The flat `deltaVMetresPerSecond` is kept alongside the structured
            # `deltaV` it duplicates, because the shard's event list used to be a
            # thin marker and the browser reads that key. Widening a published
            # shape by addition costs one number per event; changing it strands
            # every browser holding the previous manifest.
            {**record, "deltaVMetresPerSecond": record["deltaV"]["totalMetresPerSecond"]}
        )
    for group in events_by_object.values():
        group.sort(key=lambda record: record["startAt"])

    return (events_bundle, stats, wanted, events_at, events_by_object, clusters_by_object)


def _history_shard(connection, index, wanted, events_at, events_by_object, clusters_by_object):
    # Each read is already indexed by NORAD. Read only this shard's members;
    # sorted member/sample/event order is unchanged from the all-series build.
    members = read_series(connection, {n for n in wanted if n % HISTORY_SHARDS == index}, events_at)
    if members:
        # Deliberately no `generatedAt` and no `coverage` in a shard. Artifacts
        # are content-addressed, so any field that changes when the DATA has not
        # would mint 256 new files on every five-minute publish cycle -- about a
        # hundred and fifty thousand files a day, all of them identical in
        # substance. A shard therefore contains only what it is about, and
        # changes only when one of its objects gains an element set or an event.
        # Coverage and generation time live once, in the events bundle, which
        # the browser has already loaded before it asks for any shard.
        return {
            "schema": SCHEMA_VERSION,
            "shard": index,
            "shardCount": HISTORY_SHARDS,
            "objects": [
                {
                    "norad": norad,
                    "samples": samples,
                    "events": events_by_object.get(norad, []),
                    # Present only where this object actually repeats itself.
                    # An absent key means "no cadence found", which is a
                    # different statement from an empty one and is drawn
                    # differently.
                    **(
                        {"repeatClusters": clusters_by_object[norad]}
                        if norad in clusters_by_object
                        else {}
                    ),
                }
                for norad, samples in sorted(members.items())
            ],
        }
    return None


def _build_drag(connection, stats, events_bundle, step):
    generated_at = events_bundle["generatedAt"]
    cover = events_bundle["coverage"]
    # --- population / drag ------------------------------------------------
    end_ms = step("drag-end", lambda: observed_archive_end_ms(
        stats, now_ms=_parse_iso_ms(generated_at)))
    # Bounded to the most recent window rather than run over the whole archive.
    # Two reasons, and the second is the one that matters: a median decay rate
    # per shell is a statement about *the atmosphere the objects are flying
    # through*, and an atmosphere averaged over fifteen years of solar cycle is
    # not a measurement of anything. (The first reason is that
    # `population_decay` pulls each object's series in turn, so an unbounded
    # window is twelve thousand queries over six million rows.) A window with
    # too few tracers is refused by `min_objects`, which is the honest failure.
    start_ms = end_ms - int(POPULATION_WINDOW_DAYS * 86_400_000)
    watched_days = step("watched-days", lambda: observation_span_days(connection))
    def population_shells():
        try:
            return population_decay(connection, start_ms=start_ms, end_ms=end_ms)
        except Exception as error:  # Optional estimate; checkpoint errors must still propagate.
            print(f"WARNING: population decay unavailable: {error}")
            return []

    shells = step("shells", population_shells)

    drag_bundle = {
        "schema": SCHEMA_VERSION,
        "generatedAt": generated_at,
        "coverage": cover,
        "shells": shells,
        "densityEnhancement": step("density", lambda: _density_if_possible(connection, start_ms, end_ms, watched_days)),
        "kp": [
            {"at": iso(observed_ms), "value": value}
            for observed_ms, value in kp_series(connection, start_ms=start_ms, end_ms=end_ms)
        ],
        "spaceWeatherGaps": space_weather_gaps(),
        "maturity": events_bundle["maturity"],
        "method": {
            "shells": (
                "Median rate of change of semi-major axis per fifty-kilometre perigee shell, over "
                "debris and spent stages only. Passive objects are clean ballistic tracers and "
                "cannot manoeuvre, so the same population is both the null hypothesis for the "
                "manoeuvre detector and the instrument for measuring the atmosphere."
            ),
            "densityRatio": (
                "Each object's storm-time decay against its OWN quiet-time decay, then the median "
                "of those ratios. Because decay is linear in neutral density, the ballistic "
                "coefficient cancels exactly and what is left is a measurement of thermospheric "
                "density enhancement made with satellites rather than with a model."
            ),
            "diurnalTrap": (
                "Neutral density changes by about a factor of two between the day and night sides, "
                "so a rate measured over less than three complete revolutions measures local solar "
                "time rather than the atmosphere. Every rate used here spans at least three."
            ),
        },
    }
    return drag_bundle


def _density_if_possible(
    connection: sqlite3.Connection, start_ms: int, end_ms: int, watched_days: float
) -> dict[str, Any]:
    """The storm density ratio, or an honest statement of what is missing.

    Needs a quiet baseline window and a disturbed window in the same archive.
    On an archive hours old there is only one window, and dividing it by itself
    would return 1.0 with a straight face -- a number that looks like a
    measurement and is not one.
    """
    # Gated on how long the archive has been WATCHING, not on the span of the
    # epochs it holds -- see observation_span_days() for why the difference bites.
    span_days = watched_days
    if span_days < 7.0:
        return {
            "available": False,
            "reason": "insufficient-archive-span",
            "needs": (
                "A geomagnetically quiet reference window and a disturbed window inside the same "
                "archive. The ratio is each object's storm-time decay against its own quiet-time "
                "decay, so the archive has to contain both."
            ),
            "spanDays": round(span_days, 3),
            "validationTarget": {
                "event": "Gannon storm, May 2024",
                "expectedRatio": 4.7,
                "note": (
                    "KANOPUS-V 3's decay went from about 38 to about 180 metres per day at roughly "
                    "475 km during the May 2024 storm. Because decay is linear in density and the "
                    "ballistic coefficient cancels in the ratio, that factor of 4.7 IS a measured "
                    "density enhancement. NRLMSIS 2.1 gives 2.06 for the same conditions. This "
                    "archive cannot check itself against May 2024 -- it begins in August 2026 -- so "
                    "the check that can be run is the forward one, on the next storm it sees."
                ),
            },
        }
    midpoint = start_ms + (end_ms - start_ms) // 2
    try:
        shells = density_enhancement(
            connection,
            quiet_start_ms=start_ms,
            quiet_end_ms=midpoint,
            storm_start_ms=midpoint,
            storm_end_ms=end_ms,
        )
    except Exception as error:                      # noqa: BLE001
        return {"available": False, "reason": f"estimator-failed: {error}"}
    return {
        "available": bool(shells),
        "reason": None if shells else "no-shell-met-the-minimum-population",
        "shells": shells,
        "windowSplit": {"quietTo": iso(midpoint), "stormFrom": iso(midpoint)},
        "caution": (
            "The window split here is the midpoint of the archive, not a geomagnetically chosen "
            "one. Once the archive spans a real storm, choose the windows from Kp."
        ),
    }


# ---------------------------------------------------------------------------
# Publishing
# ---------------------------------------------------------------------------
# The manifest fragment last written by the offline builder. Small on purpose:
# it holds paths and digests, never bundle contents, so reading it costs a few
# milliseconds and duplicates none of the data.
FRAGMENT_PATH = ROOT / "pipeline" / ".cache" / "orbit-manifest.json"

# ---------------------------------------------------------------------------
# The sweep is a multi-run job now. These three numbers are why.
# ---------------------------------------------------------------------------
# How long one run may spend inside the archive sweep before it checkpoints and
# stops. It has to leave room, under the unit's TimeoutStartSec, for the TAIL
# that a sweep-completing run then does -- cohort detection, the event cards,
# `read_series` over the catalogue, and 256 shards -- because the tail is not
# itself resumable and must never be the thing that gets killed.
DEFAULT_SWEEP_BUDGET_SECONDS = 2400.0

# THE BANDWIDTH DECISION, ENFORCED IN CODE RATHER THAN BY THE TIMER.
#
# The rebuild is daily for a measured reason: the shards are
# content-addressed, so every completed rebuild ships all 256 of them in full --
# 2.26 GB raw, 0.53 GB compressed, which at an hourly cadence was 71% of ALL
# traffic from bigmem to the VPS and 382 GB a month against a 2 TB allowance.
#
# A sweep now takes several runs, so RUN frequency and SHIP frequency are no
# longer the same thing, and the timer can no longer express that decision on
# its own. This does: a finished sweep does not begin another until this long
# after the last one finished, so however often the timer fires, the shards ship
# about once a day. Changing the timer's period is a scheduling choice; changing
# THIS is a bandwidth choice.
MINIMUM_SECONDS_BETWEEN_SWEEPS = 20 * 3600.0

# Where a half-finished sweep waits for the next run. Beside the manifest
# fragment, because it is the same kind of thing: private build state, rebuilt
# from the archive if it is ever lost, and never served to anyone.
SWEEP_STATE_PATH = ROOT / "pipeline" / ".cache" / "orbit-sweep-state.pickle"
# Persistence first changed the meaning of cached ArchivePass records, then the
# failed passive control forced self-history RAAN back off. Reject both older
# shapes structurally: a mixed RAAN event cannot be repaired by subtracting one
# aggregate counter after its signature and cost were already materialised.
# v5 adds the tail identity only: v4 sweep results must migrate, not restart.
SWEEP_STATE_VERSION = 5

# A cursor above every catalogue number, meaning "the sweep reached the end".
#
# Persist the finished pass before starting the independently resumable tail.
# A resumed tail skips the sweep entirely, keeping its final controls intact.
SWEPT_TO_END = 1 << 62


def _read_sweep_state(
    *, self_history_kappa: float, catalog_size: int
) -> dict[str, Any] | None:
    """The half-finished sweep to continue, or `None` to start a fresh one.

    Refuses the file rather than repairing it whenever continuing would mix
    incomparable work: a different `kappa` is a different detector, and a
    catalogue that changed size means `keep_summaries_for` changed, so the
    summaries already accumulated are not the set this run would produce. Both
    are cheap to detect and expensive to publish, and starting over costs one
    sweep while publishing a mixture costs the numbers' credibility.
    """
    try:
        with SWEEP_STATE_PATH.open("rb") as handle:
            state = pickle.load(handle)
    except (OSError, EOFError, pickle.UnpicklingError, AttributeError, ImportError):
        return None
    if not isinstance(state, dict) or state.get("version") not in (4, SWEEP_STATE_VERSION):
        return None
    if (
        state.get("kappa") != self_history_kappa
        or state.get("detectorFlags") != orbit_campaigns.detector_flags()
        or state.get("catalogSize") != catalog_size
    ):
        return None
    if not isinstance(state.get("resumeAfter"), int):
        return None
    if not isinstance(state.get("passed"), orbit_campaigns.ArchivePass):
        return None
    # Version 5 adds a tail identity; v4 detector results remain compatible.
    state["version"] = SWEEP_STATE_VERSION
    return state


def _write_sweep_state(state: dict[str, Any]) -> None:
    """Checkpoint atomically, for the same reason `write_fragment` does.

    A run that is killed while writing this must leave either the previous
    checkpoint or none -- never a truncated one, which would silently restart a
    sweep that was most of the way through and look like no progress at all.
    """
    state = {**state, "detectorFlags": orbit_campaigns.detector_flags()}
    SWEEP_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = SWEEP_STATE_PATH.with_suffix(".pickle.tmp")
    with temporary.open("wb") as handle:
        pickle.dump(state, handle, protocol=pickle.HIGHEST_PROTOCOL)
    temporary.replace(SWEEP_STATE_PATH)


def _clear_sweep_state() -> None:
    SWEEP_STATE_PATH.unlink(missing_ok=True)
    SWEEP_STATE_PATH.with_suffix(".pickle.tmp").unlink(missing_ok=True)


def _sweep_lock_path() -> Path:
    """Derived from the state file so a test root carries its own lock."""
    return SWEEP_STATE_PATH.with_suffix(".lock")


def _acquire_sweep_lock():
    """Take the one permission to advance this sweep, or return None.

    WHY THIS EXISTS (2026-09-20)
    ----------------------------
    Both halves of this job are resumable and both can outlast the timer's
    period: a two-hourly slice can fire while the previous slice -- or an
    operator's forced run -- is still inside the tail. Until now nothing
    stopped them, and two processes sharing one stage store is not a slow
    build, it is a broken one. They interleave `TailCheckpoint.has()` and its
    `INSERT`, and the loser dies on `UNIQUE constraint failed: stage.name`.
    That is exactly what happened twice on 2026-09-20: the 14:30 slice died at
    14:34 against an operator's forced tail, and the forced tail then died at
    16:44 against the 16:30 slice, throwing away three hours of finished
    analysis and leaving the manoeuvre-label gate shut.

    `tailId` is not the missing piece and was never meant to be. It keeps two
    DIFFERENT sweeps' stages apart, which is why a superseded workspace is
    deleted rather than adopted. Nothing kept two runs of the SAME sweep apart,
    because a resumed tail is *supposed* to adopt the stages already there.
    That is this lock's job, and only this lock's.

    POSIX record locks rather than `flock`, deliberately. The tail forks a
    worker pool whose children install `SIG_IGN` for SIGTERM; an `flock` lives
    on the open file description and would be inherited by every one of them,
    so a single lingering worker could lock the sweep out of all future slices.
    A record lock belongs to the process that took it and to no child of it.

    Nonblocking, because a slice that waits has spent the budget it was given
    to make progress. Being refused costs nothing: the sweep state and the tail
    stages are untouched and the next firing continues from them.
    """
    path = _sweep_lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+")
    try:
        fcntl.lockf(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        # Held by another run. Any other OSError is a real fault -- a
        # filesystem without locking would otherwise mean "busy" forever.
        handle.close()
        return None
    # Name the holder, so the run that is refused can say who has it.
    handle.truncate(0)
    handle.write(f"{os.getpid()}\n")
    handle.flush()
    return handle


def _sweep_lock_in_flight() -> dict[str, Any] | None:
    """Read-only: is a run holding the lock right now, and which one.

    Probed by taking the lock and dropping it again, which is why it may only
    be called from a path that does not intend to sweep -- `--sweep-status`.
    """
    handle = _acquire_sweep_lock()
    if handle is None:
        return {"heldBy": _sweep_lock_holder()}
    handle.close()
    return None


def _sweep_lock_holder() -> str:
    try:
        return _sweep_lock_path().read_text().strip() or "unknown"
    except OSError:
        return "unknown"


def _seconds_until_sweep_due(minimum_seconds: float, *, now: float) -> float:
    """How long until a NEW sweep may start, from the last one's own timestamp.

    Read from the published fragment rather than from a counter this module
    keeps, because the fragment's `generatedAt` is the moment the shards that
    are actually on disk were built. A separate counter could disagree with it,
    and then the bandwidth rule would be enforced against a number nobody can
    see.
    """
    if minimum_seconds <= 0:
        return 0.0
    try:
        payload = json.loads(FRAGMENT_PATH.read_text())
        generated_at = payload["generatedAt"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return 0.0
    last = _parse_iso_ms(generated_at)
    if last is None:
        return 0.0
    return max(0.0, (last / 1000.0) + minimum_seconds - now)


def publish(
    data_root: Path,
    *,
    write_artifact: Callable[[Path, str, Any], tuple[str, str]] | None = None,
    connection: sqlite3.Connection | None = None,
    kappa: float = 8.0,
) -> dict[str, dict[str, Any]]:
    """The manifest records for the orbit artifacts, read from the offline build.

    **This function does not touch the archive, and must not start to.**

    It used to. It called `build_bundles`, which called `load_intervals`, which
    materialised every consecutive pair of element sets in the archive as a
    Python object. On an archive of a few thousand element sets that cost
    1.6 seconds. After the 2004-2025 backfill landed 15.5 million of them it
    cost **9.3 GB resident and more than five minutes**, which is longer than
    the five-minute publish cycle it was running inside: `space-explorer-data.
    service` hit its 240 s `TimeoutStartSec`, was killed, and every subsequent
    cycle died the same way. The live site served four-hour-old data.

    The shape of the mistake is worth naming, because it is not "the archive got
    big". It is that **a job whose cost scales with the whole history was placed
    on a timer whose period is set by how often the newest data arrives.**
    Element sets arrive hourly and manoeuvre history changes hourly at most;
    recomputing twenty-two years of it twelve times an hour was waste even when
    it was affordable.

    So the heavy pass moved to `build_cache()` on its own timer, and the publish
    cycle does what it should always have done: check that the artifacts the
    offline build produced are still on disk, and name them in the manifest.
    `write_artifact` is accepted and ignored, so `build_release.py` needed no
    change at all.
    """
    del write_artifact, connection, kappa      # signature kept for the caller
    fragment = read_fragment(data_root) or previous_records(data_root)
    # Independent nightly lane: never let a step rebuild overwrite its pointer,
    # and preserve the last published drift artifact if its fragment is absent.
    drift = read_fragment(data_root, ROOT / "pipeline/.cache/orbit-drift-manifest.json")
    if not drift.get("orbitDrift"):
        drift = previous_records(data_root)
    if drift.get("orbitDrift"):
        fragment["orbitDrift"] = drift["orbitDrift"]
    if not fragment:
        # Raised rather than returned empty, so `build_release.py`'s existing
        # degrade path runs: it preserves whatever was published before instead
        # of quietly dropping three manifest keys and 404-ing a visitor whose
        # browser still holds the old manifest.
        raise FileNotFoundError(
            f"no usable orbit manifest fragment at {FRAGMENT_PATH}; "
            "run `python3 -m pipeline.orbit_release --build-cache`"
        )
    return fragment


def read_fragment(data_root: Path, path: Path | None = None) -> dict[str, dict[str, Any]]:
    """The offline build's manifest fragment, or `{}` if it cannot be trusted.

    Every referenced artifact is checked for existence before the fragment is
    handed back. A fragment naming a file `prune_data.py` has since removed
    would put a 404 in a visitor's browser rather than an error in the
    pipeline, which is the failure mode this project has learned to fear most.
    """
    try:
        payload = json.loads((path or FRAGMENT_PATH).read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    fragment = payload.get("manifest")
    if not isinstance(fragment, dict):
        return {}
    for record in fragment.values():
        if not isinstance(record, dict):
            return {}
        candidates = record.get("shards") if isinstance(record.get("shards"), list) else [record]
        for candidate in candidates:
            path = candidate.get("path") if isinstance(candidate, dict) else None
            if not isinstance(path, str) or not (data_root / path).is_file():
                return {}
    return fragment


def previous_records(data_root: Path) -> dict[str, dict[str, Any]]:
    """The orbit records already in the published manifest, if their files survive.

    `build_release.py`'s degrade path preserves `orbitEvents` and `orbitDrag`
    with `prior_artifact_record`, and **explicitly skips `orbitHistory`**,
    because that record is a list of 256 shards rather than a single
    `path`+`sha256` and `prior_artifact_record` cannot see inside it. The
    asymmetry is silent and it costs the visitor every plot for a cycle: the
    shards are still on disk and still correct, and the manifest simply stops
    naming them.

    Fixing it here rather than there keeps `build_release.py` untouched, which
    matters while several agents are in that file — and it is the right place
    anyway, since this module owns the sharded shape.
    """
    try:
        manifest = json.loads((data_root / "manifest.json").read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    kept: dict[str, dict[str, Any]] = {}
    for key in ("orbitHistory", "orbitEvents", "orbitDrag", "orbitDrift"):
        record = manifest.get(key)
        if not isinstance(record, dict):
            continue
        candidates = record.get("shards") if isinstance(record.get("shards"), list) else [record]
        if all(
            isinstance(entry, dict)
            and isinstance(entry.get("path"), str)
            and (data_root / entry["path"]).is_file()
            for entry in candidates
        ) and candidates:
            kept[key] = record
    return kept


def build_cache(
    data_root: Path,
    *,
    write_artifact: Callable[[Path, str, Any], tuple[str, str]],
    connection: sqlite3.Connection | None = None,
    self_history_kappa: float = DEFAULT_SELF_HISTORY_KAPPA,
    budget_seconds: float | None = DEFAULT_SWEEP_BUDGET_SECONDS,
    sweep_workers: int | None = None,
    sweep_gpu: tuple[int, ...] | None = None,
    sweep_gpu_verify: tuple[int, ...] | None = None,
    sweep_gpu_ceiling_mib: int = 1335,
    tail_workers: int | None = None,
    minimum_seconds_between_sweeps: float = MINIMUM_SECONDS_BETWEEN_SWEEPS,
    now: float | None = None,
) -> tuple[dict[str, dict[str, Any]] | None, dict[str, Any]]:
    """Advance the archive sweep; publish the three artifacts if it finished.

    Returns `(fragment, report)`. `fragment` is None until both sweep and tail
    finish. Tail slices write immutable artifacts, but `orbit-manifest.json`
    keeps naming the previous complete set until the new set is ready.
    `report` says which
    of the three things happened -- `swept`, `checkpointed` or `held` -- and is
    what the unit's log shows.

    WHAT THIS FUNCTION LEARNED ON 2026-08-18
    ----------------------------------------
    It used to run the whole pass in one call, which was right when the pass
    took 32-45 minutes. The 2004-2025 back-fill took `element_set` from 55.2 M
    rows to 181.3 M, and on WSL drvfs 9p a cold ordered scan of that is 7,557
    rows/s -- 6 h 40 m. `orbit-release.service` allows 3,600 s, so from
    2026-08-13 every run was SIGTERMed at the ceiling and discarded one to two
    hours of completed analysis. Six consecutive nights, and the published orbit
    artifacts did not move between 2026-08-08 and 2026-08-18.

    So the sweep is now budgeted and resumable, and this function is a state
    machine over three cases rather than one long straight line:

      held           a sweep finished recently and the next one is not due.
                     `MINIMUM_SECONDS_BETWEEN_SWEEPS` is the bandwidth
                     decision; see its comment. Costs nothing and reads nothing.
      busy           another run holds the sweep lock and is advancing this
                     same sweep or its tail. Costs nothing and reads nothing;
                     the work it would have done is being done already.
      checkpointed   the budget ran out in the sweep or tail. Completed work
                     is retained; the report names the phase and tail stage.
      swept          both the archive sweep and the tail finished; the complete
                     manifest fragment has been atomically rewritten.

    Publishing requires both a complete sweep and a complete tail. A partial pass
    has partial control counters, and the false-alarm rate that decides whether
    the word "manoeuvre" may appear at all is computed from them; publishing one
    measured over a fraction of the population would put a number on the page
    that no one could defend.

    `write_artifact` is injected rather than imported so this module never
    imports `build_release`, which is shared and which imports the world. The
    caller passes its own, which is the one that already content-addresses,
    gzips and sets permissions.
    """
    if sweep_gpu is not None and sweep_gpu_verify is not None:
        raise ValueError("GPU execution and verification are mutually exclusive")
    # Before the archive is opened: a refused run must cost nothing at all.
    lock = _acquire_sweep_lock()
    if lock is None:
        return None, {
            "status": "busy",
            "reason": (
                "another orbit-release run holds the sweep lock and is advancing this "
                "sweep or its tail; one stage store admits exactly one writer"
            ),
            "lockPath": _sweep_lock_path().as_posix(),
            "heldBy": _sweep_lock_holder(),
            "published": False,
        }
    close_after = connection is None
    connection = connection or orbit_campaigns.open_archive_for_reading()
    clock = time.time() if now is None else now
    deadline = None if budget_seconds is None else clock + budget_seconds
    try:
        catalog = load_catalog(data_root)
        state = _read_sweep_state(
            self_history_kappa=self_history_kappa,
            catalog_size=len(catalog),
        )
        if state is None:
            held_for = _seconds_until_sweep_due(minimum_seconds_between_sweeps, now=clock)
            if held_for > 0:
                return None, {
                    "status": "held",
                    "reason": (
                        "a sweep finished less than "
                        f"{minimum_seconds_between_sweeps / 3600.0:.0f} h ago; the shards "
                        "ship once per finished sweep and that is the bandwidth budget"
                    ),
                    "secondsUntilDue": round(held_for, 1),
                }

        started_at = state["startedAt"] if state else dt.datetime.now(
            dt.timezone.utc
        ).isoformat(timespec="seconds").replace("+00:00", "Z")
        tail_resume = state is not None and state["resumeAfter"] == SWEPT_TO_END
        if tail_resume:
            progress = orbit_campaigns.SweepProgress(state["passed"], None, 0, 0.0)
        else:
            progress = orbit_campaigns.sweep_archive(
                connection,
                kappa=self_history_kappa,
                catalog=catalog,
                keep_summaries_for=set(catalog),
                start_after=state["resumeAfter"] if state else None,
                deadline=deadline,
                into=state["passed"] if state else None,
                workers=sweep_workers,
                gpu_devices=sweep_gpu,
                gpu_verify_devices=sweep_gpu_verify,
                gpu_ceiling_mib=sweep_gpu_ceiling_mib,
            )
        if not progress.complete:
            _write_sweep_state(
                {
                    "version": SWEEP_STATE_VERSION,
                    "kappa": self_history_kappa,
                    "catalogSize": len(catalog),
                    "startedAt": started_at,
                    "resumeAfter": progress.resume_after,
                    "passed": progress.passed,
                }
            )
            return None, {
                "status": "checkpointed",
                "sweepStartedAt": started_at,
                "resumeAfter": progress.resume_after,
                "objectsThisRun": progress.objects_this_run,
                "objectsSoFar": progress.passed.objects_scanned,
                "secondsThisRun": round(progress.seconds, 1),
                "published": False,
                "note": (
                    "budget spent mid-sweep; the accumulated pass is checkpointed and the "
                    "previously published artifacts are untouched"
                ),
            }

        # Keep v4 sweep results intact; add an identity only when the pass ends.
        # The identity survives restarts and prevents mixing two tails' stages.
        state = {
            **(state or {}),
            "version": SWEEP_STATE_VERSION,
            "kappa": self_history_kappa,
            "catalogSize": len(catalog),
            "startedAt": started_at,
            "resumeAfter": SWEPT_TO_END,
            "passed": progress.passed,
        }
        if "tailId" not in state:
            state["tailId"] = uuid.uuid4().hex
            _write_sweep_state(state)
        report = {
            "status": "swept",
            "sweepStartedAt": started_at,
            "objectsThisRun": progress.objects_this_run,
            "objectsSoFar": progress.passed.objects_scanned,
            "secondsThisRun": round(progress.seconds, 1),
            "published": True,
        }
        tail_root = SWEEP_STATE_PATH.with_suffix(".tail")
        # If the sweep spent this run's budget, let the next invocation begin
        # the tail with a fresh budget. A sentinel resume scans zero objects.
        if progress.objects_this_run and deadline is not None and time.time() >= deadline:
            return None, {**report, "status": "checkpointed", "phase": "tail",
                          "published": False, "shardsDone": 0}
        with TailCheckpoint(tail_root, state["tailId"], data_root.resolve(), deadline) as tail:
            try:
                fragment = _finish_tail(connection, data_root, write_artifact,
                                        self_history_kappa, progress.passed, tail, tail_workers)
            except TailPaused:
                return None, {
                    **report, "status": "checkpointed", "phase": "tail",
                    "published": False, "lastStage": tail.last_stage,
                    "shardsDone": len(tail.values("shard:")),
                    "secondsThisRun": round(time.time() - clock, 1),
                    "note": "tail checkpoint saved; previous manifest remains available",
                }
        # Clearing the sweep BEFORE its private workspace makes a crash here
        # harmless: the published fragment gates the next sweep as usual.
        _clear_sweep_state()
        tail.clear()
        return fragment, report
    finally:
        if close_after:
            connection.close()
        # Last, and unconditionally: the next slice's whole ability to make
        # progress is this handle being closed however this run ended.
        lock.close()


_tail_archive = None
_tail_writer = None
_tail_data_root = None
_tail_visual_usage = None
_tail_visual_admit = None


def _start_tail_worker(path, data_root, writer, series_policy, visual_usage):
    global _tail_archive, _tail_writer, _tail_data_root, _tail_visual_usage, _tail_visual_admit
    global HISTORY_SHARDS, SERIES_GRID_HOURS, EVENT_DETAIL_HOURS
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    _tail_archive = orbit_campaigns.open_archive_for_reading(Path(path))
    _tail_data_root, _tail_writer = Path(data_root), writer
    HISTORY_SHARDS, SERIES_GRID_HOURS, EVENT_DETAIL_HOURS = series_policy
    # The production callback also writes plot derivatives. Its admission
    # counter was process-local; preserve ONE budget across this worker pool.
    from pipeline import visual_storage
    _tail_visual_usage = visual_usage
    _tail_visual_admit = visual_storage.admit
    visual_storage.admit = _admit_tail_visuals


def _admit_tail_visuals(root, additional_bytes, additional_files):
    from pipeline import visual_storage as storage
    with _tail_visual_usage.get_lock():
        key = str(Path(root).resolve())
        storage._usage[key] = dict(zip(("bytes", "files"), _tail_visual_usage[:]))
        _tail_visual_admit(root, additional_bytes, additional_files)
        _tail_visual_usage[:] = (storage._usage[key]["bytes"], storage._usage[key]["files"])


def _write_tail_shard(index, wanted, marks, events, clusters):
    shard = _history_shard(_tail_archive, index, wanted, marks, events, clusters)
    if shard is None:
        return None
    path, digest = _tail_writer(_tail_data_root, f"orbit-history-{index:03d}", shard)
    return {"shard": index, "path": path, "sha256": digest, "objects": len(shard["objects"])}


def _write_tail_shards(connection, prepared, tail, data_root, writer, workers=None, *, indices=None):
    workers = orbit_campaigns.sweep_worker_count() if workers is None else workers
    if workers < 1:
        raise ValueError("orbit tail workers must be positive")
    indices = range(HISTORY_SHARDS) if indices is None else indices
    remaining = iter(i for i in indices if not tail.has(f"shard:{i:03d}"))
    _, _, wanted, marks, events, clusters = prepared
    path = next((row[2] for row in connection.execute("PRAGMA database_list") if row[1] == "main"), "")
    try:
        pickle.dumps(writer)
    except (TypeError, AttributeError, pickle.PicklingError):
        workers = 1  # Local injected callbacks, as with uncommitted fixture DBs.
    if workers == 1 or not path or connection.in_transaction or tail.expired():
        for index in remaining:
            def build(index=index):
                shard = _history_shard(connection, index, wanted, marks, events, clusters)
                if shard is None:
                    return None
                path, digest = writer(data_root, f"orbit-history-{index:03d}", shard)
                tail.pin(path, digest)
                return {"shard": index, "path": path, "sha256": digest, "objects": len(shard["objects"])}
            tail.step(f"shard:{index:03d}", build)
        return

    first = next(remaining, None)
    if first is None:
        return
    from pipeline import visual_storage
    usage = visual_storage.report(data_root)
    context = multiprocessing.get_context("spawn")
    shared_usage = context.Array("q", (usage["bytes"], usage["files"]))
    with ProcessPoolExecutor(max_workers=workers, mp_context=context,
                             initializer=_start_tail_worker,
                             initargs=(path, str(data_root), writer,
                                       (HISTORY_SHARDS, SERIES_GRID_HOURS, EVENT_DETAIL_HOURS),
                                       shared_usage)) as pool:
        pending = {}
        def submit(index):
            members = {n for n in wanted if n % HISTORY_SHARDS == index}
            # The stage DB has one owner. Loading this shard's cards here
            # avoids readers competing with parent checkpoint commits in the
            # existing rollback journal; only shard-local cards cross the pipe.
            local_events = {n: events.get(n, []) for n in members}
            future = pool.submit(_write_tail_shard, index, members,
                                 {n: marks[n] for n in members if n in marks}, local_events,
                                 {n: clusters[n] for n in members if n in clusters})
            pending[future] = index

        submit(first)
        for _ in range(workers - 1):
            if tail.expired():
                break
            index = next(remaining, None)
            if index is None:
                break
            submit(index)
        error = None
        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                index = pending.pop(future)
                try:
                    record = future.result()
                    if record is not None:
                        tail.pin(record["path"], record["sha256"])
                    # Never raise TailPaused until EVERY in-flight result is
                    # pinned and banked. No more than one shard per worker.
                    tail.save(f"shard:{index:03d}", record, check_budget=False)
                except Exception as failure:
                    error = error or failure
            if error is None and not tail.expired():
                for _ in range(workers - len(pending)):
                    if tail.expired():
                        break
                    index = next(remaining, None)
                    if index is None:
                        break
                    submit(index)
        visual_storage._usage[str(Path(data_root).resolve())] = dict(
            zip(("bytes", "files"), shared_usage[:]))
        if error is not None:
            raise error
    if tail.expired():
        raise TailPaused(tail.last_stage)


def _prepared_tail(connection, data_root, self_history_kappa, scan, tail):
    def prepare():
        # Old prepared tuples and every existing shard/stage remain valid. This
        # additive projection can be rebuilt after interruption without changing
        # the tail identity, timestamp, narratives, cards or banked artifacts.
        def fresh():
            narratives = tail.step("narratives", _load_narratives)
            return _prepare_tail(connection, data_root, self_history_kappa,
                                 narratives, scan, tail.step)

        prepared = tail.step("prepared", fresh)
        if isinstance(prepared[4], TailEvents):
            return prepared
        offset = 0
        TailEvents.put(tail.db, [])
        batch = []
        def spill():
            tail.step(f"cards-spilled:{offset}", lambda: TailEvents.put(tail.db, batch, offset))
        for records in prepared[4].values():
            for record in records:
                batch.append(record)
                if len(batch) == 128:
                    spill()
                    offset += len(batch)
                    batch = []
        if batch:
            spill()
        return (*prepared[:4], TailEvents(tail.root), prepared[5])

    return tail.step("prepared-streamed", prepare)


def _finish_tail(connection, data_root, write_artifact, self_history_kappa, scan, tail, workers=None):
    # Freeze the clock before the first possible yield, including preparation.
    tail.step("generated-at", _generation_time)

    def artifact(prefix, bundle):
        path, digest = write_artifact(data_root, prefix, bundle)
        tail.pin(path, digest)
        return {"path": path, "sha256": digest}

    prepared = _prepared_tail(connection, data_root, self_history_kappa, scan, tail)
    events_bundle, stats, *_ = prepared
    _write_tail_shards(connection, prepared, tail, data_root, write_artifact, workers)
    drag_bundle = tail.step("drag", lambda: _build_drag(connection, stats, events_bundle, tail.step))
    shard_records = [r for r in tail.values("shard:") if r is not None]
    event_record = tail.step("artifact:events", lambda: artifact("orbit-events", events_bundle))
    drag_record = tail.step("artifact:drag", lambda: artifact("orbit-drag", drag_bundle))
    events_path, events_digest = event_record["path"], event_record["sha256"]
    drag_path, drag_digest = drag_record["path"], drag_record["sha256"]
    fragment = {
        "orbitHistory": {
            "shardCount": HISTORY_SHARDS,
            "shards": shard_records,
            "objects": sum(record["objects"] for record in shard_records),
            "generatedAt": events_bundle["generatedAt"],
        },
        "orbitEvents": {
            "path": events_path,
            "sha256": events_digest,
            "count": len(events_bundle["events"]),
            "manoeuvreLabelPermitted": events_bundle["labelPolicy"]["manoeuvreLabelPermitted"],
            "generatedAt": events_bundle["generatedAt"],
        },
        "orbitDrag": {
            "path": drag_path,
            "sha256": drag_digest,
            "shells": len(drag_bundle["shells"]),
            "generatedAt": drag_bundle["generatedAt"],
        },
    }
    records = [*shard_records, event_record, drag_record]
    for record in records:
        tail.step(f"verify:{record['path']}", lambda: tail.restore([record]))
    # A verified public name could have been pruned during a later slice.
    # Relinking all retained immutable files is bounded metadata-only work.
    tail.restore(records, verify=False)
    # A fragment write is atomic and idempotent. Leave the checkpoint available
    # if the process exits after publishing but before cleanup.
    write_fragment(fragment, generated_at=events_bundle["generatedAt"])
    return fragment


def write_fragment(fragment: dict[str, dict[str, Any]], *, generated_at: str) -> None:
    """Record the fragment atomically, so a half-written one is never read.

    Written to a sibling temporary file and renamed, because `publish()` reads
    this on a five-minute timer and the builder can be running when it does.
    A partially written JSON file would be caught by the `JSONDecodeError`
    branch and degrade correctly, but it would also drop the orbit layer for a
    cycle for no reason, and a rename costs nothing.
    """
    FRAGMENT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = FRAGMENT_PATH.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps({"generatedAt": generated_at, "manifest": fragment}, indent=1, sort_keys=True)
    )
    temporary.replace(FRAGMENT_PATH)


def _load_narratives() -> dict[str, Any]:
    try:
        payload = json.loads(NARRATIVE_CACHE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT / "public" / "data")
    parser.add_argument("--archive", type=Path, default=None)
    parser.add_argument(
        "--self-history-kappa",
        type=float,
        default=DEFAULT_SELF_HISTORY_KAPPA,
        help="self-history step-detector threshold; the cohort threshold remains fixed at 8",
    )
    parser.add_argument("--dry-run", action="store_true", help="report sizes without writing")
    parser.add_argument("--build-cache", action="store_true",
                        help="the expensive pass: scan the archive, write the artifacts and the "
                             "manifest fragment the five-minute publish cycle reads")
    parser.add_argument("--budget-seconds", type=float, default=DEFAULT_SWEEP_BUDGET_SECONDS,
                        help="how long one run may spend on the sweep and tail before it "
                             "checkpoints and stops; 0 means no budget (the old behaviour, "
                             "which the unit's TimeoutStartSec will kill part-way)")
    parser.add_argument("--sweep-workers", type=int, default=None,
                        help="archive sweep processes; default leaves four CPUs free, capped at 12; "
                             "SPACE_EXPLORER_ORBIT_SWEEP_WORKERS overrides the default")
    gpu_modes = parser.add_mutually_exclusive_group()
    gpu_modes.add_argument("--sweep-gpu", type=int, nargs="+", default=None, metavar="DEVICE",
                           help="default off: use GPU sweep arithmetic on one/two devices; "
                                "skip CPU arithmetic on success, fall back loudly on failure")
    gpu_modes.add_argument("--sweep-gpu-verify", type=int, nargs="+", default=None, metavar="DEVICE",
                        help="default off: verify sweep arithmetic on one/two GPUs against CPU; "
                             "CPU verdicts remain authoritative; unavailable GPU is a loud fallback")
    parser.add_argument("--sweep-gpu-ceiling-mib", type=int, default=1335,
                        help="private GPU pool plus context reserve ceiling per card, 320..1335 MiB")
    parser.add_argument("--tail-workers", type=int, default=None,
                        help="shard processes; same default/environment policy as sweep workers; "
                             "budget/TERM drains at most one in-flight shard per worker plus checkpoint I/O")
    parser.add_argument("--force-sweep", action="store_true",
                        help="start a new sweep even if the last one finished less than "
                             "MINIMUM_SECONDS_BETWEEN_SWEEPS ago. The interval is a bandwidth "
                             "budget, not a safety rail, so an operator may spend it knowingly")
    parser.add_argument("--sweep-status", action="store_true",
                        help="report the checkpointed sweep, if any, and exit without reading "
                             "the archive")
    args = parser.parse_args(argv)

    devices = args.sweep_gpu if args.sweep_gpu is not None else args.sweep_gpu_verify
    if devices is not None:
        if not args.build_cache or args.dry_run or args.sweep_status:
            parser.error("--sweep-gpu/--sweep-gpu-verify requires --build-cache; use tools/verify_orbit_sweep_gpu.py for bounded tests")
        if (len(devices) > 2 or len(set(devices)) != len(devices)
                or min(devices) < 0 or not 320 <= args.sweep_gpu_ceiling_mib <= 1335):
            parser.error("GPU sweep requires one/two distinct nonnegative devices and a 320..1335 MiB ceiling")

    if args.sweep_status:
        catalog_size = len(load_catalog(args.data_root))
        state = _read_sweep_state(
            self_history_kappa=args.self_history_kappa,
            catalog_size=catalog_size,
        )
        print(json.dumps({
            "statePath": SWEEP_STATE_PATH.as_posix(),
            "inProgress": state is not None,
            "sweepStartedAt": state["startedAt"] if state else None,
            "resumeAfter": state["resumeAfter"] if state else None,
            "objectsSoFar": state["passed"].objects_scanned if state else 0,
            "eventsSoFar": len(state["passed"].events) if state else 0,
            "tail": TailCheckpoint.status(SWEEP_STATE_PATH.with_suffix(".tail")),
            "runInFlight": _sweep_lock_in_flight(),
            "secondsUntilNextSweepDue": round(
                _seconds_until_sweep_due(MINIMUM_SECONDS_BETWEEN_SWEEPS, now=time.time()), 1
            ),
        }, indent=2))
        return 0

    connection = orbit_campaigns.open_archive_for_reading(args.archive)
    if args.dry_run:
        from pipeline.build_release import canonical_json
        import gzip

        def size(value: Any) -> tuple[int, int]:
            raw = canonical_json(value)
            return len(raw), len(gzip.compress(raw, 9, mtime=0))

        # Measured and dropped one at a time, for the same reason the real build
        # writes them one at a time: a dry run that costs a gigabyte to tell you
        # how big something is has told you something you did not need to know
        # that expensively.
        shard_sizes: list[tuple[int, int]] = []
        _shards, events_bundle, drag_bundle = build_bundles(
            connection,
            args.data_root,
            self_history_kappa=args.self_history_kappa,
            narratives=_load_narratives(),
            on_shard=lambda shard: shard_sizes.append(size(shard)),
        )
        total_raw = sum(raw for raw, _ in shard_sizes)
        total_gz = sum(gz for _, gz in shard_sizes)
        events_raw, events_gz = size(events_bundle)
        drag_raw, drag_gz = size(drag_bundle)
        print(json.dumps({
            "shards": len(shard_sizes),
            "peakResidentMB": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 1),
            "shardBytesRaw": total_raw,
            "shardBytesGzip": total_gz,
            "largestShardGzip": max((gz for _, gz in shard_sizes), default=0),
            "eventsBytesGzip": events_gz,
            "dragBytesGzip": drag_gz,
            "events": len(events_bundle["events"]),
            "objectsSummarised": len(events_bundle["objects"]),
            "manoeuvreLabelPermitted": events_bundle["labelPolicy"]["manoeuvreLabelPermitted"],
        }, indent=2))
        return 0

    from pipeline.build_release import write_artifact

    if args.build_cache:
        started = time.time()
        fragment, report = build_cache(
            args.data_root,
            write_artifact=write_artifact,
            connection=connection,
            self_history_kappa=args.self_history_kappa,
            budget_seconds=args.budget_seconds if args.budget_seconds > 0 else None,
            sweep_workers=args.sweep_workers,
            sweep_gpu=None if args.sweep_gpu is None else tuple(args.sweep_gpu),
            sweep_gpu_verify=None if args.sweep_gpu_verify is None else tuple(args.sweep_gpu_verify),
            sweep_gpu_ceiling_mib=args.sweep_gpu_ceiling_mib,
            tail_workers=args.tail_workers,
            minimum_seconds_between_sweeps=(
                0.0 if args.force_sweep else MINIMUM_SECONDS_BETWEEN_SWEEPS
            ),
        )
        peak_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        payload: dict[str, Any] = {
            "builtIn": round(time.time() - started, 1),
            "peakResidentMB": round(peak_kb / 1024.0, 1),
            "fragment": FRAGMENT_PATH.as_posix(),
            "sweep": report,
        }
        if fragment is not None:
            payload.update({
                "orbitEvents": fragment["orbitEvents"],
                "orbitDrag": fragment["orbitDrag"],
                "orbitHistoryShards": len(fragment["orbitHistory"]["shards"]),
            })
        print(json.dumps(payload, indent=2))
        # Zero on every one of the three outcomes. A checkpointed run did real
        # work and kept it, and a held run obeyed the bandwidth budget; reporting
        # either as a unit failure is how a healthy schedule ends up looking
        # broken, and how a genuinely broken one stops being noticed.
        return 0

    print(json.dumps(publish(args.data_root, write_artifact=write_artifact,
                             connection=connection, kappa=COHORT_KAPPA), indent=2)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
