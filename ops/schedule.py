#!/usr/bin/env python3
"""The grid: what was supposed to run, in which hour, and what actually happened.

This module is pure. It takes timestamps and systemd facts in, and returns cell
states out. No file reads, no subprocesses, no network, no clock except the
"now" it is handed. That is what makes it testable offline, and it is also the
reason every colour on the page can be checked by hand.

WHY A GRID RATHER THAN A STATUS LIST
------------------------------------
A status list tells you what is stale. It cannot tell you about the fetch that
never happened, because a job that never ran leaves nothing to look stale. The
grid has a cell for every hour a job was *supposed* to run, so an hour with
nothing in it is visible as a hole rather than as an absence of evidence.

THE FIVE STATES THE GRID WAS SPECIFIED WITH, AND THE FOUR THIS ADDS
-------------------------------------------------------------------
Specified:

    ok       ran and succeeded
    running  in progress right now
    failed   attempted and failed
    pending  scheduled later today, not due yet          (empty cell)
    na       this hour is a scheduled slot, but not for this row   (dash)

Added, each because merging it into one of the five above would have lied:

    missed   the slot is in the past, was due, and NOTHING ran. This is the
             case the whole grid exists for. It is red, but it is drawn hollow,
             because "attempted and failed" and "never attempted" call for
             different first moves.
    partial  the slot holds several runs (the publish pipeline runs about
             twelve times an hour) and some succeeded while others failed. A
             single tick would hide the failures; a single cross would claim an
             outage that did not happen. The cell carries the count.
    halted   a halt marker is in place. The job stopped ON PURPOSE, exactly as
             CelesTrak's usage policy requires, and is waiting for a human. It
             is not a crash and it is not red: the operator's move is to read
             the marker and clear it, not to restart anything.
    unknown  the slot is in the past and we could not measure it — the journal
             had rolled, or the VPS did not answer. A check that could not run
             has not passed, so this is never drawn as a tick.

HOW THE EXPECTED SCHEDULE IS DERIVED
------------------------------------
Never by hand. A hand-written table of "what should run when" drifts away from
the units that actually run, and then the page lies, which is worse than having
no page. Every slot in this module comes from one of exactly two sources:

  * systemd's own parse of the timer (``TimersCalendar`` / ``TimersMonotonic``
    out of ``systemctl show``), for when a unit fires;
  * the interval constants imported from the fetchers themselves
    (``GP_INTERVAL``, ``SATCAT_INTERVAL``, ``SATCAT_EARLIEST_UTC_HOUR``,
    ``GROUP_INTERVAL``, ``GROUPS_PER_RUN``), for the gates the fetcher applies
    *after* the timer has fired.

If neither is available for a row, the row says so on the page and its past
cells are ``unknown``. It does not guess.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from typing import Iterable, Sequence

HOUR = 3600

# Cell states, worst-first where it matters for roll-ups.
OK = "ok"
PARTIAL = "partial"
RUNNING = "running"
FAILED = "failed"
MISSED = "missed"
HALTED = "halted"
PENDING = "pending"
NA = "na"
UNKNOWN = "unknown"

#: States that mean a human should look. Used for the alert decision and for
#: the row roll-up; ``halted`` is in here because a halt that nobody clears is
#: a catalogue quietly ageing, even though it is not a crash.
NEEDS_ATTENTION = (FAILED, MISSED, HALTED)


@dataclass(frozen=True)
class Event:
    """One thing that happened to one unit, at one instant.

    ``kind`` is 'start', 'success' or 'failure'. ``detail`` is whatever the
    journal said, kept verbatim so the page can show the operator the actual
    line rather than a paraphrase of it.
    """

    at: float
    kind: str
    detail: str = ""


@dataclass
class Slot:
    """One hour of one source's lane in the bar.

    ``marks`` carries the exact instant of every failure inside the hour, so a
    failure can be drawn where it actually happened rather than smeared across
    the whole hour, and so the click-through overlay can quote the journal line
    verbatim instead of paraphrasing it.
    """

    hour_start: float
    state: str
    attempts: int = 0
    successes: int = 0
    failures: int = 0
    note: str = ""
    marks: list = field(default_factory=list)     # (timestamp, kind, line)


# ---------------------------------------------------------------------------
# Journal parsing
# ---------------------------------------------------------------------------
# systemd's own wording. These are the only three lines that decide a colour,
# and they come from systemd rather than from the script's stdout, so a script
# that dies without printing anything still lands as a failure rather than as
# silence. That distinction is not theoretical on this stack: an empty
# completion reading as success has bitten this installation before.

_START = re.compile(r"systemd\[\d+\]: Starting ")
_SUCCESS = re.compile(r"systemd\[\d+\]: Finished ")
_FAILURE = re.compile(r"systemd\[\d+\]: (?:Failed to start |.*Failed with result )")
_TIMESTAMP = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})([+-]\d{2}:\d{2}|Z)")


def parse_journal(lines: Iterable[str]) -> list[Event]:
    """Turn ``journalctl -o short-iso`` output into events.

    Only systemd's own lines count. A unit that logs 'ERROR' on stdout and then
    exits zero has succeeded as far as systemd is concerned, and systemd is the
    thing that decides whether the next run happens — so systemd is the
    authority here too. Application-level complaints are surfaced separately as
    row notes, never as a cell colour.
    """
    events: list[Event] = []
    for line in lines:
        match = _TIMESTAMP.match(line)
        if not match:
            continue
        stamp = match.group(1) + ("+00:00" if match.group(2) == "Z" else match.group(2))
        try:
            when = dt.datetime.fromisoformat(stamp).timestamp()
        except ValueError:
            continue
        if _FAILURE.search(line):
            # Checked before success: a run that times out emits both a
            # 'Failed with result' and, sometimes, a late stdout flush.
            events.append(Event(when, "failure", line.strip()))
        elif _SUCCESS.search(line):
            events.append(Event(when, "success", line.strip()))
        elif _START.search(line):
            events.append(Event(when, "start", line.strip()))
    return events


# ---------------------------------------------------------------------------
# Which hours are slots
# ---------------------------------------------------------------------------


def calendar_slots(hours: Sequence[float], minute_of_hour: Sequence[int] | None,
                   hours_of_day: Sequence[int] | None) -> set[float]:
    """Slots for a timer with an ``OnCalendar`` expression.

    ``hours_of_day`` of ``None`` means every hour (``*:17:00``). A list means
    only those UTC hours (``13:40:00 UTC`` -> ``[13]``).
    """
    chosen = set()
    for start in hours:
        hour = dt.datetime.fromtimestamp(start, dt.timezone.utc).hour
        if hours_of_day is None or hour in hours_of_day:
            chosen.add(start)
    return chosen


def interval_slots(hours: Sequence[float], fetches: Sequence[float], interval: float,
                   earliest_utc_hour: int | None = None,
                   last_known_before: float | None = None) -> set[float]:
    """Slots for a dataset the fetcher gates on its own age, not on the clock.

    This SIMULATES the fetcher's rule rather than approximating it. Both
    ``spacetrack_ingest.py`` and ``celestrak_mirror.py`` ask the same question
    before every fetch — "is the file on disk at least ``interval`` old?" — so
    an hour is a slot only if the answer would have been yes at some point
    inside it. Everything else is a dash: the timer fired, the fetcher looked,
    and it was not this dataset's turn.

    Getting this wrong is not hypothetical. Gating SATCAT on the 1700Z
    publication boundary ALONE produced a red "was due and nothing ran" at 17Z
    on a day when the catalogue was twenty-three hours old and genuinely not
    due until 18:46Z. A false red is worse than no page, because it is the
    thing that teaches a person to stop looking.
    """
    ordered = sorted(fetches)
    chosen = set()
    for start in hours:
        if earliest_utc_hour is not None:
            if dt.datetime.fromtimestamp(start, dt.timezone.utc).hour < earliest_utc_hour:
                continue
        previous = max((when for when in ordered if when < start), default=None)
        # A FETCH WE CANNOT SEE IS NOT A FETCH THAT DID NOT HAPPEN.
        #
        # `last_known_before` is the caller's own evidence of when this dataset
        # was last written -- a file mtime -- for the hours where the journal
        # does not reach back far enough to hold the previous run. Without it
        # the only two options are both wrong: treat an unobserved past as due
        # (asserting a miss from absence) or as not due (hiding a feed that
        # died before the journal window).
        if previous is None and last_known_before is not None and last_known_before < start:
            previous = last_known_before
        # DUE AT THE START OF THE HOUR, NOT MERELY BY ITS END.
        #
        # This read `(start + HOUR) - previous > interval`: due if the file
        # COULD cross the interval at any instant inside the hour. But the
        # fetcher cannot act at any instant -- it acts when its timer fires,
        # and a timer that fires before the crossing correctly answers "not my
        # turn". The hour then had no fetch in it through no fault of anyone,
        # and the row went red.
        #
        # Measured 2026-08-31: SATCAT was written 08-30 17:23Z and again 08-31
        # 18:20Z, 24 h 57 m apart and entirely correct. The old test called the
        # 17:00Z hour due, because 18:00Z minus 17:23Z is 24 h 37 m -- while the
        # file only turned 24 h old at 17:23Z, after that hour's timer run. One
        # red row, every quarter hour, for six hours, for a download that had
        # already happened.
        #
        # Asking whether it was ALREADY due when the hour began costs at most
        # one hour of detection latency on a genuine outage, and the outage
        # still reddens every hour after that. This module's own docstring says
        # a false red is worse than no page.
        if previous is None and not ordered:
            # NEVER RAN, and that is a fact rather than a gap.
            #
            # No fetch anywhere in the window is itself the evidence: there is
            # no horizon to be behind, so the hour is genuinely due and unmet.
            # This is the case tests/test_watchdog.py::SatcatGate protects, and
            # it is the outage a first-run or long-dead feed presents as.
            chosen.add(start)
            continue
        if previous is None:
            # RAN, BUT BEFORE WE COULD SEE IT -- so nothing is claimed.
            #
            # The feed HAS fetched inside the window, just not before this
            # hour -- so this hour sits behind the journal's retention horizon
            # and the previous run is unobservable, not absent. Marking it due
            # is the one inference this page must never make: drawing "we
            # cannot know" as "it did not happen".
            # Measured 2026-08-31: the two oldest hours in the drawn grid,
            # 08-29 21:00Z and 22:00Z, hatched as "was due and nothing ran"
            # purely because the earliest SATCAT the journal still held was
            # 08-30 17:23Z -- an artefact of journal retention, printed as a
            # finding about the feed.
            #
            # A dead feed is still caught, and by better evidence: the caller
            # passes the file's own mtime as `last_known_before`, so a dataset
            # that stopped weeks ago still has a previous time, still goes due,
            # and still reddens. What is left here is the genuinely unknowable
            # case, and `cell_state` already has a colour for it.
            continue
        if start - previous > interval:
            chosen.add(start)
    return chosen


# ---------------------------------------------------------------------------
# Cell state
# ---------------------------------------------------------------------------


def cell_state(*, is_slot: bool, in_future: bool, measurable: bool,
               successes: int, failures: int, running: bool,
               halted: bool, overrunning: bool = False,
               deliberately_skipped: bool = False) -> str:
    """The whole colour decision, in one place, as arithmetic.

    No model is consulted and no heuristic is applied. Given the same booleans
    and two counts, this always returns the same string, and the page prints
    the counts beside the cell so the reader can redo the sum.

    ``deliberately_skipped`` is the case that makes the dash mean something.
    ``spacetrack_ingest.py`` logs "nothing due; not logging in" when its own
    interval has not elapsed, and the CelesTrak mirror simply does not fetch a
    dataset whose cadence is not up. Those are successful no-ops: the job ran,
    it just was not this dataset's turn. Colouring them red would train the
    reader to ignore red, and colouring them green would claim a fetch that
    never happened. They are dashes — exactly "this time has something else
    downloading, but not this particular thing".
    """
    if halted:
        return HALTED
    if not is_slot:
        return NA
    if overrunning:
        return FAILED
    attempts = successes + failures
    if deliberately_skipped and attempts == 0 and not running:
        return NA
    if attempts == 0:
        if running:
            return RUNNING
        if in_future:
            return PENDING
        if not measurable:
            return UNKNOWN
        return MISSED
    if failures and not successes:
        return FAILED
    if failures and successes:
        return PARTIAL
    if running:
        # Succeeded at least once this hour and is mid-run again: the honest
        # reading is that the hour is fine so far.
        return OK
    return OK


@dataclass
class Row:
    """One scheduled fetch or computation, and its day of cells."""

    key: str
    title: str
    machine: str
    kind: str                      # "download" or "compute"
    schedule_text: str             # human sentence, derived not typed
    schedule_source: str           # WHERE the sentence came from
    remedy: str                    # exact command when it is red
    slots: list[Slot] = field(default_factory=list)
    note: str = ""
    derived: bool = True           # False -> the page says it could not derive

    @property
    def worst(self) -> str:
        order = [FAILED, MISSED, HALTED, PARTIAL, UNKNOWN, RUNNING, OK, PENDING, NA]
        present = {slot.state for slot in self.slots}
        for state in order:
            if state in present:
                return state
        return NA

    def worst_since(self, cutoff: float) -> str:
        """Worst state among slots that START at or after ``cutoff``.

        The bars deliberately show a whole week, but an alert must be about
        NOW. Without this, a single failed hour last Tuesday would keep the page
        red and keep the alerter announcing it forever, and a person who is paged
        about last Tuesday stops reading pages.
        """
        order = [FAILED, MISSED, HALTED, PARTIAL, UNKNOWN, RUNNING, OK, PENDING, NA]
        present = {slot.state for slot in self.slots if slot.hour_start >= cutoff}
        for state in order:
            if state in present:
                return state
        return NA

    @property
    def needs_attention(self) -> bool:
        return self.worst in NEEDS_ATTENTION


def build_slots(*, hours: Sequence[float], slot_hours: set[float], events: Sequence[Event],
                now: float, measurable_from: float | None,
                halted_from: float | None = None,
                running_since: float | None = None,
                run_timeout: float | None = None,
                skip_hours: set[float] | None = None) -> list[Slot]:
    """Bucket events into hourly cells and colour each one.

    ``measurable_from`` is the oldest instant the evidence covers — the start of
    the journal window, or the moment the VPS probe's data begins. Anything
    before it is ``unknown`` rather than ``missed``, because we genuinely cannot
    tell, and calling that a failure would train the reader to ignore red.

    ``halted_from`` is when a halt marker was written. Every slot from then on
    is ``halted``: the job is deliberately not running and its cells should say
    so rather than accumulate a wall of red.
    """
    slots: list[Slot] = []
    overrunning = bool(
        running_since is not None and run_timeout and (now - running_since) > run_timeout
    )
    for start in hours:
        end = start + HOUR
        window = [event for event in events if start <= event.at < end]
        successes = sum(1 for event in window if event.kind == "success")
        failures = sum(1 for event in window if event.kind == "failure")
        starts = sum(1 for event in window if event.kind == "start")
        running = bool(running_since is not None and start <= running_since < end)
        state = cell_state(
            is_slot=start in slot_hours,
            # An hour is only judgeable once it has FINISHED. The hour we are
            # standing in still has minutes left to run, and calling it "was due
            # and nothing ran" at five past the hour would put a red box on the
            # page every single hour, which is the fastest way to make a person
            # stop reading red boxes.
            in_future=end > now,
            measurable=measurable_from is None or start >= measurable_from,
            successes=successes,
            failures=failures,
            running=running,
            halted=bool(halted_from is not None and end > halted_from and start <= now),
            overrunning=overrunning and running,
            deliberately_skipped=bool(skip_hours and start in skip_hours),
        )
        note = ""
        if state == FAILED and overrunning and running:
            note = f"running {int((now - running_since) / 60)} min, past its {int(run_timeout / 60)} min timeout"
        slots.append(Slot(
            hour_start=start, state=state, attempts=max(starts, successes + failures),
            successes=successes, failures=failures, note=note,
            marks=[(event.at, event.kind, event.detail) for event in window
                   if event.kind == "failure"],
        ))
    return slots


def describe_calendar(expression: str) -> str:
    """Plain English for an OnCalendar expression, for the schedule column."""
    expression = expression.strip()
    if expression in {"*-*-* *:17:00", "*-*-* *:17:00 UTC"}:
        return "every hour at 17 minutes past, plus up to 6 minutes of jitter"
    match = re.match(r"\*-\*-\* (\d{2}):(\d{2}):\d{2}(?: (\w+))?$", expression)
    if match:
        zone = match.group(3) or "local"
        return f"once a day at {match.group(1)}:{match.group(2)} {zone}"
    match = re.match(r"\*-\*-\* \*:(\d{2}):\d{2}", expression)
    if match:
        return f"every hour at {int(match.group(1))} minutes past"
    return expression
