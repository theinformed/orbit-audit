#!/usr/bin/env python3
"""Let the operations page choose how often the orbit archive is rebuilt.

THE PROBLEM THIS SOLVES, AND THE ONE IT MUST NOT CREATE
-------------------------------------------------------
Sean asked to set the orbit-history rebuild cadence from the operations page.
That page is static HTML: it is generated on bigmem, rsynced to the VPS by
``pipeline/publish_vps.sh``, and served by Caddy behind ``forward_auth`` at
``/space/ops``. A static page cannot change a systemd timer on a machine three
thousand miles away, and nothing on the VPS should ever be able to.

So the flow is deliberately one-way and asymmetric:

    browser  --PUT-->  a file on the VPS whose NAME is the chosen cadence
    bigmem   --pull--> that file, on the publish cycle it already runs
    bigmem   --reads-> the name, validates it AGAIN, and edits its own systemd

**The VPS never executes anything on bigmem's behalf.** It holds a request. The
only thing that touches bigmem's systemd is a program on bigmem, and that
program does not trust the request: ``apply()`` re-checks the value against
``CADENCES`` before doing anything, because "the endpoint already validated it"
is how a validated endpoint becomes the only validation.

WHY A FILENAME AND NOT A FILE'S CONTENTS
----------------------------------------
The request file's body is never read. Not parsed, not logged, not echoed. The
whole of the operator's input is *which* of a fixed set of filenames exists,
and that set is written here in Python. There is no path to interpolate, no
string to expand, no shell to reach. A request for a cadence this file does not
name is not an error to be handled — it is a file that is skipped, counted, and
shown on the page as rejected.

That matters more than usual here. This ultimately edits a systemd unit on
Sean's personal machine.

REQUESTS ARE DESIRED STATE, NOT COMMANDS
----------------------------------------
The reconciler is idempotent because it compares desired against live and does
nothing when they match, not because it deletes anything after acting. That is
what makes it safe to run every five minutes forever, and it means the request
survives the ``rsync --delete`` pull that brings it over.

**No request at all means the repository default**, read from
``deploy/systemd/orbit-release.timer``. Removing the request on the VPS is
therefore the escape hatch, and the repo file stays meaningful rather than
becoming a fossil that the live system silently diverged from years ago.

THE INGEST COLLISION, WHICH IS WHY THE OPTIONS ARE NOT JUST NUMBERS
--------------------------------------------------------------------
``deploy/systemd/orbit-release.timer`` explains that 07:25 UTC is chosen to
clear the hourly element ingest, which runs at :17 plus up to six minutes of
jitter, and that a rebuild takes 32–45 minutes. From :25 it lands by about :10,
ahead of the next :17.

**Hourly cannot clear it.** A 32–45 minute job on a one-hour period occupies
most of every hour; there is no start minute from which it finishes before the
next ingest begins. The old hourly setting at :42 cleared the ingest it read
FROM and then overlapped the next one. That is not a reason to withhold the
option — Sean is moving to an unlimited home connection and may well want
hourly rebuilds again — but the page says it plainly next to the button rather
than letting someone find out from a lock-contention incident. ``clears_ingest``
is that fact, per option, and it is displayed, not enforced.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]

#: The repository's copy of the unit. The DEFAULT, and the thing the page
#: compares the live timer against so a silent divergence is visible.
REPO_TIMER = ROOT / "deploy" / "systemd" / "orbit-release.timer"

#: Where the pulled request files land on bigmem. Filled by the rsync pull in
#: pipeline/publish_vps.sh; see the hand-over notes for the VPS-side endpoint.
REQUEST_DIR = ROOT / "runtime" / "cadence-requests"
# Where a DELIBERATE pause is declared. Same contract as REQUEST_DIR: only the
# filename is read, never the contents.
#
#   <unit>--until--<YYYYMMDDTHHMMZ>.pause
#   e.g. orbit-release.timer--until--20260904T1400Z.pause
#
# The expiry is the point. A pause with no end is the failure it is meant to
# prevent, so there is no way to write one.
PAUSE_DIR = ROOT / "runtime" / "timer-pauses"
PAUSE_NAME = re.compile(
    r"^(?P<unit>[A-Za-z0-9@_.-]+\.timer)--until--"
    r"(?P<stamp>\d{8}T\d{4}Z)\.pause$"
)

#: Written by the reconciler, which runs as root. Deliberately NOT inside the
#: project tree: a root process writing into a uid-1000 checkout is how file
#: ownership quietly breaks everything else that reads it.
APPLIED_LOG = Path("/var/lib/space-explorer-cadence/applied.jsonl")

SYSTEMD_DIR = Path("/etc/systemd/system")
UNIT = "orbit-release.timer"
DROPIN_NAME = "50-ops-page-cadence.conf"

#: The one unit this program is allowed to touch, as a literal. Not a
#: parameter, not derived from anything an operator can influence.
DROPIN_HEADER = (
    "# Written by ops/cadence.py from a request made on the operations page.\n"
    "# Do not edit by hand: the reconciler rewrites this file whenever the\n"
    "# request and the live timer disagree. The repository default lives in\n"
    "# deploy/systemd/orbit-release.timer; deleting the request on the VPS\n"
    "# removes this drop-in and restores it.\n"
)


@dataclass(frozen=True)
class Cadence:
    """One allowed option. The ONLY things an operator can choose between."""

    key: str
    label: str
    on_calendar: str
    randomized_delay_sec: int
    runs_per_day: float
    clears_ingest: bool
    note: str

    @property
    def runs_per_month(self) -> float:
        """A 30-day month. Stated rather than 30.44, so the arithmetic on the
        page is reproducible by hand."""
        return self.runs_per_day * 30


#: THE ALLOW-LIST. Nothing outside this dictionary can be requested, applied,
#: or rendered. Adding an option is a code change with a test behind it.
CADENCES: dict[str, Cadence] = {
    "hourly": Cadence(
        key="hourly",
        label="Hourly, at :42",
        on_calendar="*-*-* *:42:00",
        randomized_delay_sec=300,
        runs_per_day=24,
        clears_ingest=False,
        note="What ran until 2026-08-08. A rebuild takes 32-45 minutes, so at an "
             "hourly period it overlaps the next element ingest at :17-:23 no matter "
             "which minute it starts. Safe only because the archive reader yields; "
             "the schedule is not what protects it.",
    ),
    "every-2h": Cadence(
        key="every-2h",
        label="Every 2 hours, at :25",
        on_calendar="*-*-* 00/2:25:00 UTC",
        randomized_delay_sec=120,
        runs_per_day=12,
        clears_ingest=True,
        note="The default since 2026-08-18, when the pass stopped being one run. A full "
             "sweep of 181.3 M element sets is about 6 h 40 m of reading, so the job now "
             "works to a wall-clock budget, checkpoints and continues on the next firing - "
             "roughly eleven runs to a sweep. RUN frequency is no longer SHIP frequency: "
             "this is how often it makes progress, not how often it publishes. Starts at "
             ":25 and yields well before the :17 ingest.",
    ),
    "every-4h": Cadence(
        key="every-4h",
        label="Every 4 hours, at :25",
        on_calendar="*-*-* 03,07,11,15,19,23:25:00 UTC",
        randomized_delay_sec=120,
        runs_per_day=6,
        clears_ingest=True,
        note="Starts at :25 and lands by about :10, ahead of the :17 ingest.",
    ),
    "every-6h": Cadence(
        key="every-6h",
        label="Every 6 hours, at :25",
        on_calendar="*-*-* 01,07,13,19:25:00 UTC",
        randomized_delay_sec=120,
        runs_per_day=4,
        clears_ingest=True,
        note="Starts at :25 and lands by about :10, ahead of the :17 ingest.",
    ),
    "every-12h": Cadence(
        key="every-12h",
        label="Twice a day, 07:25 and 19:25 UTC",
        on_calendar="*-*-* 07,19:25:00 UTC",
        randomized_delay_sec=120,
        runs_per_day=2,
        clears_ingest=True,
        note="Starts at :25 and lands by about :10, ahead of the :17 ingest.",
    ),
    "daily": Cadence(
        key="daily",
        label="Once a day, 07:25 UTC",
        on_calendar="*-*-* 07:25:00 UTC",
        randomized_delay_sec=120,
        runs_per_day=1,
        clears_ingest=True,
        note="The repository default since 2026-08-08. 03:25 local on bigmem, which "
             "is quiet, and clear of the :17 ingest.",
    ),
    "weekly": Cadence(
        key="weekly",
        label="Once a week, Sunday 07:25 UTC",
        on_calendar="Sun *-*-* 07:25:00 UTC",
        randomized_delay_sec=120,
        runs_per_day=1 / 7,
        clears_ingest=True,
        note="The archive is a months-long record. A weekly rebuild means a "
             "manoeuvre shows up within the week.",
    ),
}

#: What the repository ships. Used when there is no request at all, and as the
#: thing the live timer is checked against.
# Was "daily" until 2026-08-18. A daily firing can no longer finish a sweep at
# all: the pass checkpoints on a budget and needs about eleven runs, so daily
# would leave the artifacts permanently one incomplete sweep behind.
DEFAULT_KEY = "every-2h"


def allowed(value: str | None) -> bool:
    """Membership in the allow-list. The whole of the input validation."""
    return isinstance(value, str) and value in CADENCES


# ---------------------------------------------------------------------------
# Reading what is actually configured, from the files that actually configure it
# ---------------------------------------------------------------------------

# `[ \t]` and not `\s`, deliberately. `\s` matches a newline, so a greedy `\s*`
# after the `=` walks off the end of an EMPTY `OnCalendar=` line and swallows
# the next line whole -- which made the reset directive read as a schedule of
# "OnCalendar=*-*-* *:42:00" and the real schedule vanish. Caught by
# tests/test_cadence.TheDropInIsBuiltFromConstantsOnly.
_ON_CALENDAR = re.compile(r"^[ \t]*OnCalendar[ \t]*=[ \t]*(.*?)[ \t]*$", re.M)


def calendars_in(text: str) -> list[str]:
    """Every non-empty OnCalendar= in a unit file, in order.

    An empty ``OnCalendar=`` is systemd's reset directive, so it clears
    everything collected so far rather than being one more entry. Getting that
    backwards would make a drop-in look like it had ADDED a schedule to the
    default rather than replaced it, and the page would report two cadences
    where one is running.
    """
    out: list[str] = []
    for value in _ON_CALENDAR.findall(text):
        if value == "":
            out.clear()
        else:
            out.append(value)
    return out


def repo_default() -> tuple[str | None, list[str]]:
    """The cadence the repository file expresses, and its raw OnCalendar lines.

    Returns ``(None, lines)`` when the file says something no option in the
    allow-list says. That is not an error — someone may have hand-edited the
    unit — but the page must show it as "the repository default is not one of
    the options on this page" instead of silently claiming it is ``daily``.
    """
    try:
        text = REPO_TIMER.read_text(encoding="utf-8")
    except OSError:
        return None, []
    lines = calendars_in(text)
    for key, cadence in CADENCES.items():
        if lines == [cadence.on_calendar]:
            return key, lines
    return None, lines


def key_for_calendars(lines: Sequence[str]) -> str | None:
    """Which allow-list entry, if any, a set of OnCalendar lines corresponds to."""
    for key, cadence in CADENCES.items():
        if list(lines) == [cadence.on_calendar]:
            return key
    return None


def live_calendars(unit_facts: dict | None) -> list[str]:
    """The schedule systemd itself reports, from ``TimersCalendar``.

    Read from systemd's own parse rather than from any file, for the same
    reason ops/watchdog.py reads retention windows out of the publish script:
    a page that reports what a file says while a different thing is running is
    worse than a page that reports nothing.
    """
    if not unit_facts:
        return []
    raw = unit_facts.get("TimersCalendar") or ""
    # systemd prints e.g. `{ OnCalendar=*-*-* 07:25:00 ; next_elapse=... }`,
    # repeated per entry and joined with spaces by ops/watchdog.unit_facts.
    return [match.strip() for match in re.findall(r"OnCalendar=([^;}]+)", raw)]


def unit_facts(unit: str = UNIT) -> dict | None:
    """systemctl's own facts. Never a judgement, just the fields."""
    try:
        done = subprocess.run(
            ["systemctl", "show", unit, "--no-pager",
             "--property=TimersCalendar", "--property=UnitFileState",
             "--property=ActiveState", "--property=NextElapseUSecRealtime",
             "--property=DropInPaths"],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    out: dict[str, str] = {}
    for line in done.stdout.splitlines():
        key, _, value = line.partition("=")
        out[key] = (out[key] + " " + value) if key in out else value
    return out or None


# ---------------------------------------------------------------------------
# The request, as pulled from the VPS
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Request:
    key: str | None
    at: float | None
    rejected: tuple[str, ...] = ()
    ambiguous: tuple[str, ...] = ()

    @property
    def present(self) -> bool:
        return self.key is not None


def read_pause(unit: str, *, directory: Path | None = None, now: float | None = None):
    """The unexpired pause for `unit`, if an operator declared one.

    Returns the expiry as an epoch float, or None. Only the FILENAME is parsed;
    the file is never opened, so a pause cannot smuggle in anything this program
    will act on -- the same property read_request() relies on.

    An EXPIRED pause deliberately returns None. That is the whole mechanism: a
    lane someone paused and forgot comes back as a finding by itself, rather
    than staying quietly dead until a human happens to ask.
    """
    import calendar  # noqa: PLC0415 - keeps the module import-light
    # Resolved at CALL time, not bound as a default. A default argument is
    # evaluated once when the function is defined, so `directory=PAUSE_DIR`
    # would freeze the module-level value and quietly ignore any later change
    # to it -- which made this untestable and would have made it wrong under a
    # reload. Caught by its own test on the first run.
    directory = PAUSE_DIR if directory is None else directory
    stamp_now = time.time() if now is None else now
    latest: float | None = None
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return None
    for name in names:
        match = PAUSE_NAME.match(name)
        if not match or match.group("unit") != unit:
            continue
        try:
            parsed = time.strptime(match.group("stamp"), "%Y%m%dT%H%MZ")
        except ValueError:
            continue
        until = calendar.timegm(parsed)
        if until > stamp_now and (latest is None or until > latest):
            latest = until
    return latest


def read_request(directory: Path = REQUEST_DIR) -> Request:
    """The newest valid request in the directory, plus what was thrown away.

    Only the filename is consulted. The file's contents are never opened, so
    there is nothing an operator can put inside one that this program will act
    on, log, or render.
    """
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return Request(key=None, at=None)
    valid: list[tuple[float, str]] = []
    rejected: list[str] = []
    for name in names:
        full = directory / name
        if not full.is_file():
            continue
        if not allowed(name):
            rejected.append(name)
            continue
        try:
            valid.append((full.stat().st_mtime, name))
        except OSError:
            continue
    if not valid:
        return Request(key=None, at=None, rejected=tuple(rejected))
    newest = max(stamp for stamp, _ in valid)
    # WebDAV stamps a PUT to whole seconds, so two clicks inside one second are
    # genuinely indistinguishable. Picking one would be picking at random and
    # then acting on it, on a systemd timer, on Sean's own machine. An
    # ambiguous request is therefore no request: the current cadence stands and
    # the page says why.
    tied = sorted(name for stamp, name in valid if stamp == newest)
    if len(tied) > 1:
        return Request(key=None, at=newest, rejected=tuple(rejected),
                       ambiguous=tuple(tied))
    return Request(key=tied[0], at=newest, rejected=tuple(rejected))


# ---------------------------------------------------------------------------
# Applying it. The only part that writes outside this project's own tree.
# ---------------------------------------------------------------------------

def dropin_text(cadence: Cadence) -> str:
    """The drop-in, built entirely from this file's own constants.

    Nothing an operator supplies reaches this string. ``cadence`` came out of
    ``CADENCES`` by key lookup, so every character below was written here.
    """
    return (
        f"{DROPIN_HEADER}"
        f"# cadence: {cadence.key}\n"
        f"[Timer]\n"
        f"OnCalendar=\n"
        f"OnCalendar={cadence.on_calendar}\n"
        f"RandomizedDelaySec={cadence.randomized_delay_sec}\n"
    )


def _log(entry: dict, log_path: Path) -> None:
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")
        os.chmod(log_path, 0o644)
    except OSError:
        pass


def read_applied(log_path: Path = APPLIED_LOG, limit: int = 50) -> list[dict]:
    """What the reconciler has changed, newest last. Shown on the page."""
    try:
        lines = log_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def reconcile(*, request_dir: Path = REQUEST_DIR, systemd_dir: Path = SYSTEMD_DIR,
              log_path: Path = APPLIED_LOG, now: float | None = None,
              dry_run: bool = False, reload: bool = True) -> dict:
    """Make the live timer match the request. Idempotent by comparison.

    The order here is the security property. The value is validated against
    ``CADENCES`` a second time, on bigmem, after it has crossed the network —
    ``read_request`` already filtered on the same list, and this checks again
    anyway, because an endpoint that validated is not a validation this program
    performed.
    """
    moment = float(now if now is not None else time.time())
    request = read_request(request_dir)
    default_key, _ = repo_default()

    # An ambiguous request is NOT an absent one. Absent means "go back to the
    # repository default" and is a real change; ambiguous means "we could not
    # tell what was asked for", and reverting the cadence because two files
    # share a timestamp would be the worst possible reading of that.
    if request.ambiguous:
        return {"action": "refused",
                "reason": "two requests share the newest timestamp and cannot be "
                          f"ordered: {', '.join(request.ambiguous)}. Nothing changed.",
                "requested": None, "ambiguous": list(request.ambiguous),
                "rejected": list(request.rejected)}

    desired_key = request.key if request.present else (default_key or DEFAULT_KEY)
    # Second validation, on bigmem, after the value crossed a network.
    if not allowed(desired_key):
        return {"action": "refused", "reason": f"{desired_key!r} is not an allowed cadence",
                "requested": request.key, "rejected": list(request.rejected)}
    cadence = CADENCES[desired_key]

    dropin_dir = systemd_dir / f"{UNIT}.d"
    dropin = dropin_dir / DROPIN_NAME
    wanted = dropin_text(cadence)

    #: No request means the repository file is the authority again, so the
    #: drop-in must go rather than linger as an override that agrees by
    #: coincidence.
    if not request.present:
        if not dropin.exists():
            return {"action": "none", "reason": "no request; the repository default is live",
                    "cadence": desired_key, "rejected": list(request.rejected)}
        if dry_run:
            return {"action": "would-remove", "cadence": desired_key,
                    "path": str(dropin), "rejected": list(request.rejected)}
        try:
            dropin.unlink()
        except OSError as error:
            return {"action": "failed", "reason": str(error), "path": str(dropin)}
        _reload(reload)
        entry = {"at": moment, "action": "removed", "cadence": desired_key,
                 "onCalendar": cadence.on_calendar,
                 "reason": "the request was withdrawn; back to the repository default"}
        _log(entry, log_path)
        return {**entry, "rejected": list(request.rejected)}

    try:
        current = dropin.read_text(encoding="utf-8")
    except OSError:
        current = None
    if current == wanted:
        return {"action": "none", "reason": "the live timer already matches the request",
                "cadence": desired_key, "onCalendar": cadence.on_calendar,
                "rejected": list(request.rejected)}

    if dry_run:
        return {"action": "would-apply", "cadence": desired_key,
                "onCalendar": cadence.on_calendar, "path": str(dropin),
                "rejected": list(request.rejected)}

    try:
        dropin_dir.mkdir(parents=True, exist_ok=True)
        temporary = dropin.with_suffix(".conf.next")
        temporary.write_text(wanted, encoding="utf-8")
        os.chmod(temporary, 0o644)
        temporary.replace(dropin)
    except OSError as error:
        return {"action": "failed", "reason": str(error), "path": str(dropin)}

    reloaded = _reload(reload)
    entry = {
        "at": moment,
        "action": "applied",
        "cadence": desired_key,
        "onCalendar": cadence.on_calendar,
        "randomizedDelaySec": cadence.randomized_delay_sec,
        "clearsIngest": cadence.clears_ingest,
        "requestedAt": request.at,
        "previous": key_for_calendars(calendars_in(current)) if current else None,
        "reloaded": reloaded,
        "reason": "the operations page requested this cadence",
    }
    _log(entry, log_path)
    return {**entry, "rejected": list(request.rejected)}


def _reload(enabled: bool) -> bool:
    if not enabled:
        return False
    for command in (["systemctl", "daemon-reload"],
                    ["systemctl", "restart", UNIT]):
        try:
            done = subprocess.run(command, capture_output=True, text=True,
                                  timeout=60, check=False)
        except (OSError, subprocess.SubprocessError):
            return False
        if done.returncode != 0:
            return False
    return True


# ---------------------------------------------------------------------------
# What the page needs
# ---------------------------------------------------------------------------

def status(*, request_dir: Path = REQUEST_DIR, facts: dict | None = None,
           log_path: Path = APPLIED_LOG, now: float | None = None,
           pause_dir: Path | None = None) -> dict:
    """Requested, repository default, and what systemd is actually running.

    ``diverged`` is true when the live schedule is not what the repository file
    says AND no request explains why. That is the case the brief cares about:
    a live timer quietly drifting away from the file that is supposed to define
    it, with nobody having asked for the drift.
    """
    request = read_request(request_dir)
    # KEEP THE DIFFERENCE between "systemd says no" and "we could not ask".
    # `facts or {}` below turns an unreadable systemd into a confident set of
    # Falses, and every False then reads as a clean bill of health. That is
    # absence of evidence rendered as an all-clear, which is the one answer a
    # monitor must never give.
    facts_read = bool(facts)
    facts = facts or {}
    active_state = facts.get("ActiveState")
    # `enabled` and `enabled-runtime` both mean systemd intends to run it; a
    # `static` or `masked` unit is not a lane anybody expects to fire.
    enabled = str(facts.get("UnitFileState") or "").startswith("enabled")
    running = active_state == "active"
    paused_until = read_pause(UNIT, directory=pause_dir, now=now)
    default_key, default_lines = repo_default()
    live = live_calendars(facts)
    live_key = key_for_calendars(live)
    expected = request.key if request.present else default_key
    explained = bool(live) and live_key is not None and live_key == expected
    return {
        "options": [CADENCES[key] for key in CADENCES],
        "requested": request.key,
        "requestedAt": request.at,
        "rejected": list(request.rejected),
        "ambiguous": list(request.ambiguous),
        "repoDefault": default_key,
        "repoCalendars": default_lines,
        "live": live,
        "liveKey": live_key,
        "expected": expected,
        "diverged": bool(live) and not explained,
        "measurable": bool(live),
        "applied": read_applied(log_path),
        # RUNNING STATE, which the schedule comparison above cannot see.
        # A stopped-but-enabled timer reports a perfect TimersCalendar, so every
        # field above says it is healthy while it will never fire again.
        "activeState": active_state,
        "enabled": enabled,
        "running": running,
        "pausedUntil": paused_until,
        # The finding: enabled, not running, and nobody said so.
        #
        # KEPT AS IT WAS, because it is what the watchdog has always read and
        # its meaning is exact. It is also only ONE of the four ways this lane
        # stops firing, which is why the two fields below exist.
        "stoppedUnexplained": bool(enabled) and not running and paused_until is None,
        # THE LANE WILL NOT FIRE, whatever the reason, and nothing explains it.
        #
        # Measured 2026-09-08 against all four states: `stoppedUnexplained`
        # catches ENABLED-but-stopped and stays silent on `disable` and `mask`,
        # even though systemd reports both plainly. `systemctl disable` is
        # precisely what leaves "0 timers listed" -- the state this site was
        # actually sitting in while serving a four-day-old artifact. A monitor
        # that reports only the failure it was written for is not a monitor.
        "willNotFire": facts_read and not running and paused_until is None,
        # Which of the ways, in a word a reader can act on.
        "deadReason": (
            None
            if not facts_read or running or paused_until is not None
            else "masked" if str(facts.get("UnitFileState") or "") == "masked"
            else "disabled" if not enabled
            else "stopped"
        ),
        # THE THIRD STATE. Not "healthy" and not "broken": unknown, because
        # systemd could not be read at all. Drawn as a labelled gap, never as a
        # zero and never as a green tick.
        "stateUnknown": not facts_read,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Orbit-history rebuild cadence.")
    parser.add_argument("--request-dir", type=Path, default=REQUEST_DIR)
    parser.add_argument("--systemd-dir", type=Path, default=SYSTEMD_DIR)
    parser.add_argument("--log", type=Path, default=APPLIED_LOG)
    parser.add_argument("--dry-run", action="store_true",
                        help="say what would change and change nothing")
    parser.add_argument("--no-reload", action="store_true",
                        help="write the drop-in but do not touch systemd")
    parser.add_argument("--status", action="store_true",
                        help="print requested / default / live as JSON and exit")
    args = parser.parse_args(argv)

    if args.status:
        state = status(request_dir=args.request_dir, facts=unit_facts(),
                       log_path=args.log)
        print(json.dumps({**state, "options": [c.key for c in state["options"]]},
                         indent=2, default=str))
        return 0

    result = reconcile(request_dir=args.request_dir, systemd_dir=args.systemd_dir,
                       log_path=args.log, dry_run=args.dry_run,
                       reload=not args.no_reload)
    print(json.dumps(result, indent=2, default=str))
    if result["action"] == "failed":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
